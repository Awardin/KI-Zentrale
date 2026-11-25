# Spec: Strata-Eintrag mit zweiter Installation je Variante

Stand 24.11.2026, eingefroren. Auftrag Sascha („Ja, vorbereiten“) nach der Messung von Strata v0.2.21 gegen v0.2.1.3
(PLAN.md, „Flash-Next: Strata v0.2.21 gegen v0.2.1.3 gemessen“).

## Ziel

Der Eintrag `flash-next-strata` der Modellzentrale bekommt eine zusätzliche Wahl, die Flash-Next mit der neuen
Strata-Installation `C:\LLM\runtimes\Strata-0.2.21` startet. Die bisherige Installation `C:\LLM\runtimes\Strata` bleibt
für alle vorhandenen Varianten und bleibt Standard. Beide laufen nie gleichzeitig: ein Eintrag, ein Port (8095).

Fertig ist es, wenn die Zentrale Prozesse beider Installationen als „Strata“ erkennt, die neue Variante mit ihren
eigenen Pfaden startet, sie sauber beendet und alles Bisherige unverändert funktioniert.

## Ausgangslage (gelesen am 24.11.2026)

- `zentrale\planung.py`, `variante(e, vid)`: Eine Variante überschreibt beliebige Felder des Eintrags (alles außer
  `id`, `name`, `standard`). `_strata_starten` in `zentrale\aktionen.py` nimmt `python`, `server_skript`, `engine`,
  `konfig`, `ram_bedarf_gib` schon aus dem zusammengeführten Eintrag. **Starten braucht also keine Codeänderung**, nur
  die Felder in der Variante.
- `zentrale\erfassung.py` kennt dagegen genau eine Installation: `self.strata_engine`, `self.strata_vision`,
  `self.strata_skript` kommen nur aus dem Eintrag selbst. `ist_strata()` vergleicht damit. Prozesse der zweiten
  Installation würden als fremd gelten: Die Anzeige zeigte „Port belegt“, Beenden fände nichts, der Grafikspeicher
  landete unter „Windows & Programme“.
- `zentrale\aktionen.py`, `_strata_stoppen`: Die Reihenfolge (Engine, Bildprozess, Python) vergleicht ebenfalls mit
  `self.erf.strata_engine` und `self.erf.strata_vision`.
- `zentrale\server.py` erkennt die laufende Variante an `modell` und `kontext` aus `/health`. Das bleibt so; die neue
  Variante hat einen eigenen Modellnamen.

## Änderungen

### 1. `zentrale\erfassung.py`

- Im Konstruktor zusätzlich zu den drei vorhandenen Feldern (die bleiben unverändert, PolyStrata-Code und Tests nutzen
  `strata_engine`) drei Mengen normalisierter Pfade (`norm`) aufbauen, jeweils aus dem Eintrag und allen seinen Varianten:
  - `self.strata_engines`: `engine` des Eintrags und jedes `engine` einer Variante.
  - `self.strata_visions`: je Installation der Bildprozess. Regel je Variante: hat sie `vision_exe`, gilt das; hat sie
    nur `engine`, gilt `strata-vision.exe` im Ordner dieser Engine; hat sie keins von beiden, gilt der Bildprozess des
    Eintrags (wie bisher berechnet).
  - `self.strata_skripte`: `server_skript` des Eintrags und jedes `server_skript` einer Variante.
  Ohne Strata-Eintrag sind alle drei leer.
- `ist_strata()`:
  - `strata-vision.exe`: Pfad liegt in `strata_visions`.
  - Engine: Pfad liegt in `strata_engines`.
  - Python (`python.exe`, `pythonw.exe`): eines der `strata_skripte` steht in der Kommandozeile **und** `strata_port_arg`.
  - Der Sonderfall „Pfad leer, Elternprozess ist unser Server“ bleibt wie er ist.
- Sonst nichts ändern: `einordnen`, `_verbraucher`, `messen`, PolyStrata, llama.cpp, NInfer bleiben unberührt.
- Der Port bleibt Sache des Eintrags. Eine Variante mit eigenem `port` ist nicht vorgesehen und wird nicht unterstützt.

### 2. `zentrale\aktionen.py`

- `_strata_stoppen`, innere Funktion `reihenfolge`: `0`, wenn der Pfad in `self.erf.strata_engines` liegt, `1`, wenn er
  in `self.erf.strata_visions` liegt, sonst `2`.
- `_strata_starten` nicht umbauen. Nur falls ein Test zeigt, dass ein Variantenfeld nicht ankommt, die kleinste
  Korrektur.

### 3. `zentrale\config.json`

Im Eintrag `flash-next-strata` eine Variante **am Ende der Liste** ergänzen, exakt so:

```json
{"id": "q4-v31-q8-s21", "name": "Q4 v3.1 + Engram Q8 · Strata 0.2.21 (neu, im Test) · 128K · mit Bildern", "kontext": 131072,
 "modell": "qwen3.8-flash-next-unsloth-ud-iq4_xs-v31-q8engram-s21", "ram_bedarf_gib": 40,
 "python": "C:\\LLM\\runtimes\\Strata-0.2.21\\terminal\\.venv\\Scripts\\python.exe",
 "server_skript": "C:\\LLM\\runtimes\\Strata-0.2.21\\terminal\\serve\\server.py",
 "engine": "C:\\LLM\\runtimes\\Strata-0.2.21\\terminal\\engine\\strata.exe",
 "vision_exe": "C:\\LLM\\runtimes\\Strata-0.2.21\\terminal\\engine\\strata-vision.exe",
 "konfig": "C:\\LLM\\runtimes\\Strata-0.2.21\\terminal\\strata-unsloth-ud-iq4_xs-v31-q8engram-2gpu-128k.json"}
```

- `standard` bleibt bei `q4-v31-q8`. Keine andere Variante ändern.
- `varianten_grund`: vorn einen Satz ergänzen: „24.11.2026, Auftrag Sascha („Ja, vorbereiten“): zusätzliche Wahl mit
  Strata v0.2.21 / Engine 0.1.67 aus der zweiten Installation `C:\LLM\runtimes\Strata-0.2.21` (gemessen: Schreiben
  6–9 % schneller, Agenten-Runden etwa doppelt so schnell beim ersten Token); die alte Installation bleibt Standard. “
- Sonst nichts in `config.json` anfassen (Schreibweise, Einrückung und Reihenfolge der übrigen Zeilen bleiben).

### 4. Tests (`zentrale\tests\test_strata.py`, `zentrale\tests\test_varianten.py`)

Im Stil der vorhandenen Tests (gestellte Prozesse und `erf.info`, kein echter Systemzugriff). Neu:

1. **Erkennung zweite Installation:** Engine, Bildprozess und Python-Server (venv-Starter und Basisinterpreter) der
   Variante `q4-v31-q8-s21` mit `--port 8095` gelten als Strata; derselbe Server mit anderem Port nicht; `strata.exe`
   und `strata-vision.exe` an einem unbekannten Pfad nicht; eine Engine ohne lesbaren Pfad gilt, wenn ihr Elternprozess
   der Server der zweiten Installation ist.
2. **Einordnung:** `einordnen()` liefert für Prozesse der zweiten Installation `('strata', <Name des Eintrags>)`.
3. **Starten mit Variante:** `starten('flash-next-strata', variante='q4-v31-q8-s21')` ruft `starte_losgeloest` mit
   Python, Server-Skript und Einstellung der Variante auf, mit `--port 8095` und `--fit-max-tokens`, Arbeitsordner ist
   der Ordner über `serve` der zweiten Installation.
4. **Starten ohne Variante:** unverändert die alte Installation (vorhandene Tests bleiben grün, bei Bedarf einer ergänzt).
5. **Fehlende Datei:** Fehlt eine der vier Dateien der Variante, kommt `Fehler` „Datei fehlt: …“ und nichts wird gestartet.
6. **Beenden:** Laufen Prozesse der zweiten Installation, werden alle beendet, in der Reihenfolge Engine, Bildprozess,
   Python.
7. **Konfiguration:** Die Variante existiert mit genau den fünf Pfadfeldern; genau eine Variante ist Standard und das
   ist `q4-v31-q8`; die Paare aus `modell` und `kontext` aller Strata-Varianten sind eindeutig, **außer** den zwei
   schon vorhandenen Paaren, die sich heute decken (falls es welche gibt: im Test benennen statt die Konfiguration zu
   ändern).
8. **Anzeige:** Meldet `/health` das Modell `qwen3.8-flash-next-unsloth-ud-iq4_xs-v31-q8engram-s21` mit Kontext 131072,
   enthält das Detail des Eintrags den Namen der neuen Variante.
9. **Abgrenzung:** PolyStrata- und Edge0-Prozesse gelten weiter nicht als Strata (vorhandene Trenn-Tests bleiben grün).

Alle vorhandenen Tests bleiben grün. Erwartungen bestehender Tests nur anpassen, wenn sie wegen der zusätzlichen
Variante zählen oder auflisten (dann die kleinste Anpassung).

## Nicht-Ziele

- Kein Wechsel des Standards, keine 256K-Variante der neuen Fassung, kein DFlash2.
- Keine neue Art, kein zweiter Strata-Eintrag, kein zweiter Port.
- Nichts in `werkstatt\`, `atelier\`, `fibo\`, `gemeinsam\`, an der Weboberfläche oder an Dateien außerhalb des Repos.
- Keine Doku (PLAN.md, README.md, AGENTS.md): das macht Claude nach der Abnahme.
- Keine Umgebungsvariablen für den Start. Die neue Installation braucht mit MTP keine.

## Feste Grenzen

- Nur `zentrale\erfassung.py`, `zentrale\aktionen.py`, `zentrale\config.json` und die zwei Testdateien ändern.
- Prozesse werden weiterhin nur nach eindeutiger Prüfung zugeordnet (Programmpfad, Port, Kommandozeile). Die Erkennung
  darf durch die Änderung nicht weiter werden als „eine der bestätigten Installationen dieses Eintrags“.
- Tests starten oder beenden nichts Echtes.
- Kein Commit durch den Builder.

## Nachweis für den Builder

Im Ordner des Worktrees:

```
"%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe" -m unittest discover -s zentrale\tests
```

Falls der Sandkasten Tests mit temporären Ordnern nicht zulässt: die betroffenen Tests nennen, die übrigen ausführen.
Claude führt die ganze Suite außerhalb des Sandkastens aus.

## Abnahme durch Claude (nicht Aufgabe des Builders)

1. Ganzes Diff lesen, Suite außerhalb des Sandkastens: alle Tests grün.
2. Am echten System, Karten frei, mindestens 45 GiB RAM frei: Zentrale neu starten; neue Variante über `/api/plan` und
   `/api/starten` starten → „bereit“, Detail zeigt den Namen der neuen Variante, Grafikspeicher steht in der Anzeige
   unter dem Strata-Eintrag (nicht unter „Windows & Programme“), eine kurze Anfrage an Port 8095 wird beantwortet.
3. Über die Zentrale beenden → Port frei, keine `strata.exe` der zweiten Installation mehr, Karten frei.
4. Standardvariante starten → läuft aus der alten Installation, „bereit“, wieder beenden.
