# Bau-Log: Reiter „Prompts“ – neue Oberfläche nach Vorlage

Plan: [SPEC-prompts-oberflaeche.md](SPEC-prompts-oberflaeche.md), geschrieben von Astra (gpt-6-astra, xhigh, nur lesend)
am 08.11.2026, von Claude gegen den Code geprüft. Sascha entschied am 08.11.2026: dunkel lassen, Diktat später, übrige
Punkte mit Spec-Vorgabe; Bau-Go „Ja, bauen“.

## Act 3 — Build

Builder: gpt-6.1-sol, Denkstufe xhigh (Sascha 07.11.2026: „Nutze SOL auf Xhigh zum bauen falls möglich“, am 08.11.2026
für diesen Bau bestätigt). Worktree `C:\Workstation\Werkzeuge\KI-Zentrale-bau-oberflaeche`, Branch
`bau/prompts-oberflaeche` ab b22e36c. Start abgekoppelt über WMI (CREATE_BREAKAWAY_FROM_JOB), Ausgabe nur in Dateien.
Ausgangsstand im Worktree: 403 Tests OK, 1 übersprungen. Thread 01a1bbd7-377f-7300-8b5b-32001b159b4a.

### Runde 1 — Sol baut Scheiben 1–3

- Lauf 08.11.2026 16:46–17:14 (28 min), ein Versuch, Exit 0. Tokens: Eingabe neu 141 k, aus Cache 7 064 k, Ausgabe 68 k
  (davon Denken 26 k); Wochenfenster aller Chats 15 → 16 %.
- Bericht: Scheiben 1–3 umgesetzt, 48 neue Tests, nach jeder Scheibe volle Suite grün (410 / 421 / 451), keine
  inhaltlichen Abweichungen, Regeldatei nur unter `_uebergabe/`, kein Testserver gestartet, kein Commit.

### Claudes Urteil (Runde 1)

- Diff vollständig gelesen (auswertung.py, config.json, server.py, prompts.py, prompts.js, zusammenfassung.js, Tests).
  Spec-treu: 27B nur für `qwen27-unsloth`/`qwen27-iq3s`, Abo-Kennzeichnung (`zugang`, `prompts_verfuegbar`,
  `zugang_text`), erneute Abo-Prüfung vor dem Aufruf, Codex-Kindprozess ohne `OPENAI_*`/`CODEX_API_*`, Bauversion 2
  getrennt vom alten Auftragsbau (feste Referenzhashes), Idempotenz über `_Auftraege\<anfrage_id>.json` mit allen fünf
  Absturzstellen getestet, `_Auftraege` erscheint nicht in der Liste (`_`-Präfix wird übersprungen).
- Eigene Prüfung: Suite selbst gelaufen, **Ran 451 tests, OK (skipped=1)**; `git diff --check` sauber.
- Echtdaten nur lesend (Skript `echtdaten_check.py` im Bauordner): echte Sammlung ergibt 34 Kästen in sechs
  Abschnitten („1. Wissen einpflegen“ … „6. Diese Sammlung erweitern“), Werkstatt-Abschnitt ausgeschlossen, IDs
  eindeutig; echte Zentrale-Konfiguration liefert beide 27B-Einträge (8106/8103) mit ihren Modellkennungen, OCR und
  Coder-Modelle bleiben draußen; Codex-Zugang aus der echten Anmeldedatei = `abo` (nur das Ergebnis ausgegeben);
  Regeldatei aus `_uebergabe/` validiert.
- Kleiner Vermerk, nicht nachgebessert: `composer_senden` hält die Dateisperre auch während der Verfügbarkeitsprüfung
  (bei Claude ein frischer Anmeldestatus). Betrifft nur den Moment des Sendens; vertretbar.
- Browser-Abnahme der Scheiben 1–3 folgt zusammen mit Scheibe 4, weil die Oberfläche erst dort entsteht.
- Ergebnis: angenommen, keine Nachbesserung. Weiter mit Runde 2 (Scheiben 4–6) im selben Thread.

### Runde 2 — Sol baut Scheiben 4–6

- Resume desselben Threads, 08.11.2026 17:18–17:59 (41 min), ein Versuch, Exit 0. Thread gesamt bis dahin: Eingabe neu
  272 k, aus Cache 22 945 k, Ausgabe 169 k (davon Denken 72 k); Wochenfenster aller Chats 15 → 18 %.
- Bericht (`_uebergabe/ABNAHME-SCHEIBEN-4-6.md`): Oberfläche nach Vorlage, Material/Kontextbausteine, Harness
  `werkstatt/tests/abnahme_harness.py` (nur 127.0.0.1:3897, Fake-Anbieter, `steuerung.json`/`aufrufe.json`),
  deutsche Netzfehlermeldung in `api()`. Suite 452 / 461 / 467 grün. Regeldatei unverändert. Prüfdateien unter
  `_uebergabe/` blieben liegen (Löschen von der Freigabeprüfung blockiert).

### Claudes Urteil (Runde 2)

- Suite selbst: **Ran 467 tests, OK (skipped=1)**, `git diff --check` sauber. Kein `innerHTML`, kein neuer Zeitgeber
  (nur der bestehende `P.timer`), Material über vorhandenes `datei_lesen` (Wurzeln, Sperrordner, Zugangsdaten),
  Browserdateien ohne Pfad, Kontextkennungen über `kennung()`; Harness sperrt fremde Verbindungen und Programmstarts.
- Browser am Harness (1366, 1920, 390 px): drei Ziele senden → je Ziel eine Fassung mit Original/Neu nebeneinander;
  Strg+Enter sendet, Esc schließt die Typauswahl mit Fokusrückgabe; verlorene Sendebestätigung → Meldung „Die
  Bestätigung fehlt …“ und „Status prüfen“ findet dieselbe Gruppe; `aufrufe.json` 6 Aufrufe für 2 × 3 Ziele (kein
  Doppellauf); absichtlich fehlgeschlagenes Flash-Next-Ziel mit Grund, „Wiederholen“ macht es fertig; Entdecken mit
  sechs Abschnittsgruppen und Eigene Prompts nach Typ; Kontextbaustein anlegen und im Composer auswählen; 390 px ohne
  horizontalen Überlauf.
- Befunde für Fixrunde 1: (1) „Zuletzt“ läuft bei 1366/1920 px horizontal über; (2) „Wiederholen“ fehlt im
  Ergebnisblock des fehlgeschlagenen Ziels; (3) Kategorie „Auto“ in Entdecken; (4) Liste aller nicht verfügbaren
  Profile unter dem Composer zu laut; (5) doppelter Grund in Auswahltexten.

### Runde 3 — Fixrunde 1 (Sol, Resume)

- Resume desselben Threads, 08.11.2026 18:05–18:16 (11 min), ein Versuch, Exit 0. Tokens: Eingabe neu 85 k, aus Cache
  4 699 k, Ausgabe 25 k (davon Denken 13 k); Wochenfenster aller Chats 18 → 19 %.
- Bericht: alle fünf Punkte umgesetzt (style.css/prompts.js für „Zuletzt“; Wiederholen/Abbrechen im Zielblock;
  Auto-Einträge nur in der Anzeige unter dem erkannten Typ oder „Weitere Prompts“; Problemhinweise nur zur Auswahl,
  volle Liste eingeklappt; doppelte Gründe entfernt). Neuer Node-Test `prompts_fixrunde1_bedienung.js` (in
  `test_prompts.py` eingebunden), ein Python-Test für Typmetadaten bei unveränderten Dateibytes. Suite 469 OK.

### Claudes Urteil (Runde 3)

- Browser am Harness bei 1366 px: „Zuletzt“ bricht um, Spalte 175 px = scrollWidth (kein Überlauf); Entdecken ohne
  „Auto“ (Code, Schreiben, Weitere Prompts, 1.–6. Testbereich); unter dem Composer nur Hinweise zur Auswahl und
  „Nicht verfügbare Modelle (5)“ eingeklappt; Auswahltexte ohne doppelten Grund. Wiederholen/Abbrechen im Zielblock
  durch den Node-Bedientest belegt, im Browser nicht eigens nachgeklickt.
- Sols manuelles Geometrie-Skript `prompts_fixrunde1_geometrie.mjs` (ego-browser, nicht in der Suite) nach
  `_uebergabe/` verschoben; es gehört nicht in den Commit.
- Ergebnis: angenommen. Eine Fixrunde von zwei möglichen verbraucht; keine Übernahme durch Claude nötig.

### Sicherheitsprüfung (Skill security-review, 08.11.2026)

- Gegenstand: Arbeitsbaum gegen HEAD (prompts.py, server.py, auswertung.py, config.json, web/*), Tests ausgenommen.
  Prüfer: Claude-Subagent (nur lesend), Ergebnis von Claude gegengelesen.
- **Keine ausnutzbaren Befunde.** Geprüft und sicher: POST-Aktionen über `_post_ok()` (Host, `X-Werkstatt: 1`, fremde
  Origin) – kein CSRF; neue GET-Routen über `_host_ok()` ohne CORS-Freigabe; `anfrage_id` nur kanonische UUID;
  Kontextkennung über `kennung()` plus `_pfad()`/`pfad_erlaubt`; Material „datei“ über das bestehende `datei_lesen`
  (Wurzeln, Sperrordner, `.env`, realpath) plus Endungsliste, Browsermaterial ohne Pfad; Belegköpfe über `_kopfwert`;
  Claude/Codex mit argv-Liste ohne Shell, Prompt über stdin; Codex-Umgebung nur gekürzt; `zugang()` liefert nur die
  Einordnung, nie Werte; keine neuen Logzeilen mit Inhalt; kein neues `innerHTML` (Modellantworten jetzt sogar als
  Text statt Markdown-HTML).
- Härtung übernommen: `auftrag_aus_beleg` übernimmt `auftrags_id` aus dem Belegkopf nur in der selbst vergebenen
  Hexform (8–16 Zeichen), sonst neue Kennung – die Kennung geht in den Dateinamen `codex-<id>.txt`. Test
  `test_auftragskennung_aus_dem_beleg_nur_in_hexform`. Nicht übernommen (nur DoS, ausgeschlossen): blinde GET-Aufrufe von
  `/api/prompt-optionen` lösen `claude auth status` aus (60 s zwischengespeichert).

### Übergabe (Claude, 08.11.2026)

- Regeldatei: Sols Vorschlag übernommen, Bild- und Videoregeln nach STUDIO.md §7 geschärft (Aussehen jeder Person,
  Gegenstände genau, Farben mit Namen, Schrift wörtlich mit Anzahl bzw. „ohne Schrift“, Layouts nummerieren, Ausschlüsse
  im Haupttext, Freifläche, Gleichbleibendes beim Bearbeiten; Video: Gesprochenes als `<d>`-Block mit 20–24 Wörtern je
  8 s, Hintergrundvideos ruhig, Szenen trennen). Abgelegt unter
  `C:\Workstation\Skills\aktiv\prompt-schaerfen\references\werkstatt-profile.json` (neu) und als Testkopie
  `werkstatt\tests\werkstatt-profile.json`.
- Befund bei der Übergabe: sieben Tests und das Harness lasen die Regeldatei aus `_uebergabe/`, das nicht in den Commit
  gehört – auf dem Branch wäre die Suite rot gewesen. Verweise auf die Testkopie umgestellt, `_uebergabe/` in
  `.gitignore`, Test `EchteRegeldatei` prüft die Skill-Datei, wenn sie vorliegt. Gegenprobe mit weggeschobenem
  `_uebergabe/`: 470 OK.
- README.md: Abschnitt „Prompts“ um Composer, Abo, Senden, Material/Kontext, Entdecken, Bibliothek ergänzt; Harness
  unter „Tests“. Spec: Freigabe und „Baustand“. PLAN.md bleibt im Branch unberührt (im Hauptordner liegen 28 fremde
  uncommittete PLAN-Zeilen); Entwurf des Eintrags in `_uebergabe/PLAN-eintrag-beim-zusammenfuehren.md`.
- Endstand: **Ran 471 tests, OK (skipped=1)**, `git diff --check` sauber.

## Lehre aus diesem Lauf

- Zeit gekostet: Testverweise auf den nicht zu committenden Übergabeordner (erst bei der Übergabe entdeckt) und
  Backslash-Pfade in einem Python-Heredoc (Steuerzeichen in der Spec, dreimal nachgebessert).
- Geändert: Skill `codex-build` („Handover folder“: Tests nur auf committete Dateien, vor dem Human Gate einmal ohne
  Übergabeordner testen). Für Pfade in Skripten Dateien mit Write anlegen und Raw-Strings verwenden (deckt sich mit
  der bestehenden Regel zu langen Bash-Befehlen, keine neue Regel nötig).
