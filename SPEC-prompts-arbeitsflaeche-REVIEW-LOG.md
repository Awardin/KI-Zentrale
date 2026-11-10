# Review-Log: Reiter Prompts – Arbeitsfläche mit Rückfragen

Act 1 (Anforderung): Sascha am 10.11.2026 nach dem ersten echten Zwei-Modell-Lauf – zwei Fenster nebeneinander
(links sein Prompt, rechts der neue), immer den neuen Prompt verbessern, beim Verbessern ein Fenster mit kurzen
Rückfragen (Vorlage-Bild mit Prioritäten), Anordnung „so, wie du meinst, dass es am praktikabelsten ist“.
Gestaltung D1–D7 von Claude festgelegt (Spec `SPEC-prompts-arbeitsflaeche.md`). MAX_ROUNDS=3.
Basis: `main` (c300a66) plus `bau/prompts-anzeige` (Menüs schließen, Laufanzeige; abgenommen, noch nicht committet).

Prüfer: gpt-6-astra (gepinnt), Denkstufe xhigh (gepinnt) – codex-cli 0.167.0-alpha.3.2, Konfig-Standard gpt-6.1-sol.

## Runde 1 — Astra (Thread 01a1c493-d2c9-7571-b72e-712a8d765a68)

Der Plan ist **noch nicht implementierungsreif**. Die Grundidee passt zum Nutzerziel; mehrere Daten- und Zustandsregeln würden bei wörtlicher Umsetzung jedoch falsche Ausgangstexte verwenden, Eingaben verlieren oder bestehende Ansichten beschädigen.

1. **P1 – Bearbeitete Fassungen verlieren ihren Auftragskontext.**  
   Nach S6 besitzt die neue Fassung keinen erzeugenden Beleg. O5 findet deshalb keine übernommenen Materialien, Kontexte oder Realismus-Einstellungen mehr und fällt auf Eintragswerte zurück. Der Eintrag enthält diese Informationen nicht. Laut Begriffsdefinition wird lediglich das Ziel im Seitenspeicher behalten; nach einem Seitenaufruf kann sogar das Ziel einer anderen Runde verwendet werden. Das betrifft bereits „Text ändern → Prompt verbessern“. Siehe [Eintragsdaten](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:660) und [bisherige Belegübernahme](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:1089).  
   **Fix:** Bei S6 die Herkunft aus Quellfassung, Quellstand und gegebenenfalls Quellbeleg dauerhaft speichern und daraus die vollständigen Einstellungen ableiten.

2. **P1 – O6 verbessert unter Umständen den alten statt des sichtbaren Texts.**  
   Nur O5 speichert Änderungen vor dem Senden. Sascha kann aber zuerst Fragen erhalten, danach rechts den Prompt ändern und anschließend „Mit Antworten verbessern“ drücken. Mit gespeichertem Text wird seine Änderung ignoriert; mit dem sichtbaren Text und alter `basis` lehnt der Server ab. Die Prüfung verlangt ausdrücklich identischen Text zur gespeicherten Basis. Auch „Testen“ und „Als bevorzugt“ haben bei ungespeicherten Änderungen keine festgelegte Bedeutung. [Basisprüfung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:931)  
   **Fix:** Für alle weiterführenden Aktionen denselben Ablauf definieren: sichtbaren Text sichern, neue Basis übernehmen und erst anschließend senden, testen oder bevorzugen.

3. **P1 – Fragen sind nicht an den tatsächlichen Fassungsstand gebunden.**  
   O3 ordnet Fragen einer Fassung zu, ohne `fassung_stand` einzubeziehen. Die weiterhin vorhandene Fassungsbearbeitung kann denselben Namen verändern. Nach einem Neuladen könnten alte Fragen und Antworten deshalb mit dem neuen Stand versendet werden. S3 verlangt außerdem keine Prüfung, ob `fragen_beleg` überhaupt zum Eintrag, Ziel und Ausgangsstand gehört. [Bestehende Bearbeitung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:716)  
   **Fix:** Fragenzuordnung und serverseitige Prüfung an Eintrag, Fassungsname, Stand und Ziel binden; bei Änderungen die Fragen als veraltet markieren und Antworten als Entwurf erhalten.

4. **P1 – „Wie `pComposerAusBeleg`“ übernimmt keine vollständig eingefrorenen Materialien.**  
   Die Funktion übernimmt Kontextreferenzen mit altem Stand. Der Server liest diese erneut und antwortet bei Änderungen mit 409. Materialdateien und frühere Antworten werden ebenfalls erneut gelesen; dabei können andere Inhalte in die nächste Runde gelangen. In der Arbeitsfläche gibt es laut Umfang keine Material-/Kontextbearbeitung und für diesen Konflikt keinen beschriebenen Ausweg. [Materialauflösung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1246), [Kontextauflösung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1339)  
   **Fix:** Entweder ausdrücklich die gespeicherten Momentaufnahmen weiterverwenden oder bei Änderungen einen erreichbaren Composer-Wechsel mit erhaltenen Antworten anbieten.

5. **P1 – Das Zustandsmodell setzt eine Ergebnisfassung voraus, die häufig nicht existiert.**  
   O6 soll sofort die neue Runde zeigen, während O4 seine Anzeige von der „gezeigten Fassung“ ableitet. Während des Laufs existiert diese noch nicht. Bei ungültiger Antwort, Abbruch oder Fehler entsteht möglicherweise nie eine. Auch Sammlungsvorschläge erhalten keine Ergebnisfassung. Ungeklärt bleibt außerdem: Modell A scheitert, Modell B liefert; oder eine ältere Runde wird fertig, während bereits an einer neueren gearbeitet wird. [Ergebnisübernahme](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:384)  
   **Fix:** Aktive Runde, ausgewählten Lauf und editierte Fassung getrennt verwalten; für jeden Laufzustand Anzeige, erlaubte Aktionen und Rückfallfassung festlegen.

6. **P1 – Der Schutz vor Neuzeichnen deckt nicht alle Eingaben und Wechsel ab.**  
   `pGeschuetzt()` schützt aktuell nur bei Fokus oder offenem Dialog. O3 sichert Antworten und Überspringen, erwähnt aber „Weitere Wünsche“ nicht. Nach Fokusverlust kann dieses Feld beim nächsten Neuzeichnen verschwinden. Für ungespeicherte Promptänderungen bei Modell-, Ziel-, Versions- oder Eintragswechsel fehlt ebenfalls eine Regel. Eine globale Erweiterung von `pGeschuetzt()` würde zugleich bewusstes `pWaehlen()` blockieren. [Ladeschutz](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:8), [Auswahl](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:130)  
   **Fix:** Alle Entwurfsfelder samt Ausgangsstand außerhalb des DOM halten und automatische Aktualisierung getrennt von bewusster Navigation behandeln.

7. **P1 – Der vorhandene Composer-Sendeweg ist nicht unabhängig vom Composer verwendbar.**  
   `pComposerSenden()` liest `P.entwurf` und verwendet globale Sendungszustände. `pSendungUebernommen()` kann den Composer leeren und wechselt Auswahl und Fokus. Damit ist „denselben Sendeweg benutzen, ohne den Composer-Entwurf zu verändern“ keine einfache Wiederverwendung. Eine ungeklärte Composer-Sendung und eine Arbeitsflächen-Sendung könnten sich außerdem gegenseitig blockieren oder überschreiben. [Senden](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:971), [Erfolgsbehandlung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:1035)  
   **Fix:** Einen gemeinsamen Transportablauf mit übergebenen, eingefrorenen Daten und eindeutig zugeordnetem Sendungszustand herauslösen.

8. **P1 – Der neue Requestvertrag ist unvollständig beschrieben.**  
   S3 nennt ausdrücklich nur `rueckfragen` als Erweiterung der Fingerabdruck-Whitelist; O6 sendet zusätzlich `fragen_beleg`, was ohne weitere Änderung als unbekanntes Feld abgewiesen wird. Außerdem ist das definierte „Ziel der gezeigten Fassung“ ein `zielschluessel`, während `ziele` Objekte mit `zielprofil`, gegebenenfalls `eintrag`, `testprofil` und `variante` erwartet. [Whitelist](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1049), [Zielvertrag](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:835)  
   **Fix:** Einen vollständigen Beispielrequest festschreiben, beide neuen Felder validieren und das Ziel ausdrücklich in das bestehende Eingabeformat übersetzen.

9. **P1 – Die unveränderte Schärfen-Anzeige versteht Rückfragen-Belege nicht.**  
   `pSchaerfenErgebnis()` behandelt nur „Erst klären“ als Fragen. „Rückfragen“ würde im bisherigen Abschnitt als „Keine gültige neue Fassung“ erscheinen. Zudem ist `datei_inhalt()['fragen']` bereits ein **String** für „Erst klären“; S4 bezeichnet dasselbe Feld als Liste. Die bestehende Typsemantik muss ausdrücklich erhalten bleiben. [Renderer](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:367), [Antwortformat](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1624)  
   **Fix:** Rückfragen in allen Ergebnisansichten ausdrücklich behandeln und für strukturierte Fragen ein eigenes Feld oder einen eindeutig aktionsabhängigen Vertrag definieren.

10. **P1 – S6 beschreibt keine atomare Standprüfung und Namensvergabe.**  
    `Eintrag.fassung_neu()` sperrt nur seinen eigenen Lese-/Schreibvorgang. Wenn S6 vorher den Quellstand und Namen prüft, kann dazwischen eine andere Anfrage die Quelle ändern oder denselben Namen vergeben. Zusätzlich erzeugt eine Wiederholung nach verlorener Speicherantwort eine weitere „Bearbeitet … (2)“-Fassung, weil S6 keine Idempotenzkennung besitzt. [Fassung anlegen](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:730)  
    **Fix:** Standprüfung, Namensreservierung und Anlage unter dieselbe `_SPERRE` legen und wiederholte Speicheranfragen eindeutig wiedererkennen.

11. **P1 – Die Modellwahl kann feststecken.**  
    O7 sagt „nicht verfügbare gesperrt“. Bereits gewählte, inzwischen nicht verfügbare Modelle müssen aber **abwählbar** bleiben; genau das berücksichtigt die bestehende Implementierung. Andernfalls bleibt ein ungültiges Modell dauerhaft Teil der Sendung. Außerdem erscheint die Auswahl nach O3 erst bei fertigen Fragen: Scheitert schon die Vorschau mangels Fragesteller, fehlt innerhalb des beschriebenen Ablaufs die direkte Korrekturmöglichkeit. [Bestehende Auswahlregel](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:823)  
    **Fix:** Gewählte Modelle stets abwählbar lassen und Modellwahl sowie Fehlerbehebung bereits im Leer-, Vorbereitung- und Fehlerzustand anbieten.

12. **P2 – Mehrzeilige Antworten widersprechen der Validierung.**  
    O3 bietet Textareas an, S3 verbietet sämtliche Steuerzeichen. Die vorhandene `_STEUERZEICHEN`-Prüfung umfasst auch Zeilenumbrüche. Eine normale zweizeilige Antwort würde damit scheitern. S4 kann seinerseits JSON-Fragen mit eingebetteten Zeilenumbrüchen akzeptieren, die S3 später zurückweist. [Zeichenprüfung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:15)  
    **Fix:** Zeilenumbrüche für Antworten ausdrücklich zulassen und normalisieren; dieselben Regeln für geparste und zurückgesendete Fragefelder verwenden.

13. **P2 – S7 garantiert eine Reihenfolge, die der Code nicht zuverlässig liefert.**  
    Gruppen entstehen aus alphabetisch sortierten Belegdateinamen mit sekundengenauem Zeitpräfix. Zwei Sendungen derselben Sekunde können daher nach Modellname oder Kollisionssuffix statt nach Startreihenfolge erscheinen. Darauf „letzte Runde“ aufzubauen ist unzuverlässig. [Dateisortierung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1672), [Gruppenbildung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1753)  
    **Fix:** Eine stabile Startreihenfolge der Sendungen festlegen und bestehende Gruppen mit einer dokumentierten Rückfallordnung behandeln.

Die Entscheidungen D1–D7 bewerte ich so:

| Entscheidung | Bewertung und konkrete Korrektur |
|---|---|
| **D1** | **P2:** Auf großen Fenstern praktikabel. Bei 1280 px bleiben wegen Seitenleiste und Abständen ungefähr 1024 px Inhalt; O1 schaltet schon auf eine Spalte. **Fix:** Zweispaltigkeit anhand der tatsächlich benötigten Mindestbreiten ermöglichen; mobil den langen Ergebnistext begrenzen, damit die Fragen erreichbar bleiben. |
| **D2** | Inhaltlich richtig und zentral für Saschas Wunsch. **P1:** O6 erfüllt die Regel bei nachträglichen Änderungen nicht. **Fix:** Befund 2 umsetzen. |
| **D3** | **P2:** „Ohne Antworten“ erspart aktuell nicht den Fragenlauf; der Knopf erscheint erst danach oder nach einem Fehler. **Fix:** Direktes Verbessern bereits vor dem Fragenlauf anbieten und den Abbruchzustand ausdrücklich behandeln. |
| **D4** | **P2:** „Es kennt die eigenen Annahmen“ ist technisch unbegründet: Der neue Aufruf erhält keinen Gesprächsverlauf und keine früheren Überlegungen. **Fix:** Dasselbe Modell als einfache Vorgabe behandeln, sichtbar machen und wechseln lassen. |
| **D5** | Sinnvoll: direkte Bearbeitung plus neue Fassung. **P1:** Ohne dauerhafte Herkunft und atomaren Speicherablauf ist die Umsetzung unvollständig. **Fix:** Befunde 1 und 10 umsetzen. |
| **D6** | Reiter plus Vergleich sind praktikabel. **P2:** Beim erneuten Öffnen gewinnt trotzdem immer das erste Modell der letzten Runde, selbst wenn Sascha das zweite bevorzugt hat. **Fix:** Bewusste Auswahl erhalten und beim erneuten Öffnen die bevorzugte gültige Fassung berücksichtigen. |
| **D7** | **P2:** Maximal fünf Fragen ist sinnvoll; mindestens eine Frage erzwingt dagegen auch bei vollständigen Prompts unnötige Rückfragen. Die unveränderten Vollansichten darunter verdoppeln zudem viel Inhalt. **Fix:** Null sinnvolle Rückfragen zulassen und den bisherigen Verlauf einklappbar erhalten. |

**P2 – Der Nachweis braucht zusätzliche Fehler- und Konkurrenzfälle.** Die vorgesehenen Tests erfassen viele Einzelaktionen, aber nicht die kritischen Übergänge. Ergänzen würde ich insbesondere:

- Fragen beantworten → rechts ändern → mit Antworten senden; einschließlich unverändertem Composer-Entwurf.
- Externe Fassungsänderung unter gleichem Namen; geänderter oder gelöschter Kontext; fremder `fragen_beleg`.
- Verzögerte Speicher-/Ladeantwort während weiterer Eingaben oder eines Versionswechsels; Erhalt von „Weitere Wünsche“.
- Zwei parallele Runden, Teilfehler, Abbruch, ungültige Antwort, fehlende Ergebnisfassung und Sammlungsvorschlag.
- Gleichzeitige S6-Anfragen und verlorene Speicherantwort.
- Ablehnung von „Rückfragen“ auch über die beiden Einzelwege, nicht nur im Composer.

**Fix:** Diese Abläufe als explizite Abnahmekriterien aufnehmen.

Einen zwangsläufigen Bruch alter Auftragshashes schreibt der Plan nicht vor. Die Kompatibilität ist aber nur gesichert, wenn fehlende neue Felder beim Lesen und beim Fingerabdruck **fehlend bleiben**, statt nachträglich mit `[]` oder `null` ergänzt zu werden. Neben festen Altaufträgen für beide Bauversionen muss deshalb auch eine bereits teilweise angelegte alte Sendung ihren ursprünglichen Fingerabdruck behalten und fortgesetzt werden können.

Die Prüfung war ausschließlich statisch; ich habe keine Dateien verändert, Server gestartet oder Modelle aufgerufen.

VERDICT: REVISE
### Antwort Claude (Fassung 2)

Übernommen:
- 1 Herkunft: `herkunft.json` je Eintrag mit `von_fassung`, `von_stand`, geerbtem `quell_beleg`, `anfrage_id` (S6);
  Einstellungen neuer Runden kommen aus dem Quellbeleg (Begriffe).
- 2 Speichern vor jeder weiterführenden Aktion (O5), auch Testen und Als bevorzugt; Kopieren ohne Speichern.
- 3 Fragen an Name + Stand gebunden, eine Herkunftsstufe erlaubt (Fragen beantworten → Text ändern → senden bleibt
  gültig); Zustand „veraltet“; Serverprüfung des `fragen_beleg` (Eintrag, Aktion, fertig, Bezugsfassung, Ziel).
- 4 Kontexte mit aktuellem Stand (vorher `kontext_lesen`), Materialien wie im Quellbeleg; jeder Fehler führt zu
  „Im Composer öffnen“ mit Wünschen und Antworten als Hinweise-Text.
- 5 Zustandsmodell O4 (`P.af[eid]` mit runde/ziel/lauf/fassung/bewusst), Zustände je Lauf, Teilfehler, kein
  Selbstwechsel nach fertigem Text.
- 6 Entwürfe, Antworten, Überspringen, Wünsche im Speicher (O5); `pGeschuetzt` bleibt, Navigation nicht blockiert.
- 7 Transport aus `pComposerSenden` herauslösen, eigener Sendungszustand der Arbeitsfläche (O6).
- 8 Vollständiger Beispielrequest, `fragen_beleg` in der Erlaubtliste, Zielübersetzung über gemeinsame Hilfsfunktion.
- 9 Neues Feld `fragenliste`, `fragen` (Text) bleibt; O8 für bestehende Ansichten.
- 10 S6 in einer Methode unter `_SPERRE` (RLock), idempotent über `anfrage_id`.
- 11 Gewählte bleiben abwählbar; Fragesteller-Auswahl schon im Leer- und Fehlerzustand.
- 12 Zeilenumbrüche in Antworten erlaubt und normalisiert; Parser normalisiert Fragefelder auf eine Zeile.
- 13 Stabile Sortierung der Gruppen (S7).
- Antworten jetzt als `{nr, antwort}`; Server löst gegen den Fragen-Beleg auf und speichert eine Momentaufnahme.
- D1 Container-Abfrage ab 860 px, schmal 60vh; D3 „Direkt verbessern“; D4 Begründung gestrichen, Vorgabe sichtbar
  und änderbar; D6 bevorzugte Fassung gewinnt, bewusste Wahl bleibt; D7 0 Fragen erlaubt („Jetzt verbessern“).
- Nachweis um die genannten Übergänge, Konkurrenz- und Altfälle ergänzt.

Abgelehnt:
- D7 Teil 2 (Abschnitte darunter einklappen): verändert die heutige Bedienung (Tests, Warteschlange), die Sascha
  nutzt; erst nach seiner Probe entscheiden (unter „Nicht im Umfang“ vermerkt).

## Runde 2 — Astra

**Fassung 2 löst viele frühere Befunde, ist aber noch nicht freigabereif.** Auf Planebene geschlossen sind insbesondere der getrennte Transport, die Requestfelder und Zielübersetzung, `fragenliste` statt Feldkollision, die Modellwahl und mehrzeilige Antworten. Herkunft, Standbindung, Wiederherstellung und Entwurfsschutz bleiben teilweise fehlerhaft.

D1, D3, D4 und die Zulassung von null Fragen sind jetzt praktikabel. Die bestehenden Abschnitte vorerst unverändert zu lassen, akzeptiere ich als bewusste Umfangsentscheidung.

1. **P1 – S3 widerspricht seiner eigenen Momentaufnahme-Regel.**  
   S3 verlangt dieselbe Referenzprüfung in `composer_vorschau`, `composer_senden` **und `schaerfen_lesen`**. Gespeichert werden aber aufgelöste `{prioritaet, frage, antwort}` statt `{nr, antwort}`. Beim späteren Lesen gibt es außerdem keine Anfrage-`basis`. Eine Prüfung gegen den aktuellen Fragen-Beleg würde gespeicherte Aufträge nach dessen Änderung oder Löschung unlesbar machen. Der Leser wird auch bei Anzeige und Ausführung aufgerufen. [Bestehender Leser](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:321)  
   **Fix:** Anfrageprüfung und Belegprüfung trennen: Referenzen nur beim Erzeugen auflösen; danach ausschließlich das gespeicherte Schema prüfen.

2. **P1 – S6 ist trotz RLock nicht absturzsicher oder vollständig idempotent.**  
   Nach „Fassung anhängen“, aber vor `herkunft.json`, fehlt die gespeicherte `anfrage_id`. Ein erneuter identischer Request erzeugt deshalb eine zweite Fassung. Die ausdrücklich akzeptierte Unterbrechung verliert auch Ziel-/Materialherkunft. Eine beschädigte Herkunftsdatei als leer zu behandeln, kann beim nächsten Schreiben sämtliche bisherigen Zuordnungen ersetzen. Der vorhandene Gruppenweg reserviert seinen Ergebnisnamen aus genau diesem Grund **vor** dem Anhängen. [Reservierung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:420)  
   **Fix:** Operation mit vollständigem Request-Fingerprint und Ergebnisname vorab reservieren und fortsetzbar abschließen; beschädigte Herkunftsdaten nicht still überschreiben.

3. **P1 – Die Herkunftsausnahme umgeht weiterhin die Standprüfung.**  
   Beispiel: Fragen zu F → bearbeitete Fassung G → G später über den unveränderten alten Bearbeitungsdialog ändern. G behält `von_fassung=F` und `von_stand`; damit gelten die alten Fragen nach der neuen Regel weiterhin. `herkunft.json` enthält keinen Stand der ursprünglich angelegten Fassung G, an dem diese Ausnahme geprüft werden könnte. [Bestehende Änderung unter gleichem Namen](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:718)  
   **Fix:** Auch den erzeugten Fassungsstand speichern und die Herkunftsausnahme nur zulassen, solange der aktuelle Text diesem Stand entspricht.

4. **P1 – `{nr, antwort}` bindet Antworten nicht an die tatsächlich angezeigten Fragen.**  
   Wird der Fragen-Beleg nach dem Anzeigen geändert oder seine Fragenreihenfolge vertauscht, ordnet S3 die Antwort einer anderen Frage zu. Eintrag, Bezugsfassung und Ziel können dabei unverändert bleiben. Der Vorschauhash hilft nicht: Er wird erst nach der erneuten Auflösung berechnet.  
   **Fix:** Einen Hash der angezeigten normalisierten Fragenliste mitsenden und vor der Auflösung prüfen.

5. **P1 – O4 verwendet den falschen Wiederholungsweg.**  
   `wiederholen_beleg` liefert 409, wenn der Beleg noch in der Warteschlange steht – auch bei Fehler oder Abbruch. Dafür verwendet die vorhandene Oberfläche `/api/fassung` mit `wiederholen`. Bei einer bereits gespeicherten **ungültigen Antwort** ruft Wiederholen außerdem kein Modell erneut auf, sondern wertet dieselbe Antwort nochmals aus. Der angebotene Knopf behebt diesen Zustand nicht. [Belegwiederholung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1908), [Antwortwiederverwendung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/auswertung.py:1197)  
   **Fix:** Warteschlangen-Wiederholung, verwaisten Beleg und bewusste Neuerzeugung mit neuer Sendungs-ID ausdrücklich unterscheiden.

6. **P1 – Der Composer-Ausweg überschreitet die bestehende Hinweisgrenze.**  
   O6 überträgt Wünsche und sämtliche Fragen/Antworten in `hinweise`. Schon fünf erlaubte Antworten ergeben bis zu 3.000 Zeichen; Fragen und bis zu 2.000 Zeichen Wünsche kommen hinzu. `composer_vorschau` lehnt alles über 2.000 Zeichen ab. Der versprochene Ausweg funktioniert damit gerade bei umfangreicheren Antworten nicht. [Hinweisvalidierung](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:919)  
   **Fix:** Antworten verlustfrei getrennt von den weiterhin auf 2.000 Zeichen begrenzten Hinweisen übertragen.

7. **P1 – „Nochmal …“ verliert die neuen Antworten.**  
   O8 ergänzt nur deren Anzeige. Der weiterhin vorhandene Knopf ruft `pComposerNochmal()` auf; diese Funktion übernimmt `eingaben.hinweise`, aber keine `rueckfragen`. Eine Wiederholung eines mit Antworten geschärften Prompts würde damit ohne diese Vorgaben senden. Die gespeicherten aufgelösten Antworten können auch nicht unmittelbar als neue `{nr, antwort}`-Anfrage übernommen werden. [Nochmal-Datenfluss](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:1065)  
   **Fix:** Für „Nochmal“ ausdrücklich einen verlustfreien Rückweg der gespeicherten Antworten definieren und testen.

8. **P1 – Alte Entwürfe können im Speicher bleiben und trotzdem unerreichbar werden.**  
   O5 adressiert Entwürfe mit `eid|fassung|stand`. Ändert sich die gespeicherte Fassung extern, sucht die nächste Darstellung unter dem neuen Stand; der alte Entwurf ist unter keinem beschriebenen Bedienweg mehr erreichbar. Außerdem fehlt die Regel für weitere Eingaben während eines laufenden S6-Speicherns: Eine verspätete Antwort darf weder neuere Eingaben verbergen noch eine inzwischen bewusst gewechselte Ansicht zurücksetzen.  
   **Fix:** Veraltete Entwürfe als sichtbaren Konflikt erhalten und Speicherantworten an Eintrag, Ausgangsstand und eingefrorene Entwurfsrevision binden.

9. **P2 – Die Ein-Stufen-Regel erzeugt einen überraschenden Bedienbruch.**  
   Fragen zu F beantworten → Text ändern → „Als bevorzugt“ erzeugt G → erneut ändern → „Mit Antworten verbessern“ erzeugt H. Danach sind dieselben Antworten wegen zweier Herkunftsstufen ungültig. O3 zeigt sie vor dem Speichern noch als gültig an; erst die Folgeaktion scheitert. Die Einschränkung ist ausdrücklich beschlossen, ihre Auswirkung aber nicht sinnvoll in die Bedienung integriert.  
   **Fix:** Vor dem Speichern prüfen, ob die Folgeaktion den Fragenbezug verliert, und einen klaren Übergang mit erhaltenen Antworten anbieten.

10. **P2 – „Bevorzugte Fassung gewinnt“ gilt weiterhin nur innerhalb der neuesten Runde.**  
    Eine bevorzugte „Bearbeitet …“-Fassung oder das bevorzugte Ergebnis einer älteren Runde gehört nicht zur neuesten Runde. Beim frischen Seitenaufruf zeigt O4 deshalb wieder eine andere, möglicherweise unbearbeitete Fassung. Das widerspricht der Aussage im Review-Log, D6 sei damit geschlossen.  
    **Fix:** Beim erstmaligen Öffnen die gültige bevorzugte Fassung vor der neuesten Runde wählen; nur unmittelbar nach eigener Sendung dieser neuen Runde folgen.

11. **P2 – „In der Arbeitsfläche öffnen“ öffnet nicht zuverlässig den angeklickten Fragen-Beleg.**  
    O8 wählt dessen Bezugsfassung, O3 zeigt jedoch stets die neueste passende Fragen-Runde. Bei zwei Fragen-Belegen zur gleichen Fassung landet der Klick auf den älteren beim neueren. `P.af[eid]` besitzt keine Auswahl für einen bestimmten Fragen-Beleg.  
    **Fix:** Eine bewusste Fragen-Belegauswahl speichern und gegenüber der automatischen Auswahl der neuesten Runde priorisieren.

12. **P3 – Die Begründung zur Sekundenreihenfolge in S7 ist falsch.**  
    Die Sendesperre gilt nur während der Übertragung; zwei schnelle Sendungen können innerhalb derselben Sekunde angenommen werden. Nach O6 können außerdem Composer und Arbeitsfläche unabhängig senden. Die definierte ID-Sortierung ist stabil, bildet dann aber auch eigene Sendungen nicht chronologisch ab.  
    **Fix:** Die Einschränkung ehrlich dokumentieren oder eine feinere serverseitige Startreihenfolge speichern.

Die ergänzten Tests schließen viele alte Lücken. Noch erforderlich sind insbesondere: Unterbrechung zwischen Fassungs- und Herkunftsschreiben, Lesen eines gespeicherten Antwortauftrags nach Löschung seines Fragen-Belegs, veränderte Fragenreihenfolge, nachträglich bearbeitete Herkunftsfassung, Composer-Übergabe über 2.000 Zeichen, „Nochmal“ mit Antworten sowie veraltete Entwürfe und verspätete Speicherantworten.

Die Regel für unveränderte **alte** Auftragshashes ist jetzt klar formuliert. Das neue Reproduzierbarkeitsproblem liegt in S3s widersprüchlicher Lesevalidierung. Ausschließlich statisch geprüft; keine Dateien geändert oder Dienste gestartet.

VERDICT: REVISE
### Antwort Claude (Fassung 3)

Grundsatzänderung statt Einzelreparatur: Die Oberfläche schickt die angezeigten Fragen samt Antworten als
Momentaufnahme `[{prioritaet, frage, antwort}]`; der Server prüft nur die Form. `fragen_beleg` und `{nr, antwort}`
entfallen. Ob Fragen zur gezeigten Fassung passen, ist eine Regel der Oberfläche (Bezugsfassung über eine gültige
Bearbeitet-Kette).
- 1 (Lesevalidierung widersprüchlich): gelöst – keine Verweise mehr, `schaerfen_lesen` prüft nur die Form.
- 2 (S6 absturzsicher/idempotent): Reservierung des Herkunftseintrags vor dem Anhängen (wie
  `_gruppenergebnis_uebernehmen`), Fingerabdruck, Fortsetzen nach Abbruch, beschädigte Herkunftsdatei → 409 ohne
  Schreiben plus `herkunft_fehler`.
- 3 (Herkunft umgeht Standprüfung): `stand` der angelegten Fassung gespeichert, `herkunft_gueltig` nur bei gleichem
  Stand.
- 4 (Antworten an falsche Frage): gelöst – Fragetexte gehen mit; zusätzlich `fragen_hash`, damit Antwortentwürfe bei
  neu ausgeführtem Fragen-Beleg nicht übertragen werden.
- 5 (Wiederholungsweg): „Neu senden“ = bewusst neue Runde mit neuer `anfrage_id`, Hinweisen und Antworten des Laufs;
  Warteschlangen-Wiederholen bleibt im Abschnitt darunter.
- 6 (Composer-Ausweg über 2.000): Antworten getrennt als `P.entwurf.rueckfragen` mit eigenem Kasten.
- 7 („Nochmal“ verliert Antworten): `pComposerNochmal` übernimmt `eingaben.rueckfragen`.
- 8 (unerreichbare Entwürfe, verspätete Antworten): Entwurf je `eid|fassung` mit `von_stand`, sichtbarer Konflikt,
  S6 ohne 409 bei geänderter Quelle (`quelle_geaendert`), Textfeld während Speichern gesperrt, Ansicht nur ohne
  bewussten Wechsel umgestellt.
- 9 (Ein-Stufen-Bruch): Kette beliebiger Länge (≤ 10) mit gültiger Herkunft.
- 10 (Bevorzugt nur in neuester Runde): Vorgabe-Reihenfolge eigene Runde → bevorzugte Fassung (≠ Fassung 1) →
  neueste Runde → Fassung 1.
- 11 (angeklickter Fragen-Beleg): `P.af[eid].fragen` als bewusste Wahl.
- 12 (Sekunden-Begründung): ehrlich als Grenze dokumentiert; Arbeitsfläche folgt der gemerkten eigenen Gruppe.
- Tests um alle genannten Fälle ergänzt.

## Runde 3 — Astra

**Die Vereinfachung ist tragfähig, aber zwei P1-Lücken bleiben.** Eine reine Formprüfung ist hier ausreichend: Fragen und Antworten sind ausdrücklich übergebene Nutzereingaben. Die gespeicherte Momentaufnahme erhält die Reproduzierbarkeit ohne Abhängigkeit vom Fragen-Beleg.

Aus Runde 2 sind die Befunde **1, 3–7 und 9–12 auf Planebene gelöst**. Befund 2 ist bei der Wiederaufnahme noch unvollständig; bei Befund 8 bleibt eine kleinere Unklarheit zur verspäteten Folgeaktion. Keine P0.

1. **P1 – Antworten können beim Wechsel auf eine andere Composer-Basis mitwandern.**  
   O8 leert `rueckfragen` beim **Entfernen** der Basis oder beim Aktionswechsel, nicht beim **Ersetzen** der Basis. Der bestehende Weg „Im Composer schärfen“ ruft direkt `pComposerBasis()` auf. Diese Funktion ersetzt Text und Basis, lässt übrige Entwurfsfelder aber stehen. Beispiel: Antworten aus Eintrag A übernehmen, anschließend Eintrag B im Composer öffnen und senden. Basis und Aktion sind gültig; die neue reine Formprüfung akzeptiert die fremden Antworten. [Bestehender Basiswechsel](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/web/prompts.js:1051)  
   **Fix:** Bei jedem Wechsel von `{id, fassung, stand}` die bisherigen Antworten entfernen; nur ausdrücklich vorgesehene Übernahmen wie „Nochmal“ setzen danach ihre eigene Momentaufnahme.

2. **P1 – S6 prüft bei Wiederaufnahme nicht den bereits vorhandenen Ergebnistext.**  
   Schritt 2 prüft den Request-Fingerprint und gibt bei vorhandener Fassung deren Namen zurück. Es fehlt der Vergleich zwischen deren aktuellem Text und dem Text der wiederholten Anfrage. Nach einer verlorenen Antwort oder einem Abbruch kann die reservierte Fassung inzwischen über den alten Bearbeitungsdialog geändert worden sein. O5 würde dann mit diesem anderen Text weiterarbeiten. Beim Ergänzen eines fehlenden Herkunftsstands könnte dieser sogar fälschlich als ursprüngliches Ergebnis bestätigt werden. Der bestehende Gruppenweg enthält ausdrücklich eine solche Kollisionsprüfung. [Vorhandenes Vorbild](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:452)  
   **Fix:** Vor Wiederverwendung und vor Ergänzung von `stand` den vorhandenen Fassungsstand mit `stand(normalisierter Requesttext)` vergleichen; bei Abweichung 409 ohne Änderung oder Folgeaktion.

Kleinere Restpunkte:

- **P2 – Verspäteter Sendeabschluss:** O5 respektiert einen bewussten Ansichtswechsel beim Speichern; O6 lässt den späteren Sendeerfolg wieder bedingungslos der neuen Gruppe folgen. **Fix:** Dieselbe Prüfung auf zwischenzeitliche Navigation auch im Erfolgs-Rückruf anwenden.
- **P2 – `eigeneRunde` ist zu weit definiert:** O4 nennt die letzte eigene Sendung, also auch „Rückfragen“; die rechte Seite soll aber keiner Fragen-Runde ohne Ergebnisfassung folgen. **Fix:** `eigeneRunde` ausschließlich bei Schärfen-Sendungen setzen; Fragen-Sendungen ändern nur die linke Fragenauswahl.
- **P2 – Herkunft und Cache:** Die Wiederaufnahme kann ausschließlich `herkunft.json` ändern; der vorhandene Eintragscache berücksichtigt nur `prompt.md`. **Fix:** Herkunft außerhalb dieses Caches ergänzen oder ihren Dateistand in die Cache-Gültigkeit aufnehmen. [Cache](/C:/Workstation/Werkzeuge/KI-Zentrale-bau-anzeige/werkstatt/prompts.py:1661)

Für die beiden P1 fehlen noch gezielte Tests: **Antworten aus A → Basis B → Senden** sowie **S6 unterbrochen/Antwort verloren → Ergebnisfassung verändert → gleiche Anfrage erneut**. Die übrigen Ergänzungen schließen die wesentlichen Testlücken der vorigen Runde.

Nur statisch geprüft; keine Dateien geändert und keine Dienste oder Modelle gestartet.

VERDICT: REVISE
### Antwort Claude (Fassung 3.1) und Abschluss

Alle Punkte aus Runde 3 übernommen, ohne Runde 4 (Grenze drei Runden; Astra sah die Vereinfachung als tragfähig,
keine P0, beide P1 mit eindeutigem Einzeiler-Fix):
- P1 Antworten wandern bei Basiswechsel mit: jede Basisänderung (`id`/`fassung`/`stand`, auch `pComposerBasis`)
  leert `P.entwurf.rueckfragen`; nur „Nochmal“ und „Im Composer öffnen“ setzen danach eine eigene Momentaufnahme.
- P1 S6-Wiederaufnahme ohne Textvergleich: vorhandene Fassung muss `stand(normalisierter Text)` haben, sonst 409 ohne
  Änderung und ohne Folgeaktion.
- P2 verspäteter Sendeabschluss respektiert bewussten Wechsel; P2 `eigeneRunde` nur für Schärfen; P2 Cache
  berücksichtigt `herkunft.json`.
- Tests für beide P1 und die P2 ergänzt.

Ergebnis: **nicht APPROVED** – drei Runden REVISE, Rest eingearbeitet und nicht mehr gegengelesen. Abnahme beim Bau
prüft die Punkte aus Runde 3 gezielt.

## Act 3 — Build

Builder gpt-6.1-sol, effort xhigh (Sascha 07.11.2026: „Sol auf xhigh zum bauen falls möglich“), eigener Worktree
`KI-Zentrale-bau-arbeitsflaeche`, Zweig `bau/prompts-arbeitsflaeche`, Start abgekoppelt (WMI, CREATE_BREAKAWAY_FROM_JOB),
Ausgabe nur in Dateien. Thread `01a1c4f3-9d43-7a53-b89b-25210ff38fe3`.

### Round 1 — Codex build
- 10.11.2026, 33 min, 1 Versuch ohne Kapazitätsabbruch, 11.055k Thread-Token, Wochenkontingent 36 → 37 %.
- Gebaut: Server S1–S8 (Aktion „Rückfragen“ mit JSON-Prüfung, `rueckfragen` im Auftrag nach „Hinweise von Sascha“,
  `fassung_bearbeitet` mit herkunft.json, Fingerabdruck nur mit Rückfragen erweitert), Transport aus pComposerSenden
  herausgelöst (pTransportSenden/-Aktionen/-Unklar/-Status), Arbeitsfläche O1–O9, neue
  prompts_arbeitsflaeche_bedienung.js (20 Abläufe).
- Suite von Claude selbst: 511 Tests OK (Baseline 487).

### Claude's verdict (Runde 1)
Diff gelesen, Suite selbst gelaufen, Bedienung im Harness 3897. In Ordnung:
- Raster breit (375/563 px) und schmal (375 px, Reihenfolge dein → rechts → links, kein Querscrollen);
- Fragenkarten mit Priorität, Zähler, Vorschläge und Überspringen;
- „Bearbeitet …“-Fassung mit gültiger Herkunft; „Mit Antworten verbessern“ mit richtigem Auftragsabschnitt;
- Teilfehler mit „Neu senden“; Konsole ohne Fehler.

Befunde:
- F1 (P2): Editor zu niedrig, `.p-fassung > textarea` überstimmt die Regel.
- F2 (P2): Feld „Weitere Wünsche“ 340 px hoch, wegen `.dialog-feld textarea`.
- F3 (P1): Nach einer Composer-Sendung folgt die Arbeitsfläche der neuen Runde nicht (`fest` bzw. `bevorzugt`) –
  Rückschritt gegenüber „Zuletzt gestarteter Auftrag“.
- F4 (P3): Laufzeile der Fragen ohne „Läuft seit …“.
- F5 (P3): Reihenfolge der Fehlermeldung.
- F6 (P3): Sprung zur Fassungsliste.
- K1–K3: Vorgabe für „Fragen stellt“ nicht verfügbar; Sperre ohne sichtbaren Grund; Hinweis auf einen fehlenden Knopf.

→ Nachbesserung über resume (Runde 2).

### Round 2 — Codex fix (resume)
- 10.11.2026, 7 min, 2.366k Thread-Token, Kontingent 37 → 38 %.
- F1/F2 über spezifischere Regeln in `.p-arbeitsflaeche`.
- F3 in pSendungUebernommen: Arbeitsflächen-Zustand auf die neue Runde.
- F4: pLaufanzeige mit Lauftext.
- F5: Meldung vor Grund bei `fehler`.
- F6: Fokus und scrollIntoView der Arbeitsfläche nach erfolgreichem Senden, `scroll-margin-top`.
- K1–K3 wie verlangt.
- 7 neue Abläufe (27 gesamt). Suite 511 OK.

### Claude's verdict (Runde 2)
Diff gelesen, Suite selbst 511 OK. Im Browser auf 3897 geprüft und in Ordnung:
- Editor 260 px (≥ 12 Zeilen) breit und schmal, schmal höchstens 60vh, kein Querscrollen; Wünsche 59 px;
- Composer-Sendung bei fest angezeigter bevorzugter „Bearbeitet“-Fassung → oben die laufende neue Runde, danach deren
  Ergebnis;
- „Läuft seit 12:11 – Fragen werden gestellt …“;
- die konkrete Fehlermeldung des Harness;
- nach „Mit Antworten verbessern“ steht die Arbeitsfläche oben im Bild;
- K2-Hinweis mit „Dorthin wechseln“; K3-Text bei fehlgeschlagenem Lauf;
- keine Konsolenfehler aus prompts.js.

Neuer Befund F7 (P3): Nach „Dorthin wechseln“ und „Status prüfen“ bleibt die alte Fehlerrunde sichtbar, weil die
Navigationsmarke der Sendung veraltet ist (gleich = false → bewusst). → Runde 3 (letzte erlaubte Nachbesserung).

### Round 3 — Codex fix (resume)
- 10.11.2026, 3 min, 1.657k Thread-Token, Kontingent 38 → 38 %.
- Neuer Haken `vorWiederaufnahme` im Arbeitsflächen-Kanal. Er setzt die Navigationsmarke neu, wenn
  „Status prüfen“, „Einreihung fortsetzen“ oder „Als neue Sendung senden“ im gewählten Eintrag geklickt wird und keine
  Anfrage läuft. Der Composer bleibt unverändert.
- Test `sendungNachRueckkehrWiederaufnehmen` deckt alle drei Knöpfe ab, je für Schärfen, Rückfragen und den Wechsel
  während der Antwort. Insgesamt 28 Abläufe.

### Claude's verdict (Runde 3, Abnahme)
- Diff gelesen.
- Suite: Der erste Lauf war rot, 1 Fehler in `test_paralleler_doppelpost_einreihung_dedupliziert` mit PermissionError 13
  „Zugriff verweigert“ im Arbeitsfaden. Der Test ist unverändert. Einzeln lief er 8 von 8 Mal grün, der zweite volle Lauf
  mit 511 Tests war OK (skipped=1). Wertung: Windows-Dateisperre, offen als Wackeltest.
- Im Browser auf 3897 nachgestellt: X „Neu senden“ → Bestätigung verloren → Y → „Dorthin wechseln“ → „Status prüfen“.
  Danach zeigt die Arbeitsfläche die neue fertige Runde (bewusst false, runde = eigeneRunde). Keine Konsolenfehler.
- **Abgenommen.**

Bilanz Act 3:
- Gesamtdauer Sol 43 min in 3 Läufen (33 + 7 + 3), Kontingent 36 → 38 %.
- 2 Nachbesserungsrunden. 10 Befunde aus der Abnahme behoben, davon 1 × P1, 2 × P2 und 7 × P3/Kleinigkeiten.
- Keine Abweichung vom Spec gemeldet.

## Lehre aus diesem Lauf
- Zeit kostete: Die Suite belegt mit `test_abnahme_prompts.py` selbst Port 3897. Das eigene Harness muss also vor jedem
  Suite- oder Sol-Lauf gestoppt und danach neu gestartet werden. Außerdem zeigte der versteckte Browserbereich Breite 0,
  darum vor Layoutmessungen eine feste Viewportgröße setzen.
- Ändert sich: codex-build Schritt 3/5 bekommt den Satz „Harness vor Suite- und Builder-Läufen stoppen, wenn die Suite
  denselben Port nutzt“. Sonst keine Vorlage.
