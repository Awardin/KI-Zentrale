"""Stufe 8 (16.10.2026): zweiter ComfyUI-Prozess – Erkennung, Verbraucher, Start, Beenden, Entladen, Platzgründe."""
import copy
import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung, norm  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class ZweiterProzess(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.comfy
        py = os.path.join(self.e['comfy_ordner'], '.venv', 'Scripts', 'python.exe')
        # 10/11: Prozess 1 (Starter + Python), 20/21: Prozess 2, 30: fremdes Programm
        self.procs = {10: (0, 'python.exe'), 11: (10, 'python.exe'), 20: (0, 'python.exe'), 21: (20, 'python.exe'),
                      30: (0, 'fremd.exe')}
        eins = 'main.py --listen 127.0.0.1 --port 8188 --cuda-device 0,1 --default-device 0'
        zwei = 'main.py --listen 127.0.0.1 --port 8189 --cuda-device 1'
        self.infos = {10: (py, eins), 11: (sys.executable, eins), 20: (py, zwei), 21: (sys.executable, zwei),
                      30: (r'C:\Fremd\fremd.exe', 'main.py --port 8189')}
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}

    def test_konfiguration(self):
        self.assertEqual((self.e['comfy_port_2'], self.e['comfy_karte_2']), (8189, 1))
        self.assertEqual(self.erf.comfy2_port, 8189)

    def test_einordnen_trennt_die_prozesse(self):
        self.assertEqual(self.erf.einordnen(11, self.procs), ('bild-video', self.e['name']))
        self.assertEqual(self.erf.einordnen(21, self.procs), ('bild-video-2', self.e['comfy_name_2']))
        self.assertEqual(self.erf.einordnen(30, self.procs)[0], 'andere')

    def test_verbraucher_je_prozess_mit_eigenem_entladen(self):
        dienste = {'comfy': {'laeuft': True, 'auftraege_laufend': 0}, 'comfy2': {'laeuft': True, 'auftraege_laufend': 1}}
        v = self.erf._verbraucher(self.procs, [], {0: {11: 9000}, 1: {21: 8000}},
                                  {'erreichbar': True, 'geladen': []}, dienste)
        v = {x['schluessel']: x for x in v}
        self.assertEqual(v['bild-video']['mib_je_karte'], {0: 9000})
        self.assertEqual(v['bild-video-2']['mib_je_karte'], {1: 8000})
        self.assertEqual(v['bild-video']['schritt']['id'], 'freigeben:bild-video')
        self.assertEqual(v['bild-video-2']['schritt']['id'], 'freigeben:bild-video-2')
        self.assertIn('läuft gerade ein Auftrag', v['bild-video-2']['blockiert'])
        self.assertIsNone(v['bild-video']['blockiert'])


class Aktionen2(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        self.e = next(e for e in self.cfg['eintraege'] if e['art'] == 'comfy')
        self.erf = Mock(comfy=self.e, comfy_ordner=norm(self.e['comfy_ordner']), comfy2_port=8189,
                        comfy2_name=self.e['comfy_name_2'])
        self.akt = Aktionen(self.cfg, self.erf, 'logs', Mock())
        for name in ('starte_losgeloest', 'beenden', 'prozesse', 'lauschende_ports'):
            p = patch('gemeinsam.winapi.' + name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.starte_losgeloest.return_value.poll.return_value = None
        for name, wert in (('os.path.exists', True), ('os.makedirs', None)):
            p = patch('zentrale.aktionen.' + name, return_value=wert)
            p.start()
            self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.http_erreichbar', return_value=True)
        p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.http_json')
        self.http_json = p.start()
        self.addCleanup(p.stop)

    def dienste(self, eins=None, zwei=None):
        leer = {'pid': None, 'laeuft': False, 'fremd': None, 'auftraege_laufend': 0, 'auftraege_wartend': 0}
        return {'dienste': {'comfy': dict(leer, **(eins or {})), 'comfy2': dict(leer, **(zwei or {})),
                            'studio': {'pid': None, 'laeuft': False, 'fremd': None}}, 'procs': {}}

    def test_start_beider_prozesse(self):
        self.erf.messen.return_value = self.dienste()
        self.akt._comfy_starten(self.e)
        argv = [c.args[0] for c in self.starte_losgeloest.call_args_list]
        self.assertEqual(len(argv), 2)
        self.assertIn('0,1', argv[0])
        zwei = argv[1]
        self.assertEqual(zwei[zwei.index('--port') + 1], '8189')
        self.assertEqual(zwei[zwei.index('--cuda-device') + 1], '1')
        self.assertEqual(zwei[zwei.index('--output-directory') + 1], self.e['ausgabe_ordner'])
        self.assertTrue(zwei[zwei.index('--temp-directory') + 1].endswith('temp-2'))
        self.assertTrue(zwei[zwei.index('--user-directory') + 1].endswith('user-2'))
        self.assertNotIn('--default-device', zwei)

    def test_laufender_erster_prozess_startet_nur_den_zweiten_nach(self):
        self.erf.messen.return_value = self.dienste(eins={'pid': 5, 'laeuft': True})
        self.akt._comfy_starten(self.e)
        self.assertEqual(len(self.starte_losgeloest.call_args_list), 1)
        self.assertIn('8189', self.starte_losgeloest.call_args.args[0])

    def test_fremder_port_des_zweiten_prozesses(self):
        self.erf.messen.return_value = self.dienste(zwei={'fremd': 'Python'})
        with self.assertRaisesRegex(Fehler, 'Port 8189'):
            self.akt._comfy_starten(self.e)
        self.starte_losgeloest.assert_not_called()

    def test_beenden_wartet_auf_auftraege_in_beiden_und_beendet_beide(self):
        self.erf.messen.return_value = self.dienste(eins={'pid': 5, 'laeuft': True}, zwei={'pid': 6, 'auftraege_laufend': 1})
        with self.assertRaisesRegex(Fehler, 'läuft gerade ein Auftrag'):
            self.akt._comfy_stoppen(self.e, False)
        self.lauschende_ports.return_value = []
        with patch.object(self.akt, '_comfy_beenden') as beenden:
            self.akt._comfy_stoppen(self.e, True)
        self.assertEqual([c.args[0] for c in beenden.call_args_list], [5, 6])

    def test_entladen_je_prozess(self):
        self.erf.messen.return_value = self.dienste(eins={'laeuft': True}, zwei={'laeuft': True})
        self.assertIn('ComfyUI 2', self.akt.schritt('freigeben:bild-video-2'))
        self.assertEqual(self.http_json.call_args.args[0], 'http://127.0.0.1:8189/free')
        self.akt.schritt('freigeben:bild-video')
        self.assertEqual(self.http_json.call_args.args[0], 'http://127.0.0.1:8188/free')


class Platzgruende(unittest.TestCase):
    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = dict(KONFIG, eintraege=[])
        self.z._lock, self.z._platz_lock = threading.Lock(), threading.Lock()
        self.z.anmeldungen, self.z.aktion, self.z.verlauf = {}, None, []
        self.z.melden = Mock()
        self.z._uebernehmen = Mock()
        self.z._kurzname = lambda i: f'Karte {i}'
        self.roh = {'karten': [{'index': 0, 'gesamt': 24576, 'belegt': 1000, 'last': 0},
                               {'index': 1, 'gesamt': 24576, 'belegt': 1000, 'last': 0}],
                    'verbraucher': [], 'dienste': {'comfy': {'auftraege_laufend': 0}, 'comfy2': {'auftraege_laufend': 1}}}
        self.z._aktuell = Mock(return_value=self.roh)

    def test_auftrag_im_zweiten_prozess_ohne_anmeldung_ist_ein_grund(self):
        code, a = self.z.platz({})
        self.assertEqual(a['gruende'], ['Im zweiten ComfyUI-Prozess läuft gerade ein Auftrag.'])
        # Mit Studio-Anmeldung für genau diesen Prozess ist er gedeckt – die des ersten Prozesses reicht nicht.
        self.z.anmeldungen['x'] = {'id': 'x', 'zweck': 'Bild', 'bedarf_mib': {}, 'schluessel': 'bild-video',
                                   'seit': time.time(), 'bis': time.time() + 60}
        self.assertEqual(self.z.platz({})[1]['gruende'], ['Im zweiten ComfyUI-Prozess läuft gerade ein Auftrag.'])
        self.z.anmeldungen['y'] = dict(self.z.anmeldungen['x'], id='y', schluessel='bild-video-2')
        self.assertEqual(self.z.platz({})[1]['gruende'], [])

    def test_studio_anmeldung_des_zweiten_prozesses_ohne_bedarf_und_mit_basis(self):
        self.roh['dienste']['comfy2']['auftraege_laufend'] = 0
        self.roh['verbraucher'] = [{'schluessel': 'bild-video-2', 'name': 'ComfyUI 2', 'farbe': '#B1407C',
                                    'mib_je_karte': {1: 4000}}]
        code, a = self.z.platz({'reservieren': True, 'zweck': 'Bild (Studio)', 'schluessel': 'bild-video-2',
                                'bedarf_mib': {'1': 9000}})
        self.assertEqual(code, 200)
        r = self.z.anmeldungen[a['anmeldung']['id']]
        self.assertEqual((r['schluessel'], r['basis']), ('bild-video-2', {1: 4000}))
        self.assertEqual(self.z.platz({'reservieren': True, 'zweck': 'Bild (Studio)', 'schluessel': 'bild-video-2',
                                       'bedarf_mib': {}})[0], 200)


if __name__ == '__main__':
    unittest.main()
