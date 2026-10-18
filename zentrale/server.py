"""Modellzentrale: lokaler Dienst auf 127.0.0.1 mit Oberfläche und Schnittstelle.

Start: pythonw server.py  (normalerweise über start.py)
"""
import collections
import json
import os
import secrets
import sys
import threading
import time
import traceback

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)

from gemeinsam import dienst  # noqa: E402
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen, Fehler  # noqa: E402
from zentrale.erfassung import Erfassung  # noqa: E402

APP_ORDNER = os.path.dirname(os.path.abspath(__file__))
WEB_ORDNER = os.path.join(APP_ORDNER, 'web')
LOG_ORDNER = os.path.join(BASIS, 'logs')
KENNUNG = {'dienst': 'ki-zentrale', 'app': 'modellzentrale', 'version': 2}
ANMELDUNG_MAX_S = 300


class Zentrale:
    def __init__(self, cfg):
        self.cfg = cfg
        self.eintraege = {e['id']: e for e in cfg['eintraege']}
        os.makedirs(LOG_ORDNER, exist_ok=True)
        self._logdatei = os.path.join(LOG_ORDNER, 'zentrale.log')
        self.erf = Erfassung(cfg)
        self.akt = Aktionen(cfg, self.erf, LOG_ORDNER, self.log)
        self._lock = threading.Lock()
        self._aktion_lock = threading.Lock()
        self.aktion = None
        self.laufend = {}
        self.protokoll = collections.deque(maxlen=40)
        self.verlauf = collections.deque(maxlen=300)
        self.roh = None
        self.stand = None
        self.letzter_abruf = time.time()
        self.anmeldungen = {}
        self._platz_lock = threading.Lock()

    # ------------------------------------------------------------ Protokoll

    def log(self, text):
        zeile = time.strftime('%Y-%m-%d %H:%M:%S') + '  ' + text + '\n'
        try:
            with open(self._logdatei, 'a', encoding='utf-8') as f:
                f.write(zeile)
        except OSError:
            pass

    def melden(self, text, art='info'):
        self.log(('FEHLER  ' if art == 'fehler' else '') + text)
        with self._lock:
            self.protokoll.appendleft({'zeit': time.strftime('%H:%M:%S'), 'text': text, 'art': art})

    # ------------------------------------------------------------ Messen

    def schleife(self):
        while True:
            beginn = time.time()
            aktiv = beginn - self.letzter_abruf < 90 or self.aktion
            if aktiv:
                try:
                    self._uebernehmen(self.erf.messen())
                except Exception:
                    self.log('Messfehler: ' + traceback.format_exc(limit=3).replace('\n', ' | '))
            time.sleep(max(0.3, 2.0 - (time.time() - beginn)) if aktiv else 1.0)

    def _uebernehmen(self, roh):
        rest, name, farbe = self._anmeldung_rest(roh)
        namen = planung.kurznamen(roh['karten'], self.cfg['karten'])
        karten = []
        for k in roh['karten']:
            idx = k['index']
            belegung = [{'schluessel': v['schluessel'], 'name': v['name'], 'farbe': v['farbe'],
                         'mib': v['mib_je_karte'].get(idx, 0), 'details': v.get('details_je_karte', {}).get(idx, [])}
                        for v in roh['verbraucher'] if v['mib_je_karte'].get(idx, 0) >= 1]
            if rest.get(idx):
                belegung.append({'schluessel': 'angemeldet', 'name': name, 'farbe': farbe, 'mib': rest[idx], 'details': []})
            kurz = namen[idx]
            karten.append(dict(k, kurz=kurz, belegung=belegung, angemeldet=rest.get(idx, 0)))
        stand = {'zeit': roh['zeit'], 'dauer_ms': roh['dauer_ms'], 'karten': karten,
                 'eintraege': self._zustaende(roh), 'ollama_erreichbar': roh['ollama']['erreichbar'],
                 'fremde_ollama_modelle': [m['tag'] for m in roh['ollama']['geladen']
                                           if m['tag'] not in self.erf.ollama_tags]}
        with self._lock:
            self.roh = roh
            self.stand = stand
            self.verlauf.append({'t': round(roh['zeit']),
                                 'k': [[k['index'], k['belegt'], k['temp'], k['last'], k['watt']] for k in roh['karten']]})

    def _karte_von(self, roh, schluessel):
        """Kurzname der Karte, auf der ein Dienst den meisten Speicher hält (ab 256 MiB), sonst None."""
        anteile = {int(i): m for v in roh.get('verbraucher', []) if v.get('schluessel') == schluessel
                   for i, m in v['mib_je_karte'].items() if m >= 256}
        idx = max(anteile, key=anteile.get, default=None)
        return planung.kurznamen(roh.get('karten', []), self.cfg['karten']).get(idx)

    def _zustaende(self, roh):
        d = roh['dienste']
        z = {}
        for e in self.cfg['eintraege']:
            detail = ''
            karte = None
            if e['art'] == 'ninfer':
                n = d['ninfer']
                zustand = n['zustand']
                if n['fremd']:
                    detail = f"Port {e['port']} ist von {n['fremd']} belegt."
                elif zustand == 'bereit':
                    karte = self._karte_von(roh, 'ninfer')
                    detail = f'Auf der {karte}' if karte else ''
            elif e['art'] == 'strata':
                s = d['strata']
                zustand = s['zustand']
                if zustand == 'bereit':
                    # Laufende Fassung aus Modellname und Kontext laut /health (Q4 und IQ3_XXS 128K haben denselben Kontext).
                    v = next((v for v in e.get('varianten') or [] if v.get('modell') == s.get('modell')
                              and v.get('kontext') == s['kontext']), None)
                    teile = [v['name']] if v else []
                    if s['kontext'] is not None and not v:
                        teile.append(f"Kontext {s['kontext']:,}".replace(',', '.'))
                    teile.append(f"Port {e['port']}")
                    detail = ' · '.join(teile)
                elif zustand == 'fremd':
                    detail = f"Port {e['port']} ist von {s['fremd']} belegt."
            elif e['art'] == 'llamacpp':
                s = d[e['id']]
                zustand = s['zustand']
                if zustand == 'bereit':
                    karte = self._karte_von(roh, 'llamacpp:' + e['id'])
                    detail = f"Port {e['port']}" + (f' · {karte}' if karte else '')
                elif zustand == 'fremd':
                    detail = f"Port {e['port']} ist von {s['fremd']} belegt."
            elif e['art'] == 'polystrata':
                s = d[e['id']]
                zustand = s['zustand']
                if zustand == 'bereit':
                    karte = self._karte_von(roh, 'polystrata:' + e['id'])
                    teile = [f"Kontext {s['kontext']:,}".replace(',', '.')] if s.get('kontext') else []
                    teile.append(f"Port {e['port']}")
                    if karte:
                        teile.append(karte)
                    detail = ' · '.join(teile)
                elif zustand == 'fremd':
                    detail = f"Port {e['port']} ist von {s['fremd']} belegt."
            elif e['art'] == 'ollama':
                m = next((m for m in roh['ollama']['geladen'] if m['tag'] == e['tag']), None)
                if not roh['ollama']['erreichbar']:
                    zustand, detail = 'aus', 'Ollama läuft nicht. Es wird beim Laden gestartet.'
                elif m:
                    zustand = 'bereit'
                    teile = []
                    if m.get('kontext'):
                        teile.append(f"Kontext {m['kontext']:,}".replace(',', '.'))
                    if m['groesse_mib'] - m['vram_mib'] > 256:
                        teile.append(f"{(m['groesse_mib'] - m['vram_mib']) / 1024:.1f} GiB im Arbeitsspeicher".replace('.', ','))
                    detail = ' · '.join(teile)
                else:
                    zustand = 'aus'
            elif e['art'] == 'comfy':
                # 2Wild ist stillgelegt (Stufe 3c); läuft es noch von früher, beendet „Beenden“ es mit.
                c, s = d['comfy'], d['studio']
                if c['fremd']:
                    zustand, detail = 'fremd', f"Port belegt von {c['fremd']}."
                elif c['laeuft']:
                    zustand = 'bereit'
                elif c['pid']:
                    zustand = 'startet'
                else:
                    zustand = 'aus'
                if s['pid']:
                    detail = 'Das alte 2Wild Studio läuft noch; „Beenden“ beendet es mit.'
                c2 = d.get('comfy2') or {}
                if e.get('comfy_port_2') and c['laeuft'] and not s['pid']:
                    detail = ('Zwei Prozesse bereit (je ein Auftrag gleichzeitig).' if c2.get('laeuft') else
                              'Zweiter Prozess startet …' if c2.get('pid') else
                              'Nur ein Prozess läuft; „Starten“ startet den zweiten nach.')
                laufend = c['auftraege_laufend'] + c2.get('auftraege_laufend', 0)
                if laufend:
                    wartend = c['auftraege_wartend'] + c2.get('auftraege_wartend', 0)
                    detail = (f'{laufend} Aufträge laufen' if laufend > 1 else 'Ein Auftrag läuft') + (
                        f', {wartend} warten.' if wartend else '.')
            else:
                zustand = 'laeuft' if d[e['id']]['pids'] else 'aus'
            z[e['id']] = {'zustand': self.laufend.get(e['id'], zustand), 'detail': detail,
                          'auftrag': e['art'] == 'comfy' and (d['comfy']['auftraege_laufend']
                                                              + (d.get('comfy2') or {}).get('auftraege_laufend', 0)) > 0}
            if e['art'] in ('llamacpp', 'ninfer', 'polystrata'):
                z[e['id']]['karte'] = karte
        return z

    def status(self):
        self.letzter_abruf = time.time()
        with self._lock:
            return {'stand': self.stand, 'aktion': self.aktion, 'protokoll': list(self.protokoll)}

    # ------------------------------------------------------------ Planen und Handeln

    def _aktuell(self):
        roh = self.erf.messen()
        self._uebernehmen(roh)
        return roh

    def plan(self, eintrag_id, aktion, variante=None):
        """`variante`: gewählte Variante (Kontextgröße), sonst die Standardvariante; unbekannt -> ValueError."""
        if aktion != 'freigeben':
            e = planung.variante(self.eintraege[eintrag_id], variante)
        roh = self._aktuell()
        karten, verbraucher = planung.mit_anmeldungen(roh['karten'], roh['verbraucher'], *self._anmeldung_rest(roh))
        if aktion == 'freigeben':
            return planung.plan_freigeben(verbraucher)
        if 'karten' in e:
            idx, grund = planung.karte_waehlen(karten, verbraucher, e, self.cfg['reserve_mib'],
                                               self.cfg.get('monitor_puffer_mib', 0))
            if idx is None:
                return {'schritte': [], 'genug_platz': False, 'hinweise': [], 'gruende': [grund],
                        'karte': None, 'karte_kurz': None, 'bedarf_mib': {}}
            bedarf = {idx: e['bedarf_je_karte_mib']}
            ziel = dict(e, bedarf_mib=bedarf)
            plan = planung.plan_fuer_start(karten, verbraucher, ziel, self.cfg['reserve_mib'])
            return dict(plan, karte=idx, karte_kurz=planung.kurznamen(karten, self.cfg['karten'])[idx],
                        bedarf_mib={str(idx): e['bedarf_je_karte_mib']})
        if 'bedarf_mib' not in e and 'bedarf_gesamt_mib' not in e:
            return {'schritte': [], 'genug_platz': True, 'hinweise': [], 'gruende': []}
        plan = planung.plan_fuer_start(karten, verbraucher, e, self.cfg['reserve_mib'])
        if 'bedarf_mib' in plan:
            plan['bedarf_mib'] = {str(i): m for i, m in plan['bedarf_mib'].items()}
        return plan

    # ------------------------------------------------------------ Anmeldungen der Werkstatt

    def _anmeldungen_aktiv(self):
        jetzt = time.time()
        with self._lock:
            abgelaufen = [self.anmeldungen.pop(a) for a, r in list(self.anmeldungen.items()) if r['bis'] < jetzt]
            aktiv = list(self.anmeldungen.values())
        for r in abgelaufen:
            self.melden(f"Anmeldung der Werkstatt ({r['zweck']}) ist abgelaufen.")
        return aktiv

    def _anmeldung_rest(self, roh):
        """-> (Rest je Karte, Anzeigename, Farbe) der noch nicht belegten Anmeldungen."""
        aktiv = self._anmeldungen_aktiv()
        zwecke = sorted({r['zweck'] for r in aktiv})
        name = f"{zwecke[0] if len(zwecke) == 1 else 'Werkstatt'} (angemeldet)"
        farbe = self.cfg['nur_anzeigen']['transkription']['farbe'] + '80'
        return planung.angemeldet_rest(aktiv, roh['verbraucher']), name, farbe

    def _kurzname(self, idx):
        karten = (self.roh or {}).get('karten', [])
        return planung.kurznamen(karten, self.cfg['karten']).get(
            idx, self.cfg['karten'].get(str(idx), {}).get('kurz') or f'Karte {idx}')

    def platz(self, daten):
        """Frischer Stand je Karte; mit `bedarf_mib` und `reservieren` wird geprüft und angemeldet."""
        try:
            bedarf = {int(i): int(m) for i, m in (daten.get('bedarf_mib') or {}).items()}
            dauer = min(ANMELDUNG_MAX_S, max(10, int(daten.get('dauer_s', 60))))
        except (TypeError, ValueError, AttributeError):
            return 400, {'fehler': 'Ungültiger Bedarf.'}
        zweck = str(daten.get('zweck') or 'Werkstatt')[:40]
        # Welcher Verbraucher den angemeldeten Speicher belegen wird (Transkription, „bild-video“ = ComfyUI).
        schluessel = str(daten.get('schluessel') or 'transkription')[:40]
        with self._platz_lock:
            roh = self._aktuell()
            indizes = {k['index'] for k in roh['karten']}
            if any(i not in indizes or not 0 < m <= 49152 for i, m in bedarf.items()):
                return 400, {'fehler': 'Ungültiger Bedarf.'}
            karten, verbraucher = planung.mit_anmeldungen(roh['karten'], roh['verbraucher'], *self._anmeldung_rest(roh))
            pruefung = planung.platz_pruefen(karten, verbraucher, bedarf, self.cfg['reserve_mib'])
            gruende = []
            if self.aktion:
                gruende.append(f"Die Modellzentrale ist gerade beschäftigt: {self.aktion['text']}")
            # Einen Studio-Auftrag deckt seine Anmeldung ab (keine GPU-Sperre mehr, 16.10.2026); nur ein fremder
            # ComfyUI-Auftrag ohne Anmeldung ist ein Grund zu warten, weil sein Bedarf unbekannt ist.
            # Je ComfyUI-Prozess (Stufe 8): ein laufender Auftrag ohne Studio-Anmeldung für genau diesen Prozess.
            for dienst, sl in (('comfy', 'bild-video'), ('comfy2', 'bild-video-2')):
                if (roh['dienste'].get(dienst) or {}).get('auftraege_laufend') and not any(
                        r.get('schluessel') == sl for r in self._anmeldungen_aktiv()):
                    gruende.append('In ComfyUI läuft gerade ein Auftrag.' if dienst == 'comfy' else
                                   'Im zweiten ComfyUI-Prozess läuft gerade ein Auftrag.')
            # Im Leerlauf hält Ollama wenige KiB; erst ein echter Lade- oder Entladevorgang zählt.
            if any(v['schluessel'] == 'ollama' and sum(v['mib_je_karte'].values()) >= 256 for v in roh['verbraucher']):
                gruende.append('Ollama lädt gerade ein Modell oder gibt Speicher frei.')
            def belegt_von(idx):
                gross = sorted((v for v in verbraucher if v['mib_je_karte'].get(idx, 0) >= 256),
                               key=lambda v: -v['mib_je_karte'][idx])
                return [v['name'] for v in gross]
            antwort = {'karten': [{'index': k['index'], 'kurz': self._kurzname(k['index']), 'gesamt': k['gesamt'],
                                   'belegt': k['belegt'], 'frei': max(0, pruefung['frei_mib'][k['index']]),
                                   'last': k['last'], 'belegt_von': belegt_von(k['index']),
                                   'monitor': bool(k.get('monitor'))} for k in karten],
                       'monitor_puffer_mib': self.cfg.get('monitor_puffer_mib', 0),
                       # Wer wie viel belegt, damit andere Apps den eigenen Anteil herausrechnen können (z. B. ComfyUI).
                       'verbraucher': [{'schluessel': v['schluessel'], 'name': v['name'], 'farbe': v.get('farbe'),
                                        'mib_je_karte': {str(i): round(m) for i, m in v['mib_je_karte'].items()}}
                                       for v in verbraucher],
                       'reserve_mib': self.cfg['reserve_mib'], 'genug': pruefung['genug'] and not gruende,
                       'hinweise': pruefung['hinweise'], 'gruende': gruende, 'anmeldung': None}
            if not daten.get('reservieren'):
                return 200, antwort
            if not bedarf and schluessel not in ('bild-video', 'bild-video-2'):
                # Ein Studio-Auftrag darf ohne Zusatzbedarf anmelden (ComfyUI hält schon alles): nur als Kennzeichen.
                return 400, {'fehler': 'Für eine Anmeldung fehlt der Bedarf.'}
            if not antwort['genug']:
                return 409, dict(antwort, fehler='Gerade ist nicht genug Grafikspeicher frei.')
            aid = secrets.token_hex(6)
            basis = {}
            for v in roh['verbraucher']:
                if v.get('schluessel') == schluessel:
                    for i, m in v['mib_je_karte'].items():
                        basis[int(i)] = basis.get(int(i), 0) + m
            with self._lock:
                self.anmeldungen[aid] = {'id': aid, 'zweck': zweck, 'bedarf_mib': bedarf, 'schluessel': schluessel,
                                         'basis': basis, 'seit': time.time(), 'bis': time.time() + dauer}
            antwort['anmeldung'] = {'id': aid, 'bis': time.time() + dauer}
            teile = ' und '.join(f"{m / 1024:.1f} GiB auf der {self._kurzname(i)}".replace('.', ',')
                                 for i, m in sorted(bedarf.items()))
            self.melden(f'Werkstatt hat {zweck} angemeldet: {teile}.' if teile else
                        f'Werkstatt hat {zweck} angemeldet (ComfyUI hält den Speicher schon).')
            self._uebernehmen(roh)
            return 200, antwort

    def platz_halten(self, daten):
        try:
            dauer = min(ANMELDUNG_MAX_S, max(10, int(daten.get('dauer_s', 60))))
        except (TypeError, ValueError):
            dauer = 60
        self._anmeldungen_aktiv()
        with self._lock:
            r = self.anmeldungen.get(str(daten.get('id')))
            if not r:
                return 404, {'fehler': 'Diese Anmeldung gibt es nicht mehr.'}
            r['bis'] = time.time() + dauer
            return 200, {'ok': True, 'bis': r['bis']}

    def platz_freigeben(self, daten):
        with self._lock:
            r = self.anmeldungen.pop(str(daten.get('id')), None)
        if r:
            self.melden(f"Werkstatt hat {r['zweck']} abgemeldet.")
        return 200, {'ok': True}

    def _im_hintergrund(self, text, funktion):
        if not self._aktion_lock.acquire(blocking=False):
            return False
        self.aktion = {'text': text, 'seit': time.time()}

        def lauf():
            try:
                self.melden(funktion(), 'ok')
            except Fehler as f:
                self.melden(str(f), 'fehler')
            except Exception as ex:
                self.log(traceback.format_exc())
                self.melden(f'Unerwarteter Fehler: {ex}', 'fehler')
            finally:
                self.laufend.clear()
                try:
                    self._aktuell()  # Anzeige sofort auf den neuen Stand bringen
                except Exception:
                    pass
                self.aktion = None
                self._aktion_lock.release()
        threading.Thread(target=lauf, daemon=True).start()
        return True

    def _schritte_ausfuehren(self, schritt_ids):
        for sid in schritt_ids:
            ziel = sid.partition(':')[2]
            eintrag = 'ninfer' if ziel == 'ninfer' else ('bild-video' if ziel in ('bild-video', 'bild-video-2') else
                                                         (self.erf.ollama_tags.get(ziel) or {}).get('id'))
            if ziel == 'strata':
                eintrag = self.erf.strata['id'] if self.erf.strata else None
            elif ziel in self.erf.llamacpp or ziel in self.erf.polystrata:
                eintrag = ziel
            if eintrag:
                self.laufend[eintrag] = 'stoppt'
            self.melden(self.akt.schritt(sid), 'ok')
            if eintrag:
                self.laufend.pop(eintrag, None)

    def starten(self, eintrag_id, schritte, ohne_freigabe, variante=None):
        try:
            e = planung.variante(self.eintraege[eintrag_id], variante)
        except ValueError as ex:
            return 400, {'fehler': str(ex)}
        karte = None
        if not ohne_freigabe or 'karten' in e:
            plan = self.plan(eintrag_id, 'starten', variante)
            if 'karten' in e:
                karte = plan['karte']
                if karte is None:
                    return 409, {'fehler': ' '.join(plan['gruende'])}
            if not ohne_freigabe and sorted(schritte) != sorted(s['id'] for s in plan['schritte']):
                return 409, {'fehler': 'Die Belegung hat sich geändert. Bitte erneut bestätigen.'}

        def ablauf():
            if schritte and not ohne_freigabe:
                self._schritte_ausfuehren(schritte)
                if 'karten' in e:
                    self.akt.warten_auf_platz(e, self.cfg['reserve_mib'], bedarf={karte: e['bedarf_je_karte_mib']})
                elif 'bedarf_gesamt_mib' in e:
                    self.akt.warten_auf_platz(e, self.cfg['reserve_mib'], gesamt=e['bedarf_gesamt_mib'])
                else:
                    self.akt.warten_auf_platz(e, self.cfg['reserve_mib'])
            self.laufend[eintrag_id] = 'startet'
            extra = {'variante': e['variante']} if e.get('variante') else {}
            if 'karten' in e:
                return self.akt.starten(eintrag_id, karte=karte, **extra)
            return self.akt.starten(eintrag_id, **extra)
        verb = 'wird geladen' if e['art'] == 'ollama' else 'wird gestartet'
        name = e['name'] + (f" ({e['variante_name']})" if e.get('variante_name') else '')
        if not self._im_hintergrund(f"{name} {verb} …", ablauf):
            return 409, {'fehler': 'Es läuft noch eine andere Aktion.'}
        return 202, {'ok': True}

    def stoppen(self, eintrag_id, erzwingen):
        e = self.eintraege[eintrag_id]

        def ablauf():
            self.laufend[eintrag_id] = 'stoppt'
            return self.akt.stoppen(eintrag_id, erzwingen)
        verb = 'wird entladen' if e['art'] == 'ollama' else 'wird beendet'
        if not self._im_hintergrund(f"{e['name']} {verb} …", ablauf):
            return 409, {'fehler': 'Es läuft noch eine andere Aktion.'}
        return 202, {'ok': True}

    def freigeben(self, schritte):
        plan = self.plan(None, 'freigeben')
        if not schritte or not planung.schritte_gueltig(schritte, plan):
            return 409, {'fehler': 'Die Belegung hat sich geändert. Bitte erneut bestätigen.'}

        def ablauf():
            self._schritte_ausfuehren(schritte)
            return 'GPU freigegeben.'
        if not self._im_hintergrund('GPU wird freigegeben …', ablauf):
            return 409, {'fehler': 'Es läuft noch eine andere Aktion.'}
        return 202, {'ok': True}

    def konfig(self):
        felder = ('id', 'art', 'gruppe', 'name', 'untertitel', 'wofuer', 'farbe', 'bedarf_mib', 'bedarf_geschaetzt',
                  'karten', 'bedarf_je_karte_mib', 'bedarf_gesamt_mib', 'bedarf_hinweis')
        eintraege = []
        for e in self.cfg['eintraege']:
            x = {f: e[f] for f in felder if f in e}
            if e.get('varianten'):
                # Auswahl in der Oberfläche: Name und Bedarf je Variante (Kontext lt. Ollama-Optionen bzw. Einstellung).
                x['varianten'] = [dict({f: v[f] for f in ('id', 'name', 'standard', 'bedarf_mib', 'bedarf_gesamt_mib',
                                                          'bedarf_je_karte_mib') if f in v},
                                       kontext=(v.get('ollama_optionen') or {}).get('num_ctx') or v.get('kontext'))
                                  for v in e['varianten']]
            if e['art'] == 'comfy':
                x['links'] = [{'art': 'comfy', 'text': 'ComfyUI öffnen', 'url': f"http://127.0.0.1:{e['comfy_port']}/"}]
            elif e['art'] in ('strata', 'polystrata'):
                x['links'] = [{'art': e['art'], 'text': 'Chat öffnen', 'url': f"http://127.0.0.1:{e['port']}/"}]
            eintraege.append(x)
        return {'eintraege': eintraege, 'reserve_mib': self.cfg['reserve_mib'],
                'karten_namen': {i: c.get('kurz') for i, c in self.cfg.get('karten', {}).items()},
                'vram_je_prozess': self.erf.vram.verfuegbar}


# ---------------------------------------------------------------- HTTP

class Anfrage(dienst.Anfrage):
    zentrale = None
    kopfzeile = 'X-Zentrale'
    web_ordner = WEB_ORDNER
    statisch = dienst.STATISCH_STANDARD

    def do_GET(self):
        if not self._host_ok():
            return self._senden(403, {'fehler': 'Nur lokal erreichbar.'})
        pfad = self.path.split('?', 1)[0]
        z = self.zentrale
        if self._statisch_senden(pfad):
            return
        if pfad == '/api/health':
            return self._senden(200, KENNUNG)
        if pfad == '/api/konfig':
            return self._senden(200, z.konfig())
        if pfad == '/api/status':
            return self._senden(200, z.status())
        if pfad == '/api/verlauf':
            with z._lock:
                return self._senden(200, list(z.verlauf))
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})

    def do_POST(self):
        if not self._post_ok():
            return self._senden(403, {'fehler': 'Nur aus der Modellzentrale erlaubt.'})
        try:
            daten = self._json_lesen()
            if not isinstance(daten, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self._senden(400, {'fehler': 'Ungültige Anfrage.'})
        z = self.zentrale
        pfad = self.path
        eintrag_id = daten.get('id')
        if pfad in ('/api/plan', '/api/starten', '/api/stoppen') and daten.get('aktion') != 'freigeben' \
                and eintrag_id not in z.eintraege:
            return self._senden(400, {'fehler': 'Unbekannter Eintrag.'})
        try:
            variante = daten.get('variante') or None
            if variante is not None and not isinstance(variante, str):
                return self._senden(400, {'fehler': 'Ungültige Variante.'})
            if pfad == '/api/plan':
                try:
                    return self._senden(200, z.plan(eintrag_id, daten.get('aktion', 'starten'), variante))
                except ValueError as ex:
                    return self._senden(400, {'fehler': str(ex)})
            if pfad == '/api/starten':
                schritte = [str(s) for s in daten.get('schritte', [])]
                return self._senden(*z.starten(eintrag_id, schritte, bool(daten.get('ohne_freigabe')), variante))
            if pfad == '/api/stoppen':
                return self._senden(*z.stoppen(eintrag_id, bool(daten.get('erzwingen'))))
            if pfad == '/api/freigeben':
                return self._senden(*z.freigeben([str(s) for s in daten.get('schritte', [])]))
            if pfad == '/api/platz':
                return self._senden(*z.platz(daten))
            if pfad == '/api/platz/halten':
                return self._senden(*z.platz_halten(daten))
            if pfad == '/api/platz/freigeben':
                return self._senden(*z.platz_freigeben(daten))
        except Exception as ex:
            z.log(traceback.format_exc())
            return self._senden(500, {'fehler': str(ex)})
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})


def main():
    with open(os.path.join(APP_ORDNER, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    zentrale = Zentrale(cfg)
    Anfrage.zentrale = zentrale
    server = dienst.Server(('127.0.0.1', cfg['port']), Anfrage)
    zentrale.log(f"Modellzentrale gestartet auf http://127.0.0.1:{cfg['port']}/")
    threading.Thread(target=zentrale.schleife, daemon=True).start()
    server.serve_forever()


if __name__ == '__main__':
    main()
