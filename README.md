# KI-Zentrale

Zwei lokale Apps rund um die beiden Grafikkarten: seit 14.10.2026 zwei RTX 3090 mit je 24 GiB, „RTX 3090 FE“
(Steckplatz 02, Karte 0) und „RTX 3090 Suprim“ (Steckplatz 04, Karte 1, Monitor). Im Task-Manager heißen sie
GPU 1 und GPU 2 (GPU 0 ist die Intel-Grafik). Keine Karte ist für bestimmte Modelle reserviert: Was auf eine Karte
passt, startet dort, wo Platz ist, und mehrere Modelle teilen sich eine Karte (Abschnitt „Kartenwahl“).

- **Modellzentrale** (fertig): Wer belegt die Karten? Sprachmodelle starten, laden,
  entladen, wechseln; Bild & Video starten; GPU freigeben.
- **Werkstatt** (fertig): Videos und YouTube-Links mit watch transkribieren, mit wählbaren
  Modellen zusammenfassen, eigenes Studio für Bilder und Videos mit Bibliothek und Projektordnern
  (auch einzelne Stellen verbessern, etwa Hände reparieren), PDFs und Scans mit LightOnOCR lesen
  (Texterkennung), Messungen.
  Siehe [PLAN.md](PLAN.md).

## Modellzentrale bedienen

Start: Doppelklick auf **Modellzentrale starten** in `C:\Workstation`. Das öffnet
ein eigenes Fenster (Edge im App-Modus) und startet vorher bei Bedarf den kleinen
Hintergrunddienst auf `http://127.0.0.1:3894/`. Ein zweiter Doppelklick öffnet
nur ein weiteres Fenster, keinen zweiten Dienst.

- **Belegungsleiste:** ein Kästchen je GiB, eingefärbt nach Belegung. Die Farben
  entsprechen dem Streifen links an jedem Eintrag. „Windows & Programme“ ist der
  Rest bis zur vom Treiber gemessenen Belegung; die Programmnamen stehen im
  Tooltip.
- **Messwerte:** Temperatur, Auslastung, Leistung mit Limit, Lüfter und ein
  Verlauf der letzten 10 Minuten. Die Speichertemperatur liefert der Treiber
  bei GeForce-Karten nicht.
- **Starten/Laden:** Passt ein Modell nicht mehr, zeigt ein Dialog, was dafür
  weichen muss, mit Vorher/Nachher-Leiste. Nichts wird ohne Bestätigung
  beendet. „Ohne Freigabe“ startet trotzdem (kann scheitern oder langsam werden).
- **GPU freigeben:** listet nur, was die Zentrale selbst freigeben darf, jeweils
  abwählbar. Fremde Programme und laufende Transkriptionen werden nur genannt.
- **Bild & Video:** startet ComfyUI (Bilder und Videos entstehen im Studio der Werkstatt; 2Wild ist seit
  24.09.2026 stillgelegt, ein noch laufendes 2Wild beendet „Beenden“ mit). „GPU freigeben“ entlädt
  nur die Modelle aus ComfyUI, der Dienst läuft weiter. Läuft gerade ein
  Auftrag, wird nichts entladen; Beenden verlangt dann eine eigene Bestätigung.
- **Texterkennung:** „LightOnOCR-3 · Texterkennung“ startet einen llama.cpp-Server auf einer RTX 3090
  (Port 8096, etwa 4,4 GiB, bereit nach wenigen Sekunden). Ihn nutzt die Werkstatt im Reiter „Texterkennung“.
  Die Karte wählt die Zentrale (Abschnitt „Kartenwahl“); die Anzeige nennt die gemessene Karte. Für Strata
  (braucht beide Karten) muss er weichen; der Startdialog bietet das an.
- **Ornith über PolyStrata** (seit 18.10.2026): „Ornith 1.5 · PolyStrata“ startet PolyStratas Server
  (`C:\LLM\runtimes\PolyStrata`, Engine `strata-poly`) mit der unveränderten Ollama-Datei Ornith Q4_K_M auf **einer**
  RTX 3090, 128K Kontext, mit Bildern; OpenAI-API auf Port 8097, „Chat öffnen“ wie bei Strata. Gemessen 182 Token/s
  Text, 200–211 Code (auch mit Temperatur), Bild ~1 s, etwa 23 GiB. Die Karte wählt die Zentrale (praktisch die
  Suprim, weil die FE den Monitor trägt) und übergibt sie mit `--gpu`; der Server läuft mit Strata's Python-Umgebung
  (nur gelesen). Die Ollama-Einträge Ornith Q4/Q5 bleiben daneben; nicht beide gleichzeitig laden, wenn der Platz fehlt.

### Kartenwahl (seit 14.10.2026)

- **Eine beliebige Karte** (`karten` + `bedarf_je_karte_mib`): NInfer, LightOnOCR, Ornith über PolyStrata und ComfyUI. Passt es ohne
  Freigabe auf mehrere Karten, nimmt die Zentrale die engste – kleine Modelle teilen sich eine Karte, die andere
  bleibt für große frei. Die Monitorkarte (nvidia-smi `display_attached`) füllt sie nur so weit, dass dort noch
  `monitor_puffer_mib` (2 GiB) für Windows frei bleiben, solange die andere Karte reicht. Passt es nirgends, schlägt
  sie die Karte vor, auf der am wenigsten weichen muss. NInfer startet mit `CUDA_VISIBLE_DEVICES` auf der gewählten
  Karte, LightOnOCR ebenso.
- **Alle Karten zusammen** (`bedarf_gesamt_mib`): Ornith Q5 und Q4. Ollama verteilt selbst; gezählt wird der freie
  Platz beider Karten. Reicht es, ein einzelnes Modell freizugeben, schlägt die Zentrale das kleinste passende vor.
- **Feste Karten** (`bedarf_mib`): Strata braucht beide Karten.
- **Varianten** (`varianten`, seit 14.10.2026): Unter dem Eintrag steht eine Auswahl „Laden mit“ bzw. „Starten mit“,
  solange er aus ist; der Bedarf darunter wechselt mit. Ornith Q4: 256K Kontext (Standard, 26,5 GiB) oder 32K
  (22,5 GiB, gemessen). Strata: 128K mit Bildern (Standard) oder 256K ohne Bilder (Einstellung
  `strata-iq3_xxs-2gpu-256k.json`, geprüft 14.10.2026: 79 % der Experten auf den Karten, 95–106 Token/s) oder
  **Q4** (seit 16.10.2026: Unsloth UD-IQ4_XS, genauer, 128K mit Bildern, `strata-unsloth-ud-iq4_xs-2gpu-128k.json`,
  32 GiB RAM-Rahmen, RAM-Prüfung 40 GiB; braucht die feste Auslagerungsdatei 64 GB, gemessen 89–98 Token/s Text,
  108–116 Code, 2.681 Token/s Einlesen). Die Zeile im Betrieb nennt die laufende Fassung aus Strata selbst
  (Modellname und Kontext laut `/health`). Ornith Q5 bleibt fest bei 128K, weil Hermes es
  ohne Optionen anfragt. Was geladen ist, zeigt die Zeile („Kontext 32.768“) aus dem Programm selbst. Die Werkstatt
  schickt Ollama den Kontext mit, mit dem das Modell geladen ist; ein Programm, das Q4 ohne `num_ctx` anfragt, lädt es
  mit Ollamas Standard (256K) neu (gemessen: 6,3 s).
- **Studio:** wählt je Auftrag (Werkstatt, `karten_waehlen`): ein Bild möglichst ganz auf einer Karte (dort, wo
  ComfyUI seine Modelle schon hält, sonst die engste), sonst geteilt; Videos seit 16.10.2026 ganz auf einer Karte, aber nie auf der
  Monitorkarte (sonst geteilt, das Videomodell nicht auf der Monitorkarte). Mit zwei ComfyUI-Prozessen (Stufe 8) rechnet
  ComfyUI 2 die Videos auf der Suprim und ComfyUI 1 Bilder daneben auf der FE. Abläufe ohne Kartenwahl (Pose, schnelles Freistellen, Stelle per Wort, Zeitlupe, Video
  freistellen, 3D) rechnen auf ComfyUIs Standardkarte 0 (FE).

Der Dienst misst nur, solange ein Fenster offen ist (danach Ruhe nach 90 s).
Er belegt selbst keinen Grafikspeicher.

Meldet die Werkstatt eine Transkription an, erscheint der noch nicht belegte Teil als
„Transkription (angemeldet)“ in der Leiste und zählt beim Starten und Wechseln mit.

## Werkstatt bedienen

Start: Doppelklick auf **Werkstatt starten** in `C:\Workstation` (Dienst auf
`http://127.0.0.1:3895/`, eigenes Fenster).

- **Hinzufügen:** Dateien oder ganze Ordner aus dem Explorer hineinziehen, „Dateien
  wählen …“ oder YouTube-Links bzw. Dateipfade einfügen (einer pro Zeile). Playlists und
  Kanäle werden abgelehnt. Beim Hineinziehen erkennt die Werkstatt die Dateien an ihrer
  Markierung im Explorer; vom Desktop geht das nicht, dann „Dateien wählen …“.
- **Modus:** 0 = nur Transkript, 0b = Transkript plus Originalbilder. Sprache automatisch
  (bei YouTube aus dessen Angabe, sonst erkannt), Deutsch oder Englisch.
- **Warteschlange:** ein Auftrag nach dem anderen; wartende lassen sich verschieben,
  umstellen (0/0b) und entfernen. „Anhalten“ lässt den laufenden Auftrag zu Ende laufen.
  Abbrechen beendet sofort alle Whisper-Worker; „Wiederholen“ schreibt dann in einen
  neuen Unterordner `transkript-<Zeit>`.
- **Erledigtes:** Liegt schon ein vollständiges Transkript (bei 0b auch die Bilder) vor,
  wird der Auftrag übersprungen; fehlen nur die Bilder, werden nur sie nachgeholt.
- **Grafikkarten:** Vor jeder Transkription fragt die Werkstatt die Modellzentrale und
  meldet ihren Bedarf an (2,8 GiB je Worker). Passen beide Karten, bekommt jede einen
  Worker; sonst beide auf eine Karte oder nur ein Worker. Fehlt Platz, wartet der Auftrag
  und nennt, wer belegt. Freigeben geht nur in der Modellzentrale, mit Bestätigung.
- **Ergebnisse** wie bei watch üblich unter `C:\Workstation\Arbeitsmaterial\watch`:
  YouTube in `<Titel> [Video-ID]`, lokale Dateien in `<Dateiname> [datei-<Prüfsumme>]`
  mit Verweis auf das Original (keine Kopie). „Ordner öffnen“ zeigt den Ordner.

### Zusammenfassung

Reiter **Zusammenfassung** (oder „Zusammenfassen“ an einem fertigen Auftrag):

- **Links** alle Transkripte aus `Arbeitsmaterial\watch`, durchsuchbar.
- **Auswerter** anhaken, mehrere zugleich: Codex (Modelle und Denkstufen aus der Codex-App),
  Claude (eigene Anmeldung der Kommandozeile, Abo), DeepSeek direkt (Flash, V4 Pro; Schlüssel wird aus
  DSH Desktop gelesen, `~\.dsh\.credentials.yaml`; Denkstufe ohne Nachdenken/niedrig/hoch/maximal),
  OpenRouter nur mit kostenlosen Modellen (Schlüssel in `00_Secrets\OpenRouter`; bei Überlastung bis zu
  drei neue Versuche, ebenso bei DeepSeek) oder lokal (NInfer-Qwen, Ornith Q5/Q4, sofern in der
  Modellzentrale geladen). „Auswerter verwalten …“ legt neue an (Anbieter, Modell, Denkstufe).
  Nicht nutzbare Auswerter sind ausgegraut und nennen den Grund (nicht angemeldet, kein
  Guthaben, nicht geladen). Cloud-Auswerter sind als „Cloud“ markiert: Das Transkript geht dorthin.
- **Anweisungen** anhaken, ebenfalls mehrere: Kurzzusammenfassung, Ausführliche Analyse,
  Gezielte Frage (mit Fragefeld) oder eigene. „Ansehen“ öffnet den Text zum Ändern,
  „Als neue Anweisung speichern“ legt eine Variante an. Gespeichert wird in der
  Promptsammlung `C:\Users\sasch\Desktop\Meine-Wissens-Prompts.md`, Abschnitt
  „Werkstatt: Anweisungen für Zusammenfassungen“; dort lässt sich auch direkt ändern.
  Der „Rahmen“ wird jeder Anweisung vorangestellt.
- **Auswerten** erzeugt je Auswerter × Anweisung eine Fassung. Die Fassungen stehen
  nebeneinander zum Vergleich, mit Dauer, Token und (bei DeepSeek/OpenRouter) Kosten. DeepSeek-Kosten
  rechnet die Werkstatt aus der Preisliste in `werkstatt\config.json` (außerhalb der Hauptzeit halber
  Preis); Codex und Claude laufen im Abo und zeigen keine Einzelkosten.
- **Dateien:** `<Videoordner>\zusammenfassungen\<Anweisung> – <Auswerter>.md`, mit Kopf
  (Quelle, Modell, Anweisungsstand, Dauer, „Entwurf, nicht geprüft“).
- Lokale Modelle rechnen seit 16.10.2026 auch neben Whisper, Bildern und Texterkennung (keine gemeinsame
  GPU-Sperre mehr); das Modell ist schon geladen und braucht keinen neuen Platz.
  Cloud-Fassungen laufen zu zweit parallel.

### Bild & Video

ComfyUI starten und beenden geschieht in der Modellzentrale, die vorher den Platz prüft; ist es aus,
zeigt das Studio einen Hinweis und „Erstellen“ bleibt gesperrt. 2Wild ist stillgelegt und nicht mehr eingebettet.

**Studio** (Bilder mit Qwen-Image 2.1, Videos mit MiniMax-H3, lokal). Arten, LoRAs, Rezepte, Prompt-Tipps, was nicht
geht, Dauer und die Schnittstelle stehen ausführlich in **[STUDIO.md](STUDIO.md)**. Agenten nutzen den gemeinsamen Skill
`bild-video-studio` (`C:\Workstation\Skills\aktiv\bild-video-studio`). Hier nur die Bedienung:

- **Erstellen** (links): Projekt wählen oder „Neu …“, Art wählen (Bild: Neu, Bearbeiten, Verbessern, Freistellen,
  Pose; Video: Aus Text, Aus Bild, Mit Referenz, Weiterführen), beschreiben, Format bzw. Größe, Qualität, Variationsnummer (zufällig oder
  fest; gleiche Nummer + gleiche Einstellungen = dasselbe Ergebnis), Anzahl 1–4. „Vorschlag“ bzw. „Vorschlag
  einsetzen …“ füllt geprüfte Rezepte ein und markiert, was man anpassen soll. Strg+Enter startet.
  - Bearbeiten: bis zu 10 Vorlagen aus der Bibliothek („Als Vorlage“, ohne Kopie) oder „Aus Datei …“; die erste
    bestimmt Seitenverhältnis und Ausschnitt, „↑“ holt eine andere nach vorn. „Größe“: wie Vorlage 1, 2 MP oder 4 MP
    (hochskalieren) oder ein Format. Häkchen „Details auffrischen“ nur für schwache Fotos.
  - Neu: Häkchen „Durchsichtiger Hintergrund“ für ein Motiv ohne Hintergrund (PNG, nur das Motiv beschreiben);
    Häkchen „Wunsch ausformulieren lassen“: ein lokales Sprachmodell schreibt aus einem kurzen Wunsch die ausführliche
    Beschreibung (15–34 s statt 7 s; „ohne Schrift“ dazuschreiben, wenn keine gewünscht ist). Formate bis Banner 3:1
    und Panorama 4:1.
  - Neue Bildaufträge rechnen mit den INT8-Fassungen von Qwen und der schnelleren Aufmerksamkeit, etwa doppelt so
    schnell bei gleicher Qualität (Turbo-Bild 1328² ~7 s); „Nochmal“ älterer Bilder bleibt wie damals.
  - Ein Feld „Vermeiden“ gibt es nicht mehr (es wirkte bei CFG 1 nicht); Ausschlüsse in die Beschreibung schreiben.
- **Verbessern:** Bild wählen (Großansicht „Stelle verbessern …“ oder „Aus Datei …“), die Stelle im eigenen Fenster
  markieren (Pinsel/Radierer B/E, Größe [ ], Mausrad zoomt, rechte Maustaste oder Leertaste verschiebt, Strg+Z/Y,
  Alles löschen, Umkehren, Einpassen 0), beschreiben, was dort sein soll, „Wie viel darf sich ändern“ wählen.
  Statt zu markieren geht auch „Oder Stelle per Wort finden“ mit einem englischen Wort („hand“, zwei Hände „hand:2“).
  Freiwillig ein **Vorbild für die Stelle** (Porträt, Logo, Produktfoto; „Aus Datei …“ oder in der Großansicht „Für
  die Stelle“), im Text „Bild 2“; Vorschläge „Kopf/Logo/Gegenstand nach Vorbild“ (seit 05.10.2026, STUDIO.md).
  Ergebnis ist eine neue Datei `Verbessert_…png`; das Original bleibt unverändert.
- **Videos mit Personen:** Häkchen „Realistische Personen“ (Realism-LoRA, seit 05.10.2026) für natürlichere Haut und
  Gesichter; bei Räumen ohne Personen weglassen.
- **Szenenfolge** (Video, seit 05.10.2026): oben den gemeinsamen Teil (Figuren, Ort, Licht, Stil), darunter die Szenen mit
  Länge; „Szenenfolge starten“. Nach jeder Szene oben in der Bibliothek „Passt“ oder „Nochmal“ (oder Häkchen „Nach
  jeder Szene prüfen“ weg, dann läuft alles durch). Heraus kommt ein Video mit allen Szenen. „Realistische Personen“
  gibt es dort je Szene (seit 09.10.2026).
- **Person tauschen** (seit 09.10.2026): „Video mit Referenz“, Clip = das Video, Bild 1 = die neue Person, Vorschlag
  „Person tauschen“, im Text nur ändern, wer ersetzt wird (englisch). Etwa 7–8 min je 5 s.
- **Zeitlupe und Video freistellen** (seit 09.10.2026): in der Großansicht eines Videos „Zeitlupe 1,5×/2×“ (ohne Ton, in
  Sekunden) bzw. „Person freistellen“ (WebM mit durchsichtigem Hintergrund, ohne Ton, etwa 1 min je 5 s).
- **Seit 11.10.2026:** „Turbo“ bei Bildern rechnet mit dem offiziellen Qwen-Turbo-Modell; „Schnell“ bei Videos aus Text
  oder Bild mit DMAD (natürlichste Haut, halbe Zeit von „Schnell beste“) – für Personen die erste Wahl.
- **3D-Modell** (seit 11.10.2026): Art-Gruppe „3D“ – aus einem Drehblatt (beim Bearbeiten Vorschlag „Drehblatt (Figur)“
  oder „(Gegenstand)“, zwei Variationen rechnen, Rückansicht prüfen) oder aus einem Bild (Großansicht „3D-Modell“) rechnet
  Pixal3D ein texturiertes 3D-Modell. In der Bibliothek erscheint ein Drehteller-Video, die GLB liegt daneben („GLB
  speichern …“, „Im Ordner zeigen“, „In ComfyUI ansehen“). Detailstufe „fein“ oder „leicht“ (fürs Web). Einige Minuten
  je Modell; Einzelheiten und Grenzen in STUDIO.md, „3D-Modell im Detail“.
- **Querformat 4:3** (1472 × 1104) bei den Bildformaten; „Ausformuliert übernehmen …“ in der Großansicht setzt den
  ausformulierten Text als Prompt ein. Die Zeitschätzung lernt aus den eigenen Aufträgen (seit 09.10.2026).
- **Freistellen:** Bild wählen (Großansicht „Freistellen“ oder „Aus Datei …“), unter „Was soll bleiben?“ nichts
  (Hauptmotiv, schnell in etwa 1 s) oder etwa „den Hund“ eintragen (Qwen, 15–30 s). Ergebnis `Freigestellt_…png` mit
  Transparenz.
- **Pose:** aus einem Bild mit der gewünschten Haltung ein Pose-Skelett machen (Art „Pose“ oder Großansicht
  „Pose-Skelett“, 1–2 s; alle Personen im Bild, dicht überlappende nur einmal). In dessen Großansicht „Als
  Pose-Vorlage“: Bearbeiten mit dem Vorschlag „Pose übernehmen“, die Person als Bild 2 dazu.
- **Video weiterführen:** in der Großansicht eines Videos „Verlängern …“, „Davor setzen …“, „Schleife schließen …“
  oder „Verbinden …“ (dann beim zweiten Video „Als Clip danach“); oder Art „Weiterführen“ mit „Wie weiterführen?“.
  Clips nur aus der Bibliothek. Beschreiben, was im neuen Stück geschieht (der Prompt des Clips steht schon da), die
  Länge des neuen Stücks wählen, bei Bedarf das Ende des Clips davor bzw. den Anfang des Clips danach kürzen. Ergebnis
  ist ein neues, ganzes Video `Video_…mp4`; die Clips bleiben unverändert.
- **Bibliothek** (rechts): alle Bilder und Videos, neueste zuerst; Suche in Prompts, Filter nach Projekt und
  Bild/Video. Laufende und wartende Aufträge stehen als Kacheln vorn, mit Fortschritt und „Abbrechen“; fehlgeschlagene
  mit „Wiederholen“. Ältere Dateien ohne `.json` werden aus ihren Metadaten erschlossen.
- **Großansicht** (Kachel anklicken, ← → blättern): alle Einstellungen, „Nochmal“ (gleiche Nummer), „Variation“ (neue
  Nummer), „Mit Änderungen …“ (füllt das Formular), „Prompt kopieren“, „Verschieben“, „Im Ordner zeigen“, „In den
  Papierkorb …“.
  - „Bearbeiten:“ „Stelle verbessern …“, „Freistellen“, „Hochskalieren“ (nächste Stufe, die größer ist als das Bild),
    „Pose-Skelett“, „Als Vorlage“; bei freigestellten und durchsichtig erzeugten Bildern nur „Als Vorlage“, bei einem
    Pose-Skelett nur „Als Pose-Vorlage“. Ausformulierte Bilder zeigen die Beschreibung unter „Ausformuliert“.
  - „Für Video:“ als Startbild („Zu Video“), Endbild oder Referenz; ein Video als Referenz-Clip oder
    „Weiterführen:“ (verlängern, davor setzen, Schleife schließen, verbinden).
  - „Vorher zeigen“ (Taste V) bei verbesserten, freigestellten und „wie Vorlage 1“ bearbeiteten Bildern.
    Durchsichtiges steht auf einem Schachbrett.
- **Auswählen:** mehrere Kacheln wählen, dann verschieben oder in den Papierkorb (rückholbar).
- **Ablage:** ComfyUI speichert direkt in `C:\Workstation\Arbeitsmaterial\Studio\<Projekt>\` (Startoption der
  Zentrale), daneben `<datei>.json` mit Prompt und allen Einstellungen. Keine Kopien. Was früher 2Wild erzeugt hat,
  liegt in `Studio\gencenter` („Aus 2Wild“).
- **Grafikkarten:** Ein Auftrag fragt die Zentrale nach Platz und meldet seinen Bedarf an (`schluessel` „bild-video“;
  die Zentrale zieht ab, was ComfyUI seit der Anmeldung belegt). Er rechnet neben Transkription, Texterkennung und
  lokalen Modellen, auch auf derselben Karte, wenn der Speicher reicht (seit 16.10.2026, keine gemeinsame GPU-Sperre);
  fehlt Platz, wartet er und nennt, wer belegt. Ein fremder ComfyUI-Auftrag ohne Anmeldung lässt andere warten.
- **Abbrechen:** ComfyUI hört erst am Ende des laufenden Rechenschritts auf (bei Videos ein Schritt: 5 s ~15 s,
  7 s ~32 s, längere Clips mehr); so lange
  zeigt die Kachel „Wird abgebrochen …“ und die Grafikkarten bleiben für andere gesperrt – ohne Frist, bis ComfyUI
  wirklich steht (seit 27.09.2026; vorher gab die Werkstatt nach 90 s auf). Antwortet ComfyUI eine Weile nicht, wartet
  ein Auftrag weiter, statt ihn für beendet zu halten; verloren ist er erst, wenn ComfyUI nachweislich beendet wurde.
- **Lizenz** (entschieden von Sascha, 24.09.2026): Die Bilder aus Qwen-Image 2.1 und der Turbo-LoRA dürfen privat und
  gewerblich genutzt werden, etwa für YouTube. Eine Lizenz wäre erst nötig, wenn das System weitergegeben wird, etwa
  zusammen mit einem PC ausgeliefert.

### Texterkennung

„PDF/Scan lesen“: PDFs, Scans und Bildschirmfotos (PDF, PNG, JPG) werden lokal mit LightOnOCR-3 als Markdown
gelesen, mit Überschriften und Tabellen (als HTML-Tabellen).

- **Voraussetzung:** LightOnOCR in der Modellzentrale starten. Die Werkstatt startet oder beendet es nie; läuft es
  nicht, steht oben ein Hinweis mit „Modellzentrale öffnen“, und ein Auftrag scheitert mit klarer Meldung.
- **Hinzufügen:** wie bei der Transkription hineinziehen (im Reiter Texterkennung), „Dateien wählen …“ oder Pfade
  einfügen; Ordner werden nach PDFs und Bildern durchsucht. „Seiten“ leer = alle, sonst etwa `1-5, 8`.
- **Ablauf:** ein Auftrag nach dem anderen. Die Seitenbilder rendert das vorhandene PDF-Werkzeug
  (PyMuPDF in `Werkzeuge\PDF\venv`, längste Kante 2.048 px); sie werden nicht gespeichert. Gerechnet wird, sobald
  die Zentrale über `/api/platz` keinen Grund zum Warten meldet – seit 16.10.2026 auch neben Whisper, lokalen
  Zusammenfassungen und Studio-Aufträgen (ein laufender ComfyUI-Auftrag ist kein Grund). Etwa 6–9 s je Seite.
- **Ergebnis** in `C:\Workstation\Arbeitsmaterial\Texterkennung\<Dateiname>\`: `Seite 001.md` … je Seite,
  `Volltext.md` mit Kopf (Quelle, Seiten, SHA-256, Modell, Status „nicht geprüft“) und `lauf.json` (Einstellungen,
  Zeit und Zeichen je Seite). Die Quelle bleibt unverändert. Abbrechen oder ein Fehler behält die fertigen Seiten;
  „Fortsetzen“ macht danach weiter.
- **Grenzen:** sehr genau, aber gelegentlich **Fehlwörter, die echt aussehen** („Sehnenvorlauf“ statt
  „Sehnenverlauf“) – für Wissensquellen Stichproben gegen das Original. Abbildungen erscheinen nur als Platzhalter
  `![image](image_1.png)` ohne Bilddatei. Bei Bildschirmfotos fehlen Randbereiche (Browserleiste) oft.

Agenten (Claude, Codex, Hermes) nutzen den gemeinsamen Skill **`texterkennung`**
(`C:\Workstation\Skills\aktiv\texterkennung`, `scripts\ocr.py lesen <pfad> [--seiten …]`): startet bei Bedarf
LightOnOCR über die Zentrale – nur, wenn dafür nichts weichen muss – und beendet ein selbst gestartetes Modell danach
wieder. Schnittstelle (nur `127.0.0.1:3895`, Kopfzeile `X-Werkstatt: 1` bei POST): `GET /api/texterkennung`
(Aufträge, `modell.bereit`), `POST /api/texterkennung` mit `aktion` `hinzufuegen` (`text` = Pfade, eine je Zeile,
`seiten`; Antwort mit `auftraege` = IDs der neuen bzw. schon offenen Aufträge), `abbrechen`/`wiederholen`/
`entfernen`/`ordner`/`volltext` (`id`) oder `aufraeumen`.

### Messungen

Alles entsteht automatisch aus echten Läufen:

- **LLM-Messlauf** per Knopf für ein in der Zentrale geladenes lokales Modell: fester Text
  (`werkstatt\messtext.txt`), Aufwärmen, 256 Token Antwort; Prefill, Decode, erste Antwort und
  Spitzenwerte je Karte. Seit 16.10.2026 ohne GPU-Sperre: für saubere Werte nichts anderes daneben rechnen lassen.
- **Transkription:** Tempo je Aufbau aus allen `run.json` (Median; Läufe mit sehr wenig Sprache
  zählen nicht) und die letzten Läufe.
- **Zusammenfassung:** Dauer, Token/s und Kosten je Auswerter.
- **Bild & Video:** Rechenzeiten der Studio-Aufträge (je Art, Größe, Schritte), Auftragsdauern aus
  2Wild (`data\jobs.json`, ohne Prompts) und sonstige ComfyUI-Läufe.
- **Historisch:** die 141 Läufe aus GPU-Lab (einmalig übernommen, GPU-Lab ist stillgelegt).

Ablage ins Wissen, Auswertung mit Bildern und OCR bleiben bei den Agenten (Skill `watch`).

## Verwaltete Einträge

| Eintrag | Art | Belegung (gemessen 23.09.2026 mit RTX 3090 + 3080; seit 14.10.2026 zwei RTX 3090) |
|---|---|---|
| Qwen3.8 27B · NInfer, 128K | eigener Server, Port 8080, eine RTX 3090 | 21,8 GiB (14.10.2026: auf der FE, 22.286 MiB) |
| Ornith 1.5 Q5, 128K | Ollama `ornith-q5-128k:latest`, verteilt | 14.10.2026: 14.633 (FE) + 12.787 MiB (Suprim) |
| Ornith 1.5 Q6, 256K | Ollama `ornith-q6-256k:latest` (Q6_K, num_ctx und num_batch 256 im Modelfile), beide Karten | 19.10.2026: 18.742 (FE, inkl. ~1,1 GiB Windows) + 15.644 MiB (Suprim), 31,2 GiB ganz im Grafikspeicher, bereit nach 9 s, 121 Token/s; Bedarf 33.500 MiB |
| Ornith 1.5 Q4 | Ollama `ornith-1.5:35b`, verteilt | 14.10.2026: 14.051 + 12.411 MiB bei 256K Kontext (Ollama wählt ihn nach dem Grafikspeicher; mit 3090 + 3080 waren es 32K, 13,0 + 9,4 GiB) |
| Qwen3.8 Flash-Next · Strata, IQ3_XXS, 128K, Bilder | eigener Server, Port 8095, beide Karten | Strata 0.1.45 (seit 18.10.2026; Monitor an der FE: 106–116 Token/s Text, 142–158 Code, 70K 3.863 Token/s). Strata 0.1.44.1 (14.10.2026): 23.382 (FE) + 22.324 MiB (Suprim, 1 GiB Luft für Windows), 84 % der Experten auf den Karten, 112–113 Token/s Text, 145–162 Code, Prompt 3.675 Token/s; Bedarf 23.400 + 22.000 MiB (vorher mit 3080: 23.359 + 19.299 MiB) |
| Ornith 1.5 · PolyStrata (Q4_K_M aus Ollama, 128K, Bilder) | PolyStrata 0.1.45-poly.1 (`strata-poly`), Port 8097, eine RTX 3090 | 18.10.2026: 23.329 MiB auf der Suprim, alle Experten auf der Karte, 182 Token/s Text, 200–211 Code, 70K-Prompt 2.393 Token/s; Bedarf 23.000 MiB, RAM-Prüfung 24 GiB |
| LightOnOCR-3 · Texterkennung (4B, Q4_K_M, Bilder) | llama.cpp b10754, Port 8096, eine RTX 3090 | 4.311–4.535 MiB, gemessen 11.10.2026 (14.10.2026: 4.350 MiB auf der Suprim); Bedarf 4.700 MiB |
| ComfyUI (Bild & Video; 2Wild stillgelegt) | Port 8188, Ausgabe nach `Arbeitsmaterial\Studio` | im Leerlauf 0,4 GiB, nach einem Qwen-Bild 14,5 GiB |
| DSH Desktop | Programm | keine nennenswerte |

Pfade, Startoptionen und Bedarfswerte stehen in `zentrale\config.json`. Andere
Modelle (D:\LLM-lokal, weitere Ollama-Tags) werden nicht gesucht und nicht
angeboten; ein fremd geladenes Ollama-Modell erscheint aber in der Belegung und
lässt sich über „GPU freigeben“ entladen.

## Sicherheitsgrenzen

- Alles nur an `127.0.0.1`. Fremde Host-Namen werden abgewiesen, eingreifende
  Aufrufe brauchen die Kennung der eigenen Oberfläche; fremde Webseiten können
  die Zentrale nicht steuern.
- Beendet wird nur, was eindeutig passt: NInfer über Programmpfad **und**
  `--port 8080` in der Kommandozeile; ComfyUI (und ein noch laufendes, stillgelegtes 2Wild) über Port,
  Skript und Python aus dem ComfyUI-Ordner. Ollama-Modelle werden über Ollama entladen,
  der Ollama-Dienst bleibt.
- Strata wird nur über den bestätigten Programmpfad von `strata.exe` bzw. `strata-vision.exe`
  oder Python mit dem bestätigten Skriptpfad und `--port 8095` beendet. Vor dem Start
  prüft die Zentrale, ob mindestens 42 GiB physischer Arbeitsspeicher frei sind.
  Die Belegung des Bildprozesses zählt zu Strata; beendet wird zuerst die Engine, dann der Bildprozess, dann Python.
- LightOnOCR (Art `llamacpp`) wird nur erkannt und beendet, wenn Programmpfad (`llama-server.exe` aus
  `C:\LLM\runtimes\llama-b10754-cuda`), `--port 8096` und die eingetragene Modelldatei in der Kommandozeile passen.
  Ein anderer llama-server (anderer Port, anderes Modell) bleibt unberührt und zählt zu „Windows & Programme“.
- Programme wie DSH Desktop lassen sich mit „Beenden“ nach einem Hinweis auf verlorene Aufgaben und Eingaben
  schließen. Nur Prozesse mit exakt passendem Programmpfad werden angefasst: zuerst alle Top-Level-Fenster
  (auch unsichtbare) sanft schließen, bis zu 8 s warten, dann verbliebene Prozesse nach erneuter Pfadprüfung
  hart beenden. Nach weiteren höchstens 5 s wird geprüft, ob alle passenden Prozesse beendet sind.
- Keine Downloads, keine Modellkopien, kein Autostart, keine Firewall- oder
  Systemänderungen. Das Protokoll `logs\zentrale.log` enthält nur Aktionen,
  PIDs, Ports und Zeiten, keine Prompts.

## Technik

Python 3.12 nur mit Standardbibliothek (vorhandenes uv-Python unter
`%APPDATA%\uv\python\cpython-3.12.14-…`, dasselbe wie unter `watch`), Oberfläche
als HTML/CSS/JS ohne externe Bibliotheken. Nichts wurde installiert.

```
KI-Zentrale\
  gemeinsam\winapi.py     Prozesse, Ports, VRAM je Programm, Kartenzuordnung,
                          Prozessgruppen, Prozess-Handles (bestätigtes Ende), Dateidialog (ctypes)
  gemeinsam\gpu.py        nvidia-smi
  gemeinsam\dienst.py     HTTP-Grundgerüst mit den Sicherheitsprüfungen
  gemeinsam\starter.py    Dienst bei Bedarf starten + Edge-App-Fenster
  zentrale\erfassung.py   echter Zustand aller Einträge und der Belegung
  zentrale\planung.py     wer weichen muss, Anmeldungen (reine Logik, getestet)
  zentrale\aktionen.py    starten, beenden, laden, entladen, öffnen
  zentrale\server.py      Dienst und Schnittstelle
  zentrale\start.py       Starter
  zentrale\web\           Oberfläche
  werkstatt\platz.py      Kartenwahl (getestet) und Nachfrage bei der Zentrale
  werkstatt\watch_lauf.py YouTube-IDs, Vorhandenes erkennen, Fortschritt aus watch-Dateien
  werkstatt\quellen.py    Links, Pfade, Explorer-Markierung, Ordner ausklappen
  werkstatt\auftraege.py  Warteschlange und Ablauf je Auftrag
  werkstatt\auswertung.py Auswerter (Codex, Claude, DeepSeek, OpenRouter, lokal) und Fassungen
  werkstatt\anweisungen.py Anweisungen im Werkstatt-Abschnitt der Promptsammlung
  werkstatt\studio.py     Studio: Abläufe für ComfyUI (Qwen-Image, MiniMax-H3, Stelle verbessern, Freistellen, Pose,
                          Stelle per Wort, Ausformulieren, Video weiterführen), Aufträge, Bibliothek, Metadaten,
                          Markierungen (Lauflängen, Ausschnitt, Graustufen-PNG, PNG-Leser), MP4-Leser
  werkstatt\ausformulieren_t2i.txt  Systemtext des Prompt-Enhancers (aus der ComfyUI-Vorlage)
  werkstatt\messungen.py  Messwerte aus echten Läufen, LLM-Messlauf, GPU-Lab-Übernahme
  werkstatt\texterkennung.py Texterkennung: Aufträge, Seitenwahl, Anfragen an LightOnOCR, Markdown-Ablage
  werkstatt\pdf_seiten.py Seitenbilder; läuft als externer Aufruf im Python des PDF-Werkzeugs (PyMuPDF), nicht in
                          der Werkstatt selbst
  werkstatt\messtext.txt  fester Text für den LLM-Messlauf
  werkstatt\server.py     Dienst und Schnittstelle
  werkstatt\start.py      Starter
  werkstatt\web\          Oberfläche
  werkstatt\daten\        Warteschlange, Fassungen, Auswerter, Studio- und Texterkennungs-Aufträge (JSON)
  logs\                   Protokolle (ohne Inhalte, nur Aufträge, Schritte, Zeiten)
```

Schnittstelle der Zentrale für andere Apps (nur 127.0.0.1, Kopfzeile `X-Zentrale: 1`):
`POST /api/platz` liefert je Karte den freien Speicher (nach Reserve und Anmeldungen),
Auslastung und Belegung; mit `bedarf_mib` und `reservieren` wird geprüft und angemeldet
(sonst 409 mit Begründung). `POST /api/platz/halten` verlängert, `/api/platz/freigeben` löst.

Tests im Ordner `KI-Zentrale`: `python -m unittest discover -s zentrale\tests` und
`python -m unittest discover -s werkstatt\tests`.
