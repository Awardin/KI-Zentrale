import copy
import json
import os
import sys
import threading
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


class LlamaCpp(unittest.TestCase):
    """LightOnOCR als llama.cpp-Dienst: Erkennung, Zustand, Starten, Beenden, Planung."""

    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.llamacpp['lightonocr']
        cmd = (f'"{self.e["programm"]}" -m "{self.e["modelldatei"]}" --mmproj "{self.e["mmproj"]}" '
               f'--host 127.0.0.1 --port 8096 --alias lightonocr-3-4b -ngl 99')
        self.procs = {30: (0, 'llama-server.exe'), 31: (0, 'llama-server.exe'), 32: (0, 'llama-server.exe'),
                      33: (0, 'llama-server.exe'), 34: (0, 'python.exe')}
        self.infos = {
            30: (self.e['programm'], cmd),
            31: (self.e['programm'], cmd.replace('8096', '8097')),               # anderer Port
            32: (r'C:\Fremd\llama-server.exe', cmd),                             # anderes Programm
            33: (self.e['programm'], cmd.replace('Q4_K_M', 'Q8_0')),             # andere Modelldatei
            34: (r'C:\Python\python.exe', cmd),
        }
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}
        self.erf.messen = Mock(return_value={'dienste': {'lightonocr': {'zustand': 'aus'}}, 'procs': self.procs})
        self.log = Mock()
        self.akt = Aktionen(self.cfg, self.erf, 'logs', self.log)
        for name in ('starte_losgeloest', 'beenden', 'prozesse', 'lauschende_ports'):
            p = patch('gemeinsam.winapi.' + name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        p = patch('zentrale.erfassung.http_json')
        self.health = p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.http_json')
        self.antwort = p.start()
        self.addCleanup(p.stop)
        p = patch('zentrale.aktionen.os.path.exists', return_value=True)
        self.datei = p.start()
        self.addCleanup(p.stop)

    def test_eintrag_kartenliste(self):
        self.assertEqual(self.e['karten'], ['RTX 3080', 'RTX 3090'])
        self.assertEqual(self.e['bedarf_je_karte_mib'], 4700)
        self.assertNotIn('karte', self.e)
        self.assertNotIn('bedarf_mib', self.e)

    def test_erkennung_nur_mit_programm_port_und_modelldatei(self):
        self.assertEqual(self.erf.ist_llamacpp(30, self.procs), 'lightonocr')
        for pid in (31, 32, 33, 34):
            with self.subTest(pid=pid):
                self.assertIsNone(self.erf.ist_llamacpp(pid, self.procs))
        self.assertEqual(self.erf.einordnen(30, self.procs), ('llamacpp:lightonocr', self.e['name']))
        self.assertEqual(self.erf.einordnen(32, self.procs)[0], 'andere')

    def test_dienstzustand(self):
        self.health.return_value = {'status': 'ok'}
        s = self.erf._dienste(self.procs, {8096: 30})['lightonocr']
        self.assertEqual((s['zustand'], s['pids']), ('bereit', [30]))
        self.health.assert_any_call('http://127.0.0.1:8096/health', timeout=1.0)
        # Während das Modell lädt, antwortet llama-server mit 503.
        self.health.side_effect = urllib.error.HTTPError('u', 503, 'Loading model', {}, None)
        self.assertEqual(self.erf._dienste(self.procs, {8096: 30})['lightonocr']['zustand'], 'startet')
        self.health.side_effect = None
        s = self.erf._dienste(self.procs, {8096: 32})['lightonocr']
        self.assertEqual((s['zustand'], s['fremd']), ('fremd', 'llama-server'))
        self.assertEqual(self.erf._dienste(self.procs, {})['lightonocr']['zustand'], 'startet')
        self.assertEqual(self.erf._dienste({}, {})['lightonocr']['zustand'], 'aus')

    def test_verbraucher_mit_beenden_schritt_und_planung(self):
        karten = [{'index': 0, 'belegt': 1000, 'gesamt': 24576}, {'index': 1, 'belegt': 5600, 'gesamt': 20480}]
        v = self.erf._verbraucher(self.procs, karten, {1: {30: 4500.0}}, {'geladen': []},
                                  {'comfy': {'auftraege_laufend': 0, 'laeuft': False}})
        x = next(x for x in v if x['schluessel'] == 'llamacpp:lightonocr')
        self.assertEqual((x['eintrag'], x['mib_je_karte'], x['schritt']['id']),
                         ('lightonocr', {1: 4500}, 'beenden:lightonocr'))
        # Strata braucht fast die ganze 3080: LightOnOCR muss dafür weichen.
        strata = self.erf.strata
        plan = planung.plan_fuer_start(karten, v, strata, 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['beenden:lightonocr'])
        self.assertEqual(planung.plan_freigeben(v)['schritte'][0]['id'], 'beenden:lightonocr')

    def test_start_argumente_karte_und_log(self):
        self.starte_losgeloest.return_value = Mock(pid=40, poll=Mock(return_value=None))
        self.antwort.side_effect = [urllib.error.HTTPError('u', 503, 'Loading', {}, None), {'status': 'ok'}]
        with patch('zentrale.aktionen.time.sleep'):
            self.assertIn('ist bereit', self.akt.starten('lightonocr', karte=2))
        args, kwargs = self.starte_losgeloest.call_args
        self.assertEqual(args[0][:9], [self.e['programm'], '-m', self.e['modelldatei'], '--mmproj', self.e['mmproj'],
                                       '--host', '127.0.0.1', '--port', '8096'])
        self.assertEqual(args[0][9:11], ['--alias', 'lightonocr-3-4b'])
        self.assertIn('{"enable_thinking":false}', args[0])
        self.assertEqual(args[1], os.path.dirname(self.e['programm']))
        self.assertEqual((args[2]['CUDA_VISIBLE_DEVICES'], args[2]['CUDA_DEVICE_ORDER']), ('2', 'PCI_BUS_ID'))
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'lightonocr'))
        self.log.assert_called_once_with(f"{self.e['name']} gestartet auf Karte 2, PID 40, Port 8096")

    def test_start_ohne_karte_kein_start(self):
        with self.assertRaisesRegex(Fehler, 'Keine Karte für .* gewählt'):
            self.akt.starten('lightonocr')
        self.starte_losgeloest.assert_not_called()
        self.erf.messen.assert_not_called()

    def test_warten_auf_wirksamen_bedarf(self):
        self.erf.messen.return_value['karten'] = [{'index': 2, 'gesamt': 20480, 'belegt': 14000}]
        with patch('zentrale.aktionen._warten', side_effect=lambda fn, s: fn()):
            self.assertTrue(self.akt.warten_auf_platz(self.e, 768, bedarf={2: 4700}))
            self.erf.messen.return_value['karten'][0]['belegt'] = 16000
            self.assertFalse(self.akt.warten_auf_platz(self.e, 768, bedarf={2: 4700}))

    def test_start_bereit_fremd_oder_datei_fehlt(self):
        self.erf.messen.return_value['dienste']['lightonocr'] = {'zustand': 'bereit'}
        self.assertEqual(self.akt.starten('lightonocr', karte=2), f"{self.e['name']} läuft bereits.")
        self.erf.messen.return_value['dienste']['lightonocr'] = {'zustand': 'fremd', 'fremd': 'Python'}
        with self.assertRaisesRegex(Fehler, 'Port 8096 ist von Python belegt'):
            self.akt.starten('lightonocr', karte=2)
        self.erf.messen.return_value['dienste']['lightonocr'] = {'zustand': 'aus'}
        self.datei.side_effect = lambda p: p != self.e['mmproj']
        with self.assertRaises(Fehler) as ex:
            self.akt.starten('lightonocr', karte=2)
        self.assertEqual(str(ex.exception), 'Datei fehlt: ' + self.e['mmproj'])
        self.starte_losgeloest.assert_not_called()

    def test_startfehler_liest_fehlerausgabe(self):
        self.starte_losgeloest.return_value = Mock(pid=40, poll=Mock(return_value=1))
        with patch('zentrale.aktionen._letzte_meldung', return_value='CUDA error') as letzte:
            with self.assertRaisesRegex(Fehler, 'CUDA error'):
                self.akt.starten('lightonocr', karte=2)
        letzte.assert_called_once_with(os.path.join('logs', 'lightonocr.err.log'))

    def test_beenden_nur_eigener_prozess(self):
        self.prozesse.return_value = {}
        self.lauschende_ports.return_value = []
        self.assertEqual(self.akt.schritt('beenden:lightonocr'), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [30])
        self.erf.messen.return_value['procs'] = {31: self.procs[31], 32: self.procs[32]}
        self.beenden.reset_mock()
        self.assertEqual(self.akt.stoppen('lightonocr'), f"{self.e['name']} lief nicht.")
        self.beenden.assert_not_called()

    def test_server_zustand_und_schritt(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = dict(self.cfg, eintraege=[self.e])
        z.erf, z.akt, z.laufend = self.erf, self.akt, {}
        roh = {'dienste': {'lightonocr': {'zustand': 'bereit', 'fremd': None}}}
        self.assertEqual(z._zustaende(roh)['lightonocr']['detail'], 'Port 8096')
        self.assertIsNone(z._zustaende(roh)['lightonocr']['karte'])
        roh['karten'] = [{'index': 0, 'name': 'NVIDIA GeForce RTX 3080'},
                         {'index': 2, 'name': 'NVIDIA GeForce RTX 3090'}]
        for anteile, name in (({0: 300, 2: 4500}, 'RTX 3090'), ({0: 4500, 2: 255}, 'RTX 3080'),
                              ({0: 255, 2: 200}, None), ({0: 256}, 'RTX 3080')):
            with self.subTest(anteile=anteile):
                roh['verbraucher'] = [{'schluessel': 'llamacpp:lightonocr', 'mib_je_karte': anteile},
                                      {'schluessel': 'andere', 'mib_je_karte': {2: 8000}}]
                s = z._zustaende(roh)['lightonocr']
                self.assertEqual(s['karte'], name)
                self.assertEqual(s['detail'], 'Port 8096' + (f' · {name}' if name else ''))
        roh['dienste']['lightonocr'].update(zustand='fremd', fremd='Python')
        self.assertEqual(z._zustaende(roh)['lightonocr']['detail'], 'Port 8096 ist von Python belegt.')
        self.assertIsNone(z._zustaende(roh)['lightonocr']['karte'])
        self.assertNotIn('links', z.konfig()['eintraege'][0])
        self.assertEqual(z.konfig()['eintraege'][0]['karten'], ['RTX 3080', 'RTX 3090'])
        self.assertEqual(z.konfig()['eintraege'][0]['bedarf_je_karte_mib'], 4700)
        z.melden = Mock()

        def schritt(sid):
            self.assertEqual(z.laufend, {'lightonocr': 'stoppt'})
            return 'Beendet.'
        z.akt = Mock(schritt=schritt)
        z._schritte_ausfuehren(['beenden:lightonocr'])
        self.assertEqual(z.laufend, {})


class KartenlisteServer(unittest.TestCase):
    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = KONFIG
        self.e = next(e for e in KONFIG['eintraege'] if e['id'] == 'lightonocr')
        self.z.eintraege = {e['id']: e for e in KONFIG['eintraege']}
        self.z.laufend = {}
        self.roh = {'karten': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3090', 'gesamt': 24576, 'belegt': 1000}],
                    'verbraucher': []}
        self.z._aktuell = Mock(return_value=self.roh)
        self.z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        self.z.akt = Mock()
        self.z._schritte_ausfuehren = Mock()
        self.z._im_hintergrund = Mock(side_effect=lambda text, fn: (fn(), True)[1])

    def test_plan_liefert_karte_name_und_bedarf(self):
        p = self.z.plan('lightonocr', 'starten')
        self.assertEqual((p['karte'], p['karte_kurz'], p['bedarf_mib']), (0, 'RTX 3090', {'0': 4700}))
        self.assertTrue(p['genug_platz'])
        self.assertEqual(p['schritte'], [])

    def test_plan_beruecksichtigt_anmeldungen(self):
        # Zwei RTX 3090: LightOnOCR geht auf die engste Karte, auf der es passt (teilt sie sich mit anderen).
        self.roh['karten'].append({'index': 2, 'name': 'NVIDIA GeForce RTX 3090',
                                   'gesamt': 24576, 'belegt': 14000})
        self.assertEqual(self.z.plan('lightonocr', 'starten')['karte'], 2)
        self.z._anmeldung_rest.return_value = ({2: 6000}, 'Werkstatt', '#000')
        self.assertEqual(self.z.plan('lightonocr', 'starten')['karte'], 0)

    def test_start_uebergibt_karte_auch_ohne_freigabe(self):
        for ohne in (False, True):
            with self.subTest(ohne=ohne):
                self.z.akt.reset_mock()
                self.assertEqual(self.z.starten('lightonocr', [], ohne), (202, {'ok': True}))
                self.z.akt.starten.assert_called_once_with('lightonocr', karte=0)

    def test_start_nach_schritten_wartet_auf_gewaehlte_karte(self):
        self.roh['karten'][0]['belegt'] = 23000
        self.roh['verbraucher'] = [{'eintrag': 'strata', 'mib_je_karte': {0: 22000}, 'blockiert': None,
                                   'schritt': {'id': 'beenden:strata', 'text': 'Strata beenden'}}]
        reihenfolge = []
        self.z._schritte_ausfuehren.side_effect = lambda s: reihenfolge.append('schritte')
        self.z.akt.warten_auf_platz.side_effect = lambda *a, **k: reihenfolge.append('warten')
        self.z.akt.starten.side_effect = lambda *a, **k: reihenfolge.append('starten')
        self.assertEqual(self.z.starten('lightonocr', ['beenden:strata'], False)[0], 202)
        self.assertEqual(reihenfolge, ['schritte', 'warten', 'starten'])
        self.z.akt.warten_auf_platz.assert_called_once_with(self.e, 768, bedarf={0: 4700})
        self.z.akt.starten.assert_called_once_with('lightonocr', karte=0)

    def test_ohne_freigabe_nur_karte_aus_plan_keine_schritte(self):
        self.roh['karten'][0]['belegt'] = 23000
        self.assertEqual(self.z.starten('lightonocr', ['beenden:strata'], True)[0], 202)
        self.z._schritte_ausfuehren.assert_not_called()
        self.z.akt.warten_auf_platz.assert_not_called()
        self.z.akt.starten.assert_called_once_with('lightonocr', karte=0)

    def test_veraltete_schritte_werden_abgelehnt(self):
        self.assertEqual(self.z.starten('lightonocr', ['beenden:strata'], False)[0], 409)
        self.z._im_hintergrund.assert_not_called()

    def test_ohne_wunschkarte_plan_und_start_abgelehnt(self):
        self.roh['karten'][0]['name'] = 'NVIDIA GeForce RTX 4090'
        grund = 'Keine der Karten RTX 3080, RTX 3090 ist erkannt.'
        self.assertEqual(self.z.plan('lightonocr', 'starten'),
                         {'schritte': [], 'genug_platz': False, 'hinweise': [], 'gruende': [grund],
                          'karte': None, 'karte_kurz': None, 'bedarf_mib': {}})
        for ohne in (False, True):
            self.assertEqual(self.z.starten('lightonocr', [], ohne), (409, {'fehler': grund}))
        self.z._im_hintergrund.assert_not_called()

    def test_andere_eintraege_bleiben_unveraendert(self):
        self.assertEqual(self.z.plan('dsh', 'starten'),
                         {'schritte': [], 'genug_platz': True, 'hinweise': [], 'gruende': []})
        self.assertEqual(self.z.starten('dsh', [], False)[0], 202)
        self.z.akt.starten.assert_called_once_with('dsh')

    def test_kurzname_aus_gemessenem_stand(self):
        self.z.roh = self.roh
        self.roh['karten'][0]['name'] = 'NVIDIA GeForce RTX 3080'
        self.assertEqual(self.z._kurzname(0), 'RTX 3080')

    def test_belegungsanzeige_und_platz_mit_gemessenen_namen(self):
        self.z.cfg = dict(KONFIG, eintraege=[self.e])
        self.z.erf = Mock(ollama_tags={})
        self.z._lock, self.z._platz_lock = threading.Lock(), threading.Lock()
        self.z.verlauf, self.z.aktion = [], None
        self.roh['karten'] = [dict(index=i, name='NVIDIA GeForce ' + name, gesamt=20480, belegt=1000,
                                  temp=30, last=0, watt=20) for i, name in
                              ((0, 'RTX 3080'), (1, 'RTX 3090'), (2, 'RTX 3090'))]
        self.roh.update(zeit=100, dauer_ms=1, ollama={'erreichbar': False, 'geladen': []},
                        dienste={'lightonocr': {'zustand': 'aus'}, 'comfy': {'auftraege_laufend': 0}})
        self.z._uebernehmen(self.roh)
        namen = ['RTX 3080', 'RTX 3090 · Nr. 1', 'RTX 3090 · Nr. 2']
        self.assertEqual([k['kurz'] for k in self.z.stand['karten']], namen)
        code, antwort = self.z.platz({})
        self.assertEqual(code, 200)
        self.assertEqual([k['kurz'] for k in antwort['karten']], namen)


if __name__ == '__main__':
    unittest.main()
