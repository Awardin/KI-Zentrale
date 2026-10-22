"""Starten, Beenden, Laden, Entladen und Öffnen der verwalteten Einträge.

Jede Aktion misst vorher den echten Zustand neu und fasst nur Prozesse an,
deren Programmpfad, Port und Kommandozeile eindeutig passen.
"""
import os
import time

from gemeinsam import winapi
from . import planung
from .erfassung import http_erreichbar, http_json, norm


class Fehler(Exception):
    """Verständliche Meldung für das Protokoll der Oberfläche."""


def _letzte_meldung(logdatei):
    try:
        with open(logdatei, 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4000))
            zeilen = [z.strip() for z in f.read().decode('utf-8', 'replace').splitlines() if z.strip()]
        return zeilen[-1][:240] if zeilen else ''
    except OSError:
        return ''


def _warten(bedingung, sekunden, takt=1.0):
    frist = time.time() + sekunden
    while time.time() < frist:
        if bedingung():
            return True
        time.sleep(takt)
    return bedingung()


class Aktionen:
    def __init__(self, cfg, erfassung, log_ordner, protokollieren):
        self.cfg = cfg
        self.erf = erfassung
        self.logs = log_ordner
        self.log = protokollieren  # nur Datei, nicht Oberfläche
        self.eintraege = {e['id']: e for e in cfg['eintraege']}
        self.ollama_url = cfg['ollama']['url']

    # ------------------------------------------------------------ Verteiler

    def starten(self, eintrag_id, karte=None, variante=None):
        """`karte`: von der Zentrale gewählte Karte für Einträge mit Kartenliste. ComfyUI nutzt beide Karten selbst
        (das Studio wählt je Auftrag); für ComfyUI ist die Karte nur Teil der Platzplanung.
        `variante`: gewählte Variante (Kontextgröße; Ollama-Optionen bzw. Strata-Einstellung), sonst der Standard."""
        e = planung.variante(self.eintraege[eintrag_id], variante)
        if e['art'] == 'llamacpp':
            return self._llamacpp_starten(e, karte)
        if e['art'] == 'python_dienst':
            return self._python_dienst_starten(e, karte)
        if e['art'] == 'polystrata':
            return self._polystrata_starten(e, karte)
        if e['art'] == 'ninfer':
            return self._ninfer_starten(e, karte)
        return {'ollama': self._ollama_laden,
                'strata': self._strata_starten,
                'comfy': self._comfy_starten, 'programm': self._programm_oeffnen}[e['art']](e)

    def stoppen(self, eintrag_id, erzwingen=False):
        e = self.eintraege[eintrag_id]
        if e['art'] == 'ninfer':
            return self._ninfer_stoppen(e)
        if e['art'] == 'strata':
            return self._strata_stoppen(e)
        if e['art'] == 'llamacpp':
            return self._llamacpp_stoppen(e)
        if e['art'] == 'python_dienst':
            return self._python_dienst_stoppen(e, erzwingen)
        if e['art'] == 'polystrata':
            return self._polystrata_stoppen(e)
        if e['art'] == 'ollama':
            return self._ollama_entladen(e['tag'], e['name'])
        if e['art'] == 'comfy':
            return self._comfy_stoppen(e, erzwingen)
        if e['art'] == 'programm':
            return self._programm_beenden(e)
        raise Fehler(f"{e['name']} wird hier nicht beendet.")

    def schritt(self, schritt_id):
        art, _, ziel = schritt_id.partition(':')
        if art == 'beenden' and ziel == 'ninfer':
            return self._ninfer_stoppen(self.erf.ninfer)
        if art == 'beenden' and ziel == 'strata' and self.erf.strata:
            return self._strata_stoppen(self.erf.strata)
        if art == 'beenden' and ziel in self.erf.llamacpp:
            return self._llamacpp_stoppen(self.erf.llamacpp[ziel])
        if art == 'beenden' and ziel in self.erf.python_dienst:
            return self._python_dienst_stoppen(self.erf.python_dienst[ziel])
        if art == 'beenden' and ziel in self.erf.polystrata:
            return self._polystrata_stoppen(self.erf.polystrata[ziel])
        if art == 'entladen':
            e = self.erf.ollama_tags.get(ziel)
            return self._ollama_entladen(ziel, e['name'] if e else ziel)
        if art == 'freigeben' and (ziel == 'bild-video' or ziel.startswith('bild-video-')):
            return self._comfy_freigeben(ziel)
        raise Fehler(f'Unbekannter Schritt: {schritt_id}')

    def warten_auf_platz(self, e, reserve_mib, bedarf=None, sekunden=25, gesamt=None):
        """Nach dem Freigeben dauert es kurz, bis der Treiber den Speicher zurückmeldet.

        `gesamt`: MiB auf allen Karten zusammen (Ollama verteilt selbst), sonst `bedarf` je Karte. Bei `gesamt`
        zählen mit `gesamt_karten` nur Karten, deren Name einen dieser Namen enthält."""
        bedarf = {int(i): m for i, m in (bedarf if bedarf is not None else e.get('bedarf_mib', {})).items()}

        def genug():
            karten = {k['index']: k for k in self.erf.messen()['karten']}
            if gesamt is not None:
                zaehlend = set(planung.wunschkarten(list(karten.values()), e['gesamt_karten'])) \
                    if e.get('gesamt_karten') else set(karten)
                return sum(max(0, k['gesamt'] - k['belegt'] - reserve_mib)
                           for i, k in karten.items() if i in zaehlend) >= gesamt
            return all(i in karten and karten[i]['gesamt'] - karten[i]['belegt'] >= m + reserve_mib
                       for i, m in bedarf.items())
        return _warten(genug, sekunden)

    # ------------------------------------------------------------ NInfer

    def _ninfer_starten(self, e, karte=None):
        if karte is None:
            raise Fehler(f"Keine Karte für {e['name']} gewählt.")
        n = self.erf.messen()['dienste']['ninfer']
        if n['zustand'] == 'bereit':
            return f"{e['name']} läuft bereits."
        if n['zustand'] == 'fremd':
            raise Fehler(f"Port {e['port']} ist von {n['fremd']} belegt. NInfer wurde nicht gestartet.")
        for pfad in (e['programm'], e['modelldatei']):
            if not os.path.exists(pfad):
                raise Fehler(f'Datei fehlt: {pfad}')
        prozess = None
        beginn = time.time()
        if n['zustand'] != 'startet':
            log_basis = os.path.join(self.logs, 'ninfer')
            # Nur die gewählte Karte ist sichtbar (Nummern wie nvidia-smi); für NInfer ist sie dann „--device 0“.
            env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', CUDA_VISIBLE_DEVICES=str(karte))
            prozess = winapi.starte_losgeloest([e['programm'], e['modelldatei']] + e['argumente'],
                                               os.path.dirname(e['programm']), env, log_basis=log_basis)
            self.log(f'NInfer gestartet auf Karte {karte}, PID {prozess.pid}, Port {e["port"]}')
        url = f"http://127.0.0.1:{e['port']}/v1/models"
        frist = time.time() + e.get('startzeit_max_s', 240)
        while time.time() < frist:
            if prozess is not None and prozess.poll() is not None:
                grund = _letzte_meldung(os.path.join(self.logs, 'ninfer.err.log'))
                raise Fehler(f'NInfer hat sich beim Start beendet. {grund}'.strip())
            try:
                ids = [m.get('id') for m in (http_json(url, timeout=1.0) or {}).get('data', [])]
                if e['modell_id'] in ids:
                    return f"{e['name']} ist bereit ({round(time.time() - beginn)} s)."
            except Exception:
                pass
            time.sleep(1)
        raise Fehler(f"NInfer antwortet nach {e.get('startzeit_max_s', 240)} s nicht.")

    def _ninfer_stoppen(self, e):
        roh = self.erf.messen()
        procs = roh['procs']
        ziele = [p for p, (_, nm) in procs.items() if nm.lower() == 'ninfer-serve.exe' and self.erf.ist_ninfer(p, procs)]
        if not ziele:
            return f"{e['name']} lief nicht."
        for pid in ziele:
            winapi.beenden(pid)
            self.log(f'NInfer beendet, PID {pid}')
        frei = _warten(lambda: e['port'] not in {p for _, p, _ in winapi.lauschende_ports()}, 10, 0.5)
        if not frei:
            raise Fehler(f"Port {e['port']} ist nach dem Beenden noch belegt.")
        return f"{e['name']} beendet."

    # ------------------------------------------------------------ Strata

    def _strata_starten(self, e):
        s = self.erf.messen()['dienste']['strata']
        if s['zustand'] == 'bereit':
            return f"{e['name']} läuft bereits."
        if s['zustand'] == 'fremd':
            raise Fehler(f"Port {e['port']} ist von {s['fremd']} belegt. Strata wurde nicht gestartet.")
        for pfad in (e['python'], e['server_skript'], e['engine'], e['konfig']):
            if not os.path.exists(pfad):
                raise Fehler(f'Datei fehlt: {pfad}')
        prozess = None
        beginn = time.time()
        if s['zustand'] != 'startet':
            frei = winapi.freier_arbeitsspeicher_mib() / 1024
            bedarf = e['ram_bedarf_gib']
            if frei < bedarf:
                frei_text = f'{frei:.1f}'.replace('.', ',')
                bedarf_text = f'{bedarf:.1f}'.replace('.', ',')
                raise Fehler(f'Zu wenig freier Arbeitsspeicher: {frei_text} GiB frei, '
                             f'Strata braucht etwa {bedarf_text} GiB. Bitte große Programme schließen.')
            env = dict(os.environ, PYTHONIOENCODING='utf-8')
            prozess = winapi.starte_losgeloest(
                [e['python'], e['server_skript'], '--engine', 'strata', '--config', e['konfig'],
                 '--port', str(e['port'])] + (['--fit-max-tokens'] if e.get('fit_max_tokens') else []),
                os.path.dirname(os.path.dirname(e['server_skript'])),
                env, log_basis=os.path.join(self.logs, 'strata'))
            self.log(f'Strata gestartet ({os.path.basename(e["konfig"])}), PID {prozess.pid}, Port {e["port"]}')
        url = f"http://127.0.0.1:{e['port']}/health"
        frist = time.time() + e.get('startzeit_max_s', 300)
        while time.time() < frist:
            if prozess is not None and prozess.poll() is not None:
                grund = _letzte_meldung(os.path.join(self.logs, 'strata.out.log'))
                raise Fehler(f'Strata hat sich beim Start beendet. {grund}'.strip())
            try:
                h = http_json(url, timeout=1.0) or {}
                if h.get('loaded'):
                    kontext = f"{h['max_context']:,}".replace(',', '.')
                    return f"{e['name']} ist bereit ({round(time.time() - beginn)} s, Kontext {kontext})."
            except Exception:
                pass
            time.sleep(1)
        raise Fehler(f"Strata antwortet nach {e.get('startzeit_max_s', 300)} s nicht.")

    def _strata_stoppen(self, e):
        procs = self.erf.messen()['procs']
        ziele = [p for p in procs if self.erf.ist_strata(p, procs)]
        if not ziele:
            return f"{e['name']} lief nicht."
        # Erst die Engine, dann der Bildprozess, dann Python-Dienste und Starter.
        def reihenfolge(pid):
            pfad = self.erf.info(pid, procs[pid][1])['pfad']
            return 0 if pfad == self.erf.strata_engine else 1 if pfad == self.erf.strata_vision else 2
        ziele.sort(key=reihenfolge)
        for pid in ziele:
            winapi.beenden(pid)
            self.log(f'Strata beendet, PID {pid}')

        def frei():
            procs = winapi.prozesse()
            return (e['port'] not in {p for _, p, _ in winapi.lauschende_ports()} and
                    not any(self.erf.ist_strata(p, procs) for p in procs))
        if not _warten(frei, 15, 0.5):
            raise Fehler(f"Strata ist nach dem Beenden noch nicht aus (Port {e['port']} oder Prozesse noch vorhanden).")
        return f"{e['name']} beendet."

    # ------------------------------------------------------------ PolyStrata (Ornith auf einer Karte)

    def _polystrata_starten(self, e, karte=None):
        """PolyStratas Server (Strata-artig) mit seiner Einstellung; die Zentrale wählt die Karte (`--gpu`)."""
        if karte is None:
            raise Fehler(f"Keine Karte für {e['name']} gewählt.")
        s = self.erf.messen()['dienste'][e['id']]
        if s['zustand'] == 'bereit':
            return f"{e['name']} läuft bereits."
        if s['zustand'] == 'fremd':
            raise Fehler(f"Port {e['port']} ist von {s['fremd']} belegt. {e['name']} wurde nicht gestartet.")
        for pfad in (e['python'], e['server_skript'], e['engine'], e['vision_exe'], e['konfig']):
            if not os.path.exists(pfad):
                raise Fehler(f'Datei fehlt: {pfad}')
        prozess = None
        beginn = time.time()
        if s['zustand'] != 'startet':
            frei = winapi.freier_arbeitsspeicher_mib() / 1024
            bedarf = e['ram_bedarf_gib']
            if frei < bedarf:
                frei_text = f'{frei:.1f}'.replace('.', ',')
                bedarf_text = f'{bedarf:.1f}'.replace('.', ',')
                raise Fehler(f"Zu wenig freier Arbeitsspeicher: {frei_text} GiB frei, {e['name']} braucht etwa "
                             f"{bedarf_text} GiB. Bitte große Programme schließen.")
            env = dict(os.environ, PYTHONIOENCODING='utf-8')
            prozess = winapi.starte_losgeloest(
                [e['python'], e['server_skript'], '--engine', 'strata', '--config', e['konfig'],
                 '--port', str(e['port']), '--gpu', str(karte)] + (['--fit-max-tokens'] if e.get('fit_max_tokens') else []),
                os.path.dirname(os.path.dirname(e['server_skript'])), env, log_basis=os.path.join(self.logs, e['id']))
            self.log(f"{e['name']} gestartet auf Karte {karte} ({os.path.basename(e['konfig'])}), PID {prozess.pid}, "
                     f"Port {e['port']}")
        url = f"http://127.0.0.1:{e['port']}/health"
        frist = time.time() + e.get('startzeit_max_s', 180)
        while time.time() < frist:
            if prozess is not None and prozess.poll() is not None:
                grund = _letzte_meldung(os.path.join(self.logs, e['id'] + '.out.log'))
                raise Fehler(f"{e['name']} hat sich beim Start beendet. {grund}".strip())
            try:
                h = http_json(url, timeout=1.0) or {}
                if h.get('loaded'):
                    kontext = f"{h['max_context']:,}".replace(',', '.')
                    return f"{e['name']} ist bereit ({round(time.time() - beginn)} s, Kontext {kontext})."
            except Exception:
                pass
            time.sleep(1)
        raise Fehler(f"{e['name']} antwortet nach {e.get('startzeit_max_s', 180)} s nicht.")

    def _polystrata_stoppen(self, e):
        procs = self.erf.messen()['procs']
        ziele = [p for p in procs if self.erf.ist_polystrata(p, procs) == e['id']]
        if not ziele:
            return f"{e['name']} lief nicht."
        engine, vision = norm(e['engine']), norm(e['vision_exe'])

        # Erst die Engine, dann der Bildprozess, dann Python-Dienst und Starter.
        def reihenfolge(pid):
            pfad = self.erf.info(pid, procs[pid][1])['pfad']
            return 0 if pfad == engine else 1 if pfad == vision else 2
        ziele.sort(key=reihenfolge)
        for pid in ziele:
            winapi.beenden(pid)
            self.log(f"{e['name']} beendet, PID {pid}")

        def frei():
            procs = winapi.prozesse()
            return (e['port'] not in {p for _, p, _ in winapi.lauschende_ports()} and
                    not any(self.erf.ist_polystrata(p, procs) == e['id'] for p in procs))
        if not _warten(frei, 15, 0.5):
            raise Fehler(f"{e['name']} ist nach dem Beenden noch nicht aus (Port {e['port']} oder Prozesse noch vorhanden).")
        return f"{e['name']} beendet."

    # ------------------------------------------------------------ Allgemeine Python-Dienste (z. B. Fibo 2.0)

    def _python_dienst_prozesse(self, e, procs=None):
        procs = procs if procs is not None else self.erf.messen()['procs']
        return [p for p in procs if self.erf.ist_python_dienst(p, procs) == e['id']]

    def _python_dienst_starten(self, e, karte=None):
        """Python-Skript als Dienst starten; die Karte kommt über CUDA_VISIBLE_DEVICES."""
        if karte is None:
            raise Fehler(f"Keine Karte für {e['name']} gewählt.")
        s = self.erf.messen()['dienste'][e['id']]
        if s['zustand'] == 'bereit':
            return f"{e['name']} läuft bereits."
        if s['zustand'] == 'fremd':
            raise Fehler(f"Port {e['port']} ist von {s['fremd']} belegt. {e['name']} wurde nicht gestartet.")
        for pfad in (e['python'], e['skript']):
            if not os.path.exists(pfad):
                raise Fehler(f'Datei fehlt: {pfad}')
        prozess = None
        beginn = time.time()
        if s['zustand'] != 'startet':
            if e.get('ram_bedarf_gib'):
                frei = winapi.freier_arbeitsspeicher_mib() / 1024
                bedarf = e['ram_bedarf_gib']
                if frei < bedarf:
                    frei_text = f'{frei:.1f}'.replace('.', ',')
                    bedarf_text = f'{bedarf:.1f}'.replace('.', ',')
                    raise Fehler(f"Zu wenig freier Arbeitsspeicher: {frei_text} GiB frei, {e['name']} braucht etwa "
                                 f"{bedarf_text} GiB. Bitte große Programme schließen.")
            argv = [e['python'], e['skript']] + list(e.get('argumente') or []) + ['--port', str(e['port'])]
            env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', CUDA_VISIBLE_DEVICES=str(karte),
                       PYTHONIOENCODING='utf-8')
            prozess = winapi.starte_losgeloest(argv, os.path.dirname(e['skript']), env,
                                               log_basis=os.path.join(self.logs, e['id']))
            self.log(f"{e['name']} gestartet auf Karte {karte}, PID {prozess.pid}, Port {e['port']}")
        url = f"http://127.0.0.1:{e['port']}{e.get('health_pfad', '/health')}"
        frist = time.time() + e.get('startzeit_max_s', 300)
        while time.time() < frist:
            # Der uv-Starter darf sich beenden, solange sein Kindprozess noch läuft. Erst wenn kein Dienstprozess
            # mehr zu finden ist, gilt der Start als gescheitert.
            if prozess is not None and prozess.poll() is not None and not self._python_dienst_prozesse(e):
                # Dem uv-Starter kurz Zeit lassen, sein Kind zu starten, bevor der Start als gescheitert gilt.
                time.sleep(0.5)
                if not self._python_dienst_prozesse(e):
                    grund = _letzte_meldung(os.path.join(self.logs, e['id'] + '.err.log'))
                    raise Fehler(f"{e['name']} hat sich beim Start beendet. {grund}".strip())
            try:
                if (http_json(url, timeout=1.0) or {}).get('status') == 'ok':
                    return f"{e['name']} ist bereit ({round(time.time() - beginn)} s)."
            except Exception:
                pass
            time.sleep(1)
        raise Fehler(f"{e['name']} antwortet nach {e.get('startzeit_max_s', 300)} s nicht.")

    def _python_dienst_stoppen(self, e, erzwingen=False):
        """Den ganzen Prozessbaum beenden (uv-Starter und Kind) und warten, bis der Port frei ist."""
        roh = self.erf.messen()
        procs = roh['procs']
        ziele = self._python_dienst_prozesse(e, procs)
        if not ziele:
            return f"{e['name']} lief nicht."
        if not erzwingen:
            try:
                h = http_json(f"http://127.0.0.1:{e['port']}{e.get('health_pfad', '/health')}",
                              timeout=1.0) or {}
                laufend = h.get('laufend')
            except Exception:
                laufend = None
            if laufend:
                raise Fehler(f"In {e['name']} läuft gerade ein Auftrag ({laufend}). Der Dienst wurde nicht beendet.")
        # Frischer Stand, damit auch ein gerade gestartetes Kind erfasst wird.
        procs = winapi.prozesse()
        ziele = self._python_dienst_prozesse(e, procs)
        if not ziele:
            return f"{e['name']} lief nicht."
        baum = set(ziele)
        geaendert = True
        while geaendert:
            geaendert = False
            for pid, (eltern, _) in procs.items():
                if eltern in baum and pid not in baum:
                    baum.add(pid)
                    geaendert = True

        def tiefe(pid):
            t, gesehen = 0, set()
            while pid in procs and pid not in gesehen:
                gesehen.add(pid)
                eltern = procs[pid][0]
                if eltern == pid or eltern not in baum:
                    break
                t += 1
                pid = eltern
            return t

        # Erst die Kinder, dann die Eltern: so bleibt kein Kind ohne Vater weiterlaufen.
        for pid in sorted(baum, key=lambda p: (-tiefe(p), p)):
            winapi.beenden(pid)
            self.log(f"{e['name']} beendet, PID {pid}")

        def frei():
            frisch = winapi.prozesse()
            return (e['port'] not in {p for _, p, _ in winapi.lauschende_ports()} and
                    not any(self.erf.ist_python_dienst(p, frisch) == e['id'] for p in frisch))
        if not _warten(frei, 15, 0.5):
            raise Fehler(f"{e['name']} ist nach dem Beenden noch nicht aus (Port {e['port']} oder Prozesse noch "
                         f'vorhanden).')
        return f"{e['name']} beendet."

    # ------------------------------------------------------------ llama.cpp (z. B. LightOnOCR)

    def _llamacpp_starten(self, e, karte=None):
        if karte is None:
            raise Fehler(f"Keine Karte für {e['name']} gewählt.")
        s = self.erf.messen()['dienste'][e['id']]
        if s['zustand'] == 'bereit':
            return f"{e['name']} läuft bereits."
        if s['zustand'] == 'fremd':
            raise Fehler(f"Port {e['port']} ist von {s['fremd']} belegt. {e['name']} wurde nicht gestartet.")
        for pfad in (e['programm'], e['modelldatei'], e.get('mmproj')):
            if pfad and not os.path.exists(pfad):
                raise Fehler(f'Datei fehlt: {pfad}')
        prozess = None
        beginn = time.time()
        if s['zustand'] != 'startet':
            argv = [e['programm'], '-m', e['modelldatei']]
            if e.get('mmproj'):
                argv += ['--mmproj', e['mmproj']]
            argv += ['--host', '127.0.0.1', '--port', str(e['port']), '--alias', e['modell_id']] + e['argumente']
            # Die gewählte Karte; Nummern wie nvidia-smi (Reihenfolge der Steckplätze).
            env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', CUDA_VISIBLE_DEVICES=str(karte))
            prozess = winapi.starte_losgeloest(argv, os.path.dirname(e['programm']), env,
                                               log_basis=os.path.join(self.logs, e['id']))
            self.log(f"{e['name']} gestartet auf Karte {karte}, PID {prozess.pid}, Port {e['port']}")
        url = f"http://127.0.0.1:{e['port']}/health"
        frist = time.time() + e.get('startzeit_max_s', 120)
        while time.time() < frist:
            if prozess is not None and prozess.poll() is not None:
                grund = _letzte_meldung(os.path.join(self.logs, e['id'] + '.err.log'))
                raise Fehler(f"{e['name']} hat sich beim Start beendet. {grund}".strip())
            try:
                if (http_json(url, timeout=1.0) or {}).get('status') == 'ok':
                    return f"{e['name']} ist bereit ({round(time.time() - beginn)} s)."
            except Exception:
                pass
            time.sleep(1)
        raise Fehler(f"{e['name']} antwortet nach {e.get('startzeit_max_s', 120)} s nicht.")

    def _llamacpp_stoppen(self, e):
        procs = self.erf.messen()['procs']
        ziele = [p for p in procs if self.erf.ist_llamacpp(p, procs) == e['id']]
        if not ziele:
            return f"{e['name']} lief nicht."
        for pid in ziele:
            winapi.beenden(pid)
            self.log(f"{e['name']} beendet, PID {pid}")

        def frei():
            procs = winapi.prozesse()
            return (e['port'] not in {p for _, p, _ in winapi.lauschende_ports()} and
                    not any(self.erf.ist_llamacpp(p, procs) == e['id'] for p in procs))
        if not _warten(frei, 10, 0.5):
            raise Fehler(f"{e['name']} ist nach dem Beenden noch nicht aus (Port {e['port']} oder Prozess noch vorhanden).")
        return f"{e['name']} beendet."

    # ------------------------------------------------------------ Ollama

    def _ollama_bereit(self):
        if http_erreichbar(self.ollama_url + '/api/version'):
            return
        app = self.cfg['ollama']['app']
        if not os.path.exists(app):
            raise Fehler('Ollama läuft nicht, und die Ollama-App wurde nicht gefunden.')
        winapi.starte_losgeloest([app], os.path.dirname(app))
        self.log('Ollama-App gestartet')
        if not _warten(lambda: http_erreichbar(self.ollama_url + '/api/version'), 45):
            raise Fehler('Ollama antwortet nach 45 s nicht.')

    def _ollama_geladen(self):
        return [m.get('name') or m.get('model') for m in (http_json(self.ollama_url + '/api/ps', timeout=3) or {}).get('models', [])]

    def _ollama_laden(self, e):
        self._ollama_bereit()
        if e['tag'] in self._ollama_geladen():
            return f"{e['name']} ist bereits geladen."
        beginn = time.time()
        try:
            anfrage = {'model': e['tag'], 'keep_alive': -1, 'stream': False}
            if e.get('ollama_optionen'):
                # Andere Apps müssen dieselben Optionen schicken, sonst lädt Ollama das Modell neu (die Werkstatt
                # schickt dazu den Kontext, mit dem das Modell gerade geladen ist).
                anfrage['options'] = e['ollama_optionen']
            http_json(self.ollama_url + '/api/generate', anfrage, timeout=e.get('startzeit_max_s', 600))
        except Exception as ex:
            raise Fehler(f"{e['name']} konnte nicht geladen werden: {ex}")
        if e['tag'] not in self._ollama_geladen():
            raise Fehler(f"{e['name']} erscheint nach dem Laden nicht in Ollama.")
        self.log(f"Ollama-Modell geladen: {e['tag']}" + (f" ({e['variante']})" if e.get('variante') else ''))
        name = e['name'] + (f" ({e['variante_name']})" if e.get('variante_name') else '')
        return f"{name} geladen ({round(time.time() - beginn)} s)."

    def _ollama_entladen(self, tag, name):
        if not http_erreichbar(self.ollama_url + '/api/version'):
            return f'{name} war nicht geladen.'
        modelle = (http_json(self.ollama_url + '/api/ps', timeout=3) or {}).get('models', [])
        m = next((m for m in modelle if (m.get('name') or m.get('model')) == tag), None)
        if m is None:
            return f'{name} war nicht geladen.'
        belegt_vorher = sum(k['belegt'] for k in self.erf.messen()['karten'])
        http_json(self.ollama_url + '/api/generate', {'model': tag, 'keep_alive': 0, 'stream': False}, timeout=60)
        if not _warten(lambda: tag not in self._ollama_geladen(), 20, 0.5):
            raise Fehler(f'{name} ist nach 20 s noch geladen.')
        # Ollama meldet das Modell schon als entladen, bevor der Treiber den Speicher zurückgibt.
        erwartet = 0.8 * (m.get('size_vram') or 0) / 1048576
        _warten(lambda: belegt_vorher - sum(k['belegt'] for k in self.erf.messen()['karten']) >= erwartet, 15, 0.5)
        self.log(f'Ollama-Modell entladen: {tag}')
        return f'{name} entladen.'

    # ------------------------------------------------------------ ComfyUI (2Wild ist stillgelegt)

    def _comfy_starten(self, e):
        fehlend = [os.path.basename(p) for p in e['pflichtdateien']
                   if not os.path.exists(os.path.join(e['comfy_ordner'], p))]
        if fehlend:
            raise Fehler('Es fehlen Modelldateien: ' + ', '.join(fehlend))
        python = os.path.join(e['comfy_ordner'], '.venv', 'Scripts', 'python.exe')
        if not os.path.exists(python):
            raise Fehler(f'ComfyUI-Python fehlt: {python}')
        d = self.erf.messen()['dienste']
        if d['comfy']['fremd']:
            raise Fehler(f"Port {e['comfy_port']} ist von {d['comfy']['fremd']} belegt.")
        for w in e.get('comfy_weitere') or []:
            dienst = d.get(f"comfy{w['nr']}") or {}
            if dienst.get('fremd'):
                raise Fehler(f"Port {w['port']} ist von {dienst['fremd']} belegt.")
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID')
        beginn = time.time()
        comfy_url = f"http://127.0.0.1:{e['comfy_port']}/system_stats"
        # 2Wild Studio wird seit Stufe 3c nicht mehr gestartet; Bilder und Videos entstehen im Studio der Werkstatt.
        if not d['comfy']['pid']:
            # Bilder und Videos landen direkt im Studio der Werkstatt (Projekte = Unterordner), keine Kopien.
            os.makedirs(e['ausgabe_ordner'], exist_ok=True)
            p = winapi.starte_losgeloest(
                [python, 'main.py', '--listen', '127.0.0.1', '--port', str(e['comfy_port']),
                 '--cuda-device', ','.join(map(str, e.get('comfy_karten', [0, 1]))),
                 '--default-device', '0', '--output-directory', e['ausgabe_ordner']],
                e['comfy_ordner'], env, log_basis=os.path.join(self.logs, 'comfyui'))
            self.log(f'ComfyUI gestartet, PID {p.pid}')
            frist = time.time() + e.get('startzeit_max_s', 300)
            while not http_erreichbar(comfy_url):
                if p.poll() is not None:
                    raise Fehler('ComfyUI hat sich beim Start beendet. '
                                 + _letzte_meldung(os.path.join(self.logs, 'comfyui.err.log')))
                if time.time() > frist:
                    raise Fehler('ComfyUI antwortet nach dem Start nicht.')
                time.sleep(1)
        for w in e.get('comfy_weitere') or []:
            if not (d.get(f"comfy{w['nr']}") or {}).get('pid'):
                self._comfy_weiterer_starten(e, w, python, env)
        return f"Bild & Video ist bereit ({round(time.time() - beginn)} s)."

    def _comfy_weiterer_starten(self, e, w, python, env):
        """Ein weiterer ComfyUI-Prozess (Stufe 8): dieselbe Installation und Ausgabe, eigener Port, eigene
        temp-/user-Ordner, sieht nur die Karte `karte` (darin heißt sie gpu:0). So rechnen mehrere Studio-Aufträge
        gleichzeitig; Aufträge über zwei Karten bleiben beim ersten Prozess."""
        nr = w['nr']
        temp = os.path.join(e['comfy_ordner'], f'temp-{nr}')
        user = os.path.join(e['comfy_ordner'], f'user-{nr}')
        os.makedirs(temp, exist_ok=True)
        os.makedirs(user, exist_ok=True)
        p = winapi.starte_losgeloest(
            [python, 'main.py', '--listen', '127.0.0.1', '--port', str(w['port']),
             '--cuda-device', str(w['karte']), '--output-directory', e['ausgabe_ordner'],
             '--temp-directory', temp, '--user-directory', user],
            e['comfy_ordner'], env, log_basis=os.path.join(self.logs, f'comfyui-{nr}'))
        self.log(f'ComfyUI {nr} gestartet, PID {p.pid}')
        url = f"http://127.0.0.1:{w['port']}/system_stats"
        frist = time.time() + e.get('startzeit_max_s', 300)
        while not http_erreichbar(url):
            if p.poll() is not None:
                raise Fehler(f'Der ComfyUI-Prozess {nr} hat sich beim Start beendet. '
                             + _letzte_meldung(os.path.join(self.logs, f'comfyui-{nr}.err.log')))
            if time.time() > frist:
                raise Fehler(f'Der ComfyUI-Prozess {nr} antwortet nach dem Start nicht.')
            time.sleep(1)

    def _comfy_beenden(self, pid, procs):
        """Beendet den Dienst und seinen Python-Starter aus dem ComfyUI-Ordner."""
        eltern = procs.get(pid, (None, ''))[0]
        winapi.beenden(pid)
        self.log(f'Prozess beendet, PID {pid}')
        if eltern in procs:
            info = self.erf.info(eltern, procs[eltern][1])
            if info['pfad'].startswith(self.erf.comfy_ordner) and info['name'].lower() == 'python.exe':
                if not _warten(lambda: eltern not in winapi.prozesse(), 3, 0.3):
                    winapi.beenden(eltern)
                    self.log(f'Python-Starter beendet, PID {eltern}')

    def _comfy_stoppen(self, e, erzwingen):
        roh = self.erf.messen()
        c, s, procs = roh['dienste']['comfy'], roh['dienste']['studio'], roh['procs']
        weitere = [roh['dienste'].get(f"comfy{w['nr']}") or {'pid': None, 'auftraege_laufend': 0}
                   for w in e.get('comfy_weitere') or []]
        if (c['auftraege_laufend'] or any(w['auftraege_laufend'] for w in weitere)) and not erzwingen:
            raise Fehler('In ComfyUI läuft gerade ein Auftrag. Bild & Video wurde nicht beendet.')
        if not c['pid'] and not s['pid'] and not any(w['pid'] for w in weitere):
            return 'Bild & Video lief nicht.'
        for pid in [s['pid'], c['pid']] + [w['pid'] for w in weitere]:
            if pid:
                self._comfy_beenden(pid, procs)
        ports = tuple(p for p in (e['comfy_port'], e['studio_port'],
                                  *(w['port'] for w in e.get('comfy_weitere') or [])) if p)
        if not _warten(lambda: not any(p in ports for _, p, _ in winapi.lauschende_ports()), 10, 0.5):
            raise Fehler('Ein Port von Bild & Video ist nach dem Beenden noch belegt.')
        return 'Bild & Video beendet.'

    def _comfy_freigeben(self, ziel='bild-video'):
        e = self.eintraege.get('bild-video') or {}
        if ziel == 'bild-video':
            dienst, name, port = 'comfy', e.get('name') or 'ComfyUI', e['comfy_port']
        else:
            try:
                nr = int(ziel.rsplit('-', 1)[1])
            except (IndexError, ValueError):
                raise Fehler(f'Unbekannter Schritt: freigeben:{ziel}')
            w = next((w for w in self._comfy_weitere() if w['nr'] == nr), None)
            if w is None:
                raise Fehler(f'Unbekannter Schritt: freigeben:{ziel}')
            dienst, port = f'comfy{nr}', w['port']
            name = w.get('name') or f'ComfyUI {nr}'
        c = self.erf.messen()['dienste'][dienst]
        if not c['laeuft']:
            return f'{name} lief nicht.'
        if c['auftraege_laufend']:
            raise Fehler(f'In {name} läuft gerade ein Auftrag. Modelle wurden nicht entladen.')
        http_json(f'http://127.0.0.1:{port}/free', {'unload_models': True, 'free_memory': True}, timeout=10)
        self.log(f'{name}: Modelle entladen')
        return f'Modelle aus {name} entladen.'

    def _comfy_weitere(self):
        """Die weiteren ComfyUI-Prozesse aus der Erfassung (oder der Konfiguration)."""
        liste = getattr(self.erf, 'comfy_weitere', None)
        if isinstance(liste, (list, tuple)):
            return liste
        return (self.eintraege.get('bild-video') or {}).get('comfy_weitere') or []

    # ------------------------------------------------------------ Programme

    def _programm_beenden(self, e):
        ziel = norm(e['programm'])
        exe = os.path.basename(ziel)

        def passt(pid):
            # Frisch lesen: Eine inzwischen wiederverwendete PID darf keinen fremden Prozess treffen.
            details = winapi.prozess_details(pid)
            return details is not None and norm(details[0]) == ziel

        def pids():
            return [p for p, (_, nm) in winapi.prozesse().items()
                    if nm.lower() == exe and passt(p)]

        ziele = pids()
        if not ziele:
            return f"{e['name']} lief nicht."
        winapi.fenster_schliessen(ziele)
        for pid in ziele:
            self.log(f"{e['name']}: Fenster schließen angefordert, PID {pid}")
        if not _warten(lambda: not pids(), 8, 0.5):
            for pid in pids():
                if passt(pid):
                    winapi.beenden(pid)
                    self.log(f"{e['name']} beendet, PID {pid}")
        if not _warten(lambda: not pids(), 5, 0.5):
            raise Fehler(f"{e['name']} läuft nach dem Beenden noch (Prozesse noch vorhanden).")
        return f"{e['name']} beendet."

    def _programm_oeffnen(self, e):
        def pids():
            return set(self.erf.messen()['dienste'][e['id']]['pids'])
        if pids():
            # Direkt nach dem Start zeigt eine Electron-App ihr Fenster erst nach einigen Sekunden.
            if _warten(lambda: winapi.fenster_vorholen(pids()), 15, 1.0):
                return f"{e['name']} in den Vordergrund geholt."
            return f"{e['name']} läuft, zeigt aber kein Fenster. Vielleicht ist es in den Infobereich minimiert."
        if not os.path.exists(e['programm']):
            raise Fehler(f"{e['name']} ist nicht installiert: {e['programm']}")
        winapi.starte_losgeloest([e['programm']], os.path.dirname(e['programm']))
        self.log(f"{e['name']} gestartet")
        return f"{e['name']} gestartet."
