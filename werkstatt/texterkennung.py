"""Texterkennung („PDF/Scan lesen“) mit LightOnOCR aus der Modellzentrale.

Ein Auftrag nach dem anderen. Die Seitenbilder rendert das vorhandene PDF-Werkzeug (PyMuPDF in dessen
eigener Umgebung, externer Aufruf von `pdf_seiten.py` wie bei watch); erkannt wird nur, wenn die
Modellzentrale LightOnOCR gestartet hat – die Werkstatt startet oder beendet es nie. Gerechnet wird unter
der gemeinsamen GPU-Sperre (nie neben Whisper, lokalen Sprachmodellen oder Studio-Aufträgen) und erst,
wenn die Zentrale über /api/platz keinen Grund zum Warten meldet. Das Modell belegt seinen Speicher schon
beim Start in der Zentrale; eine Anmeldung von Zusatzspeicher braucht es deshalb nicht.

Ergebnis: <ausgabe_ordner>\\<Name>\\ mit „Seite 001.md“ …, „Volltext.md“ und „lauf.json“. Die Quelle bleibt
unverändert, Seitenbilder werden nicht gespeichert. Ein abgebrochener oder fehlgeschlagener Auftrag setzt
beim Wiederholen nach der letzten fertigen Seite fort.
"""
import hashlib
import json
import os
import re
import secrets
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.request

from gemeinsam import winapi

from . import platz, quellen
from .auswertung import dateiname

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HILFE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdf_seiten.py')
OFFEN = ('wartet', 'laeuft')
FELDER = ('id', 'quelle', 'titel', 'seiten_wahl', 'zustand', 'meldung', 'hinweis', 'ordner', 'volltext',
          'seiten_pdf', 'seiten', 'fertig', 'abgeschnitten', 'erstellt', 'begonnen', 'beendet', 'sekunden')
HINWEIS_PRUEFEN = ('LightOnOCR liest sehr genau, macht aber gelegentlich Fehlwörter, die echt aussehen '
                   '(z. B. „Sehnenvorlauf“ statt „Sehnenverlauf“). Für Wissensquellen Stichproben gegen das Original.')


class Abgebrochen(Exception):
    pass


class Fehler(Exception):
    pass


def seiten_lesen(text, anzahl):
    """„1-3, 7“ -> [1, 2, 3, 7]; leer -> alle Seiten. ValueError mit verständlichem Text."""
    text = (text or '').strip()
    if not text:
        return list(range(1, anzahl + 1))
    out = set()
    for teil in re.split(r'[,;\s]+', text):
        if not teil:
            continue
        m = re.fullmatch(r'(\d+)(?:\s*[-–]\s*(\d+))?', teil)
        if not m:
            raise ValueError(f'„{teil}“ ist keine Seitenangabe. Beispiel: 1-5, 8')
        von, bis = int(m.group(1)), int(m.group(2) or m.group(1))
        if von < 1 or bis < von:
            raise ValueError(f'„{teil}“ ist keine gültige Seitenangabe.')
        if bis > anzahl:
            raise ValueError(f'Seite {bis} gibt es nicht; die Datei hat {anzahl} Seite{"n" if anzahl != 1 else ""}.')
        out.update(range(von, bis + 1))
    return sorted(out)


def seiten_text(seiten):
    """[1, 2, 3, 7] -> „1–3, 7“."""
    teile, i = [], 0
    while i < len(seiten):
        j = i
        while j + 1 < len(seiten) and seiten[j + 1] == seiten[j] + 1:
            j += 1
        teile.append(str(seiten[i]) if i == j else f'{seiten[i]}–{seiten[j]}')
        i = j + 1
    return ', '.join(teile)


def seiten_datei(n):
    return f'Seite {n:03d}.md'


def pruefsumme(pfad):
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        for stueck in iter(lambda: f.read(1 << 20), b''):
            h.update(stueck)
    return h.hexdigest()


def _json_lesen(pfad):
    try:
        with open(pfad, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _json_schreiben(pfad, daten):
    tmp = pfad + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    os.replace(tmp, pfad)


def _dauer_text(s):
    s = int(round(s))
    return f'{s // 60} min {s % 60:02} s' if s >= 60 else f'{s} s'


class Texterkennung:
    def __init__(self, cfg, zentrale_cfg, daten_ordner, log, zentrale):
        self.t = cfg['texterkennung']
        self.e = next(e for e in zentrale_cfg['eintraege'] if e['id'] == self.t['eintrag'])
        self.karten = 'auf einer ' + ' oder '.join(self.e['karten'])
        self.log = log
        self.zentrale = zentrale
        self.endungen = [x.lower() for x in self.t['endungen']]
        os.makedirs(daten_ordner, exist_ok=True)
        self.datei = os.path.join(daten_ordner, 'texterkennung.json')
        self._lock = threading.RLock()
        self._wecker = threading.Event()
        self._abbruch = set()
        self._laufend = None
        self._modell = (0, False)
        self._karte = (0, None)
        d = _json_lesen(self.datei) or {}
        self.auftraege = d.get('auftraege', [])
        for a in self.auftraege:
            if a['zustand'] == 'laeuft':
                a.update(zustand='abgebrochen', meldung='Der Dienst wurde während des Auftrags beendet. '
                                                        '„Wiederholen“ setzt nach der letzten fertigen Seite fort.')
        self._speichern()
        threading.Thread(target=self._schleife, daemon=True).start()

    # ------------------------------------------------------------ Speichern und Anzeigen

    def _speichern(self):
        with self._lock:
            _json_schreiben(self.datei, {'auftraege': self.auftraege})

    def _finden(self, aid):
        return next((a for a in self.auftraege if a['id'] == aid), None)

    def modell_bereit(self, frisch=False):
        """Hat die Zentrale LightOnOCR gestartet und ist es fertig geladen? Kurz gemerkt (3 s)."""
        if not frisch and time.time() - self._modell[0] < 3:
            return self._modell[1]
        bereit = False
        if self.e['port'] in {p for _, p, _ in winapi.lauschende_ports()}:
            try:
                with _OHNE_PROXY.open(f"http://127.0.0.1:{self.e['port']}/v1/models", timeout=3) as r:
                    bereit = self.e['modell_id'] in [m.get('id') for m in json.load(r).get('data', [])]
            except Exception:
                bereit = False
        self._modell = (time.time(), bereit)
        return bereit

    def sekunden_je_seite(self):
        """Mittel der fertigen Aufträge, sonst der Erfahrungswert aus der Konfiguration."""
        n = s = 0
        for a in self.auftraege:
            if a.get('sekunden') and a.get('fertig'):
                n += len(a['fertig'])
                s += a['sekunden']
        return round(s / n, 1) if n >= 3 else self.t['sekunden_je_seite']

    def modell_karte(self):
        """Genutzte Karte laut Zentrale, höchstens alle 5 s neu gefragt (ohne Sperre: die Anfrage hält sonst die Aufträge auf)."""
        if time.time() - self._karte[0] < 5:
            return self._karte[1]
        karte = None
        try:
            s = self.zentrale.status()
            e = ((s.get('stand') or {}).get('eintraege') or {}).get(self.e['id'], {})
            if e.get('zustand') == 'bereit':
                karte = e.get('karte')
        except platz.NichtErreichbar:
            pass
        self._karte = (time.time(), karte)
        return karte

    def stand(self):
        with self._lock:
            liste = [{k: a.get(k) for k in FELDER} for a in self.auftraege]
            for x in liste:
                x['fertig'] = len(x['fertig'] or [])
                x['seiten'] = len(x['seiten'] or [])
        bereit = self.modell_bereit()
        return {'auftraege': liste, 'laufend': self._laufend, 'sekunden_je_seite': self.sekunden_je_seite(),
                'modell': {'bereit': bereit, 'name': self.e['name'],
                           'karte': self.modell_karte() if bereit else None, 'karten': self.karten},
                'hinweis_pruefen': HINWEIS_PRUEFEN, 'endungen': self.endungen}

    # ------------------------------------------------------------ Bedienung

    def _aufnehmen(self, pfade, seiten_wahl, fehler):
        ignoriert, dateien = [], []
        for p in pfade:
            p = p.strip().strip('"')
            if not p:
                continue
            if os.path.isdir(p):
                gefunden, abgeschnitten = quellen.ordner_ausklappen(p, self.endungen, self.t['ordner_max_dateien'])
                if not gefunden:
                    fehler.append(f'Im Ordner {os.path.basename(p)} liegen keine PDFs oder Bilder.')
                if abgeschnitten:
                    fehler.append(f"Im Ordner {os.path.basename(p)} liegen mehr als {self.t['ordner_max_dateien']} "
                                  'Dateien; nur die ersten wurden übernommen.')
                dateien += gefunden
            elif os.path.isfile(p):
                if quellen.ist_medium(p, self.endungen):
                    dateien.append(os.path.normpath(p))
                else:
                    ignoriert.append(os.path.basename(p))
            else:
                fehler.append(f'{p}: nicht gefunden.')
        if ignoriert:
            fehler.append('Kein PDF oder Bild (PNG, JPG): ' + ', '.join(ignoriert[:5]) + (' …' if len(ignoriert) > 5 else ''))
        seiten_wahl = str(seiten_wahl or '').strip()[:200]
        if seiten_wahl:
            try:
                seiten_lesen(seiten_wahl, 100000)
            except ValueError as e:
                fehler.append(str(e))
                return 200, {'neu': 0, 'doppelt': [], 'fehler': fehler, 'auftraege': []}
        neu, doppelt, auftraege = 0, [], []
        with self._lock:
            # Für Skripte: je Datei die ID des neuen oder des schon offenen Auftrags.
            offen = {quellen.normpfad(a['quelle']): a['id'] for a in self.auftraege if a['zustand'] in OFFEN}
            for d in dateien:
                if quellen.normpfad(d) in offen:
                    doppelt.append(os.path.basename(d))
                    auftraege.append({'id': offen[quellen.normpfad(d)], 'quelle': d, 'neu': False})
                    continue
                aid = secrets.token_hex(4)
                offen[quellen.normpfad(d)] = aid
                self.auftraege.append({
                    'id': aid, 'quelle': d, 'titel': os.path.basename(d), 'seiten_wahl': seiten_wahl,
                    'zustand': 'wartet', 'meldung': '', 'hinweis': None, 'ordner': None, 'volltext': None,
                    'seiten_pdf': None, 'seiten': [], 'fertig': [], 'abgeschnitten': [], 'erstellt': time.time(),
                    'sekunden': 0})
                auftraege.append({'id': aid, 'quelle': d, 'neu': True})
                neu += 1
            self._speichern()
        self._wecker.set()
        return 200, {'neu': neu, 'doppelt': doppelt, 'fehler': fehler, 'auftraege': auftraege}

    def hinzufuegen(self, daten):
        text = str(daten.get('text', ''))[:20000]
        return self._aufnehmen(text.splitlines(), daten.get('seiten'), [])

    def waehlen(self, daten):
        besitzer = winapi.fenster_mit_titel('Werkstatt')
        pfade = winapi.dateien_waehlen('PDFs oder Bilder wählen', 'PDF und Bilder', self.endungen, besitzer)
        if not pfade:
            return 200, {'neu': 0, 'doppelt': [], 'fehler': [], 'abgebrochen': True}
        return self._aufnehmen(pfade, daten.get('seiten'), [])

    def ablegen(self, daten):
        abgelegt = [e for e in daten.get('eintraege', []) if isinstance(e, dict)][:500]
        gefunden, offen = quellen.abgleichen(abgelegt, quellen.explorer_markierung())
        code, ergebnis = self._aufnehmen(gefunden, daten.get('seiten'), [])
        ergebnis['nicht_gefunden'] = offen
        return code, ergebnis

    def aktion(self, aid, was):
        with self._lock:
            a = self._finden(aid)
            if not a:
                return 404, {'fehler': 'Diesen Auftrag gibt es nicht mehr.'}
            z = a['zustand']
            if was in ('ordner', 'volltext'):
                ziel = a.get('volltext') if was == 'volltext' else a.get('ordner')
                if not ziel or not quellen.liegt_in(ziel, self.t['ausgabe_ordner']) or not os.path.exists(ziel):
                    return 404, {'fehler': 'Die Datei gibt es (noch) nicht.'}
                os.startfile(ziel)
                return 200, {'ok': True}
            if was == 'entfernen':
                if z == 'laeuft':
                    return 409, {'fehler': 'Der Auftrag läuft noch. Bitte zuerst abbrechen.'}
                self.auftraege.remove(a)  # Nur aus der Liste; die Dateien bleiben.
            elif was == 'abbrechen':
                if z == 'laeuft':
                    self._abbruch.add(aid)
                elif z == 'wartet':
                    a.update(zustand='abgebrochen', meldung='Abgebrochen, bevor er begonnen hat.')
            elif was == 'wiederholen':
                if z not in ('fehler', 'abgebrochen'):
                    return 409, {'fehler': 'Nur abgebrochene oder fehlgeschlagene Aufträge lassen sich wiederholen.'}
                if any(x is not a and quellen.normpfad(x['quelle']) == quellen.normpfad(a['quelle'])
                       and x['zustand'] in OFFEN for x in self.auftraege):
                    return 409, {'fehler': 'Dieselbe Datei steht schon in der Warteschlange.'}
                a.update(zustand='wartet', meldung='', hinweis=None)
            else:
                return 400, {'fehler': 'Unbekannte Aktion.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def aufraeumen(self):
        """Erledigte aus der Liste nehmen; die Dateien bleiben."""
        with self._lock:
            self.auftraege = [x for x in self.auftraege if x['zustand'] != 'fertig']
            self._speichern()
        return 200, {'ok': True}

    # ------------------------------------------------------------ Ablauf

    def _schleife(self):
        while True:
            a = self._naechster()
            if a:
                self._ausfuehren(a)
            else:
                self._wecker.wait(5)
                self._wecker.clear()

    def _naechster(self):
        with self._lock:
            a = next((x for x in self.auftraege if x['zustand'] == 'wartet'), None)
            if a:
                a.update(zustand='laeuft', begonnen=time.time(), meldung='Wird geprüft …', hinweis=None, beendet=None)
                self._laufend = a['id']
                self._speichern()
            return a

    def _ausfuehren(self, a):
        self.log(f"Texterkennung {a['id']} begonnen")
        try:
            a.update(zustand='fertig', meldung=self._bearbeiten(a))
            self.log(f"Texterkennung {a['id']} fertig: {len(a['fertig'])} Seiten in {round(a['sekunden'])} s")
        except Abgebrochen:
            a.update(zustand='abgebrochen', meldung=self._rest_text(a, 'Abgebrochen'))
            self.log(f"Texterkennung {a['id']} abgebrochen")
        except Fehler as f:
            a.update(zustand='fehler', meldung=str(f))
            self.log(f"Texterkennung {a['id']} fehlgeschlagen")
        except Exception as ex:
            a.update(zustand='fehler', meldung=f'Unerwarteter Fehler: {ex}')
            self.log(f"Texterkennung {a['id']} unerwarteter Fehler: "
                     + traceback.format_exc(limit=4).replace('\n', ' | '))
        finally:
            with self._lock:
                a['beendet'] = time.time()
                self._laufend = None
                self._abbruch.discard(a['id'])
                self._speichern()

    def _rest_text(self, a, anfang):
        fertig = len(a.get('fertig') or [])
        if not fertig:
            return f'{anfang}.'
        return f"{anfang} nach {fertig} von {len(a['seiten'])} Seiten; „Wiederholen“ setzt dort fort."

    def _meldung(self, a, text):
        with self._lock:
            a['meldung'] = text

    def _pruefe_abbruch(self, a):
        if a['id'] in self._abbruch:
            raise Abgebrochen()

    def _warten(self, a, sekunden):
        frist = time.time() + sekunden
        while time.time() < frist:
            self._pruefe_abbruch(a)
            time.sleep(0.5)

    def _hilfe(self, a, argumente, timeout=300):
        """Ruft pdf_seiten.py in der Umgebung des PDF-Werkzeugs auf. -> Liste der JSON-Zeilen."""
        self._pruefe_abbruch(a)
        try:
            r = subprocess.run([self.t['pdf_python'], '-I', HILFE, *argumente], capture_output=True,
                               timeout=timeout, creationflags=winapi.CREATE_NO_WINDOW)
        except FileNotFoundError:
            raise Fehler(f"Das PDF-Werkzeug fehlt: {self.t['pdf_python']}")
        except subprocess.TimeoutExpired:
            raise Fehler('Das PDF-Werkzeug hat nicht rechtzeitig geantwortet.')
        zeilen = []
        for z in r.stdout.decode('utf-8', 'replace').splitlines():
            try:
                zeilen.append(json.loads(z))
            except ValueError:
                continue
        fehler = next((z['fehler'] for z in zeilen if 'fehler' in z), None)
        if fehler or r.returncode:
            raise Fehler(fehler or 'Das PDF-Werkzeug ist gescheitert: '
                         + (r.stderr.decode('utf-8', 'replace').strip().splitlines() or ['ohne Meldung'])[-1][:200])
        return zeilen

    def _ordner_anlegen(self, a):
        basis = dateiname(os.path.splitext(os.path.basename(a['quelle']))[0], 80)
        ziel = os.path.join(self.t['ausgabe_ordner'], basis)
        n = 2
        while os.path.exists(ziel):
            ziel = os.path.join(self.t['ausgabe_ordner'], f'{basis} ({n})')
            n += 1
        os.makedirs(ziel)
        return ziel

    def _bearbeiten(self, a):
        q = a['quelle']
        if not os.path.isfile(q):
            raise Fehler('Die Datei ist nicht mehr da, wo sie beim Hinzufügen lag.')
        info = self._hilfe(a, ['info', q], timeout=60)[0]
        try:
            seiten = seiten_lesen(a.get('seiten_wahl'), info['seiten'])
        except ValueError as e:
            raise Fehler(str(e))
        if not seiten:
            raise Fehler('Die Datei hat keine Seiten.')
        if not self.modell_bereit(frisch=True):
            raise Fehler(f"{self.e['name']} läuft nicht. Bitte in der Modellzentrale starten ({self.karten}, "
                         'etwa 4,5 GiB), dann „Wiederholen“.')
        sha = pruefsumme(q)
        lauf_pfad = os.path.join(a['ordner'], 'lauf.json') if a.get('ordner') else None
        lauf = _json_lesen(lauf_pfad) if lauf_pfad and os.path.isdir(a['ordner']) else None
        if not lauf or lauf.get('sha256') != sha or lauf.get('seiten') != seiten:
            # Neu beginnen: neuer Ordner (ein vorhandener Teilstand bleibt unangetastet liegen).
            a.update(ordner=self._ordner_anlegen(a), fertig=[], abgeschnitten=[], sekunden=0, volltext=None)
            lauf = {'quelle': q, 'sha256': sha, 'groesse': os.path.getsize(q), 'art': info['art'],
                    'seiten_datei': info['seiten'], 'seiten': seiten, 'modell': self.e['name'],
                    'modelldatei': os.path.basename(self.e['modelldatei']),
                    'einstellungen': {'kante_px': self.t['kante_px'], 'temperatur': self.t['temperatur'],
                                      'top_p': self.t['top_p'], 'max_tokens': self.t['max_tokens'],
                                      'seed': self.t['seed'], 'prompt': 'leer (Transkription)'},
                    'begonnen': time.strftime('%Y-%m-%d %H:%M:%S'), 'je_seite': {}}
        a.update(seiten=seiten, seiten_pdf=info['seiten'])
        lauf_pfad = os.path.join(a['ordner'], 'lauf.json')
        lauf.update(zustand='laeuft', beendet=None)
        _json_schreiben(lauf_pfad, lauf)
        self._speichern()

        offen = [s for s in seiten if s not in a['fertig']]
        stapel = self.t['stapel']
        try:
            while offen:
                teil, offen = offen[:stapel], offen[stapel:]
                self._meldung(a, f"Seite {teil[0]} wird vorbereitet …")
                bilder = self._hilfe(a, ['seiten', q, *map(str, teil), '--kante', str(self.t['kante_px'])])
                self._gesperrt(a, lambda: self._erkennen(a, bilder, lauf, lauf_pfad))
            a['volltext'] = self._volltext(a, lauf)
        finally:
            komplett = len(a['fertig']) == len(seiten) and a.get('volltext')
            lauf.update(zustand='fertig' if komplett else 'unvollstaendig', sekunden=round(a['sekunden'], 1),
                        fertig=len(a['fertig']), beendet=time.strftime('%Y-%m-%d %H:%M:%S'))
            _json_schreiben(lauf_pfad, lauf)
        teile = [f"{len(seiten)} Seite{'n' if len(seiten) != 1 else ''} in {_dauer_text(a['sekunden'])}"]
        if a['abgeschnitten']:
            teile.append(f"Seite {seiten_text(sorted(a['abgeschnitten']))} an der Längengrenze abgeschnitten")
        return ', '.join(teile) + '.'

    def _gesperrt(self, a, arbeit):
        """Bei der Zentrale fragen, ob etwas dagegen spricht; sonst warten. Seit 16.10.2026 ohne gemeinsame
        GPU-Sperre: LightOnOCR ist geladen und braucht keinen neuen Platz, liest also neben Bildern und Whisper."""
        while True:
            self._pruefe_abbruch(a)
            grund = self._platz_grund()
            if grund is None:
                return arbeit()
            self._meldung(a, grund)
            self._warten(a, 10)

    def _platz_grund(self):
        try:
            code, antwort = self.zentrale.stand()
        except platz.NichtErreichbar as e:
            return f'Die Modellzentrale antwortet nicht ({str(e)[:120]}). Neuer Versuch gleich.'
        if code != 200:
            return f"Die Modellzentrale meldet einen Fehler ({antwort.get('fehler', code)}). Neuer Versuch gleich."
        # Ein Auftrag in ComfyUI hält keinen Platz frei, den LightOnOCR noch bräuchte: kein Grund zu warten.
        gruende = [g for g in antwort.get('gruende', []) if 'ComfyUI' not in g]
        if gruende:
            return 'Wartet: ' + ' '.join(gruende)
        return None

    def _erkennen(self, a, bilder, lauf, lauf_pfad):
        for b in bilder:
            self._pruefe_abbruch(a)
            if not self.modell_bereit(frisch=True):
                raise Fehler(f"{self.e['name']} läuft nicht mehr (in der Modellzentrale beendet?). "
                             + self._rest_text(a, 'Angehalten'))
            n = b['seite']
            self._meldung(a, f"Seite {n} wird gelesen ({len(a['fertig']) + 1} von {len(a['seiten'])}) …")
            beginn = time.time()
            text, ende = self._anfrage(b)
            dauer = time.time() - beginn
            with open(os.path.join(a['ordner'], seiten_datei(n)), 'w', encoding='utf-8') as f:
                f.write(text.strip() + '\n')
            with self._lock:
                a['fertig'].append(n)
                a['sekunden'] += dauer
                if ende == 'length':
                    a['abgeschnitten'].append(n)
            lauf['je_seite'][str(n)] = {'sekunden': round(dauer, 1), 'zeichen': len(text), 'breite': b['breite'],
                                        'hoehe': b['hoehe'], 'abgeschnitten': ende == 'length'}
            _json_schreiben(lauf_pfad, lauf)
            self._speichern()

    def _anfrage(self, b):
        daten = {'model': self.e['modell_id'], 'stream': False, 'seed': self.t['seed'],
                 'temperature': self.t['temperatur'], 'top_p': self.t['top_p'], 'max_tokens': self.t['max_tokens'],
                 'chat_template_kwargs': {'enable_thinking': False},
                 'messages': [{'role': 'user', 'content': [
                     {'type': 'image_url', 'image_url': {'url': f"data:{b['mime']};base64,{b['daten']}"}}]}]}
        anfrage = urllib.request.Request(f"http://127.0.0.1:{self.e['port']}/v1/chat/completions",
                                         json.dumps(daten).encode('utf-8'), {'Content-Type': 'application/json'})
        try:
            with _OHNE_PROXY.open(anfrage, timeout=self.t['zeitlimit_s']) as r:
                antwort = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                grund = (json.loads(e.read()).get('error') or {}).get('message', '')
            except Exception:
                grund = ''
            raise Fehler(f"{self.e['name']} meldet einen Fehler ({e.code}{': ' + grund[:200] if grund else ''}).")
        except (urllib.error.URLError, OSError, TimeoutError):
            raise Fehler(f"{self.e['name']} antwortet nicht mehr. Läuft es noch in der Modellzentrale?")
        wahl = antwort['choices'][0]
        text = re.sub(r'<think>.*?</think>\s*', '', wahl['message'].get('content') or '', flags=re.S)
        return text, wahl.get('finish_reason')

    def _volltext(self, a, lauf):
        seiten = a['seiten']
        kopf = ['---', f"quelle: {json.dumps(a['quelle'], ensure_ascii=False)}",
                f"titel: {json.dumps(a['titel'], ensure_ascii=False)}",
                f"seiten: \"{seiten_text(seiten)}\"" + ('' if len(seiten) == lauf['seiten_datei']
                                                        else f" # von {lauf['seiten_datei']}"),
                f"sha256: {lauf['sha256']}",
                f"modell: {json.dumps(lauf['modell'] + ' (' + lauf['modelldatei'] + ', lokal)', ensure_ascii=False)}",
                f"erstellt: {time.strftime('%Y-%m-%d %H:%M')}", f"dauer_s: {round(a['sekunden'])}",
                'status: automatisch erkannt, nicht geprüft – Stichproben gegen das Original', '---', '']
        teile = []
        for n in seiten:
            try:
                with open(os.path.join(a['ordner'], seiten_datei(n)), encoding='utf-8') as f:
                    text = f.read().strip()
            except OSError:
                text = '[Seite fehlt]'
            if n in a['abgeschnitten']:
                text += '\n\n[Hinweis der Werkstatt: Die Seite wurde an der Längengrenze abgeschnitten.]'
            teile.append(f'## Seite {n}\n\n{text}\n')
        pfad = os.path.join(a['ordner'], 'Volltext.md')
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write('\n'.join(kopf) + '\n' + '\n'.join(teile))
        return pfad
