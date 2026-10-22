"""Stufe 8 (16.10.2026): weitere ComfyUI-Prozesse – Erkennung, Verbraucher, Start, Beenden, Entladen, Platzgründe.

Seit 22.10.2026 ist Prozess 3 auf der RTX 3080 (Nebenkarte, keine Videos) dabei."""
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


class WeitereProzesse(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.comfy
        py = os.path.join(self.e['comfy_ordner'], '.venv', 'Scripts', 'python.exe')
        # 10/11: Prozess 1 (Starter + Python), 20/21: Prozess 2, 40/41: Prozess 3, 30: fremdes Programm
        self.procs = {10: (0, 'python.exe'), 11: (10, 'python.exe'), 20: (0, 'python.exe'), 21: (20, 'python.exe'),
                      40: (0, 'python.exe'), 41: (40, 'python.exe'), 30: (0, 'fremd.exe')}
        eins = 'main.py --listen 127.0.0.1 --port 8188 --cuda-device 0,1 --default-device 0'
        zwei = 'main.py --listen 127.0.0.1 --port 8189 --cuda-device 1'
        drei = 'main.py --listen 127.0.0.1 --port 8190 --cuda-device 2'
        self.infos = {10: (py, eins), 11: (sys.executable, eins), 20: (py, zwei), 21: (sys.executable, zwei),
                      40: (py, drei), 41: (sys.executable, drei),
                      30: (r'C:\Fremd\fremd.exe', 'main.py --port 8190')}
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}

    def test_konfiguration(self):
        self.assertEqual([(w['nr'], w['port'], w['karte']) for w in self.e['comfy_weitere']],
                         [(2, 8189, 1), (3, 8190, 2)])
        self.assertEqual(self.e['comfy_karten'], [0, 1])
        self.assertEqual([(w['nr'], w['port'], w['name'], w.get('videos', True)) for w in self.erf.comfy_weitere],
                         [(2, 8189, 'ComfyUI 2 (Suprim)', True), (3, 8190, 'ComfyUI 3 (RTX 3080)', False)])

    def test_einordnen_trennt_die_prozesse(self):
        self.assertEqual(self.erf.einordnen(11, self.procs), ('bild-video', self.e['name']))
        self.assertEqual(self.erf.einordnen(21, self.procs), ('bild-video-2', 'ComfyUI 2 (Suprim)'))
        self.assertEqual(self.erf.einordnen(41, self.procs), ('bild-video-3', 'ComfyUI 3 (RTX 3080)'))
        self.assertEqual(self.erf.einordnen(30, self.procs)[0], 'andere')

    def test_verbraucher_je_prozess_mit_eigenem_entladen(self):
        dienste = {'comfy': {'laeuft': True, 'auftraege_laufend': 0},
                   'comfy2': {'laeuft': True, 'auftraege_laufend': 0},
                   'comfy3': {'laeuft': True, 'auftraege_laufend': 0}}
        v = self.erf._verbraucher(self.procs, [], {0: {11: 9000}, 1: {21: 8000}, 2: {41: 7000}},
                                  {'erreichbar': True, 'geladen': []}, dienste)
        v = {x['schluessel']: x for x in v}
        self.assertEqual(v['bild-video']['mib_je_karte'], {0: 9000})
        self.assertEqual(v['bild-video-2']['mib_je_karte'], {1: 8000})
        self.assertEqual(v['bild-video-3']['mib_je_karte'], {2: 7000})
        self.assertEqual(v['bild-video']['schritt']['id'], 'freigeben:bild-video')
        self.assertEqual(v['bild-video-2']['schritt']['id'], 'freigeben:bild-video-2')
        self.assertEqual(v['bild-video-3']['schritt']['id'], 'freigeben:bild-video-3')
        dienste['comfy3']['auftraege_laufend'] = 1
        v = self.erf._verbraucher(self.procs, [], {2: {41: 7000}}, {'erreichbar': True, 'geladen': []}, dienste)
        self.assertIn('läuft gerade ein Auftrag', {x['schluessel']: x for x in v}['bild-video-3']['blockiert'])


class Aktionen3(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        self.e = next(e for e in self.cfg['eintraege'] if e['art'] == 'comfy')
        self.erf = Mock(comfy=self.e, comfy_ordner=norm(self.e['comfy_ordner']),
                        comfy_weitere=self.e['comfy_weitere'])
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

    def dienste(self, eins=None, zwei=None, drei=None):
        leer = {'pid': None, 'laeuft': False, 'fremd': None, 'auftraege_laufend': 0, 'auftraege_wartend': 0}
        return {'dienste': {'comfy': dict(leer, **(eins or {})), 'comfy2': dict(leer, **(zwei or {})),
                            'comfy3': dict(leer, **(drei or {})),
                            'studio': {'pid': None, 'laeuft': False, 'fremd': None}}, 'procs': {}}

    def test_start_aller_weiteren_prozesse(self):
        self.erf.messen.return_value = self.dienste()
        self.akt._comfy_starten(self.e)
        argv = [c.args[0] for c in self.starte_losgeloest.call_args_list]
        self.assertEqual(len(argv), 3)
        self.assertIn('0,1', argv[0])
        zwei, drei = argv[1], argv[2]
        self.assertEqual(zwei[zwei.index('--port') + 1], '8189')
        self.assertEqual(zwei[zwei.index('--cuda-device') + 1], '1')
        self.assertEqual(zwei[zwei.index('--output-directory') + 1], self.e['ausgabe_ordner'])
        self.assertTrue(zwei[zwei.index('--temp-directory') + 1].endswith('temp-2'))
        self.assertTrue(zwei[zwei.index('--user-directory') + 1].endswith('user-2'))
        self.assertNotIn('--default-device', zwei)
        self.assertTrue(self.starte_losgeloest.call_args_list[1].kwargs['log_basis'].endswith('comfyui-2'))
        # Prozess 3 (RTX 3080): Port 8190, Karte 2, eigene temp-/user-Ordner.
        self.assertEqual(drei[drei.index('--port') + 1], '8190')
        self.assertEqual(drei[drei.index('--cuda-device') + 1], '2')
        self.assertEqual(drei[drei.index('--output-directory') + 1], self.e['ausgabe_ordner'])
        self.assertTrue(drei[drei.index('--temp-directory') + 1].endswith('temp-3'))
        self.assertTrue(drei[drei.index('--user-directory') + 1].endswith('user-3'))
        self.assertNotIn('--default-device', drei)
        self.assertTrue(self.starte_losgeloest.call_args_list[2].kwargs['log_basis'].endswith('comfyui-3'))

    def test_start_nutzt_comfy_karten_fuer_cuda_device(self):
        # Prozess 1 sieht nur die Karten aus `comfy_karten`; ohne weitere Prozesse bleibt es bei einer Kommandozeile.
        e = dict(self.e, comfy_karten=[0], comfy_weitere=[])
        self.erf.messen.return_value = self.dienste()
        self.akt._comfy_starten(e)
        argv = self.starte_losgeloest.call_args.args[0]
        self.assertEqual(argv[argv.index('--cuda-device') + 1], '0')

    def test_laufender_erster_prozess_startet_die_weiteren_nach(self):
        self.erf.messen.return_value = self.dienste(eins={'pid': 5, 'laeuft': True})
        self.akt._comfy_starten(self.e)
        self.assertEqual(len(self.starte_losgeloest.call_args_list), 2)
        ports = [c.args[0][c.args[0].index('--port') + 1] for c in self.starte_losgeloest.call_args_list]
        self.assertEqual(ports, ['8189', '8190'])

    def test_fremder_port_eines_weiteren_prozesses(self):
        self.erf.messen.return_value = self.dienste(drei={'fremd': 'Python'})
        with self.assertRaisesRegex(Fehler, 'Port 8190'):
            self.akt._comfy_starten(self.e)
        self.starte_losgeloest.assert_not_called()

    def test_beenden_wartet_auf_auftraege_in_allen_und_beendet_alle(self):
        self.erf.messen.return_value = self.dienste(eins={'pid': 5, 'laeuft': True},
                                                    zwei={'pid': 6, 'auftraege_laufend': 1},
                                                    drei={'pid': 7, 'laeuft': True})
        with self.assertRaisesRegex(Fehler, 'läuft gerade ein Auftrag'):
            self.akt._comfy_stoppen(self.e, False)
        self.lauschende_ports.return_value = []
        with patch.object(self.akt, '_comfy_beenden') as beenden:
            self.akt._comfy_stoppen(self.e, True)
        self.assertEqual([c.args[0] for c in beenden.call_args_list], [5, 6, 7])

    def test_entladen_je_prozess(self):
        self.erf.messen.return_value = self.dienste(eins={'laeuft': True}, zwei={'laeuft': True},
                                                    drei={'laeuft': True})
        self.assertIn('ComfyUI 2 (Suprim)', self.akt.schritt('freigeben:bild-video-2'))
        self.assertEqual(self.http_json.call_args.args[0], 'http://127.0.0.1:8189/free')
        self.assertIn('ComfyUI 3 (RTX 3080)', self.akt.schritt('freigeben:bild-video-3'))
        self.assertEqual(self.http_json.call_args.args[0], 'http://127.0.0.1:8190/free')
        self.akt.schritt('freigeben:bild-video')
        self.assertEqual(self.http_json.call_args.args[0], 'http://127.0.0.1:8188/free')


class Platzgruende(unittest.TestCase):
    def setUp(self):
        self.comfy = next(e for e in KONFIG['eintraege'] if e['art'] == 'comfy')
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = dict(KONFIG, eintraege=[])
        self.z.erf = Mock(comfy_weitere=self.comfy['comfy_weitere'])
        self.z._lock, self.z._platz_lock = threading.Lock(), threading.Lock()
        self.z.anmeldungen, self.z.aktion, self.z.verlauf = {}, None, []
        self.z.melden = Mock()
        self.z._uebernehmen = Mock()
        self.z._kurzname = lambda i: f'Karte {i}'
        self.roh = {'karten': [{'index': 0, 'gesamt': 24576, 'belegt': 1000, 'last': 0},
                               {'index': 1, 'gesamt': 24576, 'belegt': 1000, 'last': 0},
                               {'index': 2, 'gesamt': 20480, 'belegt': 1000, 'last': 0}],
                    'verbraucher': [],
                    'dienste': {'comfy': {'auftraege_laufend': 0}, 'comfy2': {'auftraege_laufend': 0},
                                'comfy3': {'auftraege_laufend': 0}}}
        self.z._aktuell = Mock(return_value=self.roh)

    def test_auftrag_im_zweiten_prozess_ohne_anmeldung_ist_ein_grund(self):
        self.roh['dienste']['comfy2']['auftraege_laufend'] = 1
        code, a = self.z.platz({})
        self.assertEqual(a['gruende'], ['In ComfyUI 2 (Suprim) läuft gerade ein Auftrag.'])
        # Mit Studio-Anmeldung für genau diesen Prozess ist er gedeckt – die des ersten Prozesses reicht nicht.
        self.z.anmeldungen['x'] = {'id': 'x', 'zweck': 'Bild', 'bedarf_mib': {}, 'schluessel': 'bild-video',
                                   'seit': time.time(), 'bis': time.time() + 60}
        self.assertEqual(self.z.platz({})[1]['gruende'], ['In ComfyUI 2 (Suprim) läuft gerade ein Auftrag.'])
        self.z.anmeldungen['y'] = dict(self.z.anmeldungen['x'], id='y', schluessel='bild-video-2')
        self.assertEqual(self.z.platz({})[1]['gruende'], [])

    def test_auftrag_im_dritten_prozess_ohne_anmeldung_ist_ein_grund(self):
        self.roh['dienste']['comfy3']['auftraege_laufend'] = 1
        self.z.anmeldungen['x'] = {'id': 'x', 'zweck': 'Bild', 'bedarf_mib': {}, 'schluessel': 'bild-video-2',
                                   'seit': time.time(), 'bis': time.time() + 60}
        self.assertEqual(self.z.platz({})[1]['gruende'], ['In ComfyUI 3 (RTX 3080) läuft gerade ein Auftrag.'])
        self.z.anmeldungen['y'] = dict(self.z.anmeldungen['x'], id='y', schluessel='bild-video-3')
        self.assertEqual(self.z.platz({})[1]['gruende'], [])

    def test_studio_anmeldung_ohne_bedarf_und_mit_basis(self):
        self.roh['verbraucher'] = [{'schluessel': 'bild-video-3', 'name': 'ComfyUI 3 (RTX 3080)', 'farbe': '#B1407C',
                                    'mib_je_karte': {2: 4000}}]
        code, a = self.z.platz({'reservieren': True, 'zweck': 'Bild (Studio)', 'schluessel': 'bild-video-3',
                                'bedarf_mib': {'2': 9000}})
        self.assertEqual(code, 200)
        r = self.z.anmeldungen[a['anmeldung']['id']]
        self.assertEqual((r['schluessel'], r['basis']), ('bild-video-3', {2: 4000}))
        self.assertEqual(self.z.platz({'reservieren': True, 'zweck': 'Bild (Studio)', 'schluessel': 'bild-video-3',
                                       'bedarf_mib': {}})[0], 200)


class Zustandstexte(unittest.TestCase):
    def setUp(self):
        comfy = next(e for e in KONFIG['eintraege'] if e['art'] == 'comfy')
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = {'eintraege': [comfy]}
        self.z.erf = Mock(comfy_weitere=comfy['comfy_weitere'])
        self.z.erf.llamacpp, self.z.erf.polystrata, self.z.erf.python_dienst, self.z.erf.ollama_tags = {}, {}, {}, {}
        self.z.laufend = {}

    def dienste(self, laeuft=(True, True, True), pid=(1, 2, 3), auftraege=(0, 0, 0)):
        leer = {'pid': None, 'laeuft': False, 'fremd': None, 'auftraege_laufend': 0, 'auftraege_wartend': 0}
        werte = [dict(leer, pid=p, laeuft=l, auftraege_laufend=a) for p, l, a in zip(pid, laeuft, auftraege)]
        return {'dienste': {'comfy': werte[0], 'comfy2': werte[1], 'comfy3': werte[2],
                            'studio': {'pid': None, 'laeuft': False, 'fremd': None}}}

    def test_drei_prozesse_bereit(self):
        z = self.z._zustaende(self.dienste())
        self.assertEqual(z['bild-video']['zustand'], 'bereit')
        self.assertEqual(z['bild-video']['detail'], 'Drei Prozesse bereit (je ein Auftrag gleichzeitig).')

    def test_nur_zwei_von_drei_prozessen_laufen(self):
        z = self.z._zustaende(self.dienste(laeuft=(True, True, False), pid=(1, 2, None)))
        self.assertEqual(z['bild-video']['detail'],
                         'Nur zwei von drei Prozessen laufen; „Starten“ startet die fehlenden nach.')

    def test_weiterer_prozess_startet_noch(self):
        z = self.z._zustaende(self.dienste(laeuft=(True, True, False), pid=(1, 2, 7)))
        self.assertEqual(z['bild-video']['detail'], 'Weitere Prozesse starten …')

    def test_nur_ein_prozess_laeuft(self):
        z = self.z._zustaende(self.dienste(laeuft=(True, False, False), pid=(1, None, None)))
        self.assertEqual(z['bild-video']['detail'],
                         'Nur ein Prozess läuft; „Starten“ startet die fehlenden nach.')

    def test_auftraege_aller_prozesse_zaehlen(self):
        z = self.z._zustaende(self.dienste(auftraege=(0, 0, 1)))
        self.assertTrue(z['bild-video']['auftrag'])
        self.assertEqual(z['bild-video']['detail'], 'Ein Auftrag läuft.')

    def test_freigeben_eines_weiteren_prozesses_geht_an_bild_video(self):
        gesehen = {}

        def schritt(sid):
            gesehen['sid'] = sid
            gesehen['laufend'] = dict(self.z.laufend)
            return 'Modelle entladen.'
        self.z.akt = Mock()
        self.z.akt.schritt.side_effect = schritt
        self.z.melden = Mock()
        self.z._schritte_ausfuehren(['freigeben:bild-video-3'])
        self.assertEqual(gesehen, {'sid': 'freigeben:bild-video-3', 'laufend': {'bild-video': 'stoppt'}})
        self.assertEqual(self.z.laufend, {})


if __name__ == '__main__':
    unittest.main()
