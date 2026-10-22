"""Fibo-Dienst: hält Fibo 2.0 auf einer RTX 3090 und rechnet Aufträge nacheinander.

Start (die Karte wählt die Modellzentrale über CUDA_VISIBLE_DEVICES):

    C:\\LLM\\runtimes\\Fibo2\\.venv\\Scripts\\python.exe <repo>\\fibo\\dienst.py --port 8098

Der Dienst spricht nur mit 127.0.0.1. Alle POST-Aufrufe brauchen die Kopfzeile
`X-Atelier: 1`, damit fremde Webseiten ihn nicht steuern können.

torch, diffusers und bria_vgl werden erst im Arbeiter bzw. im Beschreiber geladen.
So laufen die Tests mit der normalen Python ohne GPU; die Pipeline-Fabrik ist
austauschbar.
"""
import argparse
import base64
import binascii
import gc
import io
import json
import math
import os
import queue
import re
import secrets
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

FIBO_ORDNER = os.path.dirname(os.path.abspath(__file__))
STANDARD_CONFIG = os.path.join(FIBO_ORDNER, 'config.json')
MAX_ANFRAGE = 64 * 1024 * 1024
MAX_FLAECHE = 1_100_000
LIZENZ = 'Fibo 2.0 – CC BY-NC 4.0, nur nicht-kommerziell'
MODELL_KENNUNG = 'fibo-2.0'

# Negativprompts unverändert von der Modellseite (wie in fibo_reihe.py).
NEGATIVE_T2I = ('{"short_description":"","objects":[{"description":"the main subject","texture":"smooth, featureless, '
                'plastic-like, airbrushed, no fine surface detail","appearance_details":"soft blurred edges, simplified '
                'shapes, no fine detail","skin_tone_and_texture":"waxy airbrushed skin, poreless, plastic smooth"}],'
                '"background_setting":"a plain seamless studio backdrop, perfectly smooth gradient, blurred and '
                'featureless, no visible texture","lighting":{},"aesthetics":{"artifacts":["oversaturated colours",'
                '"neon colour cast","overexposed highlights","lens flare","slight blur","motion blur","haze"]},'
                '"photographic_characteristics":{"depth_of_field":"shallow, heavy bokeh obscuring most of the frame",'
                '"focus":"soft, slightly out of focus, lacking fine texture"},"style_medium":"","context":"",'
                '"artistic_style":""}')
NEGATIVE_EDIT = ('{"short_description":"","objects":[],"background_setting":"","lighting":{},"aesthetics":{},'
                 '"photographic_characteristics":{},"style_medium":"","context":"","artistic_style":""}')


class AnfrageFehler(Exception):
    """Verständliche Ablehnung eines Auftrags; `code` ist der HTTP-Code."""

    def __init__(self, text, code=400):
        super().__init__(text)
        self.text = text
        self.code = code


def _fehlertext(fehler):
    text = str(fehler).strip() or type(fehler).__name__
    return text[:400]


def karte_aus_umgebung():
    """Karte aus `CUDA_VISIBLE_DEVICES`, wenn dort genau eine ganze Zahl steht, sonst None.

    Die Zentrale setzt die Variable beim Start (z. B. „1“); stehen dort mehrere Karten oder
    etwas anderes, ist keine eindeutige Karte bekannt.
    """
    wert = (os.environ.get('CUDA_VISIBLE_DEVICES') or '').strip()
    return int(wert) if re.fullmatch(r'\d+', wert) else None


# ---------------------------------------------------------------- Größen und Bilder

def vielfaches(wert):
    """Auf ein Vielfaches von 16 runden, mindestens 16."""
    return max(16, int(round(float(wert) / 16.0)) * 16)


def flaeche_begrenzen(breite, hoehe, max_flaeche=MAX_FLAECHE):
    """Auf Vielfache von 16 runden und die Fläche auf `max_flaeche` begrenzen, Seitenverhältnis halten."""
    breite, hoehe = vielfaches(breite), vielfaches(hoehe)
    if breite * hoehe <= max_flaeche:
        return breite, hoehe
    faktor = math.sqrt(float(max_flaeche) / (breite * hoehe))
    breite, hoehe = vielfaches(breite * faktor), vielfaches(hoehe * faktor)
    while breite * hoehe > max_flaeche:
        if breite >= hoehe and breite > 16:
            breite -= 16
        elif hoehe > 16:
            hoehe -= 16
        else:
            break
    return breite, hoehe


def bildgroesse(bild, max_flaeche=MAX_FLAECHE):
    """Zielgröße eines Eingabebildes (Vielfache von 16, höchstens `max_flaeche`)."""
    breite, hoehe = bild.size
    return flaeche_begrenzen(breite, hoehe, max_flaeche)


def bild_verkleinern(bild, max_flaeche=MAX_FLAECHE):
    """Bild auf die Zielgröße bringen; unverändert, wenn es schon passt."""
    ziel = bildgroesse(bild, max_flaeche)
    if tuple(bild.size) == ziel:
        return bild
    # 1 ist das LANCZOS-Verfahren von Pillow; der Wert ist über Versionen stabil.
    return bild.resize(ziel, 1)


def maske_anpassen(maske, groesse):
    """Maske auf die Bildgröße bringen (NEAREST) und auf 0/255 setzen; Weiß heißt neu."""
    maske = maske.convert('L')
    if tuple(maske.size) != tuple(groesse):
        # 0 ist NEAREST: harte Kanten, keine neuen Grauwerte.
        maske = maske.resize(tuple(groesse), 0)
    return maske.point(lambda wert: 255 if wert >= 128 else 0)


def bild_lesen(daten):
    """PNG/JPEG als RGB-Bild lesen; Pillow erst hier importieren."""
    from PIL import Image
    return Image.open(io.BytesIO(daten)).convert('RGB')


def maske_lesen(daten):
    """Maske als Graustufenbild lesen; Pillow erst hier importieren."""
    from PIL import Image
    return Image.open(io.BytesIO(daten)).convert('L')


def bild_speichern(bild, pfad):
    bild.save(pfad)


def generator_erzeugen(seed):
    """torch.Generator für einen reproduzierbaren Seed; torch erst hier importieren."""
    import torch
    return torch.Generator('cpu').manual_seed(int(seed))


def pipeline_laden(cfg):
    """Die Dev-Pipeline von der Platte laden (nur im Arbeiter)."""
    import torch
    from diffusers import BriaFibo2Pipeline
    return BriaFibo2Pipeline.from_pretrained(cfg['modell'], dtype=torch.bfloat16)


def transformer_laden(cfg, pfad):
    """Nur den Transformer laden (Dev oder Turbo), ohne Textencoder und VAE."""
    import torch
    from diffusers import BriaFibo2Transformer2DModel
    return BriaFibo2Transformer2DModel.from_pretrained(pfad, torch_dtype=torch.bfloat16)


# ---------------------------------------------------------------- DeepSeek

def schluessel_lesen(cfg):
    """Den DeepSeek-Schlüssel aus der Schlüsseldatei lesen; er wird nie ausgegeben."""
    d = cfg.get('deepseek') or {}
    pfad = d.get('schluessel_datei')
    name = d.get('schluessel_name') or 'DEEPSEEK_API_KEY'
    if not pfad:
        raise RuntimeError('Keine Schlüsseldatei für DeepSeek eingerichtet.')
    try:
        with open(pfad, encoding='utf-8') as f:
            inhalt = f.read()
    except OSError:
        raise RuntimeError('Die Schlüsseldatei für DeepSeek ist nicht lesbar.') from None
    treffer = re.search(r'^\s*' + re.escape(name) + r'\s*:\s*["\']?([^"\'\s]+)', inhalt, re.M)
    if not treffer:
        raise RuntimeError(f'Kein {name} in der Schlüsseldatei.')
    return treffer.group(1)


def _ohne_schluessel(wert, schluessel):
    """Den Schlüssel aus einer Meldung oder einem Text entfernen, falls er darin auftaucht."""
    if not schluessel:
        return wert
    if isinstance(wert, str):
        return wert.replace(schluessel, '***')
    if isinstance(wert, dict):
        return {k: _ohne_schluessel(v, schluessel) for k, v in wert.items()}
    if isinstance(wert, list):
        return [_ohne_schluessel(v, schluessel) for v in wert]
    return wert


def deepseek_beschreiben(cfg, prompt, timeout=120, aufruf=None):
    """Prompt über bria-vgl/DeepSeek in eine VGL-Beschreibung wandeln.

    `aufruf` ist für die Tests austauschbar; ohne ihn werden bria_vgl und litellm
    erst hier importiert. Vor dem Import wird die Preisliste lokal gehalten, sonst
    lädt litellm sie beim ersten Aufruf aus dem Internet (gemessen: 100 s Hänger).
    """
    schluessel = schluessel_lesen(cfg)
    os.environ['DEEPSEEK_API_KEY'] = schluessel
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    d = cfg.get('deepseek') or {}
    modell = str(d.get('modell') or 'deepseek-flash')
    if not modell.startswith('deepseek/'):
        modell = 'deepseek/' + modell

    def rufen():
        if aufruf is not None:
            return aufruf(prompt, modell)
        from bria_vgl import create
        from bria_vgl.dialects.thales import Generate
        scene = create(Generate(prompt=prompt), llm=modell, seed=0)
        return scene.model_dump(exclude_none=True)

    ausfuehrer = ThreadPoolExecutor(max_workers=1)
    zukunft = ausfuehrer.submit(rufen)
    try:
        caption = zukunft.result(timeout=timeout)
    except FutureTimeout:
        ausfuehrer.shutdown(wait=False)
        raise RuntimeError(f"DeepSeek antwortet nach {timeout} s nicht.".replace('.', ',')) from None
    except Exception as ex:
        ausfuehrer.shutdown(wait=False)
        raise RuntimeError(_ohne_schluessel(_fehlertext(ex), schluessel)) from None
    finally:
        ausfuehrer.shutdown(wait=False)
    return _ohne_schluessel(caption, schluessel)


# ---------------------------------------------------------------- Dienst

class Dienst:
    """Ein Arbeiter-Thread, eine Warteschlange, ein Modell auf einer Karte."""

    def __init__(self, cfg, pipeline_fabrik=None, transformer_fabrik=None, generator_fabrik=None,
                 bild_lesen_funktion=None, maske_lesen_funktion=None, bild_speichern_funktion=None,
                 beschreiber=None):
        self.cfg = cfg
        self.pipeline_fabrik = pipeline_fabrik or pipeline_laden
        self.transformer_fabrik = transformer_fabrik or transformer_laden
        self.generator_fabrik = generator_fabrik or generator_erzeugen
        self.bild_lesen = bild_lesen_funktion or bild_lesen
        self.maske_lesen = maske_lesen_funktion or maske_lesen
        self.bild_speichern = bild_speichern_funktion or bild_speichern
        if beschreiber is None:
            self.beschreiber = lambda prompt: deepseek_beschreiben(self.cfg, prompt)
        else:
            self.beschreiber = beschreiber

        self.zustand = 'loading'
        self.fehler = None
        self.pipe = None
        self.transformer_dev = None
        self.transformer_turbo = None
        self.aktiv = 'dev'
        self.beende_bei_fehler = False
        self.server = None
        self._queue = queue.Queue()
        self._warteliste = []
        self._jobs = {}
        self._laufend = None
        self._lock = threading.RLock()
        self._arbeiter = None
        self._beenden = False

    # ------------------------------------------------------------ Laden und Arbeiter

    def laden(self):
        """Pipeline Dev laden, CPU-Offload einschalten. Fehler werden als Zustand `error` gemeldet."""
        try:
            pipe = self.pipeline_fabrik(self.cfg)
            pipe.enable_model_cpu_offload()
            self.pipe = pipe
            self.transformer_dev = pipe.transformer
            self.transformer_turbo = None
            self.aktiv = 'dev'
            with self._lock:
                self.zustand = 'ok'
                self.fehler = None
        except Exception as ex:
            with self._lock:
                self.zustand = 'error'
                self.fehler = _fehlertext(ex)
            raise

    def starten(self):
        """Arbeiter starten. Die Pipeline lädt er selbst, falls das noch nicht geschah."""
        if self._arbeiter is not None and self._arbeiter.is_alive():
            return self._arbeiter
        self._beenden = False
        self._arbeiter = threading.Thread(target=self._arbeitsschleife, name='fibo-arbeiter', daemon=True)
        self._arbeiter.start()
        return self._arbeiter

    def beenden(self):
        self._beenden = True
        self._queue.put(None)
        if self.server is not None:
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _arbeitsschleife(self):
        if self.zustand == 'loading':
            try:
                self.laden()
            except Exception:
                print('Fibo 2.0 konnte nicht geladen werden: ' + (self.fehler or ''), file=sys.stderr, flush=True)
                if self.beende_bei_fehler:
                    time.sleep(1)
                    os._exit(1)
                return
        while not self._beenden:
            auftrag_id = self._queue.get()
            if auftrag_id is None:
                break
            with self._lock:
                job = self._jobs.get(auftrag_id)
                if auftrag_id in self._warteliste:
                    self._warteliste.remove(auftrag_id)
                if job is None or job['zustand'] == 'abgebrochen':
                    self._queue.task_done()
                    continue
                self._laufend = auftrag_id
                job['platz'] = 0
            try:
                self._verarbeiten(job)
            except Exception as ex:
                with self._lock:
                    if job['zustand'] != 'abgebrochen':
                        job['zustand'] = 'fehler'
                        job['fehler'] = _fehlertext(ex)
                print(f"Auftrag {auftrag_id} fehlgeschlagen: {_fehlertext(ex)}", file=sys.stderr, flush=True)
            finally:
                with self._lock:
                    if self._laufend == auftrag_id:
                        self._laufend = None
                self._queue.task_done()

    # ------------------------------------------------------------ Zustand

    def health(self):
        with self._lock:
            karte = karte_aus_umgebung()
            if self.zustand == 'error':
                return {'status': 'error', 'fehler': self.fehler, 'karte': karte}
            if self.zustand != 'ok':
                return {'status': 'loading', 'karte': karte}
            return {'status': 'ok', 'modell': MODELL_KENNUNG, 'aktiv': self.aktiv,
                    'warteschlange': len(self._warteliste), 'laufend': self._laufend, 'karte': karte}

    # ------------------------------------------------------------ Auftrag annehmen

    def _basis64(self, wert, was):
        if not isinstance(wert, str) or not wert.strip():
            raise AnfrageFehler(f'{was} fehlt.')
        if wert.startswith('data:'):
            wert = wert.split(',', 1)[-1]
        try:
            roh = base64.b64decode(wert, validate=True)
        except (binascii.Error, ValueError):
            raise AnfrageFehler(f'{was} ist kein gültiges Base64.') from None
        if not roh:
            raise AnfrageFehler(f'{was} ist leer.')
        return roh

    def _bild_aus_anfrage(self, wert, was):
        roh = self._basis64(wert, was)
        try:
            return self.bild_lesen(roh)
        except Exception:
            raise AnfrageFehler(f'{was} ist kein lesbares PNG oder JPEG.') from None

    def _maske_aus_anfrage(self, wert):
        roh = self._basis64(wert, 'Maske')
        try:
            return self.maske_lesen(roh)
        except Exception:
            raise AnfrageFehler('Maske ist kein lesbares Bild.') from None

    def auftrag_annehmen(self, daten):
        """Auftrag prüfen und in die Warteschlange stellen -> ID."""
        if not isinstance(daten, dict):
            raise AnfrageFehler('Ungültige Anfrage.')
        art = daten.get('art')
        if art not in ('bild', 'bearbeiten'):
            raise AnfrageFehler('Art muss „bild“ oder „bearbeiten“ sein.')
        prompt = daten.get('prompt')
        if isinstance(prompt, dict):
            prompt_wert = prompt
            prompt_text = json.dumps(prompt, ensure_ascii=False)
        elif isinstance(prompt, str) and prompt.strip():
            prompt_wert = prompt
            prompt_text = prompt
        else:
            raise AnfrageFehler('Prompt fehlt oder ist leer.')

        modell = daten.get('modell') or ('dev' if art == 'bild' else 'turbo')
        if modell not in ('dev', 'turbo'):
            raise AnfrageFehler('Modell muss „dev“ oder „turbo“ sein.')
        if art == 'bild' and modell == 'turbo':
            raise AnfrageFehler('Turbo kann nur bearbeiten, nicht erzeugen.')

        beschreiber = daten.get('beschreiber') or 'keiner'
        if beschreiber not in ('keiner', 'deepseek'):
            raise AnfrageFehler('Beschreiber muss „keiner“ oder „deepseek“ sein.')
        if art == 'bearbeiten' and beschreiber != 'keiner':
            raise AnfrageFehler('Beim Bearbeiten wird kein Sprachmodell verwendet.')

        standard = self.cfg.get('standard') or {}
        vorgabe = standard.get(modell) or {}
        schritte = daten.get('schritte', vorgabe.get('schritte', 4 if modell == 'turbo' else 50))
        guidance = daten.get('guidance', vorgabe.get('guidance', 1.0 if modell == 'turbo' else 5.0))
        try:
            schritte = int(schritte)
            guidance = float(guidance)
        except (TypeError, ValueError):
            raise AnfrageFehler('Schritte oder Guidance sind keine Zahl.') from None
        if not 1 <= schritte <= 200:
            raise AnfrageFehler('Schritte müssen zwischen 1 und 200 liegen.')
        if not 0 <= guidance <= 50:
            raise AnfrageFehler('Guidance muss zwischen 0 und 50 liegen.')

        seed = daten.get('seed')
        if seed is None:
            seed = secrets.randbits(31)
        else:
            try:
                seed = int(seed)
            except (TypeError, ValueError):
                raise AnfrageFehler('Seed ist keine ganze Zahl.') from None
            if not 0 <= seed < 2 ** 63:
                raise AnfrageFehler('Seed ist außerhalb des gültigen Bereichs.')

        breite = hoehe = None
        if art == 'bild':
            try:
                breite = int(daten.get('breite', 1248))
                hoehe = int(daten.get('hoehe', 832))
            except (TypeError, ValueError):
                raise AnfrageFehler('Breite oder Höhe ist keine Zahl.') from None
            if breite <= 0 or hoehe <= 0:
                raise AnfrageFehler('Breite und Höhe müssen größer als 0 sein.')
            breite, hoehe = flaeche_begrenzen(breite, hoehe)

        bilder, maske = [], None
        rohe_bilder = daten.get('bilder')
        if art == 'bild':
            if rohe_bilder not in (None, []):
                raise AnfrageFehler('Bilder sind nur beim Bearbeiten erlaubt.')
            if daten.get('maske'):
                raise AnfrageFehler('Eine Maske ist nur beim Bearbeiten erlaubt.')
        else:
            if not isinstance(rohe_bilder, list) or not 1 <= len(rohe_bilder) <= 4:
                raise AnfrageFehler('Zum Bearbeiten braucht es 1 bis 4 Bilder.')
            for i, wert in enumerate(rohe_bilder, 1):
                bilder.append(self._bild_aus_anfrage(wert, f'Bild {i}'))
            if daten.get('maske'):
                if len(bilder) != 1:
                    raise AnfrageFehler('Eine Maske gehört zu genau einem Bild.')
                maske = self._maske_aus_anfrage(daten.get('maske'))

        auftrag_id = secrets.token_hex(6)
        job = {'id': auftrag_id, 'art': art, 'prompt': prompt_wert, 'prompt_text': prompt_text,
               'caption': None, 'beschreiber': beschreiber, 'modell': modell, 'schritte': schritte,
               'guidance': guidance, 'seed': seed, 'breite': breite, 'hoehe': hoehe,
               'bilder': bilder, 'maske': maske, 'zustand': 'wartet', 'schritt': 0,
               'schritte_gesamt': schritte, 'platz': 0, 'ergebnis': None, 'fehler': None,
               'abbruch': False, 'wechsel_s': 0.0}
        with self._lock:
            self._jobs[auftrag_id] = job
            self._warteliste.append(auftrag_id)
            job['platz'] = len(self._warteliste)
            self._queue.put(auftrag_id)
        return auftrag_id

    def auftrag_info(self, auftrag_id):
        with self._lock:
            job = self._jobs.get(auftrag_id)
            if job is None:
                return None
            platz = 0
            if job['zustand'] == 'wartet':
                try:
                    platz = self._warteliste.index(auftrag_id) + 1
                except ValueError:
                    platz = 0
            info = {'id': auftrag_id, 'art': job['art'], 'zustand': job['zustand'],
                    'schritt': job['schritt'], 'schritte': job['schritte_gesamt'],
                    'platz': platz, 'seed': job['seed'], 'modell': job['modell']}
            if job['zustand'] == 'fertig' and job['ergebnis'] is not None:
                info['ergebnis'] = job['ergebnis']
            if job['zustand'] == 'fehler' and job['fehler']:
                info['fehler'] = job['fehler']
            return info

    def abbrechen(self, auftrag_id):
        """Wartend sofort entfernen, laufend im Schritt-Callback stoppen."""
        with self._lock:
            job = self._jobs.get(auftrag_id)
            if job is None:
                return 404, {'fehler': 'Diesen Auftrag gibt es nicht.'}
            if job['zustand'] in ('fertig', 'fehler', 'abgebrochen'):
                return 409, {'fehler': 'Der Auftrag ist schon beendet.', 'zustand': job['zustand']}
            job['abbruch'] = True
            if job['zustand'] == 'wartet':
                job['zustand'] = 'abgebrochen'
                if auftrag_id in self._warteliste:
                    self._warteliste.remove(auftrag_id)
                return 200, {'ok': True, 'zustand': 'abgebrochen'}
            return 200, {'ok': True, 'zustand': job['zustand']}

    def _abgebrochen(self, job):
        return job.get('abbruch')

    def _als_abgebrochen(self, job):
        with self._lock:
            job['zustand'] = 'abgebrochen'
            job['ergebnis'] = None
            job['fehler'] = None

    def beschreibungsfehler(self, fehler):
        """Fehlertext der Beschreibung ohne den Schlüssel, falls er darin auftaucht."""
        text = _fehlertext(fehler)
        try:
            text = _ohne_schluessel(text, schluessel_lesen(self.cfg))
        except Exception:
            pass
        return text

    # ------------------------------------------------------------ Rechnen

    def _modell_wechseln(self, ziel):
        """Transformer tauschen wie in fibo_reihe.py; den nicht aktiven freigeben, wenn gewünscht."""
        if ziel == self.aktiv:
            return
        behalten = bool(self.cfg.get('turbo_im_speicher', False))
        if ziel == 'turbo':
            if self.transformer_turbo is None:
                self.transformer_turbo = self.transformer_fabrik(self.cfg, self.cfg['turbo_transformer'])
            self.pipe.remove_all_hooks()
            self.pipe.transformer = self.transformer_turbo
            if not behalten:
                self.transformer_dev = None
        else:
            if self.transformer_dev is None:
                self.transformer_dev = self.transformer_fabrik(self.cfg, os.path.join(self.cfg['modell'], 'transformer'))
            self.pipe.remove_all_hooks()
            self.pipe.transformer = self.transformer_dev
            if not behalten:
                self.transformer_turbo = None
        # Den abgelegten Transformer (≈16 GB) wirklich freigeben; ohne Anstoß blieben beim Wechsel Dev → Turbo → Dev
        # gemessen 40 GB Arbeitsspeicher belegt (22.10.2026).
        gc.collect()
        self.pipe.enable_model_cpu_offload()
        self.aktiv = ziel

    def _beschreiben(self, job):
        if job['beschreiber'] != 'deepseek':
            job['caption'] = job['prompt']
            return job['prompt_text']
        with self._lock:
            job['zustand'] = 'beschreibt'
        caption = self.beschreiber(job['prompt_text'])
        if self._abgebrochen(job):
            return None
        job['caption'] = caption
        if isinstance(caption, (dict, list)):
            return json.dumps(caption, ensure_ascii=False)
        return str(caption)

    def _rechnen(self, job, prompt, bilder, maske):
        schritte = job['schritte']
        with self._lock:
            job['schritte_gesamt'] = schritte

        def callback(pipe, schritt, timestep, kwargs):
            with self._lock:
                job['schritt'] = schritt + 1
                abbruch = job['abbruch']
            if abbruch:
                pipe._interrupt = True
            return kwargs

        argumente = dict(prompt=prompt, num_inference_steps=schritte, guidance_scale=job['guidance'],
                         fonts=list(self.cfg.get('schriften') or []),
                         generator=self.generator_fabrik(job['seed']),
                         callback_on_step_end=callback,
                         callback_on_step_end_tensor_inputs=['latents'])
        if job['art'] == 'bild':
            argumente.update(width=job['breite'], height=job['hoehe'])
            if job['modell'] != 'turbo':
                argumente['negative_prompt'] = NEGATIVE_T2I
        else:
            argumente['image'] = bilder[0] if len(bilder) == 1 else bilder
            if maske is not None:
                argumente['mask'] = maske
            if job['modell'] != 'turbo':
                argumente['negative_prompt'] = NEGATIVE_EDIT
        return self.pipe(**argumente).images[0]

    def _speichern(self, job, bild, prompt, breite, hoehe, sekunden):
        with self._lock:
            if job['abbruch']:
                return None
        datum = time.strftime('%Y-%m-%d')
        ordner = os.path.join(self.cfg['ablage'], datum)
        os.makedirs(ordner, exist_ok=True)
        png = os.path.join(ordner, job['id'] + '.png')
        protokoll = os.path.join(ordner, job['id'] + '.json')
        self.bild_speichern(bild, png)
        einstellungen = {'art': job['art'], 'schritte': job['schritte'], 'guidance': job['guidance'],
                         'beschreiber': job['beschreiber'], 'breite': breite, 'hoehe': hoehe}
        daten = {'id': job['id'], 'erstellt': time.strftime('%Y-%m-%dT%H:%M:%S'),
                 'prompt': job['prompt'], 'caption': job['caption'], 'einstellungen': einstellungen,
                 'seed': job['seed'], 'modell': job['modell'], 'sekunden': sekunden,
                 'wechsel_s': job['wechsel_s'], 'breite': breite, 'hoehe': hoehe, 'lizenz': LIZENZ}
        with open(protokoll, 'w', encoding='utf-8') as f:
            json.dump(daten, f, ensure_ascii=False, indent=2)
        with self._lock:
            if job['abbruch']:
                # Ein Abbruch kurz vor dem Ablegen hinterlässt kein Bild.
                for pfad in (png, protokoll):
                    try:
                        os.remove(pfad)
                    except OSError:
                        pass
                return None
        return {'bild': f"/api/datei/{job['id']}.png", 'caption': job['caption'], 'seed': job['seed'],
                'modell': job['modell'], 'sekunden': sekunden, 'breite': breite, 'hoehe': hoehe,
                'wechsel_s': job['wechsel_s']}

    def _verarbeiten(self, job):
        prompt = self._beschreiben(job)
        if prompt is None or self._abgebrochen(job):
            self._als_abgebrochen(job)
            return

        wechsel = 0.0
        if job['modell'] != self.aktiv:
            with self._lock:
                job['zustand'] = 'laedt_modell'
                job['schritt'] = 0
            beginn = time.time()
            self._modell_wechseln(job['modell'])
            wechsel = time.time() - beginn
            job['wechsel_s'] = round(wechsel, 1)
            if self._abgebrochen(job):
                self._als_abgebrochen(job)
                return

        bilder = []
        maske = job['maske']
        if job['art'] == 'bearbeiten':
            bilder = [bild_verkleinern(b) for b in job['bilder']]
            if maske is not None:
                maske = maske_anpassen(maske, bilder[0].size)

        with self._lock:
            job['zustand'] = 'rechnet'
            job['schritt'] = 0
        beginn = time.time()
        try:
            bild = self._rechnen(job, prompt, bilder, maske)
        except Exception:
            if self._abgebrochen(job):
                self._als_abgebrochen(job)
                return
            raise
        sekunden = round(time.time() - beginn, 1)
        if self._abgebrochen(job):
            self._als_abgebrochen(job)
            return
        breite, hoehe = tuple(getattr(bild, 'size', (job['breite'], job['hoehe'])))
        ergebnis = self._speichern(job, bild, prompt, breite, hoehe, sekunden)
        if ergebnis is None:
            self._als_abgebrochen(job)
            return
        with self._lock:
            if job['abbruch']:
                self._als_abgebrochen(job)
                return
            job['ergebnis'] = ergebnis
            job['zustand'] = 'fertig'
            job['schritt'] = job['schritte']

    # ------------------------------------------------------------ Dateien

    def datei_pfad(self, name):
        """Datei der Ablage finden; nur ein reiner Dateiname, kein Pfad-Ausbruch."""
        name = unquote(name)
        if (not name or name in ('.', '..') or name != os.path.basename(name)
                or '/' in name or '\\' in name or ':' in name
                or not name.lower().endswith(('.png', '.json'))):
            return None
        basis = os.path.abspath(self.cfg['ablage'])
        kandidaten = [os.path.join(basis, name)]
        try:
            for unter in sorted(os.listdir(basis), reverse=True):
                ordner = os.path.join(basis, unter)
                if os.path.isdir(ordner):
                    kandidaten.append(os.path.join(ordner, name))
        except OSError:
            pass
        for pfad in kandidaten:
            echt = os.path.abspath(pfad)
            if os.path.commonpath([basis, echt]) == basis and os.path.isfile(echt):
                return echt
        return None


# ---------------------------------------------------------------- HTTP

class Server(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        # SO_EXCLUSIVEADDRUSE verhindert einen zweiten Dienst auf demselben Port.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        pass


class Anfrage(BaseHTTPRequestHandler):
    dienst = None
    server_version = 'Fibo/1'

    def log_message(self, *args):
        pass

    def _erlaubte_hosts(self):
        port = self.server.server_address[1]
        return {f'127.0.0.1:{port}', f'localhost:{port}'}

    def _host_ok(self):
        return self.headers.get('Host') in self._erlaubte_hosts()

    def _post_ok(self):
        herkunft = self.headers.get('Origin')
        return (self._host_ok() and self.headers.get('X-Atelier') == '1'
                and not (herkunft and herkunft.split('//', 1)[-1] not in self._erlaubte_hosts()))

    def _senden(self, code, inhalt, typ='application/json; charset=utf-8'):
        daten = inhalt if isinstance(inhalt, bytes) else json.dumps(inhalt, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(daten)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(daten)

    def _json_lesen(self):
        roh = self.headers.get('Content-Length', '0')
        try:
            laenge = int(roh)
        except (TypeError, ValueError):
            raise AnfrageFehler('Ungültige Anfrage.') from None
        if laenge < 0:
            raise AnfrageFehler('Ungültige Anfrage.')
        if laenge > MAX_ANFRAGE:
            raise AnfrageFehler('Die Anfrage ist größer als 64 MB.', 413)
        daten = self.rfile.read(laenge)
        try:
            return json.loads(daten or b'{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AnfrageFehler('Ungültiges JSON.') from None

    def do_GET(self):
        if not self._host_ok():
            return self._senden(403, {'fehler': 'Nur lokal erreichbar.'})
        pfad = urlparse(self.path).path
        d = self.dienst
        if pfad == '/health':
            return self._senden(200, d.health())
        if pfad.startswith('/api/auftrag/'):
            auftrag_id = pfad[len('/api/auftrag/'):]
            info = d.auftrag_info(auftrag_id)
            if info is None:
                return self._senden(404, {'fehler': 'Diesen Auftrag gibt es nicht.'})
            return self._senden(200, info)
        if pfad.startswith('/api/datei/'):
            datei = d.datei_pfad(pfad[len('/api/datei/'):])
            if datei is None:
                return self._senden(404, {'fehler': 'Datei nicht gefunden.'})
            typ = 'image/png' if datei.lower().endswith('.png') else 'application/json; charset=utf-8'
            try:
                with open(datei, 'rb') as f:
                    return self._senden(200, f.read(), typ)
            except OSError:
                return self._senden(404, {'fehler': 'Datei nicht gefunden.'})
        return self._senden(404, {'fehler': 'Unbekannte Adresse.'})

    def do_POST(self):
        if not self._post_ok():
            return self._senden(403, {'fehler': 'Nur aus dem Atelier erlaubt.'})
        try:
            daten = self._json_lesen()
            if not isinstance(daten, dict):
                raise AnfrageFehler('Ungültige Anfrage.')
        except AnfrageFehler as f:
            return self._senden(f.code, {'fehler': f.text})
        pfad = urlparse(self.path).path
        d = self.dienst
        try:
            if pfad == '/api/auftrag':
                return self._senden(200, {'id': d.auftrag_annehmen(daten)})
            if pfad.startswith('/api/auftrag/') and pfad.endswith('/abbrechen'):
                auftrag_id = pfad[len('/api/auftrag/'):-len('/abbrechen')]
                return self._senden(*d.abbrechen(auftrag_id))
            if pfad == '/api/beschreiben':
                prompt = daten.get('prompt')
                if not isinstance(prompt, str) or not prompt.strip():
                    raise AnfrageFehler('Prompt fehlt oder ist leer.')
                try:
                    caption = d.beschreiber(prompt)
                except Exception as ex:
                    return self._senden(502, {'fehler': 'Beschreibung mit DeepSeek fehlgeschlagen: '
                                                       + d.beschreibungsfehler(ex)})
                return self._senden(200, {'caption': caption})
            return self._senden(404, {'fehler': 'Unbekannte Adresse.'})
        except AnfrageFehler as f:
            return self._senden(f.code, {'fehler': f.text})
        except Exception as ex:
            return self._senden(500, {'fehler': 'Unerwarteter Fehler: ' + _fehlertext(ex)})


def main(argv=None):
    zerleger = argparse.ArgumentParser(description='Fibo 2.0 als lokaler Dienst.')
    zerleger.add_argument('--port', type=int, default=8098)
    zerleger.add_argument('--config', default=STANDARD_CONFIG)
    args = zerleger.parse_args(argv)
    with open(args.config, encoding='utf-8') as f:
        cfg = json.load(f)
    dienst = Dienst(cfg)
    dienst.beende_bei_fehler = True
    server = Server(('127.0.0.1', args.port), Anfrage)
    Anfrage.dienst = dienst
    dienst.server = server
    dienst.starten()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
