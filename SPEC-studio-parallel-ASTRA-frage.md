Du bist adversarialer Gutachter, nur lesend. Ändere keine Dateien. Antworte auf Deutsch, knapp, mit Datei:Zeile-Belegen.
Trenne „im Code geprüft“ von „Vermutung“. Am Ende: Urteil APPROVED oder CHANGES REQUESTED mit nummerierten Punkten.

## Projekt

`C:\Workstation\Werkzeuge\KI-Zentrale` (Regeln: `AGENTS.md`): Modellzentrale (`zentrale\`, Port 3894) und Werkstatt
(`werkstatt\`, Port 3895) mit Studio (`werkstatt\studio.py`, ~3.800 Zeilen) für Qwen-Image 2.1 und MiniMax-H3 über
ComfyUI. ComfyUI-Installation: `C:\Users\sasch\Documents\Codex\2026-09-15\ek\outputs\Lokale-LLM\ComfyUI`.
Hardware: 2× RTX 3090 24 GB (Karte 0 = FE mit Monitor, ~1 GB Programme; Karte 1 = Suprim), 64 GB RAM, Windows 11.
Python nur Standardbibliothek; keine neuen Pakete/Umgebungen.

Stand heute (Stufe 7, gerade umgesetzt): Die gemeinsame GPU-Sperre der Werkstatt ist entfernt. Schutz ist nur noch die
Speicher-Anmeldung bei der Zentrale (`zentrale\server.py` `platz`, `zentrale\planung.py` `angemeldet_rest` mit
`schluessel`/`basis`). Das Studio meldet je Auftrag an (`schluessel` „bild-video“), hält die Anmeldung bis zum Ende.

## Ziel Stufe 8 (Auftrag Sascha)

Zwei Studio-Aufträge gleichzeitig: zwei Bilder parallel (eins je Karte) oder Video auf einer Karte + Bild auf der
anderen. ComfyUI führt je Prozess nur einen Prompt zur Zeit aus.

## Geplanter Umbau

1. Zentrale (`zentrale\aktionen.py` `_comfy_starten`/`_comfy_stoppen`/Entladen über `/free`, `zentrale\erfassung.py`
   Erkennung `comfy` und Verbraucher „bild-video“, `zentrale\config.json` Eintrag `bild-video`): Beim Start zwei
   ComfyUI-Prozesse aus derselben Installation: wie heute `main.py --listen 127.0.0.1 --port 8188 --cuda-device 0,1
   --default-device 0 --output-directory C:\Workstation\Arbeitsmaterial\Studio`, dazu ein zweiter mit `--port 8189`,
   eigenem `--temp-directory` und `--user-directory` (gleiches Eingangsverzeichnis, gleiche Modelle). Beide sehen beide
   Karten; das Studio legt die Geräte je Auftrag über die Geräte-Knoten fest (wie heute `mit_geraeten`). Stoppen,
   Entladen (`/free`) und Erkennung für beide; der Verbraucher „bild-video“ zählt beide Prozesse zusammen.
2. Studio: zwei Arbeiter statt einer Schleife (`_schleife`, `_durchfuehren`, `_platz`, `_rechnen`, `_comfy_anfrage`,
   `_comfy_abbrechen`, `comfy_zustand`, Hochladen, `client_id`). Jeder Arbeiter ist an einen ComfyUI-Prozess gebunden
   und nimmt den nächsten wartenden Auftrag; Kartenwahl wie heute über die Zentrale (zwei Bilder landen dann auf
   verschiedenen Karten, weil die erste Anmeldung die eine Karte belegt). Abbrechen, Fortschritt, Bibliothek und
   Begleitdateien (`<datei>.json`, nie überschreiben) je Auftrag.
3. Dateinamen: Der zweite Prozess bekommt einen Namenszusatz im Präfix (z. B. `Bild-2_00003_.png` statt
   `Bild_00021_.png`), weil ComfyUIs Zähler (`folder_paths.get_save_image_path`) in zwei Prozessen gleichzeitig dieselbe
   Nummer wählen und überschreiben könnte. (Sascha einverstanden.)
4. Video auf einer Karte: messen, ob MiniMax-H3 (heute „haupt“ + „neben“ auf zwei Karten) auf eine 3090 passt; sonst
   bleiben Videos zweikartig und ein paralleles Bild wartet auf Speicher.
5. Arbeitsspeicher messen (zwei Prozesse könnten Modelle doppelt im RAM halten).

## Bitte prüfen

- Stimmt die Annahme, dass ComfyUI je Prozess seriell rechnet und zwei Prozesse auf denselben Karten sauber
  nebeneinander laufen (CUDA-Kontexte, `--cuda-device 0,1`, Speicherverwaltung `comfy.model_management`, freier
  Speicher je Prozess falsch eingeschätzt, weil der andere Prozess belegt)? Gibt es eine bessere Aufteilung
  (z. B. je Prozess nur eine Karte sichtbar, und zweikartige Videos nur in einem Prozess)?
- Welche Stellen in `werkstatt\studio.py` hängen an „ein ComfyUI, ein Auftrag“ (Port fest, `client_id`, Zustände,
  Abbrechen über `/interrupt`, Zeitschätzung, `_letzte_rechenzeit`, Freigabe/Entladen, Maskendateien im
  Eingangsordner, Prüfsummen, „Nochmal“ bitgleich)? Welche Wettläufe entstehen bei zwei Arbeitern?
- Zentrale: Was muss sich an Erkennung, Platzrechnung (Verbraucher „bild-video“, `basis` einer Anmeldung, wenn zwei
  Studio-Anmeldungen gleichzeitig wachsen), Stoppen und `/free` ändern? Bricht `angemeldet_rest` (Gruppe je
  Schlüssel, Basis = Minimum) bei zwei gleichzeitigen Studio-Anmeldungen?
- Dateinamen-Zusatz: richtig gelöst? Begleitdatei-Regel, Bibliothek, Skill `bild-video-studio` (`scripts\studio.py`).
- RAM/VRAM-Risiken und eine sinnvolle Reihenfolge für Bau und Tests.
