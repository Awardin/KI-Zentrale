import copy
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung, norm  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class PolyStrata(unittest.TestCase):
    """Ornith über PolyStrata (18.10.2026): Erkennung, Zustand, Starten auf der gewählten Karte, Beenden, Planung."""

    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.polystrata['ornith-polystrata']
        st = self.erf.strata
        server = (f'"{self.e["python"]}" {self.e["server_skript"]} --engine strata --config {self.e["konfig"]} '
                  f'--port 8097 --gpu 1')
        self.procs = {50: (0, 'python.exe'), 51: (50, 'python.exe'), 52: (51, 'strata-poly.exe'),
                      53: (51, 'strata-vision.exe'), 54: (0, 'python.exe'), 55: (0, 'strata-vision.exe'),
                      56: (0, 'strata.exe'), 57: (0, 'python.exe')}
        self.infos = {
            50: (self.e['python'], server),
            51: (r'C:\Users\sasch\AppData\Roaming\uv\python\cpython\python.exe', server),
            52: (self.e['engine'], f'"{self.e["engine"]}" --serve --model x.gguf'),
            53: (self.e['vision_exe'], f'"{self.e["vision_exe"]}" --mmproj y.gguf'),
            54: (self.e['python'], server.replace('8097', '8098')),                                  # anderer Port
            55: (st['vision_exe'], f'"{st["vision_exe"]}" --mmproj z.gguf'),                         # Strata-Bild
            56: (st['engine'], f'"{st["engine"]}" --serve'),                                         # Strata selbst
            57: (st['python'], f'"{st["python"]}" {st["server_skript"]} --engine strata --port 8095'),
        }
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}
        self.erf.messen = Mock(return_value={'dienste': {'ornith-polystrata': {'zustand': 'aus'}}, 'procs': self.procs})
        self.log = Mock()
        self.akt = Aktionen(self.cfg, self.erf, 'logs', self.log)
        for name in ('starte_losgeloest', 'beenden', 'prozesse', 'lauschende_ports', 'freier_arbeitsspeicher_mib'):
            p = patch('gemeinsam.winapi.' + name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.freier_arbeitsspeicher_mib.return_value = 40 * 1024
        p = patch('zentrale.erfassung.http_json')
        self.health = p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.http_json')
        self.antwort = p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.os.path.exists', return_value=True)
        self.datei = p.start()
        self.addCleanup(p.stop)

    def test_eintrag_eine_karte_ollama_datei(self):
        self.assertEqual(self.e['art'], 'polystrata')
        self.assertEqual(self.e['karten'], ['RTX 3090'])
        self.assertEqual((self.e['bedarf_je_karte_mib'], self.e['port']), (23000, 8097))
        self.assertNotIn('bedarf_mib', self.e)
        ornith_q4 = next(e for e in KONFIG['eintraege'] if e['id'] == 'ornith-q4')
        self.assertEqual(ornith_q4['art'], 'ollama')  # Ollama-Ornith bleibt daneben

    def test_erkennung_trennt_polystrata_und_strata(self):
        for pid in (50, 51, 52, 53):
            with self.subTest(pid=pid):
                self.assertEqual(self.erf.ist_polystrata(pid, self.procs), 'ornith-polystrata')
                self.assertFalse(self.erf.ist_strata(pid, self.procs))
        for pid in (54, 55, 56, 57):
            with self.subTest(pid=pid):
                self.assertIsNone(self.erf.ist_polystrata(pid, self.procs))
        for pid in (55, 56, 57):
            self.assertTrue(self.erf.ist_strata(pid, self.procs))
        self.assertEqual(self.erf.einordnen(52, self.procs), ('polystrata:ornith-polystrata', self.e['name']))
        self.assertEqual(self.erf.einordnen(56, self.procs)[0], 'strata')

    def test_dienstzustand(self):
        self.health.return_value = {'loaded': True, 'max_context': 131072, 'model': self.e['modell']}
        s = self.erf._dienste(self.procs, {8097: 51})['ornith-polystrata']
        self.assertEqual((s['zustand'], s['kontext'], s['pids']), ('bereit', 131072, [50, 51, 52, 53]))
        self.health.return_value = {'loaded': False}
        self.assertEqual(self.erf._dienste(self.procs, {8097: 51})['ornith-polystrata']['zustand'], 'startet')
        s = self.erf._dienste(self.procs, {8097: 56})['ornith-polystrata']
        self.assertEqual((s['zustand'], s['fremd']), ('fremd', 'strata'))
        self.assertEqual(self.erf._dienste(self.procs, {})['ornith-polystrata']['zustand'], 'startet')
        self.assertEqual(self.erf._dienste({}, {})['ornith-polystrata']['zustand'], 'aus')

    def test_verbraucher_und_planung(self):
        karten = [{'index': 0, 'belegt': 1000, 'gesamt': 24576}, {'index': 1, 'belegt': 23300, 'gesamt': 24576}]
        v = self.erf._verbraucher(self.procs, karten, {1: {52: 22000.0, 53: 1300.0}}, {'geladen': []},
                                  {'comfy': {'auftraege_laufend': 0, 'laeuft': False}})
        x = next(x for x in v if x['schluessel'] == 'polystrata:ornith-polystrata')
        self.assertEqual((x['eintrag'], x['mib_je_karte'], x['schritt']['id']),
                         ('ornith-polystrata', {1: 23300}, 'beenden:ornith-polystrata'))
        plan = planung.plan_fuer_start(karten, v, self.erf.strata, 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['beenden:ornith-polystrata'])

    def test_karte_monitor_nur_mit_puffer(self):
        # Beide Karten leer, die FE trägt den Monitor: PolyStrata (23 GB) geht auf die Suprim.
        karten = [{'index': 0, 'belegt': 1500, 'gesamt': 24576, 'name': 'RTX 3090', 'monitor': True},
                  {'index': 1, 'belegt': 0, 'gesamt': 24576, 'name': 'RTX 3090'}]
        self.assertEqual(planung.karte_waehlen(karten, [], self.e, 768, 2048), (1, None))

    def test_start_argumente_karte_und_log(self):
        self.starte_losgeloest.return_value = Mock(pid=60, poll=Mock(return_value=None))
        self.antwort.side_effect = [ConnectionError(), {'loaded': False}, {'loaded': True, 'max_context': 131072}]
        with patch('zentrale.aktionen.time.sleep'):
            self.assertEqual(self.akt.starten('ornith-polystrata', karte=1),
                             f"{self.e['name']} ist bereit (0 s, Kontext 131.072).")
        args, kwargs = self.starte_losgeloest.call_args
        self.assertEqual(args[0], [self.e['python'], self.e['server_skript'], '--engine', 'strata', '--config',
                                   self.e['konfig'], '--port', '8097', '--gpu', '1'])
        self.assertEqual(args[1], r'C:\LLM\runtimes\PolyStrata')
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'ornith-polystrata'))
        self.assertIn('gestartet auf Karte 1', self.log.call_args.args[0])

    def test_start_ohne_karte_zu_wenig_ram_oder_datei_fehlt(self):
        with self.assertRaisesRegex(Fehler, 'Keine Karte'):
            self.akt.starten('ornith-polystrata')
        self.freier_arbeitsspeicher_mib.return_value = 10 * 1024
        with self.assertRaisesRegex(Fehler, 'Zu wenig freier Arbeitsspeicher: 10,0 GiB frei'):
            self.akt.starten('ornith-polystrata', karte=1)
        self.freier_arbeitsspeicher_mib.return_value = 40 * 1024
        self.datei.side_effect = lambda p: p != self.e['vision_exe']
        with self.assertRaisesRegex(Fehler, 'Datei fehlt: '):
            self.akt.starten('ornith-polystrata', karte=1)
        self.starte_losgeloest.assert_not_called()

    def test_start_bereit_oder_fremd(self):
        self.erf.messen.return_value['dienste']['ornith-polystrata'] = {'zustand': 'bereit'}
        self.assertEqual(self.akt.starten('ornith-polystrata', karte=1), f"{self.e['name']} läuft bereits.")
        self.erf.messen.return_value['dienste']['ornith-polystrata'] = {'zustand': 'fremd', 'fremd': 'Python'}
        with self.assertRaisesRegex(Fehler, 'Port 8097 ist von Python belegt'):
            self.akt.starten('ornith-polystrata', karte=1)

    def test_startfehler_liest_ausgabe(self):
        self.starte_losgeloest.return_value = Mock(pid=60, poll=Mock(return_value=1))
        with patch('zentrale.aktionen._letzte_meldung', return_value='no VRAM') as letzte:
            with self.assertRaisesRegex(Fehler, 'no VRAM'):
                self.akt.starten('ornith-polystrata', karte=1)
        letzte.assert_called_once_with(os.path.join('logs', 'ornith-polystrata.out.log'))

    def test_beenden_engine_zuerst_strata_bleibt(self):
        self.prozesse.return_value = {}
        self.lauschende_ports.return_value = []
        self.assertEqual(self.akt.schritt('beenden:ornith-polystrata'), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [52, 53, 50, 51])
        self.beenden.reset_mock()
        self.erf.messen.return_value['procs'] = {k: self.procs[k] for k in (54, 55, 56, 57)}
        self.assertEqual(self.akt.stoppen('ornith-polystrata'), f"{self.e['name']} lief nicht.")
        self.beenden.assert_not_called()

    def test_server_zustand_link_und_schritt(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = dict(self.cfg, eintraege=[self.e])
        z.erf, z.akt, z.laufend = self.erf, self.akt, {}
        roh = {'dienste': {'ornith-polystrata': {'zustand': 'bereit', 'fremd': None, 'kontext': 131072}},
               'karten': [{'index': 1, 'name': 'NVIDIA GeForce RTX 3090'}],
               'verbraucher': [{'schluessel': 'polystrata:ornith-polystrata', 'mib_je_karte': {1: 23300}}]}
        s = z._zustaende(roh)['ornith-polystrata']
        self.assertEqual(s['detail'], 'Kontext 131.072 · Port 8097 · RTX 3090')
        self.assertEqual(s['karte'], 'RTX 3090')
        roh['dienste']['ornith-polystrata'].update(zustand='fremd', fremd='Python')
        self.assertEqual(z._zustaende(roh)['ornith-polystrata']['detail'], 'Port 8097 ist von Python belegt.')
        k = z.konfig()['eintraege'][0]
        self.assertEqual(k['links'], [{'art': 'polystrata', 'text': 'Chat öffnen', 'url': 'http://127.0.0.1:8097/'}])
        self.assertEqual((k['karten'], k['bedarf_je_karte_mib']), (['RTX 3090'], 23000))
        z.melden = Mock()

        def schritt(sid):
            self.assertEqual(z.laufend, {'ornith-polystrata': 'stoppt'})
            return 'Beendet.'
        z.akt = Mock(schritt=schritt)
        z._schritte_ausfuehren(['beenden:ornith-polystrata'])
        self.assertEqual(z.laufend, {})


if __name__ == '__main__':
    unittest.main()
