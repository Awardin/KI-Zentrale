"""Messungen: entstehen automatisch aus dem, was ohnehin geschrieben wird.

- Transkription: aus allen `run.json` im watch-Arbeitsordner (Tondauer, Laufzeit der Abschnitte, Karten).
- Zusammenfassung: aus den Fassungen der Werkstatt (Dauer, Token, Kosten).
- Bild & Video: aus der Auftragsliste von 2Wild (`data\\jobs.json`, nur lesend, ohne Prompts)
  und – falls ComfyUI läuft – aus dessen Verlauf.
- LLM-Messlauf per Knopf: fester Text an ein geladenes lokales Modell; Prefill, Decode, TTFT.
- Historisch: die 141 Messläufe aus GPU-Lab, einmalig übernommen und als historisch markiert.
"""
import datetime
import json
import os
import re
import sqlite3
import statistics
import threading
import time
import urllib.request

from gemeinsam import gpu, winapi

from . import watch_lauf
from .auswertung import ollama_senden

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Fester, abwechslungsreicher Messtext (gut 1.500 Token), immer derselbe, damit Läufe vergleichbar bleiben.
# Kein wiederholter Absatz: Wiederholungen lassen Ornith Q4 in Ollama 0.34 abstürzen (llama.cpp, MoE, mmq.cu).
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messtext.txt'), encoding='utf-8') as _f:
    MESSTEXT = _f.read().strip()
MESS_ID = 'werkstatt-messlauf-v2'
AUSGABE_TOKEN = 256


def _json(pfad):
    try:
        with open(pfad, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _median(werte):
    werte = [w for w in werte if w is not None]
    return statistics.median(werte) if werte else None


def _datum(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else None


# ---------------------------------------------------------------- Transkription

def transkription_lauf(ordner):
    """Kennzahlen eines vollständigen watch-Laufs oder None."""
    run = _json(os.path.join(ordner, 'run.json'))
    if not run or run.get('status') != 'complete':
        return None
    abschnitte = [c for c in run.get('chunks', []) if c.get('status') == 'complete' and c.get('started')]
    if not abschnitte:
        return None
    sig = run.get('signature', {})
    ton = sum(max(0, c['end'] - c['start']) for c in abschnitte)
    laufzeit = max(c['finished'] for c in abschnitte) - min(c['started'] for c in abschnitte)
    karten = sorted({c.get('gpu') for c in abschnitte if c.get('gpu') is not None})
    worker = run.get('workers_used') or sig.get('workers') or 1
    if len(karten) > 1:
        aufbau = f'{len(karten)} Karten, je ein Worker'
    elif worker > 1 and len(abschnitte) > 1:
        aufbau = 'eine Karte, zwei Worker'
    else:
        aufbau = 'eine Karte, ein Worker'
    # Wenig Sprache (Musik, Stille, falsche Sprache) macht Whisper scheinbar sehr schnell: kennzeichnen.
    try:
        with open(os.path.join(ordner, 'transcript.txt'), encoding='utf-8') as f:
            woerter = len(f.read().split())
    except OSError:
        woerter = None
    wpm = woerter / (ton / 60) if woerter is not None and ton else None
    return {'ordner': ordner, 'woerter_je_min': round(wpm) if wpm is not None else None,
            'wenig_sprache': wpm is not None and wpm < 40,
            'modell': os.path.basename(sig.get('model', '')).replace('faster-whisper-', ''),
            'ton_s': round(ton, 1), 'laufzeit_s': round(laufzeit, 1),
            'tempo': round(ton / laufzeit, 1) if laufzeit > 0 else None, 'karten': karten, 'aufbau': aufbau,
            'abschnitte': len(abschnitte), 'datum': _datum(min(c['started'] for c in abschnitte)),
            'zeit': min(c['started'] for c in abschnitte)}


def transkription(arbeitsordner):
    laeufe = []
    try:
        videos = [e.path for e in os.scandir(arbeitsordner) if e.is_dir() and not e.name.startswith('_')]
    except OSError:
        videos = []
    for v in videos:
        for lauf in watch_lauf.transkripte(v):
            k = transkription_lauf(lauf['ordner'])
            if k and k['ton_s'] >= 30:
                k['titel'] = re.sub(r'\s*\[[^\]]+\]$', '', os.path.basename(v))
                laeufe.append(k)
    laeufe.sort(key=lambda k: -k['zeit'])
    gruppen = {}
    for k in laeufe:
        gruppen.setdefault((k['modell'], k['aufbau']), []).append(k)
    zusammen = [{'modell': m, 'aufbau': a, 'anzahl': len(ls),
                 'tempo_median': _median([k['tempo'] for k in ls if not k['wenig_sprache']]),
                 'ausgelassen': sum(1 for k in ls if k['wenig_sprache']),
                 'ton_h': round(sum(k['ton_s'] for k in ls) / 3600, 2)}
                for (m, a), ls in gruppen.items()]
    zusammen.sort(key=lambda g: -(g['tempo_median'] or 0))
    return {'gruppen': zusammen, 'letzte': laeufe[:25], 'anzahl': len(laeufe)}


# ---------------------------------------------------------------- Zusammenfassung

def zusammenfassung(auswertungen):
    fertig = [a for a in auswertungen if a.get('zustand') == 'fertig' and a.get('dauer_s')]
    gruppen = {}
    for a in fertig:
        gruppen.setdefault(a['auswerter']['name'], []).append(a)
    out = []
    for name, ls in gruppen.items():
        out.append({'auswerter': name, 'cloud': ls[0].get('cloud'), 'anzahl': len(ls),
                    'dauer_median': _median([a['dauer_s'] for a in ls]),
                    'token_je_s': _median([a['tokens'] / a['dauer_s'] for a in ls if a.get('tokens') and a['dauer_s']]),
                    # Kosten nur bei Abrechnung je Anfrage (DeepSeek, OpenRouter); Abo (Codex, Claude) und lokal: None
                    'kosten_usd': round(sum(k), 4) if (k := [a['kosten_usd'] for a in ls
                                                              if a.get('kosten_usd') is not None]) else None})
    out.sort(key=lambda g: g['dauer_median'] or 0)
    return {'gruppen': out, 'anzahl': len(fertig)}


# ---------------------------------------------------------------- Bild & Video

def bild_video(jobs_datei, comfy_port, studio_auftraege=()):
    out = []
    # Eigene Aufträge nicht noch einmal aus dem ComfyUI-Verlauf zählen (auch nicht ihre Vorläufe).
    eigene = {p for a in studio_auftraege for p in (a.get('prompt_ids') or [a.get('prompt_id')]) if p}
    for a in studio_auftraege:
        # Nur echte Berechnungen: aus dem Zwischenspeicher von ComfyUI neu gespeichert zählt nicht.
        if a.get('zustand') != 'fertig' or not a.get('rechenzeit_s') or a.get('zwischenspeicher'):
            continue
        art = {'bearbeiten': 'Bild bearbeiten', 'verbessern': 'Stelle verbessern', 'freistellen': 'Freistellen',
               'pose': 'Pose-Skelett', 'video_text': 'Video aus Text',
               'video_bild': 'Video aus Bild', 'video_referenz': 'Video mit Referenz',
               'video_weiter': 'Video weiterführen', 'modell3d': '3D-Modell'}.get(a.get('art'), 'Bild')
        # Beim Weiterführen zählt die Länge des neu gerechneten Clips (bilder = L), nicht die des fertigen Videos.
        video_s = round(a['bilder'] / 24, 1) if a.get('bilder') else None
        aufloesung = f"{a['breite']}×{a['hoehe']}" if a.get('breite') else ''
        if a.get('arbeit'):  # beim Verbessern wird nur der Ausschnitt in dieser Größe gerechnet
            aufloesung = f"Ausschnitt {a['arbeit']['breite']}×{a['arbeit']['hoehe']}"
        if video_s:
            aufloesung += f" · {str(video_s).replace('.', ',')} s"
        zusatz = ((' · Turbo' if a.get('turbo') else '') + (' · Details' if a.get('details') else '')
                  + (' · schnell' if a.get('schnell') else '') + (' · INT8' if a.get('int8') else '')
                  + (' · ausformuliert' if a.get('ausformulieren') else '') + (' · Stelle per Wort' if a.get('stelle') else ''))
        if a.get('art') == 'modell3d':
            video_s = None  # die Vorschau ist nur ein Drehteller, kein gerechnetes Video
            aufloesung = f"{a.get('modus') or ''} · {a.get('stufe') or ''}".strip(' ·')
        modell = ('Pixal3D' if a.get('art') == 'modell3d' else 'MiniMax-H3' if video_s
                  else 'BiRefNet' if a.get('verfahren') == 'schnell'
                  else ('SDPose' + (' · alle Personen' if a.get('personen') else '')) if a.get('art') == 'pose'
                  else 'Qwen-Image 2.1' + zusatz)
        out.append({'quelle': 'Studio', 'art': art, 'modus': a.get('art') or '',
                    'modell': modell,
                    'aufloesung': aufloesung,
                    'schritte': a.get('schritte'), 'video_s': video_s, 'dauer_s': a['rechenzeit_s'],
                    'datum': _datum(a.get('beendet') or a.get('erstellt')), 'zeit': a.get('beendet') or a.get('erstellt')})
    daten = _json(jobs_datei)
    for j in (daten if isinstance(daten, list) else (daten or {}).get('jobs', [])):
        if j.get('status') != 'done' or not j.get('started') or not j.get('finished'):
            continue
        dauer = j['finished'] - j['started']
        out.append({'quelle': '2Wild Studio', 'art': 'Video' if j.get('kind') == 'video' else 'Bild',
                    'modus': j.get('mode') or '', 'modell': j.get('model') or '',
                    'aufloesung': f"{j.get('width')}×{j.get('height')}" if j.get('width') else '',
                    'schritte': j.get('steps'), 'video_s': j.get('seconds'), 'dauer_s': round(dauer, 1),
                    'datum': _datum(j['started']), 'zeit': j['started']})
    # ComfyUI-Verlauf (nur solange ComfyUI läuft; ohne Workflows und Prompts)
    try:
        if comfy_port not in {p for _, p, _ in winapi.lauschende_ports()}:
            raise ConnectionError('ComfyUI läuft nicht')
        with _OHNE_PROXY.open(f'http://127.0.0.1:{comfy_port}/history?max_items=200', timeout=2) as r:
            verlauf = json.load(r)
        for pid, e in verlauf.items():
            if pid in eigene:
                continue  # schon oben als Studio-Auftrag mit allen Angaben
            meldungen = {m[0]: m[1] for m in (e.get('status') or {}).get('messages', []) if isinstance(m, list)}
            a, b = meldungen.get('execution_start', {}).get('timestamp'), meldungen.get('execution_success', {}).get('timestamp')
            if a and b:
                out.append({'quelle': 'ComfyUI', 'art': 'Auftrag', 'modus': '', 'modell': '', 'aufloesung': '',
                            'schritte': None, 'video_s': None, 'dauer_s': round((b - a) / 1000, 1),
                            'datum': _datum(a / 1000), 'zeit': a / 1000})
    except Exception:
        pass
    out.sort(key=lambda x: -x['zeit'])
    gruppen = {}
    for x in out:
        gruppen.setdefault((x['quelle'], x['art'], x['modell'], x['aufloesung'], x['schritte']), []).append(x)
    zusammen = [{'quelle': q, 'art': art, 'modell': m, 'aufloesung': auf, 'schritte': s, 'anzahl': len(ls),
                 'dauer_median': _median([x['dauer_s'] for x in ls])}
                for (q, art, m, auf, s), ls in gruppen.items()]
    return {'gruppen': zusammen, 'letzte': out[:25], 'anzahl': len(out)}


# ---------------------------------------------------------------- GPU-Lab (historisch)

def gpu_lab_importieren(db_pfad, ziel):
    """Übernimmt die Messläufe aus GPU-Lab einmalig (nur lesend geöffnet). -> Anzahl."""
    db = sqlite3.connect(f'file:{db_pfad}?mode=ro', uri=True)
    try:
        zeilen = db.execute('select id, created_at, data_json from runs order by created_at').fetchall()
    finally:
        db.close()
    laeufe = []
    for rid, erstellt, daten in zeilen:
        try:
            d = json.loads(daten)
        except ValueError:
            continue
        laeufe.append({'id': rid, 'erstellt': erstellt, **{k: d.get(k) for k in (
            'gpu', 'type', 'model', 'quant', 'runtime', 'kv_cache', 'mtp', 'setup', 'context', 'input_tokens',
            'output_tokens', 'decode', 'prefill', 'ttft', 'test_name', 'result', 'unit', 'notes')}})
    tmp = ziel + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'quelle': db_pfad, 'uebernommen': datetime.datetime.now().isoformat(timespec='seconds'),
                   'hinweis': 'Historische Messungen aus GPU-Lab (14.–19.09.2026), unverändert übernommen.',
                   'laeufe': laeufe}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ziel)
    return len(laeufe)


def historisch(datei):
    d = _json(datei)
    if not d:
        return None
    gruppen = {}
    for l in d['laeufe']:
        if l.get('type') != 'llm':
            continue
        schluessel = (l.get('model') or '?', l.get('quant') or '', l.get('runtime') or '', l.get('gpu') or '')
        gruppen.setdefault(schluessel, []).append(l)

    def zahl(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    zusammen = [{'modell': m, 'quant': q, 'runtime': r, 'gpu': g, 'anzahl': len(ls),
                 'decode': _median([zahl(l.get('decode')) for l in ls]),
                 'prefill': _median([zahl(l.get('prefill')) for l in ls]),
                 'ttft_ms': _median([zahl(l.get('ttft')) for l in ls])}
                for (m, q, r, g), ls in gruppen.items()]
    zusammen.sort(key=lambda g: -(g['decode'] or 0))
    andere = len([l for l in d['laeufe'] if l.get('type') != 'llm'])
    return {'gruppen': zusammen, 'anzahl': len(d['laeufe']), 'andere': andere,
            'uebernommen': d.get('uebernommen'), 'quelle': d.get('quelle'), 'hinweis': d.get('hinweis')}


# ---------------------------------------------------------------- LLM-Messlauf

class Messlauf:
    """Führt den festen Messtext an einem geladenen lokalen Modell aus (nie neben Whisper)."""

    def __init__(self, datei, lokal, log, karten_cfg=None):
        self.datei = datei
        self.karten_cfg = karten_cfg or {}  # Kartennamen der Zentrale (Steckplatz -> „RTX 3090 FE“)
        self.lokal = lokal  # auswertung.Lokal: kennt Zentrale-Einträge und ob sie geladen sind
        self.log = log
        self.laufend = None
        self._lock = threading.Lock()

    def liste(self):
        return (_json(self.datei) or {}).get('laeufe', [])

    def _speichern(self, lauf):
        with self._lock:
            laeufe = self.liste() + [lauf]
            tmp = self.datei + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({'laeufe': laeufe}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.datei)

    def starten(self, modell_id):
        eintraege, _ = self.lokal._eintraege()
        e = eintraege.get(modell_id)
        if not e:
            return 404, {'fehler': 'Dieses Modell kennt die Modellzentrale nicht.'}
        ok, grund = self.lokal.verfuegbar({'modell': modell_id}, frisch=True)
        if not ok:
            return 409, {'fehler': grund}
        with self._lock:
            if self.laufend:
                return 409, {'fehler': 'Es läuft schon ein Messlauf.'}
            self.laufend = {'modell': e['name'], 'seit': time.time(), 'meldung': 'Startet …'}
        threading.Thread(target=self._lauf, args=(e,), daemon=True).start()
        return 202, {'ok': True}

    def _lauf(self, e):
        # Keine gemeinsame GPU-Sperre mehr (16.10.2026): Der Messlauf rechnet auch, wenn daneben etwas läuft;
        # ein aussagekräftiger Wert braucht dann Ruhe auf den Karten.
        try:
            spitzen = {}
            stopp = threading.Event()

            # Namen mitspeichern: Bis 13.10.2026 war Karte 1 eine RTX 3080, seit 14.10.2026 eine zweite RTX 3090.
            namen = gpu.kurznamen(gpu.karten_lesen(), self.karten_cfg)

            def sensoren():
                while not stopp.is_set():
                    for k in gpu.karten_lesen():
                        s = spitzen.setdefault(k['index'], {'watt': 0, 'temp': 0, 'last': 0, 'belegt': 0})
                        s['name'] = namen.get(k['index'])
                        for f in ('watt', 'temp', 'last', 'belegt'):
                            if k.get(f) is not None:
                                s[f] = max(s[f], k[f])
                    stopp.wait(0.5)
            t = threading.Thread(target=sensoren, daemon=True)
            t.start()
            try:
                # Aufwärmen (erste Rechnung nach dem Laden ist langsamer) und eine eindeutige Kennung am
                # Textanfang, damit der Zwischenspeicher des Modells nichts vorwegnimmt.
                kennung = f'Messlauf {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                self.laufend['meldung'] = 'Wärmt auf …'
                if e['art'] == 'ollama':
                    self._ollama(e, 'Antworte nur mit OK.', 4)
                else:
                    self._ninfer(e, 'Antworte nur mit OK.', 4)
                self.laufend['meldung'] = 'Misst …'
                werte = (self._ollama(e, kennung + MESSTEXT, AUSGABE_TOKEN) if e['art'] == 'ollama'
                         else self._ninfer(e, kennung + MESSTEXT, AUSGABE_TOKEN))
            finally:
                stopp.set()
                t.join(2)
            lauf = {'zeit': time.time(), 'datum': _datum(time.time()), 'modell': e['name'], 'eintrag': e['id'],
                    'laufzeit': 'Ollama' if e['art'] == 'ollama' else 'NInfer', 'mess_id': MESS_ID,
                    'ausgabe_token_ziel': AUSGABE_TOKEN, 'sensoren': spitzen, **werte}
            self._speichern(lauf)
            self.log(f"Messlauf {e['id']}: Decode {werte.get('decode')} tok/s, Prefill {werte.get('prefill')} tok/s")
            self.laufend = None
        except Exception as ex:
            self.laufend = None
            self._speichern({'zeit': time.time(), 'datum': _datum(time.time()), 'modell': e['name'], 'eintrag': e['id'],
                             'fehler': str(ex)[:300]})

    def _ollama(self, e, text, ausgabe):
        _, ollama = self.lokal._eintraege()
        daten = {'model': e['tag'], 'prompt': text, 'stream': False, 'keep_alive': -1,
                 'options': dict(self.lokal.ollama_optionen(e, ollama), num_predict=ausgabe, temperature=0, seed=42)}

        def oeffnen(f):
            with f() as r:
                return json.load(r)

        def melden(text):
            self.laufend['meldung'] = text
        beginn = time.time()
        a = ollama_senden(ollama.get('url', 'http://127.0.0.1:11434') + '/api/generate', daten, oeffnen, melden, 900)
        gesamt = time.time() - beginn
        pe, pd = a.get('prompt_eval_count') or 0, (a.get('prompt_eval_duration') or 0) / 1e9
        ec, ed = a.get('eval_count') or 0, (a.get('eval_duration') or 0) / 1e9
        return {'eingabe_token': pe, 'ausgabe_token': ec,
                'prefill': round(pe / pd, 1) if pd else None, 'decode': round(ec / ed, 1) if ed else None,
                'ttft_ms': round(((a.get('load_duration') or 0) / 1e9 + pd) * 1000) if pd else None,
                'gesamt_s': round(gesamt, 2)}

    def _ninfer(self, e, text, ausgabe):
        daten = {'model': e['modell_id'], 'messages': [{'role': 'user', 'content': text}], 'stream': True,
                 'max_tokens': ausgabe, 'temperature': 0, 'seed': 42, 'stream_options': {'include_usage': True}}
        anfrage = urllib.request.Request(f"http://127.0.0.1:{e['port']}/v1/chat/completions",
                                         json.dumps(daten).encode('utf-8'), {'Content-Type': 'application/json'})
        beginn = time.time()
        erstes, letztes, stuecke, nutzung = None, None, 0, {}
        with _OHNE_PROXY.open(anfrage, timeout=900) as r:
            for zeile in r:
                zeile = zeile.decode('utf-8', 'replace').strip()
                if not zeile.startswith('data:') or zeile == 'data: [DONE]':
                    continue
                try:
                    d = json.loads(zeile[5:])
                except ValueError:
                    continue
                if d.get('usage'):
                    nutzung = d['usage']
                for c in d.get('choices') or []:
                    delta = c.get('delta') or {}
                    if delta.get('content') or delta.get('reasoning_content'):
                        jetzt = time.time()
                        erstes = erstes or jetzt
                        letztes = jetzt
                        stuecke += 1
        gesamt = time.time() - beginn
        ausgabe = nutzung.get('completion_tokens') or stuecke
        eingabe = nutzung.get('prompt_tokens')
        ttft = (erstes - beginn) if erstes else None
        decode_zeit = (letztes - erstes) if erstes and letztes and letztes > erstes else None
        return {'eingabe_token': eingabe, 'ausgabe_token': ausgabe,
                'prefill': round(eingabe / ttft, 1) if eingabe and ttft else None,
                'decode': round((ausgabe - 1) / decode_zeit, 1) if decode_zeit and ausgabe > 1 else None,
                'ttft_ms': round(ttft * 1000) if ttft else None, 'gesamt_s': round(gesamt, 2)}
