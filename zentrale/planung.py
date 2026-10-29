"""Entscheidet, was weichen muss, damit ein Modell auf die Karten passt.

Reine Logik ohne Systemzugriff. Ein "Verbraucher" ist alles, was gerade
Grafikspeicher belegt:
    {'eintrag': 'ninfer' | None, 'name': str, 'mib_je_karte': {0: 21800},
     'schritt': {'id': 'beenden:ninfer', 'text': '...'} | None,   # None = nicht von uns freigebbar
     'blockiert': str | None}                                      # Grund, warum es gerade nicht geht

Ein Eintrag braucht Platz auf eine von drei Arten:
    bedarf_mib          {karte: MiB} auf festen Karten (Strata: beide Karten)
    karten + bedarf_je_karte_mib   eine beliebige passende Karte, die Zentrale wählt (NInfer, LightOnOCR, ComfyUI)
    bedarf_gesamt_mib   MiB auf allen Karten zusammen, das Programm verteilt selbst (Ollama)
"""
from gemeinsam.gpu import kurznamen  # noqa: F401  (Anzeigenamen; hier für Zentrale und Tests)

VARIANTE_META = ('id', 'name', 'standard')


def variante(e, vid=None):
    """Eintrag mit den Angaben einer Variante (z. B. Kontextgröße), sonst der Standardvariante.

    Eine Variante überschreibt Felder des Eintrags (`bedarf_gesamt_mib`, `ollama_optionen`, `konfig` …).
    Ohne `varianten` bleibt der Eintrag unverändert. Eine unbekannte Variante ist ein ValueError.
    """
    liste = e.get('varianten') or []
    if not liste:
        if vid:
            raise ValueError(f"{e['name']} hat keine Varianten.")
        return e
    if vid:
        v = next((x for x in liste if x['id'] == vid), None)
        if v is None:
            raise ValueError(f"Unbekannte Variante: {vid}")
    else:
        v = next((x for x in liste if x.get('standard')), liste[0])
    return dict(e, **{k: w for k, w in v.items() if k not in VARIANTE_META}, variante=v['id'],
                variante_name=v['name'])


def startbedarf(e):
    """Eintrag so, wie er zum Starten Platz braucht.

    Ein Dienst wie ComfyUI belegt nach dem Start fast nichts; Platz für die eigentliche Arbeit meldet jeder Auftrag
    vorher selbst an (`/api/platz`). `start_bedarf_je_karte_mib` und `start_karten` ersetzen dann beim Starten
    `bedarf_je_karte_mib` und `karten` (29.10.2026: ComfyUI ließ sich neben Strata nicht starten, obwohl Bilder auf
    der RTX 3080 rechnen). Ohne diese Felder bleibt der Eintrag unverändert.
    """
    neu = {}
    if 'start_bedarf_je_karte_mib' in e:
        neu['bedarf_je_karte_mib'] = e['start_bedarf_je_karte_mib']
    if 'start_karten' in e:
        neu['karten'] = e['start_karten']
    return dict(e, **neu) if neu else e


def wunschkarten(karten, wunsch):
    indizes = []
    for name in wunsch:
        for k in sorted(karten, key=lambda k: k['index']):
            if name.casefold() in (k.get('name') or '').casefold() and k['index'] not in indizes:
                indizes.append(k['index'])
    return indizes


def karte_waehlen(karten, verbraucher, ziel, reserve_mib, monitor_puffer_mib=0):
    """Karte für einen Eintrag, der auf jede passende Karte darf (`karten`: Namen wie „RTX 3090“).

    Passt er ohne Freigabe auf mehrere Karten, nimmt er die engste: Kleine Modelle teilen sich eine Karte, und auf der
    anderen bleibt Platz für große. Eine Nebenkarte (langsam angebunden, `nebenkarte`) bekommt dabei den Vorzug vor
    allen anderen. Die Karte mit dem Monitor füllt er nur, wenn dort danach noch `monitor_puffer_mib`
    frei bleiben (Windows braucht dort schwankend Speicher) oder keine andere Karte passt.
    Passt er nirgends, nimmt er die Karte, auf der am wenigsten weichen muss.
    Bei Gleichstand zählt die Reihenfolge der Namen, dann die Kartennummer.
    """
    indizes = wunschkarten(karten, ziel['karten'])
    if not indizes:
        return None, f"Keine der Karten {', '.join(ziel['karten'])} ist erkannt."
    frei = {k['index']: k['gesamt'] - k['belegt'] for k in karten}
    bedarf = ziel['bedarf_je_karte_mib'] + reserve_mib
    monitor = {k['index'] for k in karten if k.get('monitor')}
    neben = {k['index']: bool(k.get('nebenkarte')) for k in karten}
    passend = [i for i in indizes if frei[i] >= bedarf]
    if passend:
        return min(passend, key=lambda i: (not neben.get(i), i in monitor and frei[i] - bedarf < monitor_puffer_mib,
                                           frei[i], indizes.index(i))), None

    def aufwand(i):
        plan = plan_fuer_start(karten, verbraucher, dict(ziel, bedarf_mib={i: ziel['bedarf_je_karte_mib']}),
                               reserve_mib)
        weg = {s['id'] for s in plan['schritte']}
        mib = sum(_summe(v) for v in verbraucher if v.get('schritt') and v['schritt']['id'] in weg)
        return (not plan['genug_platz'], len(weg), mib, indizes.index(i))
    return min(indizes, key=aufwand), None


def _summe(v, karten=None):
    return sum(m for i, m in v['mib_je_karte'].items() if karten is None or i in karten)


def _plan_gesamt(karten, verbraucher, ziel, reserve_mib):
    """Ollama verteilt ein Modell selbst auf die Karten: Es zählt der freie Platz aller Karten zusammen.

    Bei `gesamt_karten` zählen nur Karten, deren gemessener Name einen dieser Namen enthält (wie `wunschkarten`);
    ohne das Feld alle Karten. Reicht es, ein einziges Modell freizugeben, wird das kleinste passende genommen,
    sonst die größten zuerst. `bedarf_mib` ist die geschätzte Verteilung (nach freiem Platz) für die Vorschau.
    """
    gesamt = ziel['bedarf_gesamt_mib']
    zaehlend = set(wunschkarten(karten, ziel['gesamt_karten'])) if ziel.get('gesamt_karten') else None
    frei = {k['index']: k['gesamt'] - k['belegt'] - reserve_mib for k in karten
            if zaehlend is None or k['index'] in zaehlend}

    def summe(v):
        return _summe(v, zaehlend)

    def fehlt(frei):
        return gesamt - sum(max(0, m) for m in frei.values())
    kandidaten = [v for v in verbraucher if v.get('eintrag') != ziel['id'] and v.get('schritt') and summe(v) > 0]
    gruende = [v['blockiert'] for v in kandidaten if v.get('blockiert')]
    kandidaten = [v for v in kandidaten if not v.get('blockiert')]

    def ohne(frei, v):
        return {i: m + v['mib_je_karte'].get(i, 0) for i, m in frei.items()}
    schritte = []
    if fehlt(frei) > 0:
        einzeln = sorted((v for v in kandidaten if fehlt(ohne(frei, v)) <= 0), key=summe)
        for v in einzeln[:1] or sorted(kandidaten, key=lambda v: -summe(v)):
            if fehlt(frei) <= 0:
                break
            schritte.append(v['schritt'])
            frei = ohne(frei, v)
    rest = fehlt(frei)
    platz = sum(max(0, m) for m in frei.values()) or 1
    bedarf = {i: round(gesamt * m / platz) for i, m in frei.items() if m > 0}
    hinweise = []
    if rest > 0:
        belegt_von = [v['name'] for v in verbraucher if summe(v) >= 256 and (not v.get('schritt') or v.get('blockiert'))]
        hinweise.append({'karte': None, 'fehlend_mib': round(rest), 'belegt_von': belegt_von})
    return {'schritte': schritte, 'genug_platz': rest <= 0, 'hinweise': hinweise,
            'gruende': gruende if rest > 0 else [], 'bedarf_mib': bedarf}


def plan_fuer_start(karten, verbraucher, ziel, reserve_mib):
    """Welche Verbraucher müssen weichen, damit `ziel` (mit bedarf_mib je Karte) passt?

    Wählt so wenige Verbraucher wie nötig, die größten zuerst. Mit `bedarf_gesamt_mib` zählen alle Karten zusammen.
    """
    if 'bedarf_gesamt_mib' in ziel:
        return _plan_gesamt(karten, verbraucher, ziel, reserve_mib)
    frei = {k['index']: k['gesamt'] - k['belegt'] for k in karten}
    bedarf = {int(i): m for i, m in ziel['bedarf_mib'].items()}
    fehlend = {i: bedarf[i] + reserve_mib - frei.get(i, 0) for i in bedarf}
    fehlend = {i: m for i, m in fehlend.items() if m > 0}
    schritte, gruende = [], []
    kandidaten = [v for v in verbraucher
                  if v.get('eintrag') != ziel['id'] and v.get('schritt') and _summe(v, fehlend) > 0]
    kandidaten.sort(key=lambda v: -_summe(v, fehlend))
    for v in kandidaten:
        if not fehlend:
            break
        if v.get('blockiert'):
            gruende.append(v['blockiert'])
            continue
        schritte.append(v['schritt'])
        for i in list(fehlend):
            fehlend[i] -= v['mib_je_karte'].get(i, 0)
            if fehlend[i] <= 0:
                del fehlend[i]
    hinweise = []
    for i, m in sorted(fehlend.items()):
        belegt_von = [v['name'] for v in verbraucher
                      if v['mib_je_karte'].get(i, 0) >= 256 and (not v.get('schritt') or v.get('blockiert'))]
        hinweise.append({'karte': i, 'fehlend_mib': m, 'belegt_von': belegt_von})
    return {'schritte': schritte, 'genug_platz': not fehlend, 'hinweise': hinweise, 'gruende': gruende}


def plan_freigeben(verbraucher):
    """Alles, was die Zentrale selbst freigeben darf, und was sie bewusst nicht anfasst."""
    schritte = [dict(v['schritt'], mib=_summe(v)) for v in verbraucher if v.get('schritt') and not v.get('blockiert')]
    gruende = [v['blockiert'] for v in verbraucher if v.get('schritt') and v.get('blockiert')]
    unberuehrt = [{'name': v['name'], 'mib': _summe(v)} for v in verbraucher
                  if not v.get('schritt') and _summe(v) >= 256]
    return {'schritte': schritte, 'gruende': gruende, 'unberuehrt': unberuehrt}


def schritte_gueltig(gesendet, plan):
    """Die vom Nutzer bestätigten Schritt-IDs müssen noch zum aktuellen Plan gehören."""
    aktuell = {s['id'] for s in plan['schritte']}
    return all(sid in aktuell for sid in gesendet)


# ---------------------------------------------------------------- Anmeldungen anderer Apps

def angemeldet_rest(reservierungen, verbraucher):
    """Noch nicht belegter Teil der Anmeldungen je Karte.

    Eine Anmeldung der Werkstatt gilt, bis ihr Programm den Speicher wirklich belegt. Was es seit der Anmeldung
    zusätzlich belegt, wird abgezogen, damit nichts doppelt zählt. Das Programm nennt `schluessel` (Verbraucher der
    Erfassung, ohne Angabe die Transkription); `basis` ist seine Belegung bei der Anmeldung (ohne Angabe 0).
    Seit 16.10.2026 (ohne GPU-Sperre) auch für Studio-Aufträge: `schluessel` „bild-video“, Basis = ComfyUI vorher.
    Je Verbraucher gilt die Basis der ältesten Anmeldung (fehlt eine Karte in ihr, zählt 0); der Zuwachs seitdem wird
    den Anmeldungen der Reihe nach (nach `seit`) angerechnet, damit zwei gleichzeitige Anmeldungen desselben
    Verbrauchers nichts doppelt abziehen (Astra, 16.10.2026). Seit Stufe 8 hat jeder ComfyUI-Prozess einen eigenen
    Schlüssel („bild-video“, „bild-video-<nr>“) und je Prozess läuft höchstens ein Auftrag.
    """
    gemessen = {}
    for v in verbraucher:
        g = gemessen.setdefault(v.get('schluessel'), {})
        for i, m in v['mib_je_karte'].items():
            g[int(i)] = g.get(int(i), 0) + m
    gruppen = {}
    for r in sorted(reservierungen, key=lambda r: r.get('seit', 0)):
        gruppen.setdefault(r.get('schluessel') or 'transkription', []).append(r)
    rest = {}
    for schluessel, liste in gruppen.items():
        basis = {int(i): m for i, m in (liste[0].get('basis') or {}).items()}
        karten = {int(i) for r in liste for i in r['bedarf_mib']}
        zuwachs = {i: max(0, gemessen.get(schluessel, {}).get(i, 0) - basis.get(i, 0)) for i in karten}
        for r in liste:
            for i, m in r['bedarf_mib'].items():
                i = int(i)
                angerechnet = min(m, zuwachs[i])
                zuwachs[i] -= angerechnet
                if m - angerechnet > 0:
                    rest[i] = rest.get(i, 0) + m - angerechnet
    return rest


def mit_anmeldungen(karten, verbraucher, rest, name, farbe, eintrag=None):
    """Karten und Verbraucher so, als wären die Anmeldungen schon belegt.

    `eintrag` ordnet den Verbraucher einem Eintrag zu (z. B. die Reserve eines laufenden python_dienst); beim
    Planen dieses Eintrags selbst wird er dann nicht als Hindernis behandelt.
    """
    if not rest:
        return karten, verbraucher
    karten = [dict(k, belegt=k['belegt'] + rest.get(k['index'], 0)) for k in karten]
    verbraucher = verbraucher + [{'eintrag': eintrag, 'schluessel': 'angemeldet', 'name': name, 'farbe': farbe,
                                  'mib_je_karte': dict(rest), 'blockiert': None, 'schritt': None}]
    return karten, verbraucher


def platz_pruefen(karten, verbraucher, bedarf, reserve_mib):
    """Ist `bedarf` ({karte: MiB}) frei? Karten und Verbraucher schon mit Anmeldungen."""
    frei = {k['index']: round(k['gesamt'] - k['belegt'] - reserve_mib) for k in karten}
    hinweise = []
    for i, m in sorted(bedarf.items()):
        fehlt = m - frei.get(i, 0) if i in frei else m
        if fehlt > 0:
            belegt_von = [v['name'] for v in verbraucher if v['mib_je_karte'].get(i, 0) >= 256]
            hinweise.append({'karte': i, 'fehlend_mib': round(fehlt), 'belegt_von': belegt_von})
    return {'frei_mib': frei, 'genug': not hinweise, 'hinweise': hinweise}
