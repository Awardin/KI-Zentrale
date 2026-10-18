"""Messwerte der NVIDIA-Karten über nvidia-smi (vom Treiber gemessen, nicht geschätzt)."""
import subprocess

from .winapi import CREATE_NO_WINDOW

_FELDER = ['index', 'pci.bus_id', 'name', 'memory.used', 'memory.total', 'temperature.gpu',
           'utilization.gpu', 'power.draw', 'power.limit', 'fan.speed', 'clocks.gr', 'pstate', 'display_attached']


def _zahl(text):
    text = text.strip()
    if not text or text.startswith('[') or text.upper() == 'N/A':
        return None
    try:
        return float(text)
    except ValueError:
        return None


def karten_lesen():
    """Liste je Karte: index, bus, name, belegt/gesamt (MiB), temp, last, watt, watt_limit, luefter, takt, pstate,
    monitor (ein Bildschirm hängt an der Karte; Windows belegt dort schwankend Speicher)."""
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=' + ','.join(_FELDER), '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=8, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return []
    karten = []
    for zeile in r.stdout.strip().splitlines():
        t = [x.strip() for x in zeile.split(',')]
        if len(t) != len(_FELDER):
            continue
        try:
            bus = int(t[1].split(':')[1], 16)  # 00000000:02:00.0 -> 2
        except (IndexError, ValueError):
            bus = None
        karten.append({
            'index': int(t[0]), 'bus': bus, 'name': t[2],
            'belegt': _zahl(t[3]), 'gesamt': _zahl(t[4]), 'temp': _zahl(t[5]), 'last': _zahl(t[6]),
            'watt': _zahl(t[7]), 'watt_limit': _zahl(t[8]), 'luefter': _zahl(t[9]), 'takt': _zahl(t[10]),
            'pstate': t[11] if t[11] and not t[11].startswith('[') else None,
            'monitor': t[12].strip().lower() == 'yes',
        })
    return karten


def kurznamen(karten, cfg_karten=None):
    """Anzeigename je Karte ({Index: Name}) aus der Messung.

    Vorrang hat ein Name aus der Konfiguration, dessen Steckplatz (`bus`) und Kartenmodell (`name`) zur Messung
    passen – so heißen zwei gleiche Karten „RTX 3090 FE“ und „RTX 3090 Suprim“. Sonst gilt der gemessene Name
    (bei gleichen Namen mit Nummer), ohne gemessenen Namen der Eintrag zum Index oder „Karte n“.
    """
    cfg_karten = cfg_karten or {}
    namen = {}
    for k in karten:
        idx = k['index']
        name = (k.get('name') or '').strip()
        passend = next((c['kurz'] for c in cfg_karten.values()
                        if c.get('bus') is not None and c.get('bus') == k.get('bus') and c.get('kurz')
                        and (c.get('name') or '').casefold() in name.casefold()), None) if name else None
        if passend:
            name = passend
        elif name:
            name = name.removeprefix('NVIDIA ').removeprefix('GeForce ')
        else:
            name = cfg_karten.get(str(idx), {}).get('kurz') or f'Karte {idx}'
        namen[idx] = name
    return {i: f'{name} · Nr. {i}' if list(namen.values()).count(name) > 1 else name
            for i, name in namen.items()}
