"""Promptdateien und schreibgeschützter Blick auf die gemeinsame Sammlung."""
import datetime
import hashlib
import json
import os
import re
import threading

from werkstatt.anweisungen import ABSCHNITT, Konflikt, name_pruefen, stand, text_pruefen
from werkstatt.auswertung import dateiname

_SPERRE = threading.RLock()
# Steuerzeichen und alles, was str.splitlines() als Zeilenumbruch nimmt (NEL, LS, PS): sonst könnte ein Name
# oder eine Kopfzeile beim nächsten Lesen als eigene Zeile oder Überschrift erscheinen.
_STEUERZEICHEN = re.compile(r'[\x00-\x1f\x7f\x85\u2028\u2029]')

_FELD = re.compile(r'\[([^\[\]\n]{1,60})\](?!\()')


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class PromptFehler(RuntimeError):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def kontext_pruefen(text, kontext):
    geschaetzt = (len(text) + 600) / 3.0
    reserve = min(32768, kontext // 4) if kontext else 0
    if kontext and geschaetzt + reserve > kontext:
        raise PromptFehler('kontext', f'Der Auftrag ist zu lang für {kontext:,} Token Kontext.'.replace(',', '.'))
    return geschaetzt, reserve


def felder_erkennen(text):
    return list(dict.fromkeys(m[1] for m in _FELD.finditer(text)
                              if ':' not in m[1] and any(c.isalpha() for c in m[1])))


def auftrag_bauen(fassung, eingaben, transkripte):
    """Ein Durchgang: eingesetztes Material wird nie erneut ersetzt."""
    namen = felder_erkennen(fassung)
    def ersetzen(m):
        name = m[0][1:-1]
        feld = eingaben.get('felder', {}).get(name, {})
        if feld.get('art') == 'woertlich' or name in eingaben.get('leer', []):
            return m[0]
        wert = transkripte.get(name, '') if feld.get('art') == 'transkript' else feld.get('wert', '')
        return wert if wert else m[0]
    muster = '|'.join(re.escape('[' + n + ']') + r'(?!\()' for n in namen)
    text = re.sub(muster, ersetzen, fassung) if muster else fassung
    rahmen = eingaben.get('rahmen', {}).get('wert', '')
    if rahmen:
        text = rahmen + '\n\n' + text
    return text, sha(text)


def _belegkopf(text):
    zeilen = text.splitlines(keepends=True)
    if not zeilen or zeilen[0].strip() != '---':
        raise ValueError('Beleg beschädigt: Kopf fehlt.')
    ende = next((i for i in range(1, len(zeilen)) if zeilen[i].strip() == '---'), None)
    if ende is None:
        raise ValueError('Beleg beschädigt: Kopf ist offen.')
    kopf = {}
    for z in zeilen[1:ende]:
        k, trenner, v = z.partition(':')
        if trenner:
            try:
                kopf[k] = json.loads(v)
            except ValueError:
                kopf[k] = v.strip()
    return zeilen, ende, kopf, stand(''.join(zeilen[:ende + 1]))


def beleg_lesen(datei):
    roh = _lesen(datei)
    zeilen, ende, kopf, ks = _belegkopf(roh)
    rest = ''.join(zeilen[ende + 1:])
    zs, bs, hs = _zeilenkopf(rest)
    abschnitte = {}
    anzahl = {}
    for i, titel in hs:
        if titel not in ('## Fassung', '## Eingaben', '## Antwort'):
            continue
        anzahl[titel] = anzahl.get(titel, 0) + 1
        bis = next((j for j, _ in hs if j > i), len(zs))
        kandidaten = [b for b in bs if i < b['auf'] < bis]
        if len(kandidaten) == 1 and not ''.join(zs[i + 1:kandidaten[0]['auf']]).strip():
            b = kandidaten[0]
            if b['geschlossen']:
                abschnitte[titel[3:].lower()] = b['text']
    if ('fassung' not in abschnitte or 'eingaben' not in abschnitte
            or anzahl.get('## Fassung') != 1 or anzahl.get('## Eingaben') != 1):
        raise ValueError('Beleg beschädigt: Fassung oder Eingaben fehlen.')
    eingaben = json.loads(abschnitte['eingaben'])
    if not isinstance(eingaben, dict) or not isinstance(eingaben.get('felder'), dict):
        raise ValueError('Beleg beschädigt: Eingaben sind ungültig.')
    return dict(kopf, kopf_stand=ks, fassung_text=abschnitte['fassung'], eingaben=eingaben,
                antwort=abschnitte.get('antwort', ''), datei=os.path.basename(datei), datei_stand=sha(roh))


def _kopf_setzen(datei, werte, kopf_stand=None):
    with _SPERRE:
        roh = _lesen(datei)
        zs, ende, _, ks = _belegkopf(roh)
        if kopf_stand is not None and ks != kopf_stand:
            raise Konflikt('Der Belegkopf wurde inzwischen geändert, bitte neu laden.')
        nl = '\r\n' if '\r\n' in roh else '\n'
        for k, v in werte.items():
            ziel = next((i for i in range(1, ende) if zs[i].startswith(k + ':')), ende)
            zs[ziel:ziel + (ziel < ende)] = [k + ': ' + _kopfwert(v, k) + nl]
            if ziel == ende:
                ende += 1
        _atomar(datei, ''.join(zs))
        return _belegkopf(_lesen(datei))[3]


def beleg_zustand(datei, zustand, meldung='', **kopf):
    return _kopf_setzen(datei, dict(kopf, zustand=zustand, meldung=meldung))


def _kopfwert(wert, schluessel):
    if (isinstance(wert, str) and schluessel in {
            'eintrag', 'herkunft', 'fassung_stand', 'rahmen', 'gesendet_stand', 'anbieter', 'modell',
            'modell_tatsaechlich', 'kontext_quelle', 'denkstufe', 'verarbeitung', 'zustand',
            'erstellt', 'html', 'urteil', 'status'} and not _STEUERZEICHEN.search(wert)):
        return wert
    text = json.dumps(wert, ensure_ascii=False)
    for c in ('\x85', '\u2028', '\u2029'):
        text = text.replace(c, '\\u%04x' % ord(c))
    return text


def beleg_anlegen(ordner, kopf, fassung, eingaben):
    with _SPERRE:
        os.makedirs(ordner, exist_ok=True)
        basis = (datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S') + ' – '
                 + dateiname(kopf['fassung']) + ' – ' + dateiname(kopf['auswerter']))
        n = 1
        while True:
            name = basis + (f' ({n})' if n > 1 else '')
            datei = os.path.join(ordner, name + '.md')
            if not pfad_erlaubt(datei, [ordner]):
                raise ValueError('Belegpfad nicht erlaubt.')
            try:
                with open(datei, 'x', encoding='utf-8', newline='') as f:
                    k = {'auftrag': name, **kopf}
                    f.write('---\n' + ''.join(key + ': ' + _kopfwert(v, key) + '\n'
                                             for key, v in k.items()) + '---\n## Fassung\n'
                            + block_schreiben(fassung, 'text') + '## Eingaben\n'
                            + block_schreiben(json.dumps(eingaben, ensure_ascii=False, indent=2), 'json'))
                return datei
            except FileExistsError:
                n += 1


def antwort_schreiben(datei, text):
    with _SPERRE:
        roh = _lesen(datei)
        zs, _, hs = _zeilenkopf(roh)
        i = next((i for i, z in hs if z == '## Antwort'), len(zs))
        nl = '\r\n' if '\r\n' in roh else '\n'
        _atomar(datei, ''.join(zs[:i]) + ('## Antwort\n' + block_schreiben(text, 'text')).replace('\n', nl))


def html_erkennen(antwort):
    if re.match(r'\s*(?:<!doctype html\b|<html\b)', antwort, re.I):
        return antwort
    kandidaten = [b['text'] for b in bloecke(antwort) if b['kennung'].lower() == 'html']
    return max(kandidaten, key=len) if kandidaten else ''


def html_schreiben(datei, antwort):
    text = html_erkennen(antwort)
    if text:
        ziel = os.path.splitext(datei)[0] + '.html'
        if not pfad_erlaubt(ziel, [os.path.dirname(datei)]):
            raise ValueError('HTML-Pfad nicht erlaubt.')
        with _SPERRE:
            _atomar(ziel, text)
    return 'ja' if text else 'nein'


def _zaunlaenge(zeile):
    m = re.match(r'^ {0,3}([~`])\1*', zeile)
    return (m.group(1), len(m.group().lstrip(' '))) if m else ('', 0)


def bloecke(text):
    """Zaunzustand; Bereiche sind nullbasiert, Ende einschließlich Schlusszeile."""
    zeilen = text.splitlines(keepends=True)
    ergebnis = []
    i = 0
    while i < len(zeilen):
        zeichen, laenge = _zaunlaenge(zeilen[i])
        if laenge < 3:
            i += 1
            continue
        kenn = zeilen[i].lstrip(' ')[laenge:].strip()
        if zeichen == '`' and '`' in kenn:
            i += 1
            continue
        ende = i + 1
        while ende < len(zeilen):
            z, n = _zaunlaenge(zeilen[ende])
            if z == zeichen and n >= laenge and not zeilen[ende].lstrip(' ')[n:].strip():
                break
            ende += 1
        inhalt = ''.join(zeilen[i + 1:ende])
        if inhalt.endswith('\r\n'):
            inhalt = inhalt[:-2]
        elif inhalt.endswith('\n'):
            inhalt = inhalt[:-1]
        ergebnis.append({'zeichen': zeichen, 'laenge': laenge, 'kennung': kenn,
                         'auf': i, 'zu': ende, 'text': inhalt, 'geschlossen': ende < len(zeilen)})
        i = ende + 1
    return ergebnis


def block_schreiben(text, kennung, zeichen='~'):
    if zeichen not in ('~', '`') or '\n' in kennung or '\r' in kennung:
        raise ValueError('Ungültiger Zaun.')
    laenge = max([2] + [n for z, n in map(_zaunlaenge, text.splitlines()) if z == zeichen]) + 1
    zaun = zeichen * laenge
    return f'{zaun}{kennung}\n{text}\n{zaun}\n'


def kennung(titel, vorhanden=()):
    basis = dateiname(titel)
    if basis.startswith('_'):
        raise ValueError('Ein führender Unterstrich ist reserviert.')
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', basis, re.I):
        stamm, punkt, endung = basis.partition('.')
        basis = (stamm + '_' + (punkt + endung if punkt else ''))[:70]
    belegt = {n.casefold() for n in vorhanden}
    wert, n = basis, 2
    while wert.casefold() in belegt:
        zusatz = f' ({n})'
        wert = basis[:70 - len(zusatz)] + zusatz
        n += 1
    return wert


def pfad_erlaubt(pfad, wurzeln):
    def sauber(p):
        p = os.fspath(p)
        return not (p.startswith(('\\\\', '//')) or '\x00' in p or ':' in os.path.splitdrive(p)[1])
    try:
        if not sauber(pfad):
            return False
        ziel = os.path.normcase(os.path.realpath(pfad))
        if not sauber(ziel):
            return False
        for wurzel in wurzeln:
            if sauber(wurzel):
                wurzel = os.path.normcase(os.path.realpath(wurzel))
                if sauber(wurzel) and os.path.commonpath([ziel, wurzel]) == wurzel:
                    return True
    except (ValueError, TypeError, OSError):
        pass
    return False


def _lesen(pfad):
    with open(pfad, encoding='utf-8', newline='') as f:
        return f.read()


def _atomar(pfad, text):
    tmp = pfad + '.werkstatt.tmp'
    if not pfad_erlaubt(tmp, [os.path.dirname(pfad)]):
        raise ValueError('Der temporäre Schreibpfad ist nicht erlaubt.')
    try:
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, pfad)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _name(name):
    if not isinstance(name, str) or _STEUERZEICHEN.search(name):
        raise ValueError('Der Name darf keine Steuerzeichen enthalten.')
    return name_pruefen(name)


def _zeilenkopf(text):
    zeilen = text.splitlines(keepends=True)
    kaesten = bloecke(text)
    innen = {i for b in kaesten for i in range(b['auf'], min(b['zu'] + 1, len(zeilen)))}
    koepfe = [(i, z.rstrip('\r\n')) for i, z in enumerate(zeilen)
              if i not in innen and re.match(r'^#{1,6} ', z)]
    return zeilen, kaesten, koepfe


def _kopf(text):
    zeilen, _, koepfe = _zeilenkopf(text)
    anfang = next((i for i, z in koepfe if z.startswith('# ')), None)
    if anfang is None:
        raise ValueError('Titel fehlt.')
    ende = anfang + 1
    werte = {}
    while ende < len(zeilen) and zeilen[ende].strip():
        k, trenner, v = zeilen[ende].rstrip('\r\n').partition(':')
        if not trenner:
            break
        werte[k] = v.strip()
        ende += 1
    return anfang, ende, werte, stand(''.join(zeilen[anfang:ende]))


class Eintrag:
    def __init__(self, pfad):
        self.pfad = os.fspath(pfad)

    def anlegen(self, titel, quelle, schlagworte, text):
        with _SPERRE:
            if os.path.exists(self.pfad):
                raise Konflikt('Diese Promptdatei gibt es bereits, bitte neu laden.')
            datum = datetime.date.today().strftime('%d.%m.%Y')
            roh = (f'# {titel.strip()}\nQuelle: {quelle}\nSchlagworte: {schlagworte}\n'
                   f'Bevorzugt: Fassung 1\nAktualisiert: {datum}\n\n#### Fassung 1\n'
                   + block_schreiben(text_pruefen(text), 'text'))
            _atomar(self.pfad, roh)
            return self.lesen()

    def lesen(self, text=None):
        text = _lesen(self.pfad) if text is None else text
        zeilen, kaesten, koepfe = _zeilenkopf(text)
        anfang, _, kopf, ks = _kopf(text)
        fassungen = []
        for b in kaesten:
            vorher = next(((i, z) for i, z in reversed(koepfe) if i < b['auf']), None)
            if b['zeichen'] == '~' and b['kennung'] in ('', 'text') and vorher and vorher[1].startswith('#### '):
                name = vorher[1][5:].strip()
                inhalt = b['text'].replace('\r\n', '\n')
                fassungen.append(dict(b, name=name, text=inhalt, stand=stand(inhalt), kopf=vorher[0]))
        namen = [f['name'] for f in fassungen]
        mehrdeutig = (any(not b['geschlossen'] for b in kaesten) or len(set(namen)) != len(namen)
                      or not fassungen)
        bevorzugt = kopf.get('Bevorzugt')
        if bevorzugt not in namen:
            bevorzugt = namen[0] if namen else ''
        return {'titel': zeilen[anfang][2:].strip(), 'quelle': kopf.get('Quelle', ''),
                'schlagworte': kopf.get('Schlagworte', ''), 'bevorzugt': bevorzugt,
                'aktualisiert': kopf.get('Aktualisiert', ''), 'kopf_stand': ks, 'fassungen': fassungen,
                'fehler': 'nicht eindeutig lesbar' if mehrdeutig else '', 'bearbeitbar': not mehrdeutig}

    def _frisch(self):
        text = _lesen(self.pfad)
        d = self.lesen(text)
        if not d['bearbeitbar']:
            raise ValueError('Die Datei ist nicht eindeutig lesbar. Bitte im Editor prüfen.')
        return text, d

    def _schreiben(self, text):
        zeilen = text.splitlines(keepends=True)
        nl = '\r\n' if '\r\n' in text else '\n'
        anfang, ende, _, _ = _kopf(text)
        datum = datetime.date.today().strftime('%d.%m.%Y')
        ziel = next((i for i in range(anfang + 1, ende) if zeilen[i].startswith('Aktualisiert:')), ende)
        if ziel == ende:
            zeilen[ziel:ziel] = [f'Aktualisiert: {datum}{nl}']
        else:
            zeilen[ziel] = f'Aktualisiert: {datum}{nl}'
        _atomar(self.pfad, ''.join(zeilen))
        return self.lesen()

    def kopf(self, titel, quelle, schlagworte, kopf_stand):
        werte = {'Quelle': quelle, 'Schlagworte': schlagworte}
        for wert in [titel, quelle, schlagworte]:
            if not isinstance(wert, str) or _STEUERZEICHEN.search(wert):
                raise ValueError('Kopfzeilen dürfen keine Steuerzeichen enthalten.')
        if not titel.strip():
            raise ValueError('Bitte einen Titel angeben.')
        with _SPERRE:
            text, d = self._frisch()
            if d['kopf_stand'] != kopf_stand:
                raise Konflikt('Der Kopf wurde inzwischen geändert, bitte neu laden.')
            zeilen = text.splitlines(keepends=True)
            nl = '\r\n' if '\r\n' in text else '\n'
            a, e, _, _ = _kopf(text)
            zeilen[a] = '# ' + titel.strip() + nl
            for k, v in werte.items():
                ziel = next((i for i in range(a + 1, e) if zeilen[i].startswith(k + ':')), None)
                if ziel is None:
                    zeilen[e:e] = [f'{k}: {v}{nl}']
                    e += 1
                else:
                    zeilen[ziel] = f'{k}: {v}{nl}'
            return self._schreiben(''.join(zeilen))

    def fassung_speichern(self, name, text, alter_stand):
        text = text_pruefen(text)
        with _SPERRE:
            roh, d = self._frisch()
            f = next((f for f in d['fassungen'] if f['name'] == name), None)
            if not f or f['stand'] != alter_stand:
                raise Konflikt('Die Fassung wurde inzwischen geändert, bitte neu laden.')
            nl = '\r\n' if '\r\n' in roh else '\n'
            zeilen = roh.splitlines(keepends=True)
            zeilen[f['auf']:f['zu'] + 1] = [block_schreiben(text, 'text').replace('\n', nl)]
            return self._schreiben(''.join(zeilen))

    def fassung_neu(self, name, text):
        name, text = _name(name), text_pruefen(text)
        with _SPERRE:
            roh, d = self._frisch()
            if any(f['name'] == name for f in d['fassungen']):
                raise ValueError('Diesen Fassungsnamen gibt es schon.')
            nl = '\r\n' if '\r\n' in roh else '\n'
            return self._schreiben(roh + ('' if roh.endswith('\n') else nl) + nl + f'#### {name}{nl}'
                                   + block_schreiben(text, 'text').replace('\n', nl))

    def bevorzugt(self, name, kopf_stand):
        with _SPERRE:
            roh, d = self._frisch()
            if d['kopf_stand'] != kopf_stand:
                raise Konflikt('Der Kopf wurde inzwischen geändert, bitte neu laden.')
            if name not in [f['name'] for f in d['fassungen']]:
                raise ValueError('Diese Fassung gibt es nicht.')
            zeilen = roh.splitlines(keepends=True)
            a, e, _, _ = _kopf(roh)
            nl = '\r\n' if '\r\n' in roh else '\n'
            ziel = next((i for i in range(a + 1, e) if zeilen[i].startswith('Bevorzugt:')), e)
            zeilen[ziel:ziel + (ziel < e)] = [f'Bevorzugt: {name}{nl}']
            return self._schreiben(''.join(zeilen))


def sammlung_kaesten(pfad):
    zeilen, kaesten, koepfe = _zeilenkopf(_lesen(pfad))
    werkstatt, titel, nummern, ergebnis = False, '', {}, []
    blocks = {b['auf']: b for b in kaesten}
    headings = dict(koepfe)
    for i in range(len(zeilen)):
        z = headings.get(i, '')
        if z.startswith(('## ', '### ')):
            werkstatt = z == ABSCHNITT
        if z.startswith('## '):
            titel = ''
        if z.startswith(('### ', '#### ')):
            titel = z.split(' ', 1)[1].strip()
        b = blocks.get(i)
        if not werkstatt and titel and b and b['zeichen'] == '~' and b['kennung'] in ('', 'text'):
            nummern[titel] = nummern.get(titel, 0) + 1
            n = nummern[titel]
            text = b['text'].replace('\r\n', '\n')
            ergebnis.append({'id': f'sammlung:{titel}#{n}', 'ueberschrift': titel, 'nummer': n,
                             'titel': titel + (f' (Kasten {n})' if n > 1 else ''), 'herkunft': 'sammlung',
                             'quelle': '', 'schlagworte': '', 'aktualisiert': '', 'bearbeitbar': False,
                             'fehler': '' if b['geschlossen'] else 'nicht eindeutig lesbar',
                             'fassungen': [{'name': 'Sammlung', 'text': text, 'stand': stand(text)}]})
    return ergebnis


class Index:
    def __init__(self, cfg, sammlung):
        self.cfg, self.sammlung = cfg, sammlung
        self.ordner = cfg['ordner']
        os.makedirs(self.ordner, exist_ok=True)
        self._cache = {}
        self.auswertung = None
        self.watch = ''

    def verbinden(self, auswertung):
        self.auswertung = auswertung
        self.watch = auswertung.w['arbeitsordner']

    def beleg_pfad(self, eid, datei):
        if (not isinstance(datei, str) or not datei or _STEUERZEICHEN.search(datei)
                or re.search(r'[/\\:]', datei) or not datei.lower().endswith('.md')):
            raise ValueError('Bitte einen reinen Belegdateinamen angeben.')
        pfad = os.path.join(self._ordner(eid), 'tests', datei)
        if not pfad_erlaubt(pfad, [self.ordner]):
            raise ValueError('Belegpfad nicht erlaubt.')
        return pfad

    def datei_lesen(self, pfad):
        wurzeln = self.cfg['dateiwurzeln'] + ([self.watch] if self.watch else [])
        if not pfad_erlaubt(pfad, wurzeln) or not os.path.isfile(pfad):
            raise ValueError('Die Datei fehlt oder liegt außerhalb der erlaubten Ordner.')
        # Zugangsdaten gehören nie in einen Prompt (AGENTS.md): gesperrte Ordner aus der Konfiguration und .env-Dateien.
        gesperrt = self.cfg.get('gesperrt') or []
        if (gesperrt and pfad_erlaubt(pfad, gesperrt)) or os.path.basename(pfad).lower().endswith('.env'):
            raise ValueError('Diese Datei enthält Zugangsdaten oder liegt in einem gesperrten Ordner; '
                             'sie geht nicht in einen Prompt.')
        grenze = self.cfg.get('feld_max_zeichen', 400000)
        with open(pfad, encoding='utf-8', errors='replace') as f:
            text = f.read(grenze + 1)
        if len(text) > grenze:
            raise ValueError(f'Die Datei überschreitet {grenze} Zeichen je Feld.')
        return {'art': 'datei', 'pfad': pfad, 'wert': text, 'sha': sha(text), 'zeichen': len(text)}

    def transkripte(self):
        from werkstatt.auswertung import transkripte_auflisten
        ergebnis = []
        for t in transkripte_auflisten(self.watch):
            pfad = os.path.join(t['transkript'], 'transcript-timestamps.txt')
            try:
                feld = self._transkript(pfad)
                feld.pop('wert')
                ergebnis.append(dict(t, **feld))
            except (OSError, ValueError):
                continue
        return ergebnis

    def _transkript(self, datei):
        if (not self.watch or not pfad_erlaubt(datei, [self.watch])
                or os.path.basename(datei) != 'transcript-timestamps.txt'):
            raise ValueError('Dieses Transkript liegt nicht im watch-Arbeitsordner.')
        with open(datei, encoding='utf-8', errors='replace') as f:
            text = f.read()
        return {'art': 'transkript', 'datei': datei, 'sha': sha(text), 'zeichen': len(text), 'wert': text}

    def transkripte_lesen(self, eingaben):
        texte = {}
        for name, feld in eingaben['felder'].items():
            if feld.get('art') == 'transkript':
                try:
                    frisch = self._transkript(feld['datei'])
                    if frisch['sha'] != feld['sha']:
                        raise ValueError('Prüfsumme abweichend')
                except (OSError, ValueError, KeyError) as ex:
                    raise PromptFehler('transkript_geaendert', f'Transkript für „{name}“ fehlt oder wurde geändert.') from ex
                texte[name] = frisch['wert']
        return texte

    def _eingaben(self, daten, fassungen):
        eingaben = {'felder': {}, 'leer': []}
        texte = {}
        namen = list(dict.fromkeys(n for f in fassungen for n in felder_erkennen(f['text'])))
        for name in namen:
            feld = dict(daten.get('eingaben', {}).get('felder', {}).get(name, {'art': 'text', 'wert': ''}))
            art = feld.get('art')
            if art == 'datei':
                feld = self.datei_lesen(feld.get('pfad', ''))
            elif art == 'transkript':
                feld = self._transkript(feld.get('datei', ''))
                texte[name] = feld.pop('wert')
            elif art == 'woertlich':
                feld = {'art': 'woertlich'}
            elif art == 'text' and isinstance(feld.get('wert', ''), str):
                if len(feld.get('wert', '')) > self.cfg.get('feld_max_zeichen', 400000):
                    raise ValueError(f'„{name}“ ist zu lang.')
                feld = {k: feld[k] for k in ('art', 'wert', 'name') if k in feld}
            else:
                raise ValueError('Unbekannte Feldart.')
            eingaben['felder'][name] = feld
            if art != 'woertlich' and not (texte.get(name) if art == 'transkript' else feld.get('wert')):
                eingaben['leer'].append(name)
        if daten.get('rahmen'):
            rahmen = self.auswertung.sammlung.lesen().get('rahmen')
            if not rahmen:
                raise ValueError('Der Rahmen der Zusammenfassung fehlt.')
            eingaben['rahmen'] = {'art': 'text', 'wert': rahmen['text']}
        return eingaben, texte

    def vorschau(self, daten):
        d = self.lesen(daten.get('id', ''))
        if d.get('fehler'):
            raise ValueError('Der Eintrag ist nicht eindeutig lesbar.')
        fassungen = [f for f in d['fassungen'] if f['name'] in daten.get('fassungen', [])]
        profile = [p for p in self.auswertung.profile if p['id'] in daten.get('auswerter', [])]
        if not fassungen or not profile:
            raise ValueError('Bitte mindestens eine Fassung und einen Auswerter anhaken.')
        eingaben, texte = self._eingaben(daten, fassungen)
        ergebnis = []
        for f in fassungen:
            text, gs = auftrag_bauen(f['text'], eingaben, texte)
            kurz = {n: f'[Transkript: {len(t)} Zeichen]' for n, t in texte.items()}
            anzeigen, _ = auftrag_bauen(f['text'], eingaben, kurz)
            auswerter = []
            for p in profile:
                anbieter = self.auswertung.anbieter[p['anbieter']]
                ok, grund = anbieter.verfuegbar(p)
                if not ok:
                    raise ValueError(grund)
                kontext, quelle, modell = anbieter.kontext_geladen(p)
                schaetzung, reserve = kontext_pruefen(text, kontext)
                hinweis = ('ohne Werkzeuge' if p['anbieter'] == 'claude' else
                           'Sandbox nur lesend, kann Dateien lesen und Befehle ausführen, liest seine globale AGENTS.md mit'
                           if p['anbieter'] == 'codex' else '')
                auswerter.append(dict(p, kontext=kontext, kontext_quelle=quelle, modell_tatsaechlich=modell,
                                      verarbeitung='Cloud (' + anbieter.cloud + ')' if anbieter.cloud else 'lokal',
                                      geschaetzt=schaetzung, reserve=reserve, hinweis=hinweis))
            ergebnis.append(dict(f, auftrag=anzeigen, gesendet_stand=gs, auswerter=auswerter))
        return {'fassungen': ergebnis, 'eingaben': eingaben, 'leer': len(eingaben['leer'])}

    def _testordner(self, eid):
        d = self.lesen(eid)
        if d['herkunft'] == 'sammlung' and not d.get('schatten'):
            basis = self._pfad('_Sammlung')
            os.makedirs(basis, exist_ok=True)
            name = kennung(d['ueberschrift'] + (f" #{d['nummer']}" if d['nummer'] > 1 else ''), os.listdir(basis))
            os.mkdir(self._pfad('_Sammlung', name))
            d['schatten'] = name
        if d['herkunft'] == 'sammlung':
            self._meta_schreiben(d['schatten'], {'ueberschrift': d['ueberschrift'], 'nummer': d['nummer'],
                'stand': d['fassungen'][0]['stand'], 'kaesten_vorher': sum(s['ueberschrift'] == d['ueberschrift']
                  for s in sammlung_kaesten(self.sammlung))})
        ziel = os.path.join(self._ordner(eid), 'tests')
        if not pfad_erlaubt(ziel, [self.ordner]):
            raise ValueError('Belegordner nicht erlaubt.')
        return ziel

    def testen(self, daten):
        auftraege = []
        with _SPERRE:
            v = self.vorschau(daten)
            staende = daten.get('gesendet_stand', {})
            if any(staende.get(f['name']) != f['gesendet_stand'] for f in v['fassungen']):
                raise Konflikt('Der Inhalt hat sich seit der Vorschau geändert.')
            d = self.lesen(daten['id'])
            ordner = self._testordner(d['id'])
            neu = []
            for f in v['fassungen']:
                for p in f['auswerter']:
                    kopf = dict(prompt=d['titel'], eintrag=d['id'], herkunft=d['herkunft'], fassung=f['name'],
                        fassung_stand=f['stand'], rahmen='ja' if 'rahmen' in v['eingaben'] else 'nein',
                        gesendet_stand=f['gesendet_stand'], auswerter=p['name'], anbieter=p['anbieter'],
                        modell=p['modell'], kontext=p['kontext'], kontext_quelle=p['kontext_quelle'],
                        verarbeitung=p['verarbeitung'], zustand='wartet', meldung='',
                        erstellt=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), hinweis='',
                        urteil='offen', notiz='', status='Entwurf, automatisch erstellt, nicht geprüft')
                    if p.get('stufe'):
                        kopf['denkstufe'] = p['stufe']
                    if p.get('modell_tatsaechlich') and p['modell_tatsaechlich'] != p['modell']:
                        kopf['modell_tatsaechlich'] = p['modell_tatsaechlich']
                    datei = beleg_anlegen(ordner, kopf, f['text'], v['eingaben'])
                    auftrag = self.auftrag_aus_beleg(d['id'], os.path.basename(datei))
                    auftraege.append(auftrag)
                    neu.append(auftrag['id'])
        # Nie die Dateisperre halten, während die Warteschlangensperre erworben wird.
        for auftrag in auftraege:
            self.auswertung.einreihen(auftrag)
        return {'neu': len(neu), 'auftraege': neu}

    def auftrag_aus_beleg(self, eid, datei):
        import secrets
        import time
        pfad = self.beleg_pfad(eid, datei)
        b = beleg_lesen(pfad)
        p = next((p for p in self.auswertung.profile if p['name'] == b['auswerter']
                  and p['anbieter'] == b['anbieter'] and p['modell'] == b['modell']
                  and p.get('stufe') == b.get('denkstufe')), None)
        p = p or {'id': '', 'name': b['auswerter'], 'anbieter': b['anbieter'], 'modell': b['modell'],
                  'stufe': b.get('denkstufe')}
        return {'id': secrets.token_hex(4), 'art': 'prompt', 'titel': b['prompt'], 'auswerter': dict(p),
                'prompt': {'eintrag': eid, 'herkunft': b['herkunft'], 'titel': b['prompt'],
                           'fassung': b['fassung'], 'stand': b['fassung_stand'], 'beleg': datei[:-3],
                           'gesendet_stand': b['gesendet_stand']}, 'datei': pfad,
                'zustand': 'wartet', 'meldung': '', 'erstellt': time.time()}

    def datei_inhalt(self, eid, was, datei):
        pfad = self.beleg_pfad(eid, datei)
        b = beleg_lesen(pfad)
        if was == 'gesendet':
            text, _ = auftrag_bauen(b['fassung_text'], b['eingaben'], self.transkripte_lesen(b['eingaben']))
            return {'text': text}
        if was != 'beleg':
            raise ValueError('Unbekannte Dateiart.')
        hinweise = {}
        for name, feld in b['eingaben']['felder'].items():
            if feld.get('art') in ('datei', 'transkript'):
                try:
                    frisch = (self.datei_lesen(feld['pfad']) if feld['art'] == 'datei'
                              else self._transkript(feld['datei']))
                    if frisch['sha'] != feld['sha']:
                        hinweise[name] = 'Datei seit dem Test geändert.'
                except (OSError, ValueError):
                    hinweise[name] = 'Datei fehlt oder ist nicht lesbar.'
        return dict(b, text=_lesen(pfad), hinweise=hinweise)

    def _pfad(self, *teile):
        pfad = os.path.join(self.ordner, *teile)
        if not pfad_erlaubt(pfad, [self.ordner]):
            raise ValueError('Dieser Pfad ist nicht erlaubt.')
        return pfad

    def _gecacht(self, pfad, lesen):
        s = os.stat(pfad)
        schluessel = (s.st_mtime_ns, s.st_size)
        alt = self._cache.get(pfad)
        if not alt or alt[0] != schluessel:
            alt = (schluessel, lesen())
            self._cache[pfad] = alt
        # Aufrufer ergänzen Anzeigeinformationen, nie den zwischengespeicherten Wert.
        import copy
        return copy.deepcopy(alt[1])

    def _belege(self, ordner):
        tests = self._pfad(ordner, 'tests')
        ergebnis = []
        if os.path.isdir(tests):
            for name in sorted(os.listdir(tests), reverse=True):
                if not name.lower().endswith('.md'):
                    continue
                try:
                    pfad = self._pfad(ordner, 'tests', name)
                    def lesen():
                        _, _, kopf, ks = _belegkopf(_lesen(pfad))
                        try:
                            beleg_lesen(pfad)
                        except (ValueError, KeyError, TypeError):
                            kopf['fehler'] = 'Beleg beschädigt'
                        return dict(kopf, kopf_stand=ks)
                    ergebnis.append(dict(self._gecacht(pfad, lesen), datei=name))
                except (OSError, ValueError, UnicodeError):
                    ergebnis.append({'datei': name, 'fehler': 'Beleg beschädigt'})
        return ergebnis

    def alle(self):
        with _SPERRE:
            return self._alle()

    def _alle(self):
        eintraege, fehler = [], []
        for name in os.listdir(self.ordner):
            if name.startswith('_'):
                continue
            try:
                pfad = self._pfad(name, 'prompt.md')
                if not os.path.exists(pfad):
                    continue
                try:
                    d = self._gecacht(pfad, lambda: Eintrag(pfad).lesen())
                except (OSError, ValueError, UnicodeError):
                    d = {'titel': name, 'fehler': 'nicht lesbar', 'bearbeitbar': False, 'fassungen': []}
                d.update(id=name, herkunft='ordner', tests=self._belege(name))
                eintraege.append(d)
            except ValueError:
                fehler.append(f'„{name}“: Pfad nicht erlaubt.')
        def datum(d):
            try:
                return datetime.datetime.strptime(d.get('aktualisiert', ''), '%d.%m.%Y')
            except ValueError:
                return datetime.datetime.min
        eintraege.sort(key=datum, reverse=True)
        try:
            if not pfad_erlaubt(self.sammlung, self.cfg['dateiwurzeln']):
                raise ValueError('Sammlungspfad nicht erlaubt.')
            sammlung = self._gecacht(self.sammlung, lambda: sammlung_kaesten(self.sammlung))
        except (OSError, ValueError, UnicodeError):
            sammlung = []
            fehler.append('Promptsammlung nicht lesbar.')
        schatten = self._schatten(sammlung)
        eintraege += sammlung + schatten
        for d in eintraege:
            d.setdefault('tests', [])
            staende = {f['stand'] for f in d['fassungen']}
            for t in d['tests']:
                t['geaendert'] = t.get('fassung_stand') not in staende
            d['getestet'] = bool(d['tests'])
        return {'eintraege': eintraege, 'fehler': fehler,
                'filter': {'herkunft': ['ordner', 'sammlung'], 'status': ['getestet', 'ungetestet']}}

    def _schatten(self, sammlung):
        basis = self._pfad('_Sammlung')
        if not os.path.isdir(basis):
            return []
        zuordnungen = []
        for name in os.listdir(basis):
            try:
                pfad = self._pfad('_Sammlung', name, 'eintrag.json')
                meta = json.loads(_lesen(pfad))
                kandidaten = [s for s in sammlung if s['ueberschrift'] == meta['ueberschrift']]
                treffer = [s for s in kandidaten if s['fassungen'][0]['stand'] == meta['stand']]
                ziel = treffer[0] if len(treffer) == 1 else None
                if not treffer and len(kandidaten) == 1 and meta.get('kaesten_vorher') == 1:
                    ziel = kandidaten[0]
                zuordnungen.append((name, meta, kandidaten, ziel))
            except (OSError, ValueError, KeyError, TypeError):
                zuordnungen.append((name, {}, [], None))
        ergebnis = []
        for name, meta, kandidaten, ziel in zuordnungen:
            if ziel and sum(z is ziel for _, _, _, z in zuordnungen) > 1:
                ziel = None
            ordner = os.path.join('_Sammlung', name)
            tests = self._belege(ordner)
            if ziel:
                ziel['tests'] = tests
                ziel['schatten'] = name
                ziel['hinweis'] = ('seit dem Test geändert' if ziel['fassungen'][0]['stand'] != meta['stand'] else '')
                if meta.get('nummer') != ziel['nummer']:
                    meta['nummer'] = ziel['nummer']
                    self._meta_schreiben(name, meta)
            else:
                ergebnis.append({'id': 'schatten:' + name, 'titel': meta.get('ueberschrift', name),
                                 'herkunft': 'sammlung', 'fassungen': [], 'tests': tests,
                                 'bearbeitbar': False, 'kandidaten': [s['id'] for s in kandidaten],
                                 'fehler': ('Zuordnung ungeklärt' if kandidaten
                                            else 'Sammlungseintrag nicht mehr gefunden')})
        return ergebnis

    def _meta_schreiben(self, name, meta):
        meta['aktualisiert'] = datetime.datetime.now().isoformat(timespec='seconds')
        _atomar(self._pfad('_Sammlung', name, 'eintrag.json'), json.dumps(meta, ensure_ascii=False, indent=2) + '\n')

    def zuordnen(self, schatten, ziel):
        with _SPERRE:
            d = self.lesen(ziel)
            if d['herkunft'] != 'sammlung' or not d['fassungen'] or d.get('fehler'):
                raise ValueError('Bitte einen lesbaren Sammlungskasten wählen.')
            if not schatten.startswith('schatten:'):
                raise ValueError('Schattenordner fehlt.')
            name = schatten[len('schatten:'):]
            self._ordner(schatten)
            meta = json.loads(_lesen(self._pfad('_Sammlung', name, 'eintrag.json')))
            if meta['ueberschrift'] != d['ueberschrift']:
                raise ValueError('Die Überschrift stimmt nicht überein.')
            meta.update(nummer=d['nummer'], stand=d['fassungen'][0]['stand'],
                        kaesten_vorher=sum(s['ueberschrift'] == d['ueberschrift']
                                          for s in sammlung_kaesten(self.sammlung)))
            self._meta_schreiben(name, meta)
            return self.lesen(ziel)

    def lesen(self, eid):
        d = next((d for d in self.alle()['eintraege'] if d['id'] == eid), None)
        if not d:
            raise ValueError('Diesen Eintrag gibt es nicht (mehr).')
        return d

    def _ordner(self, eid):
        if eid.startswith('schatten:'):
            name = eid[len('schatten:'):]
            teile = ('_Sammlung', name)
        elif eid.startswith('sammlung:'):
            d = self.lesen(eid)
            if not d.get('schatten'):
                raise ValueError('Für diesen Sammlungskasten gibt es noch keinen Belegordner.')
            name = d['schatten']
            teile = ('_Sammlung', name)
        else:
            name = eid
            teile = (name,)
        if not name or name in ('.', '..') or re.search(r'[/\\:\x00]', name):
            raise ValueError('Ungültige Kennung.')
        return self._pfad(*teile)

    def neu(self, titel, quelle, schlagworte, text):
        text = text_pruefen(text)
        for wert in (titel, quelle, schlagworte):
            if not isinstance(wert, str) or _STEUERZEICHEN.search(wert):
                raise ValueError('Ungültige Kopfzeile.')
        if not titel.strip():
            raise ValueError('Bitte einen Titel angeben.')
        with _SPERRE:
            eid = kennung(titel, os.listdir(self.ordner))
            ordner = self._pfad(eid)
            os.mkdir(ordner)
            pfad = self._pfad(eid, 'prompt.md')
            Eintrag(pfad).anlegen(titel, quelle, schlagworte, text)
            return self.lesen(eid)

    def oeffnen(self, eid, was, datei=''):
        if was == 'sammlung':
            self.lesen(eid)
            pfad = self.sammlung
            if not pfad_erlaubt(pfad, self.cfg['dateiwurzeln']) or not os.path.isfile(pfad):
                raise ValueError('Die Sammlung ist nicht erlaubt oder nicht lesbar.')
        else:
            self.lesen(eid)
            ordner = self._ordner(eid)
            if was == 'ordner':
                pfad = ordner
                if not os.path.isdir(pfad):
                    raise ValueError('Der Ordner fehlt.')
            else:
                if was not in ('beleg', 'schaerfen', 'html') or not isinstance(datei, str):
                    raise ValueError('Unbekannte Dateiart.')
                if not datei or re.search(r'[/\\:\x00]', datei) or os.path.splitext(datei)[1].lower() != (
                        '.html' if was == 'html' else '.md'):
                    raise ValueError('Bitte einen reinen Dateinamen mit erlaubter Endung angeben.')
                pfad = os.path.join(ordner, 'schaerfen' if was == 'schaerfen' else 'tests', datei)
                if not pfad_erlaubt(pfad, [self.ordner]) or not os.path.isfile(pfad):
                    raise ValueError('Die Datei fehlt oder ist nicht erlaubt.')
        os.startfile(pfad)
        return {'ok': True}

    def aktion(self, daten):
        aktion, eid = daten.get('aktion'), daten.get('id', '')
        if aktion in ('vorschau', 'testen'):
            return getattr(self, aktion)(daten)
        if aktion == 'datei_lesen':
            return self.datei_lesen(daten.get('pfad', ''))
        if aktion == 'datei_waehlen':
            from werkstatt.quellen import textdatei_waehlen
            pfade = textdatei_waehlen()
            return self.datei_lesen(pfade[0]) if pfade else {'abgebrochen': True}
        if aktion == 'urteil':
            if daten.get('urteil') not in ('offen', 'gut', 'schwach') or not isinstance(daten.get('notiz', ''), str):
                raise ValueError('Ungültiges Urteil oder Notiz.')
            ks = _kopf_setzen(self.beleg_pfad(eid, daten.get('datei')), {
                'urteil': daten['urteil'], 'notiz': daten.get('notiz', '')}, daten.get('kopf_stand', ''))
            return {'kopf_stand': ks}
        if aktion == 'wiederholen_beleg':
            a = self.auftrag_aus_beleg(eid, daten.get('datei'))
            with self.auswertung._lock:
                if any(os.path.normcase(x.get('datei') or '') == os.path.normcase(a['datei'])
                       for x in self.auswertung.liste if x.get('art') == 'prompt'):
                    raise Konflikt('Dieser Beleg steht bereits in der Warteschlange.')
                beleg_zustand(a['datei'], 'wartet')
                self.auswertung.einreihen(a)
            return {'ok': True}
        if aktion == 'neu':
            return self.neu(daten.get('titel', ''), daten.get('quelle', ''),
                            daten.get('schlagworte', ''), daten.get('text', ''))
        if aktion == 'oeffnen':
            return self.oeffnen(eid, daten.get('was'), daten.get('datei', ''))
        if aktion == 'zuordnen':
            return self.zuordnen(eid, daten.get('ziel', ''))
        if self.lesen(eid)['herkunft'] != 'ordner':
            raise ValueError('Die Sammlung bleibt schreibgeschützt.')
        pfad = os.path.join(self._ordner(eid), 'prompt.md')
        if not pfad_erlaubt(pfad, [self.ordner]):
            raise ValueError('Dieser Pfad ist nicht erlaubt.')
        e = Eintrag(pfad)
        if aktion == 'kopf':
            e.kopf(daten.get('titel', ''), daten.get('quelle', ''), daten.get('schlagworte', ''),
                   daten.get('kopf_stand'))
        elif aktion == 'fassung_speichern':
            e.fassung_speichern(daten.get('name'), daten.get('text', ''), daten.get('stand'))
        elif aktion == 'fassung_neu':
            e.fassung_neu(daten.get('name'), daten.get('text', ''))
        elif aktion == 'bevorzugt':
            e.bevorzugt(daten.get('name'), daten.get('kopf_stand'))
        else:
            raise ValueError('Unbekannte Aktion.')
        return self.lesen(eid)
