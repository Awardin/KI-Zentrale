"""Kartenwahl für die Transkription und Nachfrage bei der Modellzentrale.

Die Werkstatt steuert die Zentrale nicht. Sie fragt, wie viel frei ist, wählt die
Karten und meldet ihren Bedarf an. Die Zentrale prüft und reserviert in einem
Schritt; hat sich die Belegung inzwischen geändert, lehnt sie ab (409).
"""
import json
import os
import urllib.error
import urllib.request

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def worker_noetig(dauer_s, abschnitt_s):
    """watch schneidet erst ab dem 1,25-fachen der Abschnittslänge; kürzere Quellen sind ein Abschnitt."""
    return 1 if dauer_s is not None and dauer_s <= abschnitt_s * 1.25 else 2


def verteilen(karten, bedarf_je_worker, worker, last_grenze=60):
    """Wählt Karten und Worker-Zahl nach freiem Speicher.

    `karten`: [{'index', 'kurz', 'frei', 'last'}], `frei` schon ohne Reserve und Anmeldungen.
    Zwei Karten nur, wenn jede Karte beide Worker tragen kann: watch verteilt die Abschnitte
    abwechselnd, und wenn ein Worker früher fertig ist, landet der nächste Abschnitt kurz auf
    derselben Karte wie der noch laufende.
    Eine stark ausgelastete Karte (rechnet gerade, z. B. ein Sprachmodell) kommt nur zum Zug,
    wenn die ruhigen Karten nicht reichen.
    -> {'gpu', 'gpus', 'worker', 'bedarf_mib', 'text'} oder None, wenn nichts passt.
    """
    ruhig = [k for k in karten if (k.get('last') or 0) < last_grenze]
    if ruhig and len(ruhig) < len(karten):
        wahl = verteilen(ruhig, bedarf_je_worker, worker, last_grenze)
        if wahl:
            return wahl
    w = bedarf_je_worker
    reihenfolge = sorted(karten, key=lambda k: -k['frei'])
    if worker >= 2:
        doppelt = [k for k in reihenfolge if k['frei'] >= 2 * w]
        if len(doppelt) >= 2:
            a, b = doppelt[:2]
            return {'gpu': a['index'], 'gpus': [a['index'], b['index']], 'worker': 2,
                    'bedarf_mib': {a['index']: 2 * w, b['index']: 2 * w},
                    'text': f"{a['kurz']} + {b['kurz']}, je ein Worker"}
        if doppelt:
            a = doppelt[0]
            return {'gpu': a['index'], 'gpus': [a['index']], 'worker': 2,
                    'bedarf_mib': {a['index']: 2 * w}, 'text': f"{a['kurz']}, zwei Worker"}
    einfach = [k for k in reihenfolge if k['frei'] >= w]
    if einfach:
        a = einfach[0]
        return {'gpu': a['index'], 'gpus': [a['index']], 'worker': 1,
                'bedarf_mib': {a['index']: w}, 'text': f"{a['kurz']}, ein Worker"}
    return None


def gib(mib):
    return f'{mib / 1024:.1f}'.replace('.', ',')


def warum_nicht(antwort, bedarf_je_worker):
    """Verständlicher Satz, warum gerade nichts passt."""
    if antwort.get('gruende'):
        return ' '.join(antwort['gruende'])
    k = max(antwort['karten'], key=lambda k: k['frei'], default=None)
    if not k:
        return 'Die Modellzentrale meldet keine Grafikkarten.'
    fehlt = bedarf_je_worker - k['frei']
    wer = [n for n in k.get('belegt_von', []) if n != 'Windows & Programme']
    return (f"Auf der {k['kurz']} sind {gib(k['frei'])} GiB frei, ein Worker braucht {gib(bedarf_je_worker)} GiB "
            f"(es fehlen {gib(fehlt)} GiB" + (f"; belegt von {', '.join(wer)}" if wer else '') + ').')


class NichtErreichbar(Exception):
    pass


class Zentrale:
    """Schmale Verbindung zur Modellzentrale (nur 127.0.0.1)."""

    def __init__(self, port, starten=None):
        self.url = f'http://127.0.0.1:{port}'
        self.port = port
        self._starten = starten  # Funktion, die den Dienst der Zentrale ohne Fenster startet

    def _post(self, pfad, daten, timeout=20):
        anfrage = urllib.request.Request(self.url + pfad, json.dumps(daten).encode('utf-8'),
                                         {'Content-Type': 'application/json', 'X-Zentrale': '1'})
        try:
            with _OHNE_PROXY.open(anfrage, timeout=timeout) as r:
                return r.status, json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b'{}')
            except ValueError:
                return e.code, {'fehler': f'Fehler {e.code}'}
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise NichtErreichbar(str(e))

    def _mit_start(self, pfad, daten):
        try:
            return self._post(pfad, daten)
        except NichtErreichbar:
            if not self._starten:
                raise
            fehler = self._starten()
            if fehler:
                raise NichtErreichbar(fehler)
            return self._post(pfad, daten)

    def stand(self):
        return self._mit_start('/api/platz', {})

    def stand_ohne_start(self):
        """Stand lesen, ohne die Zentrale zu starten (Studio: welcher Prozess nimmt den nächsten Auftrag)."""
        return self._post('/api/platz', {}, timeout=5)

    def status(self):
        """Gemessene Eintragszustände lesen, ohne die Zentrale zu starten."""
        try:
            with _OHNE_PROXY.open(self.url + '/api/status', timeout=3) as r:
                return json.loads(r.read() or b'{}')
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise NichtErreichbar(str(e))

    def anmelden(self, bedarf_mib, zweck, dauer_s=60, schluessel='transkription'):
        """`schluessel`: der Verbraucher, der den Speicher belegen wird (Zentrale zieht seinen Zuwachs ab)."""
        return self._mit_start('/api/platz', {'bedarf_mib': {str(i): m for i, m in bedarf_mib.items()},
                                              'reservieren': True, 'zweck': zweck, 'dauer_s': dauer_s,
                                              'schluessel': schluessel})

    def halten(self, aid, dauer_s=60):
        try:
            return self._post('/api/platz/halten', {'id': aid, 'dauer_s': dauer_s}, timeout=10)
        except NichtErreichbar:
            return 0, {}

    def abmelden(self, aid):
        try:
            return self._post('/api/platz/freigeben', {'id': aid}, timeout=10)
        except NichtErreichbar:
            return 0, {}


def zentrale_starter(basis, port):
    """Startet den Dienst der Modellzentrale ohne Fenster, wie ihr eigener Starter."""
    from gemeinsam import starter

    def starten():
        return starter.dienst_sicherstellen(os.path.join(basis, 'zentrale'), 'modellzentrale', port, 'dienst')
    return starten
