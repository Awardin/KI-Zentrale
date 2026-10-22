"""Tests für die Art `python_dienst` am Beispiel Fibo 2.0.

Erkennung über Skriptpfad und Port (uv-Starter und Kind), Zustände über /health,
Kartenwahl, Starten, Beenden des ganzen Prozessbaums und „GPU freigeben“.
"""
import copy
import json
import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung, norm  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class PythonDienst(unittest.TestCase):
    """Fibo 2.0 als python_dienst: Erkennung, Zustand, Start, Stopp, Prozessbaum, Planung."""

    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.python_dienst['fibo2']
        cmd = f'"{self.e["python"]}" "{self.e["skript"]}" --port 8098'
        self.procs = {60: (0, 'python.exe'), 61: (60, 'python.exe'), 62: (0, 'python.exe'),
                      63: (0, 'python.exe'), 64: (0, 'python.exe'), 65: (0, 'python.exe')}
        self.infos = {
            60: (self.e['python'], cmd),                                            # uv-Starter
            61: (r'C:\Users\sasch\AppData\Roaming\uv\python\cpython\python.exe', cmd),  # Kind
            62: (self.e['python'], cmd.replace('8098', '8097')),                    # anderer Port
            63: (self.e['python'], cmd.replace('dienst.py', 'anderer.py')),         # anderes Skript
            64: (r'C:\Python\python.exe', 'python.exe -c "print(1)"'),              # fremd
            65: (r'C:\Python\python.exe', cmd),                                     # gleiche Zeile, fremder Pfad
        }
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}
        self.erf.messen = Mock(return_value={'dienste': {'fibo2': {'zustand': 'aus'}}, 'procs': self.procs})
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

    def test_eintrag_fibo2(self):
        self.assertEqual(self.e['art'], 'python_dienst')
        self.assertEqual((self.e['port'], self.e['health_pfad']), (8098, '/health'))
        self.assertEqual(self.e['karten'], ['RTX 3090'])
        self.assertEqual((self.e['bedarf_je_karte_mib'], self.e['ram_bedarf_gib'], self.e['startzeit_max_s']),
                         (19500, 36, 300))
        self.assertEqual(self.e['oeffnen_url'], 'http://127.0.0.1:3896/')
        self.assertEqual(self.e['oeffnen_text'], 'Atelier öffnen')
        self.assertTrue(self.e['skript'].endswith(os.path.join('KI-Zentrale', 'fibo', 'dienst.py')))
        self.assertEqual(KONFIG['eintraege'][-1]['id'], 'fibo2')   # am Ende angehängt
        self.assertEqual(next(e for e in KONFIG['eintraege'] if e['id'] == 'lightonocr')['port'], 8096)

    def test_erkennung_skript_und_port_egal_welcher_interpreter(self):
        for pid in (60, 61, 65):
            with self.subTest(pid=pid):
                self.assertEqual(self.erf.ist_python_dienst(pid, self.procs), 'fibo2')
        for pid in (62, 63, 64):
            with self.subTest(pid=pid):
                self.assertIsNone(self.erf.ist_python_dienst(pid, self.procs))
        self.assertEqual(self.erf.einordnen(61, self.procs), ('python_dienst:fibo2', self.e['name']))
        self.assertEqual(self.erf.einordnen(64, self.procs)[0], 'andere')

    def test_dienstzustand_health(self):
        self.health.return_value = {'status': 'ok', 'aktiv': 'dev', 'laufend': None}
        s = self.erf._dienste(self.procs, {8098: 61})['fibo2']
        self.assertEqual((s['zustand'], s['pids'], s['aktiv'], s['laufend']), ('bereit', [60, 61, 65], 'dev', None))
        self.health.assert_any_call('http://127.0.0.1:8098/health', timeout=1.0)
        self.health.return_value = {'status': 'loading'}
        self.assertEqual(self.erf._dienste(self.procs, {8098: 61})['fibo2']['zustand'], 'startet')
        self.health.return_value = {'status': 'ok', 'aktiv': 'turbo', 'laufend': 'abc123'}
        s = self.erf._dienste(self.procs, {8098: 61})['fibo2']
        self.assertEqual((s['zustand'], s['laufend'], s['aktiv']), ('bereit', 'abc123', 'turbo'))
        s = self.erf._dienste(self.procs, {8098: 64})['fibo2']
        self.assertEqual((s['zustand'], s['fremd']), ('fremd', 'Python'))
        self.assertEqual(self.erf._dienste(self.procs, {})['fibo2']['zustand'], 'startet')
        self.assertEqual(self.erf._dienste({}, {})['fibo2']['zustand'], 'aus')

    def test_verbraucher_beenden_und_freigabe(self):
        karten = [{'index': 0, 'belegt': 1000, 'gesamt': 24576}, {'index': 1, 'belegt': 19000, 'gesamt': 24576}]
        dienste = {'fibo2': {'zustand': 'bereit', 'laufend': None},
                   'comfy': {'auftraege_laufend': 0, 'laeuft': False}}
        v = self.erf._verbraucher(self.procs, karten, {1: {61: 17500.0}}, {'geladen': []}, dienste)
        x = next(x for x in v if x['schluessel'] == 'python_dienst:fibo2')
        self.assertEqual((x['eintrag'], x['mib_je_karte'], x['blockiert'], x['schritt']['id']),
                         ('fibo2', {1: 17500}, None, 'beenden:fibo2'))
        self.assertEqual(planung.plan_freigeben(v)['schritte'][0]['id'], 'beenden:fibo2')
        dienste['fibo2']['laufend'] = 'abc'
        v = self.erf._verbraucher(self.procs, karten, {1: {61: 17500.0}}, {'geladen': []}, dienste)
        x = next(x for x in v if x['schluessel'] == 'python_dienst:fibo2')
        self.assertIn('läuft gerade ein Auftrag', x['blockiert'])
        plan = planung.plan_freigeben(v)
        self.assertEqual(plan['schritte'], [])
        self.assertEqual(plan['gruende'], [x['blockiert']])

    def test_planung_waehlt_karte_und_bedarf(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = self.cfg
        z.eintraege = {e['id']: e for e in self.cfg['eintraege']}
        z.laufend = {}
        z.roh = {'karten': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3090', 'gesamt': 24576, 'belegt': 1000},
                            {'index': 1, 'name': 'NVIDIA GeForce RTX 3090', 'gesamt': 24576, 'belegt': 1000}],
                 'verbraucher': []}
        z._aktuell = Mock(return_value=z.roh)
        z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        z.akt = Mock()
        p = z.plan('fibo2', 'starten')
        self.assertEqual((p['karte'], p['karte_kurz'], p['bedarf_mib']), (0, 'RTX 3090 · Nr. 0', {'0': 19500}))
        self.assertTrue(p['genug_platz'])

    def test_start_argumente_karte_und_log(self):
        self.starte_losgeloest.return_value = Mock(pid=70, poll=Mock(return_value=None))
        self.antwort.side_effect = [ConnectionError(), {'status': 'loading'}, {'status': 'ok'}]
        with patch('zentrale.aktionen.time.sleep'):
            self.assertIn('ist bereit', self.akt.starten('fibo2', karte=1))
        args, kwargs = self.starte_losgeloest.call_args
        self.assertEqual(args[0], [self.e['python'], self.e['skript'], '--port', '8098'])
        self.assertEqual(args[1], os.path.dirname(self.e['skript']))
        self.assertEqual((args[2]['CUDA_VISIBLE_DEVICES'], args[2]['CUDA_DEVICE_ORDER'],
                          args[2]['PYTHONIOENCODING']), ('1', 'PCI_BUS_ID', 'utf-8'))
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'fibo2'))
        self.assertIn('gestartet auf Karte 1', self.log.call_args.args[0])

    def test_start_ohne_karte_ram_oder_datei(self):
        with self.assertRaisesRegex(Fehler, 'Keine Karte für .* gewählt'):
            self.akt.starten('fibo2')
        self.starte_losgeloest.assert_not_called()
        self.freier_arbeitsspeicher_mib.return_value = 10 * 1024
        with self.assertRaisesRegex(Fehler, 'Zu wenig freier Arbeitsspeicher: 10,0 GiB frei'):
            self.akt.starten('fibo2', karte=0)
        self.freier_arbeitsspeicher_mib.return_value = 40 * 1024
        self.datei.side_effect = lambda p: p != self.e['skript']
        with self.assertRaisesRegex(Fehler, 'Datei fehlt: '):
            self.akt.starten('fibo2', karte=0)
        self.starte_losgeloest.assert_not_called()

    def test_start_bereit_oder_fremd(self):
        self.erf.messen.return_value['dienste']['fibo2'] = {'zustand': 'bereit'}
        self.assertEqual(self.akt.starten('fibo2', karte=0), f"{self.e['name']} läuft bereits.")
        self.erf.messen.return_value['dienste']['fibo2'] = {'zustand': 'fremd', 'fremd': 'Python'}
        with self.assertRaisesRegex(Fehler, 'Port 8098 ist von Python belegt'):
            self.akt.starten('fibo2', karte=0)

    def test_startfehler_liest_fehlerausgabe_und_uv_starter_ende(self):
        self.starte_losgeloest.return_value = Mock(pid=70, poll=Mock(return_value=1))
        self.erf.messen.return_value['procs'] = {}
        with patch('zentrale.aktionen._letzte_meldung', return_value='CUDA out of memory') as letzte:
            with self.assertRaisesRegex(Fehler, 'CUDA out of memory'):
                self.akt.starten('fibo2', karte=0)
        letzte.assert_called_once_with(os.path.join('logs', 'fibo2.err.log'))

    def test_beenden_ganzer_prozessbaum_kind_zuerst(self):
        def prozesse():
            return {} if self.beenden.called else self.procs
        self.prozesse.side_effect = prozesse
        self.lauschende_ports.return_value = []
        self.antwort.return_value = {'status': 'ok', 'laufend': None}
        self.assertEqual(self.akt.schritt('beenden:fibo2'), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [61, 60, 65])

    def test_beenden_verweigert_laufenden_auftrag_und_erzwingt_dann(self):
        def prozesse():
            return {} if self.beenden.called else self.procs
        self.prozesse.side_effect = prozesse
        self.lauschende_ports.return_value = []
        self.antwort.return_value = {'status': 'ok', 'laufend': 'abc123'}
        with self.assertRaisesRegex(Fehler, 'läuft gerade ein Auftrag \\(abc123\\)'):
            self.akt.stoppen('fibo2')
        self.beenden.assert_not_called()
        self.assertEqual(self.akt.stoppen('fibo2', erzwingen=True), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [61, 60, 65])

    def test_beenden_laeuft_nicht(self):
        self.erf.messen.return_value['procs'] = {pid: self.procs[pid] for pid in (62, 63, 64)}
        self.assertEqual(self.akt.stoppen('fibo2'), f"{self.e['name']} lief nicht.")
        self.beenden.assert_not_called()

    def test_server_zustand_link_und_schritt(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = dict(self.cfg, eintraege=[self.e])
        z.erf, z.akt, z.laufend = self.erf, self.akt, {}
        roh = {'dienste': {'fibo2': {'zustand': 'bereit', 'fremd': None, 'laufend': None, 'aktiv': 'dev'}},
               'karten': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3090'}],
               'verbraucher': [{'schluessel': 'python_dienst:fibo2', 'mib_je_karte': {0: 17500}}]}
        s = z._zustaende(roh)['fibo2']
        self.assertEqual(s['detail'], 'Port 8098 · Dev · RTX 3090')
        self.assertEqual((s['karte'], s['auftrag'], s['laufend']), ('RTX 3090', False, None))
        roh['dienste']['fibo2'].update(laufend='abc123', aktiv='turbo')
        s = z._zustaende(roh)['fibo2']
        self.assertEqual(s['detail'], 'Port 8098 · Turbo · RTX 3090 · Auftrag abc123 läuft')
        self.assertEqual((s['auftrag'], s['laufend']), (True, 'abc123'))
        roh['dienste']['fibo2'].update(zustand='fremd', fremd='Python')
        self.assertEqual(z._zustaende(roh)['fibo2']['detail'], 'Port 8098 ist von Python belegt.')
        k = z.konfig()['eintraege'][0]
        self.assertEqual(k['links'], [{'art': 'python_dienst', 'text': 'Atelier öffnen',
                                       'url': 'http://127.0.0.1:3896/'}])
        z.melden = Mock()

        def schritt(sid):
            self.assertEqual(z.laufend, {'fibo2': 'stoppt'})
            return 'Beendet.'
        z.akt = Mock(schritt=schritt)
        z._schritte_ausfuehren(['beenden:fibo2'])
        self.assertEqual(z.laufend, {})


if __name__ == '__main__':
    unittest.main()
