# Spec: Mehrere Schreibmodelle gleichzeitig im Composer (Reiter Prompts)

Stand 08.11.2026. Auftrag Sascha: „Cool wäre wenn ich auch gleichzeitig 2 Fassungen erzeugen könnte mit Claude und
OpenAI, dann suche ich mir den Prompt, der mir besser gefällt, und den ich eventuell dann noch wieder mit einem anderen
Modell verfeinern kann“ → „Ja, planen“. Basis: `main` bei d82558b. Werkstatt `werkstatt\`, Port 3895.

## Ziel

Im Composer („Neuer Prompt“) lassen sich mehrere Schreibmodelle auf einmal wählen, z. B. „Claude · Opus 5.5 · hoch“
und „Codex · GPT-6.1-Sol · sehr hoch“. Ein Senden erzeugt je Zielmodell **und** Schreibmodell einen eigenen
Schärfen-Lauf. Die Ergebnisse stehen je Zielmodell nebeneinander. Sascha wählt die bessere Fassung („Als bevorzugt“)
und schickt sie mit einem Klick zurück in den Composer, um sie – auch mit einem anderen Schreibmodell – weiter zu
verfeinern. Mit einem einzigen Schreibmodell verhält sich alles wie heute.

## Ist-Stand (wo es sitzt)

- `werkstatt\prompts.py`
  - `composer_vorschau` (~Z. 897): prüft Eingaben, löst **ein** Profil aus `daten['schreibmodell']` auf
    (`prompt_verfuegbar(p, frisch=True)`, `kontext_geladen`), baut je Ziel `schaerfen_bauen(f, e)` und prüft
    `kontext_pruefen(auftrag, kontext)` mit dem Kontext dieses einen Schreibmodells. Rückgabe: `schreibmodell`, `ziele`,
    `gesendet_staende` (je `zielschluessel`). Die Eingaben `e` (und damit Auftragstext und `gesendet_stand`) hängen
    nicht vom Schreibmodell ab.
  - `_composer_fingerabdruck` (~Z. 1015): erlaubte Schlüssel, SHA über die Eingabe ohne `aktion`, `anfrage_id`,
    `gesendet_staende`.
  - `composer_senden` (~Z. 1024): Sendungsdatei `Prompts\_Auftraege\<uuid>.json` mit
    `ziele: [{zielschluessel, beleg, auftrags_id, eingereiht}]`; Wiederfinden von Belegen nach Absturz über den
    Belegkopf `auftragsgruppe` + `zielschluessel`; „Mehrere Belege für dasselbe Ziel“ → `Konflikt`. Kopf je Beleg
    mit `auswerter/anbieter/modell/kontext/…` des einen Schreibmodells.
  - `composer_status` (~Z. 1130): je Ziel Zustand aus Warteschlange bzw. Kopf.
  - `_gruppenergebnis_uebernehmen` (~Z. 420): Ergebnis wird Fassung mit Namen
    `<Aktion> <TT.MM.> · <Zielmodell>` (≤ 60 Zeichen, `name_pruefen`); der Name wird vor dem Anhängen als
    `ergebnis_fassung` im Belegkopf reserviert.
  - `auftrag_aus_beleg` (~Z. 1555): findet das Profil über Name + Anbieter + Modell + Denkstufe aus dem Kopf.
  - Die Liste (`lesen`/`_belege`) gibt den ganzen Belegkopf weiter; `auftragsgruppen` fasst Belege je Gruppe zusammen.
- `werkstatt\auswertung.py`: zwei Cloud-Arbeiter (`cloud_parallel` 2) – Claude und Codex laufen also gleichzeitig.
- `werkstatt\web\prompts.js`
  - Composer-Aufbau `pComposerZeigen` (~Z. 623), Schreibmodell als `select#p-schreibmodell` (~Z. 648, 692),
    Laden in `pOptionenLaden` (~Z. 739), Statuszeile `pComposerZusammenfassung` (~Z. 830),
    `pProfilProblemeZeichnen` (~Z. 841), Senden `pComposerSenden` (~Z. 865), Merken `pAuswahlMerken` (~Z. 580,
    Schlüssel `werkstatt.prompt-schreibmodell`).
  - Ergebnisgruppe `pGruppeZeichnen` (~Z. 969): je Beleg eine Karte, Ergebnis über `pSchaerfenErgebnis` (~Z. 323,
    Original | Neue Fassung, Knöpfe Kopieren/Testen/Nochmal).
  - Verfeinern heute: „Als bevorzugt“ an der Fassungskarte (~Z. 173) und „Im Composer schärfen“ → `pComposerBasis`
    (~Z. 930, Basis `{id, fassung, stand}`, Text schreibgeschützt, Änderungen über Hinweise); `pComposerNochmal`
    (~Z. 944) setzt das Schreibmodell über `b.auswerter`.
- Tests: `werkstatt\tests\test_auswertung_prompts.py` (Klasse `ComposerLaeufe`, ~Z. 827), Bedienungstests
  `werkstatt\tests\prompts_composer_bedienung.js` u. a. über `dom_nachbau.js`.

## Entscheidungen (Vorschlag; Sascha bestätigt vor dem Bau)

- **E1 Anzahl:** höchstens **drei** Schreibmodelle je Sendung. Läufe = Zielmodelle × Schreibmodelle (heute höchstens
  4 Ziele → bis 12 Läufe). Keine weitere Laufgrenze; die Statuszeile nennt die Zahl vorher.
- **E2 Vorgabe:** gemerkt wird die zuletzt gewählte Liste. Ohne gemerkte Wahl gilt die Vorgabe von heute (ein
  verfügbares Claude-/Codex-Profil).
- **E3 Fassungsname:** übernommene Ergebnisse nennen künftig auch das Schreibmodell
  (`Schärfen 08.11. · Qwen 27B Q4 · Opus 5.5 · hoch`), auch bei nur einem Schreibmodell – so bleibt in der
  Fassungsliste immer sichtbar, wer sie geschrieben hat. Bereits reservierte Namen bleiben.
- **E4 Verfeinern:** „Im Composer verfeinern“ ändert die bevorzugte Fassung nicht; „Als bevorzugt“ ist ein eigener
  Knopf daneben.

## Server (`werkstatt\prompts.py`)

1. **Eingabe.** Neu `schreibmodelle: ["<profil-id>", …]` – Liste mit 1–3 verschiedenen IDs, Reihenfolge wie
   angezeigt. Die alte Form `schreibmodell: "<id>"` bleibt erlaubt und gilt als Liste mit einem Eintrag. Beide
   zugleich → `ValueError('Bitte nur eine Schreibmodell-Angabe senden.')`. Leer → `'Bitte ein Schreibmodell
   wählen.'`, doppelt → `'Ein Schreibmodell wurde mehrfach ausgewählt.'`, mehr als drei → `'Höchstens drei
   Schreibmodelle auswählen.'`, Nicht-String-Einträge → `'Ungültige Schreibmodell-Auswahl.'`.
   `_composer_fingerabdruck` erlaubt zusätzlich `schreibmodelle`; die Eingabe wird für den Fingerabdruck **nicht**
   umgeschrieben (eine vor dem Update angefangene Sendung mit `schreibmodell` behält ihren Fingerabdruck).
2. **`composer_vorschau`.** Jedes Profil auflösen und frisch prüfen wie heute. Fehlt eines oder ist es nicht
   verfügbar, nennt die Meldung das Modell (`'<Name>: <Grund>'`, bei `PromptFehler` dieselbe Art wie heute). Pro
   Paar (Ziel, Schreibmodell) `kontext_pruefen` mit dem Kontext dieses Schreibmodells; ist der Auftrag für eines zu
   lang, nennt der Fehler dieses Modell. Rückgabe: `schreibmodelle` (Liste der aufgelösten Profile im Format des
   heutigen `schreibmodell`) **statt** `schreibmodell`; `ziele` wie heute, aber ohne `geschaetzt`/`reserve`; neu
   `laeufe: [{zielschluessel, schreibmodell_id, geschaetzt, reserve}]` (Ziel außen, Schreibmodell innen).
   `gesendet_staende` bleibt je `zielschluessel`. Sollte der Builder doch eine Abhängigkeit des Auftragstexts vom
   Schreibmodell finden: Schlüssel `zielschluessel + '|' + schreibmodell_id` und im Bericht nennen.
   **Einzelweg anpassen:** `schaerfen_vorschau` (~Z. 1468) ruft für erweiterte Eingaben `composer_vorschau` auf und
   liest `v['schreibmodell']`, `z['geschaetzt']`, `z['reserve']`. Auf `v['schreibmodelle'][0]` und `v['laeufe'][0]`
   umstellen; sein Antwortformat (`schreibmodell` mit `verfuegbar/grund/geschaetzt/reserve`) bleibt genau gleich.
3. **Sendungsdatei.** Je Lauf ein Eintrag `{zielschluessel, schreibmodell_id, beleg, auftrags_id, eingereiht}`,
   angelegt in der Reihenfolge von `laeufe`. Alte Dateien ohne `schreibmodell_id`: Beim Lesen bekommt jeder Eintrag die
   ID des einzigen Schreibmodells der Eingabe (alte Sendungen hatten genau eines; der unveränderte Fingerabdruck
   sichert, dass die Eingabe dazu passt). Diese Ergänzung wird geschrieben, **bevor** ein fehlender Beleg angelegt
   wird.
4. **Belegkopf.** Neue Felder `schreibmodell_id` (Profil-ID) und `lauf_nr` (Position in `laeufe`, ab 0);
   `auswerter/anbieter/modell/kontext/kontext_quelle/verarbeitung/denkstufe` vom jeweiligen Schreibmodell.
   **Wiederfinden nach Absturz über die Laufkennung:** Ein Beleg gehört zu einem Sendungseintrag, wenn
   `auftragsgruppe` = Sendung und `auftrags_id` = Eintrag (jeder Composer-Beleg trägt `auftrags_id`; geprüft am
   08.11.: alle 5 vorhandenen Gruppenbelege). Danach prüfen: `zielschluessel` gleich, `schreibmodell_id` gleich, sofern
   der Kopf eines hat – sonst `Konflikt('Ein Gruppenbeleg passt nicht zu seinem Lauf. Bitte die Gruppe prüfen.')`.
   Mehr als ein Treffer → `Konflikt('Mehrere Belege für denselben Lauf gefunden. Bitte die Gruppe prüfen.')`. Damit
   bleibt auch eine zweite Unterbrechung während einer Altfortsetzung eindeutig.
5. **Einreihen** unverändert je Lauf (Reihenfolge `laeufe`), danach `vollstaendig` wie heute. Bekannte, schon
   bestehende Grenze (nicht in diesem Umfang): Fehlt nach einem Absturz noch ein Beleg, rechnet die Fortsetzung die
   Vorschau neu; haben sich Material, Regeln, Kontextbausteine oder die Verfügbarkeit eines Schreibmodells geändert,
   bricht sie mit der bisherigen Meldung ab. Für diesen Fall bietet die Oberfläche „Als neue Sendung senden“
   (Oberfläche, Punkt 5a).
6. **`composer_status`** gibt je Lauf zusätzlich `schreibmodell_id` und `auswerter` zurück (aus dem Kopf, sonst aus
   der Sendung bzw. leer).
7. **Ergebnisname** (`_gruppenergebnis_uebernehmen`, nur wenn `ergebnis_fassung` noch fehlt):
   `<Aktion> <TT.MM.> · <Ziel> · <Schreibmodell kurz>`, insgesamt ≤ 60 Zeichen. *Schreibmodell kurz* = Profilname ohne
   sein erstes Segment, wenn er mindestens zwei durch `' · '` getrennte Segmente hat (`Claude · Opus 5.5 · hoch` →
   `Opus 5.5 · hoch`, `Codex · GPT-6.1-Sol · sehr hoch` → `GPT-6.1-Sol · sehr hoch`), sonst der ganze Name; höchstens
   24 Zeichen. Gekürzt wird zuerst der Zielteil, dessen erstes Segment (bis zum ersten `' · '`) bleibt erhalten. Die
   Eindeutigkeit über die vorhandene `(n)`-Logik bleibt; ergeben zwei Profile denselben Kurznamen, reicht sie aus –
   welches Modell schrieb, steht ohnehin auf der Ergebniskarte und im Beleg. Steht `ergebnis_fassung` schon im Kopf,
   bleibt der Name.
8. Der alte Einzelweg (`schaerfen_vorschau`/`schaerfen`, Dialog „Schärfen ▾“) bleibt unverändert bei einem
   Schreibmodell.

## Oberfläche (`werkstatt\web\prompts.js`, `style.css`)

Oberflächentexte genau so übernehmen. Keine neuen Farben (Werkstatt-Farben nur mit Sascha); vorhandene Klassen und
Variablen nutzen. Keine Zeitgeber oder periodischen Neuladungen ohne Vorgabe.

1. **Auswahl.** `select#p-schreibmodell` wird ein Ausklappmenü wie „Prompt-Typ“ (`details.p-auswahl`,
   id `p-schreibmenue`, Summary-id `p-schreibname`) mit einem Kontrollkästchen je Profil (`aria-label` = Profilname).
   Nicht verfügbare, **nicht gewählte** Profile sind deaktiviert und tragen ihren Grund (`pBeschriftung` wie heute);
   ein gewähltes, inzwischen nicht verfügbares Profil bleibt abwählbar und trägt ebenfalls den Grund. Summary:
   `Schreibmodell: <Name>` bzw. `Schreibmodelle: <Name> + <Name>` (Namen über `pBeschriftung(p.name, p.zugang_text)`
   wie heute). Sind drei gewählt, sind die übrigen Kästchen gesperrt mit `title` „Höchstens drei Schreibmodelle“. Das
   letzte gewählte lässt sich nicht abwählen. Escape schließt das Menü wie beim Typmenü (vorhandener Handler).
   `P.entwurf.schreibmodelle` (Liste) ersetzt `P.entwurf.schreibmodell`; gesendet wird nur `schreibmodelle`.
2. **Merken.** `localStorage` `werkstatt.prompt-schreibmodelle` (JSON-Liste); ohne ihn der alte Schlüssel
   `werkstatt.prompt-schreibmodell` als Liste mit einem Eintrag. Nur beim **ersten** Laden der Optionen nach dem
   Seitenaufruf werden unbekannte oder nicht verfügbare IDs der gemerkten Liste still entfernt; bleibt keine, gilt die
   heutige Vorgabe. Beim späteren Neuladen der Optionen (z. B. nach „Modelle verwalten …“) bleibt die Auswahl des
   laufenden Entwurfs stehen; gelöschte Profile fallen heraus, nicht verfügbare bleiben sichtbar gewählt und sperren
   Senden (Punkt 5). Fehler der Browserablage stören nicht (wie heute).
3. **Texte.** Unter der Zielauswahl: „Für jedes angekreuzte Modell entsteht eine eigene Fassung. Jedes Schreibmodell
   formuliert eine eigene.“ Unter dem Fuß bei einem Schreibmodell wie heute „Dieses Modell überarbeitet deinen
   Prompt.“, bei mehreren „Jedes gewählte Modell schreibt eine eigene Fassung.“
4. **Statuszeile.** Ein Schreibmodell: wie heute. Mehrere: `<n> Zielmodell(e) × <m> Schreibmodelle · <n·m>
   Schärfen-Läufe` (Einzahl/Mehrzahl wie heute). Material-Hinweis nennt alle gewählten Cloud-Schreibmodelle:
   „Ausgewähltes Material und Kontext werden an <A> und <B> mitgesendet.“ `pProfilProblemeZeichnen` zählt alle
   gewählten Schreibmodelle als gewählt.
5. **Senden** ist gesperrt, solange ein gewähltes Schreibmodell nicht verfügbar ist; die Statuszeile nennt es
   („<Name> ist gerade nicht verfügbar.“). Ist keines gewählt: „Bitte ein Schreibmodell wählen.“ Strg+Enter wie heute.
   **Jede** Stelle, die die Auswahl setzt (Laden, Neuladen der Optionen, „Nochmal …“, „Im Composer verfeinern“),
   übernimmt nur IDs, die es unter den aktuellen Optionen gibt.
   5a. **Neu senden nach gescheiterter Fortsetzung:** Hat der Server eine Fortsetzung („Einreihung fortsetzen“ oder
   das erste Senden) mit einer Fehlermeldung **beantwortet** (Antwort erhalten, Status 4xx/5xx – nicht bei fehlender
   Antwort), zeigt `#p-sendungsaktionen` neben „Einreihung fortsetzen“ den Knopf „Als neue Sendung senden“. Er
   verwirft nur `P.sendung` (der Entwurf bleibt), vergibt eine neue `anfrage_id` und sendet wie beim ersten Mal. Ein
   kurzer Hinweis darüber: „Bereits angelegte Läufe der alten Sendung stehen unter ‚Schärfen‘ des Eintrags.“ Bei
   bloßem Antwortverlust bleibt es bei „Status prüfen“ wie heute.
6. **Auftragsvorschau** je Ziel wie heute, darunter „Geht an: <A>, <B>“.
7. **Ergebnisgruppe** (`pGruppeZeichnen`): Belege der Gruppe nach `lauf_nr` ordnen und nach `zielschluessel`
   zusammenfassen (Ziel in der Reihenfolge seines kleinsten `lauf_nr`); Belege ohne `lauf_nr` (alt) in der heutigen
   Reihenfolge dahinter. Je Ziel ein Abschnitt mit Überschrift Zielmodell. Inhalt und Knöpfe eines Ergebnisses
   erzeugt **eine** gemeinsame Funktion (aus `pSchaerfenErgebnis` heraus erweitert: neue Platzhalter, erkannter
   Prompt-Typ, Warnung, Fragen bei „Erst klären“); Einzel- und Vergleichsansicht unterscheiden sich nur in der Anordnung.
   - **Ein Ergebnis für dieses Ziel:** Anordnung wie heute (Original | Neue Fassung), mit den neuen Knöpfen.
   - **Mehrere Ergebnisse:** Original einmal oben, eingeklappt (`details`, Summary „Original anzeigen“). Darunter je
     Schreibmodell eine Spalte (CSS-Grid `repeat(auto-fit, minmax(320px, 1fr))`, auf schmalen Fenstern
     untereinander). Spaltenkopf: Schreibmodell (`auswerter`), Zustand wie heute, Dauer und Token, falls im Kopf.
     Inhalt: neue Fassung (`pre.p-text`), „Was geändert wurde“ eingeklappt (Stichpunkte), Warnung und Rohantwort bei
     ungültigem Ergebnis wie heute, „Erst klären“ zeigt die Fragen.
   - **Knöpfe je Spalte** (je nach Zustand): „Neue Fassung kopieren“; „Testen …“ (wie heute); **„Als bevorzugt“** nur
     wenn `ergebnis_fassung` zu einer Fassung des Eintrags gehört und der Eintrag bearbeitbar ist – ruft die
     vorhandene Aktion `bevorzugt` mit `kopf_stand` und lädt neu; ist sie schon bevorzugt, steht statt des Knopfs
     „Bevorzugt“; **„Im Composer verfeinern“** nur mit vorhandener Ergebnisfassung (Punkt 8); „Nochmal …“ wie
     heute; Abbrechen/Wiederholen je Lauf wie heute. In der Liste „Schärfen“ des Eintrags (die dieselbe Funktion
     nutzt) erscheinen „Als bevorzugt“ und „Im Composer verfeinern“ unter denselben Bedingungen.
   - **Nachträglich bearbeitete Ergebnisfassung:** Der Server liefert in der Liste je Schärfen-Beleg mit
     `ergebnis_fassung` zusätzlich `ergebnis_geaendert` (Stand des übernommenen Kastentexts ≠ aktueller Stand der
     Fassung dieses Namens; fehlt die Fassung, `ergebnis_fehlt`). Die Karte zeigt dann „Die übernommene Fassung
     „<Name>“ wurde seitdem bearbeitet. Die Knöpfe verwenden ihren aktuellen Stand.“; „Als bevorzugt“ und „Im Composer
     verfeinern“ arbeiten mit der Fassung, wie sie jetzt ist. Fehlt sie, entfallen beide Knöpfe.
   - **Aufgeklappt bleibt aufgeklappt:** Die neuen `details` tragen stabile `data-p-ansicht`-Schlüssel
     (`["gruppe", <gruppe>, <zielschluessel>, "original"]`, `[<beleg>, "aenderungen"]`). `pWaehlen` stellt den
     Öffnungszustand auch für die Ergebnisgruppe wieder her, also **nach** `pGruppeZeichnen`.
8. **„Im Composer verfeinern“** setzt den Entwurf vollständig neu, statt Reste des alten Entwurfs zu behalten: Basis
   = Ergebnisfassung `{id, fassung, stand}` (Text schreibgeschützt, Titel und Ablage vom Eintrag), Prompt-Typ, Modus,
   Realismus, Materialien und Kontexte aus `eingaben` des Belegs (wie `pComposerNochmal`), Hinweise leer, Aktion
   „Schärfen“, Ziele = genau dieses Ziel (Zielschlüssel zerlegen wie in `pComposerNochmal`, Testprofil übernehmen),
   Schreibmodelle = die gemerkte Auswahl. Typname, Modus-Knöpfe, Ziele und Chips neu zeichnen; „Weitere Angaben“
   aufklappen, dann Fokus in „Hinweise“.
9. **`pComposerNochmal`** setzt `schreibmodelle = [<Profil-ID>]`: die `schreibmodell_id` aus dem Kopf, wenn es sie
   unter den aktuellen Optionen gibt; sonst das Profil mit gleichem Namen, Anbieter, Modell und Denkstufe (wie
   `auftrag_aus_beleg`); sonst leere Auswahl mit Statuszeile „Das Schreibmodell dieses Laufs gibt es nicht mehr. Bitte
   neu wählen.“ Den Composer-Weg nur nehmen, wenn der Beleg `auftragsgruppe` **und** `zielschluessel` hat;
   sonst (Belege aus dem Einzelweg, auch mit `bau_version`) den bisherigen Dialog `pSchaerfendialog` öffnen – heute
   bricht `pComposerNochmal` dort mit einem `TypeError` ab.

## Nicht im Umfang

- Zwei Fassungen automatisch mischen oder bewerten lassen.
- Der Einzel-Dialog „Schärfen ▾“ und der Testdialog bleiben bei einem Modell.
- Testprofile und lokale Läufe für Qwen 27B und Flash-Next.
- `werkstatt\config.json`, die Regeldatei `werkstatt-profile.json` und Profile auf der Platte bleiben unverändert.

## Nachweis

Neue und angepasste Tests; bestehende Tests bleiben grün. Anpassen nur, wo sie `v['schreibmodell']` oder
`geschaetzt/reserve` des Composers lesen, die Sendungsfelder genau prüfen, `select#p-schreibmodell` bedienen oder den
Fassungsnamen genau prüfen – jede Anpassung im Bericht nennen. Eine neue JS-Datei wird in
`werkstatt\tests\test_prompts.py` wie die vorhandenen (`subprocess.run([node, 'werkstatt/tests/…'])`, Node Pflicht)
eingebunden.

Python (`ComposerLaeufe` o. neue Klasse):
- Zwei Schreibmodelle × drei Ziele → 6 Belege, 6 Aufträge, gleiche `auftragsgruppe`, je Beleg richtige
  `auswerter/anbieter/modell/schreibmodell_id`, Belegnamen eindeutig ohne `(n)`.
- Alte Form `schreibmodell: 'p'` ergibt dieselben Belege wie bisher.
- Fehlerfälle: beide Felder, leer, doppelt, vier, Nicht-String; eines von zwei nicht verfügbar → Fehler mit Namen und
  **kein** Beleg, keine Sendungsdatei; Auftrag zu lang nur für eines → Fehler mit dessen Namen, nichts angelegt.
- Wiederaufnahme: nach dem ersten von vier Belegen abgebrochen → erneutes Senden legt keine doppelten an, alle vier
  eingereiht; zwei Belege mit derselben `auftrags_id` → `Konflikt`; Beleg mit passender `auftrags_id`, aber anderem
  Ziel oder Schreibmodell → `Konflikt`; gleiche Gruppe und Ziel, anderes Schreibmodell → kein Konflikt.
- Altfortsetzung: alte Sendungsdatei (ohne `schreibmodell_id`, Eingabe mit `schreibmodell`) mit einem alten Beleg
  ohne `schreibmodell_id` und einem fehlenden → fortsetzen legt genau den fehlenden an; **zweite Unterbrechung**
  direkt nach dessen Anlage, dann erneut senden → keine Doppelbelege, kein Konflikt, alle eingereiht.
- Einzelweg: `schaerfen_vorschau` mit erweiterten Eingaben liefert dasselbe Antwortformat wie vor dem Umbau.
- `composer_status` liefert `schreibmodell_id` und `auswerter` je Lauf.
- Ergebnisnamen zweier Schreibmodelle für dasselbe Ziel: verschieden, ≤ 60 Zeichen, enthalten Ziel-Anfang und
  Schreibmodell kurz; ein schon reservierter Name bleibt.

Bedienung (JS über `dom_nachbau.js`, z. B. neue Datei `prompts_mehrfach_bedienung.js`):
- Menü: zwei wählen, drittes geht, viertes gesperrt, letztes nicht abwählbar; Statuszeile mit „×“ und Laufzahl;
  gesendete Daten enthalten `schreibmodelle` in Anzeigereihenfolge und kein `schreibmodell`.
- Merken und Laden samt Rückfall auf den alten Schlüssel; nicht verfügbare werden beim ersten Laden entfernt; ein
  gewähltes, später nicht verfügbares bleibt abwählbar und sperrt Senden mit Namen.
- Gruppe mit zwei Ergebnissen je Ziel: Spalten in `lauf_nr`-Reihenfolge, Original einmal, Knöpfe; „Als bevorzugt“
  sendet `bevorzugt` mit `kopf_stand`. Ein Ergebnis je Ziel: Anordnung wie bisher, aber mit „Als bevorzugt“ und
  „Im Composer verfeinern“.
- „Im Composer verfeinern“ aus einem Bild-Entwurf heraus auf ein Code-Ergebnis: Typ, Ziel, Materialien und Kontexte
  kommen aus dem Beleg, nichts vom Bild-Entwurf bleibt; `basis {id, fassung, stand}`, Text schreibgeschützt,
  „Weitere Angaben“ offen, Fokus in „Hinweise“.
- Aufgeklappte Original-/Änderungsbereiche bleiben nach einem Neuzeichnen (Statuswechsel eines Geschwisterlaufs) offen.
- „Nochmal …“ auf einem Einzelweg-Beleg mit `bau_version`, aber ohne `zielschluessel`, öffnet den Schärfen-Dialog
  ohne Fehler.
- „Nochmal …“ mit gelöschter `schreibmodell_id`: Zuordnung über Name/Anbieter/Modell/Denkstufe; ohne Treffer leere
  Auswahl, Hinweis, Senden gesperrt – keine unsichtbare ID in den gesendeten Daten.
- Fortsetzung vom Server mit 409 abgelehnt → „Als neue Sendung senden“ erscheint, sendet mit neuer `anfrage_id` und
  unverändertem Entwurf; bei fehlender Antwort erscheint der Knopf nicht.
- Ergebnisfassung nach Übernahme bearbeitet → Hinweis auf der Karte, „Im Composer verfeinern“ setzt den aktuellen
  Stand als `basis.stand`; Fassung gelöscht → beide Knöpfe fehlen. Python: `ergebnis_geaendert`/`ergebnis_fehlt` in
  der Liste.

PROOF (im Repo-Ordner, Node auf dem PATH):
`"%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe" -m unittest discover -s werkstatt\tests`

Abnahme durch Claude: Diff lesen, Suite selbst laufen lassen, Bedienung im Browser auf Port 3897 mit
Temp-Datenordner (`python -m werkstatt.tests.abnahme_harness --datenordner <Temp-Ordner>`). Merge, Push und Neustart
von 3895 nur auf Saschas Wort; danach ein echter Lauf Opus + Sol.
