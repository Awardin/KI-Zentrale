import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import studio  # noqa: E402
from werkstatt.tests.test_studio import S  # noqa: E402

M3 = {
    'modell_name': 'Pixal3D',
    'modelle': {'multiview': 'pixal3d_multiview_int8_convrot.safetensors', 'einzelbild': 'pixal3d_int8_convrot.safetensors',
                'dino': 'dino_v3_L_naf_fp32.safetensors', 'vae_form': 'trellis_2_shape_vae_bf16.safetensors',
                'vae_textur': 'trellis_2_texture_vae_bf16.safetensors', 'biref': 'birefnet.safetensors',
                'moge': 'moge_2_vitl_normal_fp16.safetensors'},
    'fov': 20.0, 'rand': 1.1, 'remesh': 768,
    'schritte': {'struktur': 12, 'form': 20, 'feinform': 12, 'textur': 12},
    'cfg': {'struktur': 7.5, 'struktur_ab': 0.667, 'struktur_rescale': 0.7, 'struktur_shift': 5.0,
            'form': 7.5, 'form_ab': 0.769, 'form_rescale': 0.5, 'textur': 1.0},
    'stufen': [{'id': 'fein', 'name': 'Fein', 'aufloesung': 1536, 'dreiecke': 700000, 'textur': 2048, 'normalen': True,
                'standard': True},
               {'id': 'leicht', 'name': 'Leicht', 'aufloesung': 1024, 'dreiecke': 150000, 'textur': 1024, 'normalen': False}],
    'vorschau': {'bilder': 24, 'fps': 12, 'groesse': 768, 'hintergrund': '#FFFFFF'},
    'bedarf_mib': {'fest': 16384}, 'zeit': {'fein': 420, 'leicht': 240},
}


def png_kopf(pfad, breite, hoehe):
    """Nur Signatur und IHDR: reicht für die Größenerkennung."""
    ihdr = struct.pack('>IIBBBBB', breite, hoehe, 8, 6, 0, 0, 0)
    with open(pfad, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr)))


class Modell3D(unittest.TestCase):
    """Stufe 3t: 3D-Modell mit Pixal3D – Prüfung, Graph, Begleitdaten, Ablage der GLB neben dem Vorschau-Video."""
    BEREIT = {'laeuft': True, 'ordner_ok': True}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = os.path.join(self.tmp.name, 'Studio')
        os.makedirs(os.path.join(self.wurzel, 'Praxis'))
        os.makedirs(os.path.join(self.wurzel, 'Garten'))
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI',
                             'studio_ordner': os.path.join(self.tmp.name, '2wild'), 'bedarf_je_karte_mib': 20000}]}
        with mock.patch('threading.Thread'):
            self.s = studio.Studio({'studio': dict(S, ordner=self.wurzel, modell3d=M3)}, zc, self.tmp.name,
                                   lambda t: None, mock.MagicMock())
        png_kopf(os.path.join(self.wurzel, 'Praxis', 'Blatt_00001_.png'), 4096, 1024)
        png_kopf(os.path.join(self.wurzel, 'Praxis', 'Bild_00001_.png'), 1024, 1328)
        png_kopf(os.path.join(self.wurzel, 'Praxis', 'Bild_00002_.png'), 1024, 1328)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def v(name, rolle='vorlage'):
        return {'art': 'bibliothek', 'pfad': 'Praxis/' + name, 'rolle': rolle}

    def erzeugen(self, d):
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT):
            return self.s.erzeugen(d)

    def test_nicht_eingerichtet(self):
        code, a = self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Blatt_00001_.png')]})
        self.assertEqual(code, 400)
        self.assertIn('Pixal3D', a['fehler'])
        e = self.s.einstellungen()
        self.assertEqual((e['modell3d_verfuegbar'], e['modell3d_bild_verfuegbar']), (False, False))
        self.assertIn('modell3d', e['arten'])

    def test_pruefen_drehblatt_bild_und_ansichten(self):
        with mock.patch.object(self.s, '_modell_da', return_value=True):
            e = self.s.einstellungen()
            self.assertEqual((e['modell3d_verfuegbar'], e['modell3d_bild_verfuegbar'], e['modell3d_zeit']),
                             (True, True, {'fein': 420, 'leicht': 240}))
            self.assertEqual([x['id'] for x in e['modell3d_stufen']], ['fein', 'leicht'])
            # Drehblatt: erkannt am Seitenverhältnis, Standardstufe, zufällige Nummer, Anzahl erlaubt
            code, a = self.erzeugen({'art': 'modell3d', 'projekt': 'Praxis', 'vorlagen': [self.v('Blatt_00001_.png')], 'anzahl': 2})
            self.assertEqual((code, len(a['neu'])), (200, 2))
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j['modus'], j['stufe'], j['breite'], j['hoehe'], j['prompt'], j['schritte'], j['qualitaet']),
                             ('drehblatt', 'fein', 4096, 1024, '', None, None))
            self.assertEqual(j['detail'], {'aufloesung': 1536, 'dreiecke': 700000, 'textur': 2048, 'normalen': True})
            self.assertTrue(0 < j['variation'] < 2 ** 48)
            self.assertEqual((self.s._bedarf(j), self.s._erwartet(j)), ({'fest': 16384}, 420))
            # Ein Bild: Modus bild, leichte Stufe, feste Nummer
            j = self.s._finden(self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Bild_00001_.png')], 'stufe': 'leicht',
                                              'variation': 7})[1]['neu'][0])
            self.assertEqual((j['modus'], j['stufe'], j['variation'], self.s._erwartet(j)), ('bild', 'leicht', 7, 240))
            # Erzwungen: ein hochkantiges Bild als Drehblatt
            j = self.s._finden(self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Bild_00001_.png')], 'modus': 'drehblatt'})[1]['neu'][0])
            self.assertEqual(j['modus'], 'drehblatt')
            # Einzelansichten
            j = self.s._finden(self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Bild_00002_.png', 'hinten'),
                                                                               self.v('Bild_00001_.png', 'vorn')]})[1]['neu'][0])
            self.assertEqual((j['modus'], [x['rolle'] for x in j['vorlagen']]), ('ansichten', ['vorn', 'hinten']))
            for falsch, wort in (({'art': 'modell3d', 'vorlagen': []}, 'Drehblatt'),
                                 ({'art': 'modell3d', 'vorlagen': [self.v('Bild_00002_.png', 'hinten')]}, 'vorn'),
                                 ({'art': 'modell3d', 'vorlagen': [self.v('Blatt_00001_.png')], 'stufe': 'x'}, 'Detailstufe'),
                                 ({'art': 'modell3d', 'vorlagen': [self.v('Blatt_00001_.png')], 'variation': 'a'}, 'ganze Zahl'),
                                 ({'art': 'modell3d', 'vorlagen': [self.v('Blatt_00001_.png')], 'projekt': 'Nix'}, 'Projekt')):
                code, a = self.erzeugen(falsch)
                self.assertEqual(code, 400, falsch)
                self.assertIn(wort, a['fehler'])
            # Meta des Vorschau-Videos
            m = self.s._meta(j)
            self.assertEqual((m['art'], m['modell'], m['modell_datei'], m['laenge_bilder'], m['sekunden'], m['breite']),
                             ('modell3d', 'Pixal3D', 'pixal3d_multiview_int8_convrot.safetensors', 24, 2.0, 768))
        # Ohne Einzelbild-Modell geht nur das Drehblatt
        da = lambda ordner, datei: datei not in ('pixal3d_int8_convrot.safetensors',)  # noqa: E731
        with mock.patch.object(self.s, '_modell_da', side_effect=da):
            self.assertEqual((self.s.modell3d_verfuegbar(), self.s.modell3d_bild_verfuegbar()), (True, False))
            code, a = self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Bild_00001_.png')]})
            self.assertEqual(code, 400)
            self.assertIn('aus einem Bild', a['fehler'])
            self.assertEqual(self.erzeugen({'art': 'modell3d', 'vorlagen': [self.v('Blatt_00001_.png')]})[0], 200)

    def test_graph_drehblatt(self):
        e = {'modus': 'drehblatt', 'breite': 4096, 'hoehe': 1024, 'variation': 5,
             'detail': {'aufloesung': 1536, 'dreiecke': 700000, 'textur': 2048, 'normalen': True}}
        g = studio.modell3d_graph(e, M3, 'Praxis/Modell', {'vorlage': 'Praxis/Blatt_00001_.png [output]'})
        self.assertEqual(g['1']['inputs'], {'image': 'Praxis/Blatt_00001_.png [output]'})
        self.assertEqual([(g[f'1{k}']['inputs']['x'], g[f'1{k}']['inputs']['width'], g[f'1{k}']['inputs']['height'])
                          for k in range(4)], [(0, 1024, 1024), (1024, 1024, 1024), (2048, 1024, 1024), (3072, 1024, 1024)])
        self.assertEqual(g['30']['inputs']['pad_factor'], 1.1)
        self.assertEqual(g['41']['class_type'], 'Pixal3DMultiViewConditioning')
        self.assertEqual({k: g['41']['inputs'][k] for k in ('front', 'left', 'back', 'right', 'fov')},
                         {'front': ['30', 0], 'left': ['31', 0], 'back': ['32', 0], 'right': ['33', 0], 'fov': 20.0})
        self.assertEqual(g['50']['inputs']['unet_name'], 'pixal3d_multiview_int8_convrot.safetensors')
        # Sampler wie die Vorlage: Struktur 12 (shift 5, CFG-Verlauf), Form 20, feine Form 12 simple, Textur 12 bei CFG 1
        self.assertEqual((g['61']['inputs']['steps'], g['61']['inputs']['cfg'], g['61']['inputs']['seed'], g['53']['inputs']['shift']),
                         (12, 7.5, 5, 5.0))
        self.assertEqual((g['65']['inputs']['steps'], g['65']['inputs']['seed'], g['67']['inputs']['scheduler'],
                          g['71']['inputs']['cfg'], g['71']['inputs']['model']), (20, 6, 'simple', 1.0, ['50', 0]))
        self.assertEqual(g['66']['inputs']['target_resolution'], 1536)
        self.assertEqual((g['81']['inputs']['sign_mode'], g['81']['inputs']['sign_mode.qef'], g['82']['inputs']['target_face_count'],
                          g['84']['inputs']['resolution'], g['85']['inputs']['texture_size']), ('udf', False, 700000, 2048, 2048))
        self.assertEqual(g['88']['inputs']['normal_map'], ['86', 0])
        self.assertEqual(g['88']['inputs']['occlusion'], ['87', 0])
        self.assertEqual((g['91']['class_type'], g['91']['inputs']['filename_prefix']), ('SaveGLB', 'Praxis/Modell'))
        # Drehteller: 24 Drehungen um die Hochachse, Bilder in einer Kette gebündelt, Video mit 12 Bildern je Sekunde
        self.assertEqual([g[str(100 + k)]['inputs']['mode.angle_y'] for k in (0, 1, 23)], [0.0, 15.0, 345.0])
        self.assertEqual(g['100']['inputs']['mode'], 'euler_xyz')
        self.assertEqual((g['200']['inputs']['width'], g['200']['inputs']['background']), (768, '#FFFFFF'))
        self.assertEqual((g['301']['inputs'], g['323']['inputs']['image2']), ({'image1': ['200', 0], 'image2': ['201', 0]}, ['223', 0]))
        self.assertEqual((g['400']['inputs'], g['401']['inputs']['filename_prefix']), ({'images': ['323', 0], 'fps': 12.0}, 'Praxis/Modell'))
        # Leichte Stufe: ohne Normalen und Verschattung
        g = studio.modell3d_graph(dict(e, detail={'aufloesung': 1024, 'dreiecke': 150000, 'textur': 1024, 'normalen': False}),
                                  M3, 'P', {'vorlage': 'x.png'})
        self.assertNotIn('86', g)
        self.assertNotIn('normal_map', g['88']['inputs'])
        self.assertEqual((g['66']['inputs']['target_resolution'], g['82']['inputs']['target_face_count']), (1024, 150000))

    def test_graph_bild_und_ansichten(self):
        e = {'modus': 'bild', 'breite': 1024, 'hoehe': 1328, 'variation': 1,
             'detail': {'aufloesung': 1536, 'dreiecke': 700000, 'textur': 2048, 'normalen': True}}
        g = studio.modell3d_graph(e, M3, 'P/Modell', {'vorlage': 'foto.png'})
        self.assertEqual(g['41']['class_type'], 'Pixal3DConditioning')
        self.assertEqual((g['41']['inputs']['image'], g['41']['inputs']['camera_angle_x']), (['30', 0], ['28', 0]))
        self.assertEqual((g['26']['inputs']['model_name'], g['27']['inputs']['image'], g['28']['inputs']['axis']),
                         ('moge_2_vitl_normal_fp16.safetensors', ['30', 0], 'horizontal'))
        self.assertEqual(g['50']['inputs']['unet_name'], 'pixal3d_int8_convrot.safetensors')
        self.assertNotIn('10', g)
        g = studio.modell3d_graph(dict(e, modus='ansichten'), M3, 'P/Modell', {'vorn': 'a.png', 'hinten': 'b.png'})
        self.assertEqual((g['10']['inputs']['image'], g['12']['inputs']['image']), ('a.png', 'b.png'))
        self.assertEqual({k for k in g['41']['inputs'] if k in ('front', 'left', 'back', 'right')}, {'front', 'back'})
        self.assertNotIn('11', g)

    def test_ablegen_verschieben_papierkorb(self):
        ordner = os.path.join(self.wurzel, 'Praxis')
        mp4 = os.path.join(ordner, 'Modell_00001_.mp4')
        glb = os.path.join(ordner, 'Modell_00002_.glb')
        for p in (mp4, glb):
            with open(p, 'wb') as f:
                f.write(b'x' * 10)
        meta = {}
        self.assertEqual(self.s._modell3d_ablegen([mp4, glb], meta), [mp4])
        self.assertTrue(os.path.isfile(os.path.join(ordner, 'Modell_00001_.glb')))
        self.assertFalse(os.path.exists(glb))
        self.assertEqual((meta['modell_3d'], meta['modell_3d_bytes']), ('Modell_00001_.glb', 10))
        with self.assertRaises(studio.Fehler):
            self.s._modell3d_ablegen([mp4], {})
        with open(mp4 + '.json', 'w', encoding='utf-8') as f:
            json.dump({'art': 'modell3d', 'modell_3d': 'Modell_00001_.glb', 'datei': 'Modell_00001_.mp4'}, f)
        # Die 3D-Datei ist über die Bibliothek erreichbar (Herunterladen, im Ordner zeigen), aber keine eigene Kachel
        self.assertTrue(self.s.datei('Praxis/Modell_00001_.glb'))
        self.assertFalse(any(x['name'].endswith('.glb') for x in self.s.bibliothek(neu=True)['eintraege']))
        # Verschieben nimmt die 3D-Datei mit; Begleitdaten zeigen weiter auf sie
        code, a = self.s.verschieben(['Praxis/Modell_00001_.mp4'], 'Garten')
        self.assertEqual((code, a['verschoben'], a['fehler']), (200, ['Garten/Modell_00001_.mp4'], []))
        self.assertTrue(os.path.isfile(os.path.join(self.wurzel, 'Garten', 'Modell_00001_.glb')))
        self.assertFalse(os.path.exists(os.path.join(ordner, 'Modell_00001_.glb')))
        # Papierkorb: Video, Begleitdaten und 3D-Datei zusammen, gezählt wird nur das Video
        with mock.patch('werkstatt.studio.winapi.in_papierkorb', return_value=True) as korb:
            code, a = self.s.papierkorb(['Garten/Modell_00001_.mp4'])
        self.assertEqual((code, a['anzahl']), (200, 1))
        self.assertEqual(sorted(os.path.basename(p) for p in korb.call_args.args[0]),
                         ['Modell_00001_.glb', 'Modell_00001_.mp4', 'Modell_00001_.mp4.json'])

    def test_bild_masse(self):
        png = os.path.join(self.tmp.name, 'a.png')
        png_kopf(png, 4096, 1024)
        self.assertEqual(studio.bild_masse(png), (4096, 1024))
        jpg = os.path.join(self.tmp.name, 'a.jpg')
        with open(jpg, 'wb') as f:  # SOI, APP0 (leer), SOF0 mit Höhe 1786 und Breite 1286
            f.write(b'\xff\xd8' + b'\xff\xe0' + struct.pack('>H', 4) + b'\x00\x00'
                    + b'\xff\xc0' + struct.pack('>H', 17) + b'\x08' + struct.pack('>HH', 1786, 1286) + b'\x03' + b'\x00' * 9)
        self.assertEqual(studio.bild_masse(jpg), (1286, 1786))
        webp = os.path.join(self.tmp.name, 'a.webp')
        with open(webp, 'wb') as f:  # VP8X: Breite-1 und Höhe-1 als 24-Bit-Zahlen
            f.write(b'RIFF' + struct.pack('<I', 30) + b'WEBP' + b'VP8X' + struct.pack('<I', 10) + b'\x00' * 4
                    + (800 - 1).to_bytes(3, 'little') + (1424 - 1).to_bytes(3, 'little'))
        self.assertEqual(studio.bild_masse(webp), (800, 1424))
        self.assertEqual(studio.bild_masse(os.path.join(self.tmp.name, 'fehlt.png')), (None, None))


if __name__ == '__main__':
    unittest.main()
