# Spec: Studio-Art „Video hochrechnen“ (1080p mit Open-H3-Regenerate-2K)

_Stand 05.11.2026, Claude, nach Codex-Runden 1–3 (Astra xhigh); Reste entschieden von Claude._ Auftrag Sascha nach Test A (PLAN.md, „Vorgemerkt für 31.10.2026“, Test A): „als
zusätzlichen Knopf integrieren … hochwertiges Bild, aber nicht 100 % originalgetreu – das ist ok.“_

## Ziel

Ein fertiges Studio-Video (MiniMax-H3, 960 × 544, Ton) lässt sich mit einem Knopf in der Großansicht auf 1920 × 1088
neu rechnen: deutlich schärfer, gleicher Bildaufbau, gleiche Bewegung und Mundformen, **Originalton**. Bekannte Grenze,
in der Oberfläche benannt: Gesichter werden glatter/jünger, kleine Gegenstände können sich ändern. Das Original bleibt
unverändert; das Ergebnis ist eine neue Datei mit Begleit-JSON in der Bibliothek.

## Gemessener Ablauf (Test A, 05.11.2026 – genau so übernehmen)

Kernknoten ComfyUI 0.37.0, Graph aus `SPEC-video-hochrechnen-referenz.py` (Funktion `graph()`):

1. `LoadVideo` (Quelle aus der Bibliothek, `<pfad> [output]`) → `GetVideoComponents` (Bilder, Ton).
2. `ImageScale` lanczos auf Zielgröße, `crop: disabled`.
3. `VAEEncode` mit der bisherigen H3-Video-VAE (`modelle.vae_video`, fp16) → Video-Latent.
4. `MiniMaxH3ImageToVideo` (Text-Encoder, Prompt, Zielgröße, Länge = Bilder der Quelle) → Conditioning + leeres AV-Latent;
   `LTXVSeparateAVLatent` nimmt daraus den (leeren) Tonteil; `LTXVConcatAVLatent` setzt Video-Latent + Tonteil zusammen.
5. `MiniMaxH3AddGuide` mit dem Originalton (`frame_idx` 0, `audio_vae`) → Ton bleibt als Führung fest.
6. Modell: `UNETLoader` ref2va INT8 (`modelle.ref2va`) → `SelectModelDevice` → `LoraLoaderModelOnly` (umgerechnete
   Regenerate-LoRA, Stärke 1,0) → `ModelAttentionBackend` (`comfy kitchen attention`, wie `schnell`).
7. `KSamplerSelect` euler, `ManualSigmas` `0.909375, 0.857143, 0.666667, 0.0`, `RandomNoise` (Variationsnummer),
   `BasicGuider`, `SamplerCustomAdvanced`.
8. `VAEDecode` mit der INT8-VAE (`dekoder.int8_v1.datei`), `CreateVideo` (24 fps), `SaveVideo`.

**Abweichung vom Testlauf (Runde 1/2):** Der Ton wird auf exakt die Bilddauer gebracht – `TrimAudioDuration` (Start 0,
Dauer = Bilder / 24) und, wenn der Quellton kürzer ist (bis 25 ms erlaubt `mp4_info`), mit `EmptyAudio` + `AudioConcat`
aufgefüllt, genau wie `quellton` in `weiter_graph` (dieselbe Hilfe wiederverwenden). Derselbe normalisierte Originalton führt bei `MiniMaxH3AddGuide` und kommt **direkt** in `CreateVideo` (kein
`VAEDecodeAudio`): echter Originalton, bildgenau, ohne den 4,5-ms-Versatz der Ton-VAE.

Messwerte: 124 Bilder 960 × 544 → 1920 × 1088 in 373 s bzw. 369 s **mit Laden** (Prozess 1: Modell FE, Text-Encoder
und VAE Suprim); Spitze Modellkarte 23,8 GiB (7–8,6 GiB in den gemeinsamen Speicher ausgelagert), andere Karte 7,4 GiB.
Ton: Korrelation 0,98 zum Original.

## Umsetzung

### A1 Modelldatei und Umrechnung
- Die LoRA liegt umgerechnet als `ComfyUI\models\loras\open_h3_regenerate_2k_comfy_bf16.safetensors`
  (9.421.966.736 Byte, SHA-256 `0291f98110844496fdef4f3b9a8cd3a47cbf66b0dc8de9e59378ca37502532cd`), Quelle
  `open_h3_regenerate_2k_lora.safetensors` (SHA-256 `8e36a091…0bb04`) + `open_h3_regenerate\sharp_curve_branches.safetensors`.
- Das Umrechnungsskript kommt (verschärft, s. u.) als `werkstatt\regenerate_lora.py` ins Repository (Inhalt = `SPEC-video-hochrechnen-lora.py`,
  Pfade als Argumente `--quelle --kurve --ziel`, Aufruf im ComfyUI-venv, wie `pdf_seiten.py` ein externes Werkzeug; die
  Werkstatt ruft es **nicht** auf). Docstring nennt die Umrechnungsregeln (qkv Blockdiagonale, fc1-Hälften getauscht,
  Sharp-Zweige auf `adaln_proj.linear`). Verschärfung: prüft vor dem Speichern **alle** Module (52 Blöcke × 4 Ziele,
  50 Kurvenzweige), Zielschlüssel und Formen gegen das Modell (`--modell` = ref2va-Datei, nur Header lesen), Delta-Fehler
  je Modul (bf16 gegen fp32) endlich und < 0,2 %; fehlt etwas oder liegt ein Wert darüber → Abbruch ohne Datei.
  Ausgabe: SHA-256 der neuen Datei. (Die vorhandene Datei wird nach dem Bau damit neu erzeugt; ergibt sich eine andere
  Prüfsumme, trägt Claude nach Prüfung die neue ein.)

### A2 Einstellungen (`werkstatt\config.json`, `studio.video.hochrechnen`)
```json
"hochrechnen": {
  "aktiv": true,
  "lora": "open_h3_regenerate_2k_comfy_bf16.safetensors",
  "lora_sha256": "0291f98110844496fdef4f3b9a8cd3a47cbf66b0dc8de9e59378ca37502532cd",
  "sigmas": "0.909375, 0.857143, 0.666667, 0.0",
  "ziel_pixel": 2088960,
  "max_bilder": 124,
  "zeit": {"grund_s": 120, "je_bild_s": 2.0},
  "bedarf_mib": {"haupt": 22528, "neben": 9216},
  "commit_frei_mib": 36864,
  "grund": "…Test A 05.11.2026, Messwerte, Grenze Gesicht/Gegenstände…"
}
```
- `ziel_pixel` = 1920 × 1088. Zielgröße: Quelle × Faktor, Faktor so, dass Breite × Höhe ≤ `ziel_pixel`, beide Seiten
  Vielfache von 32, Seitenverhältnis wie die Quelle (±1 Raster); 960 × 544 → 1920 × 1088, 544 × 960 → 1088 × 1920,
  768 × 768 → 1440 × 1440 (Funktion `hochrechnen_masse(breite, hoehe, ziel_pixel)`, rein, getestet).
- `max_bilder` 124 (gemessen sind nur 5 s). Längere Quellen → klare Meldung („bisher bis 5 s geprüft“). Die Länge muss
  17k + 5 Bilder sein (H3-Raster), sonst Meldung.
- `bedarf_mib` (neben 9.216 MiB: 7,4 GiB gemessen + Reserve) in den Rollen, die die Kartenwahl für geteilte Videos schon kennt (`haupt` = Modellkarte, `neben` =
  Text-Encoder/VAE). **Nur geteilt** über Prozess 1 (beide Karten), Modell nie auf der Monitorkarte; keine
  Ganz-auf-einer-Karte-Variante, kein Prozess 2. Der Builder prüft in `verteilungen`/`karten_waehlen`, wie ein
  bestehendes geteiltes Video das erreicht, und benutzt denselben Weg (keine neue Bedarfsrolle, wenn eine passende da ist).
- **Monitorkarte hart ausgeschlossen (Runde 1):** In `karten_waehlen` ist „Modell nicht auf der Monitorkarte“ nur ein
  Sortierkriterium. Für `video_hochrechnen` werden Verteilungen mit Hauptrolle auf einer Monitorkarte **vor** der
  Bewertung verworfen; passt sonst nichts, wartet der Auftrag. Test: FE 18.000 frei, Suprim (Monitor) 23.000 frei → wartet.
- **Arbeitsspeicher (Entscheid Claude nach Runde 3):** ComfyUI hält Modell (21 GB) + LoRA (9,4 GB) im RAM. Ein
  verlässlicher „warm“-Nachweis fehlt (Entladen über die Zentrale ändert PID/Prozess nicht) – deshalb keine
  warm/kalt-Logik. Geschützt wird nur gegen den Absturz: Vor dem Senden an ComfyUI prüft die Werkstatt den freien
  Commit-Spielraum (Windows `GlobalMemoryStatusEx`, `ullAvailPageFile`, ctypes, Standardbibliothek) gegen
  `commit_frei_mib`; zu wenig → Auftrag wartet mit Hinweis „wartet auf Arbeitsspeicher“ (prüft erneut wie beim
  Platz-Warten), kein Fehler. Physischer RAM wird nicht geprüft (128 GB + feste Auslagerungsdatei; schlimmstenfalls
  langsamer). Funktion austauschbar für Tests.

### A3 Auftrag (`studio.py`)
- Neue Art `video_hochrechnen` in `VIDEO_HILFS_ARTEN` (gleiche Vorlage-Regeln wie Zeitlupe: genau ein Video als
  `original`, aus der Bibliothek oder von Sascha gewählt; Projektprüfung wie dort).
- `hochrechnen_verfuegbar()`: `aktiv`, LoRA-Datei da (`_modell_da('loras', …)`), ref2va, `vae_video`, `vae_audio`,
  INT8-VAE, Text-Encoder da. Im Status als `hochrechnen_verfuegbar`.
- Prüfung `_video_hilfe_pruefen` (Zweig für die neue Art): Maße/Bilder über `video_masse`, Ton über `mp4_info` (Quelle
  ohne Ton → Meldung „Nur Videos mit Ton aus dem Studio“; Tondauer > Bilddauer + 1 s → Meldung; der Graph kürzt den
  Ton ohnehin auf die Bilddauer), `max_bilder`, 17k+5. Auftragsfelder:
  `breite`/`hoehe` = **Zielgröße**, `quell_breite`, `quell_hoehe`, `quell_bilder`, `bilder` (= Quelle),
  `prompt` = Prompt aus der Begleitdatei der Quelle (fehlt sie: leer, erlaubt), `variation` (aus der Anfrage, sonst
  zufällig wie bei Videos), `quell_sha256` (Prüfsumme der Quelle beim Anlegen),
  **`hochrechnen`** = alle ergebnisbestimmenden Werte, beim Anlegen aus der Einstellung eingefroren:
  `{kennung: 'regenerate_v1', lora, lora_sha256, sigmas, modell (ref2va-Datei), clip, vae_kodieren (vae_video),
  vae_dekoder {datei, sha256} (INT8), vae_audio, fps, ziel_breite, ziel_hoehe, aufmerksamkeit}`. Unveränderlich im
  Auftrag und vollständig in der Begleitdatei; „Nochmal“ schickt das Objekt samt `prompt`,
  `variation` und `quell_sha256` zurück, der Server übernimmt es nach Prüfung (Schlüssel/Typen, Dateien vorhanden,
  LoRA- und INT8-Prüfsumme **gegen die tatsächliche Datei**, nie gegen den aktuellen Standard); fehlt eine Datei oder
  passt die Prüfsumme nicht → Fehler statt stillem Ersatz. **Unmittelbar vor jedem Rechnen** (nach dem Warten) werden
  Quelle, LoRA und INT8-VAE erneut gegen die eingefrorenen Hashes geprüft; die SHA-256 großer Modelldateien wird je
  (Pfad, Größe, Änderungszeit) zwischengespeichert, damit nicht jeder Lauf 9,4 GB liest.
  Ohne mitgeschicktes Objekt (neuer Auftrag) wird es aus der Einstellung gebaut.
- `quell_sha256`: neuer Auftrag → beim Anlegen berechnet; „Nochmal“ → der gespeicherte Wert kommt mit und wird **beim
  Anlegen** gegen die aktuelle Datei verglichen (Abweichung → „Das Ausgangsvideo wurde seitdem verändert“); vor dem
  Rechnen erneut (wie bei Weiterführen). Ein aus Fremd-/Altmetadaten erkannter Auftrag ohne Hash gilt nicht als
  identische Wiederholung (Hinweis wie bei anderen Arten ohne Beleg).
- `hochrechnen_graph(e, v, praefix, clip)`: genau der Referenzgraph; Geräte aus der Kartenwahl
  (`mit_geraeten`), Modell auf der Hauptkarte, Text-Encoder/VAE/Ton-VAE auf der Nebenkarte.
- `_bedarf`, `_erwartet` (`grund_s + je_bild_s × bilder`), Dateiname-Präfix „Hochgerechnet“, Meta: `modell`
  „Open-H3-Regenerate-2K“, `modell_datei` (ref2va), `lora`, `lora_sha256`, `quell_bilder`, `quell_breite/hoehe`,
  `quell_sha256`, `laenge_bilder`, `sekunden`; `turbo/referenz_genau/ton_behalten` None wie bei Zeitlupe.
- `einstellungen_aus_graph`: Der Referenzgraph würde heute als `video_bild`, `turbo=True`, ohne `vae_dekoder` gelesen
  (ManualSigmas-Erkennung, INT8-Suche an Knoten 3). Hochrechnen wird **vorher und gesondert** erkannt (LoraLoader mit
  einer Regenerate-LoRA + `VAEEncode` + `LTXVConcatAVLatent`) und liefert art, prompt, variation, Zielgröße und das
  `hochrechnen`-Objekt aus den verbundenen Knoten (Kodier- und Dekodier-VAE getrennt). Die bestehende Turbo-/VAE-
  Erkennung bleibt unverändert; Regressionstest mit `tests\vae_dekoder_altgraphen.json` und einem Turbo-Bildgraphen.

### A4 Oberfläche (`web\studio.js`)
- `video_hochrechnen` in `ROLLEN` (`['original']`), Bezeichnung, `VIDEO_HILFEN`-Behandlung so, dass `wiederholbar` für
  diese Art **trotz leerem Prompt** gilt und `wiederAnfrage` Originalvorlage, `hochrechnen`, `prompt`, `variation`,
  `quell_sha256` mitschickt (bei anderen Hilfsarten nichts ändern).
- **„Mit Änderungen“ ist für diese Art aus** (Knopf deaktiviert mit Titel „Für Hochgerechnet nicht verfügbar – Nochmal
  oder neu hochrechnen“); nur „Nochmal“. Die Zusage „Mit Änderungen“ in A3 entfällt.
- In der Großansicht eines MP4 in der Zeile „Bearbeiten:“ ein Knopf **„Hochrechnen 1080p“** (nur wenn
  `hochrechnen_verfuegbar`), Titel: „Rechnet das Video in 1920 × 1088 neu: viel schärfer, Ton bleibt. Nicht ganz
  originalgetreu – Gesichter oft glatter und jünger, kleine Gegenstände können sich ändern. Etwa 6 Minuten. Bis 5 s.“
  Meldung nach dem Start: „Das Video wird hochgerechnet (1920 × 1088, etwa 6 Minuten).“
- Detailzeile im Auftrag/der Großansicht: „Hochgerechnet: 960 × 544 → 1920 × 1088, Ton aus dem Original“.
- Bezeichnung der Art in den Listen: „Hochgerechnet“.

### A5 Tests (`werkstatt\tests\test_hochrechnen.py`)
- `hochrechnen_masse` (Quer, Hoch, Quadrat, schon groß → Faktor 1 bleibt erlaubt? → nein: Zielgröße muss größer als
  Quelle sein, sonst Meldung).
- Graph: Knoten/Verbindungen wie Referenzgraph, Sigmas, LoRA aus dem Auftrag, Geräte aus der Kartenwahl, INT8-VAE nur
  beim Dekodieren, fp16-VAE beim Kodieren, Ton-Führung.
- Prüfung: ohne Ton, zu lang, kein 17k+5, falsche Endung, fehlende LoRA → Meldungen; Feld `hochrechnen` unveränderlich
  (Einstellung ändern → alter Auftrag rechnet mit altem Wert); geänderte Quelle → Fehler.
- Kartenwahl: nur Prozess 1 geteilt, Modell nie auf der Monitorkarte (auch wenn dort mehr frei ist); wartet sonst.
- Ton: auf exakt `round(bilder / fps × rate)` Samples gebracht (kürzen bzw. mit Stille auffüllen), gleicher Ton an
  Führung und `CreateVideo`, kein `VAEDecodeAudio`.
- Vor dem Rechnen: geänderte LoRA/INT8-VAE (anderer Hash als im Auftrag) → Fehler; Prüfsummen-Zwischenspeicher.
- Commit-Prüfung: zu wenig → wartet; genug → läuft.
- `einstellungen_aus_graph`: Hochrechnen-Graph → richtige Art und Objekt; Altgraphen und Turbo-Bild unverändert.
- „Nochmal“: mitgeschicktes Objekt wird übernommen (Einstellung inzwischen geändert → alter Wert), falscher
  `quell_sha256` → Meldung beim Anlegen; JS-Teil (`wiederholbar`/`wiederAnfrage`) in der Live-Abnahme.
- Umrechnungsskript: Prüffunktion mit kleinen Kunsttensoren (fehlendes Modul, falsche Form, zu großer Fehler → Abbruch).
- Bestehende Tests unverändert grün (Werkstatt 283, Zentrale 193).

### A6 Skill `bild-video-studio` (macht Claude nach der Abnahme, nicht der Builder)
`scripts\studio.py hochrechnen <video.mp4> [--variation n]`, SKILL.md-Zeile mit Grenze; STUDIO.md, PLAN.md.

## Nicht Teil
- Kein Latent-Hochskalierer (kein Kernlader in 0.37), kein `vae_fast`, kein 2K/4K, keine längeren Clips als 5 s
  ohne neue Messung, keine Änderung an bestehenden Videoarten, kein ComfyUI-Update, keine neuen Pakete.
- Keine automatische Umrechnung der LoRA durch die Werkstatt.

## Abnahme (Claude)
1. Tests grün. 2. Diff gelesen. 3. Live (mit gefüllten Caches, Prozess 2 rechnet währenddessen ein Bild): Knopf an `Werkstatt-Abnahme/Video-Real-B-n11_00001_.mp4` → Ergebnis gleich
   aufgebaut wie der Testlauf (1920 × 1088, 124 Bilder; Ton: Dauer gleich ±1 Bild, Korrelation zum Original ≥ 0,99 bei Versatz ≤ 1 ms – AAC wird
   beim Speichern neu kodiert, bitgleich sind nur die PCM-Samples vor `CreateVideo`, belegt im Graph-Test), Zeit ≈ 6 min,
   Begleit-JSON mit `hochrechnen`; gleich danach ein zweites Hochrechnen (Commit-Prüfung lässt es durch).
   „Nochmal“ nach `/free` (Modelle entladen, Cache leer): neue Datei, ComfyUI-Verlauf ohne zwischengespeicherte Knoten,
   Bildvergleich mit dem ersten Ergebnis (gleich bzw. nur Rundungsunterschiede). 4. Doku und Skill nachgezogen.

## Risiken / offen
- Laden der 9,4-GB-LoRA kostet bei jedem ersten Lauf Zeit; ComfyUI hält sie danach im Speicher (RAM-Bedarf ~31 GB
  zusätzlich, abgefangen durch `commit_frei_mib`) – in der Abnahme prüfen, dass ein normales Video danach unverändert läuft.
- Auslagerung auf der FE (7–8,6 GiB): Monitor liegt an der Suprim, Ruckeln dort nicht zu erwarten.
- Strata belegt beide Karten → Auftrag wartet (Platz-Tor), wie andere geteilte Videos.

## Referenzdateien
`SPEC-video-hochrechnen-referenz.py` (Testlauf-Graph) und `SPEC-video-hochrechnen-lora.py` (Umrechnung), beide
unverändert aus Test A; nach dem Bau bleiben sie als Beleg liegen.
