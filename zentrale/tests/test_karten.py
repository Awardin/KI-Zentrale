"""Drei Karten (RTX 3090 FE, RTX 3090 Suprim, RTX 3080 als Nebenkarte): Kartenwahl und Gesamtbedarf."""
import copy
import json
import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gemeinsam import gpu  # noqa: E402
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


def karte(idx, belegt, bus, name='NVIDIA GeForce RTX 3090', gesamt=24576, nebenkarte=False):
    return {'index': idx, 'name': name, 'bus': bus, 'gesamt': gesamt, 'belegt': belegt, 'last': 0,
            'monitor': False, 'nebenkarte': nebenkarte}


def drei_karten():
    return [karte(0, 0, 2), karte(1, 884, 4),
            karte(2, 0, 135, name='NVIDIA GeForce RTX 3080', gesamt=20480, nebenkarte=True)]


class Eintraege(unittest.TestCase):
    def setUp(self):
        self.e = {e['id']: e for e in KONFIG['eintraege']}

    def test_keine_karte_fest_reserviert(self):
        for eid in ('ninfer', 'bild-video'):
            with self.subTest(eid=eid):
                self.assertEqual(self.e[eid]['karten'], ['RTX 3090'])
                self.assertNotIn('bedarf_mib', self.e[eid])
        self.assertEqual(self.e['lightonocr']['karten'], ['RTX 3080', 'RTX 3090'])
        self.assertEqual(self.e['lightonocr']['untertitel'], '4B · Q4_K_M · RTX 3080, sonst eine RTX 3090')
        for eid in ('ornith-q5', 'ornith-q6', 'ornith-q4'):
            with self.subTest(eid=eid):
                self.assertIn('bedarf_gesamt_mib', self.e[eid])
                self.assertNotIn('bedarf_mib', self.e[eid])
                self.assertEqual(self.e[eid]['gesamt_karten'], ['RTX 3090'])
        # Varianten erben die Kartenliste des Eintrags.
        self.assertEqual(planung.variante(self.e['ornith-q4'], '32k')['gesamt_karten'], ['RTX 3090'])
        self.assertEqual(set(self.e['flash-next-strata']['bedarf_mib']), {'0', '1'})  # Strata braucht beide Karten

    def test_kartennamen_nach_steckplatz(self):
        namen = {c['bus']: c['kurz'] for c in KONFIG['karten'].values()}
        self.assertEqual(namen, {2: 'RTX 3090 FE', 4: 'RTX 3090 Suprim', 135: 'RTX 3080'})

    def test_kurznamen_und_nebenkarte_aus_der_messung(self):
        k = drei_karten()
        self.assertEqual(gpu.kurznamen(k, KONFIG['karten']),
                         {0: 'RTX 3090 FE', 1: 'RTX 3090 Suprim', 2: 'RTX 3080'})
        self.assertEqual(gpu.nebenkarten(k, KONFIG['karten']), {2})


class Server(unittest.TestCase):
    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = KONFIG
        self.z.eintraege = {e['id']: e for e in KONFIG['eintraege']}
        self.z.laufend = {}
        self.roh = {'karten': [karte(0, 0, 2), karte(1, 884, 4)], 'verbraucher': []}
        self.z._aktuell = Mock(return_value=self.roh)
        self.z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        self.z.akt = Mock()
        self.z._schritte_ausfuehren = Mock()
        self.z._im_hintergrund = Mock(side_effect=lambda text, fn: (fn(), True)[1])

    def test_ninfer_plan_auf_der_festen_karte(self):
        # Seit 29.10.2026 ist NInfer 1 fest auf Karte 0; LightOnOCR dort muss dafür weichen, Karte 1 bleibt unberührt.
        self.roh['karten'][0]['belegt'] = 4700
        self.roh['verbraucher'] = [{'eintrag': 'lightonocr', 'name': 'LightOnOCR', 'mib_je_karte': {0: 4700},
                                   'blockiert': None, 'schritt': {'id': 'beenden:lightonocr', 'text': 'x'}}]
        p = self.z.plan('ninfer', 'starten')
        self.assertEqual((p['karte'], p['karte_kurz'], [s['id'] for s in p['schritte']], p['genug_platz']),
                         (0, 'RTX 3090 FE', ['beenden:lightonocr'], True))
        self.assertEqual(self.z.starten('ninfer', ['beenden:lightonocr'], False)[0], 202)
        self.z.akt.starten.assert_called_once_with('ninfer', karte=0)

    def test_ornith_plan_zaehlt_beide_karten_zusammen(self):
        p = self.z.plan('ornith-q5', 'starten')
        self.assertTrue(p['genug_platz'])
        self.assertEqual(set(p['bedarf_mib']), {'0', '1'})  # geschätzte Verteilung für die Vorschau
        self.roh['karten'][0]['belegt'] = 22300
        self.roh['verbraucher'] = [{'eintrag': 'ninfer', 'name': 'NInfer', 'mib_je_karte': {0: 22300},
                                   'blockiert': None, 'schritt': {'id': 'beenden:ninfer', 'text': 'NInfer beenden'}}]
        p = self.z.plan('ornith-q5', 'starten')
        self.assertEqual([s['id'] for s in p['schritte']], ['beenden:ninfer'])
        self.assertEqual(self.z.starten('ornith-q5', ['beenden:ninfer'], False)[0], 202)
        e = self.z.eintraege['ornith-q5']
        self.z.akt.warten_auf_platz.assert_called_once_with(e, 768, gesamt=e['bedarf_gesamt_mib'])
        self.z.akt.starten.assert_called_once_with('ornith-q5')

    def test_comfy_plant_eine_freie_karte(self):
        # ComfyUI selbst nutzt beide Karten (das Studio wählt je Auftrag); geplant wird Platz für ein Bild.
        p = self.z.plan('bild-video', 'starten')
        self.assertEqual((p['karte'], p['genug_platz']), (1, True))
        self.assertEqual(self.z.starten('bild-video', [], False)[0], 202)
        self.z.akt.starten.assert_called_once_with('bild-video', karte=1)
        self.z.erf = Mock()
        e = next(x for x in self.z.konfig()['eintraege'] if x['id'] == 'bild-video')
        self.assertTrue(e['bedarf_hinweis'].startswith('Braucht während eines Bildauftrags'))

    def test_zustand_ninfer_nennt_karte(self):
        roh = dict(self.roh, dienste={'ninfer': {'zustand': 'bereit', 'fremd': None}},
                   verbraucher=[{'schluessel': 'ninfer', 'mib_je_karte': {1: 22300}}])
        z = Zentrale.__new__(Zentrale)
        z.cfg, z.laufend = dict(KONFIG, eintraege=[self.z.eintraege['ninfer']]), {}
        s = z._zustaende(roh)['ninfer']
        self.assertEqual((s['karte'], s['detail']), ('RTX 3090 Suprim', 'Auf der RTX 3090 Suprim'))


class Dreikarten(unittest.TestCase):
    """Mit der RTX 3080 als Nebenkarte (Bus 135 = 0x87, M.2 seit 23.10.2026): LightOnOCR darf dorthin, NInfer und Ollama nur auf die 3090."""

    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = KONFIG
        self.z.eintraege = {e['id']: e for e in KONFIG['eintraege']}
        self.z.laufend = {}
        self.z.aktion = None
        self.z.anmeldungen = {}
        self.z.verlauf = []
        self.z._lock, self.z._platz_lock = threading.Lock(), threading.Lock()
        self.z.melden, self.z._uebernehmen = Mock(), Mock()
        self.roh = {'karten': drei_karten(), 'verbraucher': [], 'dienste': {}}
        self.z.roh = self.roh
        self.z._aktuell = Mock(return_value=self.roh)
        self.z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        self.z.akt = Mock()
        self.z._schritte_ausfuehren = Mock()
        self.z._im_hintergrund = Mock(side_effect=lambda text, fn: (fn(), True)[1])

    def test_lightonocr_nimmt_die_nebenkarte_auch_wenn_die_3090_enger_waere(self):
        # Auf der FE liegt ein Modell, sie wäre damit die „engste“ passende Karte; die 3080 hat trotzdem Vorrang.
        self.roh['karten'][0]['belegt'] = 18000
        self.roh['verbraucher'] = [{'eintrag': 'ninfer', 'name': 'NInfer', 'mib_je_karte': {0: 18000},
                                   'blockiert': None, 'schritt': {'id': 'beenden:ninfer', 'text': 'NInfer beenden'}}]
        p = self.z.plan('lightonocr', 'starten')
        self.assertEqual((p['karte'], p['schritte'], p['genug_platz']), (2, [], True))

    def test_lightonocr_nimmt_bei_voller_3080_eine_3090_ohne_freigabe(self):
        self.roh['karten'][2]['belegt'] = 19456  # 19 GiB belegt: LightOnOCR passt dort nicht mehr
        p = self.z.plan('lightonocr', 'starten')
        self.assertIn(p['karte'], (0, 1))
        self.assertEqual((p['schritte'], p['genug_platz']), ([], True))

    def test_ninfer_kommt_nie_auf_die_nebenkarte(self):
        self.roh['karten'][0]['belegt'] = 22300
        self.roh['karten'][1]['belegt'] = 23000
        self.roh['verbraucher'] = [{'eintrag': 'ornith-q5', 'name': 'Ornith', 'mib_je_karte': {0: 22300},
                                   'blockiert': None, 'schritt': {'id': 'beenden:ornith-q5', 'text': 'Ornith beenden'}}]
        p = self.z.plan('ninfer', 'starten')
        self.assertIn(p['karte'], (0, 1))
        self.assertEqual([s['id'] for s in p['schritte']], ['beenden:ornith-q5'])
        self.assertTrue(p['genug_platz'])

    def test_ornith_zaehlt_die_nebenkarte_nicht_mit(self):
        # Beide 3090 fast voll, die 3080 leer: Ollama zählt nur die 3090, also fehlt Platz.
        self.roh['karten'][0]['belegt'] = 22300
        self.roh['karten'][1]['belegt'] = 23000
        self.roh['verbraucher'] = [{'eintrag': 'ninfer', 'name': 'NInfer', 'mib_je_karte': {0: 22300},
                                   'blockiert': None, 'schritt': {'id': 'beenden:ninfer', 'text': 'NInfer beenden'}}]
        p = self.z.plan('ornith-q4', 'starten')
        self.assertFalse(p['genug_platz'])
        self.assertNotIn('2', p['bedarf_mib'])
        self.assertTrue(set(p['bedarf_mib']) <= {'0', '1'})
        self.assertEqual([s['id'] for s in p['schritte']], ['beenden:ninfer'])

    def test_platz_antwort_nennt_nebenkarte_je_karte(self):
        code, antwort = self.z.platz({})
        self.assertEqual(code, 200)
        self.assertEqual({k['index']: k['nebenkarte'] for k in antwort['karten']},
                         {0: False, 1: False, 2: True})


class WartenAufGesamt(unittest.TestCase):
    def test_gesamt_karten_zaehlt_die_nebenkarte_nicht(self):
        erf = Mock()
        erf.messen.return_value = {'karten': drei_karten()}
        akt = Aktionen(KONFIG, erf, 'logs', Mock())
        e = {'gesamt_karten': ['RTX 3090']}
        # Nur 3090: 24.576 + (24.576 - 884) MiB. Die leere 3080 (20.480 MiB) zählt nicht mit.
        self.assertTrue(akt.warten_auf_platz(e, 0, gesamt=24576 + 24576 - 884, sekunden=0))
        self.assertFalse(akt.warten_auf_platz(e, 0, gesamt=24576 + 24576 - 884 + 1, sekunden=0))
        # Ohne gesamt_karten zählen wie bisher alle Karten.
        self.assertTrue(akt.warten_auf_platz({}, 0, gesamt=24576 + 24576 - 884 + 20480, sekunden=0))


class NinferStart(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.erf.messen = Mock(return_value={'dienste': {'ninfer': {'zustand': 'aus'}}, 'procs': {},
                                             'karten': [karte(0, 0, 2), karte(1, 884, 4)]})
        self.akt = Aktionen(self.cfg, self.erf, 'logs', Mock())
        for name, wert in (('zentrale.aktionen.os.path.exists', True),):
            p = patch(name, return_value=wert)
            p.start()
            self.addCleanup(p.stop)
        p = patch('gemeinsam.winapi.starte_losgeloest')
        self.start = p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.http_json', return_value={'data': [{'id': self.erf.ninfer['modell_id']}]})
        p.start()
        self.addCleanup(p.stop)

    def test_nur_die_gewaehlte_karte_ist_sichtbar(self):
        self.start.return_value.poll.return_value = None
        self.assertIn('ist bereit', self.akt.starten('ninfer', karte=1))
        argv, ordner, env = self.start.call_args.args
        self.assertEqual((env['CUDA_DEVICE_ORDER'], env['CUDA_VISIBLE_DEVICES']), ('PCI_BUS_ID', '1'))
        self.assertIn('--device', argv)
        self.assertEqual(argv[argv.index('--device') + 1], '0')

    def test_ohne_karte_kein_start(self):
        with self.assertRaisesRegex(Fehler, 'Keine Karte'):
            self.akt.starten('ninfer')
        self.start.assert_not_called()

    def test_warten_auf_gesamtplatz(self):
        self.assertTrue(self.akt.warten_auf_platz({}, 768, gesamt=24576 * 2 - 884 - 2 * 768, sekunden=0))
        self.assertFalse(self.akt.warten_auf_platz({}, 768, gesamt=24576 * 2 - 884 - 2 * 768 + 1, sekunden=0))


if __name__ == '__main__':
    unittest.main()
