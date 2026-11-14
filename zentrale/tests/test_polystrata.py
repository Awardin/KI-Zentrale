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
                                   self.e['konfig'], '--port', '8097', '--gpu', '1', '--fit-max-tokens'])
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


class Edge0(unittest.TestCase):
    """Edge0 und die beiden bisherigen Strata-Dienste bleiben auch bei gleichem Engine-Namen getrennt."""

    def setUp(self):
        PolyStrata.setUp(self)
        self.ornith = self.e
        self.e = self.erf.polystrata['edge0-145b']
        server = (f'"{self.e["python"]}" "{self.e["server_skript"]}" --engine strata '
                  f'--config "{self.e["konfig"]}" "--port" "8109" --gpu 0')
        self.procs.update({60: (0, 'python.exe'), 61: (60, 'python.exe'), 62: (61, 'strata.exe'),
                           63: (0, 'pythonw.exe'), 64: (0, 'strata.exe')})
        self.infos.update({60: (self.e['python'], server), 61: (sys.executable, server),
                           62: (self.e['engine'], '--serve'),
                           63: (self.e['python'], server.replace('8109', '8110')),
                           64: (r'C:\Fremd\strata.exe', '--serve')})
        self.erf.messen.return_value['dienste']['edge0-145b'] = {'zustand': 'aus'}
        # Edge0 braucht gemessen ~46 GiB Arbeitsspeicher (14.11.2026); vor dem Start waren ~50 GiB frei.
        self.freier_arbeitsspeicher_mib.return_value = 50 * 1024

    def test_eintrag_und_schaetzwerte(self):
        self.assertEqual(self.e['art'], 'polystrata')
        self.assertEqual(self.e['name'], 'Edge0 145B · Q3_K')
        self.assertEqual(self.e['untertitel'], 'Flash-Next-Umbau · 128K · ohne Bilder · eine RTX 3090')
        self.assertEqual(self.e['modell'], 'edge0-145b')
        self.assertEqual(self.e['karten'], ['RTX 3090'])
        self.assertEqual((self.e['port'], self.e['bedarf_je_karte_mib'], self.e['ram_bedarf_gib'],
                          self.e['startzeit_max_s'], self.e['fit_max_tokens']), (8109, 23500, 40, 300, True))
        self.assertNotIn('vision_exe', self.e)
        # Standard ist „RAM sparen“ (Sascha 14.11.2026); „schnell“ nimmt die Einstellung ohne --resident-experts.
        standard, schnell = planung.variante(self.e), planung.variante(self.e, '1gpu-128k')
        self.assertTrue(self.e['konfig'].endswith('-1gpu-128k-ram-sparen.json'))
        self.assertEqual((standard['variante'], standard['konfig'], standard['ram_bedarf_gib']),
                         ('1gpu-128k-ram-sparen', self.e['konfig'], 40))
        self.assertEqual((schnell['konfig'], schnell['ram_bedarf_gib']),
                         (self.e['konfig'].replace('-ram-sparen', ''), 46))
        for feld in ('bedarf_grund', 'ram_grund'):
            self.assertIn('14.11.2026 gemessen', self.e[feld])
        for text in ('14.11.2026', 'Auftrag Sascha'):
            self.assertIn(text, self.e['eingebaut_grund'])
        self.assertNotIn(self.e['farbe'], [e['farbe'] for e in self.cfg['eintraege'] if e['id'] != self.e['id']])

    def test_erkennung_trennt_alle_drei_dienste(self):
        for pid in (60, 61, 62):
            with self.subTest(pid=pid):
                self.assertEqual(self.erf.ist_polystrata(pid, self.procs), 'edge0-145b')
                self.assertFalse(self.erf.ist_strata(pid, self.procs))
                self.assertEqual(self.erf.einordnen(pid, self.procs), ('polystrata:edge0-145b', self.e['name']))
        for pid in (63, 64):
            self.assertIsNone(self.erf.ist_polystrata(pid, self.procs))
            self.assertFalse(self.erf.ist_strata(pid, self.procs))
        for pid in (50, 51, 52, 53):
            self.assertEqual(self.erf.ist_polystrata(pid, self.procs), 'ornith-polystrata')
        for pid in (55, 56, 57):
            self.assertIsNone(self.erf.ist_polystrata(pid, self.procs))
            self.assertTrue(self.erf.ist_strata(pid, self.procs))

    def test_leerer_engine_pfad_nur_mit_eigenem_python_server(self):
        self.procs[56] = (57, 'strata.exe')
        for pid in (56, 62, 64):
            self.infos[pid] = ('', '')
        self.test_erkennung_trennt_alle_drei_dienste()
        for eltern in (0, 62, 63, 64, 50, 57):
            with self.subTest(eltern=eltern):
                self.procs[62] = (eltern, 'strata.exe')
                self.assertIsNone(self.erf.ist_polystrata(62, self.procs))
                self.assertEqual(self.erf.ist_strata(62, self.procs), eltern == 57)

    def test_ornith_erkennung_bei_leerem_pfad_bleibt_unveraendert(self):
        for pid in (52, 53):
            self.infos[pid] = ('', '')
            self.assertIsNone(self.erf.ist_polystrata(pid, self.procs))
            self.assertFalse(self.erf.ist_strata(pid, self.procs))

    def test_fremder_pfad_wird_nicht_durch_eltern_ersetzt(self):
        self.infos[62] = (r'C:\Fremd\strata.exe', '')
        self.assertIsNone(self.erf.ist_polystrata(62, self.procs))
        self.assertFalse(self.erf.ist_strata(62, self.procs))

    def test_zustaende_und_belegung_bleiben_getrennt(self):
        self.health.return_value = {'loaded': True, 'max_context': 131072, 'model': 'edge0-145b'}
        s = self.erf._dienste(self.procs, {8109: 61})
        self.assertEqual((s['edge0-145b']['zustand'], s['edge0-145b']['pids']), ('bereit', [60, 61, 62]))
        self.assertNotIn(62, s['strata']['pids'])
        self.assertNotIn(62, s['ornith-polystrata']['pids'])
        self.health.assert_called_once_with('http://127.0.0.1:8109/health', timeout=1.0)
        nur_edge0 = {p: self.procs[p] for p in (60, 61, 62)}
        s = self.erf._dienste(nur_edge0, {8109: 61})
        self.assertEqual(s['strata']['zustand'], 'aus')
        self.assertEqual(s['ornith-polystrata']['zustand'], 'aus')
        self.assertEqual(self.erf._dienste(self.procs, {8109: 57})['edge0-145b']['zustand'], 'fremd')
        karten = [{'index': 0, 'belegt': 23500, 'gesamt': 24576}]
        v = self.erf._verbraucher(nur_edge0, karten, {0: {62: 23500}}, {'geladen': []}, {})
        x = next(x for x in v if x['schluessel'] == 'polystrata:edge0-145b')
        self.assertEqual((x['eintrag'], x['mib_je_karte'], x['schritt']['id']),
                         ('edge0-145b', {0: 23500}, 'beenden:edge0-145b'))

    def test_start_ohne_bildteil_mit_gewaehlter_karte(self):
        self.starte_losgeloest.return_value = Mock(pid=70, poll=Mock(return_value=None))
        self.antwort.return_value = {'loaded': True, 'max_context': 131072}
        self.assertIn('ist bereit', self.akt.starten('edge0-145b', karte=0))
        args, kwargs = self.starte_losgeloest.call_args
        self.assertEqual(args[0], [self.e['python'], self.e['server_skript'], '--engine', 'strata', '--config',
                                   self.e['konfig'], '--port', '8109', '--gpu', '0', '--fit-max-tokens'])
        self.assertEqual(args[1], os.path.dirname(os.path.dirname(self.e['server_skript'])))
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'edge0-145b'))
        self.assertEqual([c.args[0] for c in self.datei.call_args_list],
                         [self.e[f] for f in ('python', 'server_skript', 'engine', 'konfig')])
        self.antwort.assert_called_once_with('http://127.0.0.1:8109/health', timeout=1.0)

    def test_kartenwahl_nimmt_eine_3090_mit_genug_platz(self):
        karten = [{'index': 0, 'belegt': 0, 'gesamt': 24576, 'name': 'RTX 3090'},
                  {'index': 1, 'belegt': 1500, 'gesamt': 24576, 'name': 'RTX 3090', 'monitor': True}]
        self.assertEqual(planung.karte_waehlen(karten, [], self.e, 768, 2048), (0, None))

    def test_stoppen_trifft_nur_edge0_auch_bei_leerem_pfad(self):
        for pfad in (self.e['engine'], ''):
            with self.subTest(pfad=pfad):
                self.infos[62] = (pfad, '')
                self.prozesse.return_value = {p: self.procs[p] for p in (50, 51, 52, 53, 55, 56, 57)}
                self.lauschende_ports.return_value = [('127.0.0.1', 8097, 51), ('127.0.0.1', 8095, 57)]
                self.beenden.reset_mock()
                self.assertEqual(self.akt.schritt('beenden:edge0-145b'), f"{self.e['name']} beendet.")
                self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [62, 60, 61])

    def test_anzeige_port_karte_und_link(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = dict(self.cfg, eintraege=[self.e])
        z.erf, z.akt, z.laufend = self.erf, self.akt, {}
        roh = {'dienste': {'edge0-145b': {'zustand': 'bereit', 'fremd': None, 'kontext': 131072}},
               'karten': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3090'}],
               'verbraucher': [{'schluessel': 'polystrata:edge0-145b', 'mib_je_karte': {0: 23500}}]}
        s = z._zustaende(roh)['edge0-145b']
        self.assertEqual(s['detail'], 'Kontext 131.072 · Port 8109 · RTX 3090')
        self.assertEqual(z.konfig()['eintraege'][0]['links'],
                         [{'art': 'polystrata', 'text': 'Chat öffnen', 'url': 'http://127.0.0.1:8109/'}])


if __name__ == '__main__':
    unittest.main()
