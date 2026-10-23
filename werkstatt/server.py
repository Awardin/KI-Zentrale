"""Werkstatt: lokaler Dienst auf 127.0.0.1 mit Oberfläche und Schnittstelle.

Start: pythonw server.py  (normalerweise über start.py)
"""
import json
import os
import re
import sys
import threading
import time
import traceback

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)

from gemeinsam import dienst, winapi  # noqa: E402
from werkstatt import anweisungen, messungen, platz, quellen, studio, texterkennung  # noqa: E402
from werkstatt.auftraege import Warteschlange  # noqa: E402
from werkstatt.auswertung import Auswertungen  # noqa: E402

APP_ORDNER = os.path.dirname(os.path.abspath(__file__))
WEB_ORDNER = os.path.join(APP_ORDNER, 'web')
LOG_ORDNER = os.path.join(BASIS, 'logs')
DATEN_ORDNER = os.path.join(APP_ORDNER, 'daten')
KENNUNG = {'dienst': 'ki-zentrale', 'app': 'werkstatt', 'version': 2}


class Werkstatt:
    def __init__(self, cfg):
        self.cfg = cfg
        self.w = cfg['watch']
        os.makedirs(LOG_ORDNER, exist_ok=True)
        self._logdatei = os.path.join(LOG_ORDNER, 'werkstatt.log')
        self.zentrale = platz.Zentrale(cfg['zentrale_port'], platz.zentrale_starter(BASIS, cfg['zentrale_port']))
        # Whisper und ein lokales Sprachmodell rechnen nie gleichzeitig (Regel aus watch).
        self.schlange = Warteschlange(cfg, DATEN_ORDNER, self.log, self.zentrale)
        self.auswertung = Auswertungen(cfg, DATEN_ORDNER, self.log)
        with open(cfg['zentrale_config'], encoding='utf-8') as f:
            zc = json.load(f)
        self.messlauf = messungen.Messlauf(os.path.join(DATEN_ORDNER, 'messlaeufe.json'),
                                           self.auswertung.anbieter['lokal'], self.log,
                                           zc.get('karten'))
        self.historisch_datei = os.path.join(DATEN_ORDNER, 'messungen-historisch.json')
        bv = next(e for e in zc['eintraege'] if e['art'] == 'comfy')
        # Aus 2Wild (stillgelegt) wird nur noch die Auftragsliste gelesen: Prompts alter Dateien, Messungen.
        self.bv = {'comfy_port': bv['comfy_port'], 'weitere': bv.get('comfy_weitere') or [],
                   'jobs_datei': os.path.join(bv['studio_ordner'], 'data', 'jobs.json')}
        self.studio = studio.Studio(cfg, zc, DATEN_ORDNER, self.log, self.zentrale)
        self.texterkennung = texterkennung.Texterkennung(cfg, zc, DATEN_ORDNER, self.log, self.zentrale)
        self._messungen = (0, None)
        self.endungen = [e.lower() for e in cfg['medien_endungen']]
        self._karten = {'zeit': 0, 'erreichbar': None, 'karten': [], 'gruende': []}
        self.letzter_abruf = time.time()
        threading.Thread(target=self._karten_schleife, daemon=True).start()

    def log(self, text):
        try:
            with open(self._logdatei, 'a', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S') + '  ' + text + '\n')
        except OSError:
            pass

    # ------------------------------------------------------------ Karten (von der Modellzentrale)

    def _karten_schleife(self):
        """Fragt die Zentrale alle 5 s, solange ein Fenster offen ist. Startet sie dafür nicht."""
        while True:
            if time.time() - self.letzter_abruf < 30:
                try:
                    code, a = self.zentrale._post('/api/platz', {}, timeout=10)
                    if code == 200:
                        self._karten = {'zeit': time.time(), 'erreichbar': True, 'karten': a['karten'],
                                        'gruende': a['gruende'], 'verbraucher': a.get('verbraucher', [])}
                    else:
                        self._karten = dict(self._karten, erreichbar=False)
                except platz.NichtErreichbar:
                    self._karten = {'zeit': time.time(), 'erreichbar': False, 'karten': [], 'gruende': []}
            time.sleep(5)

    def stand(self):
        self.letzter_abruf = time.time()
        s = self.schlange.stand()
        s['karten'] = self._karten
        s['bedarf_mib_je_worker'] = self.w['bedarf_mib_je_worker']
        return s

    # ------------------------------------------------------------ Hinzufügen

    def _aufnehmen(self, pfade, youtube, fehler, modus, sprache):
        """Pfade prüfen und Ordner ausklappen, dann alles in die Warteschlange."""
        eintraege = [('youtube', u) for u in youtube]
        ignoriert = []
        for p in pfade:
            if quellen.liegt_in(p, self.w['arbeitsordner']):
                fehler.append(f'{os.path.basename(p)}: liegt schon im Arbeitsordner von watch.')
            elif os.path.isdir(p):
                dateien, abgeschnitten = quellen.ordner_ausklappen(p, self.endungen, self.cfg['ordner_max_dateien'])
                if not dateien:
                    fehler.append(f'Im Ordner {os.path.basename(p)} liegen keine Audio- oder Videodateien.')
                if abgeschnitten:
                    fehler.append(f"Im Ordner {os.path.basename(p)} liegen mehr als {self.cfg['ordner_max_dateien']} "
                                  'Medien; nur die ersten wurden übernommen.')
                eintraege += [('datei', d) for d in dateien]
            elif os.path.isfile(p):
                if quellen.ist_medium(p, self.endungen):
                    eintraege.append(('datei', os.path.normpath(p)))
                else:
                    ignoriert.append(os.path.basename(p))
            else:
                fehler.append(f'{p}: nicht gefunden.')
        if ignoriert:
            fehler.append('Keine Audio- oder Videodatei: ' + ', '.join(ignoriert[:5]) + (' …' if len(ignoriert) > 5 else ''))
        ergebnis = self.schlange.hinzufuegen(eintraege, modus, sprache) if eintraege else \
            {'neu': 0, 'doppelt': [], 'erledigt': 0}
        ergebnis['fehler'] = fehler
        return 200, ergebnis

    def hinzufuegen(self, daten):
        youtube, pfade, fehler = [], [], []
        for art, wert in quellen.text_zerlegen(str(daten.get('text', ''))[:20000]):
            {'youtube': youtube, 'pfad': pfade, 'fehler': fehler}[art].append(wert)
        return self._aufnehmen(pfade, youtube, fehler, daten.get('modus'), daten.get('sprache'))

    def ablegen(self, daten):
        abgelegt = [e for e in daten.get('eintraege', []) if isinstance(e, dict)][:500]
        gefunden, offen = quellen.abgleichen(abgelegt, quellen.explorer_markierung())
        code, ergebnis = self._aufnehmen(gefunden, [], [], daten.get('modus'), daten.get('sprache'))
        ergebnis['nicht_gefunden'] = offen
        return code, ergebnis

    def waehlen(self, daten):
        pfade = quellen.dateien_waehlen(self.endungen)
        if not pfade:
            return 200, {'neu': 0, 'doppelt': [], 'erledigt': 0, 'fehler': [], 'abgebrochen': True}
        return self._aufnehmen(pfade, [], [], daten.get('modus'), daten.get('sprache'))

    # ------------------------------------------------------------ Öffnen

    def ordner_oeffnen(self, aid):
        ordner = self.schlange.ordner(aid)
        if not quellen.liegt_in(ordner, self.w['arbeitsordner']) or not os.path.isdir(ordner):
            return 404, {'fehler': 'Für diesen Auftrag gibt es noch keinen Ausgabeordner.'}
        os.startfile(ordner)
        return 200, {'ok': True}

    def _im_arbeitsordner(self, pfad):
        return quellen.liegt_in(pfad, self.w['arbeitsordner'])

    def fassung_oeffnen(self, aid, was):
        datei = self.auswertung.datei(aid)
        ziel = os.path.dirname(datei) if datei and was == 'ordner' else datei
        if not ziel or not self._im_arbeitsordner(ziel) or not os.path.exists(ziel):
            return 404, {'fehler': 'Die Datei gibt es nicht (mehr).'}
        os.startfile(ziel)
        return 200, {'ok': True}

    def transkript_oeffnen(self, ordner):
        t = next((x for x in self.auswertung.transkripte() if x['ordner'] == ordner), None)
        if not t or not self._im_arbeitsordner(t['transkript']):
            return 404, {'fehler': 'Dieses Transkript gibt es nicht (mehr).'}
        os.startfile(t['ordner'])
        return 200, {'ok': True}

    def anweisung(self, daten):
        s = self.auswertung.sammlung
        was = daten.get('aktion')
        try:
            if was == 'speichern':
                return 200, {'stand': s.speichern(str(daten.get('name')), str(daten.get('text', '')),
                                                  str(daten.get('stand')), daten.get('neuer_name'))}
            if was == 'neu':
                return 200, {'stand': s.neu(str(daten.get('name', '')), str(daten.get('text', '')))}
            if was == 'loeschen':
                s.loeschen(str(daten.get('name')), str(daten.get('stand')))
                return 200, {'ok': True}
            if was == 'einrichten':
                return 200, {'angelegt': s.einrichten()}
        except anweisungen.Konflikt as k:
            return 409, {'fehler': str(k)}
        except ValueError as v:
            return 400, {'fehler': str(v)}
        return 400, {'fehler': 'Unbekannte Aktion.'}

    # ------------------------------------------------------------ Bild & Video

    def bildvideo(self):
        """Echter Zustand von ComfyUI (nur abfragen, nichts starten). 2Wild ist stillgelegt (Stufe 3c)."""
        offen = {port for _, port, _ in winapi.lauschende_ports()}

        def erreichbar(url):
            # Geschlossene Ports gar nicht erst anfragen: Windows wiederholt den Verbindungsversuch sonst ~1 s.
            if int(url.split(':')[2].split('/')[0]) not in offen:
                return False, b''
            try:
                # Beim Rendern antwortet ComfyUI auf /queue selten erst nach 3,5 s (gemessen 25.09.2026).
                with platz._OHNE_PROXY.open(url, timeout=5) as r:
                    return r.status < 500, r.read()
            except Exception:
                return False, b''
        def warteschlange(port):
            an, antwort = erreichbar(f'http://127.0.0.1:{port}/queue') if port else (False, b'')
            laufend = wartend = 0
            if an:
                try:
                    q = json.loads(antwort)
                    laufend, wartend = len(q.get('queue_running', [])), len(q.get('queue_pending', []))
                except ValueError:
                    pass
            return an, laufend, wartend
        comfy, laufend, wartend = warteschlange(self.bv['comfy_port'])
        # Weitere ComfyUI-Prozesse (Stufe 8; seit 22.10.2026 eine Liste): jeder rechnet einen Auftrag gleichzeitig.
        weitere = []
        for w in (self.bv.get('weitere') or self.bv.get('comfy_weitere') or []):
            an, laufend_w, wartend_w = warteschlange(w['port'])
            weitere.append({'nr': w['nr'], 'name': w.get('name') or f"ComfyUI {w['nr']}",
                            'an': an, 'laufend': laufend_w, 'wartend': wartend_w})
        # Alte Felder bleiben für die bisherige Oberfläche: sie meinen Prozess 2, falls es ihn gibt.
        zwei = next((w for w in weitere if w['nr'] == 2), None)
        return {'comfy': comfy, 'laufend': laufend, 'wartend': wartend,
                'comfy_url': f"http://127.0.0.1:{self.bv['comfy_port']}/",
                'weitere': weitere,
                'comfy2_eingerichtet': zwei is not None, 'comfy2': bool(zwei and zwei['an']),
                'laufend2': zwei['laufend'] if zwei else 0, 'wartend2': zwei['wartend'] if zwei else 0}

    # ------------------------------------------------------------ Messungen

    def messungen(self, neu=False):
        if neu or time.time() - self._messungen[0] > 30 or self._messungen[1] is None:
            daten = {'transkription': messungen.transkription(self.w['arbeitsordner']),
                     'bild_video': messungen.bild_video(self.bv['jobs_datei'], self.bv['comfy_port'],
                                                         [dict(a) for a in self.studio.auftraege]),
                     'historisch': messungen.historisch(self.historisch_datei),
                     'gpu_lab_da': os.path.isfile(self.cfg['gpu_lab_db'])}
            self._messungen = (time.time(), daten)
        lokal = self.auswertung.anbieter['lokal']
        # Der Messlauf fragt über den NInfer-Weg an: nur Ollama und NInfer anbieten, keine Strata-Einträge.
        arten = {e['id']: e['art'] for e in lokal._eintraege()[0].values()}
        modelle = []
        for m in lokal.katalog():
            if arten.get(m['modell']) not in ('ollama', 'ninfer'):
                continue
            ok, grund = lokal.verfuegbar({'modell': m['modell']})
            modelle.append({'id': m['modell'], 'name': m['name'], 'geladen': ok, 'grund': grund})
        return dict(self._messungen[1], zusammenfassung=messungen.zusammenfassung(self.auswertung.liste),
                    messlaeufe=list(reversed(self.messlauf.liste()))[:50], messlauf_laeuft=self.messlauf.laufend,
                    lokale_modelle=modelle)

    def historisch_uebernehmen(self):
        if os.path.isfile(self.historisch_datei):
            return 409, {'fehler': 'Die GPU-Lab-Messungen wurden schon übernommen.'}
        if not os.path.isfile(self.cfg['gpu_lab_db']):
            return 404, {'fehler': 'Die Datenbank von GPU-Lab wurde nicht gefunden.'}
        n = messungen.gpu_lab_importieren(self.cfg['gpu_lab_db'], self.historisch_datei)
        self.log(f'GPU-Lab: {n} Messläufe als historisch übernommen')
        self._messungen = (0, None)
        return 200, {'anzahl': n}

    def studio_aktion(self, d):
        s, was = self.studio, d.get('aktion')
        pfade = [str(p) for p in d['pfade']] if isinstance(d.get('pfade'), list) else []
        if was == 'erzeugen':
            return s.erzeugen(d)
        if was in ('abbrechen', 'wiederholen', 'entfernen'):
            return s.aktion(str(d.get('id')), was)
        if was == 'projekt_neu':
            return s.projekt_neu(d.get('name'))
        if was == 'verschieben':
            return s.verschieben(pfade, d.get('projekt'))
        if was == 'papierkorb':
            return s.papierkorb(pfade)
        if was == 'zeigen':
            return s.zeigen(d.get('pfad'), d.get('projekt'))
        if was == 'vorlagen_waehlen':
            return s.vorlagen_waehlen(clips=d.get('clips') is True)
        if was == 'maske':
            return s.maske_lesen(d.get('pfad'))
        if was == 'folge_neu':
            return s.folge_neu(d)
        if was == 'folge':
            return s.folge_aktion(str(d.get('id')), d.get('was'))
        return 400, {'fehler': 'Unbekannte Aktion.'}

    def texterkennung_aktion(self, d):
        t, was = self.texterkennung, d.get('aktion')
        if was == 'hinzufuegen':
            return t.hinzufuegen(d)
        if was == 'waehlen':
            return t.waehlen(d)
        if was == 'ablegen':
            return t.ablegen(d)
        if was == 'aufraeumen':
            return t.aufraeumen()
        return t.aktion(str(d.get('id')), str(was))

    def zentrale_oeffnen(self):
        pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        winapi.starte_losgeloest([pythonw if os.path.exists(pythonw) else sys.executable,
                                  os.path.join(BASIS, 'zentrale', 'start.py')], os.path.join(BASIS, 'zentrale'))
        return 200, {'ok': True}


# ---------------------------------------------------------------- HTTP

class Anfrage(dienst.Anfrage):
    werkstatt = None
    kopfzeile = 'X-Werkstatt'
    web_ordner = WEB_ORDNER
    statisch = dict(dienst.STATISCH_STANDARD,
                    **{f'/{n}': (n, 'text/javascript; charset=utf-8')
                       for n in ('zusammenfassung.js', 'bildvideo.js', 'maske.js', 'studio.js', 'messungen.js',
                                 'texterkennung.js')})

    def _datei_senden(self, pfad):
        """Mediendatei der Bibliothek, mit Teilbereichen (Range) für Videos; die Adresse enthält die Änderungszeit."""
        typ = studio.MEDIEN_TYPEN.get(os.path.splitext(pfad)[1].lower(), 'application/octet-stream')
        groesse = os.path.getsize(pfad)
        start, ende, code = 0, groesse - 1, 200
        m = re.match(r'bytes=(\d*)-(\d*)$', self.headers.get('Range') or '')
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start, ende = int(m.group(1)), int(m.group(2)) if m.group(2) else groesse - 1
            else:
                start = max(0, groesse - int(m.group(2)))
            ende = min(ende, groesse - 1)
            if start > ende:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{groesse}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            code = 206
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(ende - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        if code == 206:
            self.send_header('Content-Range', f'bytes {start}-{ende}/{groesse}')
        self.send_header('Cache-Control', 'private, max-age=86400')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            with open(pfad, 'rb') as f:
                f.seek(start)
                rest = ende - start + 1
                while rest > 0:
                    stueck = f.read(min(1048576, rest))
                    if not stueck:
                        break
                    self.wfile.write(stueck)
                    rest -= len(stueck)
        except (ConnectionError, OSError):
            pass

    def do_GET(self):
        if not self._host_ok():
            return self._senden(403, {'fehler': 'Nur lokal erreichbar.'})
        pfad = self.path.split('?', 1)[0]
        if self._statisch_senden(pfad):
            return
        if pfad == '/api/health':
            return self._senden(200, KENNUNG)
        if pfad == '/api/stand':
            return self._senden(200, self.werkstatt.stand())
        a = self.werkstatt.auswertung
        if pfad == '/api/zusammenfassung':
            return self._senden(200, a.stand())
        if pfad == '/api/transkripte':
            return self._senden(200, a.transkripte(neu='neu=1' in self.path))
        if pfad == '/api/katalog':
            return self._senden(200, a.katalog())
        if pfad == '/api/bildvideo':
            return self._senden(200, self.werkstatt.bildvideo())
        if pfad == '/api/studio':
            return self._senden(200, self.werkstatt.studio.stand())
        if pfad == '/api/studio/bibliothek':
            return self._senden(200, self.werkstatt.studio.bibliothek(neu='neu=1' in self.path))
        if pfad in ('/studio/datei', '/studio/vorlage'):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            p = (q.get('p') or [''])[0]
            s = self.werkstatt.studio
            datei = s.datei(p) if pfad == '/studio/datei' else s.vorlage_datei(p, (q.get('von') or [''])[0])
            if not datei:
                return self._senden(404, {'fehler': 'Die Datei gibt es nicht (mehr).'})
            return self._datei_senden(datei)
        if pfad == '/api/messungen':
            return self._senden(200, self.werkstatt.messungen(neu='neu=1' in self.path))
        if pfad == '/api/texterkennung':
            return self._senden(200, self.werkstatt.texterkennung.stand())
        if pfad == '/api/fassung':
            from urllib.parse import parse_qs, urlparse
            text = a.text((parse_qs(urlparse(self.path).query).get('id') or [''])[0])
            return self._senden(200 if text is not None else 404, {'text': text})
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})

    def do_POST(self):
        if not self._post_ok():
            return self._senden(403, {'fehler': 'Nur aus der Werkstatt erlaubt.'})
        try:
            # Großzügig, weil eine Markierung zum Verbessern (Lauflängen über alle Pixel) mitkommen kann.
            daten = self._json_lesen(16 * 1024 * 1024)
            if not isinstance(daten, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self._senden(400, {'fehler': 'Ungültige Anfrage.'})
        w = self.werkstatt
        pfad = self.path
        try:
            if pfad == '/api/hinzufuegen':
                return self._senden(*w.hinzufuegen(daten))
            if pfad == '/api/ablegen':
                return self._senden(*w.ablegen(daten))
            if pfad == '/api/waehlen':
                return self._senden(*w.waehlen(daten))
            if pfad == '/api/auftrag':
                return self._senden(*w.schlange.aktion(str(daten.get('id')), str(daten.get('aktion')), daten.get('wert')))
            if pfad == '/api/warteschlange':
                return self._senden(*w.schlange.warteschlange(str(daten.get('aktion'))))
            if pfad == '/api/ordner':
                return self._senden(*w.ordner_oeffnen(str(daten.get('id'))))
            if pfad == '/api/zentrale':
                return self._senden(*w.zentrale_oeffnen())
            if pfad == '/api/auswerten':
                return self._senden(*w.auswertung.anlegen(daten))
            if pfad == '/api/fassung':
                was = str(daten.get('aktion'))
                if was in ('oeffnen', 'ordner'):
                    return self._senden(*w.fassung_oeffnen(str(daten.get('id')), was))
                return self._senden(*w.auswertung.aktion(str(daten.get('id')), was))
            if pfad == '/api/transkript-oeffnen':
                return self._senden(*w.transkript_oeffnen(str(daten.get('ordner'))))
            if pfad == '/api/anweisung':
                return self._senden(*w.anweisung(daten))
            if pfad == '/api/messlauf':
                return self._senden(*w.messlauf.starten(str(daten.get('modell'))))
            if pfad == '/api/historisch-uebernehmen':
                return self._senden(*w.historisch_uebernehmen())
            if pfad == '/api/studio':
                return self._senden(*w.studio_aktion(daten))
            if pfad == '/api/texterkennung':
                return self._senden(*w.texterkennung_aktion(daten))
            if pfad == '/api/auswerter':
                if daten.get('aktion') == 'loeschen':
                    return self._senden(*w.auswertung.profil_loeschen(str(daten.get('id'))))
                return self._senden(*w.auswertung.profil_neu(daten))
        except Exception as ex:
            w.log('Fehler: ' + traceback.format_exc(limit=4).replace('\n', ' | '))
            return self._senden(500, {'fehler': str(ex)})
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})


def main():
    with open(os.path.join(APP_ORDNER, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    werkstatt = Werkstatt(cfg)
    Anfrage.werkstatt = werkstatt
    server = dienst.Server(('127.0.0.1', cfg['port']), Anfrage)
    werkstatt.log(f"Werkstatt gestartet auf http://127.0.0.1:{cfg['port']}/")
    server.serve_forever()


if __name__ == '__main__':
    main()
