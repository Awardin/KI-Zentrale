"""Warteschlange der Transkription: ein Auftrag nach dem anderen.

Jeder Auftrag durchläuft Prüfen → Laden → Platz → Transkription → Bilder. Der Zustand
wird nach jedem Schritt gespeichert und übersteht einen Neustart des Dienstes; ein
dabei unterbrochener Auftrag steht danach als „abgebrochen“ zum Wiederholen bereit.
Der Fortschritt wird bei jeder Abfrage frisch aus den Dateien von watch gelesen.
"""
import json
import os
import secrets
import threading
import time
import traceback

from gemeinsam import winapi

from . import platz, watch_lauf

OFFEN = ('wartet', 'laeuft')
FELDER = ('id', 'art', 'quelle', 'video_id', 'titel', 'modus', 'sprache', 'zustand', 'schritt', 'meldung',
          'hinweis', 'ordner', 'transkript', 'karten', 'dauer', 'erstellt', 'begonnen', 'beendet',
          'transkription_s', 'bilder_anzahl')


class Abgebrochen(Exception):
    pass


class Fehler(Exception):
    pass


def _json_lesen(pfad):
    try:
        with open(pfad, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _dauer_text(s):
    s = int(round(s))
    return f'{s // 60} min {s % 60:02} s' if s >= 60 else f'{s} s'


class Warteschlange:
    def __init__(self, cfg, daten_ordner, log, zentrale):
        self.cfg = cfg
        # Gemeinsam mit lokalen Zusammenfassungen: Whisper und ein lokales Sprachmodell rechnen nie gleichzeitig.
        self.w = cfg['watch']
        self.log = log
        self.zentrale = zentrale
        os.makedirs(daten_ordner, exist_ok=True)
        self.datei = os.path.join(daten_ordner, 'auftraege.json')
        self._lock = threading.RLock()
        self._wecker = threading.Event()
        self._jetzt = threading.Event()
        self._gruppe = None
        self._laufend = None
        self._abbruch = set()
        self._live = {}
        d = _json_lesen(self.datei) or {}
        self.auftraege = d.get('auftraege', [])
        self.angehalten = bool(d.get('angehalten'))
        for a in self.auftraege:
            if a['zustand'] == 'laeuft':
                a.update(zustand='abgebrochen', schritt=None,
                         meldung='Der Dienst wurde während des Auftrags beendet. Du kannst ihn wiederholen.')
        self._speichern()
        threading.Thread(target=self._schleife, daemon=True).start()

    # ------------------------------------------------------------ Speichern und Anzeigen

    def _speichern(self):
        with self._lock:
            daten = {'auftraege': self.auftraege, 'angehalten': self.angehalten}
            tmp = self.datei + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(daten, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.datei)

    def _finden(self, aid):
        return next((a for a in self.auftraege if a['id'] == aid), None)

    def stand(self):
        with self._lock:
            liste = []
            for a in self.auftraege:
                x = {k: a.get(k) for k in FELDER}
                if a['id'] == self._laufend:
                    try:
                        x['fortschritt'] = self._fortschritt(a)
                    except Exception:
                        x['fortschritt'] = {}
                liste.append(x)
            return {'auftraege': liste, 'angehalten': self.angehalten, 'laufend': self._laufend}

    def _fortschritt(self, a):
        live = self._live.get(a['id'], {})
        s = a.get('schritt')
        if s == 'pruefen':
            return {'anteil': live.get('anteil')}
        if s == 'laden':
            ordner = watch_lauf.videoordner(self.w['arbeitsordner'], a['video_id'])
            groesse = 0
            if ordner:
                medienordner = os.path.join(ordner, live.get('art', 'audio'))
                try:
                    groesse = sum(e.stat().st_size for e in os.scandir(medienordner) if e.is_file())
                except OSError:
                    pass
            return {'mb': round(groesse / 1048576, 1)}
        if s == 'transkription':
            f = watch_lauf.fortschritt_transkription(live['ziel'])
            f['sekunden'] = round(time.time() - live['beginn'])
            if f.get('sek_fertig') and f.get('sek_gesamt'):
                f['anteil'] = f['sek_fertig'] / f['sek_gesamt']
                vergangen = time.time() - live['beginn']
                f['rest_s'] = round(vergangen / f['anteil'] * (1 - f['anteil'])) if f['anteil'] < 1 else 0
            return f
        if s == 'bilder':
            return {'bilder': live.get('vorher', 0) + watch_lauf.bilder_zaehlen(live['ziel']) if live.get('ziel') else live.get('vorher', 0),
                    'teil': live.get('teil'), 'teile': live.get('teile')}
        return {}

    # ------------------------------------------------------------ Bedienung

    def hinzufuegen(self, quellen, modus, sprache):
        """`quellen`: [('youtube', url) | ('datei', pfad)] -> {'neu': n, 'doppelt': [...], 'erledigt': n}."""
        modus = modus if modus in ('0', '0b') else '0'
        sprache = sprache if sprache in ('auto', 'de', 'en') else 'auto'
        neu, doppelt, erledigt = 0, [], 0
        with self._lock:
            offen = {a['schluessel'] for a in self.auftraege if a['zustand'] in OFFEN}
            for art, q in quellen:
                if art == 'youtube':
                    vid = watch_lauf.youtube_id(q)
                    schluessel, titel = 'yt:' + vid, vid
                else:
                    vid = None
                    schluessel, titel = 'datei:' + os.path.normcase(os.path.normpath(q)), os.path.basename(q)
                if schluessel in offen:
                    doppelt.append(titel)
                    continue
                a = {'id': secrets.token_hex(4), 'art': art, 'quelle': q, 'schluessel': schluessel, 'video_id': vid,
                     'titel': titel, 'modus': modus, 'sprache': sprache, 'zustand': 'wartet', 'schritt': None,
                     'meldung': '', 'hinweis': None, 'ordner': None, 'erstellt': time.time()}
                if art == 'youtube' and self._youtube_schon_erledigt(a):
                    erledigt += 1
                else:
                    offen.add(schluessel)
                self.auftraege.append(a)
                neu += 1
            self._speichern()
        self._wecker.set()
        return {'neu': neu, 'doppelt': doppelt, 'erledigt': erledigt}

    def _youtube_schon_erledigt(self, a):
        """Schnelle Prüfung beim Hinzufügen, damit Erledigtes sofort als übersprungen erscheint."""
        ordner = watch_lauf.videoordner(self.w['arbeitsordner'], a['video_id'])
        if not ordner:
            return False
        medien = watch_lauf.medien_im_ordner(ordner)
        a['titel'] = medien['titel'] or os.path.basename(ordner).rsplit(' [', 1)[0]
        a['ordner'] = ordner
        if not watch_lauf.transkript_passend(watch_lauf.transkripte(ordner), medien['dauer']):
            return False
        if a['modus'] == '0b' and not watch_lauf.bilder_vollstaendig(watch_lauf.bilder_abdeckung(ordner), medien['dauer']):
            return False
        a.update(zustand='uebersprungen', meldung='Transkript'
                 + (' und Bilder sind' if a['modus'] == '0b' else ' ist') + ' schon vorhanden.',
                 beendet=time.time(), dauer=medien['dauer'])
        return True

    def aktion(self, aid, was, wert=None):
        with self._lock:
            a = self._finden(aid)
            if not a:
                return 404, {'fehler': 'Diesen Auftrag gibt es nicht mehr.'}
            z = a['zustand']
            if was == 'entfernen':
                if z == 'laeuft':
                    return 409, {'fehler': 'Der Auftrag läuft noch. Bitte zuerst abbrechen.'}
                self.auftraege.remove(a)
            elif was in ('hoch', 'runter'):
                wartend = [x for x in self.auftraege if x['zustand'] == 'wartet']
                if a not in wartend:
                    return 409, {'fehler': 'Nur wartende Aufträge lassen sich verschieben.'}
                i = wartend.index(a)
                j = i - 1 if was == 'hoch' else i + 1
                if 0 <= j < len(wartend):
                    b = wartend[j]
                    ia, ib = self.auftraege.index(a), self.auftraege.index(b)
                    self.auftraege[ia], self.auftraege[ib] = b, a
            elif was == 'wiederholen':
                if z not in ('fehler', 'abgebrochen'):
                    return 409, {'fehler': 'Nur abgebrochene oder fehlgeschlagene Aufträge lassen sich wiederholen.'}
                if any(x['schluessel'] == a['schluessel'] and x['zustand'] in OFFEN for x in self.auftraege):
                    return 409, {'fehler': 'Dieselbe Quelle steht schon in der Warteschlange.'}
                a.update(zustand='wartet', meldung='', hinweis=None, schritt=None)
            elif was == 'abbrechen':
                if z == 'laeuft':
                    self._abbruch.add(aid)
                    self._jetzt.set()
                    if self._gruppe:
                        self._gruppe.beenden()
                elif z == 'wartet':
                    a.update(zustand='abgebrochen', meldung='Abgebrochen, bevor er begonnen hat.')
            elif was == 'modus':
                if z != 'wartet' or wert not in ('0', '0b'):
                    return 409, {'fehler': 'Der Modus lässt sich nur bei wartenden Aufträgen ändern.'}
                a['modus'] = wert
            elif was == 'erneut':
                self._jetzt.set()
            else:
                return 400, {'fehler': 'Unbekannte Aktion.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def warteschlange(self, was):
        with self._lock:
            if was == 'anhalten':
                self.angehalten = True
            elif was == 'fortsetzen':
                self.angehalten = False
            elif was == 'aufraeumen':
                self.auftraege = [a for a in self.auftraege if a['zustand'] not in ('fertig', 'uebersprungen')]
            else:
                return 400, {'fehler': 'Unbekannte Aktion.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def ordner(self, aid):
        with self._lock:
            a = self._finden(aid)
            return a.get('ordner') if a else None

    # ------------------------------------------------------------ Ablauf

    def _schleife(self):
        while True:
            with self._lock:
                a = None if self.angehalten else next((x for x in self.auftraege if x['zustand'] == 'wartet'), None)
                if a:
                    a.update(zustand='laeuft', begonnen=time.time(), meldung='', hinweis=None, beendet=None)
                    self._laufend = a['id']
                    self._speichern()
            if not a:
                self._wecker.wait(5)
                self._wecker.clear()
                continue
            self.log(f"Auftrag {a['id']} begonnen ({'YouTube' if a['art'] == 'youtube' else 'Datei'}, Modus {a['modus']})")
            try:
                ergebnis = self._bearbeiten(a)
                a.update(zustand=ergebnis[0], meldung=ergebnis[1])
                self.log(f"Auftrag {a['id']} {ergebnis[0]}")
            except Abgebrochen:
                a.update(zustand='abgebrochen', meldung='Abgebrochen.')
                self.log(f"Auftrag {a['id']} abgebrochen")
            except Fehler as f:
                a.update(zustand='fehler', meldung=str(f))
                self.log(f"Auftrag {a['id']} fehlgeschlagen im Schritt {a.get('schritt')}")
            except Exception as ex:
                a.update(zustand='fehler', meldung=f'Unerwarteter Fehler: {ex}')
                self.log(f"Auftrag {a['id']} unerwarteter Fehler: " + traceback.format_exc(limit=4).replace('\n', ' | '))
            finally:
                with self._lock:
                    a.update(schritt=None, beendet=time.time())
                    self._laufend = None
                    self._abbruch.discard(a['id'])
                    self._live.pop(a['id'], None)
                    self._speichern()

    def _schritt(self, a, schritt, meldung, **live):
        with self._lock:
            neu = a.get('schritt') != schritt
            a.update(schritt=schritt, meldung=meldung)
            if neu:
                self._live[a['id']] = {}
            self._live.setdefault(a['id'], {}).update(live)
            if neu:
                self._speichern()

    def _pruefe_abbruch(self, a):
        if a['id'] in self._abbruch:
            raise Abgebrochen()

    def _warten(self, a, sekunden):
        self._jetzt.clear()
        frist = time.time() + sekunden
        while time.time() < frist and not self._jetzt.is_set():
            self._pruefe_abbruch(a)
            time.sleep(0.5)
        self._pruefe_abbruch(a)

    def _ausfuehren(self, a, argumente, puls=None, karten=None):
        """Startet watch.py in einer eigenen Prozessgruppe. -> (Rückgabewert, Ausgabe, Fehlerausgabe).

        `karten`: Karten, die watch sieht. Dann werden alle Karten bis zur höchsten Nummer sichtbar gemacht, damit
        `--gpu` auch stimmt, wenn Windows global eine engere `CUDA_VISIBLE_DEVICES` setzt."""
        self._pruefe_abbruch(a)
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', PYTHONIOENCODING='utf-8')
        if karten:
            env['CUDA_VISIBLE_DEVICES'] = ','.join(str(i) for i in range(max(karten) + 1))
        gruppe = winapi.Prozessgruppe([self.w['python'], self.w['skript'], *argumente],
                                      os.path.dirname(self.w['skript']), env)
        with self._lock:
            self._gruppe = gruppe
        ausgabe = {}

        def lesen():
            ausgabe['aus'], ausgabe['err'] = gruppe.prozess.communicate()
        leser = threading.Thread(target=lesen, daemon=True)
        leser.start()
        letzter_puls = time.time()
        try:
            while leser.is_alive():
                leser.join(1)
                if a['id'] in self._abbruch:
                    gruppe.beenden()
                if puls and time.time() - letzter_puls > 15:
                    puls()
                    letzter_puls = time.time()
        finally:
            with self._lock:
                self._gruppe = None
            gruppe.schliessen()
        self._pruefe_abbruch(a)
        dekodieren = lambda b: (b or b'').decode('utf-8', 'replace')  # noqa: E731
        return gruppe.prozess.returncode, dekodieren(ausgabe.get('aus')), dekodieren(ausgabe.get('err'))

    # ------------------------------------------------------------ Schritte

    def _bearbeiten(self, a):
        ao = self.w['arbeitsordner']
        self._schritt(a, 'pruefen', 'Wird geprüft …')
        sha, bild_moeglich = None, True
        if a['art'] == 'youtube':
            ordner = watch_lauf.videoordner(ao, a['video_id'])
            medien = watch_lauf.medien_im_ordner(ordner)
            dauer = medien['dauer']
            if ordner:
                a.update(ordner=ordner, titel=medien['titel'] or a['titel'])
        else:
            pfad = a['quelle']
            if not os.path.isfile(pfad):
                raise Fehler('Die Datei ist nicht mehr da, wo sie beim Hinzufügen lag.')
            try:
                dauer, bild_moeglich = watch_lauf.medien_info(pfad)
            except ValueError as e:
                raise Fehler(str(e))
            self._schritt(a, 'pruefen', 'Datei wird geprüft …')
            sha = watch_lauf.pruefsumme(pfad, lambda x: self._live.setdefault(a['id'], {}).update(anteil=x))
            ordner = watch_lauf.lokaler_ordner(ao, pfad, sha, self.w['skript'])
            a['ordner'] = ordner
        a['dauer'] = dauer
        self._pruefe_abbruch(a)

        transkript_da = watch_lauf.transkript_passend(watch_lauf.transkripte(ordner), dauer, sha) if ordner else None
        bilder_gewuenscht = a['modus'] == '0b'
        if bilder_gewuenscht and not bild_moeglich:
            bilder_gewuenscht = False
            a['hinweis'] = 'Die Datei enthält nur Ton, deshalb gibt es keine Bilder.'
        bilder_da = not bilder_gewuenscht or (
            ordner and watch_lauf.bilder_vollstaendig(watch_lauf.bilder_abdeckung(ordner), dauer))
        if transkript_da and bilder_da:
            a['transkript'] = transkript_da['ordner']
            return 'uebersprungen', 'Transkript' + (' und Bilder sind' if bilder_gewuenscht else ' ist') \
                + ' schon vorhanden.'

        # Quelle beschaffen bzw. vermerken
        if a['art'] == 'youtube':
            brauche = 'video' if bilder_gewuenscht and not bilder_da else 'audio'
            vorhanden = medien['video'] if brauche == 'video' else (medien['audio'] or medien['video'])
            if not vorhanden:
                self._laden(a, brauche)
                ordner = watch_lauf.videoordner(ao, a['video_id'])
                medien = watch_lauf.medien_im_ordner(ordner)
                if not ordner or not (medien['video'] if brauche == 'video' else medien['audio']):
                    raise Fehler('Der Download ist fertig, aber die Datei wurde nicht gefunden.')
                a.update(ordner=ordner, titel=medien['titel'] or a['titel'])
            ton, bild = medien['audio'] or medien['video'], medien['video']
            sprache = watch_lauf.sprache_kurz(medien['sprache']) if a['sprache'] == 'auto' else a['sprache']
        else:
            self._quelle_vermerken(a, a['quelle'], ordner, 'video' if bild_moeglich else 'audio')
            ton, bild = a['quelle'], a['quelle'] if bild_moeglich else None
            sprache = None if a['sprache'] == 'auto' else a['sprache']
        try:
            dauer_ton = watch_lauf.medien_info(ton)[0]
        except ValueError as e:
            raise Fehler(str(e))
        a['dauer'] = dauer_ton

        teile = []
        if not transkript_da:
            self._transkribieren(a, ton, ordner, dauer_ton, sprache)
            teile.append(f"Transkript in {_dauer_text(a['transkription_s'])}")
        else:
            a['transkript'] = transkript_da['ordner']
            teile.append('Transkript war schon vorhanden')
        if bilder_gewuenscht and not bilder_da:
            self._bilder(a, bild, ordner)
            teile.append(f"{a['bilder_anzahl']} Bilder")
        return 'fertig', ', '.join(teile) + '.'

    def _laden(self, a, art):
        self._schritt(a, 'laden', 'Wird von YouTube geladen …' if art == 'audio' else 'Video wird von YouTube geladen …',
                      art=art)
        code, aus, err = self._ausfuehren(a, ['prepare', a['quelle'], '--out', self.w['arbeitsordner'],
                                              '--media', art, '--title-folder'])
        if code:
            raise Fehler(watch_lauf.fehlertext(err or aus))
        daten = watch_lauf.letztes_json(aus) or {}
        if daten.get('title'):
            a['titel'] = daten['title']

    def _quelle_vermerken(self, a, pfad, ordner, art):
        """Schreibt source.json mit Verweis auf die Originaldatei (keine Kopie)."""
        ziel = os.path.join(ordner, 'quelle')
        if os.path.isfile(os.path.join(ziel, 'source.json')):
            return
        code, aus, err = self._ausfuehren(a, ['prepare', pfad, '--out', ziel, '--media', art])
        if code:
            raise Fehler(watch_lauf.fehlertext(err or aus))

    def _platz_holen(self, a, worker):
        bw = self.w['bedarf_mib_je_worker']
        while True:
            self._pruefe_abbruch(a)
            try:
                code, antwort = self.zentrale.stand()
                if code != 200:
                    raise platz.NichtErreichbar(antwort.get('fehler', f'Fehler {code}'))
                wahl = None if antwort['gruende'] else platz.verteilen(
                    antwort['karten'], bw, worker, self.w['last_beschaeftigt_prozent'])
                if wahl:
                    code, antwort = self.zentrale.anmelden(wahl['bedarf_mib'], 'Transkription')
                    if code == 200:
                        return antwort['anmeldung'], wahl
                    if code != 409:
                        raise platz.NichtErreichbar(antwort.get('fehler', f'Fehler {code}'))
                self._schritt(a, 'platz', 'Wartet auf freien Grafikspeicher. ' + platz.warum_nicht(antwort, bw))
            except platz.NichtErreichbar as e:
                self._schritt(a, 'platz', f'Die Modellzentrale antwortet nicht ({str(e)[:120]}). Neuer Versuch gleich.')
            self._warten(a, 10)

    def _transkribieren(self, a, medium, ordner, dauer, sprache):
        # Keine gemeinsame GPU-Sperre mehr (16.10.2026, Sascha): Whisper läuft neben Bildern, Texterkennung und
        # lokalen Modellen, sobald die Zentrale den angemeldeten Speicher bestätigt.
        self._schritt(a, 'platz', 'Fragt die Modellzentrale nach freiem Grafikspeicher …')
        anmeldung, wahl = self._platz_holen(a, platz.worker_noetig(dauer, self.w['abschnitt_s']))
        try:
            ziel = watch_lauf.transkript_ziel(ordner)
            a.update(karten=wahl['text'], transkript=None)
            argumente = ['transcribe', medium, '--out', ziel, '--gpu', str(wahl['gpu']), '--workers', str(wahl['worker'])]
            if len(wahl['gpus']) > 1:
                argumente += ['--gpus', *map(str, wahl['gpus'])]
            if sprache:
                argumente += ['--language', sprache]
            beginn = time.time()
            self._schritt(a, 'transkription', f"Transkription auf {wahl['text']}", ziel=ziel, beginn=beginn)
            code, aus, err = self._ausfuehren(a, argumente, puls=lambda: self.zentrale.halten(anmeldung['id']),
                                              karten=wahl['gpus'])
        finally:
            self.zentrale.abmelden(anmeldung['id'])
        fertig = watch_lauf.ergebnis_transkription(ziel)
        if code or not fertig:
            raise Fehler('Transkription fehlgeschlagen: ' + watch_lauf.fehlertext(err or aus))
        a.update(transkript=fertig, transkription_s=round(time.time() - beginn))
        if os.path.basename(fertig) == 'single-worker':
            a['hinweis'] = 'Der Grafikspeicher reichte für zwei Worker nicht; watch hat mit einem Worker wiederholt.'
        self.log(f"Auftrag {a['id']}: {round(dauer)} s Ton in {a['transkription_s']} s transkribiert "
                 f"({wahl['text']})")

    def _bilder(self, a, medium, ordner):
        dauer = watch_lauf.medien_info(medium)[0]
        fenster = watch_lauf.bildfenster(dauer, self.w['bild_fenster_s'])
        einzeln = len(fenster) == 1
        vorhanden = watch_lauf.bilder_abdeckung(ordner)
        offen = [f for f in fenster if not watch_lauf.bereich_abgedeckt(vorhanden, *f)]
        anzahl, erledigt = 0, 0
        while offen:
            von, bis = offen.pop(0)
            ziel = watch_lauf.bild_ziel(ordner, von, bis, einzeln and von == 0 and bis >= dauer - 0.01)
            if os.path.exists(ziel):
                ziel = f'{ziel} neu {watch_lauf.zeitstempel()}'
            self._schritt(a, 'bilder', 'Originalbilder werden gewonnen …', ziel=ziel, vorher=anzahl,
                          teil=erledigt + 1, teile=erledigt + 1 + len(offen))
            argumente = ['frames', medium, '--out', ziel, '--interval', str(self.w['bild_intervall_s'])]
            if von > 0:
                argumente += ['--start', str(von)]
            if bis < dauer - 0.01:
                argumente += ['--end', str(bis)]
            code, aus, err = self._ausfuehren(a, argumente)
            if code:
                if 'split into smaller' in (err or '') and bis - von > 60:
                    # Mehr als 240 Bilder in diesem Fenster: halbieren, nichts wird still verworfen.
                    mitte = round((von + bis) / 2, 3)
                    offen[0:0] = [(von, mitte), (mitte, bis)]
                    einzeln = False
                    try:
                        os.rmdir(ziel)
                    except OSError:
                        pass
                    continue
                raise Fehler('Bilder konnten nicht gewonnen werden: ' + watch_lauf.fehlertext(err or aus))
            anzahl += watch_lauf.bilder_zaehlen(ziel)
            erledigt += 1
        a['bilder_anzahl'] = anzahl
