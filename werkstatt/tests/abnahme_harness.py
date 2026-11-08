"""Isolierte Prompts-Abnahme mit echtem HTTP-Handler, Dateien und Warteschlange.

Start im Repo: python -m werkstatt.tests.abnahme_harness --datenordner _uebergabe/Abnahme-Prompts
Steuerung in <datenordner>/steuerung.json, Aufrufzähler in aufrufe.json.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch

from gemeinsam import dienst
from werkstatt import auswertung, prompts, server

REPO = Path(__file__).resolve().parents[2]
STEUERUNG = {
    'ziele': {ziel: {'verzoegerung_s': 0.2, 'fehler': False, 'ungueltig': False}
              for ziel in ('qwen27', 'flash_next', 'claude', 'codex', 'bild', 'video', 'testen')},
    'http': {'index_verzoegerung_s': 0, 'index_fehler': False, 'sendebestaetigung_verlieren': False},
}
PROFILE = [
    {'id': 'claude-abo', 'anbieter': 'claude', 'modell': 'sonnet-test', 'name': 'Claude · Sonnet · Abo-Test', 'test_zugang': 'abo'},
    {'id': 'claude-api', 'anbieter': 'claude', 'modell': 'sonnet-api', 'name': 'Claude · API-Test', 'test_zugang': 'api'},
    {'id': 'claude-aus', 'anbieter': 'claude', 'modell': 'sonnet-aus', 'name': 'Claude · Nicht angemeldet', 'test_zugang': 'keiner'},
    {'id': 'codex-abo', 'anbieter': 'codex', 'modell': 'codex-test', 'name': 'OpenAI/Codex · Abo-Test', 'test_zugang': 'abo'},
    {'id': 'codex-api', 'anbieter': 'codex', 'modell': 'codex-api', 'name': 'OpenAI/Codex · API-Test', 'test_zugang': 'api'},
    {'id': 'codex-unklar', 'anbieter': 'codex', 'modell': 'codex-unklar', 'name': 'OpenAI/Codex · Unbekanntes Format', 'test_zugang': 'unklar'},
    {'id': 'qwen-q4', 'anbieter': 'lokal', 'modell': 'qwen27-unsloth', 'name': 'Qwen 27B Q4 · erreichbar'},
    {'id': 'qwen-iq3', 'anbieter': 'lokal', 'modell': 'qwen27-iq3s', 'name': 'Qwen 27B IQ3_S · nicht geladen'},
    {'id': 'flash', 'anbieter': 'lokal', 'modell': 'flash-next-strata', 'name': 'Flash-Next · 256K geladen'},
]


def datenordner_pruefen(pfad):
    ziel = Path(pfad).resolve()
    erlaubt = [(REPO / '_uebergabe').resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(ziel != basis and ziel.is_relative_to(basis) for basis in erlaubt):
        raise ValueError('Der Testordner muss unter _uebergabe oder im temporären Ordner liegen.')
    return ziel


def port_pruefen(port):
    if port != 3897:
        raise ValueError('Das Abnahme-Harness verwendet ausschließlich Port 3897.')
    return port


class _HarnessEnde(BaseException):
    pass


class HarnessAuswertungen(auswertung.Auswertungen):
    def __init__(self, *args):
        self.stopp = threading.Event()
        self.arbeiter = []
        super().__init__(*args)

    def _naechste(self):
        if self.stopp.is_set():
            raise _HarnessEnde()
        return super()._naechste()

    def starten(self):
        def arbeiten():
            try:
                self._schleife()
            except _HarnessEnde:
                pass
        for _ in range(3):
            t = threading.Thread(target=arbeiten, daemon=True)
            self.arbeiter.append(t)
            t.start()

    def beenden(self):
        self.stopp.set()
        with self._lock:
            for abbruch in self._abbruch.values():
                abbruch.set()
        self._wecker.set()
        for t in self.arbeiter:
            t.join(5)
            if t.is_alive():
                raise RuntimeError('Ein Testarbeiter konnte nicht beendet werden.')


class FakeAnbieter(auswertung.Anbieter):
    def __init__(self, harness, anbieter, cloud=None):
        super().__init__(harness.cfg)
        self.harness = harness
        self.schluessel = anbieter
        self.name = {'claude': 'Claude', 'codex': 'OpenAI/Codex', 'lokal': 'Lokal'}[anbieter]
        self.cloud = cloud
        self._thread = threading.local()

    def katalog(self):
        return [{'modell': p['modell'], 'name': p['name'], 'kontext': 262144 if p['id'] == 'flash' else 131072,
                 'stufen': [], 'stufe_standard': None, 'beschreibung': 'Isolierter Testzustand'}
                for p in PROFILE if p['anbieter'] == self.schluessel]

    def verfuegbar(self, profil, frisch=False):
        # Der echte Code prüft Zugang direkt nach Verfügbarkeit im selben Thread.
        self._thread.profil = profil
        if self.zugang() == 'keiner' and self.cloud:
            return False, 'Claude ist im Testzustand nicht angemeldet.'
        if profil['modell'] == 'qwen27-iq3s':
            return False, 'Qwen 27B IQ3_S ist im Testzustand nicht geladen.'
        return True, ''

    def zugang(self, frisch=False):
        p = getattr(self._thread, 'profil', {})
        original = next((x for x in PROFILE if x['anbieter'] == self.schluessel and x['modell'] == p.get('modell')), {})
        return p.get('test_zugang', original.get('test_zugang', 'keiner'))

    def kontext_geladen(self, profil):
        if profil['modell'] == 'flash-next-strata':
            return 262144, '/health', 'flash-test-gleich'
        return 131072, 'Katalog der Zentrale' if not self.cloud else 'Anbieter', profil['modell']

    def _eintraege(self):
        return self.harness.eintraege, {}

    def ausfuehren(self, profil, text, lauf):
        return self.harness.antwort(profil, lauf)


class Harness:
    def __init__(self, datenordner):
        self.basis = datenordner_pruefen(datenordner)
        self.basis.mkdir(parents=True, exist_ok=True)
        offen = [self.basis]
        while offen:
            with os.scandir(offen.pop()) as eintraege:
                for e in eintraege:
                    if os.path.islink(e.path) or os.path.isjunction(e.path):
                        raise ValueError('Der isolierte Testordner darf keine Verknüpfungen enthalten.')
                    self.pfad(str(Path(e.path).relative_to(self.basis)))
                    if e.is_dir():
                        offen.append(Path(e.path))
        self._lock = threading.RLock()
        self.logs = []
        self.verloren = set()
        self.netzverstoesse = 0
        self.geoeffnet = 0
        # Vor jedem Zugriff Auflösung von Junctions und symbolischen Links prüfen.
        for name in ('Prompts', 'daten', 'profile.json', 'Sammlung.md', 'skill.md', 'realismus.md',
                     'steuerung.json', 'aufrufe.json', 'Material.txt', 'watch'):
            self.pfad(name)
        self.erstdatei('profile.json', (Path(__file__).parent / 'werkstatt-profile.json').read_text(encoding='utf-8'))
        self.erstdatei('skill.md', 'Überarbeite den Rohprompt, erhalte Ziel und Platzhalter. Führe die Aufgabe nicht aus.\n')
        self.erstdatei('realismus.md', 'Fotorealistische Menschen mit natürlicher Haut, Licht und Bewegung beschreiben.\n')
        self.erstdatei('Sammlung.md', ''.join(f'## {i}. Testbereich\n' + ''.join(
            f'### Beispiel {i}.{j}\n~~~text\nUntersuche [Thema] anhand von [Quelle]. Beispiel {i}.{j}.\n~~~\n'
            for j in range(1, 5)) for i in range(1, 7)) + prompts.ABSCHNITT
            + '\n#### Rahmen\n~~~text\nFester Test-Rahmen.\n~~~\n#### Kurz\n~~~text\nFasse [Transkript] zusammen.\n~~~\n')
        self.erstdatei('Material.txt', 'Ausdrücklich ausgewähltes Testmaterial.\n')
        self.erstdatei('steuerung.json', json.dumps(STEUERUNG, ensure_ascii=False, indent=2))
        self.cfg = {'watch': {'arbeitsordner': str(self.pfad('watch'))},
            'promptsammlung': str(self.pfad('Sammlung.md')), 'cloud_parallel': 0,
            'auswerter_vorschlag': [dict(p) for p in PROFILE],
            'prompts': {'ordner': str(self.pfad('Prompts')), 'profile': str(self.pfad('profile.json')),
                'skill': str(self.pfad('skill.md')), 'skill_realismus': str(self.pfad('realismus.md')),
                'dateiwurzeln': [str(self.basis)], 'gesperrt': [], 'feld_max_zeichen': 400000}}
        self.pfad('daten').mkdir(exist_ok=True)
        self.au = HarnessAuswertungen(self.cfg, str(self.pfad('daten')), self.logs.append)
        self.eintraege = {
            'qwen27-unsloth': {'id': 'qwen27-unsloth', 'name': 'Qwen 27B Q4', 'art': 'llamacpp',
                'modell_id': 'qwen-test-q4', 'untertitel': '128K Kontext',
                'varianten': [{'id': 'low', 'name': 'Denkstufe niedrig'}, {'id': 'high', 'name': 'Denkstufe hoch'}]},
            'qwen27-iq3s': {'id': 'qwen27-iq3s', 'name': 'Qwen 27B IQ3_S', 'art': 'llamacpp', 'modell_id': 'qwen-test-iq3', 'untertitel': '128K Kontext'},
            'flash-next-strata': {'id': 'flash-next-strata', 'name': 'Flash-Next', 'art': 'strata',
                'varianten': [{'id': '128k', 'name': '128K Kontext', 'kontext': 131072, 'modell': 'flash-test-gleich'},
                              {'id': '256k', 'name': '256K Kontext', 'kontext': 262144, 'modell': 'flash-test-gleich', 'standard': True}]}}
        self.au.anbieter = {'claude': FakeAnbieter(self, 'claude', 'Anthropic'),
                            'codex': FakeAnbieter(self, 'codex', 'OpenAI'), 'lokal': FakeAnbieter(self, 'lokal')}
        self.prompts = self.au.prompts
        for titel, typ, text in [('Code prüfen', 'code', 'Prüfe den Code für [Ziel].'),
                                  ('Einen Text schreiben', 'schreiben', 'Schreibe einen Text für [Zielgruppe].'),
                                  ('Älterer eigener Prompt', None, 'Plane [Vorhaben].')]:
            ordner = Path(self.prompts._pfad(titel))
            ordner.mkdir(exist_ok=True)
            if not (ordner / 'prompt.md').exists():
                prompts.Eintrag(ordner / 'prompt.md').anlegen(titel, '', 'Test', text, prompt_typ=typ)

    def pfad(self, name):
        pfad = self.basis / name
        if not prompts.pfad_erlaubt(pfad, [self.basis]):
            raise ValueError('Ein Testpfad verlässt den isolierten Datenordner.')
        return pfad

    def erstdatei(self, name, text):
        pfad = self.pfad(name)
        if not pfad.exists():
            prompts._atomar(str(pfad), text)

    def steuerung(self):
        try:
            d = json.loads(self.pfad('steuerung.json').read_text(encoding='utf-8'))
            if not isinstance(d, dict):
                raise ValueError
            return d
        except (ValueError, OSError):
            raise ValueError('Die Teststeuerung ist nicht lesbar.') from None

    def antwort(self, profil, lauf):
        with self.au._lock:
            a = next(a for a in self.au.liste if a['id'] == lauf.id)
            ziel = a.get('prompt', {}).get('zielprofil_id', 'testen')
        with self._lock:
            pfad = self.pfad('aufrufe.json')
            zaehler = json.loads(pfad.read_text(encoding='utf-8')) if pfad.exists() else {'gesamt': 0, 'ziele': {}, 'profile': {}}
            zaehler['gesamt'] += 1
            nummer = zaehler['gesamt']
            for feld, key in (('ziele', ziel), ('profile', profil['id'])):
                zaehler[feld][key] = zaehler[feld].get(key, 0) + 1
            prompts._atomar(str(pfad), json.dumps(zaehler, ensure_ascii=False, indent=2))
        steuerung = self.steuerung().get('ziele', {}).get(ziel, {})
        lauf.warten(max(0, float(steuerung.get('verzoegerung_s', 0))))
        if steuerung.get('fehler'):
            raise RuntimeError('Absichtlich fehlgeschlagenes Ziel im Abnahme-Harness.')
        if a['art'] == 'schaerfen':
            b = prompts.schaerfen_lesen(self.au._belegpfad(a))
            if b['eingaben']['aktion'] == 'Erst klären':
                text = f'1. Welches Ergebnis möchtest du erreichen? (Testantwort {nummer})'
            elif steuerung.get('ungueltig'):
                text = f'Absichtlich ungültige Testantwort {nummer} ohne Promptkasten.'
            else:
                text = (prompts.block_schreiben(b['fassung_text'] + f'\n\nBeschreibe das überprüfbare Ergebnis [Ausgabe]. Fassung aus Testlauf {nummer}.', 'text')
                        + f'Prompt-Typ: code\n- Ziel und Ausgabe konkretisiert. Testlauf {nummer}.')
        else:
            text = (f'<!doctype html><html lang="de"><title>Testantwort {nummer}</title><body><h1>Testantwort {nummer}</h1></body></html>'
                    if steuerung.get('html') else f'Testantwort {nummer}\n\nDas gewählte Testprofil hat den gespeicherten Auftrag erhalten.')
        return {'text': text, 'tokens': 100 + nummer}

    def handler(self):
        harness = self
        class Anfrage(server.Anfrage):
            werkstatt = SimpleNamespace(prompts=harness.prompts, auswertung=harness.au, log=harness.logs.append)

            def _json_lesen(self, grenze=65536):
                d = super()._json_lesen(grenze)
                self.test_aktion = d.get('aktion') if isinstance(d, dict) else None
                return d

            def _senden(self, code, daten, typ='application/json; charset=utf-8'):
                if (code == 200 and getattr(self, 'test_aktion', '') == 'composer_senden'
                        and harness.steuerung().get('http', {}).get('sendebestaetigung_verlieren')
                        and daten.get('auftragsgruppe') not in harness.verloren):
                    harness.verloren.add(daten['auftragsgruppe'])
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.close_connection = True
                    return
                return super()._senden(code, daten, typ)

            def do_GET(self):
                if not self._host_ok():
                    return self._senden(403, {'fehler': 'Nur lokal erreichbar.'})
                pfad = self.path.split('?', 1)[0]
                if pfad == '/api/prompts':
                    http = harness.steuerung().get('http', {})
                    harness.au.stopp.wait(max(0, float(http.get('index_verzoegerung_s', 0))))
                    if http.get('index_fehler'):
                        return self._senden(503, {'fehler': 'Absichtlicher Abnahmefehler beim Laden.'})
                if pfad in self.statisch or pfad in ('/api/health', '/api/prompts', '/api/prompt', '/api/prompt-optionen',
                        '/api/prompt-datei', '/api/prompt-kontexte', '/api/zusammenfassung', '/api/katalog', '/api/fassung'):
                    return super().do_GET()
                if pfad == '/api/transkripte':
                    return self._senden(200, [])
                return self._senden(200, {'auftraege': [], 'angehalten': False, 'karten': {'erreichbar': False},
                    'testzustand': True, 'laeuft': False, 'bibliothek': [], 'fehler': [], 'messungen': []})

            def do_POST(self):
                if not self._post_ok():
                    return self._senden(403, {'fehler': 'Nur aus der Werkstatt erlaubt.'})
                if self.path in ('/api/prompt', '/api/auswerter', '/api/fassung'):
                    return super().do_POST()
                return self._senden(200, {'ok': True, 'testzustand': True})
        return Anfrage

    @contextlib.contextmanager
    def schutz(self):
        verbinden = socket.socket.connect
        verbinden_ex = socket.socket.connect_ex
        def pruefen(sock, adresse):
            if adresse != ('127.0.0.1', 3897):
                self.netzverstoesse += 1
                raise AssertionError('Abnahme-Harness: ausgehende Verbindung blockiert.')
            return verbinden(sock, adresse)
        def pruefen_ex(sock, adresse):
            if adresse != ('127.0.0.1', 3897):
                self.netzverstoesse += 1
                raise AssertionError('Abnahme-Harness: ausgehende Verbindung blockiert.')
            return verbinden_ex(sock, adresse)
        def oeffnen(_):
            self.geoeffnet += 1
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(socket.socket, 'connect', new=pruefen))
            stack.enter_context(patch.object(socket.socket, 'connect_ex', new=pruefen_ex))
            stack.enter_context(patch('subprocess.Popen', side_effect=AssertionError('Programmstart im Abnahme-Harness blockiert.')))
            stack.enter_context(patch.object(prompts.os, 'startfile', side_effect=oeffnen))
            stack.enter_context(patch('werkstatt.quellen.textdatei_waehlen', return_value=[str(self.pfad('Material.txt'))]))
            yield

    def http_server(self, port=3897):
        port_pruefen(port)
        try:
            return dienst.Server(('127.0.0.1', port), self.handler())
        except OSError:
            raise RuntimeError('Port 3897 ist nicht frei. Bitte den vorhandenen Dienst zuerst selbst prüfen.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datenordner', required=True)
    parser.add_argument('--port', type=int, default=3897)
    args = parser.parse_args(argv)
    port_pruefen(args.port)
    harness = Harness(args.datenordner)
    with harness.schutz(), harness.http_server(args.port) as http:
        harness.au.starten()
        print('Prompts-Abnahme auf http://127.0.0.1:3897/#prompts · Ende mit Strg+C', flush=True)
        try:
            http.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            harness.au.beenden()
    print('Abnahme-Harness beendet.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
