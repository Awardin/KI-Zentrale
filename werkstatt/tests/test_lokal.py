"""Lokale Auswerter: Antwortgrenze, Denkteil, Kontextreserve sowie Strata und PolyStrata."""
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung, messungen, watch_lauf  # noqa: E402
from werkstatt import server as wserver  # noqa: E402

NINFER = {'id': 'ninfer', 'art': 'ninfer', 'name': 'Qwen3.8 27B · NInfer', 'port': 8080,
          'modell_id': 'qwen3.8-27b-ninfer-groupwise', 'untertitel': '128K Kontext · eine RTX 3090'}
OLLAMA = {'id': 'ornith', 'art': 'ollama', 'name': 'Ornith 1.5 · Q5', 'tag': 'ornith-q5-128k:latest',
          'untertitel': '128K Kontext · Ollama verteilt auf die Karten', 'ollama_optionen': {'num_batch': 256}}
STRATA = {'id': 'flash-next-strata', 'art': 'strata', 'name': 'Qwen3.8 Flash-Next · Strata',
          'untertitel': '125B · IQ3_XXS (128K mit Bildern oder 256K) oder Q4 (genauer, mit Bildern) · beide Karten',
          'wofuer': 'Großes Modell für Projekte, Coding und lange Dokumente.', 'port': 8095,
          'varianten': [
              {'id': '128k', 'name': '128K Kontext · mit Bildern', 'standard': True, 'kontext': 131072,
               'modell': 'qwen3.8-flash-next-iq3_xxs'},
              {'id': '256k', 'name': '256K Kontext · ohne Bilder', 'kontext': 262144,
               'modell': 'qwen3.8-flash-next-iq3_xxs'},
              {'id': 'q4', 'name': 'Q4 · genauer, etwas langsamer · 128K · mit Bildern', 'kontext': 131072,
               'modell': 'qwen3.8-flash-next-unsloth-ud-iq4_xs'}]}
POLY = {'id': 'ornith-polystrata', 'art': 'polystrata', 'name': 'Ornith 1.5 · PolyStrata',
        'untertitel': 'Q4 (Ollama-Datei) · 128K · mit Bildern · eine RTX 3090',
        'wofuer': 'Schnellster Ornith-Weg auf einer Karte.', 'port': 8097,
        'modell': 'ornith-1.5-35b-a3b-q4_k_m-ollama'}
Q4 = 'qwen3.8-flash-next-unsloth-ud-iq4_xs'
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


class ModellWelt:
    """Antwortet wie die lokalen Ports; Ports sind offen, /v1/models liefert die eingetragenen Kennungen."""

    def __init__(self):
        self.modelle = {}
        self.antworten = {}
        self.anfragen = []
        self.ports = [('127.0.0.1', p, 1) for p in (8080, 8095, 8097, 11434)]

    def oeffnen(self, anfrage, timeout=0):
        ziel = anfrage.full_url if isinstance(anfrage, urllib.request.Request) else str(anfrage)
        self.anfragen.append((ziel, anfrage))
        if ziel.endswith('/api/ps'):
            return Antwort({'models': []})
        port = int(ziel.split(':')[2].split('/')[0])
        if ziel.endswith('/v1/models'):
            return Antwort({'object': 'list', 'data': [{'id': x} for x in self.modelle.get(port, [])]})
        if ziel.endswith('/v1/chat/completions'):
            return Antwort(self.antworten.get(port) or {
                'choices': [{'message': {'content': 'Fassung'}, 'finish_reason': 'stop'}], 'usage': {'total_tokens': 10}})
        raise AssertionError(ziel)


class StrataUndPolyStrata(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        zc = os.path.join(self.tmp.name, 'zentrale.json')
        with open(zc, 'w', encoding='utf-8') as f:
            json.dump({'ollama': {'url': 'http://127.0.0.1:11434'},
                       'eintraege': [NINFER, OLLAMA, STRATA, POLY]}, f)
        self.lokal = auswertung.Lokal({'zentrale_config': zc})
        self.welt = ModellWelt()
        p = mock.patch.object(auswertung._OHNE_PROXY, 'open', side_effect=self.welt.oeffnen)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(auswertung.winapi, 'lauschende_ports', return_value=self.welt.ports)
        p.start()
        self.addCleanup(p.stop)

    def anfrage(self):
        return json.loads([a for ziel, a in self.welt.anfragen if ziel.endswith('/v1/chat/completions')][-1].data)

    def test_strata_mit_geladener_q4_fassung(self):
        self.welt.modelle[8095] = [Q4]
        self.assertEqual(self.lokal.verfuegbar({'modell': 'flash-next-strata'}, frisch=True), (True, ''))
        a = self.lokal.ausfuehren({'modell': 'flash-next-strata'}, 'Prompt', Lauf())
        daten = self.anfrage()
        self.assertEqual((daten['model'], daten['max_tokens']), (Q4, auswertung.LOKAL_MAX_TOKENS))
        self.assertEqual(a['modell_tatsaechlich'], Q4)
        self.assertEqual((a['text'], a['tokens']), ('Fassung', 10))

    def test_strata_ohne_geladene_fassung_ist_nicht_verfuegbar(self):
        self.welt.modelle[8095] = []
        ok, grund = self.lokal.verfuegbar({'modell': 'flash-next-strata'}, frisch=True)
        self.assertFalse(ok)
        self.assertEqual(grund, 'Qwen3.8 Flash-Next · Strata ist nicht geladen. Bitte in der Modellzentrale laden.')

    def test_strata_faellt_zwischen_pruefung_und_anfrage_weg(self):
        self.welt.modelle[8095] = [Q4]
        self.assertEqual(self.lokal.verfuegbar({'modell': 'flash-next-strata'}, frisch=True), (True, ''))
        self.welt.modelle[8095] = []
        with self.assertRaises(RuntimeError) as e:
            self.lokal.ausfuehren({'modell': 'flash-next-strata'}, 'Prompt', Lauf())
        self.assertEqual(str(e.exception),
                         'Qwen3.8 Flash-Next · Strata ist nicht geladen. Bitte in der Modellzentrale laden.')

    def test_polystrata_mit_geladener_fassung(self):
        self.welt.modelle[8097] = [POLY['modell']]
        self.assertEqual(self.lokal.verfuegbar({'modell': 'ornith-polystrata'}, frisch=True), (True, ''))
        a = self.lokal.ausfuehren({'modell': 'ornith-polystrata'}, 'Prompt', Lauf())
        daten = self.anfrage()
        self.assertEqual((daten['model'], daten['max_tokens']), (POLY['modell'], auswertung.LOKAL_MAX_TOKENS))
        self.assertEqual(a['modell_tatsaechlich'], POLY['modell'])
        self.welt.modelle[8097] = []
        ok, grund = self.lokal.verfuegbar({'modell': 'ornith-polystrata'}, frisch=True)
        self.assertFalse(ok)
        self.assertIn('Bitte in der Modellzentrale laden.', grund)

    def test_katalog_kontexte(self):
        self.assertEqual({m['modell']: m['kontext'] for m in self.lokal.katalog()},
                         {'ninfer': 131072, 'ornith': 131072, 'flash-next-strata': 131072,
                          'ornith-polystrata': 131072})

    def test_messlauf_kennt_nur_ollama_und_ninfer(self):
        m = messungen.Messlauf(os.path.join(self.tmp.name, 'messlaeufe.json'), self.lokal, lambda text: None)
        for modell in ('flash-next-strata', 'ornith-polystrata'):
            self.assertEqual(m.starten(modell)[0], 404)

    def test_lokale_modelle_im_server_nur_ollama_und_ninfer(self):
        self.welt.modelle[8080] = [NINFER['modell_id']]
        w = wserver.Werkstatt.__new__(wserver.Werkstatt)
        w._messungen = (time.time(), {'transkription': {}, 'bild_video': {}, 'historisch': None, 'gpu_lab_da': False})
        w.auswertung = mock.Mock()
        w.auswertung.anbieter = {'lokal': self.lokal}
        w.auswertung.liste = []
        w.messlauf = mock.Mock()
        w.messlauf.liste.return_value = []
        w.messlauf.laufend = None
        st = wserver.Werkstatt.messungen(w)
        self.assertEqual([m['id'] for m in st['lokale_modelle']], ['ninfer', 'ornith'])
        self.assertNotIn('flash-next-strata', [m['id'] for m in st['lokale_modelle']])
        self.assertNotIn('ornith-polystrata', [m['id'] for m in st['lokale_modelle']])


if __name__ == '__main__':
    unittest.main()
