# Spec: Reiter Prompts – Restpunkte (07.11.2026)

_Auftrag Sascha 07.11.2026 („Restpunkte Prompts“, Bau mit Codex Sol xhigh). Grundlage: [SPEC-prompts.md](SPEC-prompts.md),
dort „Baustand“, „Risiken und offene Punkte“ und „Lehre aus diesem Lauf“. Befunde unten hat Claude am 07.11.2026 am
echten System geprüft._

Vier kleine, voneinander unabhängige Teile A–D. Kein neues Verhalten außerhalb dieser Teile.

## A. Claude-Anbieter findet Claude Code wieder

**Befund.** Die Claude-App (Store-Paket `Claude_4.23118.0.0_x64__pzs8sxrjxfjjc`) legt Claude Code inzwischen hier ab:
`%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude-code\<Version>\<Kennung>\claude.exe`
(echt vorhanden: `…\claude-code\2.1.317\a33aa5518497\claude.exe` und `…\claude-code\2.1.309\9078b9c1d466\claude.exe`).
Die beiden bisher durchsuchten Orte in `werkstatt/auswertung.py`, `Claude.exe()`, sind leer:
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe` und
`%APPDATA%\Claude\claude-code\*\claude.exe`. Deshalb liefert `Claude.exe()` `None`, und die Werkstatt meldet überall
(live auf 3895 wie im Worktree) „Die Claude-App mit Claude Code ist nicht installiert.“ Außerhalb der App ist
`claude.exe` 2.1.317 angemeldet (`auth status` mit `_ohne_app_umgebung()`: `loggedIn: true`, `authMethod: claude.ai`).

**Änderung.**
1. `Claude.exe()` sucht zuerst das neue Muster
   `os.path.join(LOCALAPPDATA, 'Claude-Data', 'claude_*', 'claude-code', '*', '*', 'claude.exe')`, danach wie bisher die
   beiden alten Muster als Rückfall (Reihenfolge: neu, Paketordner, `%APPDATA%`). Nur echte Dateien (`os.path.isfile`).
2. Unter allen Treffern des ersten Musters, das etwas findet, gewinnt die höchste Version. Die Version ist der
   Ordnername **direkt unter `claude-code`** (bei allen drei Mustern), Teil für Teil numerisch verglichen
   (`2.1.99` < `2.1.309` < `2.1.317`). Der Kennungsordner (`a33aa5518497`) enthält Ziffern und darf nie in den
   Vergleich eingehen – heute nimmt `_versionsschluessel` genau den letzten Ordner und würde beim neuen Layout falsch
   sortieren. Gleiche Version in mehreren Kennungsordnern: neueste Änderungszeit der `claude.exe` gewinnt.
3. Anmeldung, Aufrufargumente, `_ohne_app_umgebung()`, Meldungstexte und alle anderen Anbieter bleiben unverändert.

**Tests** (`werkstatt/tests`, temporäre Ordner, `LOCALAPPDATA`/`APPDATA` in `werkstatt.auswertung` per `patch`):
neues Layout mit 2.1.309 und 2.1.317 → 2.1.317; Kennungsordner mit vielen Ziffern unter der älteren Version
(`2.1.309\999999999999`) ändert die Wahl nicht; `2.1.99` gegen `2.1.317` numerisch; nur altes Paketlayout → dessen
höchste Version; nur `%APPDATA%`-Layout → dessen Datei; neues und altes Layout zugleich → neues; Ordner ohne
`claude.exe` oder mit gleichnamigem Ordner statt Datei → ignoriert; nichts vorhanden → `None`.

## B. Liste im Reiter Prompts lädt beim Öffnen sicher

**Befund.** Nach dem Neustart der Werkstatt am 07.11.2026 blieb die Liste im Reiter Prompts beim ersten Öffnen einmal
leer. Nachgestellt hat es sich nicht (frischer Start einer Abnahme-Werkstatt: 37 Einträge in 10 ms). Schwachstellen in
`werkstatt/web/prompts.js`:
- `pLaden()` setzt `P.letztesLaden` **vor** dem Abruf. Scheitert der Abruf (Dienst startet noch, Verbindungsfehler)
  oder wird sein Ergebnis verworfen, weil inzwischen ein Dialog offen oder ein Feld im Inhalt fokussiert ist
  (`pGeschuetzt()`), gilt der nächste Versuch erst nach 30 s als fällig (`pLadenFaellig()`).
- Bis zum ersten erfolgreichen Laden ist `#p-liste` eine leere `<ol>` ohne jeden Hinweis.
- Zwei Abrufe können sich überlappen (Zeitgeber und Knopf „Neu einlesen“); die spätere Antwort kann eine frühere
  überschreiben.

**Änderung** (nur `prompts.js`, keine neuen Zeitgeber, kein kürzerer Takt):
1. Bis zum ersten erfolgreichen Laden zeigt die Liste einen leisen Eintrag „Prompts werden geladen …“.
2. Nur ein erfolgreich **angewendetes** Ergebnis zählt als geladen (`P.letztesLaden` erst dann setzen). Ein
   gescheiterter oder verworfener Abruf macht den nächsten Takt des bestehenden 2,5-s-Zeitgebers fällig, sobald
   `pGeschuetzt()` nicht mehr gilt. Die übrigen Regeln bleiben: kein Neuladen bei offenem Dialog oder fokussiertem
   Feld im Inhalt; im Ruhezustand alle 30 s, bei laufenden Tests/Schärfen-Läufen bei jedem Takt.
3. Scheitert ein Abruf, steht die Fehlermeldung wie bisher in `#p-rueck`; hat die Liste noch nie Einträge gezeigt,
   zeigt sie zusätzlich leise „Liste nicht geladen – neuer Versuch läuft.“ Eine bereits gezeigte Liste bleibt bei
   einem späteren Fehler stehen. Nach dem nächsten Erfolg verschwindet der Hinweis, `#p-rueck` wird wie bisher aus
   `d.fehler` gesetzt.
4. Höchstens ein Abruf von `/api/prompts` gleichzeitig. Kommt ein Aufruf, während einer läuft, wird genau ein weiterer
   Abruf nach dessen Ende nachgeholt (Knopf „Neu einlesen“ soll nie verloren gehen); ältere Antworten überschreiben nie
   neuere.

**Tests** (JS-Bedientest gegen das echte `prompts.js`, Fake-`fetch`, Zeitgeber per Hand ausgelöst; der DOM-Nachbau
aus Teil D): vor der ersten Antwort „Prompts werden geladen …“; erster Abruf scheitert → Hinweis in der Liste und
Meldung in `#p-rueck`, nächster Takt lädt ohne Klick, danach Einträge und kein Hinweis; Ergebnis bei offenem Dialog
verworfen → nach dem Schließen lädt der nächste Takt; zweiter Aufruf während eines laufenden Abrufs startet keinen
parallelen Abruf, holt aber genau einen nach; Ruhezustand nach Erfolg: kein Abruf vor 30 s.

## C. Vorgabename für neue Fassungen

**Entscheidung** (Claude, 07.11.2026; in SPEC-prompts.md offen „Fassung n“ gegen Datum): „Fassung n“ mit
`n = max(Anzahl der Fassungen, höchste Zahl k aus Namen genau der Form „Fassung <k>“) + 1`. Beispiele:
`[Fassung 1]` → „Fassung 2“; `[Fassung 1, Schärfen 06.11. Codex · GPT-6-Luna · niedrig]` → „Fassung 3“;
`[Fassung 1, Fassung 7]` → „Fassung 8“; `[A, B]` → „Fassung 3“. Der Name ist damit immer frei.

**Änderung.**
1. Eine Funktion in `werkstatt/prompts.py` berechnet den Vorschlag; `Eintrag.lesen()` liefert ihn zusätzlich als
   `fassung_vorschlag` (eine Regel, Oberfläche rechnet nicht selbst).
2. `fassung_neu` mit leerem oder nur aus Leerraum bestehendem Namen vergibt den Vorschlag **unter der Sperre** aus dem
   frisch gelesenen Stand (nicht aus einem Wert der Oberfläche). Ein ausdrücklich angegebener Name wird wie bisher
   geprüft (Steuerzeichen, 60 Zeichen, doppelt → Fehler).
3. Dialog „Neue Fassung“: Namensfeld mit `fassung_vorschlag` vorbelegt und markiert (Tippen ersetzt ihn), änderbar.
4. Unverändert: „Fassung 1“ beim Anlegen, Namen der Schärfen-Fassungen, Sammlungseinträge (nicht bearbeitbar).

**Tests:** die vier Beispiele; leerer Name im Aufruf speichert den Vorschlag; ausdrücklicher Name bleibt; doppelter
Name weiter Fehler; Schnittstelle (`/api/prompt`, Aktion `fassung_neu`, `name: ''`) legt „Fassung n“ an; JS: Dialog
„Neue Fassung“ ist mit dem Vorschlag vorbelegt.

## D. DOM-Nachbau der JavaScript-Tests wie im Browser

**Befund.** Die JS-Bedientests haben eigene kleine DOM-Nachbauten (`werkstatt/tests/prompts_schaerfen_bedienung.js`
und die Skripte in `werkstatt/tests/test_prompts.py`). Ihr `append`/`replaceChildren` übernimmt `null`, `undefined`,
Zahlen und Text unverändert als Kind. Ein Browser hängt jedes Nicht-Element als Textknoten an (`String(wert)`), ein
`null`-Kind wird also sichtbarer Text „null“. So fiel der Fehler aus Scheibe 3 (`replaceChildren(…, null)` in der
Schärfen-Ergebnisanzeige) erst im Browser auf.

**Änderung.**
1. Neues CommonJS-Modul `werkstatt/tests/dom_nachbau.js` mit `kinder(...werte)` (Elemente bleiben, alles andere wird
   Textknoten `{ tag: '#text', textContent: String(wert) }` wie im Browser) und `keinFremdText(wurzel)` (scheitert,
   wenn irgendwo im Baum ein Textknoten oder `textContent` „null“, „undefined“ oder „[object Object]“ lautet).
2. Alle bestehenden DOM-Nachbauten nutzen `kinder(...)` in `append` und `replaceChildren`; jeder JS-Bedientest ruft
   nach dem Zeichnen `keinFremdText` auf. Die Nachbauten müssen dafür nicht zu einem einzigen verschmolzen werden;
   bestehende Prüfungen bleiben, angepasst nur, wo sie bisher Rohwerte in `children` erwarteten.
3. Selbsttest des Moduls (`append(null)` ergibt Textknoten „null“, `keinFremdText` schlägt an) und ein
   Regressionstest: Schärfen-Ergebnis ohne neue Platzhalter enthält keinen Text „null“.

## Grenzen

- Nur `werkstatt/` (Code und Tests) und diese Spec. **PLAN.md, README.md, AGENTS.md nicht ändern** (im Hauptordner
  liegen uncommittete Änderungen von Sascha an PLAN.md; die Doku trägt Claude nach der Abnahme nach).
- Kein Umbau von `_zerlegen`, nichts aus „Nicht in Version 1“ der SPEC-prompts.md, keine weiteren Anbieteränderungen.
- Keine periodischen Neuladungen oder Zeitgeber ohne Vorgabe (Lehre 06.11.2026).
- Logs ohne Prompts, Transkriptinhalte, Schlüssel oder persönliche Daten; alles nur an 127.0.0.1.
- Keine neuen Abhängigkeiten.

## Nachweis

`%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s werkstatt\tests`
im Worktree, alle grün (Stand vorher: 382 OK, 1 übersprungen); Node liegt unter
`C:\Users\sasch\AppData\Local\hermes\node\node.exe` und ist im PATH, die JS-Bedientests laufen also mit.

Abnahme (Claude, Browser, Abnahme-Werkstatt aus dem Worktree auf 3897): A – Anbieter Claude im Testdialog verfügbar
und ein echter kurzer Lauf; B – fünf frische Starts, Seite direkt auf `#prompts`, Liste da; Seite offen, Dienst noch
nicht gestartet → Hinweis, Dienst starten → Liste erscheint ohne Klick innerhalb weniger Sekunden; C – „Neue Fassung“
zeigt „Fassung n“ und speichert sie; D – Tests.

## Baustand

- **Gebaut und abgenommen (07.11.2026)**: Codex Sol xhigh (Saschas Vorgabe „Nutze SOL auf Xhigh zum bauen falls
  möglich“), 8,5 min, keine Fixrunde; Thread 1,27 Mio. Eingabe-Token (davon 1,18 Mio. aus dem Cache), 20.806
  Ausgabe-Token. 403 Tests grün, 1 übersprungen (vorher 382).
- **Claude-Nachbesserung:** `pLadenFaellig()` gibt während eines laufenden Abrufs `false` zurück. Sonst stellte jeder
  2,5-s-Takt einen zweiten Abruf hinter einen langsamen ersten, und ab 2,5 s Antwortzeit liefen die Abrufe pausenlos
  hintereinander. Dazu ein Bedientest, der ohne die Zeile scheitert (geprüft). Knopf und Aktionen holen weiterhin
  genau einen Abruf nach.
- **Browser-Abnahme** (Abnahme-Werkstatt aus dem Worktree auf 3897, eigener Promptordner):
  A – Claude Code wird am neuen Ort gefunden; Testlauf „Fassung 3“ mit Claude Sonnet 5 fertig in 3 s, Antwort
  „bereit“, 2.261 Token (Abo). B – fünf frische Starts, Seite direkt auf `#prompts`: jedes Mal 37 Einträge nach rund
  1,2 s, keine Meldung. Mit beendetem Dienst stehen „Liste nicht geladen – neuer Versuch läuft.“ und die Meldung in
  `#p-rueck`; nach dem Start des Dienstes war die Liste nach 0,3 s ohne Klick wieder da. C – „Neue Fassung“ schlägt
  bei Fassung 1 und 2 „Fassung 3“ vor (markiert); gespeichert, danach lautet der Vorschlag „Fassung 4“. D – im echten
  Reiter mit allen aufgeklappten Ansichten kein sichtbarer Text „null“, „undefined“ oder „[object Object]“.
- **Sicherheit:** kein neuer Weg nach außen und keine neue Route. `fassung_neu` vergibt den Namen nur noch serverseitig
  unter der Sperre. Die Claude-Suche bleibt im Benutzerordner (`%LOCALAPPDATA%`) wie der bisherige Paketordner.
- **Beobachtet, nicht geändert:** Ist der Dienst nicht erreichbar, steht in `#p-rueck` die englische Browsermeldung
  „Failed to fetch“. Sie kommt aus dem gemeinsamen `api()` in `app.js` und betrifft alle Reiter.

## Lehre aus diesem Lauf

- Zeit gekostet: Für die fünf frischen Starts reichte das Starten und Stoppen über Hintergrundaufgaben nicht. Ein
  kleines Neustart-Skript hat geholfen: Es beendet nur den Prozess mit `abnahme-server2.py` in der Kommandozeile,
  wartet auf den freien Port und startet neu. Der Bau selbst lief ohne Fixrunde.
- Was sich ändert: In `codex-build` (Browser-Abnahme aus dem Worktree) steht jetzt, dass wiederholte Neustarts über
  ein solches Skript laufen. AGENTS.md: nichts.
