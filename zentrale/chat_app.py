"""Chat-Reiter der Zentrale: die Oberfläche von Strata (apps\\host, Node 24) als eigener Dienst auf 127.0.0.1.

Seit 21.10.2026 (Auftrag Sascha). Die App wird abgesichert gestartet: keine Downloads oder Installationen
(STRATA_NO_ACQUIRE), keine mitgelieferte Engine, eigener Daten-, Modell- und Arbeitsordner, nur an 127.0.0.1.
Tunnel und Freigabe nach außen startet sie nur auf Klick; die Modelle der Zentrale sind darin als Verbindungen
eingetragen. Laden und Entladen der Modelle bleibt in der Zentrale.

Erkannt wird der Dienst am Port und an seiner Kommandozeile (Programm node.exe aus dem Eintrag, Skript
apps\\host\\server\\index.mjs) – beendet wird nur dieser Prozess.
"""
import os
import time
import urllib.request

from gemeinsam import winapi

SKRIPT = os.path.join('server', 'index.mjs')
_O = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _norm(pfad):
    return os.path.normcase(os.path.normpath(pfad or ''))


def _skript(c):
    return os.path.join(c['ordner'], SKRIPT)


def prozess(c):
    """PID des laufenden Chat-Dienstes auf seinem Port oder None (Programmpfad und Kommandozeile geprüft)."""
    for adresse, port, pid in winapi.lauschende_ports():
        if port != c['port'] or adresse not in ('127.0.0.1', '0.0.0.0', '::', '::1'):
            continue
        d = winapi.prozess_details(pid)
        if d and _norm(d[0]) == _norm(c['node']) and _norm(_skript(c)) in _norm(d[1]):
            return pid
    return None


def status(c):
    pid = prozess(c)
    belegt = pid is None and any(p == c['port'] for _, p, _ in winapi.lauschende_ports())
    return {'laeuft': pid is not None, 'url': f"http://127.0.0.1:{c['port']}/", 'port_fremd_belegt': belegt,
            'eingerichtet': os.path.isfile(c['node']) and os.path.isdir(os.path.join(c['ordner'], 'dist'))}


def umgebung(c):
    env = dict(os.environ)
    env.update({
        'PATH': os.path.dirname(c['node']) + os.pathsep + env.get('PATH', ''),
        'STRATA_PORT': str(c['port']), 'STRATA_BIND': '127.0.0.1',
        'STRATA_NO_ACQUIRE': '1', 'STRATA_NO_BUNDLED_ENGINE': '1', 'STRATA_NO_REPAIR_ACCESS': '1',
        'STRATA_REAL_ENGINE': '1',  # keine vorgetäuschten Antworten, wenn kein Modell läuft
        'STRATA_HOME': c['daten'], 'STRATA_MODELS_DIR': c['modelle'], 'STRATA_WORKSPACE': c['arbeitsordner'],
    })
    return env


def starten(c, warten_s=30):
    """Startet den Dienst losgelöst (läuft weiter, wenn die Zentrale neu startet). (code, antwort)"""
    s = status(c)
    if s['laeuft']:
        return 200, s
    if s['port_fremd_belegt']:
        return 409, {'fehler': f"Port {c['port']} ist von einem anderen Programm belegt."}
    if not s['eingerichtet']:
        return 409, {'fehler': 'Die Chat-App ist nicht eingerichtet (Node oder gebaute Oberfläche fehlt).'}
    for ordner in (c['daten'], c['modelle'], c['arbeitsordner'], c['logs']):
        os.makedirs(ordner, exist_ok=True)
    winapi.starte_losgeloest([c['node'], _skript(c), '--dist', os.path.join(c['ordner'], 'dist')], c['ordner'],
                             umgebung(c), log_basis=os.path.join(c['logs'], 'app'))
    ende = time.time() + warten_s
    while time.time() < ende:
        try:
            _O.open(f"http://127.0.0.1:{c['port']}/api/app/mode", timeout=2).read()
            if prozess(c):
                return 200, status(c)
        except Exception:  # noqa: BLE001 – startet noch
            pass
        time.sleep(0.5)
    return 504, {'fehler': 'Die Chat-App hat nicht rechtzeitig geantwortet (Log in C:\\LLM\\runtimes\\Strata-App\\logs).'}


def beenden(c):
    pid = prozess(c)
    if pid is None:
        return 200, status(c)
    winapi.beenden(pid)
    return 200, status(c)
