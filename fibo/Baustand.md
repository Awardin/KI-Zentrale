# Baustand: Fibo-Dienst und Zentrale-Art `python_dienst` (Scheibe 1)

Stand: 22.10.2026
Branch: `atelier/fibo-20261022`, Basis `0bb9b00`
Gebaut nach `SPEC-atelier.md`, Teil A und B, samt verbindlichen Präzisierungen 1–5, 7 und 8.

## Teil A: Fibo-Dienst (`fibo/`)

Gebaut:

- `fibo/dienst.py`: HTTP-Dienst nur auf `127.0.0.1`, `ThreadingHTTPServer`, ein Arbeiter-Thread, Warteschlange.
  - `GET /health`: `loading`, dann `ok` mit Modell, aktivem Transformer, Warteschlange und laufendem Auftrag;
    Ladefehler `error` und Prozessende mit Fehlercode.
  - `POST /api/auftrag`, `GET /api/auftrag/<id>`, `POST /api/auftrag/<id>/abbrechen`, `GET /api/datei/<name>`,
    `POST /api/beschreiben`.
  - Größen auf Vielfache von 16 gerundet und auf 1,1 MP begrenzt; Eingabebilder und Maske (NEAREST, 0/255)
    vor der Pipeline; Anfragen über 64 MB mit 413.
  - Turbo-Wechsel wie in `fibo_reihe.py` (`remove_all_hooks`, Transformer tauschen,
    `enable_model_cpu_offload`), Freigabe des nicht aktiven Transformers bei `turbo_im_speicher=false`,
    Zustand `laedt_modell` und Dauer im Begleit-JSON.
  - Abbruch wartend sofort, rechnend über `_interrupt` im Schritt-Callback; kein Bild bei Abbruch.
  - Ablage `<ablage>\<JJJJ-MM-TT>\<id>.png` und `<id>.json` mit Prompt, Caption, Einstellungen, Seed, Modell,
    Sekunden, Wechseldauer und Lizenz „Fibo 2.0 – CC BY-NC 4.0, nur nicht-kommerziell“.
  - DeepSeek nur mit dem Text-Prompt von `bild`; `bearbeiten` ohne Sprachmodell; Schlüssel wird nur gelesen,
    aus Meldungen entfernt und nie geloggt oder in Dateien geschrieben. `LITELLM_LOCAL_MODEL_COST_MAP=True`
    vor dem Import von `bria_vgl`/litellm.
  - `torch`, `diffusers`, `bria_vgl` und Pillow werden erst im Arbeiter bzw. Beschreiber importiert;
    Pipeline-, Transformer-, Generator-, Bildleser- und Beschreiber-Fabriken sind austauschbar.
- `fibo/config.json`: Dev-Ordner, Turbo-Transformer, Schriften, Ablage, DeepSeek, `turbo_im_speicher=false`,
  Standardwerte Dev 50/5,0 und Turbo 4/1,0.
- `fibo/__init__.py`.
- `fibo/tests/test_dienst.py`: 22 Tests mit Fake-Pipeline und Fake-Bildern, ohne GPU, ohne torch, diffusers
  und Pillow.

## Teil B: Zentrale-Art `python_dienst` und Eintrag `fibo2`

Gebaut:

- `zentrale/erfassung.py`: Erkennung über Skriptpfad und `--port` in der Kommandozeile, egal welcher
  Interpreter (uv-Starter und Kind); Zustände `aus`/`startet`/`bereit`/`fremd` aus `/health`; `laufend` und
  `aktiv` für die Anzeige; Verbrauchergruppe `python_dienst:<id>` mit Beenden-Schritt; bei laufendem Auftrag
  blockiert („GPU freigeben“ nennt den Grund).
- `zentrale/aktionen.py`: Start mit `CUDA_VISIBLE_DEVICES`, RAM-Prüfung, Warten auf `status == ok`;
  Stoppen beendet den ganzen Prozessbaum (Kinder zuerst, dann Eltern) und wartet, bis Port und Prozesse frei
  sind; ohne `erzwingen` wird ein laufender Auftrag nicht beendet.
- `zentrale/server.py`: Zustand und Detail (Port, Dev/Turbo, Karte, laufender Auftrag), `auftrag`/`laufend`
  für den Dialog, `beenden:fibo2` in „GPU freigeben“, Atelier-Knopf aus `oeffnen_url`/`oeffnen_text`.
- `zentrale/config.json`: Eintrag `fibo2` am Ende angehängt; bestehende Einträge unverändert.
- `zentrale/web/app.js`: Atelier-Knopf nur bei bereitem Dienst; eigener Bestätigungsdialog beim Beenden mit
  laufendem Auftrag.
- `zentrale/tests/test_python_dienst.py`: 13 Tests (Erkennung von Starter und Kind, Zustände, Start,
  Prozessbaum, Planung, Freigabe, Serveranzeige).

## Verifikation (Windows PowerShell 5.1)

Python: `C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`

- `python -m unittest discover -s zentrale/tests` → `Ran 145 tests`, `OK` (vorher 132, 13 neue).
- `python -m unittest discover -s werkstatt/tests` → `Ran 214 tests`, `OK` (unverändert).
- `python -m unittest discover -s fibo/tests` → `Ran 22 tests`, `OK`.
- `C:\LLM\runtimes\Fibo2\.venv\Scripts\python.exe -m unittest discover -s fibo/tests` → `Ran 22 tests`, `OK`
  (dieselben Tests, kein Modell geladen).
- `python -c "import json; json.load(open('zentrale/config.json', encoding='utf-8'))"` → keine Ausgabe.
- `node --check zentrale/web/app.js` → keine Ausgabe (Syntax in Ordnung).
- `git diff --check` → keine Ausgabe.

## Abweichungen und Entscheidungen

- Das Protokoll wird in einem eigenen Commit nach den beiden Teil-Commits abgelegt. Ein Commit kann seinen
  eigenen Hash nicht enthalten; die zwei Teil-Commits A und B bleiben die Bau-Commits.
- `skript` in `zentrale/config.json` zeigt auf den Hauptcheckout
  `C:\Workstation\Werkzeuge\KI-Zentrale\fibo\dienst.py`, nicht auf diesen Worktree. Die Zentrale-Konfiguration
  beschreibt den produktiven Stand; im Worktree würde der Pfad sonst nur bis zum Merge stimmen.
- `oeffnen_url` zeigt auf `http://127.0.0.1:3896/` (Atelier). Das Atelier entsteht erst in Scheibe 2/3; der
  Knopf ist deshalb bis dahin ohne Ziel.
- `ram_bedarf_gib` 30 ist laut Spec vorläufig; eine echte Messung steht aus.
- Der echte Start mit Modell und GPU wurde nicht ausgeführt (Sperrliste: kein Modell laden, keine GPU nutzen).
  Die Tests nutzen Fake-Pipeline und Fake-Bilder; der Dienst wurde in diesem Lauf nicht auf Port 8098 gestartet.
- Der Prozess beendet sich bei einem Ladefehler nach kurzer Anzeige von `status: error` mit Fehlercode 1
  (`os._exit(1)`), damit `/health` den Fehler noch zeigen kann.

## Offene Punkte

- Echte Abnahme: Fibo in der Zentrale starten, Karte prüfen, nvidia-smi ≈17,5 GiB, Stoppen und „GPU freigeben“.
- Echte API-Läufe: `bild` mit `deepseek` und `keiner`, `bearbeiten` mit Turbo und Dev, mit Maske, Abbruch.
- Atelier (Scheibe 2/3) unter Port 3896; danach `oeffnen_url` prüfen.
- `ram_bedarf_gib` nach der ersten echten Messung bestätigen oder anpassen.

## Commit-Hashes

- Teil A (`Fibo: Dienst fuer Fibo 2.0 mit Warteschlange und Ablage`):
  `3acdcbff52abf2ee6174b1c1c414afd52af89565`
- Teil B (`Zentrale: Art python_dienst und Eintrag Fibo 2.0`):
  `74fdb2c1ac6bd63a533a5ff59120f821ee480342`
