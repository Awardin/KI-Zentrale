"""Liest den echten Systemzustand: Karten, Belegung je Programm und Zustand der Einträge.

Nichts wird aus gemerkten Schaltflächen abgeleitet. Jede Anzeige stammt aus
Ports, Prozessen, den Programmschnittstellen oder nvidia-smi.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from gemeinsam import gpu, winapi

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_FREUNDLICH = {
    'dwm.exe': 'Windows-Desktop', 'explorer.exe': 'Windows-Explorer', 'chrome.exe': 'Chrome',
    'msedge.exe': 'Edge', 'msedgewebview2.exe': 'Edge WebView', 'claude.exe': 'Claude',
    'chatgpt.exe': 'Codex', 'steamwebhelper.exe': 'Steam', 'dsh desktop.exe': 'DSH Desktop',
    'whatsapp.root.exe': 'WhatsApp', 'snagiteditor.exe': 'Snagit', 'widgetboard.exe': 'Windows-Widgets',
    'python.exe': 'Python', 'pythonw.exe': 'Python', 'ninfer-serve.exe': 'NInfer (anderer Port)',
}


def http_json(url, daten=None, timeout=1.0):
    kopf = {'Content-Type': 'application/json'} if daten is not None else {}
    inhalt = None if daten is None else json.dumps(daten).encode('utf-8')
    with _OHNE_PROXY.open(urllib.request.Request(url, data=inhalt, headers=kopf), timeout=timeout) as r:
        antwort = r.read()
    return json.loads(antwort) if antwort else None


def http_erreichbar(url, timeout=1.0):
    try:
        with _OHNE_PROXY.open(url, timeout=timeout) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def norm(pfad):
    return os.path.normcase(os.path.normpath(pfad)) if pfad else ''


def freundlich(programmname):
    n = (programmname or '').lower()
    return _FREUNDLICH.get(n, n[:-4] if n.endswith('.exe') else n or 'unbekannt')


class Erfassung:
    def __init__(self, cfg):
        self.cfg = cfg
        self.eintraege = {e['id']: e for e in cfg['eintraege']}
        self.ninfer = next(e for e in cfg['eintraege'] if e['art'] == 'ninfer')
        self.comfy = next(e for e in cfg['eintraege'] if e['art'] == 'comfy')
        self.strata = next((e for e in cfg['eintraege'] if e['art'] == 'strata'), None)
        self.strata_engine = norm(self.strata['engine']) if self.strata else ''
        self.strata_vision = norm(self.strata.get('vision_exe', os.path.join(
            os.path.dirname(self.strata['engine']), 'strata-vision.exe'))) if self.strata else ''
        self.strata_skript = norm(self.strata['server_skript']) if self.strata else ''
        self.strata_port_arg = f"--port {self.strata['port']}" if self.strata else ''
        # llama.cpp-Dienste (z. B. LightOnOCR): erkannt an Programmpfad, Port und Modelldatei in der Kommandozeile.
        self.llamacpp = {e['id']: e for e in cfg['eintraege'] if e['art'] == 'llamacpp'}
        self._llamacpp_kennung = {i: (norm(e['programm']), f"--port {e['port']}", norm(e['modelldatei']))
                                  for i, e in self.llamacpp.items()}
        # PolyStrata (18.10.2026): Strata-artiger Server mit eigener Engine auf einer Karte; erkannt an Engine- und
        # Bildprogramm im PolyStrata-Ordner bzw. an Server-Skript und Port in der Kommandozeile von Python.
        self.polystrata = {e['id']: e for e in cfg['eintraege'] if e['art'] == 'polystrata'}
        self._polystrata_kennung = {i: (norm(e['server_skript']), f"--port {e['port']}", norm(e['engine']),
                                        norm(e['vision_exe'])) for i, e in self.polystrata.items()}
        # Allgemeine Python-Dienste (seit 22.10.2026, erster Eintrag Fibo 2.0): erkannt an Skriptpfad und Port in der
        # Kommandozeile, egal welcher Interpreter. Der uv-Starter und sein Kindprozess tragen beide dieselbe Kennung.
        self.python_dienst = {e['id']: e for e in cfg['eintraege'] if e['art'] == 'python_dienst'}
        self._python_dienst_kennung = {i: (norm(e['skript']), f"--port {e['port']}")
                                       for i, e in self.python_dienst.items()}
        self.ollama_tags = {e['tag']: e for e in cfg['eintraege'] if e['art'] == 'ollama'}
        self.ninfer_exe = norm(self.ninfer['programm'])
        self.ninfer_port_arg = f"--port {self.ninfer['port']}"
        self.comfy_ordner = norm(self.comfy['comfy_ordner'])
        # Zweiter ComfyUI-Prozess (Stufe 8, 16.10.2026): sieht nur eine Karte, rechnet neben dem ersten.
        self.comfy2_port = self.comfy.get('comfy_port_2')
        self.comfy2_name = self.comfy.get('comfy_name_2') or 'ComfyUI 2'
        trans = cfg['nur_anzeigen']['transkription']
        self.watch_ordner = norm(trans['ordner'])
        self.watch_skript = trans['skript'].lower()
        self.ollama_port = int(cfg['ollama']['url'].rsplit(':', 1)[1])
        self.ollama_ordner = norm(os.path.dirname(cfg['ollama']['programm']))
        self.vram = winapi.VramJeProzess()
        self.luid_bus = winapi.adapter_pci_busse()
        self._cache = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------ Prozesse

    def info(self, pid, name):
        with self._lock:
            c = self._cache.get(pid)
            if c is None or c['name'] != name:
                d = winapi.prozess_details(pid)
                c = {'pid': pid, 'name': name, 'pfad': norm(d[0]) if d else '',
                     'cmd': (d[1] or '').lower() if d else ''}
                self._cache[pid] = c
            return c

    def _vorfahren(self, pid, procs, tiefe=3):
        """Der Prozess selbst und bis zu `tiefe` Elternprozesse."""
        kette = []
        while pid in procs and len(kette) <= tiefe:
            kette.append(self.info(pid, procs[pid][1]))
            eltern = procs[pid][0]
            if eltern == pid:
                break
            pid = eltern
        return kette

    def ist_ninfer(self, pid, procs):
        if pid not in procs:
            return False
        i = self.info(pid, procs[pid][1])
        return i['pfad'] == self.ninfer_exe and self.ninfer_port_arg in i['cmd']

    def ist_strata(self, pid, procs):
        if self.strata is None or pid not in procs:
            return False
        name = procs[pid][1].lower()
        if name not in ('strata.exe', 'strata-vision.exe', 'python.exe', 'pythonw.exe'):
            return False
        i = self.info(pid, procs[pid][1])
        if name == 'strata-vision.exe':
            return i['pfad'] == self.strata_vision
        cmd = i['cmd'].replace('"', '')
        return i['pfad'] == self.strata_engine or (
            i['name'].lower() in ('python.exe', 'pythonw.exe') and
            self.strata_skript in cmd and self.strata_port_arg in cmd)

    def ist_llamacpp(self, pid, procs):
        """-> ID des llama.cpp-Eintrags, zu dem der Prozess gehört, sonst None."""
        if not self.llamacpp or pid not in procs:
            return None
        name = procs[pid][1].lower()
        for eid, (exe, port_arg, modell) in self._llamacpp_kennung.items():
            if name != os.path.basename(exe):
                continue
            i = self.info(pid, procs[pid][1])
            cmd = i['cmd'].replace('"', '')
            if i['pfad'] == exe and port_arg in cmd and modell in cmd:
                return eid
        return None

    def ist_polystrata(self, pid, procs):
        """-> ID des PolyStrata-Eintrags, zu dem der Prozess gehört, sonst None."""
        if not self.polystrata or pid not in procs:
            return None
        name = procs[pid][1].lower()
        if name not in ('strata-poly.exe', 'strata-vision.exe', 'python.exe', 'pythonw.exe'):
            return None
        i = self.info(pid, procs[pid][1])
        cmd = i['cmd'].replace('"', '')
        for eid, (skript, port_arg, engine, vision) in self._polystrata_kennung.items():
            if name == 'strata-poly.exe' and i['pfad'] == engine:
                return eid
            if name == 'strata-vision.exe' and i['pfad'] == vision:
                return eid
            if name in ('python.exe', 'pythonw.exe') and skript in cmd and port_arg in cmd:
                return eid
        return None

    def ist_python_dienst(self, pid, procs):
        """-> ID des python_dienst-Eintrags, zu dem der Prozess gehört, sonst None.

        Erkannt wird an Skriptpfad und `--port` in der Kommandozeile, nicht am Interpreter: Der uv-Starter
        `...\\.venv\\Scripts\\python.exe` startet den eigentlichen Interpreter als Kindprozess; beide tragen die
        Kennung, und beide müssen zum Dienst gehören.
        """
        if not self.python_dienst or pid not in procs:
            return None
        i = self.info(pid, procs[pid][1])
        cmd = i['cmd'].replace('"', '')
        for eid, (skript, port_arg) in self._python_dienst_kennung.items():
            if skript in cmd and port_arg in cmd:
                return eid
        return None

    def gehoert_zu_comfy(self, pid, procs, skript=None):
        """ComfyUI ('main.py') oder 2Wild ('server.py'), gestartet mit Pythons aus dem ComfyUI-Ordner."""
        kette = self._vorfahren(pid, procs, tiefe=1)
        if not kette:
            return False
        selbst = kette[0]
        im_ordner = any(k['pfad'].startswith(self.comfy_ordner) for k in kette) or self.comfy_ordner in selbst['cmd']
        if not im_ordner:
            return False
        skripte = [skript] if skript else ['main.py', 'server.py']
        return any(s in selbst['cmd'] for s in skripte)

    def ist_comfy2(self, pid, procs):
        """Der zweite ComfyUI-Prozess: sein Port steht in der eigenen oder der Kommandozeile des Starters."""
        if not self.comfy2_port:
            return False
        arg = f'--port {self.comfy2_port}'
        return any(arg in k['cmd'].replace('"', '') for k in self._vorfahren(pid, procs, tiefe=1))

    def ist_ollama(self, pid, procs):
        """Ollama selbst oder sein Modellprozess (lib\\ollama\\llama-server.exe als Kind von ollama.exe)."""
        eltern, name = procs[pid]
        if name.lower() == 'ollama.exe' or self.info(pid, name)['pfad'].startswith(self.ollama_ordner):
            return True
        return eltern in procs and procs[eltern][1].lower() == 'ollama.exe'

    def ist_transkription(self, pid, procs):
        return any(self.watch_skript in k['cmd'] or k['pfad'].startswith(self.watch_ordner)
                   for k in self._vorfahren(pid, procs))

    def einordnen(self, pid, procs):
        """-> (schluessel, name) für die Belegungsanzeige."""
        if pid not in procs:
            return 'andere', 'beendetes Programm'
        name = procs[pid][1]
        if self.ist_ninfer(pid, procs):
            return 'ninfer', self.ninfer['name']
        if self.ist_strata(pid, procs):
            return 'strata', self.strata['name']
        eid = self.ist_llamacpp(pid, procs)
        if eid:
            return 'llamacpp:' + eid, self.llamacpp[eid]['name']
        eid = self.ist_polystrata(pid, procs)
        if eid:
            return 'polystrata:' + eid, self.polystrata[eid]['name']
        eid = self.ist_python_dienst(pid, procs)
        if eid:
            return 'python_dienst:' + eid, self.python_dienst[eid]['name']
        if self.ist_ollama(pid, procs):
            return 'ollama', 'Ollama'
        if self.gehoert_zu_comfy(pid, procs):
            if self.ist_comfy2(pid, procs):
                return 'bild-video-2', self.comfy2_name
            return 'bild-video', self.comfy['name']
        if self.ist_transkription(pid, procs):
            return 'transkription', self.cfg['nur_anzeigen']['transkription']['name']
        return 'andere', freundlich(name)

    # ------------------------------------------------------------ Messung

    def messen(self):
        with self._lock:
            t0 = time.time()
            procs = winapi.prozesse()
            for pid in list(self._cache):
                if pid not in procs:
                    del self._cache[pid]
            lausch = {}
            for adresse, port, pid in winapi.lauschende_ports():
                lausch.setdefault(port, pid)
            karten = gpu.karten_lesen()
            bus_index = {k['bus']: k['index'] for k in karten}
            vram = {}
            for pid, luid, wert in self.vram.lesen():
                idx = bus_index.get(self.luid_bus.get(luid))
                if idx is not None:
                    vram.setdefault(idx, {})
                    vram[idx][pid] = vram[idx].get(pid, 0) + wert / 1048576
            ollama = self._ollama(lausch)
            dienste = self._dienste(procs, lausch)
            verbraucher = self._verbraucher(procs, karten, vram, ollama, dienste)
            return {'zeit': t0, 'dauer_ms': round((time.time() - t0) * 1000), 'karten': karten,
                    'verbraucher': verbraucher, 'ollama': ollama, 'dienste': dienste,
                    'procs': procs, 'lausch': lausch}

    def _ollama(self, lausch):
        if self.ollama_port not in lausch:
            return {'erreichbar': False, 'geladen': []}
        try:
            d = http_json(self.cfg['ollama']['url'] + '/api/ps', timeout=1.5) or {}
        except Exception:
            return {'erreichbar': False, 'geladen': []}
        geladen = []
        for m in d.get('models', []):
            geladen.append({'tag': m.get('name') or m.get('model'),
                            'vram_mib': round((m.get('size_vram') or 0) / 1048576),
                            'groesse_mib': round((m.get('size') or 0) / 1048576),
                            'kontext': m.get('context_length')})
        return {'erreichbar': True, 'geladen': geladen}

    def _dienste(self, procs, lausch):
        d = {}
        # NInfer
        e = self.ninfer
        n = {'zustand': 'aus', 'pid': None, 'fremd': None}
        pid = lausch.get(e['port'])
        if pid is not None:
            if self.ist_ninfer(pid, procs):
                n['pid'] = pid
                try:
                    m = http_json(f"http://127.0.0.1:{e['port']}/v1/models", timeout=1.0) or {}
                    ids = [x.get('id') for x in m.get('data', [])]
                    n['zustand'] = 'bereit' if e['modell_id'] in ids else 'startet'
                except Exception:
                    n['zustand'] = 'startet'
            else:
                n['zustand'] = 'fremd'
                n['fremd'] = freundlich(procs.get(pid, (0, ''))[1])
        else:
            startend = [p for p, (_, nm) in procs.items() if nm.lower() == 'ninfer-serve.exe' and self.ist_ninfer(p, procs)]
            if startend:
                n.update(zustand='startet', pid=startend[0])
        d['ninfer'] = n
        # Strata (optional)
        if self.strata:
            e = self.strata
            s = {'zustand': 'aus', 'pids': [p for p in procs if self.ist_strata(p, procs)],
                 'fremd': None, 'kontext': None, 'modell': None}
            pid = lausch.get(e['port'])
            if pid is not None:
                if self.ist_strata(pid, procs):
                    s['zustand'] = 'startet'
                    try:
                        h = http_json(f"http://127.0.0.1:{e['port']}/health", timeout=1.0) or {}
                        if h.get('loaded'):
                            s.update(zustand='bereit', kontext=h.get('max_context'), modell=h.get('model'))
                    except Exception:
                        pass
                else:
                    s.update(zustand='fremd', fremd=freundlich(procs.get(pid, (0, ''))[1]))
            elif s['pids']:
                s['zustand'] = 'startet'
            d['strata'] = s
        # llama.cpp-Dienste: /health antwortet 503, solange das Modell lädt, danach 200.
        for eid, e in self.llamacpp.items():
            s = {'zustand': 'aus', 'pids': [p for p in procs if self.ist_llamacpp(p, procs) == eid], 'fremd': None}
            pid = lausch.get(e['port'])
            if pid is not None:
                if self.ist_llamacpp(pid, procs) == eid:
                    s['zustand'] = 'startet'
                    try:
                        if (http_json(f"http://127.0.0.1:{e['port']}/health", timeout=1.0) or {}).get('status') == 'ok':
                            s['zustand'] = 'bereit'
                    except Exception:
                        pass
                else:
                    s.update(zustand='fremd', fremd=freundlich(procs.get(pid, (0, ''))[1]))
            elif s['pids']:
                s['zustand'] = 'startet'
            d[eid] = s
        # PolyStrata: /health meldet „loaded“, Kontext und Modell wie bei Strata.
        for eid, e in self.polystrata.items():
            s = {'zustand': 'aus', 'pids': [p for p in procs if self.ist_polystrata(p, procs) == eid], 'fremd': None,
                 'kontext': None, 'modell': None}
            pid = lausch.get(e['port'])
            if pid is not None:
                if self.ist_polystrata(pid, procs) == eid:
                    s['zustand'] = 'startet'
                    try:
                        h = http_json(f"http://127.0.0.1:{e['port']}/health", timeout=1.0) or {}
                        if h.get('loaded'):
                            s.update(zustand='bereit', kontext=h.get('max_context'), modell=h.get('model'))
                    except Exception:
                        pass
                else:
                    s.update(zustand='fremd', fremd=freundlich(procs.get(pid, (0, ''))[1]))
            elif s['pids']:
                s['zustand'] = 'startet'
            d[eid] = s
        # Allgemeine Python-Dienste: /health meldet `loading`, bis das Modell bereit ist, danach `ok`.
        for eid, e in self.python_dienst.items():
            s = {'zustand': 'aus', 'pids': [p for p in procs if self.ist_python_dienst(p, procs) == eid],
                 'fremd': None, 'laufend': None, 'aktiv': None, 'karte': None}
            pid = lausch.get(e['port'])
            if pid is not None:
                if self.ist_python_dienst(pid, procs) == eid:
                    s['zustand'] = 'startet'
                    try:
                        h = http_json(f"http://127.0.0.1:{e['port']}{e.get('health_pfad', '/health')}",
                                      timeout=1.0) or {}
                        if h.get('status') == 'ok':
                            s['zustand'] = 'bereit'
                        s['laufend'] = h.get('laufend')
                        s['aktiv'] = h.get('aktiv')
                        s['karte'] = h.get('karte')
                    except Exception:
                        pass
                else:
                    s.update(zustand='fremd', fremd=freundlich(procs.get(pid, (0, ''))[1]))
            elif s['pids']:
                s['zustand'] = 'startet'
            d[eid] = s
        # ComfyUI (zwei Prozesse seit Stufe 8) und 2Wild
        c = self.comfy

        def comfy_dienst(port):
            z = {'pid': None, 'laeuft': False, 'fremd': None, 'auftraege_laufend': 0, 'auftraege_wartend': 0}
            pid = lausch.get(port) if port else None
            if pid is not None:
                if self.gehoert_zu_comfy(pid, procs, 'main.py'):
                    z['pid'] = pid
                    try:
                        q = http_json(f'http://127.0.0.1:{port}/queue', timeout=1.0) or {}
                        z.update(laeuft=True, auftraege_laufend=len(q.get('queue_running', [])),
                                 auftraege_wartend=len(q.get('queue_pending', [])))
                    except Exception:
                        pass
                else:
                    z['fremd'] = freundlich(procs.get(pid, (0, ''))[1])
            return z

        comfy = comfy_dienst(c['comfy_port'])
        d['comfy2'] = comfy_dienst(self.comfy2_port)
        studio = {'pid': None, 'laeuft': False, 'fremd': None}
        pid = lausch.get(c['studio_port'])
        if pid is not None:
            if self.gehoert_zu_comfy(pid, procs, 'server.py'):
                studio.update(pid=pid, laeuft=http_erreichbar(f"http://127.0.0.1:{c['studio_port']}/", 1.0))
            else:
                studio['fremd'] = freundlich(procs.get(pid, (0, ''))[1])
        d['comfy'], d['studio'] = comfy, studio
        # Programme wie DSH
        for e in self.cfg['eintraege']:
            if e['art'] == 'programm':
                ziel = norm(e['programm'])
                exe = os.path.basename(ziel)
                d[e['id']] = {'pids': [p for p, (_, nm) in procs.items()
                                       if nm.lower() == exe and self.info(p, nm)['pfad'] == ziel]}
        d['ollama_prozess'] = lausch.get(self.ollama_port)
        return d

    def _verbraucher(self, procs, karten, vram, ollama, dienste):
        gruppen = {}
        for idx, je_pid in vram.items():
            for pid, mib in je_pid.items():
                schluessel, name = self.einordnen(pid, procs)
                g = gruppen.setdefault(schluessel, {'mib': {}, 'details': {}})
                g['mib'][idx] = g['mib'].get(idx, 0) + mib
                if schluessel == 'andere' and mib >= 16:
                    je_karte = g['details'].setdefault(idx, {})
                    je_karte[name] = je_karte.get(name, 0) + mib
        out = []
        # Während des Ladens oder kurz nach dem Entladen belegt Ollama Speicher, ohne ein Modell zu melden.
        if 'ollama' in gruppen and not ollama['geladen']:
            out.append({'eintrag': None, 'schluessel': 'ollama', 'name': 'Ollama (lädt oder gibt frei)',
                        'farbe': self.cfg['ollama']['farbe_fremd'], 'mib_je_karte': gruppen.pop('ollama')['mib'],
                        'blockiert': None, 'schritt': None})
        if 'ninfer' in gruppen:
            e = self.ninfer
            out.append({'eintrag': 'ninfer', 'schluessel': 'ninfer', 'name': e['name'], 'farbe': e['farbe'],
                        'mib_je_karte': gruppen['ninfer']['mib'], 'blockiert': None,
                        'schritt': {'id': 'beenden:ninfer', 'text': f"{e['name']} beenden"}})
        if 'strata' in gruppen:
            e = self.strata
            out.append({'eintrag': e['id'], 'schluessel': 'strata', 'name': e['name'], 'farbe': e['farbe'],
                        'mib_je_karte': gruppen['strata']['mib'], 'blockiert': None,
                        'schritt': {'id': 'beenden:strata', 'text': f"{e['name']} beenden"}})
        for eid, e in self.llamacpp.items():
            if 'llamacpp:' + eid in gruppen:
                out.append({'eintrag': eid, 'schluessel': 'llamacpp:' + eid, 'name': e['name'], 'farbe': e['farbe'],
                            'mib_je_karte': gruppen['llamacpp:' + eid]['mib'], 'blockiert': None,
                            'schritt': {'id': 'beenden:' + eid, 'text': f"{e['name']} beenden"}})
        for eid, e in self.polystrata.items():
            if 'polystrata:' + eid in gruppen:
                out.append({'eintrag': eid, 'schluessel': 'polystrata:' + eid, 'name': e['name'], 'farbe': e['farbe'],
                            'mib_je_karte': gruppen['polystrata:' + eid]['mib'], 'blockiert': None,
                            'schritt': {'id': 'beenden:' + eid, 'text': f"{e['name']} beenden"}})
        for eid, e in self.python_dienst.items():
            schluessel = 'python_dienst:' + eid
            dienst = dienste.get(eid) or {}
            # Auch ein laufender Dienst mit fast keiner Messung ist freigebbar (Beenden). Die Karte kommt aus
            # /health, damit der Eintrag ohne Messwert nicht verschwindet.
            if schluessel not in gruppen and dienst.get('zustand') not in ('startet', 'bereit'):
                continue
            mib = dict((gruppen.get(schluessel) or {}).get('mib') or {})
            if not mib:
                karte = dienst.get('karte')
                if karte is not None:
                    try:
                        mib = {int(karte): 0}
                    except (TypeError, ValueError):
                        mib = {}
            laufend = dienst.get('laufend')
            out.append({'eintrag': eid, 'schluessel': schluessel, 'name': e['name'], 'farbe': e['farbe'],
                        'mib_je_karte': mib,
                        'blockiert': f"In {e['name']} läuft gerade ein Auftrag." if laufend else None,
                        'schritt': {'id': 'beenden:' + eid, 'text': f"{e['name']} beenden"}})
        if 'ollama' in gruppen:
            gesamt = sum(m['vram_mib'] for m in ollama['geladen']) or 1
            for m in ollama['geladen']:
                anteil = m['vram_mib'] / gesamt
                e = self.ollama_tags.get(m['tag'])
                name = e['name'] if e else m['tag']
                out.append({'eintrag': e['id'] if e else None, 'schluessel': 'ollama:' + m['tag'], 'name': name,
                            'farbe': e['farbe'] if e else self.cfg['ollama']['farbe_fremd'],
                            'mib_je_karte': {i: v * anteil for i, v in gruppen['ollama']['mib'].items()},
                            'blockiert': None, 'schritt': {'id': 'entladen:' + m['tag'], 'text': f'{name} entladen'}})
        for schluessel, dienst, name in (('bild-video', 'comfy', self.comfy['name']),
                                         ('bild-video-2', 'comfy2', self.comfy2_name)):
            if schluessel not in gruppen:
                continue
            c = dienste[dienst]
            # Unter 1 GiB hält ComfyUI nur seine Grundbelegung; dann gibt es nichts zu entladen.
            modelle_geladen = sum(gruppen[schluessel]['mib'].values()) >= 1024
            out.append({'eintrag': 'bild-video', 'schluessel': schluessel, 'name': name,
                        'farbe': self.comfy['farbe'], 'mib_je_karte': gruppen[schluessel]['mib'],
                        'blockiert': f'In {name} läuft gerade ein Auftrag.' if c['auftraege_laufend'] else None,
                        'schritt': {'id': 'freigeben:' + schluessel, 'text': f'Modelle aus {name} entladen (Dienst läuft weiter)'}
                        if c['laeuft'] and modelle_geladen else None})
        if 'transkription' in gruppen:
            t = self.cfg['nur_anzeigen']['transkription']
            out.append({'eintrag': None, 'schluessel': 'transkription', 'name': t['name'], 'farbe': t['farbe'],
                        'mib_je_karte': gruppen['transkription']['mib'], 'blockiert': None, 'schritt': None})
        # "Windows & Programme" ist der Rest bis zur vom Treiber gemessenen Belegung.
        rest = {}
        for k in karten:
            if k['belegt'] is None:
                continue
            gezaehlt = sum(v['mib_je_karte'].get(k['index'], 0) for v in out)
            rest[k['index']] = max(0.0, k['belegt'] - gezaehlt)
        details = gruppen.get('andere', {}).get('details', {})
        a = self.cfg['nur_anzeigen']['andere']
        out.append({'eintrag': None, 'schluessel': 'andere', 'name': a['name'], 'farbe': a['farbe'],
                    'mib_je_karte': rest, 'blockiert': None, 'schritt': None,
                    'details_je_karte': {i: [n for n, _ in sorted(d.items(), key=lambda x: -x[1])[:6]]
                                         for i, d in details.items()}})
        for v in out:
            v['mib_je_karte'] = {i: round(m) for i, m in v['mib_je_karte'].items()}
        return out
