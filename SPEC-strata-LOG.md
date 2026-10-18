# Bauprotokoll Strata-Eintrag (SPEC-strata.md)

## Act 3 — Build

Builder: Codex `gpt-6.1-sol`, Denkstufe high (Runde 1), medium (Korrekturrunde) · Thread
`01a10bd3-2a39-7b02-9285-34b264c9c65e` · KI-Zentrale ist kein Git-Repository: Vergleich gegen eine Kopie von
`zentrale\`, `gemeinsam\`, README/PLAN/AGENTS im Claude-Scratchpad (vor dem Bau, 05.10.2026 13:28).

### Round 1 — Codex build

Geändert: `zentrale\config.json` (Eintrag), `gemeinsam\winapi.py` (`freier_arbeitsspeicher_mib`),
`zentrale\erfassung.py` (`ist_strata`, Zustand, Verbraucher), `zentrale\aktionen.py` (Start mit RAM-Prüfung,
Beenden Engine vor Python, Schritt `beenden:strata`), `zentrale\server.py` (Zustand, Schrittzuordnung,
Link „Chat öffnen“), `zentrale\web\app.js` (Link, Beenden während „startet“), neu `zentrale\tests\test_strata.py`,
README, PLAN. Codex-Bericht: 32 + 142 Tests grün, keine Abweichungen.

### Claude's verdict (Runde 1)

Diff vollständig gelesen (ohne Zeilenende-Unterschiede): spezifikationstreu, Stil passt, nichts außerhalb des
Umfangs geändert. Tests selbst ausgeführt: Zentrale 32/32, Werkstatt 142/142 grün.

Befunde für die Korrekturrunde:
1. `ist_strata` erkennt Python-Prozesse nicht, wenn Strata über `run-iq3_xxs.bat` gestartet wurde
   (Argumente in Anführungszeichen, `"--port" "8095"`) → Server würde als „fremd“ gemeldet und nicht beendet.
2. RAM-Prüfung läuft auch im Zustand „startet“ → falsche Meldung „zu wenig RAM“ bei erneutem Klick während des Ladens.
3. `ist_strata` fragt Details aller Prozesse ab → nur `strata.exe`/`python(w).exe` prüfen.

### Round 2 — Codex fixes (resume, gleicher Thread, Denkstufe medium)

Codex-Bericht: alle drei Punkte behoben (`ist_strata` ohne Anführungszeichen vergleichen und fremde Prozessnamen
vor `info()` abweisen; RAM-Prüfung nur beim tatsächlichen Start), Regressionstests ergänzt, PLAN-Zeile ergänzt.
Keine Abweichungen.

### Claude's verdict (Runde 2)

Änderungen gelesen: genau die drei Punkte, nichts außerhalb. Tests selbst ausgeführt: Zentrale 35/35, Werkstatt
142/142 grün.

### Live-Abnahme (Claude)

Zentrale-Dienst neu gestartet (nur Prozess mit `KI-Zentrale\zentrale\server.py` auf Port 3894). In der Oberfläche:
Starten → bereit nach 24 s, Detail „Kontext 131.072 · Port 8095“, Belegung lila 22,6 GiB (3090) + 18,7 GiB (3080),
„Chat öffnen“ vorhanden, API-Testfrage richtig beantwortet. „GPU freigeben“ → Schritt „… Strata beenden (41,4 GiB)“,
bestätigt → beendet in 4 s, keine Reste. Erneut gestartet (24 s) → „Beenden“ → drei Prozesse beendet, Port frei,
Karten 0 MiB, Zustand „Aus“. **Bestanden.** Kein Git-Repository: keine Commits; Änderungen sind live.

## Act 3b — Build (SPEC-strata-bilder-dsh.md)

Builder: Codex `gpt-6.1-sol`, Denkstufe medium, frische Sitzung (Thread `01a10c05-9638-71d2-9a68-ce540b287acf`);
Vergleich gegen eine zweite Kopie (14:24).

### Round 1 — Codex build

Geändert: config.json (`vision_exe`, Untertitel „Bilder“, Bedarf 23.500/19.400 MiB), erfassung.py (`strata-vision.exe`
über exakten Pfad), aktionen.py (Stoppreihenfolge; `_programm_beenden`: WM_CLOSE an alle Fenster, nach 8 s gezielt hart,
PID-Pfad jedes Mal frisch geprüft), winapi.py (`fenster_schliessen`), app.js (Knopf „Beenden“ mit Dialog), neue Tests
`test_programm.py`, erweitertes `test_strata.py`, README, PLAN. server.py unverändert (Programme hatten „stoppt“ schon).

### Claude's verdict

Diff gelesen: spezifikationstreu, nichts außerhalb des Umfangs. Tests selbst: 45/45 Zentrale, 142/142 Werkstatt.
Live-Abnahme bestanden (siehe PLAN.md). Keine Korrekturrunde nötig.
