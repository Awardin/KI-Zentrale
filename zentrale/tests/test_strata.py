import copy
import ctypes
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gemeinsam import winapi  # noqa: E402
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung, norm  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class Strata(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.e = self.erf.strata
        self.procs = {10: (0, 'python.exe'), 11: (10, 'python.exe'), 12: (11, 'strata.exe'),
                      20: (0, 'python.exe'), 21: (0, 'pythonw.exe'), 22: (0, 'python.exe'),
                      23: (0, 'strata.exe'), 24: (0, 'anderes.exe')}
        cmd = f'"{self.e["server_skript"]}" --engine strata --config konfig.json --port 8095'
        self.infos = {
            10: (self.e['python'], cmd),
            11: (sys.executable, cmd),
            12: (self.e['engine'], '--serve --pack modell'),
            20: (sys.executable, cmd.replace(' --port 8095', '')),
            21: (sys.executable, cmd),
            22: (sys.executable, cmd.replace('8095', '8096')),
            23: (r'C:\Fremd\strata.exe', '--serve'),
            24: (r'C:\Fremd\anderes.exe', cmd),
        }
        self.erf.info = lambda pid, name: {'pid': pid, 'name': name, 'pfad': norm(self.infos[pid][0]),
                                          'cmd': self.infos[pid][1].lower()}
        self.erf.messen = Mock(return_value={'dienste': {'strata': {'zustand': 'aus'}}, 'procs': self.procs})
        self.log = Mock()
        self.akt = Aktionen(self.cfg, self.erf, 'logs', self.log)
        # Jeder Systemzugriff ist gestellt; die Tests starten oder beenden keine Dienste.
        for name in ('starte_losgeloest', 'beenden', 'prozesse', 'lauschende_ports',
                     'freier_arbeitsspeicher_mib'):
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
        self.freier_arbeitsspeicher_mib.return_value = 50 * 1024

    def test_ist_strata_engine_venv_basis_und_pythonw(self):
        for pid in (10, 11, 12, 21):
            with self.subTest(pid=pid):
                self.assertTrue(self.erf.ist_strata(pid, self.procs))

    def test_ist_strata_lehnt_fremde_prozesse_ab(self):
        for pid in (20, 22, 23, 24, 99):
            with self.subTest(pid=pid):
                self.assertFalse(self.erf.ist_strata(pid, self.procs))

    def test_engine_ohne_lesbaren_pfad_ueber_den_server(self):
        # 29.10.2026: Windows lieferte für strata.exe und strata-vision.exe keinen Pfad; ihr Elternprozess ist der Server.
        self.procs.update({14: (11, 'strata.exe'), 15: (11, 'strata-vision.exe'), 16: (20, 'strata.exe'),
                           17: (0, 'strata.exe'), 18: (24, 'strata-vision.exe')})
        self.infos.update({14: ('', ''), 15: ('', ''), 16: ('', ''), 17: ('', ''), 18: ('', '')})
        self.assertTrue(self.erf.ist_strata(14, self.procs))
        self.assertTrue(self.erf.ist_strata(15, self.procs))
        for pid in (16, 17, 18):   # fremder Server, kein Elternprozess, Elternprozess ist kein Python
            with self.subTest(pid=pid):
                self.assertFalse(self.erf.ist_strata(pid, self.procs))

    def _bildprozesse(self):
        self.procs.update({13: (11, 'strata-vision.exe'), 25: (0, 'strata-vision.exe')})
        self.infos.update({13: (self.e['vision_exe'], ''),
                           25: (r'C:\Fremd\strata-vision.exe', '')})

    def test_bildprozess_nur_mit_passendem_pfad(self):
        self._bildprozesse()
        self.assertTrue(self.erf.ist_strata(13, self.procs))
        self.assertFalse(self.erf.ist_strata(25, self.procs))
        self.assertEqual(self.erf.einordnen(13, self.procs), ('strata', self.e['name']))
        v = self.erf._verbraucher(self.procs, [{'index': 0, 'gesamt': 24576, 'belegt': 23359}],
                                 {0: {12: 23300, 13: 59}}, {'geladen': []}, {})
        self.assertEqual(next(x for x in v if x['schluessel'] == 'strata')['mib_je_karte'], {0: 23359})

    def test_bildprozess_pfad_optional_oder_abweichend(self):
        self._bildprozesse()
        for vision in (None, r'C:\AndererOrdner\strata-vision.exe'):
            with self.subTest(vision=vision):
                cfg = copy.deepcopy(self.cfg)
                e = next(e for e in cfg['eintraege'] if e['art'] == 'strata')
                if vision is None:
                    del e['vision_exe']
                else:
                    e['vision_exe'] = vision
                with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse'):
                    erf = Erfassung(cfg)
                erf.info = self.erf.info
                self.assertEqual(erf.ist_strata(13, self.procs), vision is None)
                if vision:
                    self.infos[25] = (vision, '')
                    self.assertTrue(erf.ist_strata(25, self.procs))

    def test_stoppt_engine_bildprozess_python_in_dieser_reihenfolge(self):
        self._bildprozesse()
        self.prozesse.return_value = {}
        self.lauschende_ports.return_value = []
        self.assertEqual(self.akt.stoppen(self.e['id']), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [12, 13, 10, 11, 21])
        self.assertEqual([c.args[0] for c in self.log.call_args_list],
                         ['Strata beendet, PID ' + str(p) for p in (12, 13, 10, 11, 21)])

    def test_ist_strata_erkennt_vollstaendig_quotierte_kommandozeile(self):
        for pid in (10, 11):
            for port in (8095, 8096):
                with self.subTest(pid=pid, port=port):
                    python = self.infos[pid][0]
                    cmd = (f'"{python}"  "{self.e["server_skript"]}" "--engine" "strata" '
                           f'"--config" "{self.e["konfig"]}" "--port" "{port}"')
                    self.infos[pid] = (python, cmd)
                    self.assertEqual(self.erf.ist_strata(pid, self.procs), port == 8095)

    def test_ist_strata_lehnt_anderen_namen_ohne_detailabfrage_ab(self):
        self.erf.info = Mock(side_effect=AssertionError('Keine Prozessabfrage nötig'))
        self.assertFalse(self.erf.ist_strata(24, self.procs))
        self.erf.info.assert_not_called()

    def test_ohne_strata_eintrag_bleibt_erfassung_unveraendert(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['eintraege'] = [e for e in cfg['eintraege'] if e['art'] != 'strata']
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            erf = Erfassung(cfg)
        erf.info = Mock(side_effect=AssertionError('Keine Prozessabfrage nötig'))
        self.assertFalse(erf.ist_strata(12, self.procs))
        self.assertNotIn('strata', erf._dienste({}, {}))

    def test_health_bereit_mit_kontext_und_allen_pids(self):
        self.health.return_value = {'loaded': True, 'max_context': 131072}
        s = self.erf._dienste(self.procs, {8095: 11})['strata']
        self.assertEqual(s, {'zustand': 'bereit', 'pids': [10, 11, 12, 21], 'fremd': None, 'kontext': 131072,
                             'modell': None})
        self.health.assert_called_once_with('http://127.0.0.1:8095/health', timeout=1.0)

    def test_health_noch_nicht_geladen_oder_nicht_erreichbar(self):
        for antwort in ({'loaded': False}, {}, None):
            with self.subTest(antwort=antwort):
                self.health.return_value = antwort
                self.assertEqual(self.erf._dienste(self.procs, {8095: 11})['strata']['zustand'], 'startet')
        self.health.side_effect = OSError('Noch nicht erreichbar')
        self.assertEqual(self.erf._dienste(self.procs, {8095: 11})['strata']['zustand'], 'startet')

    def test_port_fremd_wird_nicht_abgefragt(self):
        s = self.erf._dienste(self.procs, {8095: 20})['strata']
        self.assertEqual((s['zustand'], s['fremd']), ('fremd', 'Python'))
        self.health.assert_not_called()

    def test_port_frei_startet_oder_aus(self):
        self.assertEqual(self.erf._dienste(self.procs, {})['strata']['zustand'], 'startet')
        self.assertEqual(self.erf._dienste({}, {})['strata']['zustand'], 'aus')
        self.health.assert_not_called()

    def _verbraucher(self):
        karten = [{'index': 0, 'gesamt': 24576, 'belegt': 24300},
                  {'index': 1, 'gesamt': 20480, 'belegt': 19350}]
        v = self.erf._verbraucher(self.procs, karten, {0: {12: 23300}, 1: {12: 19300}},
                                 {'geladen': []}, {})
        return karten, v

    def test_belegung_auf_beiden_karten_und_gpu_freigeben(self):
        self.assertEqual(self.erf.einordnen(12, self.procs), ('strata', self.e['name']))
        _, v = self._verbraucher()
        s = next(x for x in v if x['schluessel'] == 'strata')
        self.assertEqual(s['mib_je_karte'], {0: 23300, 1: 19300})
        self.assertEqual((s['eintrag'], s['farbe'], s['blockiert']), (self.e['id'], '#7A4FB5', None))
        self.assertEqual(planung.plan_freigeben(v)['schritte'][0]['id'], 'beenden:strata')

    def test_strata_muss_fuer_ninfer_weichen(self):
        karten, v = self._verbraucher()
        karten = [dict(k, name='NVIDIA GeForce RTX 3090') for k in karten]
        n = self.erf.ninfer
        idx, grund = planung.karte_waehlen(karten, v, n, 768)
        self.assertEqual((idx, grund), (0, None))  # Karte 1 wäre auch leer zu klein
        plan = planung.plan_fuer_start(karten, v, dict(n, bedarf_mib={idx: n['bedarf_je_karte_mib']}), 768)
        self.assertTrue(plan['genug_platz'])
        self.assertEqual([s['id'] for s in plan['schritte']], ['beenden:strata'])

    def test_ram_fehlermeldung_verhindert_start(self):
        self.freier_arbeitsspeicher_mib.return_value = 35.25 * 1024
        with self.assertRaises(Fehler) as ex:
            self.akt.starten(self.e['id'])
        self.assertEqual(str(ex.exception), 'Zu wenig freier Arbeitsspeicher: 35,2 GiB frei, '
                         'Strata braucht etwa 42,0 GiB. Bitte große Programme schließen.')
        self.starte_losgeloest.assert_not_called()

    def test_start_bereit_oder_fremd_startet_nicht(self):
        self.erf.messen.return_value['dienste']['strata'] = {'zustand': 'bereit'}
        self.assertEqual(self.akt.starten(self.e['id']), f"{self.e['name']} läuft bereits.")
        self.erf.messen.return_value['dienste']['strata'] = {'zustand': 'fremd', 'fremd': 'Python'}
        with self.assertRaisesRegex(Fehler, 'Port 8095 ist von Python belegt'):
            self.akt.starten(self.e['id'])
        self.starte_losgeloest.assert_not_called()

    def test_fehlende_startdateien_werden_genannt(self):
        for feld in ('python', 'server_skript', 'engine', 'konfig'):
            with self.subTest(feld=feld):
                self.datei.side_effect = lambda p: p != self.e[feld]
                with self.assertRaises(Fehler) as ex:
                    self.akt.starten(self.e['id'])
                self.assertEqual(str(ex.exception), 'Datei fehlt: ' + self.e[feld])
        self.starte_losgeloest.assert_not_called()

    def test_start_argumente_arbeitsordner_env_logs_und_kontext(self):
        self.starte_losgeloest.return_value = Mock(pid=30, poll=Mock(return_value=None))
        self.antwort.side_effect = [{'loaded': False}, {'loaded': True, 'max_context': 131072}]
        with patch('zentrale.aktionen.time.sleep'):
            meldung = self.akt.starten(self.e['id'])
        self.assertIn('Kontext 131.072', meldung)
        args, kwargs = self.starte_losgeloest.call_args
        self.assertEqual(args[0], [self.e['python'], self.e['server_skript'], '--engine', 'strata',
                                  '--config', self.e['konfig'], '--port', '8095', '--fit-max-tokens'])
        self.assertEqual(args[1], r'C:\LLM\runtimes\Strata')
        self.assertEqual(args[2]['PYTHONIOENCODING'], 'utf-8')
        self.assertEqual(kwargs['log_basis'], os.path.join('logs', 'strata'))
        self.antwort.assert_called_with('http://127.0.0.1:8095/health', timeout=1.0)

    def test_ohne_fit_max_tokens_kein_schalter(self):
        # Der Schalter kommt nur aus dem Eintrag (18.10.2026: Antwortlänge kürzen statt mit 400 ablehnen).
        self.e['fit_max_tokens'] = False
        self.starte_losgeloest.return_value = Mock(pid=30, poll=Mock(return_value=None))
        self.antwort.return_value = {'loaded': True, 'max_context': 131072}
        with patch('zentrale.aktionen.time.sleep'):
            self.akt.starten(self.e['id'])
        self.assertNotIn('--fit-max-tokens', self.starte_losgeloest.call_args[0][0])

    def test_bereits_startender_prozess_wird_nicht_doppelt_gestartet(self):
        self.erf.messen.return_value['dienste']['strata']['zustand'] = 'startet'
        self.antwort.return_value = {'loaded': True, 'max_context': 131072}
        self.assertIn('ist bereit', self.akt.starten(self.e['id']))
        self.starte_losgeloest.assert_not_called()

    def test_bereits_startender_prozess_wartet_auch_bei_wenig_ram(self):
        self.erf.messen.return_value['dienste']['strata']['zustand'] = 'startet'
        self.freier_arbeitsspeicher_mib.return_value = 128
        self.antwort.side_effect = [{'loaded': False}, {'loaded': True, 'max_context': 131072}]
        with patch('zentrale.aktionen.time.sleep') as schlafen:
            self.assertIn('ist bereit', self.akt.starten(self.e['id']))
        self.freier_arbeitsspeicher_mib.assert_not_called()
        self.starte_losgeloest.assert_not_called()
        self.assertEqual(self.antwort.call_count, 2)
        self.antwort.assert_called_with('http://127.0.0.1:8095/health', timeout=1.0)
        schlafen.assert_called_once_with(1)

    def test_startfehler_liest_stdout(self):
        self.starte_losgeloest.return_value = Mock(pid=30, poll=Mock(return_value=1))
        with patch('zentrale.aktionen._letzte_meldung', return_value='Engine fehlgeschlagen') as letzte:
            with self.assertRaisesRegex(Fehler, 'Engine fehlgeschlagen'):
                self.akt.starten(self.e['id'])
        letzte.assert_called_once_with(os.path.join('logs', 'strata.out.log'))

    def test_startzeit_limit(self):
        self.starte_losgeloest.return_value = Mock(pid=30, poll=Mock(return_value=None))
        self.antwort.return_value = {'loaded': False}
        with patch('zentrale.aktionen.time.time', side_effect=[0, 0, 301]):
            with self.assertRaisesRegex(Fehler, 'nach 300 s nicht'):
                self.akt.starten(self.e['id'])

    def test_stoppt_engine_vor_python_und_keine_fremden_prozesse(self):
        self.prozesse.return_value = {}
        self.lauschende_ports.return_value = []
        self.assertEqual(self.akt.stoppen(self.e['id']), f"{self.e['name']} beendet.")
        self.assertEqual([c.args[0] for c in self.beenden.call_args_list], [12, 10, 11, 21])
        self.assertEqual([c.args[0] for c in self.log.call_args_list],
                         ['Strata beendet, PID ' + str(p) for p in (12, 10, 11, 21)])

    def test_beenden_schritt_und_nicht_laufend(self):
        self.erf.messen.return_value['procs'] = {20: self.procs[20]}
        self.assertEqual(self.akt.schritt('beenden:strata'), f"{self.e['name']} lief nicht.")
        self.beenden.assert_not_called()

    def test_stoppen_wartet_auf_port_und_alle_prozesse(self):
        for port_belegt, prozess_da in ((True, False), (False, True)):
            with self.subTest(port=port_belegt, prozess=prozess_da):
                self.lauschende_ports.return_value = [('127.0.0.1', 8095, 20)] if port_belegt else []
                self.prozesse.return_value = {12: self.procs[12]} if prozess_da else {}
                with patch('zentrale.aktionen._warten', side_effect=lambda fn, s, takt: fn()) as warten:
                    with self.assertRaisesRegex(Fehler, 'noch nicht aus'):
                        self.akt.stoppen(self.e['id'])
                self.assertEqual(warten.call_args.args[1:], (15, 0.5))

    def test_server_zustand_link_und_stoppt_waehrend_schritt(self):
        z = Zentrale.__new__(Zentrale)
        z.cfg = dict(self.cfg, eintraege=[self.e])
        z.erf, z.akt, z.laufend = self.erf, self.akt, {}
        roh = {'dienste': {'strata': {'zustand': 'bereit', 'kontext': 131072, 'fremd': None}}}
        self.assertEqual(z._zustaende(roh)[self.e['id']]['detail'], 'Kontext 131.072 · Port 8095')
        # Mit Modellname nennt die Anzeige die laufende Fassung (Variante) statt nur den Kontext.
        roh['dienste']['strata'].update(modell='qwen3.8-flash-next-unsloth-ud-iq4_xs')
        self.assertEqual(z._zustaende(roh)[self.e['id']]['detail'],
                         'Q4 · genauer, etwas langsamer · 128K · mit Bildern · Port 8095')
        roh['dienste']['strata'].update(modell='qwen3.8-flash-next-iq3_xxs', kontext=262144)
        self.assertEqual(z._zustaende(roh)[self.e['id']]['detail'], '256K Kontext · ohne Bilder · Port 8095')
        roh['dienste']['strata'].update(modell='anderes-modell', kontext=131072)
        self.assertEqual(z._zustaende(roh)[self.e['id']]['detail'], 'Kontext 131.072 · Port 8095')
        roh['dienste']['strata'] = {'zustand': 'bereit', 'kontext': 131072, 'fremd': None}
        roh['dienste']['strata'].update(zustand='fremd', fremd='Python')
        self.assertEqual(z._zustaende(roh)[self.e['id']]['detail'], 'Port 8095 ist von Python belegt.')
        self.assertEqual(z.konfig()['eintraege'][0]['links'],
                         [{'art': 'strata', 'text': 'Chat öffnen', 'url': 'http://127.0.0.1:8095/'}])
        z.melden = Mock()
        def schritt(sid):
            self.assertEqual(sid, 'beenden:strata')
            self.assertEqual(z.laufend, {self.e['id']: 'stoppt'})
            return 'Beendet.'
        z.akt = Mock(schritt=schritt)
        z._schritte_ausfuehren(['beenden:strata'])
        self.assertEqual(z.laufend, {})


class Arbeitsspeicher(unittest.TestCase):
    def test_verfuegbarer_physischer_speicher_in_mib(self):
        def abfrage(zeiger):
            status = ctypes.cast(zeiger, ctypes.POINTER(winapi._MEMORYSTATUSEX)).contents
            self.assertEqual(status.dwLength, ctypes.sizeof(winapi._MEMORYSTATUSEX))
            status.ullAvailPhys = 42 * 1024 * 1048576
            return True
        with patch.object(winapi._k32, 'GlobalMemoryStatusEx', side_effect=abfrage):
            self.assertEqual(winapi.freier_arbeitsspeicher_mib(), 42 * 1024)


if __name__ == '__main__':
    unittest.main()
