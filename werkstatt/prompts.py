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


def beleg_lesen(datei, schaerfen=False):
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
    if not isinstance(eingaben, dict) or (not schaerfen and not isinstance(eingaben.get('felder'), dict)):
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
        teil = dateiname(kopf.get('aktion', kopf['fassung']))
        if isinstance(kopf.get('zielmodell'), str) and kopf['zielmodell'].strip():
            # Schärfen-Belege: Das Ziel gehört in den Namen, sonst heißen die Belege mehrerer Ziele nur nach dem Schreibmodell.
            teil += ' für ' + dateiname(kopf['zielmodell'], 40)
        basis = (datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S') + ' – '
                 + teil + ' – ' + dateiname(kopf['auswerter']))
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


AKTIONEN = ('Schärfen', 'Erst klären', 'Kürzen', 'Rückfragen')
_RUECKFRAGEN_GRENZE = 'Rückfragen gibt es nur für eine gespeicherte Fassung, ein Ziel und ein Schreibmodell.'
TYPEN = ('auto', 'standard', 'wissen', 'recherche', 'schreiben', 'planung', 'code',
         'agent', 'automatisierung', 'bild', 'video')
TEXT_ENDUNGEN = {'.txt', '.md', '.markdown', '.json', '.csv', '.tsv', '.yaml', '.yml',
                 '.log', '.html', '.htm', '.css', '.js', '.py', '.xml', '.rst', '.toml'}


def profile_lesen(cfg):
    """Die einzige Regelquelle frisch lesen; Fehler enthalten keine Dateiinhalte."""
    try:
        roh = _lesen(cfg.get('profile', '')).lstrip('\ufeff')
        d = json.loads(roh)
        if not isinstance(d, dict) or type(d.get('schema')) is not int or d['schema'] != 1:
            raise ValueError
        for feld, ids in (('typen', set(TYPEN)),
                          ('zielprofile', {'qwen27', 'flash_next', 'claude', 'codex'})):
            liste = d.get(feld)
            if not isinstance(liste, list) or any(not isinstance(p, dict) for p in liste):
                raise ValueError
            if len(liste) != len(ids) or {p.get('id') for p in liste} != ids:
                raise ValueError
            for p in liste:
                pflicht = ('name', 'regeln', 'untertitel') if feld == 'typen' else ('name', 'regeln', 'anbieter')
                if any(not isinstance(p.get(k), str) or not p[k].strip() for k in pflicht):
                    raise ValueError
                if feld == 'zielprofile':
                    erwartet = {'qwen27': 'lokal', 'flash_next': 'lokal', 'claude': 'claude', 'codex': 'codex'}
                    erlaubt = {'qwen27': ['qwen27-unsloth', 'qwen27-iq3s'], 'flash_next': ['flash-next-strata']}
                    if p['anbieter'] != erwartet[p['id']]:
                        raise ValueError
                    if p['anbieter'] == 'lokal' and p.get('eintraege') != erlaubt[p['id']]:
                        raise ValueError
                    if p['anbieter'] != 'lokal' and p.get('eintraege') != []:
                        raise ValueError
        for feld, ids in (('modi', ('prompt', 'vorlage')), ('generatoren', ('bild', 'video'))):
            if not isinstance(d.get(feld), dict) or set(d[feld]) != set(ids):
                raise ValueError
            for k in ids:
                p = d[feld][k]
                if not isinstance(p, dict) or any(not isinstance(p.get(n), str) or not p[n].strip()
                                                  for n in ('name', 'regeln')):
                    raise ValueError
        return dict(d, stand=sha(roh))
    except (OSError, ValueError, TypeError, UnicodeError):
        raise PromptFehler('profile_fehlen',
                           'Die Prompt-Regeln fehlen oder sind ungültig. Bitte die konfigurierte Regeldatei prüfen.') from None


def skill_lesen(cfg):
    pfad = cfg.get('skill', '')
    try:
        text = _lesen(pfad).lstrip('\ufeff')
        zeilen = text.splitlines(keepends=True)
        if zeilen and zeilen[0].strip() == '---':
            ende = next((i for i in range(1, len(zeilen)) if zeilen[i].strip() == '---'), None)
            if ende is not None:
                text = ''.join(zeilen[ende + 1:])
        if not text.strip():
            raise ValueError('leer')
    except (OSError, ValueError, TypeError, UnicodeError) as ex:
        raise PromptFehler('skill_fehlt', 'Der Skill zum Schärfen fehlt oder ist leer. Bitte den konfigurierten Pfad prüfen.') from ex
    return {'wert': text, 'pfad': pfad, 'stand': stand(text)}


def schaerfen_bauen(fassung, eingaben):
    """Nur gespeicherte Werte verwenden, nie Skill oder Quellmaterial nachladen."""
    if eingaben.get('bau_version') == 2:
        return _schaerfen_bauen_v2(fassung, eingaben)
    if eingaben.get('bau_version', 1) != 1:
        raise ValueError('Unbekannte Auftragsversion.')
    ziel = eingaben['zielmodell']
    aktion = eingaben['aktion']
    if aktion == 'Rückfragen':
        raise ValueError(_RUECKFRAGEN_GRENZE)
    if aktion not in AKTIONEN:
        raise ValueError('Unbekannte Schärfen-Aktion.')
    hinweis = ('ohne Werkzeuge, Systemprompt „Du bist ein sorgfältiger Assistent.“'
               if ziel['anbieter'] == 'claude' else 'Sandbox nur lesend mit Werkzeugen'
               if ziel['anbieter'] == 'codex' else 'ohne Werkzeuge und ohne Projektgedächtnis'
               if ziel['verarbeitung'] == 'lokal' else 'ohne Werkzeuge')
    erwartet = ('nur die Rückfragen als nummerierte Liste, keine neue Fassung, kein Kasten.'
                if aktion == 'Erst klären' else
                'zuerst die neue Fassung in genau einem Kasten (Zeile ~~~text davor, Zeile ~~~ danach, '
                'keine weiteren Kästen mit ~~~), danach die wichtigsten Änderungen als Stichpunkte. '
                'Platzhalter in eckigen Klammern zeichengetreu erhalten. Den Auftrag nicht ausführen.')
    text = (eingaben['skill']['wert'] + '\n\n---\n'
            + f'Auftrag der Werkstatt: {aktion}\n'
            + f"Zielmodell: {ziel['name']} ({ziel['verarbeitung']}, Kontextfenster "
            + (f"{ziel['kontext']} Token" if ziel.get('kontext') else 'unbekannt')
            + f', frischer Chat; {hinweis}).\n'
            + f"Hinweise von Sascha: {eingaben['hinweise'] or 'keine'}\n"
            + f'Erwartete Antwort bei {aktion}: {erwartet}\n'
            + f'Fassung „{fassung["name"]}“:\n' + block_schreiben(fassung['text'], 'text'))
    material = eingaben.get('material')
    if material:
        block = block_schreiben(material['wert'], 'text')
        n = _zaunlaenge(block.splitlines()[0])[1]
        text += (f"\nMaterial, Antwort des Zielmodells vom {material.get('erstellt', 'unbekannt')} "
                 f'auf diese Fassung (Kasten mit {n} Tilden):\n' + block)
    return text, sha(text)


def _schaerfen_bauen_v2(fassung, e):
    if e['aktion'] not in AKTIONEN:
        raise ValueError('Unbekannte Schärfen-Aktion.')
    z = e['zielmodell']
    vertrag = ('Nur die Rückfragen als nummerierte Liste, keine neue Fassung, kein Kasten.'
               if e['aktion'] == 'Erst klären' else
               'Zuerst die neue Fassung in genau einem geschlossenen Promptkasten (Zeile ~~~text davor, '
               'Zeile ~~~ danach), keine weiteren Kästen. Danach die wichtigsten Änderungen als Stichpunkte. '
               'Bei Bild/Video folgen nach dem Kasten Einstellungen und kurze Erläuterungen.')
    if e['aktion'] == 'Rückfragen':
        vertrag = ('Stelle Sascha Rückfragen, deren Antworten diese Fassung für das Zielmodell spürbar verbessern. '
                   'Schreibe keine neue Fassung und führe den Auftrag nicht aus. Antworte nur mit genau einem '
                   'geschlossenen Kasten (Zeile ~~~json davor, Zeile ~~~ danach) mit diesem JSON:\n'
                   '{"fragen": [{"prioritaet": "kritisch", "frage": "…", "warum": "…", "vorschlaege": ["…", "…"]}]}\n'
                   'Regeln: 0 bis 5 Fragen, meist 3, die wichtigste zuerst. Ist nichts Wichtiges offen, gib '
                   '{"fragen": []} zurück.\n'
                   'prioritaet ist genau eines von kritisch, hoch, mittel: kritisch = ohne Antwort muss das '
                   'Zielmodell an einer Stelle raten, die das Ergebnis unbrauchbar machen kann; hoch = die Antwort '
                   'ändert Inhalt, Umfang oder Format deutlich; mittel = Feinschliff. Frage nichts, was Fassung, '
                   'Material oder Kontext schon beantworten, und nichts, was das Zielmodell selbst gut entscheiden '
                   'kann. Eine Frage je Punkt, höchstens 25 Wörter, Du-Ansprache. warum: ein Satz, was die Antwort '
                   'am Prompt ändert. vorschlaege: 0 bis 4 kurze typische Antworten mit je höchstens 8 Wörtern, '
                   'wenn es naheliegende gibt, sonst eine leere Liste. Keine Fragen nach Zugangsdaten oder nach '
                   'Daten einzelner Patientinnen und Patienten.')
    text = (e['skill']['wert'] + '\n\n---\n'
            + f"Auftrag der Werkstatt: {e['aktion']}\n"
            + 'Werkstatt-Ausgabevertrag (hat Vorrang vor dem Skilltext): ' + vertrag + '\n'
            + 'Den Auftrag nicht ausführen. Absicht erhalten, vorhandene Platzhalter und Feldnamen '
              'zeichengetreu bewahren, keine Zugriffe, Werkzeuge oder fehlenden Fakten erfinden.\n'
            + f"Zielmodell: {z['name']} ({z['verarbeitung']}, frischer Werkstatt-Chat).\n"
            + ('Kontextfenster: ' + (str(z['kontext']) + ' Token' if z.get('kontext') else 'unbekannt')
               + ' · ' + z.get('kontext_quelle', 'Anbieter') + '\n'
               if z['anbieter'] != 'generator' else '')
            + ('Die Denkstufe wird in der Modellzentrale gewählt.\n' if z['modell'] == 'qwen27-unsloth' else '')
            + ('Werkstatt-Test: Sandbox nur lesend mit Werkzeugen; keine Schreibfähigkeit versprechen.\n'
               if z['anbieter'] == 'codex' else 'Werkstatt-Test: ohne Werkzeuge und ohne Projektgedächtnis.\n'
               if z['anbieter'] != 'generator' else 'Im Reiter Bild & Video verwenden. Keine Erzeugung starten.\n')
            + f"Prompt-Typ: {e['typ']['id']} – {e['typ']['name']}\n{e['typ']['regeln']}\n")
    if e['typ']['id'] == 'auto' and e['aktion'] != 'Rückfragen':
        text += ('Bestimme den passenden Typ in derselben Antwort; bei Unklarheit standard. '
                 'Nenne nach dem Promptkasten Prompt-Typ: <id>. Zulässige Typen:\n'
                 + '\n'.join(f"{t['id']}: {t['regeln']}" for t in e['typregeln'] if t['id'] != 'auto') + '\n')
    text += (f"Zielregeln ({e['zielprofil']['id']}): {e['zielprofil']['regeln']}\n"
             + f"Modus: {e['modus']['id']} – {e['modus']['regeln']}\n"
             + f"Hinweise von Sascha: {e['hinweise'] or 'keine'}\n")
    if 'rueckfragen' in e:
        text += ('Antworten von Sascha auf Rückfragen (gehen Annahmen vor; offene Punkte nicht raten, sondern '
                 'frei lassen oder als Platzhalter in eckigen Klammern kennzeichnen):\n')
        for i, frage in enumerate(e['rueckfragen'], 1):
            text += (f"{i}. [{frage['prioritaet']}] {frage['frage']}\n"
                     + '   Antwort: ' + frage['antwort'].replace('\n', '\n   ') + '\n')
    text += f'Fassung „{fassung["name"]}“:\n' + block_schreiben(fassung['text'], 'text')
    if e.get('material'):
        m = e['material']
        text += '\nMaterial, frühere Antwort des Zielmodells:\n' + block_schreiben(m['wert'], 'text')
    for m in e.get('materialien', []) + e.get('kontexte', []):
        text += f"\n{m['name']}:\n" + block_schreiben(m['wert'], 'text')
    return text, sha(text)


def _momentaufnahme(d):
    return dict(d, stand=sha(json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',', ':'))))


def rueckfragen_pruefen(wert, aktion, basis):
    """Nur die übergebene Momentaufnahme prüfen, keine veränderlichen Belege auflösen."""
    if aktion != 'Schärfen' or not basis:
        raise ValueError('Antworten auf Rückfragen gibt es nur beim Schärfen einer gespeicherten Fassung.')
    if not isinstance(wert, list) or not 1 <= len(wert) <= 5:
        raise ValueError('Bitte eine bis fünf beantwortete Rückfragen senden.')
    ergebnis = []
    for f in wert:
        if not isinstance(f, dict) or f.get('prioritaet') not in ('kritisch', 'hoch', 'mittel'):
            raise ValueError('Die Priorität der Rückfrage ist ungültig.')
        frage, antwort = f.get('frage'), f.get('antwort')
        if (not isinstance(frage, str) or not frage.strip() or len(frage) > 300
                or _STEUERZEICHEN.search(frage)):
            raise ValueError('Eine Rückfrage braucht 1 bis 300 Zeichen ohne Steuerzeichen.')
        if not isinstance(antwort, str):
            raise ValueError('Eine Antwort braucht 1 bis 600 Zeichen ohne Steuerzeichen außer Zeilenumbrüchen.')
        antwort = antwort.replace('\r\n', '\n').replace('\r', '\n').strip()
        if not 1 <= len(antwort) <= 600 or _STEUERZEICHEN.search(antwort.replace('\n', '')):
            raise ValueError('Eine Antwort braucht 1 bis 600 Zeichen ohne Steuerzeichen außer Zeilenumbrüchen.')
        ergebnis.append({'prioritaet': f['prioritaet'], 'frage': frage, 'antwort': antwort})
    return ergebnis


def schaerfen_anlegen(ordner, kopf, fassung, eingaben):
    return beleg_anlegen(ordner, dict(kopf, ergebnis='offen'), fassung, eingaben)


def schaerfen_lesen(datei):
    b = beleg_lesen(datei, schaerfen=True)
    e = b['eingaben']
    if e.get('aktion') == 'Rückfragen' and e.get('bau_version') != 2:
        raise ValueError(_RUECKFRAGEN_GRENZE)
    if 'rueckfragen' in e:
        e['rueckfragen'] = rueckfragen_pruefen(e['rueckfragen'], e.get('aktion'), e.get('bau_version') == 2)
    if (e.get('aktion') not in AKTIONEN or not isinstance(e.get('hinweise'), str)
            or not isinstance(e.get('skill'), dict) or not isinstance(e['skill'].get('wert'), str)
            or not isinstance(e.get('zielmodell'), dict)
            or not all(k in e['zielmodell'] for k in ('name', 'anbieter', 'modell', 'verarbeitung'))
            or (e.get('material') is not None and (not isinstance(e['material'], dict)
                                                or not isinstance(e['material'].get('wert'), str)))):
        raise ValueError('Schärfen-Datei beschädigt: Eingaben sind ungültig.')
    if e.get('bau_version') == 2:
        if any(not isinstance(e.get(k), dict) or not all(isinstance(e[k].get(n), str)
                for n in ('id', 'regeln', 'stand')) for k in ('typ', 'zielprofil', 'modus')):
            raise ValueError('Schärfen-Datei beschädigt: Regelmomentaufnahme fehlt.')
    return b


def schaerfen_auswerten(antwort, original_text, aktion, bau_version=1):
    ergebnis = {'kasten': None, 'grund': '', 'neue_platzhalter': []}
    if aktion == 'Rückfragen':
        ergebnis.update(fragenliste=[], fragen_grund='Fragen nicht lesbar', grund='Fragen nicht lesbar')
        try:
            kaesten = bloecke(antwort)
            if len(kaesten) != 1 or not kaesten[0]['geschlossen'] or kaesten[0]['kennung'] not in ('json', ''):
                return ergebnis
            d = json.loads(kaesten[0]['text'])
            if not isinstance(d, dict) or not isinstance(d.get('fragen'), list):
                return ergebnis
            fragen = []
            def normalisieren(text, grenze):
                return ' '.join(_STEUERZEICHEN.sub(' ', text).split())[:grenze]
            for f in d['fragen'][:5]:
                if (not isinstance(f, dict) or f.get('prioritaet') not in ('kritisch', 'hoch', 'mittel')
                        or not isinstance(f.get('frage'), str) or not isinstance(f.get('warum'), str)
                        or not isinstance(f.get('vorschlaege'), list)
                        or any(not isinstance(v, str) for v in f['vorschlaege'])):
                    return ergebnis
                frage = normalisieren(f['frage'], 300)
                if not frage:
                    return ergebnis
                fragen.append({'prioritaet': f['prioritaet'], 'frage': frage,
                               'warum': normalisieren(f['warum'], 300),
                               'vorschlaege': [normalisieren(v, 80) for v in f['vorschlaege'][:4]]})
            ergebnis.update(fragenliste=fragen, fragen_grund='', grund='')
        except (ValueError, TypeError):
            pass
        return ergebnis
    if aktion == 'Erst klären':
        return ergebnis
    if bau_version == 2:
        alle = bloecke(antwort)
        if any(not b['geschlossen'] for b in alle):
            ergebnis['grund'] = 'offener Kasten'
            return ergebnis
        if len(alle) > 1:
            ergebnis['grund'] = 'mehrere Kästen'
            return ergebnis
    kaesten = [b for b in bloecke(antwort) if b['kennung'] in ('text', '') and b['geschlossen']]
    if len(kaesten) != 1:
        ergebnis['grund'] = 'mehrere Kästen' if len(kaesten) > 1 else 'kein Kasten'
        return ergebnis
    b = kaesten[0]
    ergebnis['kasten'] = b
    try:
        text = text_pruefen(b['text'])
    except ValueError as ex:
        ergebnis['grund'] = str(ex)
        return ergebnis
    alt, neu = felder_erkennen(original_text), felder_erkennen(text)
    verloren = [n for n in alt if n not in neu]
    if verloren:
        ergebnis['grund'] = 'Platzhalter verloren: ' + ', '.join('[' + n + ']' for n in verloren)
        return ergebnis
    ergebnis.update(kasten=dict(b, text=text), neue_platzhalter=[n for n in neu if n not in alt])
    return ergebnis


def schaerfen_anzeige(b):
    a = schaerfen_auswerten(b['antwort'], b['fassung_text'], b['eingaben']['aktion'],
                           b['eingaben'].get('bau_version', 1))
    k = a['kasten']
    zeilen = b['antwort'].splitlines(keepends=True)
    stichpunkte = ''.join(zeilen[:k['auf']] + zeilen[k['zu'] + 1:]) if k else b['antwort']
    erkannt = None
    if b['eingaben'].get('bau_version') == 2:
        typ = b['eingaben']['typ']['id']
        treffer = re.search(r'^Prompt-Typ:\s*([a-z_]+)\s*$', stichpunkte, re.M)
        erkannt = typ if typ != 'auto' else (treffer[1] if treffer and treffer[1] in TYPEN else None)
    return dict(a, stichpunkte=stichpunkte, prompt_typ_erkannt=erkannt, typ_anzeige=erkannt or 'Typ nicht erkannt',
                **({'rueckfragen': b['eingaben']['rueckfragen']} if 'rueckfragen' in b['eingaben'] else {}))


def schaerfen_uebernehmen(eintrag, datei):
    with _SPERRE:
        b = schaerfen_lesen(datei)
        aktion = b['eingaben']['aktion']
        a = schaerfen_auswerten(b['antwort'], b['fassung_text'], aktion, b['eingaben'].get('bau_version', 1))
        if aktion == 'Rückfragen':
            ergebnis = a['grund'] or 'Fragen gestellt'
            _kopf_setzen(datei, {'ergebnis': ergebnis})
            return ergebnis
        if b.get('auftragsgruppe') and aktion != 'Erst klären' and not a['grund'] and b['herkunft'] != 'sammlung':
            return _gruppenergebnis_uebernehmen(eintrag, datei, b, a)
        if b.get('auftragsgruppe') and a['grund']:
            ergebnis = 'ungültig (' + a['grund'] + ')'
        elif b['herkunft'] == 'sammlung':
            ergebnis = 'Vorschlag, nicht übernommen'
        elif aktion == 'Erst klären':
            ergebnis = 'Fragen, nicht übernommen'
        elif a['grund']:
            ergebnis = 'ungültig (' + a['grund'] + ')'
        else:
            try:
                datum = datetime.datetime.strptime(b['erstellt'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.')
                basis = _name(f"{aktion} {datum} {b['auswerter']}")
                _, d = eintrag._frisch()
                vorhanden = next((f for f in d['fassungen'] if f['stand'] == stand(a['kasten']['text'])), None)
                if vorhanden:
                    name = vorhanden['name']
                else:
                    name, n = basis, 2
                    while any(f['name'] == name for f in d['fassungen']):
                        name = _name(basis + f' ({n})')
                        n += 1
                    eintrag.fassung_neu(name, a['kasten']['text'])
                ergebnis = f'übernommen ({name})'
            except ValueError as ex:
                ergebnis = f'ungültig ({ex})'
        _kopf_setzen(datei, {'ergebnis': ergebnis})
        return ergebnis


def _gruppenergebnis_uebernehmen(eintrag, datei, b, a):
    """Name vor dem Anhang sichern: auch ein Absturz nach dem Anhang bleibt wiederholbar."""
    _, d = eintrag._frisch()
    text = a['kasten']['text']
    name = b.get('ergebnis_fassung')
    if not name:
        datum = datetime.datetime.strptime(b['erstellt'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.')
        anfang = f"{b['eingaben']['aktion']} {datum} · "
        schreibteile = b['auswerter'].split(' · ', 1)
        schreibmodell = dateiname(schreibteile[-1], 24)
        ziel_platz = 60 - len(anfang) - len(schreibmodell) - 3
        zielteile = b['zielmodell'].split(' · ')
        while len(zielteile) > 1 and len(' · '.join(zielteile)) > ziel_platz:
            zielteile.pop()
        ziel = dateiname(' · '.join(zielteile), ziel_platz)
        basis = anfang + ziel + ' · ' + schreibmodell
        reserviert = {f['name'] for f in d['fassungen']}
        for n in os.listdir(os.path.dirname(datei)):
            pfad = os.path.join(os.path.dirname(datei), n)
            if n.lower().endswith('.md') and pfad_erlaubt(pfad, [os.path.dirname(datei)]):
                try:
                    _, _, kopf, _ = _belegkopf(_lesen(pfad))
                except (OSError, ValueError, UnicodeError):
                    continue
                if kopf.get('ergebnis_fassung'):
                    reserviert.add(kopf['ergebnis_fassung'])
        name, n = _name(basis), 2
        while name in reserviert:
            zusatz = f' ({n})'
            name = _name(basis[:60 - len(zusatz)].rstrip() + zusatz)
            n += 1
        _kopf_setzen(datei, {'ergebnis_fassung': name})
    name = _name(name)
    vorhanden = next((f for f in d['fassungen'] if f['name'] == name), None)
    if vorhanden and vorhanden['stand'] != stand(text):
        raise Konflikt('Der reservierte Ergebnisname gehört inzwischen zu einer anderen Fassung. Bitte im Beleg prüfen.')
    if not vorhanden:
        eintrag.fassung_neu(name, text)
    ergebnis = f'übernommen ({name})'
    _kopf_setzen(datei, {'ergebnis': ergebnis})
    return ergebnis


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


def fassung_vorschlag(fassungen):
    nummern = [int(m.group(1)) for f in fassungen
               if (m := re.fullmatch(r'Fassung ([0-9]+)', f['name']))]
    return f'Fassung {max([len(fassungen), *nummern]) + 1}'


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


_HERKUNFT_FEHLER = 'Die Herkunftsdatei des Eintrags ist beschädigt. Es wurde nichts gespeichert.'


def _herkunft_lesen(pfad):
    if not os.path.exists(pfad):
        return {'version': 1, 'fassungen': {}}
    try:
        d = json.loads(_lesen(pfad))
        if not isinstance(d, dict) or type(d.get('version')) is not int or d['version'] != 1:
            raise ValueError
        if not isinstance(d.get('fassungen'), dict):
            raise ValueError
        anfragen = set()
        for name, h in d['fassungen'].items():
            _name(name)
            if (not isinstance(h, dict) or any(not isinstance(h.get(k), str) or not h[k]
                    for k in ('von_fassung', 'von_stand', 'anfrage_id', 'fingerabdruck', 'erstellt'))
                    or type(h.get('quelle_geaendert')) is not bool or 'quell_beleg' not in h
                    or h['quell_beleg'] is not None and not isinstance(h['quell_beleg'], str)
                    or 'stand' in h and not isinstance(h['stand'], str)
                    or h['anfrage_id'] in anfragen):
                raise ValueError
            _name(h['von_fassung'])
            Index._anfrage_id(h)
            if not re.fullmatch(r'[0-9a-f]{12}', h['von_stand']) or not re.fullmatch(r'[0-9a-f]{64}', h['fingerabdruck']):
                raise ValueError
            if 'stand' in h and not re.fullmatch(r'[0-9a-f]{12}', h['stand']):
                raise ValueError
            anfragen.add(h['anfrage_id'])
        return d
    except (OSError, ValueError, TypeError, UnicodeError):
        raise Konflikt(_HERKUNFT_FEHLER) from None


class Eintrag:
    def __init__(self, pfad):
        self.pfad = os.fspath(pfad)

    def anlegen(self, titel, quelle, schlagworte, text, *, prompt_typ=None, modus=None, composer_auftrag=None):
        with _SPERRE:
            if os.path.exists(self.pfad):
                raise Konflikt('Diese Promptdatei gibt es bereits, bitte neu laden.')
            datum = datetime.date.today().strftime('%d.%m.%Y')
            meta = self._metadaten(prompt_typ, modus, composer_auftrag)
            roh = (f'# {titel.strip()}\nQuelle: {quelle}\nSchlagworte: {schlagworte}\n' + meta
                   + f'Bevorzugt: Fassung 1\nAktualisiert: {datum}\n\n#### Fassung 1\n'
                   + block_schreiben(text_pruefen(text), 'text'))
            _atomar(self.pfad, roh)
            return self.lesen()

    @staticmethod
    def _metadaten(prompt_typ, modus, composer_auftrag):
        if prompt_typ is not None and prompt_typ not in TYPEN:
            raise ValueError('Unbekannter Prompt-Typ.')
        if modus is not None and modus not in ('prompt', 'vorlage'):
            raise ValueError('Unbekannter Modus.')
        if composer_auftrag is not None:
            import uuid
            try:
                if str(uuid.UUID(composer_auftrag)) != composer_auftrag:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Ungültige Sendungskennung.') from None
        return ''.join(f'{k}: {v}\n' for k, v in (('Prompt-Typ', prompt_typ), ('Modus', modus),
                                                  ('Composer-Auftrag', composer_auftrag)) if v is not None)

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
        warnung = {}
        try:
            herkunft = _herkunft_lesen(os.path.join(os.path.dirname(self.pfad), 'herkunft.json'))
            for f in fassungen:
                h = herkunft['fassungen'].get(f['name'])
                if h:
                    f.update(herkunft=h, herkunft_gueltig=h.get('stand') == f['stand'] and not h['quelle_geaendert'])
        except Konflikt:
            warnung['herkunft_fehler'] = _HERKUNFT_FEHLER
        return {'titel': zeilen[anfang][2:].strip(), 'quelle': kopf.get('Quelle', ''),
                **warnung,
                'prompt_typ': kopf.get('Prompt-Typ', 'standard'), 'modus': kopf.get('Modus', 'prompt'),
                'prompt_typ_gespeichert': 'Prompt-Typ' in kopf,
                'composer_auftrag': kopf.get('Composer-Auftrag'),
                'schlagworte': kopf.get('Schlagworte', ''), 'bevorzugt': bevorzugt,
                'aktualisiert': kopf.get('Aktualisiert', ''), 'kopf_stand': ks, 'fassungen': fassungen,
                'fassung_vorschlag': fassung_vorschlag(fassungen),
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
        text = text_pruefen(text)
        with _SPERRE:
            roh, d = self._frisch()
            name = d['fassung_vorschlag'] if isinstance(name, str) and not name.strip() else _name(name)
            if any(f['name'] == name for f in d['fassungen']):
                raise ValueError('Diesen Fassungsnamen gibt es schon.')
            return self._fassung_anhaengen(roh, name, text)

    def _fassung_anhaengen(self, roh, name, text):
        nl = '\r\n' if '\r\n' in roh else '\n'
        return self._schreiben(roh + ('' if roh.endswith('\n') else nl) + nl + f'#### {name}{nl}'
                               + block_schreiben(text, 'text').replace('\n', nl))

    def fassung_bearbeitet(self, anfrage_id, von_fassung, von_stand, text):
        with _SPERRE:
            pfad = os.path.join(os.path.dirname(self.pfad), 'herkunft.json')
            herkunft = _herkunft_lesen(pfad)
            Index._anfrage_id({'anfrage_id': anfrage_id})
            von_fassung = _name(von_fassung)
            if not isinstance(von_stand, str) or not re.fullmatch(r'[0-9a-f]{12}', von_stand):
                raise ValueError('Ungültiger Stand der Ausgangsfassung.')
            if not isinstance(text, str):
                raise ValueError('Bitte einen Prompttext eingeben.')
            text = text_pruefen(text.replace('\r\n', '\n').replace('\r', '\n'))
            fingerabdruck = sha(json.dumps([von_fassung, von_stand, text], ensure_ascii=False, separators=(',', ':')))
            roh = _lesen(self.pfad)
            d = self.lesen(roh)
            # Auch der Verlust der letzten Quellfassung darf den sichtbaren Entwurf nicht vernichten.
            if not d['bearbeitbar'] and (d['fassungen'] or any(not b['geschlossen'] for b in bloecke(roh))):
                raise ValueError('Die Datei ist nicht eindeutig lesbar. Bitte im Editor prüfen.')
            fassungen = {f['name']: f for f in d['fassungen']}
            vorhanden = next(((n, h) for n, h in herkunft['fassungen'].items()
                              if h['anfrage_id'] == anfrage_id), None)
            if vorhanden:
                name, h = vorhanden
                if h['fingerabdruck'] != fingerabdruck:
                    raise Konflikt('Diese Speicheranfrage gehört zu einem anderen Eingabestand.')
                if name in fassungen and fassungen[name]['stand'] != stand(text):
                    raise Konflikt('Die gespeicherte Fassung wurde inzwischen geändert.')
            else:
                quelle = fassungen.get(von_fassung)
                if quelle and quelle['text'] == text:
                    raise ValueError('Der Text ist unverändert.')
                rest = re.split(r'\d{2}\.\d{2}\. · ', von_fassung, maxsplit=1)[-1]
                basis = 'Bearbeitet ' + datetime.date.today().strftime('%d.%m.') + ' · ' + rest
                name, n = _name(basis[:60].rstrip()), 2
                reserviert = set(fassungen) | set(herkunft['fassungen'])
                while name in reserviert:
                    zusatz = f' ({n})'
                    name = _name(basis[:60 - len(zusatz)].rstrip() + zusatz)
                    n += 1
                quell_beleg = None
                if von_fassung in herkunft['fassungen']:
                    quell_beleg = herkunft['fassungen'][von_fassung]['quell_beleg']
                else:
                    ordner = os.path.join(os.path.dirname(self.pfad), 'schaerfen')
                    belege = []
                    if os.path.isdir(ordner):
                        for datei in os.listdir(ordner):
                            p = os.path.join(ordner, datei)
                            if not datei.endswith('.md') or not pfad_erlaubt(p, [ordner]):
                                continue
                            try:
                                _, _, b, _ = _belegkopf(_lesen(p))
                                if b.get('ergebnis_fassung') == von_fassung:
                                    belege.append((b.get('erstellt', ''), datei))
                            except (OSError, ValueError, UnicodeError):
                                continue
                    if belege:
                        quell_beleg = max(belege)[1]
                h = {'von_fassung': von_fassung, 'von_stand': von_stand,
                     'quelle_geaendert': not quelle or quelle['stand'] != von_stand, 'quell_beleg': quell_beleg,
                     'anfrage_id': anfrage_id, 'fingerabdruck': fingerabdruck,
                     'erstellt': datetime.datetime.now().isoformat(timespec='seconds')}
                herkunft['fassungen'][name] = h
                _atomar(pfad, json.dumps(herkunft, ensure_ascii=False, indent=2) + '\n')
            if name not in fassungen:
                if fassungen:
                    self.fassung_neu(name, text)
                else:
                    self._fassung_anhaengen(roh, name, text)
            if h.get('stand') != stand(text):
                h['stand'] = stand(text)
                _atomar(pfad, json.dumps(herkunft, ensure_ascii=False, indent=2) + '\n')
            return name

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
    abschnitt, abschnitt_nr = '', 0
    for i in range(len(zeilen)):
        z = headings.get(i, '')
        if z.startswith(('## ', '### ')):
            werkstatt = z == ABSCHNITT
        if z.startswith('## '):
            abschnitt, abschnitt_nr = z[3:].strip(), abschnitt_nr + 1
            titel = ''
        if z.startswith(('### ', '#### ')):
            titel = z.split(' ', 1)[1].strip()
        b = blocks.get(i)
        if not werkstatt and titel and b and b['zeichen'] == '~' and b['kennung'] in ('', 'text'):
            nummern[titel] = nummern.get(titel, 0) + 1
            n = nummern[titel]
            text = b['text'].replace('\r\n', '\n')
            ergebnis.append({'id': f'sammlung:{titel}#{n}', 'ueberschrift': titel, 'nummer': n,
                             'abschnitt': abschnitt, 'abschnitt_reihenfolge': abschnitt_nr,
                             'reihenfolge': len(ergebnis), 'prompt_typ': 'standard', 'modus': 'prompt',
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

    def optionen(self):
        regeln = profile_lesen(self.cfg)
        ziele = []
        for p in regeln['zielprofile']:
            varianten = []
            if self.auswertung:
                if p['anbieter'] == 'lokal':
                    lokal = self.auswertung.anbieter.get('lokal')
                    eintraege, _ = lokal._eintraege() if lokal else ({}, {})
                    for eid in p['eintraege']:
                        e = eintraege.get(eid)
                        if not e:
                            continue
                        varianten.append({'eintrag': eid, 'name': self._zielname(eid),
                            'varianten': [{k: v[k] for k in ('id', 'name', 'kontext', 'standard') if k in v}
                                          for v in e.get('varianten', [])],
                            'testprofile': [x for x in self.auswertung.profile
                                            if x['anbieter'] == 'lokal' and x['modell'] == eid],
                            'hinweis': 'Die Denkstufe wird in der Modellzentrale gewählt.'
                                        if eid == 'qwen27-unsloth' else ''})
                else:
                    varianten = [{'testprofil': x['id'], 'name': x['name']}
                                 for x in self.auswertung.profile if x['anbieter'] == p['anbieter']]
            ziele.append(dict(p, varianten=varianten))
        return {'typen': regeln['typen'], 'zielprofile': ziele,
                'modi': regeln['modi'], 'generatoren': regeln['generatoren'],
                'regeln_stand': regeln['stand'],
                'feld_max_zeichen': self.cfg.get('feld_max_zeichen', 400000),
                'schreibmodelle': [self.auswertung.profil_info(p) for p in self.auswertung.profile]
                                  if self.auswertung else []}

    @staticmethod
    def _zielname(eid):
        return {'qwen27-unsloth': 'Qwen 27B Q4', 'qwen27-iq3s': 'Qwen 27B IQ3_S',
                'flash-next-strata': 'Flash-Next'}[eid]

    def ziel_aufloesen(self, ziel, regeln):
        if not isinstance(ziel, dict) or set(ziel) - {'zielprofil', 'eintrag', 'testprofil', 'variante'}:
            raise ValueError('Ungültige Zielauswahl.')
        if ziel.get('zielprofil') in regeln['generatoren']:
            gid = ziel['zielprofil']
            if ziel.get('testprofil') or ziel.get('eintrag') or ziel.get('variante'):
                raise ValueError('Für Bild und Video ist kein Text-Testprofil vorgesehen.')
            g = regeln['generatoren'][gid]
            modell = 'qwen-image-2.1' if gid == 'bild' else 'minimax-h3'
            return {'zielprofil': dict(g, id=gid), 'zielschluessel': gid + ':' + modell,
                    'testprofil_id': None, 'zielmodell': {'name': g['name'], 'anbieter': 'generator',
                    'modell': modell, 'kontext': None, 'verarbeitung': 'lokal'}}
        p = next((p for p in regeln['zielprofile'] if p['id'] == ziel.get('zielprofil')), None)
        if not p:
            raise ValueError('Unbekanntes Zielprofil.')
        test = next((x for x in self.auswertung.profile if x['id'] == ziel.get('testprofil')), None)
        if ziel.get('testprofil') and not test:
            raise ValueError('Das Testprofil fehlt. Bitte neu wählen.')
        if p['anbieter'] == 'lokal':
            eid = ziel.get('eintrag')
            if eid not in p['eintraege']:
                raise ValueError('Dieses Modell gehört nicht zum Zielprofil.')
            lokal = self.auswertung.anbieter.get('lokal')
            eintraege, _ = lokal._eintraege() if lokal else ({}, {})
            e = eintraege.get(eid)
            if not e:
                raise ValueError('Dieses Zielmodell steht nicht mehr in der Modellzentrale.')
            if test and (test['anbieter'] != 'lokal' or test['modell'] != eid):
                raise ValueError('Das Testprofil passt nicht zum Zielmodell.')
            variante = next((v for v in e.get('varianten', []) if v['id'] == ziel.get('variante')), None)
            if ziel.get('variante') and not variante:
                raise ValueError('Diese Zielvariante gibt es nicht.')
            name = self._zielname(eid)
            if variante:
                name += ' · ' + variante['name']
            kontext = (variante or {}).get('kontext') or next(
                (v.get('kontext') for v in e.get('varianten', []) if v.get('standard')), None)
            if eid in ('qwen27-unsloth', 'qwen27-iq3s'):
                kontext = 131072
            schluessel = p['id'] + ':' + eid + (':' + variante['id'] if variante else '')
            modell = {'name': name, 'anbieter': 'lokal', 'modell': eid, 'kontext': kontext, 'verarbeitung': 'lokal',
                      'kontext_quelle': 'Katalog der Zentrale'}
            if eid == 'flash-next-strata':
                # Gleiche Modellkennung kann mit 128K oder 256K laufen. Nie aus ihr den Kontext ableiten.
                try:
                    if lokal.verfuegbar({'modell': eid})[0]:
                        geladen, quelle, kennung_geladen = lokal.kontext_geladen({'modell': eid})
                        modell.update(kontext=geladen, kontext_quelle=quelle, modell_tatsaechlich=kennung_geladen)
                except (RuntimeError, OSError, ValueError):
                    pass  # Ein ungeladenes Ziel bleibt zum Schärfen auswählbar.
        else:
            if not test or test['anbieter'] != p['anbieter'] or ziel.get('eintrag') or ziel.get('variante'):
                raise ValueError('Bitte ein passendes Testprofil für das Ziel wählen.')
            a = self.auswertung.anbieter[p['anbieter']]
            modell = {'name': test['name'], 'anbieter': p['anbieter'], 'modell': test['modell'],
                      'kontext': a.kontext(test), 'verarbeitung': 'Cloud (' + a.cloud + ')'}
            schluessel = p['id'] + ':' + test['id']
        return {'zielprofil': dict(p), 'zielschluessel': schluessel, 'zielmodell': modell,
                'testprofil_id': test['id'] if test else None}

    def _antwortmaterial(self, eid, datei):
        if not datei:
            return None
        b = beleg_lesen(self.beleg_pfad(eid, datei))
        if not b['antwort'].strip():
            raise ValueError('Der gewählte Beleg hat keine Antwort.')
        return {'wert': b['antwort'][:30000], 'beleg': b['datei'], 'eintrag': eid,
                'erstellt': b.get('erstellt', 'unbekannt'), 'gekuerzt': len(b['antwort']) > 30000,
                'stand': sha(b['antwort'][:30000])}

    def composer_vorschau(self, daten):
        self._composer_fingerabdruck(daten)
        schreibmodell_ids = self._composer_schreibmodelle(daten)
        regeln = profile_lesen(self.cfg)
        text = daten.get('text')
        if not isinstance(text, str):
            raise ValueError('Bitte einen Rohprompt eingeben.')
        text = text_pruefen(text)
        typ, modus = daten.get('prompt_typ', 'auto'), daten.get('modus', 'prompt')
        if typ not in TYPEN or modus not in ('prompt', 'vorlage'):
            raise ValueError('Unbekannter Prompt-Typ oder Modus.')
        aktion = daten.get('schaerfen_aktion', 'Schärfen')
        if aktion not in AKTIONEN:
            raise ValueError('Unbekannte Schärfen-Aktion.')
        if aktion == 'Rückfragen' and (not daten.get('basis') or len(schreibmodell_ids) != 1
                or not isinstance(daten.get('ziele'), list) or len(daten['ziele']) != 1):
            raise ValueError(_RUECKFRAGEN_GRENZE)
        antworten = (rueckfragen_pruefen(daten['rueckfragen'], aktion, daten.get('basis'))
                     if 'rueckfragen' in daten else None)
        hinweise = daten.get('hinweise', '')
        if not isinstance(hinweise, str) or len(hinweise) > 2000:
            raise ValueError('Hinweise dürfen höchstens 2.000 Zeichen enthalten.')
        materialien = self.material_pruefen(daten)['materialien']
        kontexte = self.kontexte_aufloesen(daten.get('kontexte', []))
        if type(daten.get('realismus', False)) is not bool or (daten.get('realismus') and typ not in ('bild', 'video')):
            raise ValueError('Fotorealistische Menschen ist nur für Bild und Video vorgesehen.')
        ablage, basis = daten.get('ablage', 'ordner'), daten.get('basis')
        if ablage not in ('ordner', 'sammlung'):
            raise ValueError('Unbekannte Ablage.')
        if ablage == 'sammlung' and not basis:
            raise ValueError('Wähle einen Sammlungseintrag. Neue Wissensprompts legst du weiterhin in deiner Promptsammlung an.')
        d, f = None, {'name': 'Fassung 1', 'text': text, 'stand': stand(text)}
        if basis is not None:
            if not isinstance(basis, dict) or set(basis) != {'id', 'fassung', 'stand'}:
                raise ValueError('Ungültige Ausgangsfassung.')
            d = self.lesen(basis['id'])
            f = next((f for f in d['fassungen'] if f['name'] == basis['fassung']), None)
            if d.get('fehler') or not f or f['stand'] != basis['stand']:
                raise Konflikt('Die Ausgangsfassung wurde inzwischen geändert, bitte neu laden.')
            if daten['text'] != f['text']:
                raise Konflikt('Die Ausgangsfassung bleibt unverändert. Verwende für Änderungen die Hinweise.')
            if d['herkunft'] != ablage:
                raise ValueError('Die Ablage muss zur Ausgangsfassung passen.')
        titel = daten.get('titel', '')
        if not isinstance(titel, str) or _STEUERZEICHEN.search(titel):
            raise ValueError('Ungültige Kopfzeile.')
        titel = d['titel'] if d else titel.strip() or ' '.join(text.split()[:8])[:70].rstrip()
        if not self.auswertung:
            raise ValueError('Kein Schreibmodell verfügbar.')
        schreibmodelle = []
        for pid in schreibmodell_ids:
            p = next((p for p in self.auswertung.profile if p['id'] == pid), None)
            if not p:
                raise ValueError(f'{pid}: Dieses Schreibmodell gibt es nicht mehr.')
            try:
                ok, grund = self.auswertung.prompt_verfuegbar(p, frisch=True)
                if not ok:
                    raise PromptFehler('anbieter', grund)
                a = self.auswertung.anbieter[p['anbieter']]
                kontext, quelle, modell = a.kontext_geladen(p)
            except PromptFehler as ex:
                raise PromptFehler(ex.code, f"{p['name']}: {ex}") from None
            schreibmodelle.append(dict(p, kontext=kontext, kontext_quelle=quelle, modell_tatsaechlich=modell,
                                       verarbeitung='Cloud (' + a.cloud + ')' if a.cloud else 'lokal'))
        ziele = daten.get('ziele')
        if not isinstance(ziele, list) or not ziele:
            raise ValueError('Bitte mindestens ein Zielmodell wählen.')
        skill = skill_lesen({'skill': self.cfg.get('skill_realismus')} if daten.get('realismus') else self.cfg)
        material = self._antwortmaterial(d['id'], daten.get('material')) if d else None
        if daten.get('material') and not d:
            raise ValueError('Bitte den Eintrag zur Materialantwort wählen.')
        if material and (len(materialien) >= 5 or sum(m['zeichen'] for m in materialien) + len(material['wert'])
                         > self.cfg.get('feld_max_zeichen', 400000)):
            raise ValueError('Höchstens fünf Materialien innerhalb der Gesamtgrenze auswählen.')
        auswahl, laeufe, schluessel = [], [], set()
        for ziel in ziele:
            z = self.ziel_aufloesen(ziel, regeln)
            if (typ in ('bild', 'video') and z['zielprofil']['id'] != typ
                    or typ not in ('bild', 'video') and z['zielmodell']['anbieter'] == 'generator'):
                raise ValueError('Das Ziel passt nicht zum Prompt-Typ.')
            if z['zielschluessel'] in schluessel:
                raise ValueError('Ein Zielmodell wurde mehrfach ausgewählt.')
            schluessel.add(z['zielschluessel'])
            e = {'bau_version': 2, 'aktion': aktion, 'hinweise': hinweise, 'skill': skill,
                 'typ': _momentaufnahme(next(t for t in regeln['typen'] if t['id'] == typ)),
                 'typregeln': regeln['typen'] if typ == 'auto' else [],
                 'zielprofil': _momentaufnahme(z['zielprofil']), 'zielmodell': z['zielmodell'],
                 'modus': _momentaufnahme(dict(regeln['modi'][modus], id=modus)),
                 'regeldatei_stand': regeln['stand'], 'realismus': daten.get('realismus', False),
                 'material': material, 'materialien': materialien, 'kontexte': kontexte}
            if antworten is not None:
                e['rueckfragen'] = antworten
            auftrag, gs = schaerfen_bauen(f, e)
            for p in schreibmodelle:
                try:
                    schaetzung, reserve = kontext_pruefen(auftrag, p['kontext'])
                except PromptFehler as ex:
                    raise PromptFehler(ex.code, f"{p['name']}: {ex}") from None
                laeufe.append(dict(zielschluessel=z['zielschluessel'], schreibmodell_id=p['id'],
                                   geschaetzt=schaetzung, reserve=reserve))
            auswahl.append(dict(z, auftrag=auftrag, gesendet_stand=gs, eingaben=e))
        return {'titel': titel, 'fassung': f, 'basis': basis, 'ablage': ablage,
                'schreibmodelle': schreibmodelle, 'ziele': auswahl, 'laeufe': laeufe,
                'gesendet_staende': {z['zielschluessel']: z['gesendet_stand'] for z in auswahl}}

    @staticmethod
    def _composer_schreibmodelle(daten):
        if 'schreibmodell' in daten and 'schreibmodelle' in daten:
            raise ValueError('Bitte nur eine Schreibmodell-Angabe senden.')
        ids = daten.get('schreibmodelle', [daten['schreibmodell']] if 'schreibmodell' in daten else [])
        if not isinstance(ids, list) or any(not isinstance(pid, str) for pid in ids):
            raise ValueError('Ungültige Schreibmodell-Auswahl.')
        if not ids or any(not pid for pid in ids):
            raise ValueError('Bitte ein Schreibmodell wählen.')
        if len(ids) > 3:
            raise ValueError('Höchstens drei Schreibmodelle auswählen.')
        if len(set(ids)) != len(ids):
            raise ValueError('Ein Schreibmodell wurde mehrfach ausgewählt.')
        return ids

    @staticmethod
    def _anfrage_id(daten):
        import uuid
        aid = daten.get('anfrage_id')
        try:
            if str(uuid.UUID(aid)) != aid:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Ungültige Sendungskennung.') from None
        return aid

    def _sendung_pfad(self, aid):
        return self._pfad('_Auftraege', aid + '.json')

    def _sendung_lesen(self, aid):
        pfad = self._sendung_pfad(aid)
        if not os.path.exists(pfad):
            return None
        try:
            d = json.loads(_lesen(pfad))
            if not isinstance(d['ziele'], list) or not isinstance(d['eingabe_stand'], str):
                raise ValueError
            return d
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise ValueError('Die Sendungsdatei ist beschädigt. Bitte die vorhandenen Belege prüfen.') from None

    def _sendung_schreiben(self, aid, d):
        os.makedirs(self._pfad('_Auftraege'), exist_ok=True)
        _atomar(self._sendung_pfad(aid), json.dumps(d, ensure_ascii=False, indent=2) + '\n')

    @staticmethod
    def _composer_fingerabdruck(daten):
        erlaubt = {'aktion', 'anfrage_id', 'text', 'titel', 'ablage', 'basis', 'prompt_typ', 'modus',
                   'schreibmodell', 'schreibmodelle', 'ziele', 'hinweise', 'material', 'materialien', 'kontexte',
                   'gesendet_staende', 'realismus', 'schaerfen_aktion', 'rueckfragen'}
        if set(daten) - erlaubt:
            raise ValueError('Unbekannte Composer-Angaben.')
        if daten.get('schaerfen_aktion') == 'Rückfragen':
            ids = daten.get('schreibmodelle', [daten.get('schreibmodell')])
            if (not daten.get('basis') or not isinstance(ids, list) or len(ids) != 1
                    or not isinstance(daten.get('ziele'), list) or len(daten['ziele']) != 1):
                raise ValueError(_RUECKFRAGEN_GRENZE)
        werte = {k: v for k, v in daten.items() if k not in ('aktion', 'anfrage_id', 'gesendet_staende')}
        if 'rueckfragen' in daten:
            werte['rueckfragen'] = rueckfragen_pruefen(daten['rueckfragen'], daten.get('schaerfen_aktion', 'Schärfen'),
                                                     daten.get('basis'))
        return sha(json.dumps(werte,
                              ensure_ascii=False, sort_keys=True, separators=(',', ':')))

    def composer_senden(self, daten):
        import secrets
        aid = self._anfrage_id(daten)
        fingerabdruck = self._composer_fingerabdruck(daten)
        schreibmodell_ids = self._composer_schreibmodelle(daten)
        auftraege = []
        with _SPERRE:
            s = self._sendung_lesen(aid)
            if s and s['eingabe_stand'] != fingerabdruck:
                raise Konflikt('Diese Sendung gehört zu einem anderen Eingabestand.')
            if s and any('schreibmodell_id' not in z for z in s['ziele']):
                for z in s['ziele']:
                    z.setdefault('schreibmodell_id', schreibmodell_ids[0])
                self._sendung_schreiben(aid, s)
            if s and s.get('vollstaendig'):
                fertig = True
            else:
                fertig, v = False, None
                if not s:
                    v = self.composer_vorschau(daten)
                    if v['gesendet_staende'] != daten.get('gesendet_staende'):
                        raise Konflikt('Der Inhalt hat sich seit der Vorschau geändert.')
                    reserviert = os.listdir(self.ordner)
                    if os.path.isdir(self._pfad('_Auftraege')):
                        for n in os.listdir(self._pfad('_Auftraege')):
                            if n.endswith('.json'):
                                try:
                                    reserviert.append(json.loads(_lesen(self._pfad('_Auftraege', n)))['eintrag'])
                                except (ValueError, KeyError):
                                    pass
                    eid = v['basis']['id'] if v['basis'] else kennung(v['titel'], reserviert)
                    s = {'eingabe_stand': fingerabdruck, 'eintrag': eid, 'beleg_eintrag': eid,
                         'vollstaendig': False, 'ziele': [{'zielschluessel': z['zielschluessel'],
                         'schreibmodell_id': z['schreibmodell_id'], 'beleg': None,
                         'auftrags_id': secrets.token_hex(8), 'eingereiht': False} for z in v['laeufe']]}
                    self._sendung_schreiben(aid, s)
                eid = s['eintrag']
                if not daten.get('basis'):
                    pfad = self._pfad(eid, 'prompt.md')
                    if os.path.exists(pfad):
                        if Eintrag(pfad).lesen().get('composer_auftrag') != aid:
                            raise Konflikt('Die reservierte Eintragskennung ist inzwischen belegt.')
                    else:
                        v = v or self.composer_vorschau(daten)
                        if v['gesendet_staende'] != daten.get('gesendet_staende'):
                            raise Konflikt('Der Inhalt hat sich seit der Vorschau geändert.')
                        os.makedirs(self._pfad(eid), exist_ok=True)
                        Eintrag(pfad).anlegen(v['titel'], '', '', v['fassung']['text'],
                            prompt_typ=daten.get('prompt_typ', 'auto'), modus=daten.get('modus', 'prompt'), composer_auftrag=aid)
                if daten.get('ablage') == 'sammlung' and s['beleg_eintrag'] == eid:
                    self._testordner(eid)
                    s['beleg_eintrag'] = 'schatten:' + self.lesen(eid)['schatten']
                    self._sendung_schreiben(aid, s)
                ordner = os.path.join(self._ordner(s['beleg_eintrag']), 'schaerfen')
                if not pfad_erlaubt(ordner, [self.ordner]):
                    raise ValueError('Schärfen-Ordner nicht erlaubt.')
                for lauf_nr, z in enumerate(s['ziele']):
                    # Ein Absturz kann vor dem Eintragen des Dateinamens eingetreten sein.
                    belege = []
                    if os.path.isdir(ordner):
                        for n in os.listdir(ordner):
                            pfad = os.path.join(ordner, n)
                            if not n.endswith('.md') or not pfad_erlaubt(pfad, [self.ordner]):
                                continue
                            try:
                                _, _, kopf, _ = _belegkopf(_lesen(pfad))
                                if kopf.get('auftragsgruppe') == aid and kopf.get('auftrags_id') == z['auftrags_id']:
                                    if (kopf.get('zielschluessel') != z['zielschluessel'] or
                                            'schreibmodell_id' in kopf and kopf['schreibmodell_id'] != z['schreibmodell_id']):
                                        raise Konflikt('Ein Gruppenbeleg passt nicht zu seinem Lauf. Bitte die Gruppe prüfen.')
                                    belege.append(n)
                            except (ValueError, UnicodeError):
                                continue
                    if len(belege) > 1:
                        raise Konflikt('Mehrere Belege für denselben Lauf gefunden. Bitte die Gruppe prüfen.')
                    if belege:
                        z['beleg'] = belege[0]
                    elif z['beleg']:
                        raise Konflikt('Ein bereits angelegter Gruppenbeleg fehlt. Bitte die Gruppe prüfen.')
                    else:
                        v = v or self.composer_vorschau(daten)
                        if v['gesendet_staende'] != daten.get('gesendet_staende'):
                            raise Konflikt('Der Inhalt hat sich seit der Vorschau geändert.')
                        ziel = next(x for x in v['ziele'] if x['zielschluessel'] == z['zielschluessel'])
                        p = next(p for p in v['schreibmodelle'] if p['id'] == z['schreibmodell_id'])
                        f, e = v['fassung'], ziel['eingaben']
                        kopf = dict(prompt=v['titel'], eintrag=eid, herkunft=v['ablage'], fassung=f['name'],
                            fassung_stand=f['stand'], rahmen='nein', gesendet_stand=ziel['gesendet_stand'],
                            auswerter=p['name'], anbieter=p['anbieter'], modell=p['modell'],
                            kontext=p['kontext'], kontext_quelle=p['kontext_quelle'], verarbeitung=p['verarbeitung'],
                            zustand='wartet', meldung='', erstellt=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            hinweis='', status='Entwurf, automatisch erstellt, nicht geprüft', aktion=e['aktion'],
                            skill_stand=e['skill']['stand'], zielmodell=e['zielmodell']['name'],
                            zielmodell_anbieter=e['zielmodell']['anbieter'], zielmodell_modell=e['zielmodell']['modell'],
                            zielmodell_kontext=e['zielmodell']['kontext'], auftragsgruppe=aid,
                            zielprofil_id=e['zielprofil']['id'], zielschluessel=z['zielschluessel'],
                            testprofil_id=ziel['testprofil_id'], ergebnis_fassung=None, auftrags_id=z['auftrags_id'],
                            schreibmodell_id=p['id'], lauf_nr=lauf_nr)
                        if p.get('stufe'):
                            kopf['denkstufe'] = p['stufe']
                        z['beleg'] = os.path.basename(schaerfen_anlegen(ordner, kopf, f['text'], e))
                    self._sendung_schreiben(aid, s)
                    if not z['eingereiht']:
                        a = self.auftrag_aus_beleg(s['beleg_eintrag'], z['beleg'], 'schaerfen')
                        a['prompt']['eintrag'] = eid
                        auftraege.append(a)
        # Keine Dateisperre während des Erwerbs der Warteschlangensperre.
        if not fertig:
            for a in auftraege:
                self.auswertung.einreihen(a)
                with _SPERRE:
                    s = self._sendung_lesen(aid)
                    next(z for z in s['ziele'] if z['auftrags_id'] == a['id'])['eingereiht'] = True
                    s['vollstaendig'] = all(z['eingereiht'] for z in s['ziele'])
                    self._sendung_schreiben(aid, s)
        return self.composer_status({'anfrage_id': aid})

    def composer_status(self, daten):
        aid = self._anfrage_id(daten)
        with _SPERRE:
            s = self._sendung_lesen(aid)
        if not s:
            return {'anfrage_id': aid, 'gefunden': False}
        with self.auswertung._lock:
            schlange = {a['id']: a['zustand'] for a in self.auswertung.liste}
        ziele = []
        with _SPERRE:
            for z in s['ziele']:
                kopf = {}
                if z['beleg']:
                    try:
                        pfad = self.beleg_pfad(s['beleg_eintrag'], z['beleg'], 'schaerfen')
                        _, _, kopf, _ = _belegkopf(_lesen(pfad))
                    except (OSError, ValueError, UnicodeError):
                        kopf = {'fehler': 'Beleg nicht lesbar.'}
                ziele.append(dict(z, zustand=schlange.get(z['auftrags_id'], kopf.get('zustand',
                    'eingereiht' if z['eingereiht'] else 'Einreihung unvollständig')),
                    schreibmodell_id=kopf.get('schreibmodell_id', z.get('schreibmodell_id', '')),
                    auswerter=kopf.get('auswerter', ''),
                    **{k: kopf[k] for k in ('zielmodell', 'zielprofil_id', 'testprofil_id',
                                           'ergebnis_fassung', 'ergebnis', 'fehler') if k in kopf}))
        return {'anfrage_id': aid, 'auftragsgruppe': aid, 'gefunden': True, 'id': s['eintrag'],
                'vollstaendig': s['vollstaendig'], 'auftraege': [z['auftrags_id'] for z in s['ziele']],
                'ziele': ziele}

    def beleg_pfad(self, eid, datei, art_ordner='tests'):
        if art_ordner not in ('tests', 'schaerfen'):
            raise ValueError('Unbekannter Belegordner.')
        if (not isinstance(datei, str) or not datei or _STEUERZEICHEN.search(datei)
                or re.search(r'[/\\:]', datei) or not datei.lower().endswith('.md')):
            raise ValueError('Bitte einen reinen Belegdateinamen angeben.')
        pfad = os.path.join(self._ordner(eid), art_ordner, datei)
        if not pfad_erlaubt(pfad, [self.ordner]):
            raise ValueError('Belegpfad nicht erlaubt.')
        return pfad

    def datei_lesen(self, pfad):
        wurzeln = self.cfg['dateiwurzeln'] + ([self.watch] if self.watch else [])
        if not pfad_erlaubt(pfad, wurzeln) or not os.path.isfile(pfad):
            raise ValueError('Die Datei fehlt oder liegt außerhalb der erlaubten Ordner.')
        # Zugangsdaten gehören nie in einen Prompt (AGENTS.md): gesperrte Ordner aus der Konfiguration und .env-Dateien.
        gesperrt = self.cfg.get('gesperrt') or []
        name = os.path.basename(pfad).lower()
        if (gesperrt and pfad_erlaubt(pfad, gesperrt)) or name.endswith('.env') or name.startswith('.env.'):
            raise ValueError('Diese Datei enthält Zugangsdaten oder liegt in einem gesperrten Ordner; '
                             'sie geht nicht in einen Prompt.')
        grenze = self.cfg.get('feld_max_zeichen', 400000)
        with open(pfad, encoding='utf-8', errors='replace') as f:
            text = f.read(grenze + 1)
        if len(text) > grenze:
            raise ValueError(f'Die Datei überschreitet {grenze} Zeichen je Feld.')
        return {'art': 'datei', 'pfad': pfad, 'wert': text, 'sha': sha(text), 'zeichen': len(text)}

    @staticmethod
    def _textdatei_name(name):
        if (not isinstance(name, str) or not name or _STEUERZEICHEN.search(name)
                or re.search(r'[/\\:]', name)):
            raise ValueError('Bitte einen reinen Textdateinamen angeben.')
        if os.path.splitext(name)[1].lower() not in TEXT_ENDUNGEN:
            raise ValueError('Bitte eine Textdatei auswählen. PDF, Office-Dateien, Bilder, Audio und Video sind hier nicht vorgesehen.')
        return name

    def material_datei_lesen(self, daten):
        pfad = daten.get('pfad', '')
        self._textdatei_name(os.path.basename(pfad))
        datei = self.datei_lesen(pfad)
        return dict(datei, name=os.path.basename(pfad))

    def material_pruefen(self, daten):
        materialien = daten.get('materialien', [])
        if not isinstance(materialien, list) or len(materialien) > 5:
            raise ValueError('Bitte höchstens fünf Materialien auswählen.')
        ergebnis, gesamt = [], 0
        grenze = self.cfg.get('feld_max_zeichen', 400000)
        for m in materialien:
            if not isinstance(m, dict):
                raise ValueError('Ungültiges Textmaterial.')
            art = m.get('art')
            if art == 'datei':
                wert = self.material_datei_lesen(m)
            elif art == 'text':
                if 'pfad' in m:
                    raise ValueError('Eine Browserdatei hat keinen Dateipfad.')
                wert = {'art': 'text', 'name': self._textdatei_name(m.get('name')), 'wert': m.get('wert')}
            elif art == 'antwort':
                wert = self._antwortmaterial(m.get('eintrag', ''), m.get('beleg'))
                if wert is None:
                    raise ValueError('Bitte eine vorhandene Antwort wählen.')
                wert.update(art='antwort', name='Antwort · ' + wert['beleg'])
            else:
                raise ValueError('Unbekannte Materialart.')
            text = wert.get('wert')
            if not isinstance(text, str) or '\x00' in text:
                raise ValueError('Das Material enthält keinen lesbaren Text.')
            gesamt += len(text)
            if gesamt > grenze:
                raise ValueError(f'Die Materialien überschreiten zusammen {grenze} Zeichen. Bitte weniger Text auswählen.')
            ergebnis.append(dict(wert, zeichen=len(text), sha=sha(text)))
        return {'materialien': ergebnis, 'zeichen': gesamt}

    def _kontext_pfad(self, kid):
        if not isinstance(kid, str) or not kid or kennung(kid) != kid:
            raise ValueError('Ungültige Kontextkennung.')
        return self._pfad('_Kontext', kid + '.md')

    def kontext_lesen(self, daten):
        kid = daten.get('id')
        roh = _lesen(self._kontext_pfad(kid))
        zeilen, kaesten, koepfe = _zeilenkopf(roh)
        if (len(kaesten) != 1 or not kaesten[0]['geschlossen'] or kaesten[0]['kennung'] not in ('', 'text')
                or len(koepfe) != 1 or not koepfe[0][1].startswith('# ')):
            raise ValueError('Der Kontextbaustein muss einen Titel und genau einen geschlossenen Textkasten enthalten.')
        b = kaesten[0]
        a, titel = koepfe[0]
        if a >= b['auf'] or any(z.strip() for i, z in enumerate(zeilen) if i != a and not b['auf'] <= i <= b['zu']):
            raise ValueError('Außerhalb des Kontextkastens darf nur der Titel stehen.')
        self._kontext_pruefen(titel[2:], b['text'])
        return {'id': kid, 'titel': titel[2:], 'name': titel[2:], 'wert': b['text'],
                'stand': sha(roh), 'sha': sha(b['text']), 'zeichen': len(b['text'])}

    @staticmethod
    def _kontext_pruefen(titel, text):
        if not isinstance(titel, str) or not titel.strip() or _STEUERZEICHEN.search(titel):
            raise ValueError('Bitte einen Kontexttitel ohne Zeilenumbruch angeben.')
        if not isinstance(text, str) or not text.strip() or '\x00' in text or len(text) > 20000:
            raise ValueError('Ein Kontextbaustein braucht Text mit höchstens 20.000 Zeichen.')

    def kontexte(self):
        basis = self._pfad('_Kontext')
        ergebnis = []
        with _SPERRE:
            for name in sorted(os.listdir(basis)) if os.path.isdir(basis) else []:
                if not name.lower().endswith('.md'):
                    continue
                kid = name[:-3]
                try:
                    k = self.kontext_lesen({'id': kid})
                    ergebnis.append({n: k[n] for n in ('id', 'titel', 'stand', 'zeichen')})
                except (OSError, ValueError, UnicodeError):
                    ergebnis.append({'id': kid, 'titel': kid, 'fehler': 'Kontextbaustein nicht lesbar.'})
        return {'kontexte': ergebnis}

    def kontext_neu(self, daten):
        titel, text = daten.get('titel'), daten.get('wert')
        self._kontext_pruefen(titel, text)
        with _SPERRE:
            basis = self._pfad('_Kontext')
            os.makedirs(basis, exist_ok=True)
            kid = kennung(titel, [os.path.splitext(n)[0] for n in os.listdir(basis)])
            _atomar(self._kontext_pfad(kid), '# ' + titel.strip() + '\n\n' + block_schreiben(text, 'text'))
            return self.kontext_lesen({'id': kid})

    def kontext_speichern(self, daten):
        self._kontext_pruefen(daten.get('titel'), daten.get('wert'))
        with _SPERRE:
            alt = self.kontext_lesen(daten)
            if alt['stand'] != daten.get('stand'):
                raise Konflikt('Der Kontextbaustein wurde inzwischen geändert, bitte neu laden.')
            _atomar(self._kontext_pfad(alt['id']), '# ' + daten['titel'].strip() + '\n\n' + block_schreiben(daten['wert'], 'text'))
            return self.kontext_lesen(daten)

    def kontexte_aufloesen(self, auswahl):
        if not isinstance(auswahl, list):
            raise ValueError('Ungültige Kontextauswahl.')
        ergebnis, gesehen = [], set()
        for wahl in auswahl:
            if not isinstance(wahl, dict) or set(wahl) != {'id', 'stand'}:
                raise ValueError('Bitte Kontextbausteine aus der Übersicht wählen.')
            k = self.kontext_lesen(wahl)
            if k['stand'] != wahl['stand']:
                raise Konflikt('Ein ausgewählter Kontextbaustein wurde geändert. Bitte neu auswählen.')
            if k['id'] in gesehen:
                raise ValueError('Ein Kontextbaustein wurde mehrfach ausgewählt.')
            gesehen.add(k['id'])
            ergebnis.append(k)
        return ergebnis

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
        if daten.get('schaerfen_beleg'):
            fassungen = [self._sammlungsvorschlag(d, daten['schaerfen_beleg'])]
        profile = [p for p in self.auswertung.profile if p['id'] in daten.get('auswerter', [])]
        if not fassungen or not profile:
            raise ValueError('Bitte mindestens eine Fassung und einen Auswerter anhaken.')
        eingaben, texte = self._eingaben(daten, fassungen)
        if daten.get('schaerfen_beleg'):
            eingaben['schaerfen_beleg'] = {'datei': daten['schaerfen_beleg'],
                                          'stand': sha(_lesen(self.beleg_pfad(d['id'], daten['schaerfen_beleg'], 'schaerfen')))}
        ergebnis = []
        for f in fassungen:
            text, gs = auftrag_bauen(f['text'], eingaben, texte)
            kurz = {n: f'[Transkript: {len(t)} Zeichen]' for n, t in texte.items()}
            anzeigen, _ = auftrag_bauen(f['text'], eingaben, kurz)
            auswerter = []
            for p in profile:
                anbieter = self.auswertung.anbieter[p['anbieter']]
                ok, grund = self.auswertung.prompt_verfuegbar(p)
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

    def _sammlungsvorschlag(self, d, datei):
        if d['herkunft'] != 'sammlung':
            raise ValueError('Belegreferenzen sind nur für Sammlungsvorschläge vorgesehen.')
        b = schaerfen_lesen(self.beleg_pfad(d['id'], datei, 'schaerfen'))
        a = schaerfen_auswerten(b['antwort'], b['fassung_text'], b['eingaben']['aktion'],
                               b['eingaben'].get('bau_version', 1))
        if b['herkunft'] != 'sammlung' or not a['kasten'] or a['grund']:
            raise ValueError('Der Sammlungsvorschlag enthält keinen gültigen Promptkasten.')
        text = a['kasten']['text']
        return {'name': _name(dateiname('Vorschlag · ' + b.get('zielmodell', b['auswerter']), 60)),
                'text': text, 'stand': stand(text), 'schreibgeschuetzt': True}

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

    def schaerfen_vorschau(self, daten):
        if daten.get('schaerfen_aktion') == 'Rückfragen':
            raise ValueError(_RUECKFRAGEN_GRENZE)
        if 'rueckfragen' in daten:
            rueckfragen_pruefen(daten['rueckfragen'], daten.get('schaerfen_aktion', 'Schärfen'), None)
        d = self.lesen(daten.get('id', ''))
        f = next((f for f in d['fassungen'] if f['name'] == daten.get('fassung')), None)
        if d.get('fehler') or not f:
            raise ValueError('Bitte eine lesbare Fassung wählen.')
        if any(k in daten for k in ('prompt_typ', 'modus', 'zielprofil', 'realismus')):
            p = next((p for p in self.auswertung.profile if p['id'] == daten.get('zielmodell')), None)
            pid = daten.get('zielprofil') or (('qwen27' if p['modell'] in ('qwen27-unsloth', 'qwen27-iq3s')
                   else 'flash_next' if p['modell'] == 'flash-next-strata' else p['anbieter']) if p else None)
            ziel = {'zielprofil': pid, 'testprofil': p['id'] if p else None}
            if p and p['anbieter'] == 'lokal':
                ziel['eintrag'] = p['modell']
            v = self.composer_vorschau({k: daten[k] for k in
                ('prompt_typ', 'modus', 'realismus', 'schreibmodell', 'hinweise', 'material', 'materialien', 'kontexte')
                if k in daten} | {'text': f['text'], 'basis': {'id': d['id'], 'fassung': f['name'], 'stand': f['stand']},
                'ablage': d['herkunft'], 'ziele': [ziel], 'schaerfen_aktion': daten.get('schaerfen_aktion', 'Schärfen')})
            z = v['ziele'][0]
            return {'auftrag': z['auftrag'], 'gesendet_stand': z['gesendet_stand'], 'fassung': f,
                    'eingaben': z['eingaben'], 'schreibmodell': dict(v['schreibmodelle'][0], verfuegbar=True, grund='',
                    geschaetzt=v['laeufe'][0]['geschaetzt'], reserve=v['laeufe'][0]['reserve']), 'zielmodell': z['zielmodell']}
        aktion = daten.get('schaerfen_aktion', 'Schärfen')
        if aktion not in AKTIONEN:
            raise ValueError('Unbekannte Schärfen-Aktion.')
        hinweise = daten.get('hinweise', '')
        if not isinstance(hinweise, str) or len(hinweise) > 2000:
            raise ValueError('Hinweise dürfen höchstens 2.000 Zeichen enthalten.')
        def profil(pid):
            p = next((p for p in self.auswertung.profile if p['id'] == pid), None)
            if not p:
                raise ValueError('Bitte Schreibmodell und Zielmodell wählen.')
            info = self.auswertung.profil_info(p)
            anbieter = self.auswertung.anbieter[p['anbieter']]
            # Das Zielmodell muss zum Überarbeiten nicht laufen; nur das Schreibmodell sendet.
            if info['verfuegbar']:
                kontext, quelle, modell = anbieter.kontext_geladen(p)
            else:
                kontext, quelle, modell = info.get('kontext'), 'Anbieter', p['modell']
            return dict(info, kontext=kontext, kontext_quelle=quelle, modell_tatsaechlich=modell,
                        verarbeitung='Cloud (' + anbieter.cloud + ')' if anbieter.cloud else 'lokal',
                        hinweis='ohne Werkzeuge' if p['anbieter'] == 'claude' else
                        'Sandbox nur lesend, kann Dateien lesen und Befehle ausführen, liest seine globale AGENTS.md mit'
                        if p['anbieter'] == 'codex' else '')
        skill = skill_lesen(self.cfg)
        schreibmodell = profil(daten.get('schreibmodell'))
        schreibmodell.update(verfuegbar=schreibmodell['prompts_verfuegbar'], grund=schreibmodell['prompts_grund'])
        ziel = profil(daten.get('zielmodell'))
        material = self._antwortmaterial(d['id'], daten.get('material'))
        eingaben = {'hinweise': hinweise, 'skill': skill, 'material': material,
                    'zielmodell': {k: ziel.get(k) for k in ('name', 'anbieter', 'modell', 'kontext', 'verarbeitung')},
                    'aktion': aktion}
        text, gs = schaerfen_bauen(f, eingaben)
        if schreibmodell['verfuegbar']:
            schaetzung, reserve = kontext_pruefen(text, schreibmodell['kontext'])
            schreibmodell.update(geschaetzt=schaetzung, reserve=reserve)
        return {'auftrag': text, 'gesendet_stand': gs, 'fassung': f, 'eingaben': eingaben,
                'schreibmodell': schreibmodell, 'zielmodell': ziel}

    def schaerfen(self, daten):
        with _SPERRE:
            v = self.schaerfen_vorschau(daten)
            if v['gesendet_stand'] != daten.get('gesendet_stand'):
                raise Konflikt('Der Inhalt hat sich seit der Vorschau geändert.')
            p, f, e = v['schreibmodell'], v['fassung'], v['eingaben']
            if not p['verfuegbar']:
                raise PromptFehler('anbieter', p['grund'])
            d = self.lesen(daten['id'])
            tests = self._testordner(d['id'])
            ordner = os.path.join(os.path.dirname(tests), 'schaerfen')
            if not pfad_erlaubt(ordner, [self.ordner]):
                raise ValueError('Schärfen-Ordner nicht erlaubt.')
            kopf = dict(prompt=d['titel'], eintrag=d['id'], herkunft=d['herkunft'], fassung=f['name'],
                        fassung_stand=f['stand'], rahmen='nein', gesendet_stand=v['gesendet_stand'],
                        auswerter=p['name'], anbieter=p['anbieter'], modell=p['modell'],
                        kontext=p['kontext'], kontext_quelle=p['kontext_quelle'], verarbeitung=p['verarbeitung'],
                        zustand='wartet', meldung='', erstellt=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        hinweis='', status='Entwurf, automatisch erstellt, nicht geprüft', aktion=e['aktion'],
                        skill_stand=e['skill']['stand'], zielmodell=e['zielmodell']['name'],
                        zielmodell_anbieter=e['zielmodell']['anbieter'], zielmodell_modell=e['zielmodell']['modell'],
                        zielmodell_kontext=e['zielmodell']['kontext'])
            if p.get('stufe'):
                kopf['denkstufe'] = p['stufe']
            datei = schaerfen_anlegen(ordner, kopf, f['text'], e)
            a = self.auftrag_aus_beleg(d['id'], os.path.basename(datei), 'schaerfen')
        self.auswertung.einreihen(a)
        return {'neu': 1, 'auftraege': [a['id']]}

    def auftrag_aus_beleg(self, eid, datei, art_ordner='tests'):
        import secrets
        import time
        pfad = self.beleg_pfad(eid, datei, art_ordner)
        b = schaerfen_lesen(pfad) if art_ordner == 'schaerfen' else beleg_lesen(pfad)
        p = next((p for p in self.auswertung.profile if p['name'] == b['auswerter']
                  and p['anbieter'] == b['anbieter'] and p['modell'] == b['modell']
                  and p.get('stufe') == b.get('denkstufe')), None)
        p = p or {'id': '', 'name': b['auswerter'], 'anbieter': b['anbieter'], 'modell': b['modell'],
                  'stufe': b.get('denkstufe')}
        gruppenfelder = {k: b[k] for k in ('auftragsgruppe', 'zielprofil_id', 'zielschluessel',
                        'testprofil_id', 'ergebnis_fassung') if k in b}
        # Die Kennung geht in Dateinamen (z. B. codex-<id>.txt): nur die selbst vergebene Hexform übernehmen.
        aid = b.get('auftrags_id')
        aid = aid if isinstance(aid, str) and re.fullmatch(r'[0-9a-f]{8,16}', aid) else secrets.token_hex(4)
        return {'id': aid, 'art': 'schaerfen' if art_ordner == 'schaerfen' else 'prompt',
                'titel': b['prompt'], 'auswerter': dict(p),
                'prompt': {'eintrag': eid, 'herkunft': b['herkunft'], 'titel': b['prompt'],
                           'fassung': b['fassung'], 'stand': b['fassung_stand'], 'beleg': datei[:-3],
                           'gesendet_stand': b['gesendet_stand'], 'art_ordner': art_ordner, **gruppenfelder}, 'datei': pfad,
                'zustand': 'wartet', 'meldung': '', 'erstellt': time.time()}

    def datei_inhalt(self, eid, was, datei):
        if was == 'schaerfen':
            pfad = self.beleg_pfad(eid, datei, 'schaerfen')
            b = schaerfen_lesen(pfad)
            a = schaerfen_anzeige(b)
            k = a['kasten']
            auftrag, gs = schaerfen_bauen({'name': b['fassung'], 'text': b['fassung_text']}, b['eingaben'])
            return dict(b, text=_lesen(pfad), original=b['fassung_text'], neue_fassung=k['text'] if k and not a['grund'] else '',
                        auftrag=auftrag, auftrag_stand=gs, prompt_typ_erkannt=a['prompt_typ_erkannt'],
                        typ_anzeige=a['typ_anzeige'],
                        stichpunkte=a['stichpunkte'], neue_platzhalter=a['neue_platzhalter'], grund=a['grund'],
                        **({k: a[k] for k in ('fragenliste', 'fragen_grund')} if 'fragenliste' in a else {}),
                        **({'rueckfragen': b['eingaben']['rueckfragen']} if 'rueckfragen' in b['eingaben'] else {}),
                        fragen=b['antwort'] if b['eingaben']['aktion'] == 'Erst klären' else '')
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

    def _gecacht(self, pfad, lesen, zusaetzlich=None):
        s = os.stat(pfad)
        schluessel = (s.st_mtime_ns, s.st_size)
        if zusaetzlich:
            try:
                h = os.stat(zusaetzlich)
                schluessel += (h.st_mtime_ns, h.st_size)
            except FileNotFoundError:
                schluessel += (None, None)
        alt = self._cache.get(pfad)
        if not alt or alt[0] != schluessel:
            alt = (schluessel, lesen())
            self._cache[pfad] = alt
        # Aufrufer ergänzen Anzeigeinformationen, nie den zwischengespeicherten Wert.
        import copy
        return copy.deepcopy(alt[1])

    def _belege(self, ordner, art_ordner='tests'):
        tests = self._pfad(ordner, art_ordner)
        ergebnis = []
        if os.path.isdir(tests):
            for name in sorted(os.listdir(tests), reverse=True):
                if not name.lower().endswith('.md'):
                    continue
                try:
                    pfad = self._pfad(ordner, art_ordner, name)
                    def lesen():
                        _, _, kopf, ks = _belegkopf(_lesen(pfad))
                        try:
                            b = schaerfen_lesen(pfad) if art_ordner == 'schaerfen' else beleg_lesen(pfad)
                            kopf['antwort_vorhanden'] = bool(b['antwort'].strip())
                            if art_ordner == 'schaerfen':
                                a = schaerfen_anzeige(b)
                                kopf['ergebnis_gueltig'] = bool(a['kasten']) and not a['grund']
                                kopf['prompt_typ_erkannt'] = a['prompt_typ_erkannt'] if kopf['ergebnis_gueltig'] else None
                                if b['eingaben']['aktion'] == 'Rückfragen' and not a['grund']:
                                    kopf['fragen_anzahl'] = len(a['fragenliste'])
                                    kopf['fragen_hash'] = sha(json.dumps(a['fragenliste'], ensure_ascii=False,
                                                                       sort_keys=True, separators=(',', ':')))
                                if kopf.get('ergebnis_fassung') and a['kasten']:
                                    kopf['ergebnis_stand'] = stand(a['kasten']['text'])
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
                    d = self._gecacht(pfad, lambda: Eintrag(pfad).lesen(), self._pfad(name, 'herkunft.json'))
                except (OSError, ValueError, UnicodeError):
                    d = {'titel': name, 'fehler': 'nicht lesbar', 'bearbeitbar': False, 'fassungen': []}
                d.update(id=name, herkunft='ordner', tests=self._belege(name), schaerfen=self._belege(name, 'schaerfen'))
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
            d.setdefault('schaerfen', [])
            staende = {f['stand'] for f in d['fassungen']}
            for t in d['tests']:
                t['geaendert'] = t.get('fassung_stand') not in staende
            for b in d['schaerfen']:
                if b.get('ergebnis_fassung'):
                    f = next((f for f in d['fassungen'] if f['name'] == b['ergebnis_fassung']), None)
                    ergebnis_stand = b.pop('ergebnis_stand', None)
                    b['ergebnis_fehlt'] = f is None
                    b['ergebnis_geaendert'] = f is not None and ergebnis_stand != f['stand']
            d['getestet'] = bool(d['tests'])
            f = next((f for f in d['fassungen'] if f['name'] == d.get('bevorzugt')),
                     next(iter(d['fassungen']), {}))
            zeile = next((z for z in f.get('text', '').splitlines() if z.strip()), '')
            d['kurztext'] = ' '.join(zeile.split())[:180]
            gruppen = {}
            for b in reversed(d['schaerfen']):
                if b.get('auftragsgruppe'):
                    gruppen.setdefault(b['auftragsgruppe'], []).append(b)
            d['auftragsgruppen'] = sorted([{'id': gid, 'ergebnisse': bs} for gid, bs in gruppen.items()],
                key=lambda g: (min(b.get('erstellt', '') for b in g['ergebnisse']), g['id']))
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
            schaerfen = self._belege(ordner, 'schaerfen')
            if ziel:
                ziel['tests'] = tests
                ziel['schaerfen'] = schaerfen
                ziel['schatten'] = name
                ziel['hinweis'] = ('seit dem Test geändert' if ziel['fassungen'][0]['stand'] != meta['stand'] else '')
                if meta.get('nummer') != ziel['nummer']:
                    meta['nummer'] = ziel['nummer']
                    self._meta_schreiben(name, meta)
            else:
                ergebnis.append({'id': 'schatten:' + name, 'titel': meta.get('ueberschrift', name),
                                 'herkunft': 'sammlung', 'fassungen': [], 'tests': tests, 'schaerfen': schaerfen,
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
        if aktion in ('vorschau', 'testen', 'schaerfen_vorschau', 'schaerfen',
                      'composer_vorschau', 'composer_senden', 'composer_status',
                      'material_pruefen', 'material_datei_lesen', 'kontext_lesen', 'kontext_neu', 'kontext_speichern'):
            return getattr(self, aktion)(daten)
        if aktion == 'material_datei_waehlen':
            from werkstatt.quellen import textdatei_waehlen
            pfade = textdatei_waehlen()
            return self.material_datei_lesen({'pfad': pfade[0]}) if pfade else {'abgebrochen': True}
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
            a = self.auftrag_aus_beleg(eid, daten.get('datei'), daten.get('art_ordner', 'tests'))
            with self.auswertung._lock:
                if any(os.path.normcase(x.get('datei') or '') == os.path.normcase(a['datei'])
                       for x in self.auswertung.liste if x.get('art') in ('prompt', 'schaerfen')):
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
            e.fassung_neu(daten.get('name', ''), daten.get('text', ''))
        elif aktion == 'fassung_bearbeitet':
            name = e.fassung_bearbeitet(self._anfrage_id(daten), daten.get('von_fassung'),
                                       daten.get('von_stand'), daten.get('text'))
            return dict(self.lesen(eid), neue_fassung=name)
        elif aktion == 'bevorzugt':
            e.bevorzugt(daten.get('name'), daten.get('kopf_stand'))
        else:
            raise ValueError('Unbekannte Aktion.')
        return self.lesen(eid)
