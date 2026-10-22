# Baustand Atelier

Stand: 22.10.2026
Branch: `atelier/fibo-20261022` (Scheibe 3), davor `atelier/editor-20261022` (Scheibe 2)

## Scheibe 3 – KI-Aktionen mit Fibo und Freistellen

Basis: `e9f88ec`. Gebaut nach `SPEC-atelier.md`, Teil C Punkte 1–6, Proxy, Lizenz und den
verbindlichen Präzisierungen 5, 6, 7 und 9.

### Was gebaut ist

#### Dienst (`atelier/server.py`, `atelier/config.json`)

- **Fibo-Proxy:** `/api/fibo/*` geht an den in `config.json` eingestellten Dienst (GET und POST),
  immer mit Kopfzeile `X-Atelier: 1`, ohne System-Proxy und mit eigenen Zeitlimits. Ist der Dienst
  aus, antwortet das Atelier mit **503** und „Fibo ist aus – in der Modellzentrale starten.“
  (`/api/fibo/health` ebenso). Fibo-Status `ok`, `loading` und `error` werden unverändert
  weitergereicht; die Oberfläche leitet daraus „bereit“, „startet“ und „Fehler“ ab.
- **Ergebnis übernehmen:** `POST /api/fibo/uebernehmen` holt das fertige Bild selbst vom Dienst
  (`/api/datei/<id>.png`), prüft den Bildtyp und legt es als `Fibo_<Auftrags-ID>.<endung>` in
  `ebenen\` des Projekts ab. Daneben entsteht `Fibo_<Auftrags-ID>.json` mit Prompt, Caption, Seed,
  Modell, Breite/Höhe und `quelle = {"art":"fibo","lizenz":"CC BY-NC 4.0","modell":…}`.
  Nur Zustand `fertig` wird übernommen; `rechnet`/`wartet` → 409, `fehler` → 502 mit Klartext.
- **Freistellen über die Werkstatt** (Präzisierung 6): `GET /api/freistellen/status` prüft
  `comfy.laeuft` und `einstellungen.freistellen_schnell_verfuegbar` über `GET /api/studio`.
  `POST /api/freistellen` legt den Auftrag mit `X-Werkstatt: 1`, `art: freistellen`,
  `verfahren: schnell` (nur ohne Motiv) und der absoluten Bilddatei als Vorlage an.
  `GET /api/freistellen?id=…&projekt=…` fragt den Zustand ab und kopiert das fertige PNG
  idempotent als `Frei_<Auftrags-ID>.png` nach `ebenen\`. Werkstatt aus, ComfyUI aus und
  fehlendes BiRefNet liefern verständliche Meldungen; `POST /api/freistellen/abbrechen` reicht
  den Abbruch an die Werkstatt weiter.
- Zeitlimits und die Fibo-Anfragegrenze (64 MB) stehen in `atelier/config.json`
  (`zeitlimit_fibo_auftrag_s`, `zeitlimit_fibo_bild_s`, `zeitlimit_werkstatt_status_s`,
  `max_fibo_mb`).

#### Oberfläche (`atelier/web/index.html`, `app.js`, `style.css`)

- Der Platzhalter im Bereich „KI“ ist durch die sechs Aktionen ersetzt:
  1. **Bild erzeugen** mit Prompt, Beschreiber (DeepSeek Flash Standard / direkt), Ziel
     (Hintergrund/Objekt), Qualität (Standard 30 / Höchste 50) und optionalem Seed. Hintergrund
     wird im Seitenverhältnis der Leinwand mit ≈1 MP angefordert und danach als unterste Ebene
     auf Leinwandgröße gesetzt; Objekt ist quadratisch.
  2. **Ebene bearbeiten** mit Anweisung, Turbo als Standard und Schalter „Höchste Qualität
     (Dev, ≈6 min)“. Das Ergebnis ersetzt das Bild an gleicher Stelle, sichtbarer Größe, Drehung
     und Spiegelung; der Verlauf stellt das alte Bild wieder her.
  3. **Bereich ändern** mit Maskendialog: Pinsel, Größe, Radierer, „Maske leeren“. Die Maske
     entsteht in Bildpixeln des Originals; exportiert wird ein PNG mit schwarzem Grund und
     weißen Strichen (Weiß = neu).
  4. **Freistellen** (schnell / mit Motivbeschreibung) über den Freistell-Ablauf des Servers.
     Das freigestellte Bild ersetzt die Ebene; Fibo-Ebenen behalten `quelle` art fibo.
  5. **Zusammenführen**: alle sichtbaren Bild- und Form-Ebenen ohne Text werden mit
     Leinwandhintergrund zu einem Bild (≈1 MP) gerendert und mit der vorbelegten, änderbaren
     Anweisung (Turbo) bearbeitet. Das Ergebnis ist die unterste Ebene „Zusammengeführt“, die
     Quellen werden nur ausgeblendet, Text bleibt obenauf.
  6. **Beschreibung ändern** nur für Fibo-Ebenen mit Caption: Kurzbeschreibung, Licht, Ästhetik,
     Kamera (die drei als JSON), Stil und Text; „Neu rechnen“ nutzt denselben Seed und ersetzt
     die Ebene.
- Je Auftrag zeigt die Liste Zustand, Schritt x/y und Platz in der Warteschlange, bietet
  „Abbrechen“ und zeigt Fehler im Klartext. Mehrere Aufträge laufen hintereinander; jedes
  Ergebnis hängt an der Ebene, von der es kam, auch wenn inzwischen eine andere ausgewählt ist.
  Ist die Ebene gelöscht, wird das Ergebnis als neue Ebene eingefügt.
- **Pan:** Leertaste halten + ziehen oder mittlere Maustaste; **Strg + Mausrad** zoomt.
  Der Pan verschiebt die Leinwand per CSS-Transformation, die Dokumentkoordinaten von Fabric
  bleiben unverändert.

### Abweichungen, Entscheidungen, Grenzen

- `/api/fibo/health` liefert bei ausgeschaltetem Dienst bewusst 503 (so im Rauchtest gefordert)
  statt 200 mit `bereit:false`; die Oberfläche wertet den Dienststatus aus.
- Der Server lädt Ergebnisbild und Begleit-JSON selbst. Die Oberfläche schreibt nie direkt in
  `ebenen\`; sie ergänzt nur `quelle.datei` für das erneute Laden der Ebene, die Serverform von
  `quelle` bleibt unverändert.
- Freistell-Ergebnisse werden idempotent kopiert (gleiche Auftrags-ID und gleicher Inhalt →
  keine zweite Datei). Die Fibo-Herkunft einer freigestellten Ebene bleibt als `quelle` art fibo
  erhalten; bei gelöschter Quelle wird die gemerkte Herkunft mitgeführt.
- Der Maskenpinsel rechnet die eingestellte Größe von der Anzeige in Originalpixel um; der
  Radierer löscht die Maskenstriche, der Export setzt sie auf Schwarz/Weiß.
- Bei „Beschreibung ändern“ werden Licht, Ästhetik und Kamera als JSON bearbeitet; die übrigen
  Caption-Schlüssel bleiben erhalten. Das ist die konservative Variante, weil die VGL-Struktur
  verschachtelt ist.
- Grenze: Wird während eines Auftrags das Projekt gewechselt, speichert der Server das Ergebnis
  weiterhin im ursprünglichen Projekt; die Oberfläche fügt es dort nicht automatisch ein, sondern
  meldet es. Nach Rückgängig/Wiederholen sind Ebenen neue Objekte; ein noch laufender Auftrag
  findet seine alte Ebene dann nicht mehr und legt das Ergebnis als neue Ebene ab.
- Kein Klicktest der KI-Aktionen gegen echte Dienste (Sperrliste: kein Modell, keine GPU, keine
  echten Dienste auf 3894/3895/8095–8098). Die Sichtprüfung lief mit Fake-Fibo und Fake-Werkstatt
  in einem Temp-Profil: einmal „Fibo bereit (dev)“ mit freigeschaltetem „Bild erzeugen“, einmal
  „Fibo ist aus“ mit gesperrten Aktionen. Temp-Daten und Profil wurden danach entfernt.
- `atelier/config.json` bekam nur die neuen Zeitlimits und `max_fibo_mb`; die Ports bleiben
  `werkstatt_port`/`fibo_port` und sind für Tests überschreibbar.

### Pflichtprüfungen (Kommando und Ergebnis)

Python: `C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`

1. `python -m unittest discover -s atelier/tests` → `Ran 24 tests in 32.212s` – `OK`
   (vorher 15; neu: Fibo-Proxy inkl. Kopfzeile, 503, Ergebnis in `ebenen\` mit `quelle` und
   Begleitdaten, Freistellen fertig/Fehler/aus/ComfyUI aus/BiRefNet fehlt, Pfadschutz).
2. `python -m unittest discover -s fibo/tests` → `Ran 22 tests in 2.312s` – `OK` (unverändert).
3. `python -m unittest discover -s zentrale/tests` → `Ran 145 tests in 0.569s` – `OK` (unverändert).
4. `python -m unittest discover -s werkstatt/tests` → `Ran 214 tests in 1.787s` – `OK` (unverändert).
5. `C:\LLM\runtimes\node-v24.22.0-win-x64\node.exe --check atelier/web/app.js` → keine Ausgabe,
   Exit 0.
6. Rauchtest (freier Port, Temp-Ablage, kein Dienst auf 8098; Prozess danach beendet):
   - `GET /api/health` → `200`, `{"dienst":"ki-zentrale","app":"atelier","version":1}`
   - `GET /` → `200`, `<title>Atelier</title>` enthalten, Länge 23243
   - `GET /api/fibo/health` → `503`, `{"fehler":"Fibo ist aus – in der Modellzentrale starten."}`
   - Temp-Ablage entfernt; der Testserver ist beendet.
7. `git diff --check` → keine Ausgabe.

### Commits

- `02f5cf82cdb28482890fa5f5a0e4955899787202` – Atelier: Fibo-Proxy und Freistellen mit Tests
  (Server, Konfiguration, Tests).
- Oberfläche und dieses Protokoll: zweiter Commit auf `atelier/fibo-20261022`
  (`Atelier: Oberflaeche fuer KI-Aktionen, Maske und Pan`).

## Scheibe 2 – Ebenen-Editor ohne KI

Stand: 22.10.2026
Branch: `atelier/editor-20261022`
Basis: `0bb9b00`
Gebaut: Teil C ohne KI-Aktionen 1–6 und ohne Fibo-Proxy (nur `GET /api/fibo/health`).

### Was gebaut ist

#### Dienst (`atelier/server.py`, `atelier/start.py`, `atelier/config.json`)

- Standardbibliothek-Dienst nur auf `127.0.0.1:3896`; Kennung
  `{"dienst":"ki-zentrale","app":"atelier","version":1}` für `gemeinsam/starter.py`.
- `atelier/start.py` wie die Werkstatt: App-Name `atelier`, Titel „Atelier“, Logname
  `atelier-dienst`, Fenster `1440,920`.
- Projekte unter der in `config.json` eingestellten Ablage (Standard
  `C:\Workstation\Arbeitsmaterial\Atelier`): `projekt.json`, `ebenen\`, `export\`.
  Anlegen, Speichern (atomar über Temp-Datei), Laden, Umbenennen, Auflisten.
- Namensbereinigung: Pfade, absolute Pfade, `..`, reservierte Windows-Namen und `_fibo`
  werden abgelehnt; unzulässige Zeichen werden ersetzt. `_fibo` erscheint nie als Projekt.
- Pfadschutz auch für Bild- und Exportdateien (kein Ausbruch aus `ebenen\` bzw. `export\`).
- Hochladen: JSON mit Data-URL oder Base64, höchstens 40 MB (einstellbar), nur PNG/JPEG/WebP
  anhand der ersten Bytes; Dateiname wird bereinigt und kollisionsfrei gespeichert.
- Studio-Bibliothek: `GET /api/studio/bibliothek` liest
  `GET http://127.0.0.1:3895/api/studio/bibliothek`; Bilder werden über
  `/studio/datei?p=…` der Werkstatt geholt und nach `ebenen\` kopiert. Ist die Werkstatt aus,
  antwortet das Atelier mit 503 und „Die Werkstatt ist aus. Bitte zuerst die Werkstatt starten …“.
- Fibo: ausschließlich `GET http://127.0.0.1:8098/health` über den Atelier-Server. Aus liefert
  „aus – in der Modellzentrale starten“, `loading` wird als „startet – Fibo lädt das Modell“
  angezeigt. Kein weiterer Fibo-Proxy.
- Export: PNG/JPG als Data-URL, Ablage in `export\`; daneben eine JSON-Datei mit Format, Zeit,
  Quellen der Ebenen (inklusive `quelle` und Lizenz) und `nicht_kommerziell`/`fibo_sichtbar`.
  Sichtbare Fibo-Ebenen werden im Dialog und in der Begleitdatei gewarnt.
- `--port`/`ATELIER_PORT` und `--ablage`/`ATELIER_ABLAGE` überschreiben die Konfiguration
  (für Tests und Rauchtest; die echte Ablage wird dabei nicht berührt).

#### Oberfläche (`atelier/web/index.html`, `app.js`, `style.css`)

- Kopfleiste: Projekt (Neu, Öffnen, Umbenennen), Format (YouTube 1280×720, Instagram 1080×1080,
  Story 1080×1920, Flyer A5 1748×2480, Flyer A4 2480×3508, Eigenes), Rückgängig/Wiederholen
  (Strg+Z/Strg+Y), Speichern, Export und Fibo-Anzeige.
- Links: Ebenenliste mit Ziehen zum Umsortieren (Griff), Sichtbarkeit, Sperre, Name,
  Deckkraft, Duplizieren und Löschen; Hinzufügen von Bild (Datei oder Studio-Bibliothek),
  Text, Rechteck und Kreis; Hintergrundfarbe.
- Mitte: Fabric.js 6.4.3 (lokal, unverändert), an das Fenster angepasst, Zoom
  (−/+ / Einpassen / 100 %), Hilfslinien an Mitte und Rändern mit Einrasten, YouTube-Hinweisfläche
  unten rechts einblendbar.
- Rechts: Eigenschaften der Auswahl (Position, Größe, Drehung, Deckkraft, Spiegeln, Ausrichten;
  Text mit Schriftliste, Größe, Farbe, Kontur, Schatten, Ausrichtung, Zeilenabstand, fett/kursiv;
  Form mit Rundung, Füllung, Kontur; Bild mit Quelle/Lizenz) und der Bereich „KI“ mit dem
  Platzhalter „Kommt im nächsten Schritt“ ohne Funktion.
- Bild aus Datei per Hineinziehen oder „Bild …“, aus der Studio-Bibliothek über den Dialog.
  Test-Import erzeugt eine Ebene mit `quelle = {"art":"fibo","lizenz":"CC BY-NC 4.0"}`; nur so
  entstehen in dieser Scheibe Fibo-Ebenen. Die Liste zeigt dann „Fibo · nicht-kommerziell“.
- Automatisches Speichern nach 2 s, zusätzlich „Speichern“. Verlauf mit 50 Ständen.
- Export-Dialog mit PNG/JPG, Qualität, Maßstab 1×, Warnung bei sichtbaren Fibo-Ebenen und
  Hinweis zum Kennzeichnen von KI-Bildern; Bild und Begleit-JSON werden heruntergeladen.
- Bei Fibo-Ebenen über 100 % Vergrößerung in A5/A4 zeigt die Eigenschaftenleiste
  „unscharf beim Druck“.

### Abweichungen, Entscheidungen, Grenzen

- Die Ablage ist wie vorgegeben in `atelier/config.json` einstellbar; Tests und Rauchtest
  verwenden ausschließlich Temp-Ordner. Die echte Ablage `C:\Workstation\Arbeitsmaterial\Atelier`
  wurde nicht angelegt oder verändert (geprüft: `Test-Path` ergab `False`).
- Das Lizenzfeld heißt wie in der Mission `quelle` (nicht `atelierQuelle`). Zusätzlich tragen
  Ebenen die eigenen Felder `atelierArt`, `atelierName`, `atelierGesperrt`.
- Die Begleit-JSON wird serverseitig aus dem zuletzt gespeicherten Projekt erzeugt; der Export
  speichert vorher. So passen Bild und Quellen zusammen.
- Ein automatisierter Klicktest (Neu/Zeichnen/Export) wurde nicht ausgeführt. Zur Sichtprüfung
  lief die Oberfläche in einem eigenen Headless-Chrome-Profil (Temp-Profil, Temp-Ablage, freier
  Port): einmal im Leerzustand (Willkommen-Karte, Fibo „aus“, keine Projektliste) und einmal mit
  einem vorbereiteten Projekt aus Fläche, Text und Bild (3 Ebenen in der Liste, Text und Bild auf
  der Leinwand, Status „Gespeichert“). Beide Screenshots wurden geprüft; Temp-Daten und
  Chrome-Profil wurden danach entfernt. Domänen-IDs: alle 117 von `app.js` erwarteten IDs sind
  im HTML vorhanden, keine doppelten IDs.
- Bei 100 % Zoom werden große Formate (A4) im Bühnenbereich beschnitten; „Einpassen“ holt die
  vollständige Ansicht zurück. Eine freie Leinwand-Verschiebung (Pan) ist in dieser Scheibe
  nicht eingebaut.
- Keine KI-Aktionen, kein `/api/fibo/*` außer `health`, kein Freistellen, keine Zentrale-Änderung,
  keine README/PLAN/AGENTS-Änderung, keine Verknüpfung.

### Pflichtprüfungen (Kommando und Ergebnis)

Python:
`C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`

1. Atelier:
   `cmd /c "C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s atelier/tests 2>&1"`
   → `Ran 15 tests in 14.352s` – `OK`.

2. Werkstatt (unverändert):
   `cmd /c "C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s werkstatt/tests 2>&1"`
   → `Ran 214 tests in 1.818s` – `OK`.

3. Zentrale (unverändert):
   `cmd /c "C:\Users\sasch\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s zentrale/tests 2>&1"`
   → `Ran 132 tests in 0.055s` – `OK`.

4. JavaScript:
   `& 'C:\LLM\runtimes\node-v24.22.0-win-x64\node.exe' --check atelier/web/app.js`
   → keine Ausgabe, Exit 0. Weitere eigene JS-Module gibt es nicht.

5. Rauchtest (freier Port 62110, Temp-Ablage, Prozess danach beendet):
   `Start-Process <Python> -ArgumentList '-m','atelier.server','--port','62110','--ablage','<Temp>'`
   - `GET http://127.0.0.1:62110/api/health` → `200` und
     `{"dienst": "ki-zentrale", "app": "atelier", "version": 1}`
   - `GET http://127.0.0.1:62110/` → `200`, Länge 15578, `<title>Atelier</title>`
   - Serverprozess (PID 9200) anschließend beendet, Temp-Ablage entfernt.

### Commits

- `84e6da2` – Atelier: Server, Projekte und Tests fuer Scheibe 2
- Oberfläche und dieses Protokoll: zweiter Commit auf `atelier/editor-20261022`.
