import ctypes
import json
import os
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gemeinsam import winapi  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class Programm(unittest.TestCase):
    def setUp(self):
        self.e = next(e for e in KONFIG['eintraege'] if e['id'] == 'dsh')
        self.log = Mock()
        self.akt = Aktionen(KONFIG, Mock(), 'logs', self.log)
        self.procs = {10: (0, 'DSH Desktop.exe'), 11: (10, 'DSH Desktop.exe'),
                      20: (0, 'DSH Desktop.exe'), 21: (10, 'anderes.exe'),
                      22: (0, 'DSH Desktop.exe'), 23: (0, 'DSH Desktop.exe')}
        self.pfade = {10: self.e['programm'], 11: self.e['programm'].upper().replace('\\', '/'),
                      20: r'C:\Fremd\DSH Desktop.exe', 21: r'C:\Fremd\anderes.exe',
                      22: self.e['programm'] + '.fremd'}
        for name in ('prozesse', 'prozess_details', 'fenster_schliessen', 'beenden'):
            p = patch('gemeinsam.winapi.' + name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.prozesse.side_effect = lambda: dict(self.procs)
        self.prozess_details.side_effect = lambda pid: (self.pfade[pid], '', 1) if pid in self.pfade else None

    def test_erst_fenster_dann_nur_rest_mit_exaktem_pfad(self):
        reihenfolge = []

        def schliessen(pids):
            reihenfolge.append('fenster')
            self.assertEqual(pids, [10, 11])
            del self.procs[10]  # Ein Prozess endet sanft.

        def beenden(pid):
            reihenfolge.append(pid)
            del self.procs[pid]

        def warten(fn, sekunden, takt):
            reihenfolge.append(sekunden)
            return fn()

        self.fenster_schliessen.side_effect = schliessen
        self.beenden.side_effect = beenden
        with patch('zentrale.aktionen._warten', side_effect=warten) as w:
            self.assertEqual(self.akt.stoppen('dsh'), 'DSH Desktop beendet.')
        self.assertEqual(reihenfolge, ['fenster', 8, 11, 5])
        self.beenden.assert_called_once_with(11)
        self.assertEqual([c.args[1:] for c in w.call_args_list], [(8, 0.5), (5, 0.5)])
        self.assertEqual(set(self.procs), {20, 21, 22, 23})
        self.assertEqual(self.log.call_args_list, [
            call('DSH Desktop: Fenster schließen angefordert, PID 10'),
            call('DSH Desktop: Fenster schließen angefordert, PID 11'),
            call('DSH Desktop beendet, PID 11')])

    def test_sanft_beendet_ohne_erzwungenes_ende(self):
        self.fenster_schliessen.side_effect = lambda pids: [self.procs.pop(p) for p in pids]
        with patch('zentrale.aktionen._warten', side_effect=lambda fn, s, t: fn()):
            self.assertEqual(self.akt.stoppen('dsh'), 'DSH Desktop beendet.')
        self.beenden.assert_not_called()

    def test_lief_nicht_ohne_passende_prozesse(self):
        for procs in ({}, {20: self.procs[20], 22: self.procs[22], 23: self.procs[23]}):
            with self.subTest(procs=procs), patch('zentrale.aktionen._warten') as w:
                self.procs = procs
                self.assertEqual(self.akt.stoppen('dsh'), 'DSH Desktop lief nicht.')
                w.assert_not_called()
        self.fenster_schliessen.assert_not_called()
        self.beenden.assert_not_called()

    def test_pfadaenderung_vor_erzwungenem_ende_wird_frisch_geprueft(self):
        self.procs = {10: self.procs[10]}
        # Erste Erfassung, sanfte Warteprüfung, Restliste, erneute Prüfung vor beenden, Abschlussprüfung.
        self.prozess_details.side_effect = [(self.e['programm'], '', 1)] * 3 + [
            (r'C:\Fremd\DSH Desktop.exe', '', 2)] * 2
        with patch('zentrale.aktionen._warten', side_effect=lambda fn, s, t: fn()):
            self.assertEqual(self.akt.stoppen('dsh'), 'DSH Desktop beendet.')
        self.beenden.assert_not_called()

    def test_verbliebene_prozesse_melden_fehler(self):
        with patch('zentrale.aktionen._warten', side_effect=lambda fn, s, t: fn()):
            with self.assertRaisesRegex(Fehler, 'DSH Desktop läuft nach dem Beenden noch'):
                self.akt.stoppen('dsh')
        self.assertEqual(self.beenden.call_args_list, [call(10), call(11)])

    def test_server_meldet_beenden_und_zustand_stoppt(self):
        z = Zentrale.__new__(Zentrale)
        z.eintraege, z.laufend = {'dsh': self.e}, {}

        def stoppen(eintrag_id, erzwingen):
            self.assertEqual((eintrag_id, erzwingen), ('dsh', False))
            self.assertEqual(z.laufend, {'dsh': 'stoppt'})
            return 'DSH Desktop beendet.'

        z.akt = Mock(stoppen=stoppen)

        def hintergrund(meldung, fn):
            self.assertEqual(meldung, 'DSH Desktop wird beendet …')
            self.assertEqual(fn(), 'DSH Desktop beendet.')
            return True

        z._im_hintergrund = hintergrund
        self.assertEqual(z.stoppen('dsh', False), (202, {'ok': True}))


class FensterSchliessen(unittest.TestCase):
    def test_alle_top_level_fenster_auch_unsichtbare_nur_ziel_pids(self):
        def enum(callback, _):
            for hwnd in (101, 102, 103, 104):
                self.assertTrue(callback(hwnd, 0))
            return True

        def pid(hwnd, zeiger):
            ctypes.cast(zeiger, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value = (
                10 if hwnd in (101, 102, 104) else 20)

        with patch.object(winapi._user32, 'EnumWindows', side_effect=enum), \
                patch.object(winapi._user32, 'GetWindowThreadProcessId', side_effect=pid), \
                patch.object(winapi._user32, 'PostMessageW', side_effect=[True, True, False]) as post, \
                patch.object(winapi._user32, 'IsWindowVisible', side_effect=AssertionError('Alle Fenster')):
            self.assertEqual(winapi.fenster_schliessen([10]), 2)
        self.assertEqual(post.call_args_list, [call(101, 0x0010, 0, 0), call(102, 0x0010, 0, 0),
                                              call(104, 0x0010, 0, 0)])


if __name__ == '__main__':
    unittest.main()
