# Baustand Atelier – Scheibe 2 (Ebenen-Editor ohne KI)

Stand: 22.10.2026
Branch: `atelier/editor-20261022`
Basis: `0bb9b00`
Gebaut: Teil C ohne KI-Aktionen 1–6 und ohne Fibo-Proxy (nur `GET /api/fibo/health`).

## Was gebaut ist

### Dienst (`atelier/server.py`, `atelier/start.py`, `atelier/config.json`)

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

### Oberfläche (`atelier/web/index.html`, `app.js`, `style.css`)

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

## Abweichungen, Entscheidungen, Grenzen

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

## Pflichtprüfungen (Kommando und Ergebnis)

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

## Commits

- `84e6da2` – Atelier: Server, Projekte und Tests fuer Scheibe 2
- Oberfläche und dieses Protokoll: zweiter Commit auf `atelier/editor-20261022`.
