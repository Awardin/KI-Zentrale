"""Alles rund um watch.py: Quellen erkennen, Vorhandenes finden, Fortschritt aus Dateien lesen.

watch.py meldet unterwegs nichts. Der Fortschritt kommt deshalb aus dem, was es
schreibt: `run.json` (Abschnitte), die wachsende Download-Datei und die Bilder.
watch.py selbst bleibt unverändert (gemeinsamer Skill für Codex, Hermes und Claude).
"""
import datetime
import glob
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import time

from gemeinsam.winapi import CREATE_NO_WINDOW

TRANSKRIPT_DATEIEN = ('transcript.txt', 'transcript.json', 'transcript.srt', 'transcript-timestamps.txt')

_YT_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
_YT_HOST = re.compile(r'^(?:www\.|m\.|music\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$', re.I)


# ---------------------------------------------------------------- YouTube

def youtube_id(url):
    """Video-ID aus einem YouTube-Link. ValueError mit verständlichem Grund bei Playlist/Kanal."""
    from urllib.parse import parse_qs, urlparse
    u = urlparse(url.strip())
    if u.scheme not in ('http', 'https') or not _YT_HOST.match(u.hostname or ''):
        raise ValueError('Das ist kein YouTube-Link.')
    teile = [t for t in u.path.split('/') if t]
    kandidat = None
    if (u.hostname or '').lower().endswith('youtu.be'):
        kandidat = teile[0] if teile else None
    elif teile[:1] == ['watch']:
        kandidat = (parse_qs(u.query).get('v') or [None])[0]
    elif len(teile) >= 2 and teile[0] in ('shorts', 'live', 'embed', 'v'):
        kandidat = teile[1]
    if kandidat and _YT_ID.match(kandidat):
        return kandidat
    if 'list' in parse_qs(u.query) or teile[:1] == ['playlist']:
        raise ValueError('Playlists werden nicht verarbeitet, nur einzelne Videos.')
    if teile and (teile[0].startswith('@') or teile[0] in ('channel', 'c', 'user')):
        raise ValueError('Kanäle werden nicht verarbeitet, nur einzelne Videos.')
    raise ValueError('In diesem YouTube-Link steckt keine Video-ID.')


def youtube_url(video_id):
    return f'https://www.youtube.com/watch?v={video_id}'


def videoordner(arbeitsordner, video_id):
    """Vorhandener Ordner `<Titel> [ID]` oder alter reiner ID-Ordner, sonst None."""
    try:
        eintraege = sorted(os.scandir(arbeitsordner), key=lambda e: e.name)
    except OSError:
        return None
    titel = [e.path for e in eintraege if e.is_dir() and e.name.endswith(f'[{video_id}]')]
    alt = [e.path for e in eintraege if e.is_dir() and e.name == video_id]
    return (titel or alt or [None])[0]


# ---------------------------------------------------------------- lokale Dateien

_watch_modul = None


def watch_modul(skript):
    """watch.py als Modul, um seine Ordnerbenennung wiederzuverwenden (nur Standardbibliothek)."""
    global _watch_modul
    if _watch_modul is None:
        spec = importlib.util.spec_from_file_location('watch_skill', skript)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _watch_modul = m
    return _watch_modul


def pruefsumme(pfad, fortschritt=None):
    """SHA-256 der Datei; `fortschritt(anteil)` wird unterwegs aufgerufen."""
    h = hashlib.sha256()
    gesamt = max(1, os.path.getsize(pfad))
    gelesen = 0
    letzte = 0
    with open(pfad, 'rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
            gelesen += len(block)
            if fortschritt and time.time() - letzte > 0.3:
                fortschritt(gelesen / gesamt)
                letzte = time.time()
    return h.hexdigest()


def lokaler_ordner(arbeitsordner, pfad, sha, skript):
    name = watch_modul(skript).safe_folder_name(os.path.splitext(os.path.basename(pfad))[0], 'datei-' + sha[:12])
    return os.path.join(arbeitsordner, name)


# ---------------------------------------------------------------- Vorhandenes erkennen

def _json(pfad):
    try:
        with open(pfad, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _unterordner(ordner, tiefe):
    """Der Ordner selbst und seine Unterordner bis `tiefe` Ebenen."""
    stufe = [ordner]
    for _ in range(tiefe + 1):
        naechste = []
        for o in stufe:
            yield o
            try:
                naechste += [e.path for e in os.scandir(o) if e.is_dir() and e.name not in ('chunks',)]
            except OSError:
                pass
        stufe = naechste


def transkripte(ordner, tiefe=2):
    """Alle vollständigen watch-Läufe im Videoordner (auch transkript-*\\ und single-worker\\)."""
    laeufe = []
    if not ordner or not os.path.isdir(ordner):
        return laeufe
    for o in _unterordner(ordner, tiefe):
        run = _json(os.path.join(o, 'run.json'))
        if not run or run.get('status') != 'complete':
            continue
        if not all(os.path.isfile(os.path.join(o, n)) for n in TRANSKRIPT_DATEIEN):
            continue
        sig = run.get('signature', {})
        laeufe.append({'ordner': o, 'start': sig.get('start', 0), 'ende': sig.get('end'),
                       'sha': sig.get('source_sha256'), 'sprache': sig.get('language'),
                       'modell': os.path.basename(sig.get('model', ''))})
    return laeufe


def transkript_passend(laeufe, dauer=None, sha=None):
    """Ein vollständiger Lauf über die ganze Quelle, bei lokalen Dateien mit derselben Prüfsumme."""
    for lauf in laeufe:
        if sha and lauf['sha'] != sha:
            continue
        if (lauf['start'] or 0) > 1:
            continue
        if dauer and lauf['ende'] is not None and lauf['ende'] < dauer - 2:
            continue
        return lauf
    return None


def bilder_abdeckung(ordner, tiefe=3):
    """[(start, ende, ordner)] aller fertigen Bildläufe (frames.json) im Videoordner."""
    out = []
    if not ordner or not os.path.isdir(ordner):
        return out
    for o in _unterordner(ordner, tiefe):
        d = _json(os.path.join(o, 'frames.json'))
        if d and d.get('frames') is not None:
            out.append((float(d.get('start') or 0), float(d.get('end') or 0), o))
    return out


def bereich_abgedeckt(abdeckung, von, bis):
    """Decken die vorhandenen Bildläufe den Zeitraum von–bis lückenlos ab?"""
    stand = von
    for a, b, _ in sorted(abdeckung):
        if b <= stand:
            continue
        if a > stand + 1:
            return False
        stand = b
    return stand >= bis - 1.5


def bilder_vollstaendig(abdeckung, dauer):
    if not abdeckung:
        return False
    return True if not dauer else bereich_abgedeckt(abdeckung, 0.0, dauer)


def medien_im_ordner(ordner):
    """Vorhandene Audio-/Videoquellen (source.json) im Videoordner."""
    out = {'audio': None, 'video': None, 'dauer': None, 'sprache': None, 'titel': None, 'quelle': None}
    if not ordner:
        return out
    for manifest in sorted(glob.glob(os.path.join(glob.escape(ordner), '*', 'source.json'))
                           + glob.glob(os.path.join(glob.escape(ordner), 'source.json'))):
        d = _json(manifest)
        if not d or not os.path.isfile(d.get('media_path', '')):
            continue
        art = d.get('media_kind')
        if art in ('audio', 'video') and not out[art]:
            out[art] = d['media_path']
        out['dauer'] = out['dauer'] or d.get('duration')
        out['sprache'] = out['sprache'] or d.get('language')
        out['titel'] = out['titel'] or d.get('title')
        out['quelle'] = out['quelle'] or d.get('source')
    return out


def sprache_kurz(sprache):
    """'de-DE' -> 'de'; unbekannt -> None."""
    if not sprache:
        return None
    s = str(sprache).split('-')[0].lower()
    return s if re.fullmatch(r'[a-z]{2,3}', s) else None


def medien_info(pfad):
    """(Dauer in Sekunden, hat Bild) über ffprobe, wie watch selbst. Titelbilder in MP3s zählen nicht als Bild."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration:stream=codec_type:stream_disposition=attached_pic', '-of', 'json', pfad],
                       capture_output=True, encoding='utf-8', errors='replace', timeout=60,
                       creationflags=CREATE_NO_WINDOW)
    if r.returncode:
        raise ValueError('Die Datei lässt sich nicht als Audio oder Video lesen.')
    try:
        d = json.loads(r.stdout)
        dauer = float(d['format']['duration'])
    except (KeyError, ValueError, TypeError):
        raise ValueError('Die Dauer der Datei ist nicht lesbar.')
    bild = any(s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')
               for s in d.get('streams', []))
    return dauer, bild


# ---------------------------------------------------------------- Ausgabeordner

def zeitstempel():
    return datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')


def transkript_ziel(ordner):
    """Wie bisher direkt im Videoordner; gibt es dort schon einen (abgebrochenen) Lauf, ein neuer Unterordner."""
    if not os.path.exists(os.path.join(ordner, 'run.json')):
        return ordner
    return os.path.join(ordner, 'transkript-' + zeitstempel())


def hms(s):
    s = int(round(s))
    return f'{s // 3600:02}-{s % 3600 // 60:02}-{s % 60:02}'


def bildfenster(dauer, fenster_s):
    """Zeitfenster für `frames` (je Aufruf höchstens 240 Bilder)."""
    if dauer <= fenster_s * 1.1:
        return [(0.0, dauer)]
    n = math.ceil(dauer / fenster_s)
    return [(i * fenster_s, min(dauer, (i + 1) * fenster_s)) for i in range(n)]


def bild_ziel(ordner, a, b, einzeln):
    """frames\\ für kurze Videos (wie bisher), sonst frames\\teil 00-00-00 bis 00-30-00\\."""
    basis = os.path.join(ordner, 'frames')
    return basis if einzeln else os.path.join(basis, f'teil {hms(a)} bis {hms(b)}')


def bilder_zaehlen(ordner):
    try:
        return sum(1 for _ in glob.iglob(os.path.join(glob.escape(ordner), '**', '*.png'), recursive=True))
    except OSError:
        return 0


# ---------------------------------------------------------------- Fortschritt und Ergebnis

def fortschritt_transkription(out):
    """Stand aus run.json: Abschnitte fertig/gesamt und Audiosekunden."""
    for o in (os.path.join(out, 'single-worker'), out):
        run = _json(os.path.join(o, 'run.json'))
        if run:
            break
    else:
        return {'phase': 'start'}
    abschnitte = run.get('chunks') or []
    if not abschnitte:
        return {'phase': 'vorbereiten', 'ersatz': o != out}
    fertig = [c for c in abschnitte if c.get('status') == 'complete']
    sek = lambda cs: sum(max(0, (c.get('end') or 0) - (c.get('start') or 0)) for c in cs)  # noqa: E731
    return {'phase': 'abschnitte', 'fertig': len(fertig), 'gesamt': len(abschnitte),
            'sek_fertig': sek(fertig), 'sek_gesamt': sek(abschnitte),
            'fehlgeschlagen': sum(1 for c in abschnitte if c.get('status') == 'failed'), 'ersatz': o != out}


def ergebnis_transkription(out):
    """-> Ordner mit dem fertigen Transkript oder None (auch nach dem Ein-Worker-Ersatzlauf)."""
    for o in (out, os.path.join(out, 'single-worker')):
        lauf = transkripte(o, tiefe=0)
        if lauf:
            return o
    return None


def letztes_json(text):
    """Letztes JSON-Objekt aus einer Programmausgabe."""
    text = (text or '').strip()
    anfang = text.find('{')
    while anfang != -1:
        try:
            return json.loads(text[anfang:])
        except ValueError:
            anfang = text.find('{', anfang + 1)
    return None


_FEHLER = [
    (r'out of memory|cuda.*alloc', 'Der Grafikspeicher reichte nicht.'),
    (r'Only individual videos', 'Playlists werden nicht verarbeitet.'),
    (r'Live streams', 'Laufende Livestreams werden nicht verarbeitet.'),
    (r'Private video|Sign in to confirm|members-only|age', 'YouTube verlangt eine Anmeldung (privat, Altersgrenze oder nur für Mitglieder).'),
    (r'Video unavailable|not available|removed', 'Das Video ist bei YouTube nicht (mehr) verfügbar.'),
    (r'getaddrinfo|Unable to download|HTTP Error|timed out|Connection', 'YouTube war nicht erreichbar.'),
    (r'Local medium model missing', 'Das Whisper-Modell fehlt im Watch-Ordner.'),
    (r'frames: split into smaller', 'Zu viele Bilder für einen Durchgang.'),
]


def fehlertext(ausgabe):
    """Verständliche Meldung aus der Fehlerausgabe von watch.py; der Originaltext hängt gekürzt an."""
    d = letztes_json(ausgabe)
    roh = (d or {}).get('error') or (ausgabe or '').strip().splitlines()[-1:] or ['']
    roh = roh if isinstance(roh, str) else roh[0]
    for muster, text in _FEHLER:
        if re.search(muster, roh, re.I):
            return f'{text} ({roh[:160]})'
    return roh[:300] or 'watch.py ist ohne Meldung abgebrochen.'
