"""Startet bei Bedarf den Dienst einer App und öffnet sie in einem eigenen Edge-Fenster."""
import ctypes
import json
import os
import sys
import time
import urllib.request
import webbrowser

from . import winapi

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']


def meldung(titel, text):
    ctypes.windll.user32.MessageBoxW(None, text, titel, 0x10)


def kennung(url):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + 'api/health', timeout=1.5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def dienst_sicherstellen(app_ordner, app, port, log_name):
    """Startet `server.py` im App-Ordner, falls auf dem Port noch nichts antwortet.

    -> None, wenn der Dienst bereit ist, sonst eine verständliche Fehlermeldung.
    """
    url = f'http://127.0.0.1:{port}/'
    k = kennung(url)
    if k is None:
        if port in {p for _, p, _ in winapi.lauschende_ports()}:
            return f'Port {port} ist von einem anderen Programm belegt.'
        pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        os.makedirs(os.path.join(BASIS, 'logs'), exist_ok=True)
        winapi.starte_losgeloest([pythonw if os.path.exists(pythonw) else sys.executable,
                                  os.path.join(app_ordner, 'server.py')], app_ordner,
                                 log_basis=os.path.join(BASIS, 'logs', log_name))
        for _ in range(40):
            time.sleep(0.25)
            k = kennung(url)
            if k:
                break
        if not k:
            return f'Der Dienst startet nicht. Details stehen in logs\\{log_name}.err.log.'
    if k.get('app') != app:
        return f'Auf Port {port} läuft ein anderer Dienst.'
    return None


def fenster_oeffnen(port, groesse='1280,920'):
    url = f'http://127.0.0.1:{port}/'
    edge = next((p for p in EDGE if os.path.exists(p)), None)
    if edge:
        winapi.starte_losgeloest([edge, f'--app={url}', f'--window-size={groesse}'], os.path.dirname(edge))
    else:
        webbrowser.open(url)


def main(app_ordner, app, titel, log_name, groesse='1280,920'):
    with open(os.path.join(app_ordner, 'config.json'), encoding='utf-8') as f:
        port = json.load(f)['port']
    fehler = dienst_sicherstellen(app_ordner, app, port, log_name)
    if fehler and '--ohne-fenster' in sys.argv:
        # Ohne Fenster (Skripte, andere Apps): kein Meldungsfenster, das den Aufrufer blockiert.
        print(f'{titel}: {fehler}', file=sys.stderr)
        sys.exit(1)
    if fehler:
        return meldung(titel, f'{fehler} {titel} wurde nicht geöffnet.')
    if '--ohne-fenster' not in sys.argv:
        fenster_oeffnen(port, groesse)
