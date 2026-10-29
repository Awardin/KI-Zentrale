# Studio der Werkstatt – Handbuch für Bilder und Videos

Stand: 11.10.2026 (Stufen 3a–3t; Prompt-Regel „Aussehen von Personen“ vom 08.10.2026). Diese Datei beschreibt alles, was das Studio kann, wie es intern arbeitet und wie
man Arten, LoRAs und Prompts einsetzt – für Sascha und für jeden Agenten, der Bilder oder Videos braucht.

- Agenten nutzen den gemeinsamen Skill **`bild-video-studio`**
  (`C:\Workstation\Skills\aktiv\bild-video-studio\SKILL.md`) mit dem Hilfsskript `scripts\studio.py`.
- Bedienung der übrigen Werkstatt: [README.md](README.md). Entscheidungen, Versuche, Messungen und Abnahmen:
  [PLAN.md](PLAN.md), Stufe 3. Feste Regeln: [AGENTS.md](AGENTS.md).
- **Pflege:** Jede neue Funktion, LoRA, jedes Rezept und jeder geprüfte Befund („geht“ / „geht nicht“) kommt
  hier dazu. Diese Datei ist die maßgebliche Beschreibung des Studios; README fasst nur zusammen.
- **Belege:** Die Dateinamen in den Befunden (etwa `Bearbeitet_00039_`) stammen aus dem Testprojekt
  „Werkstatt-Abnahme“. Am 27.09.2026 wurden die Testdateien auf Saschas Wunsch in den Papierkorb gelegt; behalten sind
  die Ausgangsbilder (`Bild_00005_`, `_00007_`, `_00008_`, `_00009_`, `_00011_`, `_00017_`, `_00025_`, `_00026_`,
  `_00027_`, `_00077_`, `Vorlage_Logo-Test.png`), die abgenommenen Moodboards und die Testvideos (PLAN.md, „Offen“),
  seit Stufe 3m auch die Abnahmevideos `Video_00009_`–`_00015_` (Videos weiterführen). Weil die alten Dateien im
  Papierkorb liegen, vergibt ComfyUI ihre Nummern neu. Die Testdateien der Stufen 3n–3p (`Verbessert_00001_`–`_00019_`,
  `Video_00016_`–`_00023_`) liegen seit 05.10.2026 ebenfalls im Papierkorb; Befunde mit diesen Namen meinen die gelöschten
  Dateien. Neu behalten: `Bild_00093_` (Sitzpouf, Vorbild für Gegenstände). Der Test „Aussehen von Personen“ vom
  08.10.2026 liegt noch vollständig im Projekt (`Bild_00094_`–`_00119_`, `Bearbeitet_00001_`–`_00002_`). Belege der Stufe
  3r (09.10.2026): `Bild_00120_`–`_00121_` (4:3), `Video_00017_` (zwei Personen), `Video_00018_` (Referenz mit
  8-Schritt-LoRA), `Zeitlupe_00001_`, `Freigestellt_00001_.webm`, `Bearbeitet_00003_`–`_00005_` (Qwen 4 MP) sowie die
  Versuche in `Studio\_versuche\tausch`, `…\zeitlupe`, `…\freistellen`, `…\klein`.
- **Einsatz:** in erster Linie Mockups und Entwürfe. Personen mit Gesichtern, Teams, Behandlungsszenen, Praxisräume und
  Inventar sind ohne Einschränkung erlaubt. Bilder, die nach außen gezeigt werden, werden als KI-erzeugt gekennzeichnet;
  intern ist das nicht nötig (Entscheidung Sascha, 24.09.2026).
- **Lizenz Videos (MiniMax-H3):** Die H3-Lizenz nimmt die EU, Großbritannien, Südkorea und die USA vom Lizenzgebiet aus
  (Befund 06.10.2026, PLAN.md „Offen“). Sascha hat das zur Kenntnis genommen; die Videoarten bleiben in Betrieb.

## Inhalt

1. Überblick
2. Starten
3. Arten
4. Qualität und LoRAs
5. Größen und Formate
6. Rezepte (fertige Prompts)
7. Prompts schreiben
8. Was nicht geht (geprüft)
9. Ablage, Begleitdaten, Wiederholbarkeit
10. Schnittstelle für Agenten
11. Dauer und Grafikspeicher
12. Wie es intern arbeitet

## 1. Überblick

| | |
|---|---|
| Oberfläche | Werkstatt http://127.0.0.1:3895, Reiter **Bild & Video** → Studio (links Erstellen, rechts Bibliothek) |
| Rechenwerk | ComfyUI 0.37, Port 8188, gestartet von der Modellzentrale (http://127.0.0.1:3894, Eintrag „ComfyUI“) |
| Ablage | `C:\Workstation\Arbeitsmaterial\Studio\<Projekt>\`, neben jeder Datei `<datei>.json` mit allen Einstellungen |
| Bilder | **Qwen-Image 2.1** mit Text-Encoder Qwen3-VL 8B und VAE (RGBA, vier Kanäle), möglichst ganz auf einer der beiden RTX 3090 (Abschnitt 11, „Karten“). Neue Aufträge rechnen mit den INT8-Fassungen von Bildmodell und Text-Encoder (etwa doppelt so schnell, gleichwertig; Abschnitt 4), ältere bei „Nochmal“ weiter mit BF16 |
| Hilfsmodelle (Stufe 3l) | **BiRefNet** (schnelles Freistellen), **SAM3.1** (Stelle per Wort finden), **SDPose** (Pose-Skelett), **Qwen-Prompt-Enhancer** (Qwen3.5 9B, Wunsch ausformulieren; auf der Karte des Bildmodells) |
| Videos | **MiniMax-H3** (fl2va: Text/Bild → Video, ref2va: Referenzen → Video; INT8) auf der einen RTX 3090 (nicht der Monitorkarte, wenn es geht); Text-Encoder Qwen3-VL 32B (NVFP4), Video- und Audio-VAE auf der anderen. Erzeugt den Ton gleich mit |
| Grafikkarten | Zwei RTX 3090 (seit 14.10.2026): „FE“ = Karte 0, „Suprim“ = Karte 1. Seit Stufe 8 (16.10.2026) zwei ComfyUI-Prozesse: Prozess 1 (Port 8188, beide 3090 – `comfy_karten`; die RTX 3080 als Nebenkarte seit 22.10.2026 sieht er nicht, das Studio wählt für ihn nur Karte 0/1), Prozess 2 (Port 8189, nur die Suprim, Ein-Karten-Aufträge) – zwei Aufträge rechnen gleichzeitig; Dateien aus Prozess 2 heißen `…-2_00001_.png`. Videos rechnen seit 16.10.2026 ganz auf einer Karte (nie auf der Monitorkarte): Prozess 2 nimmt sie auf der Suprim, Bilder gehen daneben an Prozess 1 auf der FE (Video + Bild gleichzeitig, live geprüft); läuft Prozess 2 nicht, rechnet Prozess 1 das Video allein auf der Suprim. **Seit 22.10.2026 Prozess 3** (Port 8190, nur die RTX 3080, `…-3_00001_.png`, PLAN.md Stufe 8b): Bilder ohne „Ausformulieren“ (seit 23.10.2026 auch über 2 MP: 2752×1536, 40 Schritte 133 s statt 110–114 s) und Hilfsabläufe, die auf die 3080 passen, gehen zuerst dorthin (7,6 s statt 6,6 s, Spitze 17,4 GiB) – auch wenn Strata beide 3090 belegt; keine Videos. Passt ein Auftrag gerade nirgends, wartet er in der Schlange auf einen rechnenden Prozess, statt sich an einer belegten Karte festzusetzen. Seit 16.10.2026 keine gemeinsame Sperre: Aufträge rechnen neben Transkription, Texterkennung und lokalen Modellen, wenn der Speicher reicht (Anmeldung `schluessel` „bild-video“, auch ohne Zusatzbedarf). Jeder Auftrag fragt die Zentrale nach Platz (`/api/platz`), wählt seine Karten und wartet sonst; ein geladenes Sprachmodell auf der anderen Karte stört nicht |

Arten: **Bild** neu (auf Wunsch mit durchsichtigem Hintergrund oder ausformuliertem Wunsch) · bearbeiten · Stelle
verbessern (gemalt oder per Wort, auf Wunsch mit Vorbild) · freistellen · Pose-Skelett; **Video** aus Text · aus Bild · mit Referenz ·
weiterführen (verlängern, davor setzen, zwei Clips verbinden, Schleife schließen) · Szenenfolge (mehrere Szenen
hintereinander, Szene für Szene geprüft).

## 2. Starten

- **Sascha:** „Modellzentrale starten“, dort **Bild & Video** starten (die Zentrale prüft den Platz auf den Karten);
  „Werkstatt starten“, Reiter Bild & Video.
- **Agent:** `studio.py start` aus dem Skill. Startet fehlende Dienste (Zentrale und Werkstatt ohne Fenster,
  ComfyUI über die Zentrale), aber nur, wenn dafür nichts entladen werden muss. Sonst meldet es, was belegt ist –
  dann Sascha fragen. Modelle entladen oder die GPU freigeben nur mit Saschas Bestätigung in der Zentrale.
- ComfyUI ist nach etwa 10 s bereit; der erste Auftrag lädt die Modelle (einmalig 20–40 s mehr).
- Ist ComfyUI aus, nimmt das Studio keine Aufträge an („Bild & Video ist aus …“).

## 3. Arten

| Art (`art`) | Wofür | Vorlagen (Rolle) | Größe |
|---|---|---|---|
| Neues Bild (`bild`) | Bild aus Text; mit Häkchen „Durchsichtiger Hintergrund“ ein freigestelltes Motiv (PNG); mit Häkchen „Wunsch ausformulieren lassen“ schreibt ein Sprachmodell aus einem kurzen Wunsch die Beschreibung | – | Format oder eigene Größe (256–4096 px je Seite, höchstens 4,3 MP) |
| Bearbeiten (`bearbeiten`) | Bild ändern, kombinieren, Rezepte; mit einem Pose-Skelett als Bild 1 eine Haltung übernehmen | 1–10 (`vorlage`); Bild 1 ist das Ziel | „Wie Vorlage 1“ (≈1 MP, Seitenverhältnis von Bild 1), 2 MP oder 4 MP (hochskalieren), oder ein Format (neue Fläche) |
| Stelle verbessern (`verbessern`) | eine Stelle neu entstehen lassen (Hand, Gegenstand entfernen); Stelle gemalt oder per Wort gefunden; mit Vorbild eine bestimmte Person, ein Logo oder einen Gegenstand genau an diese Stelle setzen | 1 (`original`) + Markierung oder Wort (`stelle`); freiwillig 1 Vorbild (`vorbild`, im Text „Bild 2“) | wie das Original; neu gerechnet wird nur ein Ausschnitt |
| Freistellen (`freistellen`) | Motiv behalten, Rest durchsichtig; ohne Beschreibung schnell (BiRefNet, etwa 1 s), mit Beschreibung Qwen | 1 (`original`) | wie das Original (PNG mit Alphakanal) |
| Pose-Skelett (`pose`) | Strichfigur der Haltung aller Personen, als Bild 1 für „Pose übernehmen“ | 1 (`original`) | wie das Original |
| Video aus Text (`video_text`) | Clip aus Beschreibung | – | Videoformat, 5–15 s |
| Video aus Bild (`video_bild`) | Clip, der mit einem Bild beginnt (optional endet) | `start` (Pflicht), `ende` | Videoformat; das Startbild wird mittig zugeschnitten, nicht verzerrt |
| Video mit Referenz (`video_referenz`) | Personen/Dinge aus Bildern, Bewegung/Timing aus Clips übernehmen; mit Häkchen „Person tauschen“ (`tauschen: true`, seit 09.10.2026) eine Person im Clip durch die Person aus Bild 1 ersetzen | bis 9 `bild`, bis 3 `clip` (2–15 s); beim Tauschen genau 1 Clip und mindestens 1 Bild | Videoformat; „Wie genau kopieren“ normal/so genau wie möglich (viel langsamer), Ton des ersten Clips behalten/weglassen |
| Zeitlupe (`video_zeitlupe`, seit 09.10.2026, nur aus der Großansicht bzw. dem Skill) | ein Video 1,5-fach oder doppelt so lang und entsprechend langsamer, mit Zwischenbildern (RIFE), ohne neu zu rechnen; ohne Ton | 1 Video (`original`, MP4) | wie das Video; `faktor` 1,5 oder 2 |
| Video freistellen (`video_freistellen`, seit 09.10.2026, nur aus der Großansicht bzw. dem Skill) | Personen (oder ein anderes Motiv, englisch) behalten, Rest durchsichtig | 1 Video (`original`, MP4) | wie das Video; WebM (VP9) mit Transparenz, ohne Ton |
| Szenenfolge (seit 05.10.2026, eigene Aktion `folge_neu`) | ein längeres Video aus mehreren Szenen: gemeinsamer Teil (Figuren, Ort, Licht, Stil) + je Szene Handlung, Kamera, Gesprochenes; Szene 1 eigener Clip, jede weitere verlängert die freigegebene Szene davor; nach jeder Szene „Passt“ oder „Nochmal“ | freiwillig `start` (Startbild) **oder** `bild` (Referenzbilder) für Szene 1 | Videoformat; Szene 1 5–15 s, weitere 3,5–12,8 s neu, zusammen bis 60 s |
| Video weiterführen (`video_weiter`, seit 27.09.2026) | ein Studio-Video verlängern, ein Stück davor setzen, zwei Clips mit einem neuen Übergang verbinden oder zur Schleife schließen; der Clip bleibt unverändert | nur aus der Bibliothek: `ausgang` (Clip davor) und/oder `ziel` (Clip danach), je nach `modus` | wie die Clips; neues Stück 3,5–14,3 s, fertiges Video bis 60 s |
| 3D-Modell (`modell3d`, seit 11.10.2026, Stufe 3t) | ein texturiertes 3D-Modell (GLB) mit Pixal3D – aus einem Drehblatt mit vier Ansichten (Vorschlag „Drehblatt“), aus Einzelansichten oder aus einem einzelnen Bild; dazu ein Drehteller als Vorschau-Video | 1 (`vorlage`: Drehblatt, erkannt an Breite ≥ 3 × Höhe, oder ein Bild) **oder** `vorn` (Pflicht), `links`, `hinten`, `rechts` | kein Format; Detailstufe `fein` oder `leicht`; Ergebnis `Modell_…glb` + `Modell_…mp4` (gleicher Stamm) |

### Bearbeiten im Detail

- Vorlagen im Text als „Bild 1“, „Bild 2“ … ansprechen (Qwen sieht sie intern als `<image1>`, `<image2>`; beides
  funktioniert). Bild 1 bestimmt Seitenverhältnis und Ausschnitt; „↑“ in der Oberfläche holt eine Vorlage nach vorn.
- **Größe:** „Wie Vorlage 1“ ist richtig für Änderungen, die genau an ihrem Platz bleiben sollen. „· 2 MP / · 4 MP“
  rechnet größer (hochskalieren). Ein **Format** erzeugt eine neue Fläche, etwa für ein Charakterblatt (16:9).
- **Details auffrischen** (`details: true`): hängt die Detail-LoRA an (Abschnitt 4). Nur für schwache Fotos.

### Stelle verbessern im Detail

- Stelle im Markier-Fenster malen (Pinsel/Radierer B/E, Größe [ ], Mausrad zoomt, rechte Maustaste oder Leertaste
  verschiebt, Strg+Z/Y, Umkehren, Einpassen 0).
- **Wie viel darf sich ändern:** Alles (1,0, Stelle wird neu gestaltet) · Viel (0,8, grobe Form bleibt) · Wenig
  (0,6, nur ausbessern).
- Neu gerechnet wird ein Ausschnitt um die Markierung (dreifache Größe, mindestens 384 px), vergrößert auf
  1024–1328 px, damit eine kleine Hand genug Pixel bekommt. Er kommt weich ins Original zurück; weiter als etwa
  15 px von der Markierung bleibt jedes Pixel gleich. Das Original wird nie verändert.
- Beim Entfernen den Gegenstand im Text benennen.
- **Stelle per Wort** (seit 27.09.2026, `stelle`): statt zu malen im Feld „Oder Stelle per Wort finden“ sagen, was
  neu entstehen soll, etwa „hand“, „face“, „cup“; mehrere gleiche Dinge mit Anzahl: „hand:2“. SAM3 sucht die Stelle beim
  Erstellen (etwa 1 s). Englisch ist verlässlich, Deutsch nur teilweise: „Hund“, „Fahrrad“, „Hand“ gingen, „Liege“
  fand die Therapeutin. Eine gemalte Markierung hat Vorrang. Die gefundene Maske steht in der Begleitdatei; „Nochmal“
  nimmt sie wieder, „Mit Änderungen“ öffnet sie im Markier-Fenster zum Nacharbeiten.
- Geprüft am echten System: „hand:2“ fand beide Hände der Therapeutin (`Verbessert_00010_`), „hand“ die Hand im Schoß
  (`_00011_`); beide Masken lagen genau auf den Händen. Ist die Hand schon gut, zeichnet Qwen sie nur leicht nach
  (0,01–0,24 % der Pixel geändert). Liegen zwei Stellen weit auseinander, wird das ganze Bild als Ausschnitt gerechnet.
  Findet SAM3 nichts, bricht der Auftrag mit einem Hinweis ab (anders beschreiben oder malen).
- **Vorbild für die Stelle** (seit 05.10.2026, Stufe 3n): Unter der Markierung ein Bild wählen („Aus Datei …“ oder in
  der Großansicht eines Bildes „Für die Stelle“), das an die Stelle soll: ein Porträt, eine Logo-Datei, ein Produktfoto.
  Im Text heißt es „Bild 2“. Anders als „Kopf tauschen“ oder „Logo aufbringen“ beim Bearbeiten bleibt dabei alles
  außerhalb der Stelle Pixel für Pixel gleich. Vorschläge „Kopf nach Vorbild“, „Logo nach Vorbild“, „Gegenstand nach
  Vorbild“ (Abschnitt 6).
  - Das Vorbild geht auf etwa 1 MP verkleinert mit; der Ausschnitt ist dann nur doppelt so groß wie die Markierung
    (sonst dreifach), damit die Stelle mehr Pixel bekommt. Dauert etwa 6 s länger.
  - Geprüft (Turbo, INT8): **Kopf** aus einem Porträt 9 von 9 erkennbar die Person aus Bild 2 (nur beschrieben: eine
    andere Frau, 2 von 2). **Logo**-Symbol 14 von 14 richtig; der Schriftzug mit doppeltem Ausschnitt 4 von 4 richtig
    (mit dreifachem 3 von 8, meist „LINDENHOE“), eine sehr kleine Unterzeile fällt weg. **Gegenstand** (Sitzpouf aus
    einem Produktfoto) mit doppeltem Ausschnitt 5 von 5 vollständig, einmal stand das Rad der Liege davor (mit
    dreifachem 2 von 6, sonst am Rand der Markierung abgeschnitten oder gar nicht da).
  - Grenzen: Blick und Lächeln des Porträts schlagen oft durch (Kopf mit Wunsch „ernst“: 5 von 9 lächelten trotzdem) –
    den Ausdruck nennen und 2–3 Variationen rechnen. Zeigt Bild 2 nur einen Teil (ein Hund nur mit Kopf und Pfoten),
    kommt oft auch nur dieser Teil (2 von 4). Die Markierung so groß machen, dass das Ganze hineinpasst; was über ihren
    Rand hinausginge, wird abgeschnitten (bei einer zu knapp über dem Kopf gezogenen Markierung war das Haar oben flach).

### Freistellen im Detail

- „Was soll bleiben?“ leer lassen (dann das Hauptmotiv) oder benennen: „den Hund“, „die Therapeutin und den
  Patienten“. Deutsch geht, die feste Anweisung an Qwen ist englisch (Abschnitt 6).
- **Leer = schnell** (seit 27.09.2026, `verfahren: 'schnell'`): ohne Beschreibung stellt ein eigenes Freistell-Modell
  (BiRefNet, Kernknoten „Remove Background“) das Hauptmotiv in etwa 1 s frei statt Qwen in 15–30 s. Test an sechs
  Bildern (Wiese, zwei Porträts, Hund, Praxis 4 MP, Behandlung): so sauber wie Qwen, kein Schleier, **feine Haare
  bleiben** als weiche Kante (Qwen schneidet sie ab). Dafür tragen halbdurchsichtige Kanten etwas vom alten Hintergrund:
  auf dunklem Grund ein heller Saum, auf hellem Grund unsichtbar. Das Kissen unter dem Hund ließ BiRefNet von selbst
  weg. Wer die harte Qwen-Kante will: „das Hauptmotiv“ hineinschreiben (Skill: `--genau`).
- Mit Beschreibung rechnet Qwen eine Fassung mit durchsichtigem Hintergrund; genommen wird nur deren Maske. Das Motiv
  behält seine **Originalpixel in Originalgröße**. Schwache Reste fallen weg, ein Pixel Rand gegen hellen Saum ebenfalls.
- Ganz durchsichtige Stellen sind weiß hinterlegt. So taugt das Bild direkt als Vorlage („Setze die Frau aus Bild 1
  an einen Sandstrand …“ – geprüft, Motiv blieb unverändert).
- Grenzen: feinste abstehende Haare gehen verloren. Verbessern oder Hochskalieren eines freigestellten Bildes
  lieferte ein Bild ohne Transparenz (erneut 26.09.2026: `Bearbeitet_00069_` auf Weiß); dafür erst das Original
  bearbeiten, dann freistellen.
- Wird das Motiv erst erfunden, geht es in einem Schritt: neues Bild mit „Durchsichtiger Hintergrund“ (nächster
  Abschnitt). Freistellen ist für vorhandene Bilder, deren Pixel genau so bleiben sollen.

### Durchsichtiger Hintergrund im Detail (neues Bild)

- Häkchen „Durchsichtiger Hintergrund (Motiv freigestellt, PNG)“ unter **Neu** (`durchsichtig: true`, nur `art: bild`).
  Nur das Motiv beschreiben, ohne Hintergrund: „Eine weiße Keramiktasse mit einem kleinen grünen Blatt-Aufdruck,
  Produktfoto, weiches Studiolicht“. Das Studio setzt die Beschreibung in einen festen englischen Rahmen aus der
  ComfyUI-Vorlage für Qwen 2.1 (Abschnitt 6); in der `.json` steht nur die Beschreibung.
- Qwen rechnet die Transparenz selbst (VAE mit vier Kanälen), ein Schritt, so schnell wie ein normales Bild.
  Test 26.09.2026 (Person, Tasse, Pflanze je 2 Nummern, Turbo, 9–14 s): **6 von 6 sauber**, auf Weiß, Magenta und
  Schwarz ohne Saum, Haare und Blätter fein.
- Aufgeräumt wird automatisch: Qwen lässt einen fast unsichtbaren Schleier (Deckung 1–5 von 255 auf 24–47 % der
  Fläche) und legt unter durchsichtige Stellen Lila. Deckung bis 2 % wird 0, darüber gestreckt (Kanten bleiben weich);
  ganz durchsichtige Stellen sind weiß hinterlegt wie beim Freistellen. Danach Schleier 0,1–0,4 % (`Bild_00075_`,
  `Bild_00078_`).
- Ausgabe: PNG mit Alphakanal; Export als WebP behält die Transparenz, JPEG zeigt Weiß (`studio.py export`).
- „Nochmal“ und „Mit Änderungen“ übernehmen das Häkchen. Für Bearbeiten gibt es das Häkchen nicht; dort „Freistellen“
  auf das Ergebnis anwenden.
- **Gleich in der richtigen Größe erzeugen:** 4 MP geht (2048², `Bild_00079_`, 31,5 s, sauber; der Tassenboden
  reichte bis an den unteren Bildrand). Durchsichtige Bilder nicht weiterbearbeiten: Hochskalieren und Umfärben ergaben
  2 von 3 ein Bild auf Weiß (`Bearbeitet_00069_` aus einem freigestellten Bild, `_00070_`), 1 von 3 Transparenz ohne
  Aufräumen, mit Lila darunter und eher gemalt als fotografiert (`_00068_`). Die Großansicht bietet deshalb wie bei
  freigestellten Bildern nur „Als Vorlage“ (Motiv auf Weiß); der Skill lehnt `hochskalieren`, `auffrischen` und
  `verbessern` für durchsichtige Bilder ab.

### Pose übernehmen im Detail (seit 27.09.2026)

- **Zwei Schritte:** 1. Aus einem Bild mit der gewünschten Haltung ein **Pose-Skelett** machen: Art „Pose“ oder in der
  Großansicht „Pose-Skelett“ (SDPose, etwa 1–2 s; farbige Strichfigur auf Schwarz in Originalgröße, Datei
  `Pose_#####_.png`). 2. In der Großansicht des Skeletts „Als Pose-Vorlage“: Bearbeiten mit dem Skelett als Bild 1 und
  dem Vorschlag „Pose übernehmen“; die Person kommt als Bild 2 dazu (etwa ein Porträt), sonst beschreibt man sie.
- Test 27.09.2026 (Winken mit Hand in der Hüfte, Arme weit zur Seite mit Band, Band über dem Kopf; je deutsch und
  englisch, 2 Nummern, Haltung zusätzlich in Worten beschrieben): **12 von 12 in der vorgegebenen Haltung**; aus einem
  Foto als Bild 1 übernahm Qwen eine fremde Pose nur 1 von 4 Mal (Abschnitt 8). Die Person aus Bild 2 blieb erkennbar. Am echten System: Skelett aus `Bild_00007_`
  (`Pose_00001_`) + Porträt `Bild_00027_` → `Bearbeitet_00071_` (14 s), Haltung und Gesicht stimmen.
- **Mehrere Personen** (seit 27.09.2026, `personen: true`, für neue Aufträge automatisch, wenn SAM3 da ist): Ohne
  Rahmen nimmt SDPose das ganze Bild als eine Person – bei einer Behandlung kam nur die Therapeutin heraus. Jetzt sucht
  SAM3 zuerst die Personen („person:6“, bis zu sechs), SDPose zeichnet jede in ihrem Rahmen (etwa 1 s mehr). Test: in
  der Behandlung beide Personen (`Pose_00005_` statt `_00004_`); Einzelpersonen (Wiese, Porträt, Band) gleich wie
  vorher; ein Raum ohne Person gibt ein leeres Skelett. Stark überlappende Personen (Therapeutin dicht hinter dem
  Patienten mit Band) wurden weiter nur eine. Mit dem Zwei-Personen-Skelett als Bild 1 übernahm Qwen Aufbau,
  Bildausschnitt und beide Haltungen 2 von 2, sogar mit getauschten Rollen („ein Physiotherapeut … steht rechts hinter
  einer sitzenden Patientin … legt beide Hände auf ihre Schultern“). Nur aus Text gelang dieselbe Handlung ebenfalls
  2 von 2, aber mit anderem Aufbau – das Skelett lohnt sich, wenn Aufbau und Griffe wie im Vorbild sein sollen.
- **Grenzen:** Das Skelett zeigt nur den Körper. Geräte wie ein Übungsband im Text genau beschreiben; es hing trotzdem
  3 von 4 Mal eher wie ein Schal. Stand das Band im Vorbild vor dem Gesicht, lag es auch im Ergebnis dort (4 von 4). Bei
  Brustbildern erfindet SDPose Beine unterhalb des Bildrands. Einfache Haltungen („Arme weit zur Seite“) gelangen auch
  ohne Skelett (2 von 2) – das Skelett lohnt sich bei schwierigen Posen und für genaue Übungen.

### Wunsch ausformulieren im Detail (neues Bild, seit 27.09.2026)

- Häkchen „Wunsch ausformulieren lassen“ unter **Neu** (`ausformulieren: true`). Der offizielle Prompt-Enhancer von
  Qwen (ein lokales Sprachmodell, Qwen3.5 9B INT8) schreibt aus einem kurzen Wunsch eine ausführliche englische
  Bildbeschreibung (Systemtext der ComfyUI-Vorlage, Datei `werkstatt\ausformulieren_t2i.txt`). Sie steht danach in der
  Großansicht („Ausformuliert“) und in der Begleitdatei (`prompt_ausformuliert`); der Prompt bleibt der Wunsch.
- Test mit vier kurzen deutschen Wünschen × 2 Nummern: „Physiotherapeutin behandelt die Schulter …“ direkt 0 von 2
  passend (zwei posierende Personen, eine Ärztin mit Mundschutz), ausformuliert 2 von 2 echte Behandlungen;
  „Wartezimmer …“ direkt wie ein Labor, ausformuliert 2 von 2 stimmige Wartebereiche; Hund und Dehnübung schöner.
- **Schrift:** Der Enhancer erfindet gern Schrift (ein Wandspruch mit Tippfehler, ein Poster „PHYSIOTHERAPY“,
  `Bild_00081_`). Mit „ohne Schrift“ im Wunsch schrieb er ausdrücklich „keine Schrift“ hinein, das Bild war frei davon
  (`Bild_00082_`).
- **Aussehen:** Selbst schreibt der Enhancer bei Personen nur „light-to-medium skin, dark brown hair“, nie eine Herkunft;
  im Test kam so 1 von 4 ostasiatisch heraus. Steht „mitteleuropäisch“ im Wunsch, übernimmt er es („of Central European
  appearance, fair skin“, `Bild_00119_`). Also das Aussehen in den Wunsch schreiben (Abschnitt 7).
- Dauer: 15–34 s statt 7 s je Bild (INT8, Turbo), auf der 3090 (Spitze 18,7 GiB). Auf der 3080 neben dem Text-Encoder
  lief er zum Teil im Arbeitsspeicher und brauchte 517 s – deshalb läuft er auf der Karte des Bildmodells (bis
  14.10.2026 fest `gpu:0`, seither die je Auftrag gewählte Karte). Gleiche Nummer ergibt denselben Text und
  dasselbe Bild (geprüft: `Bild_00081_` → `Bild_00084_`).
- **„Ausformuliert übernehmen …“** (Großansicht, seit 09.10.2026): übernimmt alle Einstellungen wie „Mit Änderungen“ und
  setzt den ausformulierten Text als Prompt ein, das Häkchen „Wunsch ausformulieren“ ist dann aus. So lässt sich eine
  gelungene Beschreibung gezielt ändern, statt sie neu erfinden zu lassen.
- Nicht mit „Durchsichtiger Hintergrund“ (der braucht die Beschreibung selbst) und nicht für die Moodboard-Vorschläge
  (die sind schon genau formuliert). Für Agenten meist unnötig: sie schreiben ausführliche Prompts selbst.

### Videos im Detail

- **Gesprochenes** steht im Prompt als `<d>[Deutsch] Guten Morgen, schön, dass Sie da sind.</d>`; etwa 20–24 Wörter
  je 8 s. MiniMax erzeugt Stimme, Geräusche und Musik selbst.
- **Ton gibt es immer:** MiniMax-H3 rechnet Bild und Ton in einem Durchgang (Text, Schlüsselbilder, Ton und Bild in
  einer Folge); einen Modus nur für das Bild hat das Modell nicht. Der Ton kostet kaum etwas (bei 5 s in 960 × 544 etwa
  400 Ton- gegen 18.900 Bild-Teile, rund 2 % der Rechenarbeit). Für Webseiten entfernt `studio.py export` ihn
  automatisch (nur `--mit-ton` behält ihn); die Studio-Datei behält ihn als Original, etwa für YouTube. Für
  Hintergrundvideos „keine Sprache“ schreiben (Frage Sascha, 27.09.2026).
- **Schärfe verlangen**; Wörter wie Körnung, Dunst oder weich machen das Video weich.
- Aus Bild: Nur das Startbild ist fest. Wer nicht darauf zu sehen ist, kann sich im Lauf verändern.
- Mit Referenz: die Person im Text benennen und sagen, dass ihr Aussehen vollständig erhalten bleibt. Ein Clip als
  Referenz ist der verlässliche Fall. Bilder „Bild 1“ …, Clips „Video 1“ … nennen.
- Aus einem Bild der Bibliothek: Großansicht „Zu Video“ (Format passend zum Seitenverhältnis) oder „Als Endbild“.
- **Realistische Personen** (seit 05.10.2026, Stufe 3o, `realismus: true`): hängt die Realism-LoRA an. Vergleich je
  2 Nummern bei 8 Schritten, gleicher Text: Nahaufnahme aus Text 2 von 2 natürlichere, matte Haut (ohne glänzte sie,
  einmal mit Fantasie-Schrift „Nahaefsbtod“ auf dem Oberteil und Ansteckmikro); mit Referenzbild 2 von 2 die Frau aus
  dem Porträt besser zu erkennen; Porträt als Startbild kein Unterschied; leerer Raum 2 von 2 schlechter. Abnahme über
  die Oberfläche (`Video_00016_`, Nahaufnahme mit Poren und Bartstoppeln) und beim Weiterführen über den Skill
  (`Video_00017_`, dieselbe Person über die Naht). Nur für Videos mit Menschen anhaken.

### Videos weiterführen im Detail (seit 27.09.2026)

- **Wozu:** ein Studio-Video **verlängern**, ein Stück **davor setzen**, zwei Clips mit einem neuen Übergang
  **verbinden** oder ein Video zur **Schleife schließen** (endlos wiederholbar, etwa als Hintergrund einer Webseite).
  Die Clips bleiben unverändert; heraus kommt eine neue Datei `Video_…mp4` mit dem ganzen Video.
- **Bedienen:** Großansicht eines Videos → „Weiterführen:“ „Verlängern …“, „Davor setzen …“, „Schleife schließen …“,
  „Verbinden …“ (dieser Clip zuerst; beim zweiten Clip „Als Clip danach“). Oder Art „Weiterführen“ und „Wie
  weiterführen?“ im Formular; „Reihenfolge tauschen“ dreht die Clips beim Verbinden um. Clips nur aus der Bibliothek
  (kein „Aus Datei“). Der Prompt des Clips steht schon im Feld; beschreiben, was im neuen Stück geschieht.
- **Neues Stück:** Die Auswahl zeigt die tatsächliche Länge je Modus: Verlängern 3,5–12,8 s, Verbinden und Schleife
  3,5–12,7 s, Davor setzen 5,1–14,3 s. Die Schätzung nennt auch die Länge des fertigen Videos (höchstens 60 s).
- **Kürzen:** „Ende des Clips kürzen um“ lässt das Ende des Clips davor weg (Verlängern, Verbinden, Schleife), etwa
  ein missglücktes Ende; „Anfang des Clips kürzen um“ den Anfang des Clips danach (Davor setzen, Verbinden). Sekunden,
  auf ganze Bilder gerundet (die Schätzung nennt die Bilder). Vom Clip davor bleiben mindestens 1,6 s.
- **So wirkt es:** Vorn hält das Videomodell die letzten 39 Bilder (1,6 s) des Clips davor samt Ton fest und rechnet von
  dort weiter – Bewegung, Licht und Ton setzen sich fort; ins fertige Video kommt nur, was danach entsteht. Hinten
  (Davor setzen, Verbinden, Schleife) führt das neue Stück auf **ein Endbild** zu: das erste Bild des Clips danach bzw.
  bei der Schleife das erste Bild des Clips.
- **Bild und Ton:** Unveränderte Clips stecken Paket für Paket bitgleich im Ergebnis (Bildspur nur umverpackt), auch
  über mehrere Verlängerungen: `Video_00007_` → `_00009_` → `_00014_`, die ersten 124 Bilder sind in allen dreien
  dieselben Pakete. Mit Kürzen wird das ganze Video einmal neu kodiert (Abweichung 0,9 von 255). Der Ton wird genau
  an den Bildgrenzen zusammengesetzt: Ton-Versatz der übernommenen Clips 0,0 ms, Ton und Bild gleich lang (±1,7 ms).
  Er wird bei jeder Verlängerung neu kodiert (AAC, 32 kHz, 128 kbit/s): Abstand zum Original 21,6 dB nach einer,
  18,7 dB nach zwei Verlängerungen (rauschartige Umgebungsgeräusche). Das Bild leidet also nie, der Ton mit jeder
  weiteren Runde etwas; für Webseiten fällt er beim Export ohnehin weg.
- **Grenzen (geprüft am 27.09.2026):**
  - Das Endbild kennt nur die Lage, nicht die Bewegung. Weicht das neue Stück davon ab, holt das Modell es in den
    letzten Bildern ein: Beim Davor-Setzen hatte das neue Stück einen warmen Sonnenstrahl erfunden, den der Clip am
    Anfang nicht hat – in den letzten 7 Bildern (0,3 s) wurde es um etwa 20 % dunkler (`Video_00010_`). **Licht und
    Stimmung so beschreiben wie am Anfang des Clips danach.**
  - **Verbinden sehr verschiedener Clips:** Beschreibt der Prompt keinen Weg in den zweiten Clip, bleibt das neue
    Stück im ersten Raum und springt erst im letzten Bild zum Endbild – am Übergang ein harter Schnitt (`Video_00011_`:
    Praxis mit Glaswand → kleiner Raum mit Polsterliege, 5,6 s neu, Sprung 60 bei sonst 2). **Beim Verbinden den Weg in
    den zweiten Clip beschreiben** (Tür, Blickrichtung, Raum, Liege) und lieber ein längeres Stück wählen: Mit „die
    Kamera gleitet … durch die offene Glastür in den Nebenraum, einen kleineren, hellen Behandlungsraum mit … einer
    gepolsterten weißen Behandlungsliege, einem Vorhang …“ und 9,9 s fuhr die Kamera durch die Tür und kam genau auf dem
    ersten Bild des zweiten Clips an (`Video_00015_`, Sprung 3,0 bei sonst 1,0; geändert waren Prompt und Länge).
  - Der Ton wechselt am Übergang in den Clip danach hart (bei der Schleife an der Wiederholstelle).
  - Beim Verbinden müssen beide Clips gleich groß sein. Nur Studio-Videos (MP4, 24 Bilder je Sekunde, mit Ton, Größe
    ein Vielfaches von 32); andere lehnt das Studio mit Grund ab.
  - Gerechnet wird ein ganzer Clip der Länge L (neues Stück plus 1,6 s vorn plus Endbild); die Rechenzeit wächst
    stärker als die Länge (Abschnitt 11).
  - **Mehrmals hintereinander verlängern** (05.10.2026, drei Runden): Die Person bleibt erhalten, auch ohne Referenzbild
    (mit Porträt als Referenz kein sichtbarer Vorteil, 12 s mehr je Runde). Aber in Runde 3 sprang das Bild 2 von 2 in
    eine neue Einstellung (Sprung 58–61 bei sonst 4–7). Mit dem Satz **„Eine durchgehende Einstellung ohne Schnitt: Die
    Kamera bleibt in derselben Einstellung wie am Anfang, sie bewegt sich nur langsam mit.“** am Ende 2 von 2 sauber
    (4,8–4,9), die Handlung kam trotzdem. Die Szenenfolge hängt ihn selbst an.

### Szenenfolge im Detail (seit 05.10.2026)

- **Wozu:** längere Videos aus mehreren Szenen, etwa eine Therapeutin, die begrüßt, eine Übung zeigt und sich setzt, oder
  ein Hintergrundvideo mit mehreren Kamerabewegungen. Es entsteht **ein** Video; jede Szene liefert eine Zwischenstufe
  (`Video_…` mit allen Szenen bis dahin).
- **Gemeinsamer Teil** (Beschreibungsfeld): wer zu sehen ist (Alter, Haare, **Kleidung genau**), Ort, Licht, Stil,
  Kameraabstand. **Kein Gesprochenes** – das gehört in die Szene. Steht vor jeder Szene.
- **Szenen:** je Szene, was geschieht, was die Kamera tut, was gesagt wird (`<d>[Deutsch] …</d>`). Ab Szene 2 aus der
  Lage am Ende der Szene davor denken. Länge je Szene (Szene 1 wie „Aus Text“, jede weitere wie „Verlängern“).
- **Ablauf:** Szene 1 ist ein eigener Clip (aus Text, mit Startbild oder Referenzbildern), jede weitere verlängert das
  freigegebene Video (die letzten 1,6 s samt Ton festgehalten, Abschnitt „Videos weiterführen“). Ans Ende jeder Szene
  hängt das Studio den Satz „Eine durchgehende Einstellung ohne Schnitt …“.
- **Prüfen** (Häkchen, Standard): Nach jeder Szene steht über der Bibliothek eine Karte: „Szene ansehen“, „Passt – weiter
  mit Szene n“, „Nochmal“ (dieselbe Szene mit neuer Nummer), „Beenden“. Ohne Häkchen laufen alle Szenen durch. Ein Fehler
  hält die Folge an („Nochmal“ oder „Wiederholen“ in der Auftragsliste). Mit fester Nummer gilt sie für den ersten
  Versuch jeder Szene.
- **Szene 1 streng prüfen:** Was sie zeigt (Kleidung, Ausschnitt, Haltung), tragen alle weiteren Szenen weiter. Abnahme
  05.10.2026: Szene 1 kam einmal mit Bluse statt Praxiskleidung und einer zweiten Person auf der Liege („Nochmal“ half),
  der nahe Selfie-Ausschnitt blieb bis zum Ende. Nähte 3,8–5,3 bei sonst 1,5–3,1, kein harter Schnitt; mit Realism-LoRA
  erschien ab Szene 2 ein durchsichtiger Streifen von der Decke.
- **Realistische Personen je Szene** (seit 09.10.2026): Jede Szene hat ihr eigenes Häkchen (das allgemeine Häkchen ist
  in der Szenenfolge ausgeblendet). So bekommt etwa eine Szene im leeren Raum keine Realism-LoRA (dort wird sie
  schlechter, Stufe 3o), die Szenen mit Personen schon. Eine neue Szene übernimmt das Häkchen der Szene davor.
  Schnittstelle: `szenen[i].realismus`; das alte `realismus: true` für die ganze Folge gilt weiter für jede Szene ohne
  eigene Angabe, ebenso für Folgen von vor dem 09.10.2026.
- Dauer: Szene 1 wie ein Video aus Text, jede weitere wie „Verlängern“ (bei 5,7 s neu etwa 5 min); drei Szenen mit
  16,5 s etwa 12 min (Abschnitt 11).

### Person tauschen im Detail (seit 09.10.2026, Stufe 3q)

- **Wozu:** in einem vorhandenen Clip eine Person durch eine andere ersetzen – etwa eine Übung, die ein Mann vormacht,
  von der Praxis-Figur zeigen lassen. Raum, Kamera, Ausschnitt, Bewegung und alle anderen Personen bleiben.
- **So:** „Video mit Referenz“, Clip = das Ausgangsvideo, Bild 1 = die neue Person (ganz zu sehen, am besten
  freigestellt), Vorschlag „Person tauschen“. Er setzt die englische Vorlage des LoRA-Autors ein und markiert, wer
  ersetzt wird („the woman in the mint green T-shirt on the left“) – nur diese Stelle ändern, mit Kleidung und Position.
  Das Häkchen „Person tauschen“ hängt die Character-Swap-LoRA an; gerechnet wird mit der Turbo-LoRA (nicht mit der
  8-Schritt-LoRA, siehe unten).
- **Geprüft** (06. und 09.10.2026, 960 × 544, 5 s, Figur `Praxis-OS Design/Freigestellt_00005_.png`):
  eine Person (Mann bei einer Schulterübung, `Video_00016_`) und zwei Personen nebeneinander, nur die Frau links tauschen
  (`Video_00017_`). Mit Turbo wurde in **8 von 8** Läufen richtig getauscht, auch ohne LoRA; der Mann im
  Zwei-Personen-Fall blieb unverändert. Abweichung zum Original außerhalb der Person (Median, 0–255): ohne LoRA
  14,3–14,8 bzw. 12,3–12,5, mit Character-Swap-LoRA 10,6–11,3 bzw. 9,8–10,1. 20 Schritte ohne Turbo: 9,2, aber 17 statt
  8 min. Die 8-Schritt-LoRA statt Turbo hielt den Raum noch näher (7,9–8,3) und die Haut matter, setzte aber im
  Zwei-Personen-Fall 2 von 3 die Figur zusätzlich groß ins Bild (mit dem Tablet aus dem Referenzbild), die Frau blieb –
  auch ohne Character-Swap-LoRA. Deshalb tauscht das Studio mit Turbo.
- **Dauer:** 7–8 min je 5 s bei 8 Schritten, weil die Bilder des Clips mitrechnen (die Schätzung zählt sie seit
  09.10.2026 mit). Laut Autor am besten kurze Clips (4–5 s) ohne Schnitt; Mimik, Timing und Schnitte unzuverlässig.
- Schnittstelle: `tauschen: true` (nur `video_referenz`, genau 1 Clip und mindestens 1 Bild); Skill `studio.py tauschen
  <clip> <bild> "<wer, englisch>"`. Lizenz wie MiniMax-H3.

### Zeitlupe im Detail (seit 09.10.2026)

- **Wozu:** ein ruhiges Video länger und langsamer machen, ohne neu zu rechnen – etwa ein Hintergrundvideo für eine
  Webseite. Großansicht eines Videos: „Zeitlupe 1,5×“ oder „Zeitlupe 2×“. Das Original bleibt; neu entsteht
  `Zeitlupe_…mp4` **ohne Ton** (er passt nicht mehr zur Bewegung).
- **Wie:** RIFE 4.25 (Kernknoten FrameInterpolate) rechnet Zwischenbilder. ×2 setzt zwischen je zwei Bilder eins
  (124 → 247 Bilder bei 24 Bildern/s), ×1,5 rechnet dreimal so viele und nimmt jedes zweite (124 → 185).
- **Geprüft:** ruhige Kamerafahrt durch die Praxis (`Video_00008_`) und ein Mann, der die Arme hebt (`Video_00016_` →
  `Zeitlupe_00001_`): die eingefügten Bilder ohne Doppelkonturen, Verzerrung oder Flackern, auch an den bewegten Armen.
  Dauer 8–15 s für 5 s Video.
- **Warum nicht der „16-Bilder/s-Trick“** aus dem Video „One LoRA Can't Run a Whole Film“: MiniMax-H3 rechnet fest mit
  24 Bildern/s (Länge „Frame count at 24 fps“), der Ton hängt daran. Weniger Bilder rechnen und auffüllen ergäbe
  Zeitlupe mit falschem Ton. Für ruhige Videos ohne Ton ist genau das aber nützlich – deshalb die Zeitlupe.

### Video freistellen im Detail (seit 09.10.2026)

- **Wozu:** echte oder KI-Videos mit Personen ohne Hintergrund – Person über eine Webseite legen, Text hinter die
  Person (`video-regie`), anderen Hintergrund einsetzen. Großansicht eines Videos: „Person freistellen“; Skill:
  `studio.py freistellen <video.mp4> [--motiv dog]`. Ergebnis `Freigestellt_…webm` (VP9 mit Alphakanal, ohne Ton).
- **Wie (nur Kernknoten, vorhandene Modelle):** SAM3 verfolgt das Motiv (englisches Wort, Standard „person“) über alle
  Bilder und wählt aus, BiRefNet zieht je Bild die feinen Kanten; gezählt wird BiRefNet nur innerhalb der um 16 px
  erweiterten SAM3-Maske (`verfahren` kombi). Alle gefundenen Personen bleiben (zwei Personen: beide).
- **Geprüft** an drei Videos (Mann bei einer Übung, zwei Personen nebeneinander, Selfie mit offenen Haaren; je drei
  Verfahren, über Magenta begutachtet): kombi und BiRefNet allein mit weichen, natürlichen Haar- und Handkanten, ohne
  Reste; SAM3 allein mit harter Haarkante, hellem Saum an der Hand und Löchern am unteren Bildrand. Abnahme über die
  Werkstatt: `Freigestellt_00001_.webm` aus `Video_00017_`, `alpha_mode=1`, 66 s.
- **Dauer:** 58–71 s je Video (5 s quer, 8 s hoch). LTX 2.5 Alpha Gen (etwa 40 GB) braucht es dafür nicht.
- **Grenzen:** Safari zeigt WebM-Alpha nicht durchsichtig (Chrome, Edge, Firefox schon); ffmpeg liest den Alphakanal nur
  mit `-c:v libvpx-vp9` vor `-i`. Ein Motiv, das nur zeitweise zu sehen ist, oder Personen im Hintergrund nimmt SAM3 mit.

### 3D-Modell im Detail (seit 11.10.2026, Stufe 3t)

- **Wozu:** aus einer Figur oder einem Gegenstand ein echtes 3D-Modell mit Texturen (GLB) – für Webseiten und Apps
  (drehbare Figur, Requisiten in einem Beetplaner), für Blender und Spiele-Engines, oder als Vorlage, um dieselbe Sache aus
  jedem Winkel gleich zu zeichnen (Rendering → „Bearbeiten“ im gewünschten Stil). Anlass: Video „I Fixed Pixal3D's Biggest
  Weakness“ (PixelArtistry, 07.10.2026), Befund in PLAN.md.
- **Womit:** **Pixal3D** (TencentARC, SIGGRAPH 2026, MIT; Comfy-Org-Dateien, INT8) – „pixel-aligned“: es hebt die Bildpixel in
  den Raum und bleibt dadurch nah an der Vorlage. Kernknoten unseres ComfyUI 0.37.0 nach den Comfy-Org-Vorlagen „Pixal3D:
  Multi Views to 3D“ und „Pixal3D & TRELLIS.2: Image to Model“. Keine eigenen Knoten, keine neuen Pakete.
- **Drei Wege zur Vorlage:**
  1. **Drehblatt** (empfohlen für Figuren): beim Bearbeiten der Vorschlag „Drehblatt (Figur)“ bzw. „(Gegenstand)“ –
     vier Felder nebeneinander (vorn, links 90°, hinten, rechts 90°) auf Schwarz, Panorama 4:1, Turbo, 26–36 s. Das Studio
     schneidet die Viertel, stellt jedes mit BiRefNet frei und setzt es mittig auf 1024² (Rand 1,1), wie es Pixal3D erwartet
     (FOV 20). **Zwei Variationen rechnen und die Rückansicht prüfen** (Test: 1 von 2 zog die Schürze über den ganzen
     Rücken). Figuren mit Dingen in der Hand (Gießkanne) gingen; die Haltung im Prompt benennen.
  2. **Ein Bild** (`modus` bild, Knopf „3D-Modell“ in der Großansicht): Pixal3D-Einzelbildmodell; den Blickwinkel schätzt
     MoGe. Die Rückseite erfindet das Modell – gut für symmetrische Gegenstände (Hochbeet, Kübel, Gießkanne), bei Figuren
     ungenauer als das Drehblatt. Lange Kästen drehte Qwen im Drehblatt nicht (Hochbeet: alle vier Felder von vorn) – dafür
     ist dieser Weg gedacht.
  3. **Einzelansichten** (nur Skill, `--vorn … --links … --hinten … --rechts …`): eigene Bilder je Ansicht, mindestens vorn;
     Pixal3D nimmt die erste als „vorn“ und posiert das Modell danach.
- **Wie gerechnet wird:** Struktur (12 Schritte, CFG 7,5 → ab zwei Dritteln 1, Rescale 0,7, Shift 5), Form (20 Schritte,
  512) und feine Form (12, Upsample auf 1536 bzw. 1024), Textur (12, CFG 1), dann Netz neu vernetzen (768), auf die Dreiecke
  der Stufe ausdünnen, glätten, UV abwickeln und Texturen backen (Grundfarbe, Metall, Rauheit; bei „fein“ dazu Normalen und
  Verschattung aus dem feinen Netz). Die vier Seeds sind Variationsnummer, +1, +2, +3 – gleiche Nummer, gleiches Modell.
- **Detailstufen:** `fein` (Standard, wie die Vorlage: 700.000 Dreiecke, 2K-Texturen mit Normalen) und `leicht` (150.000
  Dreiecke, 1K-Texturen, 1024er Form – fürs Web und Apps).
- **Ergebnis:** `Modell_00001_.glb` und daneben `Modell_00001_.mp4` – ein Drehteller (24 Bilder im 15°-Schritt um die
  Hochachse, `RenderMesh` 768² auf Weiß, 12 Bilder/s, 2 s Schleife) als Vorschau in der Bibliothek. Die Begleitdaten des
  Videos nennen die 3D-Datei (`modell_3d`, Bytes). Verschieben und Papierkorb nehmen die GLB mit. Großansicht: „GLB
  speichern …“, „Im Ordner zeigen“, „In ComfyUI ansehen“ (Datei auf die ComfyUI-Fläche ziehen → Load-3D-Knoten zeigt sie
  drehbar; Windows hat hier keinen 3D-Betrachter, Blender ist nicht installiert).
- **Gemessen 11.10.2026 (RTX 3090, Anna, Projekt „Garten-OS Design“):** aus dem Drehblatt `Bearbeitet_00004_` (mit
  Gießkanne) → `Modell_00002_` fein in 191 s: Figur von allen Seiten stimmig, aber Hände und Kanne matschig, dunkler Fleck
  auf der Schürze. Drehblatt in **A-Haltung mit leeren Händen** (`Bearbeitet_00007_`, Skill `drehblatt --haltung …`) →
  `Modell_00004_` fein 201 s (39,7 MB) und `Modell_00006_` **leicht 52 s (6,3 MB)**: Hände mit Fingern, Seiten- und
  Rückansicht sauber; „fein“ macht die Schürze durch gebackene Schatten fleckig, „leicht“ wirkt im flächigen Stil
  stimmiger – für Illustrationsfiguren und das Web ist **leicht** die erste Wahl, „fein“ für Fotos und Blender.
  Gesichter werden in beiden Stufen weicher als im Blatt (Pixal3D-typisch). Spitze 12,8 GB auf der 3090 (fein).
  **Regel:** Figuren ohne Dinge in der Hand und ohne verdeckte Arme ins Drehblatt; Dinge als eigenes Modell.
  **Aus einem Bild:** Hochbeet `Bild_00015_` → `Modell_00008_` leicht in 114 s (7 MB): von vorn sehr gut, Rückseite
  plausibel erfunden, dünne Pflanzen werden flache Kulissen. Spitze 13,7 GB.
- **Grenzen (Pixal3D):** höchstens vier Ansichten, kein Blick von oben oder unten (Unterseiten bleiben grob); starre Netze
  ohne Skelett (keine Posen, keine Animation); feine Dinge (dünne Stiele, Blätter) werden klobig oder fehlen; Flat-Color-
  Illustrationen ergeben Texturen mit gezeichneten Konturen (gewollt für den Garten-OS-Stil). Seit 16.10.2026 auch neben
  Whisper oder Sprachmodellen, wenn der Speicher reicht; Bedarf 16 GiB auf der 3090 angenommen, Messung in PLAN.md, Stufe 3t.

## 4. Qualität und LoRAs

### Qualitätsstufen

| Bilder | Schritte | Hinweis |
|---|---|---|
| Turbo | 8 (offizielles Modell) bzw. 6 (LoRA) | seit 11.10.2026 rechnen neue Aufträge mit dem **offiziellen Qwen-Image 2.1 Turbo** (8 Schritte, trainierter Zeitplan, `turbo_modell`); ältere Turbo-Bilder bei „Nochmal“ weiter mit der Viggle-LoRA (6 Schritte). Etwa doppelt so schnell wie Standard, gleichwertig |
| Entwurf | 12 | schnell, etwas grob |
| Standard | 20 | gute Balance |
| Hoch | 30 | mehr Details |
| Max | 40 | Standard der Oberfläche; am langsamsten |

| Videos | Schritte | Hinweis |
|---|---|---|
| Schnell | 4 | aus Text bzw. Bild seit 11.10.2026 mit **DMAD** (`dmad`): natürlichste, matte Haut, Sprache wortgenau, halbe Zeit von 8 Schritten – **empfohlen für Personen**; mit Referenz Turbo-LoRA |
| Schnell+ · Schnell beste | 6 · 8 | mit Turbo-LoRA von LightX2V (automatisch bis 8 Schritte); mit Referenz und 8 Schritten die 8-Schritt-LoRA (`acc8`) |
| Mittel · Gut · Beste | 12 · 16 · 20 | ohne Turbo; „Mittel“ kann weich wirken, „Gut“ fast wie „Beste“ |

### Schneller rechnen (seit 26.09.2026)

- Neue **Bildaufträge** aller Bildarten (Neu, Bearbeiten, Verbessern, Freistellen) rechnen mit der schnelleren
  Aufmerksamkeit von ComfyUI (Kernknoten `ModelAttentionBackend`, „comfy kitchen attention“, INT8). Oberfläche und
  Skill setzen dafür `schnell: true`, solange die Werkstatt `schnell_verfuegbar` meldet; nichts einzustellen.
- Gemessen (1328², gleiche Nummer): Turbo 13,2 → 12,2 s (−8 %), Standard 38–42 → 34–36 s (−11 bis −15 %).
  Gleiche Nummer gibt weiter genau dasselbe Bild. Gegenüber vorher weichen die Pixel im Mittel um 1,5–2,1 von 255 ab;
  Gesicht, Hände und Schrift sind gleichwertig.
- Ältere Bilder rechnen bei „Nochmal“ ohne und bleiben pixelgleich (geprüft: `Bild_00029_` → `Bild_00077_`).
  Abschalten: `studio.schnelle_aufmerksamkeit.aktiv` in `werkstatt\config.json` auf `false`.
- **Videos (seit 17.10.2026, Stufe 3u):** Neue MiniMax-Videos (aus Text, aus Bild, mit Referenz, Weiterführen,
  Szenenfolge – nicht Zeitlupe und Video freistellen) rechnen ebenfalls mit `ModelAttentionBackend`. Oberfläche und
  Skill setzen `schnell: true`, solange die Werkstatt `video_schnell_verfuegbar` meldet; eine Szenenfolge merkt es sich
  für alle Szenen. Gemessen auf einer 3090 (Suprim), 960×544, 5 s, zwei Nummern:

  | Video | ohne | mit | kürzer |
  |---|---|---|---|
  | Schnell (DMAD, 4 Schritte) aus Text | 64,6 s | 49,0 s (beide Nummern) | −24 % |
  | Schnell beste (8 Schritte) mit Referenz | 117,8 s | 83,2–83,6 s | −29 % |
  | Beste (20 Schritte) aus Text | 245,1 s | 167,0 s | −32 % |

  Je Schritt (ohne die Grundzeit für Laden, Text und Dekodieren) nur 55–64 % der Zeit; bei längeren oder größeren
  Videos wächst der Gewinn, weil die Aufmerksamkeit dort den größten Teil ausmacht. Speicher gleich (~23,9 GiB).
  Gleiche Nummer ohne den Knoten bleibt bitgleich; mit ihm entsteht eine leicht andere Fassung derselben Szene:
  gleiche Person (auch aus dem Referenzporträt), gleicher Raum, gleiche Worte, ähnliche Sprechpausen (Lautstärkeverlauf
  bei Nummer 7 0,96–0,99 gleich, bei Nummer 8 0,72–1,0; Whisper hört in 5 von 6 Paaren wortgleich denselben Satz, im
  sechsten haben beide je einen kleinen Versprecher), Gesicht und Haut gleich scharf. Was der Prompt offenlässt, kann
  anders ausfallen: Gesten (eine Hand war einmal bei „ohne“, einmal bei „mit“ ungeschickt abgeknickt – Zufall der
  Fassung) oder die Farbe eines nicht beschriebenen Pullovers. Ältere Videos bleiben bei „Nochmal“ ohne.
  Abschalten: `studio.video.schnelle_aufmerksamkeit.aktiv` auf `false`. Testdateien `Video-Aufm-…` in
  „Werkstatt-Abnahme“. Veda Sparse Attention (Custom Node, nur Ref2VA, sichtbar weicher) ist nicht eingebaut.
- **INT8-Fassungen** (seit 27.09.2026, `int8: true`, ebenfalls automatisch für neue Bildaufträge): Bildmodell
  `qwen_image_2.1_int8_convrot` (7,26 statt 14,23 GB) und Text-Encoder `qwen3vl_8b_int8_convrot` (9,35 statt 17,53 GB),
  die Standardkombination der offiziellen ComfyUI-Vorlagen. Gemessen (27.09.2026, gleiche Nummer): 1328² mit
  schneller Aufmerksamkeit Turbo 12,3 → 7,1 s, Standard (20) 34,6 → 16,5 s; ohne sie 4 MP Turbo 37,8 → 25,5 s,
  Hochskalieren 2 MP 30,6 → 22,4 s. Grafikspeicher auf der 3090 9,1–10,4 statt 15,7–16,9 GiB (Hochskalieren 14,1
  statt 20,5). Bilder gleichwertig: mittlere Abweichung zur BF16-Fassung 0,9–4,1 von 255, Aufbau gleich; Gesicht,
  Hände, Schrift und 4 MP vergrößert verglichen, kein Qualitätsverlust zu sehen. Ältere
  Bilder bleiben bei „Nochmal“ BF16 und pixelgleich (geprüft: `Bild_00076_` → `Bild_00083_`). Abschalten:
  `studio.int8.aktiv` auf `false`.

### LoRAs

| LoRA (Datei in `ComfyUI\models\loras`) | Wofür | Einschalten | Grenzen |
|---|---|---|---|
| Viggle Turbo v0.2.1, 6 Schritte, Rang 128 (`Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors`) | alle Bildarten schneller (Neu, Bearbeiten, Verbessern, Freistellen) | Qualität „Turbo“ (`turbo: true`) | laut Modellkarte bei komplizierten Kompositionen gelegentlich doppelte Figuren; in unseren Tests nicht aufgetreten |
| Elusarcas Detail-Enhancer, Rang 16 (`elusarcas-qwen2-1-detailer-v1.safetensors`) | **schwache Fotos** auffrischen: überbelichtet, unscharf, komprimiert. Stellt Belichtung, Hautstruktur, Falten, Haare wieder her | Häkchen „Details auffrischen“ beim Bearbeiten (`details: true`); Rezept „Foto auffrischen“. Geht mit Turbo | bei **sauberen** Bildern verändert sie Kleinigkeiten (Test: Grasstreifen im Weg, Gesicht retuschierter) – dort „Hochskalieren“ ohne LoRA nehmen. Mit dem offiziellen Turbo-Modell (11.10.2026, Hinweis aus dem Video „Is Qwen Image 2.1 Turbo Actually Good?“: ältere LoRAs übersättigen, Stärke ~0,68): keine Übersättigung – mittlere Sättigung höchstens ~1 Punkt vom Original (wie mit der Viggle-Turbo), schwaches Porträt sauber aufgefrischt, Raum sauberer als mit Viggle (die malte Kritzel auf die Wand); 0,68 am nächsten am Original, 1,0 etwas mehr Detail. Stärke bleibt 1,0; 13 statt 20–29 s. |
| MiniMax-H3 Turbo fl2v (8 Schritte) und ref2v (4 Schritte) | Videos schnell | automatisch bei ≤ 8 Schritten | bei 4 Schritten stark glänzende, orangefarbene Haut (Test 11.10.2026); dort rechnet für neue Aufträge DMAD |
| DMAD full critic (`dmad_minimax_h3_4step_full_critic_comfyui.safetensors`, 1,96 GB, seit 11.10.2026) | **Videos aus Text bzw. Bild in 4 Schritten**: natürlichste Haut, saubere Bewegung, Sprache wortgenau | automatisch für neue Aufträge mit 4 Schritten („Schnell“, `dmad: true`); Sampler `lcm`, Verschiebung 12/2 (Kernknoten `MiniMaxH3SigmaShift`) | nur aus Text/Bild (nicht Referenz, Weiterführen, Szenenfolge); Lizenz wie MiniMax-H3 |
| Character-Swap-LoRA von Akatz Labs, Rang 16 (`h3_character_swap_pro4500_1000.safetensors`, 155 MB, seit 09.10.2026) | **Person im Video tauschen:** hält Raum, Licht und alle anderen Personen näher am Clip (Abweichung zum Original etwa 20–25 % kleiner als ohne) | Häkchen „Person tauschen“ bei „Video mit Referenz“ (`tauschen: true`), Vorschlag „Person tauschen“ setzt die englische Prompt-Vorlage des Autors | genau 1 Clip + 1 Bild; laut Autor kurze Clips ohne Schnitt; Mimik und Timing nicht verlässlich |
| 8-Schritt-LoRA für Ref2VA von alibaba-pai, ComfyUI-Fassung von Kijai (`MiniMax-H3-Ref2VA-Acc-8Step_pruned_comfy.safetensors`, 1,7 GB, seit 09.10.2026) | **Video mit Referenz in 8 Schritten** statt der Turbo-LoRA v0.1: mattere, natürlichere Haut und Farben (Turbo glänzt orange), hält sich enger an das Referenzbild (2 von 2 mit dem Tablet aus dem Bild, Turbo ließ es weg), gleiche Zeit | automatisch für neue Referenz-Videos mit genau 8 Schritten („Schnell beste“, `acc8: true`), **nicht beim Tauschen**; Sampler Euler | keine normale LoRA, sondern „Parallel Decoding Distillation“ (eigene Ausgabeköpfe, die ComfyUI 0.37 über den Sigma-Plan auswertet); nur bei 8 Schritten. Beim Tauschen setzte sie die Figur in 2 von 5 Läufen (beide mit zwei Personen im Clip) zusätzlich ins Bild, statt die Person zu ersetzen. Ältere Videos bleiben bei „Nochmal“ gleich |
| Realism-People-LoRA von fal, Rang 32 (`h3-realism-people-t2v-i2v-r2v.safetensors`, 131 MB, seit 05.10.2026) | **Videos mit Personen:** natürlichere, matte Haut statt Glanz, Gesichter in Nahaufnahme; für Text, Bild und Referenz zu Video und beim Weiterführen | Häkchen „Realistische Personen“ (`realismus: true`); das Auslösewort `r34l1sm` setzt das Studio selbst vor den Prompt (gespeichert bleibt der Prompt ohne). Geht mit Turbo, kostet keine Zeit | **nicht** für Räume ohne Personen: dort 2 von 2 schlechter (Kabel von der Decke, unplausibles Gestell unter der Liege). Mit Porträt als Startbild kein sichtbarer Gewinn |

Geprüft und **nicht** im Studio: CharSheet-/portrait2charref-LoRA (erzwingt ein Blatt mit kopfloser Vorderansicht,
kein Qualitätsgewinn; Datei liegt in Saschas „Downloads“), FLUX.2 [klein] (für Inpainting nicht nötig), automatischer
Shift (kein Gewinn), Sampler `seeds_2` (Abschnitt 8). Am 27.09.2026 auf Auftrag geladen, geprüft und **nicht**
genutzt (Abschnitt 8): Depth Anything 3 (Tiefenkarte, 1,34 GB) und Lucida (Freistellen, 0,88 GB); beide liegen seit
27.09.2026 auf Wunsch im Papierkorb. Der Prompt-Enhancer für Bearbeitungen (`pe_i2i`, 9,47 GB) wurde nicht
geladen: Bearbeitungsprompts sind meist schon genau (Rezepte). Am 05.10.2026 auf Auftrag verglichen und **nicht**
übernommen: Head-Swap-LoRA BFS v1.1 (Alissonerdx, `bfs_head_v1.1_qwen_2.1.safetensors`, Abschnitt 8).

**Hilfsmodelle** (Stufe 3l, alle von Comfy-Org auf Hugging Face, SHA-256 geprüft; Ordner unter `ComfyUI\models`):

| Datei | Ordner | Wofür |
|---|---|---|
| `birefnet.safetensors` (0,44 GB) | `background_removal` | schnelles Freistellen des Hauptmotivs |
| `sam3.1_multiplex_fp16.safetensors` (1,75 GB) | `checkpoints` | Stelle per Wort finden (Verbessern) |
| `sdpose_wholebody_fp16.safetensors` (1,92 GB) | `checkpoints` | Pose-Skelett |
| `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` (9,47 GB) | `text_encoders` | Wunsch ausformulieren |
| `qwen_image_2.1_int8_convrot.safetensors` (7,26 GB) / `qwen3vl_8b_int8_convrot.safetensors` (9,35 GB) | `diffusion_models` / `text_encoders` | INT8-Fassungen für neue Aufträge |
| `rife_v4.25.safetensors` (23 MB, Comfy-Org/frame_interpolation, MIT/Apache, seit 09.10.2026) | `frame_interpolation` | Zeitlupe (Zwischenbilder) |
| `qwen_image_2.1_turbo_int8_convrot.safetensors` (7,26 GB, Comfy-Org/Qwen-Image-2.1, seit 11.10.2026) | `diffusion_models` | Stufe „Turbo“ für neue Bildaufträge |

## 5. Größen und Formate

**Bildformate** (`format`-Kennung → Größe):

| Kennung | Name | Größe |
|---|---|---|
| `quadrat` | Quadrat 1:1 | 1328 × 1328 |
| `hoch45` | Hochformat 4:5 | 1024 × 1280 |
| `hoch916` | Hochformat 9:16 | 928 × 1664 |
| `quer169` | Querformat 16:9 | 1664 × 928 |
| `quer32` | Querformat 3:2 (Foto) | 1584 × 1056 |
| `quer43` | Querformat 4:3 (leichtes Breitformat, seit 09.10.2026; 2 von 2 stimmig, 6–14 s) | 1472 × 1104 |
| `video169` / `video916` | Für Video 16:9 / 9:16 (passt ohne Beschnitt zu einem Video) | 1920 × 1088 / 1088 × 1920 |
| `quadrat_gross` | Quadrat 1:1 · groß (4 MP) | 2048 × 2048 |
| `quer169_gross` | Querformat 16:9 · groß (4 MP) | 2752 × 1536 |
| `hoch916_gross` | Hochformat 9:16 · groß (4 MP) | 1536 × 2752 |
| `banner31` | Banner 3:1 (Webseiten-Kopfbild) | 3072 × 1024 |
| `panorama41` | Panorama 4:1 (sehr breites Kopfbild) | 4096 × 1024 |

Eigene Größe: Vielfache von 16, 256–4096 px je Seite, höchstens 4,3 MP. Über 2 MP planen die Karten 18 + 6 GiB
statt 16 + 2 GiB, auf einer Karte 19 GiB (seit 23.10.2026; passt auf jede der drei Karten). 8 MP bringt laut Quelle Layoutfehler und ist nicht vorgesehen.

**Banner und Panorama** (Test 26.09.2026, Praxisraum und Landschaft je 2 Nummern, Turbo): Aufbau 8 von 8 stimmig,
ohne Dopplungen oder Brüche über die Breite; 3:1 ≈ 26 s, 4:1 ≈ 36 s (mit „schneller rechnen“ 30 s, `Bild_00076_`).
Inhaltlich zweimal nicht sauber: einmal zwei Liegen statt einer (4:1), einmal ein seltsames Liegenbein. Möbel und
Geräte deshalb genau prüfen und 2 Variationen rechnen. Die Freifläche für eine Überschrift („the left third is a calm,
light, empty wall with room for a headline“) gelang in 4 von 4 Praxis-Bannern.

**Bearbeiten „Wie Vorlage 1“** (`groesse_von: vorlage`, `aufloesung`): 1024 ≈ 1 MP (Standard), 1440 ≈ 2 MP,
2048 ≈ 4 MP, jeweils im Seitenverhältnis von Bild 1 (gerundet auf Vielfache von 32).

**Videoformate:** `breit` 960 × 544 (Standard) · `breit_nativ` 1344 × 768 · `hoch` 544 × 960 · `hoch_nativ`
768 × 1344 · `quadrat` 704 × 704 · `quadrat_nativ` 992 × 992. „Nativ“ ist die höchste Auflösung, deutlich langsamer.
**Längen** (Bilder bei 24 fps): 124 ≈ 5 s · 192 ≈ 8 s · 243 ≈ 10 s · 311 ≈ 13 s · 362 ≈ 15 s.

## 6. Rezepte (fertige Prompts)

In der Oberfläche unter „Vorschlag“ bzw. „Vorschlag einsetzen …“; der markierte Teil ist zum Überschreiben gedacht.
Für Agenten: Text übernehmen, anpassen, mit den genannten Einstellungen schicken.

| Rezept | Art und Einstellungen | Text |
|---|---|---|
| Moodboard hoch / breit / quadratisch | `bild` (Neu); setzt Format `hoch916_gross` / `quer169_gross` / `quadrat_gross` und Turbo; Warnung bei unpassendem Format | Englische Rasterbeschreibung mit festen Zeilen und Spalten, sichtbare Texte deutsch in Anführungszeichen (Name, „Aa“, Headline). Volltexte: Moodboard-Skill `references\prompt-recipes.md`. Markiert ist der Name; anpassen: Branche, Motive, fünf Farbnamen, Headline. |
| Hand reparieren | `verbessern`, Hand markieren | Repariere die Hand an der markierten Stelle: eine natürliche, entspannte Hand mit fünf Fingern und richtiger Anatomie, passend zu Hautton und Licht. Alles andere bleibt genau gleich. |
| Etwas entfernen | `verbessern`, Gegenstand markieren | Entferne **den Gegenstand**. An seiner Stelle ist nur die passende Umgebung zu sehen, nahtlos und im gleichen Licht. |
| Kopf nach Vorbild | `verbessern`, Kopf samt Haaren großzügig markieren, Vorbild = Porträt der Person (frontal, hell) | Der Kopf der Frau aus Bild 2: Gesicht, Frisur und Haarfarbe wie in Bild 2. **Sie blickt konzentriert nach unten, ernster Ausdruck**; Größe, Licht und Schärfe passen zum übrigen Bild. – Ausdruck nennen, 2–3 Variationen |
| Logo nach Vorbild | `verbessern`, die Fläche markieren, auf die das Logo soll (nicht zu knapp), Vorbild = Logo-Datei | Das Logo aus Bild 2 als **kleine, saubere Stickerei auf dem Stoff**: Symbol, Farben und Schriftzug genau wie in Bild 2, es folgt dem Stoff und den Falten. – Schriftzug nicht ausschreiben (half nicht); sehr kleine Unterzeilen fallen weg |
| Gegenstand nach Vorbild | `verbessern`, die Fläche markieren, wo er stehen soll (das Ganze muss hineinpassen), Vorbild = Foto, das ihn ganz zeigt | **Auf dem Boden steht der Gegenstand aus Bild 2**, ganz zu sehen und in passender Größe. Form, Farben und Material wie in Bild 2, Licht und Schatten wie im übrigen Bild. – Den Gegenstand benennen („der Sitzpouf aus Bild 2“) |
| Drehblatt (Figur) | `bearbeiten`, 1 Vorlage (Figur ganz zu sehen, am besten freigestellt), Format `panorama41` (4096 × 1024), Turbo; 2 Variationen | Turn the character in image1 into an orthographic 3D modeling reference sheet: a single horizontal row of four equal-width panels, evenly spaced. From left to right: 1) front view. 2) left side view, an exact 90 degree profile, only one eye visible. 3) back view, exactly 180 degrees. 4) right side view, an exact 90 degree profile, only one eye visible. The camera orbits a completely static character: **same standing pose, same clothing** and same head direction in every view, the character never turns toward the camera. Identical outfit, colors, proportions and scale in all views, each character centered in its panel, feet on the same baseline, no overlap between views. Keep the style of image1 exactly. Flat, even lighting, solid black background, no text, no labels. – Haltung und Dinge in der Hand benennen; Rückansicht prüfen; dann „3D-Modell“ |
| Drehblatt (Gegenstand) | wie oben | Turn the object in image1 into an orthographic 3D modeling reference sheet: … 2) left side view, the object rotated exactly 90 degrees so its left side faces the camera. 3) back view, rotated exactly 180 degrees. 4) right side view, rotated exactly 90 degrees the other way. The camera orbits a completely static object: identical shape, colors, materials, proportions and scale in all views … solid black background, no text, no labels. – Lange Kästen (Hochbeet) drehte Qwen nicht (11.10.2026); dafür „3D-Modell“ direkt aus dem Bild |
| Charakterblatt | `bearbeiten`, 1 Vorlage (Person), Format `video169` (1920 × 1088) | Erstelle ein Charakterblatt der Person aus Bild 1. Gesicht, Haare, Hautton, Körperproportionen und realistisches Aussehen bleiben genau erhalten. Kleidung: **ein schlichtes, eng anliegendes weißes T-Shirt, lange blaue Jeans und weiße Sneaker**. Genau vier getrennte Ganzkörperansichten nebeneinander vor einem schlichten hellgrauen Studiohintergrund, von links nach rechts: 1. von vorn, 2. Dreiviertelansicht (halb zur Seite gedreht, das Gesicht noch zu sehen), 3. Profil von der Seite, 4. von hinten. Ganz rechts ein großes Porträt des Gesichts. Gleichmäßiges weiches Studiolicht, fotorealistisch. |
| Figur in neue Szene | `bearbeiten`, Vorlage 1 = Porträt der Figur (frontal, Brustbild), Format der Szene (Standard `quer169`) | Die Frau aus Bild 1 **behandelt in einem hellen, modernen Behandlungsraum die Schulter eines Patienten (Mitte 50, mitteleuropäisch, kurze graue Haare, hellgraues T-Shirt), der auf einer Behandlungsliege aus hellem Holz sitzt. Sie steht seitlich hinter ihm, beide Hände liegen auf seiner rechten Schulter, sie blickt freundlich zu ihm**. Gesicht, Frisur, Haarfarbe und Kleidung der Frau genau wie in Bild 1. Halbnahe Aufnahme, die Kamera steht vor den beiden auf Brusthöhe, das Gesicht der Frau ist gut zu sehen. Fotorealistisch, weiches Fensterlicht, natürliche Hauttextur, ohne Schrift. – Haltung, Blick, Kamera und weitere Personen genau beschreiben (Befunde unten) |
| Person einsetzen | `bearbeiten`, Vorlage 1 = Szene, Vorlage 2 = Person, wie Vorlage 1 | Ersetze **die Frau** in Bild 1 durch die Person aus Bild 2. Gesicht, Haare und Kleidung wie in Bild 2; Umgebung, Licht und Bildausschnitt wie in Bild 1. |
| Kopf tauschen | `bearbeiten`, Vorlage 1 = Bild, das bleibt, Vorlage 2 = Kopf, wie Vorlage 1 | Ersetze den Kopf der Person in Bild 1 durch den Kopf der Person aus Bild 2: Gesicht, Frisur und Haarfarbe wie in Bild 2. Körper, Kleidung, Haltung, Umgebung und Licht bleiben wie in Bild 1; der Kopf passt in Größe und Blickrichtung zum Körper. – Übernimmt oft Blick und Lächeln des Porträts; **bei mehreren Personen „Kopf nach Vorbild“** nehmen (einmal fehlte der zweiten Person der Kopf, Abschnitt 8) |
| Farbe ändern | `bearbeiten`, wie Vorlage 1 | Ändere die Farbe **des Kleides zu einem gedeckten Stahlblau (#4A6FA5)**. Stoff, Falten, Licht und alles andere bleiben genau gleich. – Farbe **mit Namen** nennen, Hex nur in Klammern |
| Andere Perspektive | `bearbeiten`, wie Vorlage 1 | Zeige dieselbe Szene **aus einem tiefen Blickwinkel: Die Kamera steht knapp über dem Boden und blickt nach oben**. Personen, Kleidung, Umgebung und Licht bleiben gleich. |
| Gegenstand ersetzen | `bearbeiten`, wie Vorlage 1 | Ersetze **die Tasse durch ein Glas Wasser**, in gleicher Größe und Lage und im gleichen Licht. Alles andere bleibt genau gleich. |
| Pose übernehmen | `bearbeiten`, Vorlage 1 = Pose-Skelett (Art `pose`), Vorlage 2 = die Person (etwa ein Porträt), wie Vorlage 1 | Bild 1 zeigt ein Pose-Skelett. **Die Person aus Bild 2 steht in genau dieser Körperhaltung in einem hellen Trainingsraum mit Holzboden.** Gesicht, Haare und Kleidung wie in Bild 2. Fotorealistisch, weiches Fensterlicht. – Haltung zusätzlich kurz in Worten nennen; Geräte (Übungsband) genau beschreiben; ohne Bild 2 die Person beschreiben |
| Logo aufbringen | `bearbeiten`, Vorlage 1 = Bild, Vorlage 2 = Logo-Datei (PNG auf hellem Grund), wie Vorlage 1 · 2 MP | Bringe das Logo aus Bild 2 **als kleine, saubere Stickerei auf die linke Brustseite der Kleidung der Person in Bild 1** an. Symbol, Farben und Schriftzug genau wie in Bild 2, gut lesbar. Alles andere bleibt genau gleich. – Schriftzug **nicht** ausschreiben; auf Glas dazu: „Die Scheibe bleibt durchsichtig, der Raum dahinter bleibt zu sehen.“ |
| Hochskalieren | `bearbeiten`, 2 MP (`aufloesung` 1440) oder 4 MP (2048), **ohne** Detail-LoRA | Gib genau dieses Bild in hoher Auflösung wieder. Schärfe feine Details wie Haut, Haare, Stoff und Kanten natürlich nach und entferne Unschärfe, Rauschen und Kompressionsspuren. Inhalt, Personen, Farben, Licht und Bildausschnitt bleiben genau gleich. |
| Als Garten-Illustration (seit 12.10.2026) | `bearbeiten`, ein Foto als Vorlage 1, wie Vorlage 1, ohne LoRA (Skill: `garten`) | Zeichne das Bild als Garten-Illustration: klare dunkle Konturen, flächige kräftige Farben, weiche Schatten; kein Foto, kein 3D. – Bildaufbau, Personen und Farben bleiben; graues, verwittertes Holz wird dabei honiggelb |
| Foto auffrischen | `bearbeiten`, 2 MP, `details: true` | Enhance this image to high resolution with rich fine details. Sharpen textures and surfaces, add natural microdetails, and improve clarity and definition across the image while preserving the original composition, lighting, atmosphere, and visual style. The input may be an illustration or a real photograph; preserve the original style. – Was genau bleiben soll, am Ende nennen (etwa „The round grey ring on the zipper stays.“) |
| Freistellen | `freistellen` mit Beschreibung (Qwen); das Studio setzt ein: | Isolate the main subject: keep only **{motiv}**, exactly as it is. Remove everything else completely, including the whole background and the ground, so that the background is fully transparent. Output a PNG image with a transparent background. (ohne Beschreibung rechnet BiRefNet ohne Text; ältere Aufträge ohne Beschreibung: „the main subject“) |
| Wunsch ausformulieren | `bild` mit `ausformulieren: true`; das Studio setzt ein: | Systemtext aus der offiziellen ComfyUI-Vorlage `image_qwen_image_2_1_t2i` (englisch, rund 10 300 Zeichen, `werkstatt\ausformulieren_t2i.txt`: acht Schritte, ein englischer Absatz, sichtbare Texte in ihrer Sprache) + der Wunsch als Nutzertext; das Sprachmodell antwortet ohne Nachdenken (`<think>` leer) |
| Durchsichtiger Hintergrund | `bild` mit `durchsichtig: true`; das Studio setzt ein: | This is an RGBA format image with transparency. **{beschreibung}**. The image has an alpha channel and a transparent background. (Beschreibung deutsch oder englisch; ein Punkt am Ende fällt weg) |

Weitere geprüfte Anwendungen ohne eigenes Rezept: freigestelltes Motiv in eine neue Szene setzen („Setze die Frau
aus Bild 1 an einen Sandstrand bei Sonnenuntergang. Die Frau, ihr Kleid und ihre Haltung bleiben genau gleich; Licht
und Schatten passen zur neuen Umgebung.“), Tageszeit ändern („Derselbe Raum am Abend, warmes Licht …“), Gegenstand
ergänzen („Gleicher Raum, aber mit einer großen grünen Zimmerpflanze neben der Liege“).

Befunde zu „Figur in neue Szene“ und „Logo aufbringen“ (24.09.2026, Turbo; alle Bilder in Werkstatt-Abnahme):

- **Figur:** Mit dem Porträt `Bild_00027_` als Vorlage war die Frau in jeder Szene klar dieselbe Person: Behandlung,
  Empfang, Übung 6 von 6 (`Bearbeitet_00039_`–`_00044_`), das Rezept über die Oberfläche 2 von 2 (`_00062_`,
  `_00063_`, Hände sauber). Nur beschrieben, ohne Porträt: 2 von 2 eine andere Frau (`Bild_00029_`, `_00030_`).
- **Der Wortlaut zählt:** Ohne Angaben zu Haltung und Kamera stand die Figur 2 von 2 nur lächelnd im Raum, statt zu
  behandeln (`_00057_`, `_00058_`). Mit „die Person aus Bild 1“ und einem nicht beschriebenen Patienten erschien sie
  einmal doppelt, auch als Patientin (`_00061_`). Das Rezept beschreibt deshalb Haltung, Blick, Kamera und die zweite
  Person genau.
- **Grenzen:** Blick und Lächeln des Porträts schlagen durch (am Empfang schaute sie 2 von 2 in die Kamera). Eine
  bestimmte Handlung mit zwei Personen („zeigt einem Mann eine Übung“) scheiterte 2 von 2 (Abschnitt 8). Dafür erst
  die Szene aus Text oder Foto, dann „Person einsetzen“ mit dem Porträt als Bild 2, ergänzt um „Haltung, Hände und
  Blickrichtung der Frau, Umgebung, Licht und Bildausschnitt bleiben wie in Bild 1.“ 2 von 2: Aufbau und Hände blieben,
  das Gesicht wurde die Figur (`_00051_`, `_00052_`); einmal lächelte sie danach eher zur Kamera.
- **Logo** (erfundenes Test-Logo `Vorlage_Logo-Test.png`): Symbol und Schriftzug waren in allen 11 Bildern richtig
  (Stickerei, Schaufenster, Tasse).
  - Stand der Hauptschriftzug wörtlich im Text, hatte die kleine Unterzeile auf Stoff 2 von 2 Fehler („fiür“,
    „Praxls“; `_00045_`, `_00046_`). Ohne ausgeschriebenen Schriftzug war sie 3 von 3 richtig (`_00053_`, `_00054_`,
    über die Oberfläche `_00059_`). Deshalb schreibt das Rezept den Schriftzug nicht aus.
  - Aus „Folienbeschriftung auf der Schaufensterscheibe“ wurde 2 von 2 Milchglas über der ganzen Scheibe (`_00047_`,
    `_00048_`). Mit dem Zusatz „Die Scheibe bleibt durchsichtig, die Pflanzen und der Raum dahinter bleiben zu sehen.“
    blieb sie 2 von 2 durchsichtig, einmal leicht milchig (`_00055_`, `_00056_`).
- **Moodboard** (Vorschläge „Moodboard hoch/breit/quadratisch“ seit 25.09.2026; Plan und Review mit Astra:
  `C:\Workstation\AI-Knowledge-System\Workspace\Handoffs\2026-09-25 Moodboard Studio …`; alle Bilder in
  Werkstatt-Abnahme, Turbo, 4 MP, je ≈ 37 s; gezählt wurden harte Fehler nach den Regeln des Moodboard-Skills):
  - v1 (deutsch, nur nummeriert, 1328²): 2 von 2 brauchbar, aber Mockup-Kleinschrift Kauderwelsch, einmal ein
    unplausibles Gerät, einmal eine leere Kachel (`Bild_00031_`, `_00032_`).
  - v2 (Zeilen mit Positionen, Texte nur in Anführungszeichen, Platzhalterbalken): Struktur 10 von 10; englisch 0 von 3
    mit Kleinschrift, deutsch 3 von 3 (`Bild_00033_`–`_00042_`).
  - Feste Variationsnummern, Quadrat: alter Prompt 2 von 2 mit Fehlern, v3 englisch 0 Fehler, v3 deutsch mit gleichem
    Inhalt 2 von 2 mit Fehlern (Textur als Extra-Kachel, sechs Farbfelder) – deshalb Englisch (`Bild_00043_`–`_00048_`).
  - Hochformat 2:3 0 von 2 fehlerfrei (leere Kachel, doppelte Geräte); 9:16 mit hoher halber Mockup-Kachel 1 von 2 –
    deshalb Mockup als volle unterste Zeile (`Bild_00049_`–`_00054_`, `_00055_`–`_00057_`).
  - Standard (20 Schritte) statt Turbo im Querformat: 115 statt 37 s, sichtbar kaum Gewinn (`Bild_00060_`, `_00061_`).
  - Hundezucht mit „von der Helmerotherhöhe“: 2 von 2 fehlerfrei, Umlaut richtig (`Bild_00058_`, `_00059_`).
  - Sechs statt fünf Farbfelder kamen mehrfach vor (auch Weiß neben Gebrochenweiß) → Palettensatz mit getrennten Feldern,
    Abständen und Kontur am hellen Feld. Die Textur zerfiel im Hochformat einmal in zwei Kacheln → „a single texture
    tile with one close-up photo of natural linen fabric draped over light oak wood“.
  - **Endstand (eingefroren):** Quadrat und Quer mit den Nummern 11, 22, 33 fehlerfrei (`Bild_00062_`–`_00067_`), Hoch
    mit 11, 22, 55 fehlerfrei (`Bild_00071_`–`_00073_`); Probe über die Oberfläche mit zufälliger Nummer fehlerfrei
    (`Bild_00074_`, Export als WebP geprüft).
  - **Nachprüfung mit INT8** (27.09.2026, gleiche Prompts und Nummern über den Skill, 17–22 s statt ~37 s): Quer 11, 22,
    33 fehlerfrei (`Bild_00086_`, `_00093_`, `_00094_`), Hoch 11 fehlerfrei (`_00087_`). Im Quadrat zerfiel die
    Texturkachel („natural linen next to light oak wood“) 2 von 3 in zwei Kacheln (11 und 33: `_00085_`, `_00089_`;
    22 fehlerfrei `_00088_`). Mit der Formulierung aus dem Hochformat („a single texture tile with one close-up photo of
    natural linen fabric draped over light oak wood“) 3 von 3 fehlerfrei (`_00090_`–`_00092_`); das Quadrat-Rezept
    nutzt sie seitdem.
  - Aus eigenen Bildern (`bearbeiten`, 4 Vorlagen: Raum, Porträt, Eingang, Logo; `quadrat`): Bilder und Logo kamen
    unverändert hinein, aber Dubletten (ohne Regel 2 von 2, mit „Jedes Bild erscheint genau einmal …“ 1 von 2;
    `Bearbeitet_00064_`–`_00067_`). Kein Vorschlag; dafür baut der Moodboard-Skill ein **Hybrid-Board** (Studio-Bilder
    unverändert, Raster, Schrift und Hex-Farben als HTML, Ausgabe per Edge als PNG).
- **Neue Szene nur aus dem Logo** (Vorlage 1 = Logo, Größe `quadrat`): „Nahaufnahme: Eine weiße Keramiktasse … Auf der
  Tasse ist das Logo aus Bild 1 aufgedruckt: … genau wie in Bild 1, gut lesbar und der Rundung der Tasse folgend.“
  2 von 2 richtig samt Unterzeile (`_00049_`, `_00050_`).

## 7. Prompts schreiben

**Bilder (Qwen-Image 2.1)**
- Deutsch und Englisch funktionieren. Konkret beschreiben: Motiv, Handlung, Umgebung, Licht, Kamera/Blickwinkel,
  Stil. Für Fotos: „fotorealistisch, natürliche Hauttextur, weiches Fensterlicht, 35-mm-Objektiv“.
- **Aussehen jeder Person nennen** (seit 08.10.2026): Alter, Herkunft bzw. Typ, Haare, bei Bedarf Haut- und
  Augenfarbe, etwa „mitteleuropäische Frau Ende 30, helle Haut, hellbraunes schulterlanges Haar“ – auch Patienten,
  Kunden und Personen im Hintergrund. Für Saschas Praxis- und Webseitenmockups meist „mitteleuropäisch“; ein gemischtes
  Team bewusst so beschreiben. Anlass: Sascha fielen Bilder mit leicht asiatischem Einschlag auf, wenn nichts zum
  Aussehen dastand. Ohne Angabe füllt Qwen mit seinem Durchschnitt (Vermutung: viel Material aus China im Training; Qwen stammt von Alibaba). Test
  08.10.2026 (Turbo, `hoch45`, Nummern 11/22/33/44, Projekt „Werkstatt-Abnahme“):

  | Prompt | ostasiatisch | Bilder |
  |---|---|---|
  | ausführlich deutsch: Physiotherapeutin Ende 30, Praxiskleidung, Brustbild (ohne Aussehen) | 0 von 4 | `Bild_00094_`–`_00097_` |
  | dasselbe mit „mitteleuropäisches Aussehen, helle Haut, hellbraunes Haar, blaugraue Augen“ | 0 von 4 | `_00098_`–`_00101_` |
  | ausführlich deutsch: Physiotherapeut Mitte 40, Poloshirt (ohne Aussehen) | 0 von 4 | `_00102_`–`_00105_` |
  | „Porträt einer jungen Frau“ | 0 von 4 | `_00106_`, `_00109_`, `_00112_`, `_00115_` |
  | „portrait photo of a young woman“ | **1 von 4** (Nummer 33) | `_00107_`, `_00110_`, `_00113_`, `_00116_` |
  | „Eine junge Frau in einem Café“ + Ausformulieren | **1 von 4** (Nummer 22) | `_00108_`, `_00111_`, `_00114_`, `_00117_` |
  | Kontrolle: „portrait photo of a young Central European woman“, Nummer 33 | 0 von 1 | `_00118_` |
  | Kontrolle: „Eine junge mitteleuropäische Frau in einem Café“ + Ausformulieren, Nummer 22 | 0 von 1 | `_00119_` |

  Der Effekt ist also echt, kam aber nur bei knappen Prompts vor (2 von 12, ausführliche 0 von 12); die Angabe des
  Aussehens behebt ihn (2 von 2 bei denselben Nummern). Die Angabe kostet nichts, deshalb immer. Bei Videos aus Text (MiniMax-H3) genauso schreiben
  (dort nicht getestet). Mit einer Figur als Vorlage kommt das Aussehen aus dem Bild; das Rezept „Figur in neue Szene“
  nennt seit 08.10.2026 auch beim Patienten „mitteleuropäisch“ (2 von 2 wie beschrieben, `Bearbeitet_00001_`–`_00002_`).
  Automatisch in jeden Prompt eingefügt wird nichts.
- **Kein Negativ-Prompt:** Das Studio rechnet mit CFG 1, dabei überspringt ComfyUI den Negativ-Prompt ganz (geprüft
  im Quelltext, `comfy/samplers.py`). Das Feld „Vermeiden“ ist deshalb seit 24.09.2026 entfernt; ältere Bilder behalten
  ihren Eintrag in der `.json`. Ausschlüsse in den Haupttext schreiben: „ohne Schrift, ohne Logos, ohne Wasserzeichen“.
- Mehrteilige Layouts **nummerieren** („von links nach rechts: 1. …, 2. …“) – dann hält Qwen Reihenfolge und Anzahl.
- Beim Bearbeiten sagen, was **gleich bleibt** („Alles andere bleibt genau gleich“) und Dinge benennen, die leicht
  verloren gehen („der runde graue Ring am Reißverschluss bleibt“, „er trägt eine Lederhose über der Jeans“).
- Farben mit **Namen** („gedecktes Stahlblau“, „kräftiges Ziegelrot“), Hex-Code höchstens in Klammern.
- **Schrift:** Große Schrift gelingt meist. Kleine Beschriftungen gelingen, wenn jeder Text **wörtlich in
  Anführungszeichen** steht und die Anzahl klar ist. Test 26.09.2026: Styleguide-Blatt 1664 × 928 mit 14 Texten (fünf
  Farbnamen, fünf Hex-Codes, zwei Überschriften, zwei Schriftzeilen), 8 Bilder: Hex-Codes 40 von 40 richtig,
  Farbnamen 39 von 40. Eigennamen gehen oft schief („Segoe UI“ 7 von 8 falsch geschrieben), aber auch einfache Wörter
  („Farbpalette“ 2 von 8). Jedes Bild hatte 1–2 Fehler, auch mit Standard statt Turbo. Texte deshalb immer Zeichen für
  Zeichen prüfen; was stimmen muss (Webseiten, Styleguides mit exakter Schrift), weiter im HTML setzen (Hybrid-Board
  des Moodboard-Skills).
- Freifläche für Text einplanen: „linke Bildhälfte ruhig und hell, Platz für eine Überschrift“ (gelang in Tests bei
  etwa der Hälfte der Variationen – deshalb mehrere rechnen). Im Banner 3:1 und 4:1 mit „the left third is a calm,
  light, empty wall with room for a headline“ 4 von 4 (Abschnitt 5).
- Kameraposition ausdrücklich beschreiben, wenn sie wichtig ist: „steht mit dem Rücken zur Kamera, die Kamera steht
  schräg hinter ihr“ wirkte (2 von 2), „seitlich von hinten gesehen“ nicht (0 von 2).
- Dinge genau benennen: „flaches, glattes, straff gespanntes Übungsband aus Latex“ statt „Übungsband“ (kam als
  Stoffband oder Schal).
- Hände, mehrere Personen, Mechanik: 3 Variationen einplanen und genau prüfen (einmal drei Hände; Liegengestelle
  oft unplausibel). Einzelne Fehler mit „Stelle verbessern“ beheben. Jeden Finger einzeln zu beschreiben („der
  Zeigefinger ist ausgestreckt, Mittel-, Ring- und kleiner Finger sind eingerollt …“, Tipp aus einem Video) brachte
  keinen Gewinn: Zeigen auf ein Poster und Hände auf einer Schulter, je 2 Nummern, mit und ohne Beschreibung 8 von 8
  plausible Hände (26.09.2026).
- **Stil übertragen:** den Stil in Worten beschreiben („loose watercolor painting, visible brush strokes, soft wet
  edges, white paper showing through, muted blue and ochre tones“). Ein Bild als Stil-Vorlage übernimmt meist dessen
  Inhalt (Abschnitt 8); ohne Vorlage war das Ergebnis gleich gut.
- **Vorlage statt Erfinden:** Schwierige Haltungen, Übungen mit Geräten oder ein genauer Bildaufbau gelingen aus Text
  oft nicht. Dann ein Foto mit der richtigen Haltung als Vorlage 1 nehmen („Bearbeiten“, wie Vorlage 1) und nur das
  Gewünschte ändern: „Ersetze die Frau durch einen Mann Mitte 30 …; das Band wird orange. Haltung, Hände, Band,
  Bildaufbau, Raum und Licht bleiben genau gleich.“ Personen, Gesichter, Kleidung, Farben und Hintergrund lassen sich so
  tauschen (geprüft mit „Person einsetzen“, „Kopf tauschen“, „Farbe ändern“, „Gegenstand ersetzen“ und einem
  freigestellten Motiv in neuer Szene: Aufbau und Haltung blieben jeweils erhalten). Bilder aus dem Chat legt der Skill
  mit `studio.py chatbild` als `Vorlage_<Zeit>` ins Projekt.
  Hintergrund neutral machen (14.10.2026, Buchcover-Vorlage „Magazin“): ein Foto aus dem Codex-Bildwerkzeug mit
  lindgrünem Studiohintergrund, „Ersetze den kräftig gelbgrünen Hintergrund durch einen ruhigen, einfarbig hellgrauen
  Studiohintergrund … beide Personen, Gesichter, Haare, Brille, Kleidung, Haltung, Hände, Bildausschnitt und Licht
  bleiben genau gleich“, `--groesse 2mp`: 2 von 2 sauber, 11–20 s (Projekt „Cover Praxiswissen“, `Bearbeitet_00001_`
  und `_00002_`). So passt ein festes Foto zu jeder Themenfarbe, ohne neu zu rechnen.
  Probe 24.09.2026 (je 1 Versuch, Turbo, 14–18 s, ≈1 MP): Therapeutin und Patient gleichzeitig getauscht
  (`Bearbeitet_00036_`), Frau gegen Mann mit orangem Band (`_00037_`), Wände und Polster umgefärbt (`_00038_`, alle in
  Werkstatt-Abnahme). Haltung, Hände, Band, Liegengestell, Raum und Licht blieben jedes Mal wie in der Vorlage –
  **auch deren Fehler** (die seltsam hängenden Bandenden aus `Bild_00019_` blieben). Also ein echtes Foto als Vorlage,
  kein misslungenes KI-Bild. Farben natürlich beschreiben: „rote Haare“ wurde knallig gefärbt.
  **Nur die Haltung übernehmen** (andere Person, anderer Ort): aus dem Foto ein Pose-Skelett machen und damit „Pose
  übernehmen“ (Abschnitt 3); die Haltung zusätzlich kurz in Worten nennen, Geräte genau beschreiben.
- **Kurzer Wunsch statt ausgefeilter Beschreibung:** Häkchen „Wunsch ausformulieren lassen“ (Abschnitt 3). Bringt bei
  knappen Wünschen stimmigere Szenen, erfindet aber Details (Hunderasse, Wandsprüche, Poster). Wer keine Schrift will,
  schreibt „ohne Schrift“ in den Wunsch. Die ausformulierte Fassung steht in der Großansicht; wer sie verfeinern will,
  kopiert sie als eigenen Prompt und rechnet ohne Häkchen („Mit Änderungen“ übernimmt nur Wunsch und Häkchen).
- **Stelle per Wort** (Verbessern): englische Wörter nehmen („hand“, „face“, „cup“, „left hand“), mehrere gleiche Dinge
  mit Anzahl („hand:2“). Den eigentlichen Auftrag schreibt man wie gewohnt in den Text („Repariere die Hand …“).
- **Verbessern: beschreiben, was dort ist,** statt von der „markierten Stelle“ zu sprechen – Qwen sieht die Markierung
  nicht. Einmal (1 von 11 Läufen mit „An der markierten Stelle …“, ohne Vorbild) malte es eine blaue Kreidelinie auf den
  Boden. Die Vorschläge mit Vorbild sind deshalb ohne diese Worte geschrieben.
- **Dieselbe Person oder ein Logo in mehreren Bildern:** nicht beschreiben, sondern als Bild mitgeben (Rezepte „Figur
  in neue Szene“ und „Logo aufbringen“, Abschnitt 6; für genau eine Stelle eines fertigen Bildes „Kopf/Logo nach
  Vorbild“). Nur beschrieben kam jedes Mal eine andere Frau heraus, ohne Logo-Datei ein erfundenes Logo (4 von 4).
- **Dichte Raster (Moodboards):** englisch mit festen Zeilen und Spalten beschreiben, sichtbare Texte deutsch in
  Anführungszeichen, Zahl der Felder und Geräte ausdrücklich nennen („exactly five separate … swatches with small
  gaps“, „exactly one laptop and one smartphone“), mit „Only the quoted words appear as text …“ schließen. Deutsch
  brachte im selben Aufbau Kleinschrift und Extra-Kacheln (Abschnitt 6, Moodboard).
- Gleicher Stil über mehrere Bilder: denselben Stil-Zusatz an jeden Prompt hängen (Licht, Farbwelt, Kamera, Stimmung).
- **Mehrere Szenen (Szenenfolge, Video):** gemeinsamer Teil = Figuren, Ort, Licht, Stil, Kameraabstand; Szene = Handlung,
  Kamera, Gesprochenes. Gesprochenes nie in den gemeinsamen Teil (sonst sagt die Figur es in jeder Szene).
- Mehrere Variationen (`anzahl` 2–4) und die beste nehmen; Feinkorrekturen danach mit Bearbeiten oder Verbessern.

**Videos (MiniMax-H3)**
- Beschreiben: wer zu sehen ist, wie der Ort aussieht, was geschieht, was die Kamera tut, was gesagt wird.
- Gesprochenes als `<d>[Deutsch] …</d>`, 20–24 Wörter je 8 s; „scharfes Bild“ verlangen.
- Für Hintergrundvideos auf Webseiten: ruhige, gleichmäßige Bewegung (langsame Kamerafahrt), keine Schnitte, kein
  Gesprochenes; der Ton wird beim Export entfernt.
- **Weiterführen:** Ort, Personen und Licht wie im Clip beschreiben, dazu, was als Nächstes geschieht. Die Bewegung
  der letzten 1,6 s setzt sich stärker durch als der Prompt: Fuhr die Kamera am Ende auf eine dunkle Tür zu, fuhr sie im
  neuen Stück weiter darauf zu, obwohl „an den Pflanzen vorbei“ im Prompt stand (`Video_00012_`) – ein unpassendes Ende
  vorher mit „Ende des Clips kürzen um“ weglassen. Beim Davor-Setzen und Verbinden Licht und Stimmung des Clips danach
  beschreiben und beim Verbinden den Weg dorthin (Abschnitt 3, „Videos weiterführen im Detail“).

## 8. Was nicht geht (geprüft)

| Versuch | Ergebnis |
|---|---|
| **Eigenes Edit-LoRA „Garten-OS-Stil“ v1** (12.10.2026, AI Toolkit, 20 Paare Foto → Illustration, Rang 64, 512 px, 1.000 Schritte; PLAN.md, Stufe 5) | kein Gewinn: Schon die Anweisung allein liefert denselben Stil wie die Trainingsziele (Foto + Stilvorlage) – auch bei Trainingspaaren sind Ziel, „ohne LoRA“ und LoRA praktisch gleich. Mit LoRA (alle Stände 250–1.000, Turbo und 20 Schritte) eher weicher und gemalter, Farben etwas näher am Foto. Nicht übernommen; stattdessen Rezept „Als Garten-Illustration“ |
| **LightX2V fl2v 4-step v1.2 768p** bzw. **DMAD lora critic** als „Schnell“ (11.10.2026) | LightX2V schliert bei 960 × 544 (auf 1344 × 768 trainiert) und sprach einmal „Lacken“ statt „Nacken“; DMAD lora critic ließ in 1344 × 768 eine Bank mitten auf der Laufbahn auftauchen. Geladen bleiben beide, genutzt wird DMAD full critic |
| **Haut-Prompt** „matte Haut mit sichtbaren Poren, feinem Flaum und ein paar Sommersprossen, leicht ungleichmäßiger Teint, weiches, gleichmäßiges Licht“ (DMAD, gleiche Nummer, 11.10.2026) | mehr Struktur und Sommersprossen, aber nicht matter (Stirn und Nase eher glänzender). Für matte Haut zählt das Modell (DMAD, Realism-LoRA) mehr als der Text |
| **FLUX.2 Klein 4B als Hautauffrischer** (09.10.2026; Video „Qwen Image 2.1 + FLUX Klein“, auf Auftrag geladen: `flux-2-klein-base-4b`, `qwen_3_4b`, `flux2-vae`, zusammen 16 GB, SHA-256 geprüft) | auf 4 MP vergrößert, dann die letzten 2 bzw. 3 von 8 Schritten (Euler, CFG 1, Bild als Referenz, Farbangleich), 22–30 s: Gesichter bleiben genau gleich, aber nur beim scharfen Porträt sichtbar mehr Hautstruktur; bei Behandlungsszene und zweitem Porträt kaum Unterschied zum bloßen Vergrößern, 3 Schritte eher glatter. Qwen „Hochskalieren 4 MP“ (61 s) zeichnet schärfer, verändert Gesichter aber leicht. Nicht eingebaut; die 9B aus dem Video (gesperrt, nicht gewerblich) wurde nicht geprüft |
| **8-Schritt-LoRA beim Person-Tauschen** (09.10.2026) | 2 von 5 Läufen setzten die Figur zusätzlich groß ins Bild (mit dem Tablet aus dem Referenzbild), statt die Frau zu ersetzen – auch ohne Character-Swap-LoRA. Getauscht wird deshalb mit Turbo |
| **„16-Bilder/s-Trick“** (Video „One LoRA Can't Run a Whole Film“) | passt nicht zu MiniMax-H3: Länge fest bei 24 Bildern/s, der Ton hängt daran. Stattdessen „Zeitlupe“ für Videos ohne Ton |
| **20 Schritte ohne Turbo beim Tauschen** | Hintergrund 9,2 statt 10,6–11,3 (Turbo) bzw. 7,9–8,3 (8-Schritt-LoRA), aber 17 statt 8 min |
| Fremde **Pose** aus einem Foto übernehmen (Person aus Bild 2 in Pose von Bild 1) | nur manchmal (1 von 4 nah dran). Seit 27.09.2026 stattdessen erst ein Pose-Skelett aus dem Foto, dann „Pose übernehmen“: 12 von 12 (Abschnitt 3) |
| **Übung mit Gerät nur aus Text** (Frau mit Übungsband) | unbrauchbar: Band quer über den Augen, zweites Band vor der Brust, Schlaufen um die Handgelenke; auch Rückenansichten mit herumhängenden Schlaufen. Stattdessen Foto der Übung als Vorlage (Abschnitt 7) |
| **Muster aus einer flachen Mustervorlage** auf eine Wand übertragen | 0 von 7: Qwen gibt nur das Muster aus (deutsch, englisch, „Bild 1/2“, `<image1>/<image2>`, „replace the texture …“) |
| **Hex-Code allein** für Farben | unzuverlässig: #B03A2E wurde Oliv, #4A6FA5 grelles Petrol; deutsch „Hex-Farbe B03A2E“ wurde Blau. Mit Farbnamen stimmte es |
| **Negativ-Prompt** (früheres Feld „Vermeiden“) | wirkt bei CFG 1 nicht; Feld entfernt (Abschnitt 7) |
| Detail-LoRA auf **sauberen** Bildern | verändert Inhalt (Grasstreifen im Weg); nur für schwache Fotos |
| **8 MP** | laut Quelle Layoutfehler; Studio begrenzt auf 4,3 MP |
| Vorlage klein lassen, nur die Fläche vergrößern (Workflow Ep33) | ein Viertel schneller, aber Gesichtsausdruck weicht ab; nicht übernommen |
| **Handlung mit zwei Personen direkt aus einem Porträt** („Die Frau aus Bild 1 zeigt einem Mann eine Übung …“) | 0 von 2: Rollen vertauscht bzw. Beine unplausibel, keine Übung zu sehen; das Gesicht blieb erkennbar. Stattdessen erst die Szene, dann „Person einsetzen“ (Abschnitt 6) – oder die Szene aus einem Zwei-Personen-Skelett eines passenden Fotos (Abschnitt 3, „Pose übernehmen“) |
| **Bild als Stil-Vorlage** (Bearbeiten, eigene Fläche; „im Stil von Bild 1 … aber nicht seinen Inhalt“, „Use <image1> as a style reference only; do not copy its content …“) | 0 von 10 mit gegenständlicher Vorlage (Aquarell-Leuchtturm, flache Grafik mit Fahrrad): Leuchtturm bzw. Fahrrad kamen jedes Mal wieder, die gewünschte Szene höchstens winzig dazu; Vorlage in 512 statt 1024 px änderte nichts. Abstrakte Aquarell-Textur als Vorlage 1 von 2, ohne Vorlage gleich gut. Stil in Worten beschreiben (Abschnitt 7) |
| **Schnelles Hochskalieren per Bild zu Bild** (×2 Lanczos, 6 Schritte, denoise 0,25–0,35; aus einem Video) | ergibt 5–6 MP, aber nur leicht schärfer als das hochgezogene Original; 50–66 s. Mit Turbo 21–27 s, dafür weich und glatt. Nicht übernommen; „Hochskalieren“ (Abschnitt 6) holt mehr Details (2 MP Turbo ≈ 32 s, 4 MP Turbo 84–87 s) |
| **Sampler `seeds_2`** für Kleinschrift (16 Schritte; aus einem Video) | kein Gewinn: gleiche Fehlerzahl wie Turbo, 50 statt 12–23 s (mit Turbo 19 s). Nicht übernommen |
| **Tiefenkarte als Vorlage** (Depth Anything 3, 27.09.2026: Behandlungsraum → Wartezimmer, 2 Nummern) | kein Gewinn: Raumaufbau blieb, aber die Liege auch (ihre Form steckt in der Tiefe); mit dem Foto selbst als Bild 1 gleich gut und mit mehr Einzelheiten. Beim Eingang mit Schaufenster war die Tiefenkarte fast leer. Nicht eingebaut |
| **Lucida** statt BiRefNet zum Freistellen (27.09.2026, sechs Bilder) | 2 von 6 mit Resten: milchiger Schleier des Kissens unter dem Hund, ein Stück Liege in der Praxis. BiRefNet war überall sauber. Nicht eingebaut |
| **Prompt-Enhancer auf der 3080** (neben dem Text-Encoder) | 517 s statt 15–34 s, weil das Modell teils im Arbeitsspeicher lag. Er läuft deshalb fest auf der 3090 |
| **Stelle per Wort auf Deutsch** | nur teilweise: „Hund“, „Fahrrad“, „Hand“ gingen, „Liege“ fand die Therapeutin. Englische Wörter nehmen |
| **Übungsband mit Pose-Skelett** | Haltung stimmt, das Band nicht immer: hing 3 von 4 Mal wie ein Schal, lag vor dem Gesicht, wenn die Hände im Vorbild auf Augenhöhe waren (4 von 4). Band genau beschreiben, mehrere Variationen, Fehler mit „Stelle verbessern“ |
| **Head-Swap-LoRA BFS v1.1** statt „Kopf tauschen“ (05.10.2026, 3 Bildpaare, je 2 Nummern) | Gesichter nicht ähnlicher (frontal sogar weniger); dafür Blick, Ausdruck und andere Personen besser gehalten. Nicht übernommen – für Szenen mit mehreren Personen „Kopf nach Vorbild“ (Verbessern) |
| **„Kopf tauschen“ in einer Szene mit zwei Personen** (Bearbeiten, `Bild_00008_` ← Porträt) | 1 von 2 fehlte dem Patienten danach der Kopf; 2 von 2 schaute die Therapeutin lächelnd in die Kamera statt auf den Arm. Stattdessen „Kopf nach Vorbild“: nur die markierte Stelle, Blick im Text („blickt nach unten“) |
| **Weiterführen: am Ende mehrere Bilder festhalten** (39 Bilder des Clips danach, Vorversuch 27.09.2026) | harter Schnitt direkt vor dem festgehaltenen Stück (Sprung 39 bei normal 1), auch mit Prompt für dieselbe Einstellung; mit 5 Bildern Ruckeln. Stattdessen ein einzelnes Endbild (Abschnitt 3) |
| **Schleife mit zwei festgehaltenen Stücken** (Ende des Clips vorn, Anfang hinten) | zwei harte Schnitte (Sprung 104 und 58). Stattdessen vorn das Stück, hinten das erste Bild als Endbild |
| **Ton des Clips danach mit anheften** | stört das Bild nicht, liegt aber zeitlich falsch; nicht übernommen – der Ton wechselt am Übergang hart |
| **Verbinden verschiedener Orte ohne beschriebenen Weg** (Abnahme 27.09.2026) | harter Schnitt im letzten Bild (`Video_00011_`, Sprung 60 bei sonst 2). Mit beschriebenem Weg und längerem Stück weich (`Video_00015_`, Abschnitt 3) |
| **PTD-Beschleuniger für Referenz-Videos** (Taobao, 4 und 8 Schritte; 24.10.2026 nur geklärt, nicht geladen) | nicht mit Kernknoten: braucht ComfyUI-PTD mit eigenem Sampler und für unser gekürztes INT8-Ref2VA-Modell zusätzlich einen Lader aus einem Ein-Personen-Projekt; die Hersteller nennen gekürzte und quantisierte Basen ungeeignet. 8 Schritte bleiben bei der PDD-LoRA; erst prüfen, wenn PTD im ComfyUI-Kern ist (PLAN.md, 24.10.2026) |
| **RefMods** (vorab kodierte Referenzen als kleine Datei; Video Winnougan, 24.10.2026) | nichts Neues fürs Studio: Referenzbilder gehen direkt („Figur in neue Szene“, „Video mit Referenz“), das Kodieren dauert Sekunden; die Knoten dafür sind fremd. Nicht eingebaut |

## 9. Ablage, Begleitdaten, Wiederholbarkeit

- Jede Datei landet direkt im Projektordner (ComfyUI schreibt dorthin; keine Kopien). Namen: `Bild_#####_.png`,
  `Bearbeitet_…`, `Verbessert_…`, `Freigestellt_…`, `Pose_…`, `Video_…mp4`.
- `<datei>.json` daneben (bei eigenen Bildern zusätzlich im PNG als Eintrag „werkstatt“, bei Videos im MP4): `art`,
  `prompt`, `negativ`, `variation`, `schritte`, `qualitaet`, `turbo`, `details`, `schnell`, `int8`, `durchsichtig`,
  `ausformulieren` + `prompt_ausformuliert`, `verfahren` (`schnell` = BiRefNet), `personen` (Pose-Skelett aller
  Personen), `breite`/`hoehe`, `groesse_von`,
  `aufloesung`, `motiv`, `staerke`, `maske`, `stelle` (Wort, mit dem die Maske gefunden wurde), `vorlagen` (Pfad und
  Rolle), `modell`, `modell_datei`, `rechenzeit_s`, `erstellt`, `quelle`, `auftrag`. Bei durchsichtigen Bildern steht
  in `prompt` nur die Beschreibung, bei ausformulierten nur der Wunsch. Beim Pose-Skelett und beim schnellen
  Freistellen gibt es keine Qualitätsstufe (`schritte` leer). Weitergeführte Videos (`video_weiter`) haben zusätzlich
  `modus`, `clip_bilder` (Länge des neu gerechneten Clips), `neu_bilder` (davon im fertigen Video), `neu_sekunden`
  (Wunsch), `schnitt_ende`/`schnitt_anfang` (weggelassene Bilder) und `quellen` (Pfad, Bildzahl und SHA-256 jedes
  Clips); `laenge_bilder` ist dort die Länge des fertigen Videos.
- **Nochmal** = gleiche Einstellungen und gleiche Variationsnummer = dieselben Pixel bzw. bei Videos Paket für Paket
  dieselbe Bild- und Tonspur (auch nach einem Neustart von ComfyUI); neu sind nur Auftragsnummer und Quelle in den
  eingebetteten Daten (geprüft 27.09.2026: `Video_00006_` → `_00017_`, weitergeführt `Video_00010_` → `_00016_`, beide
  mit voller Rechenzeit, also wirklich neu gerechnet; die Doppel liegen im Papierkorb). Hat ComfyUI das Ergebnis noch,
  meldet das Studio „gibt es schon“ statt einer Kopie.
  **Variation** = neue Nummer. **Mit Änderungen** füllt das Formular mit allen Einstellungen.
- Neue Funktionen wirken nur auf ausdrücklichen Wunsch (`turbo`, `details`, `aufloesung`, `groesse_von`,
  `durchsichtig`, `schnell`, `int8`, `verfahren`, `stelle`, `ausformulieren`, `personen`); ältere Bilder bleiben bei „Nochmal“
  gleich (geprüft zuletzt 27.09.2026: `Bild_00076_` → `Bild_00083_` pixelgleich und weiter BF16; ausformuliert
  `Bild_00081_` → `Bild_00084_` gleicher Text, gleiche Pixel). Eine per Wort gefundene Maske steht in der Begleitdatei;
  „Nochmal“ nimmt sie wieder, statt neu zu suchen. „Nochmal“ eines weitergeführten Videos nimmt dieselbe Clip-Länge
  (ohne neue Rundung) und die Prüfsummen der Clips mit: Wurde ein Clip inzwischen ersetzt (ComfyUI vergibt den Namen
  der jüngsten Datei nach dem Papierkorb neu), bricht der Auftrag mit Hinweis ab, statt still ein anderes Video
  weiterzuführen.
- **Auch normale Bilder sind nicht ganz deckend:** Qwen speichert immer RGBA. Gemessen an 158 Bildern (26.09.2026)
  liegt die Deckung an bis zu 97 % der Pixel bei 220–254 statt 255, vereinzelt bis 157; unter 50 % fiel kein normales
  Bild. Für Webseiten deshalb immer `studio.py export` nehmen: Er entfernt diese Restdurchsichtigkeit und behält
  Transparenz nur, wo wirklich etwas durchsichtig ist (mehr als 0,1 % der Pixel unter 50 % Deckung; das waren außer
  den freigestellten und durchsichtigen nur drei Bearbeitungen, `Bearbeitet_00014_`, `_00015_`, `_00068_`). Liegt
  darunter kein Weiß, lehnt er JPEG ab.
- Bibliothek: Suche in Prompts, Filter nach Projekt und Bild/Video; Verschieben zwischen Projekten; „In den
  Papierkorb“ (Windows-Papierkorb, rückholbar). Bilder von außerhalb des Studios zeigt die Werkstatt nur, wenn sie
  selbst gewählt wurden oder ein Studio-Bild auf sie verweist.

## 10. Schnittstelle für Agenten

Am einfachsten über das Skript des Skills (`studio.py`, siehe Skill). Direkt:

- `GET http://127.0.0.1:3895/api/studio` → `einstellungen` (`arten` = Arten, die der laufende Stand kennt; Formate,
  Stufen, `turbo_verfuegbar`,
  `details_verfuegbar`, `schnell_verfuegbar`, `video_schnell_verfuegbar`, `durchsichtig_verfuegbar`, `int8_verfuegbar`,
  `freistellen_schnell_verfuegbar`, `finden_verfuegbar`, `pose_verfuegbar`, `ausformulieren_verfuegbar`,
  `realismus_verfuegbar`,
  `ausformulieren_sekunden` …), `comfy` (`laeuft`, `ordner_ok`), `projekte`, `auftraege`. Die `…_verfuegbar`-Angaben
  prüfen, ob die Modelldateien in ComfyUI liegen.
- `GET /api/studio/bibliothek` → alle Dateien mit `info` (Begleitdaten).
- `POST /api/studio` mit Kopfzeile **`X-Werkstatt: 1`** und JSON `{"aktion": …}`:

| Aktion | Felder | Antwort |
|---|---|---|
| `erzeugen` | siehe unten | `{"neu": [Auftrags-IDs]}` |
| `projekt_neu` | `name` | `{"name": …}` (409, wenn es das Projekt schon gibt) |
| `abbrechen`, `wiederholen`, `entfernen` | `id` | `{"ok": true}` |
| `verschieben` | `pfade` (relativ), `projekt` | verschobene Pfade |
| `papierkorb` | `pfade` | nur auf Saschas Wunsch |
| `maske` | `pfad` | Markierung eines verbesserten Bildes |

**Felder von `erzeugen`:** `art`, `prompt` (beim Freistellen: das Motiv), `projekt` (muss existieren; leer = ohne
Projekt), `anzahl` 1–4 (nur mit zufälliger Nummer), `variation` (feste Nummer oder weglassen), `schritte` (6, 12,
20, 30, 40; Videos 4–20), `turbo: true` (Bilder; setzt 6 Schritte), `schnell: true` und `int8: true` (alle
Qwen-Bildarten, nur wenn `schnell_verfuegbar` bzw. `int8_verfuegbar`; sonst still ignoriert – für neue Aufträge immer
mitschicken; `schnell: true` seit 17.10.2026 auch für alle MiniMax-Videoarten einschließlich `video_weiter` und
`folge_neu`, wenn `video_schnell_verfuegbar`; „Nochmal“ nur, wenn das Original es hatte), `negativ` (wirkungslos, s. o.),
`vorlagen: [{"art": "bibliothek"|"datei", "pfad": "<Projekt>/<Datei>" | "C:\\…\\bild.jpg", "rolle": …}]`.
Je Art zusätzlich: `bild` → `breite`, `hoehe`, `durchsichtig: true` (`prompt` = nur das Motiv) oder
`ausformulieren: true` (`prompt` = kurzer Wunsch; Fehler, wenn nicht `ausformulieren_verfuegbar`; mit `durchsichtig`
wirkungslos); `bearbeiten` → `groesse_von` (`vorlage`|`format`), `aufloesung`
(1024|1440|2048), bei `format` `breite`/`hoehe`, `details: true`; `verbessern` → `maske` `{breite, hoehe, rle}`
(Lauflängen, abwechselnd frei/markiert, beginnend mit frei, Bildgröße des Originals) **oder** `stelle` (Wort, bis
100 Zeichen, etwa `"hand:2"`; SAM3 sucht beim Rechnen, findet es nichts, endet der Auftrag mit `fehler`), `staerke`
(1,0|0,8|0,6), freiwillig ein Vorbild für die Stelle als weitere Vorlage mit `rolle: "vorbild"` (höchstens
`einstellungen.verbessern.max_vorlagen`, derzeit 1; im Text „Bild 2“; fehlt das Feld, kennt der Dienst es noch nicht);
`freistellen` → `prompt` = Motiv oder leer, `verfahren: "schnell"` nur mit leerem `prompt` (BiRefNet;
sonst Fehler); `pose` → nur eine Vorlage (Rolle `original`), kein `prompt`, keine Stufe, `anzahl` wirkt nicht,
`personen: true` für alle Personen (nur mit `finden_verfuegbar`, sonst still ignoriert; für neue Aufträge mitschicken);
Videos → `breite`, `hoehe`, `bilder` (Länge), bei Referenz `referenz_genau` (`match`|`max`), `ton_behalten`;
alle Videoarten (auch `video_weiter`) `realismus: true` für Videos mit Personen (Fehler, wenn nicht
`realismus_verfuegbar`); `video_text`/`video_bild` mit `einstellungen.dmad_schritte` Schritten für neue Aufträge
`dmad: true` (DMAD statt Turbo-LoRA; „Nochmal“ nur, wenn das Original es hatte);
Bilder mit `turbo: true` für neue Aufträge zusätzlich `turbo_modell: true`, wenn `turbo_modell_verfuegbar` (offizielles
Turbo-Modell, 8 Schritte; „Nochmal“ nur, wenn das Original es hatte); `video_referenz` zusätzlich `tauschen: true` (Person tauschen: genau 1 Clip, mindestens 1 Bild;
`tauschen_verfuegbar`, Prompt-Vorlage `einstellungen.tauschen_vorlage` mit `{wer}`) und für neue Aufträge mit
`einstellungen.acc8_schritte` Schritten `acc8: true` (8-Schritt-LoRA, nicht mit `tauschen`; „Nochmal“ nur, wenn das
Original sie hatte);
`video_zeitlupe` → `vorlagen` [1 Video, Rolle `original`], `faktor` 1.5 oder 2 (`zeitlupe_verfuegbar`);
`video_freistellen` → `vorlagen` [1 Video, Rolle `original`], `motiv` (englisch, Standard
`einstellungen.video_freistellen_motiv`; `video_freistellen_verfuegbar`) – beide ohne Prompt, Stufe und Nummer;
`modell3d` (Stufe 3t) → `vorlagen` [1 Bild, Rolle `vorlage`: Drehblatt oder Bild] **oder** [Rollen `vorn` (Pflicht), `links`,
`hinten`, `rechts`], `stufe` (`fein`|`leicht`, Standard aus `einstellungen.modell3d_stufen`), `modus` (`drehblatt`|`bild`,
sonst erkannt), `variation` (Seeds; leer = zufällig), ohne Prompt und Schritte; `modell3d_verfuegbar`,
`modell3d_bild_verfuegbar`, `modell3d_zeit` je Stufe; Ergebnis in `dateien` das Vorschau-Video, die GLB mit gleichem Stamm
daneben (`info.modell_3d`), abrufbar über `/studio/datei?p=<Projekt>/<Modell>.glb`;
`video_weiter` → `modus` (`verlaengern`|`davor`|`verbinden`|`schleife`), `vorlagen` nur aus der Bibliothek (`.mp4`)
mit Rolle `ausgang` (Clip davor: verlaengern, verbinden, schleife) und/oder `ziel` (Clip danach: davor, verbinden),
`neu_sekunden` (Wunschlänge des neuen Stücks, aufgerundet auf die nächste mögliche Clip-Länge) **oder** für „Nochmal“
`clip_bilder` (genaue Clip-Länge: 124, 141, 175, 192, 226, 243, 277, 294, 328 oder 345) mit `pruefsummen`
(`{Pfad: SHA-256}` aus `quellen` der Begleitdatei), `schnitt_ende`/`schnitt_anfang` (ganze Bilder), `schritte`; Größe
und Länge kommen aus den Clips (`breite`, `hoehe`, `bilder` braucht es nicht).

**Szenenfolge:** `POST /api/studio {"aktion": "folge_neu", "gemeinsam": …, "szenen": [{"text": …, "sekunden": …,
"realismus": true|false (je Szene, seit 09.10.2026)}],
"breite", "hoehe", "schritte", "pruefen": true|false, "projekt", "variation", "realismus", "vorlagen": [Rolle `start`
oder `bild`]}` → `{"id", "neu"}` (Sekunden: Szene 1 eine Länge wie bei Videos, etwa 5,17; weitere 3,5–12,75 s neu, auf
die nächste Clip-Länge aufgerundet; zusammen höchstens 60 s, höchstens `einstellungen.szenen.max_szenen` Szenen).
Steuern: `{"aktion": "folge", "id": …, "was": "passt"|"nochmal"|"beenden"|"entfernen"}`. Zustand in `GET /api/studio`
→ `folgen`: `zustand` `laeuft` | `pruefen` | `fehler` | `fertig` | `abgebrochen`, `szene` (ab 0), `datei` (aktuelle
Fassung), `freigegeben` (je Szene), `takes` (Auftrags-IDs je Szene), `meldung`, `gesamt_bilder`.

**Aufträge verfolgen:** `GET /api/studio`, Eintrag in `auftraege` mit `zustand` `wartet` → `laeuft` (`schritt`
„platz“, „rechnet“) → `fertig` | `fehler` | `abgebrochen`; `meldung`, `hinweis`, `erwartet_s`, `sekunden`;
Ergebnis in `dateien` (relativ zu `C:\Workstation\Arbeitsmaterial\Studio`).

**ComfyUI über die Zentrale starten:** `GET http://127.0.0.1:3894/api/konfig` (Eintrag mit `art: comfy`, derzeit
`bild-video`), `POST /api/plan {"id": …, "aktion": "starten"}` und nur bei leeren `schritte`
`POST /api/starten {"id": …, "schritte": []}`, jeweils mit Kopfzeile **`X-Zentrale: 1`**.

## 11. Dauer und Grafikspeicher

**Zeitschätzung lernt nach** (seit 09.10.2026): Die Schätzung zählte nur die Rechenschritte; Text-Encoder, Vorlagen
und Dekodieren fehlten. Gemessen an 150 eigenen Aufträgen lag sie bei neuen Bildern mit Turbo um den Faktor 1,35 zu
niedrig, beim Bearbeiten wie Vorlage 1 in 2 MP um 2,2, beim Verbessern mit Vorbild um 1,8. Jetzt rechnet die Werkstatt
je Gruppe (Art, wie Vorlage 1 oder Format, Zahl der Vorlagen, Turbo, Ausformulieren) den Median gemessen/geschätzt
ihrer letzten 120 fertigen Bildaufträge ein (ab 3 Aufträgen je Gruppe, sonst den Median aller; begrenzt auf 0,5–4).
Danach lagen die Schätzungen bei 0,74–1,0 der gemessenen Zeit. Videos mit Referenz zählen seitdem die Bilder ihrer Clips
und die Referenzbilder mit (vorher fehlten sie: „Person tauschen“ geschätzt 2, gemessen 7–8 min). Videos mit schnellerer
Aufmerksamkeit (seit 17.10.2026) lernen ihre Sekunden je Schritt getrennt; ohne eigene Läufe gilt
`video.schnelle_aufmerksamkeit.zeitfaktor` (0,6) auf die übrigen.

Gemessen am 23.–26.09.2026 (RTX 3090 + 3080) mit den BF16-Modellen, ohne „schneller rechnen“. **Neue Aufträge seit
27.09.2026** (INT8 und schnellere Aufmerksamkeit) brauchen etwa die Hälfte: neues Bild 1328² Turbo ~7 s, Standard
~17 s, 4 MP Turbo ~26 s, Hochskalieren 2 MP ~22 s (Abschnitt 4). Die Tabelle gilt weiter für „Nochmal“ älterer Bilder.

| Auftrag | Standard (20) | Turbo (6) |
|---|---|---|
| Neues Bild 1328² | ~38 s (Max: ~76 s) | ~14 s |
| Neues Bild mit durchsichtigem Hintergrund 1328² | – | 9–14 s |
| Neues Bild 4 MP (2752 × 1536) | ~117 s | ~39 s |
| Banner 3:1 (3072 × 1024) / Panorama 4:1 (4096 × 1024) | – | ~26 s / ~36 s (mit „schneller rechnen“ 30 s) |
| Moodboard 4 MP (hoch, breit, quadratisch) | ~115 s | 35–39 s (mit INT8 17–22 s) |
| Bearbeiten wie Vorlage 1 (≈1 MP) | ~30 s | ~15 s |
| Bearbeiten 2 MP (Hochskalieren, Auffrischen) | ~70 s | ~30 s |
| Bearbeiten 2 MP mit 2 Vorlagen (Logo aufbringen) | – | 29–55 s (Schätzung lernt seit 09.10.2026 nach) |
| Bearbeiten mit Porträt in neues Format `quer169` | – | 13–20 s, mit INT8 7–12 s (Schätzung lernt nach) |
| Neues Bild 4:3 (1472 × 1104, INT8) | – | 6–14 s |
| Bearbeiten 4 MP (Hochskalieren) | ~188 s | 84–87 s |
| Charakterblatt 1920 × 1088 | ~53 s | ~24 s |
| Drehblatt 4096 × 1024 (Stufe 3t, Turbo-Modell) | – | 26–36 s |
| 3D-Modell aus Drehblatt (Pixal3D, Stufe 3t, mit Drehteller-Vorschau) | fein 191–201 s (40 MB GLB) | leicht 52 s (6 MB) |
| 3D-Modell aus einem Bild (Pixal3D Einzelbild + MoGe) | – | leicht 114 s (7 MB) |
| Stelle verbessern | ~25–30 s | ~15 s |
| Stelle verbessern per Wort (INT8, Suche mit SAM3 etwa 1 s) | ~29 s (3l, gelöschte Datei) | ~18 s (3l, gelöschte Datei) |
| Stelle verbessern mit Vorbild (INT8, Stufe 3n) | – | 14–23 s; mit demselben Vorbild direkt danach 6–10 s (Text-Encoder aus dem Zwischenspeicher). Ohne Vorbild gleiche Stelle etwa 6 s weniger |
| Freistellen mit Beschreibung (Qwen) | ~30 s | ~15 s |
| Freistellen ohne Beschreibung (BiRefNet) | ~1 s (0,7–1,5 s; erstes Mal mit Laden ~2 s) | |
| Pose-Skelett (SDPose) | 1–2 s | |
| Pose übernehmen (Bearbeiten, Skelett + Porträt, INT8) | – | ~14 s (`Bearbeitet_00071_`) |
| Neues Bild ausformuliert (INT8, 1584 × 1056) | – | 15–34 s statt ~7 s |
| Video 960 × 544, 5 s | 4 Schritte ~85 s · 8 Schritte ~2¼ min · 20 Schritte ~6 min (geschätzt) | |
| Video mit Realism-LoRA (Stufe 3o) | gleich: 8 Schritte 122–139 s mit und ohne | |
| Video mit Referenz (1 Bild), 8 Schritte mit 8-Schritt-LoRA (seit 09.10.2026) | 140–147 s, gleich wie mit Turbo | |
| Video auf **einer** RTX 3090 (16.10.2026, Turbo 8 Schritte, Suprim) | 960 × 544, 5 s: 118,7 s (zwei Karten 119,5 s) · 1344 × 768, 5 s: 327,8 s (zwei Karten am 11.10. 366–398 s) · 1344 × 768, 10 s: 1058 s; Spitze 23,8 GiB | |
| Video aus Text/Bild 5 s, „Schnell“ mit DMAD (seit 11.10.2026) | 960 × 544: 75–83 s (8 Schritte Turbo 131–144 s) · 1344 × 768: ~200 s (8 Schritte 366–398 s) | |
| Neues Bild mit offiziellem Turbo (INT8, schnell) | 1 MP 5–8 s · 4 MP (2752 × 1536) 32 s · Bearbeiten 9 s (LoRA 13 s) · Verbessern 20 s | |
| Person tauschen 960 × 544, 5 s (Clip 124 Bilder) | 8 Schritte Turbo 474–481 s; 20 Schritte 1029 s | |
| Zeitlupe (RIFE) 5 s Video | ×2: 8–10 s · ×1,5: 15 s | |
| Video freistellen (SAM3 + BiRefNet) | 5 s quer 66–71 s · 8 s hoch 58 s; SAM3 allein 37–54 s, BiRefNet allein 45–66 s | |
| Szenenfolge 960 × 544, 8 Schritte (Stufe 3p) | 3 Szenen (5 + 5,7 + 5,7 s, 16,5 s fertig): 120 + 298 + ~300 s; 2 Szenen (5 + 3,5 s): 323 s zusammen | |
| Video weiterführen 960 × 544, 8 Schritte (Stufe 3m) | Davor setzen 5,1 s neu (L 124): 136–141 s · Verlängern 3,5 s neu (L 124 + 39 festgehalten): 208 s · Verlängern 5,7 s neu (L 175 + 39): 301–312 s · Verbinden/Schleife 5,6 s neu (L 175 + 40): 319–327 s · Verbinden 9,9 s neu (L 277 + 40): 705 s | |

**Videos wachsen stärker als ihre Länge** (gemessen 27.09.2026): Die Zeit je Schritt steigt etwa mit dem Quadrat
von Pixeln × Bildern, und festgehaltene Bilder und Start-/Endbilder rechnen mit (je Schritt: 124 Bilder mit Endbild
13,8 s, 124 + 39 festgehalten 20,5 s, 175 + 39 32–34 s, 768 × 1344 × 124 50,7 s, 277 + 40 93 s – dann ist die 3090
voll und Modellteile werden nachgeladen). Die Schätzung rechnet deshalb seit Stufe 3m mit `Grundzeit 30 s + Schritte ×
Sekunden je Schritt × (Pixel × wirksame Bilder / 960·544·124)²` (±15 % an allen Messpunkten; vorher linear, für
175 + 39 Bilder 197 statt 301 s). Die Sekunden je Schritt lernt sie aus den eigenen Videos (ohne Referenz-Clips),
sonst 12,4 s (`video.zeit`).

Erster Auftrag nach dem Start von ComfyUI: plus Ladezeit. Grafikspeicher: Bild ~14,7 GiB (3090) + kurz ~1,3 GiB
(3080), geplant 16 + 2 GiB; über 2 MP bis 17,3 + 5,9 GiB (geplant 18 + 6); Video ~22 + 6,2 GiB (geplant 20 + 7).
Die Zeitschätzung lernt aus den eigenen Läufen; beim Bearbeiten „wie Vorlage 1“ und beim Freistellen rechnet sie
mit, dass die Vorlage in gleicher Größe mitläuft (Faktor 0,94 + 0,33 × Fläche/1328²). INT8-Läufe zählen getrennt;
solange es keine eigenen gibt, gilt die Hälfte der BF16-Zeit (`int8.zeitfaktor`). Ausformulieren schätzt sie mit
15 s zusätzlich, Pose-Skelett und schnelles Freistellen mit 3 s.

**Grafikspeicher seit Stufe 3l:** INT8 auf der 3090 9,1–10,4 GiB statt 15,7–16,9 (Hochskalieren 2 MP 14,1 statt 20,5);
die Planung bleibt vorsichtig bei 16 + 2 bzw. 18 + 6 GiB. Pose-Skelett und schnelles Freistellen planen 6 GiB auf der
3090 (kleine Modelle: SDPose 1,9 GB mit SAM3 1,75 GB für die Personenrahmen, BiRefNet 0,4 GB), keine auf der 3080. Ausformulieren plant 20 + 4 GiB (gemessen
Spitze 18,7 GiB auf der 3090, dort liegen Prompt-Enhancer und Bildmodell).

**Karten (seit 14.10.2026, zwei RTX 3090, Stufe 6 in PLAN.md):** Das Studio wählt die Karten je Auftrag nach dem Stand
der Zentrale (`karten_waehlen`). Bedarf je Rolle in `werkstatt\config.json`: `eine` (alles auf einer Karte: Bild 18 GiB,
über 2 MP 19 GiB – bis 22.10.2026 21,5 GiB, damit passte ein großes Bild weder auf die Suprim mit Monitor noch auf die
3080 und wartete auf die FE –, mit Ausformulieren 20 GiB), `eine_ohne_monitor` (ganz auf einer Karte, nie auf der Monitorkarte:
Video 22 GiB, seit 16.10.2026), `haupt`/`neben` (geteilt: Bild 16 + 2, groß 18 + 6, Video 20 + 7 GiB) und
`fest` (Abläufe ohne Kartenwahl auf ComfyUIs Standardkarte 0 = FE: Pose 6, Zeitlupe 4, Video freistellen 8, 3D 14 GiB;
„Stelle per Wort“ plant 2 GiB für SAM3 auf Karte 0 dazu). Reihenfolge: passt ohne Freigabe; Bild ganz auf einer Karte vor
geteilt; die Monitorkarte (Suprim) nicht unter 2 GiB Rest füllen; geteilt das Diffusionsmodell nicht auf die
Monitorkarte; dort, wo ComfyUI seine Modelle schon hält (sonst lädt es sie ein zweites Mal); die engste Karte.
Gemessen 14.10.2026: Bild (INT8, Turbo, 1328²) ganz auf der Suprim neben NInfer auf der FE, Spitze 8,0 GiB, 9,4 s; Video
960×544, 5 s, Schnell: Modellkarte bis 23,3 GiB, andere bis 20,8 GiB, 74–76 s – ComfyUI wächst in den freien Platz.
Welche Karte ein Auftrag nimmt, steht im Werkstatt-Protokoll („rechnet auf RTX 3090 Suprim“).

**Zwei ComfyUI-Prozesse (Stufe 8, 16.10.2026):** Welcher Prozess einen Auftrag nimmt, entscheidet `_wer_zuerst`:
Videos auf einer Karte gehören Prozess 2 (Suprim), solange er läuft; andere Aufträge der erste freie Prozess, der sie
nach dem Stand der Zentrale jetzt ganz auf eine eigene Karte legen kann – Prozess 1 (FE) zuerst, damit die Suprim für
ein Video frei bleibt; passt ein großes Bild nicht auf die FE, nimmt es Prozess 2. Ohne frischen Stand (über 15 s) oder
wenn nichts allein passt: wer zuerst kommt. Gemessen 16.10.2026: Video in Prozess 2 und Bild in Prozess 1, beide Karten
gleichzeitig bei 100 %. Nach einem Video hält ComfyUI 2 rund 20 GiB auf der Suprim (Zwischenspeicher, in der Zentrale
freigebbar).

## 12. Wie es intern arbeitet

Alle Abläufe baut `werkstatt\studio.py` aus ComfyUI-Kernknoten (keine Zusatzknoten); die je Auftrag gewählten Karten
setzen `SelectModelDevice`, `SelectCLIPDevice` und `SelectVAEDevice` (`mit_geraeten`; Vorgabe ohne Wahl in
`studio.geraete`).

- **Neues Bild** (`bild_graph`): `CLIPTextEncode` → `EmptySD3LatentImage` → `KSampler` (Euler, simple, CFG 1,
  Seed = Variationsnummer) mit `ModelSamplingAuraFlow` Shift 3,1 → `VAEDecode` → `SaveImage`.
- **Bearbeiten**: `TextEncodeQwenImage21` mit bis zu 10 Vorlagen; `resolution` ist das Pixelbudget (1024/1440/2048,
  Seitenverhältnis von Bild 1), das Latent kommt aus Bild 1; bei `groesse_von: format` eine eigene Fläche
  (`EmptySD3LatentImage`).
- **Verbessern** (`verbessern_graph`): Markierung als Graustufen-PNG `werkstatt_maske_<Prüfsumme>.png` in ComfyUIs
  Eingangsordner; Ausschnitt (`ImageCropV2`), vergrößert, `TextEncodeQwenImage21` mit dem Ausschnitt als Vorlage,
  `VAEEncode` + `SetLatentNoiseMask` (Maske etwas vergrößert), `KSampler` mit `denoise` = Stärke, zurückskaliert und
  mit weicher Maske (6 px vergrößert, 6 px weichgezeichnet) per `ImageCompositeMasked` ins Original. Mit Vorbild
  (Stufe 3n): `LoadImage` (Knoten 110) → `ImageScaleToTotalPixels` (1 MP, Lanczos, 32er-Raster, Knoten 111) als
  `images.image_2`; `resolution` bleibt 0, der Ausschnitt also Bild 1 in seiner Arbeitsgröße (das Latent kommt aus ihm).
  Der Ausschnitt ist dann doppelt statt dreifach so groß wie die Markierung (`verbessern.vorlage.ausschnitt_faktor`).
  Ohne Vorbild ist der Ablauf unverändert (ältere Bilder bleiben bei „Nochmal“ gleich).
- **Freistellen** (`freistellen_graph`): Qwen-Bearbeitung mit fester Anweisung → RGBA; `SplitImageWithAlpha` →
  Deckung; `MaskComposite` (bis 0,4 weg, ×4 bis 0,65 voll); `GrowMask` 1 px; auf Originalgröße skaliert;
  `JoinImageWithAlpha` auf den Originalpixeln; ganz Durchsichtiges weiß (`ThresholdMask`, `EmptyImage`,
  `ImageCompositeMasked`).
- **Szenenfolge** (`folge_neu`, `_szene_anlegen`, `_folgen_abgleichen`): keine eigenen Abläufe – Szene 1 ist ein
  Auftrag „Video aus Text/Bild/Referenz“, jede weitere ein Auftrag „Video weiterführen“ (`verlaengern`) an die
  freigegebene Datei. Der Prompt ist `gemeinsamer Teil + Szene + Zusatz ohne Schnitt` (`szenen_prompt`). Die Folge merkt
  sich nur Angaben, Auftrags-IDs und Freigaben; ihr Zustand kommt jedes Mal aus dem Zustand des aktuellen Auftrags.
- **Realistische Personen** (Videos, `video_graph`): `LoraLoaderModelOnly` (Knoten 26) hinter der Turbo-LoRA (24)
  bzw. dem Modell, Stärke 1,0; der Prompt im Knoten 5 bekommt `r34l1sm, ` davor. Beim Zurücklesen aus einem
  ComfyUI-Ablauf erkennt `einstellungen_aus_graph` die LoRA und nimmt das Auslösewort wieder weg.
- **Turbo** (`_mit_turbo`): `LoraLoaderModelOnly` (Knoten 24) + `ManualSigmas` (Stützstellen 1,0 · 0,9375 · 0,875 ·
  0,75 · 0,5 · 0,25, mit dem dynamischen Zeitplan von Qwen 2.1 nach Bildgröße verschoben) + `BasicGuider` +
  `SamplerCustomAdvanced`.
- **Details** (`_mit_details`): `LoraLoaderModelOnly` (Knoten 25, Stärke 1,0) hinter der Turbo-LoRA, vor dem Shift.
- **Durchsichtig** (`_mit_durchsichtig`, nur neues Bild): Beschreibung im Rahmen-Prompt (`durchsichtig_prompt`; die
  Umkehrung `durchsichtig_beschreibung` stellt für „Nochmal“ und die Bibliothek die Beschreibung wieder her); nach
  `VAEDecode` `SplitImageWithAlpha` → Deckung; `MaskComposite` (bis 0,02 weg, darüber auf 0–1 gestreckt);
  `JoinImageWithAlpha`; ganz Durchsichtiges weiß (`ThresholdMask`, `EmptyImage`, `ImageCompositeMasked`).
- **Schnell** (`_mit_schnell`): `ModelAttentionBackend` (Knoten 26, „comfy kitchen attention“) als letzter Schritt
  zwischen Modell bzw. LoRAs und dem Shift. Die Bibliothek erkennt ihn im gespeicherten Ablauf (`schnell: true`).
  Videos (`video_graph`, seit 17.10.2026): derselbe Knoten als Knoten 29 hinter allen LoRAs und hinter
  `MiniMaxH3SigmaShift` (DMAD), direkt vor `BasicScheduler` (10) und `BasicGuider` (11); `weiter_graph` übernimmt ihn,
  weil es auf `video_graph` aufbaut. Backend aus `video.schnelle_aufmerksamkeit.backend`.
- **INT8** (`qwen_dateien`): wählt Bildmodell und Text-Encoder nach dem Feld `int8` (`modelle.unet_int8`/`clip_int8`
  statt `unet`/`clip`); sonst ist der Ablauf gleich. Die Bibliothek erkennt INT8 am Dateinamen im gespeicherten Ablauf.
- **Ausformulieren** (`_mit_ausformulieren`, nur neues Bild): `CLIPLoader` (Prompt-Enhancer) + `SelectCLIPDevice`
  auf der Karte des Bildmodells → `TextGenerate` (Temperatur 1,0, top_k 20, top_p 0,95, Wiederholungsstrafe 1,05, Seed = Variationsnummer,
  ohne Nachdenken; Chat-Vorlage selbst gebaut aus Systemtext und Wunsch, `ausformulieren_text`) → der Text geht
  direkt in `CLIPTextEncode`; `PreviewAny` (Knoten 63) liefert ihn zurück, die Werkstatt speichert ihn als
  `prompt_ausformuliert`. `ausformulieren_wunsch` holt den Wunsch für die Bibliothek aus dem gespeicherten Ablauf.
- **Schnelles Freistellen** (`freistellen_schnell_graph`): `LoadBackgroundRemovalModel` (BiRefNet) +
  `RemoveBackground` → `InvertMask` (die Maske ist 1 = Motiv, `JoinImageWithAlpha` braucht es umgekehrt); ganz
  Durchsichtiges weiß (`ThresholdMask`, `GetImageSize`, `EmptyImage`, `ImageCompositeMasked`); `JoinImageWithAlpha` auf
  den Originalpixeln in Originalgröße.
- **Pose-Skelett** (`pose_graph`): `CheckpointLoaderSimple` (SDPose) → `SDPoseKeypointExtractor` (Modell, VAE, Bild)
  → `SDPoseDrawKeypoints` (Körper, Hände, Gesicht, Füße; Strichstärke 4, Schwelle 0,5) → `SaveImage` (`Pose_`). Mit
  `personen`: `CheckpointLoaderSimple` (SAM3.1) + `CLIPTextEncode` („person:6“) → `SAM3_Detect` (Schwelle 0,5, ohne
  Verfeinerung) → dessen `bboxes` in den Eingang `bboxes` von `SDPoseKeypointExtractor` (Knoten 78/79/96 wie beim
  Suchen einer Stelle). Die Bibliothek erkennt es an `SAM3_Detect` im gespeicherten Ablauf.
- **Stelle per Wort** (`finden_graph`, vor dem Verbessern als eigener kleiner Lauf): `CheckpointLoaderSimple`
  (SAM3.1) + `CLIPTextEncode` (das Wort) → `SAM3_Detect` (Schwelle 0,5, 2 Verfeinerungen, eine Maske für alle
  Treffer) → `MaskToImage` → `ImageScaleToMaxDimension` (768 px) → `PreviewImage`; dazu Originalgröße über
  `GetImageSize` + `PreviewAny`. Die Werkstatt holt die Vorschau über `/view`, liest sie mit einem eigenen PNG-Leser
  (`png_lesen`, Standardbibliothek) und rechnet sie auf die Originalgröße hoch (`maske_hochrechnen`, jede Überdeckung
  zählt) → Lauflängen-Maske wie eine gemalte. Danach läuft das Verbessern wie gewohnt.
- **Videos**: MiniMax-H3-Abläufe nach dem Vorbild von 2Wild (fl2va bzw. ref2va), Turbo-LoRA bis 8 Schritte, Start-
  und Endbild per `ImageScale` mittig zugeschnitten, Bibliothek per `<pfad> [output]` ohne Kopie, `SaveVideo`.
- **Weiterführen** (`weiter_graph`, Stufe 3m): Grundlage ist „Video aus Text“ (fl2va, Turbo-LoRA bis 8 Schritte) mit
  der Clip-Länge L. Clips per `LoadVideo`/`LoadAudio` (`<pfad> [output]`, keine Kopie). Vorn `Video Slice` auf die
  letzten 39 Bilder des Clips davor (Zeitfenster 1 ms vor den Bildgrenzen: zusammengesetzte Videos zittern um bis
  0,5 ms) → `GetVideoComponents` → `MiniMaxH3AddGuide` (Bild 0, Bilder und exakt geschnittener Ton) als Conditioning
  des Samplers; hinten `Video Slice` auf ein Bild → `last_frame` von `MiniMaxH3ImageToVideo`. Neuer Teil:
  `ImageFromBatch` → `CreateVideo` ohne Ton. Zusammensetzen mit `ConcatenateVideo`: ungeschnittene Clips gehen als
  Datei hinein (Bildspur bitgleich umverpackt), gekürzte als `Video Slice` (dann wird einmal neu kodiert); der Ton
  kommt als `complete_audio`: je Stück `TrimAudioDuration` genau an den Bildgrenzen (Start/24, Anzahl/24), zu kurzer
  Quellton mit `EmptyAudio` aufgefüllt (auch im festgehaltenen Stück), alles per `AudioConcat` → `SaveVideo`.
  Unmittelbar vor der Übergabe prüft die Werkstatt jeden Clip erneut (`mp4_info`, SHA-256). Die Bibliothek erkennt die
  Art an `ConcatenateVideo` + `MiniMaxH3ImageToVideo`; maßgeblich sind die Begleitdaten.
- **MP4-Leser** (`mp4_info`, Standardbibliothek, bewusst eng): liest die Boxen `hdlr`, `mdhd`, `stts`, `elst`, `tkhd`
  und `stsd` und verlangt genau eine Bild- und eine Tonspur, 24 Bilder je Sekunde (je Bild ±5 %, insgesamt weniger als
  ¼ Bild Abweichung), Edit-Lists mit höchstens einem Abschnitt ohne leeren Vorspann und Ton, der das Bild bis auf
  25 ms abdeckt (H3 rundet die Tonlänge; bei 158, 209, 260, 311, 362 Bildern fehlen 8,3 ms).
- **Warten bis zum Stillstand** (Stufe 3m, alle Aufträge): Vor der Übergabe öffnet die Werkstatt einen Handle auf den
  ComfyUI-Prozess (Besitzer des Ports) und hält ihn bis zum Ende. Antwortet ComfyUI nicht, wartet der Auftrag weiter
  („ComfyUI antwortet gerade nicht …“); verloren ist er erst, wenn der Prozess bestätigt beendet ist. Abbrechen hat
  keine Frist mehr: Der Abbruch geht alle 30 s erneut hinaus, bis ComfyUI den Auftrag nicht mehr führt. Die Anmeldung
  bei der Zentrale wird in beiden Schleifen alle 20 s verlängert; Sperre und Anmeldung bleiben bis zum Stillstand.
- Dateien von außerhalb lädt die Werkstatt in ComfyUIs Eingangsordner hoch; Bibliotheksdateien gehen ohne Kopie.
- Konfiguration: `werkstatt\config.json`, Abschnitt `studio` (Modelle mit `unet_int8`/`clip_int8`, Formate, Stufen,
  `turbo`, `details`, `freistellen` mit `schnell_modell`, `durchsichtig`, `schnelle_aufmerksamkeit`, `int8`,
  `ausformulieren`, `pose` mit `personen`, `verbessern` mit `finden`, `vorlage_zeit`, `max_seite`/`max_pixel`, Grafikspeicher-Planung
  mit `bedarf_hilfe_mib`). Jeder Abschnitt trägt in `grund` die Messung, auf der er beruht.
