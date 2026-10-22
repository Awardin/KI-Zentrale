"""Tests für den Fibo-Dienst: Größen, Warteschlange, Abbruch, Ablage, HTTP und DeepSeek.

Die Tests laufen mit der normalen Python ohne GPU, ohne torch, diffusers und Pillow:
Pipeline, Bildleser, Generator und Beschreiber sind austauschbar. Die Fibo-Umgebung
führt dieselben Tests aus.
"""
import base64
import copy
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fibo import dienst as fd  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)


class FakeBild:
    """Steht für ein PIL-Bild, ohne Pillow zu laden."""

    def __init__(self, groesse=(64, 48), inhalt=b'fake-png'):
        self.size = tuple(groesse)
        self.inhalt = inhalt
        self.resize_auf = None
        self.modus = None
        self.punkt = None

    def convert(self, modus):
        neu = copy.copy(self)
        neu.modus = modus
        return neu

    def resize(self, groesse, verfahren=None):
        neu = copy.copy(self)
        neu.size = tuple(groesse)
        neu.resize_auf = (tuple(groesse), verfahren)
        return neu

    def point(self, funktion):
        neu = copy.copy(self)
        neu.punkt = funktion
        return neu

    def save(self, pfad):
        with open(pfad, 'wb') as f:
            f.write(self.inhalt)


class FakePipe:
    """Fake-Pipeline: zeichnet Aufrufe auf und kann auf Wunsch warten."""

    def __init__(self):
        self.transformer = 'dev-transformer'
        self.remove_all_hooks = Mock()
        self.enable_model_cpu_offload = Mock()
        self.aufrufe = []
        self._interrupt = False
        self.takt = 0.0
        self.gestartet = threading.Event()
        self.weiter = threading.Event()
        self.weiter.set()

    def __call__(self, **kwargs):
        self.aufrufe.append(kwargs)
        self._interrupt = False
        self.gestartet.set()
        self.weiter.wait(5)
        schritte = int(kwargs.get('num_inference_steps', 1))
        for i in range(schritte):
            if self.takt:
                time.sleep(self.takt)
            callback = kwargs.get('callback_on_step_end')
            if callback is not None:
                callback(self, i, 0, {})
            if self._interrupt:
                break
        if 'image' in kwargs:
            bild = kwargs['image']
            groesse = bild[0].size if isinstance(bild, list) else bild.size
        else:
            groesse = (kwargs.get('width'), kwargs.get('height'))
        return SimpleNamespace(images=[FakeBild(groesse)])


def b64(wert=b'bild'):
    return base64.b64encode(wert).decode('ascii')


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = copy.deepcopy(KONFIG)
        self.cfg['ablage'] = os.path.join(self.tmp.name, 'ablage')
        self.schluessel_datei = os.path.join(self.tmp.name, 'credentials.yaml')
        with open(self.schluessel_datei, 'w', encoding='utf-8') as f:
            f.write('DEEPSEEK_API_KEY: test-geheim-123\n')
        self.cfg['deepseek']['schluessel_datei'] = self.schluessel_datei
        self.pipe = FakePipe()
        self.transformer = []
        self.d = fd.Dienst(
            self.cfg,
            pipeline_fabrik=lambda cfg: self.pipe,
            transformer_fabrik=lambda cfg, pfad: self.transformer.append(pfad) or ('transformer:' + pfad),
            generator_fabrik=lambda seed: ('generator', seed),
            bild_lesen_funktion=lambda roh: FakeBild((3000, 2000)),
            maske_lesen_funktion=lambda roh: FakeBild((100, 100)),
            bild_speichern_funktion=lambda bild, pfad: bild.save(pfad),
            beschreiber=lambda prompt: {'short_description': prompt},
        )
        self.d.laden()
        self.d.starten()
        self.server = None

    def tearDown(self):
        self.pipe.weiter.set()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.d.beenden()
        if self.d._arbeiter is not None:
            self.d._arbeiter.join(3)

    def warten(self, bedingung, sekunden=3.0):
        frist = time.time() + sekunden
        while time.time() < frist:
            if bedingung():
                return True
            time.sleep(0.01)
        return bedingung()

    def zustand(self, auftrag_id):
        return self.d.auftrag_info(auftrag_id)['zustand']

    def warte_auf(self, auftrag_id, zustand, sekunden=3.0):
        self.assertTrue(self.warten(lambda: self.zustand(auftrag_id) == zustand, sekunden),
                        f'{auftrag_id} ist {self.zustand(auftrag_id)}, nicht {zustand}')

    def bild_auftrag(self, prompt='Hund', **extra):
        daten = {'art': 'bild', 'prompt': prompt, 'schritte': 1, 'seed': 7}
        daten.update(extra)
        return self.d.auftrag_annehmen(daten)


class Groessen(unittest.TestCase):
    def test_vielfaches_und_flaeche(self):
        self.assertEqual(fd.vielfaches(1), 16)
        self.assertEqual(fd.vielfaches(1248), 1248)
        self.assertEqual(fd.vielfaches(1249), 1248)
        self.assertEqual(fd.flaeche_begrenzen(1248, 832), (1248, 832))
        self.assertEqual(fd.flaeche_begrenzen(1, 1), (16, 16))
        for breite, hoehe in ((2000, 1000), (1920, 1080), (4000, 4000), (3000, 100)):
            with self.subTest(breite=breite, hoehe=hoehe):
                b, h = fd.flaeche_begrenzen(breite, hoehe)
                self.assertEqual((b % 16, h % 16), (0, 0))
                self.assertLessEqual(b * h, fd.MAX_FLAECHE)
                if breite * hoehe > fd.MAX_FLAECHE:
                    self.assertGreaterEqual(b * h, fd.MAX_FLAECHE * 0.9)

    def test_bild_verkleinern_und_maske(self):
        bild = FakeBild((3000, 2000))
        ziel = fd.flaeche_begrenzen(3000, 2000)
        klein = fd.bild_verkleinern(bild)
        self.assertEqual(klein.size, ziel)
        self.assertEqual(klein.resize_auf, (ziel, 1))
        gleich = FakeBild((1248, 832))
        self.assertIs(fd.bild_verkleinern(gleich), gleich)
        maske = fd.maske_anpassen(FakeBild((100, 100)), (64, 48))
        self.assertEqual(maske.size, (64, 48))
        self.assertEqual(maske.resize_auf, ((64, 48), 0))
        self.assertEqual(maske.punkt(0), 0)
        self.assertEqual(maske.punkt(127), 0)
        self.assertEqual(maske.punkt(128), 255)
        self.assertEqual(maske.punkt(255), 255)


class DeepSeek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = copy.deepcopy(KONFIG)
        self.datei = os.path.join(self.tmp.name, 'credentials.yaml')
        with open(self.datei, 'w', encoding='utf-8') as f:
            f.write('DEEPSEEK_API_KEY: test-geheim-123\n')
        self.cfg['deepseek']['schluessel_datei'] = self.datei

    def test_aufruf_gemockt_und_schluessel_nie_ausgegeben(self):
        gesehen = {}

        def aufruf(prompt, modell):
            gesehen['prompt'] = prompt
            gesehen['modell'] = modell
            gesehen['schluessel'] = os.environ.get('DEEPSEEK_API_KEY')
            return {'short_description': prompt, 'modell': modell}

        caption = fd.deepseek_beschreiben(self.cfg, 'Ein Hund', aufruf=aufruf)
        self.assertEqual(caption, {'short_description': 'Ein Hund', 'modell': 'deepseek/deepseek-flash'})
        self.assertEqual(gesehen, {'prompt': 'Ein Hund', 'modell': 'deepseek/deepseek-flash',
                                   'schluessel': 'test-geheim-123'})
        self.assertEqual(os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP'), 'True')
        self.assertNotIn('test-geheim-123', json.dumps(caption))

    def test_schluessel_wird_auch_aus_fehlern_entfernt(self):
        def aufruf(prompt, modell):
            return {'fehler': 'Schlüssel test-geheim-123 ist ungültig'}

        caption = fd.deepseek_beschreiben(self.cfg, 'Ein Hund', aufruf=aufruf)
        self.assertNotIn('test-geheim-123', json.dumps(caption))
        self.assertIn('***', caption['fehler'])

    def test_zeitlimit(self):
        with self.assertRaisesRegex(RuntimeError, 'antwortet nach 0,05 s nicht'):
            fd.deepseek_beschreiben(self.cfg, 'Ein Hund', timeout=0.05,
                                    aufruf=lambda p, m: time.sleep(0.2) or {'ok': True})

    def test_fehlender_schluessel(self):
        self.cfg['deepseek']['schluessel_datei'] = os.path.join(self.tmp.name, 'gibtsnicht.yaml')
        with self.assertRaisesRegex(RuntimeError, 'nicht lesbar'):
            fd.deepseek_beschreiben(self.cfg, 'Ein Hund', aufruf=lambda p, m: {'ok': True})


class DienstTests(Basis):
    def test_health_zustaende(self):
        self.assertEqual(self.d.health()['status'], 'ok')
        self.assertEqual(self.d.health()['modell'], 'fibo-2.0')
        self.assertEqual(self.d.health()['aktiv'], 'dev')
        self.assertEqual(self.d.health()['warteschlange'], 0)
        self.assertIsNone(self.d.health()['laufend'])
        self.d.zustand = 'loading'
        self.assertEqual(self.d.health(), {'status': 'loading'})
        self.d.zustand = 'error'
        self.d.fehler = 'Shader fehlt'
        self.assertEqual(self.d.health(), {'status': 'error', 'fehler': 'Shader fehlt'})
        self.d.zustand = 'ok'
        self.d.fehler = None
        self.d._laufend = 'abc'
        self.assertEqual(self.d.health()['laufend'], 'abc')

    def test_ladefehler(self):
        def kaputt(cfg):
            raise RuntimeError('CUDA nicht verfügbar')
        d = fd.Dienst(self.cfg, pipeline_fabrik=kaputt)
        with self.assertRaisesRegex(RuntimeError, 'CUDA'):
            d.laden()
        self.assertEqual(d.zustand, 'error')
        self.assertEqual(d.health(), {'status': 'error', 'fehler': 'CUDA nicht verfügbar'})

    def test_annahme_pruefungen(self):
        faelle = [
            ({}, 'Art muss'),
            ({'art': 'bild'}, 'Prompt fehlt'),
            ({'art': 'bild', 'prompt': '  '}, 'Prompt fehlt'),
            ({'art': 'bild', 'prompt': 'x', 'modell': 'turbo'}, 'Turbo kann nur bearbeiten'),
            ({'art': 'bild', 'prompt': 'x', 'modell': 'gross'}, 'Modell muss'),
            ({'art': 'bearbeiten', 'prompt': 'x'}, '1 bis 4 Bilder'),
            ({'art': 'bearbeiten', 'prompt': 'x', 'bilder': [b64()] * 5}, '1 bis 4 Bilder'),
            ({'art': 'bearbeiten', 'prompt': 'x', 'bilder': [b64(), b64()], 'maske': b64()},
             'genau einem Bild'),
            ({'art': 'bild', 'prompt': 'x', 'bilder': [b64()]}, 'nur beim Bearbeiten'),
            ({'art': 'bild', 'prompt': 'x', 'maske': b64()}, 'nur beim Bearbeiten'),
            ({'art': 'bild', 'prompt': 'x', 'seed': 'viel'}, 'Seed'),
            ({'art': 'bild', 'prompt': 'x', 'schritte': 0}, 'Schritte'),
            ({'art': 'bild', 'prompt': 'x', 'guidance': -1}, 'Guidance'),
            ({'art': 'bild', 'prompt': 'x', 'breite': 0}, 'größer als 0'),
            ({'art': 'bearbeiten', 'prompt': 'x', 'bilder': ['@@@']}, 'Base64'),
        ]
        for daten, text in faelle:
            with self.subTest(daten=daten):
                with self.assertRaises(fd.AnfrageFehler) as ex:
                    self.d.auftrag_annehmen(daten)
                self.assertIn(text, ex.exception.text)
                self.assertEqual(ex.exception.code, 400)

    def test_warteschlange_in_reihenfolge(self):
        ids = [self.bild_auftrag(p) for p in ('eins', 'zwei', 'drei')]
        for auftrag_id in ids:
            self.warte_auf(auftrag_id, 'fertig')
        self.assertEqual([a['prompt'] for a in self.pipe.aufrufe], ['eins', 'zwei', 'drei'])

    def test_abbruch_wartend(self):
        self.pipe.weiter.clear()
        erster = self.bild_auftrag('eins')
        self.assertTrue(self.pipe.gestartet.wait(2))
        zweiter = self.bild_auftrag('zwei')
        self.assertTrue(self.warten(lambda: self.d.auftrag_info(zweiter)['platz'] == 1))
        code, antwort = self.d.abbrechen(zweiter)
        self.assertEqual((code, antwort['zustand']), (200, 'abgebrochen'))
        self.assertEqual(self.d.auftrag_info(zweiter)['zustand'], 'abgebrochen')
        self.assertEqual(self.d.health()['warteschlange'], 0)
        self.pipe.weiter.set()
        self.warte_auf(erster, 'fertig')
        self.assertEqual(self.d.auftrag_info(zweiter)['zustand'], 'abgebrochen')
        self.assertEqual([a['prompt'] for a in self.pipe.aufrufe], ['eins'])
        self.assertFalse(os.path.exists(os.path.join(self.cfg['ablage'],
                                                     time.strftime('%Y-%m-%d'), zweiter + '.png')))

    def test_abbruch_rechnend_und_kein_bild(self):
        self.pipe.takt = 0.02
        auftrag_id = self.bild_auftrag('lang', schritte=100)
        self.assertTrue(self.warten(lambda: self.zustand(auftrag_id) == 'rechnet', 2))
        code, antwort = self.d.abbrechen(auftrag_id)
        self.assertEqual(code, 200)
        self.warte_auf(auftrag_id, 'abgebrochen')
        self.assertTrue(self.pipe._interrupt)
        self.assertIsNone(self.d.datei_pfad(auftrag_id + '.png'))
        self.assertIsNone(self.d.datei_pfad(auftrag_id + '.json'))
        self.assertEqual(self.d.abbrechen(auftrag_id)[0], 409)
        self.assertEqual(self.d.abbrechen('gibtsnicht')[0], 404)

    def test_bild_fertig_ablage_und_begleitjson(self):
        auftrag_id = self.bild_auftrag('Ein Hund', breite=2000, hoehe=1000, schritte=2, seed=42)
        self.warte_auf(auftrag_id, 'fertig')
        info = self.d.auftrag_info(auftrag_id)
        ergebnis = info['ergebnis']
        ziel = fd.flaeche_begrenzen(2000, 1000)
        self.assertEqual((ergebnis['breite'], ergebnis['hoehe']), ziel)
        self.assertEqual(ergebnis['bild'], f'/api/datei/{auftrag_id}.png')
        self.assertEqual((ergebnis['seed'], ergebnis['modell']), (42, 'dev'))
        png = self.d.datei_pfad(auftrag_id + '.png')
        json_pfad = self.d.datei_pfad(auftrag_id + '.json')
        self.assertTrue(png.endswith(os.path.join(time.strftime('%Y-%m-%d'), auftrag_id + '.png')))
        self.assertTrue(os.path.isfile(json_pfad))
        with open(json_pfad, encoding='utf-8') as f:
            daten = json.load(f)
        self.assertEqual(daten['id'], auftrag_id)
        self.assertEqual(daten['lizenz'], 'Fibo 2.0 – CC BY-NC 4.0, nur nicht-kommerziell')
        self.assertEqual((daten['seed'], daten['modell']), (42, 'dev'))
        self.assertIn('einstellungen', daten)
        self.assertEqual(daten['einstellungen']['breite'], ziel[0])
        self.assertEqual(daten['prompt'], 'Ein Hund')
        self.assertEqual(self.pipe.aufrufe[0]['negative_prompt'], fd.NEGATIVE_T2I)
        self.assertEqual(self.pipe.aufrufe[0]['generator'], ('generator', 42))

    def test_bearbeiten_maske_turbo_und_wechsel(self):
        auftrag_id = self.d.auftrag_annehmen({
            'art': 'bearbeiten', 'prompt': 'Mach den Himmel blau', 'bilder': [b64()], 'maske': b64(),
            'schritte': 1, 'seed': 3})
        self.warte_auf(auftrag_id, 'fertig')
        aufruf = self.pipe.aufrufe[0]
        ziel = fd.flaeche_begrenzen(3000, 2000)
        self.assertEqual(aufruf['image'].size, ziel)
        self.assertEqual(aufruf['mask'].size, ziel)
        self.assertEqual(aufruf['mask'].resize_auf, (ziel, 0))
        self.assertNotIn('negative_prompt', aufruf)
        self.assertEqual(self.d.aktiv, 'turbo')
        self.assertIsNone(self.d.transformer_dev)
        self.assertEqual(self.pipe.transformer, 'transformer:' + self.cfg['turbo_transformer'])
        with open(self.d.datei_pfad(auftrag_id + '.json'), encoding='utf-8') as f:
            daten = json.load(f)
        self.assertEqual(daten['modell'], 'turbo')
        self.assertGreaterEqual(daten['wechsel_s'], 0.0)

    def test_turbo_wechsel_gibt_nicht_aktiven_transformer_frei(self):
        self.d._modell_wechseln('turbo')
        self.assertEqual(self.d.aktiv, 'turbo')
        self.assertEqual(self.pipe.transformer, 'transformer:' + self.cfg['turbo_transformer'])
        self.assertIsNone(self.d.transformer_dev)
        self.assertTrue(self.pipe.remove_all_hooks.called)
        self.d._modell_wechseln('dev')
        self.assertEqual(self.d.aktiv, 'dev')
        self.assertEqual(self.pipe.transformer, 'transformer:' + os.path.join(self.cfg['modell'], 'transformer'))
        self.assertIsNone(self.d.transformer_turbo)
        self.assertEqual(self.transformer, [self.cfg['turbo_transformer'],
                                            os.path.join(self.cfg['modell'], 'transformer')])

    def test_turbo_im_speicher_behaelt_beide(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['turbo_im_speicher'] = True
        d = fd.Dienst(cfg, pipeline_fabrik=lambda c: FakePipe(),
                      transformer_fabrik=lambda c, p: 'transformer:' + p,
                      generator_fabrik=lambda s: ('generator', s))
        d.laden()
        dev = d.transformer_dev
        d._modell_wechseln('turbo')
        self.assertIs(d.transformer_dev, dev)
        self.assertIsNotNone(d.transformer_turbo)
        d._modell_wechseln('dev')
        self.assertIsNotNone(d.transformer_turbo)

    def test_deepseek_beschreiber_im_auftrag(self):
        auftrag_id = self.bild_auftrag('Ein roter Ball', beschreiber='deepseek')
        self.warte_auf(auftrag_id, 'fertig')
        aufruf = self.pipe.aufrufe[0]
        self.assertEqual(json.loads(aufruf['prompt']), {'short_description': 'Ein roter Ball'})
        self.assertEqual(self.d.auftrag_info(auftrag_id)['ergebnis']['caption'],
                         {'short_description': 'Ein roter Ball'})

    def test_dateischutz(self):
        ordner = os.path.join(self.cfg['ablage'], '2026-10-22')
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, 'abc.png'), 'wb') as f:
            f.write(b'png')
        with open(os.path.join(ordner, 'abc.json'), 'w', encoding='utf-8') as f:
            f.write('{}')
        self.assertTrue(self.d.datei_pfad('abc.png').endswith('abc.png'))
        self.assertTrue(self.d.datei_pfad('abc.json').endswith('abc.json'))
        for name in ('../abc.png', '..\\abc.png', '2026-10-22/abc.png', '2026-10-22\\abc.png',
                     'abc.exe', '', '.', '..', 'C:\\abc.png'):
            with self.subTest(name=name):
                self.assertIsNone(self.d.datei_pfad(name))


class HttpTests(Basis):
    def setUp(self):
        super().setUp()
        self.http = fd.Server(('127.0.0.1', 0), fd.Anfrage)
        fd.Anfrage.dienst = self.d
        self.port = self.http.server_address[1]
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.server = self.http

    def tearDown(self):
        fd.Anfrage.dienst = None
        super().tearDown()

    def anfrage(self, methode, pfad, daten=None, kopf=True):
        verbindung = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        kopfzeilen = {'Content-Type': 'application/json'}
        if kopf:
            kopfzeilen['X-Atelier'] = '1'
        inhalt = json.dumps(daten).encode('utf-8') if daten is not None else None
        verbindung.request(methode, pfad, body=inhalt, headers=kopfzeilen)
        antwort = verbindung.getresponse()
        roh = antwort.read()
        verbindung.close()
        return antwort.status, roh, antwort.getheader('Content-Type')

    def test_health_und_post_kopfzeile(self):
        code, roh, _ = self.anfrage('GET', '/health')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(roh)['status'], 'ok')
        code, roh, _ = self.anfrage('POST', '/api/auftrag', {'art': 'bild', 'prompt': 'x'}, kopf=False)
        self.assertEqual(code, 403)
        code, roh, _ = self.anfrage('POST', '/api/auftrag', {'art': 'bild', 'prompt': 'x'})
        self.assertEqual(code, 200)
        auftrag_id = json.loads(roh)['id']
        self.assertTrue(self.warten(lambda: self.anfrage('GET', '/api/auftrag/' + auftrag_id)[0] == 200))
        self.warte_auf(auftrag_id, 'fertig')
        code, roh, typ = self.anfrage('GET', f'/api/datei/{auftrag_id}.png')
        self.assertEqual((code, typ), (200, 'image/png'))
        code, roh, typ = self.anfrage('GET', f'/api/datei/{auftrag_id}.json')
        self.assertEqual((code, typ), (200, 'application/json; charset=utf-8'))
        self.assertEqual(json.loads(roh)['id'], auftrag_id)

    def test_413_bei_zu_grosser_anfrage(self):
        verbindung = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        verbindung.putrequest('POST', '/api/auftrag')
        verbindung.putheader('Host', f'127.0.0.1:{self.port}')
        verbindung.putheader('X-Atelier', '1')
        verbindung.putheader('Content-Type', 'application/json')
        verbindung.putheader('Content-Length', str(fd.MAX_ANFRAGE + 1))
        verbindung.endheaders()
        antwort = verbindung.getresponse()
        roh = antwort.read()
        verbindung.close()
        self.assertEqual(antwort.status, 413)
        self.assertIn('64 MB', json.loads(roh)['fehler'])

    def test_beschreiben_und_schluessel_nicht_in_antwort(self):
        code, roh, _ = self.anfrage('POST', '/api/beschreiben', {'prompt': 'Ein Hund'})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(roh)['caption'], {'short_description': 'Ein Hund'})
        self.d.beschreiber = lambda prompt: (_ for _ in ()).throw(
            RuntimeError('Schlüssel test-geheim-123 ungültig'))
        code, roh, _ = self.anfrage('POST', '/api/beschreiben', {'prompt': 'Ein Hund'})
        self.assertEqual(code, 502)
        self.assertNotIn(b'test-geheim-123', roh)
        code, roh, _ = self.anfrage('POST', '/api/beschreiben', {'prompt': ''})
        self.assertEqual(code, 400)
        code, roh, _ = self.anfrage('POST', '/api/beschreiben', {'prompt': 'x'}, kopf=False)
        self.assertEqual(code, 403)

    def test_dateipfad_schutz_ueber_http(self):
        ordner = os.path.join(self.cfg['ablage'], '2026-10-22')
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, 'abc.png'), 'wb') as f:
            f.write(b'png')
        self.assertEqual(self.anfrage('GET', '/api/datei/abc.png')[0], 200)
        for pfad in ('/api/datei/%2e%2e%2fabc.png', '/api/datei/2026-10-22%2fabc.png',
                     '/api/datei/abc.exe', '/api/datei/gibtsnicht.png'):
            with self.subTest(pfad=pfad):
                self.assertEqual(self.anfrage('GET', pfad)[0], 404)
        code, roh, _ = self.anfrage('POST', '/api/auftrag/gibtsnicht/abbrechen', {})
        self.assertEqual((code, json.loads(roh)['fehler']), (404, 'Diesen Auftrag gibt es nicht.'))


if __name__ == '__main__':
    unittest.main()
