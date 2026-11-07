# Review-Log: Reiter „Prompts“ in der Werkstatt

Akt 1 (Interview) abgeschlossen 06.11.2026, Plan mit Sascha festgezurrt (sechs Entscheidungen: Ablage, Sammlung,
Belege, Schärfen, Eingaben, Umfang). Plan: `SPEC-prompts.md`. MAX_ROUNDS=3 (Runde 3 nur bei offenen P0/P1).
Gegenleser Codex Astra xhigh, read-only.

Reviewer: gpt-6-astra (fest), Denkstufe xhigh (fest); Konfig-Standard gpt-6.1-sol; codex-cli 0.166.0-alpha.6; Thread 01a1b19b-84be-7f42-a767-0c0190ad22ac. Runde 1 lief 06.11.2026 17:05–17:15.

## Runde 1 – Codex Astra: REVISE (20 Punkte)

**Der Plan braucht wesentliche Korrekturen vor der Umsetzung.** Die sechs Grundentscheidungen bleiben dabei erhalten. Ich habe ausschließlich gelesen und kleine Gegenproben im Arbeitsspeicher ausgeführt; keine Dateien geändert.

1. **P0 – Die vorgesehene Pfadprüfung begrenzt den tatsächlichen Dateizugriff nicht.**  
   [`quellen.liegt_in()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/quellen.py:28) normalisiert lediglich Pfadnamen. Eine Junction unter dem erlaubten Ordner kann auf ein verbotenes Ziel zeigen und besteht trotzdem. Das betrifft Lesen, Belegzugriff und Schreiben; Windows-Sonderpfade und alternative Datenströme sind ebenfalls nicht geregelt.  
   **Korrektur:** Einen gemeinsamen Resolver verwenden, der tatsächliche Ziele beziehungsweise vorhandene Eltern auf erlaubte Wurzeln prüft und Sonderpfade sowie Datenströme ablehnt.

2. **P0 – „Unter dem erlaubten Ordner“ macht `os.startfile` nicht sicher.**  
   [Die Sicherheitsregel](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:255) erlaubt grundsätzlich beliebige Dateien innerhalb der Wurzeln. Eine handgeänderte `html`-Kopfzeile könnte damit auf eine `.cmd`, `.hta` oder `.lnk` zeigen; „Im Browser öffnen“ würde dann etwas anderes starten.  
   **Korrektur:** Öffnen ausschließlich über serverseitig zugeordnete Artefakte erlauben: echte Ordner, die exakte Sammlungsdatei, Markdown-Belege und zugehörige `.html`-Dateien mit geprüfter Endung.

3. **P0 – `RLock` und `os.replace` verhindern keine verlorenen Handänderungen.**  
   Ablauf: Werkstatt liest → Editor speichert eine Notiz → Werkstatt ersetzt die Datei aus ihrem alten Stand. Der Kastenhash erkennt Änderungen außerhalb des Kastens ohnehin nicht. Für Kopfzeilen sowie Urteil/Notiz fehlt ein eigener Konfliktstand. Eine Sperre pro neu erzeugter `Eintrag`-Instanz würde außerdem nicht einmal konkurrierende HTTP-Anfragen schützen.  
   **Korrektur:** Gemeinsame pfadbezogene Sperren und Dateirevisionen für sämtliche Änderungen festlegen; externe Schreibrennen am Commit absichern oder die verbleibende Schutzgrenze ausdrücklich benennen.

4. **P1 – Vorschau, Start und tatsächliche Ausführung sind nicht an denselben Inhalt gebunden.**  
   Das vorgeschlagene Auftragsschema enthält Referenzen und Hashes, aber keinen Fassungs-Snapshot. Die vorhandene [`_ausfuehren()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:930) liest Quellen erst beim Ausführen neu. Zwischen zwei A/B-Läufen können deshalb Fassung, Felddatei oder Skill wechseln. Später fehlt zudem der ursprüngliche Vorlagentext für „Original/neu“; aus eingesetzten Werten lässt er sich nicht zuverlässig rekonstruieren.  
   **Korrektur:** Beim bestätigten Start Fassung, Feldwerte, Skilltext und Profile einmal erfassen, gegen die Vorschau prüfen und denselben unveränderlichen Auftrag samt Herkunft im Beleg erhalten.

5. **P1 – Der Transkriptverweis ist nicht eindeutig genug.**  
   [`transkripte_auflisten()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:615) unterscheidet `ordner` und `transkript`: Unter einem Videoordner können mehrere Transkriptläufe liegen. Der Beleg nennt nur `ordner`. „Unveränderlich“ wird außerdem technisch nicht erzwungen; ein Hash erkennt Änderungen, stellt den alten Inhalt aber nicht wieder her.  
   **Korrektur:** Den exakten Lauf beziehungsweise Dateipfad und den Hash des tatsächlich verwendeten Transkripttexts speichern; fehlende oder geänderte Quellen beim Wiederholen ausdrücklich behandeln.

6. **P1 – Gleichzeitige Ergebnisse können sich überschreiben; Wiederholen kann doppelt übernehmen.**  
   Das Vorbild [`_ablegen()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:968) verwendet `exists()` und danach `open(..., 'w')`. Zwei Arbeiter können denselben freien Namen wählen. Für Markdown, HTML, angehängte Fassung und Warteschlangenstatus fehlt außerdem eine Wiederanlaufregel: Ein Absturz nach dem Anhängen kann beim Wiederholen eine zweite Fassung erzeugen.  
   **Korrektur:** Dateinamen exklusiv reservieren, zusammengehörige Artefakte über eine Auftrags-ID verbinden und Ablage sowie Übernahme anhand dieser ID wiederholbar ohne Duplikate machen.

7. **P1 – „Codex ohne Werkzeuge“ ist durch den vorhandenen Start nicht gewährleistet.**  
   [`Codex.ausfuehren()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:115) setzt `read-only`, aber keine erkennbare Werkzeugsperre. [PLAN.md](/C:/Workstation/Werkzeuge/KI-Zentrale/PLAN.md:192) begründet deshalb ausdrücklich den bisherigen Rahmen „keine Dateien/Werkzeuge/Gedächtnis“. Diesen Rahmen entfernt der neue Testweg, während die Vorschau weiterhin Werkzeugfreiheit verspricht. Gerade Sammlungsprompts enthalten Datei- und Rechercheaufträge.  
   **Korrektur:** Codex mit seinen tatsächlichen Fähigkeiten kennzeichnen; eine garantierte Werkzeugfreiheit nur nach technisch geprüfter Deaktivierung versprechen.

8. **P1 – Die Umstellung der gemeinsamen Warteschlange ist unvollständig beschrieben.**  
   Alle acht vorhandenen Einträge haben kein `art`. [`stand()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:755) liefert für neue `FELDER` zunächst `None`; ein strikter Zusammenfassungsfilter blendet diese Einträge aus. Auch unverändertes `anlegen()` erzeugt weiterhin Einträge ohne `art`. Zusätzlich zählt [`messungen.zusammenfassung()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/messungen.py:116) sämtliche fertigen Aufträge und würde künftig Prompt-Tests und Schärfen einrechnen.  
   **Korrektur:** Fehlendes `art` zentral bei alten und neuen Aufträgen normalisieren und sämtliche Verbraucher einschließlich Messungen nach Auftragsart trennen.

9. **P1 – Abgebrochene Aufträge verschwinden aus der vorgesehenen Bedienung.**  
   Die Spec nennt für die sichtbare Warteschlange Wartend/Läuft/Fehler. Beim Dienststart setzt der vorhandene Code jedoch alle wartenden und laufenden Aufträge auf `abgebrochen`. Genau diese Aufträge brauchen „Wiederholen“. Außerdem beendet [`_Lauf.http()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:677) beim Abbrechen nur das Warten; die Modellanfrage läuft im Hintergrund weiter.  
   **Korrektur:** `abgebrochen` sichtbar und wiederholbar halten sowie Ergebnisverwerfen von tatsächlichem Rechenende unterscheiden, bevor weitere lokale Läufe nachrücken.

10. **P1 – `_zerlegen` ist kein geeigneter allgemeiner Kastenparser.**  
    Die Gegenprobe zeigt: Fehlt der Abschluss von Fassung 1, nimmt der Parser Überschrift und Inhalt von Fassung 2 mit auf. Er akzeptiert außerdem `~~~python` als Anweisungskasten. Abschnittsgrenzen werden vorab auch innerhalb von Kasteninhalten gesucht. „Ersten Kasten nehmen“ schützt hier nicht vor falscher Zuordnung.  
    **Korrektur:** Einen Parser mit explizitem Zaunzustand und eindeutigen Blockgrenzen bauen; mehrdeutige oder unvollständige Dateien anzeigen, aber nicht automatisch bearbeiten.

11. **P1 – Schreiben und Lesen haben unterschiedliche Zaunregeln.**  
    Belege sollen verlängerte Zäune bekommen; vorhandener Parser und Schärfen-Auswertung erwarten dagegen feste `~~~`-Grenzen. Im Schärfen-Auftragsblock werden Vorlage und Modellantwort ebenfalls mit festen Zäunen eingebettet, obwohl das Material eigene Zäune enthalten kann. Damit ist der Rundlauf nicht definiert.  
    **Korrektur:** Eine gemeinsame Zaunimplementierung für Belege, eingebettetes Material und Antwortauswertung festlegen und verschachtelte sowie verlängerte Zäune im Rundlauf testen.

12. **P1 – Namen sind weder eindeutige Identitäten noch sichere Windows-Dateinamen.**  
    Verifiziert: `dateiname('CON')` bleibt `CON`; `A/B` und `A:B` werden beide `A B`. `_Sammlung` ist nicht reserviert. Schattenordner können außerdem durch Kürzung oder Groß-/Kleinschreibung kollidieren. Bei Sammlungseinträgen verschiebt ein neu eingefügter erster Kasten die Nummern und ordnet alte Belege möglicherweise einem anderen Prompt zu.  
    **Korrektur:** Anzeigenamen von eindeutigen Ablagekennungen trennen, Windows-Gerätenamen und `_Sammlung` reservieren und uneindeutige Sammlungszuordnungen als Konflikt behandeln.

13. **P1 – Automatische Schärfen-Übernahme prüft nicht die entscheidenden Eigenschaften.**  
    `text_pruefen()` prüft Länge, Leere und Zaunzeilen, aber keinen Platzhaltererhalt. Eine Antwort mit zwei Kästen wird laut Plan teilweise übernommen, obwohl genau einer verlangt wurde. Für einen vorhandenen, aber ungültigen Kasten fehlt ein Ergebniszustand. Zusätzlich akzeptiert `name_pruefen()` nachweislich ein eingebettetes `\r`.  
    **Korrektur:** Vor Übernahme genau einen vollständigen gültigen Kasten, erhaltene Platzhalter und steuerzeichenfreie Namen prüfen; sonst die vollständige Antwort als nicht übernommenen Vorschlag erhalten.

14. **P1 – Die Kontextanzeige kann die falsche lokale Variante prüfen.**  
    [`Lokal.katalog()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:517) verwendet bei Strata die Standardvariante der Konfiguration, während die Ausführung die tatsächlich geladene Modellkennung abfragt. Ein Wechsel zwischen 128K und 256K kann somit eine falsche Freigabe oder Ablehnung erzeugen. Die reine Vorschauprüfung schützt außerdem keinen später gestarteten Auftrag.  
    **Korrektur:** Kontextprüfung und Beleg auf die tatsächlich geladene Variante beziehen und unmittelbar vor Ausführung erneut prüfen.

15. **P1 – Die Platzhalterregel verändert potenziell gültigen Code und Markdown.**  
    Gegenproben erkennen `[red, blue]`, `\\[Name]`, `[Text][ref]` und `- [x]` als Felder. Eine Regel zum ausdrücklich wörtlichen Beibehalten fehlt. Die aktuelle Sammlung enthält außerhalb des Werkstatt-Abschnitts zudem keinen exakten `[Transkript]`-Platzhalter, wohl aber `[Transkript folgt]`; die besondere Transkriptauswahl greift dort nicht.  
    **Korrektur:** Erkannte Felder vor dem Start bestätigen beziehungsweise als wörtlichen Text markieren lassen und die Transkriptquelle unabhängig vom exakten Feldnamen zuordnen können.

16. **P1 – Die zugesagte Loghygiene gilt im wiederverwendeten Fehlerpfad nicht.**  
    [`Claude.ausfuehren()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:180) übernimmt bei unerwarteter Antwort Teile von Ausgabe oder Fehlertext in Exceptions. [`_schleife()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:919) und die Serverroute protokollieren Exceptions beziehungsweise Tracebacks. Dadurch können Modellantworten und damit übernommene Eingabeinhalte im Log landen.  
    **Korrektur:** Für diese Pfade strukturierte Fehlercodes und bereinigte Meldungen protokollieren; rohe Anbieterantworten nicht an die allgemeine Protokollierung weiterreichen.

17. **P1 – Die neue JavaScript-Datei wird ohne zusätzliche Registrierung nicht ausgeliefert.**  
    [`Anfrage.statisch`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/server.py:308) ist eine explizite Freigabeliste. Eine neue Datei und ein `<script>`-Tag reichen nicht; `/prompts.js` bekäme 404.  
    **Korrektur:** Die statische Route ausdrücklich in Scheibe 1 aufnehmen und das Laden des Reiters ohne Konsolen- oder Netzwerkfehler abnehmen.

18. **P2 – `stopPropagation()` beim Drop hinterlässt den globalen Ablagezustand.**  
    [`einrichtenAblegen()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/app.js:158) aktiviert beim `dragenter` das Overlay und setzt es beim dokumentweiten `drop` zurück. Stoppt das Promptfeld nur den Drop, erreicht dieser den Rücksetzcode nicht; Overlay und Markierung können stehen bleiben.  
    **Korrektur:** Die Dateiablegebehandlung zentral um das Promptziel erweitern oder sämtliche beteiligten Drag-Zustände ausdrücklich zurücksetzen.

19. **P2 – Der vorhandene Markdown-Renderer eignet sich nicht unverändert für Codingprompts.**  
    [`markdown()`](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/web/zusammenfassung.js:32) kennt keine Codezäune und entfernt führende Einrückungen durch `trim()`. Code erscheint dadurch als normaler Absatz; Markdown innerhalb eines Codebeispiels wird formatiert.  
    **Korrektur:** Fassungen und gesendete Texte als unveränderten Text darstellen und für Antworten einen sicheren Renderer mit Codeblock-Unterstützung verwenden.

20. **P1 – Die Abnahme lässt die wesentlichen Fehlerszenarien offen.**  
    Die vorgesehenen Tests prüfen überwiegend Einzelaufrufe und erfolgreiche Ablage. Es fehlen insbesondere externe Änderungen während des Schreibens, gleichzeitige gleichnamige Ergebnisse, Neustart nach Teilablage, alte Warteschlangeneinträge, Pfadumleitungen und gefährliche Öffnen-Ziele. Die Herkunftsprüfung weist fremde Browser-Origins in meiner Gegenprobe ab; dieses Verhalten muss bei den neuen Routen erhalten bleiben.  
    **Korrektur:** Diese Fälle als verbindliche Abnahmekriterien auf die drei bestehenden Scheiben verteilen und Fehlerzustände mit Fake-Anbietern deterministisch prüfen.

VERDICT: REVISE

### Claude (Runde 1)

Alle 20 Punkte am Code nachgeprüft; alle übernommen, zwei davon anders eingeordnet.

- 1 (Pfadprüfung): übernommen als `pfad_erlaubt` mit `realpath` auf Pfad und Wurzeln, Verbot von `\\?\`, `\\.\`,
  UNC und Datenströmen; Junction-Test mit `_winapi.CreateJunction`. Eingeordnet als P1, nicht P0: Dienst nur auf
  127.0.0.1, POST nur mit Werkstatt-Herkunft, Junctions legt nur Sascha selbst an. Trotzdem billig, darum drin.
- 2 (`os.startfile`): übernommen; `oeffnen` baut Pfade nur serverseitig aus Kennung + Art + Dateiname ohne
  Trennzeichen, Endung `.md`/`.html`, nie aus Kopfzeilen; `html: ja` statt Pfad im Kopf.
- 3 (Sperre/Revisionen): übernommen; modulweite Sperre, jede Änderung liest frisch unter der Sperre und tauscht nur
  den Zielblock (Muster `Sammlung.speichern`, das Astra im Plan nicht erkennen konnte, weil ich es nicht benannt
  hatte); `kopf_stand` für Kopf und Beleg-Urteil; verbleibendes Millisekundenfenster ausdrücklich benannt.
- 4 (Momentaufnahme): übernommen; Beleg wird beim Einreihen mit „Gesendet“ geschrieben, `_ausfuehren` sendet daraus;
  Vorschau liefert `inhalt_stand`, `testen` prüft ihn (409 bei Abweichung); Skilltext als Momentaufnahme je Lauf.
- 5 (Transkript): übernommen; exakter Laufordner + Datei + SHA-256 des Texts, Abweichung → `fehler`.
- 6 (Namen/Wiederholen): übernommen; `open(…, 'x')` unter der Sperre, Dateiname = Auftragskennung für `.md`/`.html`,
  Wiederholen nutzt denselben Beleg, Anhängen prüft vorher auf gleichen Stand.
- 7 (Codex ohne Werkzeuge): übernommen; ehrliche Kennzeichnung „Sandbox nur lesend mit Werkzeugen“ in Vorschau und
  Auftragsblock; Häkchen „Rahmen der Zusammenfassung voranstellen“ (Vorgabe aus) als bewusste Option.
- 8 (`art`): übernommen; Normalisierung in `__init__` und `anlegen`, Filter in Zusammenfassung und Messungen.
- 9 (abgebrochen): übernommen für die Anzeige. Das Weiterrechnen nach Abbruch (`_Lauf.http`) ist vorbestehend und
  nicht Teil dieses Vorhabens; als bekannte Grenze benannt, Umbau ausdrücklich außerhalb von Version 1.
- 10/11 (Parser, Zäune): übernommen; neuer Parser mit Zaunzustand für alles Neue, `_zerlegen` bleibt beim
  Werkstatt-Abschnitt; eine Schreibfunktion mit verlängertem Zaun; Rundlauftests; Material im Schärfen-Auftrag mit
  verlängertem Zaun, Fassungen bleiben `~~~text`, weil `text_pruefen` `~~~`-Zeilen ausschließt.
- 12 (Kennungen): übernommen; Ordnername = stabile Kennung, Gerätenamen, `_`-Präfix und Groß/Klein geregelt;
  Sammlung: `eintrag.json` mit Stand, Neuzuordnung über Stand, Konflikt bei mehreren Kandidaten.
- 13 (Schärfen-Übernahme): übernommen; genau ein Kasten, `text_pruefen`, Platzhaltererhalt (neue erlaubt),
  Steuerzeichenverbot, Zustand `ungültig (<Grund>)`.
- 14 (Kontext der Variante): übernommen; `Lokal.kontext_geladen`, Nachprüfung vor dem Senden.
- 15 (Platzhalter): übernommen; Häkchen „wörtlich lassen“ je Feld, Transkriptwahl für jedes Feld.
- 16 (Log): übernommen; Fehlerklasse + 80 Zeichen im Log, Volltext nur in `meldung`; Routen ohne Traceback-Log.
- 17 (`statisch`): übernommen, Scheibe 1 mit Abnahme „ohne Konsolen-/Netzwerkfehler“.
- 18 (Drop): übernommen; zentrale Erweiterung von `einrichtenAblegen`, Browser-Dateien ohne Pfad als Text.
- 19 (Markdown): übernommen; Fassungen/Gesendet als `<pre>`, `markdown()` bekommt Zaunblöcke.
- 20 (Abnahme): übernommen; Fehlerfälle als Abnahmepunkte auf die Scheiben verteilt (Fremdänderung, gleiche Namen,
  Neustart, Alt-Einträge, Junction, gefährliche Ziele, Herkunft).

## Runde 2 – Codex Astra: REVISE (11 Punkte, 10 × P1, 1 × P2)

**Der Plan hat weiterhin wesentliche P1-Probleme.** Die neue Spec und „Claude (Runde 1)“ sind vollständig gelesen. Der Abgleich mit dem vorhandenen Code und Gegenproben im Arbeitsspeicher ergibt folgende Einordnung.

| Punkte aus Runde 1 | Ergebnis |
|---|---|
| 1, 2, 5, 7, 8, 13, 15, 17, 18, 19 | Auf Planebene ausreichend behandelt |
| 3 | Interne Sperre und Konfliktstände ergänzt. Das verbleibende Rennen mit externen Editoren ist ausdrücklich benannt |
| 9 | Anzeige abgebrochener Aufträge gelöst. Weiterrechnen nach HTTP-Abbruch als bestehende Grenze abgegrenzt |
| 4, 6, 10, 11, 12, 14, 16 | Weiterhin teilweise offen, siehe unten |
| 20 | Abnahme erweitert. Die folgenden Fehlerfälle fehlen noch beziehungsweise widersprechen ihren Erwartungen |

1. **P1 – Die Momentaufnahme kann nach dem Einreihen unbemerkt verändert werden.**  
   Der Worker liest „Gesendet“ erneut aus dem handeditierbaren Beleg. `inhalt_stand` wird beim Start geprüft, anschließend aber weder im beschriebenen Warteschlangeneintrag gespeichert noch unmittelbar vor dem Senden verglichen. Eine Handänderung des Belegs verändert dadurch den Auftrag. Ebenso kann eine Änderung während des Modelllaufs nachträglich einen anderen Text als „Gesendet“ ausweisen. Damit bleibt Punkt 4 offen. [Spec, Zeile 184](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:184)

   **Korrektur** Den Hash des vollständigen Auftrags dauerhaft festhalten, vor dem Senden prüfen und die Ergebnisablage an genau diesen Stand binden.

2. **P1 – Das neue Belegformat lässt sich nicht eindeutig zurück in einen Auftrag verwandeln.**  
   Die Ausführung ersetzt eine menschenlesbare Transkriptmarkierung im Text. Dieselbe Zeichenfolge darf aber bereits wörtlich in einem Prompt oder einer Felddatei stehen. Mit mehreren Transkriptfeldern und wiederholten Platzhaltern wird die Zuordnung zusätzlich unklar. Außerdem fehlen die ursprüngliche Vorlage und einzelne Dateifeldwerte als eigenständige Daten. Ein Hash und der zusammengefügte Text reichen für deren spätere Rekonstruktion nicht aus. [Spec, Zeile 168](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:168)

   **Korrektur** Originalfassung, Feldwerte und Transkriptverweise strukturiert im bestehenden Beleg speichern und daraus mit der einmaligen Platzhalterersetzung den Auftrag rekonstruieren.

3. **P1 – Wiederholen nach einem Absturz ist weiterhin nicht duplikatfrei.**  
   Der konkrete Fehlerablauf lautet jetzt so. Antwort A wird erzeugt und als Fassung angehängt. Vor `ergebnis: übernommen` stürzt der Dienst ab. Wiederholen sendet erneut ans Modell und erhält Antwort B. Deren Stand unterscheidet sich von A, deshalb wird eine weitere Fassung angehängt. Die Prüfung auf gleichen Text schützt nur bei identischen Antworten. Gleichzeitig ersetzt B die Antwort im bisherigen Beleg, wodurch der Nachweis für A verloren geht. [Spec, Zeile 317](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:317)

   **Korrektur** Die Antwort vor der Übernahme dauerhaft speichern und die Übernahme anhand der Auftragskennung abschließen, wobei die Wiederherstellung nach einem Absturz ohne erneuten Modellaufruf erfolgt.

4. **P1 – Beleg und Warteschlange erhalten keinen vollständigen gemeinsamen Zustandsablauf.**  
   Beschrieben sind die Aktualisierung nach erfolgreicher Ausführung und beim Dienstneustart. Der vorhandene Code setzt Fehler, normalen Abbruch, Wiederholen und Laufbeginn jedoch ausschließlich im Warteschlangeneintrag. Ein fehlgeschlagener Transkriptcheck kann deshalb einen Beleg mit `zustand: wartet` hinterlassen. Zusätzlich bleibt nach einem Absturz zwischen Beleganlage und Queue-Speicherung ein wartender Beleg ohne ausführbaren Auftrag zurück. [Spec, Zeile 193](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:193), [vorhandene Zustandswechsel](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:868)

   **Korrektur** Für sämtliche Zustandswechsel die Aktualisierung beider Dateien sowie eine Wiederherstellungsregel für unvollständige Einreihung und Ablage festlegen.

5. **P1 – Die geplante Kontextbestimmung kann 128K und 256K weiterhin nicht unterscheiden.**  
   `_tatsaechliches_modell()` liefert nur die Modellkennung. In der echten Konfiguration verwenden sowohl die beiden IQ3-Varianten als auch die beiden Q4-Varianten jeweils denselben Modellnamen für unterschiedliche Kontextgrößen. Die „passende Variante“ lässt sich damit nicht eindeutig bestimmen. Die Zentrale liest hierfür bereits `max_context` aus `/health`. [Spec, Zeile 280](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:280), [Varianten](/C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/config.json:251), [vorhandene Erfassung](/C:/Workstation/Werkzeuge/KI-Zentrale/zentrale/erfassung.py:348)

   **Korrektur** Strata und PolyStrata über ihren tatsächlichen `/health`-Kontext prüfen, NInfer ausdrücklich berücksichtigen und den beim Senden verwendeten Kontext im Beleg festhalten.

6. **P1 – Die Logkorrektur schreibt weiterhin Modellinhalt ins Log.**  
   „Fehlerklasse + erste 80 Zeichen“ enthält weiterhin den Anfang des Fehlertexts. Der kann unmittelbar eine Modellantwort enthalten. Die Gegenprobe mit `RuntimeError('MODELLANTWORT_MARKIERUNG …')` schreibt die Markierung vollständig ins geplante Logformat. Damit widerspricht die Implementierungsvorgabe sowohl der zugesagten Loghygiene als auch ihrem eigenen Abnahmetest. [Spec, Zeile 129](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:129), [Abnahme, Zeile 388](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:388)

   **Korrektur** Ausschließlich Fehlerklasse, feste Fehlercodes und freigegebene Metadaten protokollieren und die ersten 80 Zeichen vollständig streichen.

7. **P1 – Der gemeinsame Parser vermischt Blockerkennung und unterschiedliche Dateiregeln.**  
   Er soll alle Formate bedienen, erkennt aber nur Tilde-Zäune und überspringt `json` sowie `html`. Genau diese Blöcke werden für Eingaben und HTML-Ergebnisse gebraucht. Außerdem gilt die Regel „ungeschlossener Zaun macht die Datei mehrdeutig“ auch für Belege. Eine abgeschnittene Modellantwort mit offenem Codeblock kann dadurch einen ansonsten gültigen Beleg unlesbar machen. Die Rohantwort steht bisher ungekapselt am Dateiende. [Spec, Zeile 95](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:95), [Belegformat](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:175)

   **Korrektur** Den gemeinsamen Parser alle Blocktypen samt Backtick-Zäunen erkennen lassen und die Gültigkeitsregeln getrennt für Promptdatei, Beleg und Modellantwort anwenden.

8. **P1 – Der verlängerte Zaun berücksichtigt eingerückte Abschlusszeilen nicht eindeutig.**  
   Der Schreiber sucht laut Regel nach Tilde-Läufen am Zeilenanfang. Ein Inhalt mit `   ~~~` beginnt mit Leerzeichen und kann deshalb einen dreistelligen Außenzaun erhalten. Ein Leser nach der angekündigten CommonMark-Regel behandelt diese eingerückte Zeile dennoch als Abschluss. Das betrifft besonders Material und Dateiinhalte, für die `text_pruefen()` keine solche Zeile ausschließt. [Spec, Zeile 95](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:95)

   **Korrektur** Für Leser und Schreiber dieselbe Abschlusszaunprüfung einschließlich Einrückung verwenden und den Rundlauf mit null bis drei führenden Leerzeichen testen.

9. **P1 – Die Sammlungszuordnung bleibt bei kombinierten Handänderungen falsch.**  
   Ausgangspunkt ist ein getesteter Kasten A an Position 1. Sascha fügt davor X ein und bearbeitet gleichzeitig A. Der alte Hash findet sich danach nirgends. Der beschriebene Fallback „sonst seit dem Test geändert“ kann den alten Beleg von A nun X an Position 1 zuordnen. Der Test mit einem lediglich davor eingefügten Kasten deckt diesen Fall nicht ab. [Spec, Zeile 210](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:210)

   **Korrektur** Bei fehlendem eindeutigen Hash-Treffer die Zuordnung als ungeklärt behandeln und eine positionsbasierte Übernahme nur nach ausdrücklicher Zuordnung erlauben.

10. **P2 – Der Kopfstand erfasst laut Definition den Titel nicht.**  
    `kopf_stand` wird über die Schlüssel-Wert-Kopfzeilen gebildet, während der Titel separat als erste `#`-Überschrift definiert ist. Ändert ein Editor nur den Titel, kann ein bereits geöffneter Kopfdialog mit unverändertem Hash den alten Titel zurückschreiben. Das liegt außerhalb des bereits benannten Millisekundenrennens. [Spec, Zeile 89](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:89)

    **Korrektur** Den Titel und sämtliche gemeinsam bearbeitbaren Kopffelder in `kopf_stand` aufnehmen.

11. **P1 – Die Abnahme muss die tatsächlichen Fehlerabläufe prüfen.**  
    „Wiederholen nach Anhängen“ kann mit einer stets identischen Fake-Antwort bestehen, obwohl Punkt 3 weiterhin auftritt. Der Kontexttest braucht zwei Varianten mit identischem Modellnamen. Der Logtest muss die vertrauliche Markierung an den Anfang der Exception setzen. Für Belegänderung, verwaiste Einreihung und Einfügen plus Bearbeiten eines Sammlungskastens fehlen passende Fälle. [Spec, Zeile 372](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:372)

    **Korrektur** Diese konkreten Gegenbeispiele einschließlich gezielter Abstürze zwischen den einzelnen Schreibschritten als verpflichtende Abnahme ergänzen.

VERDICT: REVISE

### Claude (Runde 2)

Alle 11 Punkte übernommen; Punkt 9 mit einer eigenen Regel für den Normalfall.

- 1 (Momentaufnahme veränderbar): übernommen, grundsätzlicher gelöst: Es gibt keinen gespeicherten „Gesendet“-Text
  mehr. Der Beleg trägt Fassung und Eingaben, `auftrag_bauen` ist eine reine Funktion, `gesendet_stand` liegt in der
  Warteschlange und wird vor dem Senden gegen den neu gebauten Auftrag geprüft (Code `beleg_geaendert`); Änderung
  während des Laufs → Antwort trotzdem gespeichert, `hinweis` gesetzt.
- 2 (Beleg nicht eindeutig rückführbar): übernommen durch dieselbe Umstellung: Fassung, Feldwerte (Dateiinhalte als
  `wert`) und Transkriptverweise liegen strukturiert vor, der Auftrag wird daraus deterministisch gebaut; keine
  Markierung im Text, mehrere Transkriptfelder sind eindeutig.
- 3 (Wiederholen nach Absturz): übernommen; Antwort wird vor jeder Nacharbeit gespeichert, Wiederholen mit
  vorhandener Antwort ruft kein Modell, Übernahme findet die Fassung über den Stand; Fake-Anbieter mit Zähler.
- 4 (Zustandsablauf): übernommen als Tabelle aller Übergänge mit `beleg_zustand`, Wiederherstellung beim Start
  (Beleg ohne Auftrag → abgebrochen, Wiederholen reiht aus dem Beleg neu ein; Auftrag ohne Beleg → fehler).
- 5 (Kontext 128K/256K): übernommen; `kontext_geladen` über `/health` (`max_context`, `model`) für Strata und
  PolyStrata, `/api/ps` für Ollama, Katalogwert für NInfer (gekennzeichnet); Beleg trägt `kontext` und
  `kontext_quelle`; Nachprüfung vor dem Senden; Test mit zwei Varianten gleichen Namens.
- 6 (Log): übernommen; kein Fragment des Fehlertexts mehr, nur Klasse, fester Fehlercode und Metadaten; Markierung
  im Test am Anfang der Ausnahme.
- 7 (Parser): übernommen; `bloecke` erkennt Tilde- und Backtick-Zäune mit Kennung, die Gültigkeitsregeln sitzen bei
  den Aufrufern (prompt.md, Beleg, Antwort, Sammlung); Antwort im Beleg in einem Block mit verlängertem Zaun.
- 8 (eingerückter Abschluss): übernommen; gemeinsame `_zaunlaenge` mit bis zu drei führenden Leerzeichen für Leser
  und Schreiber, Rundlauftest mit 0–3 Leerzeichen.
- 9 (Sammlungszuordnung): übernommen für Überschriften mit mehreren Kästen (ungeklärt, Knopf „Diesem Kasten
  zuordnen“, nichts automatisch). Anders gesehen für Überschriften mit genau einem Kasten (35 von 38): dort ist die
  Zuordnung auch ohne Stand-Treffer eindeutig, und eine Nachfrage nach jeder Handbearbeitung wäre im Alltag falsch;
  Anzeige „seit dem Test geändert“ bleibt. Beide Fälle als Abnahme.
- 10 (`kopf_stand` ohne Titel): übernommen.
- 11 (Abnahme): übernommen; je Aufruf andere Fake-Antworten, Varianten gleichen Namens, Markierung am Anfang,
  Belegänderung nach Einreihen, verwaiste Einreihung, Einfügen plus Bearbeiten, Absturz-Injektion zwischen den
  Schreibschritten.

## Runde 3 – Codex Astra: REVISE (4 Punkte, alle P1) – Rundengrenze erreicht

**Es bleiben vier P1-Probleme.** Die Prüfung war ausschließlich lesend.

| Punkte aus Runde 2 | Bewertung |
|---|---|
| 3, 5, 6, 8, 10 | Auf Planebene gelöst |
| 1 | Prüfung vor dem Senden gelöst. Änderungen während des Laufs sind als Grenze mit Warnhinweis dokumentiert |
| 2 | Strukturierte Eingaben für Prompt-Tests gelöst. Beim Schärfen bleibt eine Lücke |
| 4, 7 | Zustandsablauf und Parser deutlich präzisiert, aber mit widersprüchlichen Regeln für fehlende Antworten |
| 9 | Der Mehrkastenfall ist abgesichert. Die neue Einkasten-Ausnahme erzeugt einen anderen Zuordnungsfehler |
| 11 | Die geforderten Gegenproben sind aufgenommen. Die folgenden Fälle brauchen ergänzende Abnahmen |

1. **P1 – Belege ohne Antwort haben widersprüchliche Gültigkeitsregeln.**  
   Der Parser verlangt die Pflichtabschnitte Fassung, Eingaben und Antwort mit jeweils einem Block. Fehlt einer, gilt der Beleg als beschädigt und Wiederholen wird gesperrt. Der Wiederanlauf verlangt dagegen ausdrücklich einen Beleg **ohne Antwortblock**, um einen Modellaufruf auszulösen. Damit scheitert gerade die Wiederaufnahme eines vor der Antwort abgebrochenen Auftrags. Ein vorsorglich angelegter leerer Antwortblock würde wiederum die Entscheidung anhand der Blockexistenz verfälschen. [Pflichtabschnitte](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:113), [Wiederanlauf](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:266)

   **Korrektur** Den Antwortblock vor erfolgreicher Antwortablage optional machen und ausschließlich einen vollständig gespeicherten Block mit Antworttext als abgeschlossene Modellantwort behandeln.

2. **P1 – Die Einkasten-Regel kann Belege eines gelöschten Prompts einem anderen zuordnen.**  
   Unter einer Überschrift stehen die getesteten Kästen A und B. Sascha löscht A, B bleibt bestehen. Für den Schattenordner von A fehlt der Hash-Treffer, deshalb ordnet Regel 2 ihn dem einzigen verbleibenden Kasten B zu. Der Schattenordner von B wird ebenfalls B zugeordnet, diesmal über den Hash. Die Gegenprobe ergibt somit `A → B` und `B → B`. Die aktuelle Kastenanzahl beweist keine eindeutige historische Zuordnung. [Zuordnungsregeln](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:278)

   **Korrektur** Die Einkasten-Ausnahme auf nachweisliche 1→1-Änderungen begrenzen, den vorherigen Kastenbestand festhalten und konkurrierende Zuordnungen als ungeklärt behandeln.

3. **P1 – Beim Schärfen wird das Material weiterhin nur referenziert.**  
   Die Schärfen-Datei soll Hinweise, einen „Material-Verweis“ und den Skilltext speichern. Für die tatsächlich verwendeten, gegebenenfalls auf 30.000 Zeichen gekürzten Antwortinhalte fehlt die Momentaufnahme. Eine Änderung oder Löschung des Quellbelegs verändert oder blockiert damit einen bereits eingereihten Schärfenlauf. Die neue deterministische Rekonstruktion ist für diesen Auftragstyp noch unvollständig beschrieben. [Schärfen-Auftrag](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:358), [gespeicherte Eingaben](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:386)

   **Korrektur** Den tatsächlich verwendeten Materialtext zusätzlich zum Herkunftsverweis als `wert` speichern und den vollständigen Schärfenauftrag vor dem Senden gegen seinen gespeicherten Hash prüfen.

4. **P1 – Die neuen Statusschreibzugriffe können einen Arbeitsfaden beenden.**  
   `beleg_zustand()` soll bei jedem Übergang schreiben, auch in `_naechste` und innerhalb der Fehlerbehandlung. Im vorhandenen Ablauf liegt `_naechste()` jedoch außerhalb des `try`-Blocks. Wird ein Beleg nach dem Einreihen gelöscht, beschädigt oder gesperrt, kann dessen Statusaktualisierung den Arbeitsfaden beenden. Ein weiterer Schreibfehler innerhalb des `except`-Zweigs kann ebenfalls nach außen gelangen. Die Wiederherstellungsregel „Beleg fehlt → Fehler“ braucht deshalb einen ausdrücklich geregelten Fehlerpfad ohne erfolgreiche Belegänderung als Voraussetzung. [Neue Statuszugriffe](/C:/Workstation/Werkzeuge/KI-Zentrale/SPEC-prompts.md:248), [vorhandene Arbeitsschleife](/C:/Workstation/Werkzeuge/KI-Zentrale/werkstatt/auswertung.py:908)

   **Korrektur** Belegzugriffe in die geschützte Auftragsverarbeitung aufnehmen, Fehler unabhängig vom Beleg in der Warteschlange festhalten und das Weiterarbeiten des Arbeitsfadens mit fehlendem beziehungsweise unbeschreibbarem Beleg testen.

VERDICT: REVISE

### Claude (nach Runde 3, Rundengrenze erreicht)

MAX_ROUNDS=3 ist erreicht, das letzte Urteil lautet REVISE mit vier P1-Punkten. Keine erfundene Einigung: Die vier
Punkte sind klein, eindeutig und ändern keine Entscheidung, darum hat Claude sie in `SPEC-prompts.md` eingearbeitet,
**ohne** dass Codex sie noch einmal gesehen hat. Sascha entscheidet, ob das reicht (bauen) oder ob eine vierte Runde
laufen soll.

- 1 (Beleg ohne Antwort als „beschädigt“): übernommen; `## Antwort` ist optional, Pflicht sind nur Fassung und
  Eingaben; „Antwort vorhanden“ = geschlossener Block mit Text, alles andere löst beim Wiederholen einen Modellaufruf
  aus. Abnahme (n) in Scheibe 2.
- 2 (Einkasten-Regel nach Löschen): übernommen; `eintrag.json` hält `kaesten_vorher`, die Einkasten-Regel gilt nur
  bei nachweislich 1→1, sonst ungeklärt; zwei Schattenordner auf denselben Kasten → ungeklärt. Abnahme (k) ergänzt.
- 3 (Material nur referenziert): übernommen; Material als `wert` in der gesendeten Kürzung, `schaerfen_bauen` als
  reine Funktion, `gesendet_stand` auch für Schärfen in der Warteschlange und vor dem Senden geprüft. Abnahme (i) in
  Scheibe 3.
- 4 (Belegzugriffe beenden den Arbeitsfaden): übernommen; alle Belegzugriffe in `try/except`, Warteschlange bleibt
  führend, Codes `beleg_fehlt`/`beleg_gesperrt`, abgesicherter `except`-Zweig. Abnahme (n) in Scheibe 2.

Ergebnis über drei Runden: 35 Punkte, davon 33 übernommen, 2 anders eingeordnet (Weiterrechnen nach Abbruch =
vorbestehende Grenze außerhalb von Version 1; Einkasten-Zuordnung bleibt, aber nur bei nachweislich 1→1).

## Akt 3 – Bau (Codex baut, Claude prüft)

Start 06.11.2026 18:09. Builder gpt-6.1-sol, Denkstufe medium (fest); SPEC_FILE SPEC-prompts.md, LOG_FILE SPEC-prompts-REVIEW-LOG.md, MAX_FIX_ROUNDS 2, PROOF_CMD: uv-Python 3.12.14 `-m unittest discover -s werkstatt\tests` im Repo-Wurzelordner. Bau-Worktree C:\Workstation\Werkzeuge\KI-Zentrale-bau-prompts, Branch bau/reiter-prompts ab main cdba4c9; Spec als untracked Kopie im Worktree. Scheibe 1 (Ablage und Suche) zuerst.
Codex-Thread Scheibe 1: 01a1b1d7-39d7-7173-808d-320e42fc529d (Start 18:11, Hintergrundlauf, Live-Tab im Terminal-Panel).

### Runde 1 – Codex-Bau Scheibe 1 (Sol medium)

Lauf 18:11–18:22 (11 min), Thread 01a1b1d7-39d7-7173-808d-320e42fc529d, 42 Befehle. Token: 1.970.362 Eingabe
(davon 1.873.792 aus dem Zwischenspeicher), 30.534 Ausgabe (4.419 Denken). Bericht von Sol: 329 Tests grün,
1 übersprungen; Python- und JS-Syntaxcheck ok; keine Abweichung vom Spec; offen bleibt der Vorgabename neuer
Fassungen (Dialog verlangt einen Namen). Geändert: AGENTS.md, README.md, werkstatt/config.json, server.py,
tests/test_werkstatt.py, web/app.js, web/index.html, web/style.css; neu: werkstatt/prompts.py (535 Zeilen),
web/prompts.js (141), tests/test_prompts.py (339).

### Claudes Prüfung (Runde 1)

- Diff vollständig gelesen. Spec-treu: Blockparser mit Zaunzustand (Tilde und Backtick, Einrückung ≤ 3),
  `block_schreiben` mit verlängertem Zaun, `kennung` mit Gerätenamen/`_`-Verbot/Groß-Klein-Dopplung,
  `pfad_erlaubt` mit realpath auf Pfad und Wurzeln plus Verbot von UNC/`\\?\`/Datenströmen, modulweite Sperre,
  frisches Lesen vor jedem Schreiben, `kopf_stand` über Titel und Kopfzeilen, atomares Schreiben mit erhaltenen
  Zeilenenden, Sammlung nur lesend (Werkstatt-Abschnitt über Zaunzustand ausgeschlossen), Schattenordner mit
  `kaesten_vorher`-Regel und Konflikt bei doppelter Beanspruchung, `oeffnen` nur serverseitig gebaut mit
  Endungsprüfung, neue Routen vor dem Traceback-Log mit 409/400/403.
- Kleinigkeiten, nicht blockierend: `import copy` innerhalb von `_gecacht` (Stil); `oeffnen` mit `was: sammlung`
  nimmt jede gültige Kennung (harmlos); `Index.lesen` liest je Aufruf den ganzen Index (Zwischenspeicher nach
  mtime/Größe, bei der erwarteten Größe unkritisch); `dateiname('???')` ergibt die Kennung „Fassung“ (vorbestehende
  Hilfsfunktion).
- Proof selbst gelaufen: 329 Tests OK, 1 übersprungen (uv-Python 3.12.14, 3,0 s). Node-Bedientest lief mit.
- Browser-Abnahme auf Port 3896 aus dem Worktree mit eigenem Prompts-Ordner (Scratchpad), echte Sammlung nur
  gelesen: (a) 36 Einträge = 2 Ordner + 34 Sammlung (39 Kästen minus 5 im Werkstatt-Abschnitt), Reiter ohne
  Konsolen-/Netzwerkfehler, `/prompts.js` 200; Hühnerfarm über „Neu …“ angelegt, Datei korrekt; (b) Suche „html“
  → nur Hühnerfarm unter den Ordnereinträgen, Filter Sammlung blendet Ordner aus; (c) Kasten extern geändert,
  Bearbeiten mit altem Stand → „Die Fassung wurde inzwischen geändert, bitte neu laden.“ (409), nach „Neu
  einlesen“ zeigt der Dialog den externen Text, Speichern klappt, keine tmp-Datei; (d) handgeschriebene
  Videoanalyse mit Notizen: „Als bevorzugt“ ändert nur die Zeile `Bevorzugt:` (diff vorher/nachher);
  (e) „Kaputt“ (offener Zaun) → „nicht eindeutig lesbar“, nur „Im Ordner öffnen“; Sammlungseintrag zeigt Text,
  Stand und nur „In der Sammlung öffnen“; Reiter Zusammenfassung lädt weiterhin. (f)–(k) über Unit-Tests
  (Kennungen, Junction, oeffnen-Ablehnungen, 403 ohne Herkunft, Zaun-Rundlauf, Sammlungszuordnung inkl. gelöschtem A).
- Urteil: Scheibe 1 abgenommen, keine Fixrunde nötig. Sicherheitspass folgt unten.
Codex-Kontingent (used_percent aus rollout-*.jsonl): 5 % um 11:34, 7 % nach Review-Runden und Bau um 18:22.

### Sicherheitspass (Runde 1, Skill security-review, lesender Subagent)

Ergebnis: **kein Befund mit Konfidenz ≥ 0,7.** Geprüft und als sicher eingestuft: (1) neue GET-Routen hinter
`_host_ok`, POST hinter `_post_ok` (Host, `X-Werkstatt`, Origin; kein CORS, kein `do_OPTIONS` → fremde Seiten
scheitern am Preflight, DNS-Rebinding am Host-Check); (2) `pfad_erlaubt` lehnt `..`, absolute, laufwerksrelative,
UNC-, `\\?\`- und Datenstrom-Pfade ab, realpath löst Junctions auf (auf dem Rechner nachgestellt); (3) Kennungen vom
Client nur, wenn sie im Index vorkommen, `_ordner` verbietet `.`/`..`/Trennzeichen; (4) `kennung` kann keine
Traversal-Namen erzeugen; (5) `os.startfile` nur auf Sammlung, Eintragsordner oder `.md`/`.html` unter `tests\`/
`schaerfen\` mit geprüftem Dateinamen; (6) `_atomar` nur unter geprüften Pfaden; (7) kein `innerHTML` in
prompts.js, Quelle-Link nur bei `http(s)://` mit `rel="noopener"`; (8) `json.loads` in `_belege` harmlos;
(9) Zeilenumbrüche in Kopfzeilen/Namen verboten, Zäune nicht fälschbar; (10) GET-Nebenwirkung (`eintrag.json`
nachziehen) nur mit serverseitigen Werten.
Robustheitshinweis (kein Sicherheitsbefund): `[\x00-\x1f\x7f]` deckte NEL (`\x85`), LS (` `) und PS (` `)
nicht ab, die `str.splitlines()` als Zeilenumbruch nimmt. **Claude-Nachbesserung:** modulweites
`_STEUERZEICHEN` in `prompts.py` für Namen und Kopfzeilen, Tests ergänzt; Suite weiter 329 OK, `git diff --check` sauber.

### Lehre aus diesem Lauf

- Zeit gekostet: Astra-Runden (xhigh) 10–17 min, über der 10-Minuten-Grenze des Bash-Werkzeugs (Hintergrund-Verschiebung,
  kein Schaden); Live-Skript scheiterte zuerst an der PowerShell-Ausführungsrichtlinie. Bau: 11 min, keine Fixrunde.
- Was sich ändert: Review-Runden in grill-me-codex/codex-review von Anfang an als Hintergrundlauf mit Ausgabedateien;
  codex-build-Live-Tab mit `powershell -NoProfile -ExecutionPolicy Bypass -File`. AGENTS.md: nichts.

### Menschentor (Scheibe 1)

Vorgelegt 06.11.2026 abends: Commit auf `bau/reiter-prompts` (ohne Push) offen, Entscheidung bei Sascha.
Commit Scheibe 1 (Sascha: „Ja, committen“, 19:17): 12b11098 auf bau/reiter-prompts im Worktree, ohne Push; Review-Log bleibt vorerst im Hauptordner. Abnahme-Werkstatt läuft weiter auf 127.0.0.1:3897 (Port 3896 gehört dem Atelier).

### Runde 2 – Codex-Bau Scheibe 2 (Testen mit Belegen)

Start 06.11.2026 19:20 nach Saschas „Ja, Sol baut“. Builder gpt-6.1-sol, Denkstufe medium; gleicher Worktree, Basis Commit 12b1109; Bauauftrag aus den Spec-Abschnitten Testbeleg, Zustände, Testdialog, Warteschlange, Scheibe 2 (a)–(n). Abnahme-Werkstatt (3897) vorher gestoppt.
Codex-Thread Scheibe 2: 01a1b217-906a-7b40-a7f0-f6f59b697d80 (Start 19:20, Hintergrundlauf, Live-Tab im Terminal-Panel).
Sascha 06.11. 19:27: „Du kannst auch sol auf high verwenden“ – laufender medium-Lauf wird nicht abgebrochen (Regel 05.11.); Fixrunden und Scheibe 3 auf Sol high.

Lauf 19:20–19:42 (22 min), Thread 01a1b217-906a-7b40-a7f0-f6f59b697d80, 86 Befehle. Token: 6.882.125 Eingabe (davon
6.717.824 aus dem Zwischenspeicher), 57.222 Ausgabe (16.178 Denken). Bericht von Sol: 364 Werkstatt-Tests grün, 193
Zentrale-Tests grün, py_compile/node --check/git diff --check ok, keine Abweichung vom Spec; Abnahmepunkte (a)–(n) je
Test zugeordnet. Geändert: auswertung.py (+175), prompts.py (+421), server.py (+59), quellen.py, prompts.js (+185),
app.js, zusammenfassung.js, style.css, README.md, PLAN.md (ungefragt, aber nach Repo-AGENTS.md zulässig); neu:
tests/test_auswertung_prompts.py (zählende Fake-Anbieter, Wiederanlauf, Sperrtest mit CreateFileW).

### Claudes Prüfung (Runde 2)

- Diff vollständig gelesen. Spec-treu: Beleg beim Einreihen mit `'x'`, Fassung/Eingaben/Antwort-Abschnitte, Antwort
  im verlängerten Zaun, `auftrag_bauen` als reine Funktion mit `gesendet_stand` in Warteschlange und Kopf, Prüfung
  vor dem Senden (Codes `beleg_geaendert`, `transkript_geaendert`, `kontext`), `kontext_geladen` über /health, /api/ps
  und Katalog, Zustandstabelle mit `beleg_zustand` und Wiederherstellung beim Start, Wiederholen ohne zweiten
  Modellaufruf, Belegzugriffe in try/except, Log nur mit Klasse und Code, `art`-Normalisierung, Messungen-Filter,
  Markdown-Zäune, Drop-Haken. Sperrreihenfolge beachtet (Dateisperre nie um die Warteschlangensperre).
- Proof selbst gelaufen: 364 Tests OK, 1 übersprungen.
- Browser-Abnahme auf Port 3897 (Worktree, Scratchpad-Promptordner), echter Lauf mit Codex Luna (niedrig):
  (a) Beleg beim Einreihen, nach 12 s `fertig`, 16.180 Token, Antwort im Beleg (Luna stellte wie vom Prompt verlangt
  die Rückfrage Spiel oder Webseite und bezog sich dabei erkennbar auf seine globale AGENTS.md, also genau die im Spec
  benannte Färbung), `html: nein` korrekt; „Gesendet anzeigen“ zeigt den Auftragstext; (c) Urteil „gut“ + Notiz nur
  als Kopfzeilen geschrieben; (e) „Nochmal“ mit Fassung und Luna vorbelegt; Videoanalyse: Transkriptwahl (4 Einträge),
  Transkript eingeklappt als `[Transkript: 12707 Zeichen]`, Dateifeld über Pfad gelesen (START-HIER.md), Schätzung
  4.469 Token gegen 272.000; Reiter Zusammenfassung und Messungen laden weiter ohne Fehler. (b), (d), (f)–(n) über die
  Unit-Tests.
- Befunde für die Fixrunde (Sol high, Resume): (1) P1 Neuladen alle 2,5 s baut Liste und Inhalt komplett neu, klappt
  die geöffnete Antwort zu und ersetzt Knöpfe mitten im Klick (im Browser nachgestellt); (2) P2 rohe Zustandswörter
  „laeuft/fertig“ in Beleg- und Warteschlangenzeilen; (3) P2 except-Zweig von `_schleife` ohne zweites try;
  (4) P2 `fassung_oeffnen` ignoriert `was` bei Prompt-Einträgen.
- Außerhalb der Scheibe, als Folgearbeit vorgemerkt: `transkripte_auflisten` liest nur die oberste Ebene des
  watch-Ordners; seit den Bereichsordnern (25.10.) sieht die Werkstatt dadurch nur 4 von 289 Transkripten und zeigt
  Bereichsordner als Titel („Privat“, „Training-und-Therapie“). Betrifft Zusammenfassung und Prompts gleichermaßen.
  Außerdem meldet die Auswerterliste im Worktree-Dienst „Claude-App mit Claude Code nicht installiert“ (Pfadsuche der
  Claude-Anbieterklasse), vorbestehend, nicht Teil dieses Baus.
Fixrunde 1 (Scheibe 2) gestartet 19:50 per Resume auf Sol high (Saschas Freigabe 19:27), vier Punkte.

### Fixrunde 1 (Scheibe 2) – Sol high, Resume

Lauf 19:50–19:55 (5 min), Thread 01a1b217-906a-7b40-a7f0-f6f59b697d80 (Resume). Token über den ganzen Thread
seitdem: 9.114.366 Eingabe (8.715.904 aus dem Zwischenspeicher), 71.501 Ausgabe. Bericht: alle vier Punkte behoben,
365 Tests grün, py_compile/node --check/git diff --check ok, PLAN.md/README/Spec unverändert.

### Claudes Prüfung (Fixrunde 1)

- Diff gelesen: `pLaeuft`/`pLadenFaellig`/`pGeschuetzt` (Neuladen nur bei wartet/laeuft, sonst alle 30 s, nie bei
  offenem Dialog oder Fokus im Inhalt), Liste und Inhalt nur bei geänderten Daten neu gezeichnet, offene `<details>`
  über `data-p-ansicht` wiederhergestellt, Bildlauf erhalten; `ZUSTAND` und „Urteil: …“ in den Zeilen; zweites
  `try` in `_schleife` mit Rückfall auf Zustand und Code `anbieter`; `fassung_oeffnen` öffnet bei `ordner` den
  Belegordner.
- Proof selbst: 365 Tests OK, 1 übersprungen; `git diff --check` sauber.
- Browser (Port 3897, nach echtem Neuladen der Seite, weil ein Hash-Navigate die alte prompts.js behielt): nach
  `pLaden()` ist der Listenknoten dasselbe DOM-Objekt, die geöffnete Antwort bleibt offen (gleiches Objekt) und ist
  nach 6 s weiter sichtbar; Belegzeile zeigt „Fertig · Urteil: gut · <Notiz>“. Scheibe 2 abgenommen.

### Lehre aus diesem Lauf (Scheibe 2)

- Zeit gekostet: Das Neuladen alle 2,5 s war im Spec nicht vorgesehen und kam als Eigeninitiative des Builders;
  Browser-Abnahme hat es sofort gezeigt. Ein `navigate` auf dieselbe Adresse mit anderem Hash lädt die Seite nicht
  neu (alte Skripte bleiben), erst `location.reload()`. Sonst glatt.
- Was sich ändert: Bauaufträge für Oberflächen künftig mit dem Satz „keine periodischen Neuladungen ohne Vorgabe“;
  im codex-build-Ablauf nach einem Serverneustart die Seite hart neu laden. AGENTS.md: nichts.

### Sicherheitspass (Scheibe 2, Skill security-review, lesender Subagent)

Ergebnis: **kein Befund mit Konfidenz ≥ 0,7.** Geprüft: Belegschreibzugriffe nur unter dem Prompts-Ordner (dateiname,
pfad_erlaubt, 'x'), `_belegpfad` traut der persistierten Warteschlange nicht, `datei_lesen` nur unter den Wurzeln
(dynamisch mit Traversal-, UNC-, `\?\`-, ADS- und 8.3-Varianten geprüft), Transkripte nur mit festem Dateinamen unter
watch, Markdown-Zäune und alle Inline-Formen maskiert (15 Nutzlasten in Node), keine neuen innerHTML-/href-Senken,
Kontextabfragen nur an Ports aus der Zentrale-Konfiguration, handgeänderte Belege können weder Pfad noch Anbieter
außerhalb der Konfiguration wählen, neue POST-Aktionen hinter `_post_ok`, neue GETs nur lesend. Akzeptierte
Gestaltung: Antwort-HTML wird aus `file://` als eigene Origin geöffnet (kein Zugriff auf Werkstatt oder andere
Dateien), Codex liest mit `-s read-only` auch Felddateien, ein handgeänderter Beleg darf jeden konfigurierten
Anbieter wählen. Hinweis unter der Schwelle: `dateiwurzeln` enthält `C:\Workstation` und damit `00_Secrets`.
**Claude-Nachbesserung:** `prompts.gesperrt` (Vorgabe `C:\Workstation\00_Secrets`) und `.env`-Dateien werden in
`datei_lesen` abgelehnt; Test `test_datei_lesen_sperrt_zugangsdaten`; README und Spec ergänzt. Suite: 366 OK.

### Menschentor (Scheibe 2)

Vorgelegt 06.11.2026 abends: Commit auf `bau/reiter-prompts` (ohne Push) offen, Entscheidung bei Sascha.
Commit Scheibe 2 (Sascha: „Ja, committen“, 20:04): 4bc8bf46 auf bau/reiter-prompts im Worktree, ohne Push. Hinweis: Die Folgesession „Transkripte in Bereichsordnern“ bekam keinen eigenen Worktree und arbeitet im selben Ordner (bau/reiter-prompts); Scheibe 3 wartet, bis sie fertig ist.
Sascha 06.11. 20:07: „Ja, danach bauen“ – Scheibe 3 (Schärfen) startet auf Sol high, sobald die Transkript-Session im selben Worktree fertig ist; Bauauftrag liegt bereit (Scratchpad bau-scheibe-3.txt).

### Runde 3 – Codex-Bau Scheibe 3 (Schärfen)

Start 06.11.2026 20:27. Builder gpt-6.1-sol, Denkstufe high (Saschas Freigabe 19:27); Worktree sauber auf 4bc8bf46; die Transkript-Session arbeitete im Hauptordner (main, uncommitted), nicht im Worktree.
Codex-Thread Scheibe 3: 01a1b254-727a-7642-b6cf-8e88416f84da (Start 20:27, Hintergrundlauf, Live-Tab im Terminal-Panel).

Lauf 20:27–20:39 (12 min), Thread 01a1b254-727a-7642-b6cf-8e88416f84da, 52 Befehle. Token: 4.018.673 Eingabe (davon
3.863.808 aus dem Zwischenspeicher), 31.281 Ausgabe (6.018 Denken). Bericht von Sol: 382 Werkstatt-Tests grün, 193
Zentrale-Tests grün, py_compile/node --check/git diff --check ok, keine Abweichung vom Spec; Ergebnisvermerk bei
„Erst klären“ lautet „Fragen, nicht übernommen“ (im Spec nicht festgelegt, übernommen). Geändert: prompts.py (+255),
auswertung.py (+54), server.py (+13), prompts.js (+114), style.css, drei Testdateien, README.md, PLAN.md; neu:
tests/prompts_schaerfen_bedienung.js (JavaScript-Bedientest mit DOM und Fake-HTTP).

### Claudes Prüfung (Runde 3)

- Diff vollständig gelesen. Spec-treu: `skill_lesen` (Frontmatter entfernt, fehlt → `skill_fehlt` vor dem
  Einreihen), `schaerfen_bauen` als reine Funktion mit festem Auftragsblock, Zielmodell-Hinweisen je Anbieterart,
  Fassung als `~~~text`-Kasten und Material mit verlängertem Zaun samt Nennung der Zaunlänge; Schärfen-Datei beim
  Einreihen mit `'x'`, Kopf mit `aktion`, `skill_stand`, `gesendet_stand`, `ergebnis`; Auswertung verlangt genau
  einen geschlossenen Prompt-Kasten (Tilde oder Backtick), `text_pruefen`, Erhalt aller Platzhalter (neue erlaubt
  und angezeigt); Übernahme unter der Sperre mit Stand-Vergleich (duplikatfrei), Namen über `_name`, Sammlung nur
  Vorschlag, Erst klären ohne Übernahme; Warteschlange: Antwort und Token werden vor der Übernahme gespeichert,
  Wiederholen ohne zweiten Modellaufruf, `_belegpfad` prüft den Unterordner, Wiederherstellung beim Start auch für
  `schaerfen\`; Routen und Anzeige (Original/neu nebeneinander in `<pre>`, Stichpunkte über `markdown()`).
- Proof selbst: 382 Tests OK, 1 übersprungen; `git diff --check` sauber.
- Browser-Abnahme (Port 3897, echter Lauf): „Schärfen ▾“ → Dialog mit Fassung, Aktion, Schreibmodell (Vorgabe
  Codex Sol, gewählt Luna), Zielmodell (lokales Ornith, nicht geladen, als Ziel erlaubt), Hinweise; Vorschau zeigt
  Skilltext, Auftragsblock, Fassung und Stand (1.993 Token); Lauf in 7 s, 16.469 Token; Schärfen-Datei mit
  `ergebnis: übernommen (Schärfen 06.11. Codex · GPT-6-Luna · niedrig)`, neue Fassung in `prompt.md` angehängt,
  Antwort im Block mit vier Tilden, weil sie selbst einen `~~~text`-Kasten enthält; Luna hat die Rückfrage aus dem
  Original gestrichen und die Hinweise eingearbeitet. (b)–(i) über die Unit-Tests.
- Anzeige „Ergebnis anzeigen“ im Browser: Original und neue Fassung nebeneinander, Stichpunkte darunter. Befund:
  ein überzähliges „null“ am Ende des Ergebnisses, weil `replaceChildren` ein `null`-Kind als Text anhängt (im
  DOM-Fake der Tests nicht sichtbar). **Claude-Nachbesserung** in `pSchaerfenErgebnis`: Kinder vorher filtern.
- Nachbesserung im Browser bestätigt: Ergebnisanzeige endet nicht mehr mit „null“, Original und neue Fassung
  stehen nebeneinander. Suite danach 382 OK, node --check und git diff --check sauber.

### Lehre aus diesem Lauf (Scheibe 3)

- Zeit gekostet: ein vergessener Abnahme-Dienst auf Port 3897 blockierte den Neustart (Adresse belegt); ein
  `null`-Kind in `replaceChildren` erschien als Text „null“, der DOM-Fake der JavaScript-Tests zeigt das nicht.
- Was sich ändert: vor jedem Neustart der Abnahme-Werkstatt den alten Lauf stoppen (Aufgaben-Kennung notieren);
  der DOM-Fake in `werkstatt\tests` soll `null`-Kinder wie der Browser als Text anhängen. AGENTS.md: nichts.

### Sicherheitspass (Scheibe 3, Skill security-review, lesender Subagent)

Ergebnis: **kein Befund mit Konfidenz ≥ 0,7.** Geprüft: Pfade der Schärfen-Dateien (Unterordner auf
`tests`/`schaerfen` begrenzt, Namen aus Aktion und Profilname über `dateiname`, `'x'`, realpath), `_belegpfad` mit
Unterordnerprüfung, Skillpfad nur aus der Konfiguration, Übernahme von Modelltext in `prompt.md` mit
Gegenproben (Steuerzeichen, Zeilentrenner, lange Tildenläufe, Backticks, eingerückte Zäune, CRLF: immer genau eine
zusätzliche Fassung, Titel und Bevorzugt unverändert), neue `innerHTML`-Senken nur über das maskierende
`markdown()`, keine neuen Schreibzugriffe auf GET, Material nur aus Belegen desselben Eintrags (30.000 Zeichen),
keine HTML-Ablage für Schärfen. Akzeptierte Gestaltung: Prompt-Injektion aus fremdem Material kann eine neue
Fassung erzeugen, die aber nie bevorzugt wird; Skilltext und Material gehen an das gewählte Cloud-Schreibmodell,
die Vorschau zeigt das vorher. Hinweis unter der Schwelle: fester Dreifach-Zaun um die Fassung im Auftrag.
**Claude-Nachbesserung:** Fassung im Schärfen-Auftrag über `block_schreiben` eingebettet (verlängerter Zaun bei
handgeschriebenen Fassungen mit `~~~`-Zeilen); Suite weiter grün.

### Menschentor (Scheibe 3)

Vorgelegt 06.11.2026 abends: Commit auf `bau/reiter-prompts` (ohne Push) offen, Entscheidung bei Sascha.
Das Review-Log bleibt im Hauptordner und geht erst beim Zusammenführen nach main mit.
Sascha 06.11. 20:52: „Erst anschauen“ – Scheibe 3 bleibt uncommitted im Worktree, Abnahme-Werkstatt auf 3897 läuft weiter. Transkript-Session: Commit 6a680fa auf main im Hauptordner (ohne Push); Werkstatt 3895 zeigt die neue Transkriptliste erst nach Neustart.
Commit Scheibe 3 (Sascha: „mitten und dann erstmal Pause“, 20:57): 170a827 auf bau/reiter-prompts im Worktree, ohne Push; Worktree sauber. Abnahme-Werkstatt auf 3897 gestoppt. Pause bis morgen (07.11.2026). Offen: Zusammenführen nach main (Saschas Entscheidung; dort liegt 6a680fa der Transkript-Session), Review-Log beim Zusammenführen mit ins Repo, Werkstatt 3895 danach neu starten.
