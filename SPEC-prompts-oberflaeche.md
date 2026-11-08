# Spec: Reiter „Prompts“ – neue Oberfläche nach Vorlage

_Entwurf von Astra (gpt-6-astra, xhigh, nur lesend, 11 min) am 08.11.2026 auf Saschas Auftrag „analysiere das Bild und lasse dir von Astra auf Xhigh einen Umsetzungsplan schreiben“, mit Nachtrag zu Zielmodellen (27B, Flash-Next, Claude) und Abo-Anbindung. Von Claude gegen den Code geprüft (siehe „Prüfvermerk Claude“ am Ende). Von Sascha am 08.11.2026 freigegeben („Ja, bauen“) und am selben Tag gebaut (siehe „Baustand“ am Ende). Vorlage: Bildschirmfotos eines Web-Werkzeugs zum Prompt-Verbessern (nur Aufbau und Bedienidee übernommen)._

Stand: 08.11.2026. Grundlage sind die vorhandenen Specs, der aktuelle Code, die beiden angehängten Bilder und Claudes Beschreibungen der Auswahlmenüs. Diese Prüfung erfolgte ausschließlich lesend. Dienste, Modelle und Tests wurden nicht gestartet oder angesprochen. Die dokumentierte Ausgangslage lautet **403 Tests grün, 1 übersprungen**.

## Ziel

Der Reiter erhält einen zentralen Einstieg **„Rohprompt eingeben → für ausgewählte Zielmodelle schärfen → Ergebnisse vergleichen und testen“**. Aufbau und Bedienidee folgen der Vorlage, Farben und Gestaltung der vorhandenen „Bernstein-Kommandozentrale“.

Alle bestehenden Funktionen bleiben erreichbar: Sammlung, eigene Einträge, Fassungen, bevorzugte Fassung, Testeingaben, Belege, A/B, Urteil und Notiz, Schärfen, Erst klären, Kürzen sowie Warteschlange und Wiederherstellung.

Die Umsetzung umfasst außerdem:

- getrennte Auswahl von **Zielmodellen** und **Schreibmodell**;
- mehrere Zielmodelle mit je eigenem Lauf und Ergebnis;
- pflegbare Typ- und Zielprofilregeln;
- klar gekennzeichnete Abo-Anbindung von Claude und OpenAI/Codex;
- die bisher fehlende Unterstützung der beiden gewünschten `llamacpp`-Einträge;
- Katalogkarten und kleine, ausdrücklich ausgewählte Kontextbausteine.

Die unten genannten Vorgaben sind die umsetzbare Standardfassung. Offene Entscheidungen betreffen Erweiterungen und blockieren diesen Bau nicht.

## Bildanalyse: was übernommen wird, was entfällt, was ergänzt wird

| Element der Vorlage | Werkstatt-Funktion und Entscheidung |
|---|---|
| Schmale linke Leiste | Lokale Navigation innerhalb des Reiters: „Neuer Prompt“, „Bibliothek“, „Kontextbausteine“, „Suche“. Die Werkstatt-Navigation bleibt bestehen. |
| „Zuletzt“ | Bis zu sechs zuletzt bewusst geöffneten Einträge; keine Besuchsaktualisierung durch Hintergrundabrufe. |
| Große Überschrift und Unterzeile | „Prompts gezielt verbessern“ und „Schreibe deinen Rohprompt und wähle, für welche Modelle er passen soll.“ |
| Große Eingabekarte | Composer mit Rohtext, Typwahl, Schreibmodell, Material, Kontextauswahl und Senden. |
| „Prompt-Typ“ mit Untertiteln | Aufgabentypen gemäß Tabelle unten; keine Übernahme der Anbietertexte. |
| „Starkes Modell“ | Beschriftung **„Schreibmodell“**. Es formuliert um. |
| Zusätzliche Modellhäkchen | **„Für welches Modell?“** bezeichnet die späteren Zielmodelle. Mehrfachwahl erzeugt getrennte Läufe. |
| „Prompt \| Vorlage“ | Konkreter Auftrag beziehungsweise wiederverwendbare Fassung mit `[Platzhaltern]`. |
| Büroklammer | Textmaterial zum Schärfen. Das ist eine Erweiterung: Bisher gibt es Dateieingaben im Testdialog; beim Schärfen nur eine frühere Antwort als Material. |
| Gehirn/„Erinnerungen“ | „Kontextbausteine“: bewusst ausgewählte Texte; kein automatisches Gedächtnis und kein Briefingabruf. |
| Mikrofon | Eigene spätere Erweiterung. In dieser Runde kein funktionsloser Mikrofonknopf. |
| „Entdecken“, Kategorien und Kartenreihen | Katalog aus der vorhandenen Sammlung und eigenen Einträgen. |
| Anmelden, Konto, Upgrade, Schloss, Logos | Entfallen vollständig. Nicht verfügbare Profile erhalten einen konkreten Grund. |
| Ergebnisansicht | Original und neue Fassung, Änderungen, Zielmodell, Schreibmodell, Zustand, Kopieren, Testen und Nochmal. |
| In der Vorlage fehlende Fachfunktionen | Fassungen, Tests, Urteile und Warteschlange bleiben in der Bibliothek und sind vom Ergebnis aus erreichbar. |

**Korrekturen gegenüber der Voranalyse:**

1. `Lokal._eintraege()` berücksichtigt derzeit nur `ollama`, `ninfer`, `strata` und `polystrata`. Beide gewünschten Qwen-27B-Einträge sind `llamacpp` und fehlen deshalb im Auswerter-Katalog.
2. Die Sammlung hat inzwischen auch **„6. Diese Sammlung erweitern“**. Abschnitte und Eintragszahl dürfen nicht fest eingebaut werden.
3. `prompt-realismus` gilt ausdrücklich für **fotorealistische Menschen**, nicht allgemein für Bilder, Illustrationen oder Logos.
4. `schaerfen_uebernehmen()` erkennt vorhandene Ergebnisse bisher allein am Textstand. Für getrennte Zielmodellfassungen muss diese Wiederholungslogik gezielt erweitert werden.

## Aufbau der Oberfläche

### Bereiche und Navigation

Innerhalb von `#reiter-prompts` ersetzt ein eigenes `.p-layout` das bisherige `.zf-raster`. Gemeinsame `.zf-*`-Stile anderer Reiter werden nicht umgebaut.

Auf breiten Ansichten:

- lokale Leiste: 176 px;
- Hauptbereich: flexibel, maximal 1.120 px;
- Composer: maximal 800 px, zentriert;
- Eingabefeld: mindestens 180 px hoch, vertikal vergrößerbar;
- Katalog: vier Karten je Reihe, sofern die verfügbare Breite reicht.

Die lokale Leiste zeigt oben die Navigation. Bei „Neuer Prompt“ folgen die zuletzt geöffneten Einträge. Bei „Bibliothek“ stehen dort stattdessen Suche, Herkunft, Status und die vorhandene Eintragsliste. **Es entsteht keine zusätzliche vierte Spalte.**

Unter 1.100 px Fensterbreite wird die lokale Navigation zur Kopfzeile. Die Bibliotheksliste lässt sich oberhalb des Inhalts aufklappen. Unter 700 px stehen Composer-Fußzeile und Ergebnisvergleich untereinander; Kartenreihen bleiben horizontal bedienbar. Kein horizontaler Seitenüberlauf.

Start unter `#prompts`: Composer und „Entdecken“. Unteransichten bleiben interner Zustand in `P`; das bestehende Hash-Verhalten von `reiterZeigen()` bleibt erhalten. Reiterwechsel erhalten den aktuellen Entwurf während der geöffneten Seite.

### Composer

Reihenfolge:

1. Überschrift und Unterzeile.
2. Mehrzeiliges Feld, Beschriftung „Rohprompt“, Platzhalter:  
   **„Beschreibe die Aufgabe, das gewünschte Ergebnis und wichtige Grenzen …“**
3. Sichtbare Zielauswahl:
   - „Qwen 27B (lokal)“
   - „Flash-Next (lokal)“
   - „Claude“
   - „OpenAI/Codex“
4. Kartenfuß:
   - „Prompt-Typ: Auto“
   - „Schreibmodell: …“
   - „Kontext auswählen“
   - „Datei anhängen“
   - runder Pfeilknopf, zugänglicher Name **„Prompt schärfen“**.
5. Umschalter „Prompt“ / „Vorlage“.
6. Aufklappbare „Weitere Angaben“:
   - Titel, optional;
   - Hinweise, bestehende Grenze 2.000 Zeichen;
   - Ablage;
   - vollständige Auftragsvorschau.
7. Kurze Zusammenfassung, beispielsweise:  
   **„3 Zielmodelle · 3 Schärfen-Läufe · Schreibmodell: Claude · Sonnet 5 · Abo“**

Hilfetext an der Zielauswahl:

> „Für jedes angekreuzte Modell entsteht eine eigene Fassung. Das Schreibmodell formuliert sie.“

Hilfetext am Schreibmodell:

> „Dieses Modell überarbeitet deinen Prompt.“

Keine automatische Sendung beim Wechsel von Typ, Zielmodell oder Modus.

**Ablage:** Neue Ordnereinträge sind für eigene Coding-/Kreativprompts vorgesehen. Sichtbare Auswahl unter „Weitere Angaben“:

- „Eigener Prompt – Coding/Kreativ“
- „Vorhandener Wissensprompt aus der Sammlung“

Bei der zweiten Auswahl ist ein Sammlungseintrag erforderlich. Fehlermeldung:

> „Wähle einen Sammlungseintrag. Neue Wissensprompts legst du weiterhin in deiner Promptsammlung an.“

Dadurch entsteht keine zweite aktive Wissenspromptsammlung. Typwahl allein entscheidet nicht über die Ablage.

Beim Schärfen einer bestehenden Fassung zeigt der Composer deren Text unverändert und nennt die Quelle. Änderungen am Auftrag erfolgen über „Hinweise“; eigene Fassungen lassen sich weiterhin über „Bearbeiten“ ändern.

### Bibliothek und Ergebnisse

`pWaehlen()` bleibt Einstieg für vorhandene Einträge. Die Detailansicht bekommt die Bereiche:

- „Fassungen“
- „Tests“
- „Schärfen“
- „Warteschlange“

Alle bisherigen Aktionen bleiben erhalten. Der zuletzt gestartete Composer-Auftrag erscheint zusätzlich als Ergebnisgruppe oberhalb dieser Bereiche.

Je Zielmodell:

- Zustand und Zielbezeichnung;
- Original und neue Fassung über `.p-vergleich`;
- Stichpunkte und neue Platzhalter;
- „Original kopieren“, „Neue Fassung kopieren“, „Testen …“, „Nochmal …“;
- Verweis auf den Schärfen-Beleg.

Bei ungültiger Antwort: vollständige Antwort und konkreter Grund, keine erfolgreich gespeicherte Fassung vortäuschen.

Bei Sammlungseinträgen lautet der Zustand weiterhin **„Vorschlag, nicht übernommen“**. Kein Knopf zum automatischen Rückschreiben.

„Testen …“ eines Sammlungsvorschlags darf dessen gültigen Antwortkasten als schreibgeschützte Testfassung verwenden. Dafür erhält der Testdialog eine explizite Belegreferenz; der Server liest und prüft den Kasten selbst. Es entsteht nur ein Testbeleg im zugehörigen Schattenordner.

### Gestaltung

Ausschließlich vorhandene Variablen verwenden: insbesondere `--grund`, `--flaeche`, `--flaeche-2`, `--linie`, `--text`, `--leise`, `--akzent`, `--akzent-hauch`, `--warnung`.

Systemschriften bleiben unverändert. Composer mit 16 px Rundung, Karten mit 10 px; Akzent nur für Auswahl, Fokus und Hauptaktion. Keine neuen Farbwerte, Anbieterlogos, Fremdschriften oder Bilddateien. Symbole als einfache lokale Inline-SVGs.

### Zustände und Tastatur

| Zustand | Anzeige und Verhalten |
|---|---|
| Erstes Laden | „Prompts werden geladen …“; Composer-Eingabe bleibt möglich, Senden wartet auf verfügbare Optionen. |
| Optionen laden | „Modelle und Prompt-Typen werden geladen …“ |
| Leere Bibliothek | „Noch keine eigenen Prompts. Schreibe deinen ersten Rohprompt.“ Sammlung kann daneben vorhanden sein. |
| Keine Suchtreffer | „Keine passenden Prompts.“ |
| Erstabruf fehlgeschlagen | Bestehender Text „Liste nicht geladen – neuer Versuch läuft.“ |
| Späterer Ladefehler | Bereits sichtbare Inhalte und Eingaben bleiben stehen. |
| Kein Schreibmodell verfügbar | „Kein Schreibmodell verfügbar.“ Darunter Gründe und „Modelle verwalten …“. |
| Vorbereitung läuft | „Auftrag wird geprüft …“; Senden gesperrt. |
| Eingereiht | „Schärfen wartet.“ Je Ziel ein eigener Zustand. |
| Modell arbeitet | „Prompt wird geschärft …“ |
| Übertragung unklar | „Die Bestätigung fehlt. Prüfe den Auftragsstatus, bevor du erneut sendest.“ Aktion „Status prüfen“. |

`Strg+Enter` löst im Composer dieselbe Funktion wie Senden aus. `Enter` bleibt im Textfeld ein Zeilenumbruch. Keine Sendung während einer IME-Komposition.

`Esc` schließt zuerst das oberste Auswahlmenü beziehungsweise den Dialog und setzt den Fokus zurück. Es löscht keinen Entwurf und bricht keinen Modelllauf ab.

Typauswahl als beschriftete Radiogruppe in einem aufklappbaren Panel; Zielmodelle als echte Checkboxen. Alle Symbole erhalten sichtbare Tooltip-Texte und zugängliche Namen. Meldungen verwenden kleine `aria-live`-Bereiche; nicht die gesamte Ergebnisansicht erneut vorlesen.

### Laden und Entwurfschutz

`pLaden()`, `pLadenFaellig()`, `P.ladenLaeuft`, `P.ladenNachholen` und die Regeln aus `SPEC-prompts-restpunkte.md` erhalten.

`pGeschuetzt()` berücksichtigt zusätzlich Composer-, Kontext- und Materialeditoren. Ein fokussiertes oder bearbeitetes Feld darf durch Nachladen nicht ersetzt werden. Composer-DOM und Bibliotheksdarstellung getrennt aktualisieren.

Der vorhandene **2,5-Sekunden-Takt in `promptsAktiv` bleibt der einzige Zeitgeber des Reiters**. Keine neuen Intervalle, Debounce-Zeitgeber oder automatischen Karussells. Suche reagiert unmittelbar lokal.

`localStorage` speichert nur Auswahl-IDs und zuletzt geöffnete Eintrags-IDs, keine Prompt-, Material- oder Kontexttexte. Entwurfstext bleibt im Arbeitsspeicher der Seite. Beim tatsächlichen Verlassen mit ungesendetem Entwurf greift der übliche Browserhinweis.

## Ablauf „Senden“

1. **Eingabe prüfen.** Nicht leer, bestehende `text_pruefen()`-Grenzen, mindestens ein Ziel, gültiges Schreibmodell und gültige Ablage. Bei einem Sammlungseintrag müssen ID, Fassung und Stand noch stimmen.
2. **Entwurf einfrieren.** Neue `anfrage_id` mit `crypto.randomUUID()` erzeugen; bei Übertragungsproblemen dieselbe ID behalten. Bis zum Abschluss der Einreihung ist Senden gesperrt.
3. **Vorschau serverseitig berechnen.** Neue Aktion `composer_vorschau` löst Profile, Skilltext, Typregeln und Material auf. Für jedes Ziel entstehen Auftragstext und `gesendet_stand`. Dabei wird noch keine Datei angelegt und kein Modell aufgerufen.
4. **Vorschau verfügbar machen.** „Auftragsvorschau“ kann vorab ausdrücklich geöffnet werden. Beim direkten Senden erfolgt dieselbe Prüfung intern; kein zusätzlicher Pflichtdialog. Die bisherigen Test- und Schärfendialoge behalten ihren Vorschau-/Start-Ablauf.
5. **Einreihen.** `composer_senden` erhält dieselben Eingaben, die `anfrage_id` und die Hashes je Ziel. Der Server prüft erneut. Abweichungen ergeben HTTP 409, bevor neue Arbeit angelegt wird.
6. **Original sichern.** Bei einem neuen eigenen Prompt wird genau ein Ordnereintrag mit `Fassung 1` angelegt. Ohne Titel: erste acht Wörter des Rohtexts, höchstens 70 Zeichen, anschließend vorhandene Kennungs- und Kopfvalidierung. Titel bleibt später änderbar.
7. **Läufe anlegen.** Je Ziel genau ein Schärfen-Beleg und ein Auftrag `art: schaerfen`. Alle verwenden denselben Rohtext, Materialstand und dasselbe Schreibmodell. Unterschiede entstehen nur durch Zielregeln.
8. **Vorhandene Warteschlange verwenden.** `Auswertungen.einreihen()` und `_promptlauf_ausfuehren()` bleiben die Ausführungspfade. Keine neue Modellschlange.
9. **Ergebnis anzeigen.** Zum betreffenden Eintrag und zur neuen Ergebnisgruppe wechseln. Während der Laufzeit dürfen weitere neue Prompts bearbeitet und eingereiht werden.
10. **Antwort sichern und übernehmen.** Antwort wie bisher vor der Nacharbeit speichern. Gültige Ergebnisse eigener Einträge werden als zusätzliche Fassungen angehängt. Original und bevorzugte Fassung bleiben unverändert.
11. **Testen.** „Testen …“ öffnet `pTestdialog()` mit der konkreten Ergebnisfassung und passendem Ziel-Auswerter. Es startet keinen Test automatisch.

### Fehler und Wiederholung

- **Doppelklick/Strg+Enter mehrfach:** gemeinsame Sperre in `pComposerSenden()` plus serverseitige Idempotenz.
- **Gleiche `anfrage_id`, gleiche Eingaben:** vorhandene Eintrags-, Beleg- und Auftragskennungen zurückgeben.
- **Gleiche ID, andere Eingaben:** HTTP 409: „Diese Sendung gehört zu einem anderen Eingabestand.“
- **Verbindung nach POST verloren:** kein blindes erneutes Anlegen; zuerst Status dieser ID abrufen.
- **Ein Ziel scheitert während der Ausführung:** andere Ziele laufen weiter. Fehler erscheint an genau diesem Ergebnis.
- **Teilweise Einreihung:** vorhandene Dateien bleiben erhalten; fehlende Zuordnungen werden bei derselben Sendung ergänzt, ohne vorhandene Läufe neu zu erzeugen.
- **Schreibmodell inzwischen nicht verfügbar:** kein Anbieterwechsel; Fehler mit Grund.
- **Zielmodell nicht geladen:** Schärfen bleibt möglich. Nur das Testen beziehungsweise die Verwendung als Schreibmodell ist gesperrt.
- **Ungültige Modellantwort:** Beleg bleibt erhalten, keine Fassung anhängen.
- **„Wiederholen“:** bestehende Fehler-/Abbruchbehandlung mit demselben Beleg.
- **„Nochmal …“:** neuer bewusster Schärfen-Lauf mit neuer ID; öffnet zuerst die übernommenen Einstellungen.
- **Laufende Anfrage:** „Nochmal“ für diesen Lauf ist gesperrt. Abbrechen bleibt eine ausdrückliche Aktion.

## Prompt-Typen

Die folgenden IDs sind verbindlich. Untertitel stehen direkt in der Auswahl.

| ID / Name | Untertitel | Regeln für das Schreibmodell |
|---|---|---|
| `auto` – Auto | „Passenden Typ aus der Aufgabe bestimmen“ | Einen Typ aus dieser Liste wählen; keine zusätzliche Klassifikationsanfrage. Bei Unklarheit Standard verwenden. |
| `standard` – Allgemein | „Aufgaben klar und vollständig formulieren“ | Ziel, benötigte Eingaben, Grenzen und Ausgabe klären; keine unnötige Rollenbeschreibung. |
| `wissen` – Wissen & Quellen | „Quellen auswerten, Wissen und Ergebnisse festhalten“ | Quelle, Ableitung und persönlichen Transfer trennen; Fundstellen nur verlangen, wenn das Material sie ermöglicht; fehlende Quellen benennen. |
| `recherche` – Recherche & Analyse | „Fragen untersuchen und Ergebnisse vergleichen“ | Untersuchungsfrage, Kriterien und Belegbedarf nennen; Recherchezugriff nur voraussetzen, wenn vorhanden. |
| `schreiben` – Schreiben | „Texte, E-Mails und Inhalte ausarbeiten“ | Zielgruppe, Zweck, Ton und Textform konkretisieren; keine Aussagen oder Fakten erfinden. |
| `planung` – Planung | „Vorhaben in nachvollziehbare Schritte übersetzen“ | Ergebnis, Randbedingungen, Abhängigkeiten und Prüfpunkte; keine erfundenen Termine oder Ressourcen. |
| `code` – Code | „Software entwickeln, prüfen und verbessern“ | Laufzeit, vorhandenen Code, erlaubte Änderungen und Abnahme benennen; Kontextzugriff nicht behaupten. |
| `agent` – Agent & Assistent | „Dauerhafte Aufgaben und Arbeitsregeln beschreiben“ | Systemanweisung vom einzelnen Auftrag trennen; Werkzeuge, Zuständigkeit und Grenzen ausdrücklich behandeln. |
| `automatisierung` – Automatisierung | „Wiederkehrende Abläufe zuverlässig beschreiben“ | Auslöser, Eingaben, Bedingungen, Aktionen und Fehlerfälle; vorhandene Systeme statt erfundener Integrationen. |
| `bild` – Bild | „Motive, Stil und Bildaufbau beschreiben“ | Motiv, Komposition, Stil, Licht und ausdrücklich gewünschte Schrift; keine Bilder erzeugen. |
| `video` – Video | „Szenen, Bewegung und Kamera beschreiben“ | Handlung, zeitlicher Verlauf, Kamera und Ton; keine Videos erzeugen. |

Für alle Typen gelten die Grundregeln aus `prompt-schaerfen`: Auftrag nicht ausführen, Absicht erhalten, vorhandene Platzhalter zeichengetreu bewahren, keine Zugriffe erfinden.

**Prompt/Vorlage:**

- `prompt`: konkrete Angaben erhalten; fehlende Angaben nicht erfinden.
- `vorlage`: wechselnde Angaben als aussagekräftige `[Platzhalter]` ausweisen; vorhandene Feldnamen nicht umbenennen. Neue Felder erscheinen wie bisher in der Ergebnisanzeige und im Testdialog.

**Auto:** Das Modell nennt nach dem Promptkasten `Prompt-Typ: <id>`. Nur bekannte IDs akzeptieren. Fehlende oder ungültige Typangabe macht einen ansonsten gültigen Prompt nicht ungültig; Anzeige „Typ nicht erkannt“. Keine automatische Änderung des Eintragskopfs durch konkurrierende Ergebnisse.

**Bild und Video:** Hier bezeichnet das Ziel den Bild-/Videogenerator. Die vier Sprachmodellhäkchen werden durch „Qwen-Image 2.1“ beziehungsweise „MiniMax-H3“ ersetzt. Die Sprachmodellauswahl bleibt beim Zurückwechseln erhalten.

Zusatzwahl **„Fotorealistische Menschen“**, standardmäßig aus:

- aus: `prompt-schaerfen` plus Bild-/Videoregeln;
- an: `prompt-realismus` als fachlicher Skilltext;
- Werkstatt-Ausgabevertrag bleibt in beiden Fällen vorrangig: genau ein Promptkasten, danach Einstellungen und kurze Erläuterungen;
- keine Bilderkennung und keine Bildanhänge in dieser Runde;
- Bild-/Videogeneratoren erhalten keinen Text-Testknopf. Anzeige: „Im Reiter Bild & Video verwenden.“

Bei `auto` wird `prompt-realismus` nicht stillschweigend zugeschaltet.

## Zielmodelle und Zielprofile

### Auswahl

Für Textaufgaben sind mehrere Häkchen erlaubt. Standard beim ersten Öffnen: **Qwen 27B**, danach die letzte gültige Auswahl.

Unter einem aktivierten Ziel lässt sich die konkrete Variante beziehungsweise das gewünschte Testprofil wählen. Die Auswahl lädt kein Modell.

Je Ziel entsteht eine eigene Ergebnisfassung, auch wenn zwei Zielmodelle denselben Text liefern. Das erleichtert die Zuordnung und spätere Prüfung.

### Befund und Abbildung

| Ziel | Konfiguration / vorhandene Abbildung | Umsetzung |
|---|---|---|
| Qwen 27B Q4 | `qwen27-unsloth`, Art `llamacpp`, Port 8106, `modell_id: qwen3.8-27b-unsloth-q4kxl`, 131.072 Kontext; Varianten `low`/`high` | Vorgabe für „Qwen 27B“. Auswerter: `anbieter: lokal`, `modell: qwen27-unsloth`. |
| Qwen 27B IQ3_S | `qwen27-iq3s`, Art `llamacpp`, Port 8103, `modell_id: qwen3.8-27b-gsq-iq3s`, 131.072 Kontext | Zweite auswählbare 27B-Variante. Keine Denkstufenwahl erfinden. |
| Flash-Next | `flash-next-strata`, Port 8095 | Auswerter: `anbieter: lokal`, `modell: flash-next-strata`; tatsächliche Kennung und Kontext über vorhandenes `kontext_geladen()`. |
| Claude | Auswerter mit `anbieter: claude`; vorhanden ist `claude-sonnet` | Gewähltes Claude-Profil bestimmt Testmodell und Denkstufe. |
| OpenAI/Codex | Auswerter mit `anbieter: codex`; vorhanden sind `codex-sol` und `codex-luna` | Als viertes Ziel aufnehmen, weil Schreiben **und Testen** über das Abo gewünscht sind. |

Flash-Next-Varianten laut Konfiguration:

- `128k`: IQ3_XXS, 128K, mit Bildern;
- `256k`: IQ3_XXS, 256K, ohne Bilder;
- `q4`, `q4-256k`: bisheriges Q4, 128K/256K, mit Bildern;
- `q4-v31`: Q4 v3.1 mit altem Engram, 128K;
- `q4-v31-q8`: aktueller Standard, 128K;
- `q4-v31-q8-256k`: 256K.

Die letzten drei Varianten unterstützen laut Konfiguration Bilder. **Die Prompt-Testoberfläche selbst überträgt weiterhin nur Text.**

Die gegenwärtige `auswerter.json` enthält noch kein Profil für die beiden lokalen 27B-Einträge oder Flash-Next. Fehlende Testprofile werden angezeigt und können über „Testprofil anlegen …“ mit dem vorhandenen `/api/auswerter` angelegt werden. Keine automatische Veränderung bestehender Profile.

### Konkrete Zielregeln

Diese Regeln sind überprüfbare Arbeitsvorgaben, keine behaupteten Leistungsgarantien.

| Zielprofil | Schreibregeln |
|---|---|
| `qwen27` | Eine klare Hauptaufgabe; kurze, eindeutig geordnete Schritte; wichtige Einschränkungen nahe an die zugehörige Aufgabe; festes, möglichst einfaches Ausgabeformat; benötigten Kontext direkt einsetzen oder als Feld vorsehen; keine verschachtelten Rollen oder langen Wiederholungen. IQ3_S erhält dieselben Regeln mit besonderem Augenmerk auf eindeutige Begriffe. |
| `flash_next` | Aufgabe und Material klar trennen; längere Quellen in benannte Abschnitte gliedern; Vollständigkeitskriterien und Belegform nennen; bei mehrstufiger Arbeit Zwischenprodukte nur verlangen, wenn sie hilfreich sind; keine Werkzeuge oder Projektkenntnis aus dem Modellnamen ableiten. |
| `claude` | Übersichtliche Abschnitte; XML-Tags nur bei mehreren Materialarten oder komplexen Abgrenzungen; zusätzliche Erläuterung zulassen, wenn sie einen konkreten Zweck hat; im Werkstatt-Test ohne Werkzeuge und ohne geladenes Projektgedächtnis formulieren. |
| `codex` | Konkrete Aufgabe, verfügbare Eingaben, erlaubter Änderungsumfang und überprüfbares Ergebnis; für Werkstatt-Tests die lesende Sandbox berücksichtigen. Keine Schreibfähigkeit versprechen. Allgemeine Textaufgaben nicht unnötig in Coding-Anweisungen verwandeln. |

Denkstufe ist eine Ausführungseinstellung, keine Formulierung wie „denke besonders lange“. Der Composer ändert weder Servervarianten noch Modellparameter. Bei Qwen Q4 wird erklärt: **„Die Denkstufe wird in der Modellzentrale gewählt.“**

### Ablage der Regeln

Eine maßgebliche, ohne Codeänderung bearbeitbare Datei:

`C:\Workstation\Skills\aktiv\prompt-schaerfen\references\werkstatt-profile.json`

Inhalt:

- `schema: 1`;
- `typen[]`: `id`, `name`, `untertitel`, `regeln`;
- `zielprofile[]`: `id`, `name`, `regeln`, `anbieter`, zulässige Eintrags-/Modellzuordnungen;
- Modusregeln für `prompt` und `vorlage`;
- Generatorregeln für Bild/Video.

Keine Nutzerprompts oder Zugangsdaten in dieser Datei. `werkstatt/config.json` erhält im Block `prompts` die Pfade `profile` und `skill_realismus`.

Regeln werden bei Vorschau frisch gelesen und validiert. Fehlende oder beschädigte Regeln sperren den betroffenen neuen Lauf mit verständlicher Meldung; Bibliothek und alte Belege bleiben lesbar.

Jeder neue Beleg speichert ID, Regeln und Hash als Momentaufnahme. Ein eingereihter oder wiederholter Lauf liest keine inzwischen veränderten Regeln nach.

### Fehlende `llamacpp`-Unterstützung

`Lokal._eintraege()` gezielt für **`qwen27-unsloth` und `qwen27-iq3s`** erweitern. Nicht pauschal OCR- oder andere `llamacpp`-Einträge als Schreibmodelle aufnehmen.

Vorhandene Wege verwenden:

- `_kennungen()` über `modell_id`;
- `_geladen()` mit tatsächlicher Modellkennung;
- `/v1/chat/completions` über `Lokal.ausfuehren()`;
- Kontext 131.072 aus den bestätigten Konfigurationen, bezeichnet als „Katalog der Zentrale“;
- erneute Verfügbarkeits- und Kontextprüfung unmittelbar vor dem Senden.

Kein Starten, Entladen oder Wechseln einer Variante. Keine zusätzlichen Modellports oder Laufwerksuche. Eine Denkstufe wird nur als tatsächlich erkannt bezeichnet, wenn sie belegt ist; andernfalls „in der Zentrale gewählt“.

## Schreibmodelle über Abo

### Heutiger Stand im Code

**Claude**

- `Claude.exe()` findet bereits das neue `Claude-Data`-Layout und verwendet die vorhandenen Rückfälle.
- `Claude.anmeldung()` prüft `auth status`; `authMethod == 'claude.ai'` bezeichnet die Abo-Anmeldung.
- `Claude.ausfuehren()` verwendet Claude Code, keine eigene API-Anbindung.
- Werkzeuge, Settings und MCP sind deaktiviert; `_ohne_app_umgebung()` entfernt die Claude-/Anthropic-App-Umgebung.
- Bei `claude.ai` wird ein rechnerischer API-Preis bereits nicht als Kosten ausgegeben.
- `verfuegbar()` verlangt bisher nur irgendeine Anmeldung, nicht ausdrücklich die Abo-Anmeldung.

Konfigurierter Katalog: Fable 5.1, Opus 5.5, Sonnet 5 und Haiku 4.5. Das sind Konfigurationseinträge, kein Nachweis aktueller Kontingente. Die Vorlage mit Sonnet/Haiku 5.5 ist hier nicht maßgeblich.

**OpenAI/Codex**

- `Codex.exe()` nutzt die CLI der installierten Codex-App.
- Aufruf mit `exec`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `-s read-only` und leerem Arbeitsordner.
- `Codex.katalog()` liest sichtbare Modelle aus `~\.codex\models_cache.json`.
- `Codex.verfuegbar()` prüft bisher lediglich Programm und Existenz von `auth.json`. Das bestätigt die Abo-Anmeldeart nicht.
- Codex besitzt weiterhin lesende Werkzeuge; die bekannte globale `AGENTS.md` kann das Ergebnis beeinflussen.

Im gelesenen Modellcache stehen unter anderem `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6.1-terra`, `gpt-6-sol` und `gpt-6-luna`. Keine feste Modellliste im neuen JavaScript.

### Änderungen

1. `profil_info()` um sachliche Zugangsinformationen erweitern:  
   `zugang: abo | api | unklar | keiner`, außerdem `prompts_verfuegbar` und `prompts_grund`.
2. Claude/Codex für neue Prompt- und Schärfen-Läufe nur mit bestätigtem Abo zulassen. Keine automatische Anmeldung oder API-Ausweichroute.
3. Codex-Anmeldeart ausschließlich aus nicht geheimen Auth-Metadaten, insbesondere einem vorhandenen `auth_mode`, bestimmen. Unbekanntes Format ergibt `unklar`, nicht „Abo“. Keine Tokeninhalte ausgeben oder an den Browser liefern.
4. Vor dem Modellaufruf erneut prüfen. Für Codex-Kindprozesse geerbte API-Key-/API-Base-Overrides entfernen, ohne Benutzervariablen oder Dateien zu ändern. Claude verwendet weiter `_ohne_app_umgebung()`.
5. Beschriftung beispielsweise:
   - „Claude · Sonnet 5 · Abo“
   - „OpenAI/Codex · GPT-6-Sol · mittel · Abo“
   - „Abo-Anmeldung nicht bestätigt“
6. DeepSeek, OpenRouter und lokale Profile bleiben als bisherige Alternativen vorhanden und werden korrekt als API, kostenloser Anbieter beziehungsweise lokal gekennzeichnet.
7. Schreibmodell-Vorgabe: bisheriger `localStorage`-Schlüssel `werkstatt.prompt-schreibmodell`; andernfalls erstes verfügbares Claude-/Codex-Abo-Profil, danach ein anderes verfügbares Profil.
8. Keine Änderung an `config.toml`, Login-Dateien, Modellcache oder vorhandenen Profilentscheidungen.

„Modelle verwalten …“ verwendet die vorhandene Profilverwaltung. `auswerterDialog()` muss dafür von der Voraussetzung `ZF.stand` gelöst werden: aktueller Stand und Änderungsrückruf als Parameter, bisheriger Zusammenfassungsaufruf als Standard erhalten.

## Entdecken/Katalog

### Datenquelle und Gruppierung

`GET /api/prompts` bleibt die Datenquelle.

`sammlung_kaesten()` wird um die jeweils aktuelle `##`-Überschrift außerhalb von Zäunen erweitert:

- `abschnitt`;
- `abschnitt_reihenfolge`;
- `reihenfolge`.

Die bisherigen IDs `sammlung:<Überschrift>#<Nummer>`, Nummern, Stände und Schattenzuordnungen bleiben unverändert. `anweisungen._zerlegen()` wird nicht verändert.

Kategoriezeile:

- „Alle“
- „Eigene Prompts“
- die tatsächlich vorhandenen Sammlungsabschnitte in Dateireihenfolge.

Nur Abschnitte mit lesbaren Promptkästen erscheinen. Der Werkstatt-Abschnitt bleibt ausgeschlossen. Keine feste Zahl „34“.

Unter „Eigene Prompts“ entstehen Kartenreihen nach gespeichertem `prompt_typ`; alte Einträge ohne Typ stehen unter „Weitere Prompts“. Schlagworte bleiben Such- und zusätzliche Filtermerkmale, ohne einen Eintrag mehrfach in derselben Ansicht auszugeben.

### Karten

Inhalt:

- Titel;
- höchstens zwei sichtbare Zeilen Kurztext;
- Herkunft und Typ;
- Pfeilsymbol als Teil desselben Knopfs.

Kurztext: erste nicht leere Zeile der bevorzugten Fassung, Leerraum vereinheitlicht, maximal 180 Zeichen. Keine Modellgenerierung.

Kartenklick öffnet den Eintrag. Er überschreibt keinen Composer-Entwurf. Dort steht ausdrücklich „Im Composer schärfen“.

Reihen mit vorherigen/nächsten Karten über benannte Knöpfe, beispielsweise „Weitere Prompts aus Wissen einpflegen“. Kein automatisches Blättern. Suche verwendet weiterhin Titel, Schlagworte, Quelle und alle Fassungstexte.

Unlesbare Einträge und ungeklärte Schattenordner bleiben in der Bibliothek mit ihren bisherigen Reparaturaktionen sichtbar.

## Server- und Datenänderungen

### Schnittstelle

Bestehende Routen und Aktionen bleiben kompatibel.

| Route/Aktion | Ergänzung |
|---|---|
| `GET /api/prompts` | Abschnitts- und Typangaben; keine weiteren regelmäßigen Abrufe notwendig. |
| `GET /api/prompt?id=…` | Neue Metadaten und Ergebnisgruppierung, vorhandene Felder erhalten. |
| `GET /api/prompt-optionen` | Typen, Zielprofile, Profilzuordnungen, verfügbare Schreibmodelle und Gründe. Keine vollständigen Kontexttexte. |
| `POST /api/prompt`, `composer_vorschau` | Vorschauen je Ziel aus einem ungespeicherten Rohprompt oder einer vorhandenen Fassung. |
| `POST /api/prompt`, `composer_senden` | Idempotentes Anlegen und Einreihen einer Zielgruppe. |
| `POST /api/prompt`, `composer_status` | Status einer `anfrage_id`, ohne erneuten Modellaufruf. |
| Bestehende `schaerfen_vorschau` / `schaerfen` | Optional neue Typ-, Modus-, Zielprofil- und Materialfelder. Alte Aufrufe bleiben gültig. |
| Bestehende `vorschau` / `testen` | Optional geprüfte Schärfen-Belegreferenz als Testfassung eines Sammlungsvorschlags. |
| `GET /api/prompt-kontexte` | Kontextübersicht. |
| `POST /api/prompt`, `kontext_lesen`, `kontext_neu`, `kontext_speichern` | Kleine Kontextverwaltung mit Standprüfung. |

Alle neuen POST-Aktionen unter bestehendem `_post_ok()` und `X-Werkstatt`. Fehler als `{fehler}`, 409 bei Konflikten; keine Inhalte in Tracebacks oder Logs.

### Composer-Daten

```json
{
  "aktion": "composer_senden",
  "anfrage_id": "<UUID>",
  "text": "<Rohprompt>",
  "titel": "",
  "ablage": "ordner",
  "basis": null,
  "prompt_typ": "code",
  "modus": "prompt",
  "schreibmodell": "claude-sonnet",
  "ziele": [
    {
      "zielprofil": "qwen27",
      "eintrag": "qwen27-unsloth",
      "testprofil": null
    }
  ],
  "hinweise": "",
  "materialien": [],
  "kontexte": [],
  "gesendet_staende": {
    "qwen27:qwen27-unsloth": "<SHA-256>"
  }
}
```

`basis`, falls vorhanden: `{id, fassung, stand}`. IDs und Profilzuordnungen serverseitig auflösen; keine frei gelieferten Ports, Skillpfade oder Regeltexte akzeptieren.

### Dateien und Rückwärtsverträglichkeit

Eigene `prompt.md` erhalten optional:

- `Prompt-Typ: <id>`
- `Modus: prompt|vorlage`
- `Composer-Auftrag: <UUID>` für beim Senden angelegte Einträge.

Fehlende Felder bedeuten `standard` beziehungsweise `prompt`. Unbekannte Kopfzeilen, Notizen und Zeilenenden bleiben erhalten. Keine Bestandsmigration beim Start.

Neue Schärfen-Belege erhalten:

- `auftragsgruppe`;
- `zielprofil_id`, `zielschluessel`, `testprofil_id`;
- `ergebnis_fassung`;
- `bau_version: 2` in den gespeicherten Eingaben;
- Momentaufnahmen von Skill, Typregeln, Zielregeln, Modus, Material und ausgewählten Kontexten.

**Wichtig:** Alte Belege ohne `bau_version` müssen mit dem bisherigen Aufbau von `schaerfen_bauen()` bytegleich rekonstruiert werden. Sonst schlagen vorhandene `gesendet_stand`-Prüfungen bei Wiederholung fehl. Neue Regeln nur im Version-2-Zweig verwenden.

`auftrag_aus_beleg()` und `datei_inhalt()` ergänzen die neuen Felder, ohne alte Pflichtfelder zu verschärfen.

### Idempotenz und Ergebnisnamen

Neue Verwaltungsdateien unter:

`Arbeitsmaterial\Prompts\_Auftraege\<anfrage_id>.json`

Sie enthalten ausschließlich Eingabefingerabdruck, reservierte Eintragskennung, Zielschlüssel, Belegnamen, Auftragskennungen und Einreihungszustand. Keine zweite Kopie der Prompt- oder Materialtexte.

Unter `_SPERRE`:

1. Sendung reservieren;
2. Original mit `Composer-Auftrag` atomar anlegen;
3. Belege mit `auftragsgruppe` und eindeutigem `zielschluessel` anlegen;
4. bestehende oder fehlende Warteschlangenzuordnung ermitteln.

Nach einem Abbruch zwischen Schreibschritten vorhandene Dateien anhand dieser Kennungen wiederfinden. Eine Wiederaufnahme erzeugt weder einen zweiten Rohprompt noch zusätzliche Modellaufrufe. Verwaiste Belege bleiben über den vorhandenen Wiederherstellungsweg erreichbar.

Ergebnisnamen beispielsweise:

- `Schärfen 08.11. · Qwen 27B Q4`
- `Schärfen 08.11. · Flash-Next`
- `Schärfen 08.11. · Claude`

Bestehende Namensvalidierung und 60-Zeichen-Grenze beachten. Unter der Sperre zuerst den konkreten Ergebnisnamen im Beleg festhalten, danach anhängen. Wiederholung prüft diesen Namen und Textstand. Bei nachträglichem Namenskonflikt melden, nicht überschreiben.

Für neue Gruppen gilt die Identität **Gruppe + Zielschlüssel**. Die bisherige reine Text-Deduplizierung bleibt nur für alte Belege erhalten.

### Textmaterial

Büroklammer bietet „Textdatei auswählen …“ und „Vorhandene Antwort auswählen …“.

- Dateidialog/Pfad weiterhin über `Index.datei_lesen()` und bestehende Pfad-/Secretsperren.
- Browserdateien über `File.text()`, mit Dateiname, Zeichenzahl und serverseitig berechnetem Hash.
- Höchstens fünf Materialien, zusammen höchstens `feld_max_zeichen` Zeichen.
- Textformate zulassen; PDF, Office, Bilder, Audio und Video mit verständlichem Hinweis ablehnen.
- Material vollständig übernehmen oder ablehnen; bei neuen Anhängen nicht still abschneiden.
- Die bisher auf 30.000 Zeichen begrenzte Antwortauswahl bleibt kompatibel und kennzeichnet eine Kürzung.
- Nach dem Einreihen nur gespeicherte Momentaufnahmen verwenden.

`einrichtenAblegen()` in `app.js` unterscheidet bestehende Testfelder und Composer-Anhänge. Im sichtbaren Prompts-Reiter darf ein abgewiesener Anhang nicht versehentlich zur Transkription wechseln.

### Kontextbausteine

Ablage ausschließlich:

`Arbeitsmaterial\Prompts\_Kontext\<kennung>.md`

Format: Titel `# …`, darunter genau ein geschlossener Textkasten. Pro Baustein höchstens 20.000 Zeichen. Metadaten aus Datei und Hash, keine zusätzliche Datenbank.

Funktionen: Liste, Anlegen, Bearbeiten, Auswahl aufheben. Kein Löschknopf in dieser Runde. Schreiben atomar unter Standprüfung, sichere Kennungen und `pfad_erlaubt()`.

Keine vorausgewählten Bausteine beim ersten Start. Auswahl wird sichtbar als Chip angezeigt und vollständig in der Auftragsvorschau aufgeführt. Nur ausgewählte Texte gehen an das Schreibmodell.

Kontextbausteine enthalten Projekt-/Sachkontext, keine zweite Sammlung wiederverwendbarer Wissensprompts. Kein automatisches Lesen von Vault, Briefing oder anderen Dateien.

### JavaScript und statische Dateien

Bestehende Funktionen weiterverwenden; neue Aufgaben trennen:

- `pComposerZeigen()`
- `pComposerDaten()`
- `pComposerVorschau()`
- `pComposerSenden()`
- `pSendungStatus()`
- `pEntdeckenZeichnen()`
- `pKontexteZeigen()`

`pSchaerfenErgebnis()` für Kopieren, Ergebnisgruppen und Testübergabe erweitern.

Zunächst alles in `prompts.js` und vorhandener `style.css`; keine neue Laufzeitbibliothek. Falls der Builder JavaScript aufteilt, müssen neue Dateien ausdrücklich in `Anfrage.statisch` und in korrekter Reihenfolge in `index.html` aufgenommen werden.

## Was unverändert bleibt

- Sammlungstext und ihre bisherigen IDs, Schattenzuordnungen und Konfliktregeln.
- Fassungsbearbeitung, `fassung_vorschlag`, bevorzugte Fassung und unbekannte Dateiinhalte.
- Feldersetzung in einem Durchgang, „wörtlich lassen“, Transkriptprüfsummen und Rahmenauswahl.
- A/B über ausgewählte Fassungen × Auswerter; gleiche Eingaben je Vergleich.
- Testbelege, Gesendet-Anzeige, HTML-Ausgabe, Urteil und Notiz.
- „Schärfen“, „Erst klären“, „Kürzen“ und vorhandene Vorschaupflicht der Dialoge.
- Antwort zuerst sichern; Wiederholung mit vorhandener Antwort ruft das Modell nicht erneut.
- Gemeinsame Warteschlange, Zustände und Abbruchverhalten.
- Claude-Werkzeugsperre und Codex-Sandbox.
- Keine Modellstarts oder Variantenwechsel durch die Werkstatt.
- Keine Änderungen an `watch.py`, Studioabläufen oder `anweisungen._zerlegen()`.
- Keine neuen Abhängigkeiten, CDN-Zugriffe, Fonts, Anmeldungen oder API-Schlüssel.

## Scheiben mit Abnahme

### Gemeinsame Abnahmebedingungen

Bau und Prüfung in einem isolierten Checkout. Testdaten ausschließlich in einem eigenen Testordner. **3895 und 3894 bleiben bei automatisierter Abnahme unberührt.**

Für Browser-Abnahme einen Testserver auf **freiem Port 3897**, gebunden an `127.0.0.1`, verwenden. Vorher Belegung prüfen; keinen fremden Prozess beenden.

Der Testserver darf nicht einfach `Werkstatt(cfg)` mit Produktivkonfiguration instanziieren: Dessen Konstruktor startet Hintergrundarbeit. Ein Test-Harness unter `werkstatt/tests` verwendet den echten HTTP-Handler und die echte Auswertungslogik mit temporären Daten und Fake-Anbietern; andere Routen liefern feste Testzustände. Unbeabsichtigte externe Verbindungen schlagen im Harness fehl.

Nach jeder Scheibe:

```powershell
& "$env:APPDATA\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe" -m unittest discover -s werkstatt\tests
```

Node-Bedientests laufen gegen echtes JavaScript mit `dom_nachbau.js`. Node-Ausführung darf bei der Abnahme nicht übersprungen sein. Neue Fakes liefern je Aufruf verschiedene Antworten und zählen Aufrufe.

### Scheibe 1 – Daten, Katalog und Regeldatei — mittel

**Umfang:** Abschnittsmetadaten, optionale Eintragsfelder, validierte Profilregeln, Optionenroute.

**Dateien:** `prompts.py`, `server.py`, `config.json`, `test_prompts.py`, `test_werkstatt.py`; zentrale Skill-Referenz `werkstatt-profile.json`.

**Tests:**

- Abschnitte nur außerhalb von Zäunen;
- sechster und künftig weiterer Abschnitt erscheinen automatisch;
- Werkstatt-Abschnitt ausgeschlossen;
- IDs, Schattenzuordnung und Altdateien unverändert;
- unbekannte Kopfzeilen und CRLF bleiben erhalten;
- fehlende/ungültige Regeln ergeben kontrollierte Fehler;
- Herkunftsschutz der neuen Route/Aktionen.

**Browser-Abnahme:** Testkatalog mit eigenen Einträgen und sechs Sammlungsgruppen laden; Reihenfolge, Kurztexte und Fehleranzeigen prüfen. Eine Testüberschrift ändern, „Neu einlesen“ wählen: neue Gruppierung ohne veränderte Eintragszuordnung.

### Scheibe 2 – Zielprofile, 27B und Abo-Kennzeichnung — mittel

**Umfang:** gezielte `llamacpp`-Erweiterung, Ziel-/Testprofilzuordnung, Abo-Metadaten und Profilverwaltung unabhängig von `ZF`.

**Dateien:** `auswertung.py`, `prompts.py`, `zusammenfassung.js`, `prompts.js`; `test_lokal.py`, `test_auswertung_prompts.py`.

**Tests:**

- beide gewünschten 27B-Einträge erscheinen; OCR und andere `llamacpp`-Modelle nicht;
- falsche Modellkennung und geschlossenes Ziel werden abgelehnt;
- Flash-Next mit gleicher Kennung und verschiedenem Kontext bleibt korrekt;
- Claude-Abo, API-Anmeldung, keine Anmeldung;
- Codex-Abo, API, unbekanntes Auth-Format;
- keine Zugangsdaten in Antworten oder Logs;
- Abo-Prüfung erneut unmittelbar vor dem Aufruf;
- Anbieteraufrufe und bestehende Zusammenfassungsprofile bleiben ansonsten unverändert.

**Browser-Abnahme:** Fake-Profile für alle Zugangszustände anzeigen; deaktivierte Auswahl mit Grund; Zielmodell trotz fehlender Laufzeit auswählbar; fehlendes Testprofil anlegen; Verwaltung direkt aus Prompts öffnen, ohne vorher Zusammenfassung besucht zu haben.

### Scheibe 3 – Mehrziel-Senden und Belege — groß

**Umfang:** Composer-Aktionen, Version-2-Auftragsbau, Idempotenz, Gruppen, Zielnamen und Sammlungsvorschläge testen.

**Dateien:** `prompts.py`, `auswertung.py`, `server.py`; `test_prompts.py`, `test_auswertung_prompts.py`, `test_werkstatt.py`.

**Tests:**

- drei Ziele ergeben einen Rohprompt, drei Belege und drei Modellaufrufe;
- Doppel-POST ergibt keine zusätzlichen Dateien oder Aufrufe;
- gleiche ID mit geändertem Inhalt ergibt 409;
- Absturz nach Reservierung, Originalanlage, Beleganlage, Einreihung und Fassungsanhang;
- identische Antworten verschiedener Ziele bleiben getrennt;
- ein fehlgeschlagenes Ziel beeinflusst andere nicht;
- Regel-/Materialänderung nach Einreihung verändert den Lauf nicht;
- alte Belege erzeugen identischen Auftrag und Hash;
- Sammlung vor/nach Schärfen und Vorschlagstest bytegleich;
- ungültiger Antwortkasten ist nicht testbar.

**Browser-Abnahme:** Drei Ziele senden, Senden doppelt auslösen, eine Antwort künstlich verzögern und eine fehlschlagen lassen. Danach Wiederholen und Nochmal getrennt prüfen. Verbindungsabbruch nach Annahme simulieren: „Status prüfen“ findet dieselbe Gruppe.

### Scheibe 4 – Oberfläche nach Vorlage — groß

**Umfang:** lokale Navigation, Composer, Zielhäkchen, Auswahlmenüs, Katalog, Zuletzt und Ergebnisansicht.

**Dateien:** `index.html`, `style.css`, `prompts.js`, gezielt `app.js`; neue `prompts_composer_bedienung.js`, bestehende Lade-/Schärfen-Bedientests und Python-Testanbindung.

**Tests:**

- Strg+Enter, Esc, Doppelklick und Fokus;
- Entwurf bleibt beim Reiterwechsel und Nachladen erhalten;
- bestehende Ladefehler- und Serialisierungstests unverändert wirksam;
- kein weiterer Zeitgeber;
- Auswahloptionen mit Namen, Untertitel und Gründen;
- Kartenklick überschreibt keinen Entwurf;
- keine sichtbaren `null`, `undefined` oder `[object Object]`;
- Kopieren verwendet ausschließlich den jeweiligen Prompttext.

**Browser-Abnahme:** Bei 1.920, 1.366, 1.024 und 390 px Breite prüfen. Neues Composer-Bild mit der Vorlage vergleichen: großer mittiger Einstieg, schmale lokale Navigation, darunter Kategorien und Karten. Anschließend alle bisherigen Bibliotheksaktionen ausführen, einschließlich A/B, Urteil, Notiz, Öffnen, Erst klären und Kürzen.

### Scheibe 5 – Material und Kontextbausteine — mittel

**Umfang:** Anhänge, explizite Kontextauswahl und kleine Kontextverwaltung.

**Dateien:** `prompts.py`, `server.py`, `prompts.js`, `app.js`; Python- und Node-Bedientests.

**Tests:**

- Datei- und Gesamtgrenzen, ungültige Formate, gesperrte Pfade;
- Browserdatei ohne erfundenen Pfad;
- Entfernen eines Anhangs verändert die nächste Vorschau;
- Standkonflikt beim Kontextbearbeiten;
- ausschließlich ausgewählte Bausteine im Auftrag;
- nachträgliche Dateibearbeitung verändert eingereihte Momentaufnahme nicht;
- Drop im Composer wechselt nicht zur Transkription;
- bestehender Drop im Testdialog bleibt funktionsfähig.

**Browser-Abnahme:** Zwei Textdateien anhängen, eine entfernen, einen Kontextbaustein auswählen und Vorschau kontrollieren. Bei Cloud-Schreibmodell zeigt die Zusammenfassung ausdrücklich, dass ausgewähltes Material mitgesendet wird. Kontext während einer geöffneten Bearbeitung extern ändern: Speichern ergibt Konflikt.

### Scheibe 6 – Gesamtabnahme und Übergabe — klein

**Umfang:** vollständige Regression und dokumentierte Übergabe.

**Abnahme:**

- fünf frische Starts direkt auf `#prompts`;
- Dienstfehler und Wiederkehr mit erhaltenem Entwurf;
- langsame Indexantwort ohne dauernde Folgeabrufe;
- Neustart mit laufenden und verwaisten Belegen;
- vollständiger Durchgang Rohprompt → zwei Ziele → Fassungen → A/B → Urteil;
- Bild-/Videotyp mit und ohne Realismus-Skill, ohne Generatoraufruf;
- keine Anfragen an produktive Ports aus dem Test-Harness;
- kein Prompt- oder Materialinhalt im Log.

Echte Abo- und lokale Modellläufe gehören zur anschließenden bewussten Abnahme durch Claude, mit kurzen Testtexten und eigenen Belegen. Lokale Modelle müssen dafür bereits von der Zentrale geladen sein. Nicht durch Tests starten.

Claude ergänzt nach Prüfung den tatsächlichen Baustand in dieser Spec sowie die relevanten Bedienungs-/Verhaltensänderungen in `README.md` und `PLAN.md`. Der Builder verändert keine fremden uncommitteten Dokumentationsänderungen und führt weder Commit noch Push aus.

## Risiken

- **Hash-Kompatibilität:** Schon kleine Änderungen am alten Schärfen-Aufbau machen vorhandene Belege unreproduzierbar. Deshalb explizite Bauversion.
- **Mehrfachläufe:** Ohne dauerhaft gespeicherte Sendungskennung können Verbindungsfehler zusätzliche Abo-Aufrufe verursachen.
- **Zielnamen und Deduplizierung:** Textgleichheit bedeutet bei mehreren Zielen nicht dieselbe Fassung.
- **Abo-Verfügbarkeit:** Konfigurierter Modellname und vorhandene Anmeldung garantieren kein verbleibendes Kontingent. Anbieterfehler bleiben sichtbar, ohne automatischen Wechsel.
- **Modellregeln:** Die erwartete Verbesserung muss mit A/B auf dem Zielmodell geprüft werden. Modellname allein belegt keinen Qualitätsgewinn.
- **Lokaler Kontext:** Qwen-Kontext stammt zunächst aus der Konfiguration, Flash-Next aus dem geladenen Zustand. Die Quellen müssen unterscheidbar bleiben.
- **Bedienzustand:** Ungezieltes Neuzeichnen kann Eingaben, Fokus und aufgeklappte Antworten verlieren. Composer und Bibliotheksinhalt getrennt behandeln.
- **Materialumfang:** Mehrere große Momentaufnahmen vergrößern Belege. Grenzen prüfen und niemals still kürzen.
- **Bekannte Grenzen:** Codex hat lesende Werkzeuge und globale Regeln; lokales Abbrechen beendet weiterhin nur das Warten, nicht zuverlässig die bereits rechnende Modellanfrage.

## Offene Entscheidungen für Sascha

| Frage | Optionen | Empfehlung und Vorgabe dieser Spec |
|---|---|---|
| Soll es zusätzlich eine helle Oberfläche geben? | Bestehendes Dunkel / umschaltbar hell und dunkel | **Entschieden 08.11.2026 (Sascha „Dunkel lassen“): dunkel**, Werkstatt-Farben bleiben. |
| Soll Diktat direkt in den Composer? | Später / zusätzliche Scheibe jetzt | **Entschieden 08.11.2026 (Sascha „Diktat später“): später**, nicht in diesem Bau. |
| Sollen neue Wissensprompts ohne vorhandenen Sammlungseintrag entstehen können? | Weiterhin zuerst in der Sammlung / gesonderter Vorschlagsprozess | Bestehenden Ablageweg erhalten. Ein neuer Vorschlagsprozess braucht eine eigene Entscheidung über Ablage und manuelle Übernahme. |
| Soll der Zielkontext auch externe Chats oder Coding-Agenten abbilden? | Werkstatt-Testumgebung / zusätzliche Einsatzorte | Zunächst Werkstatt-Testumgebung. Andere Werkzeugrechte müssen ausdrücklich als eigene Einsatzprofile beschrieben werden. |

Mehrfachwahl der Zielmodelle, OpenAI/Codex als viertes Textziel und die kleine Kontextverwaltung sind bereits konkrete Vorgaben dieser Spec.

## Nicht in dieser Runde

- Helle Gestaltung oder Änderung der Werkstatt-Farbpalette.
- Browserdiktat. Späterer Weg: `getUserMedia`/`MediaRecorder` → begrenzter lokaler Binärupload → vorhandene Transkriptionsschlange mit Platzanmeldung → Text zur Prüfung in den Composer. `/api/ablegen` genügt dafür nicht, da es vorhandene Dateien anhand von Metadaten zuordnet. Kein Cloud-Spracherkennungsfallback und keine Änderung an `watch.py`.
- Automatische Briefings, Vault-Suche oder unbemerkte Kontextübernahme.
- Bild-, PDF-, Office- oder Audioanhänge im Schärfen-Auftrag.
- Automatische Bilder-/Videoerzeugung aus den neuen Prompt-Typen.
- Automatische Übernahme von Wissensvorschlägen in die Sammlung.
- Wortgenauer Diff, automatische Qualitätsurteile, Teststatistiken oder automatische Tests nach dem Schärfen.
- Neue Programme, Modelle, Anmeldungen, API-Schlüssel, Systemänderungen oder Änderungen an `config.toml`.

## Prüfvermerk Claude (08.11.2026)

Stichproben am Code bestätigt: `Lokal._eintraege()` nimmt nur `ollama`, `ninfer`, `strata`, `polystrata`;
`qwen27-unsloth` (8106) und `qwen27-iq3s` (8103) sind `llamacpp`; `auswerter.json` hat kein Profil für 27B oder
Flash-Next (vorhanden: codex-sol, codex-luna, claude-sonnet, deepseek-flash, deepseek-pro, ornith-q5, ornith-q4,
zwei OpenRouter); `~\.codex\auth.json` hat ein Feld `auth_mode` (Wert `chatgpt`), die Abo-Erkennung für Codex
trägt also; `auswerterDialog` hängt an `ZF.stand`; die Sammlung hat den Abschnitt „6. Diese Sammlung erweitern“;
`schaerfen_uebernehmen` erkennt Vorhandenes nur am Textstand.

Lesart von Saschas Nachtrag: „27B Modell, (Flash Next) oder Claude“ als drei getrennte Ziele, OpenAI/Codex als
viertes. Entschieden 08.11.2026: dunkel, Diktat später. Die beiden übrigen Punkte der Tabelle gelten mit der
Vorgabe dieser Spec (bestehender Ablageweg für Wissensprompts, Zielkontext nur Werkstatt). Bau-Go 08.11.2026 („Ja, bauen“).

## Baustand (08.11.2026)

Gebaut von Codex Sol (gpt-6.1-sol, xhigh) im Worktree `KI-Zentrale-bau-oberflaeche`, Branch `bau/prompts-oberflaeche`
ab b22e36c, in drei Läufen desselben Threads (Scheiben 1–3, Scheiben 4–6, eine Fixrunde); Verlauf und Urteile in
[SPEC-prompts-oberflaeche-REVIEW-LOG.md](SPEC-prompts-oberflaeche-REVIEW-LOG.md). Werkstatt-Suite 403 → 470 Tests grün.

- Alle sechs Scheiben umgesetzt wie oben beschrieben. Abweichungen: keine inhaltlichen. Die Fixrunde brachte fünf
  Bedienpunkte nach (Zeilenumbruch in „Zuletzt“, Wiederholen/Abbrechen im Zielblock, kein Kasten „Auto“ in Entdecken,
  Problemhinweise nur zur Auswahl, keine doppelten Gründe in Auswahltexten).
- Regeldatei: `C:\Workstation\Skills\aktiv\prompt-schaerfen\references\werkstatt-profile.json` (Schema 1). Sols
  Vorschlag übernommen; Bild- und Videoregeln von Claude nach STUDIO.md §7 geschärft (Aussehen jeder Person, Farben
  mit Namen, Schrift wörtlich mit Anzahl, Ausschlüsse im Haupttext statt Negativ-Prompt, Freifläche, Gesprochenes als
  `<d>`-Block, Szenen trennen). Die Tests verwenden eine Kopie unter `werkstatt\tests\werkstatt-profile.json`; ein
  zusätzlicher Test prüft die echte Datei, wenn sie vorliegt.
- Abnahme-Harness `werkstatt\tests\abnahme_harness.py` (nur 127.0.0.1:3897, Fake-Anbieter). Browserabnahme durch
  Claude bei 1366, 1920 und 390 px bestanden.
- Nebenbei behoben (alle Reiter): `api()` in `app.js` meldet bei fehlender Verbindung „Die Werkstatt antwortet gerade
  nicht …“ statt „Failed to fetch“.
- Noch nicht geprüft: echte Abo- und lokale Modellläufe mit kurzen Testtexten (Scheibe 6, bewusste Abnahme nach dem
  Zusammenführen). Diktat folgt später (Entscheidung Sascha).
