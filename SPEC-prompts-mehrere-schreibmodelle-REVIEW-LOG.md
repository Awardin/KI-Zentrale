# Review-Log: Mehrere Schreibmodelle im Composer

Plan von Claude nach Saschas „Ja, planen“ (08.11.2026), Spec `SPEC-prompts-mehrere-schreibmodelle.md`.
Prüfer: gpt-6-astra, Denkstufe xhigh, codex-cli 0.167.0-alpha.3.2, nur lesend. MAX_ROUNDS = 3.
Entscheidungen E1–E4 sind Vorschläge; Sascha bestätigt sie vor dem Bau.

## Runde 1 – Astra (thread 01a1bcdf-2ded-76e0-8e0a-57c0fcf451fb)

Der Plan hat noch materielle Lücken. Zwei UI-Fehler habe ich mit dem vorhandenen JavaScript im Speicher reproduziert. Keine Dateien wurden geändert.

1. **P1 – Das neue Vorschauformat bricht den Einzelweg.**  
   Serverpunkt 2 entfernt `schreibmodell`, Serverpunkt 8 verspricht einen unveränderten Einzelweg. Tatsächlich ruft `schaerfen_vorschau` bei den erweiterten Eingaben den Composer auf und liest anschließend `v['schreibmodell']`: Das endet mit `KeyError`. [prompts.py:1481](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1481)  
   **Fix:** Den Einzelweg ausdrücklich auf `schreibmodelle[0]` und dessen Laufwerte adaptieren und sein bisheriges Antwortformat erhalten.

2. **P1 – Die Altformat-Migration ist bei einem zweiten Absturz nicht idempotent.**  
   Ein alter Sendungseintrag hat keine `schreibmodell_id`. Wird sein fehlender Beleg nach dem Update angelegt, bekommt dessen Kopf laut Plan eine ID. Nach einem weiteren Absturz passt dieser Beleg nicht mehr zur Regel „Feld fehlt in Kopf **und** Sendungseintrag“: Je nach Speicherzeitpunkt entsteht ein Doppelbeleg oder ein falscher Fehlend-Konflikt. Die alte Sendungsdatei speichert außerdem überhaupt kein Schreibmodell, nur den Eingabefingerabdruck. [prompts.py:1050](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1050)  
   **Fix:** Eine konsistente Legacy-Zuordnung definieren, die auch gemischte alte/neue Datensätze erkennt, den ursprünglichen Fingerabdruck erhält und einen zweiten Absturz während der Migration übersteht.

3. **P1 – Unvollständige Sendungen hängen weiterhin von veränderlichen Quellen ab.**  
   Fehlt noch ein Beleg, führt `composer_senden` erneut die gesamte Vorschau aus. Nach einem Absturz können geänderte Materialien, Regeln oder Kontextbausteine die Fortsetzung blockieren; ebenso ein inzwischen unverfügbares Schreibmodell. Bereits erzeugte Belege werden dabei noch nicht eingereiht, weil die Einreihung erst nach der vollständigen Anlageschleife folgt. Das ist eine bestehende Lücke, die „Einreihen unverändert“ übernimmt. [prompts.py:1095](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1095)  
   **Fix:** Für begonnene Sendungen Auftrag und Profile aus dauerhaft gespeicherten Momentaufnahmen rekonstruieren; Quellenänderungen ausschließlich über eine neue Sendung übernehmen.

4. **P1 – „Verfeinern“ übernimmt fremden Entwurfszustand und kann das Ziel wechseln.**  
   `pComposerBasis` setzt Text und Basis, lässt aber `prompt_typ`, `modus`, `realismus`, Hinweise, Materialien und Kontexte stehen. Reproduziert: Bild-Entwurf öffnen, Code-Ergebnis übernehmen, Qwen-Ziel setzen, `pZieleZeichnen` aufrufen → Ziel wird wieder `bild`. Ohne Neuzeichnen würde die Serverprüfung den widersprüchlichen Typ ablehnen. Außerdem liegt das gewünschte Fokusfeld in möglicherweise geschlossenen „Weitere Angaben“. [prompts.js:930](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:930), [prompts.js:763](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:763)  
   **Fix:** Einen vollständigen Verfeinern-Initialisierer aus Ergebnisfassung und Belegeingaben verwenden, fremdes Material ausschließen und „Weitere Angaben“ vor dem Fokussieren öffnen.

5. **P2 – „Nochmal“ funktioniert nicht für alle bestehenden Belege.**  
   Der Einzelweg kann Belege mit `bau_version: 2`, aber ohne `zielschluessel` erzeugen. `pComposerNochmal` behandelt sie trotzdem als Composer-Belege und ruft `.split(':')` auf `undefined` auf; reproduziert als `TypeError`. Nur die Schreibmodellauswahl zu ändern behebt das nicht. [prompts.js:944](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:944), [prompts.py:1539](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1539)  
   **Fix:** Den Composer-Pfad an tatsächlich vorhandenen Gruppen-/Zielfeldern erkennen und für Einzelbelege den bisherigen Dialog verwenden.

6. **P2 – „Reihenfolge wie gesendet“ ist aus den Gruppendaten nicht rekonstruierbar.**  
   `_belege` sortiert Dateinamen; `auftragsgruppen` kehrt diese Reihenfolge um. Innerhalb derselben Sekunde bestimmen dadurch Ziel- und Profilnamen die Reihenfolge. Die Oberfläche erhält keine Position aus der Sendung und sieht fehlende, noch nicht angelegte Belege überhaupt nicht. [prompts.py:1629](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1629), [prompts.py:1698](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:1698)  
   **Fix:** Die Gruppenansicht aus der geordneten Sendungsliste speisen und Belege über die Laufidentität zuordnen, einschließlich noch fehlender Läufe.

7. **P2 – Nicht verfügbare ausgewählte Modelle können die Auswahl festsetzen.**  
   Der Plan deaktiviert sämtliche nicht verfügbaren Kontrollkästchen und sperrt gleichzeitig Senden bei ausgewählten nicht verfügbaren Modellen. „Nochmal“ kann genau eine solche Auswahl wiederherstellen: Das störende Modell lässt sich dann nicht entfernen. Das stille Entfernen beim Nachladen widerspricht wiederum der angekündigten sichtbaren Sperre.  
   **Fix:** Ausgewählte nicht verfügbare Modelle weiterhin abwählbar lassen und die Bereinigung gespeicherter Vorgaben klar vom Aktualisieren eines laufenden Entwurfs trennen.

8. **P2 – Die neuen Ergebnisaktionen fehlen im Einzelergebnis-Pfad.**  
   „Ein Ergebnis: Darstellung wie heute“ verwendet `pSchaerfenErgebnis`, das weder „Als bevorzugt“ noch „Im Composer verfeinern“ anbietet. Nach einer Vergleichsrunde mit anschließend nur einem Schreibmodell verschwindet damit der neue direkte Arbeitsablauf. Zwei getrennte Renderer erhöhen außerdem das Risiko, Hinweise wie neue Platzhalter oder den erkannten Prompt-Typ nur in einer Ansicht zu zeigen. [prompts.js:323](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:323)  
   **Fix:** Ergebnisinhalt und Aktionen gemeinsam rendern und lediglich die Anordnung zwischen Einzelansicht und Vergleich unterscheiden.

9. **P2 – Aufgeklappte Vergleiche werden während laufender Geschwisteraufträge wieder geschlossen.**  
   Die neuen `details` für Original und Änderungen erhalten laut Plan keine Zustandskennung. `pWaehlen` ersetzt bei Statusänderungen die Ansicht; seine bisherige Wiederherstellung erfasst nur bereits vorhandene `details[data-p-ansicht]`, während die Ergebnisgruppe erst danach aufgebaut wird. [prompts.js:134](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:134), [prompts.js:249](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:249)  
   **Fix:** Öffnungszustände mit stabilen Gruppen-/Laufschlüsseln speichern und nach dem Aufbau der Ergebnisgruppe wiederherstellen.

10. **P2 – Die Namenskürzung sichert Eindeutigkeit, aber nicht erkennbare Herkunft.**  
    Unterschiedliche Profile können nach Entfernen des Anbietersegments und Kürzen auf 24 Zeichen identisch heißen, insbesondere bei langen Modellnamen mit unterschiedlichen Denkstufen. `(n)` verhindert Überschreiben, verrät aber nicht das Schreibmodell; die bestehende Kollisionslogik kürzt zudem gerade das rechte Namensende. [prompts.py:438](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:438)  
    **Fix:** Beim Kürzen Platz für ein unterscheidendes Modell-/Denkstufenmerkmal reservieren und bei verbleibender Gleichheit eine kurze stabile Profilkennung ergänzen.

Der Nachweis muss diese Fälle abdecken, insbesondere die **zweite Unterbrechung einer Legacy-Fortsetzung**, veränderte Quellen während einer Teilanlage und den Wechsel Bild → Code beim Verfeinern. Die Beschränkung zulässiger Testanpassungen ist ebenfalls falsch: Bestehende Tests prüfen die exakten Sendungsfelder und das künftig entfernte `select#p-schreibmodell`. Eine neue JS-Testdatei muss außerdem ausdrücklich in den Python-Testlauf eingebunden werden.

VERDICT: REVISE

### Antwort Claude (Runde 1)

Übernommen:
- 1 Einzelweg: `schaerfen_vorschau` liest `v['schreibmodell']` (am Code bestätigt, ~Z. 1481) → auf
  `schreibmodelle[0]`/`laeufe[0]` umstellen, Antwortformat gleich; Test ergänzt.
- 2 Altfortsetzung: Wiederfinden jetzt über `auftragsgruppe` + `auftrags_id` (alle 5 vorhandenen Gruppenbelege tragen
  sie), danach Ziel/Schreibmodell gegenprüfen; alte Sendungseinträge bekommen die ID des einzigen Schreibmodells vor
  jeder Neuanlage. Test „zweite Unterbrechung“ ergänzt.
- 4 Verfeinern: vollständiger Initialisierer aus den Belegeingaben, „Weitere Angaben“ vor dem Fokus öffnen; Test
  Bild-Entwurf → Code-Ergebnis.
- 5 „Nochmal“ auf Einzelweg-Belegen: Composer-Weg nur mit `auftragsgruppe` und `zielschluessel`.
- 6 Reihenfolge: `lauf_nr` im Belegkopf, Gruppe danach geordnet.
- 7 Gewählte nicht verfügbare Modelle bleiben abwählbar; Bereinigung nur beim ersten Laden.
- 8 Ein gemeinsamer Ergebnis-Renderer; neue Knöpfe auch bei einem Ergebnis.
- 9 Stabile `data-p-ansicht`-Schlüssel, Wiederherstellung nach `pGruppeZeichnen`.
- Testanpassungen erweitert (Sendungsfelder, `select#p-schreibmodell`), neue JS-Datei in `test_prompts.py` einbinden.

Abgelehnt / anders gesehen:
- 3 Momentaufnahmen für begonnene Sendungen: bestehende Grenze des Composers, nur nach einem Prozessabsturz mitten im
  Senden relevant; die Meldung ist sichtbar und ein neues Senden löst es. Als bekannte Grenze in der Spec vermerkt,
  kein Umbau in diesem Umfang.
- 10 Stabile Profilkennung im Fassungsnamen: Die heutigen Profilnamen passen in 24 Zeichen
  („GPT-6.1-Sol · sehr hoch“ = 23); bei Gleichheit trennt `(n)`, das Schreibmodell steht auf Karte und Beleg.


## Runde 2 – Astra

Die früheren Befunde **1, 2, 4, 5, 6, 8 und 9 sowie die Testanbindung sind im Plan ausreichend adressiert**. Die Zuordnung über `auftrags_id` schließt insbesondere die beschriebene Migrationslücke.

Die Namenskürzung aus Befund 10 akzeptiere ich als dokumentierte Einschränkung. Auch zusätzliche Momentaufnahmen müssen nicht zwingend Teil dieses Umbaus werden. Drei Punkte bleiben:

1. **P1 – Der Ersatzweg für Befund 3 ist nicht bedienbar.**  
   Die Spec sagt bei gescheiterter Fortsetzung: „Sascha sendet neu“. Tatsächlich bleibt `P.sendung` gesetzt; normales Senden kehrt sofort zurück, und „Status prüfen“ bietet bei einer unvollständigen Sendung ausschließlich „Einreihung fortsetzen“. Im Speicher reproduziert: nur dieser Knopf, null neue Sendeanfragen, unveränderte UUID. Ein Seitenneuladen verliert den ungespeicherten Entwurf. Das Problem benötigt auch keinen Prozessabsturz; ein Fehler während der Beleganlage genügt. [Spec:94](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts-mehrere-schreibmodelle.md:94), [prompts.js:865](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/prompts.js:865)  
   **Fix:** Nach eindeutig gescheiterter Fortsetzung einen ausdrücklichen Neustart mit neuer UUID und erhaltenem Entwurf anbieten, der bereits vorhandene Teilläufe sichtbar macht; nicht automatisch bei bloßem Antwortverlust zurücksetzen.

2. **P2 – „Nochmal“ kann eine gelöschte Profil-ID unsichtbar wieder auswählen.**  
   Befund 7 ist für *vorhandene, unverfügbare* Profile gelöst. Neu gespeicherte Belege enthalten aber eine dauerhafte `schreibmodell_id`, während Profile löschbar sind und beim erneuten Anlegen eine neue ID bekommen. Nach dem Laden bereinigter Optionen setzt „Nochmal“ laut Spec die alte ID wieder ein. Dafür existiert kein Kontrollkästchen zum Abwählen; weitere gültige Auswahlen beseitigen diesen ungültigen Eintrag nicht. Der Namensrückfall greift laut Wortlaut nur ohne gespeicherte ID. [Spec:166](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts-mehrere-schreibmodelle.md:166), [auswertung.py:940](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:940)  
   **Fix:** Gespeicherte IDs gegen die aktuellen Optionen prüfen; bei fehlender ID über Anbieter/Modell/Denkstufe zuordnen oder eine leere Auswahl mit „Schreibmodell neu wählen“ herstellen.

3. **P2 – Die neuen Ergebnisaktionen können einen anderen Text auswählen als die Vergleichskarte zeigt.**  
   Eine übernommene Ergebnisfassung lässt sich unter demselben Namen bearbeiten. Die Ergebniskarte zeigt weiterhin `b.neue_fassung` aus dem ursprünglichen Beleg, während „Als bevorzugt“ und der neue Verfeinern-Initialisierer die inzwischen geänderte Fassung dieses Namens verwenden. Die vorgesehene Prüfung „Name gehört zum Eintrag“ erkennt diese Abweichung nicht. Beispiel: Ergebnis A wird nachträglich zu B bearbeitet; die Vergleichskarte zeigt A, „Verfeinern“ übernimmt B. [Spec:151](C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts-mehrere-schreibmodelle.md:151), [prompts.py:710](C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/prompts.py:710)  
   **Fix:** Vor den Aktionen Ergebnistext und aktuellen Fassungsstand vergleichen und eine Abweichung sichtbar machen; eindeutig festlegen, welche Version übernommen wird.

Für diese drei Fälle fehlen noch gezielte Bedienungstests. Keine Dateien geändert.

VERDICT: REVISE

### Antwort Claude (Runde 2)

Alle drei übernommen:
- 1 (P1) „Als neue Sendung senden“ nach einer vom Server beantworteten, gescheiterten Fortsetzung: neue `anfrage_id`,
  Entwurf bleibt, Hinweis auf die alten Teilläufe; bei Antwortverlust weiter nur „Status prüfen“ (Oberfläche 5a).
- 2 Jede Stelle, die die Auswahl setzt, nimmt nur vorhandene IDs; „Nochmal …“ ordnet eine gelöschte ID über
  Name/Anbieter/Modell/Denkstufe zu, sonst leere Auswahl mit Hinweis.
- 3 `ergebnis_geaendert`/`ergebnis_fehlt` aus der Liste; Hinweis auf der Karte, Knöpfe nehmen den aktuellen Stand,
  ohne Fassung keine Knöpfe.
Tests für alle drei ergänzt. Runde 3, weil nach Runde 2 ein P1 offen war.


## Runde 3 – Astra

Die drei Befunde aus Runde 2 sind **auf Planebene gelöst**:

- **Gescheiterte Fortsetzung:** Ein ausdrücklicher Neustart erhält den Entwurf und verwendet eine neue UUID. Antwortverlust bleibt davon getrennt.
- **Gelöschte Schreibprofile:** Alle Auswahlwege prüfen aktuelle IDs; „Nochmal“ verwendet eine eindeutige Ersatzzuordnung oder fordert eine neue Auswahl.
- **Bearbeitete Ergebnisfassungen:** Abweichungen werden angezeigt, Aktionen verwenden ausdrücklich den aktuellen Stand; bei fehlender Fassung entfallen die Knöpfe.

Die vorgesehenen Nachweise decken diese Fälle ab. Ich sehe **keine verbleibenden P0/P1-Probleme**, die die Umsetzung blockieren. Die dokumentierten Einschränkungen bei Momentaufnahmen und Namenskürzung bleiben vertretbar.

Die Freigabe betrifft den Plan; Implementierung, Tests und Abnahme stehen noch aus. Keine Dateien geändert.

VERDICT: APPROVED

## Ergebnis

APPROVED nach 3 Runden (08.11.2026). Offen vor dem Bau: Saschas Bestätigung von E1–E4 und das Bau-Go
(Sol xhigh, eigener Worktree ab main d82558b).

## Act 3 — Build (09.11.2026, Sascha: „Ja, so bauen“, E1–E4 bestätigt)

Builder gpt-6.1-sol, Denkstufe xhigh, Worktree `KI-Zentrale-bau-mehrfach`, Zweig `bau/prompts-mehrfach` ab d82558b,
Start abgekoppelt über WMI. Thread 01a1bfaf-d595-7843-8249-e0623449b9d2.

### Runde 1 — Sol-Bau (10:42–11:02, 20 min, 1 Versuch)
Server (Mehrfachläufe, Profilprüfung mit Namen, Wiederfinden über `auftrags_id`, `lauf_nr`, Altfortsetzung,
`ergebnis_geaendert/ergebnis_fehlt`, Einzelweg angepasst), Oberfläche (Menü mit Kontrollkästchen, Grenze drei,
Merken mit Rückfall, gemeinsamer Ergebnis-Renderer, Spalten, „Als bevorzugt“, „Im Composer verfeinern“, „Als neue
Sendung senden“ über den HTTP-Status aus `api()`), 12 neue Python-Tests, neue `prompts_mehrfach_bedienung.js`.
Angepasst: Sendungsfeld-Test, `prompts_composer_bedienung.js`, `prompts_fixrunde1_bedienung.js`. Abweichung: Bei
unbekannter Profil-ID nennt die Meldung die ID (Name ist nicht mehr bekannt).

### Claudes Urteil (Runde 1)
Diff gelesen, Suite selbst: Ran 485, OK (skipped=1). Browser auf 3897 (Harness, Temp-Daten): Menü, Grenze drei
(übrige gesperrt mit Titel), Escape, 2 Ziele × 2 Schreibmodelle = 4 Läufe, Spalten je Ziel, Original eingeklappt,
„Als bevorzugt“ → „Bevorzugt“, „Im Composer verfeinern“ (Basis = Ergebnisfassung, nur dieses Ziel, beide gemerkten
Schreibmodelle, „Weitere Angaben“ offen, Fokus Hinweise) mit zweiter Runde, 900 px zwei Spalten, 375 px untereinander
ohne Querscrollen, Konsole ohne Fehler. Zwei kleine Befunde: Zielteil des Fassungsnamens mitten im Wort gekürzt;
`pWaehlen` setzt nach dem abgewarteten Gruppenabruf ohne erneute Prüfung der Anfragekennung Stand und Scrollposition.

### Runde 2 — Sol-Nachbesserung (11:07–11:10, 3 min)
Zielteil an Segmentgrenzen kürzen (Test mit „Codex · GPT-6-Sol · mittel“ → „Codex“), Prüfung `anfrage !== P.anfrage`
nach `pGruppeZeichnen` (Bedienungstest mit verzögertem Abruf). Claude: Code gelesen, Suite selbst: Ran 486, OK
(skipped=1). Abgenommen.

Gesamt: 28 min, 2 Runden, Tokens 6,8 M (davon 6,6 M aus Cache), Ausgabe 55 k; Codex-Wochenfenster 25 → 27 %.

### Lehre aus diesem Lauf
- Zeit kostete nichts Nennenswertes: Die dreirundige Astra-Prüfung hatte die Stolperstellen (Einzelweg, Altfortsetzung,
  Verfeinern-Zustand) vorab geklärt; Sol baute in einem Durchgang.
- Keine Änderung an Skill, Vorlage oder AGENTS nötig.
