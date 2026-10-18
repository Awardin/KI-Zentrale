import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung  # noqa: E402


class _Schein(BaseHTTPRequestHandler):
    """Antwortet wie Ollama; `abstuerze` Anfragen lang mit dem Fehler eines abgestürzten Modellprozesses."""
    abstuerze = 0
    anfragen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        daten = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        _Schein.anfragen.append(daten)
        if _Schein.abstuerze > 0:
            _Schein.abstuerze -= 1
            antwort, code = {'error': 'error reading llama-server response: read tcp ...'}, 500
        else:
            antwort, code = {'message': {'content': 'OK'}, 'eval_count': 3}, 200
        roh = json.dumps(antwort).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)


class OllamaWiederholen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), _Schein)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}/api/chat'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Schein.anfragen = []
        self.meldungen = []

    def senden(self):
        oeffnen = lambda f: json.load(f())  # noqa: E731
        with mock.patch.object(auswertung.time, 'sleep'):
            return auswertung.ollama_senden(self.url, {'model': 'x', 'options': {'num_batch': 256}},
                                            oeffnen, self.meldungen.append, 10)

    def test_ein_absturz_wird_wiederholt(self):
        _Schein.abstuerze = 1
        self.assertEqual(self.senden()['message']['content'], 'OK')
        self.assertEqual(len(_Schein.anfragen), 2)
        self.assertEqual(len(self.meldungen), 1)
        self.assertEqual(_Schein.anfragen[1]['options'], {'num_batch': 256})

    def test_zwei_abstuerze_melden_verstaendlich(self):
        _Schein.abstuerze = 5
        with self.assertRaises(RuntimeError) as e:
            self.senden()
        self.assertIn('zweimal abgestürzt', str(e.exception))
        self.assertEqual(len(_Schein.anfragen), 2)


if __name__ == '__main__':
    unittest.main()
