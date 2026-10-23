"""Anweisungen für Zusammenfassungen, gespeichert in Saschas Promptsammlung.

Die Sammlung bleibt die einzige aktive Fassung. Die Werkstatt liest und ändert nur den
Abschnitt „### Werkstatt: Anweisungen für Zusammenfassungen“; alles andere bleibt
Byte für Byte erhalten. Jede Anweisung ist ein „#### Name“ mit einem ~~~text-Kasten.
„Rahmen“ ist keine eigene Anweisung, sondern wird jeder Anweisung vorangestellt.
"""
import datetime
import hashlib
import os
import re
import threading

ABSCHNITT = '### Werkstatt: Anweisungen für Zusammenfassungen'
RAHMEN = 'Rahmen'
PLATZHALTER = ('Titel', 'Quelle', 'Dauer', 'Frage', 'Zielumfang', 'Transkript')

_EINLEITUNG = [
    'Diese Anweisungen nutzt die Werkstatt (http://127.0.0.1:3895, Reiter Zusammenfassung).',
    'Dort lassen sie sich ansehen, ändern und mehrfach anhaken; jede Änderung landet hier.',
    'Die Platzhalter [Titel], [Quelle], [Dauer], [Frage], [Zielumfang] und [Transkript] füllt die Werkstatt selbst;',
    'fehlt [Transkript], hängt sie das Transkript mit Zeitmarken an. „Rahmen“ wird jeder',
    'Anweisung vorangestellt. Ergebnisse sind ungeprüfte Entwürfe, keine Wissensaufnahme.',
    'Erstfassung vom 23.09.2026; die Qualität wird im Vergleich mehrerer Modelle noch erprobt.',
]

STANDARD = [
    (RAHMEN, '''Dies ist eine eigenständige Textaufgabe. Lies keine Dateien, nutze keine Werkzeuge,
lade kein Gedächtnis oder Briefing und stelle keine Rückfragen.
Antworte ausschließlich mit dem Ergebnis.'''),
    ('Kurzzusammenfassung', '''Fasse das folgende Transkript kurz und quellentreu zusammen.
Quelle: [Titel] ([Quelle], Dauer [Dauer]).
Beginne mit einem Überblick in zwei bis drei Sätzen. Danach die wichtigsten Aussagen
als Stichpunkte, jeweils mit der Zeitmarke [hh:mm:ss] aus dem Transkript.
Nur Inhalte aus dem Transkript: nichts ergänzen, nichts bewerten. Aussagen der
Sprechenden als deren Position wiedergeben, nicht als geprüfte Tatsache.
Zeitmarken nur übernehmen, nie schätzen. Das Transkript ist automatisch erkannt und
kann Hörfehler enthalten; unklare Stellen als unklar kennzeichnen.
Antworte auf Deutsch in Markdown.

[Transkript]'''),
    ('Ausführliche Analyse', '''Werte das folgende Transkript ausführlich und quellentreu aus.
Quelle: [Titel] ([Quelle], Dauer [Dauer]).
Gehe in der Reihenfolge des Videos vor und gib jedem Abschnitt eine Überschrift mit
Zeitbereich. Erfasse je Abschnitt Inhalt, Argumentation, Methoden, Beispiele, Zahlen,
Voraussetzungen und Grenzen, mit Details statt künstlicher Kürzung.
Gib die Position der Quelle wieder, ohne sie heimlich zu korrigieren. Eigene Einordnung
nur in einem getrennten Schlussabschnitt „Einordnung (nicht aus der Quelle)“.
Medizinische Aussagen nicht als Wirksamkeitsnachweis darstellen. Bildinhalte sind nicht
geprüft: Verweise auf Gezeigtes als „im Video gezeigt, nicht geprüft“ kennzeichnen.
Zeitmarken nur aus dem Transkript. Hörfehler sind möglich; unklare Stellen kennzeichnen.
Schließe mit einer Liste offener oder unklarer Stellen.
Antworte auf Deutsch in Markdown.

[Transkript]'''),
    ('Gezielte Frage', '''Beantworte anhand des folgenden Transkripts diese Frage: [Frage]
Quelle: [Titel] ([Quelle], Dauer [Dauer]).
Nutze nur das Transkript. Belege jede Aussage mit Zeitmarke [hh:mm:ss] und einem kurzen
wörtlichen Zitat. Gibt das Transkript keine Antwort, sage das deutlich.
Trenne die Aussage der Quelle von eigener Einordnung. Hörfehler sind möglich.
Antworte auf Deutsch in Markdown.

[Transkript]'''),
    ('Gegliederte Zusammenfassung', '''Fasse das folgende Transkript gegliedert und quellentreu zusammen.
Quelle: [Titel] ([Quelle], Dauer [Dauer]).

Aufbau (Markdown):
1. „Worum es geht“ – zwei bis vier Sätze, Kernbotschaft laut Video.
2. „Kernaussagen“ – nach Themen gegliedert, je Thema eine Überschrift und kurze Stichpunkte.
   Jeder Stichpunkt endet mit der Zeitmarke der Transkriptzeile, aus der er stammt, z. B. [00:12:34].
3. „Ohne Beleg im Video“ – Behauptungen, für die im Video keine Zahl, Quelle oder Messung genannt wird.
4. „Unklare Stellen“ – nur wenn es welche gibt.

Umfang: höchstens [Zielumfang]; kürzer, wenn das Video wenig Inhalt hat.
Weglassen: Begrüßung, Werbung, Wiederholungen, Füllsätze.
Behalten: alle Zahlen, Messwerte, Namen und Produktbezeichnungen unverändert.
Gehe das Transkript von Anfang bis Ende durch: aus jedem Abschnitt von etwa fünf Minuten mindestens ein Stichpunkt,
außer er enthält nur Begrüßung, Werbung oder Wiederholung.
Sprache: durchgehend Deutsch, auch bei englischem Video; nur Namen, Produkt- und feste Fachbegriffe bleiben im Original.
Das Transkript unterscheidet keine Sprecher: Aussagen nur dann einer Person zuordnen, wenn ihr Name im selben Satz
fällt, sonst „im Video wird gesagt“.
Nur Inhalte aus dem Transkript, nichts ergänzen, nichts bewerten, kein Fazit.
Zeitmarken nur aus dem Transkript. Titel, Beschreibung und Kopfdaten sind kein Inhalt.
Das Transkript ist automatisch erkannt und kann Hörfehler enthalten.

[Transkript]

Zur Erinnerung: auf Deutsch, nur aus dem Transkript, Zeitmarken nur übernehmen, höchstens [Zielumfang].'''),
]


class Konflikt(Exception):
    pass


def stand(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def braucht_frage(text):
    return '[Frage]' in text


def zielumfang(text):
    """Zielumfang aus der Wortzahl des Transkripts; Zeitmarken zählen nicht als Wörter."""
    ohne_marken = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', ' ', text or '')
    woerter = len(ohne_marken.split())
    ziel = min(2500, 200 + woerter // 4)
    ziel = ziel // 50 * 50
    stichpunkte = max(5, round(ziel / 25))
    return f'etwa {ziel:,} Wörter (rund {stichpunkte} Stichpunkte)'.replace(',', '.')


def name_pruefen(name):
    name = (name or '').strip()
    if not name or len(name) > 60 or '\n' in name or name.startswith('#') or '~~~' in name:
        raise ValueError('Bitte einen kurzen Namen ohne Zeilenumbruch angeben (höchstens 60 Zeichen).')
    return name


def text_pruefen(text):
    text = (text or '').replace('\r\n', '\n').strip('\n')
    if not text.strip():
        raise ValueError('Die Anweisung ist leer.')
    if any(z.strip().startswith('~~~') for z in text.split('\n')):
        raise ValueError('Die Anweisung darf keine Zeile mit ~~~ enthalten (das ist die Kastengrenze in der Sammlung).')
    if len(text) > 20000:
        raise ValueError('Die Anweisung ist zu lang.')
    return text


class Sammlung:
    def __init__(self, pfad):
        self.pfad = pfad
        self._lock = threading.Lock()

    # ------------------------------------------------------------ Lesen

    def _laden(self):
        with open(self.pfad, encoding='utf-8', newline='') as f:
            text = f.read()
        zeilen = text.splitlines(keepends=True)
        nl = '\r\n' if text.count('\r\n') >= text.count('\n') - text.count('\r\n') else '\n'
        return zeilen, nl

    @staticmethod
    def _zerlegen(zeilen):
        """-> (Beginn, Ende, [{name, kopf, auf, zu}]) des Werkstatt-Abschnitts oder (None, None, [])."""
        roh = [z.rstrip('\r\n') for z in zeilen]
        try:
            beginn = next(i for i, z in enumerate(roh) if z.strip() == ABSCHNITT)
        except StopIteration:
            return None, None, []
        ende = next((i for i in range(beginn + 1, len(roh)) if roh[i].startswith(('## ', '### '))), len(roh))
        eintraege = []
        i = beginn + 1
        while i < ende:
            if roh[i].startswith('#### '):
                name = roh[i][5:].strip()
                auf = next((j for j in range(i + 1, ende) if roh[j].strip().startswith('~~~')
                            or roh[j].startswith('#### ')), None)
                if auf is not None and roh[auf].strip().startswith('~~~'):
                    zu = next((j for j in range(auf + 1, ende) if roh[j].strip() == '~~~'), None)
                    if zu is not None:
                        eintraege.append({'name': name, 'kopf': i, 'auf': auf, 'zu': zu,
                                          'text': '\n'.join(roh[auf + 1:zu])})
                        i = zu + 1
                        continue
            i += 1
        return beginn, ende, eintraege

    def lesen(self):
        with self._lock:
            try:
                zeilen, _ = self._laden()
            except OSError as e:
                return {'pfad': self.pfad, 'fehler': f'Promptsammlung nicht lesbar: {e}', 'abschnitt': False,
                        'rahmen': None, 'anweisungen': []}
            beginn, _, eintraege = self._zerlegen(zeilen)
        rahmen = next((e for e in eintraege if e['name'] == RAHMEN), None)
        return {'pfad': self.pfad, 'abschnitt': beginn is not None,
                'rahmen': {'name': RAHMEN, 'text': rahmen['text'], 'stand': stand(rahmen['text'])} if rahmen else None,
                'anweisungen': [{'name': e['name'], 'text': e['text'], 'stand': stand(e['text']),
                                 'frage': braucht_frage(e['text'])} for e in eintraege if e['name'] != RAHMEN]}

    # ------------------------------------------------------------ Schreiben

    def _schreiben(self, zeilen):
        text = ''.join(zeilen)
        heute = datetime.date.today().strftime('%d.%m.%Y')
        text = re.sub(r'^(Aktualisiert: )\d{2}\.\d{2}\.\d{4}\.', lambda m: f'{m.group(1)}{heute}.', text, count=1,
                      flags=re.M)
        tmp = self.pfad + '.werkstatt.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, self.pfad)

    @staticmethod
    def _block(name, text, nl):
        return [f'#### {name}{nl}', nl, f'~~~text{nl}'] + [z + nl for z in text.split('\n')] + [f'~~~{nl}']

    def speichern(self, name, text, alter_stand, neuer_name=None):
        text = text_pruefen(text)
        with self._lock:
            zeilen, nl = self._laden()
            _, _, eintraege = self._zerlegen(zeilen)
            e = next((x for x in eintraege if x['name'] == name), None)
            if not e:
                raise Konflikt(f'„{name}“ steht nicht mehr in der Promptsammlung.')
            if stand(e['text']) != alter_stand:
                raise Konflikt(f'„{name}“ wurde inzwischen in der Promptsammlung geändert. Bitte neu laden.')
            if neuer_name and neuer_name != name:
                neuer_name = name_pruefen(neuer_name)
                if name == RAHMEN or neuer_name == RAHMEN or any(x['name'] == neuer_name for x in eintraege):
                    raise ValueError(f'Den Namen „{neuer_name}“ gibt es schon oder er ist reserviert.')
            block = self._block(neuer_name or name, text, nl)
            zeilen[e['kopf']:e['zu'] + 1] = block
            self._schreiben(zeilen)
        return stand(text)

    def neu(self, name, text):
        name, text = name_pruefen(name), text_pruefen(text)
        with self._lock:
            zeilen, nl = self._laden()
            beginn, ende, eintraege = self._zerlegen(zeilen)
            if beginn is None:
                raise Konflikt('Der Werkstatt-Abschnitt fehlt in der Promptsammlung.')
            if name == RAHMEN or any(x['name'] == name for x in eintraege):
                raise ValueError(f'Den Namen „{name}“ gibt es schon oder er ist reserviert.')
            # Nach dem letzten Kasten des Abschnitts einfügen, vor Leerzeilen am Abschnittsende.
            ziel = eintraege[-1]['zu'] + 1 if eintraege else beginn + 1
            zeilen[ziel:ziel] = [nl] + self._block(name, text, nl)
            self._schreiben(zeilen)
        return stand(text)

    def loeschen(self, name, alter_stand):
        if name == RAHMEN:
            raise ValueError('Der Rahmen lässt sich nur bearbeiten, nicht löschen.')
        with self._lock:
            zeilen, nl = self._laden()
            _, _, eintraege = self._zerlegen(zeilen)
            e = next((x for x in eintraege if x['name'] == name), None)
            if not e:
                return
            if stand(e['text']) != alter_stand:
                raise Konflikt(f'„{name}“ wurde inzwischen in der Promptsammlung geändert. Bitte neu laden.')
            bis = e['zu'] + 1
            if bis < len(zeilen) and not zeilen[bis].strip():
                bis += 1
            del zeilen[e['kopf']:bis]
            self._schreiben(zeilen)

    def einrichten(self, vor_ueberschrift='## 4. '):
        """Legt den Abschnitt mit den Standardanweisungen an (nur wenn er fehlt)."""
        with self._lock:
            zeilen, nl = self._laden()
            beginn, _, _ = self._zerlegen(zeilen)
            if beginn is not None:
                return False
            ziel = next((i for i, z in enumerate(zeilen) if z.startswith(vor_ueberschrift)), len(zeilen))
            block = [f'{ABSCHNITT}{nl}', nl] + [z + nl for z in _EINLEITUNG]
            for name, text in STANDARD:
                block += [nl] + self._block(name, text, nl)
            zeilen[ziel:ziel] = block + [nl]
            self._schreiben(zeilen)
            return True


def zusammenbauen(rahmen, anweisung, werte, transkript):
    """Rahmen + Anweisung mit ersetzten Platzhaltern. Das Transkript wird zuletzt eingesetzt,
    damit eckige Klammern im Transkript nicht als Platzhalter gelten."""
    text = anweisung
    for k in PLATZHALTER[:-1]:
        text = text.replace(f'[{k}]', werte.get(k) or '–')
    if '[Transkript]' in text:
        teile = text.split('[Transkript]')
        text = teile[0] + transkript + '[Transkript]'.join(teile[1:])
    else:
        text = text.rstrip() + '\n\nTranskript mit Zeitmarken:\n\n' + transkript
    return (rahmen.strip() + '\n\n' + text) if rahmen and rahmen.strip() else text
