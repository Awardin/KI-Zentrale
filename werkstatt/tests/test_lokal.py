"""Lokale Auswerter: Antwortgrenze, Denkteil und Kontextreserve."""
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung, watch_lauf  # noqa: E402

NINFER = {'id': 'ninfer', 'art': 'ninfer', 'name': 'Qwen3.8 27B · NInfer', 'port': 8080,
          'modell_id': 'qwen3.8-27b-ninfer-groupwise', 'untertitel': '128K Kontext · eine RTX 3090'}
OLLAMA = {'id': 'ornith', 'art': 'ollama', 'name': 'Ornith 1.5 · Q5', 'tag': 'ornith-q5-128k:latest',
          'untertitel': '128K Kontext · Ollama verteilt auf die Karten', 'ollama_optionen': {'num_batch': 256}}
ANWEISUNG = 'Kurz [Transkript]'
HINWEIS = '[Hinweis der Werkstatt: Die Antwort wurde an der Längengrenze abgeschnitten.]'
KEINE_ZUSAMMENFASSUNG = ('Das Modell hat die Antwortgrenze schon beim Nachdenken verbraucht; es ist keine '
                         'Zusammenfassung entstanden. Mit „Wiederholen“ neu versuchen.')


class Antwort:
    def __init__(self, daten):
        self.daten = json.dumps(daten).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.daten


class Lauf:
    def __init__(self):
        self.meldungen = []

    def http(self, oeffnen):
        with oeffnen() as r:
            return json.load(r)

    def melden(self, text):
        self.meldungen.append(text)

    def warten(self, sekunden):
        pass


class Antwortgrenze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        zc = os.path.join(self.tmp.name, 'zentrale.json')
        with open(zc, 'w', encoding='utf-8') as f:
            json.dump({'ollama': {'url': 'http://127.0.0.1:11434'}, 'eintraege': [NINFER, OLLAMA]}, f)
        self.lokal = auswertung.Lokal({'zentrale_config': zc})
        self.antworten = {}
        self.anfragen = []
        p = mock.patch.object(auswertung._OHNE_PROXY, 'open', side_effect=self._oeffnen)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(auswertung.winapi, 'lauschende_ports', return_value=[('127.0.0.1', 11434, 1)])
        p.start()
        self.addCleanup(p.stop)

    def _oeffnen(self, anfrage, timeout=0):
        ziel = anfrage.full_url if isinstance(anfrage, urllib.request.Request) else str(anfrage)
        self.anfragen.append((ziel, anfrage))
        if ziel.endswith('/api/ps'):
            return Antwort({'models': []})
        if ziel.endswith('/api/chat'):
            return Antwort(self.antworten['ollama'])
        if ziel.endswith('/v1/chat/completions'):
            return Antwort(self.antworten['openai'])
        raise AssertionError(ziel)

    def openai(self, content, finish_reason='stop'):
        self.antworten['openai'] = {'choices': [{'message': {'content': content}, 'finish_reason': finish_reason}],
                                    'usage': {'total_tokens': 10}}
        return self.lokal.ausfuehren({'modell': 'ninfer'}, 'Prompt', Lauf())

    def ollama(self, content, done_reason='stop'):
        self.antworten['ollama'] = {'message': {'content': content}, 'done_reason': done_reason,
                                    'prompt_eval_count': 3, 'eval_count': 4}
        return self.lokal.ausfuehren({'modell': 'ornith'}, 'Prompt', Lauf())

    def test_anfrage_schickt_die_neue_antwortgrenze(self):
        a = self.openai('Fassung')
        ziel, anfrage = self.anfragen[-1]
        daten = json.loads(anfrage.data)
        self.assertEqual(ziel, 'http://127.0.0.1:8080/v1/chat/completions')
        self.assertEqual((daten['model'], daten['max_tokens']), ('qwen3.8-27b-ninfer-groupwise', 32768))
        self.assertEqual((a['text'], a['tokens']), ('Fassung', 10))

    def test_length_mit_text_haengt_den_hinweis_an(self):
        a = self.openai('Fassung', 'length')
        self.assertEqual(a['text'], 'Fassung\n\n' + HINWEIS)

    def test_ohne_length_bleibt_der_text_unveraendert(self):
        self.assertEqual(self.openai('Fassung')['text'], 'Fassung')

    def test_geschlossener_denkteil_wird_entfernt(self):
        a = self.openai('<think>Gedanken</think>\nFassung')
        self.assertEqual(a['text'], 'Fassung')

    def test_offener_denkteil_und_leerer_text_ergeben_keine_fassung(self):
        for content, finish in (('<think>lange Gedanken', 'length'), ('<think>lange Gedanken', 'stop'), ('', 'length'),
                                ('<think>Gedanken</think>', 'length')):
            with self.subTest(content=content, finish=finish):
                with self.assertRaises(RuntimeError) as e:
                    self.openai(content, finish)
                self.assertEqual(str(e.exception), KEINE_ZUSAMMENFASSUNG)

    def test_ollama_length_mit_text_haengt_den_hinweis_an(self):
        a = self.ollama('Fassung', 'length')
        self.assertEqual(a['text'], 'Fassung\n\n' + HINWEIS)

    def test_ollama_ohne_length_und_offener_denkteil(self):
        self.assertEqual(self.ollama('Fassung')['text'], 'Fassung')
        with self.assertRaises(RuntimeError) as e:
            self.ollama('<think>lange Gedanken')
        self.assertEqual(str(e.exception), KEINE_ZUSAMMENFASSUNG)
        with self.assertRaises(RuntimeError) as e:
            self.ollama('', 'length')
        self.assertEqual(str(e.exception), KEINE_ZUSAMMENFASSUNG)


class Kontextreserve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arbeitsordner = os.path.join(self.tmp.name, 'watch')
        os.makedirs(self.arbeitsordner)
        cfg = {'watch': {'arbeitsordner': self.arbeitsordner},
               'promptsammlung': os.path.join(self.tmp.name, 'prompts.md'),
               'auswerter_vorschlag': [{'id': 'p', 'anbieter': 'lokal', 'modell': 'ninfer', 'stufe': None,
                                        'name': 'Lokal'}],
               'cloud_parallel': 0, 'zentrale_config': os.path.join(self.tmp.name, 'zentrale.json')}
        self.au = auswertung.Auswertungen(cfg, os.path.join(self.tmp.name, 'daten'), lambda text: None)
        self.au.sammlung.lesen = lambda: {'rahmen': None, 'anweisungen': [
            {'name': 'Kurz', 'text': ANWEISUNG, 'stand': 'x', 'frage': False}]}
        self.kontext = 131072
        self.au.profil_info = lambda p: dict(p, kontext=self.kontext, cloud=None, verfuegbar=True, grund='')

    def video(self, geschaetzt):
        ordner = tempfile.mkdtemp(dir=self.arbeitsordner)
        lauf = os.path.join(ordner, 'lauf')
        os.makedirs(lauf)
        with open(os.path.join(lauf, 'run.json'), 'w', encoding='utf-8') as f:
            json.dump({'status': 'complete', 'chunks': [],
                       'signature': {'start': 0, 'end': 600, 'language': 'de', 'model': 'x'}}, f)
        laenge = max(0, int(geschaetzt * 3) - len(ANWEISUNG) - 600)
        for n in watch_lauf.TRANSKRIPT_DATEIEN:
            with open(os.path.join(lauf, n), 'w', encoding='utf-8') as f:
                f.write('x' * laenge if n == 'transcript-timestamps.txt' else '')
        return ordner

    def anlegen(self, ordner):
        return self.au.anlegen({'ordner': ordner, 'anweisungen': ['Kurz'], 'auswerter': ['p']})

    def test_128k_transkript_mit_32k_reserve_wird_abgelehnt(self):
        # 105.000 Token gingen vorher knapp durch (Grenze 111.411), mit 32.768 Reserve nicht mehr.
        code, r = self.anlegen(self.video(105000))
        self.assertEqual((code, r['neu'], r['abgelehnt']),
                         (200, 0, ['Lokal: Das Transkript ist zu lang für 131.072 Token Kontext.']))

    def test_128k_transkript_mit_reserve_passt_weiterhin(self):
        code, r = self.anlegen(self.video(90000))
        self.assertEqual((code, r['neu'], r['abgelehnt']), (200, 1, []))

    def test_32k_kontext_behaelt_8192_token_reserve(self):
        # 26.000 Token gingen vorher durch (Grenze 27.852), mit 8.192 Reserve nicht mehr.
        self.kontext = 32768
        code, r = self.anlegen(self.video(26000))
        self.assertEqual((code, r['neu'], r['abgelehnt']),
                         (200, 0, ['Lokal: Das Transkript ist zu lang für 32.768 Token Kontext.']))
        code, r = self.anlegen(self.video(24000))
        self.assertEqual((code, r['neu'], r['abgelehnt']), (200, 1, []))


if __name__ == '__main__':
    unittest.main()
