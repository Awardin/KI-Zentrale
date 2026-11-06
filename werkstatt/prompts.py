"""Promptdateien und schreibgeschützter Blick auf die gemeinsame Sammlung."""
import datetime
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
                        kopf = {}
                        with open(pfad, encoding='utf-8') as f:
                            if f.readline().strip() != '---':
                                raise ValueError('Belegkopf fehlt.')
                            for zeile in f:
                                if zeile.strip() == '---':
                                    return kopf
                                k, trenner, v = zeile.partition(':')
                                if trenner:
                                    v = v.strip()
                                    try:
                                        kopf[k] = json.loads(v)
                                    except ValueError:
                                        kopf[k] = v
                        raise ValueError('Belegkopf ist offen.')
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
