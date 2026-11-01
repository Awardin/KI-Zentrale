# Baustand: Werkstatt – Zusammenfassungen mit lokalen Modellen verbessern

Datum: 23.10.2026
Branch: `werkstatt/zusammenfassung-20261023`
Basis: `main` @ `5ea8f2b`
Ausgangsstand: 225 Werkstatt-Tests OK; Zentrale 168 Tests, davon 166 grün und die zwei bekannten
Fehler in `zentrale\tests\test_karten.py` (unverändert).

Python für alle Kommandos:
`C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`.

## Scheibe 1 – Antwortgrenze und abgeschnittene Antworten

Datum: 23.10.2026

**Gebaut:**
- `LOKAL_MAX_TOKENS = 32768`; der OpenAI-Zweig von `Lokal.ausfuehren` schickt sie statt 8192.
- `finish_reason == 'length'` (OpenAI) und `done_reason == 'length'` (Ollama) erkannt. Bleibt nach dem
  Entfernen des Denkteils Text übrig, wird der Werkstatt-Hinweis zur Längengrenze angehängt; ein offener
  `<think>`-Teil oder leerer Text führt zum verständlichen `RuntimeError` und wird nie abgelegt.
- Kontextprüfung in `Auswertungen.anlegen`: `geschaetzt + reserve > kontext` mit
  `reserve = min(LOKAL_MAX_TOKENS, kontext // 4)`; Meldungstext unverändert.
- Tests in `werkstatt\tests\test_lokal.py` (Antwortgrenze, Denkteil, Reserve bei 128K und 32K).

**Kommandos und Ergebnisse:**
- `<python> -m unittest werkstatt.tests.test_lokal -v` → Ran 10 tests, OK
- `<python> -m unittest discover -s werkstatt\tests` → Ran 235 tests in 1.793s, OK
- `<python> -m py_compile werkstatt\auswertung.py werkstatt\tests\test_lokal.py` → Exit 0

**Commit:** `a41c6d9` – Werkstatt: Lokale Antwortgrenze 32768 und Denkteil-Pruefung

**Abweichungen/offene Punkte:** keine.

## Scheibe 2 – Strata und PolyStrata als lokale Auswerter

Datum: 23.10.2026

**Gebaut:**
- `Lokal._eintraege()` liefert zusätzlich `strata` und `polystrata`; neue Hilfsfunktion `Lokal._kennungen`
  (NInfer `modell_id`, PolyStrata `modell`, Strata alle `modell` der Varianten plus `modell` des Eintrags).
- `_geladen` prüft Port und `GET /v1/models`; die Werkstatt lädt nie selbst ein Modell.
- `ausfuehren` nutzt den OpenAI-Weg mit der tatsächlich geladenen Kennung und `LOKAL_MAX_TOKENS`, gibt
  `modell_tatsaechlich` zurück und meldet bei leerer Modellliste „… ist nicht geladen. Bitte in der
  Modellzentrale laden.“
- `katalog`: Strata-Kontext aus der Standardvariante; PolyStrata aus `untertitel`.
- Messlauf (`messungen.Messlauf`) und `lokale_modelle` in `server.py` filtern weiterhin auf
  `art in ('ollama', 'ninfer')`.
- Tests in `werkstatt\tests\test_lokal.py` (Q4-Kennung, leere Modellliste, PolyStrata, Katalog, Filter).

**Kommandos und Ergebnisse:**
- `<python> -m unittest werkstatt.tests.test_lokal -v` → Ran 17 tests, OK
- `<python> -m unittest discover -s werkstatt\tests` → Ran 242 tests in 1.918s, OK
- `<python> -m py_compile werkstatt\auswertung.py werkstatt\messungen.py werkstatt\server.py werkstatt\tests\test_lokal.py` → Exit 0

**Commit:** `0d683df` – Werkstatt: Strata und PolyStrata als lokale Auswerter

**Abweichungen/offene Punkte:** Die Kontext-Erkennung aus dem Untertitel wurde von `(\d+)K Kontext` auf
`(\d+)\s*K\b` erweitert, weil PolyStrata „128K · mit Bildern“ (ohne das Wort „Kontext“) im Untertitel
trägt. Ohne diese kleine Erweiterung bliebe der Kontext für PolyStrata leer.

## Scheibe 3 – Zielumfang und Anweisung „Gegliederte Zusammenfassung“

Datum: 23.10.2026

**Gebaut:**
- `PLATZHALTER` um `Zielumfang` vor `Transkript` erweitert; `_EINLEITUNG` nennt den neuen Platzhalter.
- `zielumfang(text)`: Zeitmarken zählen nicht als Wörter, `min(2500, 200 + Woerter // 4)`, auf 50
  abgerundet, Stichpunkte `max(5, round(ziel / 25))`, deutscher Tausenderpunkt.
- `_ausfuehren` nutzt `transcript.txt`, sonst `transcript-timestamps.txt` als Wortbasis und setzt
  `werte['Zielumfang']`.
- `STANDARD` enthält die neue Anweisung als Vorlage für neu eingerichtete Sammlungen; die bestehende
  Sammlung bleibt unverändert.
- Tests in `werkstatt\tests\test_anweisungen.py` (Formel, Format, Zeitmarken, Platzhalter, STANDARD).

**Kommandos und Ergebnisse:**
- `<python> -m unittest werkstatt.tests.test_anweisungen -v` → Ran 8 tests, OK
- `<python> -m unittest discover -s werkstatt\tests` → Ran 246 tests in 1.888s, OK
- `<python> -m py_compile werkstatt\anweisungen.py werkstatt\auswertung.py werkstatt\tests\test_anweisungen.py` → Exit 0

**Commit:** `061916e` – Werkstatt: Zielumfang aus der Wortzahl und gegliederte Anweisung

**Abweichungen/offene Punkte:** „auf 50 gerundet“ wurde als Abrunden auf die nächste 50 umgesetzt
(`ziel // 50 * 50`), damit das vorgegebene Beispiel 3.300 Wörter → 1.000 Wörter aufgeht. Die vorhandene
Promptsammlung ergänzt der Abnehmer selbst; die Datei wurde nicht angefasst.

## Scheibe 4 – Automatische Nachprüfung unter dem Ergebnis

Datum: 23.10.2026

**Gebaut:**
- Neues Modul `werkstatt\pruefung.py` mit reiner Funktion `nachpruefen(text, transkript_mit_marken,
  mit_abdeckung)`: Zeitmarken mit ±5 s gegen das Transkript (höchstens 10 ungültige genannt), Abdeckung
  in 300-s-Fenstern ab 60 Wörtern, CJK-Zeichen.
- `_ausfuehren` hängt den Prüfblock unter jeden Modelltext (alle Anbieter); `mit_abdeckung` gilt für
  Anweisungen ohne `[Frage]`.
- Kurzfassung als Feld `pruefung` (in `FELDER`) und als Zeile `pruefung: "…"` im Dateikopf; die
  Oberfläche zeigt „Prüfung: …“ bei fertigen Fassungen.
- Tests in `werkstatt\tests\test_pruefung.py` (Toleranz, Zeitbereiche, höchstens 10, Abdeckungslücken,
  dünne Fenster, CJK, Block im Text, Kopfzeile, Anweisung mit `[Frage]`).

**Kommandos und Ergebnisse:**
- `<python> -m unittest werkstatt.tests.test_pruefung` → Ran 16 tests, OK
- `<python> -m unittest discover -s werkstatt\tests` → Ran 262 tests in 1.824s, OK
- `<python> -m py_compile werkstatt\auswertung.py werkstatt\pruefung.py werkstatt\tests\test_pruefung.py` → Exit 0

**Commit:** `ea16bb3` – Werkstatt: Automatische Nachpruefung unter dem Ergebnis

**Abweichungen/offene Punkte:** Abdeckungslücken werden an den 5-Minuten-Fenstern gemeldet (z. B.
„Minute 5–10“); die Beispiele „Minute 8–13“ der Auftragsbeschreibung sind als Form verstanden, nicht als
freie Minute. Die Anzeige in `web\zusammenfassung.js` ist eine Zeile in der Statuszeile.

## Abschlussverifikation (Pflicht)

Alle Kommandos im Worktree-Wurzelordner, Windows PowerShell; Python wie oben.

1. `<python> -m unittest discover -s werkstatt\tests` → **Ran 262 tests in 1.843s, OK**, Exit 0.
2. `<python> -m unittest discover -s zentrale\tests` → **Ran 168 tests in 0.574s, FAILED (failures=2)**.
   166 grün; die zwei bekannten Fehler sind `test_kartennamen_nach_steckplatz` und
   `test_kurznamen_und_nebenkarte_aus_der_messung` in `zentrale\tests\test_karten.py` (RTX-3080-
   Steckplatznummer; im Hauptcheckout schon behoben). Nicht angefasst.
3. `<python> -m py_compile werkstatt\anweisungen.py werkstatt\auswertung.py werkstatt\messungen.py
   werkstatt\pruefung.py werkstatt\server.py werkstatt\tests\test_anweisungen.py
   werkstatt\tests\test_lokal.py werkstatt\tests\test_pruefung.py` → Exit 0.

`git diff --stat 5ea8f2b..HEAD` am Ende (ohne dieses Protokoll):

```
 werkstatt/anweisungen.py            |  39 ++++-
 werkstatt/auswertung.py             |  84 ++++++++--
 werkstatt/messungen.py              |   3 +-
 werkstatt/pruefung.py               | 105 ++++++++++++
 werkstatt/server.py                 |   4 +
 werkstatt/tests/test_anweisungen.py |  34 +++-
 werkstatt/tests/test_lokal.py       | 307 ++++++++++++++++++++++++++++++++++++
 werkstatt/tests/test_pruefung.py    | 181 +++++++++++++++++++++
 werkstatt/web/zusammenfassung.js    |   1 +
 9 files changed, 740 insertions(+), 18 deletions(-)
```

## Offene Punkte und Grenzen

- Es wurden keine Server gestartet und keine Ports angefragt; Strata, PolyStrata, Ollama und NInfer sind
  in den Tests vollständig gemockt. Ein Lauf am echten geladenen Modell steht aus.
- Die bestehende Promptsammlung wurde nicht verändert; die neue Anweisung ist nur Teil von
  `anweisungen.STANDARD` für neu eingerichtete Sammlungen.
- Dieses Protokoll wird nach den vier Scheiben in einem eigenen Commit festgehalten, weil die
  Commit-Hashes erst nach den Scheiben-Commits feststehen.
