# Plan: Schnellere H3-Dekodierung – erst ohne Update, ComfyUI 0.44 nur bei Bedarf (Entwurf 05.11.2026)

Stand: **Entwurf, drei Runden eingearbeitet (Runde 3 ohne erneutes Gegenlesen)** (Gegenlesen Astra xhigh, Protokoll `SPEC-comfyui-044-REVIEW-LOG.md`).
Nichts geladen, nichts aktualisiert. Freigabe je Phase durch Sascha.

## Anlass und Befund

Video „MiniMax H3 Just Got WAY FASTER!“ (Ok Todd AI, 04.11.2026). Nachgeprüft:
- Comfy-Org hat seit ~29.10.2026 `vae/minimax_h3_sol_vae_fp16.safetensors` (3,6 GB) und `_int8_convrot` (2,0 GB).
  Laut ComfyUI-Commit 0df1646 (PR #17411, Kijai) ein **destillierter, reiner Decoder** (ViT, 24 Schichten), der den
  ganzen Clip in einem Stück dekodiert – nicht kachelbar, Speicher wächst mit der Cliplänge. Erst ab **ComfyUI 0.44.0**.
- Bei uns: ComfyUI **`v0.37.0-5-gb0f4b7b2`** (21.09.2026), Frontend 1.53.6, comfy-kitchen 0.2.35, comfy-aimdo 0.5.5,
  torch 2.14.0+cu130, Python 3.13. 0.44 wechselt Frontend auf 1.57.6, comfy-kitchen 0.2.40, comfy-aimdo 0.6.0.
- **Einfachere Alternative ohne Update:** Comfy-Org bietet die klassische H3-Video-VAE auch als
  `vae/minimax_h3_video_vae_int8_convrot.safetensors` (2,8 GB statt 5,2 GB). Unser 0.37 erkennt INT8-ConvRot-VAEs schon
  (`comfy/sd.py`); Kijai nennt ~2× schnellere Dekodierung ab ComfyUI 0.36.
- Lizenz wie H3 (Befund 06.10.2026 bekannt).

## Ziel

Kürzere Dekodierzeit am Ende jedes neuen Videos (und ggf. weniger Speicher), **ohne** dass sich alte Aufträge bei
„Nochmal“ ändern. Ein ComfyUI-Update nur, wenn Phase A nicht reicht und Sol messbar mehr bringt.

## Phase A – INT8-Fassung der bisherigen VAE, ohne Update

### A1 Decoder je Auftrag festhalten
- Neues Auftragsfeld `vae_dekoder` aus der Liste `studio.video.dekoder` in `werkstatt\config.json`:
  Kennung → Datei, SHA-256, `rolle` (`ganz` = ersetzt die Video-VAE für Kodieren und Dekodieren; `dekodieren` = nur
  `VAEDecode`, für reine Decoder wie später Sol), `bedarf_zusatz_mib`. Zunächst eine Kennung `int8_v1`
  (`minimax_h3_video_vae_int8_convrot`, Rolle `ganz`). **Ohne Feld** rechnet ein Auftrag genau wie heute.
- **Kennungen sind unveränderlich:** Im Auftrag und in der Begleit-JSON stehen Kennung, Datei und SHA-256. Beim
  Rechnen müssen alle drei mit der Konfiguration übereinstimmen; eine neue Modellfassung bekommt eine neue Kennung
  (`int8_v2` …), ein bestehender Eintrag wird nie umgeschrieben.
- **Der Server ergänzt nie einen fehlenden Wert.** Wie bei `schnell`/`int8` setzt nur das Formular bzw. der Skill das
  Feld bei einer *neuen* Erzeugung (Vorgabe `studio.video.dekoder_standard`, anfangs leer = wie heute); „Nochmal“
  (`wiederAnfrage` in `web\studio.js`) und der Skill reichen `info.vae_dekoder` unverändert weiter (fehlt es, bleibt es
  weg). Die Prüfung lehnt unbekannte Kennungen ab; passt Datei oder Prüfsumme nicht, gibt es eine klare Fehlermeldung
  statt eines stillen Rückfalls.
- Weitergereicht durch Begleit-JSON, Bibliothek, Szenenfolge (jede Szene trägt das Feld der ersten), Weiterführen,
  `einstellungen_aus_graph` (liest die Datei aus dem gespeicherten Graph) und `scripts\studio.py`.

### A2 Graph-Aufteilung
- Rolle `ganz` (Phase A): `vae_name` von Knoten 3 wird die INT8-Datei; sonst bleibt der Graph gleich. Es wird
  **keine zweite VAE** geladen, der Speicher sinkt eher (2,8 statt 5,2 GB) – `bedarf_zusatz_mib` = 0.
- Rolle `dekodieren` (nur vorbereitet, für Phase B): Kodieren bleibt an Knoten 3/22 (Start-/Endbild,
  Referenzbilder/-videos, `MiniMaxH3AddGuide`; Audio 4/23 unverändert), nur `VAEDecode` (Knoten 14, auch Quelle von
  `ImageFromBatch` 46 beim Weiterführen) bekommt einen eigenen `VAELoader` + `SelectVAEDevice`; `_bedarf` addiert
  `bedarf_zusatz_mib`. Werte dafür erst aus einer eigenen Kalibrierung, nicht aus der Dateigröße.

### A3 Tests (`werkstatt\tests`)
- Ohne Feld: Graph JSON-gleich zu heute für Text, Bild (Start/Ende), Referenz (Bild/Video), alle vier
  Weiterführen-Modi, Szenenfolge; `_bedarf` unverändert.
- Mit Feld `int8_v1`: nur `vae_name` von Knoten 3 anders, in allen diesen Arten; Rolle `dekodieren` mit Testeintrag:
  richtige Knoten/Verbindungen und Zuschlag in `_bedarf`.
- „Nochmal“: Altauftrag ohne Feld nach Umstellen von `dekoder_standard` auf `int8_v1` → weiter heutiger Graph
  (Server-Weg und die von `wiederAnfrage` erzeugte Anfrage); Auftrag mit Feld behält es; unbekannte Kennung oder
  abweichende Datei/Prüfsumme → Fehler.

### A4 Messen (Download 2,8 GB nach Saschas Ja, SHA-256 gegen Hugging Face)
- **Gleiche Latents garantiert:** Vergleichsgraph = normaler Videograph mit **zwei** `VAEDecode` an derselben
  Latent-Ausgabe (Knoten 13): einmal bisherige VAE, einmal INT8; beide speichern Bildfolge (PNG) + denselben Ton.
  Kein zweites Sampling, kein Laufzeitwechsel. Reihenfolge einmal vertauscht (gegen Warm-/Kalt-Effekte).
  Dekodierzeit je Knoten aus den ComfyUI-Ausführungsmeldungen (`executing`-Zeitstempel über die Websocket-Verbindung),
  Speicherspitze per `nvidia-smi`-Abfrage (alle 0,2 s) auf der VAE-Karte.
- Gesendet direkt an ComfyUI (8188 für geteilt, 8189 für ganz auf der Suprim) mit festen `SelectModelDevice`/
  `SelectVAEDevice`-Werten, mit Anmeldung `bild-video`/`bild-video-2` bei `/api/platz`, Verlängern bis zum bestätigten
  Ende (wie Stufe 3s); bei belegten Strata-Karten wird gewartet. Weil dieser Vergleichsgraph beide VAEs lädt (+2,8 GB),
  läuft der Ein-Karten-Fall als **Kalibrierung mit exklusiver Karte**: vorher prüfen, dass auf der Suprim nichts anderes
  rechnet, Anmeldung mit dem vollen freien Platz der Karte, kein zweiter Studio-Auftrag in der Zeit. Reicht der Platz
  für den 15-s-Clip nicht, wird dieser Fall nur geteilt gemessen und das so vermerkt. Prozess, Karten, Cachezustand
  (vorher `/free`) je Lauf festgehalten.
- Clips (fest: H3 INT8 FL2VA, Turbo-Stufe des Studios, `schnell`, gleiche Nummer): Person mit Sprache 6 s und Bewegung
  10 s bei 960×544, 15 s bei 1344×768 (362 Bilder) – je in beiden Verteilungen ⇒ **6 Samplingläufe**, je mit zwei
  Dekodierungen. Dauer vorab aus der Zeitschätzung des Studios summiert und Sascha genannt (Erwartung ~35–45 min).
- **Gesamtbetrieb** über die Werkstatt (normaler Weg, Rolle `ganz`, kein Doppel-Decoder): je ein End-zu-End-Auftrag
  Text → Video und Bild → Video mit und ohne `int8_v1` (Bild → Video zeigt auch, ob INT8-Kodieren das Startbild
  verändert); dazu **dieselben zwei Videos gleichzeitig** (Prozess 1 + 2) einmal ohne und einmal mit `int8_v1` unter
  gleichen Startbedingungen (`/free`, gleiche Karten): gemeinsame Fertigstellungszeit, RAM und VRAM-Spitze je Karte.
- **Monitorkarte** (Wunsch Sascha 05.11.2026): derselbe Clip (Text → Video, 960×544 6 s und 1344×768 10 s, `int8_v1`)
  ganz auf der FE und ganz auf der Suprim **mit Monitor** (direkt an 8189, Anmeldung `bild-video-2`, sonst nichts auf
  der Suprim). Gemessen: Rechenzeit, Speicherspitze samt Windows-Anteil, freier Rest, Auslagern (Gemeinsamer GPU-Speicher
  laut Windows-Leistungszähler `GPU Adapter Memory\Shared Usage`), Ruckeln des Bildschirms (Sascha sieht hin).
  Ist die Suprim höchstens ~10 % langsamer, ohne Auslagern und Ruckeln, wird vorgeschlagen, die Regel „nie ein Video
  ganz auf der Monitorkarte“ für Aufträge mit `int8_v1` zu lockern (eigene kleine Änderung nach Saschas Ja; dann
  zwei Videos gleichzeitig auch mit Monitor an der Suprim).
- Qualität: Pixelabstand INT8 ↔ fp16 je Bild (max., Mittel, Anteil > 2/255) + Blindvergleich (Gesichter, Hände,
  Schrift, Flimmern), ehrlich benannt.
- Kontrolle: ein alter Auftrag ohne Feld über „Nochmal“ → dekodierte Bilder und PCM-Ton identisch zum Original
  (Vergleich der Spuren, nicht der Dateiprüfsumme – Begleitdaten im MP4 ändern sich absichtlich).

### A5 Entscheidung Sascha
`dekoder_standard = int8_v1` für neue Videos nur, wenn: Dekodierzeit ≥ 25 % kürzer, Gesamtzeit je Auftrag nicht länger,
gemeinsame Fertigstellungszeit bei zwei Videos nicht länger, kein sichtbarer Unterschied im Blindvergleich (auch beim
Startbild von Bild → Video). Sonst bleibt der Standard
leer (wie heute); der Code bleibt für spätere Decoder.

### A6 Bau
Codex Sol medium im Worktree (Skill `codex-build`), Abnahme Claude gegen A3/A4. Nachziehen wie unten.

## Phase B – ComfyUI 0.44 und Sol (nur Skizze; eigene Planung und eigenes Gegenlesen, falls Sascha nach A will)

Bekannte Vorbedingungen aus dem Gegenlesen (nicht erschöpfend):
- `gehoert_zu_comfy` (`zentrale\erfassung.py`) erkennt Nachbarordner `ComfyUI-…` (Prüfung `startswith` **und**
  `comfy_ordner in cmd`) als Studio – beide auf exakte Ordnergrenze umstellen. Erfassung, Werkstatt und Studio wählen
  nur den ersten `art == 'comfy'`-Eintrag – ein getrennter Testverbraucher braucht eigene Erfassungslogik.
- `_comfy_starten` (`zentralektionen.py`) und `_modell_da` (`werkstatt\studio.py`) prüfen Modelle unter
  `comfy_ordner\models` – vor einem Laufzeitwechsel einen von der Laufzeit unabhängigen Modellpfad einführen.
- Zweite vollständige Laufzeit (eigenes `.venv`, Paketliste und Frontend festgehalten), alter Ordner bleibt als
  Rückweg; Wechsel und Rückwechsel als getesteter Ablauf (Annahme anhalten, Arbeit abschließen, Testprozess stoppen,
  Laufzeit + `dekoder_standard` gemeinsam wechseln, Dienste neu laden, inkompatible wartende Aufträge zurückhalten).
- Ausführungstests je Modellart mit Nachweis der comfy-kitchen-Kerne, Replay-Adapter, risikobasierte Gleichheitsmatrix,
  Entscheidung über die „Nochmal“-Zusage für Bilder und Videos; Sol nicht kachelbar → Bedarf ganz auf einer Karte neu.

## Nachziehen (fester letzter Schritt jeder Phase)

PLAN.md (Stufe, Messwerte, Befund), STUDIO.md (VAE-Zeile, Zeiten, ggf. „Geprüft und verworfen“), Skill
`bild-video-studio` (SKILL.md, `scripts\studio.py`), AGENTS.md (ComfyUI-Version, falls Phase B).

## Nicht Teil des Plans

Molmo2-Text-Encoder, Motion Dials, D-RoPE (fremde Knoten bzw. veränderte Gesichter), LightVAE, H3-Latent-Upscaler
(eigene Prüfung, falls gewünscht).

## Offene Fragen an Sascha

1. Phase A (INT8-VAE ohne Update, 2,8 GB) zuerst – einverstanden?
2. Schwelle aus A5 (≥ 25 % Dekodierzeit, Gesamtzeit und Durchsatz nicht schlechter, kein sichtbarer Unterschied) – passt das?
