# KI-Zentrale: Plan, Entscheidungen und Abnahme

Stand 24.09.2026. Diese Datei ersetzt als aktive Fassung die Codex-Übergabe
`Projekte\Lokale-Wissensextraktion\auswertungen\2026-09-22-modellzentrale-bauuebergabe.md`
(deren Umfang, Sicherheitsregeln und Abnahmekriterien wurden übernommen).

## Entscheidungen (Sascha, 23.09.2026)

1. **Zwei getrennte Apps statt einer großen:**
   - *Modellzentrale* für den Betrieb: schlank, muss immer funktionieren,
     auch während ein Video rendert.
   - *Werkstatt* für die Arbeit mit Reitern: Bild & Video, Transkription, Messungen.
   - Die Zentrale *sieht* alles, was die Karten belegt, steuert die Werkstatt aber nicht.
     Die Werkstatt fragt vor großen Aufträgen bei der Zentrale nach.
2. **Ort:** `C:\Workstation\Werkzeuge\KI-Zentrale` (wie Wissenssuche und Watch).
3. **Reihenfolge:** erst Modellzentrale, dann Werkstatt mit Transkription, danach Messungen.
4. **Technik** (Wahl Sascha überlassen): lokale Weboberfläche im Edge-App-Fenster,
   Dienst in Python nur mit Standardbibliothek, keine Installation.
5. **Wechseln:** Passt ein Modell nicht, schlägt die Zentrale vor, was weichen muss,
   und handelt erst nach Bestätigung.
6. **Alte Apps:**
   - Die Benchmark-App *GPU-Lab* wird nur als Idee übernommen und in der Werkstatt neu gebaut
     (falsche Pfade, RTX 5070 Ti fest eingetragen, letzter Eintrag 19.09.).
   - Die *Whisper Workbench* wird nicht wiederbelebt: Umgebung fehlt, für die RTX 5090 gebaut,
     Large-v3-turbo. Ihre guten Ideen wandern in den Transkriptionsreiter auf Basis von `watch`.
7. **2Wild** bleibt unverändert, ein fremdes GitHub-Projekt mit lokalen Änderungen. Keine
   Transkription oder Messung in 2Wild einbauen. Ergänzt 23.09.2026 abends: Die Werkstatt bekommt ein
   **eigenes Studio** (Stufe 3) und löst 2Wild danach ab; 2Wild selbst wird dabei nicht verändert.

## Stufe 1: Modellzentrale (fertig, abgenommen)

Abnahme am 23.09.2026, 13:17–13:25 Uhr, am echten System:

| # | Kriterium (aus der Codex-Übergabe) | Ergebnis |
|---|---|---|
| 1 | Start ohne Installation | Python-Standardbibliothek; Starter `Modellzentrale starten` |
| 2 | NInfer aus gestopptem Zustand | Bereit nach 5 s; `/v1/models` korrekt, Testantwort korrekt, 22.286 MiB auf der 3090, nur 127.0.0.1 |
| 3 | NInfer gezielt stoppen | Port 8080 danach frei |
| 4 | Ornith Q5 laden | 12 s; `ollama ps` zeigt genau `ornith-q5-128k:latest`, Kontext 131.072 |
| 5 | Q5 entladen, Q4 laden und entladen | Wechsel mit Bestätigung, Q4 in 9 s, danach `ollama ps` leer, Speicher frei |
| 6 | Konflikthinweis | Dialog mit Vorher/Nachher-Leiste; veralteter Plan wird mit 409 abgelehnt |
| 7 | DSH öffnen/vorholen | gestartet; zweiter Klick holt das Fenster in den Vordergrund |
| 8 | ComfyUI startet einmal und stoppt sicher | ComfyUI + 2Wild bereit nach 19 s; beenden, Ports 8188/3998 frei |
| 9 | 2Wild nur bei vollständigem Bestand | alle 10 Pflichtdateien geprüft; MiniMax-H3 ist inzwischen vollständig |
| 10 | GPU freigeben nur Verwaltetes | NInfer beendet, ComfyUI-Modelle entladen, Ollama-Dienst und DSH unberührt |
| 11 | Anzeige = Ports = `ollama ps` = nvidia-smi | nach jeder Aktion abgeglichen; Anzeige misst nach jeder Aktion sofort neu |
| 12 | nur lokal | alle Dienste an 127.0.0.1; fremder Host 403, Aufruf ohne Kennung 403, fremde Webseite 403 |

Zusätzlich geprüft:
- Echter Qwen-Bildauftrag (1024², 40 Schritte, 55 s). Während des Auftrags lehnt die
  Zentrale das Entladen und das Beenden ohne Bestätigung ab.
- Port 8080 durch fremdes Programm belegt: Anzeige „Port belegt“, NInfer startet nicht.
- Dunkle Darstellung und 390 px Breite.

Behobene Befunde während der Abnahme:
- Ollama 0.34 lädt Modelle in `lib\ollama\llama-server.exe`; die Belegung wird jetzt Ollama zugeordnet.
- Speicherfreigabe nach dem Entladen kommt verzögert; die Zentrale wartet darauf.
- DSH zeigt sein Fenster erst nach einigen Sekunden; die Zentrale wartet bis zu 15 s.
- Geerbte Electron-Variablen werden gestarteten Programmen nicht weitergegeben.

Abweichungen von der Codex-Übergabe:
- Ollama läuft aus der Desktop-App `%LOCALAPPDATA%\Programs\Ollama`, nicht aus
  `C:\Workstation\Tools\Ollama`; die Zentrale startet bei Bedarf die Ollama-App.
- Der Speicherbedarf ist jetzt gemessen statt geschätzt:
  - Q5: 16,2 + 12,2 GiB.
  - Q4 lädt mit Ollamas Standardkontext 32K.

## Strata-Eintrag (05.10.2026)

Umgesetzt nach der eingefrorenen `SPEC-strata.md`: optionaler Eintrag „Qwen3.8 Flash-Next · Strata“
(IQ3_XXS, 128K, Port 8095), Start mit Prüfung auf 42 GiB freien Arbeitsspeicher,
Bereitschaft und Kontext aus `/health`, gemessene Belegung auf beiden Karten,
gezieltes Beenden (Engine vor Python), Freigabe- und Platz-Pläne sowie „Chat öffnen“.
Bestehende Einträge und die Werkstatt bleiben unverändert.

Prüfung durch Codex: 32 Tests der Modellzentrale und 142 bestehende Werkstatt-Tests grün;
Strata-Systemzugriffe in den Tests gestellt. `config.json` gültig, `node --check zentrale\web\app.js` erfolgreich.
Beim Bau wurden keine Modelle oder Dienste gestartet, beendet oder neu gestartet.
Review-Runde 1: vollständig quotierte Strata-Kommandozeilen erkennen, RAM nur vor einem tatsächlichen Start prüfen und fremde Prozessnamen ohne Detailabfrage überspringen; Regressionstests ergänzt.
Danach 35 Zentrale- und 142 Werkstatt-Tests grün (von Claude selbst ausgeführt).

**Live-Abnahme 05.10.2026 (Claude), bestanden:** Zentrale neu gestartet; „Starten“ → bereit nach 24 s
(„Kontext 131.072 · Port 8095“); Belegung lila auf beiden Karten (22,6 GiB RTX 3090, 18,7 GiB RTX 3080; Bildschirm
hängt seit 05.10. an der CPU-Grafik); „Chat öffnen“ verlinkt `http://127.0.0.1:8095/`; Testfrage über die API
beantwortet; „GPU freigeben“ bot „… Strata beenden (41,4 GiB)“ an und beendete Strata in 4 s; erneuter Start
(24 s) und „Beenden“ beendeten Engine und beide Python-Prozesse in 2 s, Karten danach 0 MiB, Zustand „Aus“.
Bauprotokoll: `SPEC-strata-LOG.md`.

## Strata-Bilder und Beenden für Programme (05.10.2026)

Umgesetzt nach der eingefrorenen `SPEC-strata-bilder-dsh.md`: `strata-vision.exe` wird über den exakten
Programmpfad erkannt (ohne `vision_exe` im Engine-Ordner), seine Belegung Strata zugeordnet und nach der Engine,
vor den Python-Prozessen beendet. Strata-Untertitel enthält „Bilder“, Bedarf 23.500 MiB + 19.400 MiB.
Programme erhalten im Zustand „läuft“ zusätzlich „Beenden“ mit Bestätigungsdialog. Alle Top-Level-Fenster
der über den exakten Programmpfad ermittelten PIDs bekommen WM_CLOSE, auch unsichtbare. Nach höchstens 8 s
werden verbliebene Prozesse mit frisch geprüftem Pfad hart beendet; Abschlussprüfung höchstens 5 s, jede PID
protokolliert. Der vorhandene Serverablauf setzt bereits „stoppt“ und „wird beendet“ für Programme.

Systemzugriffe der neuen Tests sind gestellt. Keine Modelle, Dienste oder Programme beim Bau gestartet,
beendet oder neu gestartet; Werkstatt und Dateien unter `C:\LLM` unverändert. 
**Live-Abnahme 05.10.2026 (Claude), bestanden:** 45 + 142 Tests selbst ausgeführt; Zentrale neu gestartet; laufendes Strata mit Bildern komplett als Strata gezählt (22,9 GiB RTX 3090, 18,9 GiB RTX 3080, kein Rest unter „Windows & Programme“); DSH über „Öffnen“ gestartet, „Beenden“ zeigte den Dialog, 7 Prozesse bekamen WM_CLOSE, 3 hingen im Infobereich und wurden nach 8 s gezielt beendet, nach 9 s keiner mehr; Strata „Beenden“ beendete Engine, `strata-vision.exe` und beide Pythons in 4 s, Karten 0 MiB.
Nachweis durch Codex: 45 Tests der Modellzentrale (`unittest discover -s zentrale\tests -v`) und 142 Tests
der Werkstatt (`unittest discover -s werkstatt\tests`) grün, mit dem vorgegebenen Python 3.12.14.
`config.json` mit `json.load` geprüft; `node --check zentrale\web\app.js` erfolgreich. Keine funktionalen Abweichungen.

## Stufe 2: Werkstatt

Eigener Dienst (Port 3895) und eigenes Fenster, Starter `Werkstatt starten` in `C:\Workstation`;
nutzt `gemeinsam\`.

### Entscheidungen (Sascha, 23.09.2026)

1. **Hineinziehen ohne Kopie:** Das Browserfenster verrät beim Ablegen keinen Speicherort.
   Die Werkstatt liest die Markierung im Explorer und gleicht Name, Größe und Änderungszeit ab.
   Vom Desktop oder bei Mehrdeutigkeit: „Dateien wählen …“ (Windows-Dialog). Keine Kopie.
2. **watch.py bleibt unverändert** (gemeinsamer Skill). Fortschritt kommt aus `run.json`,
   der wachsenden Download-Datei und der Bildzahl.
3. **Abgebrochene Läufe** bleiben unberührt; ein neuer Versuch schreibt in `transkript-<Zeit>\`.
4. **Zusammenfassung in der Werkstatt** (ersetzt „Auswertungsmodi 1–4 bleiben bei den Agenten“):
   - Auswerter zum Anhaken, mehrere gleichzeitig zum Vergleichen: Codex, Claude, DeepSeek
     (direkt mit Saschas Schlüssel aus DSH Desktop; bis 23.09.2026 abends über OpenRouter), lokal als
     weitere Möglichkeit; OpenRouter für kostenlose Modelle.
   - Modelle je Anbieter (etwa Codex Astra/Sol/Luna) werden einmal in den Einstellungen als
     Auswerter angelegt; das Auftragsformular zeigt nur Kästchen.
   - Anweisungen sind in der Werkstatt sichtbar, bearbeitbar und ebenfalls mehrfach wählbar
     (Modell × Anweisung). Die aktive Fassung steht in der Promptsammlung.
   - Die Werkstatt macht 1, 2 und 4 als Entwürfe. Modus 3 (Bilder, OCR) und die Übernahme
     ins Wissen bleiben bei den Agenten.

### Stufe 2a: Transkription (fertig, abgenommen)

Abnahme am 23.09.2026, 14:28–14:47 Uhr, am echten System:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Datei hinzufügen, Modus 0 | 7-min-Datei: Prüfsumme, Verweis in `quelle\source.json` (keine Kopie), 420 s Ton in 20 s auf beiden Karten |
| 2 | YouTube, Modus 0b | 10,5-min-Video: Download 22 s (81 MB), Transkript 23 s, 228 Originalbilder; Sprache aus der YouTube-Angabe |
| 3 | Erledigtes überspringen | YouTube sofort beim Hinzufügen (Video-ID); lokale Datei über Prüfsumme; reine Tondatei in 0b mit Hinweis „keine Bilder“ |
| 4 | Hineinziehen | im Explorer markierte Datei per Name/Größe/Zeit gefunden; nicht markierte Datei als „nicht zugeordnet“ gemeldet |
| 5 | Dateien wählen | Windows-Dialog erscheint im Vordergrund; Abbrechen fügt nichts hinzu |
| 6 | Abbrechen | alle vier watch-Prozesse (Starter, Hauptprozess, zwei Worker) beendet, Speicher frei, Anmeldung gelöst |
| 7 | Wiederholen | neuer Lauf in `transkript-2026-09-23-143901\`, abgebrochener Teil unberührt |
| 8 | Warten auf Platz | Test-Anmeldung belegt fast alles: Auftrag wartet mit Begründung, startet nach Freigabe sofort |
| 9 | Ornith Q5 geladen | 5,6 + 7,1 GiB frei: Werkstatt verteilt auf beide Karten (je 2,3 GiB gemessen); Zentrale-Plan für NInfer nennt die Transkription und schiebt nichts dazwischen |
| 10 | Anzeige in der Zentrale | Worker erscheinen als „Transkription (watch)“ auf der richtigen Karte, Rest der Anmeldung als „Transkription (angemeldet)“ |
| 11 | nur lokal | beide Dienste an 127.0.0.1; fremder Host, fehlende oder fremde Kennung, fremde Webseite: 403 |
| 12 | Zentrale-Kriterien 6, 11, 12 erneut | veralteter Plan 409; Anzeige nach jeder Aktion frisch; Sicherheitsprüfungen wie oben |

Gemessen: Whisper Medium float16 braucht 2,4–2,5 GiB je Worker (Werkstatt plant 2,8 GiB plus
768 MiB Reserve der Zentrale). 10,7 min Ton: beide Karten 19 s, zwei Worker auf einer Karte 31 s.

Nachgeprüft 23.09.2026, 15:45–15:55 Uhr (mit Test-Arbeitsordner, danach zurückgestellt):
- Warteschlange: Anhalten (nichts beginnt), Verschieben, Modus 0 → 0b, Entfernen, Fortsetzen,
  Wiederholen, Erledigte entfernen.
- Dienst mitten in der Transkription neu gestartet: alle sieben Prozesse des Auftrags beendet (keine
  Waisen), Auftrag „abgebrochen“, Anmeldung in der Zentrale nach 60 s abgelaufen.
- Ganzen Ordner abgelegt: Medien samt Unterordner in natürlicher Reihenfolge, andere Dateien ignoriert.
- Lange Videos: mit 240-s-Fenstern und einem Bild je Sekunde wurden Fenster über 240 Bildern
  halbiert, 815 Bilder, Abdeckung lückenlos.
- Starter ohne Fenster meldet Fehler als Text statt mit einem Meldungsfenster, das Skripte blockiert.

Umsetzung:
- Neue Schnittstelle der Zentrale: `POST /api/platz` (frischer Stand je Karte, mit Bedarf
  prüfen und anmelden in einem Schritt, sonst 409 mit Begründung), `/api/platz/halten`,
  `/api/platz/freigeben`. Anmeldungen verfallen nach 60 s ohne Lebenszeichen und zählen in
  den eigenen Plänen der Zentrale mit.
- Kartenwahl: zwei Karten nur, wenn jede beide Worker tragen könnte (watch legt Abschnitte
  abwechselnd auf die Karten, kurzzeitig auch beide auf eine). Stark ausgelastete Karten
  nachrangig. Quellen bis 6¼ min: ein Worker.
- watch läuft in einer eigenen Windows-Prozessgruppe: Abbrechen beendet genau diese Gruppe;
  endet der Dienst, endet sie mit.
- Lokale Dateien: `Arbeitsmaterial\watch\<Dateiname> [datei-<Prüfsumme>]`, Benennung aus watch.
- Lange Videos: Bilder in 30-min-Fenstern; mehr als 240 Bilder in einem Fenster → Fenster halbieren.

### Stufe 2b: Zusammenfassung (fertig, abgenommen; Claude angemeldet, DeepSeek direkt)

Abnahme am 23.09.2026, 14:55–15:05 Uhr, am echten System:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Auswerter und Anweisungen als Kästchen, mehrere zugleich | 2 × 1 und 1 × 2 gestartet; jede Kombination eine eigene Fassung |
| 2 | Codex (Astra/Sol/Luna …) | Modellliste und Denkstufen kommen aus der Codex-App; Sol mittel 16 s, Luna niedrig 57 s für 10,5 min Video; Anmeldung der App genutzt |
| 3 | lokal | Ornith Q5: Kurzfassung 26 s, gezielte Frage 8 s, ausführliche Analyse 34 s; `keep_alive -1`, Modell bleibt geladen |
| 4 | nie gleichzeitig mit Whisper | Transkription wartete „bis die lokale Zusammenfassung fertig ist“ und lief danach; zweite lokale Fassung wartete auf die erste |
| 5 | Anweisungen sehen, ändern, neu, löschen | Abschnitt „Werkstatt: Anweisungen für Zusammenfassungen“ in der Promptsammlung; veralteter Stand 409, `~~~` abgewiesen; nach Anlegen+Ändern+Löschen Datei Byte für Byte wie vorher |
| 6 | Vergleich | Fassungen nebeneinander oder untereinander, mit Dauer, Token, ggf. Kosten; Datei öffnen, Kopieren |
| 7 | Ablage | `<Videoordner>\zusammenfassungen\<Anweisung> – <Auswerter>.md` mit Kopf (Quelle, Modell, Stufe, Anweisungsstand, Dauer, „Entwurf, nicht geprüft“) |
| 8 | Claude | eingebaut; Kommandozeile ist außerhalb der App **nicht angemeldet** – Werkstatt zeigt den Anmeldebefehl |
| 9 | OpenRouter | über den API-Schlüssel angeschlossen; kostenlose Modelle laufen (siehe Nachtrag), DeepSeek braucht **Guthaben** (402) – Werkstatt zeigt den Grund |

Befunde:
- Codex liest seine globale `AGENTS.md` trotz `--ignore-user-config` mit (abschaltbar nur mit eigenem
  Codex-Ordner ohne Anmeldung). Deshalb bekommen alle Auswerter denselben „Rahmen“ (eigenständige
  Textaufgabe, keine Dateien/Werkzeuge/Gedächtnis). Codex läuft nur mit Leserechten.
- Claude wird ohne Werkzeuge, ohne Einstellungen und ohne MCP gestartet (`--bare` scheidet aus, es
  verlangt einen API-Schlüssel statt der Anmeldung).
- Cloud-Fassungen laufen zu zweit parallel; lokale nur einzeln und nie neben Whisper.
- Zu lange Transkripte werden je Auswerter vorab abgelehnt (Kontext aus der Modellliste, gut 3 Zeichen je Token).

Nachtrag 23.09.2026, 15:05–15:13 Uhr – **OpenRouter über den API-Schlüssel angeschlossen:**
- Der Schlüssel ist gültig, das Konto hat aber kein Guthaben (0 $). Bezahlte Modelle (DeepSeek)
  bleiben deshalb gesperrt, mit Begründung; Guthaben kauft nur Sascha.
- Kostenlose Modelle (`…:free`, `openrouter/free`) sind sofort nutzbar. Die Werkstatt listet
  21 kostenlose Textmodelle und DeepSeek, kostenlose zuerst.
- Echte Fassung: Nemotron 3 Super (kostenlos) in 86 s, 12.601 Token, 0 $.
- Qwen3.8 27B (kostenlos) war beim Anbieter dauerhaft ausgelastet (429). Die Werkstatt versucht
  nach 20, 45 und 90 s erneut und meldet dann verständlich; „Wiederholen“ später.
- Beim Gratis-Router wird das tatsächlich antwortende Modell im Dateikopf festgehalten.

Nachtrag 23.09.2026, 19:05 Uhr – **Claude-Anmeldung kam nie an:**
- Die Claude-App ist ein Store-Paket. Ihr `%APPDATA%\Claude` liegt in Wirklichkeit unter
  `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude` und erscheint unter `%APPDATA%`
  nur für Programme, die aus der App gestartet wurden. Der alte Befehl lief deshalb in normaler PowerShell
  ins Leere, und eine selbst gestartete Werkstatt hätte Claude gar nicht gefunden.
- Die Anmeldung in der Claude-App gilt nicht für die Kommandozeile: `~\.claude\.credentials.json`
  enthielt nur Plugin-Anmeldungen, `auth status` meldete „nicht angemeldet“.
- Behoben: Die Werkstatt sucht `claude.exe` zuerst im Paketordner und zeigt diesen Pfad an.
  Claude (Anmeldeprüfung und Fassungen) startet ohne `CLAUDE*`/`ANTHROPIC*`-Variablen einer App-Sitzung.
- Sascha hat sich angemeldet (normale PowerShell,
  `& "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\<Version>\claude.exe" auth login`):
  `auth status` = angemeldet, Abo (Max). Echte Fassung Sonnet 5: 17 s.
- Im Abo meldet Claude nur einen rechnerischen API-Preis; die Werkstatt zeigt dann keine Kosten.
  Token zählen jetzt auch die zwischengespeicherte Eingabe mit.

Nachtrag 23.09.2026, 19:10 Uhr – **DeepSeek direkt statt über OpenRouter** (Entscheidung Sascha):
- Sascha hat einen eigenen DeepSeek-Schlüssel, er liegt in DSH Desktop (`~\.dsh\.credentials.yaml`,
  Eintrag `DEEPSEEK_API_KEY`). Die Werkstatt liest ihn dort nur, keine Kopie. Geprüft: gültig, 19,36 $ Guthaben.
- Neuer Anbieter „DeepSeek“: Modelle `deepseek-flash` und `deepseek-v4-pro` (je 1 Mio. Token Kontext),
  Denkstufe ohne Nachdenken (`thinking: disabled`), niedrig, hoch (Standard), maximal (`reasoning_effort`).
  Guthabenprüfung über `/user/balance`, bei Überlastung (429/503) drei neue Versuche wie bei OpenRouter.
- Kosten rechnet die Werkstatt aus der Preisliste in `werkstatt\config.json` (Stand 23.09.2026;
  Hauptzeit Mo–Fr 01–04 und 06–10 Uhr UTC voller Preis, sonst halber Preis).
- OpenRouter nur noch für kostenlose Modelle (`praefixe` leer); der Auswerter „OpenRouter · DeepSeek“
  ist ersetzt durch „DeepSeek · Flash“ und „DeepSeek · V4 Pro“. OpenRouter-Guthaben ist nicht mehr nötig.
- Echte Fassungen (Kurzzusammenfassung, 7,5-min-Transkript, abends = halber Preis):
  Flash 48 s, 15.009 Token, 0,0078 $; V4 Pro 105 s, 10.567 Token, 0,0172 $.
- Tests: `werkstatt\tests\test_deepseek.py` (Kosten, Schlüssel, Katalog, Denkstufen, Wiederholung).

### Stufe 2c: Bild & Video und Messungen (fertig, abgenommen)

Abnahme am 23.09.2026, 15:15–15:55 Uhr, am echten System:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | 2Wild einbetten | 2Wild setzt keine Sperre gegen Einbetten: läuft vollständig im Reiter (Rahmen), dazu Knöpfe „Studio im eigenen Fenster“, „ComfyUI öffnen“ |
| 2 | Zustand echt | Werkstatt fragt Ports 3998/8188 und ComfyUI-Warteschlange ab; aus → Hinweis „in der Modellzentrale starten“; Starten und Beenden bleiben in der Zentrale (mit Platzprüfung) |
| 3 | Transkriptionstempo automatisch | aus 205 `run.json`: Medium 2 Karten 30,8×, eine Karte 2 Worker 21,4×, ein Worker 20,0× Echtzeit (Median); Läufe mit < 40 Wörtern/min (Musik, Stille) als „wenig Sprache“ gekennzeichnet, nicht im Median |
| 4 | Bild/Video aus 2Wild-Historie | `data\jobs.json` nur lesend, ohne Prompts: Qwen-Bild ~55 s, MiniMax-Video 20 Schritte ~10 min; ComfyUI-Verlauf, solange es läuft |
| 5 | Zusammenfassungen | Dauer, Token/s und Kosten je Auswerter (Kosten nur, wo der Anbieter sie meldet) |
| 6 | LLM-Messlauf per Knopf | fester Text (`werkstatt\messtext.txt`, 1.184 Token), Aufwärmen, eindeutige Kennung gegen Zwischenspeicher, 256 Token, Temperatur 0, Sensor-Spitzen je Karte; nie neben Whisper |
| 7 | GPU-Lab historisch | 141 Läufe einmalig übernommen (`werkstatt\daten\messungen-historisch.json`), 20 Vergleichsgruppen; zweite Übernahme wird abgewiesen |
| 8 | GPU-Lab stillgelegt | lief nicht, keine Verknüpfung; `Dashboard-starten.cmd` → `.stillgelegt`, Notiz `STILLGELEGT.md`; Datenbank unverändert |

Messwerte LLM-Messlauf (23.09.2026, Mittel aus 2–3 Läufen):

| Modell | Laufzeit | Prefill tok/s | Decode tok/s | Erste Antwort |
|---|---|---|---|---|
| Ornith 1.5 Q4 (beide Karten) | Ollama 0.34, `num_batch 256` | 1.530–2.700 | 154 | 0,45–0,8 s |
| Ornith 1.5 Q5 (beide Karten) | Ollama 0.34, `num_batch 256` | 1.620–2.610 | 147 | 0,46–0,75 s |
| Qwen3.8 27B (RTX 3090) | NInfer MTP | 895–914 | 62–70 | 1,4 s |

**Befund Ollama (wichtig):** Mit Standard-Stapelgröße stürzt der Modellprozess von Ornith (Q4 und
Q5) bei Eingaben ab etwa 1.000 Token sporadisch bis regelmäßig ab („CUDA error: an illegal memory
access“ in llama.cpp `mmq.cu`, beide Karten, MoE). Gemessen: Standard 6/12 bzw. 3/6 Abstürze,
`num_batch 256` 0/12 bzw. 0/6. Deshalb:
- Die Zentrale lädt beide Ornith-Einträge mit `ollama_optionen: {num_batch: 256}` (`zentrale\config.json`).
- Die Werkstatt schickt dieselbe Option bei Zusammenfassungen und Messläufen mit; das Modell wird
  dabei nicht neu geladen (geprüft über `/api/ps`).
- Stürzt der Prozess trotzdem ab, versucht die Werkstatt es einmal erneut.
- Andere Programme, die Ornith ohne diese Option ansprechen, lassen Ollama mit Standardwerten neu
  laden und sind wieder absturzgefährdet. Dauerhaft ließe sich das nur im Modelfile festlegen
  (`PARAMETER num_batch 256`), das hieße, die Ollama-Modelle zu ändern – Entscheidung Sascha.

## Stufe 3: Eigenes Studio (3a Bilder, 3b Videos, 3d Stellen verbessern, 3e Charakterblatt, große Formate und Turbo, 3f Freistellen, Hochskalieren und Rezepte, 3g Details auffrischen fertig und abgenommen; 3h Handbuch STUDIO.md und Skill fertig; 3i Figuren und Logos als Vorschläge fertig; 3j Moodboards fertig; 3k durchsichtiger Hintergrund, Banner und schneller rechnen fertig; 3l INT8, schnelles Freistellen, Stelle per Wort, Pose und Ausformulieren fertig; 3m Videos weiterführen fertig; 3c 2Wild stillgelegt)

Übergabe 23.09.2026, 18:30 Uhr, Wunsch Sascha: Das Bild- und Videostudio soll besser werden.
Prompts sollen **zusammen mit den Bildern und Videos gespeichert** werden, damit man sie für ein
neues Bild oder Video wiederverwenden kann. Vorbild ist die frühere „Higgsfield-Ansicht“.

Befunde (nur gelesen, nichts geändert):
- **Frühere Lösung gefunden:** `C:\Users\sasch\OneDrive\Skills\Higgflield Replacement\Claude Skill ersetzt Higgsfield.md`
  (09.08.2026) mit der Bauanleitung für
  - *media-skill* (kie.ai, Cloud, Abrechnung pro Nutzung): Ablage `~/Medien/JJJJ-MM-TT-projekt/` plus
    `meta.json` je Ordner mit Zeit, Datei, Typ, Modell, **Prompt**, Credits und Euro;
  - *Mediengalerie* `galerie.py` → `galerie.html`: Raster mit Vorschau, unter jeder Kachel Prompt,
    Modell, Kosten, Projekt und Datum, Filter nach Typ und Modell, Suche, Gesamtkosten oben, neueste zuerst.
  - Die Skripte liegen noch in `C:\Users\sasch\OneDrive\Claude\claude-skills\media-skill\`
    (`scripts\galerie.py`, `scripts\kie.py`). Die damals erzeugten Medien (`~/Medien`) sind verloren
    (weder in OneDrive noch im Wiederherstellungsbestand). Der Skill ist nicht aktiv.
- **2Wild heute:** speichert Prompt, Einstellungen und Ergebnis je Auftrag in `data\jobs.json` und hat
  „Use this again“. Schnittstelle: `GET /api/jobs`, `/api/view`, `POST /api/generate`, `/api/chain`,
  `/api/cancel`, `/api/forget`. Lücken: Nach „forget“ ist der Prompt weg; neben den Dateien steht
  nichts; im Ausgabeordner `ComfyUI\output\gencenter` liegen 24 Dateien, in `jobs.json` nur 5 Aufträge.
  ComfyUI schreibt den Arbeitsablauf samt Prompt in die PNG-Metadaten.

Vorschlag Claude (noch **nicht** entschieden):
- In der Werkstatt bauen, 2Wild bleibt unverändert (Entscheidung 7 oben).
- Zu jedem fertigen Bild und Video schreibt die Werkstatt eine `<datei>.json` daneben: Prompt,
  Negativ-Prompt, Variationsnummer, Modell, Modus, Größe, Schritte, Dauer, Datum, Referenzbilder.
  Ältere PNGs: Prompt aus den ComfyUI-Metadaten lesen, soweit vorhanden.
- Bibliothek im Reiter Bild & Video: Raster, neueste zuerst, Filter Bild/Video/Modell, Suche in Prompts,
  Großansicht mit allen Einstellungen; „Prompt kopieren“, „Nochmal (neue Variation)“,
  „Mit Änderungen …“, „Zu Video“ – gestartet über die Schnittstelle von 2Wild, nie neben einer
  Transkription (gemeinsame GPU-Sperre).

Antworten Sascha (23.09.2026, abends):
- Frage 3: **eigene Projektordner.**
- Frage 2: Cloud (kie.ai) **eventuell später**. Schlüssel liegt unter `00_Secrets\agenturos\secrets\kie.env`
  (Stand 09.08.2026, Guthaben ungeprüft); auch `fal.env` ist vorhanden. Datenformat soll Cloud später aufnehmen können.
- Frage 1: nach der Übersicht unten entschieden: **C, eigenes Studio in der Werkstatt.**

Befunde zu Frage 1 (nur gelesen, 23.09.2026):
- 2Wild (tonyd2wild, MIT-Lizenz: Ändern und Übernehmen erlaubt) wurde am 20.09.2026 veröffentlicht:
  3 Commits an einem Tag, seitdem keine Änderung. Lokal nur flach geklont (1 Commit).
- Unsere lokalen Änderungen: `server.py` +136 Zeilen (Multi-GPU-Knoten, CFG 1.0), `index.html` +23
  (Qualität „Max“ als Standard, native Videogrößen). Jedes Update von 2Wild müsste dagegen abgeglichen werden.
- 2Wild ist eine Einzeldatei-App (Server 1.706 Zeilen, Oberfläche 996), englisch, mit Pillow für den
  Schritt Bild → Video. Es behält höchstens 200 Aufträge; „Remove“ löscht den Prompt. `jobs.json` enthält
  derzeit nur noch 2 Aufträge zu 24 Dateien.
- Ausgabe fest in `ComfyUI\output\gencenter\` (Präfix im Code von 2Wild). ComfyUI kann per
  `--output-directory` in einen anderen Ordner schreiben; die Zentrale startet ComfyUI (`zentrale\aktionen.py`).
- Alle 16 PNGs tragen den ComfyUI-Arbeitsablauf samt Prompt in den Metadaten, die Videos ebenso
  (MP4-Metadaten). Die Bibliothek kann damit auch alte Dateien ohne 2Wild-Auftrag erschließen.
- 2Wild kennt die GPU-Sperre der Werkstatt und die Platzprüfung der Zentrale nicht.

Optionen zu Frage 1:

| | A: Werkstatt-Bibliothek, 2Wild bleibt Generator | B: 2Wild umbauen | C: eigenes Studio in der Werkstatt |
|---|---|---|---|
| Bedienung | zwei Bereiche: Erstellen (2Wild, englisch) und Bibliothek (deutsch) | eine Oberfläche, englisch | eine Oberfläche, deutsch |
| Projekt vor dem Erstellen wählen | nein, danach einsortieren | ja | ja |
| „Mit Änderungen …“ | braucht ein eigenes Formular (= Teil von C) | ja | ja |
| Schutz vor Kollision mit Transkription | nur für Aufträge aus der Bibliothek | müsste in 2Wild eingebaut werden | vollständig |
| Aufwand | mittel | mittel, in fremdem Code | groß (vier Arten: Bild, Bild bearbeiten, Video aus Bild, Video mit Referenz) |
| Risiko | gering, 2Wild bleibt Rückfall | Entscheidung 7 fällt, Umbau einer fremden Einzeldatei | Nachbau muss 2Wilds abgestimmte Einstellungen treffen; 2Wild bleibt bis zur Abnahme |

Empfehlung Claude war: C, mit A als Zwischenschritt; B nicht. Entscheidung Sascha: C.

Aufteilung (jeder Teil wird einzeln gebaut, abgenommen und erst dann der nächste begonnen):
- **3a Bilder:** Studio-Bereich im Reiter Bild & Video: Projekt wählen oder anlegen, Prompt,
  Negativ-Prompt, Format, Qualität, Variationsnummer, optional Referenzbilder (Bild bearbeiten).
  Ergebnis direkt im Projektordner, daneben `<datei>.json` mit allen Einstellungen. Bibliothek: Raster,
  neueste zuerst, Filter (Bild/Video, Projekt, Modell), Suche in Prompts, Großansicht, „Prompt kopieren“,
  „Nochmal“ (gleiche Variationsnummer), „Variation“ (neue Nummer), „Mit Änderungen …“ (Formular vorbefüllt),
  „In Projekt verschieben“, „Ordner öffnen“. Die 24 vorhandenen Dateien werden erschlossen (Prompt aus
  den Metadaten).
- **3b Videos:** Text → Video, Bild → Video (Start-/Endbild), Video mit Referenz (Personen, Clips),
  „Zu Video“ aus einem Bild der Bibliothek.
- **3c 2Wild stilllegen** wie GPU-Lab, sobald 3a und 3b abgenommen sind: nicht mehr einbetten, nicht
  mehr starten; Dateien von 2Wild bleiben unverändert.
- **Später, nur auf Wunsch:** Cloud (kie.ai) in dieselbe Bibliothek, mit Kosten je Datei.

Technischer Ansatz:
- Die Werkstatt spricht ComfyUI direkt an (`/prompt`, `/history`, `/queue`, `/view`, `/upload/image`,
  `/interrupt`, installierte Modelle). Die Arbeitsabläufe entstehen nach dem Vorbild von 2Wild (MIT,
  Herkunft im Code vermerkt), samt unserer Anpassungen: Diffusionsmodell auf gpu:0, Text-Encoder und VAE
  auf gpu:1, CFG 1.0, „Max“ = 40 Schritte als Standard, native Videogrößen.
- Ablage `C:\Workstation\Arbeitsmaterial\Studio\<Projekt>\`: Die Zentrale startet ComfyUI mit
  `--output-directory` auf diesen Ordner, der Auftrag gibt `<Projekt>/…` als Präfix mit. Keine Kopien.
  Solange 2Wild noch läuft, landet dessen Ausgabe in `Studio\gencenter` (Projekt „Aus 2Wild“); die 24
  vorhandenen Dateien werden dorthin verschoben, damit 2Wilds Verweise gültig bleiben.
- Vor jedem Auftrag: ComfyUI muss laufen (Starten/Beenden bleibt in der Zentrale), Platz über
  `/api/platz`, und die gemeinsame GPU-Sperre: nie neben einer Transkription oder lokalen Zusammenfassung.
- Fortschritt zunächst aus Warteschlange und gemessener Dauer (Qwen-Bild ~55 s), ohne Websocket.
- Nur Standardbibliothek: Zuschneiden für „Zu Video“ im Browser oder mit ComfyUI-Knoten, nicht mit Pillow.

Abnahme 3a (Entwurf): echtes Bild in ein neues Projekt; Datei und `.json` im Projektordner, sonst nirgends;
„Nochmal“ ergibt dasselbe Bild, „Variation“ ein neues; „Mit Änderungen“ übernimmt alle Einstellungen;
Bild bearbeiten mit Referenz; Auftrag wartet während einer Transkription und startet danach; alte 24 Dateien
mit Prompt in der Bibliothek; Suche und Filter; 2Wild unverändert (`git status` wie vorher) und weiter nutzbar.

### Stufe 3a: Bilder und Bibliothek (fertig, abgenommen)

Go Sascha 23.09.2026, 19:25 Uhr; Ort `C:\Workstation\Arbeitsmaterial\Studio` (Vorschlag, ohne Einwand).
Abnahme am 23.09.2026, 19:55–20:12 Uhr, am echten System (Testprojekt „Werkstatt-Abnahme“, neutrale Motive):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Echtes Bild in ein neues Projekt | Projekt über „Neu …“ angelegt; Qwen 1328², 40 Schritte: 85 s (erstes Bild inkl. Laden), danach 74–77 s |
| 2 | Datei und `.json` nur im Projektordner | `Studio\Werkstatt-Abnahme\Bild_00001_.png` + `.json`; alter ComfyUI-Ausgabeordner leer; Einstellungen zusätzlich im PNG („werkstatt“) |
| 3 | „Nochmal“ = dasselbe Bild | neu gerechnet: Bilddaten Byte für Byte gleich wie das Original |
| 4 | „Variation“ = neues Bild | neue Nummer, neues Bild (75 s) |
| 5 | „Mit Änderungen“ | Art, Projekt, Prompt, Qualität, feste Nummer, Vorlagen übernommen; bei altem 2Wild-Bild 1024² als eigene Größe, Nummer 42 |
| 6 | Bild bearbeiten | Vorlage aus der Bibliothek („Als Vorlage“, per `[output]`, keine Kopie): 57 s; Vorlage von außerhalb hochgeladen: 32 s (20 Schritte) |
| 7 | Nie neben einer Transkription | Testton transkribiert, Bildauftrag zeigte „Wartet auf die Grafikkarten …“ und startete direkt danach |
| 8 | Alte Dateien mit Prompt | alle 26 (24 aus 2Wild, 2 ComfyUI-Tests) aus PNG-/MP4-Metadaten bzw. 2Wild-Aufträgen erschlossen, `.json` angelegt |
| 9 | Suche und Filter | Suche in Prompts, Projekt, Bild/Video; Mehrfachauswahl verschieben (hin und zurück), Papierkorb mit Rückfrage |
| 10 | 2Wild unverändert und nutzbar | `git status` wie vorher; 2Wilds Ansicht liefert die umgezogenen Dateien aus `Studio\gencenter` |
| 11 | nur lokal, nur Studio | Dateien nur aus dem Studio-Ordner (Pfadausbruch 404, `.json` 404); Videos mit Teilbereichen (206) |

Umsetzung:
- `werkstatt\studio.py` (Arbeitsabläufe nach 2Wild, MIT; Aufträge; Bibliothek; PNG-/MP4-Metadaten),
  `werkstatt\web\studio.js`, Reiter Bild & Video mit Umschalter „Studio | 2Wild (alt)“.
- Zentrale: ComfyUI startet mit `--output-directory C:\Workstation\Arbeitsmaterial\Studio`
  (`ausgabe_ordner` in `zentrale\config.json`); `/api/platz` liefert zusätzlich `verbraucher` je Karte,
  damit die Werkstatt ComfyUIs eigene Belegung anrechnen kann. Die 24 Dateien aus
  `ComfyUI\output\gencenter` und zwei ComfyUI-Testbilder wurden nach `Studio\` verschoben (keine Kopie).
- `gemeinsam\winapi.in_papierkorb` (SHFileOperation mit Rückholbarkeit).
- Messungen: Studio-Aufträge je Art, Größe und Schritten (Median der echten Rechenzeit).
- Tests: `werkstatt\tests\test_studio.py` (Namen, Pfade, Abläufe, Metadaten, Platz, Bibliothek, Aufträge).

Befunde:
- Grafikspeicher gemessen (nvidia-smi, alle 2 s): Qwen-Bild 1328², 40 Schritte belegt in ComfyUI
  ~14,7 GiB auf der 3090 und nur kurz ~1,3 GiB auf der 3080 (Text-Encoder). Studio plant deshalb 16 + 2 GiB
  (`studio.bedarf_mib`); die Zentrale plant für Bild & Video weiter 20 + 16 GiB (Videos).
- ComfyUI hält nach einem Bild ~13,6 GiB auf der 3090; „GPU freigeben“ in der Zentrale entlädt sie.
- ComfyUI nimmt einen identischen Auftrag aus seinem Zwischenspeicher (nur den jeweils letzten) und
  liefert die vorhandene Datei. Das Studio legt dann keine Kopie an und meldet „Genau dieses Bild gibt es
  schon“; ist die Datei inzwischen verschoben, speichert es sie neu (unbekannte Eingabe an SaveImage).
  Gefunden, weil der erste Test die Begleitdatei des Originals überschrieb (behoben, wiederhergestellt).
- Rechenzeit 1328², 40 Schritte: Median 76 s (4 Läufe); 12 Schritte 28 s. Die Zeitschätzung lernt daraus.

Entschieden (Sascha, 23.09.2026): Testprojekt `Studio\Werkstatt-Abnahme` (7 Bilder) bleibt.

### Stufe 3b: Videos (fertig, abgenommen)

Befunde (nur gelesen, 23.09.2026):
- 2Wild baut Videos mit MiniMax-H3 in zwei Abläufen: `fl2va` (aus Text, oder mit Start- und optional
  Endbild) und `ref2va` (bis 9 Referenzbilder, bis 3 Clips à 2–15 s, Ton des ersten Clips wählbar,
  „ref_image_size“ normal/max). Diffusionsmodell gpu:0, Encoder (Qwen3-VL-32B NVFP4) und beide VAEs gpu:1.
  Bis 8 Schritte hängt 2Wild die Turbo-LoRA an (fl2v: 8-Schritt, ref2v: 4-Schritt), darüber nie.
- Qualitäten: Schnell 4 · Schnell+ 6 · Schnell beste 8 (mit Turbo) · Mittel 12 · Gut 16 · Beste 20.
  Längen 124/192/243/311/362 Bilder = 5/8/10/13/15 s bei 24 fps (Raster 17n+5). Formate 960×544,
  544×960, 704×704 (schneller) und nativ 1344×768, 768×1344, 992×992.
- Ton: H3 spricht selbst; gesprochene Zeilen stehen im Prompt als `<d>[Deutsch] …</d>`. Tipps aus 2Wild:
  etwa 20–24 gesprochene Wörter je 8 s, „scharf“ verlangen (Wörter wie Körnung, Dunst, weich machen weich).
- Das Startbild zieht MiniMax ohne Rücksicht auf das Seitenverhältnis auf das Videoformat (nur das
  Endbild wird mittig beschnitten). 2Wild schneidet deshalb vorher mit Pillow zu. Das Studio erledigt
  das ohne Zusatzpaket mit ComfyUIs `ImageScale` (Mittenbeschnitt) im Ablauf.
- `LoadVideo` kennt wie `LoadImage` die Form `<pfad> [output]`: Bilder und Clips aus der Bibliothek
  gehen ohne Kopie; Dateien von außerhalb lädt ComfyUI in seinen Eingangsordner.
- Gemessen bisher nur ein 2Wild-Video: 960×544, 5 s, 8 Schritte (Turbo) 139 s; 20 Schritte laut
  2Wild-Verlauf ~10 min. Grafikspeicher für Videos noch nicht gemessen (Zentrale plant 20 + 16 GiB).

Plan:
1. Formular: Art in zwei Gruppen, Bild (neues Bild, bearbeiten) und Video (aus Text, aus Bild,
   mit Referenz). Für Video: Format, Länge, Qualität, Variationsnummer; „aus Bild“ mit Startbild und
   optionalem Endbild; „mit Referenz“ mit Bildern und Clips, „wie genau kopieren“ und „Ton des ersten Clips“.
   Vorlagen jeweils aus der Bibliothek oder „Aus Datei …“. Hinweise zu gesprochenen Zeilen und Schärfe.
2. Bibliothek: bei Bildern „Zu Video“ (Formular auf „Video aus Bild“, Format passend zum
   Seitenverhältnis, Hinweis bei Beschnitt); bei Videos „Nochmal“, „Variation“, „Mit Änderungen“.
   Videokacheln mit Länge; Großansicht mit Länge, Ton, Vorlagen.
3. Ablauf: `werkstatt\studio.py` bekommt die beiden Video-Abläufe nach 2Wild (Turbo-Regel, Geräte,
   `ImageScale` für Start-/Endbild), SaveVideo nach `<Projekt>/Video`. Begleitdaten wie bei Bildern,
   zusätzlich eingebettet im MP4 („werkstatt“). Alte 2Wild-Videos bekommen die genaue Art (Text/Bild/Referenz).
4. Grafikkarten: gleiche Sperre und Platzfrage wie bei Bildern; Bedarf für Videos beim ersten Lauf messen
   und eintragen. Zeitschätzung aus eigenen Läufen (Schritte × Pixel × Länge).
5. Messungen: Video-Aufträge mit Format, Länge und Schritten.

Standardwerte (änderbar, das Formular merkt sich die letzte Wahl): 5 s, Breit 16:9 (960×544), „Beste“ (20).

Go Sascha 23.09.2026, 20:15 Uhr. Abnahme am 23.09.2026, 20:37–21:02 Uhr, am echten System
(Testprojekt „Werkstatt-Abnahme“, neutrale Motive, 5-s-Videos 960×544):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Video aus Text | 8 Schritte (Turbo): 136 s, Schätzung 140 s; Begleitdatei + Einstellungen im MP4 („werkstatt“) |
| 2 | „Zu Video“ aus der Bibliothek | quadratisches Bild, Format automatisch 1:1; auf 16:9 umgestellt: Hinweis „wird mittig zugeschnitten“, erstes Videobild mittig beschnitten, nicht verzerrt; Vorlage per `[output]`, keine Kopie; 137 s |
| 3 | Video mit Referenzbild | Hund aus der Bibliothek, 4 Schritte (Turbo-LoRA ref2v): 84 s, Aussehen erhalten |
| 4 | „Nochmal“ = gleiches Video | Bild- und Tondaten (mdat) Byte für Byte gleich, auch nach Neustart von ComfyUI (ebenso ein Bild) |
| 5 | „Variation“ | neue Nummer, anderes Video (123 s) |
| 6 | „Mit Änderungen“ | Art, Format, Qualität, Länge, feste Nummer, Startbild samt Beschnitt-Hinweis übernommen |
| 7 | Abbrechen | ComfyUI stoppt am Ende des Rechenschritts (~5 s); Kachel „Wird abgebrochen …“, erst danach Sperre und Anmeldung frei |
| 8 | Wartet neben Transkription | „Wartet auf die Grafikkarten …“, startete direkt nach der Transkription |
| 9 | Grafikspeicher, Zeiten | ComfyUI ~22 GiB auf der 3090 beim Rechnen, ~6,2 GiB auf der 3080 beim Entschlüsseln; eingetragen 20 + 7 GiB |
| 10 | Alte 2Wild-Videos | 8 Videos mit genauer Art (6 aus Bild, 1 Referenz, 1 aus Text) aus den MP4-Metadaten |
| 11 | 2Wild unverändert | nicht angefasst; Abläufe identisch mit 2Wilds (per Metadaten verglichen, nur der Ablageort unterscheidet sich) |

Befunde:
- Beim ersten Abbrechen gab das Studio Sperre und Anmeldung frei, während ComfyUI noch bis zu einem
  Rechenschritt (~13,5 s bei „Beste“) weiterlief. Behoben: Das Studio wartet, bis ComfyUI steht.
- Ein altes 2Wild-Video (22.09.) mit identischem Ablauf und gleicher Nummer ergab im Studio eine andere
  Szene. Im Studio selbst ist dasselbe reproduzierbar, auch über einen Neustart von ComfyUI hinweg;
  das Original entstand offenbar unter anderen Bedingungen (Startoptionen von damals nicht mehr auffindbar).
- Die Kachel zeigte den Hinweis „gibt es schon“ (3a) nicht an (Reihenfolgefehler); behoben.
- `MiniMaxH3ImageToVideo` zieht das Startbild ohne Rücksicht auf das Seitenverhältnis; `ImageScale` mit
  `crop: center` davor löst das ohne Pillow.

### Stufe 3d: Stellen verbessern (fertig, abgenommen)

Auftrag Sascha 24.09.2026: „Plan ausarbeiten und alles implementieren; falls nötig auch Flux2 Klein laden.“
Anlass: Video „Qwen Image 2.1 … Pose Transfer and Fixing Hands“ (Ok Todd AI, 23.09.2026). Dort wird die Pose
per Prompt mit zwei Bildern übertragen und eine Hand mit Maske und „Inpaint Crop“ repariert (mit Flux2 Klein und
Zusatzknoten von Pixaroma).

Versuche am 24.09.2026 (ComfyUI 0.37, nur Kernknoten, Ergebnisse nur als Vorschau in ComfyUIs temp, nichts im Studio):
- Testbild Qwen 1024², 20 Schritte: Die Hand an der Hüfte war von selbst missraten (kein künstlicher Fehler).
- Ausschnitt 320² um die Hand, auf 1024² vergrößert, 20 Schritte, je 25–34 s:
  - A: Ausschnitt als Vorlage bearbeiten (leeres Latent): gute Hand.
  - B: wie A, aber das Latent des Ausschnitts behalten und nur in der Markierung neu rechnen (Latent-Maske): gute Hand.
  - C: Vorlage mit transparentem Loch: gute Hand, beim Entfernen aber magentafarbene Artefakte.
  - D: nur Text, ohne Vorlage: viel zu große Hand.
- Entfernen (hoher Baum am Horizont): B entfernt sauber. Die Loch-Varianten lassen den Baum stehen oder erzeugen Artefakte.
- Deutsche Prompts wirken wie englische.
- Stärke: 1,0 gestaltet neu, 0,8 lehnt sich an die Form an, 0,6 behält zu viel vom Fehler.
- Außerhalb der weichen Zone ist jedes Pixel gleich dem Original (gemessen; die 8-Bit-Rundreise in ComfyUI ist verlustfrei).
- **Entscheidung Claude:** Verfahren B mit Qwen-Image 2.1. Flux2 Klein ist dafür nicht nötig und wurde nicht geladen.

Umsetzung:
1. **Art „Verbessern“** in der Gruppe Bild: ein Bild (aus der Bibliothek „Stelle verbessern …“ oder „Aus Datei …“),
   Stelle markieren, beschreiben, was dort sein soll. Vorschläge „Hand reparieren“ und „Entfernen“ füllen den Text.
   „Wie viel darf sich ändern“: alles (1,0, Standard), viel (0,8), wenig (0,6). Anzahl 1–4 wie bei Bildern.
2. **Markieren** im eigenen Fenster: Pinsel, Radierer, Größe, Zoom mit dem Mausrad, Verschieben (rechte Maustaste
   oder Leertaste), Rückgängig/Wiederholen, Alles löschen, Umkehren. Die Maske kommt als Lauflängen-Kodierung zum Dienst.
3. **Ablauf** (`werkstatt\studio.py`):
   - Ausschnitt um die Markierung (3 × ihre lange Seite, mindestens 384 px, im Bild gehalten).
   - Arbeitsgröße 1024² bis 1328² in 32er-Schritten.
   - Qwen bearbeitet den Ausschnitt mit ihm selbst als Vorlage und rechnet nur in der Markierung neu (etwas größer).
   - Das Ergebnis kommt weich ins Original: 6 px Rand, 6 px Übergang.
   - Größe und alles außerhalb bleiben wie im Original. Nur Kernknoten.
4. **Ablage** wie immer:
   - Neue Datei `Verbessert_…png` im gewählten Projekt; das Original bleibt unangetastet.
   - Maske, Ausschnitt und alle Einstellungen stehen in der `.json` und im PNG („werkstatt“).
   - Für ComfyUI wird die Maske als kleines Graustufen-PNG in dessen Eingangsordner gelegt (wie Vorlagen von außerhalb),
     benannt nach ihrem Inhalt.
5. **Bibliothek:**
   - Bei verbesserten Bildern „Vorher/Nachher“, „Nochmal“ (gleiches Bild), „Variation“, „Mit Änderungen …“ (Maske und Text im Editor).
   - „Stelle verbessern …“ gibt es auf jedem Bild, auch auf verbesserten.
   - Bilder von außerhalb zeigt die Werkstatt nur, wenn Sascha sie selbst gewählt hat oder ein Studio-Bild auf sie verweist.
6. **Pose übertragen** geht schon über „Bearbeiten“: Vorlagen lassen sich jetzt nach vorn holen (die erste bestimmt
   Größe und Ausschnitt), Hinweis zu „Bild 1“, „Bild 2“ im Text.
7. **Gleiche Regeln wie bei Bildern:**
   - GPU-Sperre und Platzfrage (16 + 2 GiB).
   - Abbrechen wartet, bis ComfyUI steht.
   - Keine Kopien; Begleitdateien werden nie überschrieben.

Abnahme am 24.09.2026, 09:29–09:50 Uhr, am echten System (Testprojekt „Werkstatt-Abnahme“, neutrale Motive,
Qualität Standard = 20 Schritte, Oberfläche im Browser bedient, einzelne Fälle über die Schnittstelle):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Echte missratene Hand | `Bild_00007_` (Qwen 1024², Hand an der Hüfte von selbst missraten). Großansicht „Stelle verbessern …“, im Editor gezoomt (229 %), zwei Striche, „Hand reparieren“: natürliche Hand, Übergang unsichtbar. 30 s (Schätzung 24 s); Ausschnitt 384² auf 1024² |
| 2 | Rest unverändert | Kein Pixel weiter als 13,4 px von der Markierung geändert (Rand 6 + Übergang 6). Original-Hash vorher = nachher. Ergebnis RGB in Originalgröße |
| 3 | „Nochmal“ / „Variation“ | Variation: neue Nummer, andere Hand (24,5 s). Danach „Nochmal“: ComfyUI rechnete neu, Bilddaten Byte für Byte gleich wie das erste Ergebnis |
| 4 | „Mit Änderungen“ | Formular mit Text, Nummer, Qualität, Stärke. Editor öffnet das Original mit der gespeicherten Markierung (0,4 %) |
| 5 | Entfernen | Hoher Baum („Entferne den hohen Baum …“) sauber entfernt, 29,8 s |
| 6 | Bild von außerhalb | Foto aus einem fremden Ordner: Brille entfernt, Gesicht natürlich (29,9 s, Ausschnitt 1120×928). `/studio/vorlage` liefert es nur, weil der Auftrag bzw. das Ergebnis darauf verweist; eine andere Datei gibt 404 |
| 7 | Abbrechen | Nach 8 s Rechnen abgebrochen: „Abgebrochen.“ nach 2 s, erst als ComfyUIs Warteschlange leer war |
| 8 | Neben Transkription | nicht erneut geprüft: gleicher Ablauf (`_durchfuehren`, GPU-Sperre, Platzfrage) wie Bilder und Videos, dort in 3a/3b geprüft |
| 9 | Pose über „Bearbeiten“ | Person in Szene setzen gelingt („Ersetze die Frau in Bild 1 durch den Mann aus Bild 2 …“). Eine fremde Pose übernimmt Qwen nur manchmal: 1 von 4 Versuchen nah dran (Arm erhoben), sonst neben die Frau gestellt, eigene Pose behalten oder Bild 2 wiedergegeben. Hinweis im Formular entsprechend |
| 10 | Nur im Projektordner | neu nur `Werkstatt-Abnahme\Verbessert_0000n_.png` + `.json`; Markierungen als `werkstatt_maske_<Prüfsumme>.png` in ComfyUIs Eingangsordner |
| 11 | Bedienung | Pinsel, Größe, Zoom um den Mauszeiger, Rückgängig/Wiederholen, Anteil („0,4 % des Bildes markiert“), Vorher/Nachher (V), 1440×900 und 800×600 geprüft; Konsole ohne Fehler |

Umsetzung:
- `werkstatt\studio.py`: `maske_pruefen`, `maske_rahmen`, `maske_png` (Graustufen-PNG, nur Standardbibliothek),
  `ausschnitt_berechnen`, `verbessern_graph` (mit `ImageCropV2` + `PrimitiveBoundingBox`, weil `ImageCrop` in 0.37 als
  veraltet markiert ist). Dazu `_verbessern_pruefen`, Upload der Markierung, Aktion `maske`, `vorlage_datei`.
  Masken stehen nicht in der Statusabfrage, nicht in der Bibliotheksliste (nur `hat_maske`) und nicht bei fertigen
  Aufträgen in `studio.json`.
- `werkstatt\web\maske.js` (Editor), `studio.js` (Art, Vorschau, Vorschläge, Großansicht, Nochmal/Variation/Mit
  Änderungen, Vorlagen nach vorn), `index.html`, `style.css`.
- `werkstatt\server.py`: `/studio/vorlage`, Aktion `maske`, POST-Grenze 16 MiB (Markierung als Lauflängen).
- `werkstatt\config.json` (`studio.verbessern`), `werkstatt\messungen.py` („Stelle verbessern“, Ausschnittgröße).
- Tests: 11 neue in `werkstatt\tests\test_studio.py` (Markierung, Rahmen, PNG, Ausschnitt, Ablauf, Prüfung,
  Bibliothek, Bilder von außerhalb); Werkstatt 78/78, Zentrale 11/11.

Befunde:
- FLUX.2 [klein] 4B wäre ohne Anmeldung ladbar (Comfy-Org/flux2-klein: Diffusionsmodell 7,75 GB, Text-Encoder
  Qwen3-4B 8,04 GB, VAE 0,34 GB); ComfyUI 0.37 kann Klein (CLIPLoader-Typ `flux2`, `ReferenceLatent`). Nicht geladen,
  weil nicht nötig.
- Qwen 2.1 hat keinen eigenen Maskeneingang; offiziell gibt es lokale Änderungen per Kreis, Einzeichnung oder Maske als
  weiteres Bild. Die Maske als zweites Bild brachte in den Versuchen keinen Vorteil (+20 % Zeit), beim Entfernen hilft
  nur das Benennen des Gegenstands.
- Die VAE von Qwen 2.1 hat vier Kanäle: eigene Studio-Bilder sind RGBA-PNGs (Alpha voll), verbesserte RGB.
- Das Studio nutzt `ModelSamplingAuraFlow` mit Shift 3,1 (von 2Wild übernommen); ComfyUIs eigene Vorlage für
  Qwen 2.1 setzt keinen Shift (Modellstandard, bei 1024² etwa 2). Auswirkung ungeprüft, nicht geändert.
- Kein Upscaler-Modell vorhanden (`models\upscale_models` leer).

### Stufe 3c: 2Wild stilllegen (erledigt)

Go Sascha 24.09.2026 („alles implementieren“, nach der Übersicht vom selben Tag).

Umfang wie beschlossen:
- Die Zentrale startet unter „Bild & Video“ nur noch ComfyUI.
- Ein noch laufendes 2Wild erkennt sie weiter und beendet es mit.
- Die Werkstatt bettet 2Wild nicht mehr ein: Umschalter und eigene Ansicht entfallen.
- Der Ordner `Studio\gencenter` bleibt, wie er ist (in der Bibliothek „Aus 2Wild“).
- 2Wilds `data\jobs.json` wird weiter nur gelesen (Prompts alter Dateien, Messungen).
- Am 2Wild-Ordner ändert sich nichts, auch keine Notiz darin.
- Rückweg: den Startteil in `zentrale\aktionen.py` und die Ansicht in der Werkstatt zurückholen.

Umgesetzt und geprüft am 24.09.2026:
- Zentrale: Eintrag heißt „ComfyUI“, nur noch Link „ComfyUI öffnen“; `_comfy_starten` startet 2Wild nicht mehr.
  Zustand: kein „teilweise“ mehr; läuft 2Wild noch, steht „Das alte 2Wild Studio läuft noch; ‚Beenden‘ beendet es mit.“
- Werkstatt: Umschalter, eingebettete 2Wild-Ansicht und „2Wild im eigenen Fenster“ entfernt; `/api/bildvideo` nur ComfyUI.
- Am echten System: Zentrale neu gestartet (Hinweis auf das noch laufende 2Wild erschien), „Beenden“ → Ports 8188 und
  3998 frei, „Starten“ → nur ComfyUI (8188), 3998 bleibt frei, Zustand „bereit“ ohne Hinweis.
- 2Wild-Ordner: `git status` wie vorher (`M index.html`, `M server.py`, `?? LOCAL-SETUP.md`).

### Stufe 3e: Anregungen aus „Qwen Image 2.1: Create Character Sheets on 8GB VRAM“ (fertig, abgenommen)

Auftrag Sascha 24.09.2026: „Beurteile, was sich integrieren lässt, und baue es ein oder um. Die Qualität sollte nicht
darunter leiden, sonst frag erst nach.“ Quelle: Video von Tensor Alchemist (24.09.2026, YouTube `uWQrtLT357o`) und
dessen Workflow-JSON (Text zu Bild mit INT8-Dateien, Viggle-Turbo-LoRA überbrückt, automatischer Shift). Gelesen wurden
nur das Transkript und der Workflow; die Bildinhalte des Videos wurden nicht geprüft.

| Idee | Prüfung am echten System | Entscheidung |
|---|---|---|
| Automatischer Shift (`ModelSamplingFlux` 0,5–0,69, entspricht dem offiziellen Zeitplan von Qwen 2.1) statt Studio-Shift 3,1 | Vergleich 1328², 20 und 40 Schritte, gleiche Nummer: Haut gleich (Schärfemaß 178/178 bzw. 194/192), Gesamtbild mit 3,1 minimal detailreicher | nicht übernommen: kein Gewinn, würde „Nochmal“ aller bisherigen Bilder verändern |
| Charakterblatt aus einer Vorlage auf eigener Fläche | Größe wie Vorlage (1024²): nur 3 Ansichten. 16:9 mit 1920×1088: alle 4 Ansichten und Porträt | übernommen: „Größe“ beim Bearbeiten (Standard „Wie Vorlage 1“), Vorschlag „Charakterblatt“ |
| 2, 4 und 8 MP | 4 MP (2752×1536, 20 Schritte): 112–117 s, VRAM 17,3 + 5,9 GiB, stimmig, keine Doppelungen. Autor: bei 8 MP Layoutfehler | übernommen: drei „groß“-Formate bis 4 MP; 8 MP nicht |
| 25 statt 4 Schritte | Studio hat 20, 30 und 40 Schritte | nichts zu tun |
| Viggle-Turbo-LoRA (4, 5 oder 6 Schritte) | nicht vorhanden; Download 340 MB (v0.1, 4 Schritte, r64) bis 1,36 GB (v0.2, r256). Autor: bei Text zu Bild mit 4 Schritten Plastikhaut und Fehler, Charakterblätter brauchbar | zuerst gefragt; auf Auftrag v0.2.1 (6 Schritte) geladen, verglichen und als Stufe „Turbo“ übernommen (Nachtrag unten) |
| INT8-Modell und -Encoder, „Comfy Kitchen attention“ (INT8), Prefix-Cache | gedacht für 8-GB-Karten; INT8 kostet Genauigkeit; der Cache arbeitet ohnehin automatisch | nicht übernommen (ohne Messung eingeschätzt; die Aufmerksamkeit wurde am 26.09.2026 gemessen und als „schneller rechnen“ übernommen, Stufe 3k) |
| „Person einsetzen“ (Befund aus 3d) | – | als Vorschlag ergänzt |

Umsetzung:
- `werkstatt\studio.py`:
  - Neues Feld `groesse_von` (`vorlage` oder `format`). Bei `format` rechnet Qwen auf einer eigenen Fläche
    (`EmptySD3LatentImage`); ohne Angabe bleibt alles wie bisher, auch „Nochmal“ älterer Bilder.
  - Bilder bis 2816 px je Seite und höchstens 4,3 MP; Videos weiter bis 2048 px.
  - Bilder über 2 MP planen 18 + 6 GiB (`bedarf_gross_mib`).
- `werkstatt\config.json`: die Formate „Quadrat 1:1 · groß“ (2048²), „Querformat 16:9 · groß“ (2752×1536) und
  „Hochformat 9:16 · groß“ (1536×2752), außerdem `max_seite`, `max_pixel` und `bedarf_gross_*`.
- `studio.js`, `index.html`:
  - Feld „Größe“ beim Bearbeiten.
  - Vorschläge je Art: beim Verbessern „Hand reparieren“ und „Etwas entfernen“; beim Bearbeiten „Charakterblatt“
    (setzt 16:9 mit 1920×1088; nummerierte Ansichten) und „Person einsetzen“.
  - „Mit Änderungen“ übernimmt die Größe.
- Tests: 3 neue, Werkstatt 81/81.

Abnahme am 24.09.2026, 11:44–11:54 Uhr (Testprojekt „Werkstatt-Abnahme“):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Charakterblatt über die Oberfläche | „Als Vorlage“, dann Vorschlag „Charakterblatt“: Der Text wird eingesetzt, 16:9 gewählt und die Kleidung zum Überschreiben markiert. Ergebnis 1920×1088 in 56 s, `.json` mit `groesse_von: format` |
| 2 | Verlässliche Vorlage | Nummerierte Fassung: 2 von 2 Variationen mit allen vier Ansichten in der richtigen Reihenfolge plus Porträt; die freiere Fassung ergab 3 bzw. 4 Ansichten |
| 3 | Alte Bilder unverändert | „Nochmal“ eines Bearbeitet-Bildes von vor dem Umbau: Bilddaten Byte für Byte gleich |
| 4 | 4 MP über das Studio | 2752×1536 in 117 s (Schätzung 102 s), pixelgleich mit dem Versuch; VRAM 17,3 + 5,9 GiB bei Plan 18 + 6 GiB |
| 5 | „Mit Änderungen“ | Größe richtig übernommen: „Für Video 16:9“ bzw. „Wie Vorlage 1“ |
| 6 | Konsole | ohne Fehler |

Befunde:
- Qwen 2.1 plant offiziell dynamisch (mu 0,5 bei 256 bis 0,9 bei 8192 Token), ComfyUI nimmt fest 0,69. Das Studio
  (von 2Wild übernommen) nutzt Shift 3,1, das entspricht mu ≈ 1,13. Ein sichtbarer Nachteil war nicht messbar.
- Beim Bearbeiten nutzt ComfyUI freien Grafikspeicher zusätzlich als Zwischenspeicher für die Vorlagen (mit zwei
  Vorlagen bis 21,1 GiB auf der 3090). Wird es knapp, weicht er in den Arbeitsspeicher aus; das ist kein harter Bedarf.
- VRAM-Spitzen im 1-s-Takt: 2 MP 16,1 + 3,5 GiB, 4 MP 17,3 + 5,9 GiB (auf der 3090 jeweils mit ~1,4 GiB für Windows).
  Die frühere Messung „~1,3 GiB auf der 3080“ lief im 2-s-Takt und hat kurze Spitzen verpasst.

#### Nachtrag 3e: Stufe „Turbo“ (Viggle v0.2.1, 6 Schritte; fertig, abgenommen)

Auftrag Sascha 24.09.2026: „Ja, lade die 6-Schritte-Version und vergleiche sie.“
- **Download:** `Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors` von Hugging Face (Viggle, öffentlich, ohne
  Anmeldung). 679.604.800 Byte, SHA-256 `bafb91d0…345b` stimmt mit Hugging Face überein. Abgelegt in
  `ComfyUI\models\loras` (erst als `.part`, nach bestandener Prüfsumme umbenannt).
- **Einstellungen laut Modellkarte:** 6 Schritte mit den Sigmas 1,0 · 0,9375 · 0,875 · 0,75 · 0,5 · 0,25, CFG 1,
  Euler, Stärke 1,0, Bearbeiten mit 1–3 Vorlagen. Wie in Diffusers werden die Sigmas mit dem dynamischen Zeitplan von
  Qwen 2.1 verschoben (mu nach Bildgröße). In ComfyUI umgesetzt mit `LoraLoaderModelOnly`, `ManualSigmas`,
  `BasicGuider` und `SamplerCustomAdvanced`, nur Kernknoten.
- **Vergleich** (gleiche Nummer und gleicher Text wie das 20-Schritt-Bild):

| Fall | Standard 20 | Turbo 6 | Urteil |
|---|---|---|---|
| Neues Bild 1328², Porträt | 38 s (40 Schritte: 74 s) | 14 s | Hautdetail feiner (Schärfemaß Haut 258 gegen 178/194), Aufbau gleich |
| Neues Bild 2 MP, Szene | 49 s | 17 s | stimmig, Hände und Band plausibel |
| Charakterblatt 1920×1088 | 53 s | 24 s | praktisch gleich: vier Ansichten plus Porträt, gleiches Gesicht |
| Hand reparieren | 30 s | 14,5 s | gleich gut, Übergang unsichtbar |
| Person einsetzen, zwei Vorlagen | 37 s | 19 s | sauber, keine Geister oder Doppelungen, Pose sogar näher an der Vorgabe |

  Der einfache Zeitplan des Studios (KSampler „simple“, Shift 3,1) wirkt mit der LoRA etwas härter und verändert den
  Aufbau stärker; deshalb der Zeitplan der Modellkarte.
- **Einbau:**
  - Qualitätsstufe „Turbo“ (6 Schritte) für Bilder, Bearbeiten und Verbessern. Sie erscheint nur, wenn die LoRA im
    Ordner liegt. Die Stufe wird ausdrücklich angefordert (`turbo: true`), deshalb bleiben ältere Bilder bei
    „Nochmal“ unverändert. Der Standard bleibt „Max“.
  - Beim Verbessern mit „viel“ oder „wenig“ läuft nur der untere Teil des Zeitplans (`SplitSigmasDenoise`).
  - `.json` und Metadaten tragen `turbo: true`; die Zeitschätzung rechnet mit Faktor 1,4 je Schritt.
  - Die Messungen zeigen „Qwen-Image 2.1 · Turbo“.
  - Videos bleiben unberührt (dort gibt es die MiniMax-Turbo-LoRAs wie bisher).
- **Abnahme:**
  - Ein Porträt über das Studio ist pixelgleich mit dem Versuch.
  - „Nochmal“ auf ein Turbo-Verbessern-Ergebnis rechnete neu (15 s) und ergab Byte für Byte dieselben Bilddaten.
  - Die Oberfläche zeigt „Turbo, Entwurf, Standard, Hoch, Max“, dazu die passende Schätzung; in der Großansicht
    steht „Turbo (6 Schritte, mit Turbo)“.
  - 4 neue Tests, Werkstatt 85/85.
- **Grenzen laut Modellkarte:** Komplizierte Bearbeitungen, Gesichtstausch und Kompositionen aus mehreren Vorlagen
  können doppelte oder geisterhafte Figuren ergeben; kleiner Text wird schwach. In den Tests trat das nicht auf.

### Stufe 3f: Freistellen, Hochskalieren, Rezepte (fertig, abgenommen)

Auftrag Sascha 24.09.2026: „ja bau alle ein“, zu meinem Angebot aus dem Video „Why I'm Switching to Qwen Image 2.1 for
Editing“ (Ok Todd AI, 22.09.2026, YouTube `aWhqVdzWWAg`): Freistellen samt Aufräumen, Hochskalieren im Seitenverhältnis
der Vorlage und die Prompt-Rezepte als Vorschläge. Zusage: nur übernehmen, was die Qualität hält. Gelesen wurde nur das
Transkript; die Workflow-Datei wurde nicht geladen, und die Bildinhalte des Videos sind ungeprüft.

| Idee | Prüfung am echten System (Projekt „Werkstatt-Abnahme“) | Entscheidung |
|---|---|---|
| Freistellen: Qwen 2.1 gibt echte Transparenz aus | Wiese, Porträt, Hund („den Hund“), breites Praxisbild 2752×1536 („die Therapeutin und den älteren Patienten …“): keine Reste, Kissen, Gerät und Liege sauber weg. Bei starker Vergrößerung ein heller Saum aus Hintergrundfarbe. Vier Aufräum-Varianten auf Qwens roher Maske: 1 Pixel Randabzug nimmt den Saum, ohne dass Arm oder Haare schmaler wirken; eine weichere Rampe allein half nicht | übernommen, mit Randabzug (`kante_px` 1) |
| Freistellen mit Turbo | Porträt in 15 s, so sauber wie mit Standard (30 s) | Turbo geht auch hier |
| Hochskalieren | 688×384-JPEG (Qualität 55, aus dem 4-MP-Praxisbild) auf 2 MP: scharf, ohne Blockartefakte, Gesichter nahe am echten Original (leicht neu gezeichnet), 71 s. Wiese 1024² auf 4 MP (2048²): sichtbar mehr Detail in Haar und Haut, Gesicht leicht verändert, etwas mehr Kontrast, 188 s | übernommen: „Größe“ beim Bearbeiten um 2 MP und 4 MP ergänzt, Vorschlag und Knopf „Hochskalieren“ |
| Farbe per Hex-Code | Hex allein: #4A6FA5 wurde grelles Petrol (Turbo und Standard gleich), #B03A2E wurde Oliv. Mit Farbnamen („gedecktes Stahlblau (#4A6FA5)“, „kräftiges Ziegelrot (#B03A2E)“) stimmten beide | übernommen als „Farbe ändern“ mit Farbnamen, Hex nur in Klammern; Hinweis im Formular |
| Andere Perspektive | Wiese von knapp über dem Boden: tiefer Blickwinkel, Person, Kleid und Pose bleiben | übernommen |
| Gegenstand ersetzen | Behandlungsliege durch graues Sofa: gleiche Lage, gleiches Licht, Raum unverändert | übernommen |
| Kopf tauschen | Kopf der Porträt-Frau auf die Frau auf der Wiese: erkennbar dieselbe Person, Körper, Kette und Kleid bleiben | übernommen |
| Muster aus Bild 2 auf die Wand von Bild 1 | Sechs Versuche (Turbo und Standard, deutsch und englisch, mit „Bild 1/2“ und `<image1>/<image2>`): Qwen gab jedes Mal nur das flache Muster aus. Im Video war Vorlage 2 ein Raumfoto mit Tapete | nicht übernommen |
| Freigestelltes Bild als Vorlage | „Setze die Frau aus Bild 1 an einen Sandstrand bei Sonnenuntergang“: Frau, Kleid und Pose unverändert, 16 s (Turbo) | geht, weil ganz durchsichtige Stellen weiß sind |

Umsetzung:
- `werkstatt\studio.py`:
  - Neue Art `freistellen` mit `freistellen_graph`, nur Kernknoten:
    - Qwen bearbeitet das Original mit einer festen Anweisung aus `config.json` (`freistellen.vorlage`, darin
      `{motiv}`; leer: „the main subject“).
    - Genommen wird nur die Maske (`SplitImageWithAlpha`). Deckung bis 0,4 fällt weg, bis 0,65 steigt sie auf voll
      (`MaskComposite`); dann ein Pixel Randabzug (`GrowMask`), Skalieren auf Originalgröße.
    - Die Maske kommt auf die Originalpixel (`JoinImageWithAlpha`); ganz durchsichtige Stellen werden weiß
      (`ThresholdMask`, `EmptyImage`, `ImageCompositeMasked`). Die Datei wird dadurch auch kleiner (2,1 MB → 0,17 MB).
  - Beim Freistellen gibt man nur an, was bleiben soll (`prompt` = Motiv, höchstens 300 Zeichen); `.json` trägt
    `motiv` und die volle Anweisung.
  - Bearbeiten: neues Feld `aufloesung` (1024, 1440 oder 2048; nur Werte aus `bearbeiten_aufloesungen`). Ohne Angabe
    1024 wie bisher, deshalb bleibt „Nochmal“ älterer Bilder gleich. Über 2 MP plant die Werkstatt 18 + 6 GiB.
  - Zeitschätzung: Beim Bearbeiten „wie Vorlage 1“ und beim Freistellen läuft die Vorlage in gleicher Größe mit. Faktor
    `0,94 + 0,33 × Fläche` (relativ zu 1328², `vorlage_zeit`); damit werden 1, 2 und 4 MP auf etwa ±5 % getroffen.
    Neue Bilder und eigene Formate bleiben linear.
- `studio.js`, `index.html`, `style.css`:
  - Art „Freistellen“ mit Feld „Was soll bleiben?“ (statt Beschreibung und „Vermeiden“).
  - Größenstufen „Wie Vorlage 1 · 2 MP / 4 MP (hochskalieren)“.
  - Vorschläge beim Bearbeiten als Auswahlliste „Vorschlag einsetzen …“ (ab vier Einträgen): Charakterblatt,
    Person einsetzen, Kopf tauschen, Farbe ändern, Andere Perspektive, Gegenstand ersetzen, Hochskalieren. Der
    Hinweis nennt, welche Vorlagen es braucht.
  - Großansicht mit zwei Zeilen: „Bearbeiten:“ (Stelle verbessern, Freistellen, Hochskalieren, Als Vorlage) und
    „Für Video:“. „Hochskalieren“ wählt die nächste Stufe, die größer ist als das Bild. Bei freigestellten Bildern
    nur „Als Vorlage“.
  - „Vorher zeigen“ (V) auch für freigestellte und „wie Vorlage 1“ bearbeitete Bilder, in gleicher Anzeigegröße.
  - Schachbrett hinter Durchsichtigem; Kacheln zeigen „Freistellen: <Motiv>“.
- Tests: 4 neue bzw. erweiterte, Werkstatt 89/89, Zentrale 11/11.

Abnahme am 24.09.2026, 16:29–16:56 Uhr:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Freistellen über die Oberfläche | Großansicht „Freistellen“: Art, Original und Fokus auf „Was soll bleiben?“ richtig; mit Turbo in 15 s, `.json` mit `motiv`, `turbo`, Original |
| 2 | „Nochmal“ | Freigestellt (Standard) neu gerechnet in 30 s, hochskaliert (2 MP) in 69 s (Schätzung 74 s), altes Bearbeitet-Bild aus 3a in 31 s: jeweils Bilddaten Byte für Byte gleich. Direkt nach dem Erstellen meldet „Nochmal“ wie vorgesehen „gibt es schon“ |
| 3 | „Mit Änderungen“ | Freigestellt: Art, Motiv „den Hund“, Original; hochskaliert: Stufe 4 MP, Vorlage, Rezepttext |
| 4 | Formular | Freistellen blendet Beschreibung, „Vermeiden“, Format und Größe aus; ohne Bild „Erst ein Bild wählen“; Rezept „Hochskalieren“ setzt 2 MP |
| 5 | Konsole | ohne Fehler |

Befunde:
- Qwen 2.1 benennt Vorlagen intern als `<image1>`, `<image2>` (Vorlage im Knoten `TextEncodeQwenImage21`). „Bild 1/2“
  im Text funktionierte bei Person und Kopf trotzdem.
- Bearbeiten-Ergebnisse speichert ComfyUI als RGBA (die VAE hat vier Kanäle); das Studio behandelt sie wie bisher.

### Stufe 3g: „Details auffrischen“ mit Detail-LoRA (fertig, abgenommen); CharSheet-LoRA geprüft, nicht übernommen

Auftrag Sascha 24.09.2026: zwei LoRAs und der Workflow `Ep33 Qwen Image 2.1 Edit.json` in „Downloads“, zum Video „Is this
the Best New Lora for Enhancing an Image with Qwen Image 2.1?“ (Ok Todd AI, 22.09.2026, YouTube `ZtYBksmD9Qk`). Gelesen
wurden Transkript und Workflow; die Bildinhalte des Videos sind ungeprüft. Wie bisher: nur übernehmen, was die Qualität hält.

Dateien:
- `elusarcas-qwen2-1-detailer-v1.safetensors`: 79.744.352 Byte, SHA-256 `c1298f51…4f96`. Trainiert mit ai-toolkit,
  Rang 16, Attention und MLP aller 32 Blöcke, Beschriftung „enhance this image“. Verschoben nach `ComfyUI\models\loras`;
  ComfyUI lädt alle Schlüssel (keine Meldung „lora key not loaded“).
- `CharSheet.safetensors`: 335.602.856 Byte, SHA-256 `9aef911a…c9d1`. Von ModelScope (A964325/JSK), Rang 64,
  Auslösewort „角色卡“; laut Workflow die „portrait2charref“-LoRA. Nur zum Test verschoben, danach zurück nach „Downloads“.
- Workflow: Q8-GGUF, Detail-LoRA mit Stärke 1,0, 40 Schritte (Euler, simple, CFG 1), Enhance-Text des LoRA-Autors.
  Die Vorlage geht in eigener Größe hinein (`resolution 0`), die leere Fläche ist doppelt so groß (JPS-Knoten). Die eigenen
  Knoten (Pixaroma, JPS, GGUF) braucht das Studio nicht.
- Nach dem Neustart des Rechners (18:37 Uhr) liefen Zentrale, Werkstatt und ComfyUI nicht. Für die Tests: Zentrale und
  Werkstatt mit `--ohne-fenster` gestartet, ComfyUI über die Zentrale (Platzprüfung: genug Platz, keine Schritte).

Vergleich (gleiche Nummer, 20 Schritte, 2 MP „wie Vorlage 1“, nur Vorschaubilder):

| Fall | Ergebnis | Entscheidung |
|---|---|---|
| Überbelichtetes 512²-Porträt (künstlich aus `Bild_00009_`) | Studio bisher: bleibt überbelichtet. Mit Detail-LoRA: Belichtung, Hautstruktur, Falten und Hintergrund kommen zurück, nah am echten Original. Enhance-Text ohne LoRA wirkt kaum, Studio-Text mit LoRA gleich gut: Die Wirkung kommt von der LoRA | übernommen als „Details auffrischen“ |
| Komprimiertes 688×384-Foto (aus dem Praxisbild) | mit LoRA etwas mehr Falten- und Haardetail, näher an der Hauttextur des Originals | – |
| Sauberes KI-Bild (Wiese, 1 MP) | mit LoRA schärfer, aber der Inhalt ändert sich (Grasstreifen mitten im Weg, Gesicht stärker retuschiert) | „Hochskalieren“ bleibt ohne LoRA |
| LoRA mit Turbo | gleich gut, 33 statt 69 s | geht |
| Größenlogik des Workflows (Vorlage klein, Fläche groß) | 51 statt 69 s, aber Ausdruck und Augenform weichen stärker ab | nicht übernommen |
| CharSheet-LoRA, Prompt aus dem Workflow, 3:2 (1536×1024) | Sie erzwingt ihr Layout: kopflose Vorderansicht, großes Kopfporträt, Rückansicht, zwei Profilköpfe; fotorealistisch, Gesicht gut getroffen. Derselbe Prompt ohne LoRA ergibt ein vollständiges Blatt im Illustrationsstil. Unser Rezept: vier Ganzkörperansichten und Porträt | nicht übernommen: kein Qualitätsgewinn, die kopflose Figur taugt für echte Personen nicht |
| Farbe laut Notizen („hex color B03A2E“ ohne #, Turbo) | Englisch: Rot stimmt (1 Versuch). Deutsch „Hex-Farbe B03A2E“: Blau | Rezept bleibt bei Farbname mit Hex in Klammern |
| Wand laut Notizen („replace the texture of the wall on <image1> …“) | wieder nur das Muster (siebter Versuch) | bleibt draußen |

Umsetzung:
- `werkstatt\config.json`: Block `details` (LoRA-Datei, Stärke 1,0, Begründung).
- `werkstatt\studio.py`:
  - Neues Feld `details`, nur beim Bearbeiten und nur auf ausdrücklichen Wunsch; fehlt die LoRA, gibt es eine Meldung.
    Ohne Angabe bleibt „Nochmal“ älterer Bilder gleich.
  - `_mit_details` hängt `LoraLoaderModelOnly` (Knoten 25) hinter die Turbo-LoRA und vor den Shift.
  - `.json` und Metadaten tragen `details: true`; der Ablauf wird beim Einlesen erkannt; `details_verfuegbar`.
- `werkstatt\messungen.py`: Modell „Qwen-Image 2.1 · Details“.
- Oberfläche:
  - Häkchen „Details auffrischen (für schwache Fotos)“ beim Bearbeiten, nur wenn die LoRA vorhanden ist; die Schätzung
    sagt „mit Detail-LoRA: kann Kleinigkeiten verändern“.
  - Rezept „Foto auffrischen“: Enhance-Text des Autors, 2 MP, Häkchen an. Andere Rezepte und der Knopf „Hochskalieren“
    schalten es aus.
  - Großansicht „mit Detail-LoRA“, Kachel „· Details“; „Nochmal“ und „Mit Änderungen“ übernehmen es.
- Tests: 2 neue, Werkstatt 91/91.

Abnahme am 24.09.2026, 19:12–19:16 Uhr:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | „Foto auffrischen“ über die Schnittstelle (überbelichtetes Porträt, Standard) | 70 s; Bilddaten pixelgleich mit dem Versuch |
| 2 | Über die Oberfläche (Vorlage aus der Bibliothek, Rezept, Turbo) | Häkchen gesetzt, 2 MP, Schätzung 30 s, gerechnet 32 s; Kachel „Turbo · Details“; Großansicht „Turbo (6 Schritte, mit Turbo, mit Detail-LoRA)“ |
| 3 | „Nochmal“ und „Mit Änderungen“ | Anfrage mit `details`, Turbo und 2 MP; ältere Bilder ohne `details`; das Häkchen wird übernommen |
| 4 | Konsole | ohne Fehler |

### Stufe 3h: Handbuch STUDIO.md und Skill `bild-video-studio` (fertig)

Auftrag Sascha 24.09.2026: eine MD-Datei führen, die alles Gebaute auflistet und erklärt (Funktionsweise, LoRAs und
Prompts, wofür sie gut sind), sodass auch ein anderer Agent die App versteht. Außerdem einen Skill, der greift, sobald ein
Bild gebraucht wird (besonders beim Bau von Webseiten) und über das lokale Modell erzeugt; ebenso für Videos, gern in
einem Skill.

Umsetzung:
- **[STUDIO.md](STUDIO.md)** (neu, maßgeblich für das Studio): Überblick, Starten, Arten, Qualitätsstufen und LoRAs,
  Formate, alle Rezepte im Wortlaut, Prompt-Regeln, was nicht geht, Ablage und Wiederholbarkeit, Schnittstelle für
  Agenten, Dauer und Grafikspeicher, interne Abläufe. README fasst den Studio-Teil nur noch zur Bedienung zusammen und
  verweist darauf; AGENTS.md verpflichtet, STUDIO.md bei jeder Studio-Änderung mitzuführen.
- **Skill `bild-video-studio`** unter `C:\Workstation\Skills\aktiv\bild-video-studio`, verknüpft für Claude, Codex
  und Hermes (Junctions wie bei den anderen gemeinsamen Skills), in BETRIEB.md eingetragen:
  - `SKILL.md`: wann (Bild/Video gebraucht, besonders Mockups und Webseiten) und wann nicht (Diagramme, Logos,
    UI-Entwürfe), Ablauf (vorhandene Bilder suchen, Bereitschaft, Projekt, 2–3 Variationen, ansehen,
    nachbessern, exportieren, berichten), Befehle, Prompt-Regeln, Regeln der Werkstatt.
  - `references/webseiten.md`: Format je Einsatz, einheitlicher Stil-Zusatz, Musterprompts, Export, HTML-Einbau,
    Alt-Texte, Herkunft festhalten.
  - `scripts/studio.py` (nur Standardbibliothek, Export über ffmpeg): `status`, `start` (Zentrale und Werkstatt ohne
    Fenster, ComfyUI über die Zentrale nur ohne Entladen; sonst Exit 3 und Sascha fragen), `projekt`, `bild`,
    `bearbeiten`, `verbessern --rechteck`, `freistellen`, `hochskalieren`, `auffrischen`, `video` (Text, Start-/Endbild,
    Referenz), `warten`, `bibliothek`, `export` (WebP/JPEG/PNG mit Breite oder genauem Zuschnitt, Transparenz nur bei
    freigestellten Bildern; MP4/WebM ohne Ton, Posterbild).
- Geprüft am echten System (Projekt „Werkstatt-Abnahme“): Status/Start/Bibliothek; zwei Hero-Bilder mit Turbo (15 und
  10 s); Export 2,1 MB PNG → 63 KB WebP (1600 px), JPEG, genauer Zuschnitt 1200 × 630; Freistellen per Skript (14 s)
  und WebP mit Alphakanal; Verbessern per Rechteck (Pflanze → Monstera, 16 s, nahtlos); Video aus Text 5 s (88 s) und
  Export als MP4/WebM ohne Tonspur samt Posterbild.
- **Probelauf mit einem zweiten Agenten**, der nur den Skill kannte: kleine Landingpage „Praxis Lindenhof“ mit Hero und
  zwei Abschnittsbildern. Er suchte zuerst in der Bibliothek, legte einen Stil-Zusatz fest, rechnete 8 Bilder mit Turbo
  (113 s), sah alle an, wählte die besten (Hände geprüft, Gesichter verborgen), exportierte WebP mit Alt-Texten und
  Herkunftsliste und prüfte die Seite bei 1440/1024/390/360 px. Seine Kritik wurde eingearbeitet: `export` nimmt
  Bibliothekspfade, nennt Breite und Höhe und warnt, weil es nicht vergrößert; unbekannte Projektnamen werden abgewiesen
  (neu nur mit `studio.py projekt`); genauere Musterprompts (Kameraposition, Material), realistische Trefferquoten,
  Prüfliste für Hände und Mechanik, Aufruf für PowerShell und Bash. Turbo bei 4 MP gemessen: 39 s.
- Befund dabei: **„Vermeiden“ (Negativ-Prompt) wirkt im Studio nicht.** Es rechnet mit CFG 1; ComfyUI überspringt dann
  den Negativ-Prompt (`comfy/samplers.py`, `cond_scale == 1`), die Turbo-Stufe nutzt ohnehin nur den positiven Text.
  In STUDIO.md, README und Skill vermerkt.
- **Entscheidungen Sascha (24.09.2026, abends):**
  - Einschränkung gestrichen: Der Skill hatte Bilder echter Personen, des Teams und der eigenen Praxisräume ausgeschlossen
    und im Probelauf Gesichter vermieden. Einsatz ist in erster Linie Mockups (Seite, Praxis und Personen erfunden);
    intern gibt es keine Einschränkung bei Gesichtern, Personen, Praxisräumen und Inventar. Bilder, die nach außen gezeigt
    werden, werden als KI-erzeugt gekennzeichnet. Umgesetzt in SKILL.md, `references/webseiten.md` (neue Musterprompts
    mit Gesichtern, Team-Porträt, Außenansicht) und STUDIO.md („Einsatz“).
  - Feld „Vermeiden“ wollte er nicht; es ist aus der Oberfläche entfernt. Neue Aufträge schicken keinen Negativ-Prompt;
    „Nochmal“ älterer Bilder übernimmt den gespeicherten Wert (ohne Wirkung).
- **Befund Sascha:** Das Trainingsbild aus Text hatte mehrere Bänder vor Kopf und Armen (von mir zunächst zu mild als
  „Schlaufe“ beschrieben). Übungen mit Geräten sind aus Text allein unzuverlässig. Daraus:
  - Abschnitt „Vorlage statt Erfinden“ in Skill und STUDIO.md: Foto mit richtiger Haltung als Vorlage, Person, Gesicht,
    Farben per „Bearbeiten“ ändern.
  - Neuer Befehl `studio.py chatbild`: legt ein in den Chat eingefügtes Bild aus dem Sitzungsprotokoll als
    `Vorlage_<Zeit>` ins Studio-Projekt; geprüft mit dem am Morgen eingefügten Bildschirmfoto (2000 × 1136, kein
    Überschreiben). Nur für Claude-Code-Sitzungen; sonst die Datei in den Chat ziehen oder den Pfad nennen.
  - Drei Proben dazu warteten zuerst auf die Grafikkarte (Ornith Q5, von einem Testlauf im Praxis-OS-Chat geladen).
    Nach dem Entladen durch Sascha gerechnet (je 1 Versuch, Turbo, 14–18 s, ≈1 MP, Projekt Werkstatt-Abnahme):
    - `Bearbeitet_00036_` aus `Bild_00022_`: Therapeutin (kurze rote Haare, Sommersprossen, dunkelblau) und Patient
      (dunkle Haut, Bart, weißes T-Shirt) gleichzeitig getauscht; Haltung, beide Hände, Liege, Raum, Licht gleich.
      Das Rot kam knallig gefärbt („natürliches Kupferrot“ wäre genauer).
    - `Bearbeitet_00037_` aus `Bild_00019_`: Frau gegen sportlichen Mann, Band orange; Arme, Fäuste und Bandverlauf
      gleich – einschließlich der seitlich hängenden Bandenden der KI-Vorlage.
    - `Bearbeitet_00038_` aus `Bild_00013_`: Wände hellblau (eher klar als graues Taubenblau), Polster dunkelblau, Holz
      hell; Gestell, Pflanzen, Fenster und Lichtflecken gleich.
    - Folgerung: Bearbeiten mit Vorlage übernimmt Haltung und Gegenstände zuverlässig, auch deren Fehler. Für Übungen
      also ein echtes Foto als Vorlage. In STUDIO.md, SKILL.md und `references/webseiten.md` ergänzt.

### Stufe 3i: Figuren und Logos als Vorlage (getestet und als Vorschläge eingebaut, 24.09.2026)

Anlass: Build-Guide „/generate skill“ (RoboNuggets, PDF von Sascha). Die meisten Punkte hatte das Studio schon
(Begleitdatei mit Prompt und Einstellungen, Bibliothek, Vorlagen, Turbo als günstiger Entwurf). Neu waren zwei
Ideen: Gesichter und Logos nicht beschreiben, sondern als Bild mitgeben. Sascha: „Ja, Teste 1 und 2.“ Alle Bilder liegen
in Werkstatt-Abnahme; je Szene 2 Versuche, Turbo.

- **Figur:** Porträt `Bild_00027_` (hoch45; Variante `_00028_` nicht gewählt).
  - Porträt als Vorlage, Szene nur beschrieben (Behandlung, Empfang, Übung; `Bearbeitet_00039_`–`_00044_`): In 6 von 6
    Bildern klar dieselbe Person, in der Ganzkörperszene etwas schwächer. Ohne Vorlage mit derselben Beschreibung
    (`Bild_00029_`, `_00030_`): 2 von 2 eine andere Frau.
  - Grenzen: Blick und Lächeln des Porträts schlagen durch (am Empfang schaut sie 2 von 2 in die Kamera). „Die Frau
    zeigt einem Mann eine Übung“ scheiterte 2 von 2: Rollen vertauscht bzw. Beine unplausibel, keine Übung zu sehen.
  - Zweistufig (Szene aus Text, dann Rezept „Person einsetzen“ mit dem Porträt als Bild 2; `Bearbeitet_00051_`,
    `_00052_`): 2 von 2 blieben Aufbau, Hände und Patient, das Gesicht wurde die Figur. Einmal lächelte sie danach
    eher zur Kamera.
- **Logo:** Test-Logo `Vorlage_Logo-Test.png`, erfunden und selbst gezeichnet („PHYSIO LINDENHOF“, Blatt im Kreis).
  - Symbol und Schriftzug waren in 6 von 6 Bildern richtig: Stickerei auf dem Porträt (`Bearbeitet_00045_`,
    `_00046_`, 2 MP), Schaufenster (`_00047_`, `_00048_`, 2 MP) und Tasse als neue Szene nur aus dem Logo (`_00049_`,
    `_00050_`, quadrat).
  - Die kleine Unterzeile auf dem Stoff hatte 2 von 2 Fehler („fiür“, „Praxls“), auf Fenster und Tasse war sie richtig.
  - Aus „Folienbeschriftung“ wurde 2 von 2 eine Milchglasfolie über der ganzen Scheibe; die Pflanzen dahinter
    verschwanden.
- Dauer: Porträt in neues Format 13–20 s (die Schätzung zeigte 10 s); 2 MP mit zwei Vorlagen 31–55 s (geschätzt 18 s).
- Nebenbefund: Deutsche Anführungszeichen „…“ in einem PowerShell-Prompt mit `"…"` beenden den Text; das Skript meldet
  „unrecognized arguments“. In SKILL.md vermerkt: in PowerShell `'…'` verwenden, die Bash ist nicht betroffen.
- **Eingebaut** (Auftrag Sascha: „Ja, auf jeden Fall. Bau die Vorschläge ein.“): zwei neue Vorschläge beim Bearbeiten
  in `werkstatt\web\studio.js` (`VORSCHLAEGE.figur`, `VORSCHLAEGE.logo`), nur Oberfläche, kein Dienst-Code.
  - „Figur in neue Szene“: Größe Querformat 16:9, markiert die Szenenbeschreibung, Hinweis zu Porträt, Haltung, Blick,
    Kamera und „Person einsetzen“ für Handlungen zu zweit.
  - „Logo aufbringen“: Größe wie Vorlage 1 mit 2 MP, markiert die Stelle, Hinweis zu Logo-Datei und Glas.
  - Die Schätzzeile nennt beim Format jetzt „Charakterblatt oder Figur in neuer Szene“.
- Prüfung am echten System, alles über die Oberfläche (Vorlage per „Als Vorlage“, Vorschlag gewählt, Turbo):
  - Figur, erster Wortlaut („die Person aus Bild 1 … behandelt die Schulter …“ ohne Haltung und Kamera): 2 von 2 stand
    sie nur lächelnd im Raum (`Bearbeitet_00057_`, `_00058_`).
  - Mit Haltung und Kamera, Patient nicht beschrieben: 1 von 2 gut, 1 von 2 erschien die Figur doppelt
    (`_00060_`, `_00061_`).
  - Endgültiger Wortlaut (wie der erfolgreiche Test `_00039_`, mit beschriebenem Patienten): 2 von 2 richtig, Hände
    sauber (`_00062_`, `_00063_`).
  - Logo ohne ausgeschriebenen Schriftzug: 3 von 3 fehlerfrei samt Unterzeile (`_00053_`, `_00054_` per Skript,
    `_00059_` über die Oberfläche). Auf Glas mit „Die Scheibe bleibt durchsichtig …“: 2 von 2 durchsichtig (`_00055_`,
    `_00056_`).
  - Tests: Werkstatt 91 OK, Zentrale 11 OK, `node --check studio.js` OK. Dienst nicht neu gestartet (die Oberfläche
    wird bei jedem Aufruf frisch gelesen).
  - Die Formulareinstellungen der Oberfläche habe ich nach den Proben zurückgesetzt (Neu, Max, feste Nummer, 1 Bild).
    Der zuletzt eingetragene Prompttext ging dabei verloren.
- Festgehalten in STUDIO.md (Abschnitt 6: zwei Rezepte samt Befunden, 7, 8, 11), SKILL.md („Figuren und Logos als
  Bild mitgeben“) und `references/webseiten.md`.

### Stufe 3j: Moodboards – Vorschläge in drei Formaten und Hybrid-Board (25.09.2026, fertig)

Auftrag Sascha: Moodboard-Rezepte, „Möglichkeiten für hoch, breit, square“, näher an die früheren GPT-Image-2-Boards;
Prompt analysieren, mit Astra abstimmen; nach Freigabe „1“ (Claude baut). Plan und Review (3 Runden, am Ende
APPROVED): `C:\Workstation\AI-Knowledge-System\Workspace\Handoffs\2026-09-25 Moodboard Studio Plan.md` und
`… Astra-Review-Log.md`.

- **Testreihe** (feste Variationsnummern, harte Fehler gezählt, Einzelheiten in STUDIO.md Abschnitt 6): Englisch mit
  festen Positionen schlug den alten und einen inhaltsgleichen deutschen Prompt; Hochformat 9:16 statt 2:3; Mockup im
  Hochformat als volle Zeile; Palettensatz mit getrennten Feldern und Kontur; Textur im Hochformat als ein Foto;
  Standard statt Turbo ohne Gewinn (3× Zeit). Endstand eingefroren: Quadrat/Quer 11, 22, 33 und Hoch 11, 22, 55 ohne
  harten Fehler; Hundezucht mit langem Namen und Umlaut 2 von 2.
- **Oberfläche** (`werkstatt\web\studio.js`, `index.html`): drei Vorschläge unter „Neu“ mit genau den abgenommenen
  Texten. `vorschlagEinsetzen()` setzt jetzt auch `format` und `qualitaet`. Der Formularzustand merkt sich den
  Moodboard-Vorschlag (Rezept-ID, Formatfamilie, Rastersatz; auch nach Neuladen). Passt das Format nicht, erscheint
  `#st-rezept-hinweis`: „Das Raster im Text passt nur zum Hochformat 9:16 oder 2:3 …“; fehlt der Rastersatz:
  „Rasterzuordnung ungeprüft“. Bekannte Formate sind fest ihrer Familie zugeordnet, eigene Größen mit 2 % Toleranz;
  Nutzertext wird nie umgeschrieben, ein geleertes Feld beendet die Zuordnung.
- **Geprüft im echten Studio** (Browser, eigenes Profil): Vorschlag setzt Format und Turbo und markiert den Namen;
  Warnung bei Quadrat und 4:5, keine bei 9:16 klein, 1664 × 2496 und 1152 × 2048; „Rasterzuordnung ungeprüft“ nach
  Entfernen des Rastersatzes; nach Leeren keine Warnung; Erstellen „Moodboard breit“ → `Bild_00074_` fehlerfrei;
  Export als WebP 1920 × 1072 über `studio.py export`. Tests: Werkstatt 92 OK, Zentrale 11 OK, `node --check` OK.
- **Hybrid-Board** (Moodboard-Skill, `C:\Workstation\Skills\aktiv\moodboard\scripts\board.py`, nur
  Standardbibliothek + ffmpeg + Edge headless): eine JSON-Beschreibung → WebP-Assets (Ausschnitte), HTML je Format,
  PNG 2× (2160 × 3840, 3840 × 2160, 2880 × 2880), `style-notes.md`, `manifest.json`. Prüft geladene Bilder/Schriften
  und die PNG-Größe; alle drei Formate in ≈ 7 s. Beispiel mit vorhandenen Studio-Bildern (keine neuen erzeugt):
  `OneDrive\Mood Board\outputs\2026-09-25-physio-lindenhof-hybrid\`; Hex-Werte aus den Farbfeldern von
  `Bild_00051_` gemessen.
- **Moodboard-Skill** neu: neutraler Kern (Weg A Stimmungsboard, Weg B Hybrid-Board, Zählregeln, Prompt-Regeln),
  Profile `profil-praxis.md` und `profil-hundezucht.md`, abgenommene Prompts in `references\prompt-recipes.md`,
  GPT Image 2 nur auf ausdrücklichen Wunsch. OneDrive-`AGENTS.md`: Kopieranweisung ersetzt, `skill-mirror` als
  historische Kopie gekennzeichnet (`HISTORISCH.md`), nichts gelöscht.

### Fehlerbehebung 25.09.2026: „Bild & Video ist aus“ während einer Renderung

- Meldung Sascha: Während eine Videorenderung lief, kam beim Erstellen eines weiteren Auftrags unter dem Knopf „Bild &
  Video ist aus. Bitte in der Modellzentrale starten.“, obwohl ComfyUI lief. Der Auftrag hätte in die Warteschlange
  gehört.
- Ursache, gemessen während der Renderung (6 min, etwa alle 1,5 s): ComfyUIs `/system_stats` antwortete jedes Mal
  erst nach 3,8–4,2 s, `/queue` meist nach 6–20 ms (zweimal 1,4 bzw. 3,5 s). Die Werkstatt fragte bei jeder Zustandsprüfung beide mit 3 s Frist ab. Die Zeitüberschreitung
  galt als „ComfyUI aus“, und `erzeugen` lehnte mit 409 ab. Die Anzeige oben konnte deshalb ebenfalls „aus“ zeigen.
- Behebung (`werkstatt\studio.py`, `comfy_zustand`): Ob ComfyUI läuft, zeigt nur noch `/queue` (Frist 5 s). Die
  Startoptionen mit dem Ausgabeordner liest die Werkstatt aus `/system_stats` einmal je ComfyUI-Prozess (Prozess-ID des
  Ports), mit 15 s Frist. `server.py` (`bildvideo`, Anzeige „ComfyUI bereit“) wartet auf `/queue` jetzt 5 statt 1,5 s.
- Neuer Test `test_comfy_zustand_liest_startoptionen_einmal_je_prozess`; Werkstatt 92 OK, Zentrale 11 OK.
- Neustart der Werkstatt erst, wenn nichts mehr läuft; die laufende Renderung wurde nicht abgebrochen.

### Stufe 3k: Anregungen aus „Qwen Image 2.1 – Runs Locally in ComfyUI“ (26.09.2026, fertig)

Auftrag Sascha: das Video von Nerdy Rodent (YouTube `iJoo2RuAfZ0`) samt Folien auswerten (Skill `watch`, mit
Standbildern), dann „2 und ja 1-7 testen und wenn es funktioniert korrekt implementieren“ (2 = Auswertung als
vorübergehendes Arbeitswissen ablegen). Auswertung, Ideenliste und Ergebnisse:
`C:\Workstation\Arbeitsmaterial\watch\Qwen Image 2.1 - Runs Locally in ComfyUI [iJoo2RuAfZ0]\studio-ideen.md`
(A1–A7 ohne Download, B1–B3 nur mit Download).

Die Versuche liefen als Vorschau direkt über ComfyUI (keine Dateien im Studio), mit den Abläufen aus
`werkstatt\studio.py`, feste Nummern 11 und 22, Turbo, wenn nicht anders genannt.

| Nr. | Idee aus dem Video | Ergebnis | Entscheidung |
|---|---|---|---|
| A1 | Durchsichtige Bilder direkt (Rahmen-Prompt der ComfyUI-Vorlage) | Person, Tasse, Pflanze je 2: 6 von 6 sauber freigestellt, 9–14 s, kein Saum auf Weiß, Magenta und Schwarz. Aber ein Schleier (Deckung 1–5 von 255 auf 24–47 % der Fläche) und Lila (RGB 164, 57, 208) unter durchsichtigen Stellen | übernommen, mit Aufräumen (Häkchen „Durchsichtiger Hintergrund“) |
| A2 | Banner 3:1, Panorama 4:1 | Praxis und Landschaft je 2: Aufbau 8 von 8 stimmig, 26 bzw. 36 s; einmal zwei Liegen, einmal ein seltsames Liegenbein; Freifläche links 4 von 4 | übernommen (`banner31`, `panorama41`, `max_seite` 4096) |
| A3 | Schnelles Hochskalieren ×2 per Bild zu Bild (Lanczos, 6 Schritte, denoise 0,25/0,35) | 2 Bilder → 5,2 bzw. 6,2 MP in 50–66 s, nur leicht schärfer; mit Turbo 21–27 s, aber weich. Unser Hochskalieren holt mehr Details: 2 MP Turbo 32 s, 4 MP Turbo 84–87 s | nicht übernommen |
| A4 | Kleinschrift mit Sampler `seeds_2` | Styleguide-Blatt 1664 × 928 mit 14 Texten; Turbo, Turbo + `seeds_2`, Euler 20, `seeds_2` 16, je 2: alle 8 mit 1–2 Fehlern; Hex 40/40, Farbnamen 39/40, „Segoe UI“ 7/8 falsch, „Farbpalette“ 2/8; 12–23 s, 19 s, 34–35 s, 50 s | Sampler nicht übernommen; Prompt-Regel in STUDIO.md |
| A5 | Bild als Stil-Vorlage | gegenständliche Vorlagen (Aquarell-Leuchtturm, flache Grafik mit Fahrrad und Haus), deutsch, englisch, lang mit „do not copy its content“, Vorlage 1024 und 512 px: 0 von 10, der Inhalt der Vorlage kam jedes Mal wieder. Abstrakte Textur 1 von 2; ohne Vorlage gleich gut | nicht übernommen; Regel „Stil in Worten“ |
| A6 | Schnellere Aufmerksamkeit (`ModelAttentionBackend`, „comfy kitchen attention“, INT8) | Turbo 13,2 → 12,2 s, Standard 38–42 → 34–36 s; zweiter Lauf jeweils pixelgleich; zu PyTorch im Mittel 1,5–2,1 von 255 Abweichung, Gesicht, Hände und Schrift gleichwertig | übernommen als `schnell` für neue Bildaufträge (revidiert die ungemessene Einschätzung aus 3e) |
| A7 | Jeden Finger beschreiben | Zeigen auf ein Poster und Hände auf einer Schulter, mit und ohne, je 2: 8 von 8 plausible Hände | nur dokumentiert (kein Gewinn) |

Umsetzung:
- `werkstatt\studio.py`: `durchsichtig_prompt`/`durchsichtig_beschreibung`, `_mit_durchsichtig` (Knoten 80–95: Schleier
  bis `rest_bis` 0,02 weg, darüber gestreckt, ganz Durchsichtiges weiß), `_mit_schnell` (Knoten 26, als letzter Schritt
  in `bild_graph`, `freistellen_graph` und `verbessern_graph`). `_pruefen` nimmt `durchsichtig` (nur `bild`) und
  `schnell` (nur Bilder, nur wenn eingeschaltet) an, sonst still ignoriert. `einstellungen()` meldet
  `schnell_verfuegbar` und `durchsichtig_verfuegbar`; `einstellungen_aus_graph` erkennt beides im gespeicherten Ablauf;
  Begleitdaten `durchsichtig` und `schnell`. Ohne die Felder bleibt jeder Ablauf wie bisher („Nochmal“ alter Bilder).
- `werkstatt\config.json`: Abschnitte `durchsichtig` und `schnelle_aufmerksamkeit`, Formate `banner31` und
  `panorama41`, `max_seite` 4096 (das Pixelbudget 4,3 MP bleibt die Grenze).
- `studio.js`/`index.html`: Häkchen „Durchsichtiger Hintergrund (Motiv freigestellt, PNG)“ nur unter „Neu“, Hinweis in
  der Zeitschätzung, „Nochmal“ und „Mit Änderungen“ übernehmen es, Detailansicht „· durchsichtiger Hintergrund“,
  Bibliothekskachel mit Schachbrett. Neue Bildaufträge schicken `schnell: true`, wenn verfügbar; „Nochmal“ nur, wenn
  das Original es hatte. `messungen.py`: Zusatz „· schnell“.
- Skill `bild-video-studio`: `bild --durchsichtig` (bricht ab, wenn die Werkstatt es nicht meldet), Formate,
  `schnell` automatisch, Export behält die Transparenz durchsichtiger Bilder; SKILL.md und `references\webseiten.md`.
  Moodboard-Skill: Nachtest Kleinschrift unter „Grenzen“. STUDIO.md: Abschnitte 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12.
- Tests: Werkstatt 96 OK (neu: Rahmen-Prompt und Umkehrung, Aufräum-Ablauf, Reihenfolge der Knoten 24 → 25 → 26 → 7,
  Prüfung der Felder, Banner-Grenzen), Zentrale 11 OK, `node --check` OK.

Prüfung am echten System (26.09.2026, 19:48–19:55, Projekt „Werkstatt-Abnahme“, Werkstatt neu gestartet):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Durchsichtig über den Skill | `Bild_00075_` (Tasse), 14,2 s, Schleier 0,1 %, unter durchsichtigen Stellen Weiß; Export als WebP mit Alpha (yuva420p), als JPEG weiß |
| 2 | Durchsichtig über die Oberfläche | Häkchen nur unter „Neu“; `Bild_00078_` (Monstera), 13,8 s, mit `durchsichtig` und `schnell`; Kachel mit Schachbrett |
| 3 | Panorama | `Bild_00076_` 4096 × 1024 in 30,4 s mit `schnell`, sauber; Banner und Panorama in der Formatliste |
| 4 | Schnell in den übrigen Bildarten | `Freigestellt_00010_` (13,6 s) und `Verbessert_00009_` (15,5 s) mit Knoten 26. Das Verbessert-Bild ist inhaltlich unbrauchbar (Hand ohne Arm), weil der Test eine Hand an eine Stelle ohne Arm verlangte; geprüft wurde nur der Ablauf |
| 5 | Alte Bilder unverändert | „Nochmal“ von `Bild_00029_` → `Bild_00077_` pixelgleich, ohne `schnell` |
| 6 | Formular | Einstellungen der Oberfläche nach den Proben wiederhergestellt |

Nachtrag 26.09.2026, 20:05–20:25 – durchsichtige Bilder weiterbearbeiten (beim Nachziehen der Doku aufgefallen: die
Großansicht bot bei durchsichtigen Bildern „Stelle verbessern“, „Freistellen“ und „Hochskalieren“ an):
- Proben über den Skill: Monstera `Bild_00078_` auf 2 MP hochskaliert → `Bearbeitet_00068_` durchsichtig, aber ohne
  Aufräumen (Schleier auf 25 % der Fläche, Lila darunter) und eher gemalt als fotografiert. `Freigestellt_00010_`
  hochskaliert → `_00069_` auf Weiß. Tasse `Bild_00075_` rot gefärbt → `_00070_` auf Weiß. Durchsichtig in 4 MP
  (2048²) → `Bild_00079_` sauber in 31,5 s (Tassenboden am unteren Rand).
- Ein WebP-Export von `_00068_` hätte ohne Transparenz einen lila Hintergrund gezeigt, weil der Export nur markierte
  Bilder als durchsichtig behandelte. Messung aller 158 normalen Bilder: Qwen-Bilder sind nie ganz deckend (Deckung an
  bis zu 97 % der Pixel 220–254, vereinzelt bis 157), aber keines hat Stellen unter 50 %.
- Umgesetzt: Die Großansicht zeigt bei durchsichtig erzeugten Bildern wie bei freigestellten nur „Als Vorlage“
  (`studio.js`). Der Skill erkennt echte Transparenz (mehr als 0,1 % der Pixel unter 50 % Deckung, per ffmpeg; normale
  Bilder 0 %, durchsichtige 32–49 %), lehnt `hochskalieren`, `auffrischen` und `verbessern` dafür mit Alternativen ab,
  weist bei `bearbeiten` darauf hin und behält beim Export die Transparenz auch unmarkierter Bilder; JPEG lehnt er
  ab, wenn darunter kein Weiß liegt. Geprüft: Großansicht Monstera nur „Als Vorlage“, normales Bild alle vier Knöpfe;
  drei Ablehnungen ohne Auftrag; Exporte `_00068_` → WebP mit Alpha (auf Weiß ohne Saum), → JPEG abgelehnt,
  `Bild_00075_` → JPEG weiß und WebP mit Alpha, `Bild_00077_` → WebP und JPEG ohne Alpha; `node --check` OK.
- Nicht gebaut (möglicher nächster Schritt): Bearbeiten eines durchsichtigen Bildes so, dass es sauber durchsichtig
  bleibt (Aufräumen auch beim Bearbeiten, wenn Bild 1 durchsichtig ist). Heute: danach „Freistellen“.

Nicht gebaut, weil ein Download nötig wäre (Entscheidung Sascha, „Offen“): B1 Maske per Wort (SAM3), B2 Pose- oder
Tiefensteuerung, B3 INT8-Modell von Qwen 2.1. Am 27.09.2026 auf Auftrag nachgeholt (Stufe 3l).

### Stufe 3l: Hilfsmodelle und INT8 (27.09.2026, fertig)

Auftrag Sascha: „Bitte alles downloaden und einbauen, was Sinn macht. Wofür das kleinere INT8-Modell von Qwen?“ –
also die Modelle hinter B1–B3 aus 3k laden, prüfen und einbauen, was sich bewährt.

**Geladen** (alle von Comfy-Org auf Hugging Face, Größe und SHA-256 gegen die Angaben des Repos geprüft; Skript im
Scratchpad der Sitzung, nur Standardbibliothek; Ziel `…\Lokale-LLM\ComfyUI\models\<Ordner>`):

| Datei | Repo / Ordner | Größe | SHA-256 (Anfang) | genutzt |
|---|---|---|---|---|
| `birefnet.safetensors` | BiRefNet / `background_removal` | 0,44 GB | `9ab37426bf4d` | ja: schnelles Freistellen |
| `lucida.safetensors` | BiRefNet / `background_removal` | 0,88 GB | `a43e3dd84cbe` | nein (Reste) |
| `depth_anything_3_mono_large.safetensors` | Depth-Anything-3 / `geometry_estimation` | 1,34 GB | `9b44eda5bedb` | nein (kein Gewinn) |
| `sam3.1_multiplex_fp16.safetensors` | sam3.1 / `checkpoints` | 1,75 GB | `9ba99c92703c` | ja: Stelle per Wort |
| `sdpose_wholebody_fp16.safetensors` | SDPose / `checkpoints` | 1,92 GB | `63d01f9a7494` | ja: Pose-Skelett |
| `qwen_image_2.1_int8_convrot.safetensors` | Qwen-Image-2.1 / `diffusion_models` | 7,26 GB | `cb74113cb03f` | ja: neue Bildaufträge |
| `qwen3vl_8b_int8_convrot.safetensors` | Qwen-Image-2.1 / `text_encoders` | 9,35 GB | `8bfd0f6e12ab` | ja: neue Bildaufträge |
| `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` | Qwen-Image-2.1 / `text_encoders` | 9,47 GB | `9182abae56fe` | ja: Wunsch ausformulieren |

Nicht geladen: der Prompt-Enhancer für Bearbeitungen (`…pe_i2i…`, 9,47 GB; Bearbeitungsprompts sind über die Rezepte
schon genau), RT-DETR und SAM-3D-Body (kein Einsatz im Studio).

**Versuche** (Vorschau direkt über ComfyUI mit den Abläufen der Werkstatt, feste Nummern 11 und 22, Turbo; Tafeln im
Scratchpad der Sitzung):

| Nr. | Was | Ergebnis | Entscheidung |
|---|---|---|---|
| B3 | INT8 statt BF16 (Bildmodell, dazu INT8-Text-Encoder) | gleiche Nummer, 1328²: mit schneller Aufmerksamkeit Turbo 12,3 → 7,1 s, Standard 34,6 → 16,5 s; ohne 4 MP Turbo 37,8 → 25,5 s, Hochskalieren 2 MP 30,6 → 22,4 s. 3090 9,1–10,4 statt 15,7–16,9 GiB (Hochskalieren 14,1 statt 20,5). Mittlere Abweichung zu BF16 0,9–4,1 von 255, Aufbau gleich; Gesicht, Hände, Schrift und 4 MP vergrößert verglichen: kein Unterschied in der Qualität zu sehen | übernommen für neue Aufträge (`int8`) |
| – | Freistellen mit BiRefNet bzw. Lucida (6 Bilder: Wiese, 2 Porträts, Hund, Praxis 4 MP, Behandlung) | BiRefNet je etwa 1 s, 6 von 6 sauber, feine Haare als weiche Kante (Qwen schneidet sie ab), auf dunklem Grund heller Saum an halbdurchsichtigen Kanten; ließ das Kissen unter dem Hund von selbst weg. Lucida 2 von 6 mit Resten (Kissen-Schleier, Stück Liege) | BiRefNet übernommen, wenn nichts beschrieben ist (`verfahren: schnell`) |
| B1 | Maske per Wort (SAM3.1, 15 Suchen in 5 Bildern) | je etwa 1 s; 14 von 15 richtig (Hände, Hund, Fahrrad, Gesicht, Haare, Frau, Baum, Liege englisch); ohne Anzahl nur der sicherste Treffer, „hand:4“ fand beide Hände; deutsch „Hund“, „Fahrrad“, „Hand“ richtig, „Liege“ fand die Therapeutin | übernommen als „Stelle per Wort“ beim Verbessern (`stelle`) |
| B2 | Pose-Skelett (SDPose) und damit Pose übernehmen (Winken, Arme zur Seite mit Band, Band über dem Kopf; deutsch und englisch, je 2 Nummern) | Skelett je 1–2 s; Haltung 12 von 12 wie vorgegeben, Person aus Bild 2 erkennbar. Das Band hing 3 von 4 wie ein Schal und lag 4 von 4 vor dem Gesicht, wo die Hände im Vorbild auf Augenhöhe waren. Gegenprobe nur mit Text (Arme weit zur Seite): 2 von 2 – einfache Haltungen gehen auch ohne | übernommen: Art „Pose“ und Vorschlag „Pose übernehmen“ |
| B2 | Mehrere Personen im Skelett (nachträglich, 10:55): SDPose nimmt ohne Rahmen das ganze Bild als eine Person (Behandlung: nur die Therapeutin). SAM3 („person:6“) liefert Personenrahmen für den Eingang `bboxes` | Behandlung beide Personen; Einzelpersonen (Wiese, Porträt, Band) gleich wie ohne; Raum ohne Person: leeres Skelett, kein Fehler; dicht überlappende Personen (Übung mit Band) weiter nur eine; ~1 s mehr. Zwei-Personen-Skelett als Bild 1 mit getauschten Rollen: Aufbau, Ausschnitt und Griffe 2 von 2 wie im Foto (nur Text: Handlung 2 von 2, aber anderer Aufbau) | übernommen als Feld `personen` für neue Pose-Aufträge (ohne Download, SAM3 ist schon da) |
| B2 | Tiefenkarte (Depth Anything 3) als Bild 1, Behandlungsraum → Wartezimmer | Aufbau blieb, die Liege aber auch; mit dem Foto selbst als Bild 1 gleich gut und detailreicher. Beim Eingang mit Schaufenster war die Tiefenkarte fast leer | nicht übernommen |
| – | Prompt-Enhancer (Qwen3.5 9B INT8, Systemtext der ComfyUI-Vorlage `image_qwen_image_2_1_t2i`), 4 kurze deutsche Wünsche × 2 Nummern | Schulterbehandlung direkt 0 von 2 passend, ausformuliert 2 von 2; Wartezimmer direkt wie ein Labor, ausformuliert stimmig; Hund und Dehnen schöner, aber beide Hunde Golden Retriever. Einmal ein erfundener Wandspruch mit Tippfehler. Auf der 3090 15–34 s statt 7 s (Spitze 18,7 GiB); auf der 3080 neben dem Text-Encoder 517 s | übernommen als Häkchen „Wunsch ausformulieren lassen“ (nur neues Bild, Enhancer fest auf gpu:0) |

Antwort auf die INT8-Frage: Das INT8-Modell ist dieselbe Qwen-Image-2.1 in 8-Bit-Ganzzahlen statt 16-Bit-Gleitkomma,
halb so groß. Die 3090 kann INT8 besonders schnell rechnen; deshalb brauchen Bilder etwa die Hälfte der Zeit und
6 GiB weniger Grafikspeicher, bei gleicher Qualität in unseren Vergleichen.

Umsetzung:
- `werkstatt\studio.py`: `qwen_dateien` (INT8 je Auftrag), `_mit_ausformulieren` + `ausformulieren_text`/
  `ausformulieren_wunsch`, `freistellen_schnell_graph`, `pose_graph`, `finden_graph`, `png_lesen` (PNG-Leser für
  8 Bit, alle Filter), `maske_hochrechnen`; neue Art `pose` (`HILFS_ARTEN`: ohne Qwen, keine Stufe, `anzahl` 1;
  mit `personen` SAM3-Personenrahmen für SDPose);
  `_pruefen` nimmt `int8`, `verfahren`, `ausformulieren` an, `_verbessern_pruefen` statt einer Maske auch `stelle`;
  `_stelle_finden` sucht vor dem Verbessern und speichert die Maske am Auftrag; `…_verfuegbar` je Modell in
  `einstellungen()`; Zeitschätzung mit eigenem INT8-Median; Grafikspeicher `bedarf_hilfe` bzw. mit Enhancer 20 + 4
  GiB; `einstellungen_aus_graph` erkennt INT8, Enhancer, Pose und BiRefNet im gespeicherten Ablauf; Begleitdaten
  `int8`, `verfahren`, `stelle`, `ausformulieren`, `prompt_ausformuliert`. Ohne die neuen Felder bleibt jeder Ablauf
  wie bisher.
- `werkstatt\ausformulieren_t2i.txt`: Systemtext des Enhancers aus der ComfyUI-Vorlage (unverändert übernommen).
- `werkstatt\config.json`: `modelle.unet_int8`/`clip_int8`, Abschnitte `int8`, `ausformulieren`, `pose` (mit
  `personen`), `freistellen.schnell_modell`, `verbessern.finden`, `bedarf_hilfe_mib` (6 GiB auf der 3090), jeweils mit
  `grund`.
- `studio.js`/`index.html`: Art „Pose“ (nur, wenn verfügbar), Feld „Oder Stelle per Wort finden“ beim Verbessern,
  „Was soll bleiben?“ leer = schnell (Qualität und Variation ausgeblendet), Häkchen „Wunsch ausformulieren lassen“,
  Vorschlag „Pose übernehmen“, Großansicht „Pose-Skelett“ bzw. beim Skelett „Als Pose-Vorlage“, Zeilen
  „Ausformuliert“, „Stelle per Wort“, „Verfahren“, „Personen“, Modell „· INT8“; neue Aufträge schicken `int8: true`
  bzw. beim Skelett `personen: true`, „Nochmal“ nur, wenn das Original es hatte. Beim Skelett und beim schnellen
  Freistellen ist „Variation“ aus (jede Nummer gibt dasselbe), beim Skelett auch „Prompt kopieren“. Der Hinweis bei
  mehreren Vorlagen nennt statt „Anzahl 4“ jetzt das Pose-Skelett. Quadrat-Moodboard mit neuer Texturzeile (unten).
  `messungen.py`: Pose-Skelett (· alle Personen), BiRefNet, Zusätze „· INT8“, „· ausformuliert“, „· Stelle per Wort“.
- Skill `bild-video-studio`: `status` meldet die neuen Möglichkeiten, `pose`, `verbessern --stelle`, `freistellen`
  ohne Motiv schnell (`--genau` für Qwen), `bild --ausformulieren`, INT8 automatisch; SKILL.md, `references\webseiten.md`.
  Moodboard-Skill: Ausformulieren nicht für Moodboards. STUDIO.md: Abschnitte 1, 3, 4, 6–12.
- Tests: Werkstatt 109 OK (neu: INT8-Dateiwahl, schneller Freistell-Ablauf, Pose mit und ohne Personenrahmen, Stelle
  per Wort mit PNG-Leser aller Filter und Hochrechnen, Ausformulieren samt Umkehrung, Prüfung der neuen Felder,
  Begleitdaten), Zentrale 11 OK, `node --check` OK.

Prüfung am echten System (27.09.2026, 10:20–10:29, Projekt „Werkstatt-Abnahme“; ComfyUI, Zentrale und Werkstatt
waren nach einem Neustart des PCs aus und wurden gestartet, die Werkstatt zuletzt 10:28 mit dem fertigen Stand):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | INT8 über die Oberfläche | `Bild_00080_` 8,0 s (Turbo, 1328²), pixelgleich zur Probe, Modell „· INT8“ |
| 2 | Alte Bilder unverändert | „Nochmal“ von `Bild_00076_` (BF16, Panorama) → `Bild_00083_` pixelgleich, weiter BF16 |
| 3 | Schnell freistellen | `Freigestellt_00011_` 1,5 s, `_00012_` 0,7 s; Qualität und Variation ausgeblendet |
| 4 | Pose-Skelett und Pose übernehmen | `Pose_00001_`–`_00003_` 1,2–1,9 s, pixelgleich zur Probe; „Als Pose-Vorlage“ setzt Skelett und Vorschlag; `Bearbeitet_00071_` 14,3 s mit Porträt `Bild_00027_`: Haltung und Gesicht stimmen |
| 5 | Stelle per Wort | `Verbessert_00010_` („hand:2“, Turbo, 17,9 s) und `_00011_` („hand“, 29,3 s): Masken genau auf den Händen; da die Hände schon gut waren, nur 0,01–0,24 % der Pixel geändert |
| 6 | Ausformulieren | `Bild_00081_` 20,1 s (erfand ein Poster „PHYSIOTHERAPY“), mit „ohne Schrift“ `Bild_00082_` 34,4 s ohne Schrift; „Nochmal“ `Bild_00081_` → `Bild_00084_` gleicher Text, gleiche Pixel |
| 7 | Oberfläche | Sichtbarkeit der neuen Felder je Art, Großansicht, Schätzungen; keine Fehler in der Konsole; Formular danach wiederhergestellt |
| 8 | Moodboard-Rezepte mit INT8 (über den Skill, gleiche Prompts und Nummern wie die Abnahme 3j, 10:35–10:45) | 17–22 s statt ~37 s. Quer 11, 22, 33 und Hoch 11 fehlerfrei (`Bild_00086_`, `_00093_`, `_00094_`, `_00087_`). Quadrat: Texturkachel 2 von 3 in zwei Kacheln zerfallen (`_00085_`, `_00089_`; `_00088_` fehlerfrei) – mit der Texturzeile des Hochformats 3 von 3 fehlerfrei (`_00090_`–`_00092_`). Quadrat-Rezept in `studio.js` und im Moodboard-Skill entsprechend geändert |
| 9 | Neue Skill-Befehle (10:49–10:50) | `pose` → `Pose_00004_` 1,5 s; `freistellen` ohne Motiv → `Freigestellt_00013_` 0,8 s (BiRefNet); `verbessern --stelle "raised hand"` → `Verbessert_00012_` 13,1 s, Maske genau auf der erhobenen Hand, neue Hand mit fünf Fingern; `bild --durchsichtig --ausformulieren` und `verbessern` ohne Stelle abgelehnt. Ein Aufruf ohne `--projekt` landete im Studio-Wurzelordner und wurde mit „Verschieben“ nach Werkstatt-Abnahme gelegt (`Freigestellt_00001_ (2)`) |
| 10 | Alle Personen im Skelett (Werkstatt neu gestartet 10:57) | `Pose_00005_` aus der Behandlung `Bild_00077_`: beide Personen (vorher `Pose_00004_` nur die Therapeutin), 1,4 s, `personen: true`; Großansicht zeigt „Personen: alle“, „Variation“ und „Prompt kopieren“ sind beim Skelett aus |

### Stufe 3m: Videos weiterführen (27.09.2026, fertig)

Auftrag Sascha: „Lösche was wir nicht mehr brauchen. Dann dieses Video mit Watch B anschauen, falls es für dich Sinn
macht“ (YouTube `kqP09NfJXaQ`, „Mini Video Editor Timeline Node for H3!“, ChanonDevs, mit eingefügtem Transkript) und
das Repo `chanon/comfyui-obvpm-timeline`: „Weitere Verbesserungen und neue Workflows planen und erstellen und
ergänzen. Wenn was unklar ist, frag Astra über den Codex-Skill.“

- **Aufräumen:** siehe „Offen“ (171 Testdateien und Probe-Uploads in den Papierkorb).
- **Video nicht mit watch angesehen:** Transkript und Beschreibung lagen vollständig vor, das Repo (GPL-3.0) ließ sich
  lesen. Es speichert je Clip die Latents (`.mctx`) und hält sie per Latent-Maske fest, dazu eine Zeitleiste als
  Oberfläche. Für das Studio zählte das Verfahren, nicht die Oberfläche; die Bilder des Videos hätten nichts gezeigt,
  was nicht im Code steht. Übernommen wurde die Idee, kein Code.
- **Plan:** mit Vorversuchen (unten) als `AI-Knowledge-System\Workspace\Handoffs\2026-09-27 Studio Video weiterführen
  Plan.md`; von Astra (Codex, schreibgeschützt) in fünf Runden geprüft und freigegeben (`… Astra-Review-Log.md`
  daneben). Astras wichtigste Punkte: Zeitgrenzen und Ton exakt an Bildgrenzen, Quellen per eigenem MP4-Leser und
  Prüfsumme prüfen, „keine Antwort“ nie als Stillstand werten, Nochmal ohne neue Rundung.

**Vorversuche** (ComfyUI 0.37, fl2va INT8, Turbo 8 Schritte, 960 × 544; Messgröße: mittlerer Betrag der
Bilddifferenz 0–255 in 240 × 136, „normal“ = Median von Bild zu Bild):

| Versuch | Ergebnis | Entscheidung |
|---|---|---|
| Vorn 39 Bilder (samt Ton) festhalten (`MiniMaxH3AddGuide`, 17k+5 Bilder, 65 Ton-Latents) | Stück getroffen 3,97; Nähte 12,3 / 11,3 bei normal 13,2–14,3, ohne Sprung | übernommen (Verlängern, Verbinden, Schleife) |
| Am Ende 39 Bilder festhalten | harter Schnitt direkt davor (39,2 bei normal 1,1), auch mit Prompt für dieselbe Einstellung (51,8); mit 5 Bildern Ruckeln | verworfen |
| Am Ende ein Endbild (`last_frame` von fl2va) | Naht 2,7 bei normal 1,3–1,6 | übernommen (Davor, Verbinden, Schleife) |
| Ton zusätzlich am Ende anheften | stört das Bild nicht, liegt aber zeitlich falsch | verworfen |
| Schleife mit zwei 39er-Stücken | zwei harte Schnitte (104 / 58) | verworfen; vorn Stück, hinten Endbild: Nähte 2,5 / 3,5 bzw. 3,5 / 6,5 |
| Zusammensetzen mit `ConcatenateVideo` | Bildspur ungeschnittener Datei-Stücke bitgleich (Remux); mit Zeitfenster alles neu kodiert (Abweichung 1,36) | übernommen |

**Abweichungen vom Plan** (bei der Umsetzung gemessen):
- Rollen `ausgang` (Clip davor) und `ziel` (Clip danach) statt `clip`/`clip_danach`: beim Davor-Setzen ist der einzige
  Clip der Clip danach.
- Zeitfenster per `Video Slice` 1 ms vor den Bildgrenzen statt `VideoTemporalCrop`: zusammengesetzte Videos (auch die
  eigenen Ergebnisse) haben ±0,5 ms Zittern in den Zeitstempeln; ein genaues Fenster verlor dann ein Bild.
- Ton nicht je Stück in `CreateVideo`, sondern als ganzer Ton (`complete_audio`), exakt aus `LoadAudio` bzw. dem neuen
  Clip geschnitten: Stücke aus `CreateVideo` laufen durch einen MKV-Puffer mit ms-Zeitstempeln (Zittern, am Ende
  1,3 ms zu kurz).
- H3 rundet die Tonlänge: Bei L mod 3 = 2 (158, 209, 260, 311, 362 Bilder) fehlen 8,3 ms. Solche Clip-Längen bietet
  das Studio nicht an; zu kurzer Quellton (Studio-Videos von 13 und 15 s) wird mit Stille aufgefüllt, auch im
  festgehaltenen Stück. `mp4_info` erlaubt deshalb 25 ms zu kurzen Ton und eine B-Bild-Verzögerung in der Edit-List.
- „Nochmal“ schickt zusätzlich die Prüfsummen der Clips mit (ComfyUI vergibt den Namen der jüngsten Datei nach dem
  Papierkorb neu).
- Warten mit einem Handle auf den ComfyUI-Prozess statt einer gemerkten PID (eine PID kann neu vergeben werden).

Umsetzung:
- `werkstatt\studio.py`: Art `video_weiter` (`VIDEO_ARTEN`), `WEITER_MODI`, `weiter_laenge`/`weiter_laenge_ok`
  (17k+5-Raster, 124–345, ohne L mod 3 = 2), `weiter_bereiche` (Führung, Endbild, neuer Teil, Stücke, Gesamtlänge; Schnitte
  mit Mindestlängen), `weiter_graph`, `datei_pruefsumme`, `mp4_info` (eigener MP4-Leser), `_weiter_quellen`/
  `_weiter_pruefen` (nur Bibliothek, gleiche Größe, bis 60 s, `clip_bilder` für „Nochmal“, `pruefsummen`), erneute
  Prüfung vor der Übergabe in `_rechnen`, Begleitdaten (`modus`, `clip_bilder`, `neu_bilder`, `neu_sekunden`,
  Schnitte, `quellen`), `einstellungen.arten`. Für alle Aufträge: `_comfy_rechnen` hält einen Prozess-Handle und
  wartet bei fehlender Antwort weiter, `_comfy_abbrechen` ohne Frist, `zentrale.halten` alle 20 s in beiden Schleifen.
- `gemeinsam\winapi.py`: `prozess_oeffnen`, `prozess_beendet` (True nur bei bestätigtem Ende), `handle_schliessen`.
- `studio.js`/`index.html`: Art „Weiterführen“ mit „Wie weiterführen?“, Clip-Feldern nur aus der Bibliothek,
  „Reihenfolge tauschen“, „Neues Stück“ (tatsächliche Sekunden je Modus), Kürzen in Sekunden (Rundung angezeigt),
  Schätzung mit neuer und gesamter Länge, Hinweise (zu kurz, ungleich groß, über 60 s), sichtbare Grenzen je Modus;
  Großansicht „Weiterführen:“ mit fünf Knöpfen; Kacheln, Großansicht, „Nochmal“ (mit `clip_bilder` und Prüfsummen),
  „Mit Änderungen“. `messungen.py`: Art „Video weiterführen“ (gezählt wird der gerechnete Clip).
- Skill `bild-video-studio`: `weiter <clip> ["<prompt>"] --modus … [--danach] [--neu] [--schnitt-ende]
  [--schnitt-anfang]`, `status` meldet `weiterfuehren`, `bibliothek` nennt Sekunden; SKILL.md, `references\webseiten.md`.
  STUDIO.md: Abschnitte 1, 3, 7–12. README, AGENTS.md.
- Tests: Werkstatt 131 OK (neu: Längen und Raster, Bereiche aller Modi mit Schnittgrenzen, Zeitfenster, Abläufe aller
  Modi samt Ton-Verkettung und Auffüllen, `mp4_info` an künstlichen MP4-Strukturen mit allen Ablehnungsgründen und an
  allen echten Studio-Videos, Prüfung im Dienst, Prüfsumme vor der Übergabe, Begleitdaten und „Nochmal“, Verlängern
  eines Ergebnisses, Warten und Abbrechen mit simulierter Uhr über 120 s, echtes Prozessende, Zeitschätzung), Zentrale
  11 OK, `node --check` OK.
- Zusätzlich (aus der Abnahme): **Zeitschätzung für Videos** neu. Die Zeit je Schritt wächst etwa mit dem Quadrat
  von Pixeln × Bildern, festgehaltene Bilder und Start-/Endbilder rechnen mit; die lineare Schätzung ergab für
  175 + 39 Bilder 197 statt 301 s. Jetzt `Grundzeit 30 s + Schritte × Sekunden je Schritt × (Pixel × wirksame
  Bilder / 960·544·124)²` (`video_zeit`, Konfiguration `video.zeit` mit 12,4 s, gelernt aus eigenen Läufen ohne
  Referenz-Clips), in Dienst und Formular gleich. Exponent aus sechs Messpunkten (13,8 s bis 93 s je Schritt): 2,0
  passt auf ±15 %, 1,7 wich beim größten Clip um −24 % ab.

Prüfung am echten System (27.09.2026, 12:57–14:17 mit Pause, Projekt „Werkstatt-Abnahme“, 8 Schritte, Nummer 11, 960 × 544;
gemessen mit eigenen Skripten: Bildzahl, Pakete und dekodierte Bilder gegen die Quelle, Ton-Versatz per
Kreuzkorrelation, Sprung an jeder Naht gegenüber dem Median der Nachbarbilder, Sichtprüfung der Standbilder). Parallel
arbeitete eine andere Sitzung mit dem Studio (Projekt „Haltungsanalyse Sichtprobe“); ihre Bilder wurden vorgelassen,
meine wartenden Testvideos dafür kurz zurückgestellt und danach unverändert wiederholt:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Verlängern über den Skill (`Video_00007_` → `Video_00009_`, Prompt des Clips) | 260 Bilder wie geplant, 301 s; Original Paket für Paket bitgleich; Ton-Versatz 0,0 ms am Anfang und Ende des Originalteils, Ton 1,3 ms kürzer als das Bild; Naht 11,6 bei sonst 12,3 – nicht zu sehen |
| 2 | Kette: `Video_00009_` noch einmal verlängern (`Video_00014_`, neuer Prompt „setzt sich hin“) | 396 Bilder, 312 s; die 260 Bilder der Quelle (selbst zusammengesetzt, mit Zittern) bitgleich, die ersten 124 über beide Runden dieselben Pakete wie `Video_00007_`; Versatz 0,0 ms; Naht 13,1 bei sonst 10,2; der Hund wird langsamer und setzt sich wie beschrieben. Ton des Originals nach einer Runde 21,6 dB, nach zwei 18,7 dB Abstand zum Original |
| 3 | Davor setzen (`Video_00006_` → `Video_00010_`, eigener Prompt „aus der Tür in den Raum“) | 247 Bilder, 141 s; Clip danach bitgleich, Ton-Versatz 0,0 ms (belegt: das neue Stück hat genau so viel Ton wie Bild); Naht 3,8 bei sonst 1,9. Das Stück erfand einen warmen Sonnenstrahl, den der Clip am Anfang nicht hat: in den letzten 7 Bildern 20 % dunkler – als Hinweis in Formular, STUDIO.md und Skill |
| 4 | Verbinden mit Kürzen (`Video_00008_` Ende −0,5 s → `Video_00002_` Anfang −0,25 s, `Video_00011_`) | 365 Bilder, 319 s; Schnitte genau (112 + 135 + 118 Bilder), einmal neu kodiert (Abweichung 0,87), Ton gleich lang, Versatz 0,0 ms. **Zweiter Übergang ein harter Schnitt** (Sprung 60 bei sonst 2): Der Prompt beschrieb nur eine Fahrt im ersten Raum, das Stück blieb dort und sprang erst im letzten Bild zum ganz anderen Raum des zweiten Clips. Quelltext geprüft: `MiniMaxH3AddGuide` hängt an die Schlüsselbilder an, das Endbild ging nicht verloren. Die Vorversuche hatten Ziel und Anfang aus demselben Clip |
| 5 | Verbinden derselben Clips mit beschriebenem Weg („… durch die offene Glastür in den Nebenraum, einen kleineren, hellen Behandlungsraum mit … gepolsterter weißer Behandlungsliege, einem Vorhang …“), 9,9 s neu, ohne Kürzen (`Video_00015_`) | 485 Bilder, 705 s (neue Schätzung 675 s); beide Clips Paket für Paket bitgleich (umverpackt vor und hinter dem neuen Teil); Ton 1,7 ms kürzer als das Bild. Die Kamera fährt durch die Tür in den Nebenraum und kommt genau auf dem ersten Bild des zweiten Clips an: Sprung 3,0 bei sonst 1,0 (vorher 60). Geändert waren Prompt und Länge zugleich |
| 6 | Schleife über die Oberfläche (Großansicht „Schleife schließen …“, Erstellen; `Video_00013_`) | 259 Bilder, 327 s; `neu_sekunden` 5,625 und `clip_bilder` 175 kamen genau an; Original bitgleich; Wiederholstelle Sprung 5,3 bei sonst 2,8, letztes Bild steht fast wie Bild 0; die Kamera kehrt für den Rückweg sichtbar um |
| 7 | Verlängern eines Clips mit zu kurzem Ton (Probe `_versuche/schleife2`, 158 Bilder, Ton 8,3 ms kurz; `Video_00012_`) | 243 Bilder, 208 s; Auffüllen im festgehaltenen Stück und im Stück wirkt (Ton im Ergebnis nur 1,0 ms kürzer); Original bitgleich, Naht 4,9 bei sonst 3,1. Inhaltlich fuhr die Kamera weiter auf die dunkle Tür zu, mit der die Quelle endet, statt „an den Pflanzen vorbei“ – die Bewegung setzt sich stärker durch als der Prompt |
| 8 | Abbrechen während der Rechnung (R4b nach 83 s, damit vier wartende Bilder der anderen Sitzung nicht 10 min warten) | ComfyUI führte den Auftrag nach 1,6 s nicht mehr, die Werkstatt meldete „Abgebrochen.“ nach 2,0 s, die Anmeldung bei der Zentrale endete nach 2 s (Protokoll, ganze Sekunden) – Reihenfolge stimmt; dazwischen „Wird abgebrochen; ComfyUI beendet noch den laufenden Rechenschritt …“. Danach „Wiederholen“ |
| 9 | Abbrechen während des Dekodierens (eigener Auftrag, Abbruch 1 s nach Beginn des Video-Dekodierens, 170 s nach dem Anlegen) | ComfyUI meldete „Processing interrupted“ im Video-VAE und führte den Auftrag nach 1,8 s nicht mehr; die Werkstatt meldete „Abgebrochen.“ nach 2,2 s, die Anmeldung endete nach 2 s; keine halbe Datei. Der kurze Moment des Zusammensetzens danach (wenige Sekunden) ließ sich nicht gezielt treffen; er folgt derselben Warte-Logik (Unit-Tests) |
| 10 | „Nochmal“ ohne Neustart von ComfyUI (eine andere Sitzung arbeitete gerade mit dem Studio; ComfyUI hatte die Ergebnisse nach anderen Aufträgen nicht mehr im Speicher, die volle Rechenzeit belegt das Neurechnen) | über die Oberfläche: weitergeführt `Video_00010_` → `Video_00016_` (136 s) und altes Video aus Text `Video_00006_` → `Video_00017_` (125 s): Bild- und Tonspur jeweils Paket für Paket gleich, dekodierte Bilder und Ton gleich; nur Auftragsnummer, Quelle und beim Weiterführen `neu_sekunden` in den eingebetteten Daten neu. Ältere Videos bleiben also unverändert |
| 11 | Oberfläche (Browser) | Art „Weiterführen“ mit Modus, Clip-Feldern ohne „Aus Datei“, „Neues Stück“ je Modus (Davor 5,1–14,3 s, sonst 3,5–12,8 s), Kürzen nur für die passenden Clips, Warnung bei zu starkem Kürzen („bleiben vom Clip 0,2 s …“), „Reihenfolge tauschen“, Moduswechsel übernimmt den Clip in die richtige Rolle; Großansicht „Weiterführen:“ mit fünf Knöpfen; Kacheln „Video weitergeführt (verlängert) · … 10,8 s, davon 5,7 s neu“; Großansicht mit „Neues Stück“, „Gekürzt“ und Rollen der Clips; „Mit Änderungen …“ übernimmt Modus, beide Clips, Schnitte (0,5/0,25 s), Länge, Nummer und Qualität; „Nochmal“ schickt `clip_bilder` und Prüfsummen. Mit einem Dienst älteren Stands (ohne `zeit`) lässt das Formular die Zeitangabe weg, statt abzubrechen |
| 12 | Für die Homepage (Frage Sascha: „muss immer Ton erzeugt werden?“) | MiniMax-H3 rechnet Ton immer mit (Quelltext: Ton und Bild in einer Folge, kein Modus nur fürs Bild), bei 5 s etwa 400 Ton- gegen 18.900 Bild-Teile, rund 2 % der Rechenarbeit. `studio.py export Video_00013_ … .webm --poster` ergab nur eine VP9-Bildspur ohne Ton, 1,56 MB für 10,8 s, dazu das Posterbild |
| 13 | Werkstatt neu gestartet (14:13, in einem ruhigen Moment ohne Aufträge) | `einstellungen.video.zeit` mit Exponent 2,0; aus den eigenen Läufen gelernt 12,34 s je Schritt (Konfiguration 12,4 s). Formular: Video aus Text 5 s „etwa 2 min“ (gemessen 125–139 s), Verbinden mit 5,6 s neu „etwa 5 min“ (gemessen 319–327 s); vorher „etwa 3 min“ für 301–327 s |

### Bewertet 04.10.2026: „MiniMax H3 on Steroids: Hollywood Multi-Scene Long Videos“ (nur gelesen, nichts geändert)

Quelle: YouTube `TY8bAoM9jWc` (The AI Brief, 03.10.2026), Beschreibung und Transkript von Sascha eingefügt. Gelesen:
Repo `ethanfel/ComfyUI-MiniMaxH3-Contex-Loop`, `LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler` und die Modellseiten.
Video nicht mit watch angesehen (Code und Modellseiten sagen mehr, ein ausgesuchtes Beispiel belegt wenig). Kein
Download, keine Änderung. „Hollywood-Langvideo“ heißt im Video: drei Abschnitte à ~10 s, zwei Figuren reden weiter.

| Baustein | Bewertung |
|---|---|
| **Context Loop** (GPL-3.0) | Szenen nacheinander, Fortsetzung über denselben Kernknoten `MiniMaxH3AddGuide` wie Stufe 3m (setzt ihn voraus), reicht Latents statt dekodierter Bilder weiter; dazu Szenenplan, „Review Gate“ (je Szene annehmen, neu würfeln, abbrechen), Zwischenstände, Zusammensetzen mit ffmpeg. Die Mechanik hat das Studio seit 3m (bitgleich, Ton exakt); neu wäre nur der Ablauf |
| **Realism-People-LoRA** (`fal/MiniMax-H3-Realism-People-LoRA`, Auslöser `r34l1sm`, t2v/i2v/r2v, Rang 32, Stärke 1,0 bzw. 0,6–0,8, Lizenz wie H3) | gegen Plastikhaut, für Gesichter in Nahaufnahme; eine Datei, normaler LoRA-Lader. Aussichtsreichster Einzeltest |
| **DualPass mit Latent-Upscaler** (MIT, eigene Knoten) | erst ~0,7 MP, Latent ×1,5, zweiter Durchgang. Videos über 960 × 544 wären eine echte Lücke, aber nach `video_zeit` (über den Messbereich hinaus hochgerechnet) etwa 7 min je Schritt für 10 s bei ~1,6 MP; laut Autor „spart Zeit, nicht VRAM“. Nur für kurze Clips denkbar |
| **LMS-LoRA** (`Alissonerdx/Minimax-H3-ComfyUI`) | Schärfen anhand eines ausgerichteten Quellvideos über `MiniMaxH3AddGuide`; laut Autor Forschungsmodell, im Video „notfalls weglassen“. Nicht vorrangig |
| **Singularity-Modell** (`WarmBloodAban/Minimax-h3_Singularity`) | Community-Mischung aus ref/fl-Checkpoints, nur Werbeangaben, keine Messungen. Nicht übernehmen: ersetzt das offizielle Modell, „Nochmal“ alter Videos wäre nicht mehr gleich |
| KJNodes, VHS, rgthree, Easy-Use | nicht nötig, das Studio bleibt bei Kernknoten. Die Turbo-LoRA ref2v (4 Schritte) ist schon da |

- **Prompt-Regel** (übernehmenswert, noch nicht in STUDIO.md): gemeinsamer Teil (Figuren, Ort, Licht, Stil, ggf.
  Auslösewort) getrennt vom Szenenteil (Handlung, Kamera, Dialog); Dialog nie in den gemeinsamen Teil.
- **Lücke im Studio:** Weiterführen rechnet das neue Stück ohne Referenzbilder der Figuren (fl2va). In 3m waren nur
  Hund und Räume zu sehen; ob Gesichter über mehrere Abschnitte abweichen, ist ungeprüft. Der Workflow im Video gibt
  Referenzbilder (Ref2VA) und Fortsetzung zusammen in jede Szene.
- Auffällig: keine Rechenzeiten genannt; der Autor hat 16 GB Grafikspeicher und braucht 46 GB Arbeitsspeicher.

Mögliche nächste Schritte (nur auf Auftrag, in dieser Reihenfolge):
1. Realism-LoRA laden (Download-Ok nötig) und vergleichen: gleicher Prompt und Nummer, mit/ohne, Nahaufnahme, mit Turbo.
   **Erledigt 05.10.2026, Stufe 3o.**
2. Vorversuch Referenzbilder + Weiterführen mit Kernknoten (ref2va + `MiniMaxH3AddGuide`), ohne Download.
   **Erledigt 05.10.2026 (Stufe 3p): kein Gewinn, nicht eingebaut.**
3. Bei Erfolg Art „Szenenfolge“: gemeinsamer Teil + Szenen, Szene für Szene „Passt“/„Nochmal“, auch für `ki-werbevideo`.
   **Erledigt 05.10.2026, Stufe 3p (Entscheidung Sascha: bauen, ohne Referenzbilder).**
4. DualPass nur, wenn 960 × 544 zu weich ist; zuerst mit 5-s-Clips messen. Nicht beauftragt.

Offene Frage an Sascha: Sind längere Videos mit sprechenden Personen (YouTube, Werbung) gewollt? Davon hängt Schritt 3
ab; für Hintergrundvideos reicht 3m. Beantwortet mit dem Auftrag vom 05.10.2026 (Szenenfolge gebaut).

### Bewertet 04.10.2026: „I Tested MiniMax H3 for Static Images“ (nur gelesen, nichts geändert)

Quelle: YouTube `vy-oWQJwNgw` (CG Pixel, 04.10.2026), Beschreibung und Transkript von Sascha eingefügt. Gelesen: Repo
`shootthesound/ComfyUI-Fizgig-H3-Still` und `RealRebelAI/MiniMax-H3-LongVideos_OPTIMIZED`. Ergebnis: **nicht einbauen.**

- **Was es ist:** H3 als Bildmodell. „Fizgig H3 Still Latent“ erzeugt ein echtes Ein-Bild-Latent (sonst mindestens
  5 Bilder), „Fizgig H3 Still Decode“ dekodiert gekachelt, weil der normale VAE-Decode eines Einzelbilds Streifen gibt
  (MIT, keine Modelle oder Pakete). Laut Knoten-Autor gut erst ab ~3 MP, darunter „spürbar schwächer“; Bearbeiten über
  Referenz („<Picture 1>“) geht. Der Videoautor macht damit Charakterblätter aus einem Eingangsbild.
- **Gegen das Studio:** Im Video 8 Schritte ~3 min, 10 Schritte ~6 min (kleine Karte), dazu laut Autor doppelte Posen
  und einmal ein fehlender Arm (Abhilfe 16–25 Schritte). Das Qwen-Rezept „Charakterblatt“ liefert 1920 × 1088 in ~24 s
  (Turbo), in 3e mit vier Ansichten plus Porträt und gleichem Gesicht. Bei uns käme das Umladen Qwen ↔ H3 auf der 3090
  dazu. Die „bessere Prompttreue“ ist nicht belegt, ein Vergleich mit einem Bildmodell fehlt.
- **Einzige Idee:** Ein Charakterblatt aus H3 selbst könnte als Referenz für Videos (ref2va) die Figur besser halten –
  Vermutung, nicht gezeigt. Erst prüfen, wenn Vorversuch 2 oben zeigt, dass Gesichter mit Qwen-Blättern abweichen; dann
  Qwen-Blatt gegen H3-Blatt als Referenz.
- **Übrige Links:** LongVideos_OPTIMIZED (Abschnitte ~15 s mit Figurenblatt, wie Context Loop) hat eine Lizenz ohne
  Weitergabe und mit Inhaltsbeschränkungen – nein. „Fuse Delta“-Modell: Community-Mischung, Einwände wie bei
  Singularity. INT8-VAE (Kijai) und Tempo-Knoten (SLA-Attention u. a.): nicht nötig, INT8 und Turbo sind da.

### Bewertet 04.10.2026: „Qwen Image 2.1 … Any Angle, Head & Body Swap Loras“ (nur gelesen, nichts geändert)

Quelle: YouTube `i9A99RNOe4A` (Ok Todd AI, 04.10.2026), Beschreibung und Transkript von Sascha eingefügt. Gelesen: die
Modellseiten `lilylilith/QI_2.1_AnyAngle` und `Alissonerdx/BFS-Best-Face-Swap`. Ergebnis: **nicht einbauen.**

| LoRA | Bewertung |
|---|---|
| **AnyAngle** (Apache 2.0) | Braucht neben dem Original eine grobe Ansicht aus dem Zielwinkel aus einem Gaussian Splat oder 3D-Modell (Tripo Splat, Trellis2 o. Ä.), im 3D-Fenster gedreht und abfotografiert; Prompt „Change the camera angle from <image2> to <image1>.“, CFG 3, 20+ Schritte (ohne Turbo). Laut Autor verformte Gesichter bei ungenauem 3D-Modell. Nein: bräuchte ein weiteres Modell, eigene Knoten und eine 3D-Ansicht zum Drehen in der Werkstatt; der Vorschlag „Andere Perspektive“ (nur Text, 3f), „Pose übernehmen“ und „Charakterblatt“ decken den üblichen Bedarf |
| **BFS Head Swap v1.1** (MIT; Dateien `bfs_head_v1.1_qwen_2.1`, `…_alternative_…`, `bfs_head_v1_…`) | Zwei Bilder, Reihenfolge laut Anleitung oft erst Körper, dann Gesicht; normaler LoRA-Lader. Im Video 4–5 min, der Autor selbst: Ähnlichkeit „80–90 %“. Das Rezept „Kopf tauschen“ (Qwen ohne LoRA, ~15 s Turbo) hielt in der Probe Aufbau und Haltung. Höchstens Vergleich, falls Gesichter beim Tauschen nicht ähnlich genug werden (z. B. Praxis-OS-Figuren). Bedingung der LoRA: nur eigene oder erfundene Personen bzw. mit Einwilligung |
| **BFS Body Swap v1.0** | Pose bleibt, andere Person; im Video leichte Verschiebung am Rand, Schuhe übernommen, ~2 min. Nein: „Person einsetzen“ und „Pose übernehmen“ (12 von 12) decken das ab |

Möglicher nächster Schritt (nur auf Auftrag, Download-Ok nötig): „Kopf tauschen“ gegen BFS Head v1.1 an denselben
Bildern vergleichen, gewertet nach Ähnlichkeit des Gesichts.

### Stufe 3n: Vorbild für die Stelle (05.10.2026, fertig)

Frage Sascha: „Kann man aktuell NICHT, wenn man ein Bild verbessern will, ein anderes Bild als Referenz hinterlegen?“ –
richtig, Verbessern gab Qwen nur den Ausschnitt als Bild 1. Auftrag: „ja“, danach die sinnvollen Punkte aus den
Videos vom 04.10.2026, alles nacheinander mit Tests.

**Vorversuche** (ComfyUI 0.37, Turbo, INT8, direkt an ComfyUI mit `verbessern_graph` + Bild 2, nur Vorschau, nichts im
Studio; Ausgangsbilder aus „Werkstatt-Abnahme“):

| Fall | Ergebnis | Entscheidung |
|---|---|---|
| Kopf der Therapeutin (`Bild_00008_`) → Frau aus `Bild_00027_` | mit Vorbild 3 von 3 erkennbar die Frau aus Bild 2, ohne (nur beschrieben) 2 von 2 eine andere, jüngere; 2 von 3 lächelten wie im Porträt, obwohl „ernst“ verlangt | übernommen |
| Logo (`Vorlage_Logo-Test.png`) aufs grüne Oberteil von `Bild_00027_` | Symbol 4 von 4 richtig (ohne Vorbild ein anderes Symbol), Schriftzug 3 von 4 („LINDENHOE“), Unterzeile 0 von 4 lesbar | übernommen, Schrift siehe unten |
| Hund aus `Bild_00005_` auf den Boden von `Bild_00001_` | Fell und Zeichnung mittel ähnlich; 2 von 4 nur Kopf und Pfoten (so zeigt ihn Bild 2); ohne Vorbild einmal eine blaue Kreidelinie („An der markierten Stelle …“, 1 von 11 Läufen mit diesen Worten) | Hinweis: Bild 2 soll das Ganze zeigen; Vorschläge ohne „markierte Stelle“ |
| Zeit | +6 s (10 → 16 s bei 1 MP Arbeitsgröße, 20 → 26 s bei 1,8 MP) | Schätzung: 1 + 0,55 × Vorbild-MP / Arbeits-MP |
| Bild 2 in Originalgröße (`resolution` 0 gilt für alle Bilder) | nicht probiert: würde ein 2-MP-Porträt voll mitrechnen | Bild 2 per `ImageScaleToTotalPixels` auf 1 MP, Bild 1 bleibt in Arbeitsgröße (sonst verschiebt sich die Änderung) |

**Umsetzung:**
- `werkstatt\studio.py`: `verbessern_graph(…, vorlagen)` hängt das Vorbild als `images.image_2` an (Knoten 110/111);
  ohne Vorbild unverändert. Neue Rolle **`vorbild`** (nicht `vorlage`: sonst gingen Vorlagen vom Bearbeiten beim
  Wechsel der Art unbemerkt als Bild 2 mit), höchstens `verbessern.vorlage.max` (1). Mit Vorbild ist der Ausschnitt
  doppelt statt dreifach so groß wie die Markierung (`vorlage.ausschnitt_faktor` 2), auch bei „Stelle per Wort“.
  Zeitschätzung `_vorlage_faktor`; solche Läufe zählen nicht für die gelernten Sekunden je Schritt.
  `einstellungen.verbessern` meldet `max_vorlagen`, `vorlage_megapixel`, `vorlage_zeitfaktor`.
- `config.json`: `studio.verbessern.vorlage` (max 1, 1 MP, Zeitfaktor 0,55, Ausschnitt-Faktor 2, Grund).
- Oberfläche (`studio.js`): beim Verbessern unter der Markierung „Vorbild für die Stelle“ (Aus Datei …), in der
  Großansicht eines anderen Bildes „Für die Stelle“ (nur, wenn gerade eine Stelle verbessert wird), Chip „Bild 2: …“,
  Schätzung mit Vorbild, „Mit Änderungen“ übernimmt das Vorbild, „Stelle verbessern …“ aus der Bibliothek beginnt ohne
  altes Vorbild. Vorschläge „Kopf nach Vorbild“, „Logo nach Vorbild“, „Gegenstand nach Vorbild“.
- Skill `bild-video-studio`: `studio.py verbessern … --vorbild <Bild>`, `status` meldet `vorbild`. STUDIO.md
  (Abschnitte 1, 3, 6, 7, 10–12), SKILL.md, `references\webseiten.md`.
- Tests: Werkstatt 135 OK (neu: Ablauf mit Vorbild und ohne unverändert, Rollen und Höchstzahl, Begleitdaten,
  Schätzung, gelernte Zeit ohne Vorbild-Läufe, kleinerer Ausschnitt auch bei Stelle per Wort, Übergabe an ComfyUI
  direkt aus der Bibliothek), Zentrale 11 OK, `node --check` OK.

**Nachjustiert bei der Abnahme:** Mit dem dreifachen Ausschnitt war der Logo-Schriftzug über den Skill 0 von 4 richtig
(„LINDENHOE“; auch ausgeschrieben in Anführungszeichen 0 von 2) und der Gegenstand (Sitzpouf aus einem Produktfoto,
`Bild_00093_`) 2 von 6 vollständig, sonst am Rand der Markierung halbiert oder gar nicht da. Vergleich am selben Fall:
doppelter Ausschnitt (Arbeitsgröße 1120 × 960 statt 1088 × 960 für ein Drittel der Fläche) Schriftzug 2 von 2 richtig,
Pouf 3 von 3 vollständig, Kopf weiter erkennbar; größere Arbeitsfläche (1408 × 1280) 1 von 2 richtig samt Unterzeile,
einmal das „F“ am Rand abgeschnitten, 26 statt 16 s. Übernommen: doppelter Ausschnitt mit Vorbild.

Prüfung am echten System (05.10.2026, Projekt „Werkstatt-Abnahme“, Turbo, INT8):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Oberfläche: `Bild_00008_` „Stelle verbessern …“, Kopf gemalt (5,1 %), Porträt per Großansicht „Für die Stelle“, Vorschlag „Kopf nach Vorbild“, 2 Variationen (dreifacher Ausschnitt) | Feld, Chip „Bild 2: Bild_00027_.png“, Schätzung „mit dem Vorbild als Bild 2“; `Verbessert_00001_` ernst und erkennbar die Frau aus Bild 2, `_00002_` dieselbe Person, aber lächelnd. 22,7 s / 9,8 s (Schätzung 12 s). Geändert 5,5 % der Pixel, außerhalb des Ausschnitts kein einziges. 3090 Spitze 15,0 GiB (geplant 16) |
| 2 | Großansicht, „Vorher zeigen“, „Mit Änderungen“, „Nochmal“ | Vorlagen „Original: Bild_00008_.png, Vorbild für die Stelle: Bild_00027_.png“; Vorher zeigt das Original; „Mit Änderungen“ übernimmt Vorbild, Text, Turbo, Nummer und Markierung; „Nochmal“ (`Verbessert_00003_`) Pixel für Pixel gleich `_00001_` |
| 3 | Skill, Vorschlag „Logo nach Vorbild“, Rechteck, 2 Nummern (doppelter Ausschnitt) | `Verbessert_00014_`, `_00015_`: Symbol und „PHYSIO LINDENHOF“ richtig, Unterzeile weggelassen; 14,5 s / 5,7 s |
| 4 | Skill, „Gegenstand nach Vorbild“ (Sitzpouf `Bild_00093_`), kleines Rechteck neben der Liege | `Verbessert_00016_`, `_00017_`: vollständig, passende Größe und Schatten |
| 5 | Skill, „Kopf nach Vorbild“ als Rechteck | `Verbessert_00018_`, `_00019_`: erkennbar die Frau aus Bild 2, beide ernst wie verlangt; das Rechteck endete knapp über dem Kopf, das Haar ist oben flach – großzügig markieren |
| 6 | Ältere Aufträge ohne Vorbild | Ablauf unverändert (Unit-Test: Graph ohne Vorbild identisch); Rolle `vorlage` vom Bearbeiten geht nicht mit |

Testdateien: `Verbessert_00001_`–`_00019_` seit 05.10.2026 im Papierkorb (Auftrag Sascha, rückholbar); `Bild_00093_`
(Sitzpouf, Vorbild für Gegenstände) bleibt als Ausgangsbild.
`_00001_`–`_00013_` entstanden noch mit dreifachem Ausschnitt; „Nochmal“ rechnet sie jetzt mit dem doppelten.

### Stufe 3o: Realism-LoRA für Videos mit Personen (05.10.2026, fertig)

Auftrag Sascha 05.10.2026 (Punkt 1 der Bewertung vom 04.10.2026, Download 131 MB freigegeben): Die LoRA
`h3-realism-people-t2v-i2v-r2v.safetensors` von Hugging Face `fal/MiniMax-H3-Realism-People-LoRA` (Lizenz wie
MiniMax-H3) liegt in `ComfyUI\models\loras`, SHA-256 `acc529601d2da117fb81179e76c56e488a3beab1171659d305f04fa3655b787e`
gegen die Angabe von Hugging Face geprüft.

**Vergleich** (ComfyUI direkt, `video_graph` + LoRA hinter der Turbo-LoRA, Stärke 1,0, Auslösewort `r34l1sm` vor dem
Prompt; 960 × 544, 5 s, 8 Schritte, Nummern 11 und 22, gleicher Text; Probevideos in `Studio\_versuche\realism`):

| Fall | ohne LoRA | mit LoRA | Bewertung |
|---|---|---|---|
| Nahaufnahme aus Text (Therapeutin spricht) | Haut glänzt („Plastik“); einmal Fantasie-Schrift „Nahaefsbtod“ auf dem Oberteil und ein Ansteckmikro | 2 von 2 matte, natürliche Haut, keine Schrift | klarer Gewinn |
| Porträt `Bild_00027_` als Startbild | Person erhalten, Haut mit Poren | Person erhalten, Haut etwas glatter | kein Unterschied |
| Porträt als Referenzbild, Behandlungsszene mit Patient | Frau ähnlich; einmal eine Patientin in grüner Praxiskleidung statt des beschriebenen Mannes | 2 von 2 die Frau besser zu erkennen, einmal der Patient wie beschrieben | Gewinn; eine Nummer hatte in beiden Fassungen zeitweise abgeschnittene Köpfe |
| Leerer Raum, Kamerafahrt (Hintergrundvideo) | stimmig | 2 von 2 schlechter: Kabel von der Decke, Scherengestell unter der Liege, weißes Teil unter der Liege | nicht verwenden |
| Zeit | 126–139 s | 126–139 s | gleich |

**Entscheidung:** Häkchen „Realistische Personen“ (`realismus: true`) für alle Videoarten und das Weiterführen, nur auf
Wunsch (kein Standard: Räume ohne Personen litten; ältere Videos bleiben bei „Nochmal“ gleich).

**Umsetzung:** `werkstatt\studio.py` (`video_graph` Knoten 26 und Auslösewort, `realismus_prompt`/`realismus_weg`,
`einstellungen_aus_graph` erkennt die LoRA, `realismus_verfuegbar`, `_realismus` in beiden Prüfungen, Begleitdaten),
`config.json` (`studio.video.realismus`), Oberfläche (Häkchen bei Videos, Hinweis in der Schätzung, „Nochmal“ und „Mit
Änderungen“ übernehmen es, Großansicht „mit Realism-LoRA“), Skill (`video … --realismus`, `weiter … --realismus`,
`status` meldet `realismus`), STUDIO.md (Abschnitte 3, 4, 10–12), SKILL.md, `ki-werbevideo` (lokal-studio.md).
Tests: Werkstatt 137 OK (neu: Ablauf mit und ohne LoRA, mit Referenz ohne Turbo, Weiterführen, Zurücklesen ohne
Auslösewort, Prüfung und Begleitdaten), Zentrale 11 OK, `node --check` OK.

Prüfung am echten System (05.10.2026, „Werkstatt-Abnahme“):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Oberfläche: Häkchen nur bei Videos, Hinweis in der Schätzung | „Realistische Personen (nur für Videos mit Menschen)“, Schätzung „… mit Realism-LoRA: natürlichere Haut bei Personen; für Räume ohne Personen weglassen“ |
| 2 | Video aus Text mit Häkchen, Nummer 33, 8 Schritte | `Video_00016_` in 122 s (Schätzung 133 s), Haut mit Poren und Bartstoppeln; Begleitdaten `realismus: true`, Prompt ohne Auslösewort; Großansicht „8 Schritte, mit Turbo, mit Realism-LoRA“. Verlangt war „halbnah“, gekommen ist eine Nahaufnahme mit angeschnittenem Kopf (Bildgestaltung, nicht die LoRA) |
| 3 | „Nochmal“ | ComfyUI erkannte denselben Ablauf: „Genau dieses Video gibt es schon“ |
| 4 | Skill `weiter … --realismus` (verlängern 5 s) | `Video_00017_`, 260 Bilder, 293 s; dieselbe Person über die Naht, Handlung wie beschrieben |
| 5 | Ältere Videos | ohne das Feld unverändert (Unit-Test: Ablauf ohne Knoten 26, Prompt ohne Auslösewort) |

Nebenbei: Die Großansicht spielt Videos automatisch mit Ton in Schleife; beim Test lief `Video_00016_` hörbar weiter,
bis die Ansicht geschlossen wurde (Hinweis Sascha). Entscheidung Sascha 05.10.2026: bleibt so (nicht stumm). Agenten
schließen die Großansicht nach dem Prüfen.

### Vergleich Head-Swap-LoRA BFS v1.1 (05.10.2026, nicht übernommen)

Auftrag Sascha 05.10.2026 (Download 260 MB freigegeben; eingebaut nur, wenn die Gesichter deutlich ähnlicher werden).
`bfs_head_v1.1_qwen_2.1.safetensors` von Hugging Face `Alissonerdx/BFS-Best-Face-Swap` (MIT; SHA-256
`d1d748d5601077f3b6d05766f6823510e901970d916afa404a97e85dc92fa88e` geprüft) liegt in `ComfyUI\models\loras`.
Anleitung des Autors: Bild 1 = Zielbild (Körper, Haltung, Licht), Bild 2 = Kopf, Stärke 1,0, fester englischer Prompt
(„head_swap: start with <image1> as the base image … copy the direction of the eye, head rotation, micro expressions
from <image1> …“). Vergleich: Bearbeiten wie Vorlage 1 (≈1 MP), Turbo, INT8, gleiche Nummern 11 und 22; unser Vorschlag
„Kopf tauschen“ (deutscher Text, ohne LoRA) gegen BFS (sein Text, mit LoRA). Nur Vorschau, nichts im Studio.

| Bildpaar | „Kopf tauschen“ (Studio) | BFS v1.1 |
|---|---|---|
| Therapeutin in der Behandlungsszene (`Bild_00008_` ← `Bild_00027_`) | Gesicht wie Bild 2, aber 2 von 2 lächelt sie in die Kamera statt auf den Arm des Patienten zu schauen; **1 von 2 fehlte dem Patienten der Kopf** | 2 von 2 sauber: Blick nach unten wie im Original, Patient unverändert |
| Frau frontal (`ki-werbevideo Abnahme/Bearbeitet_00001_` ← ältere Frau `Bild_00009_`) | 2 von 2 dem Vorbild ähnlicher (rundes Gesicht, Lachfalten); 1 von 2 Polokragen verändert | 2 von 2 Gesicht schmaler, weniger ähnlich; Kleidung unverändert |
| Profil, Kopf im Nacken, Augen zu (`Haltungsanalyse Sichtprobe/Bild_00001_` ← `Bild_00027_`) | 2 von 2 breites Lächeln aus dem Porträt | 2 von 2 Ausdruck und Augen wie im Original |
| Zeit | 6–24 s | 6–16 s |

**Entscheidung:** nicht einbauen – die Gesichter werden nicht ähnlicher (frontal sogar weniger). BFS hält Blick,
Ausdruck und andere Personen besser fest; dafür gibt es seit Stufe 3n „Kopf nach Vorbild“ (Verbessern: nur die
markierte Stelle wird neu gerechnet, Blick und Ausdruck stehen im Text). Neuer Hinweis beim Vorschlag „Kopf tauschen“:
bei mehreren Personen „Kopf nach Vorbild“ nehmen. Die LoRA-Datei bleibt in `ComfyUI\models\loras` liegen
(Entscheidung Sascha 05.10.2026).

### Stufe 3p: Szenenfolge (05.10.2026, fertig)

Auftrag Sascha 05.10.2026 (Schritte 2 und 3 der Bewertung vom 04.10.2026); nach dem Vorversuch entschieden: „Szenenfolge
bauen“, ohne Referenzbilder.

**Vorversuch Referenzbilder beim Weiterführen** (ComfyUI direkt, `weiter_graph`; Startclip `_versuche/realism/
referenz_ohne_11_s8` mit der Frau aus `Bild_00027_`; je drei Verlängerungen à 5,7 s neu hintereinander, Nummer 41,
8 Schritte; Arm „mit“: ref2va mit dem Porträt als `ref_image_0` + `MiniMaxH3AddGuide` wie bisher, im Text „Die Frau aus
Bild 1 …, Gesicht und Haare bleiben wie in Bild 1“; Arm „ohne“: wie Stufe 3m, die Frau im Text beschrieben):

| Messung | ohne Referenz | mit Referenz |
|---|---|---|
| Gesicht nach 1, 2, 3 Runden | dieselbe Frau, in Runde 3 kaum anders | dieselbe Frau; kein sichtbarer Vorteil |
| Nähte 1 / 2 / 3 (Median im Video) | 4,9 / 6,8 / **57,7** (3,6) | 4,6 / 15,9 / **60,7** (7,2) |
| Zeit je Runde | 299–302 s | 312–314 s |

Die Naht 3 war in beiden Armen ein **harter Schnitt in eine neue Einstellung** (Totale statt Halbnah bzw. umgekehrt),
die Handlung („setzt sich auf die Liege“) stimmte. Runde 3 ohne Referenz noch einmal mit dem Zusatz „Eine durchgehende
Einstellung ohne Schnitt: Die Kamera bleibt in derselben Einstellung wie am Anfang, sie bewegt sich nur langsam mit.“:
Nummer 41 und 42 Naht 4,9 / 4,8 (Median 3,7 / 4,2), die Frau setzte sich 2 von 2 wie beschrieben. **Entscheidung:**
Referenzbilder beim Weiterführen nicht einbauen; der Zusatz kommt in jede Szene einer Szenenfolge und als Regel ins
Handbuch. Probevideos in `Studio\_versuche\weiter`.

**Umsetzung:**
- `werkstatt\studio.py`: Szenenfolgen (`self.folgen`, gespeichert in `studio.json`): `folge_neu` (Prüfung
  `_folge_pruefen`: gemeinsamer Teil, 1–8 Szenen mit Länge, zusammen höchstens 60 s, Szene 1 aus Text, mit Startbild oder
  mit Referenzbildern), `_szene_anlegen` (Szene 1 eigener Clip, jede weitere `video_weiter`/`verlaengern` an das
  freigegebene Video der Szene davor; Prompt = gemeinsamer Teil + Szene + Zusatz, `szenen_prompt`), `folge_aktion`
  (`passt`, `nochmal` mit neuer Nummer, `beenden`, `entfernen`), `_folgen_abgleichen` (Zustand immer aus dem echten
  Zustand des aktuellen Auftrags, auch nach „Wiederholen“ in der Auftragsliste, einem Neustart oder einem Fehler;
  ohne Prüfen startet die nächste Szene von selbst). `_anlegen` gemeinsam mit `erzeugen`. Begleitdaten `szenenfolge`
  (Folge, Szene, Szenen). `server.py`: Aktionen `folge_neu` und `folge`. `config.json`: `studio.video.szenen`
  (`max_szenen` 8, Zusatz, Grund).
- Oberfläche: Art „Szenenfolge“ (Startbild oder Referenzbilder, gemeinsamer Teil im Beschreibungsfeld, Szenen-Liste mit
  Länge je Szene, „Szene dazu“, Häkchen „Nach jeder Szene prüfen“, Realistische Personen), Schätzung (Rechenzeit aller
  Szenen, Länge des fertigen Videos, Warnung über 60 s), Karte über der Bibliothek je Folge („Szene ansehen“, „Passt –
  weiter mit Szene n“ bzw. „Passt – fertig“, „Nochmal“, „Beenden“, „Ansehen“, „Ausblenden“); Großansicht „Szenenfolge:
  Szene i von n“.
- Skill: `studio.py szenen "<gemeinsam>" --szene … --sekunden 5,5.7 [--pruefen] [--realismus] [--start|--bild]`,
  `studio.py szene <id> passt|nochmal|beenden|entfernen`. STUDIO.md (Abschnitte 1, 3, 7, 10–12), SKILL.md,
  `ki-werbevideo` (lokal-studio.md), README, AGENTS.md.
- Tests: Werkstatt 142 OK (neu: Prüfung aller Grenzen, Ablauf mit Prüfen inkl. Nochmal/Passt/Fehler/Wiederholen/
  Neustart/Entfernen, Durchlauf ohne Prüfen mit fester Nummer, Startbild und Beenden, fehlende Quelle vor Szene 2),
  Zentrale 11 OK, `node --check` OK.

Prüfung am echten System (05.10.2026, „Werkstatt-Abnahme“, 960 × 544, 8 Schritte):

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Oberfläche: Art, Szenenliste, „Szene dazu“, Schätzung | 2 Szenen vorbelegt, „Szene dazu“ legt Szene 3 an und springt hinein; Schätzung „3 Szenen, zusammen etwa 12 min Rechenzeit · fertiges Video 16,5 s“; Knopf „Szenenfolge starten (3 Szenen)“ |
| 2 | Folge mit Prüfen und Realism-LoRA (Therapeutin, 5 + 5,7 + 5,7 s) | Karte „Szene 1 von 3 ist fertig …“ mit vier Knöpfen. Szene 1 (`Video_00018_`, 130 s): olivgrüne Bluse statt Praxiskleidung und eine nicht beschriebene zweite Frau auf der Liege → „Nochmal“: `Video_00019_` (120 s, neue Nummer) nur eine Person, grüner Pulli, eher Selfie-Ausschnitt → „Passt“ |
| 3 | Szene 2 verlängert genau die freigegebene Szene | `video_weiter` an `Video_00019_`; `Video_00020_` (298 s, Schätzung 311 s): dieselbe Frau, hebt den Arm seitlich; Naht 5,3 bei sonst 2,8 |
| 4 | Steuern über den Skill (`szene <id> passt`) | Szene 3 `Video_00021_` (in 5 min): setzt sich auf die Liege wie beschrieben; Nähte 5,3 / 3,8 bei sonst 3,1; 396 Bilder = 16,5 s wie geschätzt, Ton 16,499 s. Mängel: ab Szene 2 hängt ein durchsichtiger Streifen von der Decke (ähnlich den Kabeln der Realism-LoRA in leeren Räumen), in Szene 3 ist der Kopf oben angeschnitten |
| 5 | Abschluss in der Oberfläche („Passt – fertig“) | „Fertig: 3 Szenen, 16,5 s.“ mit „Ansehen“ und „Ausblenden“; freigegeben `Video_00019_`, `_00020_`, `_00021_` |
| 6 | Skill `szenen` ohne Prüfen, Hintergrundvideo (leerer Raum, 5 + 3,5 s, Nummer 55) | lief allein durch (`Video_00022_`, `_00023_`, zusammen 323 s): Kamerafahrt zum Fenster, dann Schwenk; Naht 3,9 bei sonst 1,5; Begleitdaten `szenenfolge: Szene 2 von 2`, Nummer 55 in beiden Szenen |

Befund für Prompts: Was Szene 1 zeigt (Kleidung, Ausschnitt, Selfie-Haltung), tragen alle weiteren Szenen weiter – Szene 1
deshalb streng prüfen und lieber „Nochmal“ als weiter; Kleidung und Kameraabstand im gemeinsamen Teil genau nennen
(„salbeigrüne Praxiskleidung“ allein reichte 2 von 2 nicht).

Testdateien: `Video_00018_`–`_00023_` und die Probevideos in `Studio\_versuche\realism` (16) und
`Studio\_versuche\weiter` (8) seit 05.10.2026 im Papierkorb (Auftrag Sascha, rückholbar); die beiden leeren Ordner sind
entfernt.

### Bewertet 05.10.2026: „LTX 2.5 Alpha Gen is Amazing!“ – Videos freistellen (zurückgestellt)

Quelle: YouTube `dKbT0x9Se-s` (Alex Villabon, 02.10.2026, Partnerschaft mit LTX, Dell und NVIDIA), Beschreibung und
Transkript von Sascha eingefügt. Gelesen: Modellkarte `Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen`, Dateiliste
`Lightricks/LTX-2.5`, ComfyUI-Quelltext. Kein Download, keine Änderung.

- **Was es ist:** IC-LoRA (1,31 GB) für LTX 2.5 22B (distilled), macht aus einem Video eine Graustufen-Maske (nur Alpha,
  ohne Prompt, keine Wahl, wer freigestellt wird). Im Video sehr stabil, auch bei Haaren, Fell, Rauch, Glas.
- **Aufwand für das Studio:** LTX 2.5 ist nicht installiert (Studio rechnet mit MiniMax-H3). INT8-Fassungen etwa 40 GB
  (Transformer 21,5 GB, Text-Encoder Gemma 15,4 GB, VAE 1,5 GB, LoRA); die Modellkarte nennt BF16 (Transformer 42 GB),
  INT8 mit der LoRA ungeprüft. Laut Modellkarte Full HD × 145 Bilder nur auf H100-Klasse – auf der 3090 nur kürzere oder
  kleinere Clips. Ab etwa 6 s (145 Bilder) „leakt“ Bildinhalt in die Maske; Löcher bei offenem Mund, glänzenden Teilen,
  Geisterbilder von Personen im Hintergrund. Eigene LTX-Community-Lizenz (vor Einsatz prüfen). LTX-Kernknoten
  (`LTXVAddGuide`, `LTXVCropGuides` …) sind in ComfyUI 0.37 vorhanden; ob der IC-LoRA-Ablauf damit ohne Zusatzknoten geht,
  ist ungeprüft (Modellkarte verweist auf die LTX-Knoten).
- **Wofür es gebraucht würde:** echte Aufnahmen (Sascha, Team) freistellen – Hintergrund tauschen, Person über eine
  Webseite legen, Text hinter die Person (`video-regie`), durchsichtige Videos für Webseiten. KI-Videos lassen sich
  meist gleich mit passendem Hintergrund rechnen.
- **Vorhanden ohne Download:** Kernknoten `SAM3_VideoTrack` (+ `SAM3_TrackToMask`) mit dem schon geladenen SAM3.1 –
  verfolgt etwa „person“ über ein ganzes Video mit stabiler, aber härterer Maske (feine Haare eher nicht). Ungeprüft.

**Entscheidung Sascha 05.10.2026: zurückgestellt.** Vorschlag für später (nur auf Auftrag): 1. Bedarf klären (Videos
freistellen?). 2. Wenn ja, zuerst `SAM3_VideoTrack` an einem echten bzw. Studio-Video mit Person testen (kein Download).
3. Nur wenn die Kanten nicht reichen, LTX 2.5 + Alpha Gen (Download etwa 40 GB nach Freigabe, Lizenz prüfen), zuerst
kurze Clips in 960 × 544.

### Bewertet 06.10.2026: „Highest quality workflow for minimax h3“ (nur gelesen, nichts geändert)

Quelle: YouTube `fptCq7s0ig0` (VYREKAI, 04.10.2026), Beschreibung und Transkript von Sascha eingefügt; die
Workflow-Datei liegt nur auf Google Drive und wurde nicht geladen. Ein Stapel aus mehreren LoRAs plus zweiter
Durchgang, ohne Vergleiche oder Messungen; die meisten LoRAs nennt das Video nicht beim Namen.

| Baustein | Bewertung |
|---|---|
| 8-Schritt-Turbo-LoRA mit 16 Schritten gerechnet („maximale Qualität“) | Studio nutzt Turbo nur bis 8 Schritte (`turbo_bis_schritte`). Ungeprüft; wäre ohne Download testbar (gleiche Nummer: Turbo 8 / Turbo 16 / ohne Turbo 20) |
| „HDR-Realism“-LoRA, Stärke 0,75 | gleicher Zweck wie die Realism-LoRA (Stufe 3o); welche LoRA, bleibt offen |
| „Motion Repair“- und Schärfe-LoRA | ohne Namen, für Kampf- und Laufszenen; für Praxis-Videos kaum nötig |
| 0,5 MP rechnen, dann hochskalieren (2. Durchgang, 3 Schritte) | entspricht dem DualPass (Bewertung 04.10.2026), nicht beauftragt |
| Start-/Endbild, Referenzbilder ein/aus | im Studio vorhanden |

**Entscheidung Sascha 06.10.2026:** festhalten, nicht testen. Nichts einbauen. Möglicher Test für später (nur auf
Auftrag): Turbo-LoRA bei 12/16 Schritten gegen 8 Schritte und gegen 20 Schritte ohne Turbo.

### Bewertet 06.10.2026: „Best MiniMax H3 Realistic Skin Workflow — No More Plastic Skin“ (nur gelesen, nichts geändert)

Quelle: YouTube `wtHrJ4qb_Wc` (Prompt Mastery, 05.10.2026), Beschreibung und Transkript von Sascha eingefügt; Workflow
und Anleitung nur über Gumroad bzw. einen Cloud-Dienst, nicht geladen. Laut Autor rund 200 Generierungen in einer Woche,
eigene Vergleiche ohne Zahlen.

| Aussage im Video | Bewertung für das Studio |
|---|---|
| Ein Durchgang mit 8 Schritten; Hochskalieren bzw. zweiter Durchgang macht die Haut öliger | stützt die Entscheidung gegen DualPass (Bewertung 04.10.2026) |
| Realism-LoRA von fal (`r34l1sm`) als wichtigster Baustein | haben wir seit Stufe 3o („Realistische Personen“) |
| Nur eine Turbo-/Speed-LoRA gleichzeitig | so rechnet das Studio ohnehin |
| Mehr Hautrealismus macht das Modell „dümmer“ (Hintergründe zerfallen, Text wird ignoriert) | passt zum Befund 3o (Kabel im leeren Raum) |
| Grundmodell Singularity, „EMA-600“-LoRA | Singularity abgelehnt (04.10.2026); EMA-600 nicht genau benannt |
| Ref2V-Turbo 4 Schritte v0.1 = „öligste“ Haut, eine 8-Schritt-Ref2V-Turbo deutlich besser | Studio nutzt für „Video mit Referenz“ die 4-Schritt-Turbo v0.1. Comfy-Org hat keine 8-Schritt-Ref2V-Fassung; gemeint ist vermutlich Kijais `MiniMax-H3-Ref2VA-Acc-8Step` (1,7 GB, `Kijai/MiniMax-H3-experimental`). Ungeprüft |
| Prompt-Regeln Haut: „matte skin, visible pores, peach fuzz, faint freckles, slight unevenness“, weiches gleichmäßiges Licht, Kamera näher; nie „flawless“, „glow“, „shimmer“, „highlighter“, „wet skin“; keine Verneinungen („keine ölige Haut“ bewirkt das Gegenteil) | ungeprüft; passt zur Erfahrung, dass Ausschlüsse im Prompt wenig taugen |

**Entscheidung Sascha 06.10.2026:** nur festhalten, nichts testen, nichts einbauen. Mögliche Tests für später (nur auf
Auftrag): Prompt-Regeln für Haut (gleiche Nummer, je 2 Videos, kein Download); Kijais Ref2VA-Acc-8Step gegen die
4-Schritt-Turbo v0.1 bei Referenz-Videos und beim Character Swap (Download 1,7 GB nach Freigabe).

### Bewertet 06.10.2026: „I Combined Qwen Image 2.1 with FLUX Klein …“ – Haut auffrischen mit FLUX.2 Klein (festgehalten)

Quelle: YouTube `KTuENenmdDY` (The Ai Blueprint, 03.10.2026), Beschreibung und Transkript von Sascha eingefügt
(„das sieht sehr gut aus“). Workflow nur über Patreon, nicht geladen. Gelesen: Modellseiten und Lizenz bei Hugging Face.

- **Ablauf im Video:** Qwen-Image 2.1 rechnet das Bild (2K, 30 Schritte, CFG 2 bzw. CFG 1 mit Turbo) → schärfen →
  FLUX.2 Klein **Base 9B fp8** auf 4 MP (`ImageScaleToTotalPixels`), nur **2 Schritte**, CFG 1, Euler, Prompt sinngemäß
  „hochauflösend, realistische Hauttextur, keine Plastikhaut, Bild sonst unverändert“ → Farbangleich → nochmals schärfen.
  3 Schritte veränderten laut Autor zu viel. Ergebnis im Video: mehr Poren, Fältchen, Stoffdetails; der Autor sagt selbst,
  das Gesicht habe sich „deutlich verändert“ (für wiederkehrende Figuren wie Praxis-OS heikel). „Detail Daemon“-Sampler
  ist ein Zusatzknoten; Schärfen und Farbangleich gibt es als Kernknoten (`ImageSharpen`, `ColorTransfer`).
- **9B (aus dem Video):** `black-forest-labs/FLUX.2-klein-base-9b-fp8`, Datei `flux-2-klein-base-9b-fp8.safetensors`
  9,57 GB. **Gesperrt** (Anmeldung bei Hugging Face und Zustimmung nötig) – kann der Agent nicht laden; Sascha müsste
  selbst laden und nach `ComfyUI\models\diffusion_models` legen. Dazu frei: Text-Encoder `qwen_3_8b_fp8mixed` (8,66 GB)
  und `flux2-vae` (0,34 GB) aus `Comfy-Org/vae-text-encorder-for-flux-klein-9b`.
  **Lizenz: FLUX Non-Commercial License.** Erlaubt ist Nutzung, die nicht „direkt oder indirekt“ mit geschäftlicher
  Tätigkeit verbunden ist; zu den Ergebnissen heißt es, Outputs dürften für jeden Zweck genutzt werden, auch gewerblich
  (soweit nicht ausdrücklich verboten). Das Modell für Praxis, Webseite oder YouTube zu betreiben, fällt nach dem
  Wortlaut eher unter geschäftlich; Black Forest Labs bietet dafür eine gewerbliche Lizenz an. Einschätzung bleibt bei
  Sascha.
- **4B (frei):** Apache-2.0, ohne Anmeldung, in ComfyUI-Form bei `Comfy-Org/vae-text-encorder-for-flux-klein-4b`
  (`flux-2-klein-4b` bzw. `flux-2-klein-base-4b` je 7,75 GB, Text-Encoder `qwen_3_4b` 8,04 GB oder fp4 3,85 GB, VAE
  0,34 GB). Ob 4B so gut auffrischt wie 9B, ist offen. ComfyUI 0.37 kann Klein (Stufe 3d).
- Vergleichsmaßstab im Studio: „Hochskalieren“ (Qwen selbst, 2/4 MP; zeichnet Gesichter leicht neu) und „Foto
  auffrischen“ (Detail-LoRA).

**Entscheidung Sascha 06.10.2026:** erst festhalten, nichts laden. Möglicher Test (nur auf Auftrag): an 3–4 Bildern mit
Personen (Porträt, Behandlungsszene 4 MP, Praxis-OS-Figur) Original, „Hochskalieren“ (Qwen 4 MP) und Klein 2 bzw. 3
Schritte vergleichen – Haut, gleiche Person, Details, Zeit; Varianten: nur 4B (16 GB Download), nur 9B (Sascha lädt
selbst, Agent holt Encoder/VAE 9 GB) oder beide. Einbau nur, wenn sichtbar besser und die Gesichter halten (etwa
Häkchen „Haut auffrischen“ beim Hochskalieren).

### Stufe 3q (Vorversuch, unterbrochen 06.10.2026): Person im Video tauschen (Character-Swap-LoRA)

Anlass: Video „MiniMax H3 Character Swap is NEXT LEVEL!“ (The Ai Blueprint, YouTube `_ofr6LWN5-8`, 06.10.2026).
Auftrag Sascha 06.10.2026 („go“): LoRA laden, vergleichen, bei Erfolg als Option bei „Video mit Referenz“ einbauen.

- **LoRA:** `h3_character_swap_pro4500_1000.safetensors` (Akatz Labs, Hugging Face `akatz-ai/MiniMax-H3-Character-Swap-LoRA`,
  155 MB, SHA-256 `4b2a3f420ae804c0aa3422761ff84dbd1bf52eef6900ffab6d2e66df63cb4e79` geprüft) in `ComfyUI\models\loras`.
  Trainiert genau auf `minimax_h3_ref2va_pruned_int8_convrot` (unser Referenz-Modell), Rang 16, 1.000 Schritte, Stärke 1,0,
  kein Auslösewort. Eingänge: Ausgangsvideo als „Video 1“ (`ref_video_0`), Figur als „Bild 1“ (`ref_image_0`). Prompt des
  Autors (englisch): „Replace only <wer> in <Video 1> with the character in <Picture 1>. Keep the replacement character's
  identity, outfit, and art style from <Picture 1>. Preserve the source video's camera, background, lighting, objects,
  and all other people. Match the target person's position, scale, pose, and movement. Do not show the reference sheet
  or its background.“ Laut Autor am besten kurze Clips (4–5 s) ohne Schnitt; Mimik, Timing und Schnitte unzuverlässig;
  mehrere Personen kaum geprüft. Lizenz wie MiniMax-H3 (siehe „Offen“, Befund zur H3-Lizenz).
- **Aufbau:** Ausgangsvideo `Werkstatt-Abnahme/Video_00016_.mp4` (Mann, graues T-Shirt, hebt die Arme seitlich; per Skill
  gerechnet, Nummer 7, 5 s). Figur: `Praxis-OS Design/Freigestellt_00005_.png` (Frau, dunkler Bob, dunkelblaue Strickjacke,
  helle Hose, freigestellt). `video_graph` (Art `video_referenz`, `referenz_genau` match, Ton des Clips behalten), 960 × 544,
  124 Bilder; LoRA als Knoten 27 hinter der Turbo-LoRA. Skript `versuch_tausch.py` (Sitzungs-Notizblock), Ergebnisse in
  `Studio\_versuche\tausch`.

| Lauf (8 Schritte, Turbo ref2v 4-Step) | Ergebnis | Hintergrund: Abweichung zum Original in den Randstreifen (Median) | Zeit |
|---|---|---|---|
| ohne LoRA, Nummer 11 / 22 | 2 von 2 sauber getauscht: die Figur mit Frisur, Strickjacke, Bluse, Gürtel, Hose; Raum, Kamera, Ausschnitt und Armbewegung Bild für Bild wie im Original | 14,8 / 14,3 | 434 / 443 s |
| mit LoRA, Nummer 11 / 22 | 2 von 2 sauber getauscht, mit bloßem Auge kaum von „ohne“ zu unterscheiden | **11,3 / 10,6** (rund ein Viertel näher am Original) | 479 / 437 s |
| mit LoRA, 20 Schritte ohne Turbo | abgebrochen (Sascha brauchte die Grafikkarte) | – | – |

**Zwischenstand:** Der Tausch gelingt im einfachen Fall (eine Person, frontal, ruhige Kamera) schon mit dem Grundmodell und
dem Prompt des Autors; die LoRA hält messbar den Hintergrund besser. Die Rechenzeit ist hoch (gut 7 min für 5 s), weil das
Ausgangsvideo mitgerechnet wird (Schätzung: Bilder des Clips als zusätzliche Bilder, `video_zeit` ergab 427 s).

**Fortgesetzt und abgeschlossen am 09.10.2026 in Stufe 3r** (unten). Ursprünglich geplant:
**Fortsetzung (geplant für 07.10.2026):** 1. Die beiden 20-Schritt-Läufe ohne Turbo. 2. Schwerer Fall: zwei Personen im
Ausgangsvideo, nur eine tauschen (laut Video der Fall, in dem das Grundmodell oft nur die Kleidung ändert), je ohne/mit LoRA.
3. Optional: sprechende Person (Selfie, `ki-werbevideo Abnahme/Video_00001_`) und ein echtes Handyvideo von Sascha, falls
er eines gibt. 4. Danach entscheiden und ggf. einbauen: Option „Person tauschen“ bei „Video mit Referenz“ (LoRA + Vorschlag
mit der Prompt-Vorlage, 1 Clip + 1 Bild Pflicht, Zeitschätzung mit den Clip-Bildern), Skill, STUDIO.md.
Abbruch am 06.10.2026 um etwa 20:35: Testschleife gestoppt, ComfyUI-Auftrag unterbrochen, danach „GPU freigeben“ in der
Zentrale (nur Modelle aus ComfyUI entladen, Dienst läuft weiter) – auf Saschas Wunsch, damit er spielen kann.

### Bewertet 08.10.2026: „One LoRA Can't Run a Whole Film (MiniMax H3 Workflow)“ (nur gelesen, nichts geändert)

Quelle: YouTube `tEWNWC0Sx-M` (Kanal @Viper_AI_Vaunt, 08.10.2026, 10:19 min, laut YouTube „mit KI erstellt“). Link von
Sascha; gelesen wurden Beschreibung und Kapitelliste im Browser (Video sofort angehalten), Transkript nicht. Im Kern
Werbung für ein eigenes Produkt („VIPER Producer“, kostenpflichtige Workflows und Auto-Installer über whop.com).

| Idee im Video | Stand im Studio |
|---|---|
| Gemeinsames Grundmodell (Singularity + Turbo), je Einstellung eine eigene Anweisung und Referenz | Szenenfolge (Stufe 3p): gemeinsamer Teil + Szene; Singularity abgelehnt (04.10.2026) |
| Nur eine Einstellung neu drehen | „Nochmal“ je Szene in der Szenenfolge |
| Zusammenhang zwischen Einstellungen, ohne Adapter zu teilen | jede Szene setzt die letzten 1,6 s fort, Zusatz „ohne Schnitt“ |
| Figur-Referenz für alle, Requisiten-Referenz je Einstellung | Referenzbilder nur für Szene 1; beim Weiterführen geprüft, ohne Gewinn (3p) |
| Eigene LoRA je Einstellung (Kampf, Waffen, Kamera) | diese LoRAs nicht nötig. Übertragbar: „Realistische Personen“ je Szene statt für die ganze Folge (leere Räume werden mit der Realism-LoRA schlechter, 3o) – kleine Änderung, kein Download |
| 16 Bilder/s rechnen + Zwischenbilder für ruhige Szenen, volle 24 für Action | könnte die Rechenzeit grob halbieren (Zeit wächst etwa mit dem Quadrat der Bilder); braucht aber ein Zwischenbild-Modell mit Zusatzknoten, H3 ist auf 24 Bilder/s trainiert, Ton und Bild könnten auseinanderlaufen. Ungeprüft |

**Entscheidung Sascha 08.10.2026:** festhalten, nichts einbauen. Mögliche Schritte für später (nur auf Auftrag):
„Realistische Personen“ je Szene schaltbar; 16-Bilder/s-Trick nur nach Test (Zusatzmodell nötig).

### Befund 08.10.2026: Aussehen von Personen („leicht asiatischer Touch“) – Prompt-Regel

Anlass: Sascha fiel auf, dass viele Bilder ohne klare Anweisung einen leicht asiatischen Einschlag haben. Auftrag
(„ja mach das mal“): Regel in Handbuch und Skill, Rezepte mit Personen ergänzen, kurzer Test; nichts automatisch in
Prompts einfügen.

- **Test** (Turbo, `hoch45`, Nummern 11/22/33/44, „Werkstatt-Abnahme“, `Bild_00094_`–`_00119_`): ausführliche deutsche
  Prompts mit Beruf und Kleidung ohne Aussehen 0 von 12 ostasiatisch; „Porträt einer jungen Frau“ 0 von 4; „portrait
  photo of a young woman“ 1 von 4; „Eine junge Frau in einem Café“ mit Ausformulieren 1 von 4 (der Enhancer schreibt
  nur „light-to-medium skin, dark brown hair“). Kontrolle mit denselben Nummern und „Central European“ bzw.
  „mitteleuropäisch“: 2 von 2 mitteleuropäisch; der Enhancer übernimmt die Angabe.
- **Regel** (STUDIO.md Abschnitt 7 mit Tabelle, „Wunsch ausformulieren im Detail“; Skill `bild-video-studio` SKILL.md
  „Prompts“ und „Figuren“, `references\webseiten.md` Team/Porträt und Behandlungsszene; `ki-werbevideo`
  `references\lokal-studio.md`): jede Person mit Alter, Herkunft bzw. Typ und Haaren beschreiben, für Saschas Mockups
  meist „mitteleuropäisch“, gemischte Teams bewusst so.
- **Rezept „Figur in neue Szene“** (`studio.js`): Patient jetzt „Mitte 50, mitteleuropäisch, …“, Hinweis nennt das
  Aussehen weiterer Personen. Geprüft mit `Bild_00094_` als Porträt, Nummern 11/22 (`Bearbeitet_00001_`–`_00002_`):
  Patient 2 von 2 wie beschrieben, Figur 2 von 2 dieselbe. Wie schon bekannt: in 1 von 2 blickt sie in die Kamera, die
  Liege wurde 2 von 2 eher ein Stuhl. Die übrigen Rezepte nehmen Personen aus Vorlagen und bleiben unverändert.
- Testdateien bleiben im Projekt, bis Sascha aufräumen lassen will.

### Stufe 3r: Festgehaltenes eingebaut (09.10.2026, fertig)

Auftrag Sascha 09.10.2026: „bau mal alles was wir festgehalten [haben] ein. außerdem wäre eine zusätzlich 4:3 (leichtes
Breitformat) sinnvoll.“ Downloads freigegeben (RIFE 4.25, Ref2VA-8-Schritt-LoRA, FLUX.2 Klein 4B) und „Videos
freistellen“ mit SAM3 ohne Download. Alle Dateien von Hugging Face, SHA-256 geprüft: `rife_v4.25.safetensors` (23 MB,
Comfy-Org/frame_interpolation), `MiniMax-H3-Ref2VA-Acc-8Step_pruned_comfy.safetensors` (1,7 GB, Kijai/MiniMax-H3-experimental,
Original alibaba-pai/MiniMax-H3-Acc-LoRAs), `flux-2-klein-base-4b.safetensors` (7,75 GB), `qwen_3_4b.safetensors`
(8,04 GB), `flux2-vae.safetensors` (0,34 GB; alle drei Comfy-Org/vae-text-encorder-for-flux-klein-4b, Apache-2.0).
DualPass nicht gebaut (fremde Knoten; zwei Videos: zweiter Durchgang macht die Haut öliger).

| Punkt | Ergebnis |
|---|---|
| Format 4:3 (`quer43`, 1472 × 1104) | eingebaut; 2 von 2 stimmig, 6–14 s (`Bild_00120_`, `_00121_`) |
| Realistische Personen je Szene | eingebaut (`szenen[i].realismus`, Skill `--realismus 2,3`); altes Häkchen gilt für alle Szenen ohne Angabe |
| „Ausformuliert übernehmen …“ | eingebaut (Großansicht): Einstellungen + ausformulierter Text als Prompt, Ausformulieren aus |
| Zeitschätzung | lernt je Gruppe aus den letzten 120 Bildaufträgen (Median gemessen/geschätzt); vorher 1,35- bis 3,8-fach zu niedrig, jetzt 0,74–1,0. Referenz-Videos zählen die Clip-Bilder mit |
| Person tauschen (Fortsetzung Stufe 3q) | eingebaut: Häkchen und Vorschlag bei „Video mit Referenz“, Skill `tauschen`. Mit Turbo 8 von 8 richtig (eine Person 4, zwei Personen 4); Character-Swap-LoRA hält den Rest 20–25 % näher am Clip (zwei Personen: 9,8–10,1 statt 12,3–12,5). 20 Schritte: 9,2, aber 17 statt 8 min |
| 8-Schritt-LoRA (Ref2VA, PDD) | eingebaut für neue Referenz-Videos mit 8 Schritten (`acc8`, Sampler Euler; ComfyUI 0.37 wertet die PDD-Köpfe selbst aus). Gegen Turbo: mattere Haut, natürlichere Farben, hält sich enger an das Referenzbild (2 von 2 mit dem Tablet aus dem Bild), gleiche Zeit (140–147 s). **Nicht beim Tauschen:** dort 2 von 5 die Figur zusätzlich ins Bild gesetzt (auch ohne Swap-LoRA), bei Erfolg Raum aber am nächsten am Clip (7,9–8,3). Abnahme über den Skill: `Video_00018_` |
| 16-Bilder/s-Trick | geht nicht mit H3 (fest 24 Bilder/s, Ton hängt daran); RIFE stattdessen als **Zeitlupe** eingebaut (Großansicht „Zeitlupe 1,5×/2×“, Skill `zeitlupe`, ohne Ton, 8–15 s). Zwischenbilder auch an bewegten Armen sauber (`Zeitlupe_00001_`) |
| Videos freistellen (am 05.10.2026 zurückgestellt) | eingebaut ohne LTX: SAM3-Videoverfolgung wählt aus, BiRefNet zieht die Kanten, WebM (VP9) mit Alpha. Drei Videos × drei Verfahren: kombi und BiRefNet weich und sauber, SAM3 allein harte Kante, Saum, Löcher am Rand. Großansicht „Person freistellen“, Skill `freistellen <video.mp4>`; 58–71 s. Abnahme `Freigestellt_00001_.webm` |
| FLUX.2 Klein 4B „Haut auffrischen“ | verglichen (3 Bilder, 2 bzw. 3 von 8 Schritten, 4 MP, 22–30 s) gegen bloßes Vergrößern und Qwen 4 MP (61 s): Gesichter bleiben gleich, aber nur beim scharfen Porträt sichtbar mehr Haut; sonst kaum Unterschied, 3 Schritte glatter. **Nicht eingebaut** (Plan: nur bei sichtbarem Gewinn). Die 16 GB liegen in `ComfyUI\models`; Entscheidung Sascha 09.10.2026: behalten |

Werkstatt-Tests 148 OK, Zentrale 45 OK; Werkstatt neu gestartet. Handbuch STUDIO.md (Abschnitte 3, 4, 5, 7, 8, 10, 11 und
„… im Detail“), Skill `bild-video-studio` (SKILL.md, `scripts\studio.py`: `tauschen`, `zeitlupe`, `freistellen` für
Videos, `szenen --realismus 2,3`, `acc8` automatisch, `--format quer43`), README und AGENTS.md nachgezogen. Versuche in
`Studio\_versuche\tausch`, `…\zeitlupe`, `…\freistellen`, `…\klein`; Skripte im Sitzungs-Notizblock.

### Bewertet 10.10.2026: „MiniMax H3 Character Swap vs the Base Model“ (festgehalten, nichts geändert)

Quelle: YouTube `AKFhMSJ3Lro` (Viper AI Vaunt, 10.10.2026), Beschreibung und Transkript von Sascha eingefügt. Vergleich
Character-Swap-LoRA Stärke 0 gegen 1, gleicher Clip, Bild, Prompt und Seed, ohne Turbo, 20 Schritte; Kampf, Laufen,
Schwert. Ergebnis im Video: Das Grundmodell tauscht schon; die LoRA brachte keinen durchgehenden, sichtbaren Gewinn,
nur einzelne Unterschiede (etwa die Blickrichtung). Ganzer Clip zu prüfen, nicht das erste Bild.

- **Passt zu Stufe 3q/3r:** auch bei uns 8 von 8 ohne LoRA richtig getauscht und mit bloßem Auge kaum Unterschied.
  Gemessen hält die LoRA den Rest des Bildes aber in allen 4 Vergleichspaaren rund 20 % näher am Clip, ohne Mehrzeit.
- Unterschied: wir mit Turbo 8 Schritte, das Video ohne Turbo 20 Schritte (dort ungeprüft, ob der kleine Vorteil hält);
  schnelle Kampf- und Laufszenen und der Ton sind bei uns ungeprüft.
- **Entscheidung:** nichts ändern; die LoRA bleibt beim Häkchen „Person tauschen“.

### Bewertet 10.10.2026: „I Tested the BEST MiniMax H3 Turbo LoRAs So You Don't Have To“ (festgehalten, Test beauftragt)

Quelle: YouTube `RSeMMqJg_DY` (Viper AI Vaunt, 09.10.2026), Beschreibung und Transkript von Sascha eingefügt. Vergleich
an einem Seed, Bild zu Video, 1344 × 768, 124 Bilder: LightX2V 4 und 8 Schritte, DMAD „lora critic“ und „full critic“
(4 und 8 Schritte), Grundmodell 50 bzw. 20 Schritte. Aussagen: 4 Schritte reichen für Porträt, Laufen, Kampf, Schwert und
Dialog; 8 Schritte kein automatischer Gewinn (eher zurückhaltendere Mimik); RTX 3090: 4 Schritte ~4 min, 8 ~7 min,
Grundmodell 20 Schritte ~16 min. Favoriten: DMAD lora critic (Dialog), DMAD full critic (Bewegung), LightX2V 4 Schritte.

- **Stand im Studio:** Text und Bild zu Video rechnen mit `minimax_h3_fl2v_turbo_8step_v1.0` (LightX2V, auf 544p
  trainiert, Verschiebung 12/3). Laut LightX2V für 8 **und 4** Schritte empfohlen – „Schnell“ (4) ist also vorgesehen.
  Die 768p-Fassungen und DMAD sind auf 1344 × 768 trainiert (bei uns „breit nativ“); das Studio rechnet standardmäßig
  960 × 544.
- **Einstellungen laut Modellkarten:** DMAD: `LoraLoaderModelOnly` 1,0, CFG 1, `ModelSamplingMiniMaxH3` 12/2, Sampler
  `lcm`, Planer `simple` (Euler nicht ihr Arbeitspunkt); Lizenz MiniMax-H3-Community (wie das Modell). LightX2V 768p:
  Verschiebung 6/3, Sampler Euler; Apache-2.0.
- **Richtigstellung zu „Bewertet 06.10.2026 … Realistic Skin“:** Eine 8-Schritt-Ref2V-Turbo gibt es auch von LightX2V
  (`minimax_h3_ref2v_turbo_8step_v1.0_768p`); vermutlich war die gemeint, nicht die PDD-LoRA von alibaba-pai/Kijai.
  Die PDD-LoRA ist seit Stufe 3r für Referenz-Videos im Einsatz und hat sich dort bewährt.
- **Auftrag Sascha 10.10.2026:** testen. Geladen (SHA-256 geprüft): `dmad_minimax_h3_4step_full_critic_comfyui`,
  `dmad_minimax_h3_4step_lora_critic_comfyui` (ZhengmingYu/DMAD), `minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16`
  (lightx2v), je 1,96 GB. Ergebnis: Stufe 3s.

### Bewertet 11.10.2026: „Qwen-Image 2.1 Turbo – fastest model yet?“ (festgehalten, Test beauftragt)

Quelle: YouTube `QiSVLf-CGDI` (Loop Forge, 10.10.2026), Beschreibung und Transkript von Sascha eingefügt, dazu die Seite
loopforge.cc/projects/qwen-image-2-1-turbo (gelesen). Qwen hat am 09.10.2026 ein **eigenes 8-Schritt-Modell** von
Qwen-Image 2.1 veröffentlicht; Comfy-Org: `qwen_image_2.1_turbo_int8_convrot.safetensors` (7,26 GB; auch BF16 14,2 GB und
eine LoRA-Fassung 0,9 GB). Text-Encoder und VAE wie bei 2.1. Einstellungen: 8 Schritte, CFG 1, Euler, trainierte Sigmas
per ManualSigmas `1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0`.

- **Im Video** (RTX 3060, 27 Tests nach Augenmaß, 2 Seeds): Schrift, Hände, Prompt-Treue, dieselbe Person, Bearbeiten
  mit Referenzen, Durchsichtiges und Freistellen gleichwertig zum Grundmodell; bei 2K im Augen-Ausschnitt kein
  Unterschied; über Seeds etwas weniger Abwechslung. 1024² 15 s statt 35 s (Grundmodell 25 Schritte); Bearbeiten 24 statt
  63 s.
- **Stand im Studio:** Stufe „Turbo“ = Viggle-Turbo-LoRA v0.2.1 (6 Schritte, eigener Sigma-Plan) auf dem INT8-Modell,
  1328² ≈ 7 s. Auf der 3090 vermutlich kein Tempogewinn (LoRA-Aufschlag ~1,4 je Schritt gegen 2 Schritte mehr); die
  Frage ist die Qualität.
- **Auftrag Sascha 11.10.2026:** laden und vergleichen – offizielles Turbo (8) gegen Viggle-Turbo (6) und Standard, gleiche
  Nummern; Porträt, Hände, Schrift, Bearbeiten mit Vorlage, durchsichtiger Hintergrund, Moodboard. Bei Gewinn rechnet
  „Turbo“ neue Bilder mit dem offiziellen Modell (alte bleiben bei „Nochmal“ gleich). Ergebnis: Stufe 3s.

### Stufe 3s: Offizielles Bild-Turbo und DMAD für Videos (11.10.2026, fertig)

Auftrag Sascha 10./11.10.2026 („beides festhalten und testen“, „Download und go“, „wenn alles fertig ist einbauen und in
die Tagesnotiz schreiben“). Geladen (SHA-256 geprüft): DMAD full/lora critic (ZhengmingYu/DMAD), LightX2V fl2v 4-step
v1.2 768p, je 1,96 GB; `qwen_image_2.1_turbo_int8_convrot` (Comfy-Org, 7,26 GB). Tests direkt an ComfyUI mit Graphen
wie die Werkstatt, gesperrt über ein Platz-Tor (wartet auf ruhige Karten: am 11.10. liefen Whisper und ein
OCR-`llama-server` aus `C:\LLM` nebenher; meldet den Zusatzbedarf an wie die Werkstatt).

**Bilder:** offizielles Turbo (8 Schritte, trainierte Sigmas, Euler) gegen Viggle-LoRA (6) und Standard (20), 6 Motive ×
2 Nummern: gleichwertig in 12 von 12 (Porträt, Hände, Schrift „Mo–Fr 8–19 Uhr“ richtig – Standard schrieb 2× eine Tilde,
Raum mit Sprossenwand, durchsichtig, Bearbeiten mit Vorlage); 1 MP 5–8 s wie die LoRA, Bearbeiten 9 statt 13 s.
**Eingebaut:** Stufe „Turbo“ rechnet neue Aufträge mit dem Modell (`turbo_modell`); ältere Turbo-Bilder bleiben bei
„Nochmal“ gleich. Abnahme über die Werkstatt: 4 MP `Bild_00122_` (32 s, stimmig) und Verbessern per Wort
`Verbessert_00001_` (Hand, 20 s, sauber).

**Videos aus Text/Bild:** Studio-LoRA (LightX2V 8-step v1.0) bei 8 und 4 Schritten gegen DMAD full critic, DMAD lora critic
und LightX2V 4-step v1.2 768p (je 4 Schritte), drei Szenen (Therapeutin spricht, Jogger, Kamerafahrt aus Praxisbild),
960 × 544 und 1344 × 768, Nummer 11:

| Variante | Haut / Bild | Bewegung | Sprache (Whisper) | Zeit 5 s (544p / 768p) |
|---|---|---|---|---|
| Studio 8 Schritte | glänzend, starkes Grinsen | in 768p schiebt sich ein Tor vor den Läufer | 2/2 richtig | 131–144 / 366–398 s |
| Studio 4 Schritte | am stärksten glänzend, orange | wie 8 | in 544p fehlt „Guten Morgen“ | 72–81 / ~200 s |
| **DMAD full critic** | **natürlichste, matte Haut** | **sauber** | **2/2 richtig** | 75–83 / ~200 s |
| DMAD lora critic | sauber, leicht glatt | in 768p taucht eine Bank auf | 2/2 richtig | 75–81 / ~200 s |
| LightX2V 4 v1.2 768p | ordentlich, ein Mikrofon im Bild | schliert in 544p, sauber in 768p | „Lacken“ statt „Nacken“ (768p) | 75–84 / ~200 s |

Kamerafahrt: alle gleich gut. **Eingebaut:** „Schnell“ (4 Schritte) bei Video aus Text/Bild rechnet neue Aufträge mit DMAD
(`dmad`, lcm, Verschiebung 12/2, Kernknoten `MiniMaxH3SigmaShift`); Skill-Standard aus Text/Bild jetzt „schnell“. Abnahme
über den Skill: `Video_00019_` bitgleich mit dem Testlauf, 76 s. Haut-Prompt-Test (`Video_00020_`): mehr Sommersprossen,
nicht matter. Lippen nicht geprüft.

**Detail-LoRA mit dem neuen Turbo** (Hinweis einer anderen Sitzung, Auftrag Sascha 11.10.2026): „Foto auffrischen“ an einem
künstlich verschlechterten Porträt (512 px, überbelichtet, JPEG), dem Praxisraum `Bild_00011_` und dem Porträt `Bild_00027_`,
je Viggle-Turbo + 1,0, Turbo-Modell + 1,0 und + 0,68: Mit dem offiziellen Turbo-Modell (11.10.2026, Hinweis aus dem Video „Is Qwen Image 2.1 Turbo Actually Good?“: ältere LoRAs übersättigen, Stärke ~0,68): keine Übersättigung – mittlere Sättigung höchstens ~1 Punkt vom Original (wie mit der Viggle-Turbo), schwaches Porträt sauber aufgefrischt, Raum sauberer als mit Viggle (die malte Kritzel auf die Wand); 0,68 am nächsten am Original, 1,0 etwas mehr Detail. Stärke bleibt 1,0; 13 statt 20–29 s. Die offizielle Turbo-LoRA von Comfy-Org
(0,9 GB) nicht geladen: das Vollmodell genügt.

Werkstatt-Tests 152 OK. Doku: STUDIO.md (Qualitätsstufen, LoRAs, Modelle, Abschnitt 8, Schnittstelle, Zeiten), Skill
`bild-video-studio` (SKILL.md, `scripts\studio.py`: `turbo_modell`, `dmad`, Standard „schnell“, Startfehler-Text).

Einstieg für einen neuen Chat: in `C:\Workstation\Werkzeuge\KI-Zentrale` starten, AGENTS.md und diese
Datei lesen. 2Wild nie verändern.

### Bewertet 11.10.2026: „I Fixed Pixal3D's Biggest Weakness (Free Local 3D AI)“ (festgehalten, Vorschlag; nichts geladen)

Quelle: YouTube `PpuNKVoSYB4` (PixelArtistry, 07.10.2026), Beschreibung und Transkript von Sascha eingefügt; dazu gelesen:
GitHub `pixelartistry/PixelArtistry-Pixal3D-MultiView` (MIT), `TencentARC/Pixal3D` (SIGGRAPH 2026, MIT; Multiview-Code
seit Sept. 2026), HF `Comfy-Org/Pixal3D` (MIT), comfyui-wiki zum Multiview-Knoten. Kern des Videos: Qwen-Image 2.1 macht
aus einer Figur (Text zu Bild, dann Bearbeiten) ein **Drehblatt** mit vier Ansichten (vorn, links 90°, hinten, rechts 90°,
schwarzer Hintergrund, 4096 × 1024), das wird in vier Felder geschnitten, freigestellt, und **Pixal3D Multiview** rechnet
daraus ein texturiertes 3D-Modell (GLB, PBR). Funktioniert für Figuren und Requisiten; ~12 GB VRAM beim Autor, 3D-Schritt
300 s auf einer RTX 5080. Kein Blick von oben/unten (höchstens 4 Ansichten).

- **Stand bei uns:** ComfyUI 0.37.0 (21.09.2026) enthält die Pixal3D-Knoten schon (`Pixal3DMultiViewConditioning`,
  `Pixal3DConditioning`, Trellis-2-Stufen, Mesh-Nachbearbeitung, `RenderMesh`, `Save3DAdvanced`; PR #16048 vom 08.09.);
  die Vorlagen `3d_pixal3d_multi_views.json` und `3d_pixal3d_trellis2_image_to_model.json` liegen im ComfyUI-venv. Nötige
  Pakete (scipy, kornia, PIL) sind da – **kein Update, keine Pakete, keine eigenen Knoten nötig.** Qwen-Image 2.1 INT8,
  Text-Encoder, VAE und BiRefNet haben wir. **Es fehlen nur Modelle:** `pixal3d_multiview_int8_convrot` (5,2 GB),
  `trellis_2_shape_vae_bf16` (1,02 GB), `trellis_2_texture_vae_bf16` (0,9 GB), `dino_v3_L_naf_fp32` (1,13 GB) – zusammen
  ≈ 8,3 GB (Comfy-Org/Pixal3D). Für **Einzelbild → 3D** (ein Foto, ohne Drehblatt) zusätzlich `pixal3d_int8_convrot`,
  `trellis_2_int8_convrot` und `moge_2_vitl_normal_fp16` (≈ 10 GB). Platz: C: 2,7 TB frei. Lizenz: Pixal3D und die
  Comfy-Org-Dateien MIT; Drittkomponenten (DINOv3 von Meta) behalten ihre eigene Lizenz – vor gewerblicher Nutzung prüfen.
  Auf dem PC gibt es keinen GLB-Betrachter (kein 3D-Viewer, kein Blender); ComfyUIs eigener Load-3D-Knoten zeigt GLB an.
- **Test Drehblatt (nur Qwen, Turbo, Format Panorama 4:1, Studio-Projekt „Garten-OS Design“):** Anna (Gemüsegärtnerin,
  `Freigestellt_00001_` als Vorlage, Prompt des Videos auf „gleiche Haltung mit Gießkanne“ angepasst) → `Bearbeitet_00003_`
  (36 s) und `_00004_` (26 s): beide mit echten 90°-Profilen (ein Auge), schwarzem Hintergrund, vier gleich großen Feldern,
  Stil erhalten; `_00003_` zieht hinten die Schürze über den ganzen Rücken (Fehler), `_00004_` ist sauber → wie im Video
  zwei Nummern rechnen und wählen. Requisit Hochbeet (`Bild_00015_`, 9 s) → `Bearbeitet_00005_` (31 s): **gescheitert**,
  alle vier Felder zeigen die Längsseite von vorn, nur die Gießkanne wandert – bei langen Kästen dreht Qwen nicht, trotz
  Beschreibung der Schmalseite. Für solche Gegenstände wäre der Einzelbild-Weg (symmetrisch, Rückseite egal) sinnvoller.
- **Vorschlag Studio (Stufe 3t, nur auf Auftrag):** (1) Vorschlag „Drehblatt (4 Ansichten)“ beim Bearbeiten (Panorama 4:1,
  Turbo, Prompt-Vorlage für Figur und Gegenstand) plus Skill-Befehl `drehblatt` – geht heute ohne Download.
  (2) Neue Art „3D-Modell“ (`modell3d`): Vorlage = Drehblatt aus der Bibliothek (Viertel schneiden, BiRefNet, auf
  1024² mit Rand 1,1 auf Schwarz) oder bis zu vier Einzelbilder oder ein Bild (Einzelbild-Modell); Graph nach der
  Comfy-Org-Vorlage (Struktur 20 Schritte, Form 12, Textur 12, Upsample 1536, Remesh 768, 700k Dreiecke, UV 2048,
  Textur 2048); Ausgabe `<Projekt>\Modell_00001_.glb` plus Vorschaubilder über `RenderMesh` (vier Ansichten) für die
  Bibliothek; GPU-Sperre und `/api/platz` wie Videos (Bedarf schätzen, dann messen; VRAM auf der 3090 unbekannt, laut
  Quellen 12–15 GB). Danach STUDIO.md, Skill (`modell3d`), Messung Zeit je Modell.
- **Vorschlag Garten-OS:** DESIGN.md sagt für den Figurenstil bindend „kein 3D“ – Sascha entscheidet, ob 3D als
  **Zusatz** erlaubt ist. Sinnvolle Einsätze: (a) **Requisiten als 3D** (Hochbeet, Kübel, Tunnel, Gießkanne, Werkzeuge)
  für E6 Beetplan/Beetraster – einmal gebaut, aus jedem Winkel gleich; als isometrische Renderings (RenderMesh) oder später
  echter 3D-Planer; (b) **gleiche Gegenstände in allen Illustrationen** (E5): 3D-Rendering im gewünschten Winkel als
  Vorlage für „Bearbeiten“ im Stilblatt-Stil; (c) **Anna und Team drehbar** auf der Teamseite (Web-Betrachter in der App,
  nicht in der Werkstatt) – Pixal3D-Meshes sind starr (keine Posen/Animation), Nutzen eher Schauwert. Pflanzen mit feinen
  Blättern sind für 3D-Generatoren schwer – niedrige Erwartung.

### Stufe 3t: 3D-Modelle mit Pixal3D (11.10.2026)

**Auftrag Sascha 11.10.2026** („ja überrasch mich mal was geht“) zu den drei Fragen aus „Bewertet … Pixal3D“: Modelle
laden, Art „3D-Modell“ bauen, Drehblatt-Vorschlag einbauen, 3D im Garten-OS als Zusatz. Geladen von Comfy-Org (SHA-256
geprüft, `laden_pixal3d.log`): `pixal3d_multiview_int8_convrot` (5,58 GB), `trellis_2_shape_vae_bf16` (1,10 GB),
`trellis_2_texture_vae_bf16` (0,95 GB), `dino_v3_L_naf_fp32` (1,22 GB), `pixal3d_int8_convrot` (5,58 GB, Einzelbild),
`moge_2_vitl_normal_fp16` (0,66 GB, Blickwinkel) – zusammen 15,1 GB. `trellis_2_int8_convrot` (5,25 GB) **nicht** geladen:
die Comfy-Org-Vorlage nutzt es nur im TRELLIS.2-Modus, Pixal3D braucht es nicht.

**Gebaut (Werkstatt, Kernknoten, keine neuen Pakete):**
- Art `modell3d` (`werkstatt\studio.py`: `modell3d_graph`, `_modell3d_pruefen`, `_modell3d_ablegen`; Einstellung
  `studio.modell3d` in `config.json`). Vorlage = ein Drehblatt (Rolle `vorlage`, erkannt an Breite ≥ 3 × Höhe), ein Bild
  (Modus `bild`: Pixal3D-Einzelbildmodell, Blickwinkel über MoGe) oder Einzelansichten (Rollen `vorn`/`links`/`hinten`/
  `rechts`, mindestens `vorn`). Graph nach den Comfy-Org-Vorlagen: je Ansicht BiRefNet-Maske + `ImageCropToMask` 1024²
  (Rand 1,1, Schwarz) → `Pixal3DMultiViewConditioning` (FOV 20) bzw. `Pixal3DConditioning` → Struktur (12 Schritte,
  CFG 7,5 mit Override ab 66,7 %, Rescale 0,7, Shift 5) → Form (20) → feine Form (12, `target_resolution` 1536/1024) →
  Textur (12, CFG 1) → `RemeshMesh` 768 (udf) → `DecimateMesh` → `UnwrapMesh` → `BakeTextureFromVoxel` (+ Normalen und
  Verschattung bei „fein“) → `ApplyTextureToMesh` → `SaveGLB`. Dazu ein Drehteller als Vorschau: 24 × `RotateMesh`
  (15°-Schritte um die Hochachse) + `RenderMesh` 768² auf Weiß → `CreateVideo` 12 Bilder/s (2 s Schleife) → `SaveVideo`.
  Die GLB bekommt danach den Stamm des Videos (`Modell_00001_.glb` neben `Modell_00001_.mp4`); Begleitdaten des Videos
  nennen sie (`modell_3d`, `modell_3d_bytes`); Verschieben und Papierkorb nehmen sie mit; `/studio/datei` liefert sie
  (`model/gltf-binary`). Variationsnummer = Seeds der vier Sampler (gleiche Nummer, gleiches Modell); Detailstufen `fein`
  (1536, 700.000 Dreiecke, 2K-Texturen mit Normalen) und `leicht` (1024, 150.000, 1K). Bedarf 16 GiB auf der 3090
  (Schätzung), Zeit nachgelernt je Stufe (Median der eigenen Läufe).
- Oberfläche: Art-Gruppe „3D“ (nur sichtbar, wenn die Dateien da sind), Feld „Detailstufe“, Kachel-Marke „3D-Modell ·
  Vorschau“, Großansicht mit „GLB speichern …“, „Im Ordner zeigen“ und „In ComfyUI ansehen“ (dort zeigt der Load-3D-Knoten
  die Datei drehbar; einen GLB-Betrachter hat Windows hier nicht), Knopf „3D-Modell“ in der Großansicht jedes Bildes,
  Vorschläge „Drehblatt (Figur)“ und „Drehblatt (Gegenstand)“ beim Bearbeiten (Panorama 4:1, Turbo).
- Skill `bild-video-studio`: `drehblatt <bild> [--gegenstand] [--haltung …]`, `modell3d <drehblatt|bild> [--stufe] [--modus]`
  bzw. `--vorn/--links/--hinten/--rechts`; `status` meldet `modell3d`, `modell3d_bild`.
- Tests: `werkstatt\tests\test_modell3d.py` (Prüfung, Graphen, Ablage, Verschieben/Papierkorb, Bildmaße aus PNG/JPEG/WebP).
  Werkstatt-Tests 171 OK.

**Abnahme am echten System (11.10.2026, RTX 3090, über Werkstatt und Skill, Projekt „Garten-OS Design“):**

| Lauf | Vorlage | Stufe | Zeit | GLB | Befund |
|---|---|---|---|---|---|
| `Modell_00002_` | Drehblatt `Bearbeitet_00004_` (Anna mit Gießkanne) | fein | 191 s | 39,8 MB | von allen Seiten stimmig (Hut, Schürzenbänder, Hose); Hände und Kanne matschig, dunkler Fleck auf der Schürze |
| `Modell_00004_` | Drehblatt `Bearbeitet_00007_` (A-Haltung, leere Hände; Skill `drehblatt --haltung …`, 2 Variationen 38/26 s, beide sauber) | fein | 201 s | 39,7 MB | Hände mit Fingern, Seiten und Rücken sauber; gebackene Schatten machen die Schürze fleckig, Gesicht weicher |
| `Modell_00006_` | dieselbe | leicht | **52 s** | **6,3 MB** | gleiche Form, flächiger und im Illustrationsstil stimmiger – erste Wahl für Figuren und Web |

Spitze 12.810 MiB auf der 3090 (ComfyUI hielt davor 9.443 MiB mit Qwen) → Bedarf 13.312 MiB in der Einstellung;
Zeitschätzung lernt aus den Läufen (fein 201, leicht 52). Vorschau-Video 24 Bilder 768², 12 Bilder/s, ~180 KB; die
GLB erscheint in der Großansicht mit „GLB speichern …“. Die Zählung von ComfyUI springt (GLB und Video zählen getrennt
hoch, die GLB wird auf den Stamm des Videos umbenannt): `Modell_00002_`, `_00004_`, `_00006_`.
**Regel aus dem Test:** Figuren für das Drehblatt in A-Haltung mit leeren Händen; Dinge als eigenes Modell. Drehblatt mit
Gegenstand (Hochbeet) scheiterte an Qwen (dreht nicht) – dafür der Einzelbild-Weg:

| Lauf | Vorlage | Stufe | Zeit | GLB | Befund |
|---|---|---|---|---|---|
| `Modell_00008_` | `Bild_00015_` (Hochbeet mit Tomaten und Gießkanne, ein Bild; Pixal3D Einzelbild + MoGe) | leicht | 114 s | 7,0 MB | von vorn sehr gut (Kasten, Erde, Stäbe, Kanne); Rückseite plausibel erfunden; Pflanzen werden flache Kulissen (dünne Blätter) – für Beetplan-Ansichten von vorn/schräg oben brauchbar, nicht für Nahaufnahmen von hinten |

Spitze dabei 13.689 MiB (ComfyUI startete leer mit 2.783 MiB) → Bedarf auf 14.336 MiB gesetzt.
**Stand:** Stufe 3t fertig und abgenommen; Werkstatt-Tests 171 OK. Garten-OS: Vorschlag als Nachtrag N4
(`Workspace\Missions\2026-10-11 Garten-OS N4 3D-Figuren Sol.md`), wartet auf Saschas Go. Testdateien bleiben im Projekt
„Garten-OS Design“ (Modelle `Modell_00002_`, `_00004_`, `_00006_`, `_00008_`; Drehblätter `Bearbeitet_00003_`–`_00007_`;
Hochbeet `Bild_00015_`) als Belege und Material für N4.

### Bewertet 11.10.2026: „QWEN IMAGE 2.1 EDIT LORA TRAINING! LESS THAN 10GB VRAM!“ (festgehalten, nichts geändert)

Quelle: YouTube `_YF8GC6Qd2I` (Aitrepreneur, 11.10.2026), Beschreibung und Transkript von Sascha eingefügt. Inhalt: eigene
**Edit-LoRAs** für Qwen-Image 2.1 mit **AI Toolkit** (Ostris) trainieren – lokal ab ~10 GB VRAM oder auf RunPod. Datensatz
= zwei Ordner mit gleichnamigen Bildern: „control“ (Ausgangsbilder) und „target“ (gewünschte Bearbeitung), dazu je
Zielbild dieselbe kurze Anweisung als Caption („transform the image into …“); ~20 Paare reichen, Rang 64 statt 32,
Standardmodell 2.1 (nicht Turbo), Text-Embeddings zwischenspeichern, 512 px genügt, ~1.000 Schritte, Zwischenstände
250/500/750/1.000 in ComfyUI nebeneinander vergleichen. FluxGym-Alternative laut Autor schlechter.

- **Was uns das bringen könnte:** (a) **Garten-OS-Stil als Edit-LoRA** – Paare „Foto → Illustration im Stilblatt S2-a“
  (die Zielbilder kann das Studio heute schon per Bearbeiten erzeugen), danach jede Illustration mit einem festen Satz
  statt langem Stil-Prompt und mit gleichmäßigerem Strich; (b) ein **Drehblatt-LoRA** (Stufe 3t), falls Qwen bei
  Gegenständen weiter nicht dreht; (c) Praxis-Bildstil. Nutzen erst bei vielen Bildern derselben Art; heute reicht meist
  das Stilblatt als Vorlage.
- **Was es braucht:** AI Toolkit ist eine eigene Python-Umgebung (PyTorch, Diffusers, mehrere GB) – fällt unter „keine neuen
  Umgebungen ohne Auftrag“. Training lokal auf der 3090 (24 GB) möglich, dabei kein Studio/Whisper daneben (GPU-Sperre).
  RunPod wäre Cloud mit Konto – macht Sascha.
- **Auftrag Sascha 11.10.2026 (abends): Umsetzung am 12.10.2026** („merk dir das 2. Video für morgen zur Umsetzung“).
  Vorher klären: lokal (AI Toolkit als eigene Umgebung auf der 3090) oder RunPod; welches LoRA zuerst (Vorschlag:
  Garten-OS-Stil, Zielbilder aus dem Studio); Training nie neben Studio/Whisper.

## Stufe 5: Eigene Edit-LoRAs für Qwen-Image 2.1 mit AI Toolkit (12.10.2026; v1 geprüft, nicht übernommen)

**Auftrag Sascha 12.10.2026** (Umsetzung des Videos „QWEN IMAGE 2.1 EDIT LORA TRAINING“, s. o.); Entscheidungen: lokal auf der
Workstation, erstes LoRA „Garten-OS-Stil“ (Foto → Illustration im Stilblatt S2-a), Garten-OS-Nachtrag N4 läuft parallel bei Sol.

**Eingerichtet (eigene Umgebung, außerhalb von KI-Zentrale und ComfyUI):** AI Toolkit (Ostris, MIT, Stand `f7a1fb9` vom
09.10.2026) unter `C:\LLM\runtimes\ai-toolkit` mit eigenem venv (Python 3.12.14 aus uv, torch 2.13.0 cu130; Treiber 616.92,
CUDA 13.4). Befund aus dem Quelltext (`extensions_built_in/diffusion_models/qwen_image_2`): Qwen-Image 2.1 ist eine
Architektur für Text-zu-Bild **und** Bearbeiten (mit `control_path` im Datensatz wird es ein Edit-LoRA); der Transformer
wird **aus der Comfy-Org-Datei** geladen – wir nehmen unsere vorhandene `qwen_image_2.1_int8_convrot.safetensors`
(vorquantisiert, kein Quantisierungslauf). Text-Encoder und VAE: geplant aus `Qwen/Qwen-Image-2.1` (Hugging Face,
`HF_HOME=C:\LLM\hf-cache`, ohne den 14-GB-Transformer, 18 GB geladen). **Korrektur beim ersten Lauf:** Für `qwen_image_2`
lädt AI Toolkit Text-Encoder und VAE im ComfyUI-Aufbau aus `MODELS_PATH` (Comfy-Org-Repack) und begann, den 16-GB-Text-
Encoder ein zweites Mal herunterzuladen; Lauf beendet, Teildatei entfernt, `MODELS_PATH` auf ComfyUIs Modellordner gesetzt –
seitdem nimmt es unsere vorhandenen Dateien an Ort und Stelle. Der HF-Cache (18 GB) wird dafür nicht gebraucht
(Löschen entscheidet Sascha). Die Oberfläche von AI Toolkit
(Node, Port 8675) wurde nicht gebaut; gesteuert wird über YAML und `run.py`.

**Datensatz `C:\Workstation\Arbeitsmaterial\LoRA-Training\garten-stil-v1`** (20 Paare, alle aus dem Studio, Projekt
„Garten-OS Design“, `paare.json` = Herkunft): `control\gNN.png` = fotorealistisches Gartenfoto (12 Szenen: Hochbeete,
Kompost, Anzucht, Folientunnel, Permakultur, Schädlinge, Hydroponik, Schubkarre, Ernte, Kartoffelfeld, Apfelbaum,
Frühbeet; 8 mit Personen), `target\gNN.png` = dieselbe Szene als Illustration (Bearbeiten, 1 MP, Turbo), `target\gNN.txt`
= feste Anweisung „Zeichne das Bild als Garten-Illustration: klare dunkle Konturen, flächige kräftige Farben, weiche
Schatten; kein Foto, kein 3D.“ Befund beim Erzeugen: mit dem **Stilblatt** als Bild 2 setzte Qwen bei Szenen ohne
Personen die Gemüsegärtnerin ins Bild (2 von 2); mit der illustrierten Gartenszene `Bild_00013_` als Stilvorlage blieb
die Szene unverändert. Deshalb Szenen mit `Bild_00013_`, Personenfotos mit dem Stilblatt; je zwei Variationen, Wahl per
Kontaktbogen (`auswahl.json`). Zwei Fotos außerhalb des Datensatzes für den Vergleich: `Bild_00038_` (Gartenhaus),
`Bild_00039_` (Frau pflückt Äpfel).

**Konfiguration** `C:\LLM\runtimes\ai-toolkit\config\garten_stil_v1.yaml` (nach dem Video): LoRA Rang 64, 512 px, Batch 1,
1.000 Schritte, adamw8bit, lr 1e-4, Text-Embeddings zwischengespeichert, Zwischenstände alle 250 Schritte (behalten),
kein Sampling (Vergleich in ComfyUI: `lora_vergleich.py`, derselbe Graph wie die Werkstatt mit dem trainierten LoRA im
Knoten 25). **Training auf der RTX 3080** (gpu:1): ComfyUI behält seine Modelle auf der 3090 (Entladen bleibt der Zentrale
mit Bestätigung vorbehalten); Start nur über das Platz-Tor (`training_lauf.py`: keine Werkstatt-Aufträge, Bedarf 14 GiB
auf Karte 1 angemeldet und gehalten).

**Lauf (12.10.2026, 11:05–11:59):** 54 min für 1.000 Schritte (2,2–3,3 s je Schritt, Eimer 576×448 und 480×544),
16,3 GB auf der 3080, 192 LoRA-Module, Zwischenstände 250/500/750/1.000 (je 319 MB). ComfyUI lädt das LoRA ohne
Warnung („192 patches attached“).

**Ergebnis: kein Gewinn, nicht übernommen.** Vergleich mit `lora_vergleich.py` (gleiche Nummer, Anweisung wie im
Training) an zwei Fotos außerhalb des Datensatzes (`Bild_00038_` Gartenhaus, `Bild_00039_` Frau mit Äpfeln), je ohne LoRA
und mit allen vier Ständen, mit Turbo-Modell und mit 20 Schritten; dazu als Referenz das Rezept der Trainingsziele
(Foto + Stilvorlage) und zwei Trainingspaare (`g07`, `g13`):
- Die **Anweisung allein** liefert schon denselben Stil wie die Trainingsziele (klare Konturen, flächige Farben). Auch
  bei den Trainingspaaren sind Ziel, „ohne LoRA“ und LoRA 1.000 praktisch gleich. Das LoRA hatte also nichts zu lernen,
  was Qwen nicht schon aus dem Text kann; die Stilvorlage als Bild 2 trug beim Erzeugen der Ziele kaum etwas bei.
- **Mit LoRA** (alle Stände, Turbo und 20 Schritte gleich): Bilder eher weicher und gemalter, Konturen schwächer,
  Farben etwas näher am Foto (Holz der Hütte heller). Für den Garten-OS-Stil eher ein Rückschritt.
- **Übernommen:** Vorschlag „Als Garten-Illustration“ (Bearbeiten, wie Vorlage 1, nur die Anweisung) in der Oberfläche
  und als Skill-Befehl `garten`; am echten System geprüft (Skill → Werkstatt, Turbo, 1184×896; Vorschlag setzt in der
  Oberfläche Anweisung und Größe). Grenze: graues, verwittertes Holz wird honiggelb.
- Eine Anbindung eigener Stil-LoRAs (Auswahl „Stil“, Knoten 29 nach der Detail-LoRA, wie `details`) war gebaut und
  getestet, wurde mangels tauglichem LoRA wieder entfernt – nachbauen, wenn ein LoRA den Test besteht.

**Lehre für das nächste Edit-LoRA:** Die Zielbilder müssen etwas zeigen, das Qwen aus Anweisung und Vorlage **nicht**
schon kann – etwa Annas Figurenstil S2-a genau (Gesichter, Proportionen; das gelang mit dem Stilblatt als Bild 2 nicht),
eine feste Umwandlung wie „Foto → Beetplan von oben“ oder ein Stil aus von Hand ausgewählten Zielen. Vorher prüfen:
Zielrezept gegen „nur Anweisung“; sind sie gleich, lohnt kein Training. Training mit 1.024 statt 512 px erwägen.
Werkzeuge im Scratchpad dieser Sitzung (`training_lauf.py`, `lora_vergleich.py`, `stil_referenz.py`); AI Toolkit und
venv bleiben eingerichtet (4,4 GB).

**Aufgeräumt (12.10.2026, Auftrag Sascha „aufräumen und Toolkit behalten“):** in den Papierkorb – Trainingsordner
`Arbeitsmaterial\LoRA-Training` (1,6 GB, Datensatz und Stände), vier Kopien der Stände in ComfyUIs LoRA-Ordner
(`garten_stil_v1_*`), Vergleichsbilder `Studio\_versuche\lora`, HF-Cache `C:\LLM\hf-cache` (17,6 GB); das Testbild
`Bearbeitet_00002_` hat Sascha selbst entfernt. **Behalten:** AI Toolkit mit venv (`C:\LLM\runtimes\ai-toolkit`, 4,4 GB)
samt Konfiguration `config\garten_stil_v1.yaml` als Vorlage für das nächste LoRA. Die Bilder des Datensatzes im Studio-
Projekt „Garten-OS Design“ (Fotos und Stilfassungen) bleiben dort.

## Stufe 4: Texterkennung mit LightOnOCR-3 (11.10.2026, fertig)

**Anlass und Auftrag:** Test der Sitzung „Tesla V100“ (Nachweis
`C:\Workstation\Projekte\Lokale-Wissensextraktion\nachweise\LightOnOCR-3-Test-2026-10-11\Auswertung.md`):
LightOnOCR-3-4B liest PDFs, Scans und Tabellen deutlich besser als die Windows-OCR (Zeichen 99,5 % statt 92–96 %,
alle Zahlen in Tabellen und Bögen, Scans praktisch wie saubere Seiten), Q4_K_M so gut wie Q8_0 und schneller.
Sascha hat Ja zum Einbau in Modellzentrale und Werkstatt gesagt (über die Sitzung „Tesla V100“ und hier).
Entscheidungen Sascha 11.10.2026: Seitenbilder über das **vorhandene PDF-Werkzeug** (PyMuPDF in
`Werkzeuge\PDF\venv`, externer Aufruf wie watch); Ablage **`Arbeitsmaterial\Texterkennung\<Name>\`**, Markdown je
Seite plus Volltext, Quelle unverändert. Keine Downloads: Modell und llama.cpp lagen schon von dem Test vor.

**Modellzentrale:** neue Art `llamacpp` (allgemein für llama.cpp-Server), Eintrag `lightonocr` in eigener Gruppe
„Texterkennung“: `llama-server.exe` (b10754) mit `-m …Q4_K_M.gguf --mmproj …mmproj-f16.gguf --host 127.0.0.1
--port 8096 --alias lightonocr-3-4b -ngl 99 -c 16384 -np 1 --jinja --chat-template-kwargs {"enable_thinking":false}
--image-max-tokens 4096 --no-webui`, nur `CUDA_VISIBLE_DEVICES=1` mit `CUDA_DEVICE_ORDER=PCI_BUS_ID` (RTX 3080),
Bedarf 4.700 MiB. Bereit über `/health` (503 beim Laden). Erkennung und Beenden nur bei passendem Programmpfad,
`--port 8096` und Modelldatei in der Kommandozeile; Protokoll `logs\lightonocr.*.log`. Die Belegung erscheint jetzt
als „LightOnOCR-3 · Texterkennung“ statt unter „Windows & Programme“, mit Schritt „beenden“ für Planung und
„GPU freigeben“.

**Werkstatt:** Reiter „Texterkennung“ („PDF/Scan lesen“), `werkstatt\texterkennung.py`, `werkstatt\pdf_seiten.py`
(läuft im PDF-venv, liest nur, liefert die Seiten als Base64 über die Standardausgabe – keine Zwischendateien),
`web\texterkennung.js`. Anfrage wie Modellkarte und Test: nur das Bild (leerer Prompt = Transkription),
Temperatur 0,2, top_p 0,9, höchstens 4.096 Token, Seed 1, Thinking aus; PDF-Seiten mit längster Kante 2.048 px,
Bilder nur verkleinert. Je 4 Seiten gerendert, dann unter der GPU-Sperre gelesen; vorher `/api/platz` ohne
Anmeldung (das Modell belegt seinen Speicher schon beim Start), bei Gründen der Zentrale wird gewartet. Nutzt
LightOnOCR nur, wenn die Zentrale es gestartet hat (`/v1/models` mit `lightonocr-3-4b`). Abbrechen/Fehler behalten
fertige Seiten, „Fortsetzen“ macht im selben Ordner weiter (gleiche Prüfsumme und Seitenwahl). Abgeschnittene Seiten
(Längengrenze) werden gemeldet und im Volltext markiert.

**Abnahme 11.10.2026 (Claude):** 54 Zentrale-Tests (9 neu) und 165 Werkstatt-Tests (13 neu) grün. Live:
- Zentrale: „Starten“ → bereit nach 4 s, 4.311 MiB auf der RTX 3080, richtig benannt; „Port 8096 · RTX 3080“.
- Planung: Strata-Start schlägt „LightOnOCR-3 · Texterkennung beenden“ vor; „GPU freigeben“ bietet es an (4.535 MiB).
- Werkstatt: `druck-lernen.pdf` (Sehnen-Lernfassung), Seiten 2–4 und 8 (Grafik, Fließtext, Tabellen) in 28 s
  (4,7–8,6 s je Seite), simulierter Scan `knie-s01-scan.jpg` in 9 s. **Alle fünf Seiten byte-gleich** mit der
  ausgewerteten Q4_K_M-Ausgabe des Tests (Seed 1) – die Werkstatt liefert genau die gemessene Qualität.
  Die Testergebnisse (`druck-lernen`, `knie-s01-scan`, `Ruecken-Routinen fuer den Bueroalltag`) liegen seit
  11.10.2026 auf Saschas Wunsch im Papierkorb (rückholbar); die Vergleichstexte bleiben im Testordner der anderen Sitzung.
- „Beenden“ in der Zentrale: Speicher frei, Werkstatt zeigt „läuft nicht“ mit Knopf zur Zentrale.

**Grenzen (aus dem Test, gelten weiter):** wenige, aber echt aussehende Fehlwörter (über Seeds und Q8/Q4 gleich) –
Hinweis im Reiter und Status „nicht geprüft“ im Volltext; Abbildungen nur als Platzhalter `![image](image_N.png)`;
bei Bildschirmfotos schwanken Randbereiche, kleine Monospace-Schrift teils falsch. Nicht gleichzeitig mit Strata
(Planung lässt LightOnOCR weichen).

**Skill `texterkennung` (Auftrag Sascha „ja skill bauen“, 11.10.2026):** `C:\Workstation\Skills\aktiv\texterkennung`
(SKILL.md, `scripts\ocr.py`, `agents\openai.yaml`), verknüpft für Claude, Codex und Hermes; Eintrag in
`Skills\BETRIEB.md`, Verweis in `wissens-notebook`. `ocr.py lesen` startet Zentrale, Werkstatt und LightOnOCR bei
Bedarf – LightOnOCR nur, wenn der Plan der Zentrale keine Schritte braucht (sonst Exit 3, „Sascha fragen“) – wartet
und beendet ein selbst gestartetes Modell danach wieder, wenn keine anderen Aufträge offen sind. Dafür liefert
`hinzufuegen` jetzt die Auftrags-IDs (`auftraege`, auch für schon offene Doppel). Abnahme: aus dem Zustand „aus“
Rücken-Ratgeber S. 5 (Plan-Tabelle) in 10,8 s gesamt (Start, 4 s Lesen, Beenden), Seite byte-gleich mit dem Test,
LightOnOCR danach wieder aus; „kein Platz“, „Port fremd“ und „andere Aufträge offen“ gestellt geprüft.

**Nicht gemacht (nur auf Auftrag):** Grounding-Modus (Blöcke mit Koordinaten), Seitenbild und Text nebeneinander
zum Stichproben-Prüfen. Im Modellordner
`C:\LLM\models\LightOnOCR-3-4B` liegen nur noch Q4_K_M und mmproj (Q8_0 war bei Baubeginn schon nicht mehr da).

**Kartenliste statt fester Karte (13.10.2026, Auftrag Sascha):** Wegen des GPU-Umbaus können sich die Kartennummern
verschieben; die Übergangslösung `karte: 0` ist im Code und in der Konfiguration abgelöst. Während des Umbaus war
nur eine RTX 3090 sichtbar (Index 0); der erste McRae-Lauf mit 273 Buchseiten lief auf ihr (Modell „bereit“, ~7 GiB).
`lightonocr` hat jetzt `karten: ["RTX 3080", "RTX 3090"]` und `bedarf_je_karte_mib: 4700`. Zuordnung nach dem
gemessenen Namen aus nvidia-smi, je Wunschname aufsteigend nach Index: Die erste Wunschkarte mit genug freiem
Speicher einschließlich Reserve und Anmeldungen wird ohne Beenden/Entladen gewählt. Passt keine, plant die Zentrale
Schritte für die erste vorhandene Wunschkarte; fehlt jede Wunschkarte, wird der Start mit Grund abgelehnt.
Startumgebung und Platzprüfung bekommen die gewählte Karte. Zentrale, Werkstatt und Skill zeigen die wirklich
genutzte Karte aus dem gemessenen llama.cpp-Verbraucher (größter Anteil ab 256 MiB), sonst keinen Kartennamen.
Allgemeine Kartenbeschriftungen stammen ebenfalls aus der Messung; die Konfiguration ist nur Rückfall bei fehlendem
Namen, gleiche Namen werden mit „· Nr. <index>“ unterschieden. Die Werkstatt liest GET `/api/status` ohne Autostart,
höchstens alle 5 s. Der OCR-Skill startet nur ohne Freigabeschritte; sonst Exit 3 mit Kartenwunsch, Hinweisen und
Gründen. Gebaut von Codex Sol 6.1 (high) nach Claudes Vorgabe; Claude hat den Unterschied gelesen und nachgebessert
(Werkstatt fragt die Karte ohne die Auftragssperre ab). Beide Testsuiten grün (76 Zentrale-Tests, 180 Werkstatt-Tests).
Hinweis: Nach dem Umbau müssen die **festen Kartennummern der übrigen Einträge** (Ninfer `karte`/`bedarf_mib`, Ornith,
Strata, bild-video, Werkstatt-Transkription) geprüft werden – nicht Teil dieses Auftrags.

**Abnahme 13.10.2026 (Claude), Umbau noch nicht fertig (nvidia-smi: nur RTX 3090, Index 0, Bus 02):** Zentrale und
Werkstatt nach der Regel neu gestartet (keine Aufträge offen). Das schon laufende LightOnOCR zeigten Zentrale
(„Port 8096 · RTX 3090“, Belegungsleiste RTX 3090 mit 4,5 GiB), Werkstatt (`modell.karte` „RTX 3090“) und
`ocr.py status` (`karte`) richtig an. Dann über die Zentrale beendet; `/api/plan` wählte Karte 0 „RTX 3090“ ohne
Schritte (3080 fehlt → Ausweichkarte). `ocr.py lesen ruecken-s05.png --laufen-lassen` (Plan-Tabelle aus dem Test vom
11.10.) startete LightOnOCR („gestartet auf Karte 0, PID 18000“, nvidia-smi: llama-server auf der RTX 3090), las die
Seite in 4 s, Exit 0; Text inhaltsgleich mit `Q4_K_M-seed1` des Tests. LightOnOCR läuft danach weiter (lief vorher).
Ergebnisordner `Arbeitsmaterial\Texterkennung\ruecken-s05` liegt noch dort. **Offen nach dem Umbau:** einmal prüfen,
dass bei freier 3080 die 3080 gewählt wird und die Beschriftung der drei Karten stimmt.

## Bewertet 13.10.2026: „ClickDesigns X“ – 3D-Mockups nachbauen (Plan mit Astra xhigh, nichts geändert)

Auftrag Sascha: Produkt https://clickdesignsx.com/brand-new/ analysieren (Seite, Bilder, Videos) und klären, was wir lokal
nachbauen können. Am öffentlichen Betrachter (`create.clickdesigns.com/mockup_preview/628`) beobachtet: three.js r165,
Buchmodell als Blender-GLB mit Teil `Replacer-Cover`, das Design-PNG wird als Textur getauscht, HDR-Licht – keine KI.
Ergebnis: Hauptweg **eigene 3D-Modelle (Code, später Blender) + Design als Textur + three.js 0.186.1** (liegt lokal, MIT),
KI nur für Szenen-Hintergründe und Sonderformen; nicht: Editor, Vorlagen-/Stockbestand, KI-3D mit lesbarem Etikett.
Optional später als Browser-Baustein in Praxis-OS (S4). Plan und Review-Log (4 Runden, APPROVED):
`AI-Knowledge-System\Workspace\Handoffs\2026-10-13 Mockup-Studio nach ClickDesigns X Plan.md` und `… Astra-Review-Log.md`.
Nächster Schritt nur auf Auftrag: Vorversuch M0a/M0b; Blender 5.2.2 LTS portabel (386 MB) nur nach Saschas Ja.
**14.10.2026 (Auftrag Sascha „M0a starten, Blender laden“):** Blender 5.2.2 LTS portabel unter `C:\LLM\runtimes\blender-5.2.2`
(Zip von blender.org, SHA-256 geprüft, Ordner `portable` → keine Einstellungen in AppData; Zip gelöscht). **M0a bestanden**
(nur Software-WebGL in Edge, keine GPU, KI-Zentrale unverändert): Geometrie max. 0,17 px, unbeleuchtete Farben exakt,
Schrift ab 10 px lesbar, pixelgleich auch nach Neustart, Standbild 2048 px in 0,14–1,3 s, Speicherspitze 1,95 GB (SSAA 2×).
Beleuchtete Cover-Farben brauchen kalibriertes Licht ohne Tonemapping. Messakte
`AI-Knowledge-System\Workspace\Experimente\2026-10-14 Mockup M0a\Bericht.md`.

## Stufe 6: Zwei RTX 3090, freie Kartenwahl (14.10.2026, fertig)

Auftrag Sascha: „Zwei RTX 3090 (FE und Suprim, je 24 GB), die 3080 ist erstmal raus. Alle Einträge ändern, Zentrale und
Werkstatt für beide Karten umbauen. Verschiedene Modelle können auf einer Karte laufen, wenn genug Platz ist; die feste
Zuordnung 3080/3090 ist nicht mehr nötig.“

**Hardware (gemessen):** Karte 0 = Steckplatz 02 = RTX 3090 **FE** (Teilenummer 900-1G136-2510-000, 350 W, kein Monitor);
Karte 1 = Steckplatz 04 = RTX 3090 **Suprim** (420 W, Monitor, Windows belegt 0,6–0,9 GiB). CUDA zählt in beiden
Reihenfolgen (FASTEST_FIRST und PCI_BUS_ID) gleich. Im Task-Manager: GPU 0 Intel, GPU 1 = FE, GPU 2 = Suprim.

**Umbau:**
- Kartennamen nach Steckplatz (`zentrale\config.json` `karten` mit `bus` und `name`, `gemeinsam\gpu.kurznamen`): „RTX 3090
  FE“ und „RTX 3090 Suprim“; passt Steckplatz oder Kartenmodell nicht, gilt der gemessene Name. nvidia-smi liefert jetzt auch
  `display_attached` (Feld `monitor`).
- Zentrale, drei Bedarfsarten (README „Kartenwahl“): `karten` + `bedarf_je_karte_mib` (NInfer, LightOnOCR, ComfyUI) – engste
  passende Karte, Monitorkarte nur bis 2 GiB Rest (`monitor_puffer_mib`), sonst wenigstes Freigeben; `bedarf_gesamt_mib`
  (Ornith Q5/Q4, Ollama verteilt selbst) – freier Platz aller Karten zusammen, kleinstes einzelnes passendes Modell zuerst;
  `bedarf_mib` fest (Strata, beide Karten). NInfer startet mit `CUDA_VISIBLE_DEVICES=<Karte>` und `--device 0`.
- Studio (`karten_waehlen`, Bedarf je Rolle `eine`/`haupt`/`neben`/`fest`): Bild ganz auf einer Karte (wo ComfyUI schon
  Speicher hält, sonst die engste), sonst Modell auf der einen, Text-Encoder und VAE auf der anderen; Videos geteilt, das
  Videomodell nicht auf der Monitorkarte; Abläufe ohne Kartenwahl auf ComfyUIs Standardkarte 0; „Stelle per Wort“ plant
  2 GiB für SAM3 auf Karte 0 dazu. Die gewählten Geräte gehen in `SelectModelDevice`/`SelectCLIPDevice`/`SelectVAEDevice`
  und den Prompt-Enhancer. Die Ein-Karten-Einstellung vom Vormittag ist damit abgelöst.
- Texte: LightOnOCR „eine RTX 3090“, Messläufe speichern die Kartennamen (ältere Läufe: Karte 1 = 3080), Skill
  `texterkennung` angepasst. Tests: Zentrale 95, Werkstatt 195 (neu: Kartenwahl, Gesamtbedarf, Monitorpuffer, Geräte im Ablauf).

**Abnahme am echten System (Claude, 14.10.2026):**

| Prüfung | Ergebnis |
|---|---|
| LightOnOCR starten (beide Karten leer) | Suprim (engste), 4.350 MiB, bereit nach 4 s |
| NInfer starten (LightOnOCR auf der Suprim) | FE, 22.286 MiB, bereit nach 5 s; Antwort „OK“ in 0,8 s |
| Bild neben NInfer (INT8, Turbo, 1328²) | ganz auf der Suprim, Spitze 8,0 GiB, 9,4 s; FE unberührt |
| Video 960×544, 5 s, Schnell (DMAD), geteilt | Modell FE (Spitze 23,3 GiB), Text-Encoder/VAE Suprim; 76 s (vorher 74 s mit Modell auf der Suprim, dort Spitze 23,7 GiB → Regel „Videomodell nicht auf die Monitorkarte“) |
| Ornith Q4 laden | Ollama verteilt 14.051 + 12.411 MiB, **Kontext 262.144** (siehe Befund) |
| Ornith Q5 laden | 14.633 + 12.787 MiB, Kontext 131.072, nach dem Aufwärmen 95–158 Token/s |
| Oberfläche | Namen, „Monitor“, Bedarfstexte und Strata-Zeile mit Kartennamen richtig |
| Strata (nach Schließen der Ollama-App 47,5 GiB Arbeitsspeicher frei) | bereit nach 32 s, Kontext 131.072; 23.380 MiB (FE) + 23.422 MiB (Suprim), auf der Suprim mit Windows nur 0,4 GiB frei; 21.245 Experten auf den Karten (86 %, vorher 18.962), Trefferquote 98,6–99,4 %, 92–95 Token/s; Bild richtig beschrieben (2,9 s). Bedarf auf 23.400 + 22.000 MiB |

**Befunde:**
- Erster Bildversuch lief trotz Wahl „Suprim“ auf der FE neben NInfer: `_rechnen` hatte die Geräte nicht an die Abläufe
  gegeben (behoben, Test `test_gewaehlte_karten_kommen_in_den_ablauf`). Dabei lief die FE auf 24,2 von 24,6 GiB, und der
  Treiber lagerte in den Arbeitsspeicher aus (CUDA-Sysmem-Fallback): kein Absturz, NInfer verlor 0,7 GiB Grafikspeicher
  (danach neu gestartet). Lehre: Überbelegung fällt unter Windows nicht als Fehler auf – das Platz-Tor bleibt nötig.
- ComfyUI wächst in den freien Platz: bei Videos 23,3 GiB auf der Modellkarte und bis 20,8 GiB auf der anderen (geplant
  20 + 7). Die Bedarfswerte sind Mindestwerte für den Start.
- Ornith Q4 hat kein `num_ctx` im Modelfile: Ollama 0.40.4 wählt den Kontext nach dem Grafikspeicher (mit 3090 + 3080
  32K/23,0 GiB, mit 2 × 24 GiB 256K/26,5 GiB). Sascha: „256K ist ja nicht schlecht, wenn der Platz nicht anderweitig
  benötigt wird“ → Kontextauswahl statt fester Einstellung (unten).

**Kontextauswahl (14.10.2026, Auftrag Sascha „Ja Kontextauswahl“, Strata nicht weiter testen):** Einträge können
`varianten` haben (Felder, die den Eintrag überschreiben: `bedarf_gesamt_mib`, `ollama_optionen`, `konfig` …;
`planung.variante`). Oberfläche: Auswahl „Laden mit“/„Starten mit“ unter dem Eintrag, nur solange er aus ist, Bedarf
wechselt mit; `/api/plan` und `/api/starten` nehmen `variante`. Ornith Q4: 256K (Standard, `num_ctx 262144`) oder 32K
(`num_ctx 32768`); Strata: 128K mit Bildern (Standard) oder 256K ohne Bilder (`strata-iq3_xxs-2gpu-256k.json`). Q5
bleibt fest bei 128K (Hermes fragt ohne Optionen an). Die Werkstatt schickt bei jeder Ollama-Anfrage den Kontext, mit
dem das Modell laut `/api/ps` geladen ist (`Lokal.ollama_optionen`, auch im Messlauf); ihr Katalog nennt diesen Kontext,
damit zu lange Transkripte richtig abgelehnt werden. UD-IQ4_XS für Strata nicht angeboten (nur eine Karte, 28–60 Token/s,
Qualität im Test 04.10. nicht besser). Geprüft: Q4 mit 32K über die Zentrale 22,5 GiB (11.944 + ~10.540 MiB), Kontext
32.768; Anfrage wie die Werkstatt ohne Neuladen (Ladezeit 0,0 s), Anfrage ohne `num_ctx` lud in 6,3 s auf 256K neu;
Auswahl und Bedarfstext in der Oberfläche. Strata-256K auf zwei 3090 nicht live geprüft (Wunsch Sascha). Tests:
Zentrale 102, Werkstatt 198.

**Strata-Update 0.1.39 → 0.1.44.1 (14.10.2026, Auftrag Sascha „Mach das Update und teste nochmal“):** Das Strata-Repo
(github.com/Niko1221/Strata) hat seine Versionsgeschichte neu geschrieben (kein gemeinsamer Ursprung mehr, `git pull
--ff-only` scheitert); unser alter Stand `6f32ec0` ist Datei für Datei gleich dem Commit `a1641e9f` der neuen Geschichte.
Deshalb `git reset --hard v0.1.44.1` (Rückweg: `6f32ec0`), dann `setup.py --update` (keine Fragen, Modelldateien
unberührt, nichts außerhalb des Strata-Ordners): neue Engine 0.16 GB, SHA-256 gegen GitHub geprüft, alte Engine in
`engine\.previous` (`setup.py --rollback-engine`). Unsere Einstellungsdateien blieben unverändert.
**Befund:** Die neue Engine meldete „CUDA1: 0 MiB of VRAM free – LOW … under WDDM a full card pages“ – die Suprim
trägt den Monitor. Gemessen ohne Abhilfe 16–19 Token/s und 477 Token/s beim Einlesen (Windows lagert aus). Abhilfe nach
Strata-Anleitung (docs/MULTI_GPU.md): `--vram-reserve-later-mib 1800` in `strata-iq3_xxs-2gpu-128k.json` und
`…-256k.json`. Danach 128K: 1 GiB frei auf der Suprim, 84 % der Experten auf den Karten, **112–113 Token/s** Text,
**145–162 Token/s** Code, 70.093 Token Prompt in 19 s (**3.675 Token/s**), Bild 2,1 s; 256K: bereit nach 24 s, 79 %,
95–106 Token/s. Damit schneller als am 05.10. mit RTX 3090 + 3080 (damals hing der Monitor an der Intel-Grafik).

**Strata Q4 als Variante (16.10.2026, Wunsch Sascha: „auf Knopfdruck starten“).** Unsloth UD-IQ4_XS (93,7 GB, seit
17.09. vorhanden) läuft seit Engine 0.1.40 mit RAM-Rahmen auch auf zwei Karten. Erster Test ohne Rahmen: Windows zählt
den Grafikspeicher beider Karten zur Speicherzusage (Grenze 80,5 GiB, 2 GiB frei), Strata las die übrigen Experten
von der SSD (49–72 Token/s). Sascha stellte die Auslagerungsdatei auf C: fest auf 64 GB (Grenze 127,5 GiB); danach
mit 32 GiB Rahmen: 89–98 Token/s Text, 108–116 Code, 70.595 Token in 26 s (2.681 Token/s), RAM frei ~8 GiB.
Laut Strata-Doku 88,9 statt 84,5 % gleiches Wort wie Q8_0 (KL 0,10 statt 0,20); im Schulter-Test kein Unterschied.
Umsetzung: Variante `q4` im Strata-Eintrag (`konfig` `strata-unsloth-ud-iq4_xs-2gpu-128k.json`, `ram_bedarf_gib` 40,
`modell`), Erfassung liest den Modellnamen aus `/health`, die Zeile nennt die laufende Variante. Tests: Zentrale 103,
Werkstatt 198 grün. Live über die Zentrale gestartet (bereit nach 40 s) und beendet. **Befund dabei:** Nach Saschas
Neustart ist die Anzeige wieder auf der FE (Karte 0, `display_active`, ~0,9 GiB Programme); dann bleiben auf der FE
nur 694 MiB frei und Q4 schrieb 46 / 78 Token/s statt 89 / 108. Die Reserven der Strata-Einstellungen (700 MiB
erste Karte, 1.800 MiB spätere Karte) passen zur Monitorkarte Suprim bzw. zur Intel-Grafik, nicht zur FE.

**Monitor an der FE (16.10.2026, Sascha: Kabel steckt an der FE).** Nach Strata-Anleitung (docs/MULTI_GPU.md: die Karte
mit dem Monitor braucht mehr Luft) in allen drei Einstellungen (`strata-iq3_xxs-2gpu-128k.json`, `…-256k.json`,
`strata-unsloth-ud-iq4_xs-2gpu-128k.json`) `--vram-reserve-mib 1800` (FE, erste Karte) und `--vram-reserve-later-mib
1000` (Suprim); vorher 700 / 1800 (256K ohne eigene Erst-Reserve). Bedarf in der Zentrale von 23.400 + 22.000 auf
**22.000 (FE) + 23.200 (Suprim)** MiB, sonst meldete der Plan wegen ~0,9 GiB Windows & Programme auf der FE immer
~450–600 MiB zu wenig. Gemessen über die Zentrale: **128K** bereit nach 29 s, 92–97 Token/s Text, 122–147 Code,
70.595 Token in 19,6 s (3.609 Token/s), Bild 1,8 s (3 Pflanzen, richtig); **Q4** bereit nach 38 s, 89–93 / 97–103,
2.591 Token/s. Gegenüber dem Monitor an der Suprim (14.10.: 112–113 / 145–162) beim Text etwa 15 % weniger, weil auf
der FE weniger Experten Platz haben. Zurück, falls der Monitor wieder an die Suprim oder die Intel-Grafik kommt:
Reserven 700 / 1800 und Bedarf 23.400 + 22.000.

**Q4 mit Bildern (16.10.2026, Sascha: „ich bräuchte auch ein Bildmodell bei Q4“).** `--vision` und derselbe
`vision`-Abschnitt wie bei 128K (Encoder `mmproj-Qwen3.8-Flash-Next-BF16.gguf` auf der GPU, `model` = Q4-Teil 1).
Über die Zentrale gemessen (Monitor an der FE): 83–96 Token/s Text, 99–115 Code, 70.595 Token in 28 s
(2.541 Token/s), Bild 3,8 s, 3 Pflanzen richtig; Karten 22.709 + 23.251 MiB, RAM frei 7,0–8,0 GiB. Gegenüber Q4 ohne
Bilder kaum langsamer. Variante heißt jetzt „Q4 · genauer, etwas langsamer · 128K · mit Bildern“.

**Hermes nutzt Strata (16.10.2026, Sascha: „in Hermes anbinden“).** In `%LOCALAPPDATA%\hermes\config.yaml` gab es den
Anbieter `strata-local` (Port 8095) schon mit IQ3_XXS. Ergänzt: Modell `qwen3.8-flash-next-unsloth-ud-iq4_xs`, bei
beiden `supports_vision: true` (Hermes hängt Bilder dann direkt an, statt sie vorher beschreiben zu lassen), Name
„Strata Flash-Next (vorher in der Zentrale starten)“. Standard bleibt Ornith Q5. Ablauf: Fassung in der Zentrale
starten, in Hermes `/model strata-local:qwen3.8-flash-next-unsloth-ud-iq4_xs` (bzw. `…-iq3_xxs`). Strata beantwortet
jede Anfrage mit der gerade gestarteten Fassung; der Name in Hermes ist nur die Beschriftung. Geprüft: Q4 über die
Zentrale, Hermes-Einzelanfrage mit Bild (`hermes chat --oneshot --provider strata-local --image …`): richtig
beschrieben, 3 Pflanzen, 22 s. **Achtung:** Solange Strata läuft, nicht auf Ornith zurückschalten – Ollama würde
Ornith Q5 neben Strata laden (beide Karten voll). Erst Strata in der Zentrale beenden.

**Strata-Update 0.1.44.1 → 0.1.45 (18.10.2026, Sascha: „Strata würde ich auf jeden Fall mal updaten“).** Nach dem
IQ3_S-Download einer anderen Sitzung `git pull --ff-only` (v0.1.45 = `477ac13c`), dann `setup.py --update`: neue Engine
0,17 GB, SHA-256 gegen GitHub geprüft, alte in `engine\.previous` (`setup.py --rollback-engine`); Pakete und
CUDA-Bibliotheken unverändert. Alle 13 `strata-*.json`, `packs\iq3_s` und `models\IQ3_S` vorher/nachher verglichen:
unverändert. **Flash-Next IQ3_XXS 128K (Zentrale-Einstellung, Monitor an der FE):** Text 106–116, Code 142–158 Token/s,
70.595 Token mit 3.863 Token/s, Bild 1,8 s richtig – gleich oder besser als vorher (92–97 / 122–147 / 3.609).
**Ornith Q5 über den `qwen35moe`-Weg** liest jetzt Bilder (Ollama-Projektor, 1,9 s richtig), schreibt bei fester
Wortwahl aber langsamer als mit 0.1.44.1 (113–129 statt 123–164 Token/s), mit Temperatur etwas schneller (Schulter-Test
105–109 statt 95–100). Q4 geht dort weiter nicht. Vergleich mit PolyStrata und llama.cpp:
`Projekte\Lokale-Wissensextraktion\auswertungen\2026-10-18-polystrata.md`.

## Ornith über PolyStrata in der Zentrale (18.10.2026)

Auftrag Sascha: „bau PolyStrata mit Ornith Q4 (Ollama-Datei, eine Karte, 128K, Bilder) als zusätzliche Variante in
die Zentrale ein; Ollama-Ornith bleibt daneben.“ Anlass: Messung desselben Tages (PolyStrata auf einer 3090 182 Token/s
Text, 200–211 Code, auch mit Temperatur; Bild 1,1 s; llama.cpp auf zwei Karten 138–172; Ollama Q5 116–154).

- **Eigener Eintrag statt Variante von „Ornith 1.5 · Q4“:** Varianten teilen in der Zentrale die Art (Ollama-Optionen
  bzw. Strata-Einstellung); PolyStrata ist ein eigener Server. Neuer Eintrag `ornith-polystrata`, Art `polystrata`.
- **Kartenwahl wie LightOnOCR** (`karten` + `bedarf_je_karte_mib` 23.000): die engste passende Karte, die Monitorkarte
  nur mit 2 GiB Rest – praktisch die Suprim. Die Karte geht als `--gpu <n>` an PolyStratas Server (nvidia-smi-Zählung).
- **Start wie Strata:** `python server.py --engine strata --config strata-ornith-q4-ollama-1gpu.json --port 8097 --gpu n`
  mit Strata's venv (gleiche Pakete und CUDA-13-Bibliotheken, nur gelesen), RAM-Prüfung 24 GiB, bereit bei `/health`
  `loaded`. Beenden: erst `strata-poly.exe`, dann `strata-vision.exe`, dann Python – nur Prozesse mit PolyStrata-Pfad
  bzw. Server-Skript und Port 8097 (`erfassung.ist_polystrata`); Strata wird davon nicht berührt (Test).
- Anzeige: „Kontext 131.072 · Port 8097 · RTX 3090“, Link „Chat öffnen“, „GPU freigeben“ bietet „beenden“ an.
- Tests: Zentrale 127 (11 neu in `tests/test_polystrata.py`), Werkstatt 214 grün. Die Werkstatt bietet PolyStrata
  nicht an (sie nutzt für Zusammenfassungen nur Ollama und NInfer).
- **Live geprüft (18.10.2026, 14:56):** Zentrale neu gestartet (nur der Prozess auf 3894 mit `zentrale\server.py`),
  Plan wählt „RTX 3090 Suprim“ ohne Freigabe-Schritte; bereit nach 26 s, Anzeige „Kontext 131.072 · Port 8097 ·
  RTX 3090 Suprim“, Belegungsleiste ordnet 23,3 GiB „Ornith 1.5 · PolyStrata“ zu. Probe über Port 8097: Text
  178–180 Token/s, Code 199–200, Bild 0,6 s (3 Pflanzen, richtig). Beenden über die Zentrale: Port frei, keine
  PolyStrata-Prozesse mehr. (Ein gleichzeitiger ComfyUI-Start aus der Werkstatt ließ „Beenden“ kurz warten – die
  Zentrale nimmt immer nur eine Aktion an.)

## Strata mit `--fit-max-tokens` (18.10.2026)

Auftrag Sascha nach dem Pac-Man-Test über DSH („Antwortgrenze 65536 … Zentrale mit --fit-max-tokens“). Anlass: DSH schickt
bei jeder Anfrage die volle Antwortgrenze als `max_tokens` und kürzt sie nicht selbst; Strata lehnt dann mit 400 ab, sobald
Verlauf + `max_tokens` über den Kontext gehen (Q4 brach bei 66.103 + 65.536 > 131.072 ab). Akte:
`Projekte\Lokale-Wissensextraktion\README.md` (Nächste Versuche, 18.10.).

- Eintrag `flash-next-strata`: `"fit_max_tokens": true` (mit `fit_max_tokens_grund`); die Zentrale hängt dann beim Start
  `--fit-max-tokens` an (alle drei Varianten 128K, 256K, Q4). Strata kürzt `max_tokens` auf den Restplatz statt 400.
  Gilt für DSH, Hermes und Werkstatt gleich. Stratas Einstellungsdateien bleiben unverändert.
- Tests: Zentrale 128 grün (Startbefehl mit Schalter; neu: ohne Eintrag kein Schalter).
- **Live geprüft (18.10.2026):** Zentrale neu gestartet, Strata über die Zentrale gestartet – Kommandozeile endet auf
  `--port 8095 --fit-max-tokens`; Anfrage mit `max_tokens` 140.000 (mehr als der Kontext) → HTTP 200 statt 400. Danach
  über die Zentrale gestoppt.
- Daneben in DSH Desktop (`~\.dsh\settings.yaml`, nicht Teil der Zentrale): Antwortgrenze für „Strata – Flash-Next lokal“
  8.192 → 65.536. Verdichtung ab 50 % war gewünscht, geht in DSH Desktop 0.1.5 aber nicht sauber (steckt in den
  mitgelieferten Agent-Voreinstellungen; eigene Überschreibung ersetzt deren ganze Liste und zöge Updates nicht mit) –
  bleibt bei 80 % (~104.900 Token); danach kürzt Strata lange Antworten auf den Rest.

## Ornith Q6 mit 256K auf beiden Karten; DSH über Ornith (19.10.2026)

Auftrag Sascha: „in der Modellzentrale die Möglichkeit einrichten, Ornith auf 1 Karte zu starten als auch mit Q6 auf
beiden Karten, Kontextfenster bei Q6 auf 256K“ und „DSH über Ornith steuern können, Einstellungen wie für Strata“.

- **Eine Karte** gab es schon: „Ornith 1.5 · PolyStrata“ (Q4, 128K, Bilder, Kartenwahl). Dazu startet PolyStrata jetzt
  wie Strata mit `--fit-max-tokens` (`fit_max_tokens` im Eintrag; derselbe Schalter im Startcode der Art `polystrata`).
- **Neuer Eintrag „Ornith 1.5 · Q6“** (`ornith-q6`, Art `ollama`): Ollama-Fassung `ornith-q6-256k:latest`, angelegt mit
  `ollama create` (über `/api/create`) aus den vorhandenen Q6_K-Gewichten `hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q6_K`
  (30,1 GB, gleiche Datei, nichts kopiert) mit `num_ctx 262144` und `num_batch 256` im Modelfile – wie bei
  `ornith-q5-128k`, damit DSH und Hermes über `/v1` (ohne Optionen) nicht mit anderem Kontext neu laden. Bedarf 33.500 MiB
  gesamt, Ollama verteilt auf beide Karten. Für den Webdesign-Test entstand außerdem `ornith-q6-128k:latest` (128K,
  gleiche Gewichte); bleibt vorerst, kann bei Bedarf weg (nur die Fassung, die Gewichte bleiben).
- Tests: Zentrale 128 grün (PolyStrata-Startbefehl mit Schalter).
- **Live geprüft (19.10.2026):** Zentrale neu gestartet; Q6 über die Zentrale geladen: bereit nach 9 s, `/api/ps` zeigt
  Kontext 262.144, 31,2 GiB ganz im Grafikspeicher (18.742 MiB FE inkl. ~1,1 GiB Windows, 15.644 MiB Suprim). Eine
  `/v1`-Anfrage wie von DSH lädt nicht neu (gleiche Kennung, Kontext unverändert, bleibt dauerhaft geladen), 121 Token/s.
  Entladen über die Zentrale: Karten frei. PolyStrata über die Zentrale gestartet: Kommandozeile endet auf
  `--gpu 1 --fit-max-tokens`, Anfrage mit `max_tokens` 200.000 → 200 statt 400; gestoppt.
- **DSH Desktop** (`~\.dsh\settings.yaml`, nicht Teil der Zentrale): neue Anbieter „Ornith – Ollama lokal“
  (`ornith-q6-256k:latest`, Kontext 262.144, Antwortgrenze 49.152 – Ollama kürzt nicht selbst, DSH Desktop fasst bei 80 %
  ≈ 209.700 zusammen) und „Ornith – PolyStrata (eine Karte)“ (Port 8097, 131.072, Antwortgrenze 65.536 dank
  `--fit-max-tokens`). Q4 über Ollama bewusst nicht: Dessen Kontext legt erst die Zentrale beim Laden fest, eine
  DSH-Anfrage würde neu laden. Als Schlüssel nutzen beide den vorhandenen Platzhalter `STRATA_LOCAL_API_KEY`
  (Ollama/PolyStrata prüfen keinen); die Zugangsdatei von DSH blieb unberührt.
- Befund aus dem Webdesign-Test: Ornith arbeitet über DSH als Agent schlecht (viele fehlgeschlagene Werkzeugaufrufe,
  keine fertige Seite) – für Agentenarbeit Flash-Next nehmen (Akte Lokale-Wissensextraktion, 19.10.).

## Strata 0.2.0-beta, dann v0.2.1.3 mit Engine 0.1.45.3; Monitor wieder an der Suprim (20.10.2026)

Auftrag Sascha: Release v0.2.0-beta (19.10.2026) lesen und als Update der vorhandenen Installation
`C:\LLM\runtimes\Strata` einspielen. Dabei fiel auf, dass der Monitor wieder an der **Suprim** hängt
(`display_active` Bus 04); Sascha bestätigte: „das muss geändert werden“.

- **Was 0.2.0 ist:** vor allem eine neue Verpackung – Desktop-App (Installer mit eigener Engine und Modellverwaltung),
  „Terminal“ (`strata launch/monitor/connect/update`) und die Engine als eigenes, signiertes Paket (Ed25519-Feed, Update
  mit Probestart). Für uns relevant ist die Engine 0.1.45.3: **RTX 30 (sm_86) bekommt neun bitgleiche Tempo-Schalter
  standardmäßig** (`STRATA_SM86_PERF=0` schaltet ab; Protokoll: „sm_86 (Ampere): 9 exact speed switches on by default“).
  Server: `--fit-max-tokens` ist jetzt Standard (unser Schalter bleibt gültig), neue Optionen `--parallel`, `--max-queue`
  u. a., keine entfernt; die Engine hängt in einem Windows-Job am Server (stirbt mit ihm). `/health` unverändert.
  „Bilder standardmäßig an“ betrifft nur neue Einrichtungen: die 256K-Einstellung ohne `vision`-Abschnitt bleibt ohne Bilder.
  Kein neues Paket im venv (cmake/ninja nur aus der Laufzeitliste genommen), kein neues Pack, kein Requantisieren.
- **Wichtig für künftige Updates:** Bei unserer Quellcode-Installation holt `UPDATE.bat` (`setup.py --update`) seit 0.2.0
  **keine neue Engine** mehr (`MIN_ENGINE` bleibt 0.1.45, und die Releases haben kein `strata-windows-x64.zip` mehr). Die
  Engine kommt aus dem Release-Paket `strata-engine-<ver>-windows-x86_64-cuda-cuda13.tar.gz`.
- **Ablauf:** `git merge --ff-only v0.2.0-beta` (Rückweg: `477ac13c` = v0.1.45), `setup.py --update` (keine Fragen;
  Pakete, alle 13 `strata-*.json` vorher/nachher gleich). Engine-Paket 580 MB geladen: SHA-256 = GitHub-Angabe =
  `SHA256SUMS.txt` = signierter Feed; Feed- und Manifest-Signatur mit Stratas `strata_control/signing.py` und
  `update_keys.json` geprüft, jede Datei gegen das Manifest. Übernommen nur `strata.exe`, `strata-vision.exe`,
  `strata_kq.dll`, `BUILD.json`; die mitgelieferten cuBLAS-DLLs sind bitgleich mit denen im venv (`lib_dirs`). Alte
  Engine 0.1.45 in `engine\.previous` (`setup.py --rollback-engine`, hin und zurück geprüft), die dort liegende 0.1.44.1
  im Papierkorb. PolyStrata (eigener Server, nutzt das venv nur lesend) ist davon unberührt.
- **Monitor an der Suprim:** wie bis 16.10. `--vram-reserve-mib 700` (FE) und `--vram-reserve-later-mib 1800` (Suprim)
  in allen drei Einstellungen (128K, 256K, Q4; 256K hatte bis 16.10. keine eigene Erst-Reserve, jetzt 700), Bedarf
  in der Zentrale 23.400 + 22.000 MiB. PolyStrata wählt dadurch jetzt die FE. Der neue Server warnt, auf der FE seien
  beim Start nur ~450 MiB frei, und empfiehlt `--vram-reserve-mib 1280`; gemessen kein Auslagern (FE ohne Monitor),
  daher nicht geändert.
- **Gemessen über die Zentrale** (`/api/plan` + `/api/starten`, Kommandozeile endet auf `--fit-max-tokens`, `max_tokens`
  140.000 → 200), gleiche Proben wie 16./18.10., je Lauf frisch gestartet, RAM vor dem Start 50–52 GiB frei; Skript und
  Rohwerte: `Projekte\Lokale-Wissensextraktion\nachweise\2026-10-20-strata-020\`:

| Lauf (Monitor an der Suprim) | Text (Token/s) | Code | 70K-Prompt | Bild | bereit |
|---|---|---|---|---|---|
| 128K, Engine 0.1.45 (Code 0.2.0) | 104–105 | 133–151 | 3.858 | 2,3 s, 3 Pflanzen | 32 s |
| **128K, Engine 0.1.45.3**, zwei Läufe | **109–115** | 131–175 (175 bei kürzerer Antwort) | 3.846–3.877 | 2,0–2,1 s, 3 Pflanzen | 32 s |
| Q4, Engine 0.1.45 | 72–81 | 83–98 | 2.531 | 3,2 s, 3 Pflanzen | 42 s |
| **Q4, Engine 0.1.45.3** | **77–91** | 94–99 | 2.512 | 3,0 s, 3 Pflanzen | 45 s |

  Ergebnis: Schreiben rund 5–12 % schneller, Einlesen gleich; 84 % der Experten auf den Karten, 23.361 + 23.397 MiB.
  Gegenüber 18.10. (Monitor an der FE, 106–116 / 142–158 / 3.863) etwa gleich. Ein erster Lauf mit der alten Engine bei
  nur 44 GiB freiem RAM (geladen 0,6 GiB frei) schrieb 91 / 133 – knapper Arbeitsspeicher kostet spürbar.
  PolyStrata kurz über die Zentrale: auf der FE bereit nach 30 s, 172 Token/s, sauber beendet.
- **Neue Oberflächen:** Stratas Webseite liegt wie bisher unter `http://127.0.0.1:8095/`, solange Strata läuft. Der
  Terminal-Monitor (`strata.py monitor --url http://127.0.0.1:8095`) braucht das Paket `rich` (nicht im venv, nicht
  installiert). Die Desktop-App ist ein eigener Installer neben der Zentrale – nicht installiert.
- Zentrale-Tests: 128 grün (kein Code geändert, nur `config.json`).

**Nachtrag am selben Abend: Code v0.2.1.3, Engine bleibt 0.1.45.3** (Sascha: „Warum nicht die neueste?“ – „go“).
v0.2.1 (Engine 0.1.46) kam am 20.10. um 09:47, v0.2.1.1–0.2.1.3 sind nur Tags (Control/Terminal 0.1.46.1–0.1.46.2, deren
Dateien hängen am Release 0.2.1); die neueste Windows-CUDA-13-Engine ist 0.1.46. Für uns in 0.2.1 nur: mehrere Anfragen
auf zwei NVIDIA-Karten in einer Gruppe (nur mit `--batch`), kleinere Standard-Reserve auf Karten ohne Monitor (wir setzen
eigene Werte, die gelten weiter), eigene Optionen bleiben bei App/Setup erhalten (`user_args`, nur bei Einrichtungsläufen).
- `git merge --ff-only v0.2.1.3` (`cbfd5b92`), `setup.py --update`: Einstellungen und venv gleich, Engine unverändert.
  Engine 0.1.46 geladen und geprüft wie oben (SHA-256 = GitHub = `SHA256SUMS.txt` = Feed Nr. 105; Feed- und
  Manifest-Signatur gültig; cuBLAS bitgleich mit dem venv), eingesetzt, 0.1.45 in den Papierkorb.
- Gemessen wie oben (Monitor an der Suprim, RAM vor dem Start 50–51 GiB frei):

| Lauf | Text (Token/s) | Code | 70K-Prompt | Bild |
|---|---|---|---|---|
| 128K, Engine 0.1.46, zwei Läufe | 106–116 | 134–160 (177 kurz) | 3.745–3.752 | 1,9–2,0 s, 3 Pflanzen |
| **128K, Engine 0.1.45.3, Code 0.2.1.3** | **115–117** | **159–179** | **3.895** | 1,6 s, 3 Pflanzen |
| Q4, Engine 0.1.46 | 82–85 | 89–112 | 2.570 | 3,3 s, 3 Pflanzen |
| **Q4, Engine 0.1.45.3, Code 0.2.1.3** | **86–93** | **100–117** | **2.673** | 3,0 s, 3 Pflanzen |

  Die 0.1.46 liest in allen Läufen 3–4 % langsamer ein und schreibt nicht schneller. **Entschieden: neuester Code
  v0.2.1.3 mit Engine 0.1.45.3** (aktiv); 0.1.46 liegt in `engine\.previous` – `setup.py --rollback-engine` schaltet um.
  PolyStrata danach kurz: FE, 172 Token/s, sauber beendet. Bei der nächsten Engine (> 0.1.46) wieder beide vergleichen.

## RTX 3080 über USB4 als dritte Karte für Strata – getestet, nicht lohnend (22.10.2026)

Anlass: Sascha wollte die RTX 3080 (20 GB) für größere Modelle nutzen und hat sie über ein Thunderbolt-Gehäuse (AG02)
angeschlossen; Go für den Strata-Test („Go für den 1. Strata Test würde ich sagen“). Die Karte ist **Index 2, Bus 07**,
Verbindung x4; Stratas eigene Messung: **3,1 GB/s** zur 3080 statt 12,9 GB/s zu den 3090 (USB4 1.0 ≈ PCIe 3.0 x4). Nach dem
Neustart von Windows war die Zentrale aus (kein Autostart) und wurde mit `start.py --ohne-fenster` gestartet; sie erkennt die
dritte Karte richtig als „RTX 3080“ (20.480 MiB).

Test ohne Änderung an der Zentrale: eigene Einstellungen `strata-iq3_s-3gpu-128k-test.json` und
`strata-unsloth-ud-iq4_xs-3gpu-128k-test.json` (Port 8099), Skript `Projekte\Lokale-Wissensextraktion\nachweise\
2026-10-21-strata-rtx3080\strata_test.py` (Anmeldung über `/api/platz`, gleiche Proben wie am 20.10., nur eigene Prozesse
beendet). `strata-iq3_s-2gpu-128k.json` hat dafür die Reserven 700 / 1.800 bekommen (Monitor an der Suprim). Engine 0.1.45.3.

| Lauf (RAM vor dem Start 49–55 GiB frei) | Text (Token/s) | Code | 70K-Prompt | RAM frei geladen |
|---|---|---|---|---|
| IQ3_S, zwei 3090 | 113–114 | 149–175 | 3.158 | 0,5 GiB |
| IQ3_S, drei Karten, Reihenfolge von Strata (3080 zuerst) | 26–39 | 37–43 | 3.380 | 0,9 GiB |
| IQ3_S, drei Karten, FE → 3080 → Suprim (`"gpu_order": "as_given"`) | 37–68 | 33–44 | 3.647 | 0,7 GiB |
| Q4, zwei 3090 (20.10.) | 86–93 | 100–117 | 2.673 | 10–12 GiB |
| Q4, drei Karten, FE → 3080 → Suprim | 44–60 | 42–44 | 3.036 | 21,5 GiB |

- **Schreiben halbiert bis gedrittelt**, auch wenn Strata nur 5 Schichten auf die 3080 legt und deren Experten ganz in ihren
  Speicher passen: Jeder Schreibschritt muss über die langsame Leitung. Einlesen 10–15 % schneller.
- **RAM:** IQ3_S braucht mit drei Karten gleich viel (Strata hält alle Experten im RAM, 40.290 MiB gesperrt; die Karten sind
  nur Zwischenspeicher). Nur Q4 (RAM-Rahmen) gewinnt ~10 GiB freien RAM.
- Strata ordnet Karten von sich aus nach Rechenleistung, die langsamste zuerst – dann wird die 3080 die erste Stufe; mit
  `"gpu_order": "as_given"` lässt sich das festlegen, hilft aber nicht genug.
- Bilder lesen alle Läufe richtig (3 Pflanzen). **Entscheidung offen bei Sascha**; Empfehlung: Strata bleibt auf den zwei 3090.
  Die 3080 käme höchstens als Nebenkarte für Whisper oder Bilder in Frage (eigener Umbau, ungetestet).
- **Achtung, solange die 3080 dranhängt:** Zentrale und Studio kennen keine Regel „langsame Karte zuletzt“ – die Kartenwahl
  („engste passende Karte“) kann LightOnOCR, NInfer oder Bilder auf die 3080 legen, und Ollama verteilt Modelle selbst auch
  auf sie. Strata und PolyStrata nutzen sie nicht (feste Kartenliste bzw. `--gpu`). → Erledigt mit dem nächsten Abschnitt.

## RTX 3080 als Nebenkarte für Whisper und LightOnOCR (22.10.2026)

Auftrag Sascha: Die 3080 (USB4, AG02) dient als Nebenkarte für Arbeiten, die ganz auf sie passen; Ornith und die großen
Modelle bleiben auf den 3090. Bau: DeepSeek V4.1 Flash (DSH, 4 min, 0,06 USD), Abnahme und Nacharbeit Claude.

- **Zentrale:** `karten."2"` = „RTX 3080“, Bus 7, `nebenkarte: true` (gilt nur bei passendem Steckplatz und Modell,
  `gpu.nebenkarten`); die Erfassung markiert sie, `/api/platz` meldet `nebenkarte` je Karte. Kartenwahl: Unter den Karten,
  die ohne Freigabe passen, hat die Nebenkarte Vorrang; passt nichts, gilt die bisherige Logik. Nur Einträge, die „RTX 3080“
  in `karten` nennen, kommen dorthin: **LightOnOCR** (`["RTX 3080", "RTX 3090"]`). NInfer, PolyStrata, Fibo und Bild & Video
  bleiben bei „RTX 3090“, Strata bei den festen Karten 0/1.
- **Ollama:** `gesamt_karten: ["RTX 3090"]` bei Ornith Q4/Q5/Q6 – Planung und Warten zählen nur den Platz der 3090.
  Gemessen vorher: Ollama (`OLLAMA_SCHED_SPREAD=1`) legte Ornith Q4 32K auf alle drei Karten (6,9 / 9,8 / 6,7 GiB), **37 Token/s**.
  Saschas Ja („ja dann auf 2 karten beschränken“): Benutzervariable `CUDA_VISIBLE_DEVICES` =
  `GPU-70c82ca0-8776-0b32-5800-59c65fde88d3,GPU-dee760fc-3741-1029-39ad-e562aada83f5` (FE, Suprim; UUIDs aus `nvidia-smi -L`)
  und Ollama über die App neu gestartet. Danach sah Ollama die 3080 noch über **Vulkan** (in Ollama 0.40.8 ab Werk an) und lud
  Ornith ganz dorthin (18,7 GiB) – deshalb zusätzlich Benutzervariable `OLLAMA_VULKAN=0`, erneut neu gestartet. Ergebnis:
  Ollama meldet nur die zwei 3090 (CUDA), Ornith Q4 32K 11,9 + 11,6 GiB, **154–156 Token/s**, 3080 0 MiB.
  **Rückweg:** beide Benutzervariablen löschen (Systemsteuerung → Umgebungsvariablen oder
  `[Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES',$null,'User')`, ebenso `OLLAMA_VULKAN`), Ollama über die App
  beenden und neu starten. Nach einem Kartentausch die UUIDs neu eintragen.
- **Wirkung der Variable auf alles andere:** Programme, die keine Karte vorgeben, sehen nur die 3090. Die Zentrale setzt für
  NInfer, LightOnOCR (llama.cpp) und Fibo `CUDA_VISIBLE_DEVICES=<karte>` mit `CUDA_DEVICE_ORDER=PCI_BUS_ID` selbst (überschreibt
  die Variable); ComfyUI setzt sie über `--cuda-device` selbst; Strata/PolyStrata sehen die zwei 3090 in derselben Reihenfolge
  (FE = 0, Suprim = 1). Die Werkstatt gibt watch jetzt `CUDA_VISIBLE_DEVICES=0,…,höchste gewählte Karte` mit, damit `--gpu 2` stimmt.
  Andere Agenten, die watch direkt aufrufen, sehen nur die 3090 (`--gpu 0/1`).
- **Whisper (Werkstatt):** `platz.verteilen` nimmt die Nebenkarte, wenn sie alle Worker trägt (zwei Worker = 5,6 GiB),
  sonst wie bisher nach freiem Speicher. `watch.py` unverändert.
- **Studio:** ComfyUI 1 sieht nur `comfy_karten` (`[0, 1]`, auch für `--cuda-device`); `Instanz.sichtbar` begrenzt die
  Kartenwahl darauf. Vorher hätte das Studio bei leerer 3080 ein Bild als „engste Karte“ auf `gpu:2` gelegt, das ComfyUI 1 gar
  nicht kennt (mit dem echten `/api/platz`-Stand nachgestellt). Dritter ComfyUI-Prozess: nächster Abschnitt.
- **Tests:** Zentrale 161, Werkstatt 220, alle grün (neu: drei Karten, Nebenkarte, Ollama nur 3090, `/api/platz`, Whisper-Vorrang,
  watch-Umgebung, Studio nur sichtbare Karten).

**Am echten System (22.10.2026, Zentrale und Werkstatt mit gesetzter Benutzervariable neu gestartet):**
- Zentrale zeigt drei Karten („RTX 3080 · 20 GiB · Steckplatz 7“); Plan LightOnOCR → Karte 2 „RTX 3080“.
- LightOnOCR über `ocr.py lesen` (Skill texterkennung): llama-server auf Bus 07; `ruecken-s05.png` in 4,3 s (13.10. auf der 3090
  3,8 s), **byte-gleich** mit dem Ergebnis vom 13.10.; Sehnen-`druck-lernen.pdf` Seiten 2–4 und 8 in 29 s (11.10. mit der 3080
  im PCIe-Steckplatz 28 s). Danach wieder beendet.
- Whisper über die Werkstatt (Studio-Testclip, 5 s Ton): „RTX 3080, ein Worker“, `run.json` gpu 2, 4 s.
- Whisper-Vergleich direkt (watch, angemeldet über `/api/platz`), 984 s Ton, zwei Worker: **3080 78–79 s, 3090 FE 53 s**;
  3080 zweimal byte-gleich, gegenüber der 3090 wenige Wortunterschiede (z. B. „19%“ statt „19 Prozent“).
- Testordner: `Arbeitsmaterial\watch\Video-2-EineKarte_00003_ [datei-b662d1204b51]`, `Arbeitsmaterial\Texterkennung\ruecken-s05 (2)`
  und `…\druck-lernen` (können in den Papierkorb, wenn Sascha will).

## Stufe 8b – dritter ComfyUI-Prozess auf der RTX 3080 (22.10.2026)

Auftrag Sascha („ja auf jeden fall“, nach der Frage, was ein dritter Prozess bringt): erst messen, dann bauen.

**Messung vorab** (eigener ComfyUI-Testprozess auf Port 8190 mit `--cuda-device 2` bzw. `0`, Platz angemeldet, Ablauf
`bild_graph` mit den Einstellungen von `Nachbau Osteokinetics\Bild_00006_` – Turbo, INT8, schnell, 1584×1056):

| | RTX 3080 (USB4) | RTX 3090 FE |
|---|---|---|
| erstes Bild (mit Laden) | 13,6 s | 8,9 s |
| weitere Bilder | 7,6–7,7 s | 6,6–6,7 s |
| Spitze Grafikspeicher | 17,4 GiB | 17,3 GiB |
| 2048×1152 (2,4 MP) | 11,7 s, 17,9 GiB | – |

Neben laufendem Strata (beide 3090 voll, 2,4 GiB RAM frei): 3080 gleich schnell (7,8 s), RAM blieb stabil; Strata dabei
118 und 100 statt 131 und 87 Token/s (je eine Probe, Einlesen eingerechnet – kein messbarer Verlust). Bildqualität angesehen: sauber.

**Bau** (DeepSeek V4.1 Flash, 9 min, 0,11 USD; Abnahme und Nacharbeit Claude):
- `comfy_weitere` im Eintrag `bild-video` ersetzt `comfy_port_2`/`comfy_karte_2`/`comfy_name_2`: Prozess 2 (8189, Suprim) wie bisher,
  **Prozess 3 „ComfyUI 3 (RTX 3080)“** (8190, `--cuda-device 2`, `temp-3`/`user-3`, Log `comfyui-3`, Schlüssel `bild-video-3`,
  Dateien `-3`, `videos: false`). Zentrale erfasst, startet, beendet und entlädt alle Prozesse aus der Liste; Zustand „Drei
  Prozesse bereit …“. Werkstatt-Status liefert `weitere` (alte Felder `comfy2…` bleiben).
- Studio: `Instanz.kann` lehnt für Prozess 3 Videos ab und alles, dessen Ein-Karten-Bedarf nicht in die Karte passt
  (`kapazitaet` = Gesamt − Reserve laut `/api/platz`, 19.712 MiB): Bild 18.432 ja, groß 22.016 und „Ausformulieren“ 20.480 nein,
  Hilfsabläufe (`fest` 4–14 GiB) ja. `_wer_zuerst` fragt Nebenkarten zuerst – ein Bild, das jetzt auf die 3080 passt, rechnet
  Prozess 3; rechnet er schon, der nächste freie.
- **Nacharbeit nach dem Echttest:** Mit belegten 3090 nahm Prozess 3 das erste Bild, die beiden anderen griffen sich Prozess 1
  und 2 und warteten dort 10 min auf Platz („wer zuerst kommt“). Neu `_darf_nehmen`: Passt ein Auftrag gerade nirgends, bleibt er
  in der Schlange, solange ein anderer geeigneter Prozess nur rechnet; rechnet keiner, gilt wie bisher „wer zuerst kommt“
  (mit Begründung im Auftrag).
- Tests: Zentrale 168, Werkstatt 225, grün.

**Echttest (22.10.2026):** Zentrale startet drei Prozesse („Drei Prozesse bereit“), ComfyUI 3 meldet nur die RTX 3080.
Vier Bilder über den Skill (`studio.py bild … --anzahl 4`): erstes an Prozess 3 (3080), die nächsten parallel an Prozess 1 (FE) und
2 (Suprim) – drei Bilder gleichzeitig. Beide 3090 über `/api/platz` belegt (ComfyUI 1/2 entladen, 21,5 + 20,5 GiB angemeldet),
drei Bilder bestellt: alle drei nacheinander auf der 3080, je 7,5–7,7 s, keiner blieb hängen. „GPU freigeben“ bietet „Modelle aus
ComfyUI 3 (RTX 3080) entladen“ an; die Belegungsleiste zeigt „ComfyUI 3 (RTX 3080) 15,9 GiB“.

**Grenze Arbeitsspeicher:** Drei leere ComfyUI-Prozesse halten zusammen ~6 GiB (≈ 2 GiB je Prozess; gemessen 35,8 → 42,1 GiB
verfügbar nach „Beenden“). Strata prüft beim Start 42 GiB verfügbar; an diesem Tag reichte es auch ohne ComfyUI knapp nicht
(41,8 GiB – ein fremder Dienst `praxis_kb`, Port 3897, hielt 8,5 GiB). Reihenfolge deshalb: erst Strata, dann Bild & Video (so
gemessen: Bilder auf der 3080 neben Strata ohne Auslagern). Den Strata-Start mit laufenden drei Prozessen nicht mehr
nachgeprüft.
Testbilder: `Studio\Werkstatt-Abnahme\Test3080-k*` (ohne Begleitdatei, aus dem Messskript), `Bild-3_0000*`, `Bild_0013*`,
`Bild-2_0000*` (können in den Papierkorb, wenn Sascha will).

## RTX 3080 am M.2-Steckplatz statt USB4; Bilder und Strata neu gemessen (23.10.2026)

Sascha hat die 3080 vom eGPU-Dock (USB4) an einen M.2-Steckplatz umgesteckt. Geprüft: Windows und Treiber sehen sie als
Karte 2 (gleiche UUID, Bus 0x87 statt 07, PCIe 4.0 ×4); die Reihenfolge nach Busnummer bleibt FE 0, Suprim 1, 3080 2.
`karten."2".bus` in `zentrale\config.json` musste von 7 auf 135 (= 0x87): Name und `nebenkarte` gelten nur bei passendem
Steckplatz – sonst meldete `/api/platz` die 3080 nicht mehr als Nebenkarte (beim ersten Start nach dem Umstecken gesehen). Kopiergeschwindigkeit (PyTorch, 1 GiB gepinnt, je
5 Läufe): **3080 6,6 GB/s** hin und zurück (USB4 vorher 3,1), die 3090 je 12,9–13,2 GB/s (PCIe 4.0 ×8). Die Messungen
„lohnt nicht für Strata/verteilte Modelle“ vom 22.10. galten für USB4.

**Bilder auf der 3080 am M.2** (Studio, ComfyUI 3 frisch gestartet, je ein Auftrag allein): erstes Bild 1584×1056 Turbo mit
Laden **11,1 s** (USB4 13,6, FE 8,9), Folgebild **7,4 s** (USB4 7,6, FE 6,6), Bearbeiten 2752×1536, 40 Schritte, Details
**129,9 s** (USB4 133,2, FE 113,9, Suprim 109,6). Nur wenig Gewinn: Den Abstand zur 3090 macht die Rechenleistung der 3080,
nicht die Leitung. Testbilder `Werkstatt-Abnahme\Bild-3_00007_`, `Bild-3_00008_`, `Bearbeitet-3_00002_`.

**Strata auf drei Karten am M.2** (Auftrag Sascha „dann Strata auf drei Karten“; gleiches Skript und gleiche Proben wie am
22.10., `nachweise\2026-10-21-strata-rtx3080`, Läufe `*-m2` in `ergebnisse.jsonl`; Bild & Video vorher beendet, für den Test
`CUDA_VISIBLE_DEVICES=0,1,2`, weil die Benutzervariable die 3080 sonst ausblendet). Strata misst selbst 6,7 GB/s zur 3080.
Schreiben laut Server in Token/s:

| Lauf | Text | Code | 70K-Prompt | RAM frei geladen |
|---|---|---|---|---|
| IQ3_S, zwei 3090 | 102–108 | 136–158 | 3.067 | 0,3 GiB |
| IQ3_S, FE → 3080 → Suprim (M.2) | 37–39 | 60–63 | 3.547 | 1,2 GiB |
| – dasselbe über USB4 (22.10.) | 37–68 | 33–44 | 3.647 | 0,7 GiB |
| Q4, zwei 3090 | 86–97 | 108–119 | 2.578 | 15,4 GiB |
| Q4, FE → 3080 → Suprim (M.2) | 48–62 | 46–49 | 3.289 | 21,6 GiB |
| – dasselbe über USB4 (22.10.) | 44–60 | 42–44 | 3.036 | 21,5 GiB |

Ergebnis: Die doppelte Übertragungsrate ändert am Schreiben fast nichts – mit der 3080 bleibt es bei der Hälfte bis einem
Drittel. Pro Token wandern nur wenige Daten zwischen den Karten; es bremsen die zusätzliche Stufe in der Kette und die
langsamere 3080. Einlesen langer Prompts 16–28 % schneller, Bilder lesen alle Läufe richtig (3 Pflanzen). **Strata bleibt auf
den zwei 3090.** Ornith 122B über drei Karten (gleiche Kette, 22.10. Schreiben langsamer) daraufhin nicht neu gemessen.

## Werkstatt: Formular unter der Taskleiste, Kartenband mit drei Karten, große Bilder auf jeder Karte (23.10.2026)

Saschas Meldung: „Erstellen“ liegt oft unter der Windows-Taskleiste, der Scrollbalken klappt nicht immer; ein zweites
bearbeitetes Bild wartet auf die FE, statt die nächste freie Karte zu nehmen.

- **Formular:** Im breiten Fenster steht das Studio-Formular ab `--oben` (210 px), durfte aber `100vh − 134 px` hoch sein –
  es ragte 76 px unter den Fensterrand, samt Ende des Scrollbalkens und „Erstellen“. Jetzt `100vh − --oben − 16 px` (ebenso die
  Transkriptliste der Zusammenfassung, dort 70 px), und „Erstellen“ bleibt unten im Formular stehen (`sticky`), auch wenn
  darüber gescrollt wird. Geprüft bei 1600×860 und 1200×760: Formular endet 16 px über dem Rand.
- **Kartenband:** Seit der RTX 3080 rutschte ihre Kachel in eine zweite Zeile und verdeckte den Kopf des Inhalts. Jetzt eine
  Spalte je Karte (`--karten`), Text „Alle Karten sind frei“ / „n Karten rechnen parallel“.
- **Große Bilder:** Im Protokoll vom 23.10.2026 12:32 lief Bearbeiten 2752×1536 auf der FE, das zweite wartete 87 s, obwohl
  die Suprim frei war. Ursache: Bilder über 2 MP planten auf einer Karte 22.016 MiB (Messung 24.09.2026, BF16); die Suprim hat mit
  Monitor ~21,6 GiB frei (Windows & Programme ~2,4 GiB), die 3080 fasst 19,7 GiB – also passte das Bild nirgends sonst, und
  `_darf_nehmen` ließ es in der Schlange auf Prozess 1 warten (richtig nach der Regel). **Messung** mit `eine` 19.456 MiB: drei
  INT8-Bearbeitungen 2752×1536, 40 Schritte, Details, gleichzeitig (`--anzahl 3`) – Prozess 3 (3080) 133,2 s, Prozess 1 (FE)
  113,9 s, Prozess 2 (Suprim, Monitor) 109,6 s; Spitzen 18,6 GiB (3080), 23,1 GiB belegt auf der Suprim samt Windows; Bilder
  angesehen, sauber (keine Kachelnähte). **Übernommen:** `bedarf_gross_mib.eine` 19.456 (geteilt bleibt 18 + 6 GiB). Große Bilder
  gehen damit wie kleine zuerst an die 3080 (gut 15 % langsamer als eine 3090, aber parallel statt nacheinander).
  Testbilder: `Studio\Werkstatt-Abnahme\Bearbeitet_00006_`, `Bearbeitet-2_00001_`, `Bearbeitet-3_00001_`.
- Nebenbefund: ComfyUI 3 beendete sich am 23.10.2026 12:30 beim Start („No CUDA GPUs are available“) – die 3080 war da noch
  nicht bereit; später lief er. Bei fehlender 3080 rechnen die 3090 wie vorher.
- Tests: Zentrale 168, Werkstatt 225, grün (Werkstatt neu gestartet).

## Regel „nur Standardbibliothek, keine Pakete/Downloads“ gestrichen (21.10.2026)

Sascha: „Das kam aus einem Video, nicht von mir“ – die feste Grenze „Python nur mit Standardbibliothek. Keine neuen
Pakete, Umgebungen, Downloads oder Modelle“ ist aus AGENTS.md entfernt. Bestehender Code bleibt, wie er ist; neue
Pakete, Umgebungen, Downloads oder Modelle sind möglich, wenn Sascha sie beauftragt (globale Regel: nichts ungefragt).
Ältere Einträge hier und in den SPEC-Dateien, die „nur Standardbibliothek“ nennen, beschreiben den damaligen Stand.

## Reiter „Chat“ mit der Strata-Oberfläche (21.10.2026)

Auftrag Sascha: „Prüf zuerst die Strata-App aus apps\host: was sie beim Start tut, Updater/Tunnel abschalten, dann als
Reiter in die Zentrale einbetten“, danach „Node 24 portabel nach C:\LLM\runtimes, npm-Pakete holen, UI bauen“.

- **Geprüft (Strata v0.2.1.3, `apps\host\server\index.mjs`):** Beim Start lauscht die App nur auf `STRATA_BIND`
  (127.0.0.1) und `STRATA_PORT`. Cloudflare-Tunnel und Freigabe nach außen starten nur über `/api/serving/tunnel` bzw.
  `/api/serving/share` (Klick). Die Update-Prüfung liest nur die Release-Liste von GitHub, wenn man sie in den
  Einstellungen anstößt. Downloads/Installationen sperrt `STRATA_NO_ACQUIRE=1`; `STRATA_NO_BUNDLED_ENGINE=1` verhindert
  das Auspacken einer mitgelieferten Engine (im Quellordner gibt es ohnehin keine). `/api/*` weist fremde Herkunft
  (Origin nicht localhost) mit 403 ab; `/v1/*` ist offen (CORS `*`), wie Stratas eigene Schnittstelle. Ohne
  `STRATA_REAL_ENGINE=1` liefe die Modellbibliothek als Vorführung (vorgetäuschte Antworten), deshalb gesetzt.
- **Eingerichtet:** Node v24.22.0 portabel (`C:\LLM\runtimes\node-v24.22.0-win-x64`, SHA-256 aus `SHASUMS256.txt`
  geprüft; Node 22 auf dem PC reicht nicht, die App will ≥ 24.12). In `apps\host`: `npm ci --ignore-scripts`
  (80 Pakete), `npm run build` → `dist`. Daten `C:\LLM\runtimes\Strata-App\daten`, Modellordner (leer)
  `…\modelle`, Arbeitsordner `C:\Workstation\Arbeitsmaterial\Strata-Chat`.
- **Zentrale:** `zentrale\chat_app.py` (Status, Starten losgelöst, Beenden nur bei passendem Port, `node.exe` und Skript),
  Eintrag `chat_app` in `config.json`, `GET /api/chat-app`, `POST /api/chat-app/starten|beenden`, Reiter „Modelle | Chat“
  im Kopf, eingebettet per iframe (die App setzt kein `X-Frame-Options`). Tests `test_chat_app.py`; Zentrale 132 OK.
- **Verbindungen in der App** (über `/api/model-providers`): Flash-Next (8095), Ornith Q4 PolyStrata (8097),
  Qwen3.8-27B NInfer (8080), Ornith Q6 Ollama (11434), Test Ornith 122B llama.cpp (8098).
- **Am echten System geprüft:** Start über den Reiter, App eingebettet und bedienbar, Verbindungen gespeichert.
  Noch offen: ein Chat mit geladenem Modell durch die App.
- **Grenze:** Ein Ollama-Modell, das nicht geladen ist, lädt Ollama auf Anfrage der App selbst (an der Zentrale
  vorbei) – in README.md als Hinweis.

## Reiter „Monitor“ mit Stratas Monitor-Seite (21.10.2026)

Sascha: Gemeint war eigentlich Stratas Anzeige mit Token/s, Vorgängen und Temperaturen – „Bau einen Reiter Monitor,
der Stratas eigene Monitor-Seite zeigt (Strata 8095 oder PolyStrata 8097, je nachdem was läuft)“. Nur Oberfläche
(`web\index.html`, `app.js`, `style.css`): Der Reiter nimmt die laufenden Einträge der Arten `strata`/`polystrata` aus
dem Status und bettet `http://127.0.0.1:<port>/#monitor` ein (Strata setzt keine Rahmen-Sperre); laufen beide, Auswahl
per Knopf; beim Verlassen wird die Seite entladen (sie fragt sonst `/metrics` weiter ab). Den API-Monitor mit
gespeicherten Prompts (`--api-monitor`) nicht eingeschaltet. Geprüft am echten System: ohne Strata Hinweistext; mit
Flash-Next (Zentrale gestartet) Anzeige live – Testanfrage 114,8 Token/s, 56 °C, 527 W.

## Ornith 1.5 122B getestet (21.10.2026, nicht in der Zentrale)

Auftrag Sascha nach dem Video von Fahd Mirza: „lad mal runter wir testen“. AtomicChat `AD-Q5_K-IQ4_XS` (70,8 GiB,
KL 0,023, Top-1 94 %), SHA-256 = Hugging Face, in `C:\LLM\models\Ornith-1.5-122B\` (zwei Teile und zusammengefügt eine
Datei für PolyStrata, `llama-gguf-split --merge`). Bauart Qwen3.5-MoE: 48 Schichten, 256 Experten, 8 je Token
(~10 Mrd. aktiv). Gleiche drei Messungen (Text 570, Code ~1.000 Antworttoken, PLAN.md als langer Text 39.198 Token):

| Weg | Text | Code | lang: lesen / schreiben | im VRAM |
|---|---:|---:|---:|---|
| llama.cpp b10754, `--fit`, MTP | 9,7 | 19,1 | 125 / 20,3 Token/s | 43 GiB, ~28 GiB Experten rechnet die CPU |
| PolyStrata 0.1.45-poly.1, Expert-Cache | 13,2 | 27,8 | **808** / 16,7 Token/s | 6.147 von 12.544 Experten (31,6 GiB) |

- PolyStrata liest 6,5-mal schneller ein, schreibt aber kaum schneller: Die Hälfte der Experten bleibt auf der CPU.
  Nach dem Laden waren nur noch 0,3 GiB RAM frei. Zum Vergleich Flash-Next über Strata: 115–117 / 159–179 / 3.895.
- Lehre: Der Q5-Fassung fehlt VRAM, nicht RAM. Schneller würde eine kleinere Fassung, die fast ganz in 2 × 24 GiB
  passt (etwa `AD-IQ3_XXS-IQ2_S`, 44 GiB, Top-1 86 %) – dann aber ungenauer. Agententest über DSH ausgelassen (zu
  langsam). Einstellungen: `C:\LLM\runtimes\PolyStrata\strata-ornith-122b-2gpu.json`, Tokenizer `packs\ornith-122b`;
  Skripte und `ergebnisse.jsonl` in `Projekte\Lokale-Wissensextraktion\nachweise\2026-10-18-strata-webdesign\`
  (`ornith122_test.py`, `ornith122_poly.py`).
- **22.10.2026, dazu die RTX 3080 20 GiB am AG02 über USB4** (Auftrag Sascha „miss Ornith 122B Q5 mit llama.cpp auf allen
  drei Karten“; `ornith122_test.py --ncmoe 0 --drei tempo`, Port 8100, `--fit` mit Rand 1024/1800/1024 MiB): belegt
  22,6 + 21,6 + 17,4 GiB, nur noch ~10 GiB Experten auf der CPU (vorher ~28). Ergebnis: Text 9,0, Code 12,9, lang
  **190** / 20,1 Token/s – Einlesen 50 % schneller, **Schreiben nicht** (Code sogar langsamer, 19,1 → 12,9). Jedes
  Token läuft nacheinander durch alle drei Karten und zweimal über die USB4-Leitung; die bremst stärker, als die
  eingesparten CPU-Experten bringen. Wie bei Strata (Abschnitt vom 22.10.): die 3080 über USB4 lohnt sich nicht für ein
  Modell, das über mehrere Karten verteilt wird. Nach dem Laden nur 1,7 GiB RAM frei (mmap).

## Messungen lokaler Sprachmodelle am 16.10.2026 (Übersicht)

Alle Läufe mit denselben Proben (`llm_test.py`: kurz, 2× Text à 400, 2× Code à 600 Token, langer Prompt ≈ 70.600 Token);
Werte = Schreiben laut Server in Token/s. Vollständige Liste aller 23 Läufe mit Uhrzeit:
`Projekte\Lokale-Wissensextraktion\auswertungen\2026-10-16-tagesuebersicht-messungen.md`, Rohdaten
`nachweise\2026-10-16-llamacpp-strata-vergleich\ergebnisse.jsonl`. In die Zentrale eingebaut wurde davon nur Strata Q4
(Stufe 6 oben); alles andere sind Prüfungen.

| Modell / Weg | Text | Code | Einlesen | Ergebnis | Akte |
|---|---|---|---|---|---|
| **Strata IQ3_XXS 128K** (Zentrale), Monitor Intel / FE | 110 / 92–97 | 139–166 / 122–147 | 3.611 / 3.609 | bleibt Standard | `2026-10-16-llamacpp-…-vs-strata.md` |
| Strata Q4 (UD-IQ4_XS), 64-GB-Auslagerung, mit Bildern | 83–93 | 97–115 | 2.541–2.591 | Variante „Q4 · genauer“ | `2026-10-16-strata-udiq4xs-2x3090.md` |
| Flash-Next IQ3_XXS in llama.cpp b11669 (`--fit`) | 51–55 | 55–56 | 675–701 | Strata 2× schneller | `2026-10-16-llamacpp-…-vs-strata.md` |
| dto. mit MoE-Expertencache 8 GB | 25–51 | 34–50 | 269–303 | langsamer, verworfen | dto. |
| Qwen3.8 27B Q8, llama.cpp `-sm tensor` / `layer` | 43 / 28 | 43 / 26–27 | 1.354 / 1.849 | tensor schneller, NInfer besser | dto. |
| NInfer 27B (eine Karte) | 55–57 | 57–62 | 733 | bleibt | dto. |
| Nemotron 3.5 Super VL UD-Q3_K_XL (llama.cpp) | 34 (18–23 mit wenig Kernen) | 34 | 225 | zu langsam, Bild falsch; Dateien in `D:\LLM-lokal\Testmodelle` | `2026-10-16-nemotron35-super-vl-udq3kxl.md` |
| Ornith 1.5 Q5 mit Strata, eine Karte (Temp. 0 / 0,2) | 123–141 / 95–100 | 151–164 | 1.600 | ≈ Ollama auf zwei Karten; nicht eingebaut | `2026-10-16-ornith-mit-strata.md` |
| Ornith 1.5 Q6 mit Strata, eine Karte | 101–108 | 127–136 | – | RAM zu knapp (1,6 GiB frei) | dto. |
| Ornith 1.5 Q5 über Ollama (Zentrale), beide Karten | 116–150 | 154 | – | bleibt Standard (Hermes) | dto. |

Ornith Q4_K_M startet in Strata nicht (Experten-„down“ in Q4_K). **Entschieden (Sascha 16.10.2026, „alles erstmal da
lassen“):** die drei für Strata umgewandelten Ornith-Dateien (72 GB, `C:\LLM\models\Ornith-1.5-Strata\`) bleiben vorerst
liegen; ebenso die Testdateien des Tages im Studio-Projekt „Werkstatt-Abnahme“ (`Video-2-EineKarte_00001_`–`00003_`,
Testbilder und -videos). Später klären: behalten, nach `D:\LLM-lokal\Testmodelle` verschieben oder nur Q5 behalten.

## Stufe 7 – ohne gemeinsame GPU-Sperre (16.10.2026)

Auftrag Sascha: „Ja, Sperre raus … beide Karten gleichzeitig“, „warum sollen nicht zwei Arbeiter parallel auf die eine
Grafikkarte zugreifen?“ Die Werkstatt hatte seit September eine gemeinsame Sperre (`threading.Lock` in `server.py`,
weitergereicht an Transkription, lokale Zusammenfassung, Messlauf, Studio, Texterkennung): immer nur ein GPU-Auftrag.
Grund damals: 3090 + 3080, fast jeder Auftrag brauchte beide Karten.

**Umbau:** Sperre an allen fünf Stellen entfernt; Schutz ist allein der Speicher laut Zentrale.
- Zentrale `/api/platz`: Anmeldung trägt `schluessel` (welcher Verbraucher belegen wird) und `basis` (seine Belegung
  bei der Anmeldung); `planung.angemeldet_rest` zieht je Schlüssel nur den Zuwachs seit der Anmeldung ab (vorher nur
  für die Transkription, Studio-Anmeldungen zählten doppelt). „In ComfyUI läuft gerade ein Auftrag“ ist nur noch ein
  Grund, wenn kein Studio-Auftrag angemeldet ist (fremder Auftrag, Bedarf unbekannt). Studio darf ohne Zusatzbedarf
  anmelden (leerer Bedarf als Kennzeichen).
- Studio meldet immer an (`schluessel` „bild-video“) und hält die Anmeldung bis zum Ende (wie bisher alle 20 s).
- Texterkennung wartet nicht mehr auf ComfyUI (LightOnOCR ist geladen, braucht keinen neuen Platz).
- Lokale Zusammenfassung und Messlauf ohne Sperre (Modell geladen); Messlauf daher nur mit Ruhe aussagekräftig.

**Geprüft (16.10.2026):** Tests Zentrale 104, Werkstatt 199 grün. Live: 8 Seiten Texterkennung (LightOnOCR auf der FE)
und 2 Studio-Bilder (Suprim) gleichzeitig – beide Karten 16:22:46–16:23:25 bei 90–100 % Last, OCR 45 s, Bilder fertig.
Danach 2 Bilder (Suprim) und eine Whisper-Transkription (FE, 2,7 GiB angemeldet, 4 s) gleichzeitig, beide fertig.
Grenze: ComfyUI rechnet je Prozess einen Auftrag nach dem anderen; zwei Studio-Aufträge parallel brauchen einen
zweiten ComfyUI-Prozess (Stufe 8, geplant).

**Design der Werkstatt (16.10.2026, Sascha: „Design modifizieren, moderner gestalten“).** App-Stil „Petrol klar“ wie
Praxis-OS (Saschas Designsystem): helle Flächen, 1-px-Linien, Radien 8/12 px, Petrol `#0B6478` für Hauptaktionen und
Fokus, Windows-11-Schrift (Segoe UI Variable), Großbuchstaben-Beschriftungen; ab 1.280 px Breite eine dunkle
Petrol-Leiste links (Navigation), darunter die alte Kopfleiste in Petrol. Signatur: **Kartenbahnen** unten in der
Leiste – je 3090 die Belegung nach Verbraucher in dessen Zentrale-Farbe (Zentrale gibt `farbe` in `/api/platz` mit,
Werkstatt reicht `verbraucher` weiter) und wer wie viel hält. Seitentitel je Bereich. Dunkelmodus angepasst. Nur
`web\style.css`, `web\app.js` (Kartenbahnen), ein Satz in `index.html`; keine Abläufe geändert. Geprüft im Browser
(alle fünf Bereiche, hell/dunkel, 1.120/1.440 px). Die Zentrale hat das alte Design (offen: angleichen).

**Stufe 8 – Gutachten Astra (gpt-6-astra xhigh, nur lesend), Urteil CHANGES REQUESTED** (Wortlaut: `SPEC-studio-parallel-ASTRA-frage.md` und `-antwort.md`):
Speicherrechnung je ComfyUI-Prozess statt Gesamtverbraucher „bild-video“ (sonst landet der zweite Auftrag auf
derselben Karte, und `angemeldet_rest` rechnet überlappende Studio-Anmeldungen falsch – für einen Prozess ohne
Überlappung heute korrekt); Anmeldung über den ganzen Lebenszyklus (auch verlorene `/prompt`-Antwort, Uploads);
Dateischutz (Präfix je Prozess für alle Ausgaben, Uploads/Masken und Begleitdateien exklusiv); vollständiger
Instanzkontext im Studio (Port, Zustand, Abbruch, `_letzte_rechenzeit`); Erkennung/Stopp/`/free` je Prozess;
Empfehlung: je Prozess **eine** sichtbare Karte, Zweikarten-Videos nur mit koordiniertem Moduswechsel; H3 auf einer
3090 erst messen. Stand: nicht gebaut, überarbeiteter Plan bei Sascha.

## Stufe 8 – zwei Studio-Aufträge gleichzeitig (16.10.2026)

Auftrag Sascha: „zwei Aufträge direkt nebeneinander … Bilder parallel auf beiden Karten oder Video auf der einen, Bild
auf der anderen“. ComfyUI rechnet je Prozess einen Auftrag, daher **zwei ComfyUI-Prozesse** aus derselben Installation.
Plan von Astra (gpt-6-astra xhigh) gegengelesen: CHANGES REQUESTED, alle Punkte eingebaut (Wortlaut
`SPEC-studio-parallel-ASTRA-frage.md`/`-antwort.md`). Eine zweite Astra-Runde war nicht mehr möglich (Codex-Abo abgelaufen).

- **Zentrale:** Eintrag `bild-video` mit `comfy_port_2` 8189, `comfy_karte_2` 1, `comfy_name_2`. Starten startet beide
  (Prozess 2: `--cuda-device 1`, eigene `temp-2`/`user-2`, gleiche Ausgabe), Beenden beide, Entladen je Prozess
  (`freigeben:bild-video-2`). Erfassung: Prozess 2 an `--port 8189` erkannt, Verbraucher `bild-video-2` („ComfyUI 2
  (Suprim)“). `/api/platz`: Anmeldung mit `schluessel` (`bild-video` bzw. `bild-video-2`) und `basis`;
  `planung.angemeldet_rest` rechnet je Schlüssel ab der ältesten Basis und verteilt den Zuwachs der Reihe nach (Astras
  Gegenbeispiele als Tests); „In ComfyUI läuft gerade ein Auftrag“ nur für einen Prozess ohne Studio-Anmeldung.
- **Studio:** `Instanz` je Prozess, zwei Arbeiter (`_schleife(inst)`). Prozess 1 sieht beide Karten und rechnet alles
  (Videos über zwei Karten nur hier); Prozess 2 sieht nur die Suprim (dort „gpu:0“, `mit_geraeten(..., lokal)`) und nimmt
  nur Aufträge mit Ein-Karten-Möglichkeit, und nur wenn er läuft. Solange Prozess 2 läuft, nimmt Prozess 1 für
  Ein-Karten-Aufträge die Suprim nicht (gemessen: sonst legte er ein Bild dorthin und Prozess 2 stand). Kartenwahl rechnet
  nur den eigenen Cache an (`platz_fehlt(..., schluessel)`). Ausgaben von Prozess 2 heißen **`…-2_00001_.png`** (ComfyUI
  zählt nicht prozessübergreifend). Anmeldung immer (auch ohne Zusatzbedarf) und von einem eigenen Faden alle 20 s
  verlängert; Übergabe mit eigener `prompt_id` (verlorene Antwort gibt nicht frei); Hochladen unter einem Lock, bytegleiche
  Markierungen nicht neu geschrieben; Begleitdateien mit eigenem tmp-Namen, die Bibliothek legt nur exklusiv neu an.
- **Geprüft:** Tests Zentrale 116, Werkstatt 209 grün (`zentrale\tests\test_comfy2.py`, `werkstatt\tests\test_parallel.py`).
  Live: Prozess 2 sieht nur die Suprim (nvidia-smi Bus 04). Zwei Entwurfsbilder (2752×1536, 30 Schritte) **gleichzeitig**:
  17:07:09–17:08:20 beide Karten 100 %, Prozess 1 auf der FE, Prozess 2 auf der Suprim. Zwei Fehler beim echten Lauf
  gefunden und behoben (Prozess 2 nahm wegen der geteilten Bild-Variante keine Bilder; Prozess 1 belegte die Suprim).
- **FE gegen Suprim** (gleiches Bild): Suprim 70,6/72,4 s bei ~398 W (Grenze 420 W), FE 82,0 s bei ~324 W (Grenze
  350 W, Monitor) – Suprim ~12 % schneller für ~23 % mehr Leistung. Leistungsgrenze senken nur durch Sascha (Systemeinstellung).
- **MiniMax-H3 auf einer RTX 3090** (Auftrag Sascha „mach die Messung mit dem Videomodell“): Video-Ablauf des Studios
  mit allen Geräten auf der einzigen Karte von ComfyUI 2 (Suprim), Platz vorher angemeldet, Text aus Physio-Szene,
  Turbo, 8 Schritte (Skript `h3_eine_karte.py` in `Lokale-Wissensextraktion\nachweise\2026-10-16-llamacpp-strata-vergleich`).
  ComfyUI 0.37 lädt dynamisch („prepared for dynamic VRAM loading … Staged“) und braucht keine zweite Karte:

  | Video | eine Karte (Suprim) | über zwei Karten | VRAM-Spitze | RAM frei min |
  |---|---|---|---|---|
  | 960×544, 5 s (124 Bilder) | **118,7 s** (`Video-2-EineKarte_00001_`) | 119,5 s (heute, `Video_00023_`) | 23,8 GiB | 35,9 GiB |
  | 1344×768, 5 s (124 Bilder) | **327,8 s** (`…_00003_`, 36 s je Schritt) | 366–398 s (11.10., 3090 + 3080) | 23,9 GiB | 26,7 GiB |
  | 1344×768, 10 s (243 Bilder) | **1058 s** (`…_00002_`, 123 s je Schritt) | – | 23,8 GiB | 26,2 GiB |

  Eine Karte ist also nicht langsamer. **Eingebaut:** Video-Bedarf `eine_ohne_monitor` 22.528 MiB (neue Rolle: ganz
  auf einer Karte, nie auf der Monitorkarte – die FE hat mit Monitor ~21,3 GiB frei). Prozess 2 kann damit Videos
  (`Instanz.kann`, nicht wenn der Monitor an seiner Karte hängt) und nimmt sie zuerst (`bevorzugt`); Prozess 1 lässt
  sie ihm, solange er läuft; läuft er nicht, rechnet Prozess 1 das Video allein auf der Suprim (FE bleibt frei).
  **Befund beim echten Lauf:** Bild zuerst bestellt → Prozess 2 nahm es sofort, das Video wartete danach auf ihn.
  Deshalb `_wer_zuerst`: Aufträge ohne Video gehen an den ersten freien Prozess, der sie jetzt ganz auf eine eigene
  Karte legen kann (Prozess 1 zuerst, die Suprim bleibt für ein Video frei; ein großes Bild, das nicht auf die FE
  passt, nimmt Prozess 2). Grundlage ist der Stand der Zentrale, den die Arbeiter höchstens alle 3 s außerhalb der
  Sperre holen (`_lage_auffrischen`, `platz.stand_ohne_start` – startet die Zentrale nicht); älter als 15 s oder
  nichts passt allein: wer zuerst kommt (wie vorher). Tests Werkstatt 211 grün. **Live 18:02–18:03:** Bild (1664×928)
  in Prozess 1 auf der FE, Video in Prozess 2 auf der Suprim; ein zweites Bild (1584×1056) während des Videos:
  18:02:58–18:03:02 **beide Karten 100 %**, Bild 6,9 s; das Video (960×544, 5 s, „Schnell“) war nach 71,0 s fertig
  (allein sonst 72–83 s) – die beiden stören sich nicht.
- **Nach einem Video hält ComfyUI 2 ~20 GiB auf der Suprim** (sein Zwischenspeicher, wie ComfyUI 1 bisher). Bilder
  daneben stört das nicht (FE); wer sonst die Suprim braucht (Strata, ein großes Modell), gibt in der Zentrale frei
  (`freigeben:bild-video-2`, mit Bestätigung). Gemessen vorher: Ein Video von Prozess 1 über beide Karten wartete
  deshalb, bis ich `bild-video-2` in der Zentrale freigab – mit der neuen Verteilung kommt das nur noch vor, wenn
  Prozess 2 aus ist.

**Design „Bernstein-Kommandozentrale“ (16.10.2026, Saschas Wahl).** Das Petrol-Design gefiel Sascha nicht („hättest mich
fragen können“). Codex erzeugte einen Entwurf (Bernstein, angelehnt an die Whisper Workbench RTX), das lokale Studio drei
weitere (Signalstudio, Nachtstrom, Studio Volt); Ablage `C:\Workstation\Arbeitsmaterial\Werkstatt-Design\` bzw. Studio-Projekt
`Werkstatt-Design`. Umgesetzt: fast schwarzer Grund `#050606`, Flächen `#0B0F0F`/`#131716`, warme Linien
`#3A2410`/`#9A5208`, Text `#F5F1E8`/`#BDB4A5`, Akzent `#FF8A00`/`#F59E0B` (dunkler Text auf Orange), Status Lime/Gelb/Rosa,
Consolas für Messwerte; immer dunkel. Leiste links ab 1.280 px mit orange markiertem Bereich; **Kartenband oben** (fest)
mit beiden 3090: Belegung/Gesamt, Verbraucher, Auslastung als 24er-Segmentleiste und Verlaufskurve (aus `/api/platz`,
letzte 72 Werte), Zeile „Beide Karten rechnen parallel“. Nur `web\style.css`, `web\app.js`; ersetzt das Petrol-Design.

## Stufe 3u – schnellere Aufmerksamkeit für Videos (17.10.2026)

Anlass: GitHub-Recherche vom 16.10.2026 (`Projekte\Lokale-Wissensextraktion\auswertungen\2026-10-16-github-recherche-2x3090.md`,
Vorschlag 1) und Video „MiniMax H3 Just Got 2.6x Faster (New Veda Attention)“ (The AI Brief, 17.10.2026: Sage ~2,3×
schneller, fast bildgleich). Auftrag Sascha: „ok dann go für das was Sinn macht. Achtung beide Karten können jetzt
gleichzeitig angesprochen werden.“ Gewählt: der Kernknoten `ModelAttentionBackend` („comfy kitchen attention“, INT8), den
Bilder seit Stufe 3k nutzen – ohne neue Pakete, Custom Nodes oder Downloads. Veda (Custom Node, ComfyUI ≥ 0.38, nur
Ref2VA, sichtbar weicher) und das SageAttention-Paket nicht.

**Messung** (Skript `h3_aufmerksamkeit.py`, Ergebnisse `ergebnisse.jsonl`, Transkripte unter
`Lokale-Wissensextraktion\nachweise\2026-10-17-h3-schnelle-aufmerksamkeit\`): Studio-Ablauf `video_graph`, alles auf
ComfyUI 2 (Suprim), Platz angemeldet, 960×544, 5 s (124 Bilder), Sprech-Prompt einer Physiotherapeutin; je Fall A1 (lädt),
B (mit Knoten), A2; dann zweite Nummer A/B.

| Fall | ohne (A2) | mit (B) | zweite Nummer ohne/mit | je Schritt ohne Grundzeit |
|---|---|---|---|---|
| Schnell, DMAD, 4 Schritte, aus Text | 64,6 s | 49,0 s | 66,7*/49,0 s | ×0,55 |
| Schnell beste, acc8, 8 Schritte, Referenz (`Bild_00027_`) | 117,8 s | 83,6 s | 125,9*/83,2 s | ×0,61 |
| Beste, 20 Schritte, aus Text | 245,1 s | 167,0 s | 251,3*/167,3 s | ×0,64 |

\* mit Laden der Modelle. VRAM-Spitze gleich (23,8–24,0 GiB). A1 und A2 bitgleich (SSIM 1,0): ohne Knoten bleibt alles
wie bisher. A2 gegen B SSIM 0,81–0,85: eine leicht andere Fassung derselben Szene.

**Ehrlich angesehen** (Einzelbilder, Ausschnitte von Gesicht und Hand, Ton): gleiche Person, auch aus dem
Referenzporträt; gleicher Raum, gleiche Kamera, Gesicht und Haut gleich scharf. Ton: Lautstärkeverlauf bei Nummer 7
0,96–0,99, bei Nummer 8 0,72–1,0 gleich; Whisper Medium hört in 5 von 6 Paaren wortgleich „Willkommen! Heute zeige ich
Ihnen eine einfache Übung für die Schulter.“ (im sechsten, Referenz Nummer 7, haben beide je einen kleinen Versprecher:
ohne „Kjell … Shooter“, mit „heute, heute“). Unterschiede nur, wo der Prompt offenlässt: 20 Schritte Nummer 7 – ohne
eine saubere Faust, mit eine ungeschickt abgeknickte flache Hand; Nummer 8 aus Text 4 Schritte genau umgekehrt (Zufall
der Fassung, kein Muster); Nummer 8 bei 20 Schritten der nicht beschriebene Pullover beige statt grau. Urteil:
gleichwertig, ein Viertel bis ein Drittel kürzer.

**Eingebaut** (nur neue Aufträge, Feld `schnell`, wie bei Bildern; „Nochmal“ älterer Videos bleibt ohne):
- `video_graph`: Knoten 29 `ModelAttentionBackend` hinter allen LoRAs und `MiniMaxH3SigmaShift`, vor Scheduler/Guider;
  `weiter_graph` übernimmt ihn. Rücklesen (`einstellungen_aus_graph`) und Bibliothek (`info.schnell`) auch für Videos.
- `werkstatt\config.json` `studio.video.schnelle_aufmerksamkeit` (`aktiv`, `backend`, `zeitfaktor` 0,6);
  `video_schnell_verfuegbar` in den Einstellungen. Text, Bild, Referenz, Weiterführen; Szenenfolge merkt es sich für alle
  Szenen (`f.schnell`). Nicht Zeitlupe und Video freistellen.
- Zeitschätzung: Sekunden je Schritt mit schneller Aufmerksamkeit getrennt gelernt, ohne eigene Läufe ×0,6;
  `video.zeit.je_schritt_schnell_s` für die Oberfläche.
- Oberfläche (`studio.js`): neue Videos und Szenenfolgen senden `schnell: true`, „Nochmal“ nur, wenn das Original es
  hatte; Zeitanzeige mit dem schnellen Wert. Skill `bild-video-studio`: `video_schnell` in `status`,
  `video_schnell_wunsch` für Video, Weiterführen und Szenenfolge.

**Geprüft:** Tests Werkstatt 214 (3 neu: Ablauf, Auftrag/Zeitschätzung, Szenenfolge), Zentrale 116 grün. Live über den
Skill: Video aus Text „schnell“ (`Video-2_00003_`, Nummer 11) in Prozess 2 auf der Suprim, **geschätzt 56 s, gerechnet
56,3 s**, gleichzeitig ein Bild in Prozess 1 auf der FE; Begleitdatei und Bibliothek `schnell: true`, im Video Knoten 29
hinter Knoten 28. Oberfläche: „Beste“ zeigt „etwa 3 min je Video“, das Formular schickt `schnell: true` und `dmad: true`
(Anfrage abgefangen, nichts erzeugt). Abschalten: `studio.video.schnelle_aufmerksamkeit.aktiv` auf `false`.

## Fibo 2.0 in der Zentrale und das Atelier (22.10.2026, fertig)

Auftrag Sascha: Fibo 2.0 (Bria, 8B, Dev + Edit Turbo) testen, „nach erfolgreichem Test in die Modellzentrale einbauen
oder standalone, was sinnvoller ist“, dazu ein Programm, in dem man Bilder und Objekte etwa auf einem YouTube-Thumbnail
oder Flyer verschiebt; das Destillat (Edit Turbo) nutzen. Entscheidung: Modell als Dienst in der Zentrale (Art
`python_dienst`), Editor als eigene App „Atelier“. Spec, Gegenprüfung (Codex nicht nutzbar: `gpt-6-astra` mit
ChatGPT-Konto abgelehnt) und Messwerte: [SPEC-atelier.md](SPEC-atelier.md), [SPEC-atelier-REVIEW-LOG.md](SPEC-atelier-REVIEW-LOG.md).

- **Tests (FE):** Dev 30 Schritte = 50 Schritte in der Qualität (98 statt 160 s); Guidance 3,5/5/7 gleichwertig. Gedruckte
  Schrift korrekt („Backstube Müller“), Kreide-Handschrift 1 von 3 richtig. Beschreiber: Claude ≥ DeepSeek Flash > V4 Pro.
  Edit Turbo 20–35 s, gleich gut oder besser als Dev (≈6 min); Zusammenführen einer Collage mit Turbo stimmig, mit Dev
  kaum verändert. Mehrere Referenzen: gescheitert; Aquarell schwach.
- **Bau:** DeepSeek V4.1 Flash über DSH in vier Läufen (Dienst + Zentrale-Art; Editor; KI-Aktionen; Platzreserve), je eigener
  Worktree, Abnahme durch Claude gegen den Verifikationsplan.
- **Korrekturen bei der Abnahme:** Transformer beim Wechsel Dev/Turbo wirklich freigeben (`gc.collect()`; vorher 78,9 GB
  zugesagt, danach 36,4 GB stabil); Bedarf 19.500 MiB / 36 GiB RAM gemessen; Platzreserve für den im Leerlauf fast leeren
  Dienst; Zusammenführen nur mit Bild-Ebenen (Fibo malte ein Rechteck weg); „Beschreibung ändern“ nur für echte
  VGL-Beschreibungen; Freistellen ohne Fibo möglich.
- **Abnahme 22.10.2026:** alle Tests grün (Zentrale 153, Werkstatt 214, Fibo 23, Atelier 24). Echt: Start über die Zentrale
  (Kartenwahl Suprim, bereit nach ≈10 s, Reserve sichtbar, Ornith-Plan weicht auf die FE aus); API-Fälle Bild mit DeepSeek,
  direkt, Turbo, Maske, Abbruch; im Atelier Projekt, Text mit Kontur, Verschieben, Export 1280×720 + Quellen-JSON,
  Hintergrund erzeugen, Ebene bearbeiten, Zusammenführen, Objekt erzeugen + Freistellen (BiRefNet, saubere Kante),
  Bereich ändern (Tasse → Saftglas), Beschreibung ändern (gleicher Seed, anderes Licht).
- **Offen/später:** LoRA-Feintuning auf Fibo Dev (Hausstil), Bria-LoRAs „Multi-Turn Local Editing“/„Product Shot“, sobald
  veröffentlicht; Scene Analyzer (`C:\LLM\models\fibo-scene-analyzer-gguf`, geladen, nicht eingebunden) für Ebenen-Zerlegung;
  ein lokaler Beschreiber statt DeepSeek.

## Offen

- **Zwei RTX 3090 seit 14.10.2026** (Stufe 6): Ein-Karten-Einstellung abgelöst, freie Kartenwahl, Strata gemessen. Offen:
  Möglich (nur auf Auftrag): Monitor an die Intel-Grafik, dann könnte die Reserve der FE kleiner werden
  (Saschas Idee, 14.10.2026); IQ3_S als genauere Strata-Fassung (Download ~80 GB). Möglich (nur auf Auftrag): Transkription und Bilder/Videos auf
  getrennten Karten gleichzeitig – erledigt 16.10.2026 (Stufe 7: gemeinsame GPU-Sperre entfernt).

- Starter (entschieden 23.09.2026): bleibt so. Kein Autostart; jeder Starter startet nur seinen Dienst,
  „Werkstatt starten“ die Zentrale nur mit, wenn eine Transkription sie braucht.
- Erledigt 23.09.2026 (Auftrag Sascha): `PARAMETER num_batch 256` steht jetzt im Modelfile von
  `ornith-q5-128k:latest` und `ornith-1.5:35b`. Grund: **Hermes** nutzt Ornith Q5 als Standardmodell über
  Ollamas `/v1`-Schnittstelle (`%LOCALAPPDATA%\hermes\config.yaml`), die `num_batch` nicht mitgeben kann.
  Umgesetzt mit `ollama create <Name> -f` (`FROM <Name>`, bisherige Parameter + num_batch); Gewichte
  unverändert, nichts kopiert; Vorlage und übrige Parameter vorher/nachher verglichen. Neue IDs:
  Q5 `1e57d0e420a0` (vorher `459961ddb2de`), Q4 `2fe00ff8ce7c` (vorher `9f3b89b25219`).
  Zurück: dasselbe ohne die Zeile `num_batch`. Zentrale und Werkstatt geben die Option weiterhin mit.
- Leerer Ordner `C:\Workstation\Projekte\LLM-Starter` kann entfernt werden.
- Starter liegen unter `C:\Workstation`; Desktop-Verknüpfungen nur auf Wunsch.
- Erledigt 23.09.2026: die neun Testordner `Arbeitsmaterial\watch\Werkstatt-Abnahme … [datei-…]` liegen im
  Papierkorb (Auftrag Sascha); Claude angemeldet; DeepSeek direkt angebunden (Stufe 2b).
- **Lizenz Qwen-Image 2.1 und Turbo-LoRA:** entschieden von Sascha am 24.09.2026, Thema abgeschlossen und nicht erneut
  ansprechen.
  - Die Bilder dürfen privat und gewerblich kostenlos genutzt werden, etwa für YouTube.
  - Eine Lizenz braucht es erst, wenn das System weitergegeben wird, etwa zusammen mit einem PC ausgeliefert.
    Heute ist es der eigene PC.
- **Lizenz MiniMax-H3 (Videos):** Befund 06.10.2026: Die MiniMax H3 Community License (Videomodell, ebenso die H3-LoRAs) nimmt die EU, Großbritannien, Südkorea und die USA vom Lizenzgebiet aus; Nutzung des Modells und seiner Ergebnisse dort ist nach dem Wortlaut nicht erlaubt, MiniMax bietet dafür eine eigene Lizenz an. Gefunden bei der Character-Swap-LoRA (Stufe 3q), Wortlaut
  in deren `LICENSE` („Excluded Territories“, Abschnitt „Applicable Territory“). Bisher war nur die Qwen-Lizenz
  entschieden. Entscheidung Sascha 06.10.2026: festhalten, das Studio rechnet Videos weiter; der Vorversuch läuft.
- Optional später: ein eigenes Upscaler-Modell (Hochskalieren geht seit 3f mit Qwen selbst). Nur auf Auftrag.
  Kandidat aus der GitHub-Recherche vom 16.10.2026: SeedVR2 (Kernknoten schon in ComfyUI 0.37, Modelle fehlen).
  Die Recherche steht in `Projekte\Lokale-Wissensextraktion\auswertungen\2026-10-16-github-recherche-2x3090.md`.
- Idee (16.10.2026, auf Saschas „Ja“ festgehalten): **erzeugte Bilder automatisch vorprüfen** mit einem lokalen
  Entscheidungsmodell. Gemeint ist eines, das keinen Text schreibt, sondern Wahrscheinlichkeiten für vorgegebene Antworten
  liefert, etwa „Hände in Ordnung?“, „Schrift lesbar?“, „Gesicht verzerrt?“. Bei niedriger Sicherheit entscheidet Sascha.
  - Offener Kandidat: `Mapika/decider-2b-vision` (4,1 GB, Apache 2.0, Basis Qwen3.5).
  - Braucht eine eigene Python-Umgebung (PyTorch, transformers ≥ 5); passt nicht in die Werkstatt (nur Standardbibliothek).
    Deshalb nur als externer Aufruf wie `pdf_seiten.py`.
  - Ob das kleine Bildmodell solche Fehler zuverlässig erkennt, ist völlig offen.
  - Anlass: Video „Jev Can Now SEE“ (The AI Automators, 15.10.2026). Details in der Kundenbox-Akte, Abschnitt 27
    (`AI-Knowledge-System\Workspace\Handoffs\2026-09-07 Hardwarediskussion Tesla V100 und lokale Kundenbox.md`).
  - Nur auf Auftrag.
- Erledigt 27.09.2026 (Auftrag Sascha, Stufe 3l): SAM3.1, SDPose, INT8-Modell und -Text-Encoder, BiRefNet und der
  Prompt-Enhancer sind geladen und eingebaut. Die ungenutzten Depth Anything 3 (1,34 GB) und Lucida (0,88 GB) liegen
  seit 27.09.2026 auf Saschas Wunsch im Papierkorb (rückholbar). Die BF16-Fassungen von Bildmodell und Text-Encoder
  bleiben für „Nochmal“ älterer Bilder nötig.
- Erledigt 27.09.2026 (Auftrag Sascha „Lösche was wir nicht mehr brauchen“): 171 Testdateien der Stufen 3a–3l aus
  „Werkstatt-Abnahme“ über die Papierkorb-Funktion des Studios entfernt (542 MB, rückholbar; die Befunde stehen hier
  und in STUDIO.md). Behalten (33 Dateien): Ausgangsbilder für Tests und Beispiele (`Bild_00005_`, `_00007_`,
  `_00008_`, `_00009_`, `_00011_`, `_00017_`, `_00025_`, `_00026_`, `_00027_`, `_00077_`, `Vorlage_Logo-Test.png`), die
  abgenommenen Moodboards (`Bild_00062_`–`_00067_`, `_00071_`–`_00074_`, neues Quadrat `_00090_`–`_00092_`) und die
  Testvideos `Video_00001_`–`_00008_` mit ihrem Startbild `Bild_00001_`. Ebenfalls im Papierkorb: meine
  Probe-Uploads in ComfyUIs Eingangsordner (`versuch_*`, `bank_10_0.png`, `klein_praxis.jpg`, `portrait_hell.jpg`).
- Möglicher nächster Schritt (nur auf Auftrag): „Ausformuliert“ in der Großansicht als Prompt übernehmen; der
  Enhancer für Bearbeitungen (`pe_i2i`, 9,47 GB) ist nicht geladen.
- Erledigt 27.09.2026 (Stufe 3m): meine 16 Probe-Videos der Vorversuche (`Studio\_versuche`, 20 MB) und die beiden
  „Nochmal“-Doppel `Video_00016_`, `_00017_` über die Papierkorb-Funktion des Studios entfernt (rückholbar). Behalten
  als Belege: die Abnahmevideos `Video_00009_`–`_00015_` in „Werkstatt-Abnahme“. `Video_00012_` lässt sich nicht mehr
  „nochmal“ rechnen, seine Quelle war eine Probe.
- Mögliche nächste Schritte zu Stufe 3m (nur auf Auftrag): Übergang nach dem Verbinden automatisch messen und bei
  einem Sprung warnen (bräuchte ffmpeg in der Werkstatt); fremde Videos (andere Bildrate) vorher umwandeln;
  Zwischenbilder für „Video aus Bild“; ein Video-Editor mit Zeitleiste wie im Repo ist nicht geplant.
- Erledigt 05.10.2026 (Auftrag Sascha zu den Bewertungen vom 04.10.2026, nacheinander mit Tests): Stufe 3n (Vorbild
  für die Stelle), 3o (Realism-LoRA), 3p (Szenenfolge; Referenzbilder beim Weiterführen geprüft, kein Gewinn), Vergleich
  Head-Swap-LoRA (nicht übernommen). DualPass nicht beauftragt; H3 als Bildmodell, AnyAngle und Body Swap nicht einbauen.
- Erledigt 05.10.2026 (Auftrag Sascha „aufräumen“): 51 Testdateien der Stufen 3n–3p über die Papierkorb-Funktion des
  Studios entfernt (rückholbar): `Verbessert_00001_`–`_00019_`, `Video_00016_`–`_00023_` in „Werkstatt-Abnahme“ und die
  24 Probevideos in `Studio\_versuche\realism` und `…\weiter` (leere Ordner entfernt). Behalten: `Bild_00093_`
  (Ausgangsbild). Die nicht übernommene LoRA `bfs_head_v1.1_qwen_2.1.safetensors` bleibt in `ComfyUI\models\loras`
  liegen (Entscheidung Sascha 05.10.2026). Die Belege der Stufen 3n–3p stehen in den Tabellen oben; die Dateinamen dort meinen die
  gelöschten Dateien (ComfyUI vergibt die Nummern neu).
- Entschieden 05.10.2026 (Sascha): Videos in der Großansicht starten weiter mit Ton (nicht stumm). Wer im Browser
  testet, schließt die Großansicht nach dem Prüfen, sonst läuft der Ton in Schleife weiter.
- Erledigt 09.10.2026 (Stufe 3r): Videos freistellen mit SAM3 + BiRefNet, ohne LTX. Ebenso erledigt: „Ausformuliert als
  Prompt übernehmen“ und die zu niedrige Zeitschätzung beim Bearbeiten.
- Entschieden 09.10.2026 (Sascha): die FLUX.2-Klein-4B-Dateien (16 GB, Stufe 3r) bleiben in `ComfyUI\models` (etwa
  für einen späteren 9B-Test); die Versuchsdateien der Stufe 3r (`Studio\_versuche\…`, Belege in „Werkstatt-Abnahme“)
  bleiben ebenfalls.
- **Zurückgestellt 05.10.2026 (Sascha): Videos freistellen.** Erst Bedarf klären, dann `SAM3_VideoTrack` testen (kein
  Download), erst danach evtl. LTX 2.5 Alpha Gen (etwa 40 GB). Siehe Abschnitt „Bewertet 05.10.2026: LTX 2.5 Alpha Gen“.
- Erledigt 24.09.2026 (Entscheidung Sascha): Feld „Vermeiden“ entfernt; es wirkte bei CFG 1 nicht (Stufe 3h).
- Zeitschätzung beim Bearbeiten zu niedrig, wenn das Format neu ist oder zwei Vorlagen mitlaufen (10 statt 13–20 s,
  18–20 statt 29–55 s; Stufe 3i). Anpassen nur auf Auftrag.
- Erledigt 24.09.2026 (Auftrag Sascha): Viggle-Turbo-LoRA v0.2.1 geladen, verglichen und als Stufe „Turbo“ eingebaut
  (Stufe 3e, Nachtrag).
- Das Projekt „Werkstatt-Abnahme“ bleibt als Test- und Referenzprojekt (Entscheidung 23.09.2026); seine Testdateien
  bis 3l sind aufgeräumt (siehe oben).
