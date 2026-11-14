# SPEC: Edge0-145B als Zentrale-Eintrag

Stand 14.11.2026, Entwurf Claude, Auftrag Sascha („Ja, planen“). Noch nichts geladen oder installiert.
Anlass: Video „Edge0-145B … runs on 1 GPU“ (Shaown Ships AI). Lizenz spielt keine Rolle (private Nutzung).

## Ziel

Edge0-145B (Q3_K) als neuer Eintrag in der Zentrale, auf **einer** RTX 3090 nach Kartenwahl, OpenAI-API auf
`127.0.0.1:8109`. Prüfen, ob er Flash-Next über Strata ersetzen kann: ähnlich gut bei Coding/Agentenarbeit,
die zweite Karte bleibt aber frei (Studio-Video, Whisper, OCR).

## Was feststeht (Modellkarte, GitHub Edge0-AI/Edge0 v0.2.0)

- Edge0 ist ein Umbau von **Qwen3.8 Flash-Next** zu einem „Latent MoE“ (512 Experten je Schicht, 10 + 1 aktiv,
  10,1 Mrd. aktiv, 256K Kontext, Vorlage nutzt 128K mit KV int8). Kein Bildteil.
- Engine **edge0-strata** = Strata-Abspaltung (Basis Strata-Commit vom 31.10.2026). Gleicher Aufbau wie unser
  Strata: `serve/server.py --engine strata --config <json> --port … --gpu …`, Einstellungsdatei mit `exe`, `args`,
  `env`, `lib_dirs`, `tokenizer`, `model_name`. Vorlage: `edge0-strata/edge0/models/edge0-145b.json`.
- Das Windows-Paket `edge0-chat-0.2.0-windows-x64.zip` (264 MiB, SHA-256 `c7146b76…31b9`) enthält die fertige
  Engine für Rechenstufe 7.5+ (unsere 3090: 8.6). Kein eigener Bau nötig (CUDA-Toolkit, Visual Studio, CMake und
  Ninja fehlen auf der Workstation und werden nicht installiert).
- Verlangt „CUDA Toolkit 13“; tatsächlich gebraucht werden nur die DLLs (`cublas64_13.dll` u. a.). Unser Strata holt
  sie aus `C:\LLM\runtimes\Strata\.venv\Lib\site-packages\nvidia\cu13\bin\x86_64` – denselben Weg nehmen.
- Modell `Edge0/Edge0-145B-q3k`: 93 Dateien, **98,1 GiB** (Experten 37,3 · PLE-Tabelle fp8 47,7 · Gerüst 5,6 ·
  D/U Q8 3,5 / Q4 1,9 · MTP 0,8 GiB). Die PLE-Tabelle wird mit `--ple-io direct` von der SSD gelesen, nicht in den RAM.
- Herstellerwerte Q3_K auf einer 24-GB-Karte: 23,1 GiB Grafikspeicher + 31,3 GiB RAM; RTX 4090 ~70 Token/s Chat,
  ~92 Agent, 3.179 Token/s Einlesen (16K). Die 3090 wird darunter liegen.

## Ablage

- Engine: `C:\LLM\runtimes\Edge0\` (Paket entpackt, nur der Teil `edge0-strata` und was `serve/server.py` braucht).
- **Geladen 14.11.2026:** Paket nach `C:\LLM\runtimes\Edge0\paket\edge0-chat-0.2.0-windows-x64\` (SHA-256 stimmt).
  Engine `edge0-strata\build\strata.exe` (Engine 0.1.55, CUDA 13.5, Architekturen 75/86/89/120) startet mit Stratas
  pip-DLLs (cuBLAS 13.0.2, cudart 13.0.96) – kein Toolkit nötig (nur `--help` geprüft, noch kein Lauf auf der Karte).
- Python: **mitgeliefert** in `edge0-strata\.venv\Scripts\python.exe` (3.12.10, eingebettet); `serve/server.py`
  läuft damit. Kein eigenes venv nötig.
- Modell: `C:\LLM\models\Edge0-145B-q3k\` (C: hat 1,3 TB frei; Ordner unverändert lassen, `model.json` nennt das Modell).
- Einstellung: `C:\LLM\runtimes\Edge0\edge0-145b-q3k-1gpu-128k.json`, aus der Vorlage mit festen Pfaden:
  `${MODEL_DIR}` → Modellordner, `${DU_FILE}` → `latent_dense_q8.bin`, `${DU_FMT}` → `8`, `${LAT_FUSED_Q3K}` → `1`,
  `${PLE_IO}` → `direct`, `lib_dirs` → cu13-Ordner oben, `exe` → Paket-Engine. Zusätzlich `--vram-reserve-mib` wie
  bei PolyStrata (Monitorkarte Suprim) und `--kv-resident 32768`.

## Bau (Code, an Codex Sol medium im eigenen Worktree)

Die Art `polystrata` macht schon fast alles (Strata-artiger Server, eine Karte, Kartenwahl mit `--gpu`,
`fit_max_tokens`). Änderungen in `zentrale\`:

1. `erfassung.py`, `ist_polystrata`: Engine-Name aus `os.path.basename(e['engine'])` statt fest `strata-poly.exe`;
   `vision_exe` optional (Edge0 hat keinen Bildteil).
2. Sicherstellen, dass `ist_strata` die Edge0-Engine (`strata.exe` in `C:\LLM\runtimes\Edge0\…`) **nicht** als
   Flash-Next-Strata zählt – auch im Fall „Pfad leer, Elternprozess entscheidet“ (Elternprozess ist dann Edge0s
   `server.py` mit Port 8109, nicht unserer). Reihenfolge der Erkennung so, dass Edge0 zuerst geprüft wird, falls nötig.
3. `aktionen.py`, `_polystrata_starten`: unverändert nutzbar; nur prüfen, dass fehlende `vision_exe` nichts bricht.
4. Neuer Eintrag `edge0-145b` in `config.json` (Art `polystrata`, Port 8109, `karten` [„RTX 3090“],
   `bedarf_je_karte_mib` zunächst 23.500, `ram_bedarf_gib` 34, `startzeit_max_s` 300, `fit_max_tokens` true,
   Name „Edge0 145B · Q3_K“, Untertitel „Flash-Next-Umbau · 128K · ohne Bilder · eine RTX 3090“).
5. Tests in `zentrale\tests` (Muster `test_polystrata.py`): Erkennung mit anderem Engine-Namen, ohne `vision_exe`,
   keine Verwechslung mit Strata (auch leerer Pfad). Alle bestehenden Tests grün.

## Abnahme (Claude, am echten System)

1. Start über die Zentrale: bereit innerhalb 300 s, `/health` meldet „loaded“, Anzeige „läuft“ mit Karte und Speicher.
   Flash-Next-Strata wird dabei nicht als laufend angezeigt.
2. Messung je zweimal, gleiche Prompts wie bei Strata (PLAN.md): Chat- und Code-Token/s, Einlesen 16K und 70K,
   Grafik- und Arbeitsspeicher. Vergleich mit Flash-Next Q4 v3.1 (88,7 Token/s, 2.014 Token/s Einlesen 32K).
3. Kurzer Qualitätsvergleich mit Flash-Next: zwei Coding-Aufgaben (z. B. eine Ein-Datei-Webseite, ein kleines
   Spiel) und eine Agentenaufgabe über DSH. Ergebnisse nebeneinander zeigen, ehrlich bewerten.
4. Beenden über die Zentrale: Prozessbaum weg, Speicher frei.
5. Läufe über ~15 min nur nach Rückfrage.

## Danach (nur nach Ergebnis und Saschas Ja)

- Variante „zwei Karten“ mit `--expert-cache-device1 auto` (fast alle Experten im Grafikspeicher) messen.
- Anbieter in DSH/Hermes eintragen, falls Edge0 bei Coding mithält.
- Doku: PLAN.md (Befund und Messwerte), README.md (Eintrag), AGENTS.md (Kurzeintrag).

## Freigaben, die vor dem Start nötig sind

- Download `edge0-chat-0.2.0-windows-x64.zip` (264 MiB, GitHub-Release Edge0-AI/Edge0 v0.2.0, SHA-256 prüfen).
- Download `Edge0/Edge0-145B-q3k` von Hugging Face (98,1 GiB) nach `C:\LLM\models\Edge0-145B-q3k`.
- Eigenes Python-venv für edge0-strata (falls Strata's venv nicht passt).

## Bauprotokoll

- 14.11.2026, Runde 1: Codex gpt-6.1-sol, medium, Worktree `bau/edge0` (Thread 01a1da95-…). Geändert: `erfassung.py`
  (Engine-Name aus der Konfiguration, `vision_exe` optional, Edge0 bei leerem Pfad über den eigenen Server erkannt),
  `aktionen.py` (Start/Beenden ohne Bildteil), `config.json` (Eintrag `edge0-145b`), 10 neue Tests in
  `test_polystrata.py`. Abweichung: `_polystrata_starten` musste angepasst werden (verlangte `vision_exe`) – sinnvoll.
- Urteil Claude: Diff gelesen, passt zum Spec, nichts außerhalb von `zentrale\`. Selbst geprüft: Zentrale 204 Tests OK,
  Werkstatt OK, config.json gültig. Keine Fixrunde nötig. Kleine Grenze: Der Rückgriff über den Elternprozess bei leerem
  Pfad greift nur, wenn die Engine `strata.exe` heißt (wie Strata) – genau der Edge0-Fall.
- Abnahme am echten System 14.11.2026: Start über die Zentrale (nach Korrektur der `env`-Pfade auf `/`) bereit nach
  23 s, Anzeige „bereit“ auf der FE, Flash-Next und Ornith bleiben „aus“; zwei Messläufe; Beenden räumt Prozesse,
  Grafik- und Arbeitsspeicher. Messwerte, RAM-Befund (~46 GiB) und Bildteil-Test in PLAN.md, „Edge0-145B als
  Zentrale-Eintrag (14.11.2026)“. Nachgezogen: `ram_bedarf_gib` 46, Gründe gemessen, Tests angepasst (204 OK).
- 14.11.2026, Runde 2 (Nachtrag „beide Karten“): Codex gpt-6.1-sol, medium, eigener Worktree, eine Runde; Diff gelesen,
  212 Tests OK, Zentrale neu gestartet. Am echten System: Absturz (#205), Hilfscache NaN – Bau wieder herausgenommen,
  Tests zurück auf 204 OK. Dafür Variante „RAM sparen“ (nur `config.json` und eine Einstellungsdatei), über die
  Zentrale gestartet und geprüft; auf Saschas Wort Standard (Eintrag zeigt auf die Spar-Einstellung, „schnell“ ist die
  Variante), Start ohne Wahl geprüft, 204 Tests OK.

## Nachtrag: Variante „beide Karten“ (14.11.2026, Sascha: „Beide testen“)

Anlass: Edge0 auf einer Karte belegt ~46 GiB RAM (Standard) bzw. ~36 GiB (`--resident-experts`). Auf beiden Karten
(Schichtaufteilung wie Flash-Next, Edge0s `server.py` macht das bei mehreren Karten in `gpu` von selbst) sollen mehr
Experten im Grafikspeicher und weniger im RAM liegen. Dafür muss die Zentrale einen `polystrata`-Eintrag auch auf
beiden Karten starten können. Bau (Codex Sol medium, eigener Worktree):

1. `planung.variante`: Ein Variantenwert `null` entfernt das Feld aus dem zusammengesetzten Eintrag (z. B.
   `"karten": null`, `"bedarf_je_karte_mib": null`). Docstring ergänzen. Bestehende Varianten ändern sich nicht.
2. `aktionen._polystrata_starten`: Ohne gewählte Karte, aber mit `bedarf_mib` (Karten → MiB) startet der Server mit
   `--gpu 0,1` (Kartennummern aus `bedarf_mib`, aufsteigend, mit Komma); Logzeile nennt die Karten. Ohne beides bleibt
   der Fehler „Keine Karte … gewählt“.
3. `server.py` (Zentrale): Planen und Starten einer solchen Variante laufen über den vorhandenen Weg für feste
   Karten (`bedarf_mib`, wie Strata); `/api/konfig` gibt bei Varianten auch `karten` mit, wenn die Variante das Feld
   setzt (auch `null`).
4. `web/app.js`, `mitVariante`: übernimmt `karten` aus der Variante, wenn sie das Feld hat (`null` entfernt es), damit
   die Bedarfszeile „… auf der RTX 3090 FE und … auf der RTX 3090 Suprim“ zeigt.
5. `config.json`, Eintrag `edge0-145b`: `varianten` = Standard „eine Karte · 128K“ (ohne Überschreibungen) und
   „beide Karten · 128K (Test)“ mit `konfig` `C:\LLM\runtimes\Edge0\edge0-145b-q3k-2gpu-128k.json`, `karten` null,
   `bedarf_je_karte_mib` null, `bedarf_mib` {"0": 23400, "1": 22000} (wie Strata), `ram_bedarf_gib` 24 (geschätzt).
6. Tests: Variante mit `null` entfernt Felder; Start der Zwei-Karten-Variante ruft `--gpu 0,1` auf; Plan/Start im
   Server wählen keine Einzelkarte und prüfen beide Karten; Ein-Karten-Standard, Ornith, Strata unverändert.

**Ausgang (14.11.2026):** Codex hat die Punkte 1–6 in einer Runde gebaut (212 Tests grün, Diff geprüft). Am echten
System lud die Zwei-Karten-Variante in 24 s und belegte nur ~26 GiB RAM, brach aber bei der ersten Anfrage ab („layer 22
never rang (an illegal memory access was encountered)“) – offener Engine-Fehler
[Edge0-AI/Edge0#205](https://github.com/Edge0-AI/Edge0/issues/205): Das latente D/U-Paar liegt in einem einzigen
prozessweiten Zeiger auf der ersten Karte. Der zweite Weg ohne Schichtaufteilung – Suprim als Experten-Hilfscache
(`--expert-cache-device1 12500`, Test-Einstellung über `env` `CUDA_VISIBLE_DEVICES=0,1`, ohne Codeänderung) – lud
(~12 GiB RAM), lieferte aber bei jeder Anfrage NaN, sobald die Suprim Experten rechnete. Peer-Stufe: kein P2P zwischen
den 3090 („CNS“). Weil keine Zwei-Karten-Art läuft, ist der Bau wieder herausgenommen (nicht committet); stattdessen
ist „RAM sparen“ (`--resident-experts`, ohne neuen Code) seit 14.11.2026 der Standard (Sascha), die schnelle Fassung
die Variante „schnell“. Neu bauen nach den Punkten 1–6,
wenn eine Engine #205 behebt – vorher den Modus mit einer Test-Einstellung prüfen. Werte: PLAN.md, Edge0-Abschnitt.

## Lehre aus diesem Lauf

- Zeit kostete nichts Nennenswertes; der vorher fertig angelegte Einstellungsdatei-Pfad und die geprüften Fakten im
  Bauauftrag (Engine-Name, leerer Pfad) machten eine Runde reichen. Keine Änderung an Skill oder Vorlagen.
- Nachtrag „beide Karten“: Die Bau-Runde war umsonst, weil die Engine den Modus nicht kann. Die `env` der
  Einstellungsdatei überschreibt `CUDA_VISIBLE_DEVICES` des Servers; so lässt sich ein Engine-Modus über die vorhandene
  Variante ausprobieren. Regel: erst den Engine-Modus mit einer Test-Einstellung prüfen (offene Issues der Engine
  ansehen), Zentrale-Code erst danach bauen lassen.

## Risiken

- Engine-Paket ist für Windows mit CUDA-Toolkit gebaut; laufen die pip-DLLs nicht, Fehler `0xC0000135` →
  dann Sascha fragen (Toolkit-Installation wäre eine neue Installation).
- RAM: 31 GiB Experten im RAM + Studio-Video daneben kann eng werden (63,5 GiB gesamt); Edge0 und Flash-Next nie
  gleichzeitig (beide brauchen die Karten).
- Die Benchmarks sind Herstellerwerte; erst unsere Messung entscheidet.
