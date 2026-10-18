import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import studio  # noqa: E402

S = {
    'ordner': '', 'ordner_2wild': 'gencenter', 'modell_name': 'Qwen-Image 2.1',
    'modelle': {'unet': 'qwen_image_2.1_bf16.safetensors', 'clip': 'qwen3vl_8b_bf16.safetensors',
                'unet_int8': 'qwen_image_2.1_int8_convrot.safetensors', 'clip_int8': 'qwen3vl_8b_int8_convrot.safetensors',
                'vae': 'qwen_image_2.1_vae_bf16.safetensors'},
    'int8': {'aktiv': True, 'zeitfaktor': 0.5},
    'ausformulieren': {'modell': 'pe_t2i.safetensors', 'geraet': 'gpu:0', 'system_datei': 'ausformulieren_t2i.txt',
                       'max_laenge': 2048, 'sekunden': 15, 'bedarf_mib': {'eine': 20480, 'haupt': 20480, 'neben': 4096}},
    'pose': {'modell': 'sdpose.safetensors', 'beschreibung': 'Pose-Skelett'},
    'bedarf_hilfe_mib': {'fest': 4096},
    'geraete': {'modell': 'gpu:0', 'clip': 'gpu:1', 'vae': 'gpu:1'},
    'cfg': 1.0, 'shift': 3.1, 'bearbeiten_aufloesung': 1024, 'max_vorlagen': 10, 'sekunden_je_schritt': 1.4,
    'max_seite': 4096, 'max_pixel': 4300000, 'bedarf_gross_mib': {'eine': 22016, 'haupt': 18432, 'neben': 6144}, 'bedarf_gross_ab_pixel': 2000000,
    'durchsichtig': {'vorlage': 'This is an RGBA format image with transparency. {beschreibung}. The image has an alpha '
                                'channel and a transparent background.', 'rest_bis': 0.02},
    'schnelle_aufmerksamkeit': {'aktiv': True, 'backend': 'comfy kitchen attention'},
    'bearbeiten_aufloesungen': [{'wert': 1024, 'name': 'Wie Vorlage 1'}, {'wert': 1440, 'name': '2 MP'}, {'wert': 2048, 'name': '4 MP'}],
    'freistellen': {'vorlage': 'Isolate the main subject: keep only {motiv}. Transparent background.',
                    'motiv_standard': 'the main subject', 'rest_bis': 0.4, 'schnell_modell': 'birefnet.safetensors'},
    'vorlage_zeit': {'fest': 0.94, 'je_flaeche': 0.33},
    'details': {'lora': 'detail.safetensors', 'staerke': 1.0},
    'turbo': {'lora': 'turbo_qwen21.safetensors', 'staerke': 1.0, 'sigmas': [1.0, 0.9375, 0.875, 0.75, 0.5, 0.25],
              'mu_basis': 0.5, 'mu_max': 0.9, 'token_basis': 256, 'token_max': 8192, 'zeitfaktor': 1.4,
              'modell': 'qwen_image_turbo.safetensors', 'modell_aktiv': True,
              'modell_sigmas': [1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568]},
    'verbessern': {'ausschnitt_faktor': 3, 'ausschnitt_min': 384, 'arbeit_min': 1024, 'arbeit_max': 1328,
                   'arbeit_seite_max': 2048, 'rand_px': 6, 'weich_px': 6,
                   'finden': {'modell': 'sam3.safetensors', 'schwelle': 0.5, 'verfeinern': 2, 'vorschau_px': 768},
                   'vorlage': {'max': 1, 'megapixel': 1.0, 'zeitfaktor': 0.55, 'ausschnitt_faktor': 2},
                   'staerken': [{'wert': 1.0, 'name': 'Alles', 'text': '', 'standard': True},
                                {'wert': 0.8, 'name': 'Viel', 'text': ''}, {'wert': 0.6, 'name': 'Wenig', 'text': ''}]},
    'qualitaet': [{'schritte': 6, 'name': 'Turbo', 'text': '', 'turbo': True}, {'schritte': 20, 'name': 'Standard', 'text': ''},
                  {'schritte': 40, 'name': 'Max', 'text': '', 'standard': True}],
    'formate': [{'id': 'quadrat', 'name': 'Quadrat 1:1', 'breite': 1328, 'hoehe': 1328}],
    'video': {
        'modell_name': 'MiniMax-H3',
        'modelle': {'fl2va': 'h3_fl2va.safetensors', 'ref2va': 'h3_ref2va.safetensors', 'clip': 'h3_clip.safetensors',
                    'vae_video': 'h3_vae_video.safetensors', 'vae_audio': 'h3_vae_audio.safetensors',
                    'turbo_fl2va': 'turbo_fl2v.safetensors', 'turbo_ref2va': 'turbo_ref2v.safetensors'},
        'geraete': {'modell': 'gpu:0', 'clip': 'gpu:1', 'vae_video': 'gpu:1', 'vae_audio': 'gpu:1'},
        'fps': 24, 'turbo_bis_schritte': 8, 'max_referenzbilder': 9, 'max_clips': 3,
        'realismus': {'lora': 'realism.safetensors', 'staerke': 1.0, 'ausloeser': 'r34l1sm'},
        'tauschen': {'lora': 'tausch.safetensors', 'staerke': 1.0, 'vorlage': 'Replace only {wer} in <Video 1>.',
                     'wer_beispiel': 'the woman'},
        'acc8': {'aktiv': True, 'lora': 'MiniMax-H3-Ref2VA-Acc-8Step_x.safetensors', 'schritte': 8},
        'dmad': {'aktiv': True, 'lora': 'dmad_full.safetensors', 'schritte': 4, 'sampler': 'lcm', 'shift_video': 12.0,
                 'shift_audio': 2.0},
        'schnelle_aufmerksamkeit': {'aktiv': True, 'backend': 'comfy kitchen attention', 'zeitfaktor': 0.6},
        'zeitlupe': {'modell': 'rife.safetensors', 'zeit': {'grund_s': 3, 'je_bild_s': 0.03}, 'bedarf_mib': {'fest': 4096}},
        'freistellen': {'verfahren': 'kombi', 'motiv': 'person', 'sam3': 'sam3.safetensors', 'biref': 'biref.safetensors',
                        'erweitern_px': 16, 'crf': 20, 'zeit': {'grund_s': 10, 'je_bild_s': 0.3}, 'bedarf_mib': {'fest': 8192}},
        'szenen': {'max_szenen': 8, 'ohne_schnitt': 'Ohne Schnitt.'},
        'zeit': {'grund_s': 30, 'je_schritt_s': 12.4, 'exponent': 2.0},
        'qualitaet': [{'schritte': 8, 'name': 'Schnell beste', 'text': ''}, {'schritte': 20, 'name': 'Beste', 'text': '', 'standard': True}],
        'formate': [{'id': 'breit', 'name': 'Breit', 'breite': 960, 'hoehe': 544, 'standard': True}],
        'laengen': [{'bilder': 124, 'name': 'etwa 5 s', 'standard': True}, {'bilder': 192, 'name': 'etwa 8 s'}],
    },
}
VIDEO = {'art': 'video_text', 'prompt': 'Ein Hund läuft über eine Wiese', 'breite': 960, 'hoehe': 544, 'bilder': 124,
         'schritte': 20, 'variation': 7}
EINSTELLUNG = {'art': 'bild', 'prompt': 'Ein ruhiger Raum', 'negativ': 'unscharf', 'breite': 1328, 'hoehe': 1328,
               'schritte': 40, 'cfg': 1.0, 'variation': 424242}


def _block(typ, daten):
    return struct.pack('>I', len(daten)) + typ + daten + struct.pack('>I', zlib.crc32(typ + daten))


def png_bauen(pfad, texte, breite=4, hoehe=3):
    ihdr = struct.pack('>IIBBBBB', breite, hoehe, 8, 2, 0, 0, 0)
    roh = b''.join(b'\x00' + b'\x00' * breite * 3 for _ in range(hoehe))
    teile = [b'\x89PNG\r\n\x1a\n', _block(b'IHDR', ihdr)]
    for k, v in texte.items():
        teile.append(_block(b'tEXt', k.encode('latin-1') + b'\0' + v.encode('latin-1')))
    teile += [_block(b'IDAT', zlib.compress(roh)), _block(b'IEND', b'')]
    with open(pfad, 'wb') as f:
        f.write(b''.join(teile))


def rle_aus(breite, hoehe, markiert):
    """Lauflängen wie aus der Oberfläche: abwechselnd frei/markiert, beginnend mit frei."""
    rle, wert, n = [], False, 0
    for y in range(hoehe):
        for x in range(breite):
            if markiert(x, y) != wert:
                rle.append(n)
                wert, n = not wert, 0
            n += 1
    rle.append(n)
    return {'breite': breite, 'hoehe': hoehe, 'rle': rle}


def png_pixel(daten):
    """Graustufen-PNG (Filter 0, wie maske_png es schreibt) -> (breite, hoehe, Pixelbytes)."""
    breite, hoehe, tiefe, farbe = struct.unpack('>IIBB', daten[16:26])
    assert (tiefe, farbe) == (8, 0)
    pos, idat = 8, b''
    while pos < len(daten):
        laenge, typ = struct.unpack('>I4s', daten[pos:pos + 8])
        if typ == b'IDAT':
            idat += daten[pos + 8:pos + 8 + laenge]
        pos += 12 + laenge
    roh = zlib.decompress(idat)
    return breite, hoehe, b''.join(roh[y * (breite + 1) + 1:(y + 1) * (breite + 1)] for y in range(hoehe))


def _atom(typ, inhalt):
    return struct.pack('>I', 8 + len(inhalt)) + typ + inhalt


def mp4_video_bauen(pfad, bilder=124, breite=960, hoehe=544, stts=None, ton_s=None, tonrate=44100, kanaele=2,
                    bild_elst=((0, 1024),), ton_elst=((0, 1024),), ohne_ton=False, zwei_bildspuren=False, fuellung=b'\0' * 64):
    """MP4-Struktur wie aus ComfyUI (PyAV) für mp4_info: Bild mit Zeitmaß 12288 und 512 je Bild (24 fps, B-Bild-
    Verzögerung 1024 in der Edit-List), Ton als AAC mit 1024 Vorlauf; `ton_s` ist die wirksame Tondauer."""
    def edts(e):
        return _atom(b'edts', _atom(b'elst', struct.pack('>II', 0, len(e)) + b''.join(
            struct.pack('>IiHH', d, z, 1, 0) for d, z in e))) if e else b''

    def spur(art, zeitmass, dauer, eintraege, e, stsd=b''):
        b, h = (breite, hoehe) if art == b'vide' else (0, 0)
        tkhd = _atom(b'tkhd', b'\0' * 76 + struct.pack('>II', b << 16, h << 16))
        mdhd = _atom(b'mdhd', struct.pack('>IIIII', 0, 0, 0, zeitmass, dauer) + b'\0' * 4)
        hdlr = _atom(b'hdlr', b'\0' * 8 + art + b'\0' * 13)
        tabelle = _atom(b'stts', struct.pack('>II', 0, len(eintraege)) + b''.join(struct.pack('>II', n, d) for n, d in eintraege))
        return _atom(b'trak', tkhd + edts(e) + _atom(b'mdia', mdhd + hdlr + _atom(b'minf', _atom(b'stbl', stsd + tabelle))))
    stts = stts or [(bilder, 512)]
    spuren = spur(b'vide', 12288, sum(n * d for n, d in stts), stts, bild_elst) * (2 if zwei_bildspuren else 1)
    if not ohne_ton:
        vorlauf = ton_elst[0][1] if ton_elst else 0
        dauer = round((sum(n for n, _ in stts) / 24 if ton_s is None else ton_s) * tonrate) + vorlauf
        stsd = _atom(b'stsd', struct.pack('>II', 0, 1) + struct.pack('>I4s6sH', 36, b'mp4a', b'\0' * 6, 1) + b'\0' * 8
                     + struct.pack('>HHHHI', kanaele, 16, 0, 0, tonrate << 16))
        spuren += spur(b'soun', tonrate, dauer, [(dauer // 1024, 1024)], ton_elst, stsd)
    with open(pfad, 'wb') as f:
        f.write(_atom(b'ftyp', b'isom\0\0\0\0') + _atom(b'mdat', fuellung) + _atom(b'moov', _atom(b'mvhd', b'\0' * 100) + spuren))


def mp4_bauen(pfad, texte):
    """Minimal-MP4 wie von ComfyUI (PyAV): mdat vor moov, Metadaten als mdta-Schlüssel in moov/meta."""
    namen = list(texte)
    keys = struct.pack('>II', 0, len(namen)) + b''.join(
        struct.pack('>I', 8 + len(n.encode())) + b'mdta' + n.encode() for n in namen)
    ilst = b''.join(_atom(struct.pack('>I', i + 1), _atom(b'data', struct.pack('>II', 1, 0) + texte[n].encode()))
                    for i, n in enumerate(namen))
    meta = _atom(b'meta', _atom(b'hdlr', b'\0' * 8 + b'mdta' + b'\0' * 13) + _atom(b'keys', keys) + _atom(b'ilst', ilst))
    with open(pfad, 'wb') as f:
        f.write(_atom(b'ftyp', b'isom\0\0\0\0') + _atom(b'mdat', b'\0' * 5000) + _atom(b'moov', _atom(b'mvhd', b'\0' * 100) + meta))


class Namen(unittest.TestCase):
    def test_projektname(self):
        self.assertEqual(studio.projektname('  Praxis   Website  '), 'Praxis Website')
        for falsch in ('', 'a/b', 'a:b', 'CON', 'con.txt', '_intern', 'x' * 61):
            with self.assertRaises(ValueError, msg=falsch):
                studio.projektname(falsch)
        with self.assertRaises(ValueError):
            studio.projektname('GenCenter', reserviert=('gencenter',))

    def test_pfade_bleiben_in_der_bibliothek(self):
        w = r'C:\Studio'
        self.assertEqual(studio.absolut('Projekt/Bild_00001_.png', w), os.path.normpath(r'C:\Studio\Projekt\Bild_00001_.png'))
        for falsch in ('../x.png', 'Projekt/../../x.png', '/x.png', r'\x.png', 'C:/x.png', '', None, '.'):
            self.assertIsNone(studio.absolut(falsch, w), falsch)

    def test_freier_name(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, 'Bild.png'), 'w').close()
            open(os.path.join(d, 'Bild (2).png.json'), 'w').close()
            self.assertEqual(studio.freier_name(d, 'Bild.png'), 'Bild (3).png')
            self.assertEqual(studio.freier_name(d, 'Neu.png'), 'Neu.png')


class Ablauf(unittest.TestCase):
    def test_neues_bild(self):
        g = studio.bild_graph(EINSTELLUNG, S, 'Praxis/Bild')
        self.assertEqual(g['10']['inputs']['filename_prefix'], 'Praxis/Bild')
        self.assertEqual(g['6']['inputs'], {'width': 1328, 'height': 1328, 'batch_size': 1})
        self.assertEqual(g['20']['inputs']['device'], 'gpu:0')
        self.assertEqual(g['21']['inputs']['device'], 'gpu:1')
        k = g['8']['inputs']
        self.assertEqual((k['seed'], k['steps'], k['cfg'], k['positive'], k['negative']), (424242, 40, 1.0, ['4', 0], ['5', 0]))

    def test_bearbeiten(self):
        e = dict(EINSTELLUNG, art='bearbeiten')
        g = studio.bild_graph(e, S, 'Bearbeitet', ['Praxis/Bild_00001_.png [output]', 'hochgeladen.png'])
        self.assertEqual(g['4']['class_type'], 'TextEncodeQwenImage21')
        self.assertEqual(g['4']['inputs']['images.image_2'], ['102', 0])
        self.assertEqual(g['101']['inputs']['image'], 'Praxis/Bild_00001_.png [output]')
        self.assertEqual(g['8']['inputs']['latent_image'], ['4', 2])
        self.assertNotIn('6', g)
        with self.assertRaises(studio.Fehler):
            studio.bild_graph(e, S, 'Bearbeitet', [])

    def test_bearbeiten_mit_eigenem_format(self):
        # Charakterblatt: eigene Fläche statt der Größe von Vorlage 1
        g = studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', breite=1920, hoehe=1088, groesse_von='format'), S, 'x', ['v.png'])
        self.assertEqual(g['6'], {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': 1920, 'height': 1088, 'batch_size': 1}})
        self.assertEqual(g['8']['inputs']['latent_image'], ['6', 0])
        self.assertEqual(g['4']['inputs']['images.image_1'], ['101', 0])
        r = studio.einstellungen_aus_graph(g)
        self.assertEqual((r['art'], r['groesse_von'], r['breite'], r['hoehe']), ('bearbeiten', 'format', 1920, 1088))
        ohne = studio.einstellungen_aus_graph(studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten'), S, 'x', ['v.png']))
        self.assertEqual(ohne['groesse_von'], 'vorlage')  # Maße allein schalten das eigene Format nicht ein

    def test_ablauf_zurueck_lesen(self):
        g = studio.einstellungen_aus_graph(studio.bild_graph(EINSTELLUNG, S, 'x/Bild'))
        self.assertEqual((g['art'], g['prompt'], g['negativ'], g['variation'], g['schritte'], g['breite'], g['hoehe']),
                         ('bild', 'Ein ruhiger Raum', 'unscharf', 424242, 40, 1328, 1328))
        self.assertEqual(studio.modellname(g['modell_datei']), 'Qwen-Image 2.1')
        b = studio.einstellungen_aus_graph(studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten'), S, 'x', ['v.png']))
        self.assertEqual((b['art'], b['prompt'], b['negativ'], b['vorlagen']), ('bearbeiten', 'Ein ruhiger Raum', 'unscharf', ['v.png']))


class Freistellen(unittest.TestCase):
    def test_prompt(self):
        self.assertEqual(studio.freistellen_prompt(S, ''), 'Isolate the main subject: keep only the main subject. Transparent background.')
        self.assertIn('keep only die Frau.', studio.freistellen_prompt(S, '  die Frau '))

    def test_ablauf(self):
        e = dict(EINSTELLUNG, art='freistellen', prompt=studio.freistellen_prompt(S, 'die Frau'))
        g = studio.freistellen_graph(e, S, 'Praxis/Freigestellt', 'Praxis/Bild_00001_.png [output]')
        self.assertEqual(g['101']['inputs']['image'], 'Praxis/Bild_00001_.png [output]')
        self.assertEqual((g['4']['inputs']['images.image_1'], g['4']['inputs']['resolution']), (['101', 0], 1024))
        self.assertEqual(g['8']['inputs']['latent_image'], ['4', 2])
        self.assertEqual(g['82']['inputs']['value'], 0.4)
        self.assertEqual([g[n]['inputs']['operation'] for n in ('83', '84', '85')], ['subtract', 'add', 'add'])
        self.assertEqual((g['88']['inputs']['width'], g['88']['inputs']['height']), (['90', 0], ['90', 1]))
        # Ein schmaler Rand fällt weg (sonst heller Saum), vor dem Skalieren auf Originalgröße
        self.assertEqual((g['92']['inputs']['mask'], g['92']['inputs']['expand'], g['87']['inputs']['mask']), (['86', 0], 1, ['92', 0]))
        # Maske auf die Originalpixel, ganz durchsichtige Stellen weiß; gespeichert wird das Original mit Transparenz
        self.assertEqual((g['95']['inputs']['destination'], g['95']['inputs']['mask']), (['101', 0], ['93', 0]))
        self.assertEqual(g['94']['inputs']['color'], 0xFFFFFF)
        self.assertEqual(g['91']['inputs'], {'image': ['95', 0], 'alpha': ['89', 0]})
        self.assertEqual(g['10']['inputs'], {'images': ['91', 0], 'filename_prefix': 'Praxis/Freigestellt'})
        r = studio.einstellungen_aus_graph(g)
        self.assertEqual((r['art'], r['breite'], r['vorlagen']), ('freistellen', None, ['Praxis/Bild_00001_.png [output]']))
        t = studio.freistellen_graph(dict(e, turbo=True), S, 'x', 'o.png')
        self.assertEqual((t['8']['class_type'], t['43']['inputs']['sigmas']), ('SamplerCustomAdvanced', studio.turbo_sigmas(S['turbo'], 1024, 1024)))

    def test_hochskalieren(self):
        g = studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', aufloesung=1440), S, 'x', ['v.png'])
        self.assertEqual((g['4']['inputs']['resolution'], g['8']['inputs']['latent_image']), (1440, ['4', 2]))
        self.assertEqual(studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten'), S, 'x', ['v.png'])['4']['inputs']['resolution'], 1024)
        t = studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', aufloesung=2048, turbo=True), S, 'x', ['v.png'])
        self.assertEqual(t['43']['inputs']['sigmas'], studio.turbo_sigmas(S['turbo'], 2048, 2048))


class Details(unittest.TestCase):
    def test_ablauf(self):
        e = dict(EINSTELLUNG, art='bearbeiten', details=True)
        g = studio.bild_graph(e, S, 'x', ['v.png'])
        self.assertEqual(g['25']['inputs'], {'model': ['20', 0], 'lora_name': 'detail.safetensors', 'strength_model': 1.0})
        self.assertEqual(g['7']['inputs']['model'], ['25', 0])
        self.assertTrue(studio.einstellungen_aus_graph(g)['details'])
        # mit Turbo: erst die Turbo-LoRA, dann die Detail-LoRA, dann der Shift
        t = studio.bild_graph(dict(e, turbo=True), S, 'x', ['v.png'])
        self.assertEqual((t['24']['inputs']['model'], t['25']['inputs']['model'], t['7']['inputs']['model']),
                         (['20', 0], ['24', 0], ['25', 0]))
        r = studio.einstellungen_aus_graph(t)
        self.assertEqual((r['turbo'], r['details'], r['schritte']), (True, True, 6))
        # ohne Wunsch und bei neuen Bildern bleibt alles wie bisher
        self.assertNotIn('25', studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten'), S, 'x', ['v.png']))
        self.assertNotIn('25', studio.bild_graph(dict(EINSTELLUNG, details=True), S, 'x'))
        self.assertNotIn('details', studio.einstellungen_aus_graph(studio.bild_graph(dict(EINSTELLUNG, turbo=True), S, 'x')))


class Durchsichtig(unittest.TestCase):
    def test_prompt_und_umkehrung(self):
        p = studio.durchsichtig_prompt(S, ' Eine weiße Tasse. ')
        self.assertEqual(p, 'This is an RGBA format image with transparency. Eine weiße Tasse. The image has an alpha '
                            'channel and a transparent background.')
        self.assertEqual(studio.durchsichtig_beschreibung(S['durchsichtig']['vorlage'], p), 'Eine weiße Tasse')
        self.assertIsNone(studio.durchsichtig_beschreibung(S['durchsichtig']['vorlage'], 'Eine weiße Tasse'))

    def test_ablauf(self):
        g = studio.bild_graph(dict(EINSTELLUNG, durchsichtig=True), S, 'x/Bild')
        self.assertTrue(g['4']['inputs']['text'].startswith('This is an RGBA format image'))
        self.assertIn('Ein ruhiger Raum.', g['4']['inputs']['text'])
        # aufräumen: Schleier bis 2 % weg, Rest gestreckt, unter ganz Durchsichtigem Weiß
        self.assertEqual((g['80']['inputs']['image'], g['10']['inputs']['images'], g['91']['inputs']['alpha']),
                         (['9', 0], ['91', 0], ['87', 0]))
        self.assertEqual((g['82']['inputs']['value'], g['83']['inputs']['operation'], g['85']['inputs']['operation']),
                         (0.02, 'subtract', 'multiply'))
        self.assertAlmostEqual(g['84']['inputs']['value'], 0.02 / 0.98)
        self.assertEqual((g['94']['inputs']['color'], g['95']['inputs']['mask'], g['95']['inputs']['destination']),
                         (0xFFFFFF, ['93', 0], ['80', 0]))
        r = studio.einstellungen_aus_graph(g, S['durchsichtig']['vorlage'])
        self.assertEqual((r['art'], r['durchsichtig'], r['prompt']), ('bild', True, 'Ein ruhiger Raum'))
        # mit Turbo liest das Aufräumen weiter das dekodierte Bild
        t = studio.bild_graph(dict(EINSTELLUNG, durchsichtig=True, turbo=True), S, 'x/Bild')
        self.assertEqual((t['8']['class_type'], t['9']['inputs']['samples'], t['80']['inputs']['image']),
                         ('SamplerCustomAdvanced', ['8', 0], ['9', 0]))
        # nur bei neuen Bildern und nur auf Wunsch; Freigestelltes bleibt Freigestelltes
        self.assertNotIn('80', studio.bild_graph(EINSTELLUNG, S, 'x'))
        self.assertNotIn('80', studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', durchsichtig=True), S, 'x', ['v.png']))
        f = studio.freistellen_graph(dict(EINSTELLUNG, art='freistellen', prompt='p'), S, 'x', 'o.png')
        self.assertEqual(studio.einstellungen_aus_graph(f)['art'], 'freistellen')


class Schnell(unittest.TestCase):
    def test_ablauf(self):
        g = studio.bild_graph(dict(EINSTELLUNG, schnell=True), S, 'x')
        self.assertEqual(g['26'], {'class_type': 'ModelAttentionBackend',
                                   'inputs': {'model': ['20', 0], 'attention': 'comfy kitchen attention'}})
        self.assertEqual(g['7']['inputs']['model'], ['26', 0])
        self.assertTrue(studio.einstellungen_aus_graph(g)['schnell'])
        # nach Turbo- und Detail-LoRA, vor dem Shift
        t = studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', turbo=True, details=True, schnell=True), S, 'x', ['v.png'])
        self.assertEqual((t['24']['inputs']['model'], t['25']['inputs']['model'], t['26']['inputs']['model'],
                          t['7']['inputs']['model'], t['42']['inputs']['model']),
                         (['20', 0], ['24', 0], ['25', 0], ['26', 0], ['7', 0]))
        e = dict(EINSTELLUNG, schnell=True)
        self.assertEqual(studio.freistellen_graph(dict(e, art='freistellen', turbo=True), S, 'x', 'o.png')['7']['inputs']['model'],
                         ['26', 0])
        v = dict(e, staerke=1.0, ausschnitt={'x': 0, 'y': 0, 'breite': 512, 'hoehe': 512},
                 arbeit={'breite': 1024, 'hoehe': 1024})
        self.assertEqual(studio.verbessern_graph(v, S, 'V', 'o.png', 'm.png')['26']['class_type'], 'ModelAttentionBackend')
        # ohne Wunsch bleibt der Ablauf wie bisher (so bleibt „Nochmal“ älterer Bilder pixelgleich)
        alt = studio.bild_graph(EINSTELLUNG, S, 'x')
        self.assertNotIn('26', alt)
        self.assertEqual(alt['7']['inputs']['model'], ['20', 0])
        self.assertNotIn('schnell', studio.einstellungen_aus_graph(alt))


def png_mit_filter(breite, hoehe, pixel, k, filter_typ):
    """PNG (8 Bit, k = 1 Graustufen / 3 RGB) mit einem festen Zeilenfilter, wie ihn Pillow wählen kann."""
    def paeth(a, b, c):
        pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
        return a if pa <= pb and pa <= pc else b if pb <= pc else c
    n, vorher, roh = breite * k, bytes(breite * k), b''
    for y in range(hoehe):
        z = pixel[y * n:(y + 1) * n]
        a = lambda i: z[i - k] if i >= k else 0  # noqa: E731
        c = lambda i: vorher[i - k] if i >= k else 0  # noqa: E731
        f = [lambda i: z[i], lambda i: z[i] - a(i), lambda i: z[i] - vorher[i],
             lambda i: z[i] - (a(i) + vorher[i]) // 2, lambda i: z[i] - paeth(a(i), vorher[i], c(i))][filter_typ]
        roh += bytes([filter_typ]) + bytes(f(i) & 255 for i in range(n))
        vorher = z
    kopf = struct.pack('>IIBBBBB', breite, hoehe, 8, {1: 0, 3: 2}[k], 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + _block(b'IHDR', kopf) + _block(b'IDAT', zlib.compress(roh)) + _block(b'IEND', b'')


class Int8(unittest.TestCase):
    def test_dateien_und_ablauf(self):
        self.assertEqual(studio.qwen_dateien({}, S), ('qwen_image_2.1_bf16.safetensors', 'qwen3vl_8b_bf16.safetensors'))
        e = dict(EINSTELLUNG, int8=True)
        g = studio.bild_graph(e, S, 'Praxis/Bild')
        self.assertEqual((g['1']['inputs']['unet_name'], g['2']['inputs']['clip_name']),
                         ('qwen_image_2.1_int8_convrot.safetensors', 'qwen3vl_8b_int8_convrot.safetensors'))
        z = studio.einstellungen_aus_graph(g)
        self.assertEqual((z['int8'], z['art'], z['prompt']), (True, 'bild', 'Ein ruhiger Raum'))
        # ohne das Feld (ältere Aufträge, „Nochmal“) bleibt BF16
        g = studio.bild_graph(EINSTELLUNG, S, 'Praxis/Bild')
        self.assertEqual(g['1']['inputs']['unet_name'], 'qwen_image_2.1_bf16.safetensors')
        self.assertNotIn('int8', studio.einstellungen_aus_graph(g))
        # MiniMax-Dateien heißen auch „int8“, sind aber kein Qwen
        self.assertNotIn('int8', studio.einstellungen_aus_graph(studio.video_graph(VIDEO, S['video'], 'x')))


class FreistellenSchnell(unittest.TestCase):
    def test_ablauf_und_zurueck_lesen(self):
        g = studio.freistellen_schnell_graph({}, S, 'Praxis/Freigestellt', 'Praxis/Bild_00001_.png [output]')
        self.assertEqual((g['70']['inputs']['bg_removal_name'], g['71']['class_type'], g['10']['inputs']['images']),
                         ('birefnet.safetensors', 'RemoveBackground', ['91', 0]))
        self.assertEqual((g['91']['inputs']['alpha'], g['95']['inputs']['mask'], g['93']['inputs']['mask']),
                         (['72', 0], ['93', 0], ['72', 0]))  # Durchsichtigkeit; ganz Durchsichtiges wird weiß
        self.assertFalse({'UNETLoader', 'KSampler'} & {n['class_type'] for n in g.values()})
        z = studio.einstellungen_aus_graph(g)
        self.assertEqual((z['art'], z['verfahren'], z['vorlagen'], z['breite']),
                         ('freistellen', 'schnell', ['Praxis/Bild_00001_.png [output]'], None))


class Pose(unittest.TestCase):
    def test_ablauf_und_zurueck_lesen(self):
        g = studio.pose_graph({}, S, 'Praxis/Pose', 'Praxis/Bild_00001_.png [output]')
        self.assertEqual((g['75']['inputs']['ckpt_name'], g['76']['inputs']['vae'], g['77']['inputs']['keypoints'],
                          g['77']['inputs']['draw_feet'], g['10']['inputs']['images']),
                         ('sdpose.safetensors', ['75', 2], ['76', 0], True, ['77', 0]))
        z = studio.einstellungen_aus_graph(g)
        self.assertEqual((z['art'], z['vorlagen']), ('pose', ['Praxis/Bild_00001_.png [output]']))
        self.assertNotIn('personen', z)
        self.assertNotIn('bboxes', g['76']['inputs'])
        self.assertFalse({'78', '79', '96'} & set(g))

    def test_alle_personen(self):
        # SAM3 sucht die Personen, SDPose zeichnet jede in ihrem Rahmen
        g = studio.pose_graph({'personen': True}, S, 'Praxis/Pose', 'Praxis/Bild_00001_.png [output]')
        self.assertEqual((g['78']['inputs']['ckpt_name'], g['79']['inputs']['text'], g['79']['inputs']['clip'],
                          g['96']['inputs']['image'], g['96']['inputs']['refine_iterations'], g['76']['inputs']['bboxes']),
                         ('sam3.safetensors', 'person:6', ['78', 1], ['101', 0], 0, ['96', 1]))
        z = studio.einstellungen_aus_graph(g)
        self.assertEqual((z['art'], z['personen']), ('pose', True))


class StellePerWort(unittest.TestCase):
    def test_ablauf(self):
        g = studio.finden_graph(S, 'Praxis/Bild_00001_.png [output]', 'hand:2')
        self.assertEqual((g['78']['inputs']['ckpt_name'], g['79']['inputs']['text'], g['79']['inputs']['clip'],
                          g['96']['inputs']['threshold'], g['98']['inputs']['largest_size'], g['98']['inputs']['upscale_method']),
                         ('sam3.safetensors', 'hand:2', ['78', 1], 0.5, 768, 'area'))
        self.assertEqual((g['88']['inputs']['source'], g['89']['inputs']['source']), (['90', 0], ['90', 1]))

    def test_png_lesen_alle_filter(self):
        breite, hoehe = 7, 5
        rgb = bytes((x * 37 + y * 11 + k * 5) & 255 for y in range(hoehe) for x in range(breite) for k in range(3))
        for f in range(5):
            self.assertEqual(studio.png_lesen(png_mit_filter(breite, hoehe, rgb, 3, f)), (breite, hoehe, 3, rgb), f)
        grau = bytes((x * 50 + y * 3) & 255 for y in range(hoehe) for x in range(breite))
        self.assertEqual(studio.png_lesen(png_mit_filter(breite, hoehe, grau, 1, 4))[3], grau)
        # die eigene Markierung als PNG lässt sich wieder lesen
        m = rle_aus(9, 4, lambda x, y: 2 <= x < 5 and y >= 1)
        b, h, k, px = studio.png_lesen(studio.maske_png(m))
        self.assertEqual((b, h, k), (9, 4, 1))
        self.assertEqual(studio.maske_hochrechnen(b, h, k, px, 9, 4), m)
        with self.assertRaises(ValueError):
            studio.png_lesen(b'kein png')

    def test_maske_hochrechnen(self):
        # 4×3-Vorschau, markiert: Spalte 1–2 in Zeile 0–1 und die ganze Zeile 2 (auch über den Zeilenwechsel hinweg)
        klein = [[0, 9, 255, 0], [0, 1, 200, 0], [5, 5, 5, 5]]
        px = bytes(v for zeile in klein for v in zeile for _ in range(3))
        m = studio.maske_hochrechnen(4, 3, 3, px, 8, 6)
        self.assertEqual(sum(m['rle']), 48)
        self.assertEqual(m, rle_aus(8, 6, lambda x, y: y >= 4 or (y < 4 and 2 <= x < 6)))
        self.assertEqual(studio.maske_hochrechnen(4, 3, 3, bytes(36), 8, 6)['rle'], [48])
        self.assertEqual(studio.maske_hochrechnen(4, 3, 3, bytes([255] * 36), 8, 6)['rle'], [0, 48])  # alles markiert


class Ausformulieren(unittest.TestCase):
    def test_rahmen_und_umkehrung(self):
        t = studio.ausformulieren_text('<|im_start|>system\nSei knapp.<|im_end|>', ' Hund im Garten ')
        self.assertTrue(t.startswith('<|im_start|>system\nSei knapp.<|im_end|>\n<|im_start|>user\nHund im Garten<|im_end|>'))
        self.assertTrue(t.endswith('<|im_start|>assistant\n<think>\n</think>\n'))
        self.assertEqual(studio.ausformulieren_wunsch(t), 'Hund im Garten')
        self.assertIsNone(studio.ausformulieren_wunsch('Hund im Garten'))

    def test_ablauf(self):
        e = dict(EINSTELLUNG, ausformulieren=True, int8=True)
        g = studio.bild_graph(e, S, 'Praxis/Bild', system='<|im_start|>system\nX<|im_end|>')
        self.assertEqual((g['4']['inputs']['text'], g['61']['inputs']['device'], g['62']['inputs']['sampling_mode.seed'],
                          g['63']['inputs']['source'], g['60']['inputs']['type']),
                         (['62', 0], 'gpu:0', 424242, ['62', 0], 'stable_diffusion'))
        z = studio.einstellungen_aus_graph(g)
        self.assertEqual((z['ausformulieren'], z['prompt'], z['int8']), (True, 'Ein ruhiger Raum', True))
        # nicht mit durchsichtigem Hintergrund und nicht ohne Systemtext
        for extra, system in (({'durchsichtig': True}, 'X'), ({}, None)):
            g = studio.bild_graph(dict(e, **extra), S, 'x', system=system)
            self.assertNotIn('62', g)


class Turbo(unittest.TestCase):
    def test_zeitplan(self):
        # Stützstellen der Modellkarte, verschoben mit mu nach Bildgröße (Werte wie im Versuch vom 24.09.2026)
        self.assertEqual(studio.turbo_sigmas(S['turbo'], 1328, 1328),
                         '1.000000, 0.971870, 0.941598, 0.873574, 0.697269, 0.434310, 0')
        klein = [float(x) for x in studio.turbo_sigmas(S['turbo'], 1024, 1024).split(',')]
        self.assertEqual((len(klein), klein[0], klein[-1]), (7, 1.0, 0.0))
        self.assertTrue(all(a > b for a, b in zip(klein, klein[1:])))

    def test_neues_bild_mit_turbo(self):
        g = studio.bild_graph(dict(EINSTELLUNG, schritte=6, turbo=True), S, 'x')
        self.assertEqual(g['24']['inputs'], {'model': ['20', 0], 'lora_name': 'turbo_qwen21.safetensors', 'strength_model': 1.0})
        self.assertEqual(g['7']['inputs']['model'], ['24', 0])
        self.assertEqual(g['8']['class_type'], 'SamplerCustomAdvanced')
        self.assertEqual((g['8']['inputs']['sigmas'], g['8']['inputs']['latent_image'], g['41']['inputs']['noise_seed']),
                         (['43', 0], ['6', 0], 424242))
        self.assertEqual(g['42']['inputs']['conditioning'], ['4', 0])
        self.assertEqual(g['43']['inputs']['sigmas'], studio.turbo_sigmas(S['turbo'], 1328, 1328))
        self.assertEqual(g['9']['inputs']['samples'], ['8', 0])
        self.assertNotIn('KSampler', {n['class_type'] for n in g.values()})
        r = studio.einstellungen_aus_graph(g)
        self.assertEqual((r['art'], r['turbo'], r['schritte'], r['variation'], r['prompt']), ('bild', True, 6, 424242, 'Ein ruhiger Raum'))
        # ohne Turbo unverändert
        self.assertNotIn('24', studio.bild_graph(EINSTELLUNG, S, 'x'))

    def test_bearbeiten_und_verbessern_mit_turbo(self):
        b = studio.bild_graph(dict(EINSTELLUNG, art='bearbeiten', turbo=True), S, 'x', ['v.png'])
        self.assertEqual(b['43']['inputs']['sigmas'], studio.turbo_sigmas(S['turbo'], 1024, 1024))
        self.assertEqual((b['8']['inputs']['latent_image'], b['42']['inputs']['conditioning']), (['4', 2], ['4', 0]))
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        a, arb = studio.ausschnitt_berechnen(studio.maske_rahmen(m)[0], 64, 48, S['verbessern'])
        v = studio.verbessern_graph(dict(EINSTELLUNG, art='verbessern', staerke=0.8, ausschnitt=a, arbeit=arb, turbo=True),
                                    S, 'x', 'o.png [output]', 'm.png')
        self.assertEqual(v['44'], {'class_type': 'SplitSigmasDenoise', 'inputs': {'sigmas': ['43', 0], 'denoise': 0.8}})
        self.assertEqual((v['8']['inputs']['sigmas'], v['8']['inputs']['latent_image']), (['44', 1], ['31', 0]))
        self.assertEqual(v['43']['inputs']['sigmas'], studio.turbo_sigmas(S['turbo'], arb['breite'], arb['hoehe']))
        voll = studio.verbessern_graph(dict(EINSTELLUNG, art='verbessern', staerke=1.0, ausschnitt=a, arbeit=arb, turbo=True),
                                       S, 'x', 'o.png [output]', 'm.png')
        self.assertNotIn('44', voll)


    def test_offizielles_turbo_modell(self):
        """Seit 11.10.2026: Turbo-Modell statt LoRA, trainierter 8-Schritt-Plan, nur mit Feld turbo_modell."""
        g = studio.bild_graph(dict(EINSTELLUNG, schritte=8, turbo=True, turbo_modell=True, int8=True), S, 'x')
        self.assertNotIn('24', g)
        self.assertEqual((g['1']['inputs']['unet_name'], g['7']['inputs']['model']), ('qwen_image_turbo.safetensors', ['20', 0]))
        self.assertEqual(g['43']['inputs']['sigmas'],
                         '1, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0')
        r = studio.einstellungen_aus_graph(g)
        self.assertEqual((r['turbo'], r.get('turbo_modell'), r['schritte']), (True, True, 8))
        self.assertNotIn('turbo_modell', studio.einstellungen_aus_graph(studio.bild_graph(dict(EINSTELLUNG, schritte=6, turbo=True), S, 'x')))
        # Verbessern: derselbe Plan, unten abgeschnitten
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        a, arb = studio.ausschnitt_berechnen(studio.maske_rahmen(m)[0], 64, 48, S['verbessern'])
        v = studio.verbessern_graph(dict(EINSTELLUNG, art='verbessern', staerke=0.8, ausschnitt=a, arbeit=arb, turbo=True,
                                         turbo_modell=True), S, 'x', 'o.png [output]', 'm.png')
        self.assertEqual((v['1']['inputs']['unet_name'], '24' in v, v['44']['inputs']['denoise']),
                         ('qwen_image_turbo.safetensors', False, 0.8))
        self.assertEqual(studio.zeit_gruppe(dict(art='bild', turbo=True, turbo_modell=True)), 'bild|format|0|turbom|-')


class VideoAblauf(unittest.TestCase):
    v = S['video']

    def test_laengenraster(self):
        self.assertEqual([studio.bilder_raster(x) for x in (1, 124, 130, 192, 500)], [124, 124, 124, 192, 362])

    def test_aus_text_ohne_turbo(self):
        g = studio.video_graph(VIDEO, self.v, 'Praxis/Video')
        self.assertEqual(g['5']['class_type'], 'MiniMaxH3ImageToVideo')
        self.assertEqual((g['5']['inputs']['width'], g['5']['inputs']['length']), (960, 124))
        self.assertNotIn('first_frame', g['5']['inputs'])
        self.assertNotIn('24', g)
        self.assertEqual(g['17']['inputs']['filename_prefix'], 'Praxis/Video')
        self.assertEqual((g['20']['inputs']['device'], g['21']['inputs']['device']), ('gpu:0', 'gpu:1'))
        self.assertEqual(g['12']['inputs']['noise_seed'], 7)

    def test_turbo_bis_acht_schritte(self):
        g = studio.video_graph(dict(VIDEO, schritte=8), self.v, 'Video')
        self.assertEqual(g['24']['inputs']['lora_name'], 'turbo_fl2v.safetensors')
        self.assertEqual((g['10']['inputs']['model'], g['11']['inputs']['model']), (['24', 0], ['24', 0]))

    def test_aus_bild_mit_zuschnitt(self):
        e = dict(VIDEO, art='video_bild')
        g = studio.video_graph(e, self.v, 'Video', {'start': 'Praxis/Bild_00001_.png [output]', 'ende': 'ende.png'})
        self.assertEqual(g['30']['inputs']['image'], 'Praxis/Bild_00001_.png [output]')
        self.assertEqual({k: g['31']['inputs'][k] for k in ('width', 'height', 'crop')}, {'width': 960, 'height': 544, 'crop': 'center'})
        self.assertEqual((g['5']['inputs']['first_frame'], g['5']['inputs']['last_frame']), (['31', 0], ['33', 0]))
        with self.assertRaises(studio.Fehler):
            studio.video_graph(e, self.v, 'Video', {})

    def test_mit_referenz(self):
        e = dict(VIDEO, art='video_referenz', schritte=4, referenz_genau='max', ton_behalten=True)
        g = studio.video_graph(e, self.v, 'Video', {'bilder': ['a.png [output]', 'b.png'], 'clips': ['c.mp4 [output]']})
        i = g['5']['inputs']
        self.assertEqual(g['5']['class_type'], 'MiniMaxH3ReferenceToVideo')
        self.assertEqual(g['1']['inputs']['unet_name'], 'h3_ref2va.safetensors')
        self.assertEqual((i['ref_images.ref_image_1'], i['ref_videos.ref_video_0'], i['ref_video_audios.ref_video_audio_0']),
                         (['401', 0], ['301', 0], ['301', 1]))
        self.assertEqual((g['300']['inputs']['file'], i['ref_image_size']), ('c.mp4 [output]', 'max'))
        self.assertEqual(g['24']['inputs']['lora_name'], 'turbo_ref2v.safetensors')
        ohne_ton = studio.video_graph(dict(e, ton_behalten=False), self.v, 'Video', {'clips': ['c.mp4']})
        self.assertNotIn('ref_video_audios.ref_video_audio_0', ohne_ton['5']['inputs'])
        with self.assertRaises(studio.Fehler):
            studio.video_graph(e, self.v, 'Video', {})

    def test_zurueck_lesen(self):
        t = studio.einstellungen_aus_graph(studio.video_graph(VIDEO, self.v, 'Video'))
        self.assertEqual((t['art'], t['prompt'], t['variation'], t['schritte'], t['laenge_bilder']),
                         ('video_text', 'Ein Hund läuft über eine Wiese', 7, 20, 124))
        b = studio.einstellungen_aus_graph(studio.video_graph(dict(VIDEO, art='video_bild'), self.v, 'Video', {'start': 's.png'}))
        self.assertEqual((b['art'], b['vorlagen']), ('video_bild', ['s.png']))
        r = studio.einstellungen_aus_graph(studio.video_graph(dict(VIDEO, art='video_referenz'), self.v, 'Video', {'clips': ['c.mp4']}))
        self.assertEqual((r['art'], r['vorlagen']), ('video_referenz', ['c.mp4']))

    def test_realismus(self):
        """Stufe 3o: Realism-LoRA hinter der Turbo-LoRA, Auslösewort vor dem Prompt; ohne Wunsch unverändert."""
        ohne = studio.video_graph(dict(VIDEO, schritte=8), self.v, 'Video')
        mit = studio.video_graph(dict(VIDEO, schritte=8, realismus=True), self.v, 'Video')
        self.assertEqual(mit['26']['inputs'], {'model': ['24', 0], 'lora_name': 'realism.safetensors', 'strength_model': 1.0})
        self.assertEqual((mit['10']['inputs']['model'], mit['11']['inputs']['model']), (['26', 0], ['26', 0]))
        self.assertEqual(mit['5']['inputs']['prompt'], 'r34l1sm, Ein Hund läuft über eine Wiese')
        self.assertNotIn('26', ohne)
        self.assertEqual(ohne['5']['inputs']['prompt'], 'Ein Hund läuft über eine Wiese')
        # ohne Turbo direkt am Modell, auch mit Referenz
        ref = studio.video_graph(dict(VIDEO, art='video_referenz', realismus=True), self.v, 'Video', {'bilder': ['a.png']})
        self.assertEqual((ref['26']['inputs']['model'], ref['5']['inputs']['prompt'][:9]), (['20', 0], 'r34l1sm, '))
        # Weiterführen: dieselbe LoRA im neuen Stück, die festgehaltenen Bilder bleiben am Text
        e = {'modus': 'verlaengern', 'prompt': 'Sie setzt sich', 'breite': 960, 'hoehe': 544, 'bilder': 175, 'schritte': 8,
             'variation': 1, 'realismus': True,
             'quellen': [{'rolle': 'ausgang', 'bilder': 124, 'tondauer': 124 / 24, 'tonrate': 44100, 'tonkanaele': 2}]}
        w = studio.weiter_graph(e, self.v, 'V', {'ausgang': 'a.mp4 [output]'})
        self.assertEqual((w['11']['inputs']['model'], w['11']['inputs']['conditioning'], w['5']['inputs']['prompt']),
                         (['26', 0], ['50', 0], 'r34l1sm, Sie setzt sich'))
        # zurück lesen: Häkchen erkannt, Prompt ohne Auslösewort (sonst käme es bei „Nochmal“ doppelt)
        z = studio.einstellungen_aus_graph(mit, realismus=self.v['realismus'])
        self.assertEqual((z.get('realismus'), z['prompt']), (True, 'Ein Hund läuft über eine Wiese'))
        self.assertNotIn('realismus', studio.einstellungen_aus_graph(ohne, realismus=self.v['realismus']))

    def test_dmad(self):
        """Seit 11.10.2026: DMAD statt Turbo-LoRA, Sampler lcm, Verschiebung 12/2 hinter allen LoRAs; nur aus Text/Bild."""
        ohne = studio.video_graph(dict(VIDEO, schritte=4), self.v, 'Video')
        mit = studio.video_graph(dict(VIDEO, schritte=4, dmad=True), self.v, 'Video')
        self.assertEqual((mit['24']['inputs']['lora_name'], mit['9']['inputs']['sampler_name']), ('dmad_full.safetensors', 'lcm'))
        self.assertEqual(mit['28'], {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['24', 0], 'shift_video': 12.0,
                                                                                    'shift_audio': 2.0}})
        self.assertEqual((mit['10']['inputs']['model'], mit['11']['inputs']['model']), (['28', 0], ['28', 0]))
        self.assertNotIn('28', ohne)
        real = studio.video_graph(dict(VIDEO, schritte=4, dmad=True, realismus=True), self.v, 'Video')
        self.assertEqual((real['26']['inputs']['model'], real['28']['inputs']['model'], real['10']['inputs']['model']),
                         (['24', 0], ['26', 0], ['28', 0]))
        ref = studio.video_graph(dict(VIDEO, art='video_referenz', schritte=4, dmad=True), self.v, 'Video', {'bilder': ['a.png']})
        self.assertNotIn('28', ref)
        self.assertTrue(studio.einstellungen_aus_graph(mit).get('dmad'))
        self.assertNotIn('dmad', studio.einstellungen_aus_graph(ohne))

    def test_video_schnell(self):
        """Seit 17.10.2026: schnellere Aufmerksamkeit (Knoten 29) als letzter Modell-Schritt vor Scheduler und Guider."""
        ohne = studio.video_graph(VIDEO, self.v, 'Video')
        mit = studio.video_graph(dict(VIDEO, schnell=True), self.v, 'Video')
        self.assertEqual(mit['29'], {'class_type': 'ModelAttentionBackend',
                                     'inputs': {'model': ['20', 0], 'attention': 'comfy kitchen attention'}})
        self.assertEqual((mit['10']['inputs']['model'], mit['11']['inputs']['model']), (['29', 0], ['29', 0]))
        self.assertEqual({k: v for k, v in mit.items() if k not in ('10', '11', '29')},
                         {k: v for k, v in ohne.items() if k not in ('10', '11')})
        self.assertNotIn('29', ohne)
        # hinter allen LoRAs und der Verschiebung von DMAD
        dmad = studio.video_graph(dict(VIDEO, schritte=4, dmad=True, realismus=True, schnell=True), self.v, 'Video')
        self.assertEqual((dmad['29']['inputs']['model'], dmad['10']['inputs']['model']), (['28', 0], ['29', 0]))
        ref = studio.video_graph(dict(VIDEO, art='video_referenz', schritte=8, acc8=True, schnell=True), self.v, 'Video',
                                 {'bilder': ['a.png']})
        self.assertEqual((ref['29']['inputs']['model'], ref['11']['inputs']['model']), (['24', 0], ['29', 0]))
        # Weiterführen baut auf video_graph auf und behält den Knoten
        e = {'modus': 'verlaengern', 'prompt': 'Sie setzt sich', 'breite': 960, 'hoehe': 544, 'bilder': 175, 'schritte': 8,
             'variation': 1, 'schnell': True,
             'quellen': [{'rolle': 'ausgang', 'bilder': 124, 'tondauer': 124 / 24, 'tonrate': 44100, 'tonkanaele': 2}]}
        w = studio.weiter_graph(e, self.v, 'V', {'ausgang': 'a.mp4 [output]'})
        self.assertEqual((w['29']['inputs']['model'], w['11']['inputs']['model'], w['11']['inputs']['conditioning']),
                         (['24', 0], ['29', 0], ['50', 0]))
        # Bibliothek: aus dem gespeicherten Ablauf erkannt, ältere Videos ohne
        self.assertTrue(studio.einstellungen_aus_graph(mit).get('schnell'))
        self.assertNotIn('schnell', studio.einstellungen_aus_graph(ohne))

    def test_tauschen(self):
        """Stufe 3q: Character-Swap-LoRA (Knoten 27) hinter der Turbo-LoRA, nur bei „Video mit Referenz“."""
        namen = {'bilder': ['figur.png'], 'clips': ['quelle.mp4']}
        ref = dict(VIDEO, art='video_referenz', schritte=8)
        ohne = studio.video_graph(ref, self.v, 'Video', namen)
        mit = studio.video_graph(dict(ref, tauschen=True), self.v, 'Video', namen)
        self.assertNotIn('27', ohne)
        self.assertEqual(mit['27']['inputs'], {'model': ['24', 0], 'lora_name': 'tausch.safetensors', 'strength_model': 1.0})
        self.assertEqual((mit['10']['inputs']['model'], mit['11']['inputs']['model']), (['27', 0], ['27', 0]))
        self.assertEqual({k: v for k, v in mit.items() if k != '27' and k not in ('10', '11')},
                         {k: v for k, v in ohne.items() if k not in ('10', '11')})
        # mit Realism-LoRA dahinter; ohne Turbo direkt am Modell; aus Text nie
        beide = studio.video_graph(dict(ref, tauschen=True, realismus=True), self.v, 'Video', namen)
        self.assertEqual((beide['26']['inputs']['model'], beide['10']['inputs']['model']), (['27', 0], ['26', 0]))
        self.assertEqual(studio.video_graph(dict(ref, schritte=20, tauschen=True), self.v, 'V', namen)['27']['inputs']['model'],
                         ['20', 0])
        self.assertNotIn('27', studio.video_graph(dict(VIDEO, tauschen=True), self.v, 'Video'))
        self.assertTrue(studio.einstellungen_aus_graph(mit, tauschen=self.v['tauschen']).get('tauschen'))
        self.assertNotIn('tauschen', studio.einstellungen_aus_graph(ohne, tauschen=self.v['tauschen']))
        # 8-Schritt-LoRA (seit 09.10.2026) ersetzt bei Referenz-Videos die Turbo-LoRA, mit Euler; aus Text nie
        acc = studio.video_graph(dict(ref, acc8=True), self.v, 'Video', namen)
        self.assertEqual((acc['24']['inputs']['lora_name'], acc['9']['inputs']['sampler_name']),
                         ('MiniMax-H3-Ref2VA-Acc-8Step_x.safetensors', 'euler'))
        self.assertEqual((ohne['24']['inputs']['lora_name'], ohne['9']['inputs']['sampler_name']), ('turbo_ref2v.safetensors', 'res_multistep'))
        self.assertEqual(studio.video_graph(dict(VIDEO, schritte=8, acc8=True), self.v, 'V')['24']['inputs']['lora_name'],
                         'turbo_fl2v.safetensors')
        self.assertTrue(studio.einstellungen_aus_graph(acc).get('acc8'))
        self.assertNotIn('acc8', studio.einstellungen_aus_graph(ohne))
        # Zeitmodell: Clip-Bilder und Referenzbilder rechnen mit
        a = dict(ref, ref_bilder=124, vorlagen=[{'rolle': 'bild'}, {'rolle': 'clip'}])
        self.assertEqual(studio.video_bilder_wirksam(a), 124 + 124 + 1)


class Verbessern(unittest.TestCase):
    v = S['verbessern']

    def test_maske_pruefen(self):
        m = rle_aus(20, 16, lambda x, y: 3 <= x < 7 and 2 <= y < 5)
        self.assertEqual(studio.maske_pruefen(m), m)
        falsch = [None, 'x', dict(m, breite=10), dict(m, rle=m['rle'][:-1]), dict(m, rle=[-1] + m['rle'][1:]),
                  dict(m, rle=[True] + m['rle'][1:]), dict(m, breite=8, hoehe=40), rle_aus(20, 16, lambda x, y: False)]
        for f in falsch:
            with self.assertRaises(ValueError, msg=str(f)[:60]):
                studio.maske_pruefen(f)

    def test_rahmen_auch_ueber_zeilen(self):
        m = rle_aus(20, 16, lambda x, y: 3 <= x < 7 and 2 <= y < 5)
        self.assertEqual(studio.maske_rahmen(m), ((3, 2, 7, 5), 12))
        # ein Lauf über das Zeilenende hinaus: Rahmen über die ganze Breite
        z = rle_aus(20, 16, lambda x, y: (y == 4 and x >= 18) or (y == 5 and x <= 1))
        self.assertEqual(studio.maske_rahmen(z), ((0, 4, 20, 6), 4))

    def test_maske_als_png(self):
        m = rle_aus(20, 16, lambda x, y: 3 <= x < 7 and 2 <= y < 5)
        breite, hoehe, pixel = png_pixel(studio.maske_png(m))
        self.assertEqual((breite, hoehe), (20, 16))
        self.assertEqual({(i % 20, i // 20) for i, p in enumerate(pixel) if p == 255},
                         {(x, y) for x in range(3, 7) for y in range(2, 5)})
        self.assertEqual(set(pixel), {0, 255})

    def test_ausschnitt_kleine_stelle(self):
        # Hand von 60 × 60 px in einem 1024²-Bild: mindestens 384 px, mittig, auf 1024² vergrößert
        a, arb = studio.ausschnitt_berechnen((425, 535, 485, 595), 1024, 1024, self.v)
        self.assertEqual(a, {'x': 263, 'y': 373, 'breite': 384, 'hoehe': 384})
        self.assertEqual(arb, {'breite': 1024, 'hoehe': 1024})

    def test_ausschnitt_am_rand_und_gross(self):
        a, _ = studio.ausschnitt_berechnen((0, 0, 50, 40), 1328, 1328, self.v)
        self.assertEqual((a['x'], a['y'], a['breite'], a['hoehe']), (0, 0, 384, 384))
        # am rechten Rand: nach innen geschoben, die Markierung bleibt ganz im Ausschnitt
        a, arb = studio.ausschnitt_berechnen((1200, 900, 1300, 1000), 1328, 1328, self.v)
        self.assertEqual(a, {'x': 944, 'y': 758, 'breite': 384, 'hoehe': 384})
        # große Markierung in einem großen Foto: ganzes Bild, höchstens etwa 1328² gerechnet, 32er-Schritte
        a, arb = studio.ausschnitt_berechnen((500, 400, 3500, 2600), 4000, 3000, self.v)
        self.assertEqual(a, {'x': 0, 'y': 0, 'breite': 4000, 'hoehe': 3000})
        self.assertEqual((arb['breite'] % 32, arb['hoehe'] % 32), (0, 0))
        self.assertLessEqual(arb['breite'] * arb['hoehe'], 1328 * 1328 * 1.03)
        # schmale lange Markierung: lange Seite höchstens 2048
        a, arb = studio.ausschnitt_berechnen((0, 500, 3000, 520), 3000, 1000, self.v)
        self.assertLessEqual(max(arb.values()), 2048)

    def test_ablauf(self):
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        a, arb = studio.ausschnitt_berechnen(studio.maske_rahmen(m)[0], 64, 48, self.v)
        e = dict(EINSTELLUNG, art='verbessern', staerke=0.8, ausschnitt=a, arbeit=arb, negativ='')
        g = studio.verbessern_graph(e, S, 'Praxis/Verbessert', 'Praxis/Bild_00001_.png [output]', 'werkstatt_maske_x.png')
        self.assertEqual(g['50']['inputs']['image'], 'Praxis/Bild_00001_.png [output]')
        self.assertEqual(g['51']['inputs'], {'image': 'werkstatt_maske_x.png', 'channel': 'red'})
        self.assertEqual(g['10']['inputs'], {'images': ['65', 0], 'filename_prefix': 'Praxis/Verbessert'})
        k = g['8']['inputs']
        self.assertEqual((k['denoise'], k['latent_image'], k['positive'], k['negative'], k['seed']),
                         (0.8, ['31', 0], ['4', 0], ['4', 1], 424242))
        self.assertEqual(g['4']['inputs']['images.image_1'], ['54', 0])
        self.assertEqual(g['4']['inputs']['resolution'], 0)
        self.assertEqual(g['52']['inputs'], {'x': a['x'], 'y': a['y'], 'width': a['breite'], 'height': a['hoehe']})
        self.assertEqual((g['65']['inputs']['x'], g['65']['inputs']['destination']), (a['x'], ['50', 0]))
        # neu gerechnet wird mehr als Rand und Übergang (in Arbeitsgröße)
        self.assertGreaterEqual(g['59']['inputs']['expand'], (6 + 6) * arb['breite'] / a['breite'])
        klassen = {n['class_type'] for n in g.values()}
        self.assertNotIn('ImageCrop', klassen)  # in ComfyUI 0.37 als veraltet markiert

    def test_ablauf_zurueck_lesen(self):
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        a, arb = studio.ausschnitt_berechnen(studio.maske_rahmen(m)[0], 64, 48, self.v)
        e = dict(EINSTELLUNG, art='verbessern', staerke=1.0, ausschnitt=a, arbeit=arb)
        g = studio.einstellungen_aus_graph(studio.verbessern_graph(e, S, 'V', 'o.png [output]', 'm.png'))
        self.assertEqual((g['art'], g['prompt'], g['negativ'], g['breite'], g['vorlagen'], g['variation']),
                         ('verbessern', 'Ein ruhiger Raum', 'unscharf', None, ['o.png [output]'], 424242))

    def test_ablauf_mit_vorlage_fuer_die_stelle(self):
        """Stufe 3n: Bild 2 geht auf etwa 1 MP verkleinert dazu; der Ausschnitt bleibt Bild 1 in Arbeitsgröße."""
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        a, arb = studio.ausschnitt_berechnen(studio.maske_rahmen(m)[0], 64, 48, self.v)
        e = dict(EINSTELLUNG, art='verbessern', staerke=1.0, ausschnitt=a, arbeit=arb, turbo=True, schnell=True)
        ohne = studio.verbessern_graph(e, S, 'V', 'o.png [output]', 'm.png')
        mit = studio.verbessern_graph(e, S, 'V', 'o.png [output]', 'm.png', ['Praxis/Logo.png [output]', 'zweite.png'])
        self.assertEqual(mit['110']['inputs'], {'image': 'Praxis/Logo.png [output]'})
        self.assertEqual(mit['111'], {'class_type': 'ImageScaleToTotalPixels', 'inputs': {
            'image': ['110', 0], 'upscale_method': 'lanczos', 'megapixels': 1.0, 'resolution_steps': 32}})
        t = mit['4']['inputs']
        self.assertEqual((t['images.image_1'], t['images.image_2'], t['resolution']), (['54', 0], ['111', 0], 0))
        self.assertNotIn('images.image_3', t)  # höchstens `vorlage.max` (1)
        self.assertNotIn('112', mit)
        # sonst derselbe Ablauf: ältere Aufträge ohne Vorlage bleiben bei „Nochmal“ gleich
        for k in ('110', '111'):
            mit.pop(k)
        del mit['4']['inputs']['images.image_2']
        self.assertEqual(mit, ohne)
        self.assertNotIn('110', ohne)
        # Begleitdaten fremder Abläufe: das Original bleibt die einzige bekannte Vorlage
        g = studio.einstellungen_aus_graph(studio.verbessern_graph(e, S, 'V', 'o.png [output]', 'm.png', ['l.png [output]']))
        self.assertEqual((g['art'], g['vorlagen']), ('verbessern', ['o.png [output]']))


class Metadaten(unittest.TestCase):
    def test_png(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.png')
            png_bauen(p, {'prompt': json.dumps({'1': {'class_type': 'X', 'inputs': {}}}), 'werkstatt': '{"a": 1}'}, 7, 5)
            t = studio.png_texte(p)
            self.assertEqual(json.loads(t['werkstatt']), {'a': 1})
            self.assertIn('prompt', t)
            self.assertEqual(studio.png_masse(p), (7, 5))
            with open(os.path.join(d, 'kein.png'), 'wb') as f:
                f.write(b'kein Bild')
            self.assertEqual(studio.png_texte(os.path.join(d, 'kein.png')), {})
            self.assertEqual(studio.png_masse(os.path.join(d, 'kein.png')), (None, None))

    def test_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'v.mp4')
            mp4_bauen(p, {'prompt': '{"x": 1}', 'workflow': '{"y": 2}'})
            self.assertEqual(studio.mp4_texte(p), {'prompt': '{"x": 1}', 'workflow': '{"y": 2}'})
            with open(os.path.join(d, 'leer.mp4'), 'wb') as f:
                f.write(_atom(b'ftyp', b'isom'))
            self.assertEqual(studio.mp4_texte(os.path.join(d, 'leer.mp4')), {})


class Platz(unittest.TestCase):
    antwort = {'karten': [{'index': 0, 'kurz': 'RTX 3090', 'frei': 4000, 'belegt_von': ['Ornith 1.5 Q5', 'ComfyUI + 2Wild Studio']},
                          {'index': 1, 'kurz': 'RTX 3080', 'frei': 15000, 'belegt_von': []}],
               'verbraucher': [{'schluessel': 'bild-video', 'mib_je_karte': {'0': 14000, '1': 800}}]}

    def test_comfyui_eigenes_zaehlt_mit(self):
        fehlend, zusatz = studio.platz_fehlt(self.antwort, {0: 20000, 1: 16000})
        self.assertEqual(fehlend, {0: 2000, 1: 200})
        self.assertEqual(zusatz, {0: 6000, 1: 15200})
        text = studio.platz_text(self.antwort, fehlend, 'ComfyUI + 2Wild Studio')
        self.assertIn('RTX 3090 fehlen 2,0 GiB (belegt von Ornith 1.5 Q5)', text)

    def test_schon_geladen(self):
        a = dict(self.antwort, verbraucher=[{'schluessel': 'bild-video', 'mib_je_karte': {'0': 19800, '1': 15900}}])
        self.assertEqual(studio.platz_fehlt(a, {0: 20000, 1: 16000}), ({}, {}))

    def test_ohne_verbraucher_vorsichtig(self):
        fehlend, _ = studio.platz_fehlt({'karten': self.antwort['karten']}, {0: 20000, 1: 16000})
        self.assertEqual(fehlend, {0: 16000, 1: 1000})


class KartenJeAuftrag(unittest.TestCase):
    """Zwei RTX 3090 (seit 14.10.2026): Das Studio wählt die Karten je Auftrag nach dem Stand der Zentrale."""
    BILD = {'eine': 18432, 'haupt': 16384, 'neben': 2048}
    VIDEO = {'haupt': 20480, 'neben': 7168}

    def antwort(self, frei0, frei1, comfy=None):
        a = {'karten': [{'index': 0, 'kurz': 'RTX 3090 FE', 'frei': frei0, 'belegt_von': []},
                        {'index': 1, 'kurz': 'RTX 3090 Suprim', 'frei': frei1, 'belegt_von': []}], 'verbraucher': []}
        if comfy:
            a['verbraucher'] = [{'schluessel': 'bild-video', 'mib_je_karte': {str(i): m for i, m in comfy.items()}}]
        return a

    def test_verteilungen(self):
        v = studio.verteilungen(self.BILD, [0, 1])
        self.assertEqual([(x['rang'], x.get('haupt'), x['mib']) for x in v],
                         [(0, None, {0: 18432}), (0, None, {1: 18432}), (1, 0, {0: 16384, 1: 2048}),
                          (1, 1, {1: 16384, 0: 2048})])
        self.assertEqual(v[1]['geraete'], dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:1'))
        self.assertEqual((v[3]['geraete']['modell'], v[3]['geraete']['clip'], v[3]['geraete']['vae_audio']),
                         ('gpu:1', 'gpu:0', 'gpu:0'))
        self.assertEqual(studio.verteilungen({'fest': 4096}, [0, 1]), [{'rang': 0, 'mib': {0: 4096}, 'geraete': None}])
        self.assertEqual(studio.verteilungen(self.VIDEO, [0]), [])  # Videos brauchen zwei Karten
        mit_sam3 = studio.verteilungen(dict(self.BILD, standard_zusatz=2048), [0, 1])
        self.assertEqual([x['mib'] for x in mit_sam3[:2]], [{0: 18432}, {1: 18432, 0: 2048}])

    def test_bild_auf_einer_karte_die_engste(self):
        v, fehlend, zusatz = studio.karten_waehlen(self.antwort(23800, 22900), self.BILD)
        self.assertEqual((v['mib'], fehlend, zusatz), ({1: 18432}, {}, {1: 18432}))
        self.assertEqual(v['geraete']['modell'], 'gpu:1')

    def test_grosses_bild_nicht_bis_zum_rand_der_monitorkarte(self):
        a = self.antwort(23808, 22946)
        a['karten'][1]['monitor'] = True
        a['monitor_puffer_mib'] = 2048
        gross = {'eine': 22016, 'haupt': 18432, 'neben': 6144}
        self.assertEqual(studio.karten_waehlen(a, gross)[0]['mib'], {0: 22016})  # Suprim behielte nur 0,9 GiB
        self.assertEqual(studio.karten_waehlen(a, self.BILD)[0]['mib'], {1: 18432})  # 4,4 GiB bleiben: in Ordnung

    def test_video_modell_nicht_auf_die_monitorkarte(self):
        # Gemessen 14.10.2026: ComfyUI füllt die Karte des Videomodells fast ganz (23,7 von 24 GiB).
        a = self.antwort(23808, 22946 - 7900, comfy={1: 7900})
        a['karten'][1]['monitor'] = True
        a['monitor_puffer_mib'] = 2048
        v, fehlend, _ = studio.karten_waehlen(a, self.VIDEO)
        self.assertEqual((v['haupt'], v['geraete']['modell'], v['geraete']['clip'], fehlend), (0, 'gpu:0', 'gpu:1', {}))
        # Ohne Monitorangabe bleibt das Modell, wo ComfyUI schon Speicher hält.
        a['karten'][1]['monitor'] = False
        self.assertEqual(studio.karten_waehlen(a, self.VIDEO)[0]['haupt'], 1)

    def test_bild_neben_einem_sprachmodell_auf_der_anderen_karte(self):
        # NInfer belegt die FE fast ganz: das Bild geht ganz auf die Suprim.
        v, fehlend, _ = studio.karten_waehlen(self.antwort(1500, 22900), self.BILD)
        self.assertEqual((v['mib'], fehlend), ({1: 18432}, {}))

    def test_bild_bleibt_wo_comfyui_seine_modelle_haelt(self):
        a = self.antwort(23800 - 18000, 22900, comfy={0: 18000})
        v, fehlend, zusatz = studio.karten_waehlen(a, self.BILD)
        self.assertEqual((v['mib'], fehlend, zusatz), ({0: 18432}, {}, {}))

    def test_bild_geteilt_wenn_keine_karte_allein_reicht(self):
        v, fehlend, zusatz = studio.karten_waehlen(self.antwort(17000, 3000), self.BILD)
        self.assertEqual((v['rang'], v['mib'], fehlend), (1, {0: 16384, 1: 2048}, {}))
        self.assertEqual((v['geraete']['modell'], v['geraete']['clip'], v['geraete']['vae']), ('gpu:0', 'gpu:1', 'gpu:1'))

    def test_video_geteilt_und_was_fehlt(self):
        v, fehlend, _ = studio.karten_waehlen(self.antwort(23800, 22900), self.VIDEO)
        self.assertEqual((v['mib'], fehlend, v['geraete']['modell'], v['geraete']['vae_video']),
                         ({0: 20480, 1: 7168}, {}, 'gpu:0', 'gpu:1'))
        # Die FE ist von NInfer belegt: Video passt nicht, gemeldet wird die Verteilung, der am wenigsten fehlt.
        v, fehlend, _ = studio.karten_waehlen(self.antwort(1500, 22900), self.VIDEO)
        self.assertEqual((v['mib'], fehlend), ({1: 20480, 0: 7168}, {0: 5668}))

    def test_ohne_karten_keine_verteilung(self):
        self.assertEqual(studio.karten_waehlen({'karten': []}, self.BILD), (None, {}, {}))

    def test_mit_geraeten_setzt_bild_video_und_ausformulieren(self):
        g = dict(dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:0'), modell='gpu:1')
        s = studio.mit_geraeten(S, g)
        self.assertEqual(s['geraete'], {'modell': 'gpu:1', 'clip': 'gpu:0', 'vae': 'gpu:0'})
        self.assertEqual(s['video']['geraete'], {'modell': 'gpu:1', 'clip': 'gpu:0', 'vae_video': 'gpu:0', 'vae_audio': 'gpu:0'})
        self.assertEqual(s['ausformulieren']['geraet'], 'gpu:1')
        self.assertEqual(S['geraete']['modell'], 'gpu:0')  # die Einstellung selbst bleibt unverändert
        self.assertIs(studio.mit_geraeten(S, None), S)
        graph = studio.bild_graph(dict(EINSTELLUNG), s, 'P/Bild')
        self.assertEqual((graph['20']['inputs']['device'], graph['21']['inputs']['device'], graph['22']['inputs']['device']),
                         ('gpu:1', 'gpu:0', 'gpu:0'))
        graph = studio.video_graph(dict(VIDEO), s['video'], 'P/Video')
        self.assertEqual((graph['20']['inputs']['device'], graph['23']['inputs']['device']), ('gpu:1', 'gpu:0'))


class PlatzImStudio(unittest.TestCase):
    """_platz: wählt die Karten, meldet nur den neuen Bedarf an und gibt die Geräte an _rechnen weiter."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI', 'studio_ordner': self.tmp.name,
                             'bedarf_je_karte_mib': 20000}]}
        self.zentrale = mock.MagicMock()
        with mock.patch('threading.Thread'):
            self.s = studio.Studio({'studio': dict(S, ordner=os.path.join(self.tmp.name, 'Studio'),
                                                   bedarf_mib={'eine': 18432, 'haupt': 16384, 'neben': 2048})},
                                   zc, self.tmp.name, mock.MagicMock(), self.zentrale)
        self.s._schritt = mock.MagicMock()
        self.a = {'id': 'x1', 'art': 'bild', 'breite': 1328, 'hoehe': 1328}
        self.karten = [{'index': 0, 'kurz': 'RTX 3090 FE', 'frei': 1500, 'belegt_von': ['NInfer']},
                       {'index': 1, 'kurz': 'RTX 3090 Suprim', 'frei': 22900, 'belegt_von': []}]

    def test_bild_neben_ninfer_auf_der_suprim(self):
        self.zentrale.stand.return_value = (200, {'karten': self.karten, 'verbraucher': [], 'gruende': []})
        self.zentrale.anmelden.return_value = (200, {'anmeldung': {'id': 'a1'}})
        anmeldung, grund, geraete = self.s._platz(self.a)
        self.assertEqual((anmeldung, grund), ({'id': 'a1'}, None))
        self.assertEqual(geraete, dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:1'))
        self.zentrale.anmelden.assert_called_once_with({1: 18432}, 'Bild (Studio)', dauer_s=120,
                                                       schluessel='bild-video')

    def test_meldet_auch_ohne_zusatzbedarf_an(self):
        # Ohne GPU-Sperre (16.10.2026): Hält ComfyUI schon alles, meldet das Studio trotzdem an (leerer Bedarf),
        # damit die Zentrale weiß, dass der laufende ComfyUI-Auftrag gedeckt ist und andere daneben rechnen dürfen.
        comfy = {'schluessel': 'bild-video', 'name': 'ComfyUI', 'mib_je_karte': {'1': 18432}}
        self.karten[1]['frei'] = 4000
        self.zentrale.stand.return_value = (200, {'karten': self.karten, 'verbraucher': [comfy], 'gruende': []})
        self.zentrale.anmelden.return_value = (200, {'anmeldung': {'id': 'a2'}})
        anmeldung, grund, geraete = self.s._platz(self.a)
        self.assertEqual((anmeldung, grund), ({'id': 'a2'}, None))
        self.zentrale.anmelden.assert_called_once_with({}, 'Bild (Studio)', dauer_s=120, schluessel='bild-video')

    def test_video_wartet_mit_verstaendlichem_grund(self):
        self.a = {'id': 'x2', 'art': 'video_text'}
        self.karten[0]['belegt_von'] = ['NInfer']
        self.zentrale.stand.return_value = (200, {'karten': self.karten, 'verbraucher': [], 'gruende': []})
        anmeldung, grund, geraete = self.s._platz(self.a)
        self.assertEqual((anmeldung, geraete), (None, None))
        self.assertIn('auf der RTX 3090 FE fehlen 5,5 GiB (belegt von NInfer)', grund)
        self.zentrale.anmelden.assert_not_called()

    def test_nur_eine_karte_gemeldet(self):
        self.a = {'id': 'x3', 'art': 'video_text'}
        self.zentrale.stand.return_value = (200, {'karten': self.karten[1:], 'verbraucher': [], 'gruende': []})
        self.assertEqual(self.s._platz(self.a)[1], 'Dieser Auftrag braucht zwei Grafikkarten; die Modellzentrale meldet nur eine.')

    def test_stelle_per_wort_braucht_platz_fuer_sam3_auf_der_standardkarte(self):
        a = {'id': 'x4', 'art': 'verbessern', 'stelle': 'hand', 'maske': None, 'breite': 1024, 'hoehe': 1024}
        self.assertEqual(self.s._bedarf(a)['standard_zusatz'], 2048)
        self.assertNotIn('standard_zusatz', self.s._bedarf(dict(a, maske=[[0, 0, 1, 1]])))


class Bibliothek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = os.path.join(self.tmp.name, 'Studio')
        os.makedirs(os.path.join(self.wurzel, 'Praxis'))
        os.makedirs(os.path.join(self.wurzel, 'gencenter'))
        cfg = {'studio': dict(S, ordner=self.wurzel)}
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI + 2Wild Studio',
                             'studio_ordner': os.path.join(self.tmp.name, '2wild'), 'bedarf_je_karte_mib': 20000}]}
        with mock.patch('threading.Thread'):
            self.s = studio.Studio(cfg, zc, self.tmp.name, lambda t: None, mock.MagicMock())
        alt = time.time() - 60
        eigen = {'format': studio.FORMAT, 'art': 'bild', 'prompt': 'Eigenes Bild', 'variation': 7, 'schritte': 40}
        self.bild = os.path.join(self.wurzel, 'Praxis', 'Bild_00001_.png')
        png_bauen(self.bild, {'werkstatt': json.dumps(eigen)})
        self.alt = os.path.join(self.wurzel, 'gencenter', 'IMG_00001_.png')
        png_bauen(self.alt, {'prompt': json.dumps(studio.bild_graph(EINSTELLUNG, S, 'gencenter/IMG'))})
        for p in (self.bild, self.alt):
            os.utime(p, (alt, alt))

    def tearDown(self):
        self.tmp.cleanup()

    def test_liest_und_legt_begleitdaten_an(self):
        b = self.s.bibliothek(neu=True)
        infos = {e['pfad']: e for e in b['eintraege']}
        self.assertEqual(infos['Praxis/Bild_00001_.png']['info']['prompt'], 'Eigenes Bild')
        self.assertEqual(infos['Praxis/Bild_00001_.png']['info']['herkunft'], 'studio')
        alt = infos['gencenter/IMG_00001_.png']
        self.assertEqual((alt['projekt'], alt['info']['herkunft'], alt['info']['prompt'], alt['info']['variation']),
                         ('gencenter', 'metadaten', 'Ein ruhiger Raum', 424242))
        self.assertTrue(os.path.isfile(self.alt + '.json'))
        self.assertEqual({p['name']: p['aus_2wild'] for p in b['projekte']}, {'Praxis': False, 'gencenter': True})

    def test_frische_datei_wird_noch_nicht_beschrieben(self):
        frisch = os.path.join(self.wurzel, 'Praxis', 'Bild_00002_.png')
        png_bauen(frisch, {})
        eintrag = next(e for e in self.s.bibliothek(neu=True)['eintraege'] if e['name'] == 'Bild_00002_.png')
        self.assertIsNone(eintrag['info'])
        self.assertFalse(os.path.exists(frisch + '.json'))

    def test_verschieben_mit_begleitdatei(self):
        self.s.bibliothek(neu=True)
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'IMG_00001_.png'), {})
        code, a = self.s.verschieben(['gencenter/IMG_00001_.png'], 'Praxis')
        self.assertEqual(code, 200)
        self.assertEqual(a['verschoben'], ['Praxis/IMG_00001_ (2).png'])
        neu = os.path.join(self.wurzel, 'Praxis', 'IMG_00001_ (2).png')
        self.assertTrue(os.path.isfile(neu) and os.path.isfile(neu + '.json'))
        with open(neu + '.json', encoding='utf-8') as f:
            self.assertEqual(json.load(f)['datei'], 'IMG_00001_ (2).png')
        self.assertFalse(os.path.exists(self.alt))
        self.assertEqual(self.s.verschieben(['gencenter/fehlt.png', '../x.png'], 'Praxis')[1]['fehler'][0][:3], 'gen')
        self.assertEqual(self.s.verschieben(['Praxis/Bild_00001_.png'], 'Gibtsnicht')[0], 400)

    def test_papierkorb_mit_begleitdatei(self):
        self.s.bibliothek(neu=True)
        with mock.patch.object(studio.winapi, 'in_papierkorb', return_value=True) as pk:
            code, a = self.s.papierkorb(['gencenter/IMG_00001_.png'])
        self.assertEqual((code, a['anzahl']), (200, 1))
        self.assertEqual(pk.call_args[0][0], [self.alt, self.alt + '.json'])

    def test_projekt_neu(self):
        self.assertEqual(self.s.projekt_neu('Hunde Website'), (200, {'name': 'Hunde Website'}))
        self.assertEqual(self.s.projekt_neu('Hunde Website')[0], 409)
        self.assertEqual(self.s.projekt_neu('gencenter')[0], 400)

    def test_video_pruefen(self):
        bereit = {'laeuft': True, 'ordner_ok': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit):
            code, a = self.s.erzeugen({'art': 'video_bild', 'prompt': 'x', 'breite': 960, 'hoehe': 544})
            self.assertEqual(code, 400)
            self.assertIn('Startbild', a['fehler'])
            code, a = self.s.erzeugen({'art': 'video_bild', 'prompt': 'x', 'breite': 970, 'hoehe': 544, 'bilder': 190,
                                       'schritte': 8, 'vorlagen': [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'start'}]})
            self.assertEqual(code, 200)
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j['breite'], j['bilder'], j['turbo'], j['qualitaet'], j['negativ'], j['vorlagen'][0]['rolle']),
                             (960, 192, True, 'Schnell beste', '', 'start'))
            code, a = self.s.erzeugen({'art': 'video_referenz', 'prompt': 'x', 'breite': 960, 'hoehe': 544,
                                       'vorlagen': [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'clip'}]})
            self.assertEqual(code, 400)  # ein Bild ist kein Clip
            code, a = self.s.erzeugen({'art': 'video_text', 'prompt': 'x', 'breite': 960, 'hoehe': 544})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j['schritte'], j['bilder'], j['turbo'], j['vorlagen']), (20, 124, False, []))
            self.assertEqual(self.s._erwartet(j), 30 + 12.4 * 20)  # das Bezugsvideo: Grundzeit + Schritte × 12,4 s

    def test_dmad_pruefen(self):
        bereit = {'laeuft': True, 'ordner_ok': True}
        video = {'art': 'video_text', 'prompt': 'Eine Frau spricht', 'breite': 960, 'hoehe': 544, 'schritte': 4, 'dmad': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit):
            self.assertNotIn('dmad', self.s._finden(self.s.erzeugen(video)[1]['neu'][0]))  # LoRA fehlt: wie bisher
            with mock.patch.object(self.s, '_modell_da', return_value=True):
                self.assertEqual((self.s.einstellungen()['dmad_verfuegbar'], self.s.einstellungen()['dmad_schritte']), (True, 4))
                j = self.s._finden(self.s.erzeugen(video)[1]['neu'][0])
                self.assertEqual((j['dmad'], self.s._meta(j)['dmad']), (True, True))
                self.assertNotIn('dmad', self.s._finden(self.s.erzeugen(dict(video, schritte=8))[1]['neu'][0]))
                self.assertNotIn('dmad', self.s._finden(self.s.erzeugen(dict(video, dmad=None))[1]['neu'][0]))

    def test_video_schnell_pruefen(self):
        """Seit 17.10.2026: neue MiniMax-Videos mit schnellerer Aufmerksamkeit (Feld schnell), eigene Zeitschätzung."""
        bereit = {'laeuft': True, 'ordner_ok': True}
        video = {'art': 'video_text', 'prompt': 'Eine Frau spricht', 'breite': 960, 'hoehe': 544, 'schritte': 20}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit):
            self.assertTrue(self.s.einstellungen()['video_schnell_verfuegbar'])
            j = self.s._finden(self.s.erzeugen(dict(video, schnell=True))[1]['neu'][0])
            self.assertEqual((j['schnell'], self.s._meta(j)['schnell']), (True, True))
            # ohne eigene schnelle Läufe: Sekunden je Schritt × zeitfaktor (0,6) auf die übrigen
            self.assertEqual(self.s._erwartet(j), round(30 + 12.4 * 0.6 * 20))
            k = self.s._finden(self.s.erzeugen(video)[1]['neu'][0])  # „Nochmal“ älterer Videos: wie bisher
            self.assertNotIn('schnell', k)
            self.assertNotIn('schnell', self.s._meta(k))
            self.assertEqual(self.s._erwartet(k), 30 + 12.4 * 20)
            # eigene fertige Läufe zählen getrennt
            j.update(zustand='fertig', rechenzeit_s=30 + 7.0 * 20)
            k.update(zustand='fertig', rechenzeit_s=30 + 13.0 * 20)
            self.assertEqual((self.s._video_je_schritt(True), self.s._video_je_schritt()), (7.0, 13.0))
            self.assertEqual(self.s.einstellungen()['video']['zeit']['je_schritt_schnell_s'], 7.0)
            with mock.patch.dict(self.s.s['video']['schnelle_aufmerksamkeit'], {'aktiv': False}):
                self.assertFalse(self.s.einstellungen()['video_schnell_verfuegbar'])
                self.assertNotIn('schnell', self.s._finden(self.s.erzeugen(dict(video, schnell=True))[1]['neu'][0]))

    def test_turbo_modell_pruefen(self):
        """Seit 11.10.2026: neue Turbo-Aufträge mit Feld turbo_modell rechnen 8 Schritte mit dem Turbo-Modell."""
        bereit = {'laeuft': True, 'ordner_ok': True}
        bild = {'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'turbo': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit),                 mock.patch.object(self.s, '_modell_da', return_value=True),                 mock.patch.object(self.s, 'turbo_verfuegbar', return_value=True):
            self.assertTrue(self.s.einstellungen()['turbo_modell_verfuegbar'])
            self.assertEqual(self.s.einstellungen()['turbo_modell_schritte'], 8)
            j = self.s._finden(self.s.erzeugen(dict(bild, turbo_modell=True))[1]['neu'][0])
            m = self.s._meta(j)
            self.assertEqual((j['turbo_modell'], j['schritte'], j['qualitaet'], m['turbo_modell'], m['modell_datei']),
                             (True, 8, 'Turbo', True, 'qwen_image_turbo.safetensors'))
            k = self.s._finden(self.s.erzeugen(bild)[1]['neu'][0])  # ältere Aufträge („Nochmal“): LoRA, 6 Schritte
            self.assertEqual((k.get('turbo_modell'), k['schritte'], k['qualitaet']), (None, 6, 'Turbo'))
            self.assertNotIn('turbo_modell', self.s._finden(self.s.erzeugen(dict(bild, turbo=None, turbo_modell=True,
                                                                                      schritte=20))[1]['neu'][0]))

    def test_realismus_pruefen(self):
        bereit = {'laeuft': True, 'ordner_ok': True}
        video = {'art': 'video_text', 'prompt': 'Eine Frau spricht', 'breite': 960, 'hoehe': 544, 'schritte': 8}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit):
            code, a = self.s.erzeugen(dict(video, realismus=True))
            self.assertEqual(code, 400)  # LoRA fehlt im Testordner: verständlich ablehnen
            self.assertIn('Realism-LoRA', a['fehler'])
            self.assertFalse(self.s.einstellungen()['realismus_verfuegbar'])
            with mock.patch.object(self.s, '_modell_da', return_value=True):
                self.assertTrue(self.s.einstellungen()['realismus_verfuegbar'])
                j = self.s._finden(self.s.erzeugen(dict(video, realismus=True))[1]['neu'][0])
                self.assertEqual((j['realismus'], self.s._meta(j)['realismus'], j['prompt']), (True, True, 'Eine Frau spricht'))
                k = self.s._finden(self.s.erzeugen(dict(video, realismus='ja'))[1]['neu'][0])
                self.assertNotIn('realismus', k)  # nur ausdrücklich true
                self.assertNotIn('realismus', self.s._meta(k))
                # Bilder kennen das Häkchen nicht
                b = self.s._finden(self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328,
                                                    'realismus': True})[1]['neu'][0])
                self.assertNotIn('realismus', b)

    def test_erzeugen_prueft_und_braucht_comfyui(self):
        code, a = self.s.erzeugen({'art': 'bild', 'prompt': '', 'breite': 1328, 'hoehe': 1328})
        self.assertEqual(code, 400)
        code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 100, 'hoehe': 1328})
        self.assertEqual(code, 400)
        code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': [{'art': 'bibliothek', 'pfad': '../x.png'}]})
        self.assertEqual(code, 400)
        code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'projekt': 'Praxis'})
        self.assertEqual((code, a['fehler']), (409, studio.COMFY_AUS))
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1330, 'hoehe': 1328, 'anzahl': 3})
            self.assertEqual((code, len(a['neu'])), (200, 3))
            auftrag = self.s._finden(a['neu'][0])
            self.assertEqual((auftrag['breite'], auftrag['schritte'], auftrag['qualitaet']), (1328, 40, 'Max'))
            self.assertEqual(len({self.s._finden(i)['variation'] for i in a['neu']}), 3)
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'variation': 5, 'anzahl': 3})
            self.assertEqual((len(a['neu']), self.s._finden(a['neu'][0])['variation']), (1, 5))

    def test_comfy_zustand_liest_startoptionen_einmal_je_prozess(self):
        # /system_stats antwortet beim Rendern eines Videos erst nach ~4 s; gefragt wird es nur für einen neuen Prozess.
        antworten = {'/queue': {'queue_running': [['x', 'p1']], 'queue_pending': []},
                     '/system_stats': {'system': {'argv': ['main.py', '--output-directory', self.wurzel]}}}
        gefragt = []

        def anfrage(pfad, daten=None, timeout=10, inst=None):
            gefragt.append(pfad)
            return antworten[pfad]
        ports = [('127.0.0.1', 1, 111)]
        with mock.patch.object(studio.winapi, 'lauschende_ports', side_effect=lambda: list(ports)), \
                mock.patch.object(self.s, '_comfy_anfrage', side_effect=anfrage):
            z = self.s.comfy_zustand(frisch=True)
            self.assertEqual((z['laeuft'], z['ordner_ok'], z['laufend']), (True, True, 1))
            self.assertTrue(self.s.comfy_zustand(frisch=True)['laeuft'])
            self.assertEqual(gefragt.count('/system_stats'), 1)
            ports[0] = ('127.0.0.1', 1, 222)  # ComfyUI neu gestartet
            self.assertTrue(self.s.comfy_zustand(frisch=True)['ordner_ok'])
            self.assertEqual(gefragt.count('/system_stats'), 2)
            ports.clear()
            self.assertFalse(self.s.comfy_zustand(frisch=True)['laeuft'])

    def test_freistellen_und_hochskalieren_pruefen(self):
        vorlage = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'original'}]
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'freistellen', 'prompt': '', 'vorlagen': vorlage})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['motiv'], j['breite'], j['negativ']), (200, '', None, ''))
            self.assertIn('keep only the main subject', j['prompt'])
            self.assertEqual(self.s._meta(j)['motiv'], '')
            self.assertEqual(self.s._bedarf(j), {'eine': 20000})  # ohne eigenen Wert: der der Zentrale
            f = 1024 ** 2 / 1328 ** 2  # die Vorlage wird mitgerechnet: mehr als linear
            self.assertEqual(self.s._erwartet(j), round(1.4 * 40 * f * (0.94 + 0.33 * f)))
            code, a = self.s.erzeugen({'art': 'freistellen', 'prompt': 'die Frau', 'vorlagen': vorlage})
            self.assertIn('keep only die Frau', self.s._finden(a['neu'][0])['prompt'])
            self.assertEqual(self.s.erzeugen({'art': 'freistellen', 'prompt': 'x', 'vorlagen': []})[0], 400)
            # Hochskalieren: wie Vorlage 1, aber größer; nur angebotene Stufen
            v = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorlage'}]
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v, 'aufloesung': 2048})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['aufloesung'], j['breite']), (200, 2048, None))
            self.assertEqual((self.s._meta(j)['aufloesung'], self.s._pixel(j)), (2048, 2048 ** 2))
            self.assertEqual(self.s._bedarf(j), {'eine': 22016, 'haupt': 18432, 'neben': 6144})  # über 2 MP: großer Plan
            f = 2048 ** 2 / 1328 ** 2
            self.assertEqual(self.s._erwartet(j), round(1.4 * 40 * f * (0.94 + 0.33 * f)))
            self.assertEqual(self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v, 'aufloesung': 1500})[0], 400)
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v})
            self.assertEqual(self.s._finden(a['neu'][0])['aufloesung'], 1024)

    def test_details_pruefen(self):
        v = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorlage'}]
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v, 'details': True})
            self.assertEqual(code, 400)  # LoRA fehlt im (leeren) Testordner
            self.assertIn('Detail-LoRA', a['fehler'])
            self.assertFalse(self.s.einstellungen()['details_verfuegbar'])
            with mock.patch.object(self.s, 'details_verfuegbar', return_value=True):
                code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v, 'details': True})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['details']), (200, True))
                self.assertTrue(self.s._meta(j)['details'])
                # nur beim Bearbeiten
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'details': True})
                self.assertNotIn('details', self.s._finden(a['neu'][0]))
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v})
            self.assertNotIn('details', self.s._meta(self.s._finden(a['neu'][0])))

    def test_durchsichtig_und_schnell_pruefen(self):
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'Eine Tasse', 'breite': 1328, 'hoehe': 1328,
                                       'durchsichtig': True, 'schnell': True})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['durchsichtig'], j['schnell'], j['prompt']), (200, True, True, 'Eine Tasse'))
            m = self.s._meta(j)
            self.assertEqual((m['durchsichtig'], m['schnell'], m['prompt']), (True, True, 'Eine Tasse'))
            e = self.s.einstellungen()
            self.assertEqual((e['schnell_verfuegbar'], e['durchsichtig_verfuegbar'], e['max_seite']), (True, True, 4096))
            # durchsichtig nur für neue Bilder; Videos haben seit 17.10.2026 einen eigenen Schalter (video.schnelle_aufmerksamkeit)
            v = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorlage'}]
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'vorlagen': v, 'durchsichtig': True, 'schnell': True})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j.get('durchsichtig'), j.get('schnell')), (200, None, True))
            with mock.patch.dict(self.s.s['video']['schnelle_aufmerksamkeit'], {'aktiv': False}):
                code, a = self.s.erzeugen({'art': 'video_text', 'prompt': 'x', 'breite': 960, 'hoehe': 544, 'schnell': True})
                self.assertNotIn('schnell', self.s._finden(a['neu'][0]))
            # ohne Wunsch (etwa „Nochmal“ älterer Bilder) bleibt alles wie bisher
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j.get('schnell'), j.get('durchsichtig')), (None, None))
            self.assertNotIn('schnell', self.s._meta(j))
            # abgeschaltet: auch auf Wunsch nicht
            with mock.patch.dict(self.s.s['schnelle_aufmerksamkeit'], {'aktiv': False}):
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'schnell': True})
                self.assertNotIn('schnell', self.s._finden(a['neu'][0]))
                self.assertFalse(self.s.einstellungen()['schnell_verfuegbar'])

    def test_turbo_pruefen(self):
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'turbo': True})
            self.assertEqual(code, 400)  # LoRA fehlt im (leeren) Testordner
            self.assertIn('Turbo', a['fehler'])
            with mock.patch.object(self.s, 'turbo_verfuegbar', return_value=True):
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'turbo': True, 'schritte': 40})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['schritte'], j['qualitaet'], j['turbo']), (200, 6, 'Turbo', True))
                self.assertTrue(self.s._meta(j)['turbo'])
                self.assertEqual(self.s._erwartet(j), round(1.4 * 6 * 1.4))
                code, a = self.s.erzeugen({'art': 'video_text', 'prompt': 'x', 'breite': 960, 'hoehe': 544, 'turbo': True})
                self.assertNotIn('turbo', {k for k, v in self.s._meta(self.s._finden(a['neu'][0])).items() if v is True})
            # ohne Turbo-Wunsch bleibt alles wie bisher, auch bei 6 Schritten
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'schritte': 6})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j.get('turbo'), j['qualitaet']), (None, None))
            self.assertNotIn('turbo', self.s._meta(j))

    def test_grosse_bilder(self):
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 2752, 'hoehe': 1536})
            gross = self.s._finden(a['neu'][0])
            self.assertEqual((code, gross['breite'], gross['hoehe']), (200, 2752, 1536))
            self.assertEqual(self.s._bedarf(gross), {'eine': 22016, 'haupt': 18432, 'neben': 6144})
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328})
            self.assertEqual(self.s._bedarf(self.s._finden(a['neu'][0])), {'eine': 20000})  # wie bisher (hier: Zentrale-Wert)
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 2816, 'hoehe': 2816})
            self.assertEqual(code, 400)  # zu viele Pixel
            self.assertIn('4,3 Megapixel', a['fehler'])
            # Banner und Panorama (Stufe 3k): 4096 breit geht, darüber nicht
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 4096, 'hoehe': 1024})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['breite'], j['hoehe'], self.s._bedarf(j)), (200, 4096, 1024, {'eine': 22016, 'haupt': 18432, 'neben': 6144}))
            code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 4112, 'hoehe': 1024})
            self.assertEqual(code, 400)
            code, a = self.s.erzeugen({'art': 'video_text', 'prompt': 'x', 'breite': 2752, 'hoehe': 1536})
            self.assertEqual(code, 400)  # Videos bleiben bis 2048 px

    def test_bearbeiten_groesse(self):
        vorlage = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorlage'}]
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            # ohne Angabe wie bisher: Größe von Vorlage 1, mitgeschickte Maße zählen nicht
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'breite': 1920, 'hoehe': 1088, 'vorlagen': vorlage})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['breite'], j['hoehe'], j['groesse_von']), (200, None, None, 'vorlage'))
            self.assertEqual(self.s._meta(j)['groesse_von'], 'vorlage')
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'breite': 1930, 'hoehe': 1088,
                                       'groesse_von': 'format', 'vorlagen': vorlage})
            j = self.s._finden(a['neu'][0])
            self.assertEqual((code, j['breite'], j['hoehe'], j['groesse_von']), (200, 1920, 1088, 'format'))
            self.assertEqual(self.s._erwartet(j), round(1.4 * 40 * 1920 * 1088 / 1328 ** 2))
            code, a = self.s.erzeugen({'art': 'bearbeiten', 'prompt': 'x', 'breite': 100, 'hoehe': 1088,
                                       'groesse_von': 'format', 'vorlagen': vorlage})
            self.assertEqual(code, 400)

    def test_verbessern_pruefen(self):
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'Gross.png'), {}, 64, 48)
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        grund = {'art': 'verbessern', 'prompt': 'Eine natürliche Hand', 'projekt': 'Praxis', 'maske': m,
                 'vorlagen': [{'art': 'bibliothek', 'pfad': 'Praxis/Gross.png', 'rolle': 'original'}]}
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            for falsch in (dict(grund, maske=None), dict(grund, maske=rle_aus(32, 48, lambda x, y: x < 4)),
                           dict(grund, staerke=0.5), dict(grund, vorlagen=[]),
                           dict(grund, vorlagen=[{'art': 'bibliothek', 'pfad': 'Praxis/Gross.png', 'rolle': 'vorlage'}])):
                self.assertEqual(self.s.erzeugen(falsch)[0], 400)
            code, a = self.s.erzeugen(dict(grund, staerke=0.8, anzahl=2))
            self.assertEqual((code, len(a['neu'])), (200, 2))
            j = self.s._finden(a['neu'][0])
            self.assertEqual((j['breite'], j['hoehe'], j['staerke'], j['markiert'], j['vorlagen'][0]['rolle']),
                             (64, 48, 0.8, round(100 / 3072, 5), 'original'))
            self.assertEqual(j['ausschnitt'], {'x': 0, 'y': 0, 'breite': 64, 'hoehe': 48})
            self.assertEqual((j['arbeit']['breite'] % 32, j['arbeit']['hoehe'] % 32), (0, 0))
            self.assertEqual(self.s._erwartet(j), round(1.4 * 40 * j['arbeit']['breite'] * j['arbeit']['hoehe'] / 1328 ** 2))
            self.assertTrue(all('maske' not in x for x in self.s.stand()['auftraege']))
            meta = self.s._meta(j)
            self.assertEqual((meta['maske'], meta['staerke'], meta['vorlagen']),
                             (m, 0.8, [{'pfad': 'Praxis/Gross.png', 'rolle': 'original'}]))
            # Stufe 3n: ein Vorbild für die Stelle (eigene Rolle), höchstens eins, das Original bleibt vorn; Vorlagen
            # vom Bearbeiten (Rolle „vorlage“) gehen nicht mit
            logo = {'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorbild'}
            code, a = self.s.erzeugen(dict(grund, vorlagen=[logo, grund['vorlagen'][0], dict(logo, pfad='Praxis/Gross.png'),
                                                            dict(logo, rolle='vorlage')]))
            v = self.s._finden(a['neu'][0])
            self.assertEqual((code, [(x['pfad'], x['rolle']) for x in v['vorlagen']]),
                             (200, [('Praxis/Gross.png', 'original'), ('Praxis/Bild_00001_.png', 'vorbild')]))
            self.assertEqual(self.s._meta(v)['vorlagen'], [{'pfad': 'Praxis/Gross.png', 'rolle': 'original'},
                                                           {'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorbild'}])
            pixel = v['arbeit']['breite'] * v['arbeit']['hoehe']
            self.assertEqual(self.s._erwartet(v), round(1.4 * 40 * pixel / 1328 ** 2 * (1 + 0.55 * 1024 ** 2 / pixel)))
            self.assertEqual(self.s.einstellungen()['verbessern']['max_vorlagen'], 1)
            # mit Vorbild ein kleinerer Ausschnitt (doppelt statt dreifach so groß wie die Markierung): mehr Pixel für die Stelle
            png_bauen(os.path.join(self.wurzel, 'Praxis', 'Breit.png'), {}, 1000, 800)
            klein = rle_aus(1000, 800, lambda x, y: 400 <= x < 600 and 300 <= y < 500)
            breit = [{'art': 'bibliothek', 'pfad': 'Praxis/Breit.png', 'rolle': 'original'}]
            ohne = self.s._finden(self.s.erzeugen(dict(grund, maske=klein, vorlagen=breit))[1]['neu'][0])
            mit = self.s._finden(self.s.erzeugen(dict(grund, maske=klein, vorlagen=breit + [logo]))[1]['neu'][0])
            self.assertEqual((ohne['ausschnitt']['breite'], mit['ausschnitt']['breite']), (600, 400))
            # Gelernte Sekunden je Schritt: Verbessern mit Bild 2 rechnet mehr und zählt nicht mit
            for x, zeit in ((j, 10.0), (v, 99.0)):
                x.update(zustand='fertig', rechenzeit_s=zeit, schritte=10)
            self.assertEqual(self.s._sekunden_je_schritt(), round(10.0 / 10 / (studio.Studio._pixel(j) / 1328 ** 2), 3))

    def test_verbessern_mit_vorlage_rechnen(self):
        """Das Vorbild für die Stelle geht als „Bild 2“ an ComfyUI, direkt aus der Bibliothek (keine Kopie)."""
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'Gross.png'), {}, 64, 48)
        m = rle_aus(64, 48, lambda x, y: 10 <= x < 20 and 10 <= y < 20)
        bereit = {'laeuft': True, 'ordner_ok': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit):
            code, r = self.s.erzeugen({'art': 'verbessern', 'prompt': 'Der Kopf der Frau aus Bild 2', 'projekt': 'Praxis',
                                       'maske': m, 'variation': 3,
                                       'vorlagen': [{'art': 'bibliothek', 'pfad': 'Praxis/Gross.png', 'rolle': 'original'},
                                                    {'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'vorbild'}]})
        a = self.s._finden(r['neu'][0])
        ziel = os.path.join(self.wurzel, 'Praxis', 'Verbessert_00001_.png')

        def rechnen(auftrag, graph, meta, anmeldung):
            self.assertEqual(graph['50']['inputs']['image'], 'Praxis/Gross.png [output]')
            self.assertEqual(graph['110']['inputs']['image'], 'Praxis/Bild_00001_.png [output]')
            self.assertEqual(graph['4']['inputs']['images.image_2'], ['111', 0])
            png_bauen(ziel, {}, 64, 48)
            auftrag['rechnen_ab'] = time.time() - 1
            return {'outputs': {'10': {'images': [{'filename': 'Verbessert_00001_.png', 'subfolder': 'Praxis', 'type': 'output'}]}}}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), \
                mock.patch.object(self.s, '_hochladen_daten', return_value='werkstatt_maske_x.png'), \
                mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen) as gerechnet:
            self.s._rechnen(a, None)
        self.assertEqual(gerechnet.call_count, 1)
        with open(ziel + '.json', encoding='utf-8') as f:
            info = json.load(f)
        self.assertEqual([v['rolle'] for v in info['vorlagen']], ['original', 'vorbild'])
        self.assertEqual((info['art'], info['maske'], info['variation']), ('verbessern', m, 3))

    def test_maske_lesen_und_bibliothek(self):
        m = rle_aus(64, 48, lambda x, y: x < 8)
        p = os.path.join(self.wurzel, 'Praxis', 'Verbessert_00001_.png')
        png_bauen(p, {}, 64, 48)
        with open(p + '.json', 'w', encoding='utf-8') as f:
            json.dump({'format': studio.FORMAT, 'herkunft': 'studio', 'art': 'verbessern', 'prompt': 'x', 'maske': m,
                       'vorlagen': [{'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'original'}]}, f)
        os.utime(p, (time.time() - 60,) * 2)
        e = next(x for x in self.s.bibliothek(neu=True)['eintraege'] if x['name'] == 'Verbessert_00001_.png')
        self.assertTrue(e['info']['hat_maske'])
        self.assertNotIn('maske', e['info'])
        self.assertEqual(self.s.maske_lesen('Praxis/Verbessert_00001_.png'), (200, {'maske': m}))
        self.assertEqual(self.s.maske_lesen('Praxis/Bild_00001_.png')[0], 404)
        self.assertEqual(self.s.maske_lesen('../x.png')[0], 404)
        # ohne Begleitdatei aus dem PNG („werkstatt“)
        q = os.path.join(self.wurzel, 'Praxis', 'Verbessert_00002_.png')
        png_bauen(q, {'werkstatt': json.dumps({'art': 'verbessern', 'maske': m})}, 64, 48)
        self.assertEqual(self.s.maske_lesen('Praxis/Verbessert_00002_.png'), (200, {'maske': m}))

    def test_bilder_von_aussen_nur_wenn_gewaehlt(self):
        aussen = os.path.join(self.tmp.name, 'Foto.png')
        png_bauen(aussen, {}, 32, 32)
        self.assertIsNone(self.s.vorlage_datei(aussen))
        with mock.patch.object(studio.winapi, 'fenster_mit_titel', return_value=None), \
                mock.patch.object(studio.winapi, 'dateien_waehlen', return_value=[aussen]):
            self.assertEqual(self.s.vorlagen_waehlen()[1]['pfade'], [os.path.normpath(aussen)])
        self.assertEqual(self.s.vorlage_datei(aussen), os.path.normpath(aussen))
        self.assertIsNone(self.s.vorlage_datei(os.path.join(self.tmp.name, 'fehlt.png')))
        self.assertIsNone(self.s.vorlage_datei('Praxis/Bild_00001_.png'))  # nur absolute Pfade
        anderes = os.path.join(self.tmp.name, 'Anderes.png')
        png_bauen(anderes, {}, 32, 32)
        self.assertIsNone(self.s.vorlage_datei(anderes, 'Praxis/Bild_00001_.png'))
        with open(self.bild + '.json', 'w', encoding='utf-8') as f:
            json.dump({'art': 'verbessern', 'vorlagen': [{'pfad': anderes, 'rolle': 'original'}]}, f)
        self.assertEqual(self.s.vorlage_datei(anderes, 'Praxis/Bild_00001_.png'), os.path.normpath(anderes))
        self.assertIsNone(self.s.vorlage_datei(anderes, '../Bild_00001_.png'))

    def test_neue_arten_und_felder_pruefen(self):
        vorlage = [{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'original'}]
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'Gross.png'), {}, 64, 48)
        gross = [{'art': 'bibliothek', 'pfad': 'Praxis/Gross.png', 'rolle': 'original'}]
        verfuegbar = ('int8_verfuegbar', 'freistellen_schnell_verfuegbar', 'finden_verfuegbar', 'pose_verfuegbar',
                      'ausformulieren_verfuegbar')
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True, 'ordner_ok': True}):
            # nicht eingerichtet (leerer Testordner): verständliche Ablehnung statt stiller Änderung
            for d in ({'art': 'pose', 'vorlagen': vorlage}, {'art': 'freistellen', 'verfahren': 'schnell', 'vorlagen': vorlage},
                      {'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'ausformulieren': True},
                      {'art': 'verbessern', 'prompt': 'x', 'stelle': 'hand', 'vorlagen': gross}):
                self.assertEqual(self.s.erzeugen(d)[0], 400, d)
            self.assertEqual([self.s.einstellungen()[k] for k in verfuegbar], [False] * 5)
            with mock.patch.object(self.s, '_modell_da', return_value=True):
                self.assertEqual([self.s.einstellungen()[k] for k in verfuegbar], [True] * 5)
                # Pose-Skelett: ohne Qwen, ohne Qualitätsstufe, genau ein Auftrag
                code, a = self.s.erzeugen({'art': 'pose', 'prompt': 'egal', 'vorlagen': vorlage, 'turbo': True,
                                           'schnell': True, 'int8': True, 'anzahl': 3})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, len(a['neu']), j['prompt'], j['schritte'], j['breite'], j['cfg'], j['vorlagen'][0]['rolle']),
                                 (200, 1, 'Pose-Skelett', 1, None, None, 'original'))
                self.assertFalse({'turbo', 'schnell', 'int8', 'personen'} & set(j))
                self.assertEqual((self.s._bedarf(j), self.s._erwartet(j)), ({'fest': 4096}, 3))
                m = self.s._meta(j)
                self.assertEqual((m['modell'], m['modell_datei'], m['art']), ('SDPose', 'sdpose.safetensors', 'pose'))
                self.assertNotIn('personen', m)
                # alle Personen (SAM3-Rahmen) nur auf Wunsch
                code, a = self.s.erzeugen({'art': 'pose', 'vorlagen': vorlage, 'personen': True})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['personen'], self.s._meta(j)['personen']), (200, True, True))
                # schnell freistellen (BiRefNet): nur das Hauptmotiv
                code, a = self.s.erzeugen({'art': 'freistellen', 'prompt': '', 'verfahren': 'schnell', 'vorlagen': vorlage,
                                           'turbo': True, 'int8': True})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['verfahren'], j['motiv'], j['schritte'], j.get('turbo'), j.get('int8')),
                                 (200, 'schnell', '', 1, None, None))
                m = self.s._meta(j)
                self.assertEqual((m['verfahren'], m['modell'], m['modell_datei'], self.s._erwartet(j)),
                                 ('schnell', 'BiRefNet', 'birefnet.safetensors', 3))
                code, a = self.s.erzeugen({'art': 'freistellen', 'prompt': 'den Hund', 'verfahren': 'schnell', 'vorlagen': vorlage})
                self.assertEqual(code, 400)
                self.assertIn('Hauptmotiv', a['fehler'])
                # INT8 nur auf Wunsch; Begleitdaten nennen die Datei, die Schätzung nimmt den INT8-Faktor
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328, 'int8': True})
                j = self.s._finden(a['neu'][0])
                m = self.s._meta(j)
                self.assertEqual((j['int8'], m['int8'], m['modell_datei'], self.s._erwartet(j)),
                                 (True, True, 'qwen_image_2.1_int8_convrot.safetensors', round(1.4 * 0.5 * 40)))
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'x', 'breite': 1328, 'hoehe': 1328})
                self.assertEqual(self.s._meta(self.s._finden(a['neu'][0]))['modell_datei'], 'qwen_image_2.1_bf16.safetensors')
                # Ausformulieren: mehr Grafikspeicher auf der 3090, Zeit + 15 s; nicht mit durchsichtigem Hintergrund
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'Hund', 'breite': 1328, 'hoehe': 1328, 'ausformulieren': True})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['ausformulieren'], self.s._meta(j)['ausformulieren']), (200, True, True))
                self.assertEqual((self.s._bedarf(j), self.s._erwartet(j)), ({'eine': 20480, 'haupt': 20480, 'neben': 4096}, 15 + round(1.4 * 40)))
                code, a = self.s.erzeugen({'art': 'bild', 'prompt': 'Hund', 'breite': 1328, 'hoehe': 1328, 'ausformulieren': True,
                                           'durchsichtig': True})
                self.assertNotIn('ausformulieren', self.s._finden(a['neu'][0]))
                # Verbessern mit Stelle per Wort: gesucht wird beim Rechnen, die Größe kommt vom Original
                code, a = self.s.erzeugen({'art': 'verbessern', 'prompt': 'Hand', 'stelle': '  hand:2 ', 'vorlagen': gross})
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['stelle'], j['breite'], j['hoehe'], j['staerke'], 'maske' in j), (200, 'hand:2', 64, 48, 1.0, False))
                self.assertEqual(self.s._meta(j)['stelle'], 'hand:2')
            # ohne SAM3 bleibt das Pose-Skelett wie bisher (eine Person), statt abzulehnen
            with mock.patch.object(self.s, '_modell_da', side_effect=lambda ordner, datei: datei != 'sam3.safetensors'):
                code, a = self.s.erzeugen({'art': 'pose', 'vorlagen': vorlage, 'personen': True})
                self.assertEqual(code, 200)
                self.assertNotIn('personen', self.s._finden(a['neu'][0]))

    def test_stelle_finden(self):
        a = {'id': 'x1', 'art': 'verbessern', 'stelle': 'hand', 'breite': 64, 'hoehe': 48}
        klein = bytes(255 if 4 <= x < 8 and 3 <= y < 6 else 0 for y in range(12) for x in range(16) for _ in range(3))
        eintrag = {'outputs': {'88': {'text': ['64']}, '89': {'text': ['48']},
                               '99': {'images': [{'filename': 'm.png', 'subfolder': '', 'type': 'temp'}]}}}
        with mock.patch.object(self.s, '_comfy_rechnen', return_value=eintrag) as rechnen, \
                mock.patch.object(self.s, '_comfy_datei', return_value=png_mit_filter(16, 12, klein, 3, 1)):
            self.s._stelle_finden(a, 'Praxis/Gross.png [output]', None)
        self.assertEqual(rechnen.call_args[0][1]['79']['inputs']['text'], 'hand')
        self.assertEqual((a['maske']['breite'], a['maske']['hoehe'], sum(a['maske']['rle'])), (64, 48, 3072))
        self.assertEqual(a['maske'], rle_aus(64, 48, lambda x, y: 16 <= x < 32 and 12 <= y < 24))
        self.assertEqual((a['markiert'], a['ausschnitt']['breite'] > 0, a['arbeit']['breite'] % 32), (round(192 / 3072, 5), True, 0))
        # mit Vorbild (Stufe 3n) auch hier der kleinere Ausschnitt
        b = {'id': 'x3', 'art': 'verbessern', 'stelle': 'hand', 'breite': 64, 'hoehe': 48,
             'vorlagen': [{'pfad': 'o.png', 'rolle': 'original'}, {'pfad': 'l.png', 'rolle': 'vorbild'}]}
        with mock.patch.object(self.s, '_comfy_rechnen', return_value=eintrag),                 mock.patch.object(self.s, '_comfy_datei', return_value=png_mit_filter(16, 12, klein, 3, 1)),                 mock.patch.object(self.s, '_maske_felder', wraps=self.s._maske_felder) as felder:
            self.s._stelle_finden(b, 'Praxis/Gross.png [output]', None)
        self.assertIs(felder.call_args[0][1], True)
        # nichts gefunden: verständlicher Fehler statt eines leeren Verbesserns
        leer = {'id': 'x2', 'art': 'verbessern', 'stelle': 'Liege'}
        with mock.patch.object(self.s, '_comfy_rechnen', return_value=eintrag), \
                mock.patch.object(self.s, '_comfy_datei', return_value=png_mit_filter(16, 12, bytes(576), 3, 0)):
            with self.assertRaises(studio.Fehler) as f:
                self.s._stelle_finden(leer, 'Praxis/Gross.png [output]', None)
        self.assertIn('nichts gefunden', str(f.exception))

    def test_ausformulierte_beschreibung_in_begleitdaten(self):
        bereit = {'laeuft': True, 'ordner_ok': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), mock.patch.object(self.s, '_modell_da', return_value=True):
            code, r = self.s.erzeugen({'art': 'bild', 'prompt': 'Hund im Garten', 'breite': 1328, 'hoehe': 1328,
                                       'ausformulieren': True, 'projekt': 'Praxis', 'variation': 5})
        a = self.s._finden(r['neu'][0])
        ziel = os.path.join(self.wurzel, 'Praxis', 'Bild_00009_.png')

        def rechnen(auftrag, graph, meta, anmeldung):
            self.assertEqual((graph['4']['inputs']['text'], graph['62']['inputs']['sampling_mode.seed']), (['62', 0], 5))
            self.assertIn('Hund im Garten', graph['62']['inputs']['prompt'])
            png_bauen(ziel, {}, 16, 16)
            auftrag['rechnen_ab'] = time.time() - 1
            return {'outputs': {'10': {'images': [{'filename': 'Bild_00009_.png', 'subfolder': 'Praxis', 'type': 'output'}]},
                                '63': {'text': ['A golden retriever in a sunny garden.']}}}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), \
                mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen):
            self.s._rechnen(a, None)
        with open(ziel + '.json', encoding='utf-8') as f:
            info = json.load(f)
        self.assertEqual((info['prompt'], info['prompt_ausformuliert'], info['ausformulieren']),
                         ('Hund im Garten', 'A golden retriever in a sunny garden.', True))

    def test_gewaehlte_karten_kommen_in_den_ablauf(self):
        # Seit 14.10.2026: _platz wählt die Karten, _rechnen muss sie in jeden Ablauf übernehmen (Bild samt Enhancer).
        bereit = {'laeuft': True, 'ordner_ok': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), mock.patch.object(self.s, '_modell_da', return_value=True):
            code, r = self.s.erzeugen({'art': 'bild', 'prompt': 'Hund', 'breite': 1328, 'hoehe': 1328,
                                       'ausformulieren': True, 'projekt': 'Praxis', 'variation': 6})
        a = self.s._finden(r['neu'][0])
        geraete = dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:1')
        gesehen = {}

        def rechnen(auftrag, graph, meta, anmeldung):
            gesehen.update({k: graph[k]['inputs']['device'] for k in ('20', '21', '22', '61')})
            raise studio.Fehler('nur der Ablauf zählt')
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit),                 mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen), self.assertRaises(studio.Fehler):
            self.s._rechnen(a, None, geraete)
        self.assertEqual(gesehen, {'20': 'gpu:1', '21': 'gpu:1', '22': 'gpu:1', '61': 'gpu:1'})
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit),                 mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen), self.assertRaises(studio.Fehler):
            self.s._rechnen(a, None)  # ohne Wahl: die Vorgabe aus der Einstellung
        self.assertEqual(gesehen['20'], S['geraete']['modell'])

    def test_fertige_auftraege_ohne_maske_gespeichert(self):
        self.s.auftraege = [{'id': 'a', 'zustand': 'fertig', 'maske': {'x': 1}},
                            {'id': 'b', 'zustand': 'fehler', 'maske': {'x': 2}}]
        self.s._speichern()
        with open(self.s.speicher, encoding='utf-8') as f:
            gespeichert = json.load(f)['auftraege']
        self.assertEqual([('maske' in a) for a in gespeichert], [False, True])


class Weiterfuehren(unittest.TestCase):
    """Stufe 3m: Längen, Bereiche und Ablauf „Video weiterführen“ (ohne ComfyUI)."""
    v = S['video']

    @staticmethod
    def quelle(rolle, bilder, tondauer=None):
        return {'rolle': rolle, 'bilder': bilder, 'tondauer': bilder / 24 if tondauer is None else tondauer,
                'tonrate': 44100, 'tonkanaele': 2}

    @staticmethod
    def auftrag(modus, laenge, quellen, e=0, b=0):
        return {'modus': modus, 'prompt': 'Weiter', 'breite': 960, 'hoehe': 544, 'bilder': laenge, 'schritte': 8,
                'variation': 7, 'schnitt_ende': e, 'schnitt_anfang': b, 'quellen': quellen}

    def verweise_pruefen(self, g):
        for nid, knoten in g.items():
            for wert in knoten['inputs'].values():
                if isinstance(wert, list) and len(wert) == 2 and isinstance(wert[0], str):
                    self.assertIn(wert[0], g, f'{nid} verweist auf einen fehlenden Knoten')

    def test_laenge_je_modus(self):
        L = studio.weiter_laenge
        self.assertEqual([L(m, 1) for m in studio.WEITER_MODI], [124] * 4)  # Mindestlänge des Clips
        self.assertEqual((L('verlaengern', 85 / 24), L('verlaengern', 86 / 24)), (124, 141))
        self.assertEqual(L('verlaengern', 5), 175)  # 120+39 → 158 fiele auf L mod 3 = 2 (Ton 8 ms zu kurz)
        self.assertEqual(L('verlaengern', 4.3), 175)
        self.assertEqual((L('davor', 5.125), L('davor', 14.333)), (124, 345))
        self.assertEqual((L('verlaengern', 12.75), L('verbinden', 305 / 24)), (345, 345))
        for modus, s in (('davor', 14.4), ('verlaengern', 12.8), ('schleife', 306 / 24)):
            self.assertIsNone(L(modus, s), (modus, s))  # 362 hätte kurzen Ton, darüber ist H3 nicht trainiert

    def test_laenge_aus_wiederholung(self):
        ok = studio.weiter_laenge_ok
        self.assertEqual([x for x in range(100, 400) if ok(x)], [124, 141, 175, 192, 226, 243, 277, 294, 328, 345])
        for falsch in (158, 362, 124.0, True, '124', None):
            self.assertFalse(ok(falsch), falsch)

    def test_bereiche(self):
        B = studio.weiter_bereiche
        v = B('verlaengern', 175, {'ausgang': 124})
        self.assertEqual((v['fuehrung'], v['endbild'], v['neu'], v['segmente'], v['gesamt']),
                         (('ausgang', 85, 39), None, (39, 136), [('ausgang', 0, 124), ('neu', 39, 136)], 260))
        d = B('davor', 124, {'ziel': 200}, schnitt_anfang=10)
        self.assertEqual((d['fuehrung'], d['endbild'], d['neu'], d['segmente'], d['gesamt']),
                         (None, ('ziel', 10), (0, 123), [('neu', 0, 123), ('ziel', 10, 190)], 313))
        b = B('verbinden', 175, {'ausgang': 124, 'ziel': 124}, 12, 6)
        self.assertEqual((b['fuehrung'], b['endbild'], b['segmente'], b['gesamt']),
                         (('ausgang', 73, 39), ('ziel', 6), [('ausgang', 0, 112), ('neu', 39, 135), ('ziel', 6, 118)], 365))
        s = B('schleife', 124, {'ausgang': 124})
        self.assertEqual((s['endbild'], s['segmente'], s['gesamt']), (('ausgang', 0), [('ausgang', 0, 124), ('neu', 39, 84)], 208))
        # vom Clip davor bleiben mindestens 39 Bilder; vom Clip danach mindestens eines
        self.assertEqual(B('verlaengern', 124, {'ausgang': 51}, 12)['fuehrung'], ('ausgang', 0, 39))
        self.assertEqual(B('davor', 124, {'ziel': 5}, 0, 4)['segmente'][-1], ('ziel', 4, 1))
        for args in (('verlaengern', 124, {'ausgang': 50}, 12), ('davor', 124, {'ziel': 50}, 1),
                     ('verlaengern', 124, {'ausgang': 124}, 0, 1), ('schleife', 124, {'ausgang': 124}, 0, 1),
                     ('verlaengern', 124, {'ausgang': 124}, -1), ('davor', 124, {'ziel': 5}, 0, 5),
                     ('weg', 124, {'ausgang': 124})):
            with self.assertRaises(ValueError, msg=args):
                B(*args)

    def test_rechenzeit_waechst_staerker_als_die_laenge(self):
        z = S['video']['zeit']
        a = {'art': 'video_text', 'breite': 960, 'hoehe': 544, 'bilder': 124, 'schritte': 8}
        self.assertEqual(studio.video_zeit(a, z, 12.4), 129)  # 2Wild: 138,8 s gemessen
        w = dict(a, art='video_weiter', modus='verlaengern', bilder=175)
        self.assertEqual((studio.video_bilder_wirksam(w), studio.video_zeit(w, z, 12.4)), (214, 325))  # gemessen 300,9 s
        self.assertEqual(studio.video_bilder_wirksam(dict(w, modus='davor', bilder=124)), 125)
        self.assertEqual(studio.video_bilder_wirksam(dict(a, art='video_bild', vorlagen=[{}, {}])), 126)

    def test_zeitfenster_einen_ms_frueher(self):
        # zusammengesetzte Videos zittern um bis 0,5 ms: Fenster 1 ms vor den Bildgrenzen treffen genau die Bilder
        self.assertEqual(studio._zeitfenster(85, 39, 24), (round(85 / 24 - 0.001, 6), 1.625))
        self.assertEqual(studio._zeitfenster(0, 1, 24), (0.0, round(1 / 24 - 0.001, 6)))

    def test_ablauf_verlaengern(self):
        g = studio.weiter_graph(self.auftrag('verlaengern', 175, [self.quelle('ausgang', 124)]), self.v, 'Praxis/Video',
                                {'ausgang': 'Praxis/Video_00001_.mp4 [output]'})
        self.verweise_pruefen(g)
        self.assertEqual((g['40']['inputs']['file'], g['30']['inputs']['audio']), ('Praxis/Video_00001_.mp4 [output]',) * 2)
        self.assertNotIn('41', g)
        # vorn: die letzten 39 Bilder samt Ton festgehalten
        fuehrung = g[g['43']['inputs']['video'][0]]['inputs']
        self.assertEqual((fuehrung['video'], fuehrung['start_time'], fuehrung['duration']),
                         (['40', 0], round(85 / 24 - 0.001, 6), 1.625))
        guide = g['50']['inputs']
        self.assertEqual((g['50']['class_type'], guide['frame_idx'], guide['image']), ('MiniMaxH3AddGuide', 0, ['43', 0]))
        ton = g[guide['audio'][0]]['inputs']
        self.assertEqual((ton['audio'], ton['start_index'], ton['duration']), (['30', 0], round(85 / 24, 6), 1.625))
        self.assertEqual((g['11']['inputs']['conditioning'], g['5']['inputs']['length']), (['50', 0], 175))
        self.assertNotIn('last_frame', g['5']['inputs'])
        # Original ungeschnitten (Bildspur bitgleich) + neue Bilder 39…174; Ton exakt an den Bildgrenzen
        self.assertEqual({k: g['46']['inputs'][k] for k in ('batch_index', 'length')}, {'batch_index': 39, 'length': 136})
        c = g['18']['inputs']
        self.assertEqual((c['videos.video0'], c['videos.video1'], c['codec'], g['17']['inputs']['video']),
                         (['40', 0], ['16', 0], 'auto', ['18', 0]))
        verkettet = g[c['complete_audio'][0]]
        alt, neu = (g[verkettet['inputs'][k][0]]['inputs'] for k in ('audio1', 'audio2'))
        self.assertEqual((verkettet['class_type'], alt['audio'], alt['start_index'], alt['duration']),
                         ('AudioConcat', ['30', 0], 0.0, round(124 / 24, 6)))
        self.assertEqual((neu['audio'], neu['start_index'], neu['duration']), (['15', 0], round(39 / 24, 6), round(136 / 24, 6)))
        self.assertNotIn('EmptyAudio', {k['class_type'] for k in g.values()})
        self.assertEqual(studio.einstellungen_aus_graph(g)['art'], 'video_weiter')

    def test_ablauf_verbinden_mit_schnitten(self):
        q = [self.quelle('ausgang', 124), self.quelle('ziel', 124)]
        g = studio.weiter_graph(self.auftrag('verbinden', 175, q, 12, 6), self.v, 'Video',
                                {'ausgang': 'a.mp4 [output]', 'ziel': 'b.mp4 [output]'})
        self.verweise_pruefen(g)
        ende = g[g['45']['inputs']['video'][0]]['inputs']
        self.assertEqual((ende['video'], ende['start_time'], ende['duration']), (['41', 0], round(6 / 24 - 0.001, 6), round(1 / 24, 6)))
        self.assertEqual(g['5']['inputs']['last_frame'], ['45', 0])
        self.assertEqual(g[g['43']['inputs']['video'][0]]['inputs']['start_time'], round(73 / 24 - 0.001, 6))
        c = g['18']['inputs']
        # geschnittene Quellen gehen als Ausschnitt hinein, nicht als ganze Datei
        stuecke = [g[c[f'videos.video{i}'][0]] for i in range(3)]
        self.assertEqual([s['class_type'] for s in stuecke], ['Video Slice', 'CreateVideo', 'Video Slice'])
        self.assertEqual([stuecke[i]['inputs'][k] for i in (0, 2) for k in ('video', 'start_time', 'duration')],
                         [['40', 0], 0.0, round(112 / 24 - 0.001, 6), ['41', 0], round(6 / 24 - 0.001, 6), round(118 / 24, 6)])
        self.assertEqual({k: g['46']['inputs'][k] for k in ('batch_index', 'length')}, {'batch_index': 39, 'length': 135})
        self.assertNotIn('videos.video3', c)
        ziel_ton = g[g[c['complete_audio'][0]]['inputs']['audio2'][0]]['inputs']
        self.assertEqual((ziel_ton['audio'], ziel_ton['start_index'], ziel_ton['duration']), (['31', 0], 0.25, round(118 / 24, 6)))

    def test_ablauf_davor_und_schleife(self):
        g = studio.weiter_graph(self.auftrag('davor', 124, [self.quelle('ziel', 124)]), self.v, 'Video', {'ziel': 'b.mp4 [output]'})
        self.verweise_pruefen(g)
        self.assertNotIn('50', g)  # nichts festgehalten: der Anfang ist frei
        self.assertEqual((g['5']['inputs']['last_frame'], g['46']['inputs']['batch_index'], g['46']['inputs']['length']),
                         (['45', 0], 0, 123))
        self.assertEqual((g['18']['inputs']['videos.video0'], g['18']['inputs']['videos.video1']), (['16', 0], ['41', 0]))
        s = studio.weiter_graph(self.auftrag('schleife', 124, [self.quelle('ausgang', 124)]), self.v, 'Video',
                                {'ausgang': 'a.mp4 [output]'})
        self.verweise_pruefen(s)
        ende = s[s['45']['inputs']['video'][0]]['inputs']
        self.assertEqual((ende['video'], ende['start_time']), (['40', 0], 0.0))  # zurück zum ersten Bild
        self.assertEqual((s['11']['inputs']['conditioning'], s['5']['inputs']['last_frame']), (['50', 0], ['45', 0]))

    def test_kurzer_quellton_wird_aufgefuellt(self):
        # H3 rundet die Tonlänge: bei 158 Bildern fehlen am Ende 8,3 ms – im Stück und im festgehaltenen Ton
        q = [self.quelle('ausgang', 158, 158 / 24 - 1 / 120)]
        g = studio.weiter_graph(self.auftrag('verlaengern', 124, q), self.v, 'Video', {'ausgang': 'a.mp4 [output]'})
        self.verweise_pruefen(g)
        still = [k['inputs'] for k in g.values() if k['class_type'] == 'EmptyAudio']
        self.assertEqual([(x['duration'], x['sample_rate'], x['channels']) for x in still], [(round(1 / 120, 6), 44100, 2)] * 2)
        self.assertEqual(g[g['50']['inputs']['audio'][0]]['class_type'], 'AudioConcat')


class Mp4Info(unittest.TestCase):
    """mp4_info: bewusst enger Umfang für Studio-Videos (Stufe 3m)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pfad = os.path.join(self.tmp.name, 'v.mp4')

    def tearDown(self):
        self.tmp.cleanup()

    def info(self, **k):
        mp4_video_bauen(self.pfad, **k)
        return studio.mp4_info(self.pfad)

    def test_studio_video(self):
        self.assertEqual(self.info(), {'breite': 960, 'hoehe': 544, 'bilder': 124, 'fps': 24.0, 'tonrate': 44100,
                                       'tonkanaele': 2, 'tondauer': round(124 / 24, 6), 'bilddauer': round(124 / 24, 6)})
        # zusammengesetzte Videos zittern um bis 0,5 ms (Zeitstempel in ms); H3 rundet die Tonlänge (8,3 ms kürzer)
        self.assertEqual(self.info(stts=[(1, 504), (1, 520)] * 62, ton_s=124 / 24 - 1 / 120)['bilder'], 124)
        i = self.info(bild_elst=(), ton_elst=(), kanaele=1, tonrate=48000)
        self.assertEqual((i['tonkanaele'], i['tonrate']), (1, 48000))

    def test_ablehnungen(self):
        faelle = [('keine Tonspur', dict(ohne_ton=True)), ('mehr als eine', dict(zwei_bildspuren=True)),
                  ('nicht gleichmäßig', dict(stts=[(124, 410)])),  # 30 fps
                  ('¼ Bild', dict(stts=[(124, 492)])),  # 25 fps: je Bild knapp in der Grenze, zusammen zu weit
                  ('nicht ganz ab', dict(ton_s=123 / 24)),  # ein Bild zu wenig Ton
                  ('Edit-List', dict(ton_elst=((1024, -1), (0, 1024)))),  # leerer Vorspann
                  ('Edit-List', dict(bild_elst=((0, -1),)))]
        for text, k in faelle:
            with self.assertRaises(ValueError, msg=text) as f:
                self.info(**k)
            self.assertIn(text, str(f.exception))
        with open(self.pfad, 'wb') as f:
            f.write(_atom(b'ftyp', b'isom') + _atom(b'mdat', b'\0' * 10))
        with self.assertRaises(ValueError):
            studio.mp4_info(self.pfad)
        with open(self.pfad, 'wb') as f:
            f.write(struct.pack('>I4s', 4000, b'moov') + b'\0' * 20)
        with self.assertRaises(ValueError):
            studio.mp4_info(self.pfad)

    def test_echte_studio_videos(self):
        """Die Videos des Studios erfüllen mp4_info, und die Bildzahl stimmt mit den Begleitdaten (sonst übersprungen)."""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json'), encoding='utf-8') as f:
            wurzel = json.load(f)['studio']['ordner']
        geprueft = 0
        for ordner, _, dateien in os.walk(wurzel):
            for name in dateien:
                pfad = os.path.join(ordner, name)
                if not name.lower().endswith('.mp4') or not os.path.isfile(pfad + '.json'):
                    continue
                with open(pfad + '.json', encoding='utf-8') as f:
                    info = json.load(f)
                if info.get('herkunft') == 'studio' and info.get('art') in ('video_zeitlupe', 'modell3d'):
                    # Zeitlupen (seit 09.10.2026) und Drehteller-Vorschauen (3D-Modell, Stufe 3t) haben absichtlich
                    # keinen Ton; die Bildzahl liest video_masse
                    self.assertEqual(studio.video_masse(pfad)['bilder'], info['laenge_bilder'], pfad)
                    geprueft += 1
                elif info.get('herkunft') == 'studio':
                    self.assertEqual(studio.mp4_info(pfad)['bilder'], info['laenge_bilder'], pfad)
                    geprueft += 1
        if not geprueft:
            self.skipTest('keine Studio-Videos auf diesem Rechner')


class WeiterDienst(unittest.TestCase):
    """Stufe 3m im Dienst: Prüfung, Prüfsummen vor der Übergabe, Begleitdaten und „Nochmal“-Felder."""
    BEREIT = {'laeuft': True, 'ordner_ok': True}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = os.path.join(self.tmp.name, 'Studio')
        os.makedirs(os.path.join(self.wurzel, 'Praxis'))
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI', 'studio_ordner': os.path.join(self.tmp.name, '2wild'),
                             'bedarf_je_karte_mib': 20000}]}
        with mock.patch('threading.Thread'):
            self.s = studio.Studio({'studio': dict(S, ordner=self.wurzel)}, zc, self.tmp.name, lambda t: None,
                                   mock.MagicMock())
        for name, k in (('Video_00001_.mp4', {}), ('Video_00002_.mp4', {'bilder': 192}),
                        ('Gross_00001_.mp4', {'breite': 1024, 'hoehe': 576}), ('Krumm_00001_.mp4', {'breite': 970}),
                        ('Lang_00001_.mp4', {'bilder': 1400})):
            mp4_video_bauen(os.path.join(self.wurzel, 'Praxis', name), **k)
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'Bild_00001_.png'), {})

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def clip(name, rolle='ausgang'):
        return {'art': 'bibliothek', 'pfad': 'Praxis/' + name, 'rolle': rolle}

    def erzeugen(self, **d):
        d = dict({'art': 'video_weiter', 'modus': 'verlaengern', 'prompt': 'Weiter', 'projekt': 'Praxis', 'neu_sekunden': 5,
                  'schritte': 8, 'vorlagen': [self.clip('Video_00001_.mp4')]}, **d)
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT):
            return self.s.erzeugen(d)

    def test_pruefen(self):
        code, a = self.erzeugen()
        j = self.s._finden(a['neu'][0])
        self.assertEqual((code, j['art'], j['breite'], j['hoehe'], j['bilder'], j['clip_bilder'], j['neu_bilder'],
                          j['laenge_bilder'], j['turbo'], j['neu_sekunden'], j['negativ'], j['cfg']),
                         (200, 'video_weiter', 960, 544, 175, 175, 136, 260, True, 5.0, '', None))
        q = j['quellen'][0]
        self.assertEqual((q['rolle'], q['pfad'], q['bilder'], q['tonrate'], len(q['sha256'])),
                         ('ausgang', 'Praxis/Video_00001_.mp4', 124, 44100, 64))
        # gerechnet wird der ganze neue Clip samt den 39 festgehaltenen Bildern: 175 + 39 wie 214 Bilder (gemessen 301 s)
        self.assertEqual(self.s._erwartet(j), 325)
        self.assertEqual(self.s._bedarf(j), self.s.bedarf_video)
        # Verbinden: beide Clips; Davor setzen: nur der Clip danach (der Clip davor wird nicht mitgenommen)
        code, a = self.erzeugen(modus='verbinden', vorlagen=[self.clip('Video_00001_.mp4'), self.clip('Video_00002_.mp4', 'ziel')],
                                schnitt_ende=12, schnitt_anfang=6)
        j = self.s._finden(a['neu'][0])
        self.assertEqual((code, j['bilder'], j['laenge_bilder'], [v['rolle'] for v in j['vorlagen']]),
                         (200, 175, 112 + 135 + 186, ['ausgang', 'ziel']))
        code, a = self.erzeugen(modus='davor', vorlagen=[self.clip('Video_00001_.mp4'), self.clip('Video_00002_.mp4', 'ziel')])
        j = self.s._finden(a['neu'][0])
        self.assertEqual((code, [q['pfad'] for q in j['quellen']], j['bilder'], j['laenge_bilder']),
                         (200, ['Praxis/Video_00002_.mp4'], 124, 123 + 192))
        self.assertIn('video_weiter', self.s.einstellungen()['arten'])

    def test_ablehnungen(self):
        aussen = {'art': 'datei', 'pfad': os.path.join(self.wurzel, 'Praxis', 'Video_00001_.mp4'), 'rolle': 'ausgang'}
        faelle = [(dict(modus='weg'), 'wie das Video'), (dict(prompt=' '), 'beschreiben'),
                  (dict(vorlagen=[]), 'Video wählen'), (dict(modus='verbinden'), 'vor das gesetzt'),
                  (dict(vorlagen=[aussen]), 'Bibliothek'), (dict(vorlagen=[self.clip('Bild_00001_.png')]), 'falsche Art'),
                  (dict(vorlagen=[self.clip('Krumm_00001_.mp4')]), 'Größe'),
                  (dict(modus='verbinden', vorlagen=[self.clip('Video_00001_.mp4'), self.clip('Gross_00001_.mp4', 'ziel')]),
                   'gleich groß'),
                  (dict(neu_sekunden=0), 'Länge des neuen Stücks'), (dict(neu_sekunden=13), 'höchstens'),
                  (dict(clip_bilder=158), 'Ungültige Länge'), (dict(clip_bilder='175'), 'Ungültige Länge'),
                  (dict(modus='davor', vorlagen=[self.clip('Video_00001_.mp4', 'ziel')], schnitt_ende=5), 'am Ende nichts'),
                  (dict(schnitt_ende=100), 'mindestens 39'),
                  (dict(vorlagen=[self.clip('Lang_00001_.mp4')]), '64,0 s lang'),
                  (dict(pruefsummen={'Praxis/Video_00001_.mp4': '0' * 64}), 'verändert oder ersetzt'),
                  (dict(pruefsummen=['x']), 'Prüfsummen')]
        for d, text in faelle:
            code, a = self.erzeugen(**d)
            self.assertEqual(code, 400, d)
            self.assertIn(text, a['fehler'], d)

    def test_rechnen_schreibt_begleitdaten_fuer_nochmal(self):
        code, a = self.erzeugen(variation=5)
        j = self.s._finden(a['neu'][0])
        ziel = os.path.join(self.wurzel, 'Praxis', 'Video_00003_.mp4')

        def rechnen(auftrag, graph, meta, anmeldung):
            self.assertEqual((graph['40']['inputs']['file'], graph['18']['class_type']),
                             ('Praxis/Video_00001_.mp4 [output]', 'ConcatenateVideo'))
            self.assertEqual((meta['modus'], meta['clip_bilder'], meta['laenge_bilder']), ('verlaengern', 175, 260))
            mp4_video_bauen(ziel, bilder=260)
            auftrag['rechnen_ab'] = time.time() - 1
            return {'outputs': {'17': {'images': [{'filename': 'Video_00003_.mp4', 'subfolder': 'Praxis', 'type': 'output'}],
                                       'animated': [True]}}}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT), \
                mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen):
            self.s._rechnen(j, None)
        with open(ziel + '.json', encoding='utf-8') as f:
            info = json.load(f)
        self.assertEqual((info['art'], info['modus'], info['clip_bilder'], info['neu_bilder'], info['laenge_bilder'],
                          info['sekunden'], info['schnitt_ende'], info['schnitt_anfang'], info['neu_sekunden'], info['variation']),
                         ('video_weiter', 'verlaengern', 175, 136, 260, round(260 / 24, 2), 0, 0, 5.0, 5))
        summe = studio.datei_pruefsumme(os.path.join(self.wurzel, 'Praxis', 'Video_00001_.mp4'))
        self.assertEqual(info['quellen'], [{'rolle': 'ausgang', 'pfad': 'Praxis/Video_00001_.mp4', 'bilder': 124, 'sha256': summe}])
        self.assertEqual(info['vorlagen'], [{'pfad': 'Praxis/Video_00001_.mp4', 'rolle': 'ausgang'}])
        # „Nochmal“ wie aus der Oberfläche: dieselbe Clip-Länge ohne neue Rundung, Prüfsummen der Quellen
        code, a = self.erzeugen(clip_bilder=info['clip_bilder'], neu_sekunden=None, variation=info['variation'],
                                pruefsummen={q['pfad']: q['sha256'] for q in info['quellen']})
        n = self.s._finden(a['neu'][0])
        self.assertEqual((code, n['bilder'], n['laenge_bilder'], 'neu_sekunden' in n, n['variation']), (200, 175, 260, False, 5))
        # das Ergebnis lässt sich wieder verlängern (Quelle = Ergebnis)
        code, a = self.erzeugen(vorlagen=[self.clip('Video_00003_.mp4')])
        self.assertEqual((code, self.s._finden(a['neu'][0])['laenge_bilder']), (200, 260 + 136))

    def test_zeitschaetzung_lernt_aus_eigenen_laeufen(self):
        self.assertEqual(self.s._video_je_schritt(), 12.4)
        grund = {'zustand': 'fertig', 'breite': 960, 'hoehe': 544, 'schritte': 8}
        self.s.auftraege = [dict(grund, art='video_weiter', modus='verlaengern', bilder=175, rechenzeit_s=300.9),
                            dict(grund, art='video_weiter', modus='davor', bilder=124, rechenzeit_s=140.7),
                            dict(grund, art='video_referenz', bilder=124, rechenzeit_s=900.0),  # zählt nicht mit
                            dict(grund, art='video_text', bilder=124, rechenzeit_s=20.0)]  # unter der Grundzeit
        self.assertEqual(self.s._video_je_schritt(), 13.62)
        # ohne eigene schnelle Läufe: × zeitfaktor (seit 17.10.2026, schnellere Aufmerksamkeit für neue Videos)
        self.assertEqual(self.s.einstellungen()['video']['zeit'],
                         {'grund_s': 30.0, 'je_schritt_s': 13.62, 'je_schritt_schnell_s': round(13.62 * 0.6, 2),
                          'exponent': 2.0, 'bezug': 960 * 544 * 124})

    def test_zeitschaetzung_bilder_nachlernen(self):
        """Seit 09.10.2026: Faktor gemessen/geschätzt je Gruppe aus den eigenen fertigen Bildaufträgen."""
        neu = {'art': 'bild', 'breite': 1328, 'hoehe': 1328, 'schritte': 6, 'turbo': True, 'int8': True}
        roh = self.s._erwartet_roh(neu)
        self.assertEqual(self.s._erwartet(neu), round(roh))  # ohne eigene Läufe unverändert
        self.assertEqual(studio.zeit_gruppe(neu), 'bild|format|0|turbo|-')
        self.s.auftraege = [dict(neu, zustand='fertig', rechenzeit_s=roh * f) for f in (1.2, 1.4, 1.6)]
        self.s.auftraege.append(dict(neu, zustand='fertig', rechenzeit_s=1.0, zwischenspeicher=True))  # zählt nicht
        self.assertEqual(self.s._zeit_korrekturen(), {'standard': 1.4, 'bild|format|0|turbo|-': 1.4})
        self.assertEqual(self.s._erwartet(neu), round(roh * 1.4))
        # Gruppe ohne eigene Läufe: Median aller
        vorlage = {'art': 'bearbeiten', 'groesse_von': 'vorlage', 'aufloesung': 1440, 'schritte': 6, 'turbo': True,
                   'int8': True, 'vorlagen': [{'art': 'bibliothek', 'pfad': 'a.png', 'rolle': 'vorlage'}]}
        self.assertEqual(studio.zeit_gruppe(vorlage), 'bearbeiten|vorlage|1|turbo|-')
        self.assertEqual(self.s._erwartet(vorlage), round(self.s._erwartet_roh(vorlage) * 1.4))
        self.assertEqual(self.s.einstellungen()['zeit_korrektur']['standard'], 1.4)
        # Ausreißer werden begrenzt
        self.s.auftraege = [dict(neu, zustand='fertig', rechenzeit_s=roh * 9) for _ in range(3)]
        self.assertEqual(self.s._zeit_korrekturen()['standard'], 4.0)

    def test_zeitlupe_und_freistellen(self):
        """Seit 09.10.2026: Video-Hilfsarten ohne MiniMax: ein Video als „original“, kein Prompt, keine Stufe."""
        ori = [self.clip('Video_00001_.mp4', 'original')]
        d = {'art': 'video_zeitlupe', 'projekt': 'Praxis', 'faktor': 2, 'vorlagen': ori}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT):
            code, a = self.s.erzeugen(d)
            self.assertEqual(code, 400)
            self.assertIn('RIFE', a['fehler'])
            with mock.patch.object(self.s, '_modell_da', return_value=True):
                e = self.s.einstellungen()
                self.assertEqual((e['zeitlupe_verfuegbar'], e['video_freistellen_verfuegbar'], e['video_freistellen_motiv']),
                                 (True, True, 'person'))
                code, a = self.s.erzeugen(dict(d, anzahl=3))
                self.assertEqual((code, len(a['neu'])), (200, 1))  # gleiche Eingabe, gleiches Ergebnis
                j = self.s._finden(a['neu'][0])
                self.assertEqual((j['bilder'], j['quell_bilder'], j['faktor'], j['variation'], j['schritte'], j['prompt']),
                                 (247, 124, 2, 0, None, ''))
                self.assertEqual((self.s._erwartet(j), self.s._bedarf(j)), (round(3 + 0.03 * 247), {'fest': 4096}))
                m = self.s._meta(j)
                self.assertEqual((m['modell'], m['faktor'], m['laenge_bilder'], m['quell_bilder']), ('RIFE 4.25', 2, 247, 124))
                j = self.s._finden(self.s.erzeugen(dict(d, faktor='1,5'))[1]['neu'][0])
                self.assertEqual((j['faktor'], j['bilder']), (1.5, 185))
                for falsch, wort in ((dict(d, faktor=3), 'langsamer'), (dict(d, vorlagen=[]), 'Video wählen'),
                                     (dict(d, vorlagen=[self.clip('Bild_00001_.png', 'original')]), 'falsche Art'),
                                     (dict(d, vorlagen=[self.clip('Lang_00001_.mp4', 'original')]), '60 s')):
                    code, a = self.s.erzeugen(falsch)
                    self.assertEqual(code, 400, falsch)
                    self.assertIn(wort, a['fehler'])
                # Freistellen: Motiv mit Standard, Verfahren aus der Einstellung
                f = self.s._finden(self.s.erzeugen({'art': 'video_freistellen', 'projekt': 'Praxis', 'vorlagen': ori})[1]['neu'][0])
                self.assertEqual((f['motiv'], f['verfahren'], f['bilder'], self.s._erwartet(f), self.s._bedarf(f)),
                                 ('person', 'kombi', 124, round(10 + 0.3 * 124), {'fest': 8192}))
                self.assertEqual(self.s._meta(f)['modell'], 'SAM3 + BiRefNet')
                f = self.s._finden(self.s.erzeugen({'art': 'video_freistellen', 'motiv': ' dog ', 'vorlagen': ori})[1]['neu'][0])
                self.assertEqual(f['motiv'], 'dog')

    def test_hilfs_graphen(self):
        v = S['video']
        z = studio.zeitlupe_graph({'faktor': 2, 'bilder': 247}, v, 'P/Zeitlupe', 'a.mp4 [output]')
        self.assertEqual((z['4']['inputs']['multiplier'], z['5']['inputs'], z['9']['inputs']['video']),
                         (2, {'images': ['4', 0], 'fps': 24.0}, ['5', 0]))
        z = studio.zeitlupe_graph({'faktor': 1.5, 'bilder': 185}, v, 'P/Zeitlupe', 'a.mp4 [output]')
        self.assertEqual((z['4']['inputs']['multiplier'], z['6']['inputs']['fps'], z['7']['inputs']['num_frames'],
                          z['5']['inputs']['images']), (3, 72.0, 185, ['8', 0]))
        self.assertEqual([studio.zeitlupe_laenge(124, f) for f in (2, 1.5)], [247, 185])
        k = studio.video_freistellen_graph({'motiv': 'person', 'verfahren': 'kombi'}, v, 'P/Frei', 'a.mp4 [output]')
        self.assertEqual((k['8']['inputs']['destination'], k['8']['inputs']['source'], k['20']['inputs']['mask'],
                          k['22']['class_type'], k['22']['inputs']['codec'], k['4']['inputs']['text']),
                         (['71', 0], ['7', 0], ['8', 0], 'SaveWEBM', 'vp9', 'person'))
        self.assertEqual(studio.video_freistellen_graph({'motiv': 'x', 'verfahren': 'sam3'}, v, 'P', 'a')['20']['inputs']['mask'],
                         ['6', 0])
        b = studio.video_freistellen_graph({'motiv': 'x', 'verfahren': 'biref'}, v, 'P', 'a')
        self.assertEqual((b['20']['inputs']['mask'], '5' in b), (['71', 0], False))

    def test_person_tauschen_pruefen(self):
        """Stufe 3q: genau ein Clip und ein Bild; LoRA muss da sein; Zeit mit den Bildern des Clips."""
        d = {'art': 'video_referenz', 'prompt': 'Replace only the man', 'projekt': 'Praxis', 'breite': 960, 'hoehe': 544,
             'schritte': 8, 'tauschen': True,
             'vorlagen': [self.clip('Video_00001_.mp4', 'clip'), self.clip('Bild_00001_.png', 'bild')]}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT):
            code, a = self.s.erzeugen(d)
            self.assertEqual(code, 400)
            self.assertIn('Character-Swap-LoRA', a['fehler'])
            self.assertFalse(self.s.einstellungen()['tauschen_verfuegbar'])
            with mock.patch.object(self.s, '_modell_da', return_value=True):
                e = self.s.einstellungen()
                self.assertEqual((e['tauschen_verfuegbar'], e['tauschen_vorlage'], e['tauschen_wer']),
                                 (True, 'Replace only {wer} in <Video 1>.', 'the woman'))
                code, a = self.s.erzeugen(d)
                j = self.s._finden(a['neu'][0])
                self.assertEqual((code, j['tauschen'], j['ref_bilder'], self.s._meta(j)['tauschen']), (200, True, 124, True))
                self.assertEqual(self.s._erwartet(j), round(30 + 12.4 * 8 * ((124 + 124 + 1) / 124) ** 2))
                for falsch in ([self.clip('Video_00001_.mp4', 'clip')],
                               [self.clip('Bild_00001_.png', 'bild')],
                               [self.clip('Video_00001_.mp4', 'clip'), self.clip('Video_00002_.mp4', 'clip'),
                                self.clip('Bild_00001_.png', 'bild')]):
                    code, a = self.s.erzeugen(dict(d, vorlagen=falsch))
                    self.assertEqual(code, 400, falsch)
                    self.assertIn('genau einen Clip', a['fehler'])
                # ohne Häkchen: wie bisher, aber die Zeit zählt die Clip-Bilder
                j = self.s._finden(self.s.erzeugen(dict(d, tauschen=None))[1]['neu'][0])
                self.assertEqual((j.get('tauschen'), j['ref_bilder']), (None, 124))
                # 8-Schritt-LoRA nur auf Wunsch (neue Aufträge) und nur bei 8 Schritten
                self.assertTrue(self.s.einstellungen()['acc8_verfuegbar'])
                j = self.s._finden(self.s.erzeugen(dict(d, acc8=True, tauschen=None))[1]['neu'][0])
                self.assertEqual((j['acc8'], self.s._meta(j)['acc8']), (True, True))
                self.assertNotIn('acc8', self.s._finden(self.s.erzeugen(dict(d, acc8=True, tauschen=None, schritte=20))[1]['neu'][0]))
                self.assertNotIn('acc8', self.s._finden(self.s.erzeugen(dict(d, acc8=True))[1]['neu'][0]))  # nicht beim Tauschen
                self.assertNotIn('acc8', self.s._finden(self.s.erzeugen(d)[1]['neu'][0]))

    def test_veraenderte_quelle_bricht_vor_der_uebergabe_ab(self):
        code, a = self.erzeugen()
        j = self.s._finden(a['neu'][0])
        quelle = os.path.join(self.wurzel, 'Praxis', 'Video_00001_.mp4')
        mp4_video_bauen(quelle, fuellung=b'\1' * 64)  # gleiche Maße, anderer Inhalt (etwa ein neu vergebener Name)
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT), \
                mock.patch.object(self.s, '_comfy_rechnen') as rechnen:
            with self.assertRaises(studio.Fehler) as f:
                self.s._rechnen(j, None)
            self.assertIn('verändert oder ersetzt', str(f.exception))
            os.remove(quelle)
            with self.assertRaises(studio.Fehler) as f:
                self.s._rechnen(j, None)
            self.assertIn('gibt es nicht mehr', str(f.exception))
        rechnen.assert_not_called()


class Uhr:
    """Simulierte Zeit für Warteschleifen: sleep rückt die Uhr vor."""

    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


class ComfyWarten(unittest.TestCase):
    """Warten bis zum Stillstand (Stufe 3m, gilt für alle Aufträge): keine Antwort ist kein Stillstand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI', 'studio_ordner': self.tmp.name,
                             'bedarf_je_karte_mib': 1}]}
        with mock.patch('threading.Thread'):
            self.s = studio.Studio({'studio': dict(S, ordner=os.path.join(self.tmp.name, 'Studio'))}, zc, self.tmp.name,
                                   mock.MagicMock(), mock.MagicMock())
        self.uhr = Uhr()
        self.beginn = self.uhr.t
        for name in ('time', 'sleep'):
            p = mock.patch.object(studio.time, name, getattr(self.uhr, name))
            p.start()
            self.addCleanup(p.stop)
        self.a = {'id': 'x1', 'art': 'video_text', 'bilder': 124, 'schritte': 8, 'breite': 960, 'hoehe': 544}
        self.meldungen = []
        schritt = self.s._schritt
        self.s._schritt = lambda a, s, m: (self.meldungen.append(m), schritt(a, s, m))

    def tearDown(self):
        self.tmp.cleanup()

    def stumm_bis(self, sekunden):
        def anfrage(pfad, daten=None, timeout=10):
            if pfad == '/prompt':
                return {'prompt_id': 'p1'}
            if self.uhr.t < self.beginn + sekunden:
                raise studio.ComfyAus('keine Antwort')
            return {'p1': {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {}}}
        return anfrage

    def test_rechnen_wartet_ohne_antwort_solange_comfyui_lebt(self):
        for beendet in (False, None):  # lebt bzw. nicht feststellbar (etwa leere Portliste): beides kein Stillstand
            self.uhr.t = self.beginn
            with mock.patch.object(self.s, '_comfy_anfrage', side_effect=self.stumm_bis(150)), \
                    mock.patch.object(studio.winapi, 'prozess_beendet', return_value=beendet):
                eintrag = self.s._comfy_rechnen_mit(self.a, {}, {}, {'id': 'anm'}, 'handle')
            self.assertTrue(eintrag['status']['completed'])
            self.assertGreaterEqual(self.uhr.t - self.beginn, 150)
            self.assertIn('ComfyUI antwortet gerade nicht; der Auftrag wartet …', self.meldungen)
            self.assertEqual(self.a['meldung'], 'Rechnet …')
        self.assertGreaterEqual(self.s.zentrale.halten.call_count, 12)  # Anmeldung alle 20 s verlängert

    def test_bestaetigtes_ende_beendet_das_warten(self):
        with mock.patch.object(self.s, '_comfy_anfrage', side_effect=self.stumm_bis(10 ** 6)), \
                mock.patch.object(studio.winapi, 'prozess_beendet', side_effect=lambda h: self.uhr.t > self.beginn + 50):
            with self.assertRaises(studio.ComfyAus):
                self.s._comfy_rechnen_mit(self.a, {}, {}, None, 'handle')
        self.assertLess(self.uhr.t - self.beginn, 60)

    def test_abbrechen_wartet_bis_comfyui_steht(self):
        gesendet = []

        def anfrage(pfad, daten=None, timeout=10):
            if pfad == '/queue' and daten is None:
                return {'queue_running': [[0, 'p1']] if self.uhr.t < self.beginn + 150 else [], 'queue_pending': []}
            gesendet.append(pfad)
            return {}
        with mock.patch.object(self.s, '_comfy_anfrage', side_effect=anfrage):
            self.s._comfy_abbrechen(self.a, 'p1', {'id': 'anm'}, 'handle')
        self.assertGreaterEqual(self.uhr.t - self.beginn, 150)
        self.assertEqual(gesendet, ['/interrupt'] * 5)  # alle 30 s erneut
        self.assertTrue(any('hört noch nicht auf' in m for m in self.meldungen))
        self.assertGreaterEqual(self.s.zentrale.halten.call_count, 6)

    def test_abbrechen_ohne_antwort_nur_bei_bestaetigtem_ende(self):
        with mock.patch.object(self.s, '_comfy_anfrage', side_effect=studio.ComfyAus('weg')), \
                mock.patch.object(studio.winapi, 'prozess_beendet',
                                  side_effect=lambda h: True if self.uhr.t >= self.beginn + 200 else None):
            self.s._comfy_abbrechen(self.a, 'p1', None, None)
        self.assertGreaterEqual(self.uhr.t - self.beginn, 200)

    def test_prozess_handle_wird_gehalten_und_geschlossen(self):
        with mock.patch.object(studio.winapi, 'lauschende_ports', return_value=[]):
            self.assertIsNone(self.s._comfy_prozess())
        with mock.patch.object(studio.winapi, 'lauschende_ports', side_effect=OSError):
            self.assertIsNone(self.s._comfy_prozess())
        with mock.patch.object(studio.winapi, 'lauschende_ports', return_value=[('127.0.0.1', 2, 7), ('127.0.0.1', 1, 4242)]), \
                mock.patch.object(studio.winapi, 'prozess_oeffnen', return_value='H') as oeffnen, \
                mock.patch.object(studio.winapi, 'handle_schliessen') as schliessen, \
                mock.patch.object(self.s, '_comfy_rechnen_mit', side_effect=studio.Fehler('x')) as mit:
            with self.assertRaises(studio.Fehler):
                self.s._comfy_rechnen(self.a, {}, {}, None)
        oeffnen.assert_called_once_with(4242)
        self.assertEqual(mit.call_args[0][4], 'H')
        schliessen.assert_called_once_with('H')

    def test_prozessende_wird_nur_bestaetigt_wenn_echt(self):
        w = studio.winapi
        self.assertIsNone(w.prozess_beendet(None))
        h = w.prozess_oeffnen(os.getpid())
        try:
            self.assertIs(w.prozess_beendet(h), False)
        finally:
            w.handle_schliessen(h)
        p = subprocess.Popen([sys.executable, '-c', 'pass'])
        h = w.prozess_oeffnen(p.pid)
        try:
            p.wait(30)
            self.assertIs(w.prozess_beendet(h), True)
        finally:
            w.handle_schliessen(h)


if __name__ == '__main__':
    unittest.main()


class Szenenfolge(unittest.TestCase):
    """Stufe 3p: gemeinsamer Teil + Szenen; Szene 1 eigener Clip, jede weitere verlängert die freigegebene Szene davor."""
    BEREIT = {'laeuft': True, 'ordner_ok': True}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = os.path.join(self.tmp.name, 'Studio')
        os.makedirs(os.path.join(self.wurzel, 'Praxis'))
        self.zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 1, 'name': 'ComfyUI',
                                  'studio_ordner': os.path.join(self.tmp.name, '2wild'), 'bedarf_je_karte_mib': 20000}]}
        self.s = self.studio()
        for name in ('Video_00001_.mp4', 'Video_00002_.mp4'):
            mp4_video_bauen(os.path.join(self.wurzel, 'Praxis', name))
        png_bauen(os.path.join(self.wurzel, 'Praxis', 'Bild_00001_.png'), {})

    def studio(self):
        with mock.patch('threading.Thread'):
            return studio.Studio({'studio': dict(S, ordner=self.wurzel)}, self.zc, self.tmp.name, lambda t: None,
                                 mock.MagicMock())

    def tearDown(self):
        self.tmp.cleanup()

    def neu(self, **d):
        d = dict({'gemeinsam': 'Eine Therapeutin in einem hellen Raum.', 'projekt': 'Praxis', 'breite': 960, 'hoehe': 544,
                  'schritte': 8, 'szenen': [{'text': 'Sie begrüßt.', 'sekunden': 5}, {'text': 'Sie zeigt eine Übung.', 'sekunden': 5}]},
                 **d)
        with mock.patch.object(self.s, 'comfy_zustand', return_value=self.BEREIT):
            return self.s.folge_neu(d)

    def folge(self, fid):
        return next(f for f in self.s.stand()['folgen'] if f['id'] == fid)

    def fertig(self, aid, datei):
        a = self.s._finden(aid)
        a.update(zustand='fertig', dateien=[datei])

    def test_pruefen(self):
        for falsch, wort in ((dict(gemeinsam=''), 'gemeinsamen'), (dict(szenen=[]), 'mindestens'),
                             (dict(szenen=[{'text': ' ', 'sekunden': 5}]), 'Szene 1'),
                             (dict(szenen=[{'text': 'a', 'sekunden': 15}] + [{'text': 'b', 'sekunden': 12}] * 4), '60 s'),
                             (dict(szenen=[{'text': 'a', 'sekunden': 5}, {'text': 'b', 'sekunden': 14}]), 'Szene 2'),
                             (dict(vorlagen=[{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'start'},
                                             {'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'bild'}]), 'nicht beides'),
                             (dict(szenen=[{'text': 'a', 'sekunden': 5}] * 9), 'Höchstens 8')):
            code, a = self.neu(**falsch)
            self.assertEqual(code, 400, falsch)
            self.assertIn(wort, a['fehler'])
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': False, 'ordner_ok': False}):
            self.assertEqual(self.s.folge_neu({'gemeinsam': 'x', 'szenen': [{'text': 'a', 'sekunden': 5}], 'breite': 960,
                                               'hoehe': 544})[0], 409)
        self.assertEqual(self.s.folgen, [])

    def test_ablauf_mit_pruefen(self):
        code, r = self.neu()
        self.assertEqual(code, 200)
        f = self.folge(r['id'])
        a = self.s._finden(r['neu'][0])
        self.assertEqual((f['zustand'], f['szene'], a['art'], a['bilder'], a['folge']),
                         ('laeuft', 0, 'video_text', 124, {'id': r['id'], 'szene': 0, 'szenen': 2}))
        self.assertEqual(a['prompt'], 'Eine Therapeutin in einem hellen Raum.\n\nSie begrüßt.\n\nOhne Schnitt.')
        self.assertEqual(self.s._meta(a)['szenenfolge'], {'id': r['id'], 'szene': 1, 'szenen': 2})
        # Szene 1 fertig: die Folge wartet auf „Passt“
        self.fertig(a['id'], 'Praxis/Video_00001_.mp4')
        f = self.folge(r['id'])
        self.assertEqual((f['zustand'], f['datei']), ('pruefen', 'Praxis/Video_00001_.mp4'))
        self.assertEqual(self.s.folge_aktion(r['id'], 'beenden_falsch')[0], 409)
        # „Nochmal“: neuer Versuch derselben Szene mit neuer Nummer
        self.assertEqual(self.s.folge_aktion(r['id'], 'nochmal'), (200, {'ok': True}))
        f = self.folge(r['id'])
        zweit = self.s._finden(f['takes'][0][-1])
        self.assertEqual((len(f['takes'][0]), f['zustand'], zweit['art'], zweit['prompt']), (2, 'laeuft', 'video_text', a['prompt']))
        self.fertig(zweit['id'], 'Praxis/Video_00002_.mp4')
        # „Passt“: Szene 2 verlängert genau das freigegebene Video
        self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 200)
        f = self.folge(r['id'])
        b = self.s._finden(f['takes'][1][0])
        self.assertEqual((f['szene'], f['freigegeben'], f['zustand']), (1, ['Praxis/Video_00002_.mp4'], 'laeuft'))
        self.assertEqual((b['art'], b['modus'], b['vorlagen'][0]['pfad'], b['vorlagen'][0]['rolle'], b['folge']['szene']),
                         ('video_weiter', 'verlaengern', 'Praxis/Video_00002_.mp4', 'ausgang', 1))
        self.assertTrue(b['prompt'].endswith('Sie zeigt eine Übung.\n\nOhne Schnitt.'))
        self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 409)  # läuft noch
        # Fehler: „Nochmal“ geht, „Wiederholen“ in der Auftragsliste ebenso (Zustand folgt dem Auftrag)
        b.update(zustand='fehler', meldung='ComfyUI antwortet nicht mehr.')
        self.assertEqual((self.folge(r['id'])['zustand'], self.folge(r['id'])['meldung']), ('fehler', 'ComfyUI antwortet nicht mehr.'))
        self.assertEqual(self.s.aktion(b['id'], 'wiederholen')[0], 200)
        self.assertEqual(self.folge(r['id'])['zustand'], 'laeuft')
        self.fertig(b['id'], 'Praxis/Video_00001_.mp4')
        self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 200)
        f = self.folge(r['id'])
        self.assertEqual((f['zustand'], f['freigegeben'][-1]), ('fertig', 'Praxis/Video_00001_.mp4'))
        self.assertEqual(self.s.folge_aktion(r['id'], 'nochmal')[0], 409)
        # gespeichert und nach einem Neustart wieder da
        neu = self.studio()
        self.assertEqual([x['zustand'] for x in neu.stand()['folgen']], ['fertig'])
        self.assertEqual(self.s.folge_aktion(r['id'], 'entfernen')[0], 200)
        self.assertEqual(self.s.stand()['folgen'], [])

    def test_ohne_pruefen_laeuft_durch(self):
        code, r = self.neu(pruefen=False, variation=77, realismus=False)
        f = self.folge(r['id'])
        self.assertEqual(self.s._finden(f['takes'][0][0])['variation'], 77)
        self.fertig(f['takes'][0][0], 'Praxis/Video_00001_.mp4')
        f = self.folge(r['id'])
        self.assertEqual((f['zustand'], f['szene']), ('laeuft', 1))
        b = self.s._finden(f['takes'][1][0])
        self.assertEqual((b['art'], b['variation']), ('video_weiter', 77))  # feste Nummer gilt für jede Szene
        self.fertig(b['id'], 'Praxis/Video_00002_.mp4')
        self.assertEqual(self.folge(r['id'])['zustand'], 'fertig')

    def test_schnell_fuer_alle_szenen(self):
        """Seit 17.10.2026: mit Wunsch schnell rechnen alle Szenen mit schnellerer Aufmerksamkeit; ältere Folgen ohne."""
        code, r = self.neu(pruefen=False, schnell=True)
        f = self.folge(r['id'])
        self.assertEqual((code, f['schnell'], self.s._finden(f['takes'][0][0])['schnell']), (200, True, True))
        self.fertig(f['takes'][0][0], 'Praxis/Video_00001_.mp4')
        b = self.s._finden(self.folge(r['id'])['takes'][1][0])
        self.assertEqual((b['art'], b['schnell']), ('video_weiter', True))
        code, r = self.neu()
        f = self.folge(r['id'])
        self.assertNotIn('schnell', f)
        self.assertNotIn('schnell', self.s._finden(f['takes'][0][0]))

    def test_realismus_je_szene(self):
        """Seit 09.10.2026 hat jede Szene ihr eigenes Häkchen; das alte Häkchen für alle gilt weiter."""
        je = [{'text': 'Leerer Raum.', 'sekunden': 5, 'realismus': False}, {'text': 'Sie kommt herein.', 'sekunden': 5, 'realismus': True}]
        with mock.patch.object(self.s, 'realismus_verfuegbar', return_value=True):
            code, r = self.neu(pruefen=False, szenen=je)
            f = self.folge(r['id'])
            self.assertEqual((code, [s['realismus'] for s in f['szenen']], f['realismus']), (200, [False, True], True))
            self.assertNotIn('realismus', self.s._finden(f['takes'][0][0]))
            self.fertig(f['takes'][0][0], 'Praxis/Video_00001_.mp4')
            self.assertTrue(self.s._finden(self.folge(r['id'])['takes'][1][0])['realismus'])
            # altes Häkchen für alle: jede Szene ohne eigene Angabe bekommt es
            code, r = self.neu(realismus=True)
            self.assertEqual([s['realismus'] for s in self.folge(r['id'])['szenen']], [True, True])
            self.assertTrue(self.s._finden(r['neu'][0])['realismus'])
            # Folgen vor dem 09.10.2026 (ohne Angabe je Szene) folgen ihrem Häkchen
            f = self.folge(r['id'])
            for s in f['szenen']:
                del s['realismus']
            self.fertig(r['neu'][0], 'Praxis/Video_00001_.mp4')
            self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 200)
            self.assertTrue(self.s._finden(self.folge(r['id'])['takes'][1][0])['realismus'])
        with mock.patch.object(self.s, 'realismus_verfuegbar', return_value=False):
            code, a = self.neu(szenen=je)
            self.assertEqual(code, 400)
            self.assertIn('Realism-LoRA fehlt', a['fehler'])
        self.assertTrue(self.s.einstellungen()['szenen']['realismus_je_szene'])

    def test_startbild_und_beenden(self):
        code, r = self.neu(vorlagen=[{'art': 'bibliothek', 'pfad': 'Praxis/Bild_00001_.png', 'rolle': 'start'}])
        a = self.s._finden(r['neu'][0])
        self.assertEqual((code, a['art'], a['vorlagen'][0]['rolle']), (200, 'video_bild', 'start'))
        self.assertEqual(self.s.folge_aktion(r['id'], 'beenden'), (200, {'ok': True}))
        self.assertEqual((a['zustand'], self.folge(r['id'])['zustand']), ('abgebrochen', 'abgebrochen'))
        self.assertEqual(self.s.folge_aktion('gibts-nicht', 'passt')[0], 404)

    def test_quelle_fehlt_vor_szene_2(self):
        code, r = self.neu()
        self.fertig(r['neu'][0], 'Praxis/Fehlt_00001_.mp4')  # die Datei ist inzwischen weg
        self.assertEqual(self.folge(r['id'])['zustand'], 'pruefen')
        self.assertEqual(self.s.folge_aktion(r['id'], 'passt')[0], 200)
        f = self.folge(r['id'])
        self.assertEqual((f['zustand'], f['szene']), ('fehler', 1))
        self.assertIn('Szene 2', f['meldung'])
