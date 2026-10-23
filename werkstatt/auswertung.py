"""Zusammenfassungen mit wählbaren Auswertern: Codex, Claude, DeepSeek, OpenRouter (kostenlos) und lokal.

Ein Auswerter ist Anbieter + Modell (+ Denkstufe) und wird einmal in den Einstellungen
angelegt. Jede Kombination aus Auswerter und Anweisung ergibt eine eigene Fassung als
Markdown-Datei im Videoordner. Cloud-Auswertungen laufen zu zweit parallel; lokale
Modelle rechnen nie gleichzeitig mit Whisper (gemeinsame Sperre mit der Transkription).
"""
import glob
import json
import os
import re
import secrets
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.request

from gemeinsam import winapi

from . import anweisungen, watch_lauf

_OHNE_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_NETZ = urllib.request.build_opener()
HOME = os.path.expanduser('~')
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', os.path.join(HOME, 'AppData', 'Local'))
APPDATA = os.environ.get('APPDATA', os.path.join(HOME, 'AppData', 'Roaming'))
STUFEN_TEXT = {'none': 'ohne Nachdenken', 'low': 'niedrig', 'medium': 'mittel', 'high': 'hoch', 'xhigh': 'sehr hoch',
               'max': 'maximal', 'ultra': 'ultra'}
# Antwortgrenze der lokalen Modelle: Denkteil und Zusammenfassung müssen zusammen hineinpassen.
LOKAL_MAX_TOKENS = 32768


def _json_datei(pfad):
    try:
        with open(pfad, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _neueste(muster, schluessel=os.path.getmtime):
    treffer = [p for p in glob.glob(muster) if os.path.isfile(p)]
    return max(treffer, key=schluessel) if treffer else None


def _versionsschluessel(pfad):
    teile = re.findall(r'\d+', os.path.basename(os.path.dirname(pfad)))
    return [int(t) for t in teile]


def dateiname(text, grenze=70):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' .')
    return text[:grenze].rstrip(' .') or 'Fassung'


# ---------------------------------------------------------------- Anbieter

class Anbieter:
    schluessel = ''
    name = ''
    cloud = None  # Name des Dienstes, an den der Text geht; None = lokal

    def __init__(self, cfg):
        self.cfg = cfg
        self._cache = {}

    def _gemerkt(self, schluessel, sekunden, funktion):
        eintrag = self._cache.get(schluessel)
        if eintrag and time.time() - eintrag[0] < sekunden:
            return eintrag[1]
        wert = funktion()
        self._cache[schluessel] = (time.time(), wert)
        return wert

    def katalog(self):
        return []

    def verfuegbar(self, profil):
        return True, ''

    def kontext(self, profil):
        m = next((m for m in self.katalog() if m['modell'] == profil['modell']), None)
        return (m or {}).get('kontext')

    def ausfuehren(self, profil, prompt, lauf):
        raise NotImplementedError


class Codex(Anbieter):
    schluessel, name, cloud = 'codex', 'Codex', 'OpenAI'

    def exe(self):
        return _neueste(os.path.join(LOCALAPPDATA, 'OpenAI', 'Codex', 'bin', '*', 'codex.exe'))

    def katalog(self):
        def laden():
            d = _json_datei(os.path.join(HOME, '.codex', 'models_cache.json')) or {}
            return [{'modell': m['slug'], 'name': m.get('display_name') or m['slug'],
                     'beschreibung': m.get('description', ''), 'kontext': m.get('context_window'),
                     'stufen': [s['effort'] for s in m.get('supported_reasoning_levels', [])],
                     'stufe_standard': m.get('default_reasoning_level')}
                    for m in d.get('models', []) if m.get('visibility') == 'list']
        return self._gemerkt('katalog', 300, laden)

    def verfuegbar(self, profil):
        if not self.exe():
            return False, 'Die Codex-App ist nicht installiert.'
        if not os.path.isfile(os.path.join(HOME, '.codex', 'auth.json')):
            return False, 'Codex ist nicht angemeldet. Bitte einmal die Codex-App öffnen und anmelden.'
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        ziel = os.path.join(lauf.leer, f"codex-{lauf.id}.txt")
        argv = [self.exe(), 'exec', '--ephemeral', '--skip-git-repo-check', '--ignore-user-config', '--ignore-rules',
                '-s', 'read-only', '-m', profil['modell'], '-C', lauf.leer, '-o', ziel, '-']
        if profil.get('stufe'):
            argv[2:2] = ['-c', f'model_reasoning_effort="{profil["stufe"]}"']
        code, aus, err = lauf.programm(argv, prompt)
        try:
            with open(ziel, encoding='utf-8') as f:
                text = f.read()
        except OSError:
            text = ''
        finally:
            try:
                os.remove(ziel)
            except OSError:
                pass
        if code or not text.strip():
            letzte = [z for z in (err or '').strip().splitlines() if z.strip()][-3:]
            raise RuntimeError('Codex meldet einen Fehler: ' + (' '.join(letzte)[-400:] or f'Rückgabewert {code}'))
        m = re.search(r'tokens used\s*[\r\n]+\s*([\d.,]+)', err or '')
        return {'text': text, 'tokens': int(re.sub(r'\D', '', m.group(1))) if m else None}


class Claude(Anbieter):
    schluessel, name, cloud = 'claude', 'Claude', 'Anthropic'

    def exe(self):
        # Die Claude-App ist ein Store-Paket: Ihr %APPDATA%\Claude liegt in Wirklichkeit im Paketordner und
        # erscheint unter %APPDATA% nur für Programme aus der App. Der echte Pfad geht auch in normaler PowerShell.
        paket = glob.glob(os.path.join(LOCALAPPDATA, 'Packages', 'Claude_*', 'LocalCache', 'Roaming', 'Claude',
                                       'claude-code', '*', 'claude.exe'))
        treffer = paket or glob.glob(os.path.join(APPDATA, 'Claude', 'claude-code', '*', 'claude.exe'))
        return max(treffer, key=_versionsschluessel) if treffer else None

    def katalog(self):
        return [dict(m, stufen=['low', 'medium', 'high', 'xhigh', 'max'], stufe_standard=None)
                for m in self.cfg['claude_modelle']]

    def anmeldung(self):
        """Art der Anmeldung ('claude.ai' = Abo, sonst API-Abrechnung) oder None."""
        def pruefen():
            try:
                d = json.loads(_ausgabe([self.exe(), 'auth', 'status'], 20, _ohne_app_umgebung()))
                return (d.get('authMethod') or 'unbekannt') if d.get('loggedIn') else None
            except Exception:
                return None
        return self._gemerkt('anmeldung', 60, pruefen)

    def verfuegbar(self, profil):
        exe = self.exe()
        if not exe:
            return False, 'Die Claude-App mit Claude Code ist nicht installiert.'
        if not self.anmeldung():
            return False, ('Claude ist außerhalb der App nicht angemeldet. Einmalig in PowerShell ausführen: '
                           f'& "{exe}" auth login')
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        argv = [self.exe(), '-p', '--model', profil['modell'], '--output-format', 'json', '--no-session-persistence',
                '--tools', '', '--setting-sources', '', '--strict-mcp-config', '--disable-slash-commands',
                '--system-prompt', 'Du bist ein sorgfältiger Assistent.']
        if profil.get('stufe'):
            argv += ['--effort', profil['stufe']]
        code, aus, err = lauf.programm(argv, prompt, _ohne_app_umgebung())
        try:
            d = json.loads(aus)
        except ValueError:
            raise RuntimeError('Claude antwortete unerwartet: ' + (err or aus)[-300:])
        if d.get('is_error') or code:
            self._cache.pop('anmeldung', None)
            raise RuntimeError('Claude meldet einen Fehler: ' + str(d.get('result') or err)[:400])
        nutzung = d.get('usage') or {}
        # Im Abo (claude.ai) ist total_cost_usd nur ein rechnerischer API-Preis, abgerechnet wird nichts.
        kosten = None if self.anmeldung() == 'claude.ai' else d.get('total_cost_usd')
        return {'text': d.get('result') or '', 'kosten_usd': kosten,
                'tokens': sum(nutzung.get(k) or 0 for k in ('input_tokens', 'cache_creation_input_tokens',
                                                            'cache_read_input_tokens', 'output_tokens')) or None}


def _ohne_app_umgebung():
    """Umgebung ohne die Variablen einer Claude-App-Sitzung: Wurde die Werkstatt aus der App gestartet, würde
    claude.exe sonst deren Anmeldung und Zugang erwarten statt der eigenen Anmeldung."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(('CLAUDE', 'ANTHROPIC'))}


def _cloud_anfrage(lauf, anfrage, name, fehlertexte):
    """POST an eine Cloud-Schnittstelle; bei Überlastung (429, 503) bis zu drei neue Versuche.
    anfrage() liefert je Versuch einen frischen urllib-Request."""
    wartezeiten = [20, 45, 90]
    while True:
        try:
            return lauf.http(lambda: _NETZ.open(anfrage(), timeout=900))
        except urllib.error.HTTPError as e:
            try:
                fehler = json.loads(e.read())['error']
                grund = (fehler.get('metadata') or {}).get('raw') or fehler.get('message') or f'Fehler {e.code}'
            except Exception:
                grund = f'Fehler {e.code}'
            if e.code in (429, 503) and wartezeiten:
                pause = wartezeiten.pop(0)
                lauf.melden(f'{name} ist gerade ausgelastet; neuer Versuch in {pause} s.')
                lauf.warten(pause)
                lauf.melden(f'Text liegt bei {name} …')
                continue
            deutsch = fehlertexte.get(e.code) or {
                429: 'Das Modell ist beim Anbieter weiterhin ausgelastet (drei neue Versuche). Später „Wiederholen“ '
                     'oder ein anderes Modell wählen.',
                503: 'Der Anbieter ist weiterhin überlastet (drei neue Versuche). Später „Wiederholen“.',
            }.get(e.code)
            raise RuntimeError(f'{name}: {deutsch} ({str(grund)[:160]})' if deutsch else f'{name}: {str(grund)[:300]}')


def _ausgabe(argv, timeout, env=None):
    """Standardausgabe eines kurzen Programmaufrufs ohne Fenster."""
    r = subprocess.run(argv, capture_output=True, timeout=timeout, creationflags=winapi.CREATE_NO_WINDOW,
                       stdin=subprocess.DEVNULL, env=env)
    return r.stdout.decode('utf-8', 'replace')


class OpenRouter(Anbieter):
    """OpenRouter mit Saschas Schlüssel für kostenlose Modelle (…:free, openrouter/free): gehen sofort, sind aber
    begrenzt und zeitweise ausgelastet. Bezahlte Modelle nur mit Präfix in der config und Guthaben (derzeit keine;
    DeepSeek läuft direkt)."""
    schluessel, name, cloud = 'openrouter', 'OpenRouter', 'OpenRouter'
    URL = 'https://openrouter.ai/api/v1'
    GRATIS_HINWEIS = 'kostenlos; begrenzte Anfragen je Tag, zeitweise ausgelastet; Anbieter darf Eingaben ggf. speichern'

    @staticmethod
    def kostenlos(modell):
        return modell.endswith(':free') or modell == 'openrouter/free'

    def _schluessel(self):
        try:
            with open(self.cfg['openrouter']['schluessel_datei'], encoding='utf-8') as f:
                return f.read().strip()
        except OSError:
            return None

    def _anfrage(self, pfad, daten=None):
        return urllib.request.Request(self.URL + pfad, None if daten is None else json.dumps(daten).encode('utf-8'),
                                      {'Authorization': 'Bearer ' + (self._schluessel() or ''),
                                       'Content-Type': 'application/json', 'X-Title': 'KI-Zentrale Werkstatt'})

    def katalog(self):
        def laden():
            with _NETZ.open(self.URL + '/models', timeout=30) as r:
                daten = json.load(r)['data']
            bezahlt = tuple(self.cfg['openrouter']['praefixe'])
            out = []
            for m in sorted(daten, key=lambda m: -(m.get('created') or 0)):
                mid = m['id']
                arch = m.get('architecture') or {}
                nur_text = arch.get('output_modalities', ['text']) == ['text'] and 'text' in arch.get('input_modalities', ['text'])
                if not nur_text or 'safety' in mid:
                    continue
                if self.kostenlos(mid):
                    beschreibung = self.GRATIS_HINWEIS
                    name = (m.get('name') or mid).replace(' (free)', '') + ' · kostenlos'
                elif mid.startswith(bezahlt) and ':' not in mid:
                    p = m.get('pricing') or {}
                    beschreibung = 'Eingabe {:.2f} $, Ausgabe {:.2f} $ je Million Token; braucht Guthaben'.format(
                        float(p.get('prompt') or 0) * 1e6, float(p.get('completion') or 0) * 1e6)
                    name = m.get('name') or mid
                else:
                    continue
                out.append({'modell': mid, 'name': name, 'kontext': m.get('context_length'), 'stufen': [],
                            'stufe_standard': None, 'beschreibung': beschreibung})
            # Kostenlose zuerst, weil sie ohne Guthaben sofort gehen.
            out.sort(key=lambda x: not self.kostenlos(x['modell']))
            return out
        try:
            return self._gemerkt('katalog', 6 * 3600, laden)
        except Exception:
            return self._cache.get('katalog', (0, []))[1]

    def guthaben(self):
        """Verbleibendes Guthaben in $ oder None, wenn nicht abfragbar."""
        def laden():
            with _NETZ.open(self._anfrage('/credits'), timeout=20) as r:
                d = json.load(r)['data']
            return float(d.get('total_credits') or 0) - float(d.get('total_usage') or 0)
        try:
            return self._gemerkt('guthaben', 300, laden)
        except Exception:
            return None

    def verfuegbar(self, profil):
        if not self._schluessel():
            return False, f"Kein OpenRouter-Schlüssel unter {self.cfg['openrouter']['schluessel_datei']}."
        if self.kostenlos(profil['modell']):
            return True, ''
        rest = self.guthaben()
        if rest is not None and rest <= 0:
            return False, ('Auf dem OpenRouter-Konto ist kein Guthaben (0 $). Bezahlte Modelle wie DeepSeek gehen erst '
                           'nach dem Aufladen unter openrouter.ai/settings/credits; kostenlose Modelle gehen sofort.')
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        daten = {'model': profil['modell'], 'messages': [{'role': 'user', 'content': prompt}],
                 'usage': {'include': True}}
        try:
            a = _cloud_anfrage(lauf, lambda: self._anfrage('/chat/completions', daten), 'OpenRouter', {
                402: 'Auf dem OpenRouter-Konto ist nicht genug Guthaben.',
                401: 'Der OpenRouter-Schlüssel wird nicht angenommen.',
                403: 'Dieses Modell ist über die Schnittstelle nicht freigegeben.',
                404: 'Der Anbieter dieses Modells antwortet nicht (oder es ist nicht mehr verfügbar).'})
        except RuntimeError:
            self._cache.pop('guthaben', None)
            raise
        if a.get('error'):
            raise RuntimeError(f"OpenRouter: {a['error'].get('message', a['error'])}")
        n = a.get('usage') or {}
        return {'text': a['choices'][0]['message'].get('content') or '', 'kosten_usd': n.get('cost'),
                'tokens': n.get('total_tokens'), 'modell_tatsaechlich': a.get('model')}


def deepseek_kosten(preise, nutzung, zeitpunkt, hauptzeit_utc, nebenzeit_faktor):
    """Kosten in $ aus der Nutzung einer Antwort. preise: $ je Million Token zur Hauptzeit
    (cache_treffer, eingabe, ausgabe); außerhalb der Hauptzeit (UTC, Mo–Fr) gilt der Faktor."""
    u = time.gmtime(zeitpunkt)
    haupt = u.tm_wday < 5 and any(von <= u.tm_hour < bis for von, bis in hauptzeit_utc)
    treffer = nutzung.get('prompt_cache_hit_tokens') or 0
    rest = nutzung.get('prompt_cache_miss_tokens')
    if rest is None:
        rest = max((nutzung.get('prompt_tokens') or 0) - treffer, 0)
    summe = (treffer * preise['cache_treffer'] + rest * preise['eingabe']
             + (nutzung.get('completion_tokens') or 0) * preise['ausgabe']) / 1e6
    return round(summe * (1 if haupt else nebenzeit_faktor), 6)


class DeepSeek(Anbieter):
    """DeepSeek direkt mit Saschas Schlüssel. Der Schlüssel liegt in DSH Desktop und wird dort nur gelesen
    (keine Kopie). Preise, Kontext und Hauptzeiten stehen in der config (Stand dort)."""
    schluessel, name, cloud = 'deepseek', 'DeepSeek', 'DeepSeek'
    STUFEN = ['none', 'low', 'high', 'max']  # Nachdenken aus oder reasoning_effort; Standard bei DeepSeek: high

    def _schluessel(self):
        c = self.cfg['deepseek']
        try:
            with open(c['schluessel_datei'], encoding='utf-8') as f:
                text = f.read()
        except OSError:
            return None
        m = re.search(r'^\s*%s:\s*["\']?([^"\'\s]+)' % re.escape(c['schluessel_name']), text, re.M)
        return m.group(1) if m else None

    def _anfrage(self, pfad, daten=None):
        return urllib.request.Request(self.cfg['deepseek']['url'] + pfad,
                                      None if daten is None else json.dumps(daten).encode('utf-8'),
                                      {'Authorization': 'Bearer ' + (self._schluessel() or ''),
                                       'Content-Type': 'application/json', 'Accept': 'application/json'})

    def katalog(self):
        c = self.cfg['deepseek']

        def beschreibung(info):
            p = info.get('preise')
            if not p:
                return 'Preis unbekannt'
            zahl = lambda x: f'{x:.2f}'.replace('.', ',')  # noqa: E731
            f = c['nebenzeit_faktor']
            return (f"{info.get('beschreibung', '')}; Eingabe {zahl(p['eingabe'] * f)}–{zahl(p['eingabe'])} $, "
                    f"Ausgabe {zahl(p['ausgabe'] * f)}–{zahl(p['ausgabe'])} $ je Million Token "
                    f"(günstiger außerhalb der Hauptzeit)").lstrip('; ')

        def laden():
            with _NETZ.open(self._anfrage('/models'), timeout=20) as r:
                return [m['id'] for m in json.load(r).get('data', [])]
        try:
            live = self._gemerkt('modelle', 6 * 3600, laden)
        except Exception:
            live = []
        out = []
        for mid in list(c['modelle']) + [m for m in live if m not in c['modelle']]:
            info = c['modelle'].get(mid, {})
            out.append({'modell': mid, 'name': info.get('name') or mid, 'kontext': info.get('kontext'),
                        'stufen': self.STUFEN, 'stufe_standard': 'high', 'beschreibung': beschreibung(info)})
        return out

    def guthaben(self):
        """{'nutzbar': bool, 'betrag': $ oder None, 'grund': …} oder None, wenn nicht abfragbar."""
        def laden():
            try:
                with _NETZ.open(self._anfrage('/user/balance'), timeout=20) as r:
                    d = json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    return {'nutzbar': False, 'betrag': None, 'grund': 'schluessel'}
                raise
            usd = next((b for b in d.get('balance_infos', []) if b.get('currency') == 'USD'), None)
            return {'nutzbar': bool(d.get('is_available')), 'betrag': float(usd['total_balance']) if usd else None,
                    'grund': None if d.get('is_available') else 'guthaben'}
        try:
            return self._gemerkt('guthaben', 300, laden)
        except Exception:
            return None

    def verfuegbar(self, profil):
        c = self.cfg['deepseek']
        if not self._schluessel():
            return False, f"Kein DeepSeek-Schlüssel ({c['schluessel_name']}) in {c['schluessel_datei']}."
        g = self.guthaben()
        if g and g['grund'] == 'schluessel':
            return False, 'Der DeepSeek-Schlüssel wird nicht angenommen (in DSH Desktop prüfen).'
        if g and not g['nutzbar']:
            return False, 'Auf dem DeepSeek-Konto ist kein Guthaben. Aufladen unter platform.deepseek.com.'
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        c = self.cfg['deepseek']
        daten = {'model': profil['modell'], 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
                 'max_tokens': c.get('max_tokens', 65536)}
        if profil.get('stufe') == 'none':
            daten['thinking'] = {'type': 'disabled'}
        elif profil.get('stufe'):
            daten['reasoning_effort'] = profil['stufe']
        beginn = time.time()
        try:
            a = _cloud_anfrage(lauf, lambda: self._anfrage('/chat/completions', daten), 'DeepSeek', {
                402: 'Auf dem DeepSeek-Konto ist nicht genug Guthaben (Aufladen unter platform.deepseek.com).',
                401: 'Der DeepSeek-Schlüssel wird nicht angenommen.',
                422: 'DeepSeek lehnt die Einstellungen ab (Modell oder Denkstufe).'})
        finally:
            self._cache.pop('guthaben', None)
        wahl = a['choices'][0]
        text = wahl['message'].get('content') or ''
        if wahl.get('finish_reason') == 'length' and text:
            text += '\n\n[Hinweis der Werkstatt: Die Antwort wurde an der Längengrenze abgeschnitten.]'
        n = a.get('usage') or {}
        preise = (c['modelle'].get(profil['modell']) or {}).get('preise')
        kosten = deepseek_kosten(preise, n, beginn, c['hauptzeit_utc'], c['nebenzeit_faktor']) if preise else None
        return {'text': text, 'kosten_usd': kosten, 'tokens': n.get('total_tokens')}


def _lokaler_text(text, abgeschnitten):
    """Entfernt den Denkteil. Ein offener Denkteil oder ein leerer Text ergibt keine Zusammenfassung."""
    text = re.sub(r'<think>.*?</think>\s*', '', text or '', flags=re.S)
    if '<think>' in text or not text.strip():
        raise RuntimeError('Das Modell hat die Antwortgrenze schon beim Nachdenken verbraucht; es ist keine '
                           'Zusammenfassung entstanden. Mit „Wiederholen“ neu versuchen.')
    if abgeschnitten:
        text += '\n\n[Hinweis der Werkstatt: Die Antwort wurde an der Längengrenze abgeschnitten.]'
    return text


class Lokal(Anbieter):
    schluessel, name, cloud = 'lokal', 'Lokal', None

    def _eintraege(self):
        d = _json_datei(self.cfg['zentrale_config']) or {}
        return ({e['id']: e for e in d.get('eintraege', [])
                 if e['art'] in ('ollama', 'ninfer', 'strata', 'polystrata')}, d.get('ollama', {}))

    @staticmethod
    def _kennungen(e):
        """Modellkennungen, unter denen die Zentrale einen Eintrag am OpenAI-Port geladen haben kann."""
        if e['art'] == 'strata':
            return {x for x in [v.get('modell') for v in e.get('varianten') or []] + [e.get('modell')] if x}
        if e['art'] == 'polystrata':
            return {e['modell']} if e.get('modell') else set()
        return {e['modell_id']} if e.get('modell_id') else set()

    def _modelle(self, port):
        """Kennungen laut /v1/models; leer, wenn der Port nicht antwortet oder nichts geladen ist."""
        try:
            with _OHNE_PROXY.open(f'http://127.0.0.1:{port}/v1/models', timeout=3) as r:
                return [m.get('id') for m in json.load(r).get('data', []) if m.get('id')]
        except Exception:
            return []

    def _tatsaechliches_modell(self, e):
        """Die gerade geladene Kennung; die Werkstatt lädt nie selbst ein Modell (Regel aus AGENTS.md)."""
        for kennung in self._modelle(e['port']):
            if kennung in self._kennungen(e):
                return kennung
        raise RuntimeError(f"{e['name']} ist nicht geladen. Bitte in der Modellzentrale laden.")

    def _ollama_kontexte(self, ollama):
        """{Tag: Kontext} der gerade geladenen Ollama-Modelle laut /api/ps (frisch, leer wenn Ollama aus ist)."""
        url = ollama.get('url', 'http://127.0.0.1:11434')
        if int(url.rsplit(':', 1)[1]) not in {p for _, p, _ in winapi.lauschende_ports()}:
            return {}
        try:
            with _OHNE_PROXY.open(url + '/api/ps', timeout=3) as r:
                return {(m.get('name') or m.get('model')): m.get('context_length') for m in json.load(r).get('models', [])}
        except Exception:
            return {}

    def ollama_optionen(self, e, ollama):
        """Optionen für Anfragen an ein Ollama-Modell: die des Eintrags plus der Kontext, mit dem es gerade geladen ist.

        Seit 14.10.2026 wählt die Zentrale die Kontextgröße (Varianten). Schickt eine Anfrage einen anderen Kontext
        (oder keinen, wenn das Modell mit einem anderen als dem Standard geladen ist), lädt Ollama das Modell neu."""
        optionen = dict(e.get('ollama_optionen') or {})
        kontext = self._ollama_kontexte(ollama).get(e['tag'])
        if kontext:
            optionen['num_ctx'] = kontext
        return optionen

    def katalog(self):
        eintraege, ollama = self._eintraege()
        geladen = self._gemerkt('kontexte', 5, lambda: self._ollama_kontexte(ollama))
        out = []
        for e in eintraege.values():
            # Kontext: geladen laut Ollama, sonst die Standardvariante der Zentrale, sonst aus dem Untertitel.
            kontext = geladen.get(e.get('tag')) if e['art'] == 'ollama' else None
            if not kontext and e.get('varianten'):
                v = next((x for x in e['varianten'] if x.get('standard')), e['varianten'][0])
                kontext = (v.get('ollama_optionen') or {}).get('num_ctx') or v.get('kontext')
            if not kontext:
                k = re.search(r'(\d+)\s*K\b', e.get('untertitel', ''))
                kontext = int(k.group(1)) * 1024 if k else None
            out.append({'modell': e['id'], 'name': e['name'], 'kontext': kontext,
                        'stufen': [], 'stufe_standard': None, 'beschreibung': e.get('wofuer', '')})
        return out

    def _geladen(self, e, ollama):
        port = int(ollama.get('url', 'http://127.0.0.1:11434').rsplit(':', 1)[1]) if e['art'] == 'ollama' else e['port']
        if port not in {p for _, p, _ in winapi.lauschende_ports()}:
            return False  # geschlossener Port: nicht anfragen (Windows wiederholt sonst ~1 s)
        try:
            if e['art'] == 'ollama':
                with _OHNE_PROXY.open(ollama.get('url', 'http://127.0.0.1:11434') + '/api/ps', timeout=3) as r:
                    return any((m.get('name') or m.get('model')) == e['tag'] for m in json.load(r).get('models', []))
            return bool(set(self._modelle(e['port'])) & self._kennungen(e))
        except Exception:
            return False

    def verfuegbar(self, profil, frisch=False):
        eintraege, ollama = self._eintraege()
        e = eintraege.get(profil['modell'])
        if not e:
            return False, 'Dieses Modell steht nicht mehr in der Modellzentrale.'
        if frisch:
            self._cache.pop('geladen:' + e['id'], None)
        if not self._gemerkt('geladen:' + e['id'], 5, lambda: self._geladen(e, ollama)):
            return False, f"{e['name']} ist nicht geladen. Bitte in der Modellzentrale laden."
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        eintraege, ollama = self._eintraege()
        e = eintraege[profil['modell']]
        if e['art'] == 'ollama':
            # keep_alive -1: das Modell bleibt so geladen, wie die Zentrale es geladen hat.
            daten = {'model': e['tag'], 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
                     'keep_alive': -1, 'options': self.ollama_optionen(e, ollama)}
            a = ollama_senden(ollama.get('url', 'http://127.0.0.1:11434') + '/api/chat', daten, lauf.http, lauf.melden)
            text = (a.get('message') or {}).get('content') or ''
            tokens = (a.get('prompt_eval_count') or 0) + (a.get('eval_count') or 0) or None
            abgeschnitten = a.get('done_reason') == 'length'
        else:
            modell = e['modell_id'] if e['art'] == 'ninfer' else self._tatsaechliches_modell(e)
            daten = {'model': modell, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
                     'max_tokens': LOKAL_MAX_TOKENS}
            anfrage = urllib.request.Request(f"http://127.0.0.1:{e['port']}/v1/chat/completions",
                                             json.dumps(daten).encode('utf-8'), {'Content-Type': 'application/json'})
            a = lauf.http(lambda: _OHNE_PROXY.open(anfrage, timeout=3600))
            wahl = a['choices'][0]
            text = wahl['message'].get('content') or ''
            tokens = (a.get('usage') or {}).get('total_tokens')
            abgeschnitten = wahl.get('finish_reason') == 'length'
        ergebnis = {'text': _lokaler_text(text, abgeschnitten), 'tokens': tokens}
        if e['art'] in ('strata', 'polystrata'):
            ergebnis['modell_tatsaechlich'] = modell
        return ergebnis


def ollama_senden(url, daten, oeffnen=None, melden=None, timeout=3600):
    """POST an Ollama; stürzt der Modellprozess ab, einmal neu versuchen.

    Ollama 0.34 (llama.cpp) bricht bei Ornith gelegentlich mit „CUDA error: an illegal memory access“
    in mmq.cu ab (gemessen 23.09.2026, sporadisch, beide Karten). Ollama lädt das Modell beim nächsten
    Aufruf selbst neu; dann klappt es in aller Regel.
    """
    oeffnen = oeffnen or (lambda f: f())
    for versuch in (1, 2):
        anfrage = urllib.request.Request(url, json.dumps(daten).encode('utf-8'), {'Content-Type': 'application/json'})
        try:
            return oeffnen(lambda: _OHNE_PROXY.open(anfrage, timeout=timeout))
        except urllib.error.HTTPError as e:
            try:
                grund = json.loads(e.read()).get('error', '')
            except Exception:
                grund = ''
            if e.code == 500 and 'llama-server' in grund and versuch == 1:
                if melden:
                    melden('Der Modellprozess von Ollama ist abgestürzt (bekannter CUDA-Fehler); Ollama lädt neu, zweiter Versuch …')
                time.sleep(3)
                continue
            if 'llama-server' in grund:
                raise RuntimeError('Der Modellprozess von Ollama ist zweimal abgestürzt (CUDA-Fehler in llama.cpp, '
                                   'siehe %LOCALAPPDATA%\\Ollama\\server.log). Später erneut versuchen.')
            raise RuntimeError(f'Ollama: {grund or f"Fehler {e.code}"}')


# ---------------------------------------------------------------- Transkripte

def transkripte_auflisten(arbeitsordner):
    """Alle vollständigen Transkripte im watch-Arbeitsordner, neueste zuerst."""
    out = []
    try:
        eintraege = [e for e in os.scandir(arbeitsordner) if e.is_dir() and not e.name.startswith('_')]
    except OSError:
        return out
    for e in eintraege:
        laeufe = watch_lauf.transkripte(e.path)
        lauf = watch_lauf.transkript_passend(laeufe) or (laeufe[0] if laeufe else None)
        if not lauf:
            continue
        medien = watch_lauf.medien_im_ordner(e.path)
        try:
            geaendert = os.path.getmtime(os.path.join(lauf['ordner'], 'run.json'))
        except OSError:
            geaendert = 0
        fassungen = len(glob.glob(os.path.join(glob.escape(e.path), 'zusammenfassungen', '*.md')))
        out.append({'ordner': e.path, 'transkript': lauf['ordner'],
                    'titel': medien['titel'] or re.sub(r'\s*\[[^\]]+\]$', '', e.name),
                    'quelle': medien['quelle'] or '', 'dauer': medien['dauer'] or lauf['ende'],
                    'sprache': lauf['sprache'], 'geaendert': geaendert, 'fassungen': fassungen})
    out.sort(key=lambda t: -t['geaendert'])
    return out


# ---------------------------------------------------------------- Ablauf

class _Lauf:
    """Hilfen für einen laufenden Auftrag: Programme in Prozessgruppe, abbrechbare HTTP-Anfragen."""

    def __init__(self, aid, leer, abbruch, melden=None):
        self.id, self.leer, self.abbruch = aid, leer, abbruch
        self.gruppe = None
        self.melden = melden or (lambda text: None)

    def warten(self, sekunden):
        if self.abbruch.wait(sekunden):
            raise _Abbruch()

    def programm(self, argv, eingabe, env=None):
        g = winapi.Prozessgruppe(argv, self.leer, dict(env if env is not None else os.environ), eingabe=True)
        self.gruppe = g
        ausgabe = {}

        def lesen():
            ausgabe['aus'], ausgabe['err'] = g.prozess.communicate(eingabe.encode('utf-8'))
        t = threading.Thread(target=lesen, daemon=True)
        t.start()
        try:
            while t.is_alive():
                t.join(0.5)
                if self.abbruch.is_set():
                    g.beenden()
        finally:
            g.schliessen()
            self.gruppe = None
        if self.abbruch.is_set():
            raise _Abbruch()
        dek = lambda b: (b or b'').decode('utf-8', 'replace')  # noqa: E731
        return g.prozess.returncode, dek(ausgabe.get('aus')), dek(ausgabe.get('err'))

    def http(self, oeffnen):
        """Führt die Anfrage in einem eigenen Faden aus; bei Abbruch wird das Ergebnis verworfen."""
        ergebnis = {}

        def holen():
            try:
                with oeffnen() as r:
                    ergebnis['daten'] = json.load(r)
            except Exception as e:
                ergebnis['fehler'] = e
        t = threading.Thread(target=holen, daemon=True)
        t.start()
        while t.is_alive():
            t.join(0.5)
            if self.abbruch.is_set():
                raise _Abbruch()
        if 'fehler' in ergebnis:
            raise ergebnis['fehler']
        return ergebnis['daten']


class _Abbruch(Exception):
    pass


FELDER = ('id', 'transkript', 'ordner', 'titel', 'auswerter', 'anweisung', 'frage', 'zustand', 'meldung', 'datei',
          'erstellt', 'begonnen', 'beendet', 'dauer_s', 'kosten_usd', 'tokens', 'cloud', 'modell_tatsaechlich')


class Auswertungen:
    def __init__(self, cfg, daten_ordner, log):
        self.cfg = cfg
        self.w = cfg['watch']
        self.log = log
        self.sammlung = anweisungen.Sammlung(cfg['promptsammlung'])
        self.anbieter = {a.schluessel: a for a in (Codex(cfg), Claude(cfg), DeepSeek(cfg), OpenRouter(cfg), Lokal(cfg))}
        self.leer = os.path.join(daten_ordner, 'leer')
        os.makedirs(self.leer, exist_ok=True)
        self.datei = os.path.join(daten_ordner, 'auswertungen.json')
        self.profil_datei = os.path.join(daten_ordner, 'auswerter.json')
        self._lock = threading.RLock()
        self._abbruch = {}
        self._laufend = {}
        self._transkripte = (0, [])
        d = _json_datei(self.datei) or {}
        self.liste = d.get('auswertungen', [])
        for a in self.liste:
            if a['zustand'] in ('laeuft', 'wartet'):
                a.update(zustand='abgebrochen', meldung='Der Dienst wurde währenddessen beendet. Du kannst sie wiederholen.')
        self.profile = (_json_datei(self.profil_datei) or {}).get('auswerter') or cfg['auswerter_vorschlag']
        self._speichern()
        self._wecker = threading.Event()
        for _ in range(int(cfg.get('cloud_parallel', 2))):
            threading.Thread(target=self._schleife, daemon=True).start()

    # ------------------------------------------------------------ Speichern

    def _speichern(self):
        with self._lock:
            for pfad, daten in ((self.datei, {'auswertungen': self.liste}), (self.profil_datei, {'auswerter': self.profile})):
                tmp = pfad + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(daten, f, ensure_ascii=False, indent=1)
                os.replace(tmp, pfad)

    # ------------------------------------------------------------ Anzeige

    def profil_info(self, p):
        a = self.anbieter.get(p['anbieter'])
        if not a:
            return dict(p, verfuegbar=False, grund='Unbekannter Anbieter.', cloud=None, kontext=None)
        try:
            ok, grund = a.verfuegbar(p)
        except Exception as e:
            ok, grund = False, f'Prüfung fehlgeschlagen: {e}'
        return dict(p, verfuegbar=ok, grund=grund, cloud=a.cloud, kontext=a.kontext(p))

    def stand(self):
        with self._lock:
            liste = []
            for a in self.liste:
                x = {k: a.get(k) for k in FELDER}
                if a['zustand'] == 'laeuft' and a.get('begonnen'):
                    x['sekunden'] = round(time.time() - a['begonnen'])
                liste.append(x)
            profile = list(self.profile)
        return {'auswerter': [self.profil_info(p) for p in profile], 'auswertungen': liste,
                'sammlung': self.sammlung.lesen()}

    def transkripte(self, neu=False):
        if neu or time.time() - self._transkripte[0] > 20:
            self._transkripte = (time.time(), transkripte_auflisten(self.w['arbeitsordner']))
        return self._transkripte[1]

    def katalog(self):
        out = []
        for a in self.anbieter.values():
            try:
                modelle = a.katalog()
            except Exception:
                modelle = []
            out.append({'anbieter': a.schluessel, 'name': a.name, 'cloud': a.cloud, 'modelle': modelle})
        return {'anbieter': out, 'stufen_text': STUFEN_TEXT}

    def text(self, aid):
        with self._lock:
            a = next((x for x in self.liste if x['id'] == aid), None)
        if not a or not a.get('datei'):
            return None
        try:
            with open(a['datei'], encoding='utf-8') as f:
                return f.read()
        except OSError:
            return None

    # ------------------------------------------------------------ Auswerter verwalten

    def profil_neu(self, daten):
        a = self.anbieter.get(daten.get('anbieter'))
        if not a:
            return 400, {'fehler': 'Unbekannter Anbieter.'}
        modell = next((m for m in a.katalog() if m['modell'] == daten.get('modell')), None)
        if not modell:
            return 400, {'fehler': 'Dieses Modell kennt der Anbieter nicht (mehr).'}
        stufe = daten.get('stufe') or None
        if stufe and stufe not in modell['stufen']:
            return 400, {'fehler': 'Diese Denkstufe gibt es für das Modell nicht.'}
        name = f"{a.name} · {modell['name']}" + (f' · {STUFEN_TEXT.get(stufe, stufe)}' if stufe else '')
        with self._lock:
            if any(p['anbieter'] == a.schluessel and p['modell'] == modell['modell'] and p.get('stufe') == stufe
                   for p in self.profile):
                return 409, {'fehler': 'Diesen Auswerter gibt es schon.'}
            self.profile.append({'id': secrets.token_hex(4), 'anbieter': a.schluessel, 'modell': modell['modell'],
                                 'stufe': stufe, 'name': name})
            self._speichern()
        return 200, {'ok': True}

    def profil_loeschen(self, pid):
        with self._lock:
            self.profile = [p for p in self.profile if p['id'] != pid]
            self._speichern()
        return 200, {'ok': True}

    # ------------------------------------------------------------ Aufträge

    def anlegen(self, daten):
        ordner = str(daten.get('ordner', ''))
        t = next((x for x in self.transkripte() if x['ordner'] == ordner), None) or \
            next((x for x in self.transkripte(neu=True) if x['ordner'] == ordner), None)
        if not t:
            return 404, {'fehler': 'Dieses Transkript gibt es im Arbeitsordner nicht (mehr).'}
        sammlung = self.sammlung.lesen()
        alle = {x['name']: x for x in sammlung['anweisungen']}
        gewaehlt = [alle[n] for n in daten.get('anweisungen', []) if n in alle]
        profile = [p for p in self.profile if p['id'] in daten.get('auswerter', [])]
        if not gewaehlt or not profile:
            return 400, {'fehler': 'Bitte mindestens einen Auswerter und eine Anweisung anhaken.'}
        frage = str(daten.get('frage') or '').strip()[:2000]
        if any(x['frage'] for x in gewaehlt) and not frage:
            return 400, {'fehler': 'Die gewählte Anweisung braucht eine Frage.'}
        try:
            with open(os.path.join(t['transkript'], 'transcript-timestamps.txt'), encoding='utf-8') as f:
                laenge = len(f.read())
        except OSError:
            return 404, {'fehler': 'Das Transkript mit Zeitmarken fehlt.'}
        abgelehnt, neu = [], 0
        with self._lock:
            for p in profile:
                info = self.profil_info(p)
                for anw in gewaehlt:
                    geschaetzt = (laenge + len(anw['text']) + 600) / 3.0  # vorsichtig: gut 3 Zeichen je Token
                    # Platz für Denkteil und Antwort freihalten: höchstens ein Viertel des Kontexts, aber nie mehr
                    # als die Antwortgrenze der lokalen Modelle.
                    reserve = min(LOKAL_MAX_TOKENS, info['kontext'] // 4) if info.get('kontext') else 0
                    if info.get('kontext') and geschaetzt + reserve > info['kontext']:
                        abgelehnt.append(f"{p['name']}: Das Transkript ist zu lang für {info['kontext']:,} Token Kontext."
                                         .replace(',', '.'))
                        continue
                    self.liste.append({
                        'id': secrets.token_hex(4), 'transkript': t['transkript'], 'ordner': t['ordner'],
                        'titel': t['titel'], 'quelle': t['quelle'], 'dauer': t['dauer'],
                        'auswerter': {k: p.get(k) for k in ('id', 'anbieter', 'modell', 'stufe', 'name')},
                        'anweisung': {'name': anw['name'], 'stand': anw['stand']},
                        'frage': frage if anw['frage'] else None, 'cloud': info.get('cloud'),
                        'zustand': 'wartet', 'meldung': '', 'erstellt': time.time()})
                    neu += 1
            self._speichern()
        self._wecker.set()
        return 200, {'neu': neu, 'abgelehnt': abgelehnt}

    def aktion(self, aid, was):
        with self._lock:
            a = next((x for x in self.liste if x['id'] == aid), None)
            if not a:
                return 404, {'fehler': 'Diese Fassung gibt es nicht mehr.'}
            if was == 'abbrechen' and a['zustand'] in ('wartet', 'laeuft'):
                if a['zustand'] == 'wartet':
                    a.update(zustand='abgebrochen', meldung='Abgebrochen, bevor sie begonnen hat.')
                else:
                    self._abbruch.setdefault(aid, threading.Event()).set()
            elif was == 'wiederholen' and a['zustand'] in ('fehler', 'abgebrochen'):
                a.update(zustand='wartet', meldung='', datei=None)
            elif was == 'entfernen' and a['zustand'] not in ('laeuft',):
                self.liste.remove(a)
            else:
                return 409, {'fehler': 'Das geht in diesem Zustand nicht.'}
            self._speichern()
        self._wecker.set()
        return 200, {'ok': True}

    def datei(self, aid):
        with self._lock:
            a = next((x for x in self.liste if x['id'] == aid), None)
        return a.get('datei') if a else None

    # ------------------------------------------------------------ Ausführen

    def _naechste(self):
        """Erste wartende Fassung. Lokale rechnen seit 16.10.2026 auch neben Whisper, Bildern und Texterkennung
        (keine gemeinsame GPU-Sperre mehr): Das Modell hat die Zentrale schon geladen, es braucht keinen neuen Platz."""
        with self._lock:
            for a in self.liste:
                if a['zustand'] != 'wartet':
                    continue
                a.update(zustand='laeuft', begonnen=time.time(), meldung='')
                self._abbruch[a['id']] = threading.Event()
                self._speichern()
                return a
        return None

    def _schleife(self):
        while True:
            a = self._naechste()
            if not a:
                self._wecker.wait(3)
                self._wecker.clear()
                continue
            try:
                self._ausfuehren(a)
            except _Abbruch:
                a.update(zustand='abgebrochen', meldung='Abgebrochen.')
            except Exception as ex:
                a.update(zustand='fehler', meldung=str(ex)[:600])
                self.log(f"Fassung {a['id']} ({a['auswerter']['anbieter']}) fehlgeschlagen: "
                         + traceback.format_exc(limit=2).replace('\n', ' | ')[-300:])
            finally:
                with self._lock:
                    a['beendet'] = time.time()
                    a['dauer_s'] = round(a['beendet'] - a['begonnen'])
                    self._abbruch.pop(a['id'], None)
                    self._speichern()

    def _ausfuehren(self, a):
        p = a['auswerter']
        anbieter = self.anbieter[p['anbieter']]
        ok, grund = anbieter.verfuegbar(p, frisch=True) if p['anbieter'] == 'lokal' else anbieter.verfuegbar(p)
        if not ok:
            raise RuntimeError(grund)
        sammlung = self.sammlung.lesen()
        anw = next((x for x in sammlung['anweisungen'] if x['name'] == a['anweisung']['name']), None)
        if not anw:
            raise RuntimeError(f"Die Anweisung „{a['anweisung']['name']}“ steht nicht mehr in der Promptsammlung.")
        with open(os.path.join(a['transkript'], 'transcript-timestamps.txt'), encoding='utf-8') as f:
            transkript = f.read()
        try:
            with open(os.path.join(a['transkript'], 'transcript.txt'), encoding='utf-8') as f:
                wortbasis = f.read()  # ohne Zeitmarken; daraus folgt der Zielumfang
        except OSError:
            wortbasis = transkript
        werte = {'Titel': a['titel'], 'Quelle': a.get('quelle') or a['titel'],
                 'Dauer': _dauer(a.get('dauer')), 'Frage': a.get('frage') or '',
                 'Zielumfang': anweisungen.zielumfang(wortbasis)}
        rahmen = (sammlung.get('rahmen') or {}).get('text', '')
        prompt = anweisungen.zusammenbauen(rahmen, anw['text'], werte, transkript)
        a['anweisung']['stand'] = anw['stand']
        a['meldung'] = 'Läuft …' if anbieter.cloud is None else f'Text liegt bei {anbieter.cloud} …'
        self.log(f"Fassung {a['id']}: {p['anbieter']} {p['modell']} beginnt ({len(prompt)} Zeichen)")
        ergebnis = anbieter.ausfuehren(p, prompt, _Lauf(a['id'], self.leer, self._abbruch[a['id']],
                                                         lambda text: a.update(meldung=text)))
        text = (ergebnis.get('text') or '').strip()
        if not text:
            raise RuntimeError('Das Modell hat keinen Text geliefert.')
        a['datei'] = self._ablegen(a, text, ergebnis, time.time() - a['begonnen'])
        a.update(zustand='fertig', meldung='', kosten_usd=ergebnis.get('kosten_usd'), tokens=ergebnis.get('tokens'),
                 modell_tatsaechlich=ergebnis.get('modell_tatsaechlich'))
        self.log(f"Fassung {a['id']}: fertig in {round(time.time() - a['begonnen'])} s")

    def _ablegen(self, a, text, ergebnis, dauer):
        ziel = os.path.join(a['ordner'], 'zusammenfassungen')
        os.makedirs(ziel, exist_ok=True)
        basis = dateiname(f"{a['anweisung']['name']} – {a['auswerter']['name']}")
        pfad = os.path.join(ziel, basis + '.md')
        n = 2
        while os.path.exists(pfad):
            pfad = os.path.join(ziel, f'{basis} ({n}).md')
            n += 1
        p = a['auswerter']
        kopf = ['---', f"quelle: {json.dumps(a.get('quelle') or a['titel'], ensure_ascii=False)}",
                f"titel: {json.dumps(a['titel'], ensure_ascii=False)}",
                f"transkript: {json.dumps(a['transkript'], ensure_ascii=False)}",
                f"anweisung: {json.dumps(a['anweisung']['name'], ensure_ascii=False)}",
                f"anweisung_stand: {a['anweisung']['stand']}",
                f"auswerter: {json.dumps(p['name'], ensure_ascii=False)}",
                f"anbieter: {p['anbieter']}", f"modell: {p['modell']}"]
        if ergebnis.get('modell_tatsaechlich') and ergebnis['modell_tatsaechlich'] != p['modell']:
            kopf.append(f"modell_tatsaechlich: {ergebnis['modell_tatsaechlich']}")
        if p.get('stufe'):
            kopf.append(f"denkstufe: {p['stufe']}")
        if a.get('frage'):
            kopf.append(f"frage: {json.dumps(a['frage'], ensure_ascii=False)}")
        kopf += [f"verarbeitung: {'lokal' if not a.get('cloud') else 'Cloud (' + a['cloud'] + ')'}",
                 f"erstellt: {time.strftime('%Y-%m-%d %H:%M')}", f'dauer_s: {round(dauer)}']
        if ergebnis.get('tokens'):
            kopf.append(f"tokens: {ergebnis['tokens']}")
        if ergebnis.get('kosten_usd') is not None:
            kopf.append(f"kosten_usd: {ergebnis['kosten_usd']}")
        kopf += ['status: Entwurf, automatisch erstellt, nicht geprüft', '---', '']
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write('\n'.join(kopf) + '\n' + text + '\n')
        return pfad


def _dauer(s):
    if not s:
        return 'unbekannt'
    s = int(round(float(s)))
    return f'{s // 3600}:{s % 3600 // 60:02}:{s % 60:02} h' if s >= 3600 else f'{s // 60}:{s % 60:02} min'
