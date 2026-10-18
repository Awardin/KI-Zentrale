"""Eingaben der Werkstatt: YouTube-Links, Dateipfade, abgelegte Dateien und Ordner.

Beim Hineinziehen verrät das Browserfenster den Speicherort nicht. Die Datei ist
dabei aber im Explorer markiert: Die Werkstatt liest diese Markierung und gleicht
Name, Größe und Änderungszeit ab. Es wird nichts kopiert und nichts durchsucht.
"""
import json
import os
import re
import subprocess

from gemeinsam import winapi

from . import watch_lauf

_URL = re.compile(r'https?://\S+', re.I)

_EXPLORER_MARKIERUNG = r'''
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$pfade = @()
foreach ($w in (New-Object -ComObject Shell.Application).Windows()) {
  try { foreach ($i in $w.Document.SelectedItems()) { $pfade += $i.Path } } catch {}
}
ConvertTo-Json -InputObject @($pfade) -Compress
'''


def normpfad(p):
    return os.path.normcase(os.path.normpath(p))


def liegt_in(pfad, ordner):
    """Liegt `pfad` im Ordner (oder ist er selbst)? Vergleicht ganze Pfadteile."""
    if not pfad:
        return False
    p, o = normpfad(pfad), normpfad(ordner)
    return p == o or p.startswith(o.rstrip(os.sep) + os.sep)


def text_zerlegen(text):
    """Zeilen aus dem Textfeld -> [('youtube', url) | ('pfad', pfad) | ('fehler', meldung)]."""
    out = []
    for zeile in (text or '').splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        urls = _URL.findall(zeile)
        if urls:
            for u in urls:
                u = u.rstrip('.,;)>]"\'')
                try:
                    out.append(('youtube', watch_lauf.youtube_url(watch_lauf.youtube_id(u))))
                except ValueError as e:
                    out.append(('fehler', f'{u}: {e}'))
            continue
        pfad = zeile.strip('"\'')
        if re.match(r'^[A-Za-z]:[\\/]|^\\\\', pfad):
            out.append(('pfad', os.path.normpath(pfad)))
        else:
            out.append(('fehler', f'„{zeile[:80]}“ ist weder ein YouTube-Link noch ein Dateipfad.'))
    return out


def ist_medium(pfad, endungen):
    return os.path.splitext(pfad)[1].lower() in endungen


def _natuerlich(pfad):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', pfad)]


def ordner_ausklappen(ordner, endungen, grenze, ausgeschlossen=()):
    """Medien in einem abgelegten Ordner samt Unterordnern, natürlich sortiert. -> (dateien, abgeschnitten)."""
    gefunden = []
    ausgeschlossen = [normpfad(a) for a in ausgeschlossen]
    for wurzel, ordnernamen, dateien in os.walk(ordner):
        ordnernamen[:] = [o for o in ordnernamen if not o.startswith('.')
                          and not any(normpfad(os.path.join(wurzel, o)).startswith(a) for a in ausgeschlossen)]
        for d in dateien:
            if ist_medium(d, endungen):
                gefunden.append(os.path.join(wurzel, d))
    gefunden.sort(key=_natuerlich)
    return gefunden[:grenze], len(gefunden) > grenze


def explorer_markierung():
    """Vollständige Pfade aller im Explorer markierten Einträge (alle offenen Explorer-Fenster)."""
    try:
        r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                            '-Command', _EXPLORER_MARKIERUNG], capture_output=True, timeout=15,
                           creationflags=winapi.CREATE_NO_WINDOW)
        daten = json.loads(r.stdout.decode('utf-8', 'replace').strip() or '[]')
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    return [p for p in (daten if isinstance(daten, list) else [daten]) if isinstance(p, str)]


def abgleichen(abgelegt, markiert):
    """Ordnet abgelegte Einträge den markierten Pfaden zu.

    `abgelegt`: [{'name', 'ordner': bool, 'groesse', 'geaendert' (ms)}]
    -> (gefundene Pfade, nicht zuordenbare Namen)
    """
    gefunden, offen = [], []
    for e in abgelegt:
        name = str(e.get('name', '')).lower()
        treffer = []
        for p in markiert:
            if os.path.basename(p).lower() != name:
                continue
            if e.get('ordner'):
                if os.path.isdir(p):
                    treffer.append(p)
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            if not os.path.isfile(p) or st.st_size != e.get('groesse'):
                continue
            if e.get('geaendert') and abs(st.st_mtime * 1000 - float(e['geaendert'])) > 2000:
                continue
            treffer.append(p)
        eindeutig = {normpfad(t): t for t in treffer}
        if len(eindeutig) == 1:
            gefunden.append(next(iter(eindeutig.values())))
        else:
            offen.append(e.get('name', '?'))
    return gefunden, offen


def dateien_waehlen(endungen):
    besitzer = winapi.fenster_mit_titel('Werkstatt')
    return winapi.dateien_waehlen('Audio- oder Videodateien wählen', 'Audio und Video', endungen, besitzer)
