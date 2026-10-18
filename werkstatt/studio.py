"""Eigenes Studio der Werkstatt: Bilder (Qwen-Image) und Videos (MiniMax-H3) über ComfyUI, Bibliothek mit Projektordnern.

- Ablage: ComfyUI schreibt direkt nach `<Studio>\\<Projekt>\\` (die Zentrale startet ComfyUI mit
  --output-directory). Neben jede Datei kommt `<datei>.json` mit allen Einstellungen. Keine Kopien.
- Die Arbeitsabläufe folgen 2Wild-Image-Video-Gen-Studio (MIT-Lizenz, Tony DeAngelo), samt Saschas
  Anpassungen: CFG 1.0, „Max“ = 40 Schritte. Die Karten wählt das Studio je Auftrag nach freiem Platz (seit
  14.10.2026, zwei RTX 3090): ein Bild möglichst ganz auf einer Karte, sonst Diffusionsmodell auf der einen,
  Text-Encoder und VAE auf der anderen; Videos immer so geteilt.
- Ein Auftrag nach dem anderen und nie neben einer Transkription oder einem lokalen Sprachmodell
  (gemeinsame GPU-Sperre). Vorher fragt das Studio die Modellzentrale nach Platz.
- Ältere Dateien (2Wild, ComfyUI) werden über ihre Metadaten erschlossen: ComfyUI legt den
  Arbeitsablauf samt Prompt in PNG und MP4 ab; eigene Bilder tragen zusätzlich den Eintrag „werkstatt“.
- Stelle verbessern: nur die markierte Stelle wird neu gerechnet (Ausschnitt, Latent-Maske) und weich ins
  Original gesetzt; alles außerhalb bleibt Pixel für Pixel gleich. Das Original wird nie verändert.
"""
import hashlib
import json
import math
import os
import random
import re
import secrets
import shutil
import struct
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

from gemeinsam import winapi

from . import platz, quellen

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
FORMAT = 'werkstatt-studio/1'
BILD_ENDUNGEN = ('.png', '.jpg', '.jpeg', '.webp')
VIDEO_ENDUNGEN = ('.mp4', '.webm', '.mov')
MEDIEN_TYPEN = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
                '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.glb': 'model/gltf-binary'}
OFFEN = ('wartet', 'laeuft')
BILD_ARTEN = ('bild', 'bearbeiten', 'verbessern', 'freistellen', 'pose')
HILFS_ARTEN = ('pose',)  # rechnen ohne Qwen (Stufe 3l): kein Prompt, keine Qualitätsstufe
# Zeitlupe und Video freistellen (seit 09.10.2026): bearbeiten ein vorhandenes Video ohne MiniMax, ohne Prompt und Stufe.
VIDEO_HILFS_ARTEN = ('video_zeitlupe', 'video_freistellen')
VIDEO_ARTEN = ('video_text', 'video_bild', 'video_referenz', 'video_weiter') + VIDEO_HILFS_ARTEN
# 3D-Modell (Stufe 3t, seit 11.10.2026): Pixal3D aus einem Drehblatt (vier Ansichten nebeneinander), einem Bild oder
# Einzelansichten – ohne Qwen und MiniMax. Ergebnis: GLB plus Vorschau-Video (Drehteller) mit gleichem Stamm.
MODELL_ARTEN = ('modell3d',)
MODELL_ENDUNGEN = ('.glb',)
MODELL_ANSICHTEN = ('vorn', 'links', 'hinten', 'rechts')
_WINDOWS_NAMEN = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
AUSGABE_FALSCH = ('ComfyUI speichert noch in seinen alten Ausgabeordner. Bitte Bild & Video in der Modellzentrale '
                  'einmal beenden und neu starten; danach landen die Bilder direkt im Studio.')
COMFY_AUS = 'Bild & Video ist aus. Bitte in der Modellzentrale starten.'


class Fehler(Exception):
    pass


class Abgebrochen(Exception):
    pass


class ComfyAus(Exception):
    pass


# ---------------------------------------------------------------- Namen und Pfade

def projektname(name, reserviert=()):
    """Bereinigter Name für einen Projektordner oder ValueError mit verständlichem Grund."""
    name = re.sub(r'\s+', ' ', str(name or '')).strip().strip('.').strip()
    if not name:
        raise ValueError('Bitte einen Namen für das Projekt eingeben.')
    if len(name) > 60:
        raise ValueError('Der Name ist zu lang (höchstens 60 Zeichen).')
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError('Diese Zeichen gehen in Ordnernamen nicht: < > : " / \\ | ? *')
    if name.startswith('_') or name.split('.')[0].upper() in _WINDOWS_NAMEN \
            or name.lower() in {r.lower() for r in reserviert}:
        raise ValueError(f'„{name}“ ist als Projektname nicht möglich.')
    return name


def relativ(pfad, wurzel):
    return os.path.relpath(pfad, wurzel).replace('\\', '/')


def absolut(rel, wurzel):
    """Pfad aus der Bibliothek (relativ, mit /) -> absoluter Pfad in der Wurzel oder None."""
    if not isinstance(rel, str) or not rel or rel.startswith(('/', '\\')) or ':' in rel:
        return None
    pfad = os.path.normpath(os.path.join(wurzel, rel))
    return pfad if quellen.liegt_in(pfad, wurzel) and pfad != os.path.normpath(wurzel) else None


def ist_medium(name):
    return name.lower().endswith(BILD_ENDUNGEN + VIDEO_ENDUNGEN) and not name.startswith(('.', '_'))


def ist_3d(name):
    """3D-Datei eines Modells (liegt neben ihrem Vorschau-Video, erscheint nicht als eigene Kachel)."""
    return name.lower().endswith(MODELL_ENDUNGEN) and not name.startswith(('.', '_'))


def freier_name(ordner, name):
    """Dateiname, der im Ordner noch nicht belegt ist (auch nicht als Begleitdatei)."""
    basis, endung = os.path.splitext(name)
    kandidat, n = name, 2
    while os.path.exists(os.path.join(ordner, kandidat)) or os.path.exists(os.path.join(ordner, kandidat + '.json')):
        kandidat = f'{basis} ({n}){endung}'
        n += 1
    return kandidat


# ---------------------------------------------------------------- Arbeitsabläufe (nach 2Wild)

def qwen_dateien(e, s):
    """-> (Diffusionsmodell, Text-Encoder) eines Auftrags. Mit `int8` (Stufe 3l, nur auf ausdrücklichen Wunsch neuer
    Aufträge) die INT8-Fassungen von Comfy-Org: gemessen rund doppelt so schnell mit gleichwertigen Bildern und
    9–10 statt 15–17 GiB auf der 3090. Ältere Aufträge ohne das Feld rechnen weiter mit BF16 und bleiben pixelgleich."""
    m = s['modelle']
    t = s.get('turbo') or {}
    if e.get('turbo_modell') and t.get('modell'):
        # Seit 11.10.2026: offizielles Turbo-Modell von Qwen (INT8), Text-Encoder wie bei INT8.
        return t['modell'], m.get('clip_int8') or m['clip']
    if e.get('int8') and m.get('unet_int8'):
        return m['unet_int8'], m.get('clip_int8') or m['clip']
    return m['unet'], m['clip']


def _qwen_grund(e, s):
    """Gemeinsamer Teil der Qwen-Abläufe: Modelle auf ihren Karten, Sampler, Dekodieren (ohne Text und Latent)."""
    m, g = s['modelle'], s['geraete']
    unet, clip = qwen_dateien(e, s)
    return {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': unet, 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': clip, 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['vae']}},
        '20': {'class_type': 'SelectModelDevice', 'inputs': {'model': ['1', 0], 'device': g['modell']}},
        '21': {'class_type': 'SelectCLIPDevice', 'inputs': {'clip': ['2', 0], 'device': g['clip']}},
        '22': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['3', 0], 'device': g['vae']}},
        '7': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['20', 0], 'shift': s['shift']}},
        '8': {'class_type': 'KSampler', 'inputs': {
            'model': ['7', 0], 'seed': e['variation'], 'steps': e['schritte'], 'cfg': e['cfg'],
            'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '9': {'class_type': 'VAEDecode', 'inputs': {'samples': ['8', 0], 'vae': ['22', 0]}},
    }


def turbo_sigmas(t, breite, hoehe):
    """Zeitplan der Turbo-LoRA (Modellkarte Viggle v0.2.1): feste Stützstellen, verschoben mit dem offiziellen
    dynamischen Zeitplan von Qwen 2.1 (mu wächst mit der Zahl der Bild-Token), am Ende 0."""
    token = (int(breite) // 16) * (int(hoehe) // 16)
    mu = t['mu_basis'] + (t['mu_max'] - t['mu_basis']) * (token - t['token_basis']) / (t['token_max'] - t['token_basis'])
    m = math.exp(mu)
    return ', '.join(f'{m / (m + (1 / x - 1)):.6f}' for x in t['sigmas']) + ', 0'


def _mit_turbo(graph, s, breite, hoehe, modell=False):
    """Turbo-LoRA ans Modell hängen und den Sampler durch den festen Zeitplan ersetzen (6 statt 20–40 Schritte).
    Mit `modell` (seit 11.10.2026) rechnet das offizielle Turbo-Modell (qwen_dateien) ohne LoRA mit seinem trainierten
    8-Schritt-Zeitplan. Erwartet einen fertig verdrahteten KSampler '8'; das Ergebnis bleibt unter '8' (für VAEDecode)."""
    t = s['turbo']
    k = graph['8']['inputs']
    if modell:
        sigmas = ', '.join(f'{x:g}' for x in t['modell_sigmas']) + ', 0'
    else:
        graph['24'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['20', 0], 'lora_name': t['lora'],
                                                                     'strength_model': float(t['staerke'])}}
        graph['7']['inputs']['model'] = ['24', 0]
        sigmas = turbo_sigmas(t, breite, hoehe)
    graph.update({
        '40': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'euler'}},
        '41': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': k['seed']}},
        # CFG 1 wie im Studio üblich: nur der positive Text zählt.
        '42': {'class_type': 'BasicGuider', 'inputs': {'model': ['7', 0], 'conditioning': k['positive']}},
        '43': {'class_type': 'ManualSigmas', 'inputs': {'sigmas': sigmas}},
    })
    sigmas = ['43', 0]
    if k['denoise'] < 1:  # Verbessern mit „viel“ oder „wenig“: nur der untere Teil des Zeitplans
        graph['44'] = {'class_type': 'SplitSigmasDenoise', 'inputs': {'sigmas': ['43', 0], 'denoise': k['denoise']}}
        sigmas = ['44', 1]
    graph['8'] = {'class_type': 'SamplerCustomAdvanced', 'inputs': {
        'noise': ['41', 0], 'guider': ['42', 0], 'sampler': ['40', 0], 'sigmas': sigmas, 'latent_image': k['latent_image']}}
    return graph


def _mit_details(graph, s):
    """Detail-LoRA zwischen Modell (bzw. Turbo-LoRA) und Shift hängen: frischt überbelichtete, unscharfe oder
    komprimierte Fotos auf. Nach `_mit_turbo` aufrufen, damit beide LoRAs hintereinander wirken."""
    d = s['details']
    graph['25'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
        'model': graph['7']['inputs']['model'], 'lora_name': d['lora'], 'strength_model': float(d['staerke'])}}
    graph['7']['inputs']['model'] = ['25', 0]
    return graph


def _mit_schnell(graph, s):
    """Schnellere Aufmerksamkeit (Kernknoten ModelAttentionBackend, INT8) zwischen Modell bzw. LoRAs und Shift hängen.
    Als letzter Schritt eines Ablaufs aufrufen, damit Turbo- und Detail-LoRA davor bleiben. Nur für Aufträge mit
    `schnell`, sonst ändern sich die Pixel älterer Bilder bei „Nochmal“ (Stufe 3k: rund 10 % schneller, gleichwertig)."""
    a = s.get('schnelle_aufmerksamkeit') or {}
    graph['26'] = {'class_type': 'ModelAttentionBackend', 'inputs': {
        'model': graph['7']['inputs']['model'], 'attention': a.get('backend') or 'comfy kitchen attention'}}
    graph['7']['inputs']['model'] = ['26', 0]
    return graph


def durchsichtig_prompt(s, beschreibung):
    """Rahmen-Prompt für ein neues Bild mit durchsichtigem Hintergrund (Vorlage aus der ComfyUI-Vorlage für Qwen 2.1)."""
    return s['durchsichtig']['vorlage'].replace('{beschreibung}', str(beschreibung or '').strip().rstrip('.'))


def durchsichtig_beschreibung(vorlage, prompt):
    """Umkehrung von durchsichtig_prompt: die Beschreibung aus einem gerahmten Prompt, sonst None."""
    vorne, _, hinten = vorlage.partition('{beschreibung}')
    if isinstance(prompt, str) and prompt.startswith(vorne) and prompt.endswith(hinten) and len(prompt) > len(vorne) + len(hinten):
        return prompt[len(vorne):len(prompt) - len(hinten)].strip()
    return None


def _mit_durchsichtig(graph, s):
    """Neues Bild mit durchsichtigem Hintergrund aufräumen, nur Kernknoten. Qwen liefert echte Transparenz, lässt aber einen
    fast unsichtbaren Schleier (Deckung bis etwa 2 %) und legt Lila unter die durchsichtigen Stellen. Deckung bis
    `rest_bis` wird 0, darüber wird sie auf 0–1 gestreckt (Kanten bleiben weich); ganz durchsichtige Stellen bekommen
    Weiß wie beim Freistellen (JPEG und Programme ohne Transparenz zeigen dann Weiß statt Lila)."""
    t = float(s['durchsichtig']['rest_bis'])

    def maske(op, a, b):
        return {'class_type': 'MaskComposite', 'inputs': {'destination': a, 'source': b, 'x': 0, 'y': 0, 'operation': op}}
    graph.update({
        '80': {'class_type': 'SplitImageWithAlpha', 'inputs': {'image': ['9', 0]}},
        '81': {'class_type': 'InvertMask', 'inputs': {'mask': ['80', 1]}},  # Deckung (1 = deckend)
        '82': {'class_type': 'SolidMask', 'inputs': {'value': t, 'width': 4096, 'height': 4096}},
        '83': maske('subtract', ['81', 0], ['82', 0]),  # Schleier bis rest_bis fällt auf 0
        '84': {'class_type': 'SolidMask', 'inputs': {'value': t / (1 - t), 'width': 4096, 'height': 4096}},
        '85': maske('multiply', ['83', 0], ['84', 0]),
        '86': maske('add', ['83', 0], ['85', 0]),       # (Deckung − rest_bis) / (1 − rest_bis)
        '87': {'class_type': 'InvertMask', 'inputs': {'mask': ['86', 0]}},  # wieder Durchsichtigkeit
        '93': {'class_type': 'ThresholdMask', 'inputs': {'mask': ['87', 0], 'value': 0.999}},  # ganz durchsichtig
        '90': {'class_type': 'GetImageSize', 'inputs': {'image': ['80', 0]}},
        '94': {'class_type': 'EmptyImage', 'inputs': {'width': ['90', 0], 'height': ['90', 1], 'batch_size': 1,
                                                      'color': 0xFFFFFF}},
        '95': {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['80', 0], 'source': ['94', 0],
                                                                'x': 0, 'y': 0, 'resize_source': False, 'mask': ['93', 0]}},
        '91': {'class_type': 'JoinImageWithAlpha', 'inputs': {'image': ['95', 0], 'alpha': ['87', 0]}},
    })
    graph['10']['inputs']['images'] = ['91', 0]
    return graph


AUSFORMULIEREN_NUTZER = '\n<|im_start|>user\n'
AUSFORMULIEREN_ENDE = '<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n'


def ausformulieren_text(system, wunsch):
    """Chat-Rahmen für den Prompt-Enhancer (Qwen3.5 ohne „Denken“): Systemtext der ComfyUI-Vorlage und der Wunsch."""
    return system.strip() + AUSFORMULIEREN_NUTZER + str(wunsch or '').strip() + AUSFORMULIEREN_ENDE


def ausformulieren_wunsch(text):
    """Umkehrung von ausformulieren_text: der Wunsch aus dem Chat-Rahmen, sonst None."""
    if isinstance(text, str) and AUSFORMULIEREN_NUTZER in text and text.endswith(AUSFORMULIEREN_ENDE):
        return text.rsplit(AUSFORMULIEREN_NUTZER, 1)[1][:-len(AUSFORMULIEREN_ENDE)].strip()
    return None


def _mit_ausformulieren(graph, e, s, system):
    """Prompt-Enhancer vor das Bild hängen (Stufe 3l): TextGenerate schreibt aus dem Wunsch eine ausführliche englische
    Bildbeschreibung, die statt des Wunsches in den Text-Encoder geht; PreviewAny (Knoten 63) liefert sie der Werkstatt.
    Gleiche Variationsnummer = gleicher Text (Stichprobe mit derselben Nummer), also auch dasselbe Bild."""
    a = s['ausformulieren']
    graph.update({
        '60': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': a['modell'], 'type': 'stable_diffusion', 'device': 'default'}},
        '61': {'class_type': 'SelectCLIPDevice', 'inputs': {'clip': ['60', 0], 'device': a.get('geraet') or 'gpu:0'}},
        '62': {'class_type': 'TextGenerate', 'inputs': {
            'clip': ['61', 0], 'prompt': ausformulieren_text(system, e['prompt']), 'max_length': int(a.get('max_laenge', 2048)),
            'sampling_mode': 'on', 'sampling_mode.temperature': 1.0, 'sampling_mode.top_k': 20, 'sampling_mode.top_p': 0.95,
            'sampling_mode.min_p': 0.0, 'sampling_mode.repetition_penalty': 1.05, 'sampling_mode.seed': int(e['variation']),
            'sampling_mode.presence_penalty': 0.0, 'thinking': False, 'use_default_template': False, 'mtp': 'auto'}},
        '63': {'class_type': 'PreviewAny', 'inputs': {'source': ['62', 0]}},
    })
    graph['4']['inputs']['text'] = ['62', 0]
    return graph


def bild_graph(e, s, praefix, vorlagen=(), system=None):
    """ComfyUI-Arbeitsablauf für Qwen-Image 2.1: neues Bild oder Bild bearbeiten (mit Vorlagen).

    e: Einstellungen des Auftrags (prompt, negativ, breite, hoehe, schritte, cfg, variation, art).
    s: cfg['studio']; praefix: '<Projekt>/Bild' relativ zum Ausgabeordner von ComfyUI.
    vorlagen: Namen für LoadImage ('<rel> [output]' aus der Bibliothek oder hochgeladene Namen).
    system: Systemtext des Prompt-Enhancers (nur für Aufträge mit `ausformulieren`).
    """
    graph = _qwen_grund(e, s)
    graph['10'] = {'class_type': 'SaveImage', 'inputs': {'images': ['9', 0], 'filename_prefix': praefix}}
    if e['art'] == 'bearbeiten':
        if not vorlagen:
            raise Fehler('Zum Bearbeiten fehlt mindestens eine Vorlage.')
        # TextEncodeQwenImage21 liest die Vorlagen und liefert positiv, negativ und das passende Latent. Die Auflösung
        # bestimmt die Größe im Seitenverhältnis von Vorlage 1 (größer = hochskalieren); ältere Aufträge: Standard.
        aufl = int(e.get('aufloesung') or s['bearbeiten_aufloesung'])
        graph['4'] = {'class_type': 'TextEncodeQwenImage21', 'inputs': {
            'clip': ['21', 0], 'prompt': e['prompt'], 'negative_prompt': e.get('negativ', ''),
            'resolution': aufl, 'vae': ['22', 0]}}
        latent = ['4', 2]  # Größe wie Vorlage 1 (Standard; so bleibt eine Änderung genau an ihrem Platz)
        if e.get('groesse_von') == 'format' and e.get('breite') and e.get('hoehe'):
            # Eigenes Format, etwa für ein Charakterblatt: neue Fläche statt der Größe von Vorlage 1.
            graph['6'] = {'class_type': 'EmptySD3LatentImage',
                          'inputs': {'width': e['breite'], 'height': e['hoehe'], 'batch_size': 1}}
            latent = ['6', 0]
        graph['8']['inputs'].update(positive=['4', 0], negative=['4', 1], latent_image=latent)
        for i, name in enumerate(list(vorlagen)[:int(s['max_vorlagen'])], start=1):
            graph[str(100 + i)] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            graph['4']['inputs'][f'images.image_{i}'] = [str(100 + i), 0]
    else:
        # Durchsichtiger Hintergrund: die Beschreibung kommt in den Rahmen-Prompt, gespeichert bleibt die Beschreibung.
        text = durchsichtig_prompt(s, e['prompt']) if e.get('durchsichtig') else e['prompt']
        graph['4'] = {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['21', 0], 'text': text}}
        graph['5'] = {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['21', 0], 'text': e.get('negativ', '')}}
        graph['6'] = {'class_type': 'EmptySD3LatentImage',
                      'inputs': {'width': e['breite'], 'height': e['hoehe'], 'batch_size': 1}}
        graph['8']['inputs'].update(positive=['4', 0], negative=['5', 0], latent_image=['6', 0])
    if e.get('turbo'):
        # Größe für den Zeitplan: eigenes Format bzw. neues Bild, sonst etwa die Bearbeitungsauflösung von Vorlage 1.
        b, h = (e['breite'], e['hoehe']) if e.get('breite') and e.get('hoehe') and graph.get('6') else \
            (int(e.get('aufloesung') or s['bearbeiten_aufloesung']),) * 2
        _mit_turbo(graph, s, b, h, e.get('turbo_modell'))
    if e.get('details') and e['art'] == 'bearbeiten':
        _mit_details(graph, s)
    if e.get('durchsichtig') and e['art'] == 'bild':
        _mit_durchsichtig(graph, s)
    elif e.get('ausformulieren') and e['art'] == 'bild' and system:
        _mit_ausformulieren(graph, e, s, system)
    if e.get('schnell'):
        _mit_schnell(graph, s)
    return graph


def freistellen_prompt(s, motiv):
    f = s['freistellen']
    return f['vorlage'].replace('{motiv}', str(motiv or '').strip() or f['motiv_standard'])


def freistellen_graph(e, s, praefix, original):
    """Freistellen mit Qwen-Image 2.1, nur Kernknoten: Qwen rechnet eine Fassung mit transparentem Hintergrund, genommen
    wird nur deren Maske. Schwache Reste (Deckung bis `rest_bis`) fallen weg, darüber steigt die Deckung weich an; ein
    schmaler Rand (`kante_px`) fällt weg, sonst bleibt ein heller Saum aus Hintergrundfarbe. Die Maske kommt in
    Originalgröße auf die Originalpixel, das Motiv bleibt also genau wie im Original; ganz durchsichtige Stellen werden
    weiß (als Vorlage beim Bearbeiten sieht Qwen dann das Motiv auf Weiß statt des alten Hintergrunds)."""
    aufl = int(s['bearbeiten_aufloesung'])
    rest = float(s['freistellen']['rest_bis'])
    kante = int(s['freistellen'].get('kante_px', 1))
    graph = _qwen_grund(e, s)
    graph['8']['inputs'].update(positive=['4', 0], negative=['4', 1], latent_image=['4', 2])

    def maske(op, a, b):
        return {'class_type': 'MaskComposite', 'inputs': {'destination': a, 'source': b, 'x': 0, 'y': 0, 'operation': op}}
    graph.update({
        '101': {'class_type': 'LoadImage', 'inputs': {'image': original}},
        '4': {'class_type': 'TextEncodeQwenImage21', 'inputs': {
            'clip': ['21', 0], 'prompt': e['prompt'], 'negative_prompt': '', 'resolution': aufl, 'vae': ['22', 0],
            'images.image_1': ['101', 0]}},
        '80': {'class_type': 'SplitImageWithAlpha', 'inputs': {'image': ['9', 0]}},
        '81': {'class_type': 'InvertMask', 'inputs': {'mask': ['80', 1]}},  # Deckung (1 = deckend)
        '82': {'class_type': 'SolidMask', 'inputs': {'value': rest, 'width': 4096, 'height': 4096}},
        '83': maske('subtract', ['81', 0], ['82', 0]),  # Reste bis rest_bis fallen auf 0
        '84': maske('add', ['83', 0], ['83', 0]),       # × 2
        '85': maske('add', ['84', 0], ['84', 0]),       # × 4: ab rest_bis + 0,25 voll deckend
        '86': {'class_type': 'InvertMask', 'inputs': {'mask': ['85', 0]}},  # wieder Durchsichtigkeit
        '92': {'class_type': 'GrowMask', 'inputs': {'mask': ['86', 0], 'expand': kante, 'tapered_corners': True}},
        '87': {'class_type': 'MaskToImage', 'inputs': {'mask': ['92', 0]}},
        '90': {'class_type': 'GetImageSize', 'inputs': {'image': ['101', 0]}},
        '88': {'class_type': 'ImageScale', 'inputs': {'image': ['87', 0], 'upscale_method': 'bilinear',
                                                      'width': ['90', 0], 'height': ['90', 1], 'crop': 'disabled'}},
        '89': {'class_type': 'ImageToMask', 'inputs': {'image': ['88', 0], 'channel': 'red'}},
        '93': {'class_type': 'ThresholdMask', 'inputs': {'mask': ['89', 0], 'value': 0.999}},  # ganz durchsichtig
        '94': {'class_type': 'EmptyImage', 'inputs': {'width': ['90', 0], 'height': ['90', 1], 'batch_size': 1,
                                                      'color': 0xFFFFFF}},
        '95': {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['101', 0], 'source': ['94', 0],
                                                                'x': 0, 'y': 0, 'resize_source': False, 'mask': ['93', 0]}},
        '91': {'class_type': 'JoinImageWithAlpha', 'inputs': {'image': ['95', 0], 'alpha': ['89', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['91', 0], 'filename_prefix': praefix}},
    })
    if e.get('turbo'):
        _mit_turbo(graph, s, aufl, aufl, e.get('turbo_modell'))
    if e.get('schnell'):
        _mit_schnell(graph, s)
    return graph


def freistellen_schnell_graph(e, s, praefix, original):
    """Schnelles Freistellen des Hauptmotivs mit einem eigenen Freistell-Modell (BiRefNet, Kernknoten „Remove
    Background“; Stufe 3l): etwa 1 s statt 15–30 s, feine Haare bleiben als weiche Kante erhalten. Das Motiv behält wie
    beim Qwen-Freistellen seine Originalpixel; ganz durchsichtige Stellen werden weiß. Eine Beschreibung („den Hund“)
    kennt das Modell nicht – dafür stellt Qwen frei (freistellen_graph)."""
    return {
        '101': {'class_type': 'LoadImage', 'inputs': {'image': original}},
        '70': {'class_type': 'LoadBackgroundRemovalModel', 'inputs': {'bg_removal_name': s['freistellen']['schnell_modell']}},
        '71': {'class_type': 'RemoveBackground', 'inputs': {'bg_removal_model': ['70', 0], 'image': ['101', 0]}},  # 1 = Motiv
        '72': {'class_type': 'InvertMask', 'inputs': {'mask': ['71', 0]}},  # 1 = durchsichtig
        '93': {'class_type': 'ThresholdMask', 'inputs': {'mask': ['72', 0], 'value': 0.999}},  # ganz durchsichtig
        '90': {'class_type': 'GetImageSize', 'inputs': {'image': ['101', 0]}},
        '94': {'class_type': 'EmptyImage', 'inputs': {'width': ['90', 0], 'height': ['90', 1], 'batch_size': 1,
                                                      'color': 0xFFFFFF}},
        '95': {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['101', 0], 'source': ['94', 0],
                                                                'x': 0, 'y': 0, 'resize_source': False, 'mask': ['93', 0]}},
        '91': {'class_type': 'JoinImageWithAlpha', 'inputs': {'image': ['95', 0], 'alpha': ['72', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['91', 0], 'filename_prefix': praefix}},
    }


def pose_graph(e, s, praefix, original):
    """Pose-Skelett aus einem Bild (SDPose, Kernknoten; Stufe 3l): farbige Strichfigur auf Schwarz in Originalgröße.
    Als Bild 1 beim Bearbeiten übernimmt Qwen damit eine Haltung (Test 27.09.2026: 12 von 12; aus einem Foto als Bild 1
    früher 1 von 4). Mit `personen` (nur auf ausdrücklichen Wunsch neuer Aufträge) sucht SAM3 zuerst die Personen; SDPose
    zeichnet dann jede in ihrem Rahmen (ohne Rahmen nimmt es das ganze Bild als eine Person)."""
    p = s['pose']
    z = dict({'draw_body': True, 'draw_hands': True, 'draw_face': True, 'draw_feet': True, 'stick_width': 4,
              'face_point_size': 2, 'score_threshold': 0.5, 'draw_head': True}, **(p.get('zeichnen') or {}))
    graph = {
        '101': {'class_type': 'LoadImage', 'inputs': {'image': original}},
        '75': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': p['modell']}},
        '76': {'class_type': 'SDPoseKeypointExtractor', 'inputs': {'model': ['75', 0], 'vae': ['75', 2], 'image': ['101', 0],
                                                                   'batch_size': 16}},
        '77': {'class_type': 'SDPoseDrawKeypoints', 'inputs': dict(z, keypoints=['76', 0])},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['77', 0], 'filename_prefix': praefix}},
    }
    if e.get('personen'):
        pp = p.get('personen') or {}
        graph.update({
            '78': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': s['verbessern']['finden']['modell']}},
            '79': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['78', 1], 'text': pp.get('text', 'person:6')}},
            '96': {'class_type': 'SAM3_Detect', 'inputs': {'model': ['78', 0], 'image': ['101', 0], 'conditioning': ['79', 0],
                                                           'threshold': float(pp.get('schwelle', 0.5)),
                                                           'refine_iterations': 0, 'individual_masks': False}},
        })
        graph['76']['inputs']['bboxes'] = ['96', 1]
    return graph


def finden_graph(s, original, stelle):
    """Stelle per Wort finden (SAM3, Kernknoten; Stufe 3l), etwa „hand“ oder „hand:2“ (englisch am verlässlichsten).
    Die Maske kommt verkleinert (längste Seite `finden.vorschau_px`, Mittelwert der Fläche: jede Überdeckung zählt) als
    Vorschau zurück, dazu die Originalgröße; die Werkstatt rechnet sie auf die Originalgröße hoch (maske_hochrechnen)."""
    f = s['verbessern']['finden']
    return {
        '101': {'class_type': 'LoadImage', 'inputs': {'image': original}},
        '78': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': f['modell']}},
        '79': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['78', 1], 'text': stelle}},
        '96': {'class_type': 'SAM3_Detect', 'inputs': {'model': ['78', 0], 'image': ['101', 0], 'conditioning': ['79', 0],
                                                       'threshold': float(f.get('schwelle', 0.5)),
                                                       'refine_iterations': int(f.get('verfeinern', 2)),
                                                       'individual_masks': False}},
        '97': {'class_type': 'MaskToImage', 'inputs': {'mask': ['96', 0]}},
        '98': {'class_type': 'ImageScaleToMaxDimension', 'inputs': {'image': ['97', 0], 'upscale_method': 'area',
                                                                   'largest_size': int(f.get('vorschau_px', 768))}},
        '99': {'class_type': 'PreviewImage', 'inputs': {'images': ['98', 0]}},
        '90': {'class_type': 'GetImageSize', 'inputs': {'image': ['101', 0]}},
        '88': {'class_type': 'PreviewAny', 'inputs': {'source': ['90', 0]}},  # Breite des Originals
        '89': {'class_type': 'PreviewAny', 'inputs': {'source': ['90', 1]}},  # Höhe des Originals
    }


# ---------------------------------------------------------------- Stelle verbessern

def maske_pruefen(m, grenze=16384):
    """Markierung aus der Oberfläche prüfen -> {'breite', 'hoehe', 'rle'} oder ValueError.

    rle: Lauflängen über alle Pixel, zeilenweise, abwechselnd frei und markiert, beginnend mit frei.
    """
    if not isinstance(m, dict):
        raise ValueError('Bitte zuerst die Stelle markieren.')
    try:
        breite, hoehe = int(m.get('breite')), int(m.get('hoehe'))
    except (TypeError, ValueError):
        raise ValueError('Die Markierung ist ungültig.') from None
    rle = m.get('rle')
    if not (16 <= breite <= grenze and 16 <= hoehe <= grenze) or not isinstance(rle, list) or len(rle) > 4_000_000:
        raise ValueError('Die Markierung ist ungültig.')
    if not all(type(n) is int and n >= 0 for n in rle) or sum(rle) != breite * hoehe:
        raise ValueError('Die Markierung passt nicht zur Bildgröße. Bitte neu markieren.')
    if not any(rle[1::2]):
        raise ValueError('Bitte zuerst die Stelle markieren.')
    return {'breite': breite, 'hoehe': hoehe, 'rle': rle}


def maske_rahmen(m):
    """-> ((x0, y0, x1, y1) um alle markierten Pixel, x1 und y1 ausschließlich; Zahl der markierten Pixel)."""
    b = m['breite']
    x0 = y0 = None
    x1 = y1 = anzahl = pos = 0
    for i, n in enumerate(m['rle']):
        if i % 2 and n:
            za, ze = pos // b, (pos + n - 1) // b
            xa, xe = (pos % b, (pos + n - 1) % b) if za == ze else (0, b - 1)
            x0 = xa if x0 is None else min(x0, xa)
            y0 = za if y0 is None else y0
            x1, y1 = max(x1, xe + 1), ze + 1
            anzahl += n
        pos += n
    return (x0, y0, x1, y1), anzahl


def maske_png(m):
    """Markierung als 8-Bit-Graustufen-PNG, weiß = neu rechnen (für LoadImageMask, Kanal rot)."""
    b, h = m['breite'], m['hoehe']
    pixel = bytearray(b * h)
    pos = 0
    for i, n in enumerate(m['rle']):
        if i % 2 and n:
            pixel[pos:pos + n] = b'\xff' * n
        pos += n
    roh = b''.join(b'\x00' + pixel[y * b:(y + 1) * b] for y in range(h))

    def block(typ, daten):
        return struct.pack('>I', len(daten)) + typ + daten + struct.pack('>I', zlib.crc32(typ + daten))
    return (b'\x89PNG\r\n\x1a\n' + block(b'IHDR', struct.pack('>IIBBBBB', b, h, 8, 0, 0, 0, 0))
            + block(b'IDAT', zlib.compress(roh, 6)) + block(b'IEND', b''))


def png_lesen(daten):
    """8-Bit-PNG ohne Zeilensprung (Graustufen, RGB, RGBA) -> (breite, hoehe, kanäle, Pixel als bytes), nur
    Standardbibliothek. Für kleine Bilder gedacht (Masken-Vorschau von ComfyUI), nicht für ganze Fotos."""
    if daten[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('kein PNG')
    pos, idat, kopf = 8, [], None
    while pos + 8 <= len(daten):
        laenge, typ = struct.unpack('>I4s', daten[pos:pos + 8])
        if typ == b'IHDR':
            kopf = struct.unpack('>IIBBBBB', daten[pos + 8:pos + 21])
        elif typ == b'IDAT':
            idat.append(daten[pos + 8:pos + 8 + laenge])
        elif typ == b'IEND':
            break
        pos += 12 + laenge
    if not kopf:
        raise ValueError('PNG ohne Kopf')
    breite, hoehe, tiefe, farbe, _, _, zeilensprung = kopf
    k = {0: 1, 2: 3, 4: 2, 6: 4}.get(farbe)
    if tiefe != 8 or not k or zeilensprung:
        raise ValueError('PNG-Art nicht unterstützt')
    roh = zlib.decompress(b''.join(idat))
    n = breite * k
    out = bytearray(hoehe * n)
    vorher = bytes(n)
    p = 0
    for y in range(hoehe):
        f, z = roh[p], bytearray(roh[p + 1:p + 1 + n])
        p += 1 + n
        if f == 1:
            for i in range(k, n):
                z[i] = (z[i] + z[i - k]) & 255
        elif f == 2:
            z = bytearray((a + b) & 255 for a, b in zip(z, vorher))
        elif f == 3:
            for i in range(n):
                z[i] = (z[i] + ((z[i - k] if i >= k else 0) + vorher[i]) // 2) & 255
        elif f == 4:
            for i in range(n):
                a, b, c = (z[i - k] if i >= k else 0), vorher[i], (vorher[i - k] if i >= k else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                z[i] = (z[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out[y * n:(y + 1) * n] = z
        vorher = bytes(z)
    return breite, hoehe, k, bytes(out)


_GESETZT = bytes([0] + [1] * 255)  # jeder Wert über 0 zählt als markiert (verkleinerte Maske: Mittelwert der Fläche)


def maske_hochrechnen(breite, hoehe, kanaele, pixel, ziel_breite, ziel_hoehe):
    """Verkleinerte Maske (Bild, Rot > 0 = markiert) auf die Zielgröße bringen (nächster Nachbar)
    -> {'breite', 'hoehe', 'rle'} wie aus der Oberfläche. Arbeitet mit Läufen je Zeile, nicht Pixel für Pixel."""
    gesetzt = pixel[0::kanaele].translate(_GESETZT)
    grenze = [(c * ziel_breite + breite - 1) // breite for c in range(breite + 1)]  # Quellspalte c beginnt bei grenze[c]
    zeilen = []
    for y in range(hoehe):
        zeile, stuecke, x = gesetzt[y * breite:(y + 1) * breite], [], 0
        while True:
            x = zeile.find(1, x)
            if x < 0:
                break
            e = zeile.find(0, x)
            e = breite if e < 0 else e
            stuecke.append((grenze[x], grenze[e]))
            x = e
        zeilen.append(stuecke)
    bereiche = []  # markierte Bereiche [von, bis) über das ganze Bild, zusammenhängende verschmolzen
    for y in range(ziel_hoehe):
        basis = y * ziel_breite
        for a, e in zeilen[y * hoehe // ziel_hoehe]:
            if bereiche and bereiche[-1][1] == basis + a:
                bereiche[-1][1] = basis + e
            else:
                bereiche.append([basis + a, basis + e])
    rle, ende = [], 0
    for a, e in bereiche:
        rle += [a - ende, e - a]
        ende = e
    if ende < ziel_breite * ziel_hoehe or not rle:
        rle.append(ziel_breite * ziel_hoehe - ende)  # endet die Maske markiert, fehlt der letzte freie Lauf (wie im Editor)
    return {'breite': ziel_breite, 'hoehe': ziel_hoehe, 'rle': rle}


def ausschnitt_berechnen(rahmen, breite, hoehe, v):
    """Ausschnitt um die Markierung und die Arbeitsgröße für Qwen -> ({x, y, breite, hoehe}, {breite, hoehe}).

    Der Ausschnitt ist `ausschnitt_faktor` × die lange Seite der Markierung (mindestens `ausschnitt_min`), liegt ganz
    im Bild und enthält die ganze Markierung. Kleine Ausschnitte werden auf etwa `arbeit_min`² vergrößert (so bekommt
    eine kleine Hand genug Pixel), große auf höchstens `arbeit_max`² verkleinert; beides in 32er-Schritten.
    """
    x0, y0, x1, y1 = rahmen
    bw, bh = x1 - x0, y1 - y0
    rand = (float(v['ausschnitt_faktor']) - 1) / 2 * max(bw, bh)
    w = int(round(min(breite, max(bw + 2 * rand, v['ausschnitt_min']))))
    h = int(round(min(hoehe, max(bh + 2 * rand, v['ausschnitt_min']))))
    x = max(0, min(int(round((x0 + x1 - w) / 2)), breite - w))
    y = max(0, min(int(round((y0 + y1 - h) / 2)), hoehe - h))
    ziel = min(max(w * h, v['arbeit_min'] ** 2), v['arbeit_max'] ** 2)
    skala = min(math.sqrt(ziel / (w * h)), v['arbeit_seite_max'] / max(w, h))
    aw, ah = (max(256, int(round(n * skala / 32)) * 32) for n in (w, h))
    return {'x': x, 'y': y, 'breite': w, 'hoehe': h}, {'breite': aw, 'hoehe': ah}


def verbessern_graph(e, s, praefix, original, maske, vorlagen=()):
    """Stelle verbessern (Qwen-Image 2.1, nur Kernknoten), Verfahren aus den Versuchen vom 24.09.2026:
    Ausschnitt um die Markierung auf Arbeitsgröße bringen, mit ihm selbst als Vorlage bearbeiten und nur in der
    (etwas größeren) Markierung neu rechnen, dann mit weichem Rand zurück ins Original. Außerhalb von Markierung,
    Rand und Übergang bleibt jedes Pixel gleich; die Größe ist die des Originals.

    e: Auftrag (prompt, negativ, schritte, cfg, variation, staerke, ausschnitt, arbeit); original und maske: Namen für
    LoadImage bzw. LoadImageMask. vorlagen (Stufe 3n): Namen weiterer Bilder für die Stelle („Bild 2“, etwa ein Porträt
    oder ein Logo); sie gehen auf etwa `vorlage.megapixel` verkleinert dazu, der Ausschnitt bleibt Bild 1 in seiner
    Arbeitsgröße (sonst verschöbe sich die Änderung). Ohne Vorlagen ist der Ablauf derselbe wie vorher.
    """
    v = s['verbessern']
    a, arb = e['ausschnitt'], e['arbeit']
    rand, weich = int(v['rand_px']), int(v['weich_px'])
    # Neu gerechnet wird etwas mehr als die weiche Zone, damit der Übergang nur Neues mit dem Original mischt.
    rechnen_px = math.ceil((rand + weich + 4) * arb['breite'] / a['breite'])
    graph = _qwen_grund(e, s)
    graph['8']['inputs'].update(denoise=float(e.get('staerke') or 1.0), positive=['4', 0], negative=['4', 1],
                                latent_image=['31', 0])

    def auf_arbeitsgroesse(bild, methode):
        return {'class_type': 'ImageScale', 'inputs': {'image': bild, 'upscale_method': methode,
                                                       'width': arb['breite'], 'height': arb['hoehe'], 'crop': 'disabled'}}
    graph.update({
        '50': {'class_type': 'LoadImage', 'inputs': {'image': original}},
        '51': {'class_type': 'LoadImageMask', 'inputs': {'image': maske, 'channel': 'red'}},
        '52': {'class_type': 'PrimitiveBoundingBox', 'inputs': {'x': a['x'], 'y': a['y'], 'width': a['breite'],
                                                                'height': a['hoehe']}},
        '53': {'class_type': 'ImageCropV2', 'inputs': {'image': ['50', 0], 'crop_region': ['52', 0]}},
        '54': auf_arbeitsgroesse(['53', 0], 'lanczos'),
        '55': {'class_type': 'CropMask', 'inputs': {'mask': ['51', 0], 'x': a['x'], 'y': a['y'],
                                                    'width': a['breite'], 'height': a['hoehe']}},
        # Rechenbereich in Arbeitsgröße
        '56': {'class_type': 'MaskToImage', 'inputs': {'mask': ['55', 0]}},
        '57': auf_arbeitsgroesse(['56', 0], 'bilinear'),
        '58': {'class_type': 'ImageToMask', 'inputs': {'image': ['57', 0], 'channel': 'red'}},
        '59': {'class_type': 'GrowMask', 'inputs': {'mask': ['58', 0], 'expand': rechnen_px, 'tapered_corners': True}},
        # Übergang in Originalgröße: Rand dazu, dann weich
        '60': {'class_type': 'GrowMask', 'inputs': {'mask': ['55', 0], 'expand': rand, 'tapered_corners': True}},
        '61': {'class_type': 'MaskToImage', 'inputs': {'mask': ['60', 0]}},
        '62': {'class_type': 'ImageBlur', 'inputs': {'image': ['61', 0], 'blur_radius': weich, 'sigma': weich / 2}},
        '63': {'class_type': 'ImageToMask', 'inputs': {'image': ['62', 0], 'channel': 'red'}},
        '4': {'class_type': 'TextEncodeQwenImage21', 'inputs': {
            'clip': ['21', 0], 'prompt': e['prompt'], 'negative_prompt': e.get('negativ', ''), 'resolution': 0,
            'vae': ['22', 0], 'images.image_1': ['54', 0]}},
        '30': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['54', 0], 'vae': ['22', 0]}},
        '31': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['30', 0], 'mask': ['59', 0]}},
        '64': {'class_type': 'ImageScale', 'inputs': {'image': ['9', 0], 'upscale_method': 'lanczos',
                                                      'width': a['breite'], 'height': a['hoehe'], 'crop': 'disabled'}},
        '65': {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['50', 0], 'source': ['64', 0],
                                                                'x': a['x'], 'y': a['y'], 'resize_source': False,
                                                                'mask': ['63', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['65', 0], 'filename_prefix': praefix}},
    })
    mp = float((v.get('vorlage') or {}).get('megapixel', 1.0))
    for i, name in enumerate(list(vorlagen)[:int((v.get('vorlage') or {}).get('max', 1))]):
        laden, klein = str(110 + 2 * i), str(111 + 2 * i)
        graph[laden] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
        graph[klein] = {'class_type': 'ImageScaleToTotalPixels', 'inputs': {
            'image': [laden, 0], 'upscale_method': 'lanczos', 'megapixels': mp, 'resolution_steps': 32}}
        graph['4']['inputs'][f'images.image_{i + 2}'] = [klein, 0]
    if e.get('turbo'):
        _mit_turbo(graph, s, arb['breite'], arb['hoehe'], e.get('turbo_modell'))
    if e.get('schnell'):
        _mit_schnell(graph, s)
    return graph


def bilder_raster(bilder):
    """H3 rechnet in Längen von 17n+5 Bildern; 124 (~5 s) bis 362 (~15 s) sind trainiert."""
    n = max(7, min(21, int(round((int(bilder) - 5) / 17.0))))
    return 17 * n + 5


def video_graph(e, v, praefix, namen=None):
    """ComfyUI-Arbeitsablauf für MiniMax-H3 (nach 2Wild): aus Text, aus Bild oder mit Referenzen.

    e: Auftrag (art, prompt, breite, hoehe, bilder, schritte, variation, referenz_genau, ton_behalten).
    v: cfg['studio']['video']; namen: {'start', 'ende', 'bilder': [...], 'clips': [...]} als LoadImage-/LoadVideo-Namen.
    Bis `turbo_bis_schritte` hängt die Turbo-LoRA am Modell (wie in 2Wild), darüber nie.
    """
    namen = namen or {}
    m, g = v['modelle'], v['geraete']
    referenz = e['art'] == 'video_referenz'
    graph = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['ref2va' if referenz else 'fl2va'],
                                                     'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': m['clip'], 'type': 'minimax', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['vae_video']}},
        '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': m['vae_audio']}},
        '20': {'class_type': 'SelectModelDevice', 'inputs': {'model': ['1', 0], 'device': g['modell']}},
        '21': {'class_type': 'SelectCLIPDevice', 'inputs': {'clip': ['2', 0], 'device': g['clip']}},
        '22': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['3', 0], 'device': g['vae_video']}},
        '23': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['4', 0], 'device': g['vae_audio']}},
        '9': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'res_multistep'}},
        '10': {'class_type': 'BasicScheduler', 'inputs': {'model': ['20', 0], 'scheduler': 'simple',
                                                          'steps': e['schritte'], 'denoise': 1.0}},
        '11': {'class_type': 'BasicGuider', 'inputs': {'model': ['20', 0], 'conditioning': ['5', 0]}},
        '12': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': e['variation']}},
        '13': {'class_type': 'SamplerCustomAdvanced', 'inputs': {'noise': ['12', 0], 'guider': ['11', 0],
                                                                 'sampler': ['9', 0], 'sigmas': ['10', 0],
                                                                 'latent_image': ['5', 1]}},
        '14': {'class_type': 'VAEDecode', 'inputs': {'samples': ['13', 0], 'vae': ['22', 0]}},
        '15': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['13', 0], 'vae': ['23', 0]}},
        '16': {'class_type': 'CreateVideo', 'inputs': {'images': ['14', 0], 'audio': ['15', 0], 'fps': float(v['fps'])}},
        '17': {'class_type': 'SaveVideo', 'inputs': {'video': ['16', 0], 'filename_prefix': praefix,
                                                     'format': 'auto', 'codec': 'auto'}},
    }
    if referenz:
        bilder, clips = list(namen.get('bilder') or [])[:9], list(namen.get('clips') or [])[:3]
        if not bilder and not clips:
            raise Fehler('Für ein Video mit Referenz fehlt mindestens ein Bild oder Clip.')
        graph['5'] = {'class_type': 'MiniMaxH3ReferenceToVideo', 'inputs': {
            'clip': ['21', 0], 'vae': ['22', 0], 'audio_vae': ['23', 0], 'prompt': e['prompt'],
            'width': e['breite'], 'height': e['hoehe'], 'length': e['bilder'],
            'ref_image_size': e.get('referenz_genau') or 'match'}}
        for i, name in enumerate(bilder):
            graph[str(400 + i)] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            graph['5']['inputs'][f'ref_images.ref_image_{i}'] = [str(400 + i), 0]
        for i, name in enumerate(clips):
            vid, teile = str(300 + i * 2), str(301 + i * 2)
            graph[vid] = {'class_type': 'LoadVideo', 'inputs': {'file': name}}
            graph[teile] = {'class_type': 'GetVideoComponents', 'inputs': {'video': [vid, 0]}}
            graph['5']['inputs'][f'ref_videos.ref_video_{i}'] = [teile, 0]
            if i == 0 and e.get('ton_behalten', True):
                graph['5']['inputs']['ref_video_audios.ref_video_audio_0'] = [teile, 1]
    else:
        graph['5'] = {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {
            'clip': ['21', 0], 'vae': ['22', 0], 'prompt': e['prompt'],
            'width': e['breite'], 'height': e['hoehe'], 'length': e['bilder']}}
        if e['art'] == 'video_bild' and not namen.get('start'):
            raise Fehler('Für ein Video aus einem Bild fehlt das Startbild.')
        # MiniMax zieht das Startbild ohne Rücksicht auf das Seitenverhältnis auf das Videoformat.
        # ImageScale schneidet es vorher mittig zu (wie 2Wild mit Pillow), ohne Kopie.
        for rolle, feld, nid in (('start', 'first_frame', 30), ('ende', 'last_frame', 32)):
            if namen.get(rolle) and e['art'] == 'video_bild':
                graph[str(nid)] = {'class_type': 'LoadImage', 'inputs': {'image': namen[rolle]}}
                graph[str(nid + 1)] = {'class_type': 'ImageScale', 'inputs': {
                    'image': [str(nid), 0], 'upscale_method': 'lanczos', 'width': e['breite'],
                    'height': e['hoehe'], 'crop': 'center'}}
                graph['5']['inputs'][feld] = [str(nid + 1), 0]
    if e['schritte'] <= int(v['turbo_bis_schritte']):
        graph['24'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
            'model': ['20', 0], 'lora_name': m['turbo_ref2va' if referenz else 'turbo_fl2va'], 'strength_model': 1.0}}
        graph['10']['inputs']['model'] = ['24', 0]
        graph['11']['inputs']['model'] = ['24', 0]
        acc = v.get('acc8') or {}
        if referenz and e.get('acc8') and acc.get('lora'):
            # Seit 09.10.2026: PDD-LoRA (8 Schritte) statt Turbo v0.1; ihre Köpfe sagen die mittlere Geschwindigkeit je
            # Schritt voraus, dazu passt Euler (ComfyUI wertet sie über den Sigma-Plan aus, comfy/ldm/minimax).
            graph['24']['inputs']['lora_name'] = acc['lora']
            graph['9']['inputs']['sampler_name'] = 'euler'
    t = v.get('tauschen') or {}
    if referenz and e.get('tauschen') and t.get('lora'):
        # Stufe 3q: Character-Swap-LoRA (Person im Clip „Video 1“ durch die Figur aus „Bild 1“) hinter der Turbo-LoRA.
        graph['27'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
            'model': ['24', 0] if '24' in graph else ['20', 0], 'lora_name': t['lora'],
            'strength_model': float(t.get('staerke', 1.0))}}
        graph['10']['inputs']['model'] = ['27', 0]
        graph['11']['inputs']['model'] = ['27', 0]
    r = v.get('realismus') or {}
    if e.get('realismus') and r.get('lora'):
        # Stufe 3o: Realism-LoRA hinter der Turbo-LoRA, Auslösewort vor dem Prompt (gespeichert bleibt der Prompt ohne).
        graph['26'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
            'model': ['27', 0] if '27' in graph else ['24', 0] if '24' in graph else ['20', 0], 'lora_name': r['lora'],
            'strength_model': float(r.get('staerke', 1.0))}}
        graph['10']['inputs']['model'] = ['26', 0]
        graph['11']['inputs']['model'] = ['26', 0]
        graph['5']['inputs']['prompt'] = realismus_prompt(r, e['prompt'])
    dm = v.get('dmad') or {}
    if e.get('dmad') and not referenz and '24' in graph and dm.get('lora'):
        # Seit 11.10.2026: DMAD (4 Schritte, adversarial destilliert) statt der Turbo-LoRA; laut Modellkarte Sampler lcm
        # und Verschiebung 12/2 (Euler ist nicht ihr Arbeitspunkt). Ergibt in den Tests die natürlichste Haut.
        graph['24']['inputs']['lora_name'] = dm['lora']
        graph['9']['inputs']['sampler_name'] = dm.get('sampler', 'lcm')
        graph['28'] = {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {
            'model': graph['10']['inputs']['model'], 'shift_video': float(dm.get('shift_video', 12.0)),
            'shift_audio': float(dm.get('shift_audio', 2.0))}}
        graph['10']['inputs']['model'] = ['28', 0]
        graph['11']['inputs']['model'] = ['28', 0]
    if e.get('schnell'):
        # Seit 17.10.2026: schnellere Aufmerksamkeit (Kernknoten ModelAttentionBackend, INT8) wie bei Bildern (_mit_schnell),
        # als letzter Modell-Schritt vor Scheduler und Guider. Nur neue Aufträge (Feld schnell), damit „Nochmal“ älterer
        # Videos gleich bleibt. Gemessen: rund ein Viertel bis ein Drittel kürzer, gleichwertig (PLAN.md, Stufe 3u).
        sa = v.get('schnelle_aufmerksamkeit') or {}
        graph['29'] = {'class_type': 'ModelAttentionBackend', 'inputs': {
            'model': graph['11']['inputs']['model'], 'attention': sa.get('backend') or 'comfy kitchen attention'}}
        graph['10']['inputs']['model'] = ['29', 0]
        graph['11']['inputs']['model'] = ['29', 0]
    return graph


def zeitlupe_graph(e, v, praefix, clip):
    """Zeitlupe mit RIFE (Kernknoten FrameInterpolate, seit 09.10.2026): ×2 verdoppelt die Bilder bei gleicher Bildrate
    (halbe Geschwindigkeit); ×1,5 rechnet dreimal so viele Bilder und nimmt jedes zweite. Ohne Ton (er passt nicht mehr)."""
    fps = float(v['fps'])
    g = {
        '1': {'class_type': 'LoadVideo', 'inputs': {'file': clip}},
        '2': {'class_type': 'GetVideoComponents', 'inputs': {'video': ['1', 0]}},
        '3': {'class_type': 'FrameInterpolationModelLoader', 'inputs': {'model_name': v['zeitlupe']['modell']}},
        '4': {'class_type': 'FrameInterpolate', 'inputs': {'interp_model': ['3', 0], 'images': ['2', 0],
                                                           'multiplier': 2 if e['faktor'] == 2 else 3}},
        '9': {'class_type': 'SaveVideo', 'inputs': {'video': ['5', 0], 'filename_prefix': praefix,
                                                    'format': 'auto', 'codec': 'auto'}},
    }
    if e['faktor'] == 2:
        g['5'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['4', 0], 'fps': fps}}
    else:
        g['6'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['4', 0], 'fps': fps * 3}}
        g['7'] = {'class_type': 'VideoFrameSample', 'inputs': {'video': ['6', 0], 'num_frames': e['bilder'],
                                                               'strategy': 'uniform', 'seed': 0}}
        g['8'] = {'class_type': 'GetVideoComponents', 'inputs': {'video': ['7', 0]}}
        g['5'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['8', 0], 'fps': fps}}
    return g


def video_freistellen_graph(e, v, praefix, clip):
    """Video freistellen (Kernknoten, seit 09.10.2026): SAM3 verfolgt `motiv` (etwa „person“) über alle Bilder, BiRefNet
    liefert je Bild die feinen Kanten; mit `verfahren` kombi zählt BiRefNet nur innerhalb der (etwas erweiterten)
    SAM3-Maske. Ergebnis: WebM (VP9) mit Alpha, ohne Ton (der WebM-Speicher kennt keinen)."""
    f = v['freistellen']
    g = {
        '1': {'class_type': 'LoadVideo', 'inputs': {'file': clip}},
        '2': {'class_type': 'GetVideoComponents', 'inputs': {'video': ['1', 0]}},
    }
    verfahren = e.get('verfahren') or f.get('verfahren', 'kombi')
    if verfahren in ('sam3', 'kombi'):
        g.update({
            '3': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': f['sam3']}},
            '4': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['3', 1], 'text': e['motiv']}},
            '5': {'class_type': 'SAM3_VideoTrack', 'inputs': {
                'images': ['2', 0], 'model': ['3', 0], 'conditioning': ['4', 0],
                'detection_threshold': float(f.get('schwelle', 0.5)), 'max_objects': int(f.get('max_objekte', 4)),
                'detect_interval': 1}},
            '6': {'class_type': 'SAM3_TrackToMask', 'inputs': {'track_data': ['5', 0], 'object_indices': ''}},
        })
        maske = ['6', 0]
    if verfahren in ('biref', 'kombi'):
        g.update({
            '70': {'class_type': 'LoadBackgroundRemovalModel', 'inputs': {'bg_removal_name': f['biref']}},
            '71': {'class_type': 'RemoveBackground', 'inputs': {'bg_removal_model': ['70', 0], 'image': ['2', 0]}},
        })
        maske = ['71', 0]
    if verfahren == 'kombi':
        g['7'] = {'class_type': 'GrowMask', 'inputs': {'mask': ['6', 0], 'expand': int(f.get('erweitern_px', 16)),
                                                       'tapered_corners': True}}
        g['8'] = {'class_type': 'MaskComposite', 'inputs': {'destination': ['71', 0], 'source': ['7', 0], 'x': 0, 'y': 0,
                                                            'operation': 'multiply'}}
        maske = ['8', 0]
    g.update({
        '20': {'class_type': 'InvertMask', 'inputs': {'mask': maske}},  # JoinImageWithAlpha erwartet 1 = durchsichtig
        '21': {'class_type': 'JoinImageWithAlpha', 'inputs': {'image': ['2', 0], 'alpha': ['20', 0]}},
        '22': {'class_type': 'SaveWEBM', 'inputs': {'images': ['21', 0], 'filename_prefix': praefix, 'codec': 'vp9',
                                                    'fps': float(v['fps']), 'crf': float(f.get('crf', 20))}},
    })
    return g


def modell3d_graph(e, m, praefix, namen):
    """3D-Modell mit Pixal3D (Kernknoten, Stufe 3t) nach den Comfy-Org-Vorlagen „Pixal3D: Multi Views to 3D“ und
    „Pixal3D & TRELLIS.2: Image to Model“: Ansichten freistellen (BiRefNet) und mittig auf 1024² setzen, Struktur →
    Form → feine Form → Textur, dann Netz aufbereiten (neu vernetzen, ausdünnen, UV, Texturen backen) und als GLB
    speichern. Dazu ein Drehteller aus RenderMesh-Bildern als Vorschau-Video.
    `namen`: {'vorlage': Datei} (Drehblatt oder Bild) bzw. {'vorn': …, 'links': …} (Einzelansichten)."""
    md, st = m['modelle'], e['detail']
    seed = int(e['variation'])
    g = {
        '19': {'class_type': 'LoadBackgroundRemovalModel', 'inputs': {'bg_removal_name': md['biref']}},
        '40': {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': md['dino']}},
    }

    def ansicht(k, bild):
        # Motiv freistellen und wie in der Vorlage mittig mit Rand auf Schwarz setzen (gleiche Größe in jeder Ansicht)
        g[f'2{k}'] = {'class_type': 'RemoveBackground', 'inputs': {'bg_removal_model': ['19', 0], 'image': bild}}
        g[f'3{k}'] = {'class_type': 'ImageCropToMask', 'inputs': {
            'images': bild, 'masks': [f'2{k}', 0], 'width': 1024, 'height': 1024,
            'pad_factor': float(m.get('rand', 1.1)), 'grow_mask': 0, 'background': '#000000'}}
        return [f'3{k}', 0]

    if e['modus'] == 'bild':
        g['1'] = {'class_type': 'LoadImage', 'inputs': {'image': namen['vorlage']}}
        bild = ansicht(0, ['1', 0])
        # Blickwinkel des Fotos schätzt MoGe (wie in der Vorlage), damit die Rückprojektion stimmt
        g['26'] = {'class_type': 'LoadMoGeModel', 'inputs': {'model_name': md['moge']}}
        g['27'] = {'class_type': 'MoGeInference', 'inputs': {
            'moge_model': ['26', 0], 'image': bild, 'resolution_level': 9, 'fov_x_degrees': 0.0, 'batch_size': 4,
            'force_projection': True, 'apply_mask': True, 'refine_steps': 3}}
        g['28'] = {'class_type': 'MoGeGeometryToFOV', 'inputs': {'moge_geometry': ['27', 0], 'axis': 'horizontal',
                                                                 'unit': 'degrees'}}
        g['41'] = {'class_type': 'Pixal3DConditioning', 'inputs': {'clip_vision_model': ['40', 0], 'image': bild,
                                                                   'camera_angle_x': ['28', 0]}}
        modell = md['einzelbild']
    else:
        ansichten = {}
        if e['modus'] == 'drehblatt':
            g['1'] = {'class_type': 'LoadImage', 'inputs': {'image': namen['vorlage']}}
            b = int(e['breite']) // 4
            for k, name in enumerate(MODELL_ANSICHTEN):
                g[f'1{k}'] = {'class_type': 'ImageCrop', 'inputs': {'image': ['1', 0], 'width': b,
                                                                     'height': int(e['hoehe']), 'x': k * b, 'y': 0}}
                ansichten[name] = ansicht(k, [f'1{k}', 0])
        else:
            for k, name in enumerate(MODELL_ANSICHTEN):
                if namen.get(name):
                    g[f'1{k}'] = {'class_type': 'LoadImage', 'inputs': {'image': namen[name]}}
                    ansichten[name] = ansicht(k, [f'1{k}', 0])
        englisch = {'vorn': 'front', 'links': 'left', 'hinten': 'back', 'rechts': 'right'}
        g['41'] = {'class_type': 'Pixal3DMultiViewConditioning', 'inputs': dict(
            {'clip_vision_model': ['40', 0], 'fov': float(m.get('fov', 20.0))},
            **{englisch[n]: a for n, a in ansichten.items()})}
        modell = md['multiview']
    s, c = m['schritte'], m['cfg']

    def sampler(modell_knoten, quelle, nr, schritte, cfg, planer):
        return {'class_type': 'KSampler', 'inputs': {
            'model': modell_knoten, 'positive': [quelle, 0], 'negative': [quelle, 1], 'latent_image': [quelle, 2],
            'seed': seed + nr, 'steps': int(schritte), 'cfg': float(cfg), 'sampler_name': 'euler', 'scheduler': planer,
            'denoise': 1.0}}
    g.update({
        '50': {'class_type': 'UNETLoader', 'inputs': {'unet_name': modell, 'weight_dtype': 'default'}},
        # CFG-Verlauf wie in der Vorlage („to match the original default pipeline behaviour“)
        '51': {'class_type': 'CFGOverride', 'inputs': {'model': ['50', 0], 'cfg': 1.0,
                                                       'start_percent': float(c['struktur_ab']), 'end_percent': 1.0}},
        '52': {'class_type': 'RescaleCFG', 'inputs': {'model': ['51', 0], 'multiplier': float(c['struktur_rescale'])}},
        '53': {'class_type': 'ModelSamplingSD3', 'inputs': {'model': ['52', 0], 'shift': float(c['struktur_shift'])}},
        '54': {'class_type': 'CFGOverride', 'inputs': {'model': ['50', 0], 'cfg': 1.0,
                                                       'start_percent': float(c['form_ab']), 'end_percent': 1.0}},
        '55': {'class_type': 'RescaleCFG', 'inputs': {'model': ['54', 0], 'multiplier': float(c['form_rescale'])}},
        '60': {'class_type': 'EmptyTrellis2LatentStructure', 'inputs': {'batch_size': 1}},
        '61': {'class_type': 'KSampler', 'inputs': {
            'model': ['53', 0], 'positive': ['41', 0], 'negative': ['41', 1], 'latent_image': ['60', 0], 'seed': seed,
            'steps': int(s['struktur']), 'cfg': float(c['struktur']), 'sampler_name': 'euler', 'scheduler': 'normal',
            'denoise': 1.0}},
        '62': {'class_type': 'VAELoader', 'inputs': {'vae_name': md['vae_form']}},
        '63': {'class_type': 'VaeDecodeStructureTrellis2', 'inputs': {'samples': ['61', 0], 'vae': ['62', 0],
                                                                      'resolution': '32'}},
        '64': {'class_type': 'Trellis2ShapeStage', 'inputs': {'positive': ['41', 0], 'negative': ['41', 1],
                                                              'voxel': ['63', 0]}},
        '65': sampler(['55', 0], '64', 1, s['form'], c['form'], 'normal'),
        '66': {'class_type': 'Trellis2UpsampleStage', 'inputs': {
            'positive': ['64', 0], 'negative': ['64', 1], 'shape_latent': ['65', 0], 'vae': ['62', 0],
            'target_resolution': int(st['aufloesung'])}},
        '67': sampler(['55', 0], '66', 2, s['feinform'], c['form'], 'simple'),
        '68': {'class_type': 'VaeDecodeShapeTrellis', 'inputs': {'samples': ['67', 0], 'vae': ['62', 0]}},
        '70': {'class_type': 'Trellis2TextureStage', 'inputs': {'positive': ['66', 0], 'negative': ['66', 1],
                                                                'shape_latent': ['67', 0]}},
        '71': sampler(['50', 0], '70', 3, s['textur'], c['textur'], 'normal'),
        '72': {'class_type': 'VAELoader', 'inputs': {'vae_name': md['vae_textur']}},
        '73': {'class_type': 'VaeDecodeTextureTrellis', 'inputs': {'samples': ['71', 0], 'vae': ['72', 0],
                                                                   'shape_subdivides': ['68', 1]}},
        # Netz aufbereiten wie die Vorlage: neu vernetzen, ausdünnen, glätten, abwickeln, Texturen backen
        '81': {'class_type': 'RemeshMesh', 'inputs': {
            'mesh': ['68', 0], 'resolution': int(m.get('remesh', 768)), 'sign_mode': 'udf', 'sign_mode.qef': False,
            'sign_mode.drop_inverted_components': False, 'sign_mode.drop_enclosed_components': False, 'band': 1.0,
            'project_back': 0.0, 'fix_poles': False, 'smooth_iters': 20, 'drop_small_components': 0.01,
            'precluster_max_verts': 20000000}},
        '82': {'class_type': 'DecimateMesh', 'inputs': {'mesh': ['81', 0], 'target_face_count': int(st['dreiecke']),
                                                        'placement_mode': 'midpoint'}},
        '83': {'class_type': 'MeshSmoothNormals', 'inputs': {'mesh': ['82', 0], 'crease_angle': 180.0}},
        '84': {'class_type': 'UnwrapMesh', 'inputs': {'mesh': ['83', 0], 'segmenter': 'pec',
                                                      'resolution': int(st['textur']), 'padding': 1,
                                                      'weld_distance': 0.0002}},
        '85': {'class_type': 'BakeTextureFromVoxel', 'inputs': {'mesh': ['84', 0], 'voxel_colors': ['73', 0],
                                                                'texture_size': int(st['textur']),
                                                                'reference_mesh': ['68', 0]}},
    })
    textur = {'mesh': ['84', 0], 'base_color': ['85', 0], 'metallic': ['85', 1], 'roughness': ['85', 2]}
    if st.get('normalen'):
        g['86'] = {'class_type': 'BakeNormalMapFromMesh', 'inputs': {
            'low_poly': ['84', 0], 'high_poly': ['81', 0], 'resolution': int(st['textur']), 'cage_distance': 0.05,
            'ignore_backfaces': True}}
        g['87'] = {'class_type': 'BakeAmbientOcclusion', 'inputs': {
            'low_poly': ['84', 0], 'high_poly': ['81', 0], 'resolution': min(1024, int(st['textur'])), 'samples': 64,
            'max_distance': 0.71, 'strength': 1.0, 'bias': 0.01}}
        textur.update(normal_map=['86', 0], occlusion=['87', 0])
    g.update({
        '88': {'class_type': 'ApplyTextureToMesh', 'inputs': textur},
        '89': {'class_type': 'MeshSmoothNormals', 'inputs': {'mesh': ['88', 0], 'crease_angle': 180.0}},
        '90': {'class_type': 'MeshToFile3D', 'inputs': {'mesh': ['89', 0]}},
        '91': {'class_type': 'SaveGLB', 'inputs': {'mesh': ['90', 0], 'filename_prefix': praefix}},
    })
    # Vorschau: Drehteller – das fertige Modell um die Hochachse gedreht, je Bild von vorn gerendert, als kurzes Video.
    v = m['vorschau']
    n = max(1, min(99, int(v['bilder'])))
    for k in range(n):
        g[str(100 + k)] = {'class_type': 'RotateMesh', 'inputs': {
            'mesh': ['89', 0], 'mode': 'euler_xyz', 'mode.angle_x': 0.0, 'mode.angle_y': round(360.0 * k / n, 3),
            'mode.angle_z': 0.0}}
        g[str(200 + k)] = {'class_type': 'RenderMesh', 'inputs': {
            'mesh': [str(100 + k), 0], 'mode': 'auto', 'width': int(v['groesse']), 'height': int(v['groesse']),
            'background': v.get('hintergrund', '#FFFFFF')}}
    letzte = ['200', 0]
    for k in range(1, n):
        g[str(300 + k)] = {'class_type': 'ImageBatch', 'inputs': {'image1': letzte, 'image2': [str(200 + k), 0]}}
        letzte = [str(300 + k), 0]
    g['400'] = {'class_type': 'CreateVideo', 'inputs': {'images': letzte, 'fps': float(v['fps'])}}
    g['401'] = {'class_type': 'SaveVideo', 'inputs': {'video': ['400', 0], 'filename_prefix': praefix,
                                                      'format': 'auto', 'codec': 'auto'}}
    return g


def zeitlupe_laenge(bilder, faktor):
    """Bilder nach der Zeitlupe: ×2 fügt zwischen je zwei Bildern eins ein, ×1,5 nimmt jedes zweite von dreifach so vielen."""
    return 2 * (bilder - 1) + 1 if faktor == 2 else round((3 * (bilder - 1) + 1) / 2)


def szenen_prompt(sz, gemeinsam, text):
    """Prompt einer Szene (Stufe 3p): gemeinsamer Teil, dann die Szene, dann der Zusatz gegen harte Schnitte."""
    teile = (str(gemeinsam or '').strip(), str(text or '').strip(), str((sz or {}).get('ohne_schnitt') or '').strip())
    return '\n\n'.join(t for t in teile if t)


def zeit_gruppe(a):
    """Gruppe eines Bildauftrags für das Nachlernen der Zeitschätzung (gleicher Schlüssel in studio.js, zeitGruppe):
    Art, wie Vorlage 1 oder Format, Anzahl Vorlagen bzw. Vorbilder (bis 2), Turbo, Ausformulieren."""
    n = sum(1 for v in a.get('vorlagen') or [] if isinstance(v, dict) and v.get('rolle') in ('vorlage', 'vorbild'))
    wie_vorlage = a['art'] == 'freistellen' or (a['art'] == 'bearbeiten' and a.get('groesse_von') != 'format')
    return '|'.join((a['art'], 'vorlage' if wie_vorlage else 'format', str(min(n, 2)),
                     ('turbom' if a.get('turbo_modell') else 'turbo') if a.get('turbo') else 'normal',
                     'ausf' if a.get('ausformulieren') else '-'))


def realismus_prompt(r, prompt):
    """Prompt mit dem Auslösewort der Realism-LoRA davor (Stufe 3o)."""
    return f"{r['ausloeser']}, {prompt}" if r.get('ausloeser') else prompt


def realismus_weg(ausloeser, prompt):
    """Umkehrung von realismus_prompt: der Prompt ohne das Auslösewort."""
    vorne = f'{ausloeser}, ' if ausloeser else None
    return prompt[len(vorne):] if vorne and isinstance(prompt, str) and prompt.startswith(vorne) else prompt


# ---------------------------------------------------------------- Videos weiterführen (Stufe 3m)
# Versuche und Plan (mit Astra geprüft): PLAN.md, Stufe 3m. Vorn hält MiniMaxH3AddGuide die letzten 39 Bilder samt Ton
# des Ausgangsclips fest (Stücke am Ende ergaben Schnitte), hinten führt ein einzelnes Endbild (fl2va last_frame) weich
# in den Zielclip. ConcatenateVideo setzt Originale und neuen Teil zusammen; ungeschnittene Originale reicht es in der
# Bildspur bitgleich durch, der Ton wird neu kodiert.

WEITER_MODI = ('verlaengern', 'davor', 'verbinden', 'schleife')
WEITER_FENSTER = 39  # 17k+5 Bilder und durch 3 teilbar: Bild- und Tonraster (40 Hz) passen zusammen
WEITER_MIN, WEITER_MAX = 124, 362  # H3 ist auf 124–362 Bilder trainiert
WEITER_MAX_GESAMT = 60 * 24  # Obergrenze des fertigen Videos in Bildern
WEITER_RAND_S = 0.001  # Zeitfenster 1 ms früher: zusammengesetzte Videos haben bis 0,5 ms Zittern in den Zeitstempeln


def weiter_teile(modus):
    """(festgehaltene Bilder vorn, Endbild) des neuen Clips je Modus."""
    return (0 if modus == 'davor' else WEITER_FENSTER), (0 if modus == 'verlaengern' else 1)


def weiter_laenge(modus, neu_sekunden, fps=24):
    """Kleinste Clip-Länge L auf dem 17k+5-Raster (mindestens 124), die mindestens `neu_sekunden` neue Bilder ergibt;
    None, wenn L über 362 läge. Rundet auf – anders als bilder_raster, das zum nächsten Wert rundet. Längen mit
    L mod 3 = 2 fallen weg: H3 rundet dort die Tonlänge (40 Hz) ab, der Ton wäre 8,3 ms kürzer als das Bild."""
    kontext, ende = weiter_teile(modus)
    laenge = max(WEITER_MIN, math.ceil(round(float(neu_sekunden) * fps, 6)) + kontext + ende)
    while laenge % 17 != 5 or laenge % 3 == 2:
        laenge += 1
    return laenge if laenge <= WEITER_MAX else None


def weiter_laenge_ok(laenge):
    """Clip-Länge aus einer Wiederholung: ganze Zahl auf dem Raster zwischen 124 und 362 mit vollem Ton."""
    return isinstance(laenge, int) and not isinstance(laenge, bool) and WEITER_MIN <= laenge <= WEITER_MAX \
        and laenge % 17 == 5 and laenge % 3 != 2


def weiter_bereiche(modus, laenge, bilder, schnitt_ende=0, schnitt_anfang=0):
    """Bildbereiche (Start, Anzahl), halboffen, für einen Auftrag „Video weiterführen“.

    bilder: {'ausgang': n, 'ziel': n} – Ausgangsclip (an dessen Ende angesetzt wird) und Zielclip (in dessen Anfang der
    neue Teil führt); `schnitt_ende` fällt am Ende des Ausgangs-, `schnitt_anfang` am Anfang des Zielclips weg.
    -> {'fuehrung': (Rolle, Start, Anzahl) | None, 'endbild': (Rolle, Index) | None, 'neu': (Start, Anzahl) im neuen
    Clip, 'segmente': [(Rolle | 'neu', Start, Anzahl)] des Ergebnisses, 'gesamt': Bilder}. ValueError, wenn ein Clip
    für die Schnitte zu kurz ist."""
    if modus not in WEITER_MODI:
        raise ValueError('Unbekannte Art des Weiterführens.')
    kontext, ende = weiter_teile(modus)
    e, b = int(schnitt_ende or 0), int(schnitt_anfang or 0)
    if e < 0 or b < 0:
        raise ValueError('Ein Schnitt kann nicht negativ sein.')
    if e and modus == 'davor':
        raise ValueError('Beim Davor-Setzen wird am Ende nichts abgeschnitten.')
    if b and modus in ('verlaengern', 'schleife'):
        raise ValueError('Beim Verlängern und bei der Schleife wird am Anfang nichts abgeschnitten.')
    neu = ('neu', kontext, laenge - kontext - ende)
    out = {'fuehrung': None, 'endbild': None, 'neu': neu[1:]}
    if kontext:
        rest = int(bilder['ausgang']) - e
        if rest < WEITER_FENSTER:
            raise ValueError(f'Vom Ausgangsclip bleiben nach dem Schnitt {max(rest, 0)} Bilder; zum Anheften braucht es '
                             f'mindestens {WEITER_FENSTER} (1,6 s).')
        out['fuehrung'] = ('ausgang', rest - WEITER_FENSTER, WEITER_FENSTER)
        vorn = [('ausgang', 0, rest)]
    else:
        vorn = []
    if modus in ('davor', 'verbinden'):
        n = int(bilder['ziel'])
        if n - b < 1:
            raise ValueError(f'Der Zielclip hat nur {n} Bilder; nach dem Schnitt bliebe keines übrig.')
        out['endbild'] = ('ziel', b)
        hinten = [('ziel', b, n - b)]
    else:
        hinten = []
        if modus == 'schleife':
            out['endbild'] = ('ausgang', 0)
    out['segmente'] = vorn + [neu] + hinten
    out['gesamt'] = sum(s[2] for s in out['segmente'])
    return out


def _zeitfenster(start, anzahl, fps):
    """Zeitfenster (Sekunden) für die Bilder [start, start+anzahl), an beiden Enden WEITER_RAND_S früher."""
    beginn = max(0.0, start / fps - WEITER_RAND_S)
    return round(beginn, 6), round((start + anzahl) / fps - WEITER_RAND_S - beginn, 6)


# Rechenzeit von Videos (gemessen 27.09.2026): Die Zeit je Schritt wächst etwa mit dem Quadrat von Pixel × Bildern
# (bei großen Clips ist die 3090 voll und lädt nach) – festgehaltene Stücke und Schlüsselbilder rechnet MiniMax mit.
# Bezug: 5 s in 960 × 544; Exponent und Sekunden je Schritt in `video.zeit`.
VIDEO_BEZUG = 960 * 544 * 124


def video_bilder_wirksam(a):
    """Bilder, die das Videomodell rechnet: Clip-Länge plus festgehaltene Bilder bzw. Start- und Endbild."""
    bilder = int(a.get('bilder') or 0)
    if a.get('art') == 'video_weiter':
        kontext, ende = weiter_teile(a.get('modus'))
        return bilder + kontext + ende
    if a.get('art') == 'video_bild':
        return bilder + len(a.get('vorlagen') or [])
    if a.get('art') == 'video_referenz':
        # Seit 09.10.2026: die Bilder der Clips (ref_bilder) rechnen mit (Person tauschen: 124 + 124 Bilder ≈ 7 min statt
        # der geschätzten 2), jedes Referenzbild etwa wie ein Bild.
        return bilder + int(a.get('ref_bilder') or 0) + sum(1 for v in a.get('vorlagen') or [] if v.get('rolle') == 'bild')
    return bilder


def video_einheiten(a, zeit):
    """(Pixel × wirksame Bilder / Bezug) ^ Exponent: Rechenaufwand je Schritt im Verhältnis zum Bezugsvideo."""
    return (a['breite'] * a['hoehe'] * video_bilder_wirksam(a) / VIDEO_BEZUG) ** float(zeit['exponent'])


def video_zeit(a, zeit, je_schritt):
    """Erwartete Rechenzeit eines Videoauftrags in Sekunden: Grundzeit (Laden, Text, Dekodieren) + Schritte."""
    return round(float(zeit['grund_s']) + je_schritt * a['schritte'] * video_einheiten(a, zeit))


def weiter_graph(e, v, praefix, namen):
    """ComfyUI-Ablauf „Video weiterführen“ (nur Kernknoten).

    e: Auftrag mit modus, prompt, breite, hoehe, bilder (Länge L des neuen Clips), schritte, variation, schnitt_ende,
    schnitt_anfang und quellen [{'rolle', 'bilder', 'tondauer', 'tonrate', 'tonkanaele'}]; v: cfg['studio']['video'];
    namen: {'ausgang'|'ziel': Name für LoadVideo/LoadAudio}. Ergebnis: ein zusammengesetztes Video über SaveVideo.

    Bilder: Stücke der Quellen über `Video Slice` mit Zeitfenstern 1 ms vor den Bildgrenzen (robust gegen das Zittern
    zusammengesetzter Videos); ungeschnittene Quellen gehen direkt in ConcatenateVideo (Bildspur bitgleich). Ton: exakt
    an den Bildgrenzen aus LoadAudio bzw. dem neuen Clip geschnitten, zu kurzer Quellton mit Stille aufgefüllt (H3
    rundet die Tonlänge), als ganzer Ton (`complete_audio`) an ConcatenateVideo."""
    fps = float(v['fps'])
    quellen = {q['rolle']: q for q in e['quellen']}
    bilder = {rolle: int(q['bilder']) for rolle, q in quellen.items()}
    ber = weiter_bereiche(e['modus'], int(e['bilder']), bilder, e.get('schnitt_ende'), e.get('schnitt_anfang'))
    graph = video_graph(dict(e, art='video_text'), v, praefix)
    knoten = {'ausgang': ('40', '30'), 'ziel': ('41', '31')}  # (LoadVideo, LoadAudio)
    for rolle, (nid_bild, nid_ton) in knoten.items():
        if rolle in namen:
            graph[nid_bild] = {'class_type': 'LoadVideo', 'inputs': {'file': namen[rolle]}}
            graph[nid_ton] = {'class_type': 'LoadAudio', 'inputs': {'audio': namen[rolle]}}
    frei = iter(range(70, 100))

    def neu_id():
        return str(next(frei))

    def bilder_stueck(rolle, start, anzahl):
        beginn, dauer = _zeitfenster(start, anzahl, fps)
        nid = neu_id()
        graph[nid] = {'class_type': 'Video Slice', 'inputs': {'video': [knoten[rolle][0], 0], 'start_time': beginn,
                                                              'duration': dauer, 'strict_duration': False}}
        return [nid, 0]

    def ton_stueck(quelle, start, anzahl):
        """Ton für die Bilder [start, start+anzahl), exakt geschnitten; fehlt am Ende Ton, mit Stille aufgefüllt."""
        nid = neu_id()
        graph[nid] = {'class_type': 'TrimAudioDuration', 'inputs': {
            'audio': quelle, 'start_index': round(start / fps, 6), 'duration': round(anzahl / fps, 6)}}
        return [nid, 0]

    def quellton(rolle, start, anzahl):
        ton = ton_stueck([knoten[rolle][1], 0], start, anzahl)
        q = quellen[rolle]
        fehlt = (start + anzahl) / fps - float(q['tondauer'])
        if fehlt > 1 / float(q['tonrate']):
            still = neu_id()
            graph[still] = {'class_type': 'EmptyAudio', 'inputs': {
                'duration': round(fehlt, 6), 'sample_rate': int(q['tonrate']), 'channels': int(q.get('tonkanaele') or 2)}}
            ton = verketten(ton, [still, 0])
        return ton

    def verketten(ton1, ton2):
        nid = neu_id()
        graph[nid] = {'class_type': 'AudioConcat', 'inputs': {'audio1': ton1, 'audio2': ton2, 'direction': 'after'}}
        return [nid, 0]

    if ber['fuehrung']:
        rolle, start, anzahl = ber['fuehrung']
        graph['43'] = {'class_type': 'GetVideoComponents', 'inputs': {'video': bilder_stueck(rolle, start, anzahl)}}
        # Ton genau so lang wie die 39 Bilder (65 Ton-Latents); bei 13- und 15-s-Videos fehlen am Ende 8,3 ms Ton
        graph['50'] = {'class_type': 'MiniMaxH3AddGuide', 'inputs': {
            'positive': ['5', 0], 'latent': ['5', 1], 'frame_idx': 0, 'vae': ['22', 0], 'audio_vae': ['23', 0],
            'image': ['43', 0], 'audio': quellton(rolle, start, anzahl)}}
        graph['11']['inputs']['conditioning'] = ['50', 0]
    if ber['endbild']:
        rolle, index = ber['endbild']
        graph['45'] = {'class_type': 'GetVideoComponents', 'inputs': {'video': bilder_stueck(rolle, index, 1)}}
        graph['5']['inputs']['last_frame'] = ['45', 0]
    start, anzahl = ber['neu']
    graph['46'] = {'class_type': 'ImageFromBatch', 'inputs': {'image': ['14', 0], 'batch_index': start, 'length': anzahl}}
    graph['16'] = {'class_type': 'CreateVideo', 'inputs': {'images': ['46', 0], 'fps': fps}}
    teile, ton = [], None
    for rolle, start, anzahl in ber['segmente']:
        if rolle == 'neu':
            teile.append(['16', 0])
            stueck_ton = ton_stueck(['15', 0], start, anzahl)
        else:
            # ungeschnitten geht die Datei selbst hinein: ConcatenateVideo reicht ihre Bildspur bitgleich durch
            teile.append([knoten[rolle][0], 0] if start == 0 and anzahl == bilder[rolle]
                         else bilder_stueck(rolle, start, anzahl))
            stueck_ton = quellton(rolle, start, anzahl)
        ton = stueck_ton if ton is None else verketten(ton, stueck_ton)
    graph['18'] = {'class_type': 'ConcatenateVideo', 'inputs': dict(
        {f'videos.video{i}': t for i, t in enumerate(teile)}, codec='auto', complete_audio=ton)}
    graph['17'] = {'class_type': 'SaveVideo', 'inputs': {'video': ['18', 0], 'filename_prefix': praefix,
                                                         'format': 'auto', 'codec': 'auto'}}
    return graph


def datei_pruefsumme(pfad):
    """SHA-256 einer Datei (hex)."""
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _mp4_boxen(f, von, bis):
    """Boxen zwischen von und bis: [(Typ, Inhaltsbeginn, Inhaltsende)]."""
    out, pos = [], von
    while pos + 8 <= bis:
        f.seek(pos)
        kopf = f.read(16)
        if len(kopf) < 8:
            break
        groesse, typ = struct.unpack_from('>I4s', kopf, 0)
        laenge_kopf = 8
        if groesse == 1:
            if len(kopf) < 16:
                break
            groesse, laenge_kopf = struct.unpack_from('>Q', kopf, 8)[0], 16
        elif groesse == 0:
            groesse = bis - pos
        if groesse < laenge_kopf or pos + groesse > bis:
            raise ValueError('beschädigte MP4-Struktur')
        out.append((typ, pos + laenge_kopf, pos + groesse))
        pos += groesse
    return out


def _mp4_kind(f, box, *pfad):
    """Erste Unterbox entlang des Pfads (Typen als bytes) oder None."""
    for typ in pfad:
        box = next((b for b in _mp4_boxen(f, box[1], box[2]) if b[0] == typ), None)
        if box is None:
            return None
    return box


def _mp4_lesen(f, box, groesse=None):
    f.seek(box[1])
    return f.read(groesse if groesse is not None else box[2] - box[1])


def _mp4_elst(f, trak):
    """Einträge der Edit-List: [(Abschnittsdauer, Medienzeit)] oder [] ohne Edit-List."""
    elst = _mp4_kind(f, trak, b'edts', b'elst')
    if elst is None:
        return []
    d = _mp4_lesen(f, elst)
    version, anzahl = d[0], struct.unpack_from('>I', d, 4)[0]
    out = []
    for i in range(anzahl):
        if version == 1:
            dauer, zeit = struct.unpack_from('>Qq', d, 8 + 20 * i)
        else:
            dauer, zeit = struct.unpack_from('>Ii', d, 8 + 12 * i)
        out.append((dauer, zeit))
    return out


def mp4_info(pfad, fps=24):
    """Maße einer MP4-Datei aus dem Studio – bewusst enger Umfang (Stufe 3m), sonst ValueError mit Grund.

    Verlangt genau eine Bildspur und eine Tonspur, Bildrate `fps` mit höchstens 5 % Abweichung je Bild und weniger als
    ¼ Bild Abweichung insgesamt (zusammengesetzte Videos zittern um bis 0,5 ms), Edit-Lists mit höchstens einem
    Abschnitt ohne leeren Vorspann (eine Medienzeit > 0 ist B-Bild-Verzögerung bzw. AAC-Vorlauf) und einen Ton, der
    das Bild bis auf ein Ton-Latent von H3 (25 ms; H3 rundet die Tonlänge, bei 13- und 15-s-Videos fehlen 8,3 ms)
    abdeckt – weiter_graph füllt den Rest exakt mit Stille auf. -> {'breite', 'hoehe', 'bilder', 'fps', 'tonrate',
    'tonkanaele', 'tondauer', 'bilddauer'}."""
    with open(pfad, 'rb') as f:
        f.seek(0, os.SEEK_END)
        ende = f.tell()
        moov = next((b for b in _mp4_boxen(f, 0, ende) if b[0] == b'moov'), None)
        if moov is None:
            raise ValueError('keine MP4-Datei (moov fehlt)')
        spuren = {}
        for trak in (b for b in _mp4_boxen(f, moov[1], moov[2]) if b[0] == b'trak'):
            hdlr, mdhd = _mp4_kind(f, trak, b'mdia', b'hdlr'), _mp4_kind(f, trak, b'mdia', b'mdhd')
            if hdlr is None or mdhd is None:
                continue
            art = _mp4_lesen(f, hdlr, 12)[8:12]
            if art not in (b'vide', b'soun'):
                continue
            if art in spuren:
                raise ValueError('mehr als eine Bild- oder Tonspur')
            m = _mp4_lesen(f, mdhd, 32)
            zeitmass, dauer = struct.unpack_from('>IQ', m, 20) if m[0] == 1 else struct.unpack_from('>II', m, 12)
            if not zeitmass:
                raise ValueError('Zeitmaß fehlt')
            stts = _mp4_kind(f, trak, b'mdia', b'minf', b'stbl', b'stts')
            if stts is None:
                raise ValueError('Zeittabelle fehlt')
            d = _mp4_lesen(f, stts)
            eintraege = [struct.unpack_from('>II', d, 8 + 8 * i) for i in range(struct.unpack_from('>I', d, 4)[0])]
            spuren[art] = {'trak': trak, 'zeitmass': zeitmass, 'dauer': dauer, 'stts': eintraege,
                           'elst': _mp4_elst(f, trak)}
        if b'vide' not in spuren:
            raise ValueError('keine Bildspur')
        if b'soun' not in spuren:
            raise ValueError('keine Tonspur')
        bild, ton = spuren[b'vide'], spuren[b'soun']
        tkhd = _mp4_kind(f, bild['trak'], b'tkhd')
        if tkhd is None:
            raise ValueError('Spurkopf fehlt')
        t = _mp4_lesen(f, tkhd)
        breite, hoehe = (x >> 16 for x in struct.unpack_from('>II', t, len(t) - 8))
        stsd = _mp4_kind(f, ton['trak'], b'mdia', b'minf', b'stbl', b'stsd')
        s = _mp4_lesen(f, stsd, 34) if stsd else b''
        kanaele = struct.unpack_from('>H', s, 32)[0] if len(s) >= 34 else 2  # Tonbeschreibung: channelcount
    for name, spur in (('Bild', bild), ('Ton', ton)):
        if len(spur['elst']) > 1 or any(zeit < 0 for _, zeit in spur['elst']):
            raise ValueError(f'{name}spur mit mehreren Abschnitten oder Startverzögerung (Edit-List)')
    nenn = bild['zeitmass'] / fps
    anzahl, summe, abweichung = 0, 0, 0.0
    for n, delta in bild['stts']:
        if abs(delta - nenn) > 0.05 * nenn:
            raise ValueError(f'Bildrate nicht gleichmäßig {fps} fps')
        # größte Abweichung des Zeitpunkts vom Raster am Anfang und am Ende des Eintrags
        abweichung = max(abweichung, abs(summe - anzahl * nenn), abs(summe + n * delta - (anzahl + n) * nenn))
        anzahl, summe = anzahl + n, summe + n * delta
    if not anzahl:
        raise ValueError('keine Bilder')
    if abweichung >= nenn / 4:
        raise ValueError(f'Zeitstempel weichen um mehr als ¼ Bild vom {fps}-fps-Raster ab')
    vorlauf = ton['elst'][0][1] if ton['elst'] else 0
    tondauer = (ton['dauer'] - vorlauf) / ton['zeitmass']
    bilddauer = anzahl / fps
    if tondauer < bilddauer - 0.025:
        raise ValueError(f'Ton ({tondauer:.3f} s) deckt das Bild ({bilddauer:.3f} s) nicht ganz ab')
    return {'breite': breite, 'hoehe': hoehe, 'bilder': anzahl, 'fps': round(anzahl / (summe / bild['zeitmass']), 3),
            'tonrate': ton['zeitmass'], 'tonkanaele': kanaele or 2, 'tondauer': round(tondauer, 6),
            'bilddauer': round(bilddauer, 6)}



def video_masse(pfad):
    """Breite, Höhe und Bildzahl eines Videos (MP4/MOV) nur aus der Bildspur – nachsichtiger als mp4_info, auch ohne
    Tonspur (etwa eine Zeitlupe). -> {'breite', 'hoehe', 'bilder'} oder ValueError."""
    with open(pfad, 'rb') as f:
        f.seek(0, os.SEEK_END)
        ende = f.tell()
        moov = next((b for b in _mp4_boxen(f, 0, ende) if b[0] == b'moov'), None)
        if moov is None:
            raise ValueError('keine MP4-Datei (moov fehlt)')
        for trak in (b for b in _mp4_boxen(f, moov[1], moov[2]) if b[0] == b'trak'):
            hdlr = _mp4_kind(f, trak, b'mdia', b'hdlr')
            if hdlr is None or _mp4_lesen(f, hdlr, 12)[8:12] != b'vide':
                continue
            tkhd, stts = _mp4_kind(f, trak, b'tkhd'), _mp4_kind(f, trak, b'mdia', b'minf', b'stbl', b'stts')
            if tkhd is None or stts is None:
                raise ValueError('Spurkopf oder Zeittabelle fehlt')
            t = _mp4_lesen(f, tkhd)
            breite, hoehe = (x >> 16 for x in struct.unpack_from('>II', t, len(t) - 8))
            d = _mp4_lesen(f, stts)
            bilder = sum(struct.unpack_from('>I', d, 8 + 8 * i)[0] for i in range(struct.unpack_from('>I', d, 4)[0]))
            if not bilder:
                raise ValueError('keine Bilder')
            return {'breite': breite, 'hoehe': hoehe, 'bilder': bilder}
    raise ValueError('keine Bildspur')

# ---------------------------------------------------------------- Metadaten in Dateien

def png_texte(pfad):
    """Textfelder einer PNG-Datei (tEXt, zTXt, iTXt) -> {schlüssel: text}."""
    out = {}
    try:
        with open(pfad, 'rb') as f:
            if f.read(8) != b'\x89PNG\r\n\x1a\n':
                return out
            while True:
                kopf = f.read(8)
                if len(kopf) < 8:
                    break
                laenge, typ = struct.unpack('>I4s', kopf)
                if typ == b'IDAT' or typ == b'IEND':
                    # Bei ComfyUI stehen die Texte vor den Bilddaten; dahinter muss nichts mehr gelesen werden.
                    if typ == b'IEND' or out:
                        break
                    f.seek(laenge + 4, 1)
                    continue
                daten = f.read(laenge)
                f.read(4)
                try:
                    if typ == b'tEXt':
                        k, v = daten.split(b'\0', 1)
                        out[k.decode('latin-1')] = v.decode('latin-1')
                    elif typ == b'zTXt':
                        k, v = daten.split(b'\0', 1)
                        out[k.decode('latin-1')] = zlib.decompress(v[1:]).decode('latin-1')
                    elif typ == b'iTXt':
                        k, rest = daten.split(b'\0', 1)
                        komprimiert = rest[0] == 1
                        _, _, text = rest[2:].split(b'\0', 2)
                        out[k.decode('latin-1')] = (zlib.decompress(text) if komprimiert else text).decode('utf-8')
                except (ValueError, zlib.error, IndexError):
                    continue
    except OSError:
        pass
    return out


def png_masse(pfad):
    """(Breite, Höhe) aus dem IHDR-Block einer PNG-Datei oder (None, None)."""
    try:
        with open(pfad, 'rb') as f:
            kopf = f.read(24)
        if kopf[:8] == b'\x89PNG\r\n\x1a\n' and kopf[12:16] == b'IHDR':
            return struct.unpack('>II', kopf[16:24])
    except OSError:
        pass
    return None, None


def bild_masse(pfad):
    """(Breite, Höhe) einer PNG-, JPEG- oder WebP-Datei aus dem Dateikopf, sonst (None, None)."""
    try:
        with open(pfad, 'rb') as f:
            kopf = f.read(32)
            if kopf[:8] == b'\x89PNG\r\n\x1a\n' and kopf[12:16] == b'IHDR':
                return struct.unpack('>II', kopf[16:24])
            if kopf[:4] == b'RIFF' and kopf[8:12] == b'WEBP':
                art = kopf[12:16]
                if art == b'VP8X':
                    b, h = kopf[24:27], kopf[27:30]
                    return int.from_bytes(b, 'little') + 1, int.from_bytes(h, 'little') + 1
                if art == b'VP8L':
                    bits = int.from_bytes(kopf[21:25], 'little')
                    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                if art == b'VP8 ':
                    return int.from_bytes(kopf[26:28], 'little') & 0x3FFF, int.from_bytes(kopf[28:30], 'little') & 0x3FFF
            if kopf[:2] == b'\xff\xd8':
                f.seek(2)
                while True:
                    marke = f.read(2)
                    if len(marke) < 2 or marke[0] != 0xFF:
                        break
                    if marke[1] in (0xD8, 0x01) or 0xD0 <= marke[1] <= 0xD7:
                        continue
                    laenge = struct.unpack('>H', f.read(2))[0]
                    if marke[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        f.read(1)
                        h, b = struct.unpack('>HH', f.read(4))
                        return b, h
                    f.seek(laenge - 2, 1)
    except (OSError, struct.error):
        pass
    return None, None


def _atome(daten, start, ende):
    """Kind-Atome eines MP4-Bereichs -> [(typ, anfang_inhalt, ende)]."""
    out, pos = [], start
    while pos + 8 <= ende:
        groesse, typ = struct.unpack('>I4s', daten[pos:pos + 8])
        kopf = 8
        if groesse == 1:
            groesse = struct.unpack('>Q', daten[pos + 8:pos + 16])[0]
            kopf = 16
        elif groesse == 0:
            groesse = ende - pos
        if groesse < kopf or pos + groesse > ende:
            break
        out.append((typ, pos + kopf, pos + groesse))
        pos += groesse
    return out


def _moov_lesen(pfad, grenze=32 * 1024 * 1024):
    """Nur das moov-Atom einer MP4-Datei (dort stehen die Metadaten), ohne die Videodaten zu lesen."""
    try:
        with open(pfad, 'rb') as f:
            ende = os.fstat(f.fileno()).st_size
            pos = 0
            while pos + 8 <= ende:
                f.seek(pos)
                kopf = f.read(16)
                groesse, typ = struct.unpack('>I4s', kopf[:8])
                laenge_kopf = 8
                if groesse == 1:
                    groesse, laenge_kopf = struct.unpack('>Q', kopf[8:16])[0], 16
                elif groesse == 0:
                    groesse = ende - pos
                if groesse < laenge_kopf:
                    return None
                if typ == b'moov':
                    if groesse > grenze:
                        return None
                    f.seek(pos)
                    return f.read(groesse)
                pos += groesse
    except (OSError, struct.error):
        return None
    return None


def mp4_texte(pfad):
    """Metadaten-Schlüssel (mdta) einer MP4-Datei, wie ComfyUI sie schreibt -> {schlüssel: text}."""
    daten = _moov_lesen(pfad)
    if not daten:
        return {}
    moov = next(((a, e) for t, a, e in _atome(daten, 0, len(daten)) if t == b'moov'), None)
    if not moov:
        return {}
    out = {}

    def meta_lesen(a, e):
        # meta ist in MP4 eine „FullBox“ (4 Byte Version/Flags), in QuickTime nicht.
        if daten[a + 4:a + 8] != b'hdlr' and daten[a + 8:a + 12] == b'hdlr':
            a += 4
        kinder = _atome(daten, a, e)
        schluessel = []
        for t, ka, ke in kinder:
            if t == b'keys':
                anzahl = struct.unpack('>I', daten[ka + 4:ka + 8])[0]
                p = ka + 8
                for _ in range(anzahl):
                    g = struct.unpack('>I', daten[p:p + 4])[0]
                    schluessel.append(daten[p + 8:p + g].decode('utf-8', 'replace'))
                    p += g
        for t, ka, ke in kinder:
            if t != b'ilst':
                continue
            for it, ia, ie in _atome(daten, ka, ke):
                index = struct.unpack('>I', it)[0]
                for dt, da, de in _atome(daten, ia, ie):
                    if dt == b'data' and 1 <= index <= len(schluessel):
                        out[schluessel[index - 1]] = daten[da + 8:de].decode('utf-8', 'replace')

    def suchen(a, e, tiefe=0):
        for t, ka, ke in _atome(daten, a, e):
            if t == b'meta':
                meta_lesen(ka, ke)
            elif t in (b'udta', b'moov') and tiefe < 3:
                suchen(ka, ke, tiefe + 1)
    suchen(*moov)
    return out


def _json(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def einstellungen_aus_graph(graph, durchsichtig_vorlage=None, realismus=None, tauschen=None):
    """Was sich aus einem ComfyUI-Arbeitsablauf (API-Form) über ein Ergebnis sagen lässt.

    durchsichtig_vorlage: Rahmen-Prompt für durchsichtige Bilder (studio.durchsichtig.vorlage); damit wird bei solchen
    Bildern wieder die Beschreibung zum Prompt, so dass „Nochmal“ nicht doppelt rahmt. realismus: studio.video.realismus
    (Stufe 3o); ein Video mit dieser LoRA bekommt `realismus` und seinen Prompt ohne Auslösewort."""
    if not isinstance(graph, dict):
        return {}
    knoten = {k: v for k, v in graph.items() if isinstance(v, dict) and isinstance(v.get('inputs'), dict)}

    def text_von(ref):
        if isinstance(ref, list) and ref and str(ref[0]) in knoten:
            n = knoten[str(ref[0])]
            if isinstance(n['inputs'].get('text'), str):
                return n['inputs']['text']
            if ref[1] == 1 and isinstance(n['inputs'].get('negative_prompt'), str):
                return n['inputs']['negative_prompt']
            if isinstance(n['inputs'].get('prompt'), str):
                return n['inputs']['prompt']
        return None

    e = {'prompt': None, 'negativ': None, 'variation': None, 'schritte': None, 'cfg': None,
         'breite': None, 'hoehe': None, 'laenge_bilder': None, 'modell_datei': None, 'vorlagen': []}
    klassen = {n['class_type'] for n in knoten.values()}
    for n in knoten.values():
        i, k = n['inputs'], n.get('class_type', '')
        if k in ('KSampler', 'KSamplerAdvanced'):
            e['prompt'] = e['prompt'] or text_von(i.get('positive'))
            e['negativ'] = e['negativ'] if e['negativ'] is not None else text_von(i.get('negative'))
        for feld, ziel in (('seed', 'variation'), ('noise_seed', 'variation'), ('steps', 'schritte'), ('cfg', 'cfg'),
                           ('width', 'breite'), ('height', 'hoehe'), ('length', 'laenge_bilder'),
                           ('unet_name', 'modell_datei')):
            if e[ziel] is None and isinstance(i.get(feld), (int, float, str)) and not isinstance(i.get(feld), bool):
                e[ziel] = i[feld]
        if k == 'LoadImage' and isinstance(i.get('image'), str):
            e['vorlagen'].append(i['image'])
        if k == 'LoadVideo' and isinstance(i.get('file'), str):
            e['vorlagen'].append(i['file'])
    if not e['prompt']:
        for n in knoten.values():
            i = n['inputs']
            for feld in ('prompt', 'text'):
                if isinstance(i.get(feld), str) and i[feld].strip():
                    e['prompt'] = i[feld]
                    break
            if e['prompt']:
                if e['negativ'] is None and isinstance(i.get('negative_prompt'), str):
                    e['negativ'] = i['negative_prompt']
                break
    turbo_datei = isinstance(e.get('modell_datei'), str) and 'qwen_image' in e['modell_datei'] and 'turbo' in e['modell_datei']
    if 'ManualSigmas' in klassen and ('LoraLoaderModelOnly' in klassen or turbo_datei):
        # Turbo-LoRA bzw. (seit 11.10.2026) offizielles Turbo-Modell: Schritte im festen Zeitplan (letzte Stützstelle 0)
        e['turbo'] = True
        if turbo_datei:
            e['turbo_modell'] = True
        sig = next((n['inputs'].get('sigmas') for n in knoten.values() if n.get('class_type') == 'ManualSigmas'), None)
        if isinstance(sig, str):
            e['schritte'] = max(0, len(re.findall(r'[-+]?(?:\d*\.*\d+)', sig)) - 1)
    if (knoten.get('25') or {}).get('class_type') == 'LoraLoaderModelOnly':
        e['details'] = True  # Detail-LoRA des Studios (Knoten 25, siehe _mit_details)
    if 'ModelAttentionBackend' in klassen:
        e['schnell'] = True  # schnellere Aufmerksamkeit (Bilder Knoten 26, siehe _mit_schnell; Videos Knoten 29)
    if isinstance(e['modell_datei'], str) and 'qwen_image' in e['modell_datei'] and 'int8' in e['modell_datei']:
        e['int8'] = True  # INT8-Fassung (siehe qwen_dateien)
    r = realismus or {}
    if r.get('lora') and any(n.get('class_type') == 'LoraLoaderModelOnly' and n['inputs'].get('lora_name') == r['lora']
                             for n in knoten.values()):
        e['realismus'] = True  # Realism-LoRA (Knoten 26, siehe video_graph)
        e['prompt'] = realismus_weg(r.get('ausloeser'), e['prompt'])
    t = tauschen or {}
    if t.get('lora') and any(n.get('class_type') == 'LoraLoaderModelOnly' and n['inputs'].get('lora_name') == t['lora']
                             for n in knoten.values()):
        e['tauschen'] = True  # Character-Swap-LoRA (Knoten 27, siehe video_graph)
    if any(n.get('class_type') == 'LoraLoaderModelOnly' and 'dmad' in str(n['inputs'].get('lora_name')).lower()
           for n in knoten.values()):
        e['dmad'] = True  # DMAD statt Turbo (Knoten 24, siehe video_graph)
    if any(n.get('class_type') == 'LoraLoaderModelOnly' and 'Acc-8Step' in str(n['inputs'].get('lora_name'))
           for n in knoten.values()):
        e['acc8'] = True  # 8-Schritt-LoRA statt Turbo (Knoten 24, siehe video_graph)
    if 'TextGenerate' in klassen:
        # Prompt-Enhancer (siehe _mit_ausformulieren): der Prompt ist der Wunsch, nicht der ganze Chat-Rahmen
        e['ausformulieren'] = True
        e['prompt'] = next((w for w in (ausformulieren_wunsch(n['inputs'].get('prompt')) for n in knoten.values()
                                        if n.get('class_type') == 'TextGenerate') if w), e['prompt'])
    alpha = 'JoinImageWithAlpha' in klassen and 'SplitImageWithAlpha' in klassen
    if 'SDPoseKeypointExtractor' in klassen:
        e.update(art='pose', breite=None, hoehe=None, vorlagen=e['vorlagen'][:1])
        if 'SAM3_Detect' in klassen:
            e['personen'] = True  # jede Person in ihrem Rahmen (siehe pose_graph)
    elif 'RemoveBackground' in klassen:
        # schnell freigestellt (BiRefNet, siehe freistellen_schnell_graph): Größe wie das Original
        e.update(art='freistellen', verfahren='schnell', breite=None, hoehe=None, vorlagen=e['vorlagen'][:1])
    elif alpha and e['vorlagen']:
        # Freigestellt: Größe wie das Original (nicht die der Arbeitsfläche)
        e.update(art='freistellen', breite=None, hoehe=None, vorlagen=e['vorlagen'][:1])
    elif 'ImageCompositeMasked' in klassen and 'LoadImageMask' in klassen:
        # Stelle verbessert: Breite und Höhe im Ablauf gehören zum Ausschnitt, das Ergebnis hat die Größe des Originals.
        e.update(art='verbessern', breite=None, hoehe=None, vorlagen=e['vorlagen'][:1])
    elif 'MiniMaxH3ReferenceToVideo' in klassen:
        e['art'] = 'video_referenz'
    elif 'ConcatenateVideo' in klassen and 'MiniMaxH3ImageToVideo' in klassen:
        # Video weiterführen (weiter_graph): Modus, Schnitte und Quellen stehen nur in den Begleitdaten.
        e.update(art='video_weiter', laenge_bilder=None)
    elif 'SaveVideo' in klassen or 'CreateVideo' in klassen:
        e['art'] = 'video_bild' if e['vorlagen'] else 'video_text'
    elif 'TextEncodeQwenImage21' in klassen or e['vorlagen']:
        e['art'] = 'bearbeiten'
        e['groesse_von'] = 'format' if 'EmptySD3LatentImage' in klassen else 'vorlage'
    else:
        e['art'] = 'bild'
        if alpha:  # neues Bild mit durchsichtigem Hintergrund (siehe _mit_durchsichtig)
            e['durchsichtig'] = True
            if durchsichtig_vorlage:
                e['prompt'] = durchsichtig_beschreibung(durchsichtig_vorlage, e['prompt']) or e['prompt']
    return e


def modellname(datei):
    n = (datei or '').lower()
    if 'qwen_image' in n:
        return 'Qwen-Image' + (' 2.1' if '2.1' in n else '')
    if 'minimax_h3' in n:
        return 'MiniMax-H3'
    return datei or None


# ---------------------------------------------------------------- Platz

def platz_fehlt(antwort, bedarf, schluessel='bild-video'):
    """Wie viel fehlt je Karte, wenn die eigene Belegung dieses ComfyUI-Prozesses schon angerechnet wird?

    -> (fehlend {karte: MiB}, zusatz {karte: MiB}). `zusatz` ist, was ComfyUI noch neu belegen wird
    (für die Anmeldung bei der Zentrale); kleine Reste unter 512 MiB zählen nicht. `schluessel`: der Verbraucher
    dieses Prozesses (Stufe 8: „bild-video“ oder „bild-video-2“; der Cache des anderen Prozesses zählt nicht).
    """
    comfy = {}
    for v in antwort.get('verbraucher') or []:
        if v.get('schluessel') == schluessel:
            comfy = {int(i): m for i, m in v['mib_je_karte'].items()}
    frei = {k['index']: k['frei'] for k in antwort.get('karten', [])}
    zusatz = {i: max(0, m - comfy.get(i, 0)) for i, m in bedarf.items()}
    fehlend = {i: round(z - frei.get(i, 0)) for i, z in zusatz.items() if z - frei.get(i, 0) > 0}
    return fehlend, {i: round(z) for i, z in zusatz.items() if z >= 512}


# ---------------------------------------------------------------- Karten je Auftrag

# ComfyUI startet mit --default-device 0 (Zentrale). Abläufe ohne Kartenwahl (Pose, schnelles Freistellen, SAM3,
# Zeitlupe, Video freistellen, 3D) rechnen dort.
STANDARD_KARTE = 0
BEDARF_ROLLEN = ('eine', 'eine_ohne_monitor', 'haupt', 'neben', 'fest', 'standard_zusatz')
GERAETE_ROLLEN = ('modell', 'clip', 'vae', 'vae_video', 'vae_audio')


def bedarf_lesen(d):
    """Bedarf aus der Einstellung als {Rolle: MiB}; Rollen siehe `verteilungen`."""
    return {r: int(m) for r, m in (d or {}).items() if r in BEDARF_ROLLEN and m}


def verteilungen(bedarf, karten, standard=STANDARD_KARTE):
    """Mögliche Verteilungen eines Auftrags auf die Karten (`karten`: Indizes).

    bedarf: 'eine' – alles auf einer Karte; 'eine_ohne_monitor' – ebenso, aber nie auf der Monitorkarte (Videos, Stufe 8:
    ComfyUI füllt die Karte fast ganz); 'haupt'/'neben' – Diffusionsmodell auf einer Karte, Text-Encoder und VAE auf
    der anderen; 'fest' – Abläufe ohne Kartenwahl auf ComfyUIs Standardkarte; 'standard_zusatz' – zusätzlich auf der
    Standardkarte gebraucht (SAM3 bei „Stelle per Wort“).
    -> [{'rang': 0 eine Karte / 1 geteilt, 'mib': {Karte: MiB}, 'geraete': {Rolle: 'gpu:n'} oder None,
         'haupt': Karte des Diffusionsmodells (nur geteilt), 'ohne_monitor': True (nur „eine_ohne_monitor“)}]
    """
    out = []
    if bedarf.get('fest') and standard in karten:
        out.append({'rang': 0, 'mib': {standard: bedarf['fest']}, 'geraete': None})
    if bedarf.get('eine'):
        for a in karten:
            out.append({'rang': 0, 'mib': {a: bedarf['eine']}, 'geraete': dict.fromkeys(GERAETE_ROLLEN, f'gpu:{a}')})
    if bedarf.get('eine_ohne_monitor'):
        for a in karten:
            out.append({'rang': 0, 'mib': {a: bedarf['eine_ohne_monitor']}, 'ohne_monitor': True,
                        'geraete': dict.fromkeys(GERAETE_ROLLEN, f'gpu:{a}')})
    if bedarf.get('haupt'):
        for a in karten:
            for b in karten:
                if a != b:
                    out.append({'rang': 1, 'haupt': a, 'mib': {a: bedarf['haupt'], b: bedarf.get('neben', 0)},
                                'geraete': dict(dict.fromkeys(GERAETE_ROLLEN, f'gpu:{b}'), modell=f'gpu:{a}')})
    if bedarf.get('standard_zusatz') and standard in karten:
        for v in out:
            v['mib'][standard] = max(v['mib'].get(standard, 0), bedarf['standard_zusatz'])
    return out


def karten_waehlen(antwort, bedarf, inst=None):
    """Beste Verteilung nach dem Stand der Zentrale (`/api/platz`).

    Reihenfolge: passt ohne Freigabe; alles auf einer Karte vor geteilt; die Karte mit dem Monitor nicht bis auf weniger
    als `monitor_puffer_mib` füllen (Windows); geteilt das Diffusionsmodell nicht auf die Monitorkarte (ComfyUI füllt
    dessen Karte bei Videos fast ganz, gemessen 14.10.2026); Karten, auf denen ComfyUI schon Speicher hält (sonst lädt
    es die Modelle ein zweites Mal); die engste Karte (die andere bleibt für große Modelle frei); dann die
    Kartennummern. Passt nichts, gilt die Verteilung, der am wenigsten fehlt.
    `inst` (Stufe 8): der ComfyUI-Prozess – er sieht nur seine Karten, rechnet seinen eigenen Cache an und nimmt für
    Ein-Karten-Aufträge die Karte des anderen Prozesses nicht, solange der läuft (sonst müsste der warten, gemessen
    16.10.2026: Prozess 1 legte ein Bild auf die Suprim, Prozess 2 stand); dann wartet er auf seine eigene Karte.
    Ein Video auf einer Karte („eine_ohne_monitor“) kommt nie auf die Monitorkarte.
    -> (verteilung oder None, fehlend {Karte: MiB}, zusatz {Karte: MiB})
    """
    karten = sorted(k['index'] for k in antwort.get('karten', [])
                    if inst is None or inst.karten is None or k['index'] in inst.karten)
    standard = inst.standard if inst else STANDARD_KARTE
    schluessel = inst.schluessel if inst else 'bild-video'
    meiden = inst.meiden() if inst else set()
    frei = {k['index']: k['frei'] for k in antwort.get('karten', [])}
    monitor = {k['index'] for k in antwort.get('karten', []) if k.get('monitor')}
    puffer = antwort.get('monitor_puffer_mib') or 0
    beste = None
    for nr, v in enumerate(verteilungen(bedarf, karten, standard)):
        fehlend, zusatz = platz_fehlt(antwort, v['mib'], schluessel)
        rest = sum(frei.get(i, 0) - zusatz.get(i, 0) for i in v['mib'])
        eng = any(frei.get(i, 0) - zusatz.get(i, 0) < puffer for i in v['mib'] if i in monitor and v['mib'][i])
        if v['rang'] == 0 and any(i in meiden for i, m in v['mib'].items() if m):
            continue
        if v.get('ohne_monitor') and any(i in monitor for i in v['mib']):
            continue
        wert = (sum(fehlend.values()), v['rang'], eng, v.get('haupt') in monitor, sum(zusatz.values()), rest, nr)
        if beste is None or wert < beste[0]:
            beste = (wert, v, fehlend, zusatz)
    return beste[1:] if beste else (None, {}, {})


def mit_geraeten(s, geraete, lokal=None):
    """Einstellungen mit den für einen Auftrag gewählten Karten; ohne Wahl unverändert (Vorgabe `geraete`).

    `lokal` (Stufe 8): Gerätenamen im Prozess, wenn er nur eine Karte sieht (dort heißt die Suprim „gpu:0“)."""
    if not geraete:
        return s
    if lokal:
        geraete = {r: lokal.get(g, g) for r, g in geraete.items()}
    s = dict(s, geraete={r: geraete[r] for r in ('modell', 'clip', 'vae')},
             video=dict(s['video'], geraete={r: geraete[r] for r in ('modell', 'clip', 'vae_video', 'vae_audio')}))
    if s.get('ausformulieren'):
        s['ausformulieren'] = dict(s['ausformulieren'], geraet=geraete['modell'])
    return s


def karten_text(antwort, verteilung):
    """„RTX 3090 FE“ bzw. „RTX 3090 FE + RTX 3090 Suprim“ für Meldung und Protokoll."""
    namen = {k['index']: k.get('kurz') or f"Karte {k['index']}" for k in antwort.get('karten', [])}
    return ' + '.join(namen.get(i, f'Karte {i}') for i, m in verteilung['mib'].items() if m)


def platz_text(antwort, fehlend, comfy_name):
    teile = []
    for k in antwort.get('karten', []):
        if k['index'] not in fehlend:
            continue
        wer = [n for n in k.get('belegt_von', []) if n not in (comfy_name, 'Windows & Programme')]
        teile.append(f"auf der {k['kurz']} fehlen {platz.gib(fehlend[k['index']])} GiB"
                     + (f" (belegt von {', '.join(wer)})" if wer else ''))
    return ('Wartet auf freien Grafikspeicher: ' + '; '.join(teile)
            + '. In der Modellzentrale freigeben, dann geht es von selbst weiter.')


# ---------------------------------------------------------------- ComfyUI-Prozesse (Stufe 8)

class Instanz:
    """Ein ComfyUI-Prozess mit seinem Arbeiter im Studio (Stufe 8, 16.10.2026).

    Prozess 1 sieht beide Karten (auch Aufträge über zwei Karten), Prozess 2 nur `karten` (dort heißt die Karte
    „gpu:0“). Zustand, Startoptionen und Rechenzeit gehören dem Prozess; seine Ausgaben tragen `zusatz` im Namen,
    damit zwei Prozesse nie dieselbe Dateinummer wählen."""

    def __init__(self, nr, port, schluessel, name, karten=None, standard=STANDARD_KARTE, zusatz=''):
        self.nr, self.port, self.url = nr, port, f'http://127.0.0.1:{port}'
        self.schluessel, self.name, self.karten, self.standard, self.zusatz = schluessel, name, karten, standard, zusatz
        self.lokal = {f'gpu:{k}': f'gpu:{i}' for i, k in enumerate(karten)} if karten else None
        self.zustand = (0, None)
        self.argv = (None, [])  # (Prozess-ID, Startoptionen)
        self.letzte_rechenzeit = None
        self.andere = []  # die übrigen Prozesse (für `meiden`)
        self.auf_monitor = False  # hängt der Monitor an seiner Karte? (letzter Stand der Zentrale)

    def laeuft(self):
        return bool((self.zustand[1] or {}).get('laeuft'))

    def meiden(self):
        """Karten, die ein anderer laufender Prozess für sich hat (nur für Ein-Karten-Aufträge des ersten Prozesses)."""
        return {k for i in self.andere if i.karten and i.laeuft() for k in i.karten}

    def kann(self, bedarf):
        """Kann dieser Prozess den Bedarf überhaupt rechnen? Wer nur eine Karte sieht, braucht eine Ein-Karten-Möglichkeit
        („eine“ oder „fest“, ein Video „eine_ohne_monitor“ nur, wenn der Monitor nicht an dieser Karte hängt)."""
        return self.karten is None or bool(bedarf.get('eine') or bedarf.get('fest')
                                           or (bedarf.get('eine_ohne_monitor') and not self.auf_monitor))

    def bevorzugt(self, bedarf):
        """Videos auf einer Karte gehören dem Ein-Karten-Prozess (Stufe 8: Video auf der Suprim, Bild daneben auf der
        FE); er nimmt sie vor allem anderen, der erste Prozess lässt sie ihm, solange er läuft."""
        return bool(self.karten and bedarf.get('eine_ohne_monitor') and self.kann(bedarf))


# ---------------------------------------------------------------- Studio

class Studio:
    def __init__(self, cfg, zentrale_cfg, daten_ordner, log, zentrale):
        self.s = cfg['studio']
        self.wurzel = os.path.normpath(self.s['ordner'])
        os.makedirs(self.wurzel, exist_ok=True)
        c = next(e for e in zentrale_cfg['eintraege'] if e['art'] == 'comfy')
        self.comfy_ordner = c.get('comfy_ordner') or ''
        self.comfy_name = c['name']
        self.jobs_2wild = os.path.join(c['studio_ordner'], 'data', 'jobs.json')
        # Bedarf je Rolle (eine Karte, Haupt-/Nebenkarte, Standardkarte); die Karten wählt `karten_waehlen` je Auftrag,
        # was ComfyUI schon hält, wird angerechnet. Ohne Angabe: der Wert der Zentrale für Bild & Video.
        rueckfall = {'eine': int(c.get('bedarf_je_karte_mib') or 20480)}
        self.bedarf = bedarf_lesen(self.s.get('bedarf_mib')) or rueckfall
        self.bedarf_video = bedarf_lesen((self.s.get('video') or {}).get('bedarf_mib')) or {'haupt': 20480, 'neben': 7168}
        # Große Bilder (ab etwa 2 MP) brauchen mehr, vor allem die VAE (gemessen 24.09.2026).
        self.bedarf_gross = bedarf_lesen(self.s.get('bedarf_gross_mib')) or self.bedarf
        self.bedarf_gross_ab = int(self.s.get('bedarf_gross_ab_pixel') or 2_000_000)
        # Pose-Skelett und schnelles Freistellen laden nur kleine Modelle; der Prompt-Enhancer kommt zum Bild dazu (Stufe 3l).
        self.bedarf_hilfe = bedarf_lesen(self.s.get('bedarf_hilfe_mib')) or {'fest': 4096}
        self.bedarf_ausformulieren = bedarf_lesen((self.s.get('ausformulieren') or {}).get('bedarf_mib'))
        self.bedarf_finden = int(((self.s.get('verbessern') or {}).get('finden') or {}).get('bedarf_mib') or 2048)
        self.log = log
        self.zentrale = zentrale
        self.client_id = 'werkstatt-' + secrets.token_hex(4)
        # ComfyUI-Prozesse (Stufe 8): Prozess 1 wie bisher, Prozess 2 (falls eingerichtet) nur auf seiner Karte.
        self.instanzen = [Instanz(1, c['comfy_port'], 'bild-video', c['name'])]
        if c.get('comfy_port_2'):
            karte = int(c.get('comfy_karte_2', 1))
            self.instanzen.append(Instanz(2, c['comfy_port_2'], 'bild-video-2', c.get('comfy_name_2') or 'ComfyUI 2',
                                          karten=[karte], standard=karte, zusatz='-2'))
        for i in self.instanzen:
            i.andere = [x for x in self.instanzen if x is not i]
        self._ort = threading.local()  # welcher Prozess gerade in diesem Faden rechnet
        self._stand_zentrale = (0, None)  # (Zeit, letzter Stand der Zentrale) für `_wer_zuerst`
        self._hochladen_lock = threading.Lock()  # ein gemeinsamer Eingangsordner für beide Prozesse
        self.speicher = os.path.join(daten_ordner, 'studio.json')
        self._lock = threading.RLock()
        self._bib_lock = threading.Lock()
        self._wecker = threading.Event()
        self._abbruch = set()
        self._infos = {}
        self._bib = (0, None)
        self._ausformulieren_system = None
        self._gewaehlt = set()  # Bilder von außerhalb, die Sascha in diesem Lauf selbst gewählt hat
        d = self._lesen(self.speicher) or {}
        self.auftraege = d.get('auftraege', [])
        self.folgen = d.get('folgen', [])  # Szenenfolgen (Stufe 3p); ihr Zustand folgt aus ihren Aufträgen
        for a in self.auftraege:
            if a['zustand'] == 'laeuft':
                a.update(zustand='abgebrochen', schritt=None,
                         meldung='Der Dienst wurde währenddessen neu gestartet. Hat ComfyUI fertig gerechnet, '
                                 'steht das Ergebnis trotzdem in der Bibliothek.')
        self._speichern()
        for inst in self.instanzen:
            threading.Thread(target=self._schleife, args=(inst,), daemon=True).start()

    # ------------------------------------------------------------ Hilfen

    @staticmethod
    def _lesen(pfad):
        try:
            with open(pfad, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _schreiben(pfad, daten):
        # Eigener Zwischenname je Faden: Zwei Arbeiter oder die Bibliothek schreiben nie in dieselbe .tmp (Stufe 8).
        tmp = f'{pfad}.{os.getpid()}-{threading.get_ident()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, indent=1)
        os.replace(tmp, pfad)

    def _speichern(self):
        with self._lock:
            # Erledigtes steht in der Bibliothek; die Liste behält nur die jüngsten Einträge.
            offen = [a for a in self.auftraege if a['zustand'] in OFFEN]
            rest = [a for a in self.auftraege if a['zustand'] not in OFFEN][-150:]
            self.auftraege = [a for a in self.auftraege if a in offen or a in rest]
            for a in rest:
                if a['zustand'] == 'fertig':
                    a.pop('maske', None)  # steht in der Begleitdatei des Ergebnisses
            folgen = [f for f in self.folgen if f.get('zustand') not in ('fertig', 'abgebrochen')]
            self.folgen = [f for f in self.folgen if f in folgen or f in self.folgen[-30:]]
            self._schreiben(self.speicher, {'auftraege': self.auftraege, 'folgen': self.folgen})

    def _finden(self, aid):
        return next((a for a in self.auftraege if a['id'] == aid), None)

    def _inst(self):
        """Der ComfyUI-Prozess dieses Fadens (Arbeiter), sonst der erste (Anzeige, Prüfen)."""
        return getattr(self._ort, 'inst', None) or self.instanzen[0]

    @property
    def comfy_url(self):
        return self._inst().url

    @property
    def comfy_port(self):
        return self._inst().port

    def _comfy_anfrage(self, pfad, daten=None, timeout=10, inst=None):
        kopf = {'Content-Type': 'application/json'} if daten is not None else {}
        anfrage = urllib.request.Request((inst or self._inst()).url + pfad,
                                         None if daten is None else json.dumps(daten).encode('utf-8'), kopf)
        try:
            with _OHNE_PROXY.open(anfrage, timeout=timeout) as r:
                roh = r.read()
                return json.loads(roh) if roh else {}
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise ComfyAus(str(e))

    # ------------------------------------------------------------ ComfyUI

    def comfy_zustand(self, frisch=False, inst=None):
        """Echter Zustand: läuft ComfyUI, speichert es ins Studio, wie voll ist seine Warteschlange?

        Ob ComfyUI läuft, zeigt `/queue` (antwortet auch beim Rechnen sofort). Den Ausgabeordner liefern die Startoptionen
        aus `/system_stats`; das antwortet während einer Videorenderung erst nach rund 4 s und ließ ComfyUI dann als „aus“
        erscheinen. Die Startoptionen ändern sich nur mit einem neuen Prozess und werden deshalb einmal je Prozess gelesen.
        """
        inst = inst or self._inst()
        if not frisch and time.time() - inst.zustand[0] < 3 and inst.zustand[1]:
            return inst.zustand[1]
        z = {'laeuft': False, 'ordner_ok': False, 'ausgabe': None, 'laufend': 0, 'wartend': 0}
        pid = next((p for _, port, p in winapi.lauschende_ports() if port == inst.port), None)
        if pid is not None:
            try:
                q = self._comfy_anfrage('/queue', timeout=5, inst=inst)
                if inst.argv[0] != pid:
                    stats = self._comfy_anfrage('/system_stats', timeout=15, inst=inst)
                    inst.argv = (pid, (stats.get('system') or {}).get('argv') or [])
                argv = inst.argv[1]
                ausgabe = argv[argv.index('--output-directory') + 1] if '--output-directory' in argv else None
                z.update(laeuft=True, ausgabe=ausgabe,
                         ordner_ok=bool(ausgabe) and os.path.normcase(os.path.normpath(ausgabe))
                         == os.path.normcase(self.wurzel),
                         laufend=len(q.get('queue_running', [])), wartend=len(q.get('queue_pending', [])))
            except (ComfyAus, urllib.error.HTTPError, ValueError, IndexError):
                pass
        inst.zustand = (time.time(), z)
        return z

    def _hochladen(self, pfad):
        """Datei von außerhalb des Studios in den Eingangsordner von ComfyUI (für LoadImage)."""
        with open(pfad, 'rb') as f:
            return self._hochladen_daten(f.read(), os.path.basename(pfad))

    def _hochladen_daten(self, inhalt, name, ueberschreiben=False):
        # Beide Prozesse teilen ComfyUIs Eingangsordner (Stufe 8): nacheinander hochladen; eine Markierung mit demselben
        # Inhaltsnamen, die schon bytegleich daliegt, nicht neu schreiben (der andere Prozess könnte sie gerade lesen).
        with self._hochladen_lock:
            if ueberschreiben and self.comfy_ordner:
                da = os.path.join(self.comfy_ordner, 'input', name)
                try:
                    with open(da, 'rb') as f:
                        if f.read() == inhalt:
                            return name
                except OSError:
                    pass
            return self._hochladen_senden(inhalt, name, ueberschreiben)

    def _hochladen_senden(self, inhalt, name, ueberschreiben):
        grenze = secrets.token_hex(12)
        teile = [f'--{grenze}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n'.encode(),
                 f'--{grenze}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\n'
                 f'{"true" if ueberschreiben else "false"}\r\n'.encode(),
                 f'--{grenze}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode('utf-8') + inhalt + b'\r\n',
                 f'--{grenze}--\r\n'.encode()]
        anfrage = urllib.request.Request(self.comfy_url + '/upload/image', b''.join(teile),
                                         {'Content-Type': f'multipart/form-data; boundary={grenze}'})
        try:
            with _OHNE_PROXY.open(anfrage, timeout=120) as r:
                a = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise Fehler(f'ComfyUI nimmt die Vorlage {name} nicht an (Fehler {e.code}).')
        except (urllib.error.URLError, OSError) as e:
            raise ComfyAus(str(e))
        return (a['subfolder'] + '/' + a['name']) if a.get('subfolder') else a['name']

    # ------------------------------------------------------------ Anzeige

    def turbo_verfuegbar(self):
        """Liegt die Turbo-LoRA in ComfyUIs LoRA-Ordner? (ohne sie keine Stufe „Turbo“)"""
        t = self.s.get('turbo') or {}
        return bool(t.get('lora')) and os.path.isfile(os.path.join(self.comfy_ordner, 'models', 'loras', t['lora']))

    def turbo_modell_verfuegbar(self):
        """Offizielles Turbo-Modell eingeschaltet und in ComfyUI? (seit 11.10.2026; neue Turbo-Aufträge rechnen damit)"""
        t = self.s.get('turbo') or {}
        return bool(t.get('modell_aktiv')) and self._modell_da('diffusion_models', t.get('modell'))

    def details_verfuegbar(self):
        """Liegt die Detail-LoRA in ComfyUIs LoRA-Ordner? (ohne sie kein „Details auffrischen“)"""
        d = self.s.get('details') or {}
        return bool(d.get('lora')) and os.path.isfile(os.path.join(self.comfy_ordner, 'models', 'loras', d['lora']))

    def schnell_verfuegbar(self):
        """Schnellere Aufmerksamkeit für neue Bildaufträge eingeschaltet? (studio.schnelle_aufmerksamkeit.aktiv)"""
        return bool((self.s.get('schnelle_aufmerksamkeit') or {}).get('aktiv'))

    def video_schnell_verfuegbar(self):
        """Schnellere Aufmerksamkeit für neue MiniMax-Videos eingeschaltet? (studio.video.schnelle_aufmerksamkeit.aktiv,
        seit 17.10.2026; Text, Bild, Referenz, Weiterführen und Szenenfolge – nicht Zeitlupe und Freistellen)"""
        return bool((self.s['video'].get('schnelle_aufmerksamkeit') or {}).get('aktiv'))

    def _modell_da(self, ordner, datei):
        """Liegt ein Modell in ComfyUIs Modellordner (etwa checkpoints, background_removal)?"""
        return bool(datei) and os.path.isfile(os.path.join(self.comfy_ordner, 'models', ordner, datei))

    def int8_verfuegbar(self):
        """INT8-Fassungen von Qwen eingeschaltet und vorhanden? (Stufe 3l; neue Bildaufträge rechnen dann damit)"""
        m = self.s['modelle']
        return bool((self.s.get('int8') or {}).get('aktiv')) and self._modell_da('diffusion_models', m.get('unet_int8')) \
            and (not m.get('clip_int8') or self._modell_da('text_encoders', m['clip_int8']))

    def freistellen_schnell_verfuegbar(self):
        """Liegt das Freistell-Modell (BiRefNet) in ComfyUI? (ohne es stellt immer Qwen frei)"""
        return self._modell_da('background_removal', (self.s.get('freistellen') or {}).get('schnell_modell'))

    def finden_verfuegbar(self):
        """Liegt SAM3 in ComfyUI? (ohne es nur Markieren von Hand)"""
        return self._modell_da('checkpoints', ((self.s.get('verbessern') or {}).get('finden') or {}).get('modell'))

    def pose_verfuegbar(self):
        """Liegt SDPose in ComfyUI? (ohne es keine Art „Pose“)"""
        return self._modell_da('checkpoints', (self.s.get('pose') or {}).get('modell'))

    def dmad_verfuegbar(self):
        """DMAD-LoRA für neue Videos aus Text bzw. Bild mit 4 Schritten eingeschaltet und vorhanden? (seit 11.10.2026)"""
        d = self.s['video'].get('dmad') or {}
        return bool(d.get('aktiv')) and self._modell_da('loras', d.get('lora'))

    def acc8_verfuegbar(self):
        """8-Schritt-LoRA für „Video mit Referenz“ eingeschaltet und vorhanden? (seit 09.10.2026)"""
        a = self.s['video'].get('acc8') or {}
        return bool(a.get('aktiv')) and self._modell_da('loras', a.get('lora'))

    def zeitlupe_verfuegbar(self):
        """Liegt das Zwischenbild-Modell (RIFE) in ComfyUI? (seit 09.10.2026)"""
        return self._modell_da('frame_interpolation', (self.s['video'].get('zeitlupe') or {}).get('modell'))

    def video_freistellen_verfuegbar(self):
        """Liegen SAM3 und BiRefNet in ComfyUI? (Video freistellen, seit 09.10.2026)"""
        f = self.s['video'].get('freistellen') or {}
        return bool(f) and self._modell_da('checkpoints', f.get('sam3')) and self._modell_da('background_removal', f.get('biref'))

    def modell3d_verfuegbar(self):
        """3D-Modell aus Drehblatt oder Einzelansichten (Stufe 3t): Pixal3D Multiview, DINOv3, beide Trellis-VAEs und
        BiRefNet liegen in ComfyUI?"""
        m = (self.s.get('modell3d') or {}).get('modelle') or {}
        return bool(m) and self._modell_da('diffusion_models', m.get('multiview')) \
            and self._modell_da('clip_vision', m.get('dino')) and self._modell_da('vae', m.get('vae_form')) \
            and self._modell_da('vae', m.get('vae_textur')) and self._modell_da('background_removal', m.get('biref'))

    def modell3d_bild_verfuegbar(self):
        """3D-Modell aus einem einzelnen Bild: zusätzlich Pixal3D (Einzelbild) und MoGe (Blickwinkel) da?"""
        m = (self.s.get('modell3d') or {}).get('modelle') or {}
        return self.modell3d_verfuegbar() and self._modell_da('diffusion_models', m.get('einzelbild')) \
            and self._modell_da('geometry_estimation', m.get('moge'))

    def tauschen_verfuegbar(self):
        """„Person tauschen“ (Stufe 3q): eingerichtet, und die Character-Swap-LoRA liegt in ComfyUI (ohne LoRA in der
        Einstellung nur Prompt-Vorlage und Prüfung)."""
        t = self.s['video'].get('tauschen') or {}
        return bool(t) and (not t.get('lora') or self._modell_da('loras', t['lora']))

    def realismus_verfuegbar(self):
        """Liegt die Realism-LoRA für Videos in ComfyUIs LoRA-Ordner? (Stufe 3o)"""
        return self._modell_da('loras', (self.s['video'].get('realismus') or {}).get('lora'))

    def ausformulieren_verfuegbar(self):
        """Liegen Prompt-Enhancer und sein Systemtext bereit? (ohne sie kein „Wunsch ausformulieren“)"""
        return self._modell_da('text_encoders', (self.s.get('ausformulieren') or {}).get('modell')) \
            and bool(self._system_ausformulieren())

    def _system_ausformulieren(self):
        """Systemtext des Prompt-Enhancers (Datei neben studio.py, aus der ComfyUI-Vorlage), einmal gelesen."""
        if self._ausformulieren_system is None:
            datei = (self.s.get('ausformulieren') or {}).get('system_datei')
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), datei), encoding='utf-8') as f:
                    self._ausformulieren_system = f.read().strip()
            except (OSError, TypeError):
                self._ausformulieren_system = ''
        return self._ausformulieren_system

    def einstellungen(self):
        s, v, vb = self.s, self.s['video'], self.s['verbessern']
        # `arten`: was dieser Stand des Dienstes kennt (der Skill erkennt daran eine Werkstatt mit altem Stand)
        m3 = s.get('modell3d') or {}
        return {'arten': list(BILD_ARTEN + VIDEO_ARTEN + MODELL_ARTEN), 'qualitaet': s['qualitaet'], 'formate': s['formate'],
                'max_vorlagen': s['max_vorlagen'],
                # Stufe 3t: 3D-Modell mit Pixal3D (Drehblatt/Einzelansichten; aus einem Bild nur mit Einzelbild-Modell)
                'modell3d_verfuegbar': self.modell3d_verfuegbar(),
                'modell3d_bild_verfuegbar': self.modell3d_bild_verfuegbar(),
                'modell3d_stufen': [{k: x.get(k) for k in ('id', 'name', 'standard')} for x in m3.get('stufen') or []],
                'modell3d_zeit': {x['id']: self._modell3d_erwartet(x['id']) for x in m3.get('stufen') or []},
                'modell3d_vorschau': m3.get('vorschau'),
                'max_seite': int(s.get('max_seite', 2048)), 'turbo_verfuegbar': self.turbo_verfuegbar(),
                'turbo_modell_verfuegbar': self.turbo_modell_verfuegbar(),
                'turbo_modell_schritte': len((s.get('turbo') or {}).get('modell_sigmas') or []),
                'details_verfuegbar': self.details_verfuegbar(), 'schnell_verfuegbar': self.schnell_verfuegbar(),
                'video_schnell_verfuegbar': self.video_schnell_verfuegbar(),
                'durchsichtig_verfuegbar': bool(s.get('durchsichtig')), 'int8_verfuegbar': self.int8_verfuegbar(),
                'freistellen_schnell_verfuegbar': self.freistellen_schnell_verfuegbar(),
                'finden_verfuegbar': self.finden_verfuegbar(), 'pose_verfuegbar': self.pose_verfuegbar(),
                'ausformulieren_verfuegbar': self.ausformulieren_verfuegbar(),
                'realismus_verfuegbar': self.realismus_verfuegbar(),
                # Stufe 3q: Person tauschen bei „Video mit Referenz“ (Prompt-Vorlage mit {wer} für den Vorschlag)
                'tauschen_verfuegbar': self.tauschen_verfuegbar(),
                'zeitlupe_verfuegbar': self.zeitlupe_verfuegbar(),
                'acc8_verfuegbar': self.acc8_verfuegbar(),
                'dmad_verfuegbar': self.dmad_verfuegbar(),
                'dmad_schritte': int((self.s['video'].get('dmad') or {}).get('schritte', 4)),
                'acc8_schritte': int((self.s['video'].get('acc8') or {}).get('schritte', 8)),
                'video_freistellen_verfuegbar': self.video_freistellen_verfuegbar(),
                'video_freistellen_motiv': (self.s['video'].get('freistellen') or {}).get('motiv', 'person'),
                'tauschen_vorlage': (self.s['video'].get('tauschen') or {}).get('vorlage') or '',
                'tauschen_wer': (self.s['video'].get('tauschen') or {}).get('wer_beispiel') or '',
                'szenen': {'max_szenen': int((self.s['video'].get('szenen') or {}).get('max_szenen', 8)),
                           'ohne_schnitt': (self.s['video'].get('szenen') or {}).get('ohne_schnitt') or '',
                           'realismus_je_szene': True},
                'ausformulieren_sekunden': int((s.get('ausformulieren') or {}).get('sekunden', 15)),
                'bearbeiten_aufloesung': int(s['bearbeiten_aufloesung']),
                'bearbeiten_aufloesungen': s.get('bearbeiten_aufloesungen') or [],
                'turbo_zeitfaktor': float((s.get('turbo') or {}).get('zeitfaktor', 1.0)),
                'vorlage_zeit': {k: float(v) for k, v in (s.get('vorlage_zeit') or {}).items() if k in ('fest', 'je_flaeche')},
                'modell': s['modell_name'], 'ordner': self.wurzel, 'ordner_2wild': s['ordner_2wild'],
                'sekunden_je_schritt': self._sekunden_je_schritt(self.int8_verfuegbar()),
                'zeit_korrektur': self._zeit_korrekturen(),  # je zeit_gruppe, seit 09.10.2026
                'verbessern': {'staerken': vb['staerken'], 'ausschnitt_faktor': vb['ausschnitt_faktor'],
                               'ausschnitt_min': vb['ausschnitt_min'], 'arbeit_min': vb['arbeit_min'],
                               'arbeit_max': vb['arbeit_max'],
                               # Stufe 3n: Bild für die Stelle (fehlt das Feld, kennt der Dienst es noch nicht)
                               'max_vorlagen': int((vb.get('vorlage') or {}).get('max', 1)),
                               'vorlage_megapixel': float((vb.get('vorlage') or {}).get('megapixel', 1.0)),
                               'vorlage_zeitfaktor': float((vb.get('vorlage') or {}).get('zeitfaktor', 0.55))},
                'video': {'qualitaet': v['qualitaet'], 'formate': v['formate'], 'laengen': v['laengen'],
                          'fps': v['fps'], 'turbo_bis_schritte': v['turbo_bis_schritte'],
                          'max_referenzbilder': v['max_referenzbilder'], 'max_clips': v['max_clips'],
                          'modell': v['modell_name'],
                          'zeit': {'grund_s': float(v['zeit']['grund_s']), 'je_schritt_s': self._video_je_schritt(),
                                   # neue Aufträge rechnen mit schnellerer Aufmerksamkeit (seit 17.10.2026)
                                   'je_schritt_schnell_s': self._video_je_schritt(True),
                                   'exponent': float(v['zeit']['exponent']), 'bezug': VIDEO_BEZUG}}}

    def stand(self):
        with self._lock:
            self._folgen_abgleichen()
            auftraege = [dict(a) for a in self.auftraege]
            folgen = [dict(f) for f in self.folgen]
        jetzt = time.time()
        for a in auftraege:
            a.pop('maske', None)  # groß und für die Anzeige unnötig
            if a['zustand'] == 'laeuft' and a.get('rechnen_ab'):
                a['sekunden'] = round(jetzt - a['rechnen_ab'])
        zweite = [dict(self.comfy_zustand(inst=i), name=i.name, nr=i.nr) for i in self.instanzen[1:]]
        return {'comfy': self.comfy_zustand(inst=self.instanzen[0]), 'comfy_weitere': zweite,
                'auftraege': auftraege, 'folgen': folgen, 'projekte': self.projekte(),
                'bibliothek_stand': self._bibliothek_stand(), 'einstellungen': self.einstellungen()}

    @staticmethod
    def _pixel(a):
        """Gerechnete Pixel eines Bildauftrags: beim Verbessern die Arbeitsgröße des Ausschnitts."""
        arbeit = a.get('arbeit')
        if arbeit:
            return arbeit['breite'] * arbeit['hoehe']
        if a.get('breite') and a.get('hoehe'):
            return a['breite'] * a['hoehe']
        if a.get('aufloesung'):  # Bearbeiten wie Vorlage 1: etwa Auflösung²
            return int(a['aufloesung']) ** 2
        return None

    def _bedarf(self, a):
        """Geplanter Grafikspeicher (MiB) für einen Auftrag, je Rolle (siehe `verteilungen`)."""
        if a['art'] in MODELL_ARTEN:
            return bedarf_lesen((self.s.get('modell3d') or {}).get('bedarf_mib')) or self.bedarf_hilfe
        if a['art'] in VIDEO_HILFS_ARTEN:
            h = (self.s['video'].get('freistellen' if a['art'] == 'video_freistellen' else 'zeitlupe') or {}).get('bedarf_mib')
            return bedarf_lesen(h) or self.bedarf_hilfe
        if a['art'] in VIDEO_ARTEN:
            return self.bedarf_video
        if a['art'] in HILFS_ARTEN or a.get('verfahren') == 'schnell':
            return self.bedarf_hilfe
        bedarf = self.bedarf_gross if (self._pixel(a) or 0) > self.bedarf_gross_ab else self.bedarf
        if a.get('ausformulieren') and self.bedarf_ausformulieren:
            bedarf = {k: max(bedarf.get(k, 0), self.bedarf_ausformulieren.get(k, 0))
                      for k in set(bedarf) | set(self.bedarf_ausformulieren)}
        if a['art'] == 'verbessern' and a.get('stelle') and not a.get('maske'):
            bedarf = dict(bedarf, standard_zusatz=self.bedarf_finden)  # SAM3 sucht die Stelle auf der Standardkarte
        return bedarf

    def _sekunden_je_schritt(self, int8=False):
        """Gemessen aus den eigenen fertigen Aufträgen (Median, auf 1328² umgerechnet), sonst Schätzung. INT8-Läufe
        (Stufe 3l, etwa halb so lange) zählen getrennt; ohne eigene INT8-Läufe gilt der Faktor `int8.zeitfaktor`."""
        def median(mit_int8):
            werte = sorted(a['rechenzeit_s'] / a['schritte'] / (self._pixel(a) / 1328 ** 2)
                           for a in self.auftraege[-40:]
                           if a['zustand'] == 'fertig' and a.get('rechenzeit_s') and a.get('breite') and self._pixel(a)
                           and a.get('schritte') and a.get('art') in BILD_ARTEN and not a.get('zwischenspeicher')
                           and not a.get('turbo') and not a.get('ausformulieren') and bool(a.get('int8')) == mit_int8
                           and self._vorlage_faktor(a, self._pixel(a)) == 1.0)  # Verbessern mit Bild 2 rechnet mehr
            return round(werte[len(werte) // 2], 3) if werte else None
        if int8:
            eigen = median(True)
            if eigen:
                return eigen
            return round((median(False) or self.s['sekunden_je_schritt'])
                         * float((self.s.get('int8') or {}).get('zeitfaktor', 1.0)), 3)
        return median(False) or self.s['sekunden_je_schritt']

    def _video_je_schritt(self, schnell=False):
        """Videos: Sekunden je Schritt für das Bezugsvideo (video_zeit), Median der eigenen Läufe, sonst `video.zeit`.
        Clips mit Referenzen zählen nicht mit (ihre Vorlagen rechnen zusätzlich, „so genau wie möglich“ mehrfach).
        Läufe mit schnellerer Aufmerksamkeit (seit 17.10.2026) zählen getrennt; ohne eigene gilt der Faktor
        `video.schnelle_aufmerksamkeit.zeitfaktor` auf die übrigen."""
        z = self.s['video']['zeit']

        def median(mit_schnell):
            werte = sorted((a['rechenzeit_s'] - float(z['grund_s'])) / (a['schritte'] * video_einheiten(a, z))
                           for a in self.auftraege[-40:]
                           if a['zustand'] == 'fertig' and a.get('art') in VIDEO_ARTEN and a.get('art') != 'video_referenz'
                           and a.get('rechenzeit_s') and a['rechenzeit_s'] > float(z['grund_s']) and a.get('bilder')
                           and a.get('schritte') and a.get('breite') and not a.get('zwischenspeicher')
                           and bool(a.get('schnell')) == mit_schnell)
            return round(werte[len(werte) // 2], 2) if werte else None
        ohne = median(False) or float(z['je_schritt_s'])
        if not schnell:
            return ohne
        faktor = float((self.s['video'].get('schnelle_aufmerksamkeit') or {}).get('zeitfaktor', 1.0))
        return median(True) or round(ohne * faktor, 2)

    def _modell3d_erwartet(self, stufe):
        """3D-Modell: Median der eigenen fertigen Aufträge derselben Detailstufe, sonst der Wert aus der Einstellung."""
        werte = sorted(x['rechenzeit_s'] for x in self.auftraege[-40:]
                       if x.get('zustand') == 'fertig' and x.get('art') in MODELL_ARTEN and x.get('stufe') == stufe
                       and x.get('rechenzeit_s') and not x.get('zwischenspeicher'))
        if werte:
            return round(werte[len(werte) // 2])
        return int(((self.s.get('modell3d') or {}).get('zeit') or {}).get(stufe) or 420)

    def _erwartet(self, a):
        if a['art'] in MODELL_ARTEN:
            return self._modell3d_erwartet(a.get('stufe'))
        if a['art'] in VIDEO_HILFS_ARTEN:
            z = (self.s['video'].get('freistellen' if a['art'] == 'video_freistellen' else 'zeitlupe') or {}).get('zeit') or {}
            return round(float(z.get('grund_s', 5)) + float(z.get('je_bild_s', 0.1)) * int(a.get('bilder') or 0))
        if a['art'] in VIDEO_ARTEN:
            return video_zeit(a, self.s['video']['zeit'], self._video_je_schritt(bool(a.get('schnell'))))
        if a['art'] in HILFS_ARTEN or a.get('verfahren') == 'schnell':
            return 3  # Pose-Skelett, schnelles Freistellen: gemessen 1–2 s (Laden des Modells beim ersten Mal extra)
        k = self._zeit_korrekturen()
        return round(self._erwartet_roh(a) * k.get(zeit_gruppe(a), k['standard']))

    def _erwartet_roh(self, a, sps=None):
        """Bildauftrag ohne Nachlernen: nur die Schritte (sps: Sekunden je Schritt, sonst gelernt)."""
        zusatz = int((self.s.get('ausformulieren') or {}).get('sekunden', 15)) if a.get('ausformulieren') else 0
        return zusatz + self._erwartet_qwen(a, sps)

    def _zeit_korrekturen(self):
        """Faktor gemessen/geschätzt je Gruppe (zeit_gruppe), Median der eigenen fertigen Bildaufträge (seit 09.10.2026).
        Die Schätzung zählt nur die Schritte; Text-Encoder, Vorlagen und Dekodieren fehlen. Gemessen 09.10.2026: neue Bilder
        mit Turbo ×1,35, Bearbeiten wie Vorlage 1 in 2 MP ×2,2, Verbessern mit Vorbild ×1,8. Ab 3 Aufträgen je Gruppe gilt
        ihr eigener Faktor, sonst der Median aller (ohne eigene Aufträge 1)."""
        sps = {m: self._sekunden_je_schritt(m) for m in (False, True)}
        gruppen = {}
        for a in self.auftraege[-120:]:
            if (a.get('zustand') != 'fertig' or not a.get('rechenzeit_s') or a.get('zwischenspeicher')
                    or a.get('art') not in BILD_ARTEN or a['art'] in HILFS_ARTEN or a.get('verfahren') == 'schnell'
                    or not a.get('schritte')):
                continue
            try:
                roh = self._erwartet_roh(a, sps[bool(a.get('int8'))])
            except (KeyError, TypeError, ValueError):
                continue
            if roh > 0:
                gruppen.setdefault(zeit_gruppe(a), []).append(a['rechenzeit_s'] / roh)

        def median(w):
            w = sorted(w)
            return round(min(4.0, max(0.5, w[len(w) // 2])), 2)
        alle = [x for w in gruppen.values() for x in w]
        out = {'standard': median(alle) if len(alle) >= 3 else 1.0}
        out.update({g: median(w) for g, w in gruppen.items() if len(w) >= 3})
        return out

    def _erwartet_qwen(self, a, sps=None):
        # Beim Bearbeiten bestimmt die erste Vorlage die Größe; geschätzt wird mit der Arbeitsauflösung.
        pixel = self._pixel(a) or self.s['bearbeiten_aufloesung'] ** 2
        # Turbo: wenige Schritte, aber je Schritt etwas teurer (LoRA, fester Zeitplan); gemessen etwa Faktor 1,4.
        faktor = float((self.s.get('turbo') or {}).get('zeitfaktor', 1.0)) if a.get('turbo') and not a.get('turbo_modell') \
            else 1.0
        flaeche = pixel / 1328 ** 2
        if a['art'] == 'freistellen' or (a['art'] == 'bearbeiten' and a.get('groesse_von') != 'format'):
            # Die Vorlage wird in derselben Größe mitgerechnet; das kostet mit der Fläche mehr als linear.
            vz = self.s.get('vorlage_zeit') or {}
            faktor *= float(vz.get('fest', 1.0)) + float(vz.get('je_flaeche', 0.0)) * flaeche
        faktor *= self._vorlage_faktor(a, pixel)
        sps = self._sekunden_je_schritt(bool(a.get('int8'))) if sps is None else sps
        return round(sps * a['schritte'] * flaeche * faktor, 1)

    def _vorlage_faktor(self, a, pixel):
        """Verbessern mit einem Bild für die Stelle (Stufe 3n): Die Vorlage rechnet mit etwa `vorlage.megapixel` mit;
        gemessen +6 s bei Turbo, also bei kleinem Ausschnitt anteilig mehr (1 MP: ×1,6, 1,8 MP: ×1,3)."""
        n = sum(1 for v in a.get('vorlagen') or [] if v.get('rolle') == 'vorbild')
        if a['art'] != 'verbessern' or not n or not pixel:
            return 1.0
        vz = self.s['verbessern'].get('vorlage') or {}
        return 1.0 + float(vz.get('zeitfaktor', 0.55)) * n * float(vz.get('megapixel', 1.0)) * 1024 ** 2 / pixel

    # ------------------------------------------------------------ Bibliothek

    def _ordner(self):
        """[(absoluter Ordner, Projektname)]: Wurzel („ohne Projekt“) und alle Unterordner."""
        out = [(self.wurzel, '')]
        try:
            for e in sorted(os.scandir(self.wurzel), key=lambda e: e.name.lower()):
                if e.is_dir() and not e.name.startswith(('.', '_')):
                    out.append((e.path, e.name))
        except OSError:
            pass
        return out

    def projekte(self):
        out = []
        for pfad, name in self._ordner()[1:]:
            try:
                anzahl = sum(1 for e in os.scandir(pfad) if e.is_file() and ist_medium(e.name))
            except OSError:
                anzahl = 0
            out.append({'name': name, 'anzahl': anzahl, 'aus_2wild': name == self.s['ordner_2wild']})
        return out

    def _bibliothek_stand(self):
        """Kurzer Fingerabdruck der Bibliothek, damit die Oberfläche nur bei Änderungen neu lädt."""
        teile = []
        for pfad, _ in self._ordner():
            try:
                for e in os.scandir(pfad):
                    if e.is_file() and (ist_medium(e.name) or e.name.endswith('.json')):
                        st = e.stat()
                        teile.append(f'{e.path}|{st.st_mtime_ns}|{st.st_size}')
            except OSError:
                continue
        return format(zlib.crc32('\n'.join(sorted(teile)).encode('utf-8')), '08x') + f'-{len(teile)}'

    def _jobs_2wild(self):
        jobs = self._lesen(self.jobs_2wild) or []
        out = {}
        for j in jobs if isinstance(jobs, list) else []:
            for o in j.get('outputs') or []:
                out[o.get('filename')] = j
        return out

    def _info_bilden(self, pfad, jobs):
        """Begleitdaten für eine Datei ohne .json: aus unseren PNG-Metadaten, 2Wild oder dem ComfyUI-Ablauf."""
        name = os.path.basename(pfad)
        video = name.lower().endswith(VIDEO_ENDUNGEN)
        texte = mp4_texte(pfad) if video else png_texte(pfad)
        eigen = _json(texte.get('werkstatt'))
        if isinstance(eigen, dict):
            info = dict(eigen, herkunft='studio')
        else:
            g = einstellungen_aus_graph(_json(texte.get('prompt')), (self.s.get('durchsichtig') or {}).get('vorlage'),
                                        self.s['video'].get('realismus'), self.s['video'].get('tauschen'))
            art = g.get('art') if g.get('art') in (VIDEO_ARTEN if video else BILD_ARTEN) else \
                ('video_text' if video else 'bild')
            info = {'herkunft': 'metadaten' if g.get('prompt') else 'unbekannt', 'art': art,
                    'prompt': g.get('prompt') or '', 'negativ': g.get('negativ') or '',
                    'variation': g.get('variation'), 'schritte': g.get('schritte'), 'cfg': g.get('cfg'),
                    'breite': g.get('breite'), 'hoehe': g.get('hoehe'), 'laenge_bilder': g.get('laenge_bilder'),
                    'modell_datei': g.get('modell_datei'), 'modell': modellname(g.get('modell_datei')),
                    'vorlagen': g.get('vorlagen') or []}
            if art == 'bearbeiten' and g.get('groesse_von'):
                info['groesse_von'] = g['groesse_von']
            if g.get('turbo') and not video:
                info['turbo'] = True
            if g.get('details') and art == 'bearbeiten':
                info['details'] = True
            if g.get('durchsichtig') and art == 'bild':
                info['durchsichtig'] = True
            if g.get('schnell'):
                info['schnell'] = True  # Bilder seit 26.09.2026, Videos seit 17.10.2026
            if g.get('int8') and not video:
                info['int8'] = True
            if g.get('verfahren') and art == 'freistellen':
                info.update(verfahren=g['verfahren'], modell='BiRefNet')
            if art == 'pose':
                info['modell'] = 'SDPose'
                if g.get('personen'):
                    info['personen'] = True
            if g.get('ausformulieren') and art == 'bild':
                info['ausformulieren'] = True
            if g.get('realismus') and video:
                info['realismus'] = True
            if g.get('tauschen') and video:
                info['tauschen'] = True
            if g.get('acc8') and video:
                info['acc8'] = True
            if g.get('dmad') and video:
                info['dmad'] = True
            j = jobs.get(name)
            if j:
                info.update(herkunft='2wild', prompt=j.get('prompt') or info['prompt'],
                            negativ=j.get('negative', info['negativ']) or '',
                            variation=j.get('seed', info['variation']), schritte=j.get('steps', info['schritte']),
                            cfg=j.get('cfg', info['cfg']), breite=j.get('width', info['breite']),
                            hoehe=j.get('height', info['hoehe']), rechenzeit_s=j.get('elapsed'),
                            modell=j.get('model') or info['modell'],
                            erstellt=time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(j['created'])) if j.get('created') else None)
                if j.get('length'):
                    info['laenge_bilder'] = j['length']
        if not video and not info.get('breite'):
            info['breite'], info['hoehe'] = png_masse(pfad)
        info.setdefault('erstellt', time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(os.path.getmtime(pfad))))
        info.update(format=FORMAT, datei=name, anbieter='lokal', kosten_usd=None)
        return info

    def _info(self, pfad, stat, jobs):
        """Begleitdaten aus `<datei>.json`; fehlen sie, werden sie einmal angelegt (außer bei ganz frischen Dateien)."""
        begleit = pfad + '.json'
        try:
            bst = os.stat(begleit)
        except OSError:
            bst = None
        schluessel = (pfad, stat.st_mtime_ns, stat.st_size, bst.st_mtime_ns if bst else None)
        treffer = self._infos.get(pfad)
        if treffer and treffer[0] == schluessel:
            return treffer[1]
        info = self._lesen(begleit) if bst else None
        if isinstance(info, dict) and info.get('art') == 'video' and info.get('herkunft') != 'studio':
            info = None  # vor Stufe 3b angelegt: einmal neu erschließen, um die genaue Video-Art zu kennen
        if not isinstance(info, dict):
            if time.time() - stat.st_mtime < 10:
                return None  # ComfyUI schreibt vielleicht noch
            info = self._info_bilden(pfad, jobs)
            try:
                if bst:
                    self._schreiben(begleit, info)  # alte Video-Begleitdatei (vor Stufe 3b) gezielt neu erschließen
                else:
                    self._anlegen_exklusiv(begleit, info)  # nie eine inzwischen geschriebene Begleitdatei ersetzen
                bst = os.stat(begleit)
            except OSError:
                pass
            schluessel = (pfad, stat.st_mtime_ns, stat.st_size, bst.st_mtime_ns if bst else None)
        self._infos[pfad] = (schluessel, info)
        return info

    def _anlegen_exklusiv(self, pfad, daten):
        """Begleitdatei nur anlegen, wenn es sie noch nicht gibt (Umbenennen scheitert unter Windows am Ziel)."""
        tmp = f'{pfad}.{os.getpid()}-{threading.get_ident()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, indent=1)
        try:
            os.rename(tmp, pfad)
        except FileExistsError:
            os.remove(tmp)

    def bibliothek(self, neu=False):
        with self._bib_lock:
            if not neu and self._bib[1] is not None and time.time() - self._bib[0] < 2:
                return self._bib[1]
            jobs = None
            eintraege = []
            for ordner, projekt in self._ordner():
                try:
                    dateien = [e for e in os.scandir(ordner) if e.is_file() and ist_medium(e.name)]
                except OSError:
                    continue
                for e in dateien:
                    st = e.stat()
                    if jobs is None and not os.path.exists(e.path + '.json'):
                        jobs = self._jobs_2wild()
                    info = self._info(e.path, st, jobs or {})
                    if isinstance(info, dict) and 'maske' in info:
                        # Die Markierung holt die Oberfläche nur bei Bedarf (Aktion „maske“).
                        info = dict({k: w for k, w in info.items() if k != 'maske'}, hat_maske=True)
                    eintraege.append({'pfad': relativ(e.path, self.wurzel), 'name': e.name, 'projekt': projekt,
                                      'medium': 'video' if e.name.lower().endswith(VIDEO_ENDUNGEN) else 'bild',
                                      'groesse': st.st_size, 'zeit': st.st_mtime, 'info': info})
            eintraege.sort(key=lambda x: -x['zeit'])
            self._bib = (time.time(), {'eintraege': eintraege, 'projekte': self.projekte(),
                                       'stand': self._bibliothek_stand()})
            return self._bib[1]

    def datei(self, rel):
        """Absoluter Pfad einer Mediendatei der Bibliothek (für die Anzeige) oder einer 3D-Datei daneben, sonst None."""
        pfad = absolut(rel, self.wurzel)
        name = os.path.basename(pfad) if pfad else ''
        return pfad if pfad and (ist_medium(name) or ist_3d(name)) and os.path.isfile(pfad) else None

    @staticmethod
    def _begleiter(pfad):
        """Dateien, die mit einer Mediendatei zusammengehören: Begleitdaten und die 3D-Datei gleichen Stamms."""
        out = []
        for b in (pfad + '.json', os.path.splitext(pfad)[0] + '.glb'):
            if os.path.exists(b):
                out.append(b)
        return out

    def vorlage_datei(self, pfad, von=None):
        """Bild von außerhalb des Studios für die Anzeige (Markieren, Vorher/Nachher) oder None.

        Nur, wenn Sascha es in diesem Lauf selbst gewählt hat, ein Auftrag es als Vorlage nutzt oder das Studio-Bild
        `von` (relativer Pfad) darauf verweist. Andere Dateien des Rechners zeigt die Werkstatt nicht.
        """
        p = os.path.normpath(str(pfad or ''))
        if not os.path.isabs(p) or not p.lower().endswith(BILD_ENDUNGEN) or not os.path.isfile(p):
            return None
        gleich = lambda x: isinstance(x, str) and os.path.normcase(os.path.normpath(x)) == os.path.normcase(p)  # noqa: E731
        if os.path.normcase(p) in self._gewaehlt:
            return p
        with self._lock:
            if any(v.get('art') == 'datei' and gleich(v.get('pfad')) for a in self.auftraege for v in a.get('vorlagen') or []):
                return p
        ziel = self.datei(von) if von else None
        info = self._lesen(ziel + '.json') if ziel else None
        if isinstance(info, dict) and any(gleich(v.get('pfad') if isinstance(v, dict) else v)
                                          for v in info.get('vorlagen') or []):
            return p
        return None

    def maske_lesen(self, rel):
        """Die gespeicherte Markierung eines verbesserten Bildes (aus der Begleitdatei, sonst aus dem PNG)."""
        pfad = self.datei(rel)
        if not pfad:
            return 404, {'fehler': 'Die Datei gibt es nicht (mehr).'}
        for quelle in (lambda: self._lesen(pfad + '.json'), lambda: _json(png_texte(pfad).get('werkstatt'))):
            info = quelle()
            if isinstance(info, dict) and isinstance(info.get('maske'), dict):
                return 200, {'maske': info['maske']}
        return 404, {'fehler': 'Zu dieser Datei ist keine Markierung gespeichert.'}

    # ------------------------------------------------------------ Bedienung

    def _vorlage(self, v, endungen):
        """Eine Vorlage aus dem Formular prüfen -> {'art', 'pfad', 'rolle'} oder ValueError."""
        pfad = str(v.get('pfad') or '')
        if v.get('art') == 'bibliothek' and self.datei(pfad) and pfad.lower().endswith(endungen):
            return {'art': 'bibliothek', 'pfad': pfad, 'rolle': v.get('rolle') or 'vorlage'}
        if v.get('art') == 'datei' and os.path.isfile(pfad) and pfad.lower().endswith(endungen):
            return {'art': 'datei', 'pfad': os.path.normpath(pfad), 'rolle': v.get('rolle') or 'vorlage'}
        raise ValueError('Eine Vorlage gibt es nicht (mehr) oder sie hat die falsche Art (Bild bzw. Clip).')

    def _vorlagen(self, art, liste):
        """Vorlagen je Art prüfen: Bearbeiten (Bilder), Video aus Bild (Start, Ende), Video mit Referenz (Bilder, Clips)."""
        liste = [v for v in (liste or []) if isinstance(v, dict)]
        rolle = lambda v: v.get('rolle') or 'vorlage'  # noqa: E731
        if art == 'bearbeiten':
            out = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'vorlage'][:int(self.s['max_vorlagen'])]
            if not out:
                raise ValueError('Zum Bearbeiten bitte mindestens eine Vorlage wählen.')
            return out
        if art in ('verbessern', 'freistellen', 'pose'):
            out = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'original'][:1]
            if not out:
                raise ValueError({'verbessern': 'Bitte das Bild wählen, in dem eine Stelle verbessert werden soll.',
                                  'freistellen': 'Bitte das Bild wählen, das freigestellt werden soll.',
                                  'pose': 'Bitte das Bild wählen, aus dem die Pose kommen soll.'}[art])
            if art == 'verbessern':
                # Stufe 3n: freiwillig ein Vorbild für die Stelle („Bild 2“, eigene Rolle, damit Vorlagen vom
                # Bearbeiten nicht unbemerkt mitgehen); das Original bleibt das erste.
                n = int((self.s['verbessern'].get('vorlage') or {}).get('max', 1))
                out += [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'vorbild'][:n]
            return out
        if art == 'video_bild':
            start = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'start'][:1]
            ende = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'ende'][:1]
            if not start:
                raise ValueError('Für ein Video aus einem Bild bitte ein Startbild wählen.')
            return start + ende
        if art == 'video_referenz':
            v_cfg = self.s['video']
            bilder = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'bild'][:int(v_cfg['max_referenzbilder'])]
            clips = [self._vorlage(v, VIDEO_ENDUNGEN) for v in liste if rolle(v) == 'clip'][:int(v_cfg['max_clips'])]
            if not bilder and not clips:
                raise ValueError('Für ein Video mit Referenz bitte mindestens ein Bild oder einen Clip wählen.')
            return bilder + clips
        if art == 'video_weiter':
            # Nur Studio-Videos aus der Bibliothek (Maße und Ton werden geprüft); keine Dateien von außerhalb.
            out = []
            for r in ('ausgang', 'ziel'):
                for v in [v for v in liste if rolle(v) == r][:1]:
                    if v.get('art') != 'bibliothek':
                        raise ValueError('Weiterführen geht nur mit Videos aus der Bibliothek des Studios.')
                    out.append(self._vorlage(v, ('.mp4',)))
            return out
        return []

    def _pruefen(self, d):
        """Einstellungen aus dem Formular prüfen -> Auftragsfelder (ohne id/zustand)."""
        s = self.s
        art = d.get('art')
        if art not in BILD_ARTEN + VIDEO_ARTEN + MODELL_ARTEN:
            raise ValueError('Unbekannte Art.')
        if art in MODELL_ARTEN:
            return self._modell3d_pruefen(d)
        if art == 'video_weiter':
            return self._weiter_pruefen(d)
        if art in VIDEO_HILFS_ARTEN:
            return self._video_hilfe_pruefen(d)
        video = art in VIDEO_ARTEN
        prompt = str(d.get('prompt') or '').strip()
        motiv = verfahren = None
        if art == 'freistellen':
            # Beim Freistellen sagt man nur, was bleiben soll (leer: das Hauptmotiv); der Prompt kommt aus der Vorlage.
            motiv = prompt[:300]
            if d.get('verfahren') == 'schnell':
                # Schnell (BiRefNet, Stufe 3l) kennt keine Beschreibung: nur das Hauptmotiv.
                if motiv:
                    raise ValueError('Das schnelle Freistellen nimmt immer das Hauptmotiv. Für eine Beschreibung wie „den '
                                     'Hund“ stellt Qwen frei.')
                if not self.freistellen_schnell_verfuegbar():
                    raise ValueError('Das schnelle Freistellen ist nicht eingerichtet: BiRefNet fehlt in ComfyUI.')
                verfahren = 'schnell'
            prompt = freistellen_prompt(s, motiv)
        if art == 'pose':
            if not self.pose_verfuegbar():
                raise ValueError('Die Art „Pose“ ist nicht eingerichtet: SDPose fehlt in ComfyUI.')
            prompt = (s.get('pose') or {}).get('beschreibung') or 'Pose-Skelett'
        ohne_qwen = art in HILFS_ARTEN or verfahren == 'schnell'
        if not prompt:
            raise ValueError('Bitte beschreiben, was entstehen soll.')
        if len(prompt) > 6000:
            raise ValueError('Der Prompt ist zu lang (höchstens 6.000 Zeichen).')
        projekt = str(d.get('projekt') or '')
        if projekt and projekt not in {p['name'] for p in self.projekte()}:
            raise ValueError('Dieses Projekt gibt es nicht (mehr).')
        stufen = s['video']['qualitaet'] if video else s['qualitaet']
        if ohne_qwen:
            schritte, turbo, q = 1, False, None  # kein Sampler, keine Qualitätsstufe
        else:
            schritte = int(d.get('schritte') or next(q['schritte'] for q in stufen if q.get('standard')))
            # Turbo nur für Bilder und nur auf ausdrücklichen Wunsch (so bleiben ältere Aufträge bei „Nochmal“ gleich).
            turbo = not video and d.get('turbo') is True
            # Offizielles Turbo-Modell nur für neue Aufträge (Feld turbo_modell), sonst bleiben ältere bei „Nochmal“ gleich.
            turbo_modell = turbo and d.get('turbo_modell') is True and self.turbo_modell_verfuegbar()
            if turbo:
                if not turbo_modell and not self.turbo_verfuegbar():
                    raise ValueError('Die Stufe „Turbo“ ist nicht eingerichtet: Die Turbo-LoRA fehlt in ComfyUI.')
                schritte = len(s['turbo']['modell_sigmas' if turbo_modell else 'sigmas'])
            if not 1 <= schritte <= 80:
                raise ValueError('Ungültige Qualität.')
            q = next((q for q in stufen if (bool(q.get('turbo')) if turbo else q['schritte'] == schritte and not q.get('turbo'))),
                     None)
        # Detail-LoRA nur beim Bearbeiten und nur auf ausdrücklichen Wunsch (ältere Aufträge bleiben gleich).
        details = art == 'bearbeiten' and d.get('details') is True
        if details and not self.details_verfuegbar():
            raise ValueError('„Details auffrischen“ ist nicht eingerichtet: Die Detail-LoRA fehlt in ComfyUI.')
        # Durchsichtiger Hintergrund nur für neue Bilder; schnellere Aufmerksamkeit (Qwen-Bilder, seit 17.10.2026 auch
        # MiniMax-Videos) und INT8 (nur Qwen-Bilder) nur auf ausdrücklichen Wunsch (die Oberfläche fragt sie für neue
        # Aufträge an, „Nochmal“ älterer Aufträge ohne sie bleibt gleich). Ausformulieren nur für neue Bilder ohne
        # durchsichtigen Hintergrund.
        durchsichtig = art == 'bild' and d.get('durchsichtig') is True and bool(s.get('durchsichtig'))
        schnell = d.get('schnell') is True and (self.video_schnell_verfuegbar() if video
                                                else not ohne_qwen and self.schnell_verfuegbar())
        int8 = not video and not ohne_qwen and d.get('int8') is True and self.int8_verfuegbar()
        ausformulieren = art == 'bild' and not durchsichtig and d.get('ausformulieren') is True
        if ausformulieren and not self.ausformulieren_verfuegbar():
            raise ValueError('„Wunsch ausformulieren“ ist nicht eingerichtet: Der Prompt-Enhancer fehlt in ComfyUI.')
        # Pose-Skelett aller Personen (SAM3 sucht die Personen): wie INT8 nur für neue Aufträge und nur mit SAM3.
        personen = art == 'pose' and d.get('personen') is True and self.finden_verfuegbar()
        breite = hoehe = bilder = None
        # Beim Bearbeiten kommt die Größe von Vorlage 1, außer es ist ausdrücklich ein Format gewählt.
        groesse_von = ('format' if d.get('groesse_von') == 'format' else 'vorlage') if art == 'bearbeiten' else None
        aufloesung = None
        if groesse_von == 'vorlage':
            # Wie Vorlage 1, wahlweise größer (hochskalieren); nur die angebotenen Stufen
            aufloesung = int(d.get('aufloesung') or s['bearbeiten_aufloesung'])
            if aufloesung not in [int(x['wert']) for x in s.get('bearbeiten_aufloesungen') or []] + [int(s['bearbeiten_aufloesung'])]:
                raise ValueError('Ungültige Größe.')
        if art not in ('bearbeiten', 'verbessern', 'freistellen', 'pose') or groesse_von == 'format':
            raster = 32 if video else 16  # H3 rechnet in 32er-Schritten, Qwen in 16ern
            breite, hoehe = int(d.get('breite') or 0) // raster * raster, int(d.get('hoehe') or 0) // raster * raster
            # Bilder bis etwa 4 MP (am 24.09.2026 mit 2752×1536 geprüft), Videos wie bisher bis 2048 px
            seite, pixel = (2048, 2048 * 2048) if video else (int(s.get('max_seite', 2048)), int(s.get('max_pixel', 2048 * 2048)))
            if not (256 <= breite <= seite and 256 <= hoehe <= seite) or breite * hoehe > pixel:
                raise ValueError(f'Breite und Höhe müssen zwischen 256 und {seite} Pixeln liegen'
                                 + ('.' if video else f', zusammen höchstens {pixel / 1e6:.1f} Megapixel.'.replace('.', ',', 1)))
        if video:
            standard = next(x['bilder'] for x in s['video']['laengen'] if x.get('standard'))
            bilder = bilder_raster(d.get('bilder') or standard)
        vorlagen = self._vorlagen(art, d.get('vorlagen'))
        extra = self._verbessern_pruefen(d, vorlagen[0], vorbild=len(vorlagen) > 1) if art == 'verbessern' else {}
        if extra.get('maske'):
            breite, hoehe = extra['maske']['breite'], extra['maske']['hoehe']
        variation = d.get('variation')
        variation = int(variation) if variation not in (None, '') else None
        if variation is not None and not 0 <= variation < 2 ** 53:
            raise ValueError('Die Variationsnummer ist ungültig.')
        cfg_wert = float(d.get('cfg') or s['cfg'])
        if not 0 < cfg_wert <= 20:
            raise ValueError('Ungültiger CFG-Wert.')
        quelle = str(d['quelle'])[:300] if d.get('quelle') else None
        felder = {'projekt': projekt, 'art': art, 'prompt': prompt, 'negativ': '' if video else str(d.get('negativ') or '').strip()[:2000],
                  'breite': breite, 'hoehe': hoehe, 'schritte': schritte, 'qualitaet': q['name'] if q else None,
                  'cfg': None if video else cfg_wert, 'variation': variation, 'vorlagen': vorlagen, 'quelle': quelle}
        if video:
            felder.update(bilder=bilder, turbo=schritte <= int(s['video']['turbo_bis_schritte']))
            felder.update(self._realismus(d))
            # DMAD nur für neue Videos aus Text bzw. Bild mit genau dmad.schritte Schritten (Feld dmad), wie INT8 bei Bildern.
            if art in ('video_text', 'video_bild') and d.get('dmad') is True and self.dmad_verfuegbar() \
                    and schritte == int((s['video'].get('dmad') or {}).get('schritte', 4)):
                felder['dmad'] = True
        if art == 'video_referenz':
            felder.update(referenz_genau='max' if d.get('referenz_genau') == 'max' else 'match',
                          ton_behalten=d.get('ton_behalten') is not False)
            felder.update(self._tauschen(d, vorlagen))
            # Nur neue Aufträge (Feld acc8), damit „Nochmal“ älterer Videos gleich bleibt – wie INT8 bei Bildern.
            if d.get('acc8') is True and schritte == int((s['video'].get('acc8') or {}).get('schritte', 8)) \
                    and self.acc8_verfuegbar() and not felder.get('tauschen'):  # beim Tauschen kam die Figur zusätzlich
                felder['acc8'] = True
            ref = self._ref_bilder(vorlagen)
            if ref:
                felder['ref_bilder'] = ref
        if groesse_von:
            felder['groesse_von'] = groesse_von
        if aufloesung:
            felder['aufloesung'] = aufloesung
        if art == 'freistellen':
            felder.update(motiv=motiv, negativ='')
        if ohne_qwen:
            felder.update(negativ='', cfg=None)
        if verfahren:
            felder['verfahren'] = verfahren
        if turbo:
            felder['turbo'] = True
        if turbo and turbo_modell:
            felder['turbo_modell'] = True
        if details:
            felder['details'] = True
        if durchsichtig:
            felder['durchsichtig'] = True
        if schnell:
            felder['schnell'] = True
        if int8:
            felder['int8'] = True
        if ausformulieren:
            felder['ausformulieren'] = True
        if personen:
            felder['personen'] = True
        felder.update(extra)
        return felder

    def _verbessern_pruefen(self, d, original, vorbild=False):
        """Markierung (oder Stelle per Wort), Stärke, Ausschnitt und Arbeitsgröße zum Verbessern -> zusätzliche
        Auftragsfelder. Mit `stelle` statt Markierung sucht SAM3 die Stelle erst beim Rechnen (Stufe 3l); Ausschnitt und
        Arbeitsgröße kommen dann aus der gefundenen Maske (siehe _stelle_finden). `vorbild`: mit Bild 2 (Stufe 3n)."""
        pfad = self.datei(original['pfad']) if original['art'] == 'bibliothek' else original['pfad']
        staerken = [float(x['wert']) for x in self.s['verbessern']['staerken']]
        staerke = float(d.get('staerke') or next(float(x['wert']) for x in self.s['verbessern']['staerken']
                                                 if x.get('standard')))
        if not any(abs(staerke - x) < 1e-6 for x in staerken):
            raise ValueError('Ungültige Angabe, wie viel sich ändern darf.')
        stelle = re.sub(r'\s+', ' ', str(d.get('stelle') or '')).strip()[:100]
        if not d.get('maske') and stelle:
            if not self.finden_verfuegbar():
                raise ValueError('„Stelle per Wort finden“ ist nicht eingerichtet: SAM3 fehlt in ComfyUI.')
            groesse = png_masse(pfad) if pfad and pfad.lower().endswith('.png') else (None, None)
            return {'stelle': stelle, 'staerke': staerke, 'breite': groesse[0] or None, 'hoehe': groesse[1] or None}
        maske = maske_pruefen(d.get('maske'))
        if pfad and pfad.lower().endswith('.png'):
            groesse = png_masse(pfad)
            if groesse[0] and tuple(groesse) != (maske['breite'], maske['hoehe']):
                raise ValueError('Die Markierung passt nicht zur Bildgröße. Bitte die Stelle neu markieren.')
        return dict(self._maske_felder(maske, vorbild), staerke=staerke)

    def _maske_felder(self, maske, vorbild=False):
        """Ausschnitt, Arbeitsgröße und Anteil zu einer Markierung (von Hand oder gefunden). Mit Vorbild (Stufe 3n) ist der
        Ausschnitt kleiner (`vorlage.ausschnitt_faktor`), die Stelle bekommt so mehr Pixel: Ein Logo-Schriftzug war mit
        dem dreifachen Ausschnitt 0 von 4 richtig, mit dem doppelten 2 von 2; ein Gegenstand wurde nicht mehr am Rand der
        Markierung abgeschnitten (3 von 3 vollständig statt 2 von 4)."""
        rahmen, anzahl = maske_rahmen(maske)
        v = self.s['verbessern']
        if vorbild and (v.get('vorlage') or {}).get('ausschnitt_faktor'):
            v = dict(v, ausschnitt_faktor=v['vorlage']['ausschnitt_faktor'])
        ausschnitt, arbeit = ausschnitt_berechnen(rahmen, maske['breite'], maske['hoehe'], v)
        return {'maske': maske, 'ausschnitt': ausschnitt, 'arbeit': arbeit,
                'markiert': round(anzahl / (maske['breite'] * maske['hoehe']), 5)}

    def _weiter_quellen(self, vorlagen, pruefsummen=None):
        """Quellen eines Auftrags „Video weiterführen“ prüfen (echte Maße per mp4_info, SHA-256) ->
        [{'rolle', 'pfad', 'bilder', 'breite', 'hoehe', 'tonrate', 'tonkanaele', 'tondauer', 'sha256'}].
        Mit `pruefsummen` ({pfad: sha256}) muss der Inhalt unverändert sein (vor der Übergabe an ComfyUI)."""
        out = []
        for v in vorlagen:
            pfad = self.datei(v['pfad'])
            if not pfad:
                raise ValueError(f"Das Video {v['pfad']} gibt es nicht mehr.")
            try:
                info = mp4_info(pfad, int(self.s['video']['fps']))
            except (OSError, ValueError, struct.error) as ex:
                raise ValueError(f"Das Video {v['pfad']} lässt sich nicht weiterführen: {ex}.")
            if info['breite'] % 32 or info['hoehe'] % 32:
                raise ValueError(f"Das Video {v['pfad']} hat eine Größe, die MiniMax nicht rechnet "
                                 f"({info['breite']} × {info['hoehe']}).")
            summe = datei_pruefsumme(pfad)
            if pruefsummen is not None and pruefsummen.get(v['pfad']) != summe:
                raise ValueError(f"Das Video {v['pfad']} wurde seit dem Auftrag verändert oder ersetzt. Bitte den "
                                 'Auftrag mit dem aktuellen Video neu anlegen.')
            out.append({'rolle': v['rolle'], 'pfad': v['pfad'], 'bilder': info['bilder'], 'breite': info['breite'],
                        'hoehe': info['hoehe'], 'tonrate': info['tonrate'], 'tonkanaele': info['tonkanaele'],
                        'tondauer': info['tondauer'], 'sha256': summe})
        return out

    def _weiter_pruefen(self, d):
        """Auftrag „Video weiterführen“ (Stufe 3m) prüfen -> Auftragsfelder. Längen und Bereiche: weiter_bereiche."""
        v = self.s['video']
        fps = int(v['fps'])
        modus = d.get('modus')
        if modus not in WEITER_MODI:
            raise ValueError('Bitte wählen, wie das Video weitergeführt werden soll.')
        prompt = str(d.get('prompt') or '').strip()
        if not prompt:
            raise ValueError('Bitte beschreiben, was im neuen Stück geschieht.')
        if len(prompt) > 6000:
            raise ValueError('Der Prompt ist zu lang (höchstens 6.000 Zeichen).')
        projekt = str(d.get('projekt') or '')
        if projekt and projekt not in {p['name'] for p in self.projekte()}:
            raise ValueError('Dieses Projekt gibt es nicht (mehr).')
        braucht = {'verlaengern': ('ausgang',), 'davor': ('ziel',), 'verbinden': ('ausgang', 'ziel'),
                   'schleife': ('ausgang',)}[modus]
        vorlagen = [x for x in self._vorlagen('video_weiter', d.get('vorlagen')) if x['rolle'] in braucht]
        fehlt = [r for r in braucht if r not in {x['rolle'] for x in vorlagen}]
        if fehlt:
            raise ValueError({'ausgang': 'Bitte das Video wählen, an das angesetzt wird.',
                              'ziel': 'Bitte das Video wählen, vor das gesetzt wird.'}[fehlt[0]] if len(fehlt) == 1
                             else 'Bitte beide Videos wählen.')
        # „Nochmal“/„Variation“ schicken die Prüfsummen der Quellen mit: Hat ComfyUI den Namen einer Quelle inzwischen
        # neu vergeben (Zähler nach Papierkorb), würde sonst still ein anderes Video weitergeführt.
        pruefsummen = d.get('pruefsummen')
        if pruefsummen is not None and not (isinstance(pruefsummen, dict) and all(
                isinstance(k, str) and isinstance(w, str) for k, w in pruefsummen.items())):
            raise ValueError('Ungültige Prüfsummen.')
        quellen = self._weiter_quellen(vorlagen, pruefsummen)
        groessen = {(q['breite'], q['hoehe']) for q in quellen}
        if len(groessen) > 1:
            raise ValueError('Beide Videos müssen gleich groß sein ('
                             + ' und '.join(f"{b} × {h}" for b, h in sorted(groessen)) + ').')
        breite, hoehe = next(iter(groessen))
        neu_sekunden = None
        if d.get('clip_bilder') not in (None, ''):
            # „Nochmal“: die gespeicherte Clip-Länge, ohne neue Rundung – aber nur gültige Rasterwerte
            laenge = d['clip_bilder']
            if not weiter_laenge_ok(laenge):
                raise ValueError('Ungültige Länge des neuen Clips.')
        else:
            try:
                neu_sekunden = round(float(d.get('neu_sekunden') or 0), 3)
            except (TypeError, ValueError):
                raise ValueError('Ungültige Länge des neuen Stücks.')
            if not 0 < neu_sekunden <= 16:
                raise ValueError('Bitte eine Länge des neuen Stücks von etwa 3,5 bis 14 s angeben.')
            laenge = weiter_laenge(modus, neu_sekunden, fps)
            if laenge is None:
                raise ValueError('So lang kann ein neues Stück nicht werden (höchstens etwa 13 s).')
        try:
            schnitt_ende, schnitt_anfang = int(d.get('schnitt_ende') or 0), int(d.get('schnitt_anfang') or 0)
        except (TypeError, ValueError):
            raise ValueError('Ungültiger Schnitt.')
        ber = weiter_bereiche(modus, laenge, {q['rolle']: q['bilder'] for q in quellen}, schnitt_ende, schnitt_anfang)
        if ber['gesamt'] > WEITER_MAX_GESAMT:
            raise ValueError(f"Das fertige Video wäre {ber['gesamt'] / fps:.1f} s lang; mehr als ".replace('.', ',')
                             + f'{WEITER_MAX_GESAMT // fps} s sind nicht vorgesehen.')
        stufen = v['qualitaet']
        schritte = int(d.get('schritte') or next(x['schritte'] for x in stufen if x.get('standard')))
        if not 1 <= schritte <= 80:
            raise ValueError('Ungültige Qualität.')
        q = next((x for x in stufen if x['schritte'] == schritte), None)
        variation = d.get('variation')
        variation = int(variation) if variation not in (None, '') else None
        if variation is not None and not 0 <= variation < 2 ** 53:
            raise ValueError('Die Variationsnummer ist ungültig.')
        felder = {'projekt': projekt, 'art': 'video_weiter', 'prompt': prompt, 'negativ': '', 'breite': breite,
                  'hoehe': hoehe, 'schritte': schritte, 'qualitaet': q['name'] if q else None, 'cfg': None,
                  'variation': variation, 'vorlagen': vorlagen,
                  'quelle': str(d['quelle'])[:300] if d.get('quelle') else None,
                  'bilder': laenge, 'turbo': schritte <= int(v['turbo_bis_schritte']), 'modus': modus,
                  'clip_bilder': laenge, 'neu_bilder': ber['neu'][1], 'laenge_bilder': ber['gesamt'],
                  'schnitt_ende': schnitt_ende, 'schnitt_anfang': schnitt_anfang, 'quellen': quellen}
        if neu_sekunden is not None:
            felder['neu_sekunden'] = neu_sekunden
        felder.update(self._realismus(d))
        if d.get('schnell') is True and self.video_schnell_verfuegbar():
            felder['schnell'] = True  # schnellere Aufmerksamkeit, nur neue Aufträge (seit 17.10.2026)
        return felder

    def _video_hilfe_pruefen(self, d):
        """Zeitlupe bzw. Video freistellen (seit 09.10.2026) prüfen -> Auftragsfelder: ein Video (MP4) als „original“,
        ohne Prompt, Qualitätsstufe und Variationsnummer (gleiche Eingabe, gleiches Ergebnis)."""
        art = d['art']
        if art == 'video_zeitlupe' and not self.zeitlupe_verfuegbar():
            raise ValueError('„Zeitlupe“ ist nicht eingerichtet: Das Zwischenbild-Modell (RIFE) fehlt in ComfyUI.')
        if art == 'video_freistellen' and not self.video_freistellen_verfuegbar():
            raise ValueError('„Video freistellen“ ist nicht eingerichtet: SAM3 oder BiRefNet fehlt in ComfyUI.')
        projekt = str(d.get('projekt') or '')
        if projekt and projekt not in {p['name'] for p in self.projekte()}:
            raise ValueError('Dieses Projekt gibt es nicht (mehr).')
        liste = [x for x in d.get('vorlagen') or [] if isinstance(x, dict) and x.get('rolle') == 'original'][:1]
        if not liste:
            raise ValueError('Bitte das Video wählen.')
        vorlage = self._vorlage(liste[0], ('.mp4', '.mov'))
        pfad = self.datei(vorlage['pfad']) if vorlage['art'] == 'bibliothek' else vorlage['pfad']
        try:
            m = video_masse(pfad)
        except (OSError, ValueError, struct.error) as ex:
            raise ValueError(f'Das Video lässt sich nicht lesen ({ex}).')
        felder = {'projekt': projekt, 'art': art, 'prompt': '', 'negativ': '', 'breite': m['breite'], 'hoehe': m['hoehe'],
                  'schritte': None, 'qualitaet': None, 'cfg': None, 'variation': 0, 'vorlagen': [vorlage],
                  'quelle': str(d['quelle'])[:300] if d.get('quelle') else None, 'quell_bilder': m['bilder']}
        if art == 'video_zeitlupe':
            faktor = {'2': 2, '2.0': 2, '1.5': 1.5, '1,5': 1.5}.get(str(d.get('faktor')).strip())
            if faktor is None:
                raise ValueError('Bitte wählen, wie viel langsamer: 1,5-fach oder doppelt.')
            laenge = zeitlupe_laenge(m['bilder'], faktor)
            if laenge > WEITER_MAX_GESAMT:
                raise ValueError('Das Video wäre danach länger als 60 s; bitte ein kürzeres nehmen.')
            felder.update(faktor=faktor, bilder=laenge)
        else:
            motiv = str(d.get('motiv') or '').strip() or (self.s['video'].get('freistellen') or {}).get('motiv', 'person')
            if len(motiv) > 80:
                raise ValueError('Bitte das Motiv kurz benennen (englisch, etwa „person“ oder „dog“).')
            felder.update(motiv=motiv, bilder=m['bilder'],
                          verfahren=(self.s['video'].get('freistellen') or {}).get('verfahren', 'kombi'))
        return felder

    def _modell3d_pruefen(self, d):
        """3D-Modell (Stufe 3t) prüfen -> Auftragsfelder: ein Drehblatt (vier Ansichten nebeneinander, Rolle „vorlage“),
        ein einzelnes Bild (gleiche Rolle; `modus` bild, sonst erkannt am Seitenverhältnis) oder Einzelansichten (Rollen
        vorn/links/hinten/rechts). Ohne Prompt und Qualitätsstufe; Detailstufe und Variationsnummer bestimmen das Ergebnis."""
        m = self.s.get('modell3d') or {}
        if not self.modell3d_verfuegbar():
            raise ValueError('„3D-Modell“ ist nicht eingerichtet: Die Pixal3D-Dateien fehlen in ComfyUI.')
        projekt = str(d.get('projekt') or '')
        if projekt and projekt not in {p['name'] for p in self.projekte()}:
            raise ValueError('Dieses Projekt gibt es nicht (mehr).')
        liste = [v for v in d.get('vorlagen') or [] if isinstance(v, dict)]
        rolle = lambda v: v.get('rolle') or 'vorlage'  # noqa: E731
        einzel = {rolle(v): self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) in MODELL_ANSICHTEN}
        vorlagen = [self._vorlage(v, BILD_ENDUNGEN) for v in liste if rolle(v) == 'vorlage'][:1]
        modus = str(d.get('modus') or '').strip() or None
        breite = hoehe = None
        if einzel:
            if 'vorn' not in einzel:
                raise ValueError('Für Einzelansichten braucht es mindestens die Ansicht von vorn.')
            modus, vorlagen = 'ansichten', [einzel[n] for n in MODELL_ANSICHTEN if n in einzel]
        else:
            if not vorlagen:
                raise ValueError('Bitte ein Drehblatt (vier Ansichten nebeneinander) oder ein Bild des Gegenstands wählen.')
            v = vorlagen[0]
            breite, hoehe = bild_masse(self.datei(v['pfad']) if v['art'] == 'bibliothek' else v['pfad'])
            if modus not in ('drehblatt', 'bild'):
                # Ein Drehblatt ist sehr breit (vier Felder nebeneinander, etwa 4:1); alles andere gilt als ein Bild.
                modus = 'drehblatt' if breite and hoehe and breite >= 3 * hoehe else 'bild'
            if modus == 'drehblatt' and not (breite and hoehe):
                raise ValueError('Die Größe des Drehblatts ließ sich nicht lesen.')
        if modus == 'bild' and not self.modell3d_bild_verfuegbar():
            raise ValueError('„3D aus einem Bild“ ist nicht eingerichtet: Pixal3D (Einzelbild) oder MoGe fehlt in ComfyUI. '
                             'Ein Drehblatt mit vier Ansichten geht.')
        stufen = m.get('stufen') or []
        kennung = str(d.get('stufe') or '').strip() or next((x['id'] for x in stufen if x.get('standard')),
                                                             stufen[0]['id'] if stufen else '')
        stufe = next((x for x in stufen if x['id'] == kennung), None)
        if not stufe:
            raise ValueError('Unbekannte Detailstufe für das 3D-Modell.')
        variation = d.get('variation')
        try:
            variation = int(variation) if variation not in (None, '') else None
        except (TypeError, ValueError):
            raise ValueError('Die Variationsnummer muss eine ganze Zahl sein.')
        if variation is not None and not 0 <= variation < 2 ** 48:
            raise ValueError('Die Variationsnummer muss zwischen 0 und 2^48 liegen.')
        return {'projekt': projekt, 'art': 'modell3d', 'prompt': '', 'negativ': '', 'breite': breite, 'hoehe': hoehe,
                'schritte': None, 'qualitaet': None, 'cfg': None, 'variation': variation, 'vorlagen': vorlagen,
                'quelle': str(d['quelle'])[:300] if d.get('quelle') else None, 'modus': modus, 'stufe': kennung,
                'detail': {k: stufe[k] for k in ('aufloesung', 'dreiecke', 'textur', 'normalen') if k in stufe}}

    def _tauschen(self, d, vorlagen):
        """„Person tauschen“ bei „Video mit Referenz“ (Stufe 3q, seit 09.10.2026): nur auf ausdrücklichen Wunsch; genau ein
        Clip (das Video, in dem getauscht wird) und mindestens ein Bild (die neue Person)."""
        if d.get('tauschen') is not True:
            return {}
        if not self.tauschen_verfuegbar():
            raise ValueError('„Person tauschen“ ist nicht eingerichtet: Die Character-Swap-LoRA fehlt in ComfyUI.')
        clips = [v for v in vorlagen if v.get('rolle') == 'clip']
        if len(clips) != 1 or not any(v.get('rolle') == 'bild' for v in vorlagen):
            raise ValueError('Für „Person tauschen“ braucht es genau einen Clip (das Video, in dem getauscht wird) und ein '
                             'Bild der neuen Person.')
        return {'tauschen': True}

    def _ref_bilder(self, vorlagen):
        """Bilder aller Referenz-Clips (für die Zeitschätzung); unlesbare Clips zählen nicht."""
        summe = 0
        for v in vorlagen:
            if v.get('rolle') != 'clip':
                continue
            try:
                pfad = self.datei(v['pfad']) if v.get('art') == 'bibliothek' else v['pfad']
                summe += int(mp4_info(pfad, int(self.s['video']['fps']))['bilder']) if pfad else 0
            except (OSError, ValueError, KeyError, TypeError, struct.error):
                continue
        return summe

    def _realismus(self, d):
        """Realism-LoRA für Videos mit Personen (Stufe 3o): nur auf ausdrücklichen Wunsch, sonst bleiben ältere Videos bei
        „Nochmal“ gleich und Räume ohne Personen ohne sie (dort war sie schlechter)."""
        if d.get('realismus') is not True:
            return {}
        if not self.realismus_verfuegbar():
            raise ValueError('„Realistische Personen“ ist nicht eingerichtet: Die Realism-LoRA fehlt in ComfyUI.')
        return {'realismus': True}

    def erzeugen(self, d):
        try:
            felder = self._pruefen(d)
            anzahl = max(1, min(4, int(d.get('anzahl') or 1)))
        except (ValueError, TypeError) as e:
            return 400, {'fehler': str(e) if isinstance(e, ValueError) and str(e) else 'Ungültige Angaben.'}
        z = self.comfy_zustand(frisch=True)
        if not z['laeuft']:
            return 409, {'fehler': COMFY_AUS}
        if not z['ordner_ok']:
            return 409, {'fehler': AUSGABE_FALSCH}
        if (felder['variation'] is not None or felder['art'] in HILFS_ARTEN + VIDEO_HILFS_ARTEN
                or felder.get('verfahren') == 'schnell'):
            anzahl = 1  # feste Nummer, oder ohne Qwen gerechnet: gleiche Eingabe, gleiches Ergebnis
        neu = []
        with self._lock:
            for _ in range(anzahl):
                neu.append(self._anlegen(felder)['id'])
            self._speichern()
        self._wecker.set()
        return 200, {'neu': neu}

    def _anlegen(self, felder):
        """Einen geprüften Auftrag in die Warteschlange stellen (unter self._lock) -> Auftrag."""
        a = dict(felder, id=secrets.token_hex(4), zustand='wartet', schritt=None, meldung='', erstellt=time.time(),
                 dateien=[])
        if a['variation'] is None:
            a['variation'] = random.randint(1, 2 ** 48)
        self.auftraege.append(a)
        return a

    # ------------------------------------------------------------ Szenenfolge (Stufe 3p)
    # Szene 1 ist ein eigener Clip (aus Text, Startbild oder Referenzbildern), jede weitere verlängert das freigegebene
    # Video der Szene davor (Stufe 3m). Jede Szene bekommt den gemeinsamen Teil davor und den Zusatz gegen harte Schnitte
    # dahinter. Mit `pruefen` wartet die Folge nach jeder Szene auf „Passt“ oder „Nochmal“; der Zustand folgt immer aus dem
    # echten Zustand des aktuellen Auftrags (auch nach „Wiederholen“ in der Auftragsliste oder einem Neustart).

    def _folge_pruefen(self, d):
        """Angaben einer neuen Szenenfolge prüfen -> (Folge, geprüfte Felder des ersten Auftrags)."""
        v, sz = self.s['video'], self.s['video'].get('szenen') or {}
        fps = int(v['fps'])
        gemeinsam = str(d.get('gemeinsam') or '').strip()
        if not gemeinsam:
            raise ValueError('Bitte den gemeinsamen Teil beschreiben: wer zu sehen ist, Ort, Licht und Stil.')
        if len(gemeinsam) > 3000:
            raise ValueError('Der gemeinsame Teil ist zu lang (höchstens 3.000 Zeichen).')
        roh = d.get('szenen')
        if not isinstance(roh, list) or not roh:
            raise ValueError('Bitte mindestens eine Szene beschreiben.')
        if len(roh) > int(sz.get('max_szenen', 8)):
            raise ValueError(f"Höchstens {int(sz.get('max_szenen', 8))} Szenen.")
        szenen = []
        alle_real = d.get('realismus') is True  # ältere Aufrufe: ein Häkchen für alle Szenen
        for i, s in enumerate(roh, start=1):
            s = s if isinstance(s, dict) else {}
            text = str(s.get('text') or '').strip()
            if not text:
                raise ValueError(f'Szene {i} ist leer: Was geschieht, was macht die Kamera, was wird gesagt?')
            if len(text) > 2000:
                raise ValueError(f'Szene {i} ist zu lang (höchstens 2.000 Zeichen).')
            try:
                sekunden = round(float(s.get('sekunden')), 3)
            except (TypeError, ValueError):
                raise ValueError(f'Ungültige Länge bei Szene {i}.')
            if not 0 < sekunden <= 16:
                raise ValueError(f'Ungültige Länge bei Szene {i}.')
            # Realism-LoRA je Szene (seit 09.10.2026): leere Räume werden mit ihr schlechter, Szenen mit Personen besser.
            real = alle_real if s.get('realismus') is None else s.get('realismus') is True
            szenen.append({'text': text, 'sekunden': sekunden, 'realismus': real})
        if any(s['realismus'] for s in szenen):
            self._realismus({'realismus': True})  # Fehler, wenn die LoRA fehlt
        gesamt = bilder_raster(round(szenen[0]['sekunden'] * fps))
        for i, s in enumerate(szenen[1:], start=2):
            laenge = weiter_laenge('verlaengern', s['sekunden'], fps)
            if laenge is None:
                raise ValueError(f'Szene {i} ist zu lang (höchstens etwa 12,8 s).')
            gesamt += laenge - WEITER_FENSTER
        if gesamt > WEITER_MAX_GESAMT:
            raise ValueError(f'Alle Szenen zusammen wären {gesamt / fps:.1f} s lang; mehr als '.replace('.', ',')
                             + f'{WEITER_MAX_GESAMT // fps} s sind nicht vorgesehen.')
        rollen = {x.get('rolle') for x in d.get('vorlagen') or [] if isinstance(x, dict)}
        if 'bild' in rollen and 'start' in rollen:
            raise ValueError('Entweder ein Startbild oder Referenzbilder – nicht beides.')
        art = 'video_referenz' if 'bild' in rollen else 'video_bild' if 'start' in rollen else 'video_text'
        erste = self._pruefen({
            'art': art, 'prompt': szenen_prompt(sz, gemeinsam, szenen[0]['text']), 'projekt': d.get('projekt'),
            'breite': d.get('breite'), 'hoehe': d.get('hoehe'), 'bilder': round(szenen[0]['sekunden'] * fps),
            'schritte': d.get('schritte'), 'variation': d.get('variation'), 'vorlagen': d.get('vorlagen'),
            'referenz_genau': d.get('referenz_genau'), 'ton_behalten': d.get('ton_behalten'),
            'realismus': szenen[0]['realismus'], 'schnell': d.get('schnell')})
        f = {'id': secrets.token_hex(4), 'erstellt': time.time(), 'projekt': erste['projekt'], 'gemeinsam': gemeinsam,
             'szenen': szenen, 'breite': erste['breite'], 'hoehe': erste['hoehe'], 'schritte': erste['schritte'],
             'realismus': any(s['realismus'] for s in szenen), 'variation': erste['variation'],
             'pruefen': d.get('pruefen') is not False, 'gesamt_bilder': gesamt,
             'start': {'art': art, 'vorlagen': erste['vorlagen'], 'referenz_genau': erste.get('referenz_genau'),
                       'ton_behalten': erste.get('ton_behalten')},
             'szene': 0, 'takes': [[] for _ in szenen], 'freigegeben': [], 'datei': None,
             'zustand': 'laeuft', 'meldung': ''}
        if erste.get('schnell'):
            f['schnell'] = True  # alle Szenen mit schnellerer Aufmerksamkeit (seit 17.10.2026; ältere Folgen ohne)
        return f, erste

    def _szene_anlegen(self, f, felder=None):
        """Auftrag für die aktuelle Szene anlegen (unter self._lock): beim ersten Versuch mit der festen Nummer der Folge
        (falls angegeben), bei „Nochmal“ mit einer neuen. ValueError, wenn die Angaben nicht mehr passen."""
        i = f['szene']
        if felder is None:
            fps = int(self.s['video']['fps'])
            prompt = szenen_prompt(self.s['video'].get('szenen'), f['gemeinsam'], f['szenen'][i]['text'])
            if i == 0:
                d = {'art': f['start']['art'], 'prompt': prompt, 'projekt': f['projekt'], 'breite': f['breite'],
                     'hoehe': f['hoehe'], 'bilder': round(f['szenen'][0]['sekunden'] * fps), 'schritte': f['schritte'],
                     'vorlagen': f['start']['vorlagen'], 'referenz_genau': f['start'].get('referenz_genau'),
                     'ton_behalten': f['start'].get('ton_behalten')}
            else:
                d = {'art': 'video_weiter', 'modus': 'verlaengern', 'prompt': prompt, 'projekt': f['projekt'],
                     'neu_sekunden': f['szenen'][i]['sekunden'], 'schritte': f['schritte'],
                     'vorlagen': [{'art': 'bibliothek', 'pfad': f['freigegeben'][i - 1], 'rolle': 'ausgang'}]}
            real = f['szenen'][i].get('realismus')
            if f['realismus'] if real is None else real:  # Folgen vor dem 09.10.2026 kennen nur ein Häkchen für alle
                d['realismus'] = True
            if f.get('schnell'):
                d['schnell'] = True
            if not f['takes'][i] and f.get('variation_fest'):
                d['variation'] = f['variation']
            felder = self._pruefen(d)
        a = self._anlegen(dict(felder, folge={'id': f['id'], 'szene': i, 'szenen': len(f['szenen'])}))
        f['takes'][i].append(a['id'])
        f.update(zustand='laeuft', meldung='')
        return a

    def _folge_weiter(self, f):
        """Aktuelle Szene freigeben und die nächste anlegen bzw. die Folge abschließen (unter self._lock)."""
        f['freigegeben'] = f['freigegeben'][:f['szene']] + [f['datei']]
        if f['szene'] + 1 >= len(f['szenen']):
            f.update(zustand='fertig', meldung='', fertig_um=time.time())
            return
        f['szene'] += 1
        try:
            self._szene_anlegen(f)
        except (ValueError, TypeError) as e:
            f.update(zustand='fehler', meldung=f'Szene {f["szene"] + 1} ließ sich nicht anlegen: {e}')

    def _folgen_abgleichen(self):
        """Zustand jeder offenen Szenenfolge aus ihrem aktuellen Auftrag ableiten (unter self._lock)."""
        for f in self.folgen:
            if f.get('zustand') in ('fertig', 'abgebrochen'):
                continue
            ids = f['takes'][f['szene']]
            if not ids:
                f['zustand'] = 'fehler'  # die Meldung kommt von _folge_weiter
                continue
            a = self._finden(ids[-1])
            if a is None:
                f.update(zustand='fehler', meldung='Der Auftrag dieser Szene ist nicht mehr da; „Nochmal“ rechnet sie neu.')
            elif a['zustand'] in OFFEN:
                f.update(zustand='laeuft', meldung='')
            elif a['zustand'] == 'fertig' and a.get('dateien'):
                f['datei'] = a['dateien'][0]
                if f['pruefen']:
                    f.update(zustand='pruefen', meldung='')
                else:
                    self._folge_weiter(f)
            else:
                f.update(zustand='fehler', meldung=a.get('meldung') or 'Die Szene ist nicht fertig geworden.')

    def folge_neu(self, d):
        try:
            f, erste = self._folge_pruefen(d)
        except (ValueError, TypeError) as e:
            return 400, {'fehler': str(e) if isinstance(e, ValueError) and str(e) else 'Ungültige Angaben.'}
        z = self.comfy_zustand(frisch=True)
        if not z['laeuft']:
            return 409, {'fehler': COMFY_AUS}
        if not z['ordner_ok']:
            return 409, {'fehler': AUSGABE_FALSCH}
        f['variation_fest'] = d.get('variation') not in (None, '')
        with self._lock:
            self.folgen.append(f)
            self._szene_anlegen(f, erste)
            self._speichern()
        self._wecker.set()
        return 200, {'id': f['id'], 'neu': f['takes'][0]}

    def folge_aktion(self, fid, was):
        """passt (nächste Szene bzw. fertig), nochmal (aktuelle Szene mit neuer Nummer), beenden, entfernen."""
        with self._lock:
            self._folgen_abgleichen()
            f = next((x for x in self.folgen if x['id'] == fid), None)
            if not f:
                return 404, {'fehler': 'Diese Szenenfolge gibt es nicht mehr.'}
            if was == 'passt' and f['zustand'] == 'pruefen':
                self._folge_weiter(f)
            elif was == 'nochmal' and f['zustand'] in ('pruefen', 'fehler'):
                try:
                    self._szene_anlegen(f)
                except (ValueError, TypeError) as e:
                    return 400, {'fehler': str(e) or 'Ungültige Angaben.'}
            elif was == 'beenden' and f['zustand'] not in ('fertig', 'abgebrochen'):
                ids = f['takes'][f['szene']]
                a = self._finden(ids[-1]) if ids else None
                if a and a['zustand'] == 'wartet':
                    a.update(zustand='abgebrochen', meldung='Abgebrochen, bevor er begonnen hat.')
                elif a and a['zustand'] == 'laeuft':
                    self._abbruch.add(a['id'])
                f.update(zustand='abgebrochen', meldung='Beendet.')
            elif was == 'entfernen' and f['zustand'] in ('fertig', 'abgebrochen', 'fehler'):
                self.folgen.remove(f)
            else:
                return 409, {'fehler': 'Das geht in diesem Zustand nicht.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def aktion(self, aid, was):
        with self._lock:
            a = self._finden(aid)
            if not a:
                return 404, {'fehler': 'Diesen Auftrag gibt es nicht mehr.'}
            if was == 'abbrechen' and a['zustand'] in OFFEN:
                if a['zustand'] == 'wartet':
                    a.update(zustand='abgebrochen', meldung='Abgebrochen, bevor er begonnen hat.')
                else:
                    self._abbruch.add(aid)
            elif was == 'wiederholen' and a['zustand'] in ('fehler', 'abgebrochen'):
                a.update(zustand='wartet', schritt=None, meldung='', hinweis=None, dateien=[], prompt_id=None,
                         rechnen_ab=None, zwischenspeicher=None)
            elif was == 'entfernen' and a['zustand'] not in OFFEN:
                self.auftraege.remove(a)
            else:
                return 409, {'fehler': 'Das geht in diesem Zustand nicht.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def projekt_neu(self, name):
        try:
            name = projektname(name, reserviert=(self.s['ordner_2wild'],))
        except ValueError as e:
            return 400, {'fehler': str(e)}
        pfad = os.path.join(self.wurzel, name)
        if os.path.exists(pfad):
            return 409, {'fehler': f'Das Projekt „{name}“ gibt es schon.'}
        os.makedirs(pfad)
        self.log(f'Studio: Projekt angelegt ({len(name)} Zeichen)')
        return 200, {'name': name}

    def _in_arbeit(self):
        """Pfade der Bibliothek, die offene Aufträge noch als Vorlage brauchen."""
        with self._lock:
            return {p for a in self.auftraege if a['zustand'] in OFFEN for v in a.get('vorlagen', [])
                    if v['art'] == 'bibliothek' for p in [v['pfad']]}

    def verschieben(self, pfade, projekt):
        projekt = str(projekt or '')
        ziel = os.path.join(self.wurzel, projekt) if projekt else self.wurzel
        if projekt and (projekt not in {p['name'] for p in self.projekte()} or not os.path.isdir(ziel)):
            return 400, {'fehler': 'Dieses Projekt gibt es nicht (mehr).'}
        gesperrt = self._in_arbeit()
        verschoben, fehler = [], []
        with self._lock:
            for rel in pfade[:500]:
                quelle = self.datei(rel)
                if not quelle:
                    fehler.append(f'{rel}: nicht gefunden.')
                    continue
                if rel in gesperrt:
                    fehler.append(f'{os.path.basename(quelle)}: wird gerade als Vorlage verwendet.')
                    continue
                if os.path.normcase(os.path.dirname(quelle)) == os.path.normcase(ziel):
                    continue
                name = freier_name(ziel, os.path.basename(quelle))
                try:
                    shutil.move(quelle, os.path.join(ziel, name))
                    glb = os.path.splitext(quelle)[0] + '.glb'
                    glb_neu = os.path.splitext(name)[0] + '.glb'
                    if os.path.exists(glb):  # 3D-Datei gleichen Stamms zieht mit (Stufe 3t)
                        shutil.move(glb, os.path.join(ziel, glb_neu))
                    if os.path.exists(quelle + '.json'):
                        shutil.move(quelle + '.json', os.path.join(ziel, name + '.json'))
                        if name != os.path.basename(quelle):
                            info = self._lesen(os.path.join(ziel, name + '.json'))
                            if isinstance(info, dict):
                                info['datei'] = name
                                if info.get('modell_3d'):
                                    info['modell_3d'] = glb_neu
                                self._schreiben(os.path.join(ziel, name + '.json'), info)
                    neu_rel = relativ(os.path.join(ziel, name), self.wurzel)
                    for a in self.auftraege:
                        a['dateien'] = [neu_rel if x == rel else x for x in a.get('dateien', [])]
                    verschoben.append(neu_rel)
                except OSError as e:
                    fehler.append(f'{os.path.basename(quelle)}: {e.strerror or e}')
            self._speichern()
            self._bib = (0, None)
        return 200, {'verschoben': verschoben, 'fehler': fehler}

    def papierkorb(self, pfade):
        gesperrt = self._in_arbeit()
        ziele, fehler = [], []
        for rel in pfade[:500]:
            pfad = self.datei(rel)
            if not pfad:
                fehler.append(f'{rel}: nicht gefunden.')
            elif rel in gesperrt:
                fehler.append(f'{os.path.basename(pfad)}: wird gerade als Vorlage verwendet.')
            else:
                ziele += [pfad] + self._begleiter(pfad)
        if ziele and not winapi.in_papierkorb(ziele):
            return 500, {'fehler': 'Windows konnte die Dateien nicht in den Papierkorb legen.'}
        with self._lock:
            self._bib = (0, None)
        return 200, {'anzahl': len([z for z in ziele if ist_medium(os.path.basename(z))]), 'fehler': fehler}

    def zeigen(self, rel=None, projekt=None):
        """Explorer öffnen: eine Datei markiert oder einen Projektordner."""
        if rel:
            pfad = self.datei(rel)
            if not pfad:
                return 404, {'fehler': 'Die Datei gibt es nicht (mehr).'}
            subprocess.Popen(['explorer.exe', '/select,', pfad])
            return 200, {'ok': True}
        ordner = os.path.join(self.wurzel, projekt) if projekt else self.wurzel
        if not quellen.liegt_in(ordner, self.wurzel) or not os.path.isdir(ordner):
            return 404, {'fehler': 'Diesen Ordner gibt es nicht (mehr).'}
        os.startfile(ordner)
        return 200, {'ok': True}

    def vorlagen_waehlen(self, clips=False):
        besitzer = winapi.fenster_mit_titel('Werkstatt')
        if clips:
            pfade = winapi.dateien_waehlen('Clips wählen', 'Videos', list(VIDEO_ENDUNGEN), besitzer)
        else:
            pfade = winapi.dateien_waehlen('Bilder wählen', 'Bilder', list(BILD_ENDUNGEN), besitzer)
        pfade = [os.path.normpath(p) for p in pfade][:int(self.s['max_vorlagen'])]
        self._gewaehlt.update(os.path.normcase(p) for p in pfade)
        return 200, {'pfade': pfade}

    # ------------------------------------------------------------ Ablauf

    def _naechster(self, inst):
        """Erster wartender Auftrag, den dieser Prozess rechnen kann (unter `self._lock`). Prozess 2 nimmt nur, wenn er
        läuft, und nichts über zwei Karten; Videos auf einer Karte nimmt er zuerst, und Prozess 1 lässt sie ihm, solange
        er läuft (sonst legte Prozess 1 das Video über beide Karten, und ein Bild daneben müsste warten)."""
        if inst.nr > 1 and not self.comfy_zustand(inst=inst).get('laeuft'):
            return None
        wartend = [(x, self._bedarf(x)) for x in self.auftraege if x['zustand'] == 'wartet']
        wartend = [(x, b) for x, b in wartend if inst.kann(b) and self._wer_zuerst(b) in (None, inst)]
        return next((x for x, b in wartend if inst.bevorzugt(b)), wartend[0][0] if wartend else None)

    def _wer_zuerst(self, b):
        """Welcher Prozess soll einen Auftrag mit Bedarf `b` nehmen (unter `self._lock`)? None = wer zuerst kommt.

        Videos auf einer Karte der Ein-Karten-Prozess, solange er läuft. Sonst der erste freie Prozess, der den Auftrag
        jetzt ganz auf eine eigene Karte legen kann – Prozess 1 zuerst, damit die Suprim für ein Video daneben frei bleibt
        (gemessen 16.10.2026: Bild zuerst bestellt → Prozess 2 nahm es, das Video wartete). Grundlage ist der letzte
        Stand der Zentrale (`_lage_auffrischen`, höchstens 15 s alt); ohne ihn oder wenn nichts allein passt: None."""
        verfuegbar = [i for i in self.instanzen if i.nr == 1 or i.laeuft()]
        for i in verfuegbar:
            if i.bevorzugt(b):
                return i
        zeit, stand = self._stand_zentrale
        if len(verfuegbar) < 2 or not stand or time.time() - zeit > 15:
            return None
        rechnet = {x.get('prozess') for x in self.auftraege if x['zustand'] == 'laeuft'}
        for i in verfuegbar:
            if i.nr not in rechnet and i.kann(b):
                v, fehlend, _ = karten_waehlen(stand, b, i)
                if v and v['rang'] == 0 and not fehlend:
                    return i
        return None

    def _lage_auffrischen(self):
        """Vor dem Nehmen eines Auftrags (nur mit zwei Prozessen, außerhalb der Sperre): Zustand beider ComfyUI-Prozesse
        und Stand der Zentrale, höchstens alle 3 s; die Zentrale wird dafür nicht gestartet."""
        if len(self.instanzen) < 2:
            return
        for i in self.instanzen:
            self.comfy_zustand(inst=i)
        if time.time() - self._stand_zentrale[0] < 3:
            return
        try:
            code, antwort = self.zentrale.stand_ohne_start()
        except platz.NichtErreichbar:
            return
        if code == 200:
            self._monitor_merken(antwort)
            self._stand_zentrale = (time.time(), antwort)

    def _monitor_merken(self, antwort):
        monitor = {k['index'] for k in antwort.get('karten', []) if k.get('monitor')}
        for i in self.instanzen:
            i.auf_monitor = bool(i.karten and set(i.karten) & monitor)

    def _schleife(self, inst=None):
        inst = inst or self.instanzen[0]
        self._ort.inst = inst
        while True:
            if any(x['zustand'] == 'wartet' for x in self.auftraege):
                self._lage_auffrischen()
            with self._lock:
                a = self._naechster(inst)
                if a:
                    a.update(zustand='laeuft', begonnen=time.time(), meldung='', schritt=None, prozess=inst.nr)
                    self._speichern()
            if not a:
                self._wecker.wait(3)
                self._wecker.clear()
                continue
            groesse = f"{a['breite']}x{a['hoehe']}" if a.get('breite') else f"{len(a.get('vorlagen') or [])} Vorlagen"
            if a.get('bilder'):
                groesse += f", {a['bilder']} Bilder"
            self.log(f"Studio: Auftrag {a['id']} ({a['art']}, {groesse}, {a['schritte']} Schritte) in {inst.name}")
            try:
                self._durchfuehren(a)
                a.update(zustand='fertig', meldung='')
                self.log(f"Studio: Auftrag {a['id']} fertig in {a.get('rechenzeit_s')} s")
            except Abgebrochen:
                a.update(zustand='abgebrochen', meldung='Abgebrochen.')
            except ComfyAus:
                a.update(zustand='fehler', meldung='ComfyUI antwortet nicht mehr. ' + COMFY_AUS)
            except Fehler as f:
                a.update(zustand='fehler', meldung=str(f))
                self.log(f"Studio: Auftrag {a['id']} fehlgeschlagen ({a.get('schritt')})")
            except Exception as ex:
                a.update(zustand='fehler', meldung=f'Unerwarteter Fehler: {ex}')
                self.log(f"Studio: Auftrag {a['id']} unerwartet: " + traceback.format_exc(limit=4).replace('\n', ' | '))
            finally:
                with self._lock:
                    a.update(schritt=None, beendet=time.time())
                    self._abbruch.discard(a['id'])
                    self._bib = (0, None)
                    self._folgen_abgleichen()  # ohne Prüfen startet hier die nächste Szene
                    self._speichern()

    def _schritt(self, a, schritt, meldung):
        with self._lock:
            neu = a.get('schritt') != schritt
            a.update(schritt=schritt, meldung=meldung)
            if neu:
                self._speichern()

    def _pruefe_abbruch(self, a):
        if a['id'] in self._abbruch:
            raise Abgebrochen()

    def _warten(self, a, sekunden):
        frist = time.time() + sekunden
        while time.time() < frist:
            self._pruefe_abbruch(a)
            time.sleep(0.5)

    def _durchfuehren(self, a):
        # Keine gemeinsame GPU-Sperre mehr (16.10.2026, Sascha): Ob es losgeht, entscheidet der freie Speicher laut
        # Zentrale; der Auftrag meldet seinen Bedarf an und hält die Anmeldung, bis er fertig ist.
        while True:
            self._pruefe_abbruch(a)
            anmeldung, grund, geraete = self._platz(a)
            if grund is None:
                stopp = threading.Event()
                if anmeldung:
                    # Die Anmeldung gilt für den ganzen Ablauf (Hochladen, Übergabe, Rechnen, Abbrechen), nicht erst ab
                    # dem Rechnen (Astra, Stufe 8): ein eigener Faden verlängert sie alle 20 s.
                    threading.Thread(target=self._anmeldung_halten, args=(anmeldung, stopp, a), daemon=True).start()
                try:
                    return self._rechnen(a, anmeldung, geraete)
                finally:
                    stopp.set()
                    if anmeldung:
                        self.zentrale.abmelden(anmeldung['id'])
            self._schritt(a, 'platz', grund)
            self._warten(a, 10)

    def _anmeldung_halten(self, anmeldung, stopp, a):
        while not stopp.wait(20):
            code, _ = self.zentrale.halten(anmeldung['id'], 120)
            if code not in (0, 200):
                self.log(f"Studio: Anmeldung von Auftrag {a['id']} ließ sich nicht verlängern (Code {code}).")

    def _platz(self, a):
        """-> (anmeldung oder None, None, Geräte) wenn es losgehen kann, sonst (None, Grund zum Warten, None).

        Geräte: die gewählten Karten je Rolle (`karten_waehlen`), None für Abläufe ohne Kartenwahl."""
        self._schritt(a, 'platz', 'Fragt die Modellzentrale nach freiem Grafikspeicher …')
        try:
            code, antwort = self.zentrale.stand()
            if code != 200:
                raise platz.NichtErreichbar(antwort.get('fehler', f'Fehler {code}'))
            self._monitor_merken(antwort)
            # Ein Auftrag in ComfyUI selbst ist kein Hinderungsgrund: ComfyUI stellt ihn in seine Warteschlange.
            gruende = [g for g in antwort.get('gruende', []) if 'ComfyUI' not in g]
            if gruende:
                return None, 'Wartet: ' + ' '.join(gruende), None
            inst = self._inst()
            verteilung, fehlend, zusatz = karten_waehlen(antwort, self._bedarf(a), inst)
            if verteilung is None:
                return None, ('Die Modellzentrale meldet keine Grafikkarten.' if not antwort.get('karten') else
                              'Dieser Auftrag braucht zwei Grafikkarten; die Modellzentrale meldet nur eine.'), None
            if fehlend:
                return None, platz_text(antwort, fehlend, self.comfy_name), None
            karten = karten_text(antwort, verteilung)
            zweck = 'Video (Studio)' if a['art'] in VIDEO_ARTEN else 'Bild (Studio)'
            # Immer anmelden, auch ohne Zusatzbedarf (ComfyUI hält schon alles): Die Anmeldung sagt der Zentrale,
            # dass der laufende ComfyUI-Auftrag gedeckt ist; andere Aufträge rechnen dann daneben (keine GPU-Sperre).
            code, antwort = self.zentrale.anmelden(zusatz, zweck, dauer_s=120, schluessel=inst.schluessel)
            if code == 200:
                self.log(f"Studio: Auftrag {a['id']} rechnet auf {karten} ({inst.name})")
                with self._lock:
                    a['karten'] = karten
                return antwort['anmeldung'], None, verteilung['geraete']
            if code == 409:
                gruende = [g for g in antwort.get('gruende', []) if 'ComfyUI' not in g]
                if not gruende and 'ComfyUI' in ' '.join(antwort.get('gruende', [])):
                    return None, 'Wartet, bis ComfyUI seinen laufenden Auftrag fertig hat.', None
                return None, 'Wartet auf freien Grafikspeicher. ' + platz.warum_nicht(antwort, max(zusatz.values())), None
            raise platz.NichtErreichbar(antwort.get('fehler', f'Fehler {code}'))
        except platz.NichtErreichbar as e:
            return None, f'Die Modellzentrale antwortet nicht ({str(e)[:120]}). Neuer Versuch gleich.', None

    def _meta(self, a):
        """Was als Begleitdaten neben die Datei (und als „werkstatt“ ins PNG bzw. MP4) kommt."""
        s = self.s
        if a['art'] in MODELL_ARTEN:
            # Begleitdaten des Vorschau-Videos; die 3D-Datei (gleicher Stamm, .glb) kommt nach dem Rechnen dazu.
            m, v = s['modell3d'], s['modell3d']['vorschau']
            return {'format': FORMAT, 'herkunft': 'studio', 'art': a['art'], 'projekt': a['projekt'], 'prompt': '',
                    'negativ': '', 'variation': a['variation'], 'schritte': None, 'qualitaet': None, 'cfg': None,
                    'breite': int(v['groesse']), 'hoehe': int(v['groesse']),
                    'modell': m.get('modell_name', 'Pixal3D'),
                    'modell_datei': m['modelle']['einzelbild' if a['modus'] == 'bild' else 'multiview'],
                    'vorlagen': [{'pfad': x['pfad'], 'rolle': x.get('rolle', 'vorlage')} for x in a['vorlagen']],
                    'quelle': a.get('quelle'), 'auftrag': a['id'], 'anbieter': 'lokal', 'kosten_usd': None,
                    'modus': a['modus'], 'stufe': a['stufe'], 'detail': a['detail'],
                    'laenge_bilder': int(v['bilder']), 'sekunden': round(int(v['bilder']) / float(v['fps']), 2),
                    'vorlage_breite': a.get('breite'), 'vorlage_hoehe': a.get('hoehe')}
        video = a['art'] in VIDEO_ARTEN
        meta = {'format': FORMAT, 'herkunft': 'studio', 'art': a['art'], 'projekt': a['projekt'],
                'prompt': a['prompt'], 'negativ': a['negativ'], 'variation': a['variation'],
                'schritte': a['schritte'], 'qualitaet': a['qualitaet'], 'cfg': a['cfg'],
                'breite': a['breite'], 'hoehe': a['hoehe'],
                'modell': s['video']['modell_name'] if video else s['modell_name'],
                'modell_datei': s['video']['modelle']['ref2va' if a['art'] == 'video_referenz' else 'fl2va']
                if video else qwen_dateien(a, s)[0],
                'vorlagen': [{'pfad': v['pfad'], 'rolle': v.get('rolle', 'vorlage')} for v in a['vorlagen']],
                'quelle': a.get('quelle'), 'auftrag': a['id'], 'anbieter': 'lokal', 'kosten_usd': None}
        if video:
            meta.update(laenge_bilder=a['bilder'], sekunden=round(a['bilder'] / float(s['video']['fps']), 2),
                        turbo=a.get('turbo'), referenz_genau=a.get('referenz_genau'), ton_behalten=a.get('ton_behalten'))
        if a['art'] in VIDEO_HILFS_ARTEN:
            v = s['video']
            if a['art'] == 'video_zeitlupe':
                meta.update(modell='RIFE 4.25', modell_datei=v['zeitlupe']['modell'], faktor=a['faktor'])
            else:
                meta.update(modell='SAM3 + BiRefNet', modell_datei=v['freistellen']['sam3'], motiv=a['motiv'],
                            verfahren=a['verfahren'])
            meta.update(turbo=None, referenz_genau=None, ton_behalten=None, quell_bilder=a['quell_bilder'])
        if a['art'] == 'video_weiter':
            # Gesamtlänge (fertiges Video), Länge des neuen Clips und neue Bilder getrennt (Stufe 3m, „Nochmal“ nimmt
            # clip_bilder); die Quellen mit Prüfsumme, damit eine ersetzte Datei auffällt.
            meta.update(laenge_bilder=a['laenge_bilder'], sekunden=round(a['laenge_bilder'] / float(s['video']['fps']), 2),
                        modus=a['modus'], clip_bilder=a['clip_bilder'], neu_bilder=a['neu_bilder'],
                        schnitt_ende=a.get('schnitt_ende') or 0, schnitt_anfang=a.get('schnitt_anfang') or 0,
                        quellen=[{k: q[k] for k in ('rolle', 'pfad', 'bilder', 'sha256')} for q in a['quellen']],
                        referenz_genau=None, ton_behalten=None)
            if a.get('neu_sekunden'):
                meta['neu_sekunden'] = a['neu_sekunden']
        if a['art'] == 'verbessern':
            # Bei „Stelle per Wort“ kommen Maske, Ausschnitt und Arbeitsgröße erst beim Rechnen dazu (_stelle_finden).
            meta.update(staerke=a['staerke'], markiert=a.get('markiert'), ausschnitt=a.get('ausschnitt'),
                        arbeit=a.get('arbeit'), maske=a.get('maske'))
        if a['art'] == 'bearbeiten':
            meta['groesse_von'] = a.get('groesse_von') or 'vorlage'
            if a.get('aufloesung'):
                meta['aufloesung'] = a['aufloesung']
            if a.get('details'):
                meta['details'] = True
        if a['art'] == 'freistellen':
            meta['motiv'] = a.get('motiv') or ''
        if a.get('verfahren') == 'schnell':
            meta.update(verfahren='schnell', modell='BiRefNet', modell_datei=s['freistellen']['schnell_modell'], schritte=None)
        if a['art'] == 'pose':
            meta.update(modell='SDPose', modell_datei=s['pose']['modell'], schritte=None)
            if a.get('personen'):
                meta['personen'] = True
        if a['art'] == 'verbessern' and a.get('stelle'):
            meta['stelle'] = a['stelle']
        if a['art'] == 'bild' and a.get('durchsichtig'):
            meta['durchsichtig'] = True
        if a['art'] == 'bild' and a.get('ausformulieren'):
            meta['ausformulieren'] = True
        if not video and a.get('turbo'):
            meta['turbo'] = True
        if not video and a.get('turbo_modell'):
            meta['turbo_modell'] = True
        if a.get('schnell'):
            meta['schnell'] = True
        if not video and a.get('int8'):
            meta['int8'] = True
        if video and a.get('realismus'):
            meta['realismus'] = True
        if video and a.get('tauschen'):
            meta['tauschen'] = True
        if video and a.get('acc8'):
            meta['acc8'] = True
        if video and a.get('dmad'):
            meta['dmad'] = True
        if a.get('folge'):
            meta['szenenfolge'] = {'id': a['folge']['id'], 'szene': a['folge']['szene'] + 1,
                                   'szenen': a['folge']['szenen']}
        return meta

    def _rechnen(self, a, anmeldung, geraete=None):
        inst = self._inst()
        s = mit_geraeten(self.s, geraete, inst.lokal)
        z = self.comfy_zustand(frisch=True)
        if not z['laeuft']:
            raise Fehler(COMFY_AUS)
        if not z['ordner_ok']:
            raise Fehler(AUSGABE_FALSCH)
        inst.letzte_rechenzeit = None
        namen = {}
        if a['vorlagen']:
            self._schritt(a, 'vorlagen', 'Vorlagen werden an ComfyUI übergeben …')
        for v in a['vorlagen']:
            if v['art'] == 'bibliothek':
                if not self.datei(v['pfad']):
                    raise Fehler(f"Die Vorlage {v['pfad']} gibt es nicht mehr.")
                name = v['pfad'] + ' [output]'  # ComfyUI liest direkt aus dem Studio, keine Kopie
            else:
                if not os.path.isfile(v['pfad']):
                    raise Fehler(f"Die Vorlage {v['pfad']} gibt es nicht mehr.")
                name = self._hochladen(v['pfad'])
            namen.setdefault(v.get('rolle', 'vorlage'), []).append(name)
        grundname = {'bearbeiten': 'Bearbeitet', 'bild': 'Bild', 'verbessern': 'Verbessert',
                     'freistellen': 'Freigestellt', 'pose': 'Pose', 'video_zeitlupe': 'Zeitlupe',
                     'video_freistellen': 'Freigestellt', 'modell3d': 'Modell'}.get(a['art'], 'Video')
        # Prozess 2 schreibt mit Zusatz („Bild-2_00003_.png“): ComfyUI zählt die Nummern nicht prozessübergreifend.
        praefix = (a['projekt'] + '/' if a['projekt'] else '') + grundname + inst.zusatz
        if a['art'] == 'verbessern' and a.get('stelle') and not a.get('maske'):
            self._stelle_finden(a, namen['original'][0], anmeldung)
        if a['art'] == 'video_weiter':
            # Unmittelbar vor der Übergabe: Quellen unverändert (Prüfsumme) und weiterhin verwendbar (Maße, Ton)?
            try:
                geprueft = self._weiter_quellen(a['vorlagen'], {q['pfad']: q['sha256'] for q in a['quellen']})
            except ValueError as ex:
                raise Fehler(str(ex))
            if [(q['rolle'], q['bilder']) for q in geprueft] != [(q['rolle'], q['bilder']) for q in a['quellen']]:
                raise Fehler('Die Länge eines Ausgangsvideos stimmt nicht mehr mit dem Auftrag überein.')
        meta = self._meta(a)
        if a['art'] in MODELL_ARTEN:
            graph = modell3d_graph(a, s['modell3d'], praefix, {r: n[0] for r, n in namen.items()})
        elif a['art'] == 'video_weiter':
            graph = weiter_graph(a, s['video'], praefix, {r: n[0] for r, n in namen.items()})
        elif a['art'] == 'video_zeitlupe':
            graph = zeitlupe_graph(a, s['video'], praefix, namen['original'][0])
        elif a['art'] == 'video_freistellen':
            graph = video_freistellen_graph(a, s['video'], praefix, namen['original'][0])
        elif a['art'] in VIDEO_ARTEN:
            graph = video_graph(a, s['video'], praefix, {
                'start': (namen.get('start') or [None])[0], 'ende': (namen.get('ende') or [None])[0],
                'bilder': namen.get('bild', []), 'clips': namen.get('clip', [])})
        elif a['art'] == 'verbessern':
            # Die Markierung geht als kleines Graustufen-PNG in ComfyUIs Eingangsordner, benannt nach ihrem Inhalt:
            # dieselbe Markierung ergibt denselben Namen (und damit „Nochmal“ dasselbe Bild).
            png = maske_png(a['maske'])
            name = f"werkstatt_maske_{hashlib.sha1(png).hexdigest()[:16]}.png"
            maske = self._hochladen_daten(png, name, ueberschreiben=True)
            graph = verbessern_graph(a, s, praefix, namen['original'][0], maske, namen.get('vorbild', []))
        elif a['art'] == 'freistellen':
            graph = (freistellen_schnell_graph if a.get('verfahren') == 'schnell' else freistellen_graph)(
                a, s, praefix, namen['original'][0])
        elif a['art'] == 'pose':
            graph = pose_graph(a, s, praefix, namen['original'][0])
        else:
            graph = bild_graph(a, s, praefix, namen.get('vorlage', []),
                               self._system_ausformulieren() if a.get('ausformulieren') else None)
        eintrag = self._comfy_rechnen(a, graph, meta, anmeldung)
        if a.get('ausformulieren'):
            # Die ausformulierte Beschreibung (PreviewAny, Knoten 63) steht in den Begleitdaten; der Wunsch bleibt der Prompt.
            text = ((eintrag.get('outputs') or {}).get('63') or {}).get('text') or []
            if text and isinstance(text[0], str):
                meta['prompt_ausformuliert'] = text[0].strip()[:8000]
        dateien, fehlend = self._ausgaben(eintrag)
        if not dateien and fehlend:
            # ComfyUI kennt das Ergebnis noch aus seinem Zwischenspeicher, die Datei wurde aber verschoben oder
            # gelöscht. Eine Eingabe, die SaveImage nicht kennt, ändert nur dessen Kennung: ComfyUI rechnet nicht
            # neu, speichert das Bild aber wieder.
            for n in graph.values():
                if n['class_type'] in ('SaveImage', 'SaveVideo', 'SaveWEBM', 'SaveGLB'):
                    n['inputs']['werkstatt_auftrag'] = a['id']
            dateien, fehlend = self._ausgaben(self._comfy_rechnen(a, graph, meta, anmeldung))
            a['zwischenspeicher'] = True  # nur neu gespeichert: zählt nicht als Rechenzeit
        if not dateien:
            raise Fehler('ComfyUI ist fertig, hat aber keine Datei im Studio abgelegt.')
        neu = [p for p in dateien if os.path.getmtime(p) >= a['rechnen_ab'] - 2]
        if not neu:
            # Gleiche Einstellungen, gleiche Variationsnummer: ComfyUI liefert die vorhandene Datei. Nichts doppelt
            # speichern und ihre Begleitdaten nicht überschreiben.
            with self._lock:
                a.update(dateien=[relativ(p, self.wurzel) for p in dateien], rechenzeit_s=None,
                         hinweis=f"Genau {'dieses Video' if a['art'] in VIDEO_ARTEN else 'dieses Bild'} gibt es "
                                 'schon; es wurde nicht doppelt gespeichert.')
            return
        rechenzeit = inst.letzte_rechenzeit or round(time.time() - a['rechnen_ab'], 1)
        if a['art'] in MODELL_ARTEN:
            neu = self._modell3d_ablegen(neu, meta)
        for pfad in neu:
            info = dict(meta, datei=os.path.basename(pfad), rechenzeit_s=rechenzeit,
                        erstellt=time.strftime('%Y-%m-%dT%H:%M:%S'))
            if not info.get('breite'):
                info['breite'], info['hoehe'] = png_masse(pfad)
            self._schreiben(pfad + '.json', info)
        with self._lock:
            a.update(dateien=[relativ(p, self.wurzel) for p in neu], rechenzeit_s=rechenzeit)

    def _modell3d_ablegen(self, neu, meta):
        """3D-Modell: Die GLB-Datei bekommt den Stamm ihres Vorschau-Videos (ComfyUI zählt beide getrennt hoch); nur das
        Video bekommt Begleitdaten, sie nennen die 3D-Datei. -> [Video]"""
        videos = [p for p in neu if p.lower().endswith(VIDEO_ENDUNGEN)]
        modelle = [p for p in neu if ist_3d(os.path.basename(p))]
        if not videos or not modelle:
            raise Fehler('ComfyUI hat die 3D-Datei oder ihre Vorschau nicht im Studio abgelegt.')
        video, glb = videos[0], modelle[0]
        ziel = os.path.splitext(video)[0] + '.glb'
        if os.path.normcase(ziel) != os.path.normcase(glb):
            if os.path.exists(ziel):
                ziel = os.path.join(os.path.dirname(ziel), freier_name(os.path.dirname(ziel), os.path.basename(ziel)))
            os.replace(glb, ziel)
        meta['modell_3d'] = os.path.basename(ziel)
        meta['modell_3d_bytes'] = os.path.getsize(ziel)
        return [video]

    def _stelle_finden(self, a, original, anmeldung):
        """Stelle per Wort (SAM3) suchen und als Markierung in den Auftrag schreiben (Stufe 3l). ComfyUI liefert die
        Maske verkleinert als Vorschau und die Größe des Originals; hochgerechnet wird sie hier. Danach läuft das
        Verbessern wie mit einer gemalten Markierung, die gefundene Maske steht in den Begleitdaten („Nochmal“ nimmt sie)."""
        self._schritt(a, 'finden', f"Sucht „{a['stelle']}“ im Bild …")
        eintrag = self._comfy_rechnen(a, finden_graph(self.s, original, a['stelle']), {}, anmeldung)
        aus = eintrag.get('outputs') or {}
        try:
            breite, hoehe = (int(str((aus.get(k) or {}).get('text', [''])[0]).strip()) for k in ('88', '89'))
            bild = next(o for o in (aus.get('99') or {}).get('images') or [] if o.get('filename'))
            daten = self._comfy_datei(bild)
            maske = maske_hochrechnen(*png_lesen(daten), breite, hoehe)
        except (StopIteration, ValueError, TypeError, zlib.error) as ex:
            raise Fehler(f'Die gefundene Stelle ließ sich nicht lesen ({ex}).')
        if not any(maske['rle'][1::2]):
            raise Fehler(f"Für „{a['stelle']}“ wurde im Bild nichts gefunden. Bitte anders beschreiben (am "
                         'verlässlichsten englisch, etwa „hand“ oder „face“) oder die Stelle von Hand markieren.')
        with self._lock:
            vorbild = any(v.get('rolle') == 'vorbild' for v in a.get('vorlagen') or [])
            a.update(self._maske_felder(maske, vorbild), breite=breite, hoehe=hoehe)
            self._speichern()

    def _comfy_datei(self, o):
        """Eine Ausgabedatei von ComfyUI holen (etwa eine Vorschau aus seinem temp-Ordner) -> bytes."""
        q = urllib.parse.urlencode({'filename': o['filename'], 'subfolder': o.get('subfolder') or '',
                                    'type': o.get('type') or 'temp'})
        try:
            with _OHNE_PROXY.open(self.comfy_url + '/view?' + q, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise Fehler(f'ComfyUI liefert die Datei nicht (Fehler {e.code}).')
        except (urllib.error.URLError, OSError) as e:
            raise ComfyAus(str(e))

    def _ausgaben(self, eintrag):
        """Bilddateien eines fertigen ComfyUI-Auftrags -> (vorhandene Pfade im Studio, Zahl der fehlenden)."""
        da, fehlend = [], 0
        for knoten in (eintrag.get('outputs') or {}).values():
            # SaveImage und SaveVideo melden ihre Dateien unter „images“ (Videos mit „animated“).
            for o in [x for liste in knoten.values() if isinstance(liste, list) for x in liste if isinstance(x, dict)]:
                if o.get('type') != 'output' or not o.get('filename'):
                    continue
                pfad = os.path.normpath(os.path.join(self.wurzel, o.get('subfolder') or '', o['filename']))
                if quellen.liegt_in(pfad, self.wurzel) and os.path.isfile(pfad):
                    da.append(pfad)
                else:
                    fehlend += 1
        return da, fehlend

    def _comfy_prozess(self):
        """PID des Prozesses, der auf dem Port dieses ComfyUI-Prozesses lauscht, oder None (auch wenn die Portliste
        nicht lesbar war)."""
        try:
            return next((p for _, port, p in winapi.lauschende_ports() if port == self.comfy_port), None)
        except OSError:
            return None

    def _comfy_rechnen(self, a, graph, meta, anmeldung):
        """Übergibt den Ablauf an ComfyUI und wartet auf das Ergebnis -> Verlaufseintrag von ComfyUI.

        Keine Antwort ist ein unbekannter Zustand, kein Stillstand (Regel: Sperre und Anmeldung bleiben, solange ComfyUI
        rechnen könnte): gewartet wird, bis ComfyUI wieder antwortet oder sein Prozess bestätigt beendet ist. Dafür
        wird vor der Übergabe ein Handle auf den ComfyUI-Prozess geöffnet und bis zum Ende gehalten."""
        self._pruefe_abbruch(a)
        handle = winapi.prozess_oeffnen(self._comfy_prozess())
        try:
            return self._comfy_rechnen_mit(a, graph, meta, anmeldung, handle)
        finally:
            winapi.handle_schliessen(handle)

    def _comfy_rechnen_mit(self, a, graph, meta, anmeldung, handle):
        # Eigene Kennung (Stufe 8, Astra): Geht die Antwort auf /prompt verloren, kennt das Studio den Auftrag trotzdem
        # und wartet wie sonst, statt die Anmeldung freizugeben, während ComfyUI vielleicht rechnet.
        pid = str(uuid.uuid4())
        try:
            antwort = self._comfy_anfrage('/prompt', {'prompt': graph, 'client_id': self.client_id, 'prompt_id': pid,
                                                      'extra_data': {'extra_pnginfo': {'werkstatt': meta}}}, timeout=30)
        except urllib.error.HTTPError as e:
            raise Fehler('ComfyUI lehnt den Auftrag ab: ' + _comfy_fehlertext(e))
        except ComfyAus:
            if winapi.prozess_beendet(handle) is True:
                raise
            antwort = {'prompt_id': pid}
            self.log(f"Studio: Antwort auf die Übergabe von Auftrag {a['id']} fehlt; es wird weiter auf ComfyUI gewartet.")
        pid = antwort.get('prompt_id') or pid
        if not pid:
            raise Fehler('ComfyUI hat den Auftrag nicht angenommen.')
        with self._lock:
            a.update(prompt_id=pid, rechnen_ab=time.time(), erwartet_s=self._erwartet(a))
            a.setdefault('prompt_ids', []).append(pid)
        self._schritt(a, 'rechnet', 'Rechnet …')
        letzter_puls, unbekannt, stumm = time.time(), 0, 0
        while True:
            if a['id'] in self._abbruch:
                self._schritt(a, 'abbrechen', 'Wird abgebrochen; ComfyUI beendet noch den laufenden Rechenschritt …')
                self._comfy_abbrechen(a, pid, anmeldung, handle)
                raise Abgebrochen()
            time.sleep(1)
            if anmeldung and time.time() - letzter_puls > 20:
                self.zentrale.halten(anmeldung['id'], 120)
                letzter_puls = time.time()
            try:
                eintrag = self._comfy_anfrage(f'/history/{pid}', timeout=10).get(pid)
                q = None if eintrag else self._comfy_anfrage('/queue', timeout=5)
            except (ComfyAus, urllib.error.HTTPError, ValueError):
                # Keine Antwort: weiter warten, bis ComfyUI wieder antwortet; verloren ist der Auftrag erst, wenn der
                # Prozess, dem er übergeben wurde, bestätigt beendet ist.
                if winapi.prozess_beendet(handle) is True:
                    raise ComfyAus('ComfyUI wurde beendet')
                stumm += 1
                if stumm == 30:
                    self._schritt(a, 'rechnet', 'ComfyUI antwortet gerade nicht; der Auftrag wartet …')
                continue
            if stumm >= 30:
                self._schritt(a, 'rechnet', 'Rechnet …')
            stumm = 0
            if eintrag:
                status = eintrag.get('status') or {}
                if status.get('status_str') == 'error':
                    raise Fehler('ComfyUI meldet einen Fehler: ' + _ausfuehrungsfehler(status))
                if status.get('completed'):
                    self._inst().letzte_rechenzeit = _rechenzeit(status)
                    return eintrag
                continue
            laufend = [x[1] for x in q.get('queue_running', [])]
            wartend = [x[1] for x in q.get('queue_pending', [])]
            if pid in wartend and pid not in laufend:
                self._schritt(a, 'comfy', 'ComfyUI rechnet noch einen anderen Auftrag; dieser ist als Nächstes dran.')
                with self._lock:
                    a['rechnen_ab'] = time.time()
            elif pid in laufend:
                if a.get('schritt') != 'rechnet':
                    self._schritt(a, 'rechnet', 'Rechnet …')
                unbekannt = 0
            else:
                unbekannt += 1
                if unbekannt >= 8:
                    raise Fehler('ComfyUI kennt den Auftrag nicht mehr (wurde es neu gestartet?).')

    def _comfy_abbrechen(self, a, pid, anmeldung=None, handle=None, hinweis_nach=90):
        """Auftrag in ComfyUI abbrechen und warten, bis er wirklich steht; bis dahin bleiben Sperre und Anmeldung
        (Regel). ComfyUI hört erst am Ende des laufenden Rechenschritts bzw. Knotens auf (Videos: bis etwa 15 s,
        Zusammensetzen auch länger). Ohne Frist: zu Ende ist das Warten erst, wenn ComfyUI den Auftrag nicht mehr führt
        oder sein Prozess bestätigt beendet ist. Der Abbruch geht alle 30 s erneut hinaus, die Anmeldung wird alle 20 s
        verlängert."""
        beginn = letzter_puls = time.time()
        gesendet, gemeldet = None, False
        while True:
            jetzt = time.time()
            if anmeldung and jetzt - letzter_puls > 20:
                self.zentrale.halten(anmeldung['id'], 120)
                letzter_puls = jetzt
            try:
                q = self._comfy_anfrage('/queue', timeout=5)
                laufend = [x[1] for x in q.get('queue_running', [])]
                if pid not in laufend + [x[1] for x in q.get('queue_pending', [])]:
                    return
                if gesendet is None or jetzt - gesendet >= 30:
                    if pid in laufend:
                        self._comfy_anfrage('/interrupt', {'prompt_id': pid}, timeout=10)
                    else:
                        self._comfy_anfrage('/queue', {'delete': [pid]}, timeout=10)
                    gesendet = jetzt
            except (ComfyAus, urllib.error.HTTPError, ValueError):
                if winapi.prozess_beendet(handle) is True:
                    return
            if not gemeldet and jetzt - beginn > hinweis_nach:
                self._schritt(a, 'abbrechen', 'ComfyUI hört noch nicht auf; die Grafikkarten bleiben gesperrt, bis es '
                                              'wirklich steht …')
                self.log(f'Studio: ComfyUI steht nach {hinweis_nach} s Abbruch noch nicht; es wird weiter gewartet')
                gemeldet = True
            time.sleep(1)


def _comfy_fehlertext(e):
    try:
        d = json.loads(e.read())
    except Exception:
        return f'Fehler {e.code}'
    teile = []
    for n in (d.get('node_errors') or {}).values():
        for f in n.get('errors') or []:
            teile.append(f"{f.get('message', '')}: {f.get('details', '')}".strip(': '))
    fehler = d.get('error') or {}
    text = '; '.join(teile) or f"{fehler.get('message', '')} {fehler.get('details', '')}".strip()
    return text[:400] or f'Fehler {e.code}'


def _ausfuehrungsfehler(status):
    for m in status.get('messages') or []:
        if m and m[0] == 'execution_error' and isinstance(m[1], dict):
            return str(m[1].get('exception_message') or m[1].get('exception_type') or 'unbekannt').strip()[:400]
    return 'unbekannt'


def _rechenzeit(status):
    """Rechenzeit laut ComfyUI (Beginn bis Ende der Ausführung) in Sekunden oder None."""
    zeiten = {m[0]: m[1].get('timestamp') for m in status.get('messages') or []
              if m and isinstance(m[1], dict) and m[1].get('timestamp')}
    if zeiten.get('execution_start') and zeiten.get('execution_success'):
        return round((zeiten['execution_success'] - zeiten['execution_start']) / 1000, 1)
    return None
