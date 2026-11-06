# Spec: Reiter „Prompts“ in der Werkstatt

_Stand 06.11.2026, Claude, nach Interview mit Sascha (grill-me-codex, Akt 1, sechs Entscheidungen) und Codex-Runden 1
bis 3 (Astra xhigh, 20 + 11 + 4 Punkte). Runde 3 endete mit REVISE und vier P1-Punkten; Claude hat sie nach der
Rundengrenze eingearbeitet, ohne weitere Codex-Runde (Details in `SPEC-prompts-REVIEW-LOG.md`). Noch nicht gebaut._

## Ziel

Saschas Coding- und Kreativprompts (Beispiel „Hühnerfarm“: eine HTML-Datei) und seine Vorlagen mit wechselnden
Eingaben (Beispiel „Videoanalyse“: dieselbe Vorlage mit verschiedenen Transkripten) bekommen in der Werkstatt
(`http://127.0.0.1:3895`) einen eigenen Reiter „Prompts“. Dort lassen sie sich sammeln und nach Aufgabe finden,
von Hand oder über Claude/Codex mit dem Skill `prompt-schaerfen` überarbeiten, mit Eingaben an ein frei gewähltes
Zielmodell (auch Flash-Next lokal) schicken und im A/B-Vergleich beurteilen. Jeder Testlauf hinterlässt einen
Beleg: welche Fassung mit welchen Eingaben an welches Modell ging, was zurückkam, und Saschas Urteil. Die
Wissens-Sammlung `C:\Users\sasch\Desktop\Meine-Wissens-Prompts.md` bleibt die einzige aktive Fassung ihrer
Prompts; der Reiter liest und testet sie, schreibt aber außerhalb des bestehenden Werkstatt-Abschnitts nichts hinein.
Handänderungen an allen Dateien bleiben jederzeit möglich und werden erkannt.

## Was wiederverwendet wird (Befund im Code)

- `werkstatt\auswertung.py`: Auswerter-Profile (`daten\auswerter.json`), Anbieter `Codex`, `Claude`, `DeepSeek`,
  `OpenRouter`, `Lokal` mit `verfuegbar`/`kontext`/`ausfuehren`, Warteschlange `Auswertungen` (2 Arbeitsfäden,
  Abbrechen/Wiederholen/Entfernen, `_Lauf` mit Prozessgruppe), Kopfformat von `_ablegen`, Tokenschätzung aus
  `anlegen` (`(Zeichen + 600) / 3`, Reserve `min(32768, Kontext // 4)`).
- `werkstatt\anweisungen.py`: Kastenkonvention `#### Name` + `~~~text … ~~~`, `stand()` (sha256[:12]),
  `text_pruefen` (keine Zeile, die mit `~~~` beginnt; ≤ 20.000 Zeichen), `Konflikt`, atomares `_schreiben` mit
  erhaltenen Zeilenenden, Muster „frisch lesen unter Sperre, Stand prüfen, Block tauschen“ aus `speichern`.
  `_zerlegen` selbst wird **nicht** wiederverwendet (kein Zaunzustand, nimmt `~~~python` als Kasten, Abschnittsgrenzen
  auch innerhalb von Kästen); der Werkstatt-Abschnitt bleibt bei ihm, alles Neue nutzt den Parser unten.
- `transkripte_auflisten` (Arbeitsordner `Arbeitsmaterial\watch`; je Transkriptlauf `transkript` = Laufordner mit
  `transcript-timestamps.txt`, `ordner` = Videoordner), `winapi.dateien_waehlen`, Dateidialog-Besitzerfenster.
- Lokale Modelle: Strata und PolyStrata melden unter `/health` `loaded`, `model` und `max_context` (die Zentrale
  liest das in `zentrale\erfassung.py` so aus). Nötig, weil die Varianten der Zentrale denselben Modellnamen für
  128K und 256K tragen (IQ3_XXS und Q4 je zweimal); `_tatsaechliches_modell` allein unterscheidet sie nicht.
  Ollama meldet den geladenen Kontext unter `/api/ps`. NInfer hat keinen Kontext-Endpunkt; dort gilt der Wert aus
  dem Katalog der Zentrale (Untertitel), gekennzeichnet als „laut Zentrale“.
- Oberfläche: `$`, `h`, `api`, `knopf`, `dauer` aus `app.js`; `dialogOeffnen` und `markdown` aus
  `zusammenfassung.js` (globale Funktionen, Ladereihenfolge der Skripte beachten); Reiterwechsel `reiterZeigen`
  mit `REITER` und Haken `window.<reiter>Aktiv`; statische Dateien nur über die Freigabeliste `Anfrage.statisch`
  in `server.py` (neue Datei muss dort eingetragen werden).
- Claude läuft ohne Werkzeuge, Einstellungen, Skills und MCP (`--tools ''`, `--setting-sources ''`,
  Systemprompt „Du bist ein sorgfältiger Assistent.“). Codex läuft mit `--ignore-user-config --ignore-rules
  -s read-only` in einem leeren Ordner: **nur lesend, aber mit Werkzeugen** (kann Dateien lesen und Befehle
  ausführen) und liest laut PLAN.md seine globale `AGENTS.md` mit. Beides bleibt so und wird so benannt.
- Tests: `%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe -m unittest discover -s werkstatt\tests`
  (das `python` im PATH ist nur der Store-Platzhalter). Ausgangslage 06.11.2026: 303 Tests OK, 1 übersprungen.

## Ablage (Entscheidung 1 und 3)

Wurzel aus `config.json`, neuer Block:

```json
"prompts": {
  "ordner": "C:\\Workstation\\Arbeitsmaterial\\Prompts",
  "skill": "C:\\Workstation\\Skills\\aktiv\\prompt-schaerfen\\SKILL.md",
  "dateiwurzeln": ["C:\\Workstation", "C:\\Users\\sasch\\Desktop"],
  "feld_max_zeichen": 400000
}
```

Je Prompt ein Ordner `<Ordner>\<Kennung>\`. Die **Kennung** ist der Ordnername und die stabile Identität des
Eintrags (Umbenennen des Titels ändert sie nicht): aus dem Titel über `dateiname()` (Grenze 70 Zeichen), dann
Windows-Gerätenamen (`CON`, `PRN`, `AUX`, `NUL`, `COM1–9`, `LPT1–9`, auch mit Endung) mit `_` versehen, führender
`_` verboten (`_Sammlung` ist reserviert), Eindeutigkeit ohne Groß/Klein, bei Dopplung ` (2)`.

```
prompt.md
tests\2026-11-06 14-32-07 – Fassung 2 – Flash-Next.md
tests\2026-11-06 14-32-07 – Fassung 2 – Flash-Next.html      nur wenn die Antwort HTML enthält
schaerfen\2026-11-06 15-01-40 – Schärfen – codex-sol.md
```

`prompt.md`:

```
# Hühnerfarm
Quelle: https://… oder freier Text
Schlagworte: html, spiel, three.js
Bevorzugt: Fassung 2
Aktualisiert: 06.11.2026

Freier Text (Notizen) ist überall außerhalb der Kästen erlaubt und bleibt Byte für Byte erhalten.

#### Fassung 1
~~~text
…
~~~

#### Fassung 2
~~~text
…
~~~
```

- Titel = erste `# `-Überschrift (Anzeige). Kopfzeilen `Schlüssel: Wert` direkt nach dem Titel bis zur ersten
  Leerzeile; unbekannte Schlüssel bleiben stehen. `Bevorzugt` nennt eine Fassung; fehlt die Zeile oder die Fassung,
  gilt die erste. `kopf_stand` = `stand()` über Titelzeile **und** Kopfzeilen (alles, was der Kopfdialog gemeinsam
  bearbeitet).
- Fassungen = `#### Name` + genau ein Prompt-Kasten (siehe Parser). Stand je Kasten = `stand(text)`. Namen eindeutig
  je Datei, ≤ 60 Zeichen, `name_pruefen` plus Verbot von Steuerzeichen (`\r`, `\t`, `\x00–\x1f`); `text_pruefen` wie
  bei den Anweisungen.

### Zäune: eine Lese- und eine Schreibfunktion für alles Neue

- **`prompts.bloecke(text)`** erkennt alle Zaunblöcke nach CommonMark: Öffnung = Zeile mit höchstens 3 Leerzeichen,
  dann mindestens 3 `~` **oder** 3 `` ` ``, dann optionale Kennung; Schluss = Zeile mit höchstens 3 Leerzeichen und
  nur dem gleichen Zaunzeichen in mindestens der Öffnungslänge; dazwischen zählt nichts als Überschrift oder Zaun.
  Liefert je Block Zeichen, Länge, Kennung, Zeilenbereich, Inhalt und ob er geschlossen wurde. Die **Regeln je
  Datei** sitzen bei den Aufrufern, nicht im Parser:
  - `prompt.md`: Prompt-Kasten = `~`-Block mit Kennung `text` oder leer direkt unter einer `####`-Überschrift;
    andere Blöcke (`python`, `json`, Backticks) sind Notizen. Ungeschlossener Block oder zwei Prompt-Kästen unter
    einer Überschrift → Datei **mehrdeutig**: Anzeige „nicht eindeutig lesbar“ mit „Im Ordner öffnen“, keine
    automatische Bearbeitung, kein Test.
  - Beleg und Schärfen-Datei: Pflichtabschnitte `## Fassung` und `## Eingaben` mit je genau einem geschlossenen
    Block direkt darunter; fehlt einer → Beleg „beschädigt“ (Anzeige, kein Wiederholen). `## Antwort` ist
    **optional** und wird erst mit der Modellantwort geschrieben (Block mit verlängertem Zaun, damit ein
    ungeschlossener Codeblock **in** der Antwort die Datei nicht unlesbar macht). Als „Antwort vorhanden“ zählt nur
    ein geschlossener Block mit nicht leerem Text; kein Abschnitt, offener Block oder leerer Block heißt „keine
    Antwort“, und Wiederholen löst dann einen neuen Modellaufruf aus.
  - Antwort des Schreibmodells: Prompt-Kasten = `~`- oder Backtick-Block mit Kennung `text` oder leer, geschlossen.
  - Sammlung: Prompt-Kasten wie in `prompt.md`, Überschriften nur außerhalb von Blöcken.
- **`prompts.block_schreiben(text, kennung, zeichen='~')`**: Zaun so lang, dass keine Zeile des Inhalts nach dem
  Entfernen von bis zu 3 führenden Leerzeichen mit einem gleich langen oder längeren Lauf des Zaunzeichens beginnt
  (mindestens 3). Leser und Schreiber nutzen dieselbe Funktion `_zaunlaenge(zeile)` für diese Prüfung. Fassungstexte
  enthalten wegen `text_pruefen` nie eine mit `~~~` beginnende Zeile und bekommen immer `~~~text`.

### Schreiben in `prompt.md`

Alle Änderungen laufen über `prompts.Eintrag` in `werkstatt\prompts.py` nach dem Muster von `Sammlung.speichern`:
eine **modulweite** Sperre (`threading.RLock`, ein Objekt für alle Promptdateien, damit auch gleichzeitige
HTTP-Anfragen und die Warteschlange serialisiert sind), darunter Datei frisch lesen, Zielblock suchen, übergebenen
Stand (Kasten: `stand`, Kopf: `kopf_stand`) gegen den frischen Inhalt prüfen (`Konflikt` → HTTP 409 „… wurde
inzwischen geändert, bitte neu laden“), nur die betroffenen Zeilen tauschen oder eine Fassung anhängen, atomar
schreiben (`prompt.md.werkstatt.tmp` + `os.replace`, Zeilenenden erhalten, `Aktualisiert` setzen). Änderungen
außerhalb des Zielblocks bleiben so immer erhalten, weil nie aus einem alten Abbild geschrieben wird.
**Verbleibende Schutzgrenze, bewusst akzeptiert:** speichert ein externer Editor zwischen dem frischen Lesen und
`os.replace` (Millisekunden), gewinnt die Werkstatt; das gilt heute ebenso für die Sammlung.

Der Index (alle `prompt.md`, Belegköpfe) wird je Anfrage aus den Dateien gelesen, Zwischenspeicher nach
Änderungszeit und Größe der Dateien; erwartete Größenordnung: Dutzende bis wenige hundert Einträge.

### Pfade und Öffnen (Sicherheit)

- `prompts.pfad_erlaubt(pfad, wurzeln)`: `os.path.realpath` auf Pfad **und** Wurzeln (löst Junctions und
  symbolische Verknüpfungen auf, auch bei Teilpfaden), dann Vergleich ganzer Pfadteile; abgelehnt werden
  `\\?\`-, `\\.\`- und UNC-Pfade sowie alternative Datenströme (`:` außerhalb des Laufwerksbuchstabens). Gilt für
  Felddateien (`dateiwurzeln` + watch-Arbeitsordner), für jede Datei unter dem Prompts-Ordner und für die Sammlung.
- `oeffnen` nimmt **nie** einen Pfad vom Client oder aus einer Kopfzeile: `{id, was, datei}` mit `was` ∈
  {ordner, sammlung, beleg, schaerfen, html}; `datei` ist ein reiner Dateiname ohne Trennzeichen; der Server baut den
  Pfad aus dem Eintragsordner + `tests\` bzw. `schaerfen\` + Name, verlangt eine reguläre Datei mit Endung `.md`
  bzw. `.html` unter dem Prompts-Ordner (realpath) und ruft erst dann `os.startfile`. `sammlung` öffnet genau die
  konfigurierte Datei. Alles andere → 400.
- POST weiterhin nur mit Werkstatt-Herkunft (`_post_ok`, Kopfzeile `X-Werkstatt`); jede neue Route wird im Test
  ohne diese Kopfzeile mit 403 abgenommen. Nur 127.0.0.1.
- **Log (`werkstatt.log`) ohne Inhalte:** Für alle Arten der Warteschlange protokolliert `_schleife` bei Fehlern nur
  noch Auftragskennung, Anbieter, Modell, Zeichenzahl und die **Fehlerklasse** (`RuntimeError`, `OSError`,
  `_Abbruch`) sowie einen festen Fehlercode, den die neuen Pfade setzen (`anbieter`, `transkript_geaendert`,
  `beleg_geaendert`, `kontext`, `skill_fehlt`, `antwort_leer`); **kein Fragment des Fehlertexts**, weil der
  Anbieterausgabe enthalten kann. Der vollständige Text bleibt in `meldung` (`daten\auswertungen.json`, gitignored)
  und im Beleg. Die neuen Routen fangen Ausnahmen selbst und antworten mit `{fehler}`, ohne Traceback ins Log.

### Testbeleg (eine Datei je Lauf, beim Einreihen angelegt)

Dateiname `tests\<JJJJ-MM-TT HH-MM-SS> – <Fassung> – <Auswerter>.md` über `dateiname()`; beim Einreihen unter der
Sperre exklusiv angelegt (`open(…, 'x')`, bei Dopplung ` (n)` und erneut `'x'`), damit zwei Arbeitsfäden nie
denselben Namen bekommen. Der Dateiname ohne Endung ist die **Auftragskennung** (`auftrag:` im Kopf; die
Warteschlange trägt sie als `prompt.beleg`), über die `.md` und `.html` zusammengehören.

```
---
auftrag: "2026-11-06 14-32-07 – Fassung 2 – Flash-Next"
prompt: "Hühnerfarm"
eintrag: huehnerfarm                  Kennung (Ordnername) oder sammlung:<Überschrift>#<n>
herkunft: ordner                      ordner | sammlung
fassung: "Fassung 2"
fassung_stand: 1a2b3c4d5e6f
rahmen: nein                          ja, wenn der Rahmen der Zusammenfassung vorangestellt wurde (steht dann in Eingaben)
gesendet_stand: <sha256>              Hash des vollständigen Auftrags, siehe „Zusammenbauen“
auswerter: "Flash-Next Q4"
anbieter: lokal
modell: ornith-q4
modell_tatsaechlich: …                nur bei Abweichung (laut /health bzw. /v1/models)
kontext: 262144                       beim Einreihen ermittelt (geladene Variante)
kontext_quelle: /health               /health | /api/ps | Katalog der Zentrale | Anbieter
denkstufe: medium                     nur wenn gesetzt
verarbeitung: lokal                   oder Cloud (OpenAI)
zustand: wartet                       wartet | laeuft | fertig | fehler | abgebrochen
meldung: ""                           letzter Fehler- oder Abbruchtext
erstellt: 2026-11-06 14:32:07
dauer_s: 83                           nach dem Lauf
tokens: 12345                         wenn bekannt
kosten_usd: 0.0021                    wenn bekannt
html: ja                              nur wenn die .html mit gleicher Kennung geschrieben wurde
hinweis: ""                           z. B. „Beleg während des Laufs von Hand geändert“
urteil: offen                         offen | gut | schwach
notiz: ""
status: Entwurf, automatisch erstellt, nicht geprüft
---
## Fassung
~~~text
…die Fassung wörtlich, wie sie beim Einreihen war (bei rahmen: ja ohne den Rahmen)…
~~~
## Eingaben
~~~json
{"rahmen": {"art": "text", "wert": "…"},                                          nur bei rahmen: ja
 "felder": {
   "Transkript": {"art": "transkript", "datei": "…\\transcript-timestamps.txt", "sha": "…", "zeichen": 183420},
   "Projektkontext": {"art": "datei", "pfad": "…", "sha": "…", "zeichen": 18342, "wert": "…voller Inhalt…"},
   "Beispiel": {"art": "text", "name": "beispiel.txt", "wert": "…"},
   "Titel": {"art": "text", "wert": "…"},
   "red, blue": {"art": "woertlich"}},
 "leer": ["Zielumfang"]}
~~~
## Antwort
~~~~~~text
…
~~~~~~
```

- **Zusammenbauen ist eine reine Funktion** `prompts.auftrag_bauen(fassung, eingaben, transkripte)`: ein Durchgang
  `re.sub` über alle Feldnamen gleichzeitig (ein eingesetzter Wert wird nie erneut nach Platzhaltern durchsucht;
  Felder der Art `woertlich` und leere Felder bleiben als Klammer stehen), Rahmen davor, Transkripttexte aus der
  übergebenen Abbildung. Sie liefert den Auftragstext und `gesendet_stand` = sha256 darüber. Vorschau, Einreihen und
  Ausführen rufen genau diese Funktion; es gibt **keinen** gespeicherten „Gesendet“-Text, der von Hand abweichen
  könnte, und die Zuordnung ist eindeutig, auch bei mehreren Transkriptfeldern oder Markierungen im Inhalt.
- **Einreihen (`testen`):** liest Fassung, Felddateien (`wert` kommt in die Eingaben) und Transkripte (nur SHA und
  Zeichenzahl in die Eingaben), baut den Auftrag, vergleicht `gesendet_stand` mit dem Wert aus der Vorschau
  (Abweichung → 409 „Der Inhalt hat sich seit der Vorschau geändert“), schreibt den Beleg mit `zustand: wartet`
  und hängt den Auftrag in die Warteschlange mit `prompt: {eintrag, herkunft, titel, fassung, stand, beleg,
  gesendet_stand}`. Der Hash steht damit **auch außerhalb der handeditierbaren Datei**.
- **Ausführen (`_ausfuehren`, `art: prompt`):** liest Fassung und Eingaben aus dem Beleg, liest die Transkripte aus
  den Dateien und prüft deren SHA-256 (Abweichung oder fehlende Datei → `fehler`, Code `transkript_geaendert`),
  baut den Auftrag neu und vergleicht mit `prompt.gesendet_stand` der Warteschlange (Abweichung → `fehler`, Code
  `beleg_geaendert`: der Beleg wurde seit dem Einreihen von Hand geändert), prüft den Kontext erneut, sendet.
  Nach dem Lauf: Antwort zuerst in den Beleg (Block mit verlängertem Zaun), dann `.html`, dann Kopfzeilen. Hat sich
  der Beleg während des Laufs geändert (Hash erneut verschieden), wird die Antwort trotzdem geschrieben und
  `hinweis` gesetzt.
- Transkripte als Verweis (exakter Laufordner + Datei + SHA-256 des Texts), weil sie unveränderlich im watch-Ordner
  liegen und groß sind. Dateiinhalte aus Feldern stehen wörtlich in den Eingaben, weil sich solche Dateien ändern.
- `urteil` und `notiz` setzt die Werkstatt per Knopf (nur diese beiden Kopfzeilen, frisch gelesen unter der Sperre,
  mit `kopf_stand` des Belegs gegen Konflikt) oder Sascha von Hand. Die Liste der Tests im Reiter kommt aus den
  Belegköpfen; die Warteschlange zeigt zusätzlich `wartet`, `laeuft`, `fehler` **und `abgebrochen`** (mit
  Wiederholen), weil der Dienststart laufende Aufträge auf `abgebrochen` setzt.
- HTML: Enthält die Antwort Zaunblöcke mit Kennung `html` (Tilde oder Backtick) oder beginnt sie mit
  `<!doctype html`/`<html`, wird der größte solche Block als `<Kennung>.html` geschrieben und `html: ja` gesetzt;
  „Im Browser öffnen“ geht nur über `oeffnen` mit `was: html` (serverseitige Zuordnung, nie ein Pfad aus dem Kopf).
- Nichts wird automatisch gelöscht; kein Löschknopf in Version 1.

### Zustände: Beleg und Warteschlange laufen immer gemeinsam

`prompts.beleg_zustand(datei, zustand, meldung='', **kopf)` tauscht unter der Sperre nur die Kopfzeilen `zustand`,
`meldung` und die übergebenen Felder. Die Warteschlange ruft sie bei **jedem** Übergang der neuen Arten:

| Übergang | wo im Code | Beleg |
|---|---|---|
| Einreihen | `einreihen` | Datei angelegt mit `wartet` |
| Start | `_naechste` | `laeuft` |
| Erfolg | `_ausfuehren` | Antwort, `.html`, dann `fertig` + `dauer_s`, `tokens`, `kosten_usd`, `modell_tatsaechlich`, `html` |
| Fehler (auch Transkript-, Beleg-, Kontextprüfung) | `_schleife` except | `fehler` + `meldung` |
| Abbruch (Knopf, Dienstende) | `aktion`, `_schleife`, `__init__` | `abgebrochen` + `meldung` |
| Wiederholen | `aktion` | `wartet`, `meldung` leer |
| Entfernen | `aktion` | unverändert (Datei bleibt, nur Warteschlange) |

**Wiederherstellung beim Dienststart:** Einträge der Warteschlange ohne Beleg → `fehler` „Beleg fehlt“. Belege mit
`wartet`/`laeuft` ohne Warteschlangeneintrag (Absturz zwischen Beleganlage und Speichern der Warteschlange) →
`abgebrochen` „Einreihung unvollständig“; der Reiter zeigt sie mit „Wiederholen“, und Wiederholen baut den
Warteschlangeneintrag **aus dem Beleg** neu (er enthält alles: Fassung, Eingaben, Auswerter, `gesendet_stand`).

**Wiederholen ohne zweiten Modellaufruf:** Steht im Beleg bereits eine Antwort (geschlossener Block mit Text; Absturz
nach dem Antwortblock, vor `.html` oder Kopf; bei Schärfen vor der Übernahme), ruft Wiederholen kein Modell, sondern
führt nur die Nacharbeit erneut aus (`.html`, Kopfzeilen, bei Schärfen die Übernahme). Erst ein Beleg ohne gültigen
Antwortblock löst einen neuen Modellaufruf aus; die alte Antwort geht nie verloren, weil sie vor jeder Nacharbeit
gespeichert wird.

**Belegzugriffe beenden nie den Arbeitsfaden:** Die Warteschlange bleibt die führende Quelle. `beleg_zustand` wird
in `_naechste`, `_ausfuehren` und `_schleife` nur innerhalb von `try/except` aufgerufen. Schlägt ein Belegzugriff
fehl (Datei gelöscht, exklusiv gesperrt, beschädigt), wird der Eintrag `fehler` mit Code `beleg_fehlt` bzw.
`beleg_gesperrt`, die Ausnahme nur mit Klasse geloggt, und der Faden holt den nächsten Auftrag. Der `except`-Zweig
von `_schleife` ist selbst gegen Ausnahmen abgesichert (zweites `try`), damit `finally` die Warteschlange immer
speichert. Die Regel „Auftrag ohne Beleg beim Start → `fehler`“ setzt deshalb keinen beschreibbaren Beleg voraus.

### Einträge aus der Sammlung (Entscheidung 2)

- `prompts.sammlung_kaesten(pfad)` liest mit `bloecke` alle Prompt-Kästen der Sammlung **außerhalb** des
  Werkstatt-Abschnitts (Grenzen: Überschrift `### Werkstatt: Anweisungen für Zusammenfassungen` bis zur nächsten
  `##`/`###`-Überschrift, beide außerhalb von Blöcken bestimmt). Je Kasten: nächste vorangehende `###`/`####`-
  Überschrift außerhalb von Blöcken, laufende Nummer unter dieser Überschrift (drei Überschriften tragen heute zwei
  Kästen), Text, Stand. Kennung `sammlung:<Überschrift>#<Nummer>`; Anzeige = Überschrift, bei Nummer > 1 „(Kasten 2)“.
- Belege und Schärfen-Ergebnisse solcher Einträge liegen im Schattenordner
  `<Ordner>\_Sammlung\<dateiname(Überschrift)>[ #<Nummer>]\` (Eindeutigkeit wie bei Kennungen) mit `tests\`,
  `schaerfen\` und `eintrag.json` (`{ueberschrift, nummer, stand, kaesten_vorher, aktualisiert}`), das bei jedem
  Test/Schärfen und bei jeder Zuordnung den Kastenstand und die Zahl der Kästen unter der Überschrift festhält.
- **Zuordnung beim Auflisten**, in dieser Reihenfolge: (1) unter der Überschrift gibt es einen Kasten mit dem
  gespeicherten Stand → zugeordnet (an gleicher oder anderer Nummer; Nummer in `eintrag.json` nachziehen);
  (2) kein Stand-Treffer, die Überschrift hat **genau einen** Kasten **und** `kaesten_vorher` ist 1 (nachweislich
  1→1, der Normalfall nach einer Handbearbeitung; 35 von 38 Überschriften haben einen Kasten) → zugeordnet mit
  „seit dem Test geändert“; (3) kein Stand-Treffer und mehrere Kästen, oder `kaesten_vorher` > 1 (ein Kasten wurde
  gelöscht), oder zwei Schattenordner beanspruchen denselben Kasten → **„Zuordnung ungeklärt“**: der Schattenordner
  erscheint als eigener Listeneintrag mit den Kandidaten dieser Überschrift und je einem Knopf „Diesem Kasten
  zuordnen“ (schreibt `eintrag.json`), nichts wird automatisch zugeordnet; (4) keine Überschrift mehr →
  „Sammlungseintrag nicht mehr gefunden“ mit „Im Ordner öffnen“.
- Keine Änderung des Sammlungstexts aus dem Reiter. Knöpfe: „In der Sammlung öffnen“, Testen, Schärfen. Schärfen legt
  einen „Vorschlag, nicht übernommen“ unter `schaerfen\` ab; Übernahme von Hand.
- Suche, Filter und Testdialog behandeln beide Herkünfte gleich; Kennzeichen „Sammlung“ in der Liste.

## Reiter-Oberfläche

Neuer Reiter „Prompts“ nach „Zusammenfassung“ (`index.html`, `REITER` in `app.js`, `web\prompts.js` **eingetragen in
`Anfrage.statisch`**, Haken `window.promptsAktiv`, Stile in der vorhandenen CSS-Datei, Aufbau wie Zusammenfassung:
Liste links, Inhalt rechts).

- **Liste:** Suchfeld (Teilstring, ohne Groß/Klein, über Titel, Schlagworte, Quelle und Kastentexte), Filter
  Herkunft (alle / Ordner / Sammlung) und Status (alle / getestet / ungetestet), Sortierung nach `Aktualisiert`
  absteigend, Sammlungseinträge nach Dateireihenfolge, ungeklärte und verwaiste Schattenordner am Ende. Knopf „Neu“:
  Titel, Quelle, Schlagworte, erste Fassung (Name „Fassung 1“).
- **Eintrag:** Kopf (Titel, Quelle als Link wenn `http`, Schlagworte, Bevorzugt), Knöpfe „Im Ordner öffnen“ bzw.
  „In der Sammlung öffnen“, Kopfzeilen bearbeiten (nur Ordner, mit `kopf_stand` inkl. Titel).
- **Fassungen** als Karten: Name, Standkürzel, Text als unveränderter Text (`<pre>`, eingeklappt ab 20 Zeilen),
  Knöpfe „Bearbeiten“ (Dialog wie `anweisungDialog`, mit Stand), „Neue Fassung“, „Als bevorzugt“, „Testen“,
  „Schärfen ▾“ (Schärfen / Erst klären / Kürzen). Bei Sammlung nur „Testen“ und „Schärfen ▾“.
- **Tests:** eine Zeile je Beleg: Datum, Fassung (+ „seit dem Test geändert“, wenn `fassung_stand` nicht mehr
  vorkommt), Auswerter, Dauer · Token · Kosten, Zustand, Urteil (drei Knöpfe offen/gut/schwach) + Notiz (Feld,
  speichert beim Verlassen), „Öffnen“, „Gesendet anzeigen“ (aus Fassung + Eingaben neu gebaut, `GET /api/prompt-datei`
  mit `was: gesendet`), „Im Browser öffnen“ (wenn `html: ja`), „Nochmal“ (Testdialog mit Eingaben aus dem Beleg;
  fehlende oder geänderte Datei bzw. Transkript wird je Feld gemeldet, Sascha entscheidet). Antwort aufklappbar.
- **Darstellung:** Fassungen und Gesendet immer als unveränderter Text. Antworten über `markdown()`, das um
  Zaunblöcke (```` ``` ````/`~~~` → `<pre><code>`, Inhalt nur maskiert, nicht getrimmt, keine Inline-Formatierung)
  erweitert wird; davon profitiert auch der Reiter Zusammenfassung.
- **Schärfen-Ergebnisse:** je Lauf Original und neue Fassung nebeneinander (beide `<pre>`), darunter die
  Stichpunkte des Schreibmodells; Zustand `übernommen (<Name>)` / `Vorschlag, nicht übernommen` / `ungültig: <Grund>`;
  bei „Erst klären“ nur die Fragen.
- **Warteschlange:** wartende, laufende, fehlgeschlagene und abgebrochene Aufträge des Eintrags mit
  Abbrechen/Wiederholen/Entfernen über die vorhandene `/api/fassung`-Aktion; dazu verwaiste Belege (siehe Zustände).
- **Dateien ziehen:** `einrichtenAblegen` in `app.js` wird zentral erweitert: ist der Reiter Prompts sichtbar und
  liegt das Ziel in einem Feld des Testdialogs, ruft es `window.promptsAblegen(e, feld)` und setzt Overlay und
  Markierung wie bisher zurück; sonst Verhalten wie heute. Im Browser gezogene Dateien haben keinen Pfad: ihr Inhalt
  wird mit `File.text()` gelesen und als `{"art": "text", "name": …}` eingesetzt. Pfad + Prüfsumme gibt es nur über
  „Aus Datei…“ (Dateidialog) oder einen eingegebenen Pfad.

### Testdialog (Entscheidung 5)

1. Fassungen anhaken (Vorgabe: bevorzugte), Auswerter anhaken (dieselben Profile wie in der Zusammenfassung,
   mit `verfuegbar`/Grund; Vorauswahl aus `localStorage`). Häkchen „Rahmen der Zusammenfassung voranstellen“
   (Vorgabe aus; nimmt den Kasten „Rahmen“ des Werkstatt-Abschnitts, Beleg `rahmen: ja`, Text in den Eingaben),
   gedacht für Codex.
2. Felder: erkannt mit `\[([^\[\]\n]{1,60})\]`, nicht gefolgt von `(`, mindestens ein Buchstabe, kein `:`
   (schließt `[hh:mm:ss]`, `[00:12:34]`, Markdown-Links aus); gleiche Namen = ein Feld. Jedes erkannte Feld hat ein
   Häkchen **„wörtlich lassen“** (Art `woertlich`, die Klammer bleibt unverändert; für `[red, blue]`, `[x]`, `[ref]`
   und Ähnliches); Vorgabe: Feld. Jedes Feld: mehrzeiliges Textfeld, „Aus Datei…“ (Dateidialog oder Pfad;
   erlaubt unter `dateiwurzeln` + watch-Arbeitsordner über `pfad_erlaubt`; UTF-8 mit Ersatzzeichen; Grenze
   `feld_max_zeichen`, sonst Fehler), **„Aus Transkript…“** (Auswahl aus `transkripte_auflisten` mit Titelsuche,
   Inhalt `transcript-timestamps.txt`) – für jedes Feld, nicht nur `[Transkript]`; `[Transkript]` öffnet die
   Transkriptwahl lediglich als Vorgabe. Damit lässt sich auch `[Transkript folgt]` aus der Sammlung bedienen.
3. Zusammenbauen über `auftrag_bauen` (ein Durchgang, siehe Beleg). Kein Rahmen außer über das Häkchen; bei Claude
   bleibt der feste Systemprompt.
4. Vorschau (`aktion: vorschau`): Auftragstext je Fassung, Transkripte eingeklappt als eine Zeile mit Länge,
   `gesendet_stand` je Fassung, je Auswerter Modell · lokal/Cloud · geschätzte Token gegen Kontext, Hinweise: Claude
   „ohne Werkzeuge“; Codex „Sandbox nur lesend, kann Dateien lesen und Befehle ausführen, liest seine globale
   AGENTS.md mit“; „n Felder leer“. **Kontext** über `Lokal.kontext_geladen(profil)` → `(kontext, quelle,
   modell_tatsaechlich)`: Strata/PolyStrata aus `/health` (`max_context`, `model`; nicht geladen → nicht
   verfügbar), Ollama aus `/api/ps`, NInfer aus dem Katalogwert der Zentrale („laut Zentrale“), Cloud-Anbieter wie
   bisher aus ihrem Katalog. Kombinationen über der Grenze werden abgelehnt. `_ausfuehren` prüft **unmittelbar vor
   dem Senden** erneut mit derselben Funktion (Variante kann inzwischen gewechselt haben) → `fehler`, Code `kontext`,
   mit Kontextangabe; der beim Senden gültige Wert steht im Beleg (`kontext`, `kontext_quelle`).
5. Start (`testen` mit `gesendet_stand` je Fassung): je Kombination Fassung × Auswerter ein Beleg + ein Auftrag in
   der gemeinsamen Warteschlange mit identischem Auftragstext.

### Schärfen (Entscheidung 4)

Dialog: Aktion (Schärfen / Erst klären / Kürzen), Schreibmodell (Auswerter-Profil; Vorgabe das erste verfügbare mit
Anbieter `claude` oder `codex`, zuletzt gewählt aus `localStorage`), Zielmodell (Auswerter-Profil, Vorgabe die
Testauswahl), Feld „Hinweise“ (≤ 2.000 Zeichen), optional „Letzte Antwort als Material“ (Beleg wählen; Antwort auf
30.000 Zeichen gekürzt). Vorschau wie beim Test. Aufbau des gesendeten Texts, fest in `prompts.py`; der Skilltext
wird beim Einreihen gelesen und vollständig in die Schärfen-Datei übernommen (Momentaufnahme; fehlt die Datei:
Fehler, Code `skill_fehlt`, kein Lauf):

```
<SKILL.md ohne Frontmatter>

---
Auftrag der Werkstatt: <Aktion>
Zielmodell: <Name> (<lokal | Cloud (Dienst)>, Kontextfenster <n> Token oder unbekannt, frischer Chat; Claude:
ohne Werkzeuge, Systemprompt „Du bist ein sorgfältiger Assistent.“; Codex: Sandbox nur lesend mit Werkzeugen;
lokal: ohne Werkzeuge und ohne Projektgedächtnis).
Hinweise von Sascha: <Text oder „keine“>
Erwartete Antwort bei Schärfen/Kürzen: zuerst die neue Fassung in genau einem Kasten (Zeile ~~~text davor,
Zeile ~~~ danach, keine weiteren Kästen mit ~~~), danach die wichtigsten Änderungen als Stichpunkte. Platzhalter
in eckigen Klammern zeichengetreu erhalten. Den Auftrag nicht ausführen.
Erwartete Antwort bei Erst klären: nur die Rückfragen als nummerierte Liste, keine neue Fassung, kein Kasten.
Fassung „<Name>“:
~~~text
<Text>
~~~
[Material, Antwort des Zielmodells vom <Datum> auf diese Fassung:
<Block über block_schreiben, Kennung text; der Auftrag nennt die Zaunlänge, z. B. „Kasten mit fünf Tilden“>]
```

Die Schärfen-Datei `schaerfen\<Datum> – <Aktion> – <Schreibmodell>.md` wird beim Einreihen angelegt (`'x'`), Kopf wie
Beleg, zusätzlich `aktion`, `zielmodell`, `skill_stand`, `gesendet_stand`, `ergebnis: offen`; Abschnitte
`## Fassung`, `## Eingaben` (Hinweise; Skilltext als `wert`; **Material als `wert` in der gekürzten Form, wie sie
gesendet wird**, plus Herkunftsverweis auf den Beleg; Zielmodell-Angaben), nach dem Lauf `## Antwort`. Der
Schärfen-Auftrag ist ebenso eine reine Funktion `schaerfen_bauen(fassung, eingaben)` aus diesen gespeicherten
Werten; `gesendet_stand` liegt auch im Warteschlangeneintrag und wird vor dem Senden gegen den neu gebauten Auftrag
geprüft (Code `beleg_geaendert`). Ein später geänderter oder gelöschter Quellbeleg berührt den eingereihten Lauf
nicht mehr. Zustände wie beim Beleg.

**Auswertung** (Schärfen/Kürzen, Ordnereintrag), alles muss gelten, sonst `ergebnis: ungültig (<Grund>)` und die
Antwort bleibt nur in der Datei: **genau ein** Prompt-Kasten laut `bloecke` (Tilde oder Backtick, Kennung `text`
oder leer, geschlossen); `text_pruefen` besteht; alle Platzhalter der Originalfassung kommen in der neuen vor
(Verlust → ungültig; **neue** Platzhalter sind erlaubt und werden angezeigt, das ist der Weg zum
`[Projektkontext]`); erzeugter Name `<Aktion> <TT.MM.> <Schreibmodell>` besteht `name_pruefen` plus
Steuerzeichenverbot (bei Dopplung ` (n)`).

**Übernahme, wiederholbar ohne Duplikat:** Die Antwort wird zuerst in die Schärfen-Datei geschrieben und die
Warteschlange gespeichert. Dann unter der Sperre: `prompt.md` frisch lesen; gibt es schon eine Fassung mit dem Stand
des neuen Kastens → nur `ergebnis: übernommen (<Name>)` setzen; sonst anhängen, dann `ergebnis` setzen. Ein Absturz
zwischen Anhängen und `ergebnis` ist harmlos: Wiederholen ruft wegen der vorhandenen Antwort **kein Modell** mehr
(siehe Zustände), findet die Fassung über den Stand und setzt nur `ergebnis`. Bei Sammlungseinträgen immer
`ergebnis: Vorschlag, nicht übernommen`. Bei „Erst klären“ kein Kasten erwartet; ein trotzdem gelieferter Kasten wird
nicht übernommen. Ein Urteil gibt es für Schärfen-Läufe nicht; sie werden über Tests beurteilt.

## Warteschlange und Schnittstelle

- `Auswertungen.liste`-Einträge bekommen `art` ∈ {`zusammenfassung`, `prompt`, `schaerfen`}. **Normalisierung
  zentral:** beim Laden in `__init__` bekommt jeder Eintrag ohne `art` den Wert `zusammenfassung`; `anlegen` setzt
  ihn ab sofort. `FELDER` um `art` und `prompt` ergänzt; `stand()` liefert beide. Alle Verbraucher trennen nach Art:
  der Reiter Zusammenfassung zeigt nur `art === 'zusammenfassung'`, der Reiter Prompts nur seine beiden Arten,
  `messungen.zusammenfassung()` bekommt vom Server nur Zusammenfassungs-Einträge (Prompt-Tests zählen dort nicht).
- `_ausfuehren` verzweigt nach `art`: Zusammenfassung unverändert; Prompt und Schärfen wie oben beschrieben, beide
  ohne `pruefung.nachpruefen`. Neue Methode `Auswertungen.einreihen(auftrag)` (anhängen, speichern, wecken);
  `anlegen` bleibt für Transkripte. Bekannte, unveränderte Grenze: Abbrechen eines lokalen Laufs beendet nur das
  Warten (`_Lauf.http`), das Modell rechnet die Anfrage zu Ende; gilt heute ebenso.
- Routen: `GET /api/prompts` (Index, Filterwerte, Warteschlangenstand der neuen Arten, ungeklärte/verwaiste
  Schattenordner), `GET /api/prompt?id=` (Kopf mit `kopf_stand`, Fassungen mit Stand, Belege aus den Dateien,
  Schärfen-Läufe), `GET /api/prompt-datei?id=&was=&datei=` (Inhalt eines Belegs oder Schärfen-Laufs oder der neu
  gebaute Auftragstext `was: gesendet`; Pfad serverseitig gebaut wie bei `oeffnen`), `POST /api/prompt` mit
  `aktion` ∈ {neu, kopf, fassung_speichern, fassung_neu, bevorzugt, oeffnen, urteil, zuordnen, datei_lesen,
  datei_waehlen, vorschau, testen, schaerfen, wiederholen_beleg}. Fehler als `{fehler}` mit sprechendem Text, 409 bei
  Konflikt, 403 ohne Herkunft.

## Scheiben (Entscheidung 6) mit Abnahme

Jede Scheibe läuft als eigener Bau mit Tests (Befehl oben) und Abnahme im Browser; Abnahme gegen diese Punkte, nie
gegen die Selbstauskunft des Builders. Kein Commit und kein Push ohne Saschas Auftrag (`werkstatt\daten` bleibt
gitignored; `config.json` ist versioniert und bekommt den Block `prompts`). Fake-Anbieter in den Tests liefern
**je Aufruf eine andere Antwort** (Zähler im Text), damit Duplikate nicht hinter identischen Antworten verschwinden.

**Scheibe 1, Ablage und Suche.** `prompts.py` (`bloecke`, `block_schreiben`, `_zaunlaenge`, `Eintrag`, Kennungen,
`pfad_erlaubt`, Index, `sammlung_kaesten`, Schattenordner-Zuordnung), Routen ohne Testen/Schärfen, `/prompts.js` in
der Freigabeliste, Reiter mit Liste, Suche, Filtern, Eintrag anlegen, Fassung bearbeiten/anlegen, Bevorzugt, Kopf
bearbeiten, Öffnen-Knöpfe, Zuordnen-Knöpfe. Abnahme: (a) Ordner mit zwei Beispieleinträgen (Hühnerfarm mit einer
Fassung, Videoanalyse-Kopie mit `[Transkript]` und `[Projektkontext]`) und die Sammlung erscheinen in einer Liste,
Zahl der Sammlungseinträge = Prompt-Kästen außerhalb des Werkstatt-Abschnitts; Reiter lädt ohne Konsolen- oder
Netzwerkfehler; (b) Suche nach „html“ findet Hühnerfarm, Filter Sammlung blendet Ordnereinträge aus;
(c) Bearbeiten mit veraltetem Stand → 409 mit Meldung, nach Neuladen klappt es; Kopfdialog nach Titeländerung im
Editor → 409 (Titel ist im `kopf_stand`); (d) Unit-Test: Notiz zwischen den Kästen (CRLF) wird **nach** dem Laden der
Oberfläche in die Datei geschrieben, dann speichert die Werkstatt eine andere Fassung → Notiz bleibt Byte für Byte
erhalten; (e) unlesbare und mehrdeutige `prompt.md` (ungeschlossener Zaun, zwei Kästen unter einer Überschrift)
erscheinen entsprechend gekennzeichnet, ohne Bearbeitung; Backtick-Block und `~~~python` als Notiz stören nicht;
(f) Unit-Tests Kennungen: `CON`, `A/B` gegen `A:B`, Titel `_Sammlung`, Groß/Klein-Dopplung; (g) Unit-Test
`pfad_erlaubt`: Junction (`_winapi.CreateJunction`) unter einer Wurzel auf ein Ziel außerhalb → abgelehnt; `\\?\`
und `datei.txt:strom` → abgelehnt; (h) `oeffnen` mit `datei` = `..\x.cmd`, mit absolutem Pfad, mit Endung `.cmd`
→ 400, Datei wird nicht gestartet (Test mit gepatchtem `os.startfile`); (i) POST ohne `X-Werkstatt` → 403;
(j) Zaun-Rundlauf: `block_schreiben` + `bloecke` mit Inhalten, die `~~~` mit 0, 1, 2 und 3 führenden Leerzeichen,
vier Tilden und Backticks enthalten → Inhalt kommt Byte für Byte zurück; (k) Sammlung: zwei Kästen unter einer
Überschrift bekommen Nummer 1 und 2; ein davor eingefügter Kasten verschiebt die Nummer, Zuordnung über den Stand;
Überschrift mit einem Kasten (`kaesten_vorher` 1), Kasten bearbeitet → „seit dem Test geändert“; Überschrift mit
zwei Kästen, Kasten davor eingefügt **und** getesteter Kasten bearbeitet → „Zuordnung ungeklärt“, Knopf ordnet zu
und `eintrag.json` trägt den neuen Stand; zwei getestete Kästen A und B, A gelöscht → B über den Stand zugeordnet,
der Schattenordner von A „ungeklärt“ (nie A → B); Überschrift gelöscht → „nicht mehr gefunden“.

**Scheibe 2, Testen mit Belegen.** Felder, „wörtlich lassen“, Dateien, Transkriptwahl je Feld, `auftrag_bauen`,
Vorschau mit `gesendet_stand`, Rahmen-Häkchen, Mehrfachlauf, Beleg beim Einreihen, Zustandstabelle, Wiederherstellung
beim Start, Warteschlangen-Verzweigung mit `art`-Normalisierung, `kontext_geladen` und Nachprüfung, HTML-Datei,
Urteil/Notiz, Nochmal, „Gesendet anzeigen“, Messungen-Filter, Log-Hygiene. Abnahme: (a) Hühnerfarm an ein lokales
Modell → Beleg mit Kopf, Fassung, Eingaben und Antwort, `.html` daneben, „Im Browser öffnen“ zeigt die Seite,
„Gesendet anzeigen“ zeigt den Auftragstext; (b) zwei Fassungen × ein Auswerter mit demselben Transkript → zwei
Belege, identischer Eingaben-Block, `fassung_stand` und `gesendet_stand` verschieden; (c) Urteil „gut“ + Notiz → nur
diese zwei Kopfzeilen ändern sich (Unit-Test auf Byte-Gleichheit des Rests; Urteil mit veraltetem `kopf_stand` →
409); (d) Vorschau lehnt ein zu langes Transkript für ein lokales Modell mit Kontextangabe ab; Unit-Test mit
gefälschtem `/health`: zwei Varianten mit **demselben Modellnamen**, geladen ist die 128K-Variante, Standard ist
256K → Kontext 131072, Beleg `kontext_quelle: /health`; `_ausfuehren` mit Fake, dessen Kontext nach dem Einreihen
sinkt → `fehler`, Code `kontext`; (e) „Nochmal“ füllt alle Felder, meldet eine geänderte Datei; (f) Reiter
Zusammenfassung zeigt keine Prompt-Läufe; `auswertungen.json` mit acht Alt-Einträgen ohne `art` → alle weiterhin
sichtbar; Messungen zählen keine Prompt-Tests; (g) Unit-Test: Werte mit `[Klammern]` im Inhalt werden nicht ersetzt,
„wörtlich lassen“ lässt die Klammer stehen, zwei Transkriptfelder bekommen je ihr Transkript; (h) Unit-Test: Fassung
nach der Vorschau geändert → `testen` 409; Beleg nach dem Einreihen von Hand geändert (Fassungsblock) →
`_ausfuehren` `fehler`, Code `beleg_geaendert`, kein Modellaufruf; (i) zwei Einreihungen in derselben Sekunde → zwei
verschiedene Belege (`'x'`); (j) Dienstneustart mit laufendem Auftrag → Beleg und Warteschlange `abgebrochen`,
Wiederholen schreibt die Antwort in denselben Beleg; Beleg mit `wartet` ohne Warteschlangeneintrag beim Start →
`abgebrochen` „Einreihung unvollständig“, Wiederholen reiht aus dem Beleg neu ein; Transkript nach dem Einreihen
geändert (Fake) → `fehler`, Code `transkript_geaendert`, Beleg `zustand: fehler`; Fehler in der Transkriptprüfung
hinterlässt nie `wartet` im Beleg; (k) Fake-Anbieter, der nach dem Antwortblock eine Ausnahme wirft → Beleg hat
Antwort, Zustand `fehler`; Wiederholen → **kein** zweiter Modellaufruf (Zähler des Fakes bleibt), `.html` und Kopf
werden nachgetragen; (l) abgeschnittene Antwort mit offenem Codeblock → Beleg bleibt lesbar (verlängerter Zaun);
(m) Logtest: Fake wirft `RuntimeError('MARKIERUNG-GEHEIM …')` mit der Markierung **am Anfang** → Logdatei enthält
die Markierung nicht, `meldung` enthält sie; (n) zwei Aufträge eingereiht, der Beleg des ersten wird vor dem Start
gelöscht bzw. exklusiv geöffnet → erster Eintrag `fehler` mit Code `beleg_fehlt`/`beleg_gesperrt`, der zweite läuft
im selben Arbeitsfaden durch; Beleg ohne Antwortabschnitt (vor der Antwort abgebrochen) → Wiederholen ruft das
Modell erneut (Zähler steigt), Beleg mit leerem oder offenem Antwortblock ebenso.

**Scheibe 3, Schärfen.** Dialog, Promptaufbau mit Skill-Momentaufnahme, Antwort auswerten, Übernahme, Vorschlag bei
Sammlung, Anzeige nebeneinander. Abnahme: (a) Schärfen eines Ordnereintrags mit Codex oder Claude → neue Fassung in
`prompt.md`, Datei unter `schaerfen\` mit `ergebnis: übernommen`, Anzeige Original/neu/Stichpunkte; (b) Schärfen
eines Sammlungseintrags → nur Datei im Schattenordner, Sammlung Byte für Byte unverändert (Prüfsumme
vorher/nachher); (c) Erst klären → Fragen, kein Kasten, keine neue Fassung; (d) Unit-Tests mit Fake-Anbieter: kein
Kasten, zwei Kästen, Backtick-Kasten (gültig), Kasten mit `~~~`-Zeile, verlorener Platzhalter, Name mit `\r` →
jeweils `ungültig (<Grund>)` bzw. übernommen, nichts doppelt; neuer Platzhalter → übernommen und angezeigt;
(e) Fake, der nach dem Anhängen der Fassung, vor `ergebnis`, abstürzt → Wiederholen ruft kein Modell (Zähler
unverändert), hängt nichts an, setzt `ergebnis: übernommen` auf die vorhandene Fassung; (f) fehlende `SKILL.md` →
Fehlermeldung vor dem Start; (g) nicht angemeldetes Claude → Grund mit Anmeldebefehl wie heute; (h) Material mit
`~~~`-Zeilen und eingerückten `  ~~~` im Auftrag → Zaun verlängert, Antwort korrekt ausgewertet; (i) Quellbeleg nach
dem Einreihen des Schärfen-Laufs geändert oder gelöscht → der Lauf sendet den gespeicherten Materialtext (Fake prüft
den Auftragstext), Schärfen-Datei von Hand geändert → `fehler`, Code `beleg_geaendert`.

Unit-Tests in `werkstatt\tests\test_prompts.py` (Blöcke, Zäune, Kennungen, Pfade, Eintrag, Belege, `auftrag_bauen`,
Zustände, Sammlung, Schärfen-Auswertung) und Erweiterungen in `test_werkstatt.py` (Routen, Herkunft, `oeffnen`,
Warteschlange mit Fake-Anbieter und Zähler, gefälschtes `/health`, Absturz-Injektion zwischen Schreibschritten).

Dokumentation: README „Werkstatt bedienen“ → neuer Abschnitt „### Prompts“ (Ablage, Felder, Belege, Zustände,
Schärfen, Codex-Hinweis); `AGENTS.md` Zeile „Anweisungen für Zusammenfassungen leben nur in der Promptsammlung …
keine zweite Promptablage anlegen“ wird ergänzt: Coding-/Kreativprompts und alle Testbelege liegen unter
`Arbeitsmaterial\Prompts` (Reiter Prompts); Wissensprompts bleiben in der Sammlung, die Werkstatt schreibt dort
weiterhin nur im Werkstatt-Abschnitt. Ein Satz dazu in `C:\Workstation\Skills\BETRIEB.md` („Desktop-Prompts
fortführen“) erst nach Saschas Freigabe, weil die Datei außerhalb dieses Repos liegt.

## Entscheidungen und Abwägungen

1. **Ordner je Prompt statt JSON-Datenbank oder zweiter Sammlungsdatei.** Handänderung mit jedem Editor, Belege
   liegen neben dem Prompt, Git-tauglich. Preis: Parser mit Zaunzustand und Konfliktschutz, Index aus Dateien.
2. **Sammlung nur lesen und testen.** Rückschreiben an beliebige Stellen der handgepflegten Datei ist der riskanteste
   Teil und am ersten Tag unnötig; Schattenordner hält Belege, Vorschläge bleiben erkennbar Vorschläge. Preis:
   Handkopie bei Übernahme, positionsabhängige Kennung (Stand-Zuordnung, Einkasten-Regel, sonst Nachfrage).
3. **Beleg = Fassung + Eingaben + Antwort, Auftragstext immer neu gebaut.** Es gibt keinen gespeicherten Text, der
   von Hand abweichen könnte; der Hash des Auftrags liegt in der Warteschlange und wird vor dem Senden geprüft.
   Preis: Belege mit Dateiinhalten können groß werden; Kopf- und Abschnittsparser für Belege.
4. **Transkript als Verweis mit SHA.** Reproduzierbar und lesbar; Transkripte sind unveränderlich und groß. Preis:
   geändertes Transkript macht Wiederholen unmöglich (wird gemeldet).
5. **Skill als Momentaufnahme je Lauf, Auftragsblock fest im Code.** Eine Quelle für die Schärfen-Regeln, das
   Kastenformat kann nicht von Hand kaputtgehen, jeder Lauf dokumentiert den Skilltext, mit dem er lief. Preis:
   Anpassung des Rahmens ist eine Codeänderung.
6. **Dateien je Feld statt Projektauswahl.** Ein Mechanismus für Projektkontext, Beispiele, Material; der Beleg
   bleibt nachvollziehbar. Preis: Sascha wählt die Datei selbst.
7. **Gemeinsame Warteschlange mit `art` und gespiegelten Zuständen im Beleg.** Abbrechen, Wiederholen, Parallelität
   und Anbieter kommen umsonst mit; der Beleg trägt alles, um einen Auftrag nach einem Absturz neu einzureihen.
   Preis: `art`-Normalisierung, Filter in allen Verbrauchern, Zustandsaufrufe an jedem Übergang.
8. **Antwort vor jeder Nacharbeit gespeichert, Wiederholen ohne zweiten Modellaufruf.** Duplikatfrei und ohne
   Verlust einer Antwort. Preis: ein weiterer Schreibvorgang je Lauf.
9. **Kein Rahmen und keine Nachprüfung beim Prompt-Test, Rahmen nur als Häkchen.** Der Prompt wird so getestet, wie
   er dasteht; Codex-Tests können den Rahmen bewusst dazunehmen.
10. **Ehrliche Kennzeichnung statt Werkzeugsperre bei Codex.** Eine technisch geprüfte Deaktivierung gibt es nicht;
    die Vorschau sagt, was Codex kann. Preis: Sammlungsprompts mit Datei- oder Rechercheaufträgen verhalten sich bei
    Codex anders als bei Claude oder lokal.
11. **Log ohne jeden Fehlertext.** Kein Modellinhalt kann ins Log geraten. Preis: zum Nachvollziehen eines Fehlers
    braucht man die Warteschlange oder den Beleg, nicht nur das Log.

## Risiken und offene Punkte

- Claude-CLI-Anmeldung läuft ab (zuletzt abgelaufenes Abo-Token): bleibt wie heute über `verfuegbar` sichtbar, mit
  Anmeldebefehl; keine automatische Anmeldung.
- Codex liest seine globale `AGENTS.md` mit und hat lesende Werkzeuge: Antworten können gefärbt sein; in der
  Vorschau benannt, nicht lösbar ohne eigenen Codex-Ordner.
- Lokale Modelle: Schätzung ist grob (3 Zeichen je Token); Ablehnung vor dem Einreihen und vor dem Senden; NInfer
  ohne `/health`-Kontext, Katalogwert gekennzeichnet.
- Belege mit großen Dateiinhalten (bis 400.000 Zeichen je Feld) wachsen entsprechend; bewusst, Sascha räumt von Hand.
- Abbrechen lokaler Läufe beendet das Rechnen nicht (vorbestehend).
- Handänderung am Beleg während eines Laufs: Antwort wird trotzdem gespeichert, `hinweis` gesetzt; keine
  Wiederherstellung des alten Belegtexts.
- Offen: Vorgabename neuer Fassungen („Fassung n“ gegen Datum), ob Sammlungseinträge mit Pflichtfeldern wie `[Frage]`
  eine Warnung brauchen (Vorschlag: nein, Vorschau zeigt leere Felder).

## Nicht in Version 1

Wortvergleich mit Hervorhebung; Löschknopf für Belege und Fassungen; Rückschreiben in die Sammlung außerhalb des
Werkstatt-Abschnitts; Projektauswahl oder automatisches Briefing; Skill-Entwurf aus einer bewährten Vorlage;
Statistiken über Tests; Import von Internetseiten; editierbare Auftragsblöcke; Bild- oder Binäranhänge in Feldern;
Änderungen an den Anbietern (Werkzeuge, Systemprompt, Abbruchverhalten); Umbau von `_zerlegen` für den
Werkstatt-Abschnitt.

## Baustand

- **Scheibe 1 gebaut und abgenommen (06.11.2026)**: Codex Sol medium, 11 min, keine Fixrunde; 329 Tests grün;
  Browser-Abnahme (a)–(e) auf Port 3896 aus dem Worktree, (f)–(k) über Unit-Tests; Sicherheitspass ohne Befund.
  Claude-Nachbesserung: Steuerzeichenverbot um NEL/LS/PS erweitert (`_STEUERZEICHEN`). Branch `bau/reiter-prompts`
  im Worktree `KI-Zentrale-bau-prompts`. Offen aus Scheibe 1: Vorgabename neuer Fassungen (Dialog verlangt einen Namen).
- Scheibe 2 und 3: noch nicht begonnen.

## Lehre aus diesem Lauf

- Zeit gekostet: Die drei Astra-Runden (xhigh) liefen 10–17 Minuten und überschritten die 10-Minuten-Grenze des
  Bash-Werkzeugs (Lauf wird in den Hintergrund verschoben, kein Schaden, aber unnötige Unterbrechung); das
  Live-Skript im Terminal-Panel scheiterte zuerst an der PowerShell-Ausführungsrichtlinie. Der Bau selbst lief glatt.
- Was sich ändert: In `grill-me-codex`/`codex-review` Review-Runden von Anfang an als Hintergrundlauf mit
  Ausgabedateien starten (kein 10-Minuten-Limit, keine Pipe); in `codex-build` den Live-Tab mit
  `powershell -NoProfile -ExecutionPolicy Bypass -File <skript>` starten. AGENTS.md der KI-Zentrale: nichts
  (Interpreterpfad steht schon drin).
