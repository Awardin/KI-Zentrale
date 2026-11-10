# SPEC: Reiter Prompts – Arbeitsfläche mit Rückfragen

Stand: 10.11.2026, Fassung 3.1 (nach Astra-Runde 3; deren zwei P1 und drei P2 eingearbeitet, keine Runde 4). Basis für den Bau: `main` nach dem Merge von
`bau/prompts-anzeige` (Menüs schließen beim Klick daneben `pMenuesSchliessen`, Laufanzeige `pLaufanzeige`).

## Anlass

Sascha nach dem ersten echten Zwei-Modell-Lauf (10.11.2026):
- „Schöner wäre, wenn man 2 Fenster nebeneinander hätte. Wo dann der neue Prompt ausgegeben wird neben dem alten und
  wo man dann auch einfach reinschreiben kann und auf Prompt verbessern klickt.“
- „Immer den neuen Prompt, den alten zu verbessern macht wenig Sinn. Links mein Prompt … rechts neuer Prompt und dann
  dort auch einfach auf verbessern klicken.“
- „Cool wäre es, wenn man auf Prompt verbessern nicht einfach einen neuen Prompt bekommt, sondern wenn … ein Fenster
  aufginge, wo man dann entsprechende Fragen kurz beantwortet, damit das Modell anhand der Fragen den Prompt schärfen
  und verbessern kann.“ (Vorlage: Bildschirmfoto eines Prompt-Verbesserers mit „Verbessere deinen Prompt (0/3)“,
  Fragekarten mit Priorität „Kritisch / Hohe / Mittlere Priorität“ und kurzer Begründung.)
- „Ordne die UI/UX so an, wie du meinst, dass es am praktikabelsten ist. Das gilt auch für die Rechts/links-Regel.“

## Ziel

Ein ausgewählter Eintrag im Reiter Prompts zeigt oben eine **Arbeitsfläche**: links „Dein Prompt“ und die Rückfragen,
rechts „Neuer Prompt“ zum Lesen, Bearbeiten und Weiterverbessern. „Prompt verbessern“ verbessert immer den rechts
sichtbaren Text in zwei Schritten: (1) ein Modell stellt 0–5 kurze Rückfragen mit Priorität, Begründung und
Antwortvorschlägen, (2) Sascha beantwortet (oder überspringt) sie, und die gewählten Schreibmodelle schreiben mit den
Antworten die nächste Fassung. „Direkt verbessern“ lässt die Fragen aus. Jede Runde bleibt als Fassung und Beleg
nachvollziehbar.

## Gestaltungsentscheidungen (Claude, auf Saschas „wie du meinst“)

- **D1 Links Eingaben, rechts Ergebnis.** Links steht, was von Sascha kommt (sein Ausgangsprompt, seine Antworten),
  rechts breit der aktuelle neue Prompt. Der lange neue Prompt bleibt gut lesbar, der meist kurze Ausgangsprompt braucht
  wenig Platz, und die Fragen stehen direkt neben dem Text, auf den sie sich beziehen.
- **D2 Verbessert wird immer der rechts sichtbare Text** (Saschas Wahl), samt seinen ungespeicherten Änderungen (O5).
- **D3 Rückfragen als Standard**, „Direkt verbessern“ als zweiter Knopf daneben; nach den Fragen zusätzlich
  „Ohne Antworten verbessern“ und „Weitere Wünsche“ als freies Feld.
- **D4 Fragesteller**: Vorgabe ist das Schreibmodell, das den rechts gezeigten Text geschrieben hat (eine einfache,
  nachvollziehbare Vorgabe – der neue Aufruf kennt keinen früheren Verlauf), sonst das erste der gemerkten
  Schreibmodelle. Die Vorgabe ist sichtbar und vor dem Fragen änderbar.
- **D5 Bearbeiten direkt im rechten Feld.** Geänderter Text wird vor jeder weiterführenden Aktion als eigene Fassung
  „Bearbeitet TT.MM. · …“ gespeichert, mit dauerhaft gespeicherter Herkunft (S6). Belege bleiben reproduzierbar,
  nichts wird überschrieben.
- **D6 Mehrere Schreibmodelle als Reiter** über dem rechten Feld; „Nebeneinander vergleichen“ zeigt alle Fassungen der
  Runde in Spalten (heutiger gemeinsamer Renderer) über die volle Breite.
- **D7 Höchstens 5 Fragen, meist 3, auch 0**, wenn nichts Wichtiges offen ist. Die bisherigen Abschnitte des Eintrags
  (Fassungen, Schärfen, Tests, Warteschlange) bleiben unverändert unter der Arbeitsfläche.

## Begriffe

- **Runde**: eine Composer-Sendung (`auftragsgruppe`) am Eintrag. Schärfen-Runde = Aktion „Schärfen“, Fragen-Runde =
  neue Aktion „Rückfragen“ (genau ein Beleg).
- **Lauf**: ein Beleg einer Runde (ein Ziel × ein Schreibmodell).
- **Herkunft** einer Fassung: für Ergebnisfassungen der Beleg, dessen `ergebnis_fassung` sie ist; für „Bearbeitet …“
  die in S6 gespeicherte Quelle. **Quellbeleg** = Beleg, aus dem Typ, Modus, Realismus, Materialien, Kontexte und Ziel
  für neue Runden stammen: bei Ergebnisfassungen ihr Beleg, bei „Bearbeitet …“ der in S6 gespeicherte `quell_beleg`
  (von der Quelle geerbt). Ohne Quellbeleg: Werte des Eintrags (`prompt_typ`, `modus`), keine Materialien, keine
  Kontexte, Ziel unbekannt.
- **Bezugsfassung** einer Fragen-Runde: deren Basis (`fassung`, `fassung_stand`). Fragen gelten für die rechts gezeigte
  Fassung, wenn deren Name und aktueller Stand gleich der Bezugsfassung sind oder wenn die gezeigte Fassung über eine
  Kette von „Bearbeitet …“-Fassungen mit gültiger Herkunft (`herkunft_gueltig`, S6; höchstens 10 Glieder, Schleifen
  abbrechen) auf die Bezugsfassung zurückgeht. Das ist eine Regel der Oberfläche: Der Server prüft Antworten nur auf
  ihre Form (S3), weil die Oberfläche die angezeigten Fragen samt Antworten als Momentaufnahme schickt.

## Server (werkstatt/prompts.py, ggf. werkstatt/server.py)

S1 **Neue Aktion „Rückfragen“.** `AKTIONEN = ('Schärfen', 'Erst klären', 'Kürzen', 'Rückfragen')`. Nur mit
   `bau_version` 2 und nur über `composer_vorschau`/`composer_senden` mit `basis`, genau einem Ziel und genau einem
   Schreibmodell; sonst 400 „Rückfragen gibt es nur für eine gespeicherte Fassung, ein Ziel und ein Schreibmodell.“
   `schaerfen_vorschau` und `schaerfen` (Schärfen-Dialog, Menü „Schärfen ▾“) lehnen „Rückfragen“ mit 400 ab; dort
   erscheint die Aktion nicht.

S2 **Ausgabevertrag für „Rückfragen“** in `_schaerfen_bauen_v2` (wörtlich, an der Stelle von `vertrag`):

   > Stelle Sascha Rückfragen, deren Antworten diese Fassung für das Zielmodell spürbar verbessern. Schreibe keine neue
   > Fassung und führe den Auftrag nicht aus. Antworte nur mit genau einem geschlossenen Kasten (Zeile ~~~json davor,
   > Zeile ~~~ danach) mit diesem JSON:
   > {"fragen": [{"prioritaet": "kritisch", "frage": "…", "warum": "…", "vorschlaege": ["…", "…"]}]}
   > Regeln: 0 bis 5 Fragen, meist 3, die wichtigste zuerst. Ist nichts Wichtiges offen, gib {"fragen": []} zurück.
   > prioritaet ist genau eines von kritisch, hoch, mittel: kritisch = ohne Antwort muss das Zielmodell an einer Stelle
   > raten, die das Ergebnis unbrauchbar machen kann; hoch = die Antwort ändert Inhalt, Umfang oder Format deutlich;
   > mittel = Feinschliff. Frage nichts, was Fassung, Material oder Kontext schon beantworten, und nichts, was das
   > Zielmodell selbst gut entscheiden kann. Eine Frage je Punkt, höchstens 25 Wörter, Du-Ansprache. warum: ein Satz,
   > was die Antwort am Prompt ändert. vorschlaege: 0 bis 4 kurze typische Antworten mit je höchstens 8 Wörtern, wenn
   > es naheliegende gibt, sonst eine leere Liste. Keine Fragen nach Zugangsdaten oder nach Daten einzelner
   > Patientinnen und Patienten.

   Bei „Rückfragen“ entfällt der Absatz „Bestimme den passenden Typ in derselben Antwort …“ (auch bei Typ `auto`);
   alle übrigen Zeilen (Zielmodell, Zielregeln, Modus, Hinweise, Fassung, Material, Kontexte) bleiben wie bei
   „Schärfen“. Bestehende Aktionen und ihre Aufträge bleiben Byte für Byte gleich.

S3 **Antworten im Schärfen-Auftrag.** Neues optionales Eingabefeld `rueckfragen` (nur bei Aktion „Schärfen“ mit
   `basis`, sonst 400 „Antworten auf Rückfragen gibt es nur beim Schärfen einer gespeicherten Fassung.“): Liste
   `[{"prioritaet": "kritisch"|"hoch"|"mittel", "frage": "…", "antwort": "…"}]` mit 1–5 Einträgen – genau die
   angezeigten Fragen mit Saschas Antworten (Momentaufnahme). `frage` 1–300 Zeichen ohne Zeichen aus `_STEUERZEICHEN`;
   `antwort` nach Normalisierung (`\r\n`/`\r` → `\n`, außen getrimmt) 1–600 Zeichen, Zeilenumbrüche erlaubt, alle
   anderen Zeichen aus `_STEUERZEICHEN` verboten. Sonst 400 mit deutscher Meldung. Dieselbe reine Formprüfung in
   `composer_vorschau`, `composer_senden` und `schaerfen_lesen` – keine Verweise auf andere Belege, daher bleiben
   gespeicherte Aufträge lesbar und `auftrag_aus_beleg` baut sie aus den Eingaben neu. Das Feld wird normalisiert in den
   Eingaben gespeichert und kommt in die Erlaubtliste von `_composer_fingerabdruck`. Kein Feld `fragen_beleg`.
   Steht `rueckfragen` in den Eingaben, hängt `_schaerfen_bauen_v2` direkt nach der Zeile „Hinweise von Sascha: …“ an:

   > Antworten von Sascha auf Rückfragen (gehen Annahmen vor; offene Punkte nicht raten, sondern frei lassen oder als
   > Platzhalter in eckigen Klammern kennzeichnen):
   > 1. [kritisch] <frage>
   >    Antwort: <antwort, Folgezeilen mit drei Leerzeichen eingerückt>

   Fehlt das Feld, fehlt es auch in Eingaben und Fingerabdruck (nie als `[]`/`null` ergänzen): Aufträge, Prüfsummen
   und teilweise angelegte alte Sendungen bleiben unverändert und fortsetzbar. `datei_inhalt`/`schaerfen_anzeige`
   liefern `rueckfragen` aus den Eingaben mit (für „Beantwortete Fragen“ und „Nochmal“).

S4 **Auswerten.** `schaerfen_auswerten` für „Rückfragen“: genau ein geschlossener Kasten mit Kennung `json` oder ohne
   Kennung, `json.loads`, Schema: Objekt mit Liste `fragen` (0–5 genommen, weitere abgeschnitten), je Eintrag
   `prioritaet` aus {kritisch, hoch, mittel}, `frage` nicht leer, `warum` Text, `vorschlaege` Liste von Texten (höchstens
   4). Normalisieren: Zeilenumbrüche und Steuerzeichen in allen Feldern zu einem Leerzeichen, Leerraum zusammenziehen,
   kürzen auf frage 300, warum 300, je Vorschlag 80 Zeichen. Fehlt der Kasten, sind es zwei, ist das JSON kaputt oder
   das Schema verletzt: `grund` „Fragen nicht lesbar“, Rohantwort bleibt sichtbar. `datei_inhalt` und
   `schaerfen_anzeige` liefern für Rückfragen-Belege **neu** `fragenliste` (Liste) und `fragen_grund`; das bestehende
   Feld `fragen` (Text bei „Erst klären“) bleibt unverändert.

S5 **Übernehmen.** Ein Rückfragen-Beleg legt keine Fassung an (wie „Erst klären“); `ergebnis` = „Fragen gestellt“ bzw.
   „Fragen nicht lesbar“. `_gruppenergebnis_uebernehmen` wird für „Rückfragen“ nicht aufgerufen.

S6 **Bearbeitete Fassung speichern.** Neue Eintragsaktion `fassung_bearbeitet` (`/api/prompt`):
   `{aktion, id, anfrage_id, von_fassung, von_stand, text}`; nur `herkunft` „ordner“. S6 legt immer eine **neue**
   Fassung an und überschreibt nichts; eine inzwischen geänderte oder fehlende Quelle ist deshalb kein Fehler, sondern
   wird als `quelle_geaendert: true` vermerkt (so geht kein Entwurf verloren, O5). Eine neue Methode
   `Eintrag.fassung_bearbeitet` erledigt unter `_SPERRE` (RLock) in einem Zug, fortsetzbar nach Abbruch:
   1. Herkunftsdatei lesen. Ist sie beschädigt (kein gültiges JSON/Schema): 409 „Die Herkunftsdatei des Eintrags ist
      beschädigt. Es wurde nichts gespeichert.“ – nie still überschreiben. Fehlt sie: leer.
   2. `fingerabdruck` = SHA-256 über `von_fassung`, `von_stand`, normalisierten `text`. Gibt es einen Herkunftseintrag
      mit dieser `anfrage_id`: anderer Fingerabdruck → 409; sonst fortsetzen und dessen Namen zurückgeben: Fassung
      `name` fehlt → mit diesem Text anhängen; Fassung vorhanden → ihr aktueller Stand muss `stand(normalisierter
      Text)` sein (wie die Kollisionsprüfung in `_gruppenergebnis_uebernehmen`), sonst 409 „Die gespeicherte Fassung
      wurde inzwischen geändert.“ ohne Änderung und ohne Folgeaktion; erst dann fehlenden `stand` ergänzen.
   3. Neu: `text_pruefen`; ist die Quelle vorhanden und ihr Text gleich `text`: 400 „Der Text ist unverändert.“ Namen
      bilden (unten), **zuerst** den Herkunftseintrag ohne `stand` schreiben (Reservierung, wie
      `_gruppenergebnis_uebernehmen` den Ergebnisnamen vorab reserviert), dann die Fassung anhängen (wie
      `fassung_neu`), dann `stand` der neuen Fassung in den Herkunftseintrag schreiben.
   - Name: `Bearbeitet TT.MM. · ` + Rest des Quellnamens nach dem ersten `TT.MM. · ` (bei „Schärfen 09.11. · Qwen 27B
     Q4 · Opus 5.5 · hoch“ → „Bearbeitet 10.11. · Qwen 27B Q4 · Opus 5.5 · hoch“), sonst `Bearbeitet TT.MM. ·
     <Quellname>`; auf 60 Zeichen gekürzt, eindeutig mit „ (2)“, „ (3)“ … wie bei den Ergebnisnamen.
   - Herkunftsdatei `herkunft.json` im Eintragsordner (atomar geschrieben, wie `_atomar`):
     `{"version": 1, "fassungen": {"<Name>": {"von_fassung", "von_stand", "quelle_geaendert", "quell_beleg",
     "anfrage_id", "fingerabdruck", "stand", "erstellt"}}}` (`stand` = Stand der angelegten Fassung).
     `quell_beleg` = `quell_beleg` der Quelle, falls die Quelle selbst in der Herkunftsdatei steht, sonst der neueste
     Beleg mit `ergebnis_fassung` = Quelle, sonst `null`.
   - Der Eintragscache von `lesen` berücksichtigt auch Größe und Änderungszeit von `herkunft.json` (eine Wiederaufnahme
     kann nur diese Datei ändern).
   - `lesen` liefert je Fassung `herkunft` (Objekt oder fehlt) und `herkunft_gueltig` = gespeicherter `stand` gleich dem
     aktuellen Stand und `quelle_geaendert` falsch. Wird „Bearbeitet …“ später über den bestehenden Bearbeitungsdialog
     geändert, ist die Herkunft damit nicht mehr gültig (Fragen gelten nicht mehr; der `quell_beleg` für Einstellungen
     bleibt nutzbar). Ist die Herkunftsdatei beschädigt, zeigt `lesen` Fassungen ohne Herkunft und eine Warnung
     `herkunft_fehler` (Text) am Eintrag; geschrieben wird erst nach Prüfung durch Sascha.
   - Ein reservierter Eintrag ohne angelegte Fassung (Abbruch zwischen 3a und 3b) stört nicht: Er wird beim Wiederholen
     mit derselben `anfrage_id` fortgesetzt, sonst ignoriert; sein Name gilt bei der Namensvergabe als belegt.
   - Antwort wie die übrigen Eintragsaktionen: `self.lesen(eid)` plus `neue_fassung` (Name).

S7 **Liste.** Gruppenbelege in `auftragsgruppen` tragen weiter `aktion`, `fassung`, `fassung_stand`, `zielschluessel`,
   `schreibmodell_id`, `ergebnis_fassung`, `lauf_nr`, `zustand`; Rückfragen-Belege zusätzlich `fragen_anzahl` (Zahl
   oder fehlt, wenn nicht lesbar) und `fragen_hash` (SHA-256 der normalisierten Fragenliste, damit die Oberfläche
   Antwortentwürfe verwirft, wenn ein Beleg per Wiederholen neue Fragen bekommt). `auftragsgruppen` wird stabil
   sortiert: nach dem frühesten `erstellt` der Gruppe (Sekunden), dann nach Gruppen-ID. Grenze: Zwei Sendungen in
   derselben Sekunde stehen nach ID, nicht unbedingt nach Startzeit. Die Arbeitsfläche hängt davon nicht ab, weil sie
   nach eigener Sendung der gemerkten eigenen Gruppe folgt.

S8 **Grenzen.** Keine neuen Abhängigkeiten, keine neuen Zeitgeber, Logs ohne Fragen, Antworten oder Prompttexte.

## Oberfläche (werkstatt/web/prompts.js, werkstatt/web/style.css)

O1 **Platz.** Die Arbeitsfläche steht im Eintrag (`#p-inhalt`) direkt unter dem Kopf und ersetzt dort den Kasten
   „Zuletzt gestarteter Auftrag“; dessen Spaltenansicht lebt als „Nebeneinander vergleichen“ weiter. Alles darunter
   bleibt unverändert. Zwei Spalten, sobald die Arbeitsfläche selbst mindestens 860 px breit ist (Container-Abfrage,
   `container-type: inline-size`): `minmax(300px, 2fr) minmax(480px, 3fr)`, Abstand 16 px. Schmaler eine Spalte in der
   Reihenfolge Dein Prompt, Neuer Prompt, Fragen/Versionen; dort ist das rechte Textfeld höchstens 60vh hoch und
   scrollt innen. Nur vorhandene Farben, Klassen und Variablen; kein Querscrollen bei 375 px.

O2 **Links oben „Dein Prompt“.** Text von Fassung 1 (erste Fassung), höchstens 8 Zeilen mit „Ganz anzeigen“/„Weniger“,
   Knopf „Kopieren“. Nur lesen.

O3 **Links darunter Reiter „Fragen“ | „Versionen“** (Standard „Fragen“).
   Fragen, Zustände (es gilt die bewusst gewählte Fragen-Runde `P.af[eid].fragen`, wenn sie für die rechts gezeigte
   Fassung gilt, sonst die neueste, die gilt):
   - **leer**: „Klicke rechts auf „Prompt verbessern“. Dann stellt dir ein Modell bis zu fünf kurze Fragen zum neuen
     Prompt.“ Darunter „Fragen stellt:“ mit Auswahl eines Schreibmodells (D4, nur verfügbare wählbar).
   - **wartet/läuft**: `pLaufanzeige` (Text „Fragen werden gestellt …“ statt „das Modell arbeitet noch …“), „Abbrechen“.
   - **fertig, n ≥ 1**: Kopf „Verbessere deinen Prompt (x/n)“ (x = beantwortet), darunter leise „Fragen von
     <Schreibmodell> zu „<Bezugsfassung>““ und, wenn sie über eine Bearbeitet-Kette gilt, „– du hast den Text danach
     bearbeitet“. Je Frage
     eine Karte: Etikett „Kritisch“ / „Hohe Priorität“ / „Mittlere Priorität“ (vorhandene Farben: kritisch `--heiss`,
     hoch `--bernstein`, mittel `--leise`), Frage, „warum“ klein und leise, Vorschlagsknöpfe (Klick setzt den Vorschlag
     ins Antwortfeld; steht dort schon Text, wird er mit „; “ angehängt), Antwortfeld (zwei Zeilen, wächst, höchstens
     600 Zeichen), Knopf „Überspringen“/„Doch beantworten“ (übersprungene Karte blass, Antwort zählt nicht).
     Darunter „Weitere Wünsche (optional)“ (höchstens 2.000 Zeichen, wird `hinweise`), Schreibmodell-Auswahl (O7),
     Hauptknopf „Mit Antworten verbessern“, daneben „Ohne Antworten verbessern“.
   - **fertig, n = 0**: „Keine Rückfragen nötig – der Prompt ist aus Sicht von <Schreibmodell> klar.“, „Weitere
     Wünsche“, O7, Knopf „Jetzt verbessern“ (wie „Ohne Antworten“).
   - **nicht lesbar, Fehler, abgebrochen**: „Die Fragen ließen sich nicht lesen.“ bzw. Fehlermeldung bzw.
     „Abgebrochen.“, Rohantwort eingeklappt, Fragesteller-Auswahl, Knöpfe „Nochmal fragen“ und „Ohne Fragen verbessern“.
   - **veraltet** (es gibt eine Fragen-Runde zum Namen der gezeigten Fassung, aber mit anderem Stand): Hinweis „Die
     Fassung wurde seit den Fragen geändert.“, die alten Fragen samt Antworten eingeklappt zum Nachlesen, Knöpfe
     „Nochmal fragen“ und „Ohne Fragen verbessern“.
   Versionen: alle Fassungen des Eintrags, neueste zuerst, je Zeile Name und Marken „Dein Prompt“ (Fassung 1),
   „Bevorzugt“, „Wird gezeigt“, „Geändert“ (ungespeicherter Entwurf vorhanden); Knopf „Anzeigen“ (O4, bewusste Wahl).

O4 **Rechts „Neuer Prompt“ – Zustandsmodell.** Die Seite hält je Eintrag `P.af[eid] = { runde, ziel, lauf, fassung,
   fragen, bewusst, eigeneRunde }` (Runde = Gruppen-ID oder null; Ziel = `zielschluessel`; Lauf = Beleg-Datei;
   Fassung = Name, wenn keine Runde gewählt ist; Fragen = bewusst gewählter Fragen-Beleg oder null; `bewusst` = Sascha
   hat selbst gewählt; `eigeneRunde` = Gruppen-ID der letzten eigenen **Schärfen**-Sendung aus der Arbeitsfläche;
   Fragen-Sendungen setzen nur `fragen`).
   - **Vorgabe** (solange `bewusst` falsch):
     1. Nach eigener Sendung (`eigeneRunde` gesetzt): diese Runde.
     2. Sonst, wenn die bevorzugte Fassung nicht die erste Fassung ist: die bevorzugte Fassung – als Lauf ihrer Runde,
        wenn sie Ergebnis eines Gruppenbelegs ist (dann mit Reitern), sonst als Fassung ohne Runde.
     3. Sonst die neueste Schärfen-Runde (S7-Ordnung).
     4. Ohne Schärfen-Runde: Fassung 1.
     Innerhalb einer Runde: das Ziel, das die bevorzugte Fassung enthält, sonst das erste; darin der Lauf mit der
     bevorzugten Fassung, sonst der erste Lauf (nach `lauf_nr`) mit vorhandener Ergebnisfassung, sonst der erste Lauf.
     Sobald rechts ein fertiger Text steht, wechselt die Vorgabe nicht mehr von selbst – erst wieder nach einer
     eigenen neuen Runde.
   - **Bewusste Wahl** (Reiter, Ziel-Knopf, „Anzeigen“ in Versionen, „Basis anzeigen“) setzt `bewusst`; Neuladen und
     später fertige ältere Runden ändern sie nicht. Eine eigene neue Runde setzt `bewusst` zurück.
   - Über der Karte: Ziel-Knöpfe (bei mehreren Zielen der Runde) und Reiter je Lauf des Ziels (Kurzname des
     Schreibmodells, nach `lauf_nr`, mit kleinem Zustandswort „läuft“, „wartet“, „Fehler“, „ohne Ergebnis“, wenn nicht
     fertig). Ohne Runde kein Reiter, nur der Fassungsname.
   - Inhalt nach Zustand des gezeigten Laufs bzw. der Fassung:
     - **wartet/läuft**: Kopf mit `pLaufanzeige`; darunter „Verbessert wird: <Basisname>“ und der Basistext nur lesend,
       blass; Knöpfe „Abbrechen“ und (bei mehreren Läufen) „Nebeneinander vergleichen“.
     - **fertig mit vorhandener Ergebnisfassung** bzw. **Fassung ohne Runde**: bearbeitbares Textfeld (wächst,
       mindestens 12 Zeilen, Monospace wie `.p-text`); Kopf „Fertig · 29 s · 8.286 Token“ bzw. Fassungsname.
     - **fertig ohne Ergebnis** (keine gültige Fassung, Ergebnis fehlt), **Fehler**, **abgebrochen**: Meldung (`grund`
       bzw. Fehler), Rohantwort eingeklappt, „Neu senden“ und „Basis anzeigen“. „Neu senden“ ist eine bewusst neue
       Schärfen-Runde (neue `anfrage_id`, O6) mit Basis = Basisfassung des Laufs (aktueller Stand; fehlt sie, stehen statt
       beider Knöpfe nur die Meldung und der Hinweis auf „Versionen“ links), demselben Ziel, demselben Schreibmodell und den
       `hinweise`/`rueckfragen` aus den Eingaben des Laufs. Es ruft das Modell wirklich neu auf (anders als das
       vorhandene `wiederholen_beleg`, das eine gespeicherte Antwort nur neu auswertet). Das Wiederholen einzelner
       Warteschlangen-Einträge bleibt unverändert im Abschnitt „Warteschlange“ darunter.
     - **Sammlungseintrag**: Vorschlags- bzw. Fassungstext nur lesend (siehe Alte Daten).
   - Darunter eingeklappt „Was geändert wurde“ (Stichpunkte) und, falls vorhanden, „Beantwortete Fragen“ (die
     `rueckfragen` aus den Eingaben des Belegs).
   - Knöpfe bei bearbeitbarem Text: „Kopieren“ (kopiert den sichtbaren Text, ohne zu speichern), „Als bevorzugt“
     (bzw. Marke „Bevorzugt“), „Testen …“ (wie heute), bei mehreren Läufen „Nebeneinander vergleichen“, „Direkt
     verbessern“ und als Hauptknopf „Prompt verbessern“.

O5 **Entwürfe und Speichern.** Änderungen im rechten Textfeld leben im Speicher der Seite, nicht im DOM:
   `P.afEntwurf` Map `eid|fassung` → `{text, von_stand, anfrage_id}` (Marke „Geändert“, Knopf „Verwerfen“).
   Neuzeichnen, Reiter-, Ziel-, Versions- und Eintragswechsel lassen ihn stehen; zurück an derselben Fassung erscheint
   er wieder. Ist der aktuelle Stand der Fassung inzwischen ein anderer als `von_stand`, zeigt die Karte den Entwurf mit
   dem Hinweis „Diese Fassung wurde inzwischen geändert. Dein Entwurf ist erhalten.“ und den Knöpfen „Entwurf als
   neue Fassung speichern“ (S6 mit dem alten `von_stand`, vermerkt `quelle_geaendert`), „Aktuelle Fassung zeigen“
   (Umschalten, Entwurf bleibt) und „Verwerfen“. Jede Aktion, die den Text weiterverwendet – „Prompt verbessern“,
   „Direkt verbessern“, „Mit/Ohne Antworten verbessern“, „Jetzt verbessern“, „Neu senden“, „Testen …“, „Als
   bevorzugt“ –, speichert einen vorhandenen Entwurf zuerst per S6 (die `anfrage_id` des Entwurfs, bei Wiederholung
   dieselbe; neue `anfrage_id`, sobald der Text danach wieder geändert wird) und handelt dann mit der neuen Fassung
   als Basis bzw. Gegenstand. Während Speichern und Folgeaktion ist das Textfeld schreibgeschützt (Statuszeile
   „Wird gespeichert …“), damit keine Eingabe zwischen Speichern und Senden verloren geht. Nach dem Speichern zeigt
   die Karte die neue Fassung nur, wenn Sascha die Ansicht inzwischen nicht bewusst gewechselt hat; die Folgeaktion
   läuft in jedem Fall mit der gespeicherten Fassung. Scheitert das Speichern, bleibt der Entwurf stehen, die Meldung
   erscheint an der Karte und nichts wird gesendet.
   Antworten, Überspringen und „Weitere Wünsche“ leben ebenso im Speicher: `P.afAntworten` Map
   `eid|<Datei des Fragen-Belegs>|fragen_hash` → `{antworten: {i: text}, uebersprungen: Set, wuensche}` (neue Fragen im selben Beleg
   → neuer Schlüssel, alte Antworten werden nicht auf andere Fragen übertragen); „Weitere Wünsche“ ohne Fragen-Runde
   (n = 0, Direkt verbessern) unter `eid|fassung`. Der Schutz vor Neuladen bleibt `pGeschuetzt()` (Fokus in
   `#p-inhalt`); bewusste Navigation wird nicht blockiert, weil nichts verloren geht.

O6 **Senden aus der Arbeitsfläche.** Den Transport aus `pComposerSenden`/`pSendungsaktionenZeichnen`/
   `pSendungUnklar`/`pSendungStatus` als gemeinsamen Ablauf herauslösen, der einen eigenen Sendungszustand
   (`{daten, abgelehnt, unklar}`), eine Statuszeile, einen Aktionsbereich und einen Erfolgs-Rückruf übergeben bekommt.
   Der Composer nutzt ihn mit `P.sendung` und seinem bisherigen Verhalten (Leeren, Wechsel in die Bibliothek)
   unverändert; die Arbeitsfläche mit `P.afSendung` (eine zur Zeit, Knöpfe gesperrt, solange sie läuft oder unklar ist),
   eigener Statuszeile und eigenen Knöpfen („Status prüfen“, „Einreihung fortsetzen“, „Als neue Sendung senden“) in der
   Arbeitsfläche. Erfolg dort: kein Composer-Eingriff, kein Ansichtswechsel; Rückfragen → `fragen` = neuer Beleg,
   Reiter „Fragen“ mit Laufanzeige; Schärfen → `eigeneRunde` = neue Gruppe, `bewusst` = falsch, die rechte Seite
   folgt ihr. Hat Sascha zwischen Klick und Bestätigung bewusst Eintrag oder Ansicht gewechselt, werden nur
   `fragen`/`eigeneRunde` gemerkt; die gewählte Ansicht bleibt. Composer- und Arbeitsflächen-Sendung blockieren sich
   nicht gegenseitig.
   Anfragedaten (ohne `P.entwurf` zu berühren; Hilfsfunktion aus `pComposerAusBeleg` herausgelöst, die aus Eintrag,
   Quellbeleg und Basis die Daten baut – der Composer nutzt dieselbe Funktion):
   ```json
   {"aktion": "composer_vorschau | composer_senden", "anfrage_id": "<uuid>",
    "text": "<Text der Basisfassung>", "titel": "<Eintragstitel>", "ablage": "ordner",
    "basis": {"id": "<eid>", "fassung": "<Name>", "stand": "<Stand>"},
    "prompt_typ": "<Quellbeleg eingaben.typ.id | Eintrag | auto>", "modus": "<… | prompt>",
    "realismus": false, "schaerfen_aktion": "Rückfragen | Schärfen",
    "ziele": [{"zielprofil": "…", "eintrag": "… (nur lokal)", "testprofil": "… | null (nicht bei bild/video)",
               "variante": "… (falls vorhanden)"}],
    "schreibmodelle": ["<id>"], "hinweise": "<Weitere Wünsche | ''>",
    "materialien": ["<wie im Quellbeleg, siehe unten>"], "kontexte": [{"id": "…", "stand": "<aktuell>"}],
    "rueckfragen": [{"prioritaet": "kritisch", "frage": "<wie angezeigt>", "antwort": "…"}],
    "gesendet_staende": "<aus der Vorschau>"}
   ```
   Das Ziel kommt aus dem `zielschluessel` des Quellbelegs, übersetzt wie heute in `pComposerAusBeleg` (gemeinsame
   Hilfsfunktion). Materialien wie im Quellbeleg (Datei, Text, Antwort – der Server liest sie wie heute neu).
   Kontexte mit ihrem **aktuellen** Stand (vorher je ID `kontext_lesen`). Fehlt ein Kontext oder ein Material, ist das
   Ziel unbekannt, oder lehnt die Vorschau ab: Meldung in der Arbeitsfläche und Knopf „Im Composer öffnen“ – der
   Composer bekommt Basis und Einstellungen wie bei `pComposerVerfeinern`, „Weitere Wünsche“ als Hinweise (je höchstens
   2.000 Zeichen, wie heute) und die Antworten **getrennt** als `P.entwurf.rueckfragen` (O8). Kein Zustand ohne Ausweg.
   - „Prompt verbessern“: Aktion „Rückfragen“, `schreibmodelle` = [Fragesteller].
   - „Direkt verbessern“, „Ohne Antworten verbessern“, „Jetzt verbessern“: Aktion „Schärfen“ ohne `rueckfragen`,
     `schreibmodelle` = Auswahl O7.
   - „Mit Antworten verbessern“: Aktion „Schärfen“, `rueckfragen` = beantwortete, nicht übersprungene Fragen mit
     Priorität und Fragetext genau wie angezeigt (ohne beantwortete Frage wirkt der Knopf wie „Ohne Antworten“),
     Auswahl O7.
   „Prompt verbessern“ ist gesperrt, solange für die gezeigte Fassung eine Fragen-Runde wartet oder läuft.

O7 **Schreibmodell-Auswahl** in den Fragen und bei „Direkt verbessern“ (kleines Menü am Knopf) wie im Composer: Menü
   mit Kontrollkästchen, 1–3, nicht verfügbare nicht neu wählbar, aber bereits gewählte immer abwählbar (bestehende
   Regel), gemeinsam gemerkte Auswahl `werkstatt.prompt-schreibmodelle`. Das Menü schließt beim Klick daneben
   (`pMenuesSchliessen` auf alle `details.p-auswahl` im Reiter ausweiten). Ist kein Schreibmodell verfügbar: Hinweis
   „Kein Schreibmodell verfügbar“ und „Im Composer öffnen“.

O8 **Bestehende Ansichten.** `pSchaerfenErgebnis` und die Schärfen-Liste behandeln „Rückfragen“ ausdrücklich: Zeile
   „Rückfragen · Fertig · 3 Fragen“ (bzw. Zustand/Fehler wie heute), Inhalt = Fragenliste nur lesend mit Knopf „In der
   Arbeitsfläche öffnen“ (zeigt die Bezugsfassung rechts, setzt `P.af[eid].fragen` auf genau diesen Beleg, Reiter
   „Fragen“); kein „Keine gültige neue Fassung“, kein „Testen …“. Schärfen-Belege mit `rueckfragen` zeigen
   „Beantwortete Fragen“ eingeklappt.
   **Composer:** `P.entwurf.rueckfragen` (Liste wie S3, sonst fehlt das Feld) erscheint als eingeklappter Kasten
   „Antworten auf Rückfragen (n)“ (nur lesend) mit Knopf „Entfernen“; `pComposerDaten` schickt das Feld nur mit Basis
   und Aktion „Schärfen“ und lässt es sonst weg. Jede Änderung der Basis (`id`, `fassung` oder `stand`, also auch
   `pComposerBasis` über „Im Composer schärfen“), das Entfernen der Basis und ein Aktionswechsel leeren es; erst danach
   setzen ausdrücklich vorgesehene Übernahmen ihre eigene Momentaufnahme: `pComposerNochmal` übernimmt
   `b.eingaben.rueckfragen` (verlustfreie Wiederholung), „Im Composer öffnen“ aus der Arbeitsfläche die aktuellen
   Antworten. `pComposerVerfeinern` übernimmt keine (neue Basis, neue Fragen). Nach erfolgreicher Composer-Sendung
   wird das Feld mit dem übrigen Entwurf geleert.

O9 **Texte** auf Deutsch wie oben; Knöpfe ohne „bitte“. **Barrierefreiheit:** Reiter `role="tablist"`/`tab` mit
   `aria-selected`, Fragekarten als Liste, Antwortfelder mit der Frage als Beschriftung, Laufzeilen `role="status"`.

## Alte Daten

Belege ohne `rueckfragen` und alle bestehenden Aktionen bauen denselben Auftrag mit derselben Prüfsumme;
teilweise angelegte alte Sendungen behalten ihren Fingerabdruck. Einträge ohne Composer-Runde zeigen die Arbeitsfläche
mit der bevorzugten Fassung rechts; ohne bekanntes Ziel führt „Prompt verbessern“ zu „Im Composer öffnen“. Einträge
ohne `herkunft.json` funktionieren wie bisher. Sammlungseinträge (schreibgeschützt) zeigen die Arbeitsfläche nur
lesend: rechts ohne Bearbeiten, ohne „Prompt verbessern“, ohne „Als bevorzugt“ – wie heute ohne schreibende Knöpfe.

## Nicht im Umfang

Daumen hoch/runter, „Folge-Prompt“, „Was kann ich als Nächstes tun?“, Kontext- oder Material-Bearbeitung in der
Arbeitsfläche (bleibt im Composer), Sekundenuhr, Streaming, Änderung der Zielregeln oder der Regeldatei, Diktat,
mehrere Fragesteller gleichzeitig, Rückfragen im Schärfen-Dialog oder Testdialog, Umbau der Abschnitte unter der
Arbeitsfläche (Einklappen o. Ä. erst nach Saschas Probe).

## Nachweis

- Python (`test_auswertung_prompts.py`, `test_prompts.py`):
  - S1: Rückfragen-Vertrag im Auftrag, ohne Typ-Absatz; Ablehnung ohne Basis, mit zwei Zielen, mit zwei
    Schreibmodellen, über `schaerfen_vorschau` und `schaerfen`.
  - S3: Abschnitt im Auftrag (mehrzeilige Antwort eingerückt, `\r\n` normalisiert); Ablehnung ohne Basis, bei
    anderer Aktion, mit 0 oder 6 Einträgen, falscher Priorität, leerer/zu langer Frage oder Antwort, Zeilenumbruch in
    der Frage, Steuerzeichen in der Antwort; gespeicherter Auftrag mit Antworten bleibt lesbar und baut gleich, auch
    wenn der zugehörige Fragen-Beleg gelöscht oder neu ausgeführt wurde; Fingerabdruck mit und ohne Feld.
  - S4: gültig, Kennung leer, kein Kasten, zwei Kästen, kaputtes JSON, falsche Priorität, 0 Fragen, mehr als 5,
    Kürzungen, Zeilenumbrüche normalisiert; `fragenliste` neben unverändertem `fragen` bei „Erst klären“.
  - S5: keine Fassung. S6: Namen (Schärfen-Quelle, andere Quelle, 60 Zeichen, Eindeutigkeit, reservierter Name
    belegt), geänderte/fehlende Quelle → angelegt mit `quelle_geaendert`, 400 bei unverändertem Text, Wiederholung mit
    gleicher `anfrage_id` → gleiche Fassung, mit anderem Text → 409, Abbruch nach Reservierung bzw. nach Anhängen →
    Wiederholung setzt fort ohne zweite Fassung, Abbruch → Ergebnisfassung inzwischen geändert → gleiche Anfrage
    erneut → 409 ohne Änderung, Cache sieht eine nur in `herkunft.json` ergänzte Herkunft, zwei Threads gleichzeitig →
    zwei verschiedene Namen, geerbter
    `quell_beleg`, `herkunft_gueltig` falsch nach späterer Änderung der Bearbeitet-Fassung, beschädigte Herkunftsdatei →
    409 ohne Schreiben und `herkunft_fehler` in `lesen`.
  - S7: Sortierung. Alte Daten: gleicher Auftrag und Hash für feste Altaufträge (bau_version 1 und 2), alte
    Teilsendung ohne neue Felder lässt sich fortsetzen.
- JS-Bedienungstest (neue `werkstatt/tests/prompts_arbeitsflaeche_bedienung.js`, in `test_prompts.py` eingebunden):
  Vorgabe-Auswahl (eigene Runde, bevorzugte Bearbeitet-Fassung bzw. bevorzugtes Ergebnis einer älteren Runde vor der
  neuesten Runde, erster mit Ergebnis, kein Wechsel nach fertigem Text, ältere Runde fertig ändert nichts),
  Reiter/Ziel-Knöpfe, alle Laufzustände rechts (läuft, Teilfehler A scheitert/B liefert, ohne Ergebnis, abgebrochen,
  Sammlung) samt „Neu senden“ mit Hinweisen und Antworten des Laufs, Entwurf überlebt Neuzeichnen und Wechsel,
  veralteter Entwurf nach fremder Änderung (Hinweis, speichern mit altem Stand), Textfeld gesperrt während des
  Speicherns, verspätete Speicherantwort nach bewusstem Ansichtswechsel ändert die Ansicht nicht, „Prompt verbessern“
  speichert zuerst (S6) und sendet die Fragen-Runde mit den Feldern aus O6, **Fragen beantworten → rechts ändern →
  „Mit Antworten verbessern“** und **… → „Als bevorzugt“ → erneut ändern → „Mit Antworten verbessern“** (Fragen
  gelten über die Kette weiter, gesendet werden die angezeigten Fragetexte), neue Fragen per Wiederholen
  (`fragen_hash`) übernehmen keine alten Antworten, „In der Arbeitsfläche öffnen“ zeigt genau den angeklickten
  Fragen-Beleg, „Im Composer öffnen“ mit 5 langen Antworten und 2.000 Zeichen Wünschen (Antworten getrennt, keine
  Ablehnung), „Nochmal“ eines Belegs mit Antworten schickt sie wieder mit, **Antworten aus Eintrag A im Composer →
  „Im Composer schärfen“ für Eintrag B → Senden ohne Antworten**, Fragen-Sendung ändert die rechte Seite nicht,
  Sendebestätigung nach bewusstem Wechsel ändert die Ansicht nicht, Composer-Entwurf bleibt dabei unverändert, gleichzeitige
  Composer-Sendung stört nicht, verlorene Antwort → „Status prüfen“, Fragen-Zustände (läuft, fertig, 0 Fragen, nicht
  lesbar, veraltet), Vorschlag übernehmen, Überspringen, Zähler x/n, nur beantwortete Fragen gesendet, Antworten und
  „Weitere Wünsche“ überleben Neuzeichnen und eine verzögerte Ladeantwort, Versionen „Anzeigen“, „Im Composer öffnen“
  bei fehlendem Ziel und bei Kontext-Konflikt, gemeinsame Schreibmodell-Auswahl, gewähltes nicht verfügbares Modell
  abwählbar, Rückfragen-Beleg in der Schärfen-Liste.
- Volle Werkstatt-Suite grün. Abnahme durch Claude im Harness auf 127.0.0.1:3897 (Fake-Anbieter), danach ein echter
  Lauf auf 3895 nur auf Saschas Wort.
