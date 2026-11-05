import copy
import json
from pathlib import Path
import unittest
from unittest import mock

import test_studio as basis
from werkstatt import studio

S, VIDEO = basis.S, basis.VIDEO
DATEI = 'minimax_h3_video_vae_int8_convrot.safetensors'
SHA = '52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e'
WERT = {'kennung': 'int8_v1', 'datei': DATEI, 'sha256': SHA}


def konfig():
    v = copy.deepcopy(S['video'])
    v.update(dekoder={'int8_v1': dict(datei=DATEI, sha256=SHA, rolle='ganz', bedarf_zusatz_mib=0)},
             dekoder_standard='int8_v1')
    return v


def faelle():
    yield 'text', dict(VIDEO), {}
    yield 'bild_start', dict(VIDEO, art='video_bild'), {'start': 'a.png'}
    yield 'bild_ende', dict(VIDEO, art='video_bild'), {'start': 'a.png', 'ende': 'b.png'}
    yield 'referenz_bild', dict(VIDEO, art='video_referenz'), {'bilder': ['a.png']}
    yield 'referenz_video', dict(VIDEO, art='video_referenz'), {'clips': ['a.mp4']}
    w = basis.Weiterfuehren()
    for modus in ('verlaengern', 'davor', 'verbinden', 'schleife'):
        rollen = ['ziel'] if modus == 'davor' else ['ausgang', 'ziel'] if modus == 'verbinden' else ['ausgang']
        yield modus, dict(w.auftrag(modus, 175, [w.quelle(r, 124) for r in rollen]), art='video_weiter'), {r: r + '.mp4' for r in rollen}


def graph(e, v, namen):
    return (studio.weiter_graph if e['art'] == 'video_weiter' else studio.video_graph)(e, v, 'Test/Video', namen)


class VaeGraph(unittest.TestCase):
    def test_auslieferung_mit_int8_standard(self):
        cfg = json.loads(Path(studio.__file__).with_name('config.json').read_text(encoding='utf-8'))['studio']['video']
        self.assertEqual(cfg['dekoder_standard'], 'int8_v1')
        d = dict(cfg['dekoder']['int8_v1'])
        self.assertEqual(d.pop('monitorkarte_mib'), 19456)
        self.assertIn('nur die Kartenwahl', d.pop('monitorkarte_grund'))
        self.assertEqual(d, dict(datei=DATEI, sha256=SHA, rolle='ganz', bedarf_zusatz_mib=0))

    def test_altgraphen_und_ganz(self):
        # Vor dem Umbau eingefrorene Graphen, vollständiger JSON-Vergleich, auch bei gesetztem Standard.
        alt = json.loads(Path(__file__).with_name('vae_dekoder_altgraphen.json').read_text(encoding='utf-8'))
        for name, e, namen in faelle():
            with self.subTest(art=name):
                self.assertEqual(graph(e, konfig(), namen), alt[name])
                erwartet = copy.deepcopy(alt[name])
                erwartet['3']['inputs']['vae_name'] = DATEI
                mit = graph(dict(e, vae_dekoder=WERT), konfig(), namen)
                self.assertEqual(mit, erwartet)
                z = studio.einstellungen_aus_graph(mit, dekoder=konfig()['dekoder'])
                self.assertEqual(z['vae_dekoder'], WERT)
                self.assertNotIn('vae_dekoder', studio.einstellungen_aus_graph(alt[name], dekoder=konfig()['dekoder']))

    def test_dekodieren(self):
        v = konfig()
        v['dekoder']['int8_v1'].update(rolle='dekodieren', bedarf_zusatz_mib=1234)
        for name, e, namen in faelle():
            with self.subTest(art=name):
                alt = graph(e, v, namen)
                mit = graph(dict(e, vae_dekoder=WERT), v, namen)
                self.assertEqual(mit['34'], {'class_type': 'VAELoader', 'inputs': {'vae_name': DATEI}})
                self.assertEqual(mit['35'], {'class_type': 'SelectVAEDevice', 'inputs': {
                    'vae': ['34', 0], 'device': v['geraete']['vae_video']}})
                self.assertEqual(mit['14']['inputs']['vae'], ['35', 0])
                self.assertEqual(studio.einstellungen_aus_graph(mit, dekoder=v['dekoder'])['vae_dekoder'], WERT)
                del mit['34'], mit['35']
                mit['14']['inputs']['vae'] = ['22', 0]
                self.assertEqual(mit, alt)  # Kodieren, AddGuide, Audio, ImageFromBatch bleiben identisch

    def test_unbekannte_datei(self):
        g = graph(VIDEO, konfig(), {})
        g['3']['inputs']['vae_name'] = 'fremd.safetensors'
        vorher = copy.deepcopy(g)
        self.assertNotIn('vae_dekoder', studio.einstellungen_aus_graph(g, dekoder=konfig()['dekoder']))
        self.assertEqual(g, vorher)

    def test_js_weitergabe(self):
        js = Path(studio.__file__).with_name('web').joinpath('studio.js').read_text(encoding='utf-8')
        wieder = js.split('async function wiederAnfrage(', 1)[1].split('\nfunction ', 1)[0]
        self.assertIn('vae_dekoder: video ? i.vae_dekoder : undefined', wieder)
        self.assertNotIn('video_dekoder_standard', wieder)
        self.assertIn("if (video) ST.extra.vae_dekoder = i.vae_dekoder", js)
        self.assertEqual(js.count("Object.hasOwn(ST.extra, 'vae_dekoder') ? ST.extra.vae_dekoder : EIN().video_dekoder_standard"), 2)


class VaeDienst(unittest.TestCase):
    setUp = basis.Bibliothek.setUp
    tearDown = basis.Bibliothek.tearDown

    def vorbereiten(self):
        self.s.s = dict(self.s.s, video=konfig())

    def test_server_nochmal_meta_bibliothek(self):
        self.vorbereiten()
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}), \
                mock.patch.object(self.s, '_modell_da', return_value=True):
            for wert in (None, WERT):
                self.s.s['video']['dekoder_standard'] = None
                d = dict(VIDEO, projekt='Praxis', **({'vae_dekoder': wert} if wert else {}))
                code, r = self.s.erzeugen(d)
                self.assertEqual(code, 200, r)
                a = self.s._finden(r['neu'][0])
                meta = self.s._meta(a)
                self.s.s['video']['dekoder_standard'] = 'int8_v1'
                self.assertEqual(self.s.einstellungen()['video_dekoder_standard'], WERT)
                code, r = self.s.erzeugen(dict(meta, bilder=a['bilder']))
                self.assertEqual(code, 200, r)
                b = self.s._finden(r['neu'][0])
                self.assertEqual(graph(a, konfig(), {}), graph(b, konfig(), {}))
                if wert:
                    self.assertEqual(a['vae_dekoder'], WERT)
                    self.assertEqual(meta['vae_dekoder'], WERT)
                else:
                    self.assertNotIn('vae_dekoder', a)
                    self.assertNotIn('vae_dekoder', b)
                    self.assertNotIn('vae_dekoder', meta)
                p = Path(self.wurzel, 'Praxis', 'V.mp4')
                basis.mp4_bauen(str(p), {'werkstatt': json.dumps(meta)})
                info = self.s._info_bilden(str(p), {})
                self.assertEqual(info.get('vae_dekoder'), wert)
                basis.mp4_bauen(str(p), {'prompt': json.dumps(graph(a, konfig(), {}))})
                self.assertEqual(self.s._info_bilden(str(p), {}).get('vae_dekoder'), wert)

    def test_bedarf(self):
        self.vorbereiten()
        self.s.bedarf_video = {'haupt': 20480, 'neben': 7168, 'eine_ohne_monitor': 22528}
        alt = dict(self.s.bedarf_video)
        for _, e, _ in faelle():
            self.assertEqual(self.s._bedarf(e), alt)
            self.assertEqual(self.s._bedarf(dict(e, vae_dekoder=WERT)), alt)
        self.s.s['video']['dekoder']['int8_v1'].update(rolle='dekodieren', bedarf_zusatz_mib=1234)
        self.assertEqual(self.s._bedarf(dict(VIDEO, vae_dekoder=WERT)),
                         {'haupt': 20480, 'neben': 8402, 'eine_ohne_monitor': 23762})
        self.assertEqual(self.s.bedarf_video, alt)
        for rolle in ('eine', 'fest'):
            self.s.bedarf_video = {rolle: 5000}
            self.assertEqual(self.s._bedarf(dict(VIDEO, vae_dekoder=WERT)), {rolle: 6234})

    def test_bedarf_monitorkarte_nur_mit_passendem_dekoder(self):
        self.vorbereiten()
        self.s.bedarf_video = {'haupt': 20480, 'neben': 7168, 'eine_ohne_monitor': 22528}
        alt = dict(self.s.bedarf_video)
        self.s.s['video']['dekoder']['int8_v1']['monitorkarte_mib'] = 19456
        for _, e, _ in faelle():
            with self.subTest(art=e['art']):
                self.assertEqual(self.s._bedarf(e), alt)
                self.assertEqual(self.s._bedarf(dict(e, vae_dekoder=WERT)), dict(alt, monitorkarte=19456))
        self.assertIn('monitorkarte', studio.BEDARF_ROLLEN)
        self.assertEqual(studio.bedarf_lesen({'monitorkarte': 19456}), {'monitorkarte': 19456})
        self.assertEqual(self.s.bedarf_video, alt)

    def test_validierung_und_rechnen(self):
        self.vorbereiten()
        with mock.patch.object(self.s, '_modell_da', return_value=True):
            for wert, text in ((dict(WERT, kennung='unbekannt'), 'Kennung'), (dict(WERT, datei='falsch'), 'Datei'),
                               (dict(WERT, sha256='falsch'), 'SHA-256'), ('int8_v1', 'Kennung'), (None, 'Kennung')):
                d = dict(VIDEO, vae_dekoder=wert)
                with self.subTest(wert=wert):
                    with self.assertRaisesRegex(ValueError, text):
                        self.s._pruefen(d)
                    with self.assertRaisesRegex(studio.Fehler, text):
                        self.s._rechnen(d, None)
                    self.s._bedarf(d)  # ungültiger gespeicherter Auftrag darf die Warteschlange nicht beenden
            self.assertEqual(self.s._pruefen(dict(VIDEO, vae_dekoder=WERT))['vae_dekoder'], WERT)
        with mock.patch.object(self.s, '_modell_da', return_value=False):
            with self.assertRaisesRegex(ValueError, 'Modelldatei.*fehlt'):
                self.s._pruefen(dict(VIDEO, vae_dekoder=WERT))
            with self.assertRaisesRegex(studio.Fehler, 'Modelldatei.*fehlt'):
                self.s._rechnen(dict(VIDEO, vae_dekoder=WERT), None)


class VaeSzenen(unittest.TestCase):
    setUp = basis.Szenenfolge.setUp
    tearDown = basis.Szenenfolge.tearDown
    studio = basis.Szenenfolge.studio
    neu = basis.Szenenfolge.neu
    folge = basis.Szenenfolge.folge
    fertig = basis.Szenenfolge.fertig
    BEREIT = basis.Szenenfolge.BEREIT

    def test_alle_szenen_auch_nochmal(self):
        self.s.s = dict(self.s.s, video=konfig())
        alt = json.loads(Path(__file__).with_name('vae_dekoder_altgraphen.json').read_text(encoding='utf-8'))
        with mock.patch.object(self.s, '_modell_da', return_value=True):
            for wert in (None, WERT):
                code, r = self.neu(variation=7, **({'vae_dekoder': wert} if wert else {}))
                self.assertEqual(code, 200, r)
                f = self.folge(r['id'])
                a = self.s._finden(f['takes'][0][0])
                self.assertEqual(a.get('vae_dekoder'), wert)
                self.assertEqual(f.get('vae_dekoder'), wert)
                erwartet = copy.deepcopy(alt['szene_1'])
                if wert:
                    erwartet['3']['inputs']['vae_name'] = DATEI
                self.assertEqual(graph(a, konfig(), {}), erwartet)
                self.fertig(a['id'], 'Praxis/Video_00001_.mp4')
                self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 200)
                f = self.folge(r['id'])
                b = self.s._finden(f['takes'][1][0])
                self.assertEqual(b.get('vae_dekoder'), wert)
                erwartet = copy.deepcopy(alt['szene_2'])
                if wert:
                    erwartet['3']['inputs']['vae_name'] = DATEI
                self.assertEqual(graph(b, konfig(), {'ausgang': 'a.mp4'}), erwartet)
                self.fertig(b['id'], 'Praxis/Video_00002_.mp4')
                self.assertEqual(self.s.folge_aktion(r['id'], 'nochmal')[0], 200)
                b = self.s._finden(self.folge(r['id'])['takes'][1][-1])
                self.assertEqual(b.get('vae_dekoder'), wert)
                # „Nochmal“ ändert nur die Variationsnummer, der Dekoder bleibt der ersten Szene treu.
                nochmal = graph(b, konfig(), {'ausgang': 'a.mp4'})
                nochmal['12']['inputs']['noise_seed'] = erwartet['12']['inputs']['noise_seed']
                self.assertEqual(nochmal, erwartet)

