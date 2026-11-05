# Plan Review Log: ComfyUI 0.37 → 0.44 und Sol-H3-VAE
Gestartet 05.11.2026. MAX_ROUNDS=3. Reviewer: gpt-6-astra, effort xhigh, read-only. Plan: SPEC-comfyui-044.md.

## Round 1 — Codex

Der Plan ist noch nicht umsetzungsreif. Besonders kritisch sind die fehlerhafte Isolation der Testinstanz, der unvollständige Rückweg und das weiterhin zugesagte unveränderte „Nochmal“. Ich habe ausschließlich lesend geprüft.

1. **P1 – `ComfyUI-044` wird als produktives ComfyUI erkannt.**  
   [`gehoert_zu_comfy`](C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/erfassung.py:210) prüft den Installationspfad mit `startswith`. Damit passt auch der geplante Nachbarordner `ComfyUI-044`; Port 8192 entspricht keinem weiteren konfigurierten Prozess, also landet dessen Speicher beim Verbraucher `bild-video`. Eine isolierte Probe der bestehenden Methode bestätigt das. Das Studio kann dadurch fremden Testspeicher als eigenen wiederverwendbaren Cache anrechnen.  
   **Fix:** Vor dem Teststart die Erkennung auf exakte Pfadgrenzen und Prozessidentität begrenzen; Produktions- und Testverbraucher müssen nachweislich getrennt bleiben.

2. **P1 – Ein eigener Platz-Schlüssel allein schützt den Testlauf nicht ausreichend.**  
   `comfy-test` erhält keine entsprechende Zuordnung in der Verbrauchermessung; seine Reservierung wird deshalb nicht mit seinem tatsächlichen Speicherzuwachs verrechnet. Ohne positiven Bedarf wird dieser Schlüssel sogar abgelehnt. Außerdem fehlen Verlängerung, Behandlung verlorener HTTP-Antworten und bestätigtes Rechenende vor Freigabe; die Standardanmeldung läuft nach 60 Sekunden ab. Siehe [`platz`](C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/server.py:376).  
   **Fix:** Einen Testablauf mit passender Verbraucherzuordnung, positivem Bedarf, regelmäßigem Verlängern und Freigabe erst nach bestätigtem Ende festlegen.

3. **P1 – Der Rückweg stellt die ursprüngliche Installation nicht wieder her.**  
   [Schritt 5](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:69) verändert das gemeinsame `.venv` aller Studio-Prozesse. Git stellt weder Python-Pakete noch Frontend oder mögliche Nutzerdatenmigrationen zurück; `pip freeze` ist dafür kein vollständiger Wiederherstellungsweg. Zudem ist der aktuelle Stand **`v0.37.0-5-gb0f4b7b2`**, nicht der Tag `v0.37.0`. Auch das Leerlaufen der Warteschlangen und Stoppen sämtlicher betroffener Prozesse fehlen.  
   **Fix:** Die bisherige Laufzeit unverändert erhalten und einen geprüften Versionswechsel samt Rückwechsel, Modellpfadprüfung, Konfiguration und geordnetem Prozessstopp vorsehen.

4. **P1 – Fehlendes `vae_neu` garantiert keine alten Ergebnisse.**  
   Ein unveränderter Graph läuft nach dem Update durch andere Implementierungen und Bibliotheken. Das Flag schützt nur vor dem neuen Decoder, nicht vor Änderungen an Sampling, Quantisierung, Attention oder Videokodierung. Die Abnahme erlaubt ausdrücklich Abweichungen alter **Bilder**, während Schritt 5 weiterhin unveränderte alte **Videos** verspricht.  
   **Fix:** Alte Aufträge entweder einer erhaltenen bisherigen Laufzeit zuordnen oder die Reproduzierbarkeitszusage ausdrücklich für Bilder und Videos neu festlegen.

5. **P1 – Start und vorhandene Knotennamen beweisen weder Modell- noch Kernel-Kompatibilität.**  
   Tatsächlich wechseln Frontend **1.53.6 → 1.57.6**, `comfy-kitchen` **0.2.35 → 0.2.40** und `comfy-aimdo` **0.5.5 → 0.6.0**. Python und Torch allein definieren also keine vergleichbare Umgebung. Ein vorhandener `ModelAttentionBackend` kann bei fehlendem Kitchen-Backend auf PyTorch zurückfallen; INT8-ConvRot-Gewichte, NVFP4-Textencoder und INT8-Attention brauchen getrennte Ausführungstests. Modellarchitekturen erkennt ComfyUI anhand ihrer Gewichte, nicht anhand eines plausiblen Dateinamens. Quellen: [Requirements](https://github.com/Comfy-Org/ComfyUI/blob/v0.44.0/requirements.txt), [Attention-Auswahl](https://github.com/Comfy-Org/ComfyUI/blob/v0.44.0/comfy_extras/nodes_model_advanced.py).  
   **Fix:** Die vollständige getestete Paketauflösung festhalten und Modellladen, tatsächliche CUDA-/Kitchen-Ausführung, Knoteneingaben sowie Frontend als Abnahmekriterien aufnehmen.

6. **P1 – Die vorgesehenen Bibliotheksgraphen sind auf 8192 nicht unverändert ausführbar.**  
   Studio-Vorlagen werden als `Projekt/Datei [output]` referenziert; mit dem neuen Ausgabeordner zeigen diese Verweise auf den falschen Ort. Eingabemasken fehlen ebenfalls. Gespeicherte `gpu:1`-Zuweisungen passen nicht zur Testinstanz mit nur einer sichtbaren GPU; der neue Geräteknoten kann dabei auf die Standardzuordnung zurückfallen. Außerdem fehlen im vorhandenen Kurstest-Modellmapping unter anderem `background_removal`, `frame_interpolation` und `geometry_estimation`.  
   **Fix:** Einen Replay-Adapter für Quellpfade, Masken, Ausgabeprefix und lokale GPU-Nummern sowie ein vollständiges Modellpfadmapping festlegen und vor jedem Lauf validieren.

7. **P1 – Speicherannahmen und Prozessabnahme entsprechen nicht dem aktuellen Betrieb.**  
   Die Behauptung „VAE auf der anderen 3090“ gilt nicht allgemein: Seit dem [4. November](C:/Workstation/Werkzeuge/KI-Zentrale/PLAN.md:3435) laufen zwei Videos gleichzeitig, jeweils vollständig auf einer 3090. Prozess 3 ist ausgebaut und außerdem mit `videos: false` konfiguriert. Sol benötigt längenabhängigen Aktivierungsspeicher und kann auch über `VAEDecodeTiled` nicht gekachelt werden. Die bisherigen festen Bedarfswerte berücksichtigen weder diese Änderung noch den zusätzlichen Decoder. Dynamisches VRAM-Laden existiert bereits heute und ist für den Ein-Karten-Betrieb wesentlich.  
   **Fix:** Ein-Karten-, Zwei-Karten- und Parallelbetrieb einschließlich 362 Bildern bei 1344×768/768×1344 vermessen, RAM/VRAM-Bedarfe anpassen und bei Strata auf beiden 3090 korrekt warten; Prozess 3 nur hinsichtlich seines Ausfalls prüfen.

8. **P1 – Die Encoder-Frage ist bereits geklärt; der vorgeschlagene Nachweis wäre irreführend.**  
   Die veröffentlichte Sol-Datei enthält nur den Decoder. Erfolgreiches Laden oder ein Text-zu-Video-Lauf beweist keine Encoderfähigkeit: Ohne Bild wird der Encoder dort gar nicht aufgerufen. Der Split ist richtig, braucht aber klare Verbindungen: Knoten 5 und `MiniMaxH3AddGuide` bleiben am ursprünglichen Encoder, Knoten 14 bekommt Sol, Audio bleibt separat. Das zusätzliche VAE-Objekt verursacht außerdem Lade- und Speicheraufwand. Quellen: [Sol-PR](https://github.com/Comfy-Org/ComfyUI/pull/17411), [VAE-Erkennung](https://github.com/Comfy-Org/ComfyUI/blob/v0.44.0/comfy/sd.py).  
   **Fix:** Decoder-only verbindlich festschreiben und die getrennten Verbindungen mit Start-/Endbild, Bild-/Videoreferenzen und Weiterführungs-Guide testen.

9. **P1 – `vae_neu: true` speichert nicht, womit ein Auftrag gerechnet wurde.**  
   Ändert sich später `studio.video.vae_dekodieren` von Sol INT8 auf FP16 oder LightVAE, erhält derselbe Auftrag bei „Nochmal“ einen anderen Decoder. Die geplante Sol-Erkennung am Dateinamen deckt zudem die ausdrücklich mögliche LightVAE-Entscheidung nicht sauber ab. Es fehlen die Übergaben durch API-Prüfung, Metadaten, Bibliothek, Oberfläche, Skill und sämtliche Szenen einer Folge.  
   **Fix:** Eine konkrete Decoder-ID mit Datei/Prüfsumme pro Auftrag und Szenenfolge speichern und ihren vollständigen Hin- und Rückweg einschließlich „Nochmal“ testen.

10. **P1 – Die Gleichheitsprüfung verwendet ungeeignete Kriterien.**  
    Ganze PNG-/MP4-Dateien dürfen unterschiedliche Prüfsummen haben: Laut [STUDIO.md](C:/Workstation/Werkzeuge/KI-Zentrale/STUDIO.md:810) ändern sich eingebettete Auftragsdaten absichtlich. Umgekehrt beweisen mittlerer Pixelabstand und gleiches Whisper-Transkript keine Gleichheit; lokale Bildfehler, Alpha-Abweichungen, Tonverschiebungen und fehlende Geräusche können unentdeckt bleiben. Cachetreffer können außerdem eine tatsächliche Neuberechnung vortäuschen.  
    **Fix:** Bildpixel einschließlich Alpha und getrennte Video-/Audiospuren vergleichen, Abweichungsgrenzen vorab festlegen und echte Neuberechnungen nach Neustart nachweisen.

11. **P1 – „Je Art ein Beispiel“ deckt die kritischen Varianten nicht ab.**  
    Der Schwerpunkt auf aktuellen INT8-/Turbo-Bildern prüft gerade die historischen BF16-Aufträge und alte Turbo-LoRA nicht. Weitere relevante Lücken sind Prompt-Enhancer, Transparenz/4 MP, DMAD gegenüber acc8 und normalem Sampling, Personentausch, sämtliche Weiterführungsmodi, Szenenfolgen sowie Abbruch während Sol-Dekodierung. Eine Suche nur in `*_graph` übersieht außerdem Knoten aus `_qwen_grund` und `_mit_*`-Hilfsfunktionen.  
    **Fix:** Eine risikobasierte Matrix aus historischen Varianten, heutigen Optionen, Parallelbetrieb und Fehlerfällen erstellen und Knotenschemata aus den tatsächlich erzeugten Graphen prüfen.

12. **P2 – Der VAE-Vergleich isoliert den Gewinn nicht und lässt die einfachste Alternative aus.**  
    Gleicher Seed allein sichert keine identischen Latents über Laufzeitwechsel. Es fehlen getrennte Baselines „bisherige Laufzeit + bisherige VAE“ und „0.44 + bisherige VAE“, wiederholte warme/kalte Messungen sowie ein Mindestgewinn. 1280×720 ersetzt nicht die tatsächlich angebotene native Größe 1344×768. Zudem unterstützt der bestehende [`sd.py`](C:/Users/sasch/Documents/Codex/2026-09-15/ek/outputs/Lokale-LLM/ComfyUI/comfy/sd.py:1023) bereits die INT8-ConvRot-Erkennung für eine vollständige klassische H3-VAE — deren kompatible quantisierte Fassung wäre ein kleinerer erster Versuch.  
    **Fix:** Mit einmal erzeugten, geprüften Latents zunächst bisherige VAE, kompatible klassische INT8-VAE und Sol vergleichen; das große Update erst bei nachgewiesenem praktischem Vorteil verfolgen.

VERDICT: REVISE
### Claude's response (Runde 1)

Übernommen – Plan neu gegliedert:
- **#12 (einfachste Alternative)** zum Kern gemacht: neue Phase A testet die klassische H3-VAE als INT8-ConvRot (2,8 GB) im bestehenden 0.37, ohne Update. Gleiche Laufzeit ⇒ gleiche Latents (Nochmal ist heute bitgleich), Phase B (0.44 + Sol) nur bei Bedarf.
- **#9** Decoder-ID mit Datei + SHA-256 je Auftrag (`vae_dekoder`) samt Weg durch API, Begleit-JSON, Bibliothek, Nochmal, Szenenfolge, Weiterführen, Skill.
- **#8** Decoder-only festgeschrieben, Verbindungen konkret (Kodieren/AddGuide/Audio bleiben, nur VAEDecode neu), Tests über alle Modi.
- **#10** Gleichheit über dekodierte Pixel inkl. Alpha und PCM-Ton, Neustart/`/free` gegen Cachetreffer.
- **#1/#2** als Vorbedingungen in Phase B: Pfadgrenze in `gehoert_zu_comfy`, eigener Verbraucher-Eintrag für die Testinstanz, Anmeldung mit Bedarf/Verlängern/Freigabe nach Ende. Phase A braucht keine Testinstanz.
- **#3/#4** Rückweg: altes ComfyUI + `.venv` bleibt unverändert, Umstellen nur über `comfy_ordner`; Version korrekt `v0.37.0-5-gb0f4b7b2`; geordneter Stopp; Nochmal-Zusage für Bilder und Videos als ausdrückliche Entscheidung.
- **#5/#6/#11** Ausführungstests je Modellart mit Kernel-Nachweis, vollständiges Modellpfad-Mapping, Replay-Adapter, risikobasierte Matrix.
- **#7** Messung geteilt und ganz auf einer Karte, 15 s bei 1344×768 (362 Bilder), Bedarfswert neu bestimmen.

Abgelehnt/eingegrenzt: Eine dauerhafte zweite Laufzeit nur für alte Aufträge (Option aus #4) nicht vorgesehen – Pflegeaufwand; Sascha entscheidet stattdessen über die Nochmal-Zusage.

## Round 2 — Codex

Phase A beseitigt das größte Risiko des ersten Entwurfs: den voreiligen Austausch der gemeinsamen Laufzeit. Die klassische INT8-VAE ist tatsächlich bei [Comfy-Org verfügbar](https://huggingface.co/Comfy-Org/MiniMax-H3/blob/main/vae/minimax_h3_video_vae_int8_convrot.safetensors). Es bleiben aber konkrete Lücken in beiden Phasen:

1. **P1 · Phase A: Standardwechsel kann alte „Nochmal“-Aufträge erfassen.**  
   [Zeilen 26–30](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:26) verlangen gleichzeitig automatische Standardbelegung und bisheriges Verhalten bei fehlendem Feld. Tatsächlich sendet [`wiederAnfrage`](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/studio.js:1425) ebenfalls `aktion: erzeugen`. Ergänzt der Server fehlende Decoderangaben automatisch, bekommt ein alter Auftrag nach dem Standardwechsel INT8. Der geplante reine Graphvergleich erkennt das nicht.  
   **Fix:** Den Standard nur bei ausdrücklich neuen Erzeugungen einsetzen und „Nochmal“ eines feldlosen Altauftrags nach Umschaltung auf INT8 durch Oberfläche und API testen.

2. **P1 · Phase A: Das Platz-Tor verwendet weiterhin den bisherigen Speicherbedarf.**  
   Der Split lädt bei Bild-/Referenzvideos zusätzlich zur vollständigen bisherigen VAE eine zweite Modelldatei. [`_bedarf`](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/studio.py:2351) berücksichtigt weder Decoder noch diesen zusätzlichen Speicher. Der Plan bestimmt neue Bedarfswerte erst in Phase B. Ein normal angemeldeter Studio-Auftrag begrenzt ComfyUIs tatsächlichen Verbrauch nicht; dynamisches Laden kann außerdem mehr RAM und zusätzliche Transfers verursachen. Ein einzelner Lauf auf Prozess 2 prüft noch keinen Parallelbetrieb.  
   **Fix:** Bereits für Phase A konservative Testbedarfe festlegen, RAM/VRAM bei zwei gleichzeitigen Videos messen und daraus die Reservierungen ableiten; bei belegten Strata-Karten muss der Auftrag warten.

3. **P2 · Phase A/B: Identische Latents und vergleichbare Messbedingungen sind weiterhin nur angenommen.**  
   [Zeile 53](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:53) leitet gleiche Latents aus gleicher Laufzeit ab. Der normale Scheduler kann Vergleichsläufe jedoch verschiedenen GPUs und Verteilungen zuweisen; der Graph wurde ebenfalls verändert. Für Phase B ist der Schluss über verschiedene Laufzeiten ohnehin unzulässig. Außerdem ist kein Verfahren beschrieben, mit dem der normale Studio-Weg gezielt die geteilte Verteilung erzwingt.  
   **Fix:** Pro Vergleich dieselben Video-/Audio-Latents verwenden oder deren Gleichheit per Hash nachweisen und Prozess, GPU-Verteilung sowie Cachezustand verbindlich festhalten.

4. **P2 · Phase A: Die Entscheidung kann eine insgesamt langsamere Lösung zum Standard machen.**  
   Gefordert werden mindestens 25 % kürzere Dekodierung, aber keine unveränderte oder bessere Gesamtzeit. Zusätzliche Lade- und Auslagerungsvorgänge können den Decodergewinn aufzehren. Die Zeitplanung ist ebenfalls nicht belastbar: Aus der beschriebenen Matrix ergeben sich 24 vollständige Generierungen, darunter acht native 15-Sekunden-Läufe; Sampling-Schritte fehlen.  
   **Fix:** Zusätzlich eine Grenze für Gesamtzeit und Parallel-Durchsatz setzen und den Aufwand anhand festgelegter Sampling-Einstellungen berechnen beziehungsweise Decodervergleiche ohne erneutes Sampling durchführen.

5. **P1 · Phase B: Ein zusätzlicher Konfigurationseintrag erzeugt noch keinen getrennten Testverbraucher.**  
   [`Erfassung`](C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/erfassung.py:65), Werkstatt und Studio wählen jeweils nur den ersten Eintrag mit `art == 'comfy'`; Verbraucherschlüssel und weitere Prozesse hängen an diesem einen Eintrag. Der geplante `comfy-test` braucht deshalb ausdrücklich zusätzliche Erfassungslogik. Beim Pfadfix darf zudem der zweite Erkennungspfad `self.comfy_ordner in selbst['cmd']` nicht unverändert bleiben: Er akzeptiert den Nachbarordner weiterhin.  
   **Fix:** Die getrennte Testprozess-Erfassung samt Platzabrechnung als Codeänderung einplanen, das Studio eindeutig über seine ID auswählen und beide Pfadprüfungen mit absoluten Kommandozeilen testen.

6. **P1 · Phase B: Der geplante Wechsel von `comfy_ordner` scheitert an der Modellprüfung.**  
   Die Modelle sollen ausschließlich über `extra_model_paths.yaml` eingebunden werden. [`_comfy_starten`](C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/aktionen.py:533) verlangt jedoch physische Pflichtdateien unter dem neuen `comfy_ordner/models`. Damit verweigert die Zentrale den Start. Selbst bei manuellem Start würden [`_modell_da`](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/studio.py:2176) und weitere direkte Dateiprüfungen vorhandene Modelle und LoRAs als fehlend melden.  
   **Fix:** Einen von der Laufzeit unabhängigen Modellpfad einführen und sämtliche Pflichtdatei- sowie Verfügbarkeitsprüfungen auf dieselbe Auflösung wie ComfyUI umstellen.

7. **P1 · Phase B: „Umschalten = Eintrag zurück“ ist kein vollständiger Rollback.**  
   Nach einer Sol-Übernahme bleibt beim bloßen Zurückstellen des Ordners möglicherweise Sol als Decoderstandard aktiv; die alte Laufzeit kann ihn nicht laden. Auch bereits wartende Sol-Aufträge brauchen eine definierte Behandlung. Zentrale und Werkstatt halten Konfigurationswerte im Speicher; eine JSON-Änderung allein aktualisiert diese nicht. Der Testprozess auf 8192 wird beim vorgesehenen Stoppen der Studio-Prozesse ebenfalls nicht ausdrücklich beendet.  
   **Fix:** Einen getesteten Wechsel- und Rückwechselablauf festlegen: Auftragsannahme anhalten, laufende Arbeit abschließen, Testprozess stoppen, Laufzeit und Decoderstandard gemeinsam wechseln, Dienste neu laden und inkompatible wartende Aufträge sichtbar zurückhalten.

Die frühere Forderung nach einer dauerhaft zweiten Laufzeit für Altaufträge muss nicht wieder aufgenommen werden: Die ausdrückliche Entscheidung über die Reproduzierbarkeitszusage in Phase B genügt. Die oben genannten Start-, Speicher- und Rückwegprobleme bleiben davon unabhängig.

VERDICT: REVISE
### Claude's response (Runde 2)

Übernommen:
- **#1** Server ergänzt nie einen fehlenden `vae_dekoder`; nur Formular/Skill setzen ihn bei neuen Erzeugungen (Muster wie `schnell`/`int8`), „Nochmal“ reicht `info.vae_dekoder` unverändert weiter; Test für Altauftrag nach Standardwechsel über Server-Weg und `wiederAnfrage`.
- **#2** `bedarf_zusatz_mib` je Decoder in `_bedarf` schon in Phase A (konservativer Startwert, nach Messung gesetzt); Messung auch mit zwei Videos gleichzeitig (RAM/VRAM je Karte); Warten bei belegten Strata-Karten.
- **#3/#4** Vergleich ohne zweites Sampling: ein Graph mit zwei `VAEDecode` an derselben Latent-Ausgabe ⇒ gleiche Latents garantiert; Prozess und Karten fest gesetzt und protokolliert; 6 Samplingläufe mit Dauerschätzung vorab; Schwelle zusätzlich Gesamtzeit und Durchsatz bei zwei Videos.
- **#5–#7** (Phase B) als bekannte Vorbedingungen festgehalten (beide Pfadprüfungen, getrennte Testerfassung, laufzeitunabhängiger Modellpfad, vollständiger Wechsel-/Rückwechselablauf).

Eingegrenzt: Phase B ist jetzt ausdrücklich nur Skizze mit eigener Planung und eigenem Gegenlesen, falls Sascha sie nach Phase A will – die Review bewertet Phase A als umsetzbaren Teil.

## Round 3 — Codex

**Phase A hat noch einen harten Blocker.** Der Schutz alter Aufträge, die Encoder-/Decoder-Trennung und der Vergleich gemeinsamer Latents sind jetzt ausreichend beschrieben. Phase B zählt ausdrücklich nicht zur Bewertung.

1. **P1 – Der Speicherzuschlag verhindert die vorgesehenen Ein-Karten-Tests.**  
   [A2](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:43) addiert Dateigröße plus 1.024 MiB zum bisherigen Bedarf. Für eine Karte ergibt das ungefähr **22.528 + 2.680 + 1.024 = 26.232 MiB**. Eine 3090 bietet nach der konfigurierten Reserve höchstens **23.808 MiB**. [`Instanz.kann`](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/studio.py:1932) lehnt solche Aufträge ab; auch die direkte Platzanmeldung kann diesen Bedarf nicht bewilligen. Damit sind die Ein-Karten- und Paralleltests blockiert, deren Messungen den Zuschlag erst korrigieren sollen. Dateigröße ist außerdem kein verlässlicher zusätzlicher VRAM-Spitzenbedarf bei dynamischem Laden.  
   **Fix:** Zuerst einen ausführbaren Kalibrierungslauf auf einer exklusiv reservierten Karte festlegen und daraus den gesamten Ein-Karten-Spitzenbedarf ableiten; anschließend die regulären Ein-Karten- und Paralleltests durchführen.

2. **P2 – Die Decoderidentität ist wieder nur indirekt gespeichert.**  
   [A1](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:27) speichert im Auftrag lediglich `int8`; Datei und Prüfsumme stehen ausschließlich in der aktuellen Konfiguration. Wird dieser Eintrag später auf eine andere Datei samt passender neuer Prüfsumme geändert, besteht jede Prüfung — „Nochmal“ verwendet trotzdem andere Gewichte.  
   **Fix:** Kennungen ausdrücklich unveränderlich an Datei und SHA-256 binden und für jede neue Modellfassung eine neue Kennung verlangen, oder Datei und Prüfsumme zusätzlich im Auftrag speichern.

3. **P2 – Für die Durchsatz-Abnahme fehlt die passende Vergleichsmessung.**  
   [A4](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-comfyui-044.md:66) enthält einzelne Aufträge mit/ohne Decoder sowie zwei gleichzeitige Videos **mit INT8**. Der entsprechende parallele Lauf **ohne INT8** fehlt. Aus Einzelzeiten lässt sich wegen gemeinsamer RAM-, Lade- und Transferlast nicht ableiten, ob der in A5 geforderte Parallel-Durchsatz erhalten bleibt.  
   **Fix:** Dieselben beiden Videos unter gleichen Startbedingungen einmal parallel ohne und einmal parallel mit INT8 ausführen und die gemeinsame Fertigstellungszeit vergleichen.

VERDICT: REVISE
### Claude's response (Runde 3, MAX_ROUNDS erreicht – ohne erneutes Gegenlesen eingearbeitet)

- **#1 (P1)** gelöst durch einfacheren Aufbau: Die INT8-Datei ist eine vollständige klassische VAE (Kodieren und Dekodieren). Rolle `ganz` ersetzt nur `vae_name` von Knoten 3 – keine zweite VAE, kein Zuschlag, Bedarf eher kleiner. Die Aufteilung mit eigenem Decoder (Rolle `dekodieren`) bleibt nur vorbereitet für Sol/Phase B, Zuschlag dort aus eigener Kalibrierung. Der Doppel-Decoder-Vergleichsgraph in A4 läuft im Ein-Karten-Fall als Kalibrierung mit exklusiver Karte; passt der 15-s-Fall nicht, wird er nur geteilt gemessen und vermerkt.
- **#2 (P2)** Kennungen unveränderlich (`int8_v1`), Kennung + Datei + SHA-256 im Auftrag und in der Begleit-JSON, Abgleich beim Rechnen.
- **#3 (P2)** dieselben zwei Videos parallel einmal ohne, einmal mit `int8_v1` unter gleichen Startbedingungen; Schwelle über die gemeinsame Fertigstellungszeit.

Ergebnis: kein formales APPROVED. Runde 3 hatte nur noch einen P1 (Speicherzuschlag), der durch den Wegfall der zweiten VAE in Phase A entfällt. Phase B bleibt Skizze mit eigenem Gegenlesen.

## Act 3 — Build (Phase A1–A3)

Builder: gpt-6.1-sol, effort medium, Worktree `KI-Zentrale-bau-vae`, Zweig `bau/vae-dekoder`, MAX_FIX_ROUNDS=2. Download `minimax_h3_video_vae_int8_convrot.safetensors` (Comfy-Org, SHA-256 52a2c8c7…0c0e) läuft parallel.

Ergänzung 05.11.2026 (Sascha): A4 um einen Lauf ganz auf der Suprim mit Monitor erweitert (Vergleich zur FE, Auslagern, Ruckeln); Lockerung der Monitorregel nur als eigener Vorschlag danach.

### Round 1 — Codex build
Thread 01a1acb9-2aab-7600-b773-567081ba51c2, gpt-6.1-sol medium, ohne Fixrunde. Geändert: `werkstatt/config.json` (Eintrag `int8_v1`, `dekoder_standard: null`), `werkstatt/studio.py` (`vae_dekoder`, Rolle ganz/dekodieren in `video_graph` – `weiter_graph` baut darauf auf –, `_bedarf`-Zuschlag nur für `dekodieren`, Weitergabe durch Prüfung, Szenenfolge, Begleit-JSON, `einstellungen_aus_graph`, Prüfung vor `_rechnen`), `werkstatt/web/studio.js` (Standard nur bei neuen Videos/Szenenfolgen, „Nochmal“ und „Mit Änderungen“ behalten den Altwert, Beschreibung „schnellere VAE (INT8)“), neue Tests `test_vae_dekoder.py` + eingefrorene Altgraphen. Speicherformat: `vae_dekoder: {kennung, datei, sha256}`.

### Claude's verdict
Diff vollständig gelesen: im Umfang, Stil passt, nichts außerhalb von `werkstatt/`. Eigene Läufe: werkstatt 279 OK, zentrale 193 OK. Gegenprobe: die eingefrorenen Altgraphen (9 Fälle) mit dem unveränderten `studio.py` aus `main` erzeugt → alle gleich, also echte Vorher-Graphen. Abweichung (Erkennung aus dem Graph nur über Dateiname, SHA aus der Konfiguration) ist sachlich richtig und hingenommen. Angenommen, keine Fixrunde nötig.

## A4 erster Teil — Messung 05.11.2026 (Claude)
Clip: Text → Video 960×544, 124 Bilder (5 s), 8 Schritte Turbo, schnell, Nummer 4242. Skript `vae_messung.py` (Scratchpad), Anmeldung `/api/platz` mit Halten.
- R1 geteilt (Modell FE, Encoder/VAE Suprim): Sampling+Ton 88,5 s; Dekodieren+Speichern fp16 31,7 s, INT8 19,5 s (Sampler-Knoten 13 beide Male aus dem Zwischenspeicher ⇒ identische Latents). VAE-Karte Spitze fp16 7,7 GiB, mit beiden VAEs 10,1 GiB.
- R2 ganz FE, Reihenfolge vertauscht: Sampling+Ton 77,6 s; INT8 17,1 s, fp16 27,4 s.
- R4 normaler INT8-Auftrag ganz FE: 88,2 s, Spitze 23.842 MiB. R3 derselbe ganz Suprim mit Monitor (8189): 82,7 s, Spitze 23.800 MiB samt Windows; Windows-Zähler „Gemeinsamer GPU-Speicher“ +1.230 MiB auf einem Adapter (auf der FE 5–215 MiB) – möglicherweise Auslagern, ohne Zeitverlust. Ruckeln: keins (Sascha: „lief ruhig“).
- Qualität INT8 vs fp16 (gleiche Latents, 124 Bilder): max. Abweichung 18/255, Mittel 0,103/255, 0,01 % der Werte > 2/255, PSNR 57,4–57,9 dB (unsichtbar; verstärktes Differenzbild nur Rauschen). R1 vs R2 fp16 bitgleich (Verteilung ändert das Ergebnis nicht).
- Ergebnis: Dekodieren ~38 % kürzer (Schwelle 25 % erreicht), Gesamtzeit nicht länger. Offen für A5: Parallel-Durchsatz zweier Videos, größere Clips, Bild → Video (INT8-Kodieren des Startbilds), Ruckeln.

## A4 zweiter Teil — 05.11.2026
- Zwei Videos gleichzeitig (Prozess 1 ganz FE, Prozess 2 ganz Suprim mit Monitor, 960×544, 5 s, Nummern 5151/6161): bisher gemeinsam fertig nach 111,9 s, INT8 nach 94,7 s (−15 %). Spitzen beide Karten ~23,8 GiB; Zähler „gemeinsamer GPU-Speicher“ +1,6 GiB (bisher) bzw. +1,0 GiB (INT8) auf dem Suprim-Adapter. Keine Fehler.
- Bild → Video (Porträt `Werkstatt-Abnahme/Bild_00027_`, 544×960, FE): bisher 114,4 s, INT8 (auch Kodieren) 100,4 s. Startbild ↔ Bild 1 je 30,5 dB (gleich, die Abweichung macht H3 selbst); bisher ↔ INT8 alle 124 Bilder 56,2–57,9 dB, Mittel 57,1 dB – kein sichtbarer Unterschied (Sichtprüfung Anfang/Ende).
- Damit alle A5-Kriterien für 960×544 erfüllt. Nicht gemessen: große Clips (1344×768, 10–15 s).

## A4 dritter Teil — 05.11.2026
- „Beste“ (20 Schritte ohne Turbo, 960×544, 5 s, FE): Sampling+Ton 172,4 s; Dekodieren+Speichern fp16 25,8 s, INT8 16,4 s (−36 %); 124 Bilder PSNR 57,5–57,9 dB, max. 14/255.
- Großer Clip 1344×768, 10 s (243 Bilder), 8 Schritte Turbo, ganz FE: Sampling+Ton 571,1 s; INT8 54,8 s (zuerst), fp16 90,7 s (−40 %); Spitze beim Dekodieren INT8 18,3 GiB statt fp16 23,0 GiB auf der Karte. 243 Bilder PSNR 57,9–58,3 dB, max. 16/255, Sichtprüfung Bild 120 gleich.
- Derselbe ganz Suprim mit Monitor, INT8 (Rolle ganz): 594,4 s gesamt (FE vergleichbar ~626 s: 571 + 55), Spitze 23.953 MiB. „Gemeinsamer GPU-Speicher“ wuchs um ~8 GiB – beim großen Clip aber auch auf der FE (+6 GiB): ComfyUIs dynamisches Nachladen, kein Zeitverlust.
- Ergebnis A5: alle Kriterien auch bei „Beste“ und großem Clip erfüllt.

## Act 3 — Build Runde 2 (Standard + Monitorkarte), 05.11.2026
Sascha: „Ja, beides“. Codex Sol medium, Thread 01a1ad05-43f2-7db0-9701-5cd7d2647cd2, ohne Fixrunde: `dekoder_standard` = `int8_v1`, `monitorkarte_mib` 19.456, Bedarfsrolle `monitorkarte`/Variante `nur_monitor`, `kann`/`bevorzugt`/`_wer_zuerst` angepasst, 5 neue Tests.
Claude: Diff gelesen (im Umfang, Altverhalten ohne Feld unverändert, Monitorkarte nach Karte ohne Monitor gewertet, Prozesse ohne Videos ausgeschlossen); Tests selbst: Werkstatt 283 OK, Zentrale 193 OK (Worktree und Hauptordner). Skill `bild-video-studio` (`video_schnell_wunsch` setzt `vae_dekoder`, SKILL.md) sowie PLAN/STUDIO/AGENTS von Claude nachgezogen. Live: Skill-Video → Prozess 2 ganz auf der Suprim mit Monitor, 73,7 s, Feld in Auftrag und Begleit-JSON.
