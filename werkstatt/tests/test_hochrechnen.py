"""Regenerate ohne Modelle, GPU oder laufendes ComfyUI prüfen."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

import test_studio as basis
import test_parallel as parallel
from werkstatt import studio, regenerate_lora


CFG = json.loads(Path(studio.__file__).with_name('config.json').read_text(encoding='utf-8'))['studio']['video']


class Hochrechnen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = studio.Studio.__new__(studio.Studio)
        self.s.s = copy.deepcopy(basis.S)
        self.s.s['video'] = copy.deepcopy(CFG)
        self.s.comfy_ordner = str(self.root / 'ComfyUI')
        self.s.wurzel = str(self.root)
        self.s.projekte = lambda: []
        self.s.datei = lambda p: str(self.root / p) if (self.root / p).is_file() else None
        self.s.auftraege = []
        self.s._lock = threading.RLock()
        self.source = self.root / 'Original.mp4'
        self.source.write_bytes(b'Quellvideo')
        v = self.s.s['video']
        self.modelle = {}
        for ordner, name in [('loras', v['hochrechnen']['lora']),
                ('diffusion_models', v['modelle']['ref2va']), ('text_encoders', v['modelle']['clip']),
                ('vae', v['modelle']['vae_video']), ('vae', v['modelle']['vae_audio']),
                ('vae', v['dekoder']['int8_v1']['datei'])]:
            p = Path(self.s.comfy_ordner, 'models', ordner, name)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(name.encode())
            self.modelle[ordner, name] = p
        self.lora = self.modelle['loras', v['hochrechnen']['lora']]
        self.dek = self.modelle['vae', v['dekoder']['int8_v1']['datei']]
        v['hochrechnen']['lora_sha256'] = studio.datei_pruefsumme(self.lora)
        v['dekoder']['int8_v1']['sha256'] = studio.datei_pruefsumme(self.dek)
        self.m = {'breite': 960, 'hoehe': 544, 'bilder': 124}
        self.ton = dict(self.m, tonrate=48000, tonkanaele=2, tondauer=124 / 24, bilddauer=124 / 24)
        self.d = dict(art='video_hochrechnen', variation=4711,
                      vorlagen=[dict(art='bibliothek', pfad='Original.mp4', rolle='original')])
        for name, wert in [('video_masse', self.m), ('mp4_info', self.ton)]:
            patch = mock.patch.object(studio, name, return_value=wert)
            patch.start()
            self.addCleanup(patch.stop)

    def neu(self, **extra):
        return self.s._anlegen(self.s._pruefen(dict(self.d, **extra)))

    def test_masse(self):
        for quelle, ziel in [((960, 544), (1920, 1088)), ((544, 960), (1088, 1920)),
                              ((768, 768), (1440, 1440))]:
            self.assertEqual(studio.hochrechnen_masse(*quelle, 2088960), ziel)
        for q in [(1920, 1088), (3840, 2160), (0, 544)]:
            with self.assertRaises(ValueError):
                studio.hochrechnen_masse(*q, 2088960)

    def test_verfuegbarkeit(self):
        self.assertTrue(self.s.hochrechnen_verfuegbar())
        for datei in self.modelle.values():
            inhalt = datei.read_bytes()
            datei.unlink()
            self.assertFalse(self.s.hochrechnen_verfuegbar())
            datei.write_bytes(inhalt)
        self.s.s['video']['hochrechnen']['aktiv'] = False
        self.assertFalse(self.s.hochrechnen_verfuegbar())

    def test_graph_wie_referenz(self):
        a = self.neu()
        # Nur den eingefrorenen Funktionskörper lesen: keine Imports, Modellzugriffe oder Testläufe der Referenz.
        datei = Path(studio.__file__).parents[1] / 'SPEC-video-hochrechnen-referenz.py'
        baum = ast.parse(datei.read_text(encoding='utf-8'))
        funktion = next(n for n in baum.body if isinstance(n, ast.FunctionDef) and n.name == 'graph')
        v = self.s.s['video']
        ns = dict(MD=v['modelle'], V=v, QUELLE='Original.mp4', LORA=a['hochrechnen']['lora'],
                  B=1920, H=1088, L=124, PROMPT='')
        exec(compile(ast.Module(body=[funktion], type_ignores=[]), str(datei), 'exec'), ns)
        ref = ns['graph']('Test/Hochgerechnet')
        g = studio.hochrechnen_graph(a, v, 'Test/Hochgerechnet', 'Original.mp4 [output]')
        # Spezifikationsänderung: Originalton statt dekodiertem Ton, normalisiert an beiden Ausgängen.
        del ref['15']
        ref['50']['inputs']['audio'] = ['70', 0]
        ref['16']['inputs']['audio'] = ['70', 0]
        ref['70'] = g['70']
        self.assertEqual(g, ref)
        v2 = studio.mit_geraeten(self.s.s, dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:7'))['video']
        g2 = studio.hochrechnen_graph(a, v2, 'Test/Hochgerechnet', 'Original.mp4 [output]')
        for n in ('20', '21', '22', '23', '35'):
            self.assertEqual(g2[n]['inputs']['device'], 'gpu:7')
        self.assertNotIn('VAEDecodeAudio', {n['class_type'] for n in g.values()})

    def test_prompt_und_meta(self):
        Path(str(self.source) + '.json').write_text(json.dumps({'prompt': 'Originalbeschreibung'}), encoding='utf-8')
        a = self.neu()
        meta = self.s._meta(a)
        self.assertEqual(a['prompt'], 'Originalbeschreibung')
        self.assertEqual(meta['hochrechnen'], a['hochrechnen'])
        self.assertEqual(meta['modell'], 'Open-H3-Regenerate-2K')
        self.assertEqual(meta['laenge_bilder'], 124)
        self.assertEqual(meta['quell_breite'], 960)
        for feld in ('turbo', 'referenz_genau', 'ton_behalten'):
            self.assertIsNone(meta[feld])
        self.assertEqual(self.s._bedarf(a), {'haupt': 22528, 'neben': 9216})
        self.assertEqual(self.s._erwartet(a), 368)

    def test_nochmal_trotz_neuer_standards(self):
        a = self.neu()
        h = copy.deepcopy(a['hochrechnen'])
        v = self.s.s['video']
        v['hochrechnen'].update(lora='andere.safetensors', sigmas='falsch', aktiv=False)
        v['modelle']['ref2va'] = 'anders.safetensors'
        v['dekoder']['int8_v1']['sha256'] = 'a' * 64
        d = dict(self.d, hochrechnen=h, prompt='', quell_sha256=a['quell_sha256'])
        b = self.s._pruefen(d)
        self.assertEqual(b['hochrechnen'], h)
        h['sigmas'] = 'kaputt'
        self.assertEqual(b['hochrechnen'], a['hochrechnen'])
        self.assertEqual(studio.hochrechnen_graph(a, v, 'X', 'Q'), studio.hochrechnen_graph(b, v, 'X', 'Q'))

    def test_quelle_geaendert_beim_anlegen_und_rechnen(self):
        a = self.neu()
        self.source.write_bytes(b'Anderes Video')
        with self.assertRaisesRegex(ValueError, 'Ausgangsvideo.*verändert'):
            self.s._pruefen(dict(self.d, hochrechnen=a['hochrechnen'], prompt='', quell_sha256=a['quell_sha256']))
        with self.assertRaisesRegex(studio.Fehler, 'Ausgangsvideo.*verändert'):
            self.s._rechnen(a, None)

    def test_modelle_geaendert_vor_rechnen(self):
        for p in (self.lora, self.dek):
            with self.subTest(datei=p.name):
                original = p.read_bytes()
                a = self.neu()
                p.write_bytes(b'Veraendert')
                with self.assertRaisesRegex(studio.Fehler, 'Prüfsumme'):
                    self.s._rechnen(a, None)
                p.write_bytes(original)

    def test_hashcache(self):
        studio._MODELL_HASHES.clear()
        with mock.patch.object(studio, 'datei_pruefsumme', wraps=studio.datei_pruefsumme) as h:
            studio.modell_pruefsumme(self.lora)
            studio.modell_pruefsumme(self.lora)
            self.assertEqual(h.call_count, 1)
            self.lora.write_bytes(b'neu')
            studio.modell_pruefsumme(self.lora)
            self.assertEqual(h.call_count, 2)

    def test_fehler_bei_quellen(self):
        for bilder, text in [(141, 'bis 5 s'), (123, '17k'), (4, '17k')]:
            self.m['bilder'] = bilder
            with self.assertRaisesRegex(ValueError, text):
                self.neu()
        self.m['bilder'] = 124
        with mock.patch.object(studio, 'mp4_info', side_effect=ValueError('keine Tonspur')):
            with self.assertRaisesRegex(ValueError, 'Nur Videos mit Ton aus dem Studio'):
                self.neu()
        self.ton['tondauer'] += 1.1
        with self.assertRaisesRegex(ValueError, 'Sekunde länger'):
            self.neu()

    def test_falsche_endung_und_fehlende_lora(self):
        with self.assertRaisesRegex(ValueError, 'Vorlage'):
            self.neu(vorlagen=[dict(art='bibliothek', pfad='Original.webm', rolle='original')])
        self.lora.unlink()
        with self.assertRaisesRegex(ValueError, 'Modelldatei fehlt'):
            self.neu()

    def test_unvollstaendige_wiederholung_und_typen(self):
        a = self.neu()
        d = dict(self.d, hochrechnen=a['hochrechnen'], prompt='')
        with self.assertRaisesRegex(ValueError, 'Ohne Prüfsumme'):
            self.s._pruefen(d)
        d['quell_sha256'] = a['quell_sha256']
        for feld, wert in [('kennung', 'fremd'), ('fps', True), ('ziel_breite', 1920.0),
                           ('sigmas', 'nan, 0.8, 0.6, 0'), ('lora', '../fremd'), ('vae_dekoder', {})]:
            h = dict(a['hochrechnen'], **{feld: wert})
            with self.subTest(feld=feld), self.assertRaises(ValueError):
                self.s._pruefen(dict(d, hochrechnen=h))

    def test_genau_eine_quelle_und_feste_variation(self):
        for vorlagen in ([], self.d['vorlagen'] * 2):
            with self.assertRaisesRegex(ValueError, 'genau ein'):
                self.neu(vorlagen=vorlagen)
        a = self.neu(variation=None)
        self.assertIsInstance(a['variation'], int)
        with self.assertRaisesRegex(ValueError, 'Variationsnummer'):
            self.neu(hochrechnen=a['hochrechnen'], prompt='', quell_sha256=a['quell_sha256'], variation=None)

    def test_ton_samples_und_identische_fuehrung(self):
        # PCM-Operationen des gemeinsamen Helfers an künstlichen Samples ausführen.
        for rate in (44100, 48000):
            for fehlt in (0, -500, 1, 500):
                anzahl = round(124 / 24 * rate)
                original = list(range(anzahl - fehlt))
                a = self.neu()
                a.update(tonrate=rate, tondauer=len(original) / rate)
                g = studio.hochrechnen_graph(a, self.s.s['video'], 'X', 'Q')
                ton = {('41', 1): original}
                for key, n in g.items():
                    i = n['inputs']
                    if n['class_type'] == 'TrimAudioDuration':
                        ton[key, 0] = ton[tuple(i['audio'])][round(i['start_index'] * rate):round(i['duration'] * rate)]
                    elif n['class_type'] == 'EmptyAudio':
                        ton[key, 0] = [0] * round(i['duration'] * rate)
                    elif n['class_type'] == 'AudioConcat':
                        ton[key, 0] = ton[tuple(i['audio1'])] + ton[tuple(i['audio2'])]
                guide, ausgabe = g['50']['inputs']['audio'], g['16']['inputs']['audio']
                self.assertEqual(guide, ausgabe)
                self.assertEqual(ton[tuple(ausgabe)], (original + [0] * max(0, fehlt))[:anzahl])

    def test_graph_erkennung_auch_umbenannte_knoten(self):
        a = self.neu()
        g = studio.hochrechnen_graph(a, self.s.s['video'], 'X', 'Q')
        ids = {k: 'neu-' + k for k in g}
        umbenannt = {ids[k]: dict(n, inputs={feld: [ids[w[0]], w[1]] if isinstance(w, list) else w
                     for feld, w in n['inputs'].items()}) for k, n in g.items()}
        for graph in (g, umbenannt):
            e = studio.einstellungen_aus_graph(graph, dekoder=self.s.s['video']['dekoder'])
            self.assertEqual(e['art'], 'video_hochrechnen')
            for feld in ('prompt', 'variation', 'breite', 'hoehe'):
                self.assertEqual(e[feld], a[feld])
            h = dict(e['hochrechnen'], lora_sha256=a['hochrechnen']['lora_sha256'])
            self.assertEqual(h, a['hochrechnen'])
            self.assertNotIn('turbo', e)
        turbo = studio.bild_graph(dict(basis.EINSTELLUNG, turbo=True), basis.S, 'X')
        self.assertTrue(studio.einstellungen_aus_graph(turbo)['turbo'])
        self.assertNotIn('hochrechnen', studio.einstellungen_aus_graph(turbo))

    def test_karten_und_prozesse(self):
        bedarf = self.s._bedarf(self.neu())
        inst1, inst2 = parallel.instanzen()
        stand = parallel.antwort(24000, 23000)
        stand['karten'][0]['monitor'], stand['karten'][1]['monitor'] = False, True
        v, fehlt, _ = studio.karten_waehlen(stand, bedarf, inst1, haupt_ohne_monitor=True)
        self.assertEqual(v['haupt'], 0)
        self.assertEqual(v['rang'], 1)
        self.assertFalse(fehlt)
        self.assertFalse(inst2.kann(bedarf))
        stand['karten'][0]['frei'] = 18000
        v, fehlt, _ = studio.karten_waehlen(stand, bedarf, inst1, haupt_ohne_monitor=True)
        self.assertEqual(v['haupt'], 0)
        self.assertTrue(fehlt)

    def test_commit_warten_und_anmelden(self):
        a = self.neu()
        inst, _ = parallel.instanzen()
        self.s._inst = lambda: inst
        self.s.instanzen = [inst]
        self.s._schritt = mock.Mock()
        self.s.log = mock.Mock()
        stand = parallel.antwort(24000, 23000)
        stand['karten'][0]['monitor'], stand['karten'][1]['monitor'] = False, True
        self.s.zentrale = mock.Mock()
        self.s.zentrale.stand.return_value = (200, stand)
        self.s.zentrale.anmelden.return_value = (200, {'anmeldung': {'id': 'Test'}})
        with mock.patch.object(studio, 'commit_frei_mib', return_value=36863):
            self.assertIn('Arbeitsspeicher', self.s._platz(a)[1])
            self.s.zentrale.anmelden.assert_not_called()
        with mock.patch.object(studio, 'commit_frei_mib', return_value=36864):
            anmeldung, grund, geraete = self.s._platz(a)
            self.assertIsNone(grund)
            self.assertEqual(anmeldung, {'id': 'Test'})
            self.assertEqual(geraete['modell'], 'gpu:0')

    def test_js_nochmal_ohne_prompt(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node fehlt; JavaScript wird bei der Live-Abnahme geprüft')
        datei = Path(studio.__file__).with_name('web') / 'studio.js'
        code = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const src = fs.readFileSync(process.argv[1], 'utf8');
const ctx = vm.createContext({ console, document: { addEventListener() {} } });
// Nur die Funktionen ausführen, ohne DOM-Ereignisse oder Polling der laufenden App.
vm.runInContext(src.slice(0, src.indexOf("document.addEventListener('keydown'")) + `
  ST.bib = { eintraege: [{ pfad: 'Original.mp4' }] };
  const e = { projekt: '', pfad: 'Hochgerechnet.mp4', info: {
    art: 'video_hochrechnen', herkunft: 'studio', prompt: '', variation: 4711,
    breite: 1920, hoehe: 1088, laenge_bilder: 124, quell_sha256: 'abc',
    hochrechnen: { kennung: 'regenerate_v1', lora: 'alte.safetensors' },
    vorlagen: [{ pfad: 'Original.mp4', rolle: 'original' }]
  }};
  globalThis.e = e;
  globalThis.grund = wiederholbar(e);
  globalThis.anfrage = wiederAnfrage(e, false);
`, ctx);
assert.strictEqual(ctx.grund, null);
ctx.anfrage.then(d => {
  assert.strictEqual(d.art, 'video_hochrechnen');
  assert.strictEqual(d.prompt, '');
  assert.strictEqual(d.variation, 4711);
  assert.strictEqual(d.quell_sha256, 'abc');
  assert.strictEqual(d.hochrechnen.lora, 'alte.safetensors');
  assert.strictEqual(d.vorlagen[0].rolle, 'original');
  assert.strictEqual(d.vorlagen[0].pfad, 'Original.mp4');
  vm.runInContext('delete e.info.quell_sha256; globalThis.fehlt = wiederholbar(e)', ctx);
  assert.ok(ctx.fehlt);
}).catch(e => { console.error(e); process.exitCode = 1; });
'''
        r = subprocess.run([node, '-e', code, str(datei)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Konverter(unittest.TestCase):
    def test_reine_pruefung_ohne_torch(self):
        m = 'diffusion_model.blocks.0.attn.qkv_proj'
        formen = {m + '.lora_A.weight': [2, 3], m + '.lora_B.weight': [6, 2]}
        header = {'blocks.0.attn.qkv_proj.weight': {'shape': [6, 3]}}
        regenerate_lora.pruefen(formen, header, {m: 0.001}, erwartet={m})
        for fehler in (0.002, float('nan'), float('inf'), -0.1):
            with self.assertRaisesRegex(ValueError, 'Delta'):
                regenerate_lora.pruefen(formen, header, {m: fehler}, erwartet={m})
        with self.assertRaisesRegex(ValueError, 'Module fehlen'):
            regenerate_lora.pruefen({}, header, {}, erwartet={m})
        with self.assertRaisesRegex(ValueError, 'Form'):
            regenerate_lora.pruefen(formen, {'blocks.0.attn.qkv_proj.weight': {'shape': [5, 3]}}, {m: 0}, erwartet={m})
        self.assertEqual(len(regenerate_lora.erwartete_module()), 258)

    def test_header_nur_header(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, 'Modell.safetensors')
            kopf = json.dumps({'test.weight': {'shape': [3, 2]}}).encode()
            p.write_bytes(struct.pack('<Q', len(kopf)) + kopf + b'Gewichte werden nicht gelesen')
            self.assertEqual(regenerate_lora.modell_header(p)['test.weight']['shape'], [3, 2])

    def test_kunsttensoren(self):
        try:
            import torch
        except ImportError:
            self.skipTest('torch fehlt im Werkstatt-Python; reine Prüflogik separat geprüft')
        a = torch.tensor([[1., 2., 3.], [2., 1., 0.]])
        b = torch.tensor([[1., 0.], [0., 1.]])
        ref = lambda start, ende: b[start:ende] @ a
        self.assertEqual(regenerate_lora.delta_fehler(a.bfloat16(), b.bfloat16(), ref), 0)
        self.assertGreater(regenerate_lora.delta_fehler((a * 2).bfloat16(), b.bfloat16(), ref), 0.002)


if __name__ == '__main__':
    unittest.main()
