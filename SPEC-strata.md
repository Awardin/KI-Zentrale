# Spezifikation: Strata (Qwen3.8-Flash-Next) als Eintrag der Modellzentrale

Stand 05.10.2026 · Auftrag Sascha („Konfiguration in die Modellzentrale einbauen, damit ich es von dort starten
kann“) · eingefroren, von Claude geschrieben, Umsetzung durch Codex.

## Ziel

Die Modellzentrale (`zentrale\`, Port 3894) verwaltet einen neuen Eintrag **„Qwen3.8 Flash-Next · Strata“** der
neuen Art `strata`: Starten, Bereitschaft erkennen, Belegung auf beiden Karten zuordnen, Beenden (auch als Schritt
in „GPU freigeben“ und im Platz-Dialog anderer Einträge) und ein Knopf „Chat öffnen“. Alles aus dem echten Zustand
(Ports, Prozesse, `/health`), nichts aus gemerkten Klicks.

## Hintergrund (Fakten, geprüft)

- Strata liegt unter `C:\LLM\runtimes\Strata`. Start (so schreibt es auch Stratas eigenes `run-iq3_xxs.bat`):
  `C:\LLM\runtimes\Strata\.venv\Scripts\python.exe C:\LLM\runtimes\Strata\serve\server.py --engine strata --config <konfig.json> --port 8095`
  mit Arbeitsordner `C:\LLM\runtimes\Strata` und `PYTHONIOENCODING=utf-8`.
- Prozessbaum unter Windows: `.venv\Scripts\python.exe` (venv-Weiterleitung) startet als Kind das Basis-Python
  `C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe` mit derselben
  Kommandozeile (`...serve\server.py ... --port 8095`); dieses startet `C:\LLM\runtimes\Strata\engine\strata.exe`
  (`--serve --pack ...`). Den Grafikspeicher belegt `strata.exe`; Port 8095 hält das Basis-Python.
- `GET http://127.0.0.1:8095/health` liefert u. a. `{"status": "ok", "max_context": 131072, "model": "...",
  "loaded": true, "service": "strata"}`; vor dem Laden fehlt die Antwort oder `loaded` ist falsch.
- Bereit nach etwa 20–30 s. Belegung gemessen (IQ3_XXS, beide Karten): **gpu:0 23.300 MiB, gpu:1 19.300 MiB**.
  Arbeitsspeicher: Strata hält etwa **41 GiB** der Experten fest im RAM; mit weniger freiem RAM lagert Windows
  stark aus.
- Getestet 05.10.2026: auch `strata-iq3_xxs-2gpu-256k.json` (197K Tokens, Kennwort gefunden); Standard bleibt 128K (mehr Experten auf den Karten, Strata-Empfehlung).
- Strata nimmt jeden Modellnamen an; OpenAI-API `http://127.0.0.1:8095/v1`, Chatseite `http://127.0.0.1:8095/`.

## Umsetzung

### 1. `zentrale\config.json` – neuer Eintrag (nach den Ollama-Einträgen, vor `bild-video`)

```json
{
  "id": "flash-next-strata",
  "art": "strata",
  "gruppe": "Sprachmodelle",
  "name": "Qwen3.8 Flash-Next · Strata",
  "untertitel": "125B · IQ3_XXS · 128K Kontext · beide Karten",
  "wofuer": "Großes Modell für Projekte, Coding und lange Dokumente. In DSH als „Strata – Flash-Next lokal“; OpenAI-API auf Port 8095.",
  "farbe": "#7A4FB5",
  "python": "C:\\LLM\\runtimes\\Strata\\.venv\\Scripts\\python.exe",
  "server_skript": "C:\\LLM\\runtimes\\Strata\\serve\\server.py",
  "engine": "C:\\LLM\\runtimes\\Strata\\engine\\strata.exe",
  "konfig": "C:\\LLM\\runtimes\\Strata\\strata-iq3_xxs-2gpu-128k.json",
  "port": 8095,
  "bedarf_mib": {"0": 23300, "1": 19300},
  "ram_bedarf_gib": 42,
  "startzeit_max_s": 300
}
```

Bestehende Einträge und Felder bleiben unverändert. Fehlt ein `strata`-Eintrag, muss die Zentrale wie bisher laufen
(alles Neue ist optional).

### 2. `gemeinsam\winapi.py`

Neue Funktion `freier_arbeitsspeicher_mib()` → verfügbarer physischer Speicher in MiB über
`GlobalMemoryStatusEx` (`ullAvailPhys`), nur `ctypes`.

### 3. `zentrale\erfassung.py`

- In `Erfassung.__init__`: `self.strata = next((e for e in cfg['eintraege'] if e['art'] == 'strata'), None)`;
  normierte Pfade `strata_engine`, `strata_skript` (mit `norm`), `strata_port_arg = f"--port {port}"`.
- `ist_strata(pid, procs)`: wahr, wenn (a) der Programmpfad gleich `engine` ist, oder (b) der Prozess
  `python.exe`/`pythonw.exe` heißt und seine Kommandozeile (klein geschrieben) den normierten Pfad von
  `server_skript` **und** `strata_port_arg` enthält. Ohne `strata`-Eintrag immer falsch.
- `einordnen`: vor Ollama prüfen → `('strata', name des Eintrags)`.
- `_dienste`: `d['strata'] = {'zustand': 'aus'|'startet'|'bereit'|'fremd', 'pids': [...], 'fremd': None|str,
  'kontext': int|None}`. Port lauscht und Prozess `ist_strata` → `/health` abfragen (Zeitlimit 1 s): `loaded`
  wahr → `bereit` (mit `kontext` = `max_context`), sonst `startet`. Port von anderem Prozess → `fremd` mit
  freundlichem Namen. Port frei, aber `ist_strata`-Prozesse vorhanden → `startet`. `pids` = alle `ist_strata`-PIDs.
- `_verbraucher`: Gruppe `strata` als Verbraucher mit `eintrag` = id des Eintrags, `farbe`, `blockiert: None`,
  `schritt: {'id': 'beenden:strata', 'text': f"{name} beenden"}` (wie NInfer).

### 4. `zentrale\aktionen.py`

- Verteiler: `starten` → `_strata_starten`, `stoppen` → `_strata_stoppen`, `schritt('beenden:strata')` →
  `_strata_stoppen(self.erf.strata)`.
- `_strata_starten(e)`: Zustand aus `messen()`; `bereit` → „läuft bereits“; `fremd` → `Fehler` (Port belegt von …).
  Fehlende Dateien (`python`, `server_skript`, `engine`, `konfig`) → `Fehler` mit Pfad. **RAM-Prüfung:** ist
  `freier_arbeitsspeicher_mib() / 1024 < ram_bedarf_gib` → `Fehler`: „Zu wenig freier Arbeitsspeicher: X GiB frei,
  Strata braucht etwa Y GiB. Bitte große Programme schließen.“ (eine Nachkommastelle, Komma). Dann
  `winapi.starte_losgeloest([python, server_skript, '--engine', 'strata', '--config', konfig, '--port', str(port)],
  Strata-Ordner (= Elternordner von `serve`), env mit `PYTHONIOENCODING=utf-8`, log_basis=logs\strata)`. Warten bis
  `/health` `loaded` wahr meldet (höchstens `startzeit_max_s`); beendet sich der Prozess vorher → `Fehler` mit
  `_letzte_meldung(logs\strata.out.log)` (Strata schreibt Fehler auf stdout). Rückmeldung
  „… ist bereit (N s, Kontext 131.072).“
- `_strata_stoppen(e)`: alle `ist_strata`-PIDs ermitteln; zuerst `strata.exe`, dann die Python-Prozesse mit
  `winapi.beenden` beenden; jede PID protokollieren. Danach warten, bis Port frei und keine `ist_strata`-Prozesse
  mehr da sind (15 s), sonst `Fehler`. Keine Prozesse → „… lief nicht.“ Niemals andere `python.exe` beenden.

### 5. `zentrale\server.py`

- `_zustaende`: Art `strata` → Zustand aus `d['strata']`; Detail bei `bereit`: „Kontext 131.072 · Port 8095“
  (Tausenderpunkt), bei `fremd`: „Port 8095 ist von … belegt.“
- `_schritte_ausfuehren`: Ziel `strata` dem Eintrag `strata` zuordnen (Zustand „stoppt“ während des Beendens).
- `konfig()`: bei Art `strata` `links = [{'art': 'strata', 'text': 'Chat öffnen', 'url': 'http://127.0.0.1:<port>/'}]`.

### 6. `zentrale\web\app.js`

- Links (bisher nur `comfy`) auch bei `strata` im Zustand `bereit` anzeigen.
- Beenden-Knopf auch im Zustand `startet` anbieten (wie bei NInfer).
- Kein weiteres Sonderverhalten; Texte wie bei NInfer („Starten“/„Beenden“).

### 7. Tests (`zentrale\tests\`, nur `unittest`)

Neue Datei `test_strata.py`: `ist_strata` mit gestellten Prozessinfos (Engine-Pfad, venv-Python mit Skript+Port,
Basis-Python mit Skript+Port, fremdes Python ohne Port, fremdes Python mit anderem Port) – ohne echte
Systemzugriffe (Erfassung so instanziieren bzw. `info` so ersetzen, dass kein WinAPI-Aufruf nötig ist, oder die
Prüflogik in eine reine Funktion auslagern); `plan_fuer_start` wählt `beenden:strata`, wenn ein Strata-Verbraucher
den Platz für NInfer belegt; RAM-Fehlermeldung (gestellter Wert). Bestehende Tests bleiben grün.

### 8. Doku

- `README.md`: Tabelle „Verwaltete Einträge“ um die Zeile ergänzen (eigener Server, Port 8095, gemessene Belegung);
  unter „Sicherheitsgrenzen“: Strata wird nur beendet, wenn Programmpfad `strata.exe` bzw. Python mit Skriptpfad und
  `--port 8095` passen; RAM-Prüfung vor dem Start.
- `PLAN.md`: kurzer Abschnitt „Strata-Eintrag (05.10.2026)“ mit Umfang und Abnahme.

## Grenzen

- Python nur Standardbibliothek. Nur 127.0.0.1. Kein Autostart, keine System-/Firewalländerung.
- `werkstatt\`, Studio, Ollama-, NInfer- und ComfyUI-Verhalten nicht ändern (außer der neuen Zuordnung im Verteiler).
- **Während des Baus kein Modell, kein Strata und keinen Dienst starten oder beenden**; die laufende Zentrale (3894)
  und Werkstatt (3895) nicht neu starten. Live-Abnahme macht Claude.
- Keine Dateien unter `C:\LLM` ändern.

## Nachweis

`python -m unittest discover -s zentrale\tests -v` im Ordner `C:\Workstation\Werkzeuge\KI-Zentrale` mit
`C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`; alle Tests grün.
Live-Abnahme (Claude): Zentrale neu starten, Eintrag starten → bereit, Belegung lila auf beiden Karten, „Chat öffnen“,
„GPU freigeben“ bietet „… beenden“ an, Beenden gibt Port und Speicher frei.
