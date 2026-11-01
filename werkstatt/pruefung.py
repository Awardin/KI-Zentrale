"""Automatische Nachprüfung einer Zusammenfassung ohne Netz und ohne Modell.

Geprüft werden Zeitmarken gegen das Transkript, die Abdeckung in Fünf-Minuten-Fenstern
und fremde Schriftzeichen (Chinesisch, Japanisch, Koreanisch). Das Ergebnis ist ein
kurzer Block für die Fassung und eine Kurzfassung für den Dateikopf.
"""
import re

# [hh:mm:ss] und [mm:ss]; Zeitbereiche enthalten einfach zwei Marken.
MARKE = re.compile(r'\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]')
_CJK = re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]')
FENSTER_S = 300
WOERTER_JE_FENSTER = 60
TOLERANZ_S = 5


def _sekunden(m):
    a, b, c = m.groups()
    return int(a) * 60 + int(b) if c is None else int(a) * 3600 + int(b) * 60 + int(c)


def _marken(text):
    return [(m.group(0), _sekunden(m)) for m in MARKE.finditer(text or '')]


def _abschnitte(transkript):
    """[(Sekunde, Text bis zur nächsten Marke)] des Transkripts mit Zeitmarken."""
    marken = list(MARKE.finditer(transkript or ''))
    return [(_sekunden(m), (transkript or '')[m.end():marken[i + 1].start() if i + 1 < len(marken) else None])
            for i, m in enumerate(marken)]


def _bereiche(fenster):
    """Zusammenhängende Fenster als „Minute 5–10“; ein Fenster ist fünf Minuten breit."""
    bereiche = []
    for i in fenster:
        if bereiche and i == bereiche[-1][1] + 1:
            bereiche[-1][1] = i
        else:
            bereiche.append([i, i])
    return [f'Minute {a * 5}–{(b + 1) * 5}' for a, b in bereiche]


def _abdeckung(transkript, letzte, gueltige):
    """Fenster mit mindestens 60 Wörtern, in denen keine gültige Ergebnis-Zeitmarke liegt."""
    if letzte is None:
        return []
    anzahl = letzte // FENSTER_S + 1
    woerter = [0] * anzahl
    for sekunde, text in _abschnitte(transkript):
        i = sekunde // FENSTER_S
        if 0 <= i < anzahl:
            woerter[i] += len(text.split())
    belegt = {s // FENSTER_S for s in gueltige if s < anzahl * FENSTER_S}
    return _bereiche([i for i in range(anzahl) if woerter[i] >= WOERTER_JE_FENSTER and i not in belegt])


def nachpruefen(text, transkript_mit_marken, mit_abdeckung):
    """Prüft einen Modelltext gegen das Transkript mit Zeitmarken.

    Rückgabe: Kennzahlen, der Block für die Fassung (`block`) und die Kurzfassung (`kurz`).
    """
    text = text or ''
    transkript_mit_marken = transkript_mit_marken or ''
    transkript_marken = sorted({s for _, s in _marken(transkript_mit_marken)})
    letzte = transkript_marken[-1] if transkript_marken else None
    ergebnis_marken = _marken(text)
    ungueltig, gueltige = [], []
    for roh, sekunde in ergebnis_marken:
        if (letzte is not None and sekunde <= letzte + TOLERANZ_S
                and any(abs(sekunde - t) <= TOLERANZ_S for t in transkript_marken)):
            gueltige.append(sekunde)
        else:
            ungueltig.append(roh)
    fehlend = _abdeckung(transkript_mit_marken, letzte, gueltige) if mit_abdeckung else None
    fremde = len(_CJK.findall(text))

    zeilen = ['---', '**Prüfung der Werkstatt (automatisch):**']
    if not ergebnis_marken:
        zeilen.append('- Zeitmarken: keine im Ergebnis')
    elif ungueltig:
        zeilen.append(f'- Zeitmarken: {len(ungueltig)} nicht im Transkript: ' + ', '.join(ungueltig[:10]))
    else:
        zeilen.append(f'- Zeitmarken: {len(ergebnis_marken)} geprüft, alle im Transkript.')
    if mit_abdeckung:
        if fehlend:
            zeilen.append('- Abdeckung: ohne Stichpunkt: ' + ', '.join(fehlend))
        else:
            zeilen.append('- Abdeckung: alle inhaltlichen Abschnitte haben Stichpunkte.')
    if fremde:
        zeilen.append(f'- Fremde Schriftzeichen: {fremde} Stellen – ‚Wiederholen‘ empfohlen')
    else:
        zeilen.append('- Fremde Schriftzeichen: keine.')

    hinweise = []
    if ungueltig:
        hinweise.append(f'{len(ungueltig)} Zeitmarke' if len(ungueltig) == 1 else f'{len(ungueltig)} Zeitmarken')
    if fehlend:
        hinweise += fehlend
    if fremde:
        hinweise.append('fremde Schriftzeichen')
    return {'zeitmarken_geprueft': len(ergebnis_marken), 'zeitmarken_ungueltig': ungueltig,
            'keine_zeitmarke': not ergebnis_marken, 'abdeckung_fehlt': fehlend,
            'fremde_schriftzeichen': fremde, 'block': '\n'.join(zeilen),
            'kurz': 'in Ordnung' if not hinweise else 'Hinweise: ' + ', '.join(hinweise)}
