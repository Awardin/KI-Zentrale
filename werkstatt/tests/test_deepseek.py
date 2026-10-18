import calendar
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung  # noqa: E402

PREISE = {'cache_treffer': 0.006, 'eingabe': 0.3, 'ausgabe': 1.2}
HAUPTZEIT = [[1, 4], [6, 10]]


def utc(jahr, monat, tag, stunde):
    return calendar.timegm((jahr, monat, tag, stunde, 30, 0))


class Kosten(unittest.TestCase):
    nutzung = {'prompt_cache_hit_tokens': 1_000_000, 'prompt_cache_miss_tokens': 1_000_000,
               'completion_tokens': 1_000_000}

    def test_hauptzeit_voller_preis(self):
        # Mittwoch, 24.09.2026, 07:30 UTC
        self.assertAlmostEqual(auswertung.deepseek_kosten(PREISE, self.nutzung, utc(2026, 9, 24, 7), HAUPTZEIT, 0.5),
                               0.006 + 0.3 + 1.2)

    def test_nebenzeit_halber_preis(self):
        # Mittwoch 12:30 UTC und Samstag 07:30 UTC
        for t in (utc(2026, 9, 24, 12), utc(2026, 9, 26, 7)):
            self.assertAlmostEqual(auswertung.deepseek_kosten(PREISE, self.nutzung, t, HAUPTZEIT, 0.5), 0.753)

    def test_ohne_cache_angabe_zaehlt_alles_als_neu(self):
        n = {'prompt_tokens': 2_000_000, 'completion_tokens': 0}
        self.assertAlmostEqual(auswertung.deepseek_kosten(PREISE, n, utc(2026, 9, 24, 7), HAUPTZEIT, 0.5), 0.6)


class _Schein(BaseHTTPRequestHandler):
    """Antwortet wie die DeepSeek-Schnittstelle; `ueberlastet` Anfragen lang mit 503."""
    ueberlastet = 0
    anfragen = []

    def log_message(self, *a):
        pass

    def _senden(self, code, daten):
        roh = json.dumps(daten).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        if self.path == '/user/balance':
            self._senden(200, {'is_available': True, 'balance_infos': [{'currency': 'USD', 'total_balance': '19.36'}]})
        else:
            self._senden(200, {'data': [{'id': 'deepseek-flash'}, {'id': 'deepseek-neu'}]})

    def do_POST(self):
        _Schein.anfragen.append((self.headers['Authorization'],
                                 json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        if _Schein.ueberlastet > 0:
            _Schein.ueberlastet -= 1
            return self._senden(503, {'error': {'message': 'Server overloaded'}})
        self._senden(200, {'model': 'deepseek-flash',
                           'choices': [{'message': {'content': 'Fassung', 'reasoning_content': 'Gedanken'},
                                        'finish_reason': 'stop'}],
                           'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150,
                                     'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}})


class _Lauf:
    def __init__(self):
        self.meldungen = []

    def http(self, oeffnen):
        with oeffnen() as r:
            return json.load(r)

    def melden(self, text):
        self.meldungen.append(text)

    def warten(self, sekunden):
        pass


class Anbieter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), _Schein)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.schluessel = os.path.join(cls.tmp.name, '.credentials.yaml')
        with open(cls.schluessel, 'w', encoding='utf-8') as f:
            f.write('version: 1\nrecords: {}\nrefs:\n  DEEPSEEK_API_KEY: "sk-test123"\n  ANDERER_KEY: x\n')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def setUp(self):
        _Schein.anfragen = []
        _Schein.ueberlastet = 0
        self.cfg = {'deepseek': {
            'url': f'http://127.0.0.1:{self.server.server_address[1]}', 'schluessel_datei': self.schluessel,
            'schluessel_name': 'DEEPSEEK_API_KEY', 'hauptzeit_utc': HAUPTZEIT, 'nebenzeit_faktor': 0.5,
            'modelle': {'deepseek-flash': {'name': 'Flash', 'kontext': 1000000, 'preise': PREISE}}}}
        self.patch = mock.patch.object(auswertung, '_NETZ', auswertung._OHNE_PROXY)
        self.patch.start()
        self.ds = auswertung.DeepSeek(self.cfg)

    def tearDown(self):
        self.patch.stop()

    def test_schluessel_aus_dsh_datei(self):
        self.assertEqual(self.ds._schluessel(), 'sk-test123')
        self.assertEqual(self.ds.verfuegbar({'modell': 'deepseek-flash'}), (True, ''))

    def test_ohne_schluessel_nicht_nutzbar(self):
        self.cfg['deepseek']['schluessel_datei'] = os.path.join(self.tmp.name, 'fehlt.yaml')
        ok, grund = auswertung.DeepSeek(self.cfg).verfuegbar({'modell': 'deepseek-flash'})
        self.assertFalse(ok)
        self.assertIn('Kein DeepSeek-Schlüssel', grund)

    def test_katalog_bekannte_zuerst_und_neue_ohne_preis(self):
        k = self.ds.katalog()
        self.assertEqual([m['modell'] for m in k], ['deepseek-flash', 'deepseek-neu'])
        self.assertEqual(k[0]['kontext'], 1000000)
        self.assertEqual(k[1]['beschreibung'], 'Preis unbekannt')

    def test_denkstufen_werden_uebersetzt(self):
        for stufe, erwartet in ((None, {}), ('none', {'thinking': {'type': 'disabled'}}),
                                ('low', {'reasoning_effort': 'low'}), ('max', {'reasoning_effort': 'max'})):
            _Schein.anfragen = []
            a = self.ds.ausfuehren({'modell': 'deepseek-flash', 'stufe': stufe}, 'Text', _Lauf())
            schluessel, daten = _Schein.anfragen[0]
            self.assertEqual(schluessel, 'Bearer sk-test123')
            self.assertEqual({k: daten[k] for k in ('thinking', 'reasoning_effort') if k in daten}, erwartet)
            self.assertEqual(a['text'], 'Fassung')  # ohne Gedankengang
            self.assertEqual(a['tokens'], 150)
            self.assertIsNotNone(a['kosten_usd'])

    def test_ueberlastung_wird_wiederholt(self):
        _Schein.ueberlastet = 2
        lauf = _Lauf()
        a = self.ds.ausfuehren({'modell': 'deepseek-flash', 'stufe': None}, 'Text', lauf)
        self.assertEqual(a['text'], 'Fassung')
        self.assertEqual(len(_Schein.anfragen), 3)
        self.assertIn('DeepSeek ist gerade ausgelastet; neuer Versuch in 20 s.', lauf.meldungen)


if __name__ == '__main__':
    unittest.main()
