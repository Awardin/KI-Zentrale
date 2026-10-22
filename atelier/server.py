"""Atelier: lokaler Dienst für den Ebenen-Editor (nur 127.0.0.1, Port 3896).

Start: pythonw server.py  (normalerweise über start.py)
"""
import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)

from gemeinsam import dienst  # noqa: E402

APP_ORDNER = os.path.dirname(os.path.abspath(__file__))
WEB_ORDNER = os.path.join(APP_ORDNER, 'web')
LOG_ORDNER = os.path.join(BASIS, 'logs')
KENNUNG = {'dienst': 'ki-zentrale', 'app': 'atelier', 'version': 1}

BILD_ENDUNGEN = ('.png', '.jpg', '.jpeg', '.webp')
EXPORT_ENDUNGEN = ('.png', '.jpg', '.jpeg', '.json')
STATISCH = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/index.html': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/style.css': ('style.css', 'text/css; charset=utf-8'),
    '/vendor/fabric-6.4.3.min.js': ('vendor/fabric-6.4.3.min.js', 'text/javascript; charset=utf-8'),
    '/vendor/FABRIC-LICENSE.txt': ('vendor/FABRIC-LICENSE.txt', 'text/plain; charset=utf-8'),
}
FIBO_AUS = 'Fibo ist aus – in der Modellzentrale starten.'
WERKSTATT_AUS = ('Die Werkstatt ist aus. Bitte zuerst die Werkstatt starten – dann die '
                 'Studio-Bibliothek erneut öffnen.')
WERKSTATT_FREI_AUS = ('Die Werkstatt ist aus. Bitte zuerst die Werkstatt starten – dann das '
                      'Freistellen erneut versuchen.')
COMFY_AUS = ('ComfyUI läuft nicht. Bitte ComfyUI in der Modellzentrale starten – '
             'dann das Freistellen erneut versuchen.')
FREISTELLEN_FEHLT = ('Das schnelle Freistellen ist nicht eingerichtet: In ComfyUI fehlt das '
                     'Modell BiRefNet. Bitte in der Werkstatt einrichten.')
FIBO_AUFTRAG_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class ZuGross(Exception):
    pass


def projektname_saeubern(name):
    """Projektnamen prüfen und säubern. Pfadangaben und der Fibo-Ordner werden abgelehnt."""
    text = unicodedata.normalize('NFC', str(name or '')).strip()
    if not text:
        raise ValueError('Bitte einen Projektnamen angeben.')
    if '/' in text or '\\' in text or '..' in text or re.match(r'^[A-Za-z]:', text):
        raise ValueError('Projektnamen dürfen keine Pfade enthalten.')
    if len(text) > 80:
        raise ValueError('Der Projektname ist zu lang (höchstens 80 Zeichen).')
    text = re.sub(r'[\x00-\x1f<>:"|?*]', '-', text)
    text = re.sub(r'\s+', ' ', text).strip(' .-')
    if not text or text in ('.', '..'):
        raise ValueError('Bitte einen Projektnamen angeben.')
    if text.casefold().startswith('_fibo'):
        raise ValueError('Der Name _fibo ist für den Fibo-Dienst reserviert.')
    if re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$', text, re.I):
        raise ValueError('Dieser Name ist unter Windows nicht erlaubt.')
    return text


def dateiname_saeubern(name, endung):
    """Nur den Dateistamm behalten; der endgültige Name bleibt im Zielordner."""
    basis = os.path.splitext(os.path.basename(str(name or 'bild')))[0]
    basis = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', '-', basis)
    basis = re.sub(r'\s+', ' ', basis).strip(' .-')
    if not basis:
        basis = 'bild'
    return basis[:60] + '.' + endung


def bild_typ(roh):
    """(Endung, MIME-Typ) anhand der ersten Bytes, sonst None."""
    if roh.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png', 'image/png'
    if roh.startswith(b'\xff\xd8\xff'):
        return 'jpg', 'image/jpeg'
    if len(roh) >= 12 and roh[:4] == b'RIFF' and roh[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    return None


def _endung_typ(datei):
    endung = os.path.splitext(datei)[1].lower()
    return {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.json': 'application/json; charset=utf-8'}.get(
                endung, 'application/octet-stream')


def _ohne_proxy():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Atelier:
    def __init__(self, cfg, logdatei=None):
        self.cfg = cfg
        self.ablage = os.path.realpath(os.path.abspath(str(cfg['ablage'])))
        self.werkstatt = f"http://127.0.0.1:{int(cfg['werkstatt_port'])}"
        self.fibo = f"http://127.0.0.1:{int(cfg['fibo_port'])}"
        self.zeitlimit_werkstatt = float(cfg.get('zeitlimit_werkstatt_s', 4))
        self.zeitlimit_werkstatt_status = float(cfg.get('zeitlimit_werkstatt_status_s', 10))
        self.zeitlimit_fibo = float(cfg.get('zeitlimit_fibo_s', 1.5))
        self.zeitlimit_fibo_auftrag = float(cfg.get('zeitlimit_fibo_auftrag_s', 20))
        self.zeitlimit_fibo_bild = float(cfg.get('zeitlimit_fibo_bild_s', 60))
        self.max_fibo = int(cfg.get('max_fibo_mb', 64))
        self.max_hochladen = int(cfg.get('max_hochladen_mb', 40))
        self.max_export = int(cfg.get('max_export_mb', 120))
        self.max_projekt = int(cfg.get('max_projekt_mb', 16))
        self.max_seite = int(cfg.get('max_seite', 4096))
        self.logdatei = logdatei
        self.opener = _ohne_proxy()

    # ------------------------------------------------------------ Protokoll

    def log(self, text):
        if not self.logdatei:
            return
        try:
            os.makedirs(os.path.dirname(self.logdatei), exist_ok=True)
            with open(self.logdatei, 'a', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S') + '  ' + text + '\n')
        except OSError:
            pass

    # ------------------------------------------------------------ Namen und Pfade

    def _pruefe_pfad(self, pfad):
        try:
            gemeinsam = os.path.commonpath([os.path.normcase(pfad), os.path.normcase(self.ablage)])
        except ValueError:
            gemeinsam = ''
        if gemeinsam != os.path.normcase(self.ablage):
            raise ValueError('Der Pfad liegt außerhalb der Atelier-Ablage.')

    def _projektordner(self, name):
        sauber = projektname_saeubern(name)
        pfad = os.path.realpath(os.path.join(self.ablage, sauber))
        self._pruefe_pfad(pfad)
        if os.path.basename(pfad).casefold().startswith('_fibo'):
            raise ValueError('Der Name _fibo ist für den Fibo-Dienst reserviert.')
        return pfad, sauber

    def _projektdatei(self, name):
        ordner, sauber = self._projektordner(name)
        return os.path.join(ordner, 'projekt.json'), ordner, sauber

    def _dateipfad(self, projekt, datei, unterordner='ebenen', endungen=BILD_ENDUNGEN):
        ordner, _ = self._projektordner(projekt)
        name = str(datei or '').strip()
        if (not name or name != os.path.basename(name) or '..' in name or ':' in name
                or any(ord(zeichen) < 32 for zeichen in name)
                or name.startswith(('/', '\\')) or re.match(r'^[A-Za-z]:', name)):
            raise ValueError('Ungültiger Dateiname.')
        if not name.lower().endswith(tuple(endungen)):
            raise ValueError('Ungültiger Dateityp.')
        zielordner = os.path.realpath(os.path.join(ordner, unterordner))
        pfad = os.path.realpath(os.path.join(zielordner, name))
        try:
            gemeinsam = os.path.commonpath([os.path.normcase(pfad), os.path.normcase(zielordner)])
        except ValueError:
            gemeinsam = ''
        if gemeinsam != os.path.normcase(zielordner):
            raise ValueError('Ungültiger Dateiname.')
        return pfad, ordner, name

    # ------------------------------------------------------------ Projekte

    def _format(self, format):
        if not isinstance(format, dict):
            raise ValueError('Ungültiges Format.')
        try:
            breite = int(format.get('breite'))
            hoehe = int(format.get('hoehe'))
        except (TypeError, ValueError):
            raise ValueError('Ungültige Formatgröße.')
        if not (32 <= breite <= self.max_seite and 32 <= hoehe <= self.max_seite):
            raise ValueError(f'Das Format muss zwischen 32 und {self.max_seite} Pixel je Seite liegen.')
        return {'id': str(format.get('id') or 'eigenes')[:40],
                'name': str(format.get('name') or 'Eigenes')[:80],
                'breite': breite, 'hoehe': hoehe,
                'eigen': bool(format.get('eigen'))}

    def _projekt_inhalt(self, daten, name, alt=None):
        if not isinstance(daten, dict):
            raise ValueError('Ungültige Projektdaten.')
        ebenen = daten.get('ebenen')
        if not isinstance(ebenen, dict) or not isinstance(ebenen.get('objects', []), list):
            raise ValueError('Die Ebenendaten fehlen oder sind ungültig.')
        objekte = ebenen.get('objects', [])
        if len(objekte) > 500:
            raise ValueError('Ein Projekt darf höchstens 500 Ebenen enthalten.')
        format = self._format(daten.get('format') or (alt or {}).get('format'))
        hintergrund = str(daten.get('hintergrund') or '#ffffff')[:32]
        if not re.match(r'^#[0-9A-Fa-f]{3,8}$', hintergrund):
            hintergrund = '#ffffff'
        jetzt = time.strftime('%Y-%m-%dT%H:%M:%S')
        return {'version': 1, 'name': name, 'format': format, 'hintergrund': hintergrund,
                'ebenen': ebenen, 'angelegt': (alt or {}).get('angelegt', jetzt),
                'gespeichert': jetzt}

    def projekte(self):
        if not os.path.isdir(self.ablage):
            return []
        gefunden = []
        for eintrag in os.scandir(self.ablage):
            if not eintrag.is_dir() or eintrag.name.casefold().startswith('_fibo'):
                continue
            datei = os.path.join(eintrag.path, 'projekt.json')
            try:
                with open(datei, encoding='utf-8') as f:
                    daten = json.load(f)
            except (OSError, ValueError):
                continue
            if not isinstance(daten, dict):
                continue
            gefunden.append({'name': eintrag.name,
                             'gespeichert': daten.get('gespeichert'),
                             'format': daten.get('format'),
                             'anzahl_ebenen': len((daten.get('ebenen') or {}).get('objects') or [])})
        gefunden.sort(key=lambda p: p.get('gespeichert') or '', reverse=True)
        return gefunden

    def projekt_laden(self, name):
        datei, _, sauber = self._projektdatei(name)
        if not os.path.isfile(datei):
            return None
        try:
            with open(datei, encoding='utf-8') as f:
                daten = json.load(f)
        except (OSError, ValueError):
            raise ValueError('Die Projektdatei ist beschädigt.')
        if not isinstance(daten, dict):
            raise ValueError('Die Projektdatei ist beschädigt.')
        daten['name'] = sauber
        return daten

    def projekt_neu(self, name, format=None):
        ordner, sauber = self._projektordner(name)
        if os.path.exists(ordner):
            if os.path.isdir(ordner) and os.path.isfile(os.path.join(ordner, 'projekt.json')):
                return 409, {'fehler': 'Ein Projekt mit diesem Namen gibt es schon.'}
            return 409, {'fehler': 'Diesen Ordnernamen gibt es in der Atelier-Ablage schon.'}
        if format is None:
            format = (self.cfg.get('formate') or [None])[0]
        inhalt = self._projekt_inhalt({'format': format, 'hintergrund': '#ffffff',
                                       'ebenen': {'version': '6.4.3', 'objects': []}}, sauber)
        os.makedirs(os.path.join(ordner, 'ebenen'), exist_ok=True)
        os.makedirs(os.path.join(ordner, 'export'), exist_ok=True)
        self._schreiben(os.path.join(ordner, 'projekt.json'), inhalt)
        return 200, {'projekt': inhalt}

    def projekt_speichern(self, name, daten):
        datei, ordner, sauber = self._projektdatei(name)
        if not os.path.isdir(ordner):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        alt = None
        try:
            with open(datei, encoding='utf-8') as f:
                alt = json.load(f)
        except (OSError, ValueError):
            alt = None
        inhalt = self._projekt_inhalt(daten, sauber, alt if isinstance(alt, dict) else None)
        self._schreiben(datei, inhalt)
        return 200, {'gespeichert': inhalt['gespeichert'], 'name': sauber}

    def _schreiben(self, pfad, inhalt):
        tmp = f'{pfad}.{os.getpid()}-{threading.get_ident()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(inhalt, f, ensure_ascii=False, indent=1)
        os.replace(tmp, pfad)

    def projekt_umbenennen(self, name, neu):
        alt, _, sauber = self._projektdatei(name)
        neu_pfad, neuer_name = self._projektordner(neu)
        if not os.path.isdir(os.path.dirname(alt)):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        if os.path.normcase(os.path.dirname(alt)) == os.path.normcase(neu_pfad):
            if os.path.dirname(alt) != neu_pfad:
                tmp = os.path.dirname(alt) + '.__atelier_tmp'
                os.rename(os.path.dirname(alt), tmp)
                os.rename(tmp, neu_pfad)
            daten = self.projekt_laden(neuer_name) or {}
            daten['name'] = neuer_name
            self._schreiben(os.path.join(neu_pfad, 'projekt.json'), daten)
            return 200, {'name': neuer_name}
        if os.path.exists(neu_pfad):
            return 409, {'fehler': 'Ein Projekt mit diesem Namen gibt es schon.'}
        os.rename(os.path.dirname(alt), neu_pfad)
        datei = os.path.join(neu_pfad, 'projekt.json')
        try:
            with open(datei, encoding='utf-8') as f:
                daten = json.load(f)
        except (OSError, ValueError):
            daten = {}
        if isinstance(daten, dict):
            daten['name'] = neuer_name
            self._schreiben(datei, daten)
        return 200, {'name': neuer_name}

    # ------------------------------------------------------------ Bilder

    def _bild_entpacken(self, daten, max_mb):
        text = str((daten or {}).get('daten') or '')
        m = re.match(r'^data:(image/(?:png|jpeg|webp));base64,(.+)$', text, re.S)
        if m:
            text = m.group(2)
        text = re.sub(r'\s+', '', text)
        grenze = int(max_mb * 1024 * 1024)
        if len(text) > (grenze * 4) // 3 + 4096:
            raise ZuGross(f'Das Bild ist zu groß. Erlaubt sind höchstens {max_mb} MB.')
        try:
            roh = base64.b64decode(text, validate=True)
        except (ValueError, base64.binascii.Error):
            raise ValueError('Die Bilddaten sind ungültig.')
        if len(roh) > grenze:
            raise ZuGross(f'Das Bild ist zu groß. Erlaubt sind höchstens {max_mb} MB.')
        if not roh:
            raise ValueError('Die Bilddaten sind leer.')
        typ = bild_typ(roh)
        if not typ:
            raise ValueError('Nur PNG, JPEG oder WebP sind erlaubt.')
        return roh, typ

    def _speichern_bild(self, ordner, name, roh, typ):
        unterordner = os.path.join(ordner, 'ebenen')
        os.makedirs(unterordner, exist_ok=True)
        basis = dateiname_saeubern(name, typ[0])
        stamm = os.path.splitext(basis)[0]
        ziel = os.path.join(unterordner, basis)
        nummer = 2
        while os.path.exists(ziel):
            ziel = os.path.join(unterordner, f'{stamm}-{nummer}.{typ[0]}')
            nummer += 1
        with open(ziel, 'wb') as f:
            f.write(roh)
        return os.path.basename(ziel), typ[1]

    def hochladen(self, daten):
        name = str(daten.get('projekt') or '')
        ordner, sauber = self._projektordner(name)
        if not os.path.isfile(os.path.join(ordner, 'projekt.json')):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        roh, typ = self._bild_entpacken(daten, self.max_hochladen)
        datei, mime = self._speichern_bild(ordner, daten.get('name') or 'Bild', roh, typ)
        return 200, {'datei': datei, 'name': str(daten.get('name') or datei), 'typ': mime}

    def bild_pfad(self, projekt, datei):
        pfad, _, name = self._dateipfad(projekt, datei, 'ebenen', BILD_ENDUNGEN)
        return pfad if os.path.isfile(pfad) else None

    # ------------------------------------------------------------ Studio-Bibliothek

    def _werkstatt_holen(self, pfad, grenze=None, zeitlimit=None):
        url = self.werkstatt + pfad
        try:
            with self.opener.open(url, timeout=zeitlimit or self.zeitlimit_werkstatt) as r:
                return r.status, r.headers.get('Content-Type'), r.read() if grenze is None else r.read(grenze + 1)
        except urllib.error.HTTPError as e:
            try:
                inhalt = e.read(65536)
            except OSError:
                inhalt = b''
            return e.code, e.headers.get('Content-Type'), inhalt
        except (urllib.error.URLError, OSError):
            raise ConnectionError(WERKSTATT_AUS)

    def studio_bibliothek(self):
        code, _, roh = self._werkstatt_holen('/api/studio/bibliothek', 32 * 1024 * 1024)
        if code != 200:
            return 503, {'fehler': WERKSTATT_AUS}
        try:
            daten = json.loads(roh)
        except ValueError:
            return 502, {'fehler': 'Die Werkstatt antwortet unverständlich.'}
        eintraege = []
        for e in daten.get('eintraege', []) if isinstance(daten, dict) else []:
            if not isinstance(e, dict) or e.get('medium') != 'bild':
                continue
            eintraege.append({'pfad': e.get('pfad'), 'name': e.get('name'), 'medium': 'bild',
                              'projekt': e.get('projekt'), 'zeit': e.get('zeit')})
        return 200, {'eintraege': eintraege, 'projekte': daten.get('projekte', [])}

    def studio_bild(self, pfad):
        if not pfad:
            return 400, {'fehler': 'Kein Bild angegeben.'}
        code, typ, roh = self._werkstatt_holen('/studio/datei?p=' + urllib.parse.quote(pfad, safe=''),
                                               self.max_hochladen * 1024 * 1024)
        if code != 200:
            return 503, {'fehler': WERKSTATT_AUS}
        if len(roh) > self.max_hochladen * 1024 * 1024:
            return 413, {'fehler': f'Das Bild ist zu groß (höchstens {self.max_hochladen} MB).'}
        if not bild_typ(roh):
            return 400, {'fehler': 'Die Werkstatt liefert kein PNG, JPEG oder WebP.'}
        return 200, roh, typ or 'application/octet-stream'

    def studio_uebernehmen(self, daten):
        name = str(daten.get('projekt') or '')
        ordner, sauber = self._projektordner(name)
        if not os.path.isfile(os.path.join(ordner, 'projekt.json')):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        pfad = str(daten.get('pfad') or '')
        if not pfad or pfad.startswith(('/', '\\')) or '..' in pfad.replace('\\', '/'):
            return 400, {'fehler': 'Ungültiger Bibliothekspfad.'}
        code, _, roh = self._werkstatt_holen('/studio/datei?p=' + urllib.parse.quote(pfad, safe=''),
                                               self.max_hochladen * 1024 * 1024)
        if code != 200:
            return 503, {'fehler': WERKSTATT_AUS}
        if len(roh) > self.max_hochladen * 1024 * 1024:
            return 413, {'fehler': f'Das Bild ist zu groß (höchstens {self.max_hochladen} MB).'}
        if not roh:
            return 404, {'fehler': 'Die Datei gibt es in der Studio-Bibliothek nicht (mehr).'}
        typ = bild_typ(roh)
        if not typ:
            return 400, {'fehler': 'Die Werkstatt liefert kein PNG, JPEG oder WebP.'}
        datei, mime = self._speichern_bild(ordner, os.path.basename(pfad), roh, typ)
        return 200, {'datei': datei, 'name': os.path.basename(pfad), 'typ': mime,
                     'quelle': {'art': 'studio', 'pfad': pfad}}

    # ------------------------------------------------------------ Fibo

    def _fibo_anfrage(self, methode, pfad, daten=None, zeitlimit=None, grenze=None):
        """Eine Anfrage an den Fibo-Dienst weiterreichen (ohne System-Proxy, mit X-Atelier).

        Liefert (Status, Content-Type, roher Inhalt); ein nicht erreichbarer Dienst wirft
        ConnectionError mit verständlichem Text.
        """
        if not pfad.startswith('/'):
            pfad = '/' + pfad
        kopf = {'X-Atelier': '1', 'Accept': 'application/json, image/png, */*'}
        roh = None
        if daten is not None:
            roh = json.dumps(daten, ensure_ascii=False).encode('utf-8')
            kopf['Content-Type'] = 'application/json'
        anfrage = urllib.request.Request(self.fibo + pfad, data=roh, method=methode, headers=kopf)
        try:
            with self.opener.open(anfrage, timeout=zeitlimit or self.zeitlimit_fibo_auftrag) as r:
                inhalt = r.read() if grenze is None else r.read(grenze + 1)
                return r.status, r.headers.get('Content-Type', ''), inhalt
        except urllib.error.HTTPError as e:
            try:
                inhalt = e.read(1024 * 1024)
            except OSError:
                inhalt = b''
            return e.code, e.headers.get('Content-Type', ''), inhalt
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ConnectionError(FIBO_AUS) from None

    def fibo_proxy(self, methode, pfad, daten=None):
        """GET/POST an den Fibo-Dienst; Fehler werden als Text weitergereicht."""
        try:
            return self._fibo_anfrage(methode, pfad, daten)
        except ConnectionError:
            raise

    def fibo_health(self):
        """Der echte Zustand des Fibo-Dienstes; aus -> 503 mit verständlichem Text."""
        try:
            code, _, roh = self._fibo_anfrage('GET', '/health', zeitlimit=self.zeitlimit_fibo)
        except ConnectionError:
            return 503, {'fehler': FIBO_AUS}
        if code != 200:
            return 503, {'fehler': FIBO_AUS}
        try:
            daten = json.loads(roh or b'{}')
        except ValueError:
            return 502, {'fehler': 'Fibo antwortet unverständlich.'}
        if not isinstance(daten, dict):
            return 502, {'fehler': 'Fibo antwortet unverständlich.'}
        return 200, daten

    def fibo_uebernehmen(self, daten):
        """Ein fertiges Fibo-Ergebnis in `ebenen\\` des Projekts ablegen.

        Dateiname mit Auftrags-ID; daneben eine JSON-Datei mit Prompt, Caption, Seed, Modell
        und Lizenz. Die Ebene trägt `quelle` art fibo.
        """
        name = str(daten.get('projekt') or '')
        ordner, sauber = self._projektordner(name)
        if not os.path.isfile(os.path.join(ordner, 'projekt.json')):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        auftrag_id = str(daten.get('id') or '').strip()
        if not FIBO_AUFTRAG_ID.match(auftrag_id):
            return 400, {'fehler': 'Ungültige Auftrags-ID.'}
        try:
            code, _, roh = self._fibo_anfrage('GET', f'/api/auftrag/{auftrag_id}',
                                              zeitlimit=self.zeitlimit_fibo_auftrag)
        except ConnectionError as ex:
            return 503, {'fehler': str(ex)}
        if code != 200:
            return 502, {'fehler': 'Den Fibo-Auftrag gibt es nicht (mehr).'}
        try:
            info = json.loads(roh or b'{}')
        except ValueError:
            return 502, {'fehler': 'Fibo antwortet unverständlich.'}
        if not isinstance(info, dict):
            return 502, {'fehler': 'Fibo antwortet unverständlich.'}
        zustand = info.get('zustand')
        if zustand == 'fehler':
            return 502, {'fehler': str(info.get('fehler') or 'Der Fibo-Auftrag ist fehlgeschlagen.'),
                         'zustand': zustand}
        if zustand != 'fertig':
            return 409, {'fehler': 'Der Fibo-Auftrag ist noch nicht fertig.', 'zustand': zustand}
        ergebnis = info.get('ergebnis') if isinstance(info.get('ergebnis'), dict) else {}

        begleit = {}
        try:
            b_code, _, b_roh = self._fibo_anfrage('GET', f'/api/datei/{auftrag_id}.json',
                                                  zeitlimit=self.zeitlimit_fibo_auftrag)
            if b_code == 200:
                gelesen = json.loads(b_roh or b'{}')
                if isinstance(gelesen, dict):
                    begleit = gelesen
        except (ConnectionError, ValueError):
            begleit = {}

        bildpfad = str(ergebnis.get('bild') or f'/api/datei/{auftrag_id}.png')
        if not bildpfad.startswith('/api/datei/'):
            bildpfad = f'/api/datei/{auftrag_id}.png'
        try:
            p_code, _, png = self._fibo_anfrage('GET', bildpfad, zeitlimit=self.zeitlimit_fibo_bild,
                                                grenze=self.max_hochladen * 1024 * 1024)
        except ConnectionError as ex:
            return 503, {'fehler': str(ex)}
        if p_code != 200:
            return 502, {'fehler': 'Das Fibo-Ergebnisbild ließ sich nicht holen.'}
        if len(png) > self.max_hochladen * 1024 * 1024:
            return 413, {'fehler': f'Das Fibo-Ergebnis ist zu groß (höchstens {self.max_hochladen} MB).'}
        typ = bild_typ(png)
        if not typ:
            return 502, {'fehler': 'Fibo liefert kein PNG, JPEG oder WebP.'}

        stamm = 'Fibo_' + auftrag_id
        datei, mime = self._speichern_bild(ordner, stamm, png, typ)
        caption = begleit.get('caption', ergebnis.get('caption'))
        seed = begleit.get('seed', ergebnis.get('seed'))
        modell = begleit.get('modell', ergebnis.get('modell'))
        prompt = begleit.get('prompt')
        quelle = {'art': 'fibo', 'lizenz': 'CC BY-NC 4.0', 'modell': modell}
        werte = {'datei': datei, 'name': stamm, 'prompt': prompt, 'caption': caption,
                 'seed': seed, 'modell': modell,
                 'breite': begleit.get('breite', ergebnis.get('breite')),
                 'hoehe': begleit.get('hoehe', ergebnis.get('hoehe')),
                 'quelle': quelle}
        begleitdatei = os.path.splitext(datei)[0] + '.json'
        try:
            self._schreiben(os.path.join(ordner, 'ebenen', begleitdatei), werte)
        except OSError:
            pass
        return 200, {'datei': datei, 'name': stamm, 'typ': mime, 'quelle': quelle,
                     'daten': werte, 'begleit': begleitdatei}

    # ------------------------------------------------------------ Freistellen (Werkstatt)

    def _werkstatt_json(self, pfad, zeitlimit=None):
        code, _, roh = self._werkstatt_holen(pfad, 32 * 1024 * 1024,
                                             zeitlimit=zeitlimit or self.zeitlimit_werkstatt)
        if code != 200:
            raise ConnectionError(WERKSTATT_FREI_AUS)
        try:
            daten = json.loads(roh or b'{}')
        except ValueError:
            raise ValueError('Die Werkstatt antwortet unverständlich.') from None
        if not isinstance(daten, dict):
            raise ValueError('Die Werkstatt antwortet unverständlich.')
        return daten

    def _werkstatt_post(self, pfad, daten, zeitlimit=None):
        roh = json.dumps(daten, ensure_ascii=False).encode('utf-8')
        anfrage = urllib.request.Request(self.werkstatt + pfad, data=roh, method='POST',
                                         headers={'X-Werkstatt': '1', 'Content-Type': 'application/json'})
        try:
            with self.opener.open(anfrage, timeout=zeitlimit or self.zeitlimit_werkstatt_status) as r:
                return r.status, r.read(8 * 1024 * 1024)
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.read(1024 * 1024)
            except OSError:
                return e.code, b''
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ConnectionError(WERKSTATT_FREI_AUS) from None

    def _freistellen_lage(self):
        """ComfyUI und BiRefNet über die Werkstatt prüfen; Text für die Oberfläche."""
        try:
            stand = self._werkstatt_json('/api/studio', self.zeitlimit_werkstatt_status)
        except ConnectionError:
            return {'bereit': False, 'text': WERKSTATT_FREI_AUS, 'werkstatt': False}
        except ValueError:
            return {'bereit': False, 'text': 'Die Werkstatt antwortet unverständlich.', 'werkstatt': True}
        comfy = stand.get('comfy') if isinstance(stand.get('comfy'), dict) else {}
        einstellungen = stand.get('einstellungen') if isinstance(stand.get('einstellungen'), dict) else {}
        if not comfy.get('laeuft'):
            return {'bereit': False, 'text': COMFY_AUS, 'werkstatt': True, 'comfy': False}
        if not einstellungen.get('freistellen_schnell_verfuegbar'):
            return {'bereit': False, 'text': FREISTELLEN_FEHLT, 'werkstatt': True, 'comfy': True,
                    'schnell': False}
        return {'bereit': True, 'text': 'bereit', 'werkstatt': True, 'comfy': True, 'schnell': True}

    def freistellen_status(self):
        return 200, self._freistellen_lage()

    def freistellen_start(self, daten):
        name = str(daten.get('projekt') or '')
        bild = self.bild_pfad(name, str(daten.get('datei') or ''))
        if not bild:
            return 404, {'fehler': 'Das Bild gibt es nicht (mehr).'}
        lage = self._freistellen_lage()
        if not lage['bereit']:
            return 503, {'fehler': lage['text']}
        motiv = re.sub(r'\s+', ' ', str(daten.get('motiv') or '')).strip()[:300]
        koerper = {'aktion': 'erzeugen', 'art': 'freistellen', 'prompt': motiv, 'projekt': '',
                   'vorlagen': [{'art': 'datei', 'pfad': bild, 'rolle': 'original'}]}
        if not motiv:
            koerper['verfahren'] = 'schnell'
        try:
            code, roh = self._werkstatt_post('/api/studio', koerper)
        except ConnectionError as ex:
            return 503, {'fehler': str(ex)}
        try:
            antwort = json.loads(roh or b'{}')
        except ValueError:
            antwort = {}
        if code != 200:
            fehler = antwort.get('fehler') if isinstance(antwort, dict) else None
            return 502, {'fehler': str(fehler or 'Das Freistellen wurde nicht angenommen.')}
        neu = antwort.get('neu') if isinstance(antwort, dict) else None
        if not isinstance(neu, list) or not neu or not FIBO_AUFTRAG_ID.match(str(neu[0])):
            return 502, {'fehler': 'Die Werkstatt hat keine Auftragsnummer gemeldet.'}
        return 200, {'id': str(neu[0]), 'motiv': motiv, 'verfahren': 'schnell' if not motiv else 'qwen'}

    def _freistellen_bild_speichern(self, ordner, auftrag_id, roh):
        """Ergebnis-PNG idempotent nach `ebenen\\` kopieren (Name mit Auftrags-ID)."""
        typ = bild_typ(roh)
        if typ is None or typ[0] != 'png':
            raise ValueError('Die Werkstatt liefert kein PNG.')
        unterordner = os.path.join(ordner, 'ebenen')
        os.makedirs(unterordner, exist_ok=True)
        basis = dateiname_saeubern('Frei_' + auftrag_id, 'png')
        ziel = os.path.join(unterordner, basis)
        if os.path.isfile(ziel):
            try:
                with open(ziel, 'rb') as f:
                    if f.read() == roh:
                        return basis, typ[1]
            except OSError:
                pass
        nummer = 2
        stamm = os.path.splitext(basis)[0]
        while os.path.exists(ziel):
            ziel = os.path.join(unterordner, f'{stamm}-{nummer}.png')
            nummer += 1
        with open(ziel, 'wb') as f:
            f.write(roh)
        return os.path.basename(ziel), typ[1]

    def freistellen_stand(self, auftrag_id, projekt):
        auftrag_id = str(auftrag_id or '').strip()
        if not FIBO_AUFTRAG_ID.match(auftrag_id):
            return 400, {'fehler': 'Ungültige Auftrags-ID.'}
        ordner, sauber = self._projektordner(str(projekt or ''))
        if not os.path.isfile(os.path.join(ordner, 'projekt.json')):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        try:
            stand = self._werkstatt_json('/api/studio', self.zeitlimit_werkstatt_status)
        except ConnectionError as ex:
            return 503, {'fehler': str(ex)}
        except ValueError as ex:
            return 502, {'fehler': str(ex)}
        auftraege = stand.get('auftraege') if isinstance(stand.get('auftraege'), list) else []
        eintrag = next((a for a in auftraege if isinstance(a, dict) and str(a.get('id')) == auftrag_id), None)
        if eintrag is None:
            return 404, {'fehler': 'Diesen Freistell-Auftrag gibt es nicht (mehr).'}
        zustand = eintrag.get('zustand')
        if zustand == 'fertig':
            dateien = eintrag.get('dateien') if isinstance(eintrag.get('dateien'), list) else []
            pfad = str(dateien[0]) if dateien else ''
            if not pfad:
                return 502, {'fehler': 'Die Werkstatt hat kein Ergebnis gemeldet.'}
            try:
                code, _, roh = self._werkstatt_holen(
                    '/studio/datei?p=' + urllib.parse.quote(pfad, safe=''),
                    self.max_hochladen * 1024 * 1024, zeitlimit=self.zeitlimit_werkstatt_status)
            except ConnectionError as ex:
                return 503, {'fehler': str(ex)}
            if code != 200 or not roh:
                return 502, {'fehler': 'Das freigestellte Bild ließ sich nicht holen.'}
            if len(roh) > self.max_hochladen * 1024 * 1024:
                return 413, {'fehler': f'Das Bild ist zu groß (höchstens {self.max_hochladen} MB).'}
            try:
                datei, mime = self._freistellen_bild_speichern(ordner, auftrag_id, roh)
            except ValueError as ex:
                return 502, {'fehler': str(ex)}
            return 200, {'zustand': 'fertig', 'datei': datei, 'typ': mime, 'name': datei,
                         'pfad': pfad, 'motiv': eintrag.get('motiv')}
        if zustand == 'fehler':
            return 200, {'zustand': 'fehler',
                         'fehler': str(eintrag.get('meldung') or 'Das Freistellen ist fehlgeschlagen.')}
        if zustand == 'abgebrochen':
            return 200, {'zustand': 'abgebrochen'}
        return 200, {'zustand': zustand or 'wartet', 'meldung': eintrag.get('meldung') or '',
                     'schritt': eintrag.get('schritt'), 'erwartet_s': eintrag.get('erwartet_s')}

    def freistellen_abbrechen(self, daten):
        auftrag_id = str(daten.get('id') or '').strip()
        if not FIBO_AUFTRAG_ID.match(auftrag_id):
            return 400, {'fehler': 'Ungültige Auftrags-ID.'}
        try:
            code, roh = self._werkstatt_post('/api/studio', {'aktion': 'abbrechen', 'id': auftrag_id})
        except ConnectionError as ex:
            return 503, {'fehler': str(ex)}
        if code != 200:
            try:
                fehler = json.loads(roh or b'{}').get('fehler')
            except (ValueError, AttributeError):
                fehler = None
            return 502, {'fehler': str(fehler or 'Der Auftrag ließ sich nicht abbrechen.')}
        return 200, {'ok': True}

    # ------------------------------------------------------------ Export

    def exportieren(self, daten):
        name = str(daten.get('projekt') or '')
        datei, ordner, sauber = self._projektdatei(name)
        if not os.path.isfile(datei):
            return 404, {'fehler': 'Dieses Projekt gibt es nicht.'}
        roh, typ = self._bild_entpacken({'daten': daten.get('bild')}, self.max_export)
        export_ordner = os.path.join(ordner, 'export')
        os.makedirs(export_ordner, exist_ok=True)
        stamm = dateiname_saeubern(sauber, typ[0])[:-len(typ[0]) - 1]
        stempel = time.strftime('%Y%m%d-%H%M%S')
        basis = f'{stamm}_{stempel}'
        ziel_bild = os.path.join(export_ordner, f'{basis}.{typ[0]}')
        ziel_json = os.path.join(export_ordner, f'{basis}.json')
        nummer = 2
        while os.path.exists(ziel_bild) or os.path.exists(ziel_json):
            ziel_bild = os.path.join(export_ordner, f'{basis}-{nummer}.{typ[0]}')
            ziel_json = os.path.join(export_ordner, f'{basis}-{nummer}.json')
            nummer += 1
        with open(ziel_bild, 'wb') as f:
            f.write(roh)
        try:
            with open(datei, encoding='utf-8') as f:
                projekt = json.load(f)
        except (OSError, ValueError):
            projekt = {}
        objekte = (projekt.get('ebenen') or {}).get('objects') or []
        quellen = []
        fibo_sichtbar = False
        for o in objekte:
            if not isinstance(o, dict):
                continue
            art = o.get('atelierArt') or o.get('type') or 'ebene'
            eintrag = {'name': o.get('atelierName') or art, 'art': art,
                       'sichtbar': o.get('visible') is not False}
            quelle = o.get('quelle') if isinstance(o.get('quelle'), dict) else o.get('atelierQuelle')
            if isinstance(quelle, dict):
                eintrag['quelle'] = quelle
            if art == 'text':
                eintrag['text'] = o.get('text', '')
            if isinstance(quelle, dict) and quelle.get('art') == 'fibo' and eintrag['sichtbar']:
                fibo_sichtbar = True
            quellen.append(eintrag)
        begleit = {'projekt': sauber, 'datei': os.path.basename(ziel_bild),
                   'zeit': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'format': projekt.get('format'), 'quellen': quellen,
                   'fibo_sichtbar': fibo_sichtbar,
                   'nicht_kommerziell': fibo_sichtbar,
                   'hinweis': ('Fibo-Ebenen sind nur nicht-kommerziell nutzbar. '
                               'KI-Bilder bei einer Veröffentlichung kennzeichnen.')}
        self._schreiben(ziel_json, begleit)
        return 200, {'datei': os.path.basename(ziel_bild), 'json': os.path.basename(ziel_json),
                     'fibo_sichtbar': fibo_sichtbar,
                     'nicht_kommerziell': fibo_sichtbar}

    def export_datei(self, projekt, datei):
        pfad, _, name = self._dateipfad(projekt, datei, 'export', EXPORT_ENDUNGEN)
        return pfad if os.path.isfile(pfad) else None


class Anfrage(dienst.Anfrage):
    kopfzeile = 'X-Atelier'
    web_ordner = WEB_ORDNER
    statisch = STATISCH
    atelier = None

    def _lesen(self, grenze):
        try:
            laenge = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            laenge = 0
        if laenge > grenze:
            raise ZuGross('Die Anfrage ist zu groß.')
        roh = self.rfile.read(laenge) if laenge else b'{}'
        return json.loads(roh or b'{}')

    def _senden_datei(self, pfad, typ):
        with open(pfad, 'rb') as f:
            roh = f.read()
        self.send_response(200)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(roh)))
        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" +
                         urllib.parse.quote(os.path.basename(pfad)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        if not self._host_ok():
            return self._senden(403, {'fehler': 'Nur lokal erreichbar.'})
        pfad = self.path.split('?', 1)[0]
        if self._statisch_senden(pfad):
            return
        if pfad == '/api/health':
            return self._senden(200, KENNUNG)
        if pfad == '/api/konfig':
            cfg = self.atelier.cfg
            return self._senden(200, {'app': 'atelier', 'formate': cfg.get('formate', []),
                                      'schriften': cfg.get('schriften', []),
                                      'max_seite': self.atelier.max_seite,
                                      'max_hochladen_mb': self.atelier.max_hochladen})
        if pfad == '/api/projekte':
            return self._senden(200, {'projekte': self.atelier.projekte()})
        if pfad == '/api/fibo/health':
            return self._senden(*self.atelier.fibo_health())
        if pfad.startswith('/api/fibo/'):
            rest = pfad[len('/api/fibo'):]
            if '..' in rest or '\\' in rest or ':' in rest:
                return self._senden(400, {'fehler': 'Ungültige Fibo-Adresse.'})
            try:
                code, typ, roh = self.atelier.fibo_proxy('GET', rest)
            except ConnectionError as ex:
                return self._senden(503, {'fehler': str(ex)})
            return self._senden(code, roh, typ or 'application/octet-stream')
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if pfad == '/api/freistellen/status':
            return self._senden(*self.atelier.freistellen_status())
        if pfad == '/api/freistellen':
            try:
                return self._senden(*self.atelier.freistellen_stand(
                    (q.get('id') or [''])[0], (q.get('projekt') or [''])[0]))
            except ValueError as ex:
                return self._senden(400, {'fehler': str(ex)})
        if pfad == '/api/projekt':
            name = (q.get('name') or [''])[0]
            if not name:
                return self._senden(404, {'fehler': 'Dieses Projekt gibt es nicht.'})
            try:
                daten = self.atelier.projekt_laden(name)
            except ValueError as ex:
                return self._senden(400, {'fehler': str(ex)})
            if daten is None:
                return self._senden(404, {'fehler': 'Dieses Projekt gibt es nicht.'})
            return self._senden(200, daten)
        if pfad == '/api/bild':
            try:
                bild = self.atelier.bild_pfad((q.get('projekt') or [''])[0], (q.get('datei') or [''])[0])
            except ValueError as ex:
                return self._senden(400, {'fehler': str(ex)})
            if not bild:
                return self._senden(404, {'fehler': 'Das Bild gibt es nicht (mehr).'})
            with open(bild, 'rb') as f:
                return self._senden(200, f.read(), _endung_typ(bild))
        if pfad == '/api/export-datei':
            try:
                datei = self.atelier.export_datei((q.get('projekt') or [''])[0], (q.get('datei') or [''])[0])
            except ValueError as ex:
                return self._senden(400, {'fehler': str(ex)})
            if not datei:
                return self._senden(404, {'fehler': 'Die Exportdatei gibt es nicht (mehr).'})
            return self._senden_datei(datei, _endung_typ(datei))
        if pfad == '/api/studio/bibliothek':
            try:
                return self._senden(*self.atelier.studio_bibliothek())
            except ConnectionError as ex:
                return self._senden(503, {'fehler': str(ex)})
            except Exception:
                self.atelier.log('Werkstatt-Bibliothek: ' + traceback.format_exc(limit=3).replace('\n', ' | '))
                return self._senden(502, {'fehler': 'Die Studio-Bibliothek ließ sich nicht lesen.'})
        if pfad == '/api/studio/bild':
            try:
                return self._senden(*self.atelier.studio_bild((q.get('pfad') or [''])[0]))
            except ConnectionError as ex:
                return self._senden(503, {'fehler': str(ex)})
            except Exception:
                self.atelier.log('Studio-Bild: ' + traceback.format_exc(limit=3).replace('\n', ' | '))
                return self._senden(502, {'fehler': 'Das Studio-Bild ließ sich nicht holen.'})
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})

    def do_POST(self):
        if not self._post_ok():
            self.close_connection = True
            return self._senden(403, {'fehler': 'Nur aus dem Atelier erlaubt.'})
        pfad = self.path.split('?', 1)[0]
        grenzen = {'/api/export': int(self.atelier.max_export * 1024 * 1024 * 4 / 3) + 65536,
                   '/api/hochladen': int(self.atelier.max_hochladen * 1024 * 1024 * 4 / 3) + 65536,
                   '/api/studio/uebernehmen': 65536}
        if pfad.startswith('/api/fibo/'):
            grenze = int(self.atelier.max_fibo * 1024 * 1024 * 4 / 3) + 65536
        else:
            grenze = grenzen.get(pfad, self.atelier.max_projekt * 1024 * 1024)
        try:
            daten = self._lesen(grenze)
            if not isinstance(daten, dict):
                raise ValueError
        except ZuGross as ex:
            self.close_connection = True
            return self._senden(413, {'fehler': str(ex)})
        except (ValueError, json.JSONDecodeError):
            return self._senden(400, {'fehler': 'Ungültige Anfrage.'})
        a = self.atelier
        try:
            if pfad == '/api/fibo/uebernehmen':
                return self._senden(*a.fibo_uebernehmen(daten))
            if pfad == '/api/freistellen':
                return self._senden(*a.freistellen_start(daten))
            if pfad == '/api/freistellen/abbrechen':
                return self._senden(*a.freistellen_abbrechen(daten))
            if pfad.startswith('/api/fibo/'):
                rest = pfad[len('/api/fibo'):]
                if '..' in rest or '\\' in rest or ':' in rest:
                    return self._senden(400, {'fehler': 'Ungültige Fibo-Adresse.'})
                code, typ, roh = a.fibo_proxy('POST', rest, daten)
                return self._senden(code, roh, typ or 'application/json; charset=utf-8')
            if pfad == '/api/projekt/neu':
                return self._senden(*a.projekt_neu(str(daten.get('name') or ''), daten.get('format')))
            if pfad == '/api/projekt/speichern':
                return self._senden(*a.projekt_speichern(str(daten.get('name') or ''), daten.get('projekt')))
            if pfad == '/api/projekt/umbenennen':
                return self._senden(*a.projekt_umbenennen(str(daten.get('name') or ''),
                                                          str(daten.get('neu') or '')))
            if pfad == '/api/hochladen':
                return self._senden(*a.hochladen(daten))
            if pfad == '/api/studio/uebernehmen':
                return self._senden(*a.studio_uebernehmen(daten))
            if pfad == '/api/export':
                return self._senden(*a.exportieren(daten))
        except ZuGross as ex:
            return self._senden(413, {'fehler': str(ex)})
        except ConnectionError as ex:
            return self._senden(503, {'fehler': str(ex)})
        except ValueError as ex:
            return self._senden(400, {'fehler': str(ex)})
        except Exception:
            a.log('Fehler: ' + traceback.format_exc(limit=4).replace('\n', ' | '))
            return self._senden(500, {'fehler': 'Im Atelier ist ein Fehler aufgetreten.'})
        self._senden(404, {'fehler': 'Unbekannte Adresse.'})


def starte(cfg, port=0, logdatei=None):
    """Startet den Dienst im Hintergrund (für Tests und main)."""
    atelier = Atelier(cfg, logdatei)
    Anfrage.atelier = atelier
    server = dienst.Server(('127.0.0.1', int(port)), Anfrage)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, atelier


def _einstellungen():
    with open(os.path.join(APP_ORDNER, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    parser = argparse.ArgumentParser(description='Atelier-Dienst')
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--ablage', default=None)
    args = parser.parse_args()
    if os.environ.get('ATELIER_PORT'):
        cfg['port'] = int(os.environ['ATELIER_PORT'])
    if os.environ.get('ATELIER_ABLAGE'):
        cfg['ablage'] = os.environ['ATELIER_ABLAGE']
    if args.port is not None:
        cfg['port'] = args.port
    if args.ablage:
        cfg['ablage'] = args.ablage
    return cfg


def main():
    cfg = _einstellungen()
    logdatei = os.path.join(LOG_ORDNER, 'atelier.log')
    atelier = Atelier(cfg, logdatei)
    Anfrage.atelier = atelier
    server = dienst.Server(('127.0.0.1', int(cfg['port'])), Anfrage)
    atelier.log(f"Atelier gestartet auf http://127.0.0.1:{server.server_address[1]}/ "
                f"(Ablage {atelier.ablage})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
