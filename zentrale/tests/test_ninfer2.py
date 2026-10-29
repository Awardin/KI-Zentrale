"""Zwei NInfer-Instanzen (29.10.2026): je eine Karte, eigener Port, eigener Schlüssel und Schritt."""
import copy
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung, norm  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)
E = {e['id']: e for e in KONFIG['eintraege']}


def karte(idx, belegt=0, bus=2, name='NVIDIA GeForce RTX 3090', gesamt=24576):
    return {'index': idx, 'name': name, 'bus': bus, 'gesamt': gesamt, 'belegt': belegt, 'last': 0,
            'monitor': False}


class Erkennung(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e1 = self.erf.ninfer_eintraege['ninfer']
        self.e2 = self.erf.ninfer_eintraege['ninfer-2']
        prog = self.e1['programm']
        self.procs = {40: (0, 'ninfer-serve.exe'), 41: (0, 'ninfer-serve.exe'),
                      42: (0, 'ninfer-serve.exe'), 43: (0, 'ninfer-serve.exe')}
        cmd1 = f'"{prog}" "{self.e1["modelldatei"]}" --port 8080 --model-id {self.e1["modell_id"]}'
        cmd2 = f'"{prog}" "{self.e2["modelldatei"]}" --port 8081 --model-id {self.e2["modell_id"]}'
        self.infos = {
            40: (prog, cmd1),
            41: (prog, cmd2),
            42: (prog, cmd1.replace('--port 8080', '--port 8099')),  # fremder Port
            43: (r'C:\Fremd\ninfer-serve.exe', cmd2),                 # anderes Programm
        }
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name,
                                           'pfad': norm(self.infos[pid][0]), 'cmd': self.infos[pid][1].lower()}

    def test_programmpfad_und_port_ordnen_die_instanz_zu(self):
        self.assertEqual(self.erf.ist_ninfer(40, self.procs), 'ninfer')
        self.assertEqual(self.erf.ist_ninfer(41, self.procs), 'ninfer-2')
        self.assertIsNone(self.erf.ist_ninfer(42, self.procs))
        self.assertIsNone(self.erf.ist_ninfer(43, self.procs))

    def test_verbraucher_schluessel_und_anzeige(self):
        self.assertEqual(self.erf.einordnen(40, self.procs), ('ninfer', self.e1['name']))
        self.assertEqual(self.erf.einordnen(41, self.procs), ('ninfer:ninfer-2', self.e2['name']))
        self.assertEqual(self.erf.einordnen(42, self.procs), ('andere', 'NInfer (anderer Port)'))

        v = self.erf._verbraucher(self.procs, [karte(0), karte(1)], {0: {40: 21000.0}, 1: {41: 20500.0}},
                                  {'geladen': []}, {})
        nach_schluessel = {x['schluessel']: x for x in v}
        self.assertEqual(nach_schluessel['ninfer']['mib_je_karte'], {0: 21000})
        self.assertEqual(nach_schluessel['ninfer']['schritt']['id'], 'beenden:ninfer')
        self.assertEqual(nach_schluessel['ninfer:ninfer-2']['mib_je_karte'], {1: 20500})
        self.assertEqual(nach_schluessel['ninfer:ninfer-2']['schritt']['id'], 'beenden:ninfer-2')

    def test_dienstzustand_je_eintrag(self):
        antwort = {8080: {'data': [{'id': self.e1['modell_id']}]},
                   8081: {'data': [{'id': 'noch-ein-anderes-modell'}]}}

        def http_json(url, timeout=1.0):
            return antwort[int(url.split(':')[2].split('/')[0])]
        with patch('zentrale.erfassung.http_json', side_effect=http_json):
            d = self.erf._dienste(self.procs, {8080: 40, 8081: 41})
        self.assertEqual((d['ninfer']['zustand'], d['ninfer']['pid']), ('bereit', 40))
        self.assertEqual((d['ninfer-2']['zustand'], d['ninfer-2']['pid']), ('startet', 41))


class Aktion(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e1 = self.erf.ninfer_eintraege['ninfer']
        self.e2 = self.erf.ninfer_eintraege['ninfer-2']
        prog = self.e1['programm']
        self.procs = {40: (0, 'ninfer-serve.exe'), 41: (0, 'ninfer-serve.exe')}
        cmd1 = f'"{prog}" --port 8080 --model-id {self.e1["modell_id"]}'
        cmd2 = f'"{prog}" --port 8081 --model-id {self.e2["modell_id"]}'
        self.infos = {40: (prog, cmd1), 41: (prog, cmd2)}
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name,
                                           'pfad': norm(self.infos[pid][0]), 'cmd': self.infos[pid][1].lower()}
        self.erf.messen = Mock(return_value={'dienste': {}, 'procs': self.procs})
        self.log = Mock()
        self.akt = Aktionen(self.cfg, self.erf, 'logs', self.log)
        for name in ('starte_losgeloest', 'beenden', 'prozesse', 'lauschende_ports'):
            p = patch('gemeinsam.winapi.' + name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.prozesse.return_value = {}
        self.lauschende_ports.return_value = []

    def test_stopp_beendet_nur_die_eigene_instanz(self):
        self.assertEqual(self.akt.stoppen('ninfer-2'), f"{self.e2['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [41])
        self.assertEqual(self.log.call_args_list[0].args[0], f"{self.e2['name']} beendet, PID 41")
        self.beenden.reset_mock()

        self.assertEqual(self.akt.schritt('beenden:ninfer'), f"{self.e1['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [40])

    def test_start_nimmt_eigene_kennung_und_logdatei(self):
        self.erf.messen.return_value = {'dienste': {'ninfer-2': {'zustand': 'aus'}}, 'procs': {}}
        self.starte_losgeloest.return_value = Mock(pid=50, poll=Mock(return_value=None))
        with patch('zentrale.aktionen.os.path.exists', return_value=True), \
                patch('zentrale.aktionen.http_json', return_value={'data': [{'id': self.e2['modell_id']}]}), \
                patch('zentrale.aktionen.time.sleep'):
            self.assertIn('ist bereit', self.akt.starten('ninfer-2', karte=1))
        args, kwargs = self.starte_losgeloest.call_args
        argv = args[0]
        self.assertEqual(argv[argv.index('--port') + 1], '8081')
        self.assertEqual(argv[argv.index('--max-context') + 1], '98304')
        self.assertEqual(args[2]['CUDA_VISIBLE_DEVICES'], '1')
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'ninfer-2'))
        self.log.assert_called_once_with(f"{self.e2['name']} gestartet auf Karte 1, PID 50, Port 8081")

    def test_startfehler_nennt_eintrag_und_eigene_logdatei(self):
        self.erf.messen.return_value = {'dienste': {'ninfer-2': {'zustand': 'aus'}}, 'procs': {}}
        self.starte_losgeloest.return_value = Mock(pid=50, poll=Mock(return_value=1))
        with patch('zentrale.aktionen.os.path.exists', return_value=True), \
                patch('zentrale.aktionen._letzte_meldung', return_value='CUDA error') as letzte:
            with self.assertRaises(Fehler) as ex:
                self.akt.starten('ninfer-2', karte=1)
        self.assertIn('NInfer 2 hat sich beim Start beendet', str(ex.exception))
        letzte.assert_called_once_with(os.path.join('logs', 'ninfer-2.err.log'))


class Server(unittest.TestCase):
    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = dict(KONFIG, eintraege=[E['ninfer'], E['ninfer-2']])
        self.z.eintraege = {e['id']: e for e in self.z.cfg['eintraege']}
        self.z.laufend = {}
        self.roh = {'karten': [karte(0, bus=2), karte(1, belegt=884, bus=4)],
                    'verbraucher': [
                        {'schluessel': 'ninfer', 'mib_je_karte': {0: 21000}},
                        {'schluessel': 'ninfer:ninfer-2', 'mib_je_karte': {1: 20500}}],
                    'dienste': {'ninfer': {'zustand': 'bereit', 'fremd': None},
                                'ninfer-2': {'zustand': 'bereit', 'fremd': None}}}

    def test_zustaende_und_karte_je_eintrag(self):
        s = self.z._zustaende(self.roh)
        self.assertEqual((s['ninfer']['detail'], s['ninfer']['karte']), ('Auf der RTX 3090 FE', 'RTX 3090 FE'))
        self.assertEqual((s['ninfer-2']['detail'], s['ninfer-2']['karte']),
                         ('Auf der RTX 3090 Suprim', 'RTX 3090 Suprim'))

    def test_schritte_beenden_ninfer_2(self):
        self.z.erf = Mock(ninfer_eintraege={'ninfer': E['ninfer'], 'ninfer-2': E['ninfer-2']},
                          llamacpp={}, polystrata={}, python_dienst={}, ollama_tags={}, strata=None)
        self.z.melden = Mock()

        def schritt(sid):
            self.assertEqual(sid, 'beenden:ninfer-2')
            self.assertEqual(self.z.laufend, {'ninfer-2': 'stoppt'})
            return 'Beendet.'
        self.z.akt = Mock(schritt=schritt)
        self.z._schritte_ausfuehren(['beenden:ninfer-2'])
        self.assertEqual(self.z.laufend, {})


class FesteKarte(unittest.TestCase):
    ZIEL = {'id': 'ninfer-2', 'karten': ['RTX 3090'], 'bedarf_je_karte_mib': 21000, 'feste_karte': 1}

    def test_feste_karte_geht_vor_der_engsten(self):
        k = [karte(0, belegt=2000, bus=2), karte(1, belegt=0, bus=4)]
        self.assertEqual(planung.karte_waehlen(k, [], self.ZIEL, 768), (1, None))
        ohne = dict(self.ZIEL)
        del ohne['feste_karte']
        self.assertEqual(planung.karte_waehlen(k, [], ohne, 768), (0, None))

    def test_feste_karte_plant_freigaben_auf_dieser_karte(self):
        k = [karte(0, belegt=0, bus=2), karte(1, belegt=22000, bus=4)]
        v = [{'eintrag': 'ornith-q5', 'name': 'Ornith Q5', 'mib_je_karte': {1: 21000}, 'blockiert': None,
              'schritt': {'id': 'beenden:ornith-q5', 'text': 'Ornith Q5 beenden'}},
             {'eintrag': 'ninfer', 'name': 'NInfer 1', 'mib_je_karte': {0: 21000}, 'blockiert': None,
              'schritt': {'id': 'beenden:ninfer', 'text': 'NInfer 1 beenden'}}]
        idx, grund = planung.karte_waehlen(k, v, self.ZIEL, 768)
        self.assertEqual((idx, grund), (1, None))
        plan = planung.plan_fuer_start(k, v, dict(self.ZIEL, bedarf_mib={idx: self.ZIEL['bedarf_je_karte_mib']}), 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['beenden:ornith-q5'])
        self.assertTrue(plan['genug_platz'])

    def test_feste_karte_muss_zu_karten_passen(self):
        idx, grund = planung.karte_waehlen([karte(0, bus=2), karte(1, bus=4)], [],
                                           dict(self.ZIEL, feste_karte=2), 768)
        self.assertIsNone(idx)
        self.assertEqual(grund, 'Karte 2 passt nicht zu RTX 3090.')

    def test_server_plant_ninfer_2_auf_der_suprim(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = KONFIG
        z.eintraege = dict(E)
        z.laufend = {}
        roh = {'karten': [karte(0, belegt=2000, bus=2), karte(1, belegt=0, bus=4)], 'verbraucher': []}
        z._aktuell = Mock(return_value=roh)
        z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        p = z.plan('ninfer-2', 'starten')
        self.assertEqual((p['karte'], p['karte_kurz'], p['schritte'], p['genug_platz']),
                         (1, 'RTX 3090 Suprim', [], True))

    def test_server_plant_freigaben_auf_der_festen_karte(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = KONFIG
        z.eintraege = dict(E)
        z.laufend = {}
        roh = {'karten': [karte(0, belegt=0, bus=2), karte(1, belegt=22000, bus=4)],
               'verbraucher': [{'eintrag': 'ornith-q5', 'name': 'Ornith Q5', 'mib_je_karte': {1: 21000},
                                'blockiert': None, 'schritt': {'id': 'beenden:ornith-q5', 'text': 'x'}}]}
        z._aktuell = Mock(return_value=roh)
        z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        p = z.plan('ninfer-2', 'starten')
        self.assertEqual((p['karte'], [s['id'] for s in p['schritte']], p['genug_platz']),
                         (1, ['beenden:ornith-q5'], True))


class Konfiguration(unittest.TestCase):
    def test_ninfer_2_port_karte_und_kontext(self):
        e1, e2 = E['ninfer'], E['ninfer-2']
        self.assertEqual((e1['name'], e1['untertitel'], e1['feste_karte']),
                         ('Qwen3.8 27B · NInfer 1', '128K Kontext · RTX 3090 FE', 0))
        self.assertIn('29.10.2026', e1['karten_grund'])
        self.assertEqual((e2['port'], e2['feste_karte'], e2['modell_id'], e2['karten'], e2['bedarf_je_karte_mib'],
                          e2['startzeit_max_s']),
                         (8081, 1, 'qwen3.8-27b-ninfer-2', ['RTX 3090'], 21200, 240))   # gemessen 29.10.2026
        self.assertEqual((e2['programm'], e2['modelldatei']), (e1['programm'], e1['modelldatei']))
        self.assertIn('NInfer 2 (Suprim, 96K)', e2['wofuer'])
        self.assertIn('Port 8081', e2['wofuer'])
        self.assertTrue(e2['bedarf_hinweis'].startswith('Gemessen 29.10.2026'))
        self.assertNotEqual(e2['farbe'], e1['farbe'])
        for flag, wert in (('--port', '8081'), ('--model-id', 'qwen3.8-27b-ninfer-2'),
                           ('--max-context', '98304'), ('--kv-capacity', '98304')):
            with self.subTest(flag=flag):
                self.assertEqual(e2['argumente'][e2['argumente'].index(flag) + 1], wert)
        for flag, wert in (('--max-context', '131072'), ('--kv-capacity', '131072')):
            self.assertEqual(e1['argumente'][e1['argumente'].index(flag) + 1], wert)


if __name__ == '__main__':
    unittest.main()
