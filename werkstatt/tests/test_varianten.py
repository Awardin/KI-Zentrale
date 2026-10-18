"""Kontextwahl der Zentrale (14.10.2026): Die Werkstatt fragt Ollama mit dem Kontext an, mit dem das Modell geladen ist."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung  # noqa: E402

Q4 = {'id': 'ornith-q4', 'art': 'ollama', 'name': 'Ornith 1.5 · Q4', 'tag': 'ornith-1.5:35b',
      'untertitel': '256K oder 32K Kontext · verteilt auf die Karten', 'ollama_optionen': {'num_batch': 256},
      'varianten': [{'id': '256k', 'name': '256K Kontext', 'standard': True,
                     'ollama_optionen': {'num_batch': 256, 'num_ctx': 262144}},
                    {'id': '32k', 'name': '32K Kontext', 'ollama_optionen': {'num_batch': 256, 'num_ctx': 32768}}]}
Q5 = {'id': 'ornith-q5', 'art': 'ollama', 'name': 'Ornith 1.5 · Q5', 'tag': 'ornith-q5-128k:latest',
      'untertitel': '128K Kontext · verteilt auf die Karten', 'ollama_optionen': {'num_batch': 256}}


class Antwort:
    def __init__(self, daten):
        self.daten = json.dumps(daten).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.daten


class KontextDerWerkstatt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        zc = os.path.join(self.tmp.name, 'zentrale.json')
        with open(zc, 'w', encoding='utf-8') as f:
            json.dump({'ollama': {'url': 'http://127.0.0.1:11434'}, 'eintraege': [Q4, Q5]}, f)
        self.lokal = auswertung.Lokal({'zentrale_config': zc})
        self.ps = {'models': []}
        p = mock.patch.object(auswertung._OHNE_PROXY, 'open', side_effect=lambda *a, **k: Antwort(self.ps))
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(auswertung.winapi, 'lauschende_ports', return_value=[('127.0.0.1', 11434, 1)])
        self.ports = p.start()
        self.addCleanup(p.stop)

    def test_anfrage_schickt_den_geladenen_kontext(self):
        self.ps = {'models': [{'name': 'ornith-1.5:35b', 'context_length': 32768}]}
        self.assertEqual(self.lokal.ollama_optionen(Q4, {}), {'num_batch': 256, 'num_ctx': 32768})
        self.ps = {'models': [{'name': 'ornith-1.5:35b', 'context_length': 262144},
                              {'name': 'ornith-q5-128k:latest', 'context_length': 131072}]}
        self.assertEqual(self.lokal.ollama_optionen(Q4, {})['num_ctx'], 262144)
        self.assertEqual(self.lokal.ollama_optionen(Q5, {}), {'num_batch': 256, 'num_ctx': 131072})
        self.assertEqual(Q4['ollama_optionen'], {'num_batch': 256})  # der Eintrag selbst bleibt unverändert

    def test_nicht_geladen_oder_ollama_aus_ohne_kontext(self):
        self.assertEqual(self.lokal.ollama_optionen(Q4, {}), {'num_batch': 256})
        self.ports.return_value = []
        self.ps = {'models': [{'name': 'ornith-1.5:35b', 'context_length': 32768}]}
        self.assertEqual(self.lokal.ollama_optionen(Q4, {}), {'num_batch': 256})

    def test_katalog_kontext_geladen_sonst_standardvariante(self):
        kontext = lambda: {m['modell']: m['kontext'] for m in self.lokal.katalog()}  # noqa: E731
        self.assertEqual(kontext(), {'ornith-q4': 262144, 'ornith-q5': 131072})
        self.lokal._cache.clear()
        self.ps = {'models': [{'name': 'ornith-1.5:35b', 'context_length': 32768}]}
        self.assertEqual(kontext()['ornith-q4'], 32768)  # zu lange Transkripte werden danach abgelehnt


if __name__ == '__main__':
    unittest.main()
