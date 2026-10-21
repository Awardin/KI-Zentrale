import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zentrale import chat_app  # noqa: E402

C = {'node': r'C:\LLM\runtimes\node24\node.exe', 'ordner': r'C:\LLM\runtimes\Strata\apps\host', 'port': 8791,
     'daten': r'C:\x\daten', 'modelle': r'C:\x\modelle', 'logs': r'C:\x\logs', 'arbeitsordner': r'C:\x\arbeit'}
SKRIPT = r'C:\LLM\runtimes\Strata\apps\host\server\index.mjs'


class ChatAppTest(unittest.TestCase):
    def test_umgebung_abgesichert(self):
        env = chat_app.umgebung(C)
        self.assertEqual(env['STRATA_BIND'], '127.0.0.1')
        self.assertEqual(env['STRATA_PORT'], '8791')
        self.assertEqual(env['STRATA_NO_ACQUIRE'], '1')
        self.assertEqual(env['STRATA_NO_BUNDLED_ENGINE'], '1')
        self.assertEqual(env['STRATA_HOME'], C['daten'])
        self.assertTrue(env['PATH'].startswith(r'C:\LLM\runtimes\node24'))

    def test_erkennt_nur_eigenen_prozess(self):
        ports = [('127.0.0.1', 8791, 11), ('127.0.0.1', 8095, 12)]
        details = {11: (C['node'], f'"{C["node"]}" {SKRIPT} --dist dist', 1)}
        with mock.patch.object(chat_app.winapi, 'lauschende_ports', return_value=ports), \
                mock.patch.object(chat_app.winapi, 'prozess_details', side_effect=details.get):
            self.assertEqual(chat_app.prozess(C), 11)

    def test_fremder_prozess_auf_dem_port_wird_nicht_erkannt(self):
        ports = [('127.0.0.1', 8791, 11)]
        with mock.patch.object(chat_app.winapi, 'lauschende_ports', return_value=ports), \
                mock.patch.object(chat_app.winapi, 'prozess_details',
                                  return_value=(r'C:\Program Files\nodejs\node.exe', 'node anderes.js', 1)):
            self.assertIsNone(chat_app.prozess(C))
            self.assertTrue(chat_app.status(C)['port_fremd_belegt'])

    def test_beenden_ohne_laufenden_dienst_beendet_nichts(self):
        with mock.patch.object(chat_app, 'prozess', return_value=None), \
                mock.patch.object(chat_app.winapi, 'lauschende_ports', return_value=[]), \
                mock.patch.object(chat_app.winapi, 'beenden') as beenden:
            code, _ = chat_app.beenden(C)
        self.assertEqual(code, 200)
        beenden.assert_not_called()


if __name__ == '__main__':
    unittest.main()
