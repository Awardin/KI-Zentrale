# SPEC: Fibo 2.0 in der KI-Zentrale und das Atelier

Stand: 22.10.2026 (Claude, Auftrag Sascha). Status: zum Bau freigegeben, Scheiben unten.

## Ziel

Sascha will das Bildmodell **Fibo 2.0** (Bria, 8B, offenes Gewicht, nur nicht-kommerziell) lokal nutzen und ein Programm, in
dem er **Bilder, Objekte und Text auf einer Leinwand frei verschiebt** (YouTube-Thumbnail, Flyer, Social-Media-Bild) und
dabei Fibo zum Erzeugen und Bearbeiten nutzt. Die destillierte Fassung **Edit Turbo** (4 Schritte statt 50) soll dafür
genutzt werden.

## Entscheidung (Architektur)

Drei Teile, getrennt nach Aufgabe:

1. **Fibo-Dienst** (`fibo/`): ein lokaler HTTP-Dienst, der das Modell auf **einer** RTX 3090 hält und Aufträge nacheinander
   rechnet. Läuft mit der eigenen Python-Umgebung `C:\LLM\runtimes\Fibo2\.venv` (torch, diffusers-Fork, bria-vgl).
2. **Modellzentrale**: neue Art `python_dienst` (allgemein, Fibo ist der erste Eintrag). Start, Stopp, Kartenwahl,
   Platzrechnung und „GPU freigeben“ wie bei llama.cpp/LightOnOCR. So stößt Fibo nicht mit Studio, Strata oder Ornith zusammen.
3. **Atelier** (`atelier/`): eigene kleine App neben Zentrale und Werkstatt (Port 3896, eigener Starter), der
   Ebenen-Editor. Er läuft **ohne** Grafikkarte (Layout, Text, Export) und ruft Fibo nur, wenn der Dienst läuft; Freistellen
   nimmt er vom vorhandenen Studio der Werkstatt.

Begründung: Die Zentrale ist das GPU-Steuerpult, kein Editor; die Werkstatt ist schon groß (studio.js 2.000 Zeilen) und
auftragsorientiert. Ein Editor ist interaktiv und braucht die Grafikkarte nur für einzelne Aktionen. Der Dienst in der
Zentrale hält die Kartenbuchhaltung ehrlich. Kein Umbau an Studio/ComfyUI.

## Messwerte (22.10.2026, eine RTX 3090 FE, CPU-Offload)

- Modell: Transformer 16,3 GB (BF16), Textencoder Qwen3-VL-4B 8,9 GB, VAE 0,3 GB → passt nicht ganz auf 24 GiB, daher
  `pipe.enable_model_cpu_offload()`.
- Grafikspeicher beim Rechnen: 17,4 GiB laut nvidia-smi (torch-Spitze 16,0 GiB). Bedarf für die Zentrale: 18.500 MiB.
- Dev, 1248×832, 50 Schritte, Guidance 5: 160–168 s (≈3 s/Schritt), Laden 7 s (Dateicache warm).
- Edit Turbo: 4 Schritte, Guidance 1,0: **20–34 s** je Bearbeitung (1248×832). Dev-Bearbeitung mit 50 Schritten: **≈360 s**.
  Dev-Bild mit 30 Schritten sieht aus wie mit 50 (98 statt 160 s) → Standard 30.
- Bearbeiten mit Klartext-Anweisung (Turbo): Farbe ändern, Schrift auf Schild ändern, Bereich mit Maske ersetzen –
  sehr gut, Rest pixelstabil. **Zusammenführen** einer groben Collage → stimmiges Foto (Person sitzt natürlich vor dem
  Fenster). Stilwechsel (Aquarell) schwach. **Mehrere Referenzbilder** mit Klartext: gescheitert (gab Bild 2 zurück) →
  nicht in diesem Bau.
- Edit Turbo unterscheidet sich von Dev **nur im Transformer** (Textencoder, VAE, Tokenizer byte-gleich): Pfad
  `C:\LLM\models\Fibo-2.0-edit-turbo\transformer`.
- Schrift im Bild: gedruckte Schrift korrekt („Backstube Müller“), Kreide-Handschrift fehlerhaft („Morneg“). Deshalb setzt
  das Atelier Text **immer als echte Textebene**, nie über das Modell.
- Beschreiber (Prompt → VGL-JSON) im Vergleich: Claude-Handbeschreibung ≥ DeepSeek Flash > DeepSeek V4 Pro (Pro machte aus
  der Physiotherapeutin eine Ärztin). DeepSeek Flash über `bria-vgl`/litellm: ≈14 s, Bruchteile eines Cents.

Referenzskripte (funktionieren, nur lesen): `C:\LLM\runtimes\Fibo2\fibo_reihe.py` (Pipeline laden, Dev/Turbo-Wechsel,
Bearbeiten, Maske, Negativprompts), `C:\LLM\runtimes\Fibo2\beschreibung_deepseek.py` (bria-vgl mit DeepSeek).
VGL-Format: `C:\LLM\models\Fibo-2.0-dev\vgl\README.md`.

## Teil A: Fibo-Dienst (`fibo/`)

- `fibo/dienst.py`, gestartet als `C:\LLM\runtimes\Fibo2\.venv\Scripts\python.exe <repo>\fibo\dienst.py --port 8098`; die
  Karte setzt die Zentrale über `CUDA_VISIBLE_DEVICES` (wie bei llama.cpp). Nur `127.0.0.1`.
- `fibo/config.json`: Modellpfade (Dev-Ordner, Turbo-Transformer, Schriften aus `<dev>\fonts`), Ablage
  `C:\Workstation\Arbeitsmaterial\Atelier\_fibo`, DeepSeek (`url` https://api.deepseek.com, `schluessel_datei`
  `C:\Users\sasch\.dsh\.credentials.yaml`, `schluessel_name` `DEEPSEEK_API_KEY`, `modell` `deepseek-flash`),
  `turbo_im_speicher` (Standard `false`), Standardwerte (Dev 50 Schritte/Guidance 5; Turbo 4/1,0).
- Server: Standardbibliothek (`ThreadingHTTPServer`), JSON. **Ein** Arbeiter-Thread rechnet; Aufträge stehen in einer
  Warteschlange. torch/diffusers werden erst im Arbeiter importiert, damit die Tests ohne GPU laufen
  (Pipeline-Fabrik injizierbar).
- Start: Pipeline Dev laden, `enable_model_cpu_offload()`. Bis bereit: `GET /health` → `{"status":"loading"}`, danach
  `{"status":"ok","modell":"fibo-2.0","aktiv":"dev","warteschlange":0,"laufend":null}`. Ladefehler → `{"status":"error",
  "fehler":…}` und Prozess beendet sich mit Fehlercode.
- Turbo: beim ersten Turbo-Auftrag Transformer laden; Wechsel wie in `fibo_reihe.py` (`remove_all_hooks`, Transformer
  tauschen, `enable_model_cpu_offload`). Mit `turbo_im_speicher=false` den nicht aktiven Transformer freigeben (Arbeitsspeicher:
  ein Transformer ≈16 GB) und bei Bedarf neu von der Platte laden.
- Endpunkte:
  - `POST /api/auftrag` → `{"id":…}`. Felder: `art` `bild`|`bearbeiten`; `prompt` (Text, VGL-JSON als Text oder Objekt);
    `beschreiber` `keiner`|`deepseek` (nur `bild`; `keiner` gibt den Text direkt an Fibo); `breite`/`hoehe` (nur `bild`;
    auf Vielfache von 16 runden, Fläche auf höchstens 1,1 MP verkleinern, Seitenverhältnis halten); `schritte`, `guidance`,
    `seed` (fehlt → zufällig, wird zurückgegeben); `bilder` (1–4, PNG/JPEG als Base64); `maske` (Base64, weiß = neu, wird auf
    die Größe des ersten Bildes gebracht); `modell` `turbo`|`dev` (Standard: `bild` → dev, `bearbeiten` → turbo; `bild` mit
    `turbo` ablehnen: Turbo kann nur bearbeiten).
  - `GET /api/auftrag/<id>` → `zustand` (`wartet`|`beschreibt`|`rechnet`|`fertig`|`fehler`|`abgebrochen`), `schritt`,
    `schritte`, `platz` in der Warteschlange, bei `fertig` `ergebnis` = `{bild: "/api/datei/<id>.png", caption, seed,
    modell, sekunden, breite, hoehe}`.
  - `POST /api/auftrag/<id>/abbrechen`: wartend → sofort raus; rechnend → im Schritt-Callback abbrechen (Zustand
    `abgebrochen`, kein Bild).
  - `GET /api/datei/<name>`: nur Dateien der Ablage, kein Pfad-Ausbruch.
  - `POST /api/beschreiben` `{prompt}` → `{caption}` über DeepSeek (ohne GPU, synchron, Zeitlimit 120 s).
- Ablage je Ergebnis: `<ablage>\<JJJJ-MM-TT>\<id>.png` und `<id>.json` (Prompt, Caption, Einstellungen, Seed, Modell,
  Sekunden, `lizenz`: „Fibo 2.0 – CC BY-NC 4.0, nur nicht-kommerziell“).
- Datenschutz: An DeepSeek geht **nur der Text-Prompt** von `bild`. **Nie Bilder.** `bearbeiten` nutzt kein Sprachmodell:
  Die Anweisung geht als Klartext an Fibo (von Bria dokumentierte Form). Der Schlüssel wird nur gelesen, nie geloggt,
  nie in Antworten oder Dateien geschrieben.
- Negativprompts: aus `fibo_reihe.py` übernehmen (T2I bzw. Edit); bei Turbo keinen setzen.
- Tests `fibo/tests/test_dienst.py` (unittest, ohne GPU, Fake-Pipeline): Größenrundung/1,1-MP-Grenze, Warteschlange in
  Reihenfolge, Health-Zustände, Abbruch wartend/rechnend, Ablage und Begleit-JSON, Pfadschutz `/api/datei`, `bild`+`turbo`
  abgelehnt, DeepSeek-Aufruf gemockt (Schlüssel taucht in keiner Ausgabe auf).

## Teil B: Modellzentrale, Art `python_dienst`

- Neue Art `python_dienst` nach dem Muster `llamacpp` (Erkennung über Befehlszeile: `python`-Pfad + `skript`-Pfad +
  `--port <port>`; Zustände `aus`/`startet`/`bereit`/`fremd`; bereit, wenn `GET <health_pfad>` `status == "ok"` liefert,
  `startet` solange `loading`). Felder: `python`, `skript`, `port`, `argumente`, `health_pfad`, `karten`,
  `bedarf_je_karte_mib`, `ram_bedarf_gib`, `startzeit_max_s`, optional `oeffnen_url` + `oeffnen_text` (Knopf im Eintrag, öffnet
  die URL im Browser, wie „Chat öffnen“).
- Eintrag `fibo2` in `zentrale/config.json`: Gruppe „Bild & Video“, Name „Fibo 2.0 · Bild & Bearbeiten“, Untertitel
  „8B · Dev + Edit Turbo · eine RTX 3090“, `wofuer` (Erzeugen und Bearbeiten für das Atelier; nur nicht-kommerziell),
  `karten` `["RTX 3090"]`, `bedarf_je_karte_mib` 18500 (Grund mit Messung oben), `ram_bedarf_gib` 30 (vorläufig,
  `ram_grund`), `startzeit_max_s` 300, `oeffnen_url` `http://127.0.0.1:3896/`, `oeffnen_text` „Atelier öffnen“,
  `eingebaut_grund` (22.10.2026, Auftrag Sascha).
- Überall, wo `llamacpp` behandelt wird (erfassung, aktionen, server, planung, Web-Oberfläche): `python_dienst` gleichwertig
  ergänzen – Kartenwahl („eine beliebige Karte“), Startdialog mit Freigaben, Stoppen, „GPU freigeben“ (der Dienst ist
  freigebbar; läuft gerade ein Auftrag, nennt der Dialog das).
- Tests `zentrale/tests/test_python_dienst.py` nach Vorbild `test_llamacpp.py`. Alle bestehenden Tests bleiben grün.

## Teil C: Atelier (`atelier/`)

- `atelier/server.py` (Standardbibliothek, Python wie die Werkstatt), Port 3896, `GET /api/health` liefert die Kennung,
  die `gemeinsam/starter.py` erwartet; `atelier/start.py` wie `werkstatt/start.py` (App-Name `atelier`, Titel „Atelier“,
  Logname `atelier-dienst`, Fenster 1440,920).
- Web: `atelier/web/index.html`, `app.js` (+ weitere Module nach Bedarf), `style.css` im Stil der Werkstatt (Farben/Schrift
  aus `werkstatt/web/style.css` übernehmen). Leinwand mit **Fabric.js 6.4.3**, liegt bereits unter
  `atelier/web/vendor/fabric-6.4.3.min.js` (MIT, `FABRIC-LICENSE.txt`, SHA-256
  `97b581df131f8c33871b1d9201b3058923a027dfca50520d1bc92a25aeec4255`). Kein CDN, kein npm.
- Projekte unter `C:\Workstation\Arbeitsmaterial\Atelier\<Projekt>\`: `projekt.json` (Format, Ebenen als Fabric-JSON plus
  eigene Felder), `ebenen\` (Bilddateien, beim Hinzufügen hineinkopiert), `export\`. Automatisch speichern (verzögert, 2 s) und
  „Speichern“. Projektnamen säubern, kein Pfad-Ausbruch. Ordner `_fibo` ist kein Projekt.
- Oberfläche:
  - Kopfleiste: Projekt (Neu, Öffnen, Umbenennen), Format (YouTube-Thumbnail 1280×720, Instagram 1080×1080, Story
    1080×1920, Flyer A5 hoch 1748×2480, Flyer A4 hoch 2480×3508, Eigenes), Rückgängig/Wiederholen (Strg+Z/Strg+Y), Export,
    Anzeige Fibo-Dienst („bereit“ / „aus – in der Modellzentrale starten“ / „rechnet x/50“).
  - Links: Ebenenliste (Ziehen zum Umsortieren, sichtbar, gesperrt, Name, Deckkraft, Löschen, Duplizieren).
  - Mitte: Leinwand, an das Fenster angepasst, Zoom; Hilfslinien Mitte/Ränder mit Einrasten; beim YouTube-Format die Ecke
    unten rechts (Zeitstempel) als Hinweisfläche einblendbar.
  - Rechts: Eigenschaften der Auswahl und KI-Aktionen.
  - Ebenenarten: **Bild** (Datei hineinziehen oder wählen, aus der Studio-Bibliothek, aus einem Fibo-Ergebnis), **Text**
    (Fabric-Textbox; Schrift aus einer festen Liste installierter Windows-Schriften, z. B. Arial Black, Impact, Bahnschrift,
    Segoe UI, Georgia; Größe, Farbe, Kontur mit Breite, Schatten, Ausrichtung, Zeilenabstand), **Form** (Rechteck mit
    Rundung, Kreis; Füllung, Kontur), Hintergrundfarbe der Leinwand.
  - Verschieben, Skalieren, Drehen, Spiegeln, Ausrichten (links/mitte/rechts/oben/unten an der Leinwand), Pfeiltasten (Umschalt = 10 px),
    Entf löscht.
- KI-Aktionen (nur aktiv, wenn der Fibo-Dienst bereit ist; sonst Hinweis „Fibo in der Modellzentrale starten“):
  1. **Bild erzeugen**: Prompt, Beschreiber (DeepSeek Flash – Standard / direkt), Ziel „Hintergrund“ (Seitenverhältnis der
     Leinwand, ≈1 MP, danach auf Leinwandgröße gesetzt) oder „Objekt“ (quadratisch, danach optional freistellen). Fortschritt
     und Abbrechen.
  2. **Ebene bearbeiten**: ausgewähltes Bild + Anweisung → Edit Turbo (Standard) oder „Höchste Qualität (Dev, ≈6 min)“.
     Ergebnis ersetzt das Bild an gleicher Stelle und Größe; rückgängig machbar.
  3. **Bereich ändern**: Pinsel malt eine Maske auf das ausgewählte Bild (Pinselgröße einstellbar, Radierer), Anweisung →
     Bearbeiten mit Maske.
  4. **Freistellen**: ausgewähltes Bild über das Studio der Werkstatt (`/api/studio`, Art `freistellen`, schnell =
     BiRefNet; mit Motivbeschreibung = Qwen). Schnittstelle in `STUDIO.md` Abschnitt 10 nachlesen. Läuft Werkstatt/ComfyUI
     nicht: klare Meldung.
  5. **Zusammenführen**: alle sichtbaren Bild- und Form-Ebenen (ohne Text) zu einem Bild (≈1 MP) rendern → Bearbeiten mit
     Anweisung (vorbelegt: „Make the image one coherent photograph with matching lighting, color and perspective; keep every
     element in its place.“, änderbar), Turbo Standard. Ergebnis wird neue unterste Ebene „Zusammengeführt“, die Quellen
     werden ausgeblendet (nicht gelöscht). Text bleibt als echte Ebene obenauf.
  6. **Beschreibung ändern** (nur Fibo-Bilder): VGL-Felder als Formular (Kurzbeschreibung, Licht, Ästhetik, Kamera,
     Stil, Text) → „Neu rechnen“ mit gleichem Seed.
- Proxy: `atelier/server.py` leitet `/api/fibo/*` an `127.0.0.1:8098` und Freistell-Aufträge an die Werkstatt
  (`127.0.0.1:3895`) weiter und speichert Ergebnisse in `ebenen\` des Projekts.
- Lizenz und Kennzeichnung: Ebenen aus Fibo tragen das Merkmal „Fibo · nicht-kommerziell“ (in der Ebenenliste sichtbar).
  Export-Dialog: PNG/JPG (Qualität), Maßstab 1×; Warnung, wenn sichtbare Fibo-Ebenen enthalten sind („nur
  nicht-kommerziell“), und Hinweis, KI-Bilder bei Veröffentlichung zu kennzeichnen. Neben jedem Export eine JSON-Datei mit
  Quellen der Ebenen.
- Tests `atelier/tests/test_atelier.py` (unittest): Projekte anlegen/speichern/laden, Namen säubern, Pfadschutz, Hochladen,
  Proxy-Fehler bei ausgeschaltetem Fibo/Werkstatt (verständliche Meldung, kein 500 ohne Text).

## Verbindliche Präzisierungen (Gegenprüfung 22.10.2026)

Codex war nicht nutzbar (Modell `gpt-6-astra` mit ChatGPT-Konto abgelehnt, HTTP 400); Claude hat die Spec gegen den Code
geprüft. Diese Punkte gelten zusätzlich und gehen den Abschnitten oben vor:

1. **uv-Python startet ein Kindprozess.** `C:\LLM\runtimes\Fibo2\.venv\Scripts\python.exe` ist ein uv-Starter, der den
   eigentlichen Interpreter als Kindprozess startet. Erkennung in der Zentrale daher über **Skriptpfad + `--port 8098` in der
   Befehlszeile, egal welcher Interpreter**; die Grafikspeicher-Belegung gehört zum Kindprozess. Stoppen beendet **den ganzen
   Prozessbaum** (Eltern und Kind) und wartet, bis der Port frei ist. Test mit zwei Prozessen (Starter + Kind) wie
   PolyStrata-Tests mit Fake-Prozessliste.
2. **litellm lädt beim ersten Aufruf eine Preisliste aus dem Internet** (gemessen: 100 s Hänger bei Zeitüberschreitung). Der
   Dienst setzt vor dem Import `os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"`.
3. **Abbruch:** Die Pipeline hat `interrupt` (Attribut `_interrupt`, in `__call__` auf `False` gesetzt). Abbrechen setzt im
   `callback_on_step_end` `pipe._interrupt = True`; danach Ergebnis verwerfen (kein Bild speichern), Zustand `abgebrochen`.
4. **Eingabebilder** beim Bearbeiten vor der Pipeline auf höchstens 1,1 MP verkleinern (Seitenverhältnis halten, Vielfache
   von 16); Maske auf dieselbe Größe (NEAREST, dann 0/255). Größe der Anfrage höchstens 64 MB, sonst 413 mit Text.
5. **Schutz vor fremden Webseiten:** Alle `POST` im Dienst und im Atelier verlangen eine Kopfzeile (`X-Atelier: 1`), wie die
   Werkstatt `X-Werkstatt: 1`; ohne sie 403. Nur `127.0.0.1`.
6. **Freistellen über die Werkstatt** genau nach `STUDIO.md` §10: `POST http://127.0.0.1:3895/api/studio` mit
   `X-Werkstatt: 1`, `{"aktion":"erzeugen","art":"freistellen","prompt":"" | Motiv,"verfahren":"schnell" (nur bei leerem
   Prompt),"projekt":"","vorlagen":[{"art":"datei","pfad":"<absoluter Pfad>","rolle":"original"}]}`, Ergebnis über
   `GET /api/studio` (Auftrag) bzw. die Bibliothek abholen; vorher `freistellen_schnell_verfuegbar` und `comfy.laeuft` prüfen.
   Das Atelier kopiert das Ergebnis in `ebenen\` des Projekts.
7. **Turbo-Wechsel** kostet Zeit (16 GB von der Platte). Der Dienst meldet den Wechsel als Zustand `laedt_modell` und misst
   die Dauer im Begleit-JSON. Aufträge in der Warteschlange werden nicht umsortiert.
8. **Zentrale-Freigabe während eines Auftrags:** „GPU freigeben“/Stoppen fragt `GET /health`; ist `laufend` gesetzt, nennt der
   Dialog den laufenden Auftrag und beendet nur nach eigener Bestätigung (wie ComfyUI).
9. **Flyer-Größen:** Fibo liefert ≈1 MP. Für A5/A4 zeigt das Atelier bei Fibo-Ebenen, die über 100 % vergrößert sind, einen
   Hinweis „unscharf beim Druck“ (keine eigene Hochskalierung in diesem Bau).

## Nicht bauen

Kein Umbau an Werkstatt/Studio/ComfyUI; keine Installation; kein Scene Analyzer; kein LoRA-Training; keine Verknüpfung auf
dem Desktop (macht Claude nach der Abnahme); README/PLAN/AGENTS pflegt Claude.

## Sperrliste

Nicht ändern: `werkstatt/**`, `gemeinsam/**` (nur lesen; Ausnahme: nichts), bestehende Einträge in `zentrale/config.json`
(nur den neuen anhängen), `C:\LLM\**`, `D:\**`, `C:\Users\sasch\.dsh\**`, andere Worktrees, Hauptcheckout. Keine Installation,
kein Internet, kein echtes Modell laden (GPU ist Sache der Abnahme), keine Server auf 3894/3895/8095–8098 starten. Schlüssel nie
ausgeben.

## Verifikationsplan (Abnahme durch Claude)

1. `python -m unittest discover -s zentrale/tests`, `-s werkstatt/tests`, `-s atelier/tests` mit
   `C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`; `fibo/tests` zusätzlich mit
   der Fibo-Umgebung. Alles grün, Testzahlen nicht kleiner als vorher.
2. Echt: Fibo in der Zentrale starten → Karte gewählt, bereit < 300 s, nvidia-smi ≈17,5 GiB; Stoppen gibt frei;
   „GPU freigeben“ listet Fibo.
3. Echt über die API: `bild` mit `deepseek` und `keiner`, `bearbeiten` Turbo und Dev, mit Maske, Abbruch.
4. Atelier im Browser: YouTube-Projekt, Hintergrund von Fibo, Textebene mit Kontur, Bild aus der Studio-Bibliothek,
   Freistellen, Verschieben/Skalieren/Drehen, Zusammenführen, Export 1280×720 – Datei und Bildschirmfoto prüfen.
5. Diff lesen, `pfade_ausserhalb_cwd` prüfen, Sperrliste.

## Scheiben

1. Teil A + B (Fibo-Dienst, Zentrale-Art `python_dienst`, Eintrag `fibo2`).
2. Teil C ohne KI-Aktionen (Server, Projekte, Ebenen, Text, Formen, Formate, Studio-Bibliothek, Export).
3. KI-Aktionen im Atelier (1–6).
