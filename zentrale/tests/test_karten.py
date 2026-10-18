"""Zwei RTX 3090 (seit 14.10.2026): Kartenwahl für NInfer und ComfyUI, Gesamtbedarf für Ollama, Kartennamen."""
import copy
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


def karte(idx, belegt, bus):
    return {'index': idx, 'name': 'NVIDIA GeForce RTX 3090', 'bus': bus, 'gesamt': 24576, 'belegt': belegt}


class Eintraege(unittest.TestCase):
    def setUp(self):
        self.e = {e['id']: e for e in KONFIG['eintraege']}

    def test_keine_karte_fest_reserviert(self):
        for eid in ('ninfer', 'lightonocr', 'bild-video'):
            with self.subTest(eid=eid):
                self.assertEqual(self.e[eid]['karten'], ['RTX 3090'])
                self.assertNotIn('bedarf_mib', self.e[eid])
        for eid in ('ornith-q5', 'ornith-q4'):
            with self.subTest(eid=eid):
                self.assertIn('bedarf_gesamt_mib', self.e[eid])
                self.assertNotIn('bedarf_mib', self.e[eid])
        self.assertEqual(set(self.e['flash-next-strata']['bedarf_mib']), {'0', '1'})  # Strata braucht beide Karten

    def test_kartennamen_nach_steckplatz(self):
        namen = {c['bus']: c['kurz'] for c in KONFIG['karten'].values()}
        self.assertEqual(namen, {2: 'RTX 3090 FE', 4: 'RTX 3090 Suprim'})


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

    def test_ninfer_plan_und_start_auf_der_freien_karte(self):
        # Auf der FE liegt LightOnOCR: NInfer (22,3 GiB) passt nur noch auf die Suprim.
        self.roh['karten'][0]['belegt'] = 4700
        self.roh['verbraucher'] = [{'eintrag': 'lightonocr', 'name': 'LightOnOCR', 'mib_je_karte': {0: 4700},
                                   'blockiert': None, 'schritt': {'id': 'beenden:lightonocr', 'text': 'x'}}]
        p = self.z.plan('ninfer', 'starten')
        self.assertEqual((p['karte'], p['karte_kurz'], p['schritte'], p['genug_platz']), (1, 'RTX 3090 Suprim', [], True))
        self.assertEqual(self.z.starten('ninfer', [], False)[0], 202)
        self.z.akt.starten.assert_called_once_with('ninfer', karte=1)

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
