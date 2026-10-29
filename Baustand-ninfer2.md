# Baustand NInfer 2 (Branch `ki-zentrale/ninfer2-20261029`)

## Auftrag

Zwei NInfer-Instanzen gleichzeitig: Instanz 1 fest auf der RTX 3090 FE (Index 0), Instanz 2 auf der RTX 3090
Suprim (Index 1, Monitorkarte) mit kleinerem Kontext. Mehrfachbetrieb nach dem Muster von Art `llamacpp`, dazu
das optionale Feld `feste_karte`. Basis: `main @ 3354ddb`.

## Gebaut

**A. Mehrere NInfer-Einträge** (`zentrale/erfassung.py`, `aktionen.py`, `server.py`)

- `Erfassung.ninfer_eintraege` hält alle Einträge der Art `ninfer`; `Erfassung.ninfer` bleibt als Eintrag mit der ID
  `ninfer` erhalten (Werkstatt/Test-Kompatibilität).
- `ist_ninfer` erkennt Programmpfad **und** `--port` und liefert die Eintrags-ID. Ein NInfer auf fremdem Port bleibt
  über `freundlich()` „NInfer (anderer Port)“ und zählt zu „Windows & Programme“.
- `_dienste`, `einordnen`, `_verbraucher` arbeiten je Eintrag. Der Eintrag `ninfer` behält den
  Verbraucher-Schlüssel `ninfer` und den Schritt `beenden:ninfer`; weitere Einträge nutzen `ninfer:<id>` bzw.
  `beenden:<id>`.
- Starten/Stoppen je Eintrag: Logname `ninfer` nur für `ninfer`, sonst die ID (z. B. `ninfer-2`); Fehlermeldungen
  nennen den Eintragsnamen. Der Stopp filtert Prozesse über die passende Eintrags-ID, beendet also nicht die andere
  Instanz.
- `server.py`: Zustand und Karte je Eintrag; `_schritte_ausfuehren` ordnet `beenden:ninfer` bzw. `beenden:<id>` dem
  richtigen Eintrag zu.

**B. Feste Karte** (`zentrale/planung.py`)

- Neues optionales Feld `feste_karte` (nvidia-smi-Index). Ist es gesetzt, liefert `karte_waehlen` genau diese Karte,
  sofern sie in `karten` enthalten ist; sonst `None` mit „Karte <i> passt nicht zu …“. Die Freigaben berechnet der
  Aufrufer anschließend mit `plan_fuer_start` für genau diese Karte. Ohne das Feld bleibt die bisherige Wahl
  unverändert.

**C. Konfiguration** (`zentrale/config.json`)

- `ninfer`: Name „Qwen3.8 27B · NInfer 1“, Untertitel „128K Kontext · RTX 3090 FE“, `feste_karte: 0`;
  `karten_grund` um den Satz zur festen Karte (29.10.2026, Wunsch Sascha) ergänzt.
- Neuer Eintrag direkt danach: `ninfer-2`, Port 8081, Modell-ID `qwen3.8-27b-ninfer-2`, 96K Kontext
  (`--max-context` und `--kv-capacity` 98304), `karten: ["RTX 3090"]`, `feste_karte: 1`,
  `bedarf_je_karte_mib: 21000`, `startzeit_max_s: 240`, eigene Farbe `#6F5BD0`, gleiches Programm und gleiche
  Modelldatei wie `ninfer`. `wofuer` und `bedarf_hinweis` wie im Auftrag.

**D. Tests** (`zentrale/tests/test_ninfer2.py`, ein bestehender Fall in `test_karten.py` angepasst)

- Neue Fälle: Zuordnung der Prozesse auf 8080/8081, fremder Port und fremdes Programm, Verbraucher-Schlüssel und
  Schritte, Anzeige je Eintrag, Stopp von `ninfer-2` beendet nur PID der zweiten Instanz, Start mit eigenem
  Logname/Port/Kontext, Startfehler mit Eintragsnamen und eigener Fehlerlogdatei, `_schritte_ausfuehren`.
- `feste_karte`: wählt die feste Karte auch bei engerer anderer Karte, plant Freigaben auf dieser Karte, ohne Feld
  bleibt die alte Wahl, ungültige feste Karte nennt den Grund; Server-Plan für `ninfer-2` auf der Suprim.
- Konfig-Test: Port 8081, `feste_karte` 1, 98304 Kontext, gleiche Programm-/Modelldatei, Argumente, Farbe.
- Der bestehende Test `test_ninfer_plan_und_start_auf_der_freien_karte` hieß bisher so, weil NInfer ohne feste Karte
  auf die freie Suprim auswich. Mit der gewollten festen Karte 0 muss LightOnOCR auf der FE weichen; der Test prüft
  jetzt genau das (gleiche Ausgangslage, neue erwartete Kartenwahl) und heißt
  `test_ninfer_plan_auf_der_festen_karte`.

**Werkstatt:** Keine Änderungen nötig. `werkstatt/auswertung.py` und `werkstatt/messungen.py` lesen NInfer-Einträge
generisch über `port`/`modell_id`; mit der neuen Konfiguration bleiben alle 225 Tests grün.

**`zentrale/web/app.js`:** Keine Änderung. Die Oberfläche erzeugt Zeilen, Zustände und Start/Stopp-Knöpfe generisch aus
`KONFIG.eintraege`; beide NInfer-Einträge erscheinen als eigene Zeilen. Die feste Karte wird nach dem Start über die
gemessene Belegung („Auf der RTX 3090 …“) angezeigt, vor dem Start über den Untertitel.

## Verifikation

Python:
`C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`

Vor dem Bau (Basis `3354ddb`):

- `... -m unittest discover -s zentrale\tests` → `Ran 171 tests`, `OK`
- `... -m unittest discover -s werkstatt\tests` → `Ran 225 tests`, `OK`

Nach dem Bau:

1. `& '<python>' -m unittest discover -s zentrale\tests`
   → `Ran 185 tests in 0.577s`, `OK` (Exit 0)
2. `& '<python>' -m unittest discover -s werkstatt\tests`
   → `Ran 225 tests in 1.746s`, `OK` (Exit 0)
3. `& '<python>' -c "import json; json.load(open('zentrale/config.json', encoding='utf-8'))"`
   → kein Fehler (`JSON OK`, Exit 0)

Keine Zentrale, keine Werkstatt, kein NInfer und keine Server gestartet; keine Ports 3894/3895/8080/8081/8095
angefragt. Alle Prozess- und HTTP-Zugriffe der Tests sind gestellt.

## Abweichungen / Entscheidungen

- Zwei Commits statt einem: Bau-Commit und Protokoll-Commit (dieser Datei). Der Bau-Commit-Hash steht unten.
- Die Fehlermeldung bei fehlenden NInfer-Dateien nennt jetzt zusätzlich den Eintragsnamen (Auftrag: Fehlermeldungen
  nennen den Namen); andere Dienste bleiben unverändert.
- Farbe `#6F5BD0` für NInfer 2: ähnlich dem Blau von NInfer 1 (`#4453C8`), aber im Streifen unterscheidbar.
- `bedarf_hinweis` für `ninfer-2` wird in der Oberfläche vor dem Start angezeigt; die feste Karte selbst ist dort
  nicht als eigener Text hinterlegt (kein UI-Umbau im Auftrag).

## Offene Punkte

- NInfer 2 wurde nicht gestartet; 96K-Kontext und 21.000 MiB sind die beauftragte Schätzung. Beim ersten echten
  Start messen und `bedarf_je_karte_mib`/`bedarf_hinweis` nachziehen.
- Die Erkennung wurde nur mit gestellten Prozessdaten geprüft, nicht an einem laufenden NInfer 2 (Sperrliste).
- Der Reiter „Monitor“ hat für NInfer weiterhin keine Anzeige; das war nicht Teil des Auftrags.

## Commit

- Bau-Commit: `b18f5e28f2ef8840f6fb02ba3d1b7a0d733c25a6`
  (`Zentrale: Zwei NInfer-Instanzen, jede fest auf ihrer Karte`), 7 Dateien, 396 Einfügungen, 64 Löschungen.
- Dieses Protokoll wird als eigener Commit auf demselben Branch nachgetragen.
