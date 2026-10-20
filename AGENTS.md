# KI-Zentrale – Arbeitsregeln für Agenten

Lokale Apps für Saschas zwei Grafikkarten: seit 14.10.2026 zwei RTX 3090 mit je 24 GiB – „RTX 3090 FE“ = Karte 0
(gpu:0, Steckplatz 02; Monitor 16.–20.10.2026) und „RTX 3090 Suprim“ = Karte 1 (gpu:1, Steckplatz 04; seit 20.10.2026
wieder mit Monitor, vorher bis 16.10.2026); die RTX 3080 ist ausgebaut.
Keine Karte ist für bestimmte Modelle reserviert; Zentrale und Studio wählen nach freiem Platz (README.md, „Kartenwahl“).
Bedienung und Aufbau: [README.md](README.md). Entscheidungen, Stufen, Abnahme: [PLAN.md](PLAN.md).
Studio (Bild & Video) im Detail – Arten, LoRAs, Rezepte, Prompt-Regeln, Grenzen, Schnittstelle: [STUDIO.md](STUDIO.md).
Agenten erzeugen Bilder und Videos über den gemeinsamen Skill `bild-video-studio` (`C:\Workstation\Skills\aktiv\bild-video-studio`).

- **Modellzentrale** (`zentrale\`, Port 3894): fertig und abgenommen am 23.09.2026. Seit 05.10.2026 mit Eintrag
  „Qwen3.8 Flash-Next · Strata“ (Art `strata`, Port 8095, IQ3_XXS 128K auf beiden Karten, RAM-Prüfung 42 GiB;
  [SPEC-strata.md](SPEC-strata.md), Abnahme in PLAN.md). Seit 18.10.2026 startet Strata mit `--fit-max-tokens`
  (`fit_max_tokens` im Eintrag): zu große `max_tokens` werden auf den Restplatz gekürzt statt mit 400 abgelehnt (DSH).
- **Werkstatt** (`werkstatt\`, Port 3895): fertig und abgenommen am 23.09.2026 – Transkription,
  Zusammenfassung, Studio (Bilder, Videos, Bibliothek), Messungen. Claude ist angemeldet, DeepSeek direkt
  angebunden (Schlüssel wird aus DSH Desktop gelesen), OpenRouter nur für kostenlose Modelle. Ornith hat
  `num_batch 256` jetzt auch im Ollama-Modelfile (Hermes nutzt Ornith).
- **Studio** (Stufe 3a Bilder + 3b Videos, abgenommen 23.09.2026; 3d Stellen verbessern, abgenommen 24.09.2026):
  Qwen-Image und MiniMax-H3 über ComfyUI, Ablage in `C:\Workstation\Arbeitsmaterial\Studio\<Projekt>\` mit
  `<datei>.json` daneben, Bibliothek im Reiter Bild & Video. „Verbessern“ rechnet nur einen Ausschnitt um eine
  markierte Stelle neu (Qwen 2.1, nur Kernknoten) und setzt ihn weich ins Original; Flux2 Klein war nicht nötig.
  3e (24.09.2026): Größe beim Bearbeiten (`groesse_von`, Charakterblatt), Bilder bis 4 MP. Der Studio-Shift 3,1 bleibt
  (gleichwertig zum offiziellen Zeitplan); ohne neue Angabe bleibt „Nochmal“ alter Bilder Byte für Byte gleich.
  Stufe „Turbo“ (6 Schritte, `turbo: true`) mit der Viggle-Turbo-LoRA v0.2.1, die am 24.09.2026 auf Auftrag in
  `ComfyUI\models\loras` geladen wurde (SHA-256 geprüft). Nur Kernknoten mit `ManualSigmas`.
  3f (24.09.2026): Freistellen (Qwens Maske auf den Originalpixeln, 1 px Randabzug, Durchsichtiges weiß),
  Hochskalieren beim Bearbeiten (`aufloesung` 1440/2048, ohne Angabe 1024 wie bisher) und Rezepte als Vorschläge.
  „Muster aus Bild 2“ scheiterte (nur das Muster kam heraus) und ist nicht drin; Hex-Farben nur mit Farbnamen.
  3g (24.09.2026): „Details auffrischen“ (`details: true`, nur Bearbeiten) mit Elusarcas Detail-LoRA, die Sascha
  bereitgestellt hat (in `ComfyUI\models\loras`); Rezept „Foto auffrischen“. Die CharSheet-LoRA wurde geprüft und nicht
  übernommen (kopflose Figur, kein Qualitätsgewinn); sie liegt wieder in Saschas „Downloads“.
  3i (24.09.2026): Vorschläge „Figur in neue Szene“ (Porträt als Vorlage, dieselbe Person über mehrere Bilder) und
  „Logo aufbringen“ (Logo-Datei als Vorlage 2, Schriftzug nicht ausschreiben). Befunde und Grenzen in STUDIO.md.
  3j (25.09.2026): Vorschläge „Moodboard hoch/breit/quadratisch“ (englischer Rastertext, abgenommen mit festen Nummern;
  setzen Format und Turbo; Warnung bei unpassendem Format). Styleguide-Boards mit exakter Schrift und Hex-Farben baut
  der Skill `moodboard` hybrid (`scripts\board.py`, HTML + Edge headless).
  3k (26.09.2026): Häkchen „Durchsichtiger Hintergrund“ bei neuen Bildern (`durchsichtig: true`, Rahmen-Prompt plus
  Aufräumen), Formate Banner 3:1 und Panorama 4:1 (bis 4096 px je Seite), „schneller rechnen“ mit INT8-Aufmerksamkeit
  (`schnell: true`, nur neue Bildaufträge; alte Bilder bleiben bei „Nochmal“ gleich). Stil-Vorlage, schnelles
  Hochskalieren und Sampler `seeds_2` geprüft und verworfen.
  3l (27.09.2026): Modelle auf Saschas Auftrag von Comfy-Org geladen (SHA-256 geprüft). Neue Bildaufträge rechnen mit
  den INT8-Fassungen (`int8: true`, etwa doppelt so schnell, gleichwertig; alte Bilder bleiben BF16). Freistellen ohne
  Beschreibung mit BiRefNet (`verfahren: 'schnell'`, ~1 s), „Stelle per Wort“ beim Verbessern (SAM3.1, `stelle`),
  Art „Pose“ (SDPose-Skelett, mit `personen: true` alle Personen über SAM3-Rahmen) mit Vorschlag „Pose übernehmen“,
  Häkchen „Wunsch ausformulieren“ (Qwens
  Prompt-Enhancer, fest auf gpu:0; läuft in ComfyUI als Teil des Bildauftrags, mit Anmeldung und `/api/platz` wie
  jedes Bild – kein Sprachmodell der Zentrale). Depth Anything 3 und Lucida geprüft, nicht genutzt (im Papierkorb).
  Aufgeräumt 27.09.2026: Testdateien in „Werkstatt-Abnahme“ im Papierkorb; behalten sind Ausgangsbilder, abgenommene
  Moodboards und Testvideos (PLAN.md, „Offen“).
  3m (27.09.2026): Art „Weiterführen“ (`video_weiter`, `modus` verlaengern/davor/verbinden/schleife) aus Kernknoten:
  vorn hält `MiniMaxH3AddGuide` die letzten 39 Bilder samt Ton des Clips davor, hinten führt ein einzelnes Endbild in
  den Clip danach; `ConcatenateVideo` setzt zusammen (unveränderte Clips bitgleich, Ton exakt an den Bildgrenzen).
  Clips nur aus der Bibliothek, mit Prüfsumme; `mp4_info` prüft sie. Dazu gilt für alle Aufträge: keine Antwort von
  ComfyUI ist kein Stillstand – gewartet wird, bis der Prozess (Handle) bestätigt beendet ist; Abbrechen ohne Frist.
  Anlass: Video „Mini Video Editor Timeline Node for H3“ (ChanonDevs); Plan mit Astra geprüft (PLAN.md, Stufe 3m).
  3n (05.10.2026): „Vorbild für die Stelle“ beim Verbessern – ein Porträt, Logo oder Produktfoto als „Bild 2“ (Rolle
  `vorbild`, höchstens 1, auf 1 MP verkleinert); dann ist der Ausschnitt doppelt statt dreifach so groß wie die
  Markierung (Logo-Schriftzug und Gegenstände sonst unsauber). Ohne Vorbild bleibt Verbessern unverändert.
  3o (05.10.2026): Häkchen „Realistische Personen“ für Videos (`realismus: true`, Realism-LoRA von fal, auf Auftrag
  geladen, SHA-256 geprüft): natürlichere Haut bei Personen; nicht für Räume ohne Personen (dort schlechter).
  Head-Swap-LoRA BFS v1.1 am 05.10.2026 verglichen und nicht übernommen (Gesichter nicht ähnlicher); bei mehreren
  Personen „Kopf nach Vorbild“ statt „Kopf tauschen“.
  3p (05.10.2026): Art „Szenenfolge“ – gemeinsamer Teil + bis 8 Szenen, Szene 1 eigener Clip, jede weitere verlängert
  die freigegebene Szene davor (mit Satz „ohne Schnitt“ gegen harte Sprünge), nach jeder Szene „Passt“/„Nochmal“.
  Referenzbilder beim Weiterführen geprüft: kein Gewinn, nicht eingebaut.
  3q/3r (09.10.2026, Auftrag „alles Festgehaltene einbauen“): Format 4:3; „Realistische Personen“ je Szene; „Ausformuliert
  übernehmen“; Zeitschätzung lernt nach; „Person tauschen“ (Character-Swap-LoRA, mit Turbo); 8-Schritt-LoRA (PDD, Kijai)
  für neue Referenz-Videos mit 8 Schritten, nicht beim Tauschen; Zeitlupe (RIFE) und Video freistellen (SAM3 + BiRefNet,
  WebM mit Alpha). FLUX.2 Klein 4B geladen und verglichen: Gesichter bleiben, Gewinn aber nur klein – nicht eingebaut.
  16-Bilder/s-Trick passt nicht zu H3 (fester 24-fps-Ton). Befunde in PLAN.md, Stufe 3r.
  3s (11.10.2026): Stufe „Turbo“ (Bilder) rechnet neue Aufträge mit dem offiziellen Qwen-Image 2.1 Turbo (`turbo_modell`);
  „Schnell“ (4 Schritte) bei Video aus Text/Bild mit DMAD full critic (`dmad`, lcm, Verschiebung 12/2). Testläufe direkt an
  ComfyUI nur mit Platz-Tor (keine Transkription/kein LLM auf den Karten, Zusatzbedarf anmelden). PLAN.md, Stufe 3s.
  3t (11.10.2026, Auftrag „überrasch mich“): Art „3D-Modell“ (`modell3d`) mit **Pixal3D** (TencentARC, MIT; Comfy-Org-Dateien
  auf Auftrag geladen, SHA-256 geprüft; Kernknoten unseres ComfyUI 0.37.0) aus einem **Drehblatt** (vier Ansichten, Vorschlag
  „Drehblatt (Figur/Gegenstand)“ beim Bearbeiten, Panorama 4:1), aus Einzelansichten oder aus einem Bild (Einzelbild-Modell +
  MoGe). Ergebnis `Modell_…glb` neben einem Drehteller-Vorschauvideo `Modell_…mp4` (gleicher Stamm; Verschieben/Papierkorb
  nehmen die GLB mit). Detailstufen „fein“ (Comfy-Org-Vorlage) und „leicht“ (fürs Web). Skill: `drehblatt`, `modell3d`.
  STUDIO.md „3D-Modell im Detail“, PLAN.md Stufe 3t.
  3u (17.10.2026, Auftrag „go für das was Sinn macht“): neue MiniMax-Videos (Text, Bild, Referenz, Weiterführen,
  Szenenfolge) rechnen mit der schnelleren Aufmerksamkeit (`schnell: true`, Kernknoten `ModelAttentionBackend`, Knoten 29;
  `studio.video.schnelle_aufmerksamkeit`): ein Viertel bis ein Drittel kürzer, gleichwertig (zwei Nummern, Whisper-Abgleich);
  alte Videos bleiben bei „Nochmal“ gleich. Veda/SageAttention-Paket nicht eingebaut. PLAN.md, Stufe 3u.
- **Zwei Studio-Aufträge gleichzeitig** (Stufe 8, 16.10.2026): zwei ComfyUI-Prozesse (8188 beide Karten, 8189 nur Suprim),
  je ein Arbeiter im Studio; Dateien aus Prozess 2 mit `-2`; Anmeldung je Prozess (`bild-video`, `bild-video-2`).
  MiniMax-H3 passt auf eine 3090 (gemessen, nicht langsamer): Videos rechnet Prozess 2 auf der Suprim, Bilder daneben
  Prozess 1 auf der FE (Video + Bild gleichzeitig; nie ein Video allein auf der Monitorkarte).
  Werkstatt-Design seit 16.10.2026 „Bernstein-Kommandozentrale“ (Saschas Wahl; Farben vorher mit ihm abstimmen). PLAN.md, Stufe 8.
- **Eigene Edit-LoRAs** (Stufe 5, 12.10.2026, Auftrag Sascha nach dem Video „QWEN IMAGE 2.1 EDIT LORA TRAINING“):
  AI Toolkit (Ostris, MIT) auf Auftrag in `C:\LLM\runtimes\ai-toolkit` (eigenes venv), Training damals auf der RTX 3080, künftig auf einer freien 3090, nur über
  das Platz-Tor. Erstes LoRA „Garten-OS-Stil“ v1 (20 Paare) geprüft und **nicht übernommen**: Die Anweisung allein trifft
  den Stil schon. Stattdessen Vorschlag „Als Garten-Illustration“ (Skill `garten`). Lehre und nächste Ideen: PLAN.md, Stufe 5.
- **Texterkennung** (Stufe 4, 11.10.2026): Zentrale-Eintrag „LightOnOCR-3 · Texterkennung“ (Art `llamacpp`,
  `llama-server` b10754, Port 8096, eine RTX 3090 (die Zentrale wählt die engste mit
  genug freiem Speicher), ~4,4 GiB; muss für Strata weichen). Werkstatt-Reiter „Texterkennung“
  („PDF/Scan lesen“): Seitenbilder über `werkstatt\pdf_seiten.py` im PDF-venv (PyMuPDF, externer Aufruf), Anfragen nur,
  wenn die Zentrale LightOnOCR gestartet hat, nach `/api/platz` (seit 16.10.2026 auch neben Bildern und Whisper); Ablage
  `Arbeitsmaterial\Texterkennung\<Name>\` (Markdown je Seite, `Volltext.md`, `lauf.json`). Echt aussehende Fehlwörter
  möglich → Stichproben. Agenten lesen über den gemeinsamen Skill `texterkennung` (`scripts\ocr.py lesen`).
  Schnittstelle in README.md, Befunde in PLAN.md, Stufe 4.
- **Ornith über PolyStrata** (18.10.2026, Auftrag Sascha): Zentrale-Eintrag „Ornith 1.5 · PolyStrata“ (Art
  `polystrata`, Port 8097, eine RTX 3090 nach Kartenwahl, `--gpu`), PolyStrata v0.1.45-poly.1 in
  `C:\LLM\runtimes\PolyStrata` (Handaufbau ohne Setup, Engine-Zip SHA-256 geprüft, nutzt Strata's venv nur lesend),
  Ornith Q4_K_M als unveränderte Ollama-Datei, 128K, Bilder. Ollama-Ornith bleibt daneben. Messung und Vergleich mit
  llama.cpp: `Projekte\Lokale-Wissensextraktion\auswertungen\2026-10-18-polystrata.md`. Seit 19.10.2026 mit
  `--fit-max-tokens` wie Strata.
- **Ornith Q6 auf beiden Karten** (19.10.2026, Auftrag Sascha): Eintrag „Ornith 1.5 · Q6“ (`ornith-q6`, Ollama-Fassung
  `ornith-q6-256k:latest` mit num_ctx 262144 und num_batch 256 im Modelfile, Bedarf 33.500 MiB, 31,2 GiB gemessen,
  121 Token/s). DSH Desktop kennt Ornith Q6 (Ollama) und Ornith Q4 (PolyStrata) als Anbieter. Für Agentenarbeit
  (Webseiten bauen) Flash-Next statt Ornith nehmen – Ornith scheiterte über DSH an den Werkzeugen. PLAN.md, 19.10.2026.
- **Zwei RTX 3090, freie Kartenwahl** (Stufe 6, 14.10.2026, Auftrag Sascha): NInfer, LightOnOCR und ComfyUI nehmen die
  engste passende Karte (Monitorkarte nur bis 2 GiB Rest), Ornith verteilt Ollama (Gesamtbedarf), Strata braucht beide.
  Das Studio wählt je Auftrag: Bild ganz auf einer Karte, sonst geteilt; Videos seit Stufe 8 ganz auf einer Karte,
  nie auf der Monitorkarte (sonst geteilt, Videomodell nicht auf der Monitorkarte). Strata-Code v0.2.1.3 mit Engine 0.1.45.3 (Update 20.10.2026, vorher 0.1.45; Engine 0.1.46 gemessen und
  langsamer beim Einlesen, liegt in `engine\.previous`; Engine von Hand aus dem Release-Paket, `UPDATE.bat` bringt bei
  dieser Quellcode-Installation keine neue Engine mehr – PLAN.md, „Strata 0.2.0-beta, dann v0.2.1.3“) mit Reserve für die
  Monitorkarte (seit 20.10.2026 wieder Monitor an der Suprim: `--vram-reserve-mib 700` FE, `--vram-reserve-later-mib 1800`
  Suprim; 16.–20.10. Monitor an der FE: 1800 / 1000): 115–117 Token/s Text, 159–179 Code, Prompt 3.895 Token/s; ohne
  die Reserve lagert Windows aus (16–19 Token/s). Ornith Q4 läuft jetzt
  Kontext wählbar (Varianten): Ornith Q4 256K oder 32K, Strata 128K mit Bildern, 256K oder Q4 mit Bildern (UD-IQ4_XS, genauer, seit 16.10.2026; braucht feste
  Auslagerungsdatei 64 GB); Q5 fest 128K. PLAN.md, Stufe 6.
- **2Wild ist stillgelegt** (Stufe 3c, 24.09.2026): wird nicht mehr gestartet oder eingebettet.
- **Lizenz** (entschieden 24.09.2026, Einschätzung Sascha): Die Bilder aus Qwen-Image 2.1 und der Turbo-LoRA dürfen privat
  und gewerblich genutzt werden (z. B. YouTube); eine Lizenz braucht es erst bei Weitergabe des Systems (z. B. mit einem
  PC ausgeliefert). Thema abgeschlossen, nicht erneut ansprechen. **MiniMax-H3 (Videos):** Befund 06.10.2026: Die MiniMax H3 Community License (Videomodell, ebenso die H3-LoRAs) nimmt die EU, Großbritannien, Südkorea und die USA vom Lizenzgebiet aus; Nutzung des Modells und seiner Ergebnisse dort ist nach dem Wortlaut nicht erlaubt, MiniMax bietet dafür eine eigene Lizenz an. Sascha hat
  den Befund am 06.10.2026 zur Kenntnis genommen; das Studio rechnet Videos weiter (seine Einschätzung). Nicht erneut
  ansprechen, außer es kommt Neues dazu. **Offen:** Cloud (kie.ai) evtl. später. Stand, Befunde und Abnahme in [PLAN.md](PLAN.md), Abschnitt Stufe 3 und „Offen“.

## Feste Grenzen

- Python nur mit Standardbibliothek. Keine neuen Pakete, Umgebungen, Downloads oder Modelle. (`werkstatt\pdf_seiten.py`
  läuft nicht in der Werkstatt, sondern als externer Aufruf im vorhandenen PDF-venv, wie watch in seinem venv.)
- Alles nur an `127.0.0.1`. Keine Firewall-, Autostart- oder Systemänderungen.
- Nur die in `zentrale\config.json` bestätigten Einträge verwalten. Keine Laufwerks- oder Modellsuche.
  `D:\LLM-lokal` bleibt tabu.
- Prozesse nur nach eindeutiger Prüfung beenden (Programmpfad, Port, Kommandozeile). Nie pauschal
  `python.exe`, `node.exe` oder `ollama.exe` beenden. watch-Läufe der Werkstatt nur über ihre
  eigene Prozessgruppe beenden.
- Ollama-Modelle über die Ollama-Schnittstelle entladen. Den Ollama-Dienst nicht beenden.
- Anzeigen immer aus dem echten Zustand ableiten, nie aus gemerkten Klicks.
- Die Werkstatt steuert die Zentrale nicht: Sie fragt über `/api/platz` und meldet an.
  Freigeben und Entladen bleiben in der Zentrale, mit Bestätigung.
- `watch.py` ist ein gemeinsamer Skill (Codex, Hermes, Claude) und bleibt unverändert.
  Die Werkstatt liest den Fortschritt aus seinen Dateien.
- 2Wild Studio ist ein fremdes GitHub-Projekt mit lokalen Änderungen und seit Stufe 3c stillgelegt.
  Nicht umbauen, nicht wieder starten oder einbetten, keine Dateien darin anlegen.
- Logs ohne Prompts, Transkriptinhalte, API-Schlüssel oder persönliche Daten.
- Anweisungen für Zusammenfassungen leben nur in der Promptsammlung (Abschnitt „Werkstatt: …“).
  Die Werkstatt ändert ausschließlich diesen Abschnitt; keine zweite Promptablage anlegen.
- Lokale Sprachmodelle nur nutzen, wenn die Zentrale sie geladen hat; nie selbst laden oder entladen,
  Ollama-Anfragen mit `keep_alive: -1` und den `ollama_optionen` des Eintrags (Ornith: `num_batch 256`,
  sonst lädt Ollama neu und der bekannte CUDA-Absturz kommt zurück), dazu `num_ctx` = Kontext, mit dem das Modell
  laut `/api/ps` geladen ist (Kontextwahl der Zentrale; sonst lädt Ollama mit anderem Kontext neu). Seit 16.10.2026 (Sascha: „Sperre raus“)
  keine gemeinsame GPU-Sperre: Whisper, Studio, Texterkennung, lokale Zusammenfassung und Messlauf rechnen nebeneinander,
  auch auf derselben Karte, wenn der Speicher reicht. Schutz ist allein die Anmeldung bei der Zentrale (`/api/platz`).
- Von 2Wild wird nur `data\jobs.json` gelesen (Prompts alter Dateien, Messungen), nie verändert. GPU-Lab ist stillgelegt.
- Studio: ComfyUI schreibt nur nach `Arbeitsmaterial\Studio` (Startoption der Zentrale). Keine Kopien von
  Bildern anlegen; Vorlagen aus der Bibliothek per `<pfad> [output]`. Begleitdateien (`.json`) bestehender
  Dateien nie überschreiben. Löschen nur in den Papierkorb und nur auf Wunsch. Bild- und Videoaufträge melden
  ihren Speicher vorher an (`/api/platz`, `schluessel` „bild-video“, auch ohne Zusatzbedarf) und halten die Anmeldung bis zum
  Ende; beim Abbrechen
  warten, bis ComfyUI wirklich steht.
- Verbessern: Das Original nie verändern; das Ergebnis ist eine neue Datei. Markierungen gehen als
  `werkstatt_maske_<Prüfsumme>.png` in ComfyUIs Eingangsordner. Bilder von außerhalb des Studios nur zeigen,
  wenn Sascha sie gewählt hat oder ein Studio-Bild bzw. Auftrag auf sie verweist (`vorlage_datei`).
- Keine Anmeldungen, Schlüssel oder Guthaben für Cloud-Anbieter anlegen – das macht Sascha.

## Arbeiten am Code

- **Git** (seit 18.10.2026, Wunsch Sascha): der Ordner ist ein Repository, verbunden mit dem privaten
  `github.com/Awardin/KI-Zentrale` (Zweig `main`). Nicht im Repository (`.gitignore`): `werkstatt\daten` (Aufträge mit
  Prompts), `logs`, Python-Zwischendateien, `.claude`. Keine Schlüssel oder persönlichen Daten einchecken; Commits und
  Pushes nur auf Saschas Auftrag.
- Oberflächentexte auf Deutsch, aus Sicht der Nutzerin bzw. des Nutzers. Zustände nicht aus Technikbegriffen ableiten.
- Tests im Ordner `KI-Zentrale`: `python -m unittest discover -s zentrale\tests` und
  `python -m unittest discover -s werkstatt\tests`
  (Python: `%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`).
- Einen Dienst neu starten: Prozess auf Port 3894 (Zentrale) bzw. 3895 (Werkstatt) beenden, aber nur
  wenn seine Kommandozeile `KI-Zentrale\zentrale\server.py` bzw. `KI-Zentrale\werkstatt\server.py`
  enthält. Danach `zentrale\start.py --ohne-fenster` bzw. `werkstatt\start.py --ohne-fenster`.
  Ein Neustart der Werkstatt bricht einen laufenden Auftrag ab (er lässt sich wiederholen).
- Änderungen am Verhalten am echten System prüfen und in PLAN.md festhalten. Jede Studio-Änderung (Art, Option, Format,
  LoRA, Rezept, geprüfter Befund „geht“/„geht nicht“, Schnittstelle) zusätzlich in STUDIO.md nachtragen und im Skill
  `bild-video-studio` ergänzen, was andere Agenten zum Benutzen brauchen (SKILL.md, `scripts\studio.py`,
  `references\webseiten.md`); bei Moodboards auch im Skill `moodboard`. Das ist der feste letzte Schritt jeder
  Studio-Änderung (Wunsch Sascha, 26.09.2026).
