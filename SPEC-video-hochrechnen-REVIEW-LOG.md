# Review-Log: Studio-Art „Video hochrechnen“

Start 05.11.2026 abends. Gegenleser Codex Astra xhigh (read-only), Thread 01a1ad31-d5e2-7652-aac9-d7bbb94caee7, MAX_ROUNDS 3.

## Runde 1 – REVISE (9 Punkte)
P1 Monitorkarte nur Sortierkriterium; P1 Nochmal-Pfad in studio.js (wiederholbar sperrt VIDEO_HILFEN, ROLLEN fehlt);
P1 nicht alle ergebnisbestimmenden Werte eingefroren; P1 Quellhash bei Nochmal neu berechnet; P2 einstellungen_aus_graph
liest Referenzgraph als video_bild/turbo; P1 überlanger Ton; P1 RAM ungeschützt, Abnahme unter anderen Bedingungen;
P2 Konverter prüft nicht verbindlich; P2 „Originalton“ ungenau.
### Claude
Alles übernommen. Zusätzlich: Ton direkt aus dem gekürzten Original in CreateVideo (kein VAEDecodeAudio).

## Runde 2 – REVISE (5 Punkte)
P1 RAM-Prüfung blockiert Folgeläufe/kein Commit; P1 LoRA/INT8 vor dem Rechnen nicht erneut geprüft; P2 „Mit Änderungen“
ohne UI-Pfad; P2 Ton nicht aufgefüllt; P2 Nochmal-Abnahme ohne echtes Neurechnen.
### Claude
Alles übernommen (warm/kalt, Hash vor jedem Lauf mit Zwischenspeicher, Mit Änderungen aus, Auffüllen wie quellton,
Nochmal nach /free).

## Runde 3 – REVISE (2 Punkte)
P1 warm-Nachweis unzuverlässig (Entladen über Zentrale ändert PID nicht); P2 Bitgleichheit im MP4 unerfüllbar (AAC).
### Claude (Entscheid, MAX_ROUNDS erreicht)
warm/kalt gestrichen; nur Commit-Spielraum (`commit_frei_mib` 36.864) gegen Absturz, physischer RAM nicht geprüft
(schlimmstenfalls langsamer). Ton: PCM bitgleich im Graph-Test, am MP4 Dauer ±1 Bild und Korrelation ≥ 0,99.
Kein offener P0/P1 aus Sicht Claude.
