# Spec: Video weicht auf den freien Prozess aus

Stand 24.11.2026, eingefroren. Auftrag Sascha („Ja, bauen“).

## Anlass

Am 24.11.2026 belegten Windows und Programme auf der Suprim (Monitorkarte, Prozess 2) mehr als 4.352 MiB. Ein
INT8-Video braucht dort 19.456 MiB (`monitorkarte`), es passte also nicht. Trotzdem gingen vier Videos an Prozess 2
und warteten dort („Wartet auf freien Grafikspeicher“), während die FE (Prozess 1) ganz frei war. Am Morgen wartete
ein Video so 22 Minuten.

Ursache im Code (`werkstatt/studio.py`):

1. `Studio._wer_zuerst` gibt ein Ein-Karten-Video dem Video-Prozess, sobald der nichts rechnet – ohne zu prüfen, ob es
   dort jetzt passt.
2. Hat ein Prozess den Auftrag genommen (`zustand 'laeuft'`, Schritt `platz`), hält er ihn fest und wartet in
   `_durchfuehren` auf seine eigene Karte, auch wenn inzwischen ein anderer Prozess frei ist.

## Ziel

Ein Video, das ganz auf eine Karte passt, rechnet auf dem freien Prozess, bei dem es **jetzt** passt. Es wartet nur
noch, wenn es gerade bei keinem freien Prozess passt.

## Begriffe

- **Ein-Karten-Video**: Auftrag, dessen Bedarf (`Studio._bedarf(a)`) `eine_ohne_monitor` oder `monitorkarte` enthält.
  Nur für diese Aufträge gilt diese Spec.
- **Passt jetzt bei Prozess `i`**: `karten_waehlen(stand, b, i)` liefert eine Verteilung mit `rang == 0` und leerem
  `fehlend`. Dieselbe Bedingung steht schon zweimal in `_wer_zuerst`; eine kleine Hilfsfunktion dafür ist erwünscht.
- **Frischer Stand**: `self._stand_zentrale`, höchstens 15 s alt (wie bisher).
- **Frei**: der Prozess ist verfügbar (Nr. 1 oder `laeuft()`) und hat keinen Auftrag mit `zustand 'laeuft'`.

## Teil A – Verteilen (`_wer_zuerst`, Video-Zweig)

Reihenfolge mit frischem Stand:

1. Der erste freie Video-Prozess, bei dem es jetzt passt.
2. Sonst der erste andere freie Prozess (nicht Video-Prozess, `videos`, `kann(b)`), bei dem es jetzt passt – das ist
   die vorhandene Schleife, die bisher nur lief, wenn alle Video-Prozesse rechnen.
3. Sonst wie bisher: der freie Video-Prozess, falls es einen gibt, sonst `video_prozesse[0]`.

Ohne frischen Stand bleibt alles wie bisher (`frei_video or video_prozesse[0]`).

Der Zweig für Bilder und Hilfsabläufe (kein Video-Prozess bevorzugt) bleibt unverändert.

## Teil B – Zurückgeben

Findet `_platz` für ein Ein-Karten-Video keinen Platz, weil Speicher fehlt (der Pfad `if fehlend:`), und würde laut
demselben, eben gelesenen Stand ein **anderer freier** Prozess das Video jetzt nehmen (es passt dort jetzt), dann geht
der Auftrag zurück in die Schlange:

- Felder wie bei einem frisch wartenden Auftrag: `zustand='wartet'`, `schritt=None`, `meldung=''`, `prozess=None`,
  `begonnen=None`. `beendet` wird **nicht** gesetzt. Alles andere am Auftrag bleibt.
- Der Wechsel geschieht unter `self._lock`, wird gespeichert (`_speichern`) und weckt die Arbeiter (`_wecker.set()`).
- Der Stand, mit dem entschieden wurde, wird als `self._stand_zentrale` gemerkt, damit `_wer_zuerst` gleich danach
  denselben Stand sieht und der andere Prozess den Auftrag nimmt.
- Steht für den Auftrag ein Abbruch an (`a['id'] in self._abbruch`), gewinnt der Abbruch: kein Zurückgeben, der
  Auftrag endet wie bisher als „abgebrochen“.
- Eine Protokollzeile ohne Prompt:
  `Studio: Auftrag <id> zurück in die Schlange (<Name dieses Prozesses> hat keinen Platz, <Name des anderen> ist frei)`.
- Der Arbeiter behandelt das Zurückgeben nicht als Ende des Auftrags: kein `fertig`/`fehler`/`abgebrochen`, kein
  `beendet`. Eine laufende Szenenfolge bleibt „laeuft“ (`_folgen_abgleichen` sieht den Auftrag als offen).

Kein Zurückgeben in diesen Fällen (alles bleibt wie bisher):

- Die Zentrale nennt Gründe (`gruende`), antwortet nicht oder lehnt die Anmeldung mit 409 ab.
- Der Auftrag ist kein Ein-Karten-Video (Bilder, Hilfsabläufe, `video_hochrechnen`, Videos über zwei Karten).
- Kein anderer Prozess ist frei, oder es passt dort jetzt nicht.

Vorschlag zur Umsetzung (nicht bindend, das Verhalten oben ist bindend): eigene Ausnahme `Zurueck`, in `_durchfuehren`
ausgelöst und in `_schleife` vor dem bisherigen `finally`-Verhalten abgefangen; die Entscheidung über `_wer_zuerst`,
das den haltenden Prozess wegen seines laufenden Auftrags schon als nicht frei sieht.

## Grenzen

- Nur `werkstatt/studio.py` und `werkstatt/tests/test_parallel.py` ändern. Keine anderen Dateien (insbesondere nicht
  `werkstatt/tests/test_studio.py`, `werkstatt/config.json`, `werkstatt/web/`, `PLAN.md`, `STUDIO.md`, `zentrale/`).
- In `studio.py` nur den Abschnitt „Ablauf“ (`_naechster` bis `_platz`) und, falls nötig, eine Ausnahmeklasse oben
  anfassen. Keine Umbenennungen, keine Formatierungsänderungen an fremden Zeilen.
- Keine neuen Einstellungen, keine neuen Zeitgeber, keine Zähler, keine Änderung an Texten der Oberfläche.
- `karten_waehlen`, `verteilungen`, `platz_fehlt`, `Instanz.kann`, `Instanz.bevorzugt` bleiben unverändert.
- Kein Commit.

## Tests (`werkstatt/tests/test_parallel.py`)

Vorhandene Helfer nutzen (`antwort`, `instanzen`, `VIDEO_INT8`, `VIDEO_EINE`). Neue Tests:

Teil A, Monitor an der Suprim, beide Prozesse laufen und sind frei, Bedarf `VIDEO_INT8`:

1. Suprim frei 19.000, FE frei 23.400 → Prozess 1 (der Fall vom 24.11.2026).
2. Suprim frei genau 19.456 → Prozess 2 (Grenze: passt bei Gleichheit).
3. Suprim frei 19.000, FE frei 5.000 → Prozess 2 (passt nirgends: wie bisher).
4. Suprim frei 19.000, FE frei 23.400, Prozess 1 rechnet → Prozess 2.
5. Prozess 2 hält eigenen Cache: Suprim frei 3.000 mit `comfy2=18000` → Prozess 2 (Zusatzbedarf 1.456 passt).
6. Stand älter als 15 s, Suprim frei 19.000, FE frei 23.400 → Prozess 2 (ohne frischen Stand unverändert).

Teil B:

7. Prozess 2 hat das Video genommen, Suprim zu voll, Prozess 1 frei und FE passt → Auftrag ist danach `wartet`,
   `prozess`/`begonnen` sind `None`, `beendet` fehlt oder ist `None`; `_naechster(Prozess 1)` liefert ihn,
   `_naechster(Prozess 2)` nicht.
8. Kein Zurückgeben, wenn Prozess 1 rechnet; wenn die FE nicht passt; bei einem Bild (`BILD`) mit fehlendem Platz.
9. Abbruch steht an → der Auftrag endet „abgebrochen“, nicht `wartet`.
10. Szenenfolge: Nach dem Zurückgeben lässt `_folgen_abgleichen` die Folge auf „laeuft“.

Anpassen erlaubt ist genau eine vorhandene Stelle: in `test_zweites_video_auf_die_fe_wenn_kein_monitor_an_den_3090`
die Behauptung „Ist Prozess 2 frei, bekommt er das Video wie bisher“ – sie benutzt einen Stand mit voller Suprim
(1.000 MiB frei) und freier FE; dort ist nach dieser Spec Prozess 1 richtig. Der Test soll „wie bisher“ mit freier
Suprim zeigen und den neuen Fall zusätzlich. Alle anderen vorhandenen Tests bleiben unverändert und grün.

## Abnahme

- `python -m unittest discover -s werkstatt\tests` und `python -m unittest discover -s zentrale\tests` grün
  (Python: `%APPDATA%\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe`).
- Am echten System (macht Claude): Suprim künstlich über die Grenze belegt, ein Video bestellt → es rechnet auf der FE.
