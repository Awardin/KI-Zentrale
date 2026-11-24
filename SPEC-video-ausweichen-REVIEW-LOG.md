# Bauprotokoll: Video weicht auf den freien Prozess aus

Spec: [SPEC-video-ausweichen.md](SPEC-video-ausweichen.md) (eingefroren 24.11.2026, ohne vorheriges Gegenlesen – kleiner,
klar umrissener Umbau; Auftrag Sascha „Ja, bauen“).

## Act 3 — Build

- Builder: Codex `gpt-6.2-sol`, Stufe `xhigh`, Sandkasten `workspace-write`
- Worktree: `C:\Worktrees\ki-zentrale-video-ausweichen`, Zweig `bau/video-ausweichen` (von `3b7550d`)
- Sitzung: `01a20dc1-2293-7b43-8e59-9bfab1feea6b`
- Start: 24.11.2026, 14:31
- Höchstens 2 Korrekturrunden
- Nachweis im Sandkasten: `python -m unittest werkstatt.tests.test_parallel -v`; volle Suiten außerhalb durch Claude

Der Hauptordner hat offene Änderungen aus anderen Arbeiten (CFG, Sprechtext, 3D-Figur). Deshalb baut Codex im sauberen
Worktree und darf nur `werkstatt/studio.py` (Abschnitt „Ablauf“) und `werkstatt/tests/test_parallel.py` anfassen; der
Diff wird danach als Patch auf den Hauptordner gelegt.

### Runde 1 — Codex-Bau

Bericht (gekürzt): Teil A und B umgesetzt, keine Abweichung von der Spec. Geändert `werkstatt/studio.py` (Ausnahme
`Zurueck`, `_wer_zuerst` mit `platzstand`, Rückgabe in `_platz`, `_schleife` überspringt beim Zurückgeben das
Abschließen, `_lage_auffrischen` ersetzt den Stand einer inzwischen erfolgten Rückgabe nicht) und
`werkstatt/tests/test_parallel.py` (13 neue Tests in `VideoAusweichen`, eine erlaubte Anpassung). Im Sandkasten
scheiterten neun vorhandene Tests mit `tempfile` an `PermissionError [WinError 5]`; der Builder ließ sie mit geerbten
Ordnerrechten nur im Testprozess erneut laufen (keine Dateiänderung, keine Reste im Worktree).

### Urteil Claude

- Diff ganz gelesen: Verhalten wie in der Spec, nur die zwei erlaubten Dateien, `git diff --check` sauber. Die
  Sicherung in `_lage_auffrischen` war nicht verlangt, ist aber klein und schadet nicht (zwei gleichzeitige Abfragen:
  das zweite Ergebnis fällt weg). `begonnen`/`prozess` = `None` liest im Studio nur `_wer_zuerst` per `get`.
- Eigene Nacharbeit (keine Korrekturrunde): Docstring von `_wer_zuerst` um die gemessenen Gründe ergänzt, die beim
  Umschreiben weggefallen waren (16.10.2026 Bild vor Video; 24.11.2026 Anlass).
- Tests außerhalb des Sandkastens: Worktree Werkstatt 524 (1 Fehler: Port 3897 von einem anderen Programm belegt,
  1 übersprungen), Zentrale 205 grün; Hauptordner mit Patch Werkstatt 528 (derselbe Fehler, 1 übersprungen),
  Zentrale 205 grün, `test_parallel` 35 grün.
- Patch mit `git apply` auf den Hauptordner gelegt (passte ohne Konflikt neben den offenen CFG-Änderungen).
- Am echten System (Werkstatt neu gestartet 14:42, Suprim mit 2,6 GiB gefüllt, 17,9 GiB frei): 14:43:41 Video 1 auf
  der FE; 14:43:44 Video 2 bei Prozess 2, 14:44:35 „zurück in die Schlange“, danach auf der FE; Gegenprobe ohne
  Füllung 14:45:43 wie bisher auf der Suprim. Testvideos: `Werkstatt-Abnahme\Video_00024_.mp4`, `Video_00025_.mp4`,
  `Video-2_00004_.mp4`.

### Zahlen

Ein Lauf, keine Korrekturrunde, Laufzeit 7,7 Minuten (14:31–14:39). Token: 1,81 Mio. Eingabe (davon 1,70 Mio. aus dem
Zwischenspeicher), 19 Tsd. Ausgabe.

## Lehre aus diesem Lauf

- Zeit kostete nur das Warten auf den Bau; der Weg „sauberer Worktree, zwei erlaubte Dateien, Patch auf den
  Hauptordner“ funktioniert auch bei offenem Arbeitsstand, solange die fremden Änderungen andere Stellen betreffen.
- Änderung an Skill oder Vorlage: keine.
