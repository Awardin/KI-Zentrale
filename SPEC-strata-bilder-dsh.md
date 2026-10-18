# Spezifikation: Strata-Bildprozess erkennen und „Beenden“ für Programme (DSH)

Stand 05.10.2026 · Auftrag Sascha (Bilder in Strata eingeschaltet; „DSH hat keinen Stopp-Knopf in der
Modellzentrale“) · eingefroren, von Claude geschrieben, Umsetzung durch Codex. Ergänzt `SPEC-strata.md`.

## Hintergrund (geprüft)

- Strata läuft jetzt mit Bildern. Die Konfiguration `C:\LLM\runtimes\Strata\strata-iq3_xxs-2gpu-128k.json` hat einen
  Abschnitt `vision` mit `exe = C:\LLM\runtimes\Strata\engine\strata-vision.exe`. Strata startet diesen Encoder als
  eigenen Prozess `strata-vision.exe` (Kind des Strata-Pythons). Er belegt Grafikspeicher. Gemessen mit Bildern:
  gpu:0 23.359 MiB, gpu:1 19.299 MiB.
- Die Modellzentrale erkennt bisher nur `strata.exe` und die beiden Strata-Pythons. `strata-vision.exe` landet in
  der Belegung unter „Windows & Programme“ und wird beim Beenden nicht ausdrücklich beendet.
- DSH Desktop (Art `programm`) schließt sein Fenster nur in den Infobereich; die Prozesse
  (`C:\Users\sasch\AppData\Local\Programs\DSH Desktop\DSH Desktop.exe`, etwa 7 Stück) laufen weiter. Die Zentrale
  bietet für Programme nur „Öffnen“/„Nach vorn holen“.

## Umsetzung

### 1. Strata-Bildprozess

- `zentrale\config.json`, Eintrag `flash-next-strata`: neues Feld
  `"vision_exe": "C:\\LLM\\runtimes\\Strata\\engine\\strata-vision.exe"`; `bedarf_mib` auf `{"0": 23500, "1": 19400}`;
  `untertitel` auf „125B · IQ3_XXS · 128K Kontext · Bilder · beide Karten“.
- `erfassung.py`: `ist_strata` erkennt zusätzlich Prozesse namens `strata-vision.exe`, deren Programmpfad gleich dem
  normierten `vision_exe` ist (Feld optional; fehlt es, gilt `<Ordner von engine>\strata-vision.exe`). Namensfilter
  um `strata-vision.exe` erweitern. Belegung des Bildprozesses zählt damit zum Strata-Verbraucher.
- `aktionen.py`, `_strata_stoppen`: Reihenfolge Engine, dann Bildprozess, dann Python-Prozesse.
- Tests in `zentrale\tests\test_strata.py`: Bildprozess mit richtigem Pfad erkannt, gleichnamiger mit fremdem Pfad
  nicht; Stoppreihenfolge.

### 2. „Beenden“ für Programme (Art `programm`, heute nur DSH)

- `winapi.py`: neue Funktion `fenster_schliessen(pids)` – sendet `WM_CLOSE` (PostMessage) an **alle** Top-Level-
  Fenster (auch unsichtbare) dieser PIDs; gibt die Anzahl zurück.
- `aktionen.py`: `stoppen` für Art `programm` → `_programm_beenden(e)`: PIDs mit exakt passendem Programmpfad
  ermitteln (wie in `erfassung._dienste`); keine → „… lief nicht.“ Sonst `fenster_schliessen`, bis zu 8 s warten;
  danach noch laufende PIDs **mit exakt passendem Programmpfad** per `winapi.beenden` beenden; jede PID
  protokollieren. Danach prüfen, dass keine passenden PIDs mehr laufen (5 s), sonst `Fehler`. Niemals andere
  Prozesse beenden. Rückmeldung „DSH Desktop beendet.“ (Name des Eintrags).
- `web\app.js`: bei Art `programm` im Zustand `laeuft` zusätzlich Knopf „Beenden“. Vor dem Senden ein Dialog
  (bestehendes `zeigeDialog`): Titel „<Name> beenden?“, Text „Laufende Aufgaben und nicht gesendete Eingaben in
  <Name> gehen verloren.“, Hauptknopf „Beenden“.
- `server.py`: Verb „wird beendet“ wie bei anderen Arten; Zustand während des Beendens „stoppt“.
- Tests: neue Datei `zentrale\tests\test_programm.py` (gestellte Prozessliste/WinAPI): nur Prozesse mit exakt
  passendem Pfad werden angefasst; erst Fenster schließen, dann Rest beenden; „lief nicht“ ohne Prozesse.

### 3. Doku

README (Verwaltete Einträge: Strata mit Bildern und neuer Belegung; Sicherheitsgrenzen: Programme werden nur über den
exakten Programmpfad beendet, erst sanft, dann hart; Strata-Bildprozess) und PLAN.md (kurzer Abschnitt
„Strata-Bilder und Beenden für Programme (05.10.2026)“).

## Grenzen

Wie `SPEC-strata.md`: nur Standardbibliothek, nur 127.0.0.1, `werkstatt\` und andere Arten unverändert, nichts unter
`C:\LLM` ändern, während des Baus keine Modelle/Dienste/Programme starten oder beenden und die laufende Zentrale
nicht neu starten. Live-Abnahme macht Claude.

## Nachweis

`%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s zentrale\tests -v` und
`... -s werkstatt\tests` im Ordner `C:\Workstation\Werkzeuge\KI-Zentrale`; `config.json` gültig;
`node --check zentrale\web\app.js`.
