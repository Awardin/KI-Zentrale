'use strict';

// Reiter Bild & Video, Ansicht Studio: Bilder (Qwen-Image) und Videos (MiniMax-H3) erstellen, Bibliothek mit
// Projektordnern. Alles kommt aus dem echten Zustand des Dienstes: Aufträge, Dateien im Studio-Ordner, ComfyUI.

const ST = {
  sichtbar: false, stand: null, bib: null, bibStand: null, eingerichtet: false, projekteSchluessel: '',
  filter: { suche: '', projekt: '*', medium: 'alle' },
  auswaehlen: false, auswahl: new Set(), vorlagen: [], kacheln: new Map(), liste: [], detail: null, extra: {},
  modus: null, wahl: { bild: {}, video: {} }, referenz: { genau: 'match', ton: true },
  maske: null, vorschau: null, // Stelle verbessern: Markierung {pfad, breite, hoehe, rle, anteil} und ihr Vorschaubild
  rezept: null, // eingesetzter Moodboard-Vorschlag {name, familie, raster}: sein Rastertext passt nur zu einer Formatfamilie
  weiterNeu: 120, // Video weiterführen: gewünschte neue Bilder; beim Moduswechsel gilt die nächstliegende Länge
  // Szenenfolge (Stufe 3p), Länge null = Standard; realismus je Szene (seit 09.10.2026)
  szenen: [{ text: '', sekunden: null, realismus: false }, { text: '', sekunden: null, realismus: false }],
};

const stDatum = (t) => new Date(t * 1000).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
const stZahl = (n) => (n == null || n === '' ? '' : Number(n).toLocaleString('de-DE'));
const dateiUrl = (e) => `/studio/datei?p=${encodeURIComponent(e.pfad)}&v=${Math.round(e.zeit)}`;
const etwaDauer = (s) => {
  if (s < 90) return `etwa ${Math.max(5, Math.round(s / 5) * 5)} s`;
  if (s < 3600) return `etwa ${Math.round(s / 60)} min`;
  return `etwa ${Math.floor(s / 3600)} h ${String(Math.round((s % 3600) / 60)).padStart(2, '0')} min`;
};
const EIN = () => ST.stand?.einstellungen;
const VID = () => EIN()?.video;
const istVideo = (art) => String(art || '').startsWith('video');
const istClip = (p) => /\.(mp4|webm|mov)$/i.test(p || '');
const istDateiPfad = (p) => /^[A-Za-z]:[\\/]|^\\\\/.test(p || '');
const sekundenVon = (bilder) => stZahl(Math.round((bilder / (VID()?.fps || 24)) * 10) / 10);
// Rechenzeit eines Videos wie im Dienst (video_zeit): Grundzeit + Schritte × Sekunden je Schritt ×
// (Pixel × wirksame Bilder / 5-s-Video in 960 × 544) ^ Exponent; festgehaltene Bilder und Endbilder zählen mit.
// Neue Aufträge rechnen seit 17.10.2026 mit der schnelleren Aufmerksamkeit (eigene Sekunden je Schritt).
const videoDauer = (schritte, b, hh, bilder) => {
  const z = VID().zeit;
  if (!z) return null; // Dienst mit älterem Stand: keine Schätzung statt einer falschen
  const jeSchritt = EIN().video_schnell_verfuegbar && z.je_schritt_schnell_s ? z.je_schritt_schnell_s : z.je_schritt_s;
  return z.grund_s + jeSchritt * schritte * ((b * hh * bilder) / z.bezug) ** z.exponent;
};
const jeVideo = (s) => (s == null ? null : `${etwaDauer(s)} je Video`);
const HERKUNFT = { studio: 'Studio der Werkstatt', '2wild': '2Wild Studio', metadaten: 'aus den Metadaten der Datei', unbekannt: 'unbekannt' };
const ART = { bild: 'Neues Bild', bearbeiten: 'Bild bearbeitet', verbessern: 'Stelle verbessert', freistellen: 'Freigestellt',
  pose: 'Pose-Skelett', video_text: 'Video aus Text', video_bild: 'Video aus Bild', video_referenz: 'Video mit Referenz',
  video_weiter: 'Video weitergeführt', video_szenen: 'Szenenfolge', video_zeitlupe: 'Zeitlupe',
  video_freistellen: 'Video freigestellt', video: 'Video', modell3d: '3D-Modell' };
// Zeitlupe und Video freistellen (seit 09.10.2026): nur aus der Großansicht eines Videos, ohne Formular.
const VIDEO_HILFEN = ['video_zeitlupe', 'video_freistellen'];
// Welche Vorlagen eine Art braucht (Rollen), und wie sie heißen.
// Verbessern (Stufe 3n): `vorbild` ist das freiwillige Bild für die Stelle („Bild 2“), eine eigene Rolle, damit Vorlagen
// vom Bearbeiten beim Wechsel der Art nicht unbemerkt mitgehen.
const ROLLEN = { bearbeiten: ['vorlage'], verbessern: ['original', 'vorbild'], freistellen: ['original'], pose: ['original'],
  video_bild: ['start', 'ende'], video_referenz: ['bild', 'clip'], video_weiter: ['ausgang', 'ziel'],
  video_szenen: ['start', 'bild'], video_zeitlupe: ['original'], video_freistellen: ['original'],
  modell3d: ['vorlage'] }; // 3D-Modell (Stufe 3t): ein Drehblatt (vier Ansichten nebeneinander) oder ein Bild
const ROLLENNAME = { vorlage: 'Vorlage', original: 'Original', vorbild: 'Vorbild für die Stelle', start: 'Startbild', ende: 'Endbild',
  bild: 'Referenzbild', clip: 'Clip', ausgang: 'Clip davor', ziel: 'Clip danach' };
// Wie viele Vorbilder das Verbessern annimmt (0: Dienst mit älterem Stand, das Feld bleibt verborgen).
const maxVorbilder = () => EIN()?.verbessern?.max_vorlagen || 0;
const PLATZHALTER = {
  bild: 'Was soll entstehen? Motiv, Umgebung, Licht, Stil …',
  verbessern: 'Was soll an der markierten Stelle zu sehen sein? Zum Beispiel: „Eine natürliche, entspannte Hand mit fünf Fingern“ oder „Entferne das Schild; dort ist nur die Wand zu sehen.“',
  video: 'Wer ist zu sehen, wie sieht der Ort aus, was macht die Kamera, was wird gesagt?',
  weiter: 'Was geschieht im neuen Stück? Ort und Personen wie im Clip beschreiben, dazu Bewegung, Kamera und Gesprochenes.',
  szenen: 'Gemeinsamer Teil für alle Szenen: wer zu sehen ist (Alter, Haare, Kleidung), der Ort, Licht und Stil. Kein Gesprochenes – das gehört in die Szenen.',
};
// Video weiterführen (Stufe 3m), wie im Dienst (weiter_bereiche): Das neue Stück hält vorn die letzten 39 Bilder des
// Clips davor fest (nicht beim Davor-Setzen) und endet auf einem Endbild (nicht beim Verlängern). Clips nur aus der
// Bibliothek; `grenze` steht sichtbar im Formular.
const WEITER = {
  verlaengern: { erledigt: 'verlängert', rollen: ['ausgang'], kontext: 39, ende: 0,
    grenze: 'Das neue Stück setzt die letzten 1,6 s des Clips fort, mit Bewegung und Ton; der Clip selbst bleibt unverändert. Ort, Personen und Licht wie im Clip beschreiben. Die Bewegung am Ende setzt sich stärker durch als der Text – ein unpassendes Ende vorher kürzen.' },
  davor: { erledigt: 'Stück davor gesetzt', rollen: ['ziel'], kontext: 0, ende: 1,
    grenze: 'Das neue Stück endet genau auf dem ersten Bild des Clips. Licht und Stimmung wie am Anfang des Clips beschreiben – sonst gleicht das Modell sie in den letzten Bildern schnell an. Die Bewegung des Clips kennt es nicht; der Ton wechselt am Übergang hart.' },
  verbinden: { erledigt: 'verbunden', rollen: ['ausgang', 'ziel'], kontext: 39, ende: 1,
    grenze: 'Das neue Stück setzt die letzten 1,6 s des Clips davor fort und endet genau auf dem ersten Bild des Clips danach. Den Weg dorthin beschreiben (Tür, Blickrichtung, Raum, was dort steht) und bei verschiedenen Orten ein längeres Stück wählen – sonst springt das Bild am Ende hart hinein. Beide Clips müssen gleich groß sein; am zweiten Übergang wechselt der Ton hart.' },
  schleife: { erledigt: 'Schleife geschlossen', rollen: ['ausgang'], kontext: 39, ende: 1,
    grenze: 'Das neue Stück führt vom Ende zurück zum ersten Bild; das fertige Video lässt sich endlos wiederholen, etwa als Hintergrund einer Webseite. Gelingt am besten, wenn Anfang und Ende sich ähneln; der Ton springt an der Wiederholstelle.' },
};
// Längen des neuen Clips wie weiter_laenge im Dienst: 17k+5 Bilder zwischen 124 und 362, ohne L mod 3 = 2 (dort wäre der
// Ton des Videomodells 8 ms kürzer als das Bild).
const WEITER_LAENGEN = Array.from({ length: 15 }, (_, k) => 124 + 17 * k).filter((l) => l <= 362 && l % 3 !== 2);
const WEITER_FENSTER = 39;
const weiterModus = () => (WEITER[$('#st-modus').value] ? $('#st-modus').value : 'verlaengern');
// Beim Freistellen steht im Prompt die feste Anweisung an das Modell; gezeigt wird, was bleiben sollte.
const anzeigePrompt = (i) => (i.art === 'freistellen' ? `Freistellen: ${i.motiv || 'Hauptmotiv'}${i.verfahren === 'schnell' ? ' (schnell)' : ''}`
  : i.art === 'pose' ? 'Pose-Skelett'
    : i.art === 'modell3d' ? `3D-Modell aus ${{ drehblatt: 'Drehblatt', bild: 'einem Bild', ansichten: 'Einzelansichten' }[i.modus] || 'Vorlage'}${i.modell_3d ? ` · ${i.modell_3d}` : ''}`
      : i.prompt);
// Schnelles Freistellen (BiRefNet, Stufe 3l): ohne Beschreibung, wenn das Modell in ComfyUI liegt; mit Beschreibung Qwen.
const schnellFreistellen = () => stArt() === 'freistellen' && !$('#st-motiv').value.trim() && !!EIN()?.freistellen_schnell_verfuegbar;
// Ohne Qwen gerechnet (Pose-Skelett, schnelles Freistellen): keine Qualitätsstufe, keine Variationen.
const ohneQwen = () => stArt() === 'pose' || schnellFreistellen();
const durchsichtig = (i) => (i?.art === 'freistellen' || i?.durchsichtig === true ? 'durchsichtig' : null);
const HOCHSKALIEREN = 'Gib genau dieses Bild in hoher Auflösung wieder. Schärfe feine Details wie Haut, Haare, Stoff und Kanten natürlich nach und entferne Unschärfe, Rauschen und Kompressionsspuren. Inhalt, Personen, Farben, Licht und Bildausschnitt bleiben genau gleich.';
// Vorschläge je Art; `wahl` wird nach dem Einsetzen markiert, damit man es gleich überschreiben kann, `groesse`
// stellt beim Bearbeiten die passende Größe ein, `hinweis` sagt, welche Vorlagen es braucht.
// Moodboards (Neu): englischer Text mit festen Positionen je Format, sichtbare Texte deutsch in Anführungszeichen.
// Eingefrorener Stand nach der Abnahme am 25.09.2026 (Turbo, 4 MP): je Format drei feste Variationsnummern ohne harten
// Fehler (Quadrat und Quer 11/22/33, Hoch 11/22/55). Deutsch mit gleichem Inhalt hatte Fehler (Kleinschrift, Extra-Kachel).
// `raster` ist der Satz, an dem das Formular erkennt, dass das Raster noch im Text steht (Formatwarnung).
const MOODBOARD_HINWEIS = 'Ersetze den Namen, dann Branche, Fotomotive, die fünf Farbnamen und die Überschrift (zweimal). Englisch mit festen Positionen ist am verlässlichsten; nur Wörter in Anführungszeichen erscheinen im Bild. Format und Turbo sind gesetzt; 2–3 Variationen rechnen. Hex-Werte und Schriften gehören in die Styleguide-Notiz.';
const MOODBOARD_STIL = ' Photographic style: editorial, natural daylight, calm, trustworthy, premium but approachable, realistic skin and materials. Only the quoted words appear as text; there is no other lettering, no small text and no watermark.';
const VORSCHLAEGE = {
  moodboard_hoch: { art: 'bild', name: 'Moodboard hoch', format: 'hoch916_gross', qualitaet: '6', familie: 'hoch',
    raster: 'The grid has six rows and four columns.',
    text: 'A premium vertical brand mood board for a modern physiotherapy practice, presented as a clean bento grid in the style of a Behance brand identity presentation: a light warm off-white background with rounded rectangular tiles and even gaps. The grid has six rows and four columns. The top two rows: the left half is the brand tile, a plain off-white card that shows only the name "Physio Lindenhof" in large elegant dark serif letters; the right half is one large hero photo: a bright treatment room in soft morning light with a wooden treatment table and green plants. Third row, left half: a typography tile that shows only a very large serif "Aa". Third row, right half: a palette tile with exactly five separate rounded color swatches in one row with small gaps between them, in this order: warm off-white with a thin grey outline, sand, sage green, deep forest green, warm wood brown; color only, no labels, nothing else in this tile. Fourth row, left half: a photo of the hands of a therapist resting on the shoulder of a patient. Fourth row, right half: a detail photo of rolled white towels with a eucalyptus branch. Fifth row, left half: a single texture tile with one close-up photo of natural linen fabric draped over light oak wood. Fifth row, right half: an accent tile with a fine line drawing of a linden leaf on off-white. Sixth row, full width: one wide mockup tile with exactly one laptop and one smartphone side by side and nothing else; the laptop screen shows a large photo, the headline "Bewegung, die gut tut" and three plain grey bars; the smartphone screen shows the headline "Bewegung, die gut tut" and grey bars.' + MOODBOARD_STIL,
    wahl: 'Physio Lindenhof', hinweis: MOODBOARD_HINWEIS },
  moodboard_breit: { art: 'bild', name: 'Moodboard breit', format: 'quer169_gross', qualitaet: '6', familie: 'breit',
    raster: 'The grid has three rows of equal height and four columns.',
    text: 'A premium landscape brand mood board for a modern physiotherapy practice, presented as a clean bento grid in the style of a Behance brand identity presentation: a light warm off-white background with rounded rectangular tiles and even gaps. The grid has three rows of equal height and four columns. Top row: the first column is the brand tile, a plain off-white card that shows only the name "Physio Lindenhof" in large elegant dark serif letters; the second and third columns are one wide hero photo: a bright treatment room in soft morning light with a wooden treatment table and green plants; the fourth column is a typography tile that shows only a very large serif "Aa". Middle row: the first two columns are a palette tile with exactly five separate tall rounded color swatches in one row with small gaps between them, in this order: warm off-white with a thin grey outline, sand, sage green, deep forest green, warm wood brown; color only, no labels, nothing else in this tile; the third column is a photo of the hands of a therapist resting on the shoulder of a patient; the fourth column is a detail photo of rolled white towels with a eucalyptus branch. Bottom row: the first column is a texture tile with natural linen next to light oak wood; the second column is an accent tile with a fine line drawing of a linden leaf on off-white; the third and fourth columns are one wide mockup tile with exactly one laptop and one smartphone and nothing else; the laptop screen shows a large photo, the headline "Bewegung, die gut tut" and three plain grey bars; the smartphone screen shows the headline "Bewegung, die gut tut" and grey bars.' + MOODBOARD_STIL,
    wahl: 'Physio Lindenhof', hinweis: MOODBOARD_HINWEIS },
  moodboard_quadrat: { art: 'bild', name: 'Moodboard quadratisch', format: 'quadrat_gross', qualitaet: '6', familie: 'quadrat',
    raster: 'The grid has four rows of equal height and four columns.',
    text: 'A premium square brand mood board for a modern physiotherapy practice, presented as a clean bento grid in the style of a Behance brand identity presentation: a light warm off-white background with rounded rectangular tiles and even gaps. The grid has four rows of equal height and four columns. Top row, left half: the brand tile, a plain off-white card that shows only the name "Physio Lindenhof" in large elegant dark serif letters. The right half of the top two rows is one large hero photo: a bright treatment room in soft morning light with a wooden treatment table and green plants. Second row, first column: a typography tile that shows only a very large serif "Aa". Second row, second column: a palette tile with exactly five separate rounded color swatches in one row with small gaps between them, in this order: warm off-white with a thin grey outline, sand, sage green, deep forest green, warm wood brown; color only, no labels, nothing else in this tile. Third row, left half: a photo of the hands of a therapist resting on the shoulder of a patient. Third row, right half: a detail photo of rolled white towels with a eucalyptus branch. Bottom row, left half: a single texture tile with one close-up photo of natural linen fabric draped over light oak wood. Bottom row, right half: a mockup tile with exactly one laptop and one smartphone and nothing else; the laptop screen shows a large photo, the headline "Bewegung, die gut tut" and three plain grey bars; the smartphone screen shows the headline "Bewegung, die gut tut" and grey bars.' + MOODBOARD_STIL,
    wahl: 'Physio Lindenhof', hinweis: MOODBOARD_HINWEIS },
  hand: { art: 'verbessern', name: 'Hand reparieren', text: 'Repariere die Hand an der markierten Stelle: eine natürliche, entspannte Hand mit fünf Fingern und richtiger Anatomie, passend zu Hautton und Licht. Alles andere bleibt genau gleich.' },
  entfernen: { art: 'verbessern', name: 'Etwas entfernen', text: 'Entferne den Gegenstand. An seiner Stelle ist nur die passende Umgebung zu sehen, nahtlos und im gleichen Licht.', wahl: 'den Gegenstand' },
  // Mit Vorbild für die Stelle (Stufe 3n, 05.10.2026, STUDIO.md): Kopf aus einem Porträt 9 von 9 die Person aus Bild 2
  // (nur beschrieben eine andere), Logo-Symbol 14 von 14, Schriftzug 4 von 4 (ausgeschrieben half er nicht), Gegenstand
  // 5 von 5 vollständig. Blick und Lächeln des Porträts schlugen 5 von 9 durch; ein Hund, von dem Bild 2 nur Kopf und
  // Pfoten zeigt, kam 2 von 4 nur mit Kopf und Pfoten.
  kopf_vorbild: { art: 'verbessern', name: 'Kopf nach Vorbild',
    text: 'Der Kopf der Frau aus Bild 2: Gesicht, Frisur und Haarfarbe wie in Bild 2. Sie blickt konzentriert nach unten, ernster Ausdruck; Größe, Licht und Schärfe passen zum übrigen Bild.',
    wahl: 'Sie blickt konzentriert nach unten, ernster Ausdruck',
    hinweis: 'Kopf samt Haaren großzügig markieren. Vorbild (Bild 2): ein Porträt der Person, frontal und hell. Blick und Lächeln des Porträts schlagen oft durch – den gewünschten Ausdruck nennen und 2–3 Variationen rechnen.' },
  logo_vorbild: { art: 'verbessern', name: 'Logo nach Vorbild',
    text: 'Das Logo aus Bild 2 als kleine, saubere Stickerei auf dem Stoff: Symbol, Farben und Schriftzug genau wie in Bild 2, es folgt dem Stoff und den Falten.',
    wahl: 'als kleine, saubere Stickerei auf dem Stoff',
    hinweis: 'Die Fläche markieren, auf die das Logo soll, nicht zu knapp. Vorbild (Bild 2): die Logo-Datei. Den Schriftzug nicht ausschreiben; sehr kleine Unterzeilen werden nicht lesbar.' },
  // Stufe 3q: Person im Video tauschen; Text kommt aus der Einstellung (englische Vorlage des LoRA-Autors, {wer} ersetzt).
  tauschen: { art: 'video_referenz', name: 'Person tauschen', tauschen: true, text: '',
    hinweis: 'Clip: das Video, in dem getauscht wird (am besten 4–5 s, ohne Schnitt). Bild 1: die neue Person, ganz zu sehen, am besten freigestellt. Im Text nur ändern, wer ersetzt wird – englisch, mit Kleidung und Position (etwa „the man in the grey T-shirt on the right“). Rechnet etwa so lange wie ein doppelt so langes Video.' },
  gegenstand_vorbild: { art: 'verbessern', name: 'Gegenstand nach Vorbild',
    text: 'Auf dem Boden steht der Gegenstand aus Bild 2, ganz zu sehen und in passender Größe. Form, Farben und Material wie in Bild 2, Licht und Schatten wie im übrigen Bild.',
    wahl: 'Auf dem Boden steht der Gegenstand aus Bild 2',
    hinweis: 'Die Fläche markieren, wo er hin soll. Bild 2 sollte das Ganze zeigen: Zeigt es nur einen Teil (etwa nur Kopf und Pfoten eines Hundes), kommt oft auch nur dieser Teil.' },
  // Drehblatt (Stufe 3t, 11.10.2026): vier Ansichten im Abstand von 90° auf Schwarz, das Pixal3D zu einem 3D-Modell
  // rechnet (Art „3D-Modell“). Geprüft 11.10.2026 an der Gemüsegärtnerin: 2 von 2 mit echten Profilen; ein langer Kasten
  // (Hochbeet) drehte nicht – Gegenstände lieber als „3D aus einem Bild“ rechnen. Englisch, Panorama 4:1, Turbo.
  drehblatt_figur: { art: 'bearbeiten', name: 'Drehblatt (Figur)', groesse: 'panorama41', qualitaet: '6',
    text: 'Turn the character in image1 into an orthographic 3D modeling reference sheet: a single horizontal row of four equal-width panels, evenly spaced. From left to right: 1) front view. 2) left side view, an exact 90 degree profile, only one eye visible. 3) back view, exactly 180 degrees. 4) right side view, an exact 90 degree profile, only one eye visible. The camera orbits a completely static character: same standing pose, same clothing and same head direction in every view, the character never turns toward the camera. Identical outfit, colors, proportions and scale in all views, each character centered in its panel, feet on the same baseline, no overlap between views. Keep the style of image1 exactly. Flat, even lighting, solid black background, no text, no labels.',
    wahl: 'same standing pose, same clothing',
    hinweis: 'Vorlage 1: die Figur ganz zu sehen, am besten freigestellt oder vor ruhigem Grund. Haltung und besondere Dinge (Hut, Werkzeug in der Hand) benennen. 2 Variationen rechnen und die mit der sauberen Rückansicht nehmen; danach in der Bibliothek „3D-Modell“.' },
  drehblatt_ding: { art: 'bearbeiten', name: 'Drehblatt (Gegenstand)', groesse: 'panorama41', qualitaet: '6',
    text: 'Turn the object in image1 into an orthographic 3D modeling reference sheet: a single horizontal row of four equal-width panels, evenly spaced. From left to right: 1) front view. 2) left side view, the object rotated exactly 90 degrees so its left side faces the camera. 3) back view, rotated exactly 180 degrees. 4) right side view, rotated exactly 90 degrees the other way. The camera orbits a completely static object: identical shape, colors, materials, proportions and scale in all views, each object centered in its panel, standing on the same baseline, no overlap between views. Keep the style of image1 exactly. Flat, even lighting, solid black background, no text, no labels.',
    wahl: 'the object',
    hinweis: 'Vorlage 1: der Gegenstand ganz zu sehen, frontal. Lange Kästen (Hochbeet) drehte Qwen im Test nicht – dann lieber Art „3D-Modell“ direkt mit dem Bild (3D aus einem Bild).' },
  blatt: { art: 'bearbeiten', name: 'Charakterblatt', groesse: 'video169',
    // Nummeriert hält Qwen die Reihenfolge verlässlich ein (am 24.09.2026 geprüft: 2 von 2 Variationen mit allen vier Ansichten).
    text: 'Erstelle ein Charakterblatt der Person aus Bild 1. Gesicht, Haare, Hautton, Körperproportionen und realistisches Aussehen bleiben genau erhalten. Kleidung: ein schlichtes, eng anliegendes weißes T-Shirt, lange blaue Jeans und weiße Sneaker. Genau vier getrennte Ganzkörperansichten nebeneinander vor einem schlichten hellgrauen Studiohintergrund, von links nach rechts: 1. von vorn, 2. Dreiviertelansicht (halb zur Seite gedreht, das Gesicht noch zu sehen), 3. Profil von der Seite, 4. von hinten. Ganz rechts ein großes Porträt des Gesichts. Gleichmäßiges weiches Studiolicht, fotorealistisch.',
    wahl: 'ein schlichtes, eng anliegendes weißes T-Shirt, lange blaue Jeans und weiße Sneaker' },
  // Dieselbe Person über mehrere Bilder: Porträt als Vorlage statt Beschreibung (24.09.2026: 6 von 6 dieselbe Person,
  // nur beschrieben 2 von 2 eine andere). Geprüft wurde genau dieser Wortlaut. Ohne Haltung und Kamera stand die Figur
  // 2 von 2 nur lächelnd im Raum; ohne Beschreibung des Patienten erschien sie einmal doppelt (auch als Patientin).
  // Aussehen jeder Person nennen: ohne Angabe wirkten Gesichter bei knappen Prompts teils ostasiatisch (08.10.2026);
  // „mitteleuropäisch“ beim Patienten: 2 von 2 wie beschrieben, die Figur blieb dieselbe.
  figur: { art: 'bearbeiten', name: 'Figur in neue Szene', groesse: 'quer169',
    text: 'Die Frau aus Bild 1 behandelt in einem hellen, modernen Behandlungsraum die Schulter eines Patienten (Mitte 50, mitteleuropäisch, kurze graue Haare, hellgraues T-Shirt), der auf einer Behandlungsliege aus hellem Holz sitzt. Sie steht seitlich hinter ihm, beide Hände liegen auf seiner rechten Schulter, sie blickt freundlich zu ihm. Gesicht, Frisur, Haarfarbe und Kleidung der Frau genau wie in Bild 1. Halbnahe Aufnahme, die Kamera steht vor den beiden auf Brusthöhe, das Gesicht der Frau ist gut zu sehen. Fotorealistisch, weiches Fensterlicht, natürliche Hauttextur, ohne Schrift.',
    wahl: 'behandelt in einem hellen, modernen Behandlungsraum die Schulter eines Patienten (Mitte 50, mitteleuropäisch, kurze graue Haare, hellgraues T-Shirt), der auf einer Behandlungsliege aus hellem Holz sitzt. Sie steht seitlich hinter ihm, beide Hände liegen auf seiner rechten Schulter, sie blickt freundlich zu ihm',
    hinweis: 'Vorlage 1: ein Porträt der Figur (frontal, Brustbild). Größe: das Format der Szene. Haltung, Blick und Kamera genau beschreiben, weitere Personen mit Alter, Aussehen (etwa „mitteleuropäisch“), Haaren und Kleidung – sonst erscheint die Figur doppelt, und ohne Aussehen wirken Gesichter oft ostasiatisch. Für eine bestimmte Handlung mit zwei Personen (etwa eine Übung zeigen) erst die Szene erstellen und dann „Person einsetzen“.' },
  einsetzen: { art: 'bearbeiten', name: 'Person einsetzen', groesse: 'vorlage',
    text: 'Ersetze die Frau in Bild 1 durch die Person aus Bild 2. Gesicht, Haare und Kleidung wie in Bild 2; Umgebung, Licht und Bildausschnitt wie in Bild 1.',
    wahl: 'die Frau', hinweis: 'Vorlage 1: das Bild, das bleibt. Vorlage 2: die Person, die hinein soll.' },
  kopf: { art: 'bearbeiten', name: 'Kopf tauschen', groesse: 'vorlage',
    text: 'Ersetze den Kopf der Person in Bild 1 durch den Kopf der Person aus Bild 2: Gesicht, Frisur und Haarfarbe wie in Bild 2. Körper, Kleidung, Haltung, Umgebung und Licht bleiben wie in Bild 1; der Kopf passt in Größe und Blickrichtung zum Körper.',
    hinweis: 'Vorlage 1: das Bild, das bleibt. Vorlage 2: die Person mit dem neuen Kopf. Blick und Lächeln des Porträts schlagen oft durch. Bei mehreren Personen lieber „Stelle verbessern“ mit „Kopf nach Vorbild“ – hier fehlte einmal der zweiten Person der Kopf.' },
  // Die Farbe mit Namen nennen: Ein Hex-Code allein wurde im Test falsch umgesetzt (Rot wurde Oliv), mit Namen stimmte es.
  farbe: { art: 'bearbeiten', name: 'Farbe ändern', groesse: 'vorlage',
    text: 'Ändere die Farbe des Kleides zu einem gedeckten Stahlblau (#4A6FA5). Stoff, Falten, Licht und alles andere bleiben genau gleich.',
    wahl: 'des Kleides zu einem gedeckten Stahlblau (#4A6FA5)',
    hinweis: 'Die Farbe mit Namen nennen, den Hex-Code nur in Klammern dazu; ein Hex-Code allein wird oft falsch umgesetzt.' },
  perspektive: { art: 'bearbeiten', name: 'Andere Perspektive', groesse: 'vorlage',
    text: 'Zeige dieselbe Szene aus einem tiefen Blickwinkel: Die Kamera steht knapp über dem Boden und blickt nach oben. Personen, Kleidung, Umgebung und Licht bleiben gleich.',
    wahl: 'aus einem tiefen Blickwinkel: Die Kamera steht knapp über dem Boden und blickt nach oben' },
  ersetzen: { art: 'bearbeiten', name: 'Gegenstand ersetzen', groesse: 'vorlage',
    text: 'Ersetze die Tasse durch ein Glas Wasser, in gleicher Größe und Lage und im gleichen Licht. Alles andere bleibt genau gleich.',
    wahl: 'die Tasse durch ein Glas Wasser' },
  // Logo als Bild statt Beschreibung (24.09.2026: Symbol und Schriftzug 8 von 8 richtig). Ohne ausgeschriebenen
  // Schriftzug übernahm Qwen auch die kleine Unterzeile fehlerfrei (2 von 2); mit nur dem Hauptschriftzug im Text hatte
  // sie 2 von 2 Fehler. Etwa 2 MP, damit kleine Schrift lesbar bleibt.
  logo: { art: 'bearbeiten', name: 'Logo aufbringen', groesse: 'vorlage_1440',
    text: 'Bringe das Logo aus Bild 2 als kleine, saubere Stickerei auf die linke Brustseite der Kleidung der Person in Bild 1 an. Symbol, Farben und Schriftzug genau wie in Bild 2, gut lesbar. Alles andere bleibt genau gleich.',
    wahl: 'als kleine, saubere Stickerei auf die linke Brustseite der Kleidung der Person in Bild 1',
    hinweis: 'Vorlage 1: das Bild, auf das das Logo soll. Vorlage 2: die Logo-Datei (am besten PNG auf hellem Grund). Etwa 2 MP, damit kleine Schrift lesbar bleibt. Auf Glas dazuschreiben: „Die Scheibe bleibt durchsichtig, der Raum dahinter bleibt zu sehen.“' },
  // Pose-Skelett als Bild 1 (Stufe 3l, 27.09.2026): 12 von 12 in der vorgegebenen Haltung; aus einem Foto als Bild 1
  // früher 1 von 4. Einfache Haltungen gelangen auch nur aus Text.
  // Geräte zeigt das Skelett nicht; sie genau beschreiben (ein Übungsband hing trotzdem oft wie ein Schal).
  pose: { art: 'bearbeiten', name: 'Pose übernehmen', groesse: 'vorlage',
    text: 'Bild 1 zeigt ein Pose-Skelett. Die Person aus Bild 2 steht in genau dieser Körperhaltung in einem hellen Trainingsraum mit Holzboden. Gesicht, Haare und Kleidung wie in Bild 2. Fotorealistisch, weiches Fensterlicht.',
    wahl: 'steht in genau dieser Körperhaltung in einem hellen Trainingsraum mit Holzboden',
    hinweis: 'Vorlage 1: das Pose-Skelett (Art „Pose“ oder Großansicht „Pose-Skelett“). Vorlage 2: die Person, etwa ein Porträt; ohne Bild 2 die Person im Text beschreiben. Geräte wie ein Übungsband genau beschreiben – das Skelett zeigt nur die Haltung.' },
  hochskalieren: { art: 'bearbeiten', name: 'Hochskalieren', groesse: 'vorlage_1440', text: HOCHSKALIEREN,
    hinweis: 'Größe: wie Vorlage 1, etwa 2 MP; für noch mehr Details 4 MP wählen. Bleibt nah am Original; für schwache Fotos „Foto auffrischen“.' },
  // Mit Detail-LoRA (Elusarca): Text des LoRA-Autors, sie ist auf „enhance this image“ trainiert.
  auffrischen: { art: 'bearbeiten', name: 'Foto auffrischen', groesse: 'vorlage_1440', details: true,
    text: 'Enhance this image to high resolution with rich fine details. Sharpen textures and surfaces, add natural microdetails, and improve clarity and definition across the image while preserving the original composition, lighting, atmosphere, and visual style. The input may be an illustration or a real photograph; preserve the original style.',
    hinweis: 'Mit Detail-LoRA, für überbelichtete, unscharfe oder komprimierte Fotos (etwa 2 MP). Was genau so bleiben soll, am Ende nennen, etwa „The round grey ring on the zipper stays.“' },
  // Garten-OS-Stil (Stufe 5, 12.10.2026): Die Anweisung allein trifft den Stil; ein eigenes Edit-LoRA dafür brachte keinen
  // Gewinn (gleiches Ergebnis wie Foto + Stilvorlage, mit LoRA eher weicher). Bildaufbau, Personen und Farben bleiben.
  garten: { art: 'bearbeiten', name: 'Als Garten-Illustration', groesse: 'vorlage',
    text: 'Zeichne das Bild als Garten-Illustration: klare dunkle Konturen, flächige kräftige Farben, weiche Schatten; kein Foto, kein 3D.',
    hinweis: 'Ein Foto als Vorlage 1. Bildaufbau, Personen und Farben bleiben; Gesichter werden gezeichnet, nicht verändert. Für den Garten-OS-Look (Stilblatt S2-a).' },
};

function projektName(p) {
  if (p === '' || p == null) return 'Ohne Projekt';
  return p === EIN()?.ordner_2wild ? 'Aus 2Wild' : p;
}

function stMelden(text, ok = false) {
  $('#st-rueck').replaceChildren(text ? h('p', { class: ok ? 'ok' : 'st-fehler', text }) : '');
}

function stKnopf(text, fn, { titel, haupt, aus } = {}) {
  return h('button', {
    type: 'button', title: titel, class: `knopf knopf-klein${haupt ? ' knopf-haupt' : ''}`, disabled: aus || false,
    onclick: async (ev) => {
      ev.stopPropagation();
      ev.currentTarget.disabled = true;
      try { await fn(); } catch (err) { stMelden(err.message); }
      stAktualisieren();
    },
  }, text);
}

const studio = (daten) => api('/api/studio', daten);
const option = (value, text) => h('option', { value, text });

// ------------------------------------------------------------------ Formular

const stArt = () => document.querySelector('input[name="st-art"]:checked').value;

function gemerkt() {
  try { return JSON.parse(localStorage.getItem('werkstatt.studio') || '{}'); } catch { return {}; }
}

// Format, Qualität und Länge merkt sich das Formular getrennt für Bilder und Videos.
function wahlSichern() {
  if (!ST.modus) return;
  const w = ST.wahl[ST.modus];
  w.format = $('#st-format').value;
  w.qualitaet = $('#st-qualitaet').value;
  w.breite = $('#st-breite').value;
  w.hoehe = $('#st-hoehe').value;
  if (ST.modus === 'video') w.laenge = $('#st-laenge').value;
}

function formMerken() {
  wahlSichern();
  try {
    localStorage.setItem('werkstatt.studio', JSON.stringify({
      projekt: $('#st-projekt').value, art: stArt(), zufall: $('#st-zufall').checked, anzahl: $('#st-anzahl').value,
      prompt: $('#st-prompt').value, filter: ST.filter.projekt,
      wahl: ST.wahl, referenz: ST.referenz, staerke: $('#st-staerke').value, groesse: $('#st-groesse').value,
      motiv: $('#st-motiv').value, rezept: ST.rezept, weiter: { modus: weiterModus(), neu: ST.weiterNeu },
      szenen: ST.szenen, pruefen: $('#st-pruefen').checked,
    }));
  } catch { /* ohne Speicher geht es auch */ }
}

function setze(sel, wert, standard) {
  const el = $(sel);
  el.value = [...el.options].some((o) => o.value === String(wert)) ? String(wert) : String(standard);
}

function auswahlFuellen(modus) {
  const e = EIN();
  const v = e.video;
  const w = ST.wahl[modus] || (ST.wahl[modus] = {});
  const formate = modus === 'video' ? v.formate : e.formate;
  // „Turbo“ nur anbieten, wenn die Turbo-LoRA in ComfyUI liegt.
  const stufen = modus === 'video' ? v.qualitaet : e.qualitaet.filter((q) => !q.turbo || e.turbo_verfuegbar);
  $('#st-format').replaceChildren(...formate.map((f) => option(f.id, `${f.name} · ${f.breite} × ${f.hoehe}`)), option('eigen', 'Eigene Größe …'));
  $('#st-qualitaet').replaceChildren(...stufen.map((q) => option(q.schritte, q.name)));
  $('#st-laenge').replaceChildren(...v.laengen.map((l) => option(l.bilder, l.name)));
  setze('#st-format', w.format, (formate.find((f) => f.standard) || formate[0]).id);
  setze('#st-qualitaet', w.qualitaet, (stufen.find((q) => q.standard) || stufen[0]).schritte);
  setze('#st-laenge', w.laenge, (v.laengen.find((l) => l.standard) || v.laengen[0]).bilder);
  const raster = modus === 'video' ? 32 : 16;
  const standard = formate.find((f) => f.standard) || formate[0];
  for (const [id, wert, zweit] of [['#st-breite', w.breite, standard.breite], ['#st-hoehe', w.hoehe, standard.hoehe]]) {
    $(id).step = raster;
    $(id).max = modus === 'video' ? 2048 : e.max_seite || 2048; // Bilder bis etwa 4 MP
    $(id).value = wert || zweit;
  }
  ST.modus = modus;
}

// Nach einem Wechsel der Art: bei Wechsel zwischen Bild und Video die passenden Auswahllisten füllen.
function modusSetzen() {
  const modus = istVideo(stArt()) ? 'video' : 'bild';
  if (modus === ST.modus) return;
  wahlSichern();
  auswahlFuellen(modus);
}

function formEinrichten() {
  if (ST.eingerichtet || !EIN()) return;
  ST.eingerichtet = true;
  const m = gemerkt();
  if (m.wahl) ST.wahl = { bild: m.wahl.bild || {}, video: m.wahl.video || {} };
  if (m.referenz) ST.referenz = { genau: m.referenz.genau === 'max' ? 'max' : 'match', ton: m.referenz.ton !== false };
  const radio = document.querySelector(`input[name="st-art"][value="${m.art}"]`);
  if (radio) radio.checked = true;
  if (m.zufall === false) $('#st-zufall').checked = false;
  if (m.anzahl) $('#st-anzahl').value = m.anzahl;
  for (const k of ['prompt', 'motiv']) if (m[k]) $(`#st-${k}`).value = m[k];
  ST.rezept = m.rezept && FAMILIEN[m.rezept.familie] && m.rezept.raster ? m.rezept : null;
  if (m.weiter) {
    setze('#st-modus', m.weiter.modus, 'verlaengern');
    if (+m.weiter.neu > 0) ST.weiterNeu = +m.weiter.neu;
  }
  if (Array.isArray(m.szenen) && m.szenen.length) {
    ST.szenen = m.szenen.slice(0, 8).map((s) => ({ text: String(s?.text || ''), sekunden: Number.isFinite(s?.sekunden) ? s.sekunden : null,
      realismus: s?.realismus === true }));
  }
  if (m.pruefen === false) $('#st-pruefen').checked = false;
  ST.projektGemerkt = m.projekt;
  if (m.filter != null) ST.filter.projekt = m.filter;
  const staerken = EIN().verbessern.staerken;
  $('#st-staerke').replaceChildren(...staerken.map((s) => option(s.wert, `${s.name}: ${s.text}`)));
  setze('#st-staerke', m.staerke, (staerken.find((s) => s.standard) || staerken[0]).wert);
  // Größe beim Bearbeiten: wie Vorlage 1 (Standard, auch hochskaliert) oder ein Bildformat, etwa für ein Charakterblatt.
  const stufen = (EIN().bearbeiten_aufloesungen || []).filter((a) => a.wert !== EIN().bearbeiten_aufloesung);
  $('#st-groesse').replaceChildren(option('vorlage', 'Wie Vorlage 1'), ...stufen.map((a) => option(`vorlage_${a.wert}`, a.name)),
    ...EIN().formate.map((f) => option(f.id, `${f.name} · ${f.breite} × ${f.hoehe}`)), option('eigen', 'Eigene Größe …'));
  setze('#st-groesse', m.groesse, 'vorlage');
  auswahlFuellen(istVideo(stArt()) ? 'video' : 'bild');
  formAnpassen();
}

function formatListe() {
  return ST.modus === 'video' ? VID().formate : EIN().formate;
}

// Beim Bearbeiten gilt die eigene Größenwahl (#st-groesse), sonst das Format.
const formatWahl = () => (stArt() === 'bearbeiten' ? $('#st-groesse') : $('#st-format'));
// Bearbeiten „wie Vorlage 1“: Seitenverhältnis von Vorlage 1, in Standardgröße oder hochskaliert (`vorlage_<Auflösung>`).
const wieVorlage = () => $('#st-groesse').value.startsWith('vorlage');
const standardAufl = () => EIN()?.bearbeiten_aufloesung || 1024;
const hochskaliertAuf = () => +(/^vorlage_(\d+)$/.exec($('#st-groesse').value)?.[1] || 0) || null;
const etwaMP = (aufl) => `etwa ${Math.max(1, Math.round((aufl * aufl) / 1e6))} MP`;

function groesse() {
  if (formatWahl().value === 'eigen') return [+$('#st-breite').value || 0, +$('#st-hoehe').value || 0];
  const f = formatListe().find((x) => x.id === formatWahl().value) || formatListe()[0];
  return [f.breite, f.hoehe];
}

// Moodboard-Vorschläge beschreiben ein Raster für eine Formatfamilie. Passt das gewählte Format nicht mehr, warnt das
// Formular; den Text der Nutzerin schreibt es nie um. Bekannte Formate sind ihrer Familie fest zugeordnet (die großen
// Formate sind gerundet), eigene Größen dürfen im Seitenverhältnis höchstens 2 % abweichen.
const FAMILIEN = { hoch: 'zum Hochformat 9:16 oder 2:3', breit: 'zum Querformat 16:9', quadrat: 'zum Quadrat' };
const FORMAT_FAMILIE = { hoch916: 'hoch', hoch916_gross: 'hoch', video916: 'hoch', quer169: 'breit', quer169_gross: 'breit',
  video169: 'breit', quadrat: 'quadrat', quadrat_gross: 'quadrat' };

function formatFamilie() {
  const id = $('#st-format').value;
  if (id !== 'eigen') return FORMAT_FAMILIE[id] || null;
  const [b, hh] = groesse();
  const passt = (ziel) => b > 0 && hh > 0 && Math.abs(b / hh / ziel - 1) <= 0.02;
  if (passt(9 / 16) || passt(2 / 3)) return 'hoch';
  if (passt(16 / 9)) return 'breit';
  return passt(1) ? 'quadrat' : null;
}

function rezeptHinweis() {
  const prompt = $('#st-prompt').value;
  if (ST.rezept && !prompt.trim()) ST.rezept = null; // geleertes Feld beendet die Zuordnung
  const r = ST.rezept;
  let text = '';
  if (r && stArt() === 'bild') {
    if (!prompt.includes(r.raster)) text = 'Rasterzuordnung ungeprüft: Der Rastersatz des Moodboard-Vorschlags steht nicht mehr im Text.';
    else if (formatFamilie() !== r.familie) text = `Das Raster im Text passt nur ${FAMILIEN[r.familie]}. Für dieses Format den passenden Moodboard-Vorschlag wählen.`;
  }
  $('#st-rezept-hinweis').textContent = text;
  $('#st-rezept-hinweis').hidden = !text;
}

// „Neues Stück“: zu jeder möglichen Clip-Länge die tatsächlich neuen Sekunden des Modus. Nach einem Moduswechsel gilt die
// Länge, die dem Wunsch (ST.weiterNeu, neue Bilder) am nächsten kommt.
function weiterNeuFuellen() {
  const sel = $('#st-neu');
  const modus = weiterModus();
  if (sel.dataset.modus === modus) return;
  const m = WEITER[modus];
  sel.dataset.modus = modus;
  sel.replaceChildren(...WEITER_LAENGEN.map((l) => option(l, `${sekundenVon(l - m.kontext - m.ende)} s`)));
  const abstand = (l) => Math.abs(l - m.kontext - m.ende - ST.weiterNeu);
  sel.value = String(WEITER_LAENGEN.reduce((x, l) => (abstand(l) < abstand(x) ? l : x)));
}

// Clip-Länge, neue und gesamte Bilder aus der Wahl im Formular (wie weiter_bereiche im Dienst). Die Länge der Clips kommt
// aus der Bibliothek; der Dienst prüft beim Erstellen die echte Datei.
function weiterWerte() {
  const modus = weiterModus();
  const m = WEITER[modus];
  const fps = VID()?.fps || 24;
  const laenge = +$('#st-neu').value || WEITER_LAENGEN[0];
  const schnitt = (sel, rolle) => (m.rollen.includes(rolle) ? Math.max(0, Math.round((+$(sel).value || 0) * fps)) : 0);
  // undefined: nicht gebraucht; null: noch nicht gewählt
  const clip = (rolle) => {
    if (!m.rollen.includes(rolle)) return undefined;
    const v = ST.vorlagen.find((x) => x.rolle === rolle);
    return v ? ST.bib?.eintraege.find((x) => x.pfad === v.pfad)?.info || {} : null;
  };
  const a = clip('ausgang');
  const z = clip('ziel');
  const e = schnitt('#st-schnitt-ende', 'ausgang');
  const b = schnitt('#st-schnitt-anfang', 'ziel');
  const neu = laenge - m.kontext - m.ende;
  const teil = (x, weg) => (x === undefined ? 0 : x?.laenge_bilder ? x.laenge_bilder - weg : NaN);
  const gesamt = neu + teil(a, e) + teil(z, b);
  return { modus, m, fps, laenge, neu, e, b, a, z, gesamt: Number.isFinite(gesamt) ? gesamt : null };
}

// Was sich vor dem Erstellen schon sagen lässt (der Dienst prüft dasselbe an den echten Dateien).
function weiterHinweis(w) {
  let text = '';
  const s = (bilder) => stZahl(Math.round((bilder / w.fps) * 10) / 10);
  if (w.a?.laenge_bilder && w.a.laenge_bilder - w.e < WEITER_FENSTER) {
    text = `Nach dem Kürzen bleiben vom Clip ${s(Math.max(0, w.a.laenge_bilder - w.e))} s; zum Anschließen braucht es mindestens 1,6 s.`;
  } else if (w.z?.laenge_bilder && w.z.laenge_bilder - w.b < 1) {
    text = 'Der Clip danach ist kürzer als das, was am Anfang wegfallen soll.';
  } else if (w.a?.breite && w.z?.breite && (w.a.breite !== w.z.breite || w.a.hoehe !== w.z.hoehe)) {
    text = `Die Clips sind verschieden groß (${w.a.breite} × ${w.a.hoehe} und ${w.z.breite} × ${w.z.hoehe}); verbinden lassen sich nur gleich große.`;
  } else if (w.gesamt && w.gesamt > 60 * w.fps) {
    text = `Das fertige Video wäre ${s(w.gesamt)} s lang; mehr als 60 s sind nicht vorgesehen.`;
  }
  $('#st-weiter-hinweis').textContent = text;
  $('#st-weiter-hinweis').hidden = !text;
}

function formAnpassen() {
  if (!EIN()) return;
  const e = EIN();
  const v = e.video;
  const art = stArt();
  const video = istVideo(art);
  const verbessern = art === 'verbessern';
  const freistellen = art === 'freistellen';
  const pose = art === 'pose';
  const weiter = art === 'video_weiter'; // Größe und Länge kommen aus den Clips
  const szenen = art === 'video_szenen'; // Szenenfolge (Stufe 3p): Längen je Szene
  const ohne = ohneQwen(); // Pose-Skelett, schnelles Freistellen
  const modell = art === 'modell3d'; // 3D-Modell (Stufe 3t): ohne Prompt und Qualitätsstufe, dafür Detailstufe
  const bearbeiten = art === 'bearbeiten' || verbessern || freistellen || pose; // kein Format: die Größe kommt aus dem Bild
  // Beim Bearbeiten darf man stattdessen ein Format wählen (etwa für ein Charakterblatt); Standard: wie Vorlage 1.
  const ausVorlage = verbessern || freistellen || pose || (art === 'bearbeiten' && wieVorlage());
  const zufall = $('#st-zufall').checked;
  $('#st-art-pose').hidden = !e.pose_verfuegbar && !pose;
  $('#st-art-modell3d').hidden = !e.modell3d_verfuegbar && !modell;
  $('#st-modell-stufe-feld').hidden = !modell;
  if (modell) modellStufenFuellen();
  $('#st-vorlagen-feld').hidden = !ROLLEN[art];
  $('#st-format-feld').hidden = bearbeiten || weiter || modell;
  $('#st-modus-feld').hidden = !weiter;
  $('#st-neu-feld').hidden = !weiter;
  $('#st-schnitt-feld').hidden = !weiter;
  if (weiter) {
    const rollen = WEITER[weiterModus()].rollen;
    $('#st-schnitt-ende-feld').hidden = !rollen.includes('ausgang');
    $('#st-schnitt-anfang-feld').hidden = !rollen.includes('ziel');
    $('#st-schnitt-ende-text').textContent = rollen.length > 1 ? 'Clip davor: Ende kürzen um (s)' : 'Ende des Clips kürzen um (s)';
    $('#st-schnitt-anfang-text').textContent = rollen.length > 1 ? 'Clip danach: Anfang kürzen um (s)' : 'Anfang des Clips kürzen um (s)';
    weiterNeuFuellen();
  }
  $('#st-groesse-feld').hidden = art !== 'bearbeiten';
  $('#st-staerke-feld').hidden = !verbessern;
  $('#st-stelle-feld').hidden = !verbessern || !e.finden_verfuegbar;
  $('#st-qualitaet').closest('label').hidden = ohne || modell;
  document.querySelector('.st-variation').hidden = ohne;
  // Beim Freistellen sagt man nur, was bleiben soll; die Anweisung an das Modell ist fest. Pose braucht keinen Text.
  $('#st-prompt-feld').hidden = freistellen || pose || modell;
  $('#st-motiv-feld').hidden = !freistellen;
  $('#st-details-feld').hidden = art !== 'bearbeiten' || !e.details_verfuegbar;
  const details = !$('#st-details-feld').hidden && $('#st-details').checked;
  $('#st-durchsichtig-feld').hidden = art !== 'bild' || !e.durchsichtig_verfuegbar;
  const freigestellt = !$('#st-durchsichtig-feld').hidden && $('#st-durchsichtig').checked;
  // Ausformulieren nur für neue Bilder ohne durchsichtigen Hintergrund (der Rahmen-Prompt braucht die Beschreibung selbst).
  $('#st-ausformulieren-feld').hidden = art !== 'bild' || !e.ausformulieren_verfuegbar || freigestellt;
  const ausformulieren = !$('#st-ausformulieren-feld').hidden && $('#st-ausformulieren').checked;
  // Realism-LoRA (Stufe 3o): alle Videoarten, wenn die LoRA in ComfyUI liegt; nur auf Wunsch (Räume ohne Personen litten).
  // In der Szenenfolge hat jede Szene ihr eigenes Häkchen (seit 09.10.2026).
  $('#st-realismus-feld').hidden = !video || !e.realismus_verfuegbar || szenen;
  // Person tauschen (Stufe 3q): nur bei „Video mit Referenz“.
  $('#st-tauschen-feld').hidden = art !== 'video_referenz' || !e.tauschen_verfuegbar;
  vorschlaegeZeichnen(art);
  $('#st-eigen').hidden = ausVorlage || weiter || formatWahl().value !== 'eigen';
  $('#st-laenge-feld').hidden = !video || weiter || szenen;
  $('#st-szenen-feld').hidden = !szenen;
  $('#st-pruefen-feld').hidden = !szenen;
  if (szenen) szenenZeichnen();
  $('#st-video-tipp').hidden = !video;
  $('#st-prompt').placeholder = szenen ? PLATZHALTER.szenen : weiter ? PLATZHALTER.weiter : video ? PLATZHALTER.video
    : verbessern ? PLATZHALTER.verbessern : PLATZHALTER.bild;
  $('#st-variation').disabled = zufall;
  $('#st-anzahl-feld').hidden = !zufall;
  $('#st-variation-tipp').textContent = video ? 'Gleiche Nummer und gleiche Einstellungen ergeben dasselbe Video.'
    : 'Gleiche Nummer und gleicher Text ergeben dasselbe Bild.';
  const schritte = +$('#st-qualitaet').value;
  const q = (video ? v.qualitaet : e.qualitaet).find((x) => x.schritte === schritte);
  const f = formatListe().find((x) => x.id === formatWahl().value);
  const teile = [q ? `${q.name}: ${q.text}` : `${schritte} Schritte`];
  $('#st-weiter-hinweis').hidden = !weiter;
  if (weiter) {
    // Gerechnet wird der ganze neue Clip (mit den festgehaltenen Bildern), in der Größe der Clips.
    const w = weiterWerte();
    const quelle = w.a || w.z;
    const [b, hh] = quelle?.breite && quelle?.hoehe ? [quelle.breite, quelle.hoehe] : groesse();
    teile.push(jeVideo(videoDauer(schritte, b, hh, w.laenge + w.m.kontext + w.m.ende)));
    teile.push(`neues Stück ${sekundenVon(w.neu)} s${w.gesamt ? `, fertiges Video ${sekundenVon(w.gesamt)} s` : ''}`);
    if (realismusAn()) teile.push('mit Realism-LoRA');
    const genau = (bilder) => stZahl(Math.round((bilder / w.fps) * 100) / 100);
    if (w.e) teile.push(`am Ende ${genau(w.e)} s (${w.e} Bilder) weg`);
    if (w.b) teile.push(`am Anfang ${genau(w.b)} s (${w.b} Bilder) weg`);
    weiterHinweis(w);
  } else if (szenen) {
    // Szene 1 rechnet wie „Aus Text“ (mit Startbild ein Bild mehr), jede weitere wie „Verlängern“ (39 Bilder festgehalten).
    const [b, hh] = groesse();
    const start = ST.vorlagen.some((x) => x.rolle === 'start') ? 1 : 0;
    let zeit = 0;
    let fertig = 0;
    ST.szenen.forEach((s, i) => {
      const l = szeneLaenge(s, i);
      zeit += videoDauer(schritte, b, hh, l.bilder + (i === 0 ? start : 0)) ?? 0;
      fertig += l.neu;
    });
    teile.push(`${ST.szenen.length} ${ST.szenen.length === 1 ? 'Szene' : 'Szenen'}, zusammen ${etwaDauer(zeit)} Rechenzeit`,
      `fertiges Video ${sekundenVon(fertig)} s`);
    if (fertig > 60 * (v.fps || 24)) teile.push('mehr als 60 s sind nicht vorgesehen – Szenen kürzen oder weglassen');
    teile.push($('#st-pruefen').checked ? 'nach jeder Szene oben in der Bibliothek „Passt“ oder „Nochmal“'
      : 'alle Szenen laufen ohne Halt durch');
    const real = EIN()?.realismus_verfuegbar ? ST.szenen.map((s, i) => (s.realismus ? i + 1 : 0)).filter(Boolean) : [];
    if (real.length) teile.push(real.length === ST.szenen.length ? 'alle Szenen mit Realism-LoRA'
      : `Realism-LoRA in Szene ${real.join(', ')}`);
  } else if (video) {
    const [b, hh] = groesse();
    // Start- und Endbild rechnet das Videomodell als eigene Bilder mit.
    const schluessel = art === 'video_bild' ? ST.vorlagen.filter((x) => ['start', 'ende'].includes(x.rolle)).length : 0;
    // Mit Referenz rechnen die Bilder der Clips und die Referenzbilder mit (seit 09.10.2026, wie im Dienst).
    const ref = art === 'video_referenz' ? ST.vorlagen.reduce((n, x) => n + (x.rolle === 'bild' ? 1
      : x.rolle === 'clip' ? (ST.bib?.eintraege.find((y) => y.pfad === x.pfad)?.info?.laenge_bilder || 0) : 0), 0) : 0;
    teile.push(jeVideo(videoDauer(schritte, b, hh, +$('#st-laenge').value + schluessel + ref)));
    if (tauschenAn()) teile.push('Person tauschen: genau ein Clip und ein Bild der neuen Person');
    if (art === 'video_referenz' && ST.referenz.genau === 'max') teile.push('„so genau wie möglich“ kann mehrfach so lange dauern');
    if (realismusAn()) teile.push('mit Realism-LoRA: natürlichere Haut bei Personen; für Räume ohne Personen weglassen');
  } else if (modell) {
    teile.length = 0;
    const z = (e.modell3d_zeit || {})[$('#st-modell-stufe').value];
    teile.push(`${z ? `etwa ${etwaDauer(z)}` : 'einige Minuten'} je Modell (Pixal3D auf der RTX 3090 FE)`,
      'ergibt eine 3D-Datei (GLB mit Texturen) und als Vorschau einen Drehteller als kurzes Video',
      e.modell3d_bild_verfuegbar ? 'Vorlage: ein Drehblatt mit vier Ansichten (Vorschlag „Drehblatt“ beim Bearbeiten) oder ein einzelnes Bild'
        : 'Vorlage: ein Drehblatt mit vier Ansichten (Vorschlag „Drehblatt“ beim Bearbeiten); „aus einem Bild“ ist nicht eingerichtet');
  } else if (ohne) {
    teile.length = 0;
    teile.push('etwa 1–2 s (beim ersten Mal kommt das Laden des Modells dazu)');
    if (pose) teile.push('ergibt eine Strichfigur auf Schwarz in Originalgröße; dann beim Bearbeiten als Bild 1 mit dem Vorschlag „Pose übernehmen“');
    else teile.push('Hauptmotiv schnell freigestellt: feine Haare bleiben, auf dunklem Grund evtl. ein heller Saum; mit Beschreibung stellt Qwen frei (15–30 s)');
  } else {
    const aufl = (art === 'bearbeiten' && hochskaliertAuf()) || standardAufl();
    const [b, hh] = ausVorlage ? [aufl, aufl] : groesse();
    const flaeche = (b * hh) / (1328 * 1328);
    // Wie Vorlage 1 und Freistellen: Die Vorlage wird in derselben Größe mitgerechnet (mehr als linear, siehe Dienst).
    const vz = e.vorlage_zeit || {};
    const mitVorlage = freistellen || (art === 'bearbeiten' && ausVorlage);
    // Offizielles Turbo-Modell (seit 11.10.2026): 8 Schritte ohne LoRA-Aufschlag; die Viggle-LoRA 6 Schritte mit Aufschlag.
    const turboModell = !!q?.turbo && !!e.turbo_modell_verfuegbar;
    const faktor = (q?.turbo && !turboModell ? e.turbo_zeitfaktor || 1 : 1) * (mitVorlage ? (vz.fest ?? 1) + (vz.je_flaeche ?? 0) * flaeche : 1);
    const extra = ausformulieren ? e.ausformulieren_sekunden || 15 : 0;
    // Verbessern mit Vorbild (Stufe 3n): Bild 2 rechnet mit etwa 1 MP mit (wie _vorlage_faktor im Dienst).
    const vorbilder = verbessern ? ST.vorlagen.filter((x) => x.rolle === 'vorbild').length : 0;
    const vb = e.verbessern || {};
    const mitVorbild = 1 + (vb.vorlage_zeitfaktor ?? 0.55) * vorbilder * (vb.vorlage_megapixel ?? 1) * 1024 * 1024 / (b * hh);
    // Nachgelernt aus den eigenen fertigen Aufträgen je Gruppe (Schlüssel wie zeit_gruppe im Dienst, seit 09.10.2026).
    const anzahl = art === 'bearbeiten' ? ST.vorlagen.filter((x) => x.rolle === 'vorlage').length : vorbilder;
    const gruppe = [art, mitVorlage ? 'vorlage' : 'format', Math.min(anzahl, 2), q?.turbo ? (turboModell ? 'turbom' : 'turbo') : 'normal', ausformulieren ? 'ausf' : '-'].join('|');
    const korr = e.zeit_korrektur?.[gruppe] ?? e.zeit_korrektur?.standard ?? 1;
    const n = turboModell ? e.turbo_modell_schritte || schritte : schritte;
    teile.push(`${etwaDauer((e.sekunden_je_schritt * n * flaeche * faktor * mitVorbild + extra) * korr)} je Bild`);
    if (verbessern) teile.push(vorbilder ? 'neu gerechnet wird nur die Stelle, mit dem Vorbild als Bild 2' : 'neu gerechnet wird nur die markierte oder gefundene Stelle');
    else if (freistellen) teile.push('das Motiv behält seine Pixel, alles andere wird durchsichtig (PNG in Originalgröße)');
    else if (ausVorlage) teile.push(`Seitenverhältnis von der ersten Vorlage, ${etwaMP(aufl)}${hochskaliertAuf() ? ', hochskaliert' : ''}`);
    else if (art === 'bearbeiten') teile.push('neue Fläche in diesem Format, etwa für ein Charakterblatt oder eine Figur in neuer Szene; für kleine Änderungen „Wie Vorlage 1“');
    if (details) teile.push('mit Detail-LoRA: kann Kleinigkeiten verändern');
    if (freigestellt) teile.push('Motiv mit durchsichtigem Hintergrund (PNG); nur das Motiv beschreiben');
    if (ausformulieren) teile.push('ein Sprachmodell schreibt zuerst eine ausführliche Beschreibung (steht danach in der Großansicht); es erfindet gern Schrift – soll keine ins Bild, „ohne Schrift“ in den Wunsch schreiben');
  }
  if (!ausVorlage && art !== 'bearbeiten' && !weiter && f?.hinweis) teile.push(f.hinweis);
  $('#st-schaetzung').textContent = teile.filter(Boolean).join(' · ');
  rezeptHinweis();
  vorlagenZeichnen();
  erstellenKnopf();
  formMerken();
}

const realismusAn = () => !$('#st-realismus-feld').hidden && $('#st-realismus').checked;
const tauschenAn = () => !$('#st-tauschen-feld').hidden && $('#st-tauschen').checked;

function comfyBereit() {
  const c = ST.stand?.comfy;
  return !!(c && c.laeuft && c.ordner_ok);
}

function erstellenKnopf() {
  $('#st-erstellen').disabled = !comfyBereit() || ST.sendet;
  const n = $('#st-zufall').checked ? +$('#st-anzahl').value : 1;
  const was = istVideo(stArt()) ? 'Videos' : 'Bilder';
  let text = n > 1 && !ohneQwen() ? `${n} ${was} erstellen` : 'Erstellen';
  if (stArt() === 'verbessern' && !aktuelleMaske() && !stelleWort()) text = original() ? 'Erst die Stelle markieren …' : 'Erst ein Bild wählen';
  if (['freistellen', 'pose'].includes(stArt()) && !original()) text = 'Erst ein Bild wählen';
  if (stArt() === 'video_weiter' && weiterFehlt()) text = weiterFehlt();
  if (stArt() === 'video_szenen') text = `Szenenfolge starten (${ST.szenen.length} ${ST.szenen.length === 1 ? 'Szene' : 'Szenen'})`;
  $('#st-erstellen').textContent = ST.sendet ? 'Wird übergeben …' : text;
}

// Video weiterführen: Welcher Clip fehlt noch? (Text für den Knopf, sonst leer)
function weiterFehlt() {
  const rollen = WEITER[weiterModus()].rollen;
  const fehlt = rollen.filter((r) => !ST.vorlagen.some((v) => v.rolle === r));
  if (!fehlt.length) return '';
  if (fehlt.length > 1) return 'Erst beide Clips wählen';
  return rollen.length > 1 ? `Erst den ${ROLLENNAME[fehlt[0]]} wählen` : 'Erst einen Clip wählen';
}

function comfyHinweis() {
  const c = ST.stand?.comfy;
  const box = $('#st-comfy-hinweis');
  let text = '';
  if (!ST.stand) text = 'Der Dienst der Werkstatt antwortet nicht.';
  else if (!c.laeuft) text = 'Bild & Video ist aus. Starte es in der Modellzentrale; sie prüft vorher den Platz auf den Grafikkarten.';
  else if (!c.ordner_ok) text = 'ComfyUI speichert noch in seinen alten Ausgabeordner. Beende Bild & Video in der Modellzentrale einmal und starte es neu, dann landen die Dateien direkt im Studio.';
  box.hidden = !text;
  if (text) {
    box.replaceChildren(h('p', { text }), h('button', {
      class: 'knopf knopf-klein', type: 'button', onclick: () => api('/api/zentrale', {}).catch(() => {}),
    }, 'Modellzentrale öffnen'));
  }
  erstellenKnopf();
}

function projekteFuellen() {
  const pr = ST.stand.projekte;
  const schluessel = pr.map((p) => `${p.name}:${p.anzahl}`).join('|');
  if (schluessel === ST.projekteSchluessel) return;
  ST.projekteSchluessel = schluessel;
  const eigene = pr.filter((p) => !p.aus_2wild);
  const wahl = $('#st-projekt');
  const vorher = wahl.value || ST.projektGemerkt || '';
  wahl.replaceChildren(option('', 'Ohne Projekt'), ...eigene.map((p) => option(p.name, p.name)));
  wahl.value = eigene.some((p) => p.name === vorher) ? vorher : '';
  const ziel = $('#st-ziel-projekt');
  const zielVorher = ziel.value;
  ziel.replaceChildren(option('', 'nach: Ohne Projekt'), ...eigene.map((p) => option(p.name, `nach: ${p.name}`)));
  if (eigene.some((p) => p.name === zielVorher)) ziel.value = zielVorher;
  const filter = $('#st-filter-projekt');
  filter.replaceChildren(option('*', 'Alle Projekte'), option('', 'Ohne Projekt'),
    ...pr.map((p) => option(p.name, `${projektName(p.name)} (${p.anzahl})`)));
  filter.value = ST.filter.projekt === '*' || ST.filter.projekt === '' || pr.some((p) => p.name === ST.filter.projekt) ? ST.filter.projekt : '*';
  ST.filter.projekt = filter.value;
}

// ------------------------------------------------------------------ Vorlagen

// Adresse, unter der die Werkstatt eine Vorlage zeigt: Bibliothek direkt, Bilder von außerhalb nur, wenn sie selbst
// gewählt wurden oder das Studio-Bild `von` auf sie verweist (prüft der Dienst).
function bildUrl(v, von) {
  if (v.art === 'bibliothek') {
    const e = ST.bib?.eintraege.find((x) => x.pfad === v.pfad);
    return e ? dateiUrl(e) : `/studio/datei?p=${encodeURIComponent(v.pfad)}`;
  }
  return `/studio/vorlage?p=${encodeURIComponent(v.pfad)}${von ? `&von=${encodeURIComponent(von)}` : ''}`;
}

const original = () => ST.vorlagen.find((v) => v.rolle === 'original');
// Stelle per Wort (SAM3, Stufe 3l): nur beim Verbessern, wenn eingerichtet; eine gemalte Markierung hat Vorrang.
const stelleWort = () => (stArt() === 'verbessern' && EIN()?.finden_verfuegbar ? $('#st-stelle').value.trim() : '');
// Die Markierung gilt nur für das Bild, auf dem sie gemalt wurde.
const aktuelleMaske = () => (ST.maske && ST.maske.pfad === original()?.pfad ? ST.maske : null);

async function markieren() {
  const o = original();
  if (!o) return;
  try {
    const m = await maskeBearbeiten({ url: bildUrl(o, ST.extra?.quelle), maske: aktuelleMaske(),
      titel: `Stelle markieren: ${o.pfad.split(/[\\/]/).pop()}` });
    if (m) {
      ST.maske = { ...m, pfad: o.pfad };
      formAnpassen();
      stMelden('Stelle markiert. Beschreibe, was dort zu sehen sein soll, dann „Erstellen“.', true);
      $('#st-prompt').focus();
    }
  } catch {
    stMelden('Das Bild ließ sich nicht laden. Gibt es die Datei noch?');
  }
}

function vorschlagEinsetzen(name) {
  const v = VORSCHLAEGE[name];
  const p = $('#st-prompt');
  p.value = v.text;
  if (v.tauschen) {
    // Vorlage aus der Werkstatt-Einstellung; markiert wird, wer ersetzt wird.
    v.wahl = EIN()?.tauschen_wer || 'the woman';
    p.value = (EIN()?.tauschen_vorlage || 'Replace only {wer} in <Video 1> with the character in <Picture 1>.').replace('{wer}', v.wahl);
    $('#st-tauschen').checked = true;
  }
  if (v.groesse && [...$('#st-groesse').options].some((o) => o.value === v.groesse)) $('#st-groesse').value = v.groesse;
  // Neue Bilder (Moodboards) bringen ihr Format und ihre Qualität mit; beides bleibt im Formular sichtbar und änderbar.
  if (v.format) setze('#st-format', v.format, $('#st-format').value);
  if (v.qualitaet) setze('#st-qualitaet', v.qualitaet, $('#st-qualitaet').value);
  ST.rezept = v.familie ? { name, familie: v.familie, raster: v.raster } : null;
  if (v.art === 'bearbeiten') $('#st-details').checked = !!v.details && !!EIN().details_verfuegbar;
  formAnpassen();
  stMelden(v.hinweis || '', true);
  p.focus();
  const anfang = v.wahl ? p.value.indexOf(v.wahl) : p.value.length;
  p.setSelectionRange(anfang, v.wahl ? anfang + v.wahl.length : anfang);
}

// Vorschläge für die gewählte Art: wenige als Knöpfe, viele als Auswahlliste (nur neu zeichnen, wenn sich die Art ändert).
function vorschlaegeZeichnen(art) {
  const feld = $('#st-vorschlaege');
  const passende = Object.entries(VORSCHLAEGE).filter(([, v]) => v.art === art && (!v.tauschen || EIN()?.tauschen_verfuegbar));
  feld.hidden = !passende.length;
  if (feld.dataset.art === art) return;
  feld.dataset.art = art;
  if (passende.length <= 3) {
    feld.replaceChildren(h('span', { class: 'leise', text: 'Vorschlag:' }), ...passende.map(([name, v]) => h('button', {
      type: 'button', class: 'knopf knopf-klein', onclick: () => vorschlagEinsetzen(name),
    }, v.name)));
    return;
  }
  const wahl = h('select', { 'aria-label': 'Vorschlag einsetzen' }, option('', 'Vorschlag einsetzen …'),
    ...passende.map(([name, v]) => option(name, v.name)));
  wahl.addEventListener('change', () => {
    const name = wahl.value;
    wahl.value = '';
    if (name) vorschlagEinsetzen(name);
  });
  feld.replaceChildren(wahl);
}

// Vorschaubild mit Markierung; wird nur neu gezeichnet, wenn sich Bild oder Markierung ändern.
function maskeFeld(o) {
  const m = aktuelleMaske();
  const url = bildUrl(o, ST.extra?.quelle);
  const schluessel = `${url}|${m ? `${m.rle.length}:${m.anteil}` : '-'}`;
  if (ST.vorschau?.schluessel !== schluessel) {
    const leinwand = h('canvas', { 'aria-hidden': 'true' });
    const knopfEl = h('button', { type: 'button', class: 'st-maske-vorschau', title: 'Stelle markieren', onclick: markieren }, leinwand);
    ST.vorschau = { schluessel, el: knopfEl };
    requestAnimationFrame(() => maskeVorschau(leinwand, url, m).catch(() => {
      knopfEl.replaceChildren(h('span', { class: 'leise', text: 'Das Bild lässt sich nicht anzeigen.' }));
    }));
  }
  return h('div', { class: 'st-vorlagen-bereich' },
    h('p', { class: 'st-label' }, 'Bild ', h('span', { class: 'leise', text: 'das Original bleibt unverändert' })),
    h('ul', { class: 'st-vorlagen-liste' }, vorlageChip(o)),
    ST.vorschau.el,
    h('p', { class: 'st-zeile' },
      h('button', { type: 'button', class: `knopf knopf-klein${m ? '' : ' knopf-haupt'}`, onclick: markieren },
        m ? 'Markierung ändern …' : 'Stelle markieren …'),
      h('span', { class: 'leise', text: m ? `${prozentText(m.anteil)} des Bildes markiert` : 'Noch nichts markiert.' })));
}

function zuschnittHinweis(v, e) {
  if (!['start', 'ende'].includes(v.rolle) || !e?.info?.breite || !e.info.hoehe) return null;
  const [b, hh] = groesse();
  return Math.abs((e.info.breite / e.info.hoehe) / (b / hh) - 1) > 0.03 ? 'wird mittig auf das Videoformat zugeschnitten' : null;
}

function vorlageChip(v) {
  const e = v.art === 'bibliothek' ? ST.bib?.eintraege.find((x) => x.pfad === v.pfad) : null;
  let vorschau;
  if (e?.medium === 'video') {
    vorschau = h('video', { src: `${dateiUrl(e)}#t=0.5`, preload: 'metadata', 'aria-hidden': 'true' });
    vorschau.muted = true;
  } else if (e) {
    vorschau = h('img', { src: dateiUrl(e), alt: '', class: durchsichtig(e.info) });
  } else {
    vorschau = h('span', { class: 'st-vorlage-datei', text: istClip(v.pfad) ? 'Clip' : 'Datei' });
  }
  const hinweis = zuschnittHinweis(v, e);
  // Beim Bearbeiten bestimmt die erste Vorlage Größe und Ausschnitt; jede andere lässt sich nach vorn holen.
  const gleiche = ST.vorlagen.filter((x) => x.rolle === v.rolle);
  const nachVorn = v.rolle === 'vorlage' && gleiche.indexOf(v) > 0 ? h('button', {
    type: 'button', class: 'knopf knopf-klein knopf-symbol', title: 'Nach vorn: bestimmt Größe und Ausschnitt',
    'aria-label': 'Als erste Vorlage verwenden',
    onclick: () => { ST.vorlagen = [v, ...ST.vorlagen.filter((x) => x !== v)]; formAnpassen(); },
  }, '↑') : null;
  const nummer = v.rolle === 'vorbild' ? 'Bild 2: ' : v.rolle === 'vorlage' && gleiche.length > 1 ? `Bild ${gleiche.indexOf(v) + 1}: ` : '';
  return h('li', { class: 'st-vorlage', title: v.pfad }, vorschau,
    h('span', { class: 'st-vorlage-name' }, h('span', { text: nummer + v.pfad.split(/[\\/]/).pop() }), hinweis ? h('small', { text: hinweis }) : null),
    h('span', { class: 'st-zeile' }, nachVorn, h('button', {
      type: 'button', class: 'knopf knopf-klein knopf-symbol', title: 'Entfernen', 'aria-label': `${ROLLENNAME[v.rolle]} entfernen`,
      onclick: () => { ST.vorlagen = ST.vorlagen.filter((x) => x !== v); formAnpassen(); },
    }, '×')));
}

function vorlagenBereich(rolle, titel, info, max, knopfText, tipp, clips = false) {
  const eintraege = ST.vorlagen.filter((v) => v.rolle === rolle);
  return h('div', { class: 'st-vorlagen-bereich' },
    h('p', { class: 'st-label' }, titel, ' ', h('span', { class: 'leise', text: info })),
    h('ul', { class: 'st-vorlagen-liste' },
      ...(eintraege.length ? eintraege.map(vorlageChip) : [h('li', { class: 'leise', text: 'Noch nichts gewählt.' })])),
    h('p', { class: 'st-zeile' },
      eintraege.length < max && knopfText
        ? h('button', { type: 'button', class: 'knopf knopf-klein', onclick: () => dateiWaehlen(rolle, clips) }, knopfText) : null,
      h('span', { class: 'leise', text: tipp })));
}

function referenzAuswahl(name, wert, optionen, setzen) {
  const sel = h('select', {}, ...optionen.map(([v, t]) => option(v, t)));
  sel.value = wert;
  sel.addEventListener('change', () => { setzen(sel.value); formAnpassen(); });
  return h('label', { class: 'st-feld' }, name, sel);
}

function vorlagenZeichnen() {
  const art = stArt();
  const feld = $('#st-vorlagen-feld');
  if (!ROLLEN[art]) { feld.replaceChildren(); return; }
  const e = EIN();
  const v = e.video;
  const teile = [];
  if (art === 'modell3d') {
    teile.push(vorlagenBereich('vorlage', 'Vorlage', 'ein Drehblatt (vier Ansichten nebeneinander) oder ein Bild des Gegenstands', 1,
      'Aus Datei …', 'oder in der Bibliothek „3D-Modell“'));
  } else if (art === 'bearbeiten') {
    teile.push(vorlagenBereich('vorlage', 'Vorlagen', `bis zu ${e.max_vorlagen}, die erste bestimmt die Größe`, e.max_vorlagen,
      'Aus Datei …', 'oder in der Bibliothek „Als Vorlage“'));
    if (ST.vorlagen.filter((v) => v.rolle === 'vorlage').length > 1) {
      const poseTipp = e.pose_verfuegbar
        ? 'Eine fremde Haltung übernimmt Qwen verlässlich über ein Pose-Skelett (Art „Pose“, dann Vorschlag „Pose übernehmen“); direkt aus einem Foto nur manchmal.'
        : 'Eine fremde Pose übernimmt Qwen nur manchmal: dann Anzahl 4 wählen und die beste Variation behalten.';
      teile.push(h('p', { class: 'leise', text: 'Im Text als „Bild 1“, „Bild 2“ … ansprechen. Eine Person in eine Szene setzen gelingt verlässlich, etwa „Ersetze die Frau in Bild 1 durch den Mann aus Bild 2; Gesicht und Kleidung wie in Bild 2“. ' + poseTipp }));
    }
  } else if (art === 'verbessern') {
    const o = original();
    teile.push(o ? maskeFeld(o) : vorlagenBereich('original', 'Bild', 'das Original bleibt unverändert', 1, 'Aus Datei …',
      'oder in der Bibliothek „Stelle verbessern …“'));
    // Stufe 3n: freiwillig ein Vorbild, das an die Stelle soll (Person, Logo, Gegenstand); im Text „Bild 2“.
    if (maxVorbilder()) {
      teile.push(vorlagenBereich('vorbild', 'Vorbild für die Stelle', 'freiwillig: Person, Logo oder Gegenstand, der dorthin soll; im Text „Bild 2“',
        maxVorbilder(), 'Aus Datei …', 'oder in der Bibliothek „Für die Stelle“'));
    }
  } else if (art === 'freistellen') {
    teile.push(vorlagenBereich('original', 'Bild', 'das Original bleibt unverändert', 1, 'Aus Datei …',
      'oder in der Bibliothek „Freistellen“'));
  } else if (art === 'pose') {
    teile.push(vorlagenBereich('original', 'Bild', 'die Person, deren Haltung übernommen werden soll', 1, 'Aus Datei …',
      'oder in der Bibliothek „Pose-Skelett“'));
  } else if (art === 'video_bild') {
    teile.push(vorlagenBereich('start', 'Startbild', 'das Video beginnt genau mit diesem Bild', 1, 'Aus Datei …', 'oder in der Bibliothek „Zu Video“'),
      vorlagenBereich('ende', 'Endbild', 'freiwillig: das Video endet auf diesem Bild', 1, 'Aus Datei …', 'oder in der Bibliothek „Als Endbild“'),
      h('p', { class: 'leise', text: 'Nur das Startbild ist fest. Wer nicht darauf zu sehen ist, kann sich im Lauf des Videos verändern.' }));
  } else if (art === 'video_szenen') {
    teile.push(vorlagenBereich('start', 'Startbild', 'freiwillig: Szene 1 beginnt genau mit diesem Bild', 1, 'Aus Datei …', 'oder in der Bibliothek „Zu Video“'),
      vorlagenBereich('bild', 'Referenzbilder', `freiwillig, bis zu ${v.max_referenzbilder}: Figuren für Szene 1, im gemeinsamen Teil „Bild 1“ …`,
        v.max_referenzbilder, 'Bilder aus Datei …', 'oder in der Bibliothek „Als Referenz“'),
      h('p', { class: 'leise', text: 'Entweder ein Startbild oder Referenzbilder. Jede weitere Szene setzt die letzten 1,6 s der Szene davor fort; das Studio hängt „eine durchgehende Einstellung ohne Schnitt“ an, damit das Bild nicht springt.' }));
  } else if (art === 'video_weiter') {
    // Nur Clips aus der Bibliothek (kein „Aus Datei“): Der Dienst prüft Größe, Bildrate und Ton der Studio-Videos.
    const modus = weiterModus();
    const rollen = WEITER[modus].rollen;
    const zwei = rollen.length > 1;
    if (rollen.includes('ausgang')) {
      teile.push(vorlagenBereich('ausgang', zwei ? 'Clip davor' : 'Clip',
        modus === 'schleife' ? 'das neue Stück führt von seinem Ende zurück zu seinem Anfang' : 'das neue Stück setzt an sein Ende an',
        1, null, `in der Bibliothek „${{ verlaengern: 'Verlängern …', schleife: 'Schleife schließen …', verbinden: 'Verbinden …' }[modus]}“`));
    }
    if (rollen.includes('ziel')) {
      teile.push(vorlagenBereich('ziel', zwei ? 'Clip danach' : 'Clip', 'das neue Stück führt genau in sein erstes Bild', 1, null,
        `in der Bibliothek „${zwei ? 'Als Clip danach' : 'Davor setzen …'}“`));
    }
    const clips = ST.vorlagen.filter((x) => rollen.includes(x.rolle));
    if (zwei && clips.length === 2) {
      teile.push(h('p', { class: 'st-zeile' }, h('button', {
        type: 'button', class: 'knopf knopf-klein',
        onclick: () => { for (const x of clips) x.rolle = x.rolle === 'ausgang' ? 'ziel' : 'ausgang'; formAnpassen(); },
      }, 'Reihenfolge tauschen')));
    }
    teile.push(h('p', { class: 'leise', text: WEITER[modus].grenze }));
  } else {
    teile.push(vorlagenBereich('bild', 'Referenzbilder', `bis zu ${v.max_referenzbilder}; im Text als „Bild 1“, „Bild 2“ … ansprechen`,
      v.max_referenzbilder, 'Bilder aus Datei …', 'oder in der Bibliothek „Als Referenz“'),
    vorlagenBereich('clip', 'Clips', `bis zu ${v.max_clips}, je 2–15 s; Bewegung und Timing werden übernommen („Video 1“ …)`,
      v.max_clips, 'Clips aus Datei …', 'oder in der Bibliothek „Als Referenz-Clip“', true),
    h('div', { class: 'st-zwei' },
      referenzAuswahl('Wie genau kopieren', ST.referenz.genau, [['match', 'Normal'], ['max', 'So genau wie möglich (viel langsamer)']],
        (w) => { ST.referenz.genau = w; }),
      referenzAuswahl('Ton des ersten Clips', ST.referenz.ton ? 'ja' : 'nein', [['ja', 'Behalten'], ['nein', 'Weglassen']],
        (w) => { ST.referenz.ton = w === 'ja'; })),
    h('p', { class: 'leise', text: 'Damit ein Gesicht bleibt: die Person im Text benennen und sagen, dass ihr Aussehen vollständig erhalten bleibt. Ein Clip ist der verlässliche Fall.' }));
  }
  feld.replaceChildren(...teile);
}

function vorlageDazu(v, zielArt) {
  if (zielArt) {
    document.querySelector(`input[name="st-art"][value="${zielArt}"]`).checked = true;
    modusSetzen();
  }
  const max = { vorlage: EIN().max_vorlagen, vorbild: maxVorbilder(), start: 1, ende: 1, bild: VID().max_referenzbilder,
    clip: VID().max_clips }[v.rolle];
  if (['start', 'ende', 'original', 'ausgang', 'ziel'].includes(v.rolle) || (v.rolle === 'vorbild' && max === 1)) {
    ST.vorlagen = ST.vorlagen.filter((x) => x.rolle !== v.rolle);
  } else if (ST.vorlagen.some((x) => x.rolle === v.rolle && x.pfad === v.pfad)) {
    formAnpassen();
    return;
  } else if (ST.vorlagen.filter((x) => x.rolle === v.rolle).length >= max) {
    stMelden(`Höchstens ${max} (${ROLLENNAME[v.rolle]}).`);
    formAnpassen();
    return;
  }
  ST.vorlagen.push(v);
  formAnpassen();
}

async function dateiWaehlen(rolle, clips) {
  try {
    const r = await studio({ aktion: 'vorlagen_waehlen', clips });
    for (const p of r.pfade) vorlageDazu({ art: 'datei', pfad: p, rolle });
  } catch (err) { stMelden(err.message); }
}

async function erstellen() {
  if ($('#st-erstellen').disabled) return;
  const art = stArt();
  if (art === 'video_szenen') {
    await szenenStarten();
    return;
  }
  const video = istVideo(art);
  if (art === 'verbessern' && !aktuelleMaske() && !stelleWort()) {
    if (original()) markieren(); else stMelden('Bitte zuerst das Bild wählen, in dem eine Stelle verbessert werden soll.');
    return;
  }
  if (['freistellen', 'pose'].includes(art) && !original()) {
    stMelden(art === 'pose' ? 'Bitte zuerst das Bild wählen, aus dem die Pose kommen soll.' : 'Bitte zuerst das Bild wählen, das freigestellt werden soll.');
    return;
  }
  if (art === 'modell3d' && !ST.vorlagen.some((v) => v.rolle === 'vorlage')) {
    stMelden('Bitte zuerst ein Drehblatt (vier Ansichten nebeneinander) oder ein Bild des Gegenstands wählen.');
    return;
  }
  const weiter = art === 'video_weiter';
  if (weiter && weiterFehlt()) {
    stMelden('Bitte zuerst den Clip in der Bibliothek wählen: in der Großansicht eines Videos unter „Weiterführen“.');
    return;
  }
  const w = weiter ? weiterWerte() : null;
  // Beim Weiterführen bestimmen die Clips die Größe (der Dienst misst sie selbst).
  const [breite, hoehe] = weiter ? [(w.a || w.z)?.breite, (w.a || w.z)?.hoehe] : groesse();
  const ohne = ohneQwen(); // gleiche Eingabe = gleiches Ergebnis: keine Variationen
  const zufall = $('#st-zufall').checked || ohne;
  const rollen = weiter ? w.m.rollen : ROLLEN[art] || [];
  const freistellen = art === 'freistellen';
  const daten = {
    // Kein Negativ-Prompt: Das Studio rechnet mit CFG 1, dabei nutzt ComfyUI ihn nicht (Feld „Vermeiden“ entfernt).
    aktion: 'erzeugen', projekt: $('#st-projekt').value, art,
    prompt: freistellen ? $('#st-motiv').value : ['pose', 'modell3d'].includes(art) ? '' : $('#st-prompt').value,
    breite, hoehe, schritte: +$('#st-qualitaet').value,
    variation: zufall ? null : $('#st-variation').value, anzahl: zufall && !ohne ? +$('#st-anzahl').value : 1,
    vorlagen: ST.vorlagen.filter((v) => rollen.includes(v.rolle)).map(({ art: a, pfad, rolle }) => ({ art: a, pfad, rolle })),
    ...ST.extra,
  };
  if (video && !weiter) daten.bilder = +$('#st-laenge').value;
  if (weiter) {
    // Der Wunsch in Sekunden, auf ms abgerundet: Der Dienst rundet auf die nächste Clip-Länge auf und landet so genau
    // auf der gewählten. Schnitte in ganzen Bildern, nur für die Clips, die der Modus braucht.
    Object.assign(daten, { modus: w.modus, neu_sekunden: Math.floor((w.neu / w.fps) * 1000) / 1000,
      schnitt_ende: w.e, schnitt_anfang: w.b });
  }
  if (art === 'video_referenz') Object.assign(daten, { referenz_genau: ST.referenz.genau, ton_behalten: ST.referenz.ton });
  if (art === 'bearbeiten') {
    daten.groesse_von = wieVorlage() ? 'vorlage' : 'format';
    if (hochskaliertAuf()) daten.aufloesung = hochskaliertAuf();
    if (!$('#st-details-feld').hidden && $('#st-details').checked) daten.details = true;
  }
  if (art === 'bild' && !$('#st-durchsichtig-feld').hidden && $('#st-durchsichtig').checked) daten.durchsichtig = true;
  if (art === 'bild' && !$('#st-ausformulieren-feld').hidden && $('#st-ausformulieren').checked) daten.ausformulieren = true;
  if (video && realismusAn()) daten.realismus = true;
  if (art === 'video_referenz' && tauschenAn()) daten.tauschen = true;
  // 8-Schritt-LoRA statt Turbo für neue Referenz-Videos mit 8 Schritten (seit 09.10.2026; ältere bleiben bei „Nochmal“ gleich).
  if (art === 'video_referenz' && EIN().acc8_verfuegbar && daten.schritte === EIN().acc8_schritte && !daten.tauschen) daten.acc8 = true;
  // DMAD für neue Videos aus Text bzw. Bild mit 4 Schritten (seit 11.10.2026): natürlichere Haut, halbe Zeit.
  if (['video_text', 'video_bild'].includes(art) && EIN().dmad_verfuegbar && daten.schritte === EIN().dmad_schritte) daten.dmad = true;
  if (!video && !ohne && EIN().qualitaet.find((q) => q.schritte === daten.schritte)?.turbo) {
    daten.turbo = true;
    if (EIN().turbo_modell_verfuegbar) daten.turbo_modell = true; // offizielles Turbo-Modell, nur neue Aufträge
  }
  // Neue Bildaufträge rechnen mit der schnelleren Aufmerksamkeit (Stufe 3k) und den INT8-Fassungen (Stufe 3l), neue
  // MiniMax-Videos seit 17.10.2026 ebenfalls mit der schnelleren Aufmerksamkeit (Stufe 3u); „Nochmal“ übernimmt die
  // des Originals, ältere Aufträge bleiben so gleich.
  if (!video && !ohne && EIN().schnell_verfuegbar) daten.schnell = true;
  if (video && !VIDEO_HILFEN.includes(art) && EIN().video_schnell_verfuegbar) daten.schnell = true;
  if (!video && !ohne && EIN().int8_verfuegbar) daten.int8 = true;
  if (freistellen && schnellFreistellen()) daten.verfahren = 'schnell';
  // Pose-Skelett aller Personen: SAM3 sucht sie zuerst (sonst nur eine); ebenfalls nur für neue Aufträge.
  if (art === 'pose' && EIN().finden_verfuegbar) daten.personen = true;
  if (art === 'modell3d') daten.stufe = $('#st-modell-stufe').value; // Detailstufe; Drehblatt oder Bild erkennt der Dienst
  if (art === 'verbessern') {
    const m = aktuelleMaske();
    daten.staerke = +$('#st-staerke').value;
    if (m) daten.maske = { breite: m.breite, hoehe: m.hoehe, rle: m.rle };
    else daten.stelle = stelleWort();
  }
  ST.sendet = true;
  erstellenKnopf();
  try {
    const r = await studio(daten);
    stMelden(r.neu.length > 1 ? `${r.neu.length} Aufträge übergeben.` : 'Auftrag übergeben.', true);
    ST.extra = {};
  } catch (err) {
    stMelden(err.message);
  } finally {
    ST.sendet = false;
    erstellenKnopf();
  }
  stAktualisieren();
}

// ------------------------------------------------------------------ Szenenfolge (Stufe 3p)

// Längen je Szene: Szene 1 wie „Aus Text“ (Clip-Länge = neue Bilder), jede weitere wie „Verlängern“ (Clip L, davon L − 39 neu,
// gerechnet werden L + 39 Bilder). `sekunden` geht an den Dienst; bei weiteren Szenen auf ms abgerundet, so landet er genau
// auf derselben Clip-Länge.
function szenenLaengen(i) {
  const fps = VID()?.fps || 24;
  if (i === 0) return VID().laengen.map((l) => ({ sekunden: l.bilder / fps, bilder: l.bilder, neu: l.bilder, text: l.name }));
  const k = WEITER.verlaengern.kontext;
  return WEITER_LAENGEN.map((l) => ({ sekunden: Math.floor(((l - k) / fps) * 1000) / 1000, bilder: l + k, neu: l - k,
    text: `${sekundenVon(l - k)} s` }));
}

function szeneLaenge(s, i) {
  const liste = szenenLaengen(i);
  const standard = i === 0 ? liste.find((l) => l.bilder === (VID().laengen.find((x) => x.standard) || VID().laengen[0]).bilder)
    : liste.find((l) => l.neu === 136); // etwa 5,7 s, wie in den Versuchen
  return liste.find((l) => String(l.sekunden) === String(s.sekunden)) || standard || liste[0];
}

function szenenZeichnen() {
  const liste = $('#st-szenen-liste');
  const max = EIN()?.szenen?.max_szenen || 8;
  if (liste.dataset.anzahl !== String(ST.szenen.length) || !liste.children.length) {
    liste.dataset.anzahl = String(ST.szenen.length);
    liste.replaceChildren(...ST.szenen.map((s, i) => {
      const text = h('textarea', { rows: '3', 'aria-label': `Szene ${i + 1}`,
        placeholder: i === 0 ? 'Was geschieht, was macht die Kamera, was wird gesagt? Gesprochenes als <d>[Deutsch] …</d>'
          : 'Wie geht es weiter? Handlung, Kamera, Gesprochenes – aus der Lage am Ende der Szene davor' });
      text.value = s.text;
      text.addEventListener('input', () => { s.text = text.value; formMerken(); });
      const laenge = h('select', { 'aria-label': `Länge Szene ${i + 1}` },
        ...szenenLaengen(i).map((l) => option(l.sekunden, i === 0 ? l.text : `${l.text} neu`)));
      laenge.value = String(szeneLaenge(s, i).sekunden);
      laenge.addEventListener('change', () => { s.sekunden = +laenge.value; formAnpassen(); });
      const weg = ST.szenen.length > 1 ? h('button', {
        type: 'button', class: 'knopf knopf-klein knopf-symbol', title: 'Szene entfernen', 'aria-label': `Szene ${i + 1} entfernen`,
        onclick: () => { ST.szenen.splice(i, 1); liste.dataset.anzahl = ''; formAnpassen(); },
      }, '×') : null;
      // Realism-LoRA je Szene: Szenen mit Personen gewinnen, leere Räume werden mit ihr schlechter (Stufe 3o).
      let real = null;
      if (EIN()?.realismus_verfuegbar) {
        const kasten = h('input', { type: 'checkbox', 'aria-label': `Szene ${i + 1}: realistische Personen` });
        kasten.checked = s.realismus === true;
        kasten.addEventListener('change', () => { s.realismus = kasten.checked; formAnpassen(); });
        real = h('label', { class: 'st-check' }, kasten, ' Realistische Personen ', h('span', { class: 'leise', text: '(nur wenn Menschen zu sehen sind)' }));
      }
      return h('li', { class: 'st-szene' }, h('div', { class: 'st-zeile' }, h('b', { text: `Szene ${i + 1}` }), laenge, weg), text, real);
    }));
  }
  $('#st-szene-dazu').disabled = ST.szenen.length >= max;
}

async function szenenStarten() {
  const leer = ST.szenen.findIndex((s) => !s.text.trim());
  if (!$('#st-prompt').value.trim()) {
    stMelden('Bitte oben den gemeinsamen Teil beschreiben: wer zu sehen ist, Ort, Licht und Stil.');
    return;
  }
  if (leer >= 0) {
    stMelden(`Szene ${leer + 1} ist noch leer.`);
    return;
  }
  const [breite, hoehe] = groesse();
  const zufall = $('#st-zufall').checked;
  const daten = {
    aktion: 'folge_neu', projekt: $('#st-projekt').value, gemeinsam: $('#st-prompt').value,
    szenen: ST.szenen.map((s, i) => ({ text: s.text, sekunden: szeneLaenge(s, i).sekunden,
      realismus: !!EIN()?.realismus_verfuegbar && s.realismus === true })), breite, hoehe,
    schritte: +$('#st-qualitaet').value, pruefen: $('#st-pruefen').checked, variation: zufall ? null : $('#st-variation').value,
    vorlagen: ST.vorlagen.filter((v) => ['start', 'bild'].includes(v.rolle)).map(({ art: a, pfad, rolle }) => ({ art: a, pfad, rolle })),
  };
  if (realismusAn()) daten.realismus = true;
  if (EIN()?.video_schnell_verfuegbar) daten.schnell = true; // alle Szenen mit schnellerer Aufmerksamkeit (Stufe 3u)
  ST.sendet = true;
  erstellenKnopf();
  try {
    await studio(daten);
    const n = daten.szenen.length;
    stMelden(daten.pruefen ? `Szenenfolge angelegt: Szene 1 von ${n} rechnet. Danach oben in der Bibliothek „Passt“ oder „Nochmal“.`
      : `Szenenfolge angelegt: ${n} Szenen laufen nacheinander durch.`, true);
  } catch (err) {
    stMelden(err.message);
  } finally {
    ST.sendet = false;
    erstellenKnopf();
  }
  stAktualisieren();
}

const FOLGE_TEXT = {
  laeuft: (f) => `Szene ${f.szene + 1} von ${f.szenen.length} rechnet …`,
  pruefen: (f) => `Szene ${f.szene + 1} von ${f.szenen.length} ist fertig – ansehen, dann „Passt“ oder „Nochmal“.`,
  fehler: (f) => `Szene ${f.szene + 1}: ${f.meldung || 'nicht fertig geworden.'}`,
  fertig: (f) => `Fertig: ${f.szenen.length} ${f.szenen.length === 1 ? 'Szene' : 'Szenen'}, ${sekundenVon(f.gesamt_bilder)} s.`,
  abgebrochen: () => 'Beendet.',
};

// Szenenfolgen über der Bibliothek, aus dem Zustand des Dienstes; neu gezeichnet nur, wenn sich etwas ändert.
function folgenZeichnen() {
  const box = $('#st-folgen');
  const folgen = (ST.stand?.folgen || []).filter((f) => ST.filter.projekt === '*' || f.projekt === ST.filter.projekt);
  box.hidden = !folgen.length;
  const sig = JSON.stringify(folgen.map((f) => [f.id, f.zustand, f.szene, f.meldung, f.datei]));
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  box.replaceChildren(...folgen.slice().reverse().map((f) => {
    const was = (w) => () => studio({ aktion: 'folge', id: f.id, was: w });
    const ergebnis = f.freigegeben?.length ? f.freigegeben[f.freigegeben.length - 1] : f.datei;
    const letzte = f.szene + 1 >= f.szenen.length;
    let knoepfe;
    if (f.zustand === 'pruefen') {
      knoepfe = [stKnopf('Szene ansehen', async () => detailOeffnen(f.datei), { titel: 'Das Video bis zu dieser Szene ansehen' }),
        stKnopf(letzte ? 'Passt – fertig' : `Passt – weiter mit Szene ${f.szene + 2}`, was('passt'), { haupt: true }),
        stKnopf('Nochmal', was('nochmal'), { titel: 'Diese Szene mit einer neuen Variationsnummer neu rechnen' }),
        stKnopf('Beenden', was('beenden'))];
    } else if (f.zustand === 'laeuft') {
      knoepfe = [stKnopf('Beenden', was('beenden'), { titel: 'Bricht die laufende Szene ab und beendet die Folge' })];
    } else if (f.zustand === 'fehler') {
      knoepfe = [stKnopf('Nochmal', was('nochmal'), { haupt: true }), stKnopf('Beenden', was('beenden'))];
    } else {
      knoepfe = [...(ergebnis ? [stKnopf('Ansehen', async () => detailOeffnen(ergebnis), { haupt: f.zustand === 'fertig' })] : []),
        stKnopf('Ausblenden', was('entfernen'), { titel: 'Nur aus dieser Liste; die Videos bleiben in der Bibliothek' })];
    }
    return h('li', { class: 'st-folge', 'data-zustand': f.zustand },
      h('div', { class: 'st-folge-kopf' }, h('b', { text: 'Szenenfolge' }),
        h('span', { class: 'leise', text: `${projektName(f.projekt)} · ${f.szenen.length} ${f.szenen.length === 1 ? 'Szene' : 'Szenen'}${f.pruefen ? '' : ' · ohne Prüfen'}` })),
      h('p', { class: 'st-prompt', text: f.gemeinsam, title: f.gemeinsam }),
      h('p', { class: f.zustand === 'fehler' ? 'st-fehler' : '', text: (FOLGE_TEXT[f.zustand] || (() => f.zustand))(f) }),
      h('div', { class: 'st-knoepfe' }, ...knoepfe));
  }));
}

function projektNeu() {
  const d = $('#dialog');
  d.className = '';
  const eingabe = h('input', { type: 'text', maxlength: '60', placeholder: 'z. B. Praxis-Website', autocomplete: 'off' });
  const fehler = h('p', { class: 'st-fehler' });
  const anlegen = async () => {
    try {
      const r = await studio({ aktion: 'projekt_neu', name: eingabe.value });
      d.close();
      ST.projektGemerkt = r.name;
      ST.projekteSchluessel = '';
      await stAktualisieren();
      $('#st-projekt').value = r.name;
      formMerken();
    } catch (err) { fehler.textContent = err.message; }
  };
  eingabe.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); anlegen(); } });
  d.replaceChildren(
    h('h2', { id: 'dialog-titel', text: 'Neues Projekt' }),
    h('p', { class: 'leise', text: `Legt einen Ordner im Studio an (${EIN()?.ordner || ''}). Bilder und Videos landen dort direkt, ohne Kopie.` }),
    h('label', { class: 'dialog-feld' }, 'Name', eingabe), fehler,
    h('div', { class: 'dialog-knoepfe' },
      h('button', { class: 'knopf', type: 'button', onclick: () => d.close() }, 'Abbrechen'),
      h('button', { class: 'knopf knopf-haupt', type: 'button', onclick: anlegen }, 'Anlegen')));
  d.showModal();
  eingabe.focus();
}

// ------------------------------------------------------------------ Bibliothek

function gefiltert() {
  const f = ST.filter;
  const such = f.suche.trim().toLowerCase();
  return (ST.bib?.eintraege || []).filter((e) => (f.projekt === '*' || e.projekt === f.projekt)
    && (f.medium === 'alle' || e.medium === f.medium)
    && (!such || `${e.info?.prompt || ''} ${e.info?.negativ || ''} ${e.name}`.toLowerCase().includes(such)));
}

function auftragKachel(a) {
  const schluessel = `a:${a.id}`;
  let k = ST.kacheln.get(schluessel);
  if (!k) {
    k = { balken: h('div', { class: 'balken' }, h('i')), text: h('p', { class: 'st-auftrag-text' }), prompt: h('p', { class: 'st-prompt' }),
      meta: h('p', { class: 'st-meta' }), knoepfe: h('div', { class: 'st-knoepfe' }), sig: '' };
    k.el = h('li', { class: 'st-kachel st-auftrag' },
      h('div', { class: 'st-flaeche st-platzhalter' }, k.balken, k.text), h('div', { class: 'st-unter' }, k.prompt, k.meta, k.knoepfe));
    ST.kacheln.set(schluessel, k);
  }
  k.el.dataset.zustand = a.zustand;
  k.prompt.textContent = anzeigePrompt(a);
  k.prompt.title = anzeigePrompt(a);
  const hoch = a.aufloesung && a.aufloesung !== standardAufl() ? ` · ${etwaMP(a.aufloesung)}` : '';
  // Weitergeführt: Länge des fertigen Videos und des neuen Stücks (a.bilder ist dort die Länge des gerechneten Clips).
  const dauerText = a.art === 'video_weiter' && a.laenge_bilder
    ? ` · ${sekundenVon(a.laenge_bilder)} s, davon ${sekundenVon(a.neu_bilder)} s neu` : a.bilder ? ` · ${sekundenVon(a.bilder)} s` : '';
  const format = a.art === 'bearbeiten' ? `${a.vorlagen?.length || 0} Vorlagen${a.breite ? ` · ${a.breite} × ${a.hoehe}` : hoch}`
    : !a.breite ? 'Größe wie das Original'
      : `${a.breite} × ${a.hoehe}${dauerText}`;
  const artText = a.art === 'video_weiter' && WEITER[a.modus] ? `${ART[a.art]} (${WEITER[a.modus].erledigt})` : ART[a.art] || a.art;
  k.meta.textContent = `${artText} · ${projektName(a.projekt)} · ${format} · ${a.qualitaet || `${a.schritte} Schritte`}`
    + `${a.details ? ' · Details' : ''} · Nr. ${a.variation}`;
  let text = a.meldung || '';
  let anteil = null;
  if (a.zustand === 'wartet') text = 'Wartet auf den vorherigen Auftrag.';
  if (a.zustand === 'fertig') text = a.hinweis || '';
  if (a.zustand === 'laeuft' && a.schritt === 'rechnet' && a.sekunden != null) {
    text = a.erwartet_s ? `Rechnet · ${dauer(a.sekunden)} von ${etwaDauer(a.erwartet_s)}` : `Rechnet · ${dauer(a.sekunden)}`;
    if (a.erwartet_s) anteil = Math.min(0.97, a.sekunden / a.erwartet_s);
  }
  k.text.textContent = text || (a.zustand === 'laeuft' ? 'Beginnt …' : '');
  const offen = a.zustand === 'laeuft' || a.zustand === 'wartet';
  k.balken.hidden = !offen;
  k.balken.classList.toggle('offen', anteil == null);
  k.balken.firstChild.style.width = `${Math.round((anteil ?? 0) * 100)}%`;
  if (a.zustand !== k.sig) {
    k.sig = a.zustand;
    let knoepfe;
    if (offen) knoepfe = [stKnopf('Abbrechen', () => studio({ aktion: 'abbrechen', id: a.id }))];
    else if (a.zustand === 'fertig') {
      knoepfe = [stKnopf('Zeigen', async () => detailOeffnen(a.dateien[0]), { haupt: true, aus: !a.dateien?.length }),
        stKnopf('Ausblenden', () => studio({ aktion: 'entfernen', id: a.id }))];
    } else {
      knoepfe = [stKnopf('Wiederholen', () => studio({ aktion: 'wiederholen', id: a.id }), { haupt: true }),
        stKnopf('Entfernen', () => studio({ aktion: 'entfernen', id: a.id }))];
    }
    k.knoepfe.replaceChildren(...knoepfe);
  }
  return k.el;
}

function eintragKachel(e) {
  const schluessel = `e:${e.pfad}`;
  let k = ST.kacheln.get(schluessel);
  if (!k || k.zeit !== e.zeit) {
    const medium = e.medium === 'video'
      ? h('video', { src: `${dateiUrl(e)}#t=0.5`, preload: 'metadata', playsinline: '', 'aria-hidden': 'true' })
      : h('img', { src: dateiUrl(e), alt: '', loading: 'lazy', decoding: 'async', class: durchsichtig(e.info) });
    if (e.medium === 'video') {
      medium.muted = true;
      medium.loop = true;
    }
    k = { zeit: e.zeit, medium, prompt: h('p', { class: 'st-prompt' }), meta: h('p', { class: 'st-meta' }),
      marke: e.medium === 'video' ? h('span', { class: 'st-video-marke' }) : null,
      wahl: h('input', { type: 'checkbox', class: 'st-wahl', tabindex: '-1', 'aria-hidden': 'true' }) };
    const flaeche = h('button', {
      type: 'button', class: 'st-flaeche',
      onclick: () => (ST.auswaehlen ? auswahlUmschalten(e.pfad) : detailOeffnen(e.pfad)),
    }, medium, k.marke, k.wahl);
    if (e.medium === 'video') {
      flaeche.addEventListener('mouseenter', () => medium.play().catch(() => {}));
      flaeche.addEventListener('mouseleave', () => medium.pause());
    }
    k.flaeche = flaeche;
    k.el = h('li', { class: 'st-kachel' }, flaeche, h('div', { class: 'st-unter' }, k.prompt, k.meta));
    ST.kacheln.set(schluessel, k);
  }
  const i = e.info || {};
  const text = anzeigePrompt(i);
  k.medium.classList.toggle('durchsichtig', !!durchsichtig(i)); // die Angaben können nach dem Bild kommen
  k.prompt.textContent = text || (e.info ? 'ohne Prompt' : 'Wird gerade gespeichert …');
  k.prompt.classList.toggle('leise', !text);
  k.prompt.title = text || '';
  k.meta.textContent = `${projektName(e.projekt)} · ${stDatum(e.zeit)}`;
  if (k.marke) k.marke.textContent = i.art === 'modell3d' ? '3D-Modell · Vorschau' : i.laenge_bilder ? `Video · ${sekundenVon(i.laenge_bilder)} s` : 'Video';
  k.flaeche.setAttribute('aria-label', i.art === 'freistellen' ? text
    : `${ART[i.art] || (e.medium === 'video' ? 'Video' : 'Bild')}: ${text || e.name}`);
  const gewaehlt = ST.auswahl.has(e.pfad);
  k.el.classList.toggle('gewaehlt', gewaehlt);
  k.el.classList.toggle('waehlbar', ST.auswaehlen);
  k.wahl.checked = gewaehlt;
  return k.el;
}

function rasterZeichnen() {
  folgenZeichnen();
  const raster = $('#st-raster');
  const f = ST.filter;
  const rang = { laeuft: 0, wartet: 1, fehler: 2, abgebrochen: 2, fertig: 2 };
  const auftraege = (ST.stand?.auftraege || [])
    .filter((a) => a.zustand in rang && (a.zustand !== 'fertig' || a.hinweis)
      && (f.medium === 'alle' || f.medium === (istVideo(a.art) ? 'video' : 'bild'))
      && (f.projekt === '*' || a.projekt === f.projekt))
    .sort((x, y) => rang[x.zustand] - rang[y.zustand] || (rang[x.zustand] < 2 ? x.erstellt - y.erstellt : y.erstellt - x.erstellt));
  const eintraege = gefiltert();
  ST.liste = eintraege;
  const kinder = [...auftraege.map(auftragKachel), ...eintraege.map(eintragKachel)];
  const behalten = new Set(kinder);
  for (const [schluessel, k] of ST.kacheln) if (!behalten.has(k.el)) { k.el.remove(); ST.kacheln.delete(schluessel); }
  raster.querySelector('.st-leer')?.remove();
  kinder.forEach((el, i) => { if (raster.children[i] !== el) raster.insertBefore(el, raster.children[i] || null); });
  if (!kinder.length) {
    raster.append(h('li', {
      class: 'st-leer',
      text: !ST.bib ? 'Die Bibliothek wird geladen …' : ST.bib.eintraege.length ? 'Nichts gefunden. Suche oder Filter ändern.'
        : 'Hier ist noch nichts. Links beschreiben, was entstehen soll.',
    }));
  }
  const gesamt = ST.bib?.eintraege.length || 0;
  const teile = [eintraege.length === gesamt ? `${gesamt} Dateien` : `${eintraege.length} von ${gesamt} Dateien`];
  const offen = auftraege.filter((a) => rang[a.zustand] < 2).length;
  if (offen) teile.push(`${offen} ${offen === 1 ? 'Auftrag' : 'Aufträge'} in Arbeit`);
  $('#st-zaehler').textContent = teile.join(' · ');
  auswahlLeiste();
}

// ------------------------------------------------------------------ Auswahl

function auswahlUmschalten(pfad) {
  if (ST.auswahl.has(pfad)) ST.auswahl.delete(pfad); else ST.auswahl.add(pfad);
  rasterZeichnen();
}

function auswahlLeiste() {
  $('#st-auswahl-leiste').hidden = !ST.auswaehlen;
  $('#st-auswaehlen').hidden = ST.auswaehlen;
  const n = ST.auswahl.size;
  $('#st-auswahl-zahl').textContent = n ? `${n} gewählt` : 'Kacheln anklicken, um sie zu wählen';
  $('#st-verschieben').disabled = !n;
  $('#st-papierkorb').disabled = !n;
}

function auswahlBeenden() {
  ST.auswaehlen = false;
  ST.auswahl.clear();
  rasterZeichnen();
}

async function verschieben(pfade, projekt) {
  const r = await studio({ aktion: 'verschieben', pfade, projekt });
  const n = r.verschoben.length;
  stMelden([n ? `${n} ${n === 1 ? 'Datei' : 'Dateien'} nach „${projektName(projekt)}“ verschoben.` : '', ...r.fehler].filter(Boolean).join(' '), !r.fehler.length);
  await stBibLaden(true);
  return r;
}

function papierkorbFragen(pfade, danach) {
  const d = $('#dialog');
  d.className = '';
  const n = pfade.length;
  d.replaceChildren(
    h('h2', { id: 'dialog-titel', text: n === 1 ? 'In den Papierkorb legen?' : `${n} Dateien in den Papierkorb legen?` }),
    h('p', { text: 'Die Dateien und ihre Einstellungen (.json) kommen in den Windows-Papierkorb. Von dort lassen sie sich zurückholen.' }),
    h('div', { class: 'dialog-knoepfe' },
      h('button', { class: 'knopf', type: 'button', onclick: () => d.close() }, 'Behalten'),
      h('button', {
        class: 'knopf knopf-haupt', type: 'button',
        onclick: async () => {
          d.close();
          try {
            const r = await studio({ aktion: 'papierkorb', pfade });
            stMelden([`${r.anzahl} in den Papierkorb gelegt.`, ...r.fehler].join(' '), !r.fehler.length);
            danach?.();
          } catch (err) { stMelden(err.message); }
          await stBibLaden(true);
          rasterZeichnen();
        },
      }, 'In den Papierkorb')));
  if (!d.open) d.showModal();
}

// ------------------------------------------------------------------ Großansicht

function vorlagenAus(i) {
  return (i.vorlagen || []).map((v, n) => {
    const pfad = typeof v === 'string' ? v : v.pfad;
    let rolle = typeof v === 'string' ? null : v.rolle;
    if (!rolle) {
      if (i.art === 'video_bild') rolle = n === 0 ? 'start' : 'ende';
      else if (i.art === 'video_referenz') rolle = istClip(pfad) ? 'clip' : 'bild';
      else if (['verbessern', 'freistellen', 'pose'].includes(i.art)) rolle = 'original';
      else rolle = 'vorlage';
    }
    return { art: istDateiPfad(pfad) ? 'datei' : 'bibliothek', pfad, rolle };
  });
}

function wiederholbar(e) {
  const i = e.info || {};
  if (VIDEO_HILFEN.includes(i.art)) return 'Rechnet aus demselben Video immer gleich; aus dem Original neu starten.';
  if (i.art === 'modell3d' && !i.stufe) return 'Zu diesem Modell ist die Detailstufe nicht bekannt; „Mit Änderungen“ geht.';
  if (!i.prompt && i.art !== 'modell3d') return 'Zu dieser Datei ist kein Prompt bekannt.';
  if (!ART[i.art] || i.art === 'video') return 'Die Art dieser Datei ist nicht bekannt; „Mit Änderungen“ geht.';
  if (istVideo(i.art) && !i.laenge_bilder) return 'Die Länge dieses Videos ist nicht bekannt; „Mit Änderungen“ geht.';
  if (!['bearbeiten', 'freistellen'].includes(i.art) && !(i.breite && i.hoehe)) return 'Die Größe ist nicht bekannt; „Mit Änderungen“ geht.';
  if (i.art === 'verbessern' && !i.hat_maske) return 'Die Markierung dieser Datei ist nicht bekannt; „Mit Änderungen“ geht.';
  if (i.art === 'video_weiter' && (!WEITER[i.modus] || !i.clip_bilder)) return 'Wie dieses Video weitergeführt wurde, ist nicht bekannt; „Mit Änderungen“ geht.';
  if (ROLLEN[i.art]) {
    const v = vorlagenAus(i);
    if (i.herkunft !== 'studio' || !v.length) return 'Die Vorlagen dieser Datei sind nicht bekannt; „Mit Änderungen“ geht.';
    if (v.some((x) => x.art === 'bibliothek' && !ST.bib?.eintraege.some((y) => y.pfad === x.pfad))) {
      return 'Eine Vorlage liegt nicht mehr in der Bibliothek; „Mit Änderungen“ geht.';
    }
  }
  return null;
}

function zielProjekt(e) {
  return e.projekt === EIN()?.ordner_2wild ? $('#st-projekt').value : e.projekt;
}

async function wiederAnfrage(e, neueVariation) {
  const i = e.info;
  const video = istVideo(i.art);
  const daten = {
    // Freistellen: Der Dienst baut die Anweisung aus dem, was bleiben soll (leer: das Hauptmotiv).
    aktion: 'erzeugen', projekt: zielProjekt(e), art: i.art, prompt: i.art === 'freistellen' ? i.motiv || '' : i.prompt,
    negativ: video ? '' : i.negativ || '',
    // Weitergeführt: laenge_bilder ist das fertige Video; der Dienst nimmt clip_bilder (unten).
    breite: i.breite, hoehe: i.hoehe, bilder: i.art === 'video_weiter' ? undefined : i.laenge_bilder, schritte: i.schritte || undefined,
    cfg: video ? undefined : i.cfg || undefined, variation: neueVariation ? null : i.variation, anzahl: 1,
    vorlagen: ROLLEN[i.art] ? vorlagenAus(i) : [], referenz_genau: i.referenz_genau || undefined,
    ton_behalten: i.ton_behalten !== false, quelle: e.pfad,
    groesse_von: i.art === 'bearbeiten' ? i.groesse_von || 'vorlage' : undefined, // ältere Dateien: wie Vorlage 1
    aufloesung: i.art === 'bearbeiten' && i.aufloesung ? i.aufloesung : undefined, // hochskaliert (ältere: Standard)
    details: i.art === 'bearbeiten' && i.details === true ? true : undefined, // nur mit Detail-LoRA entstandene
    turbo: !video && i.turbo === true ? true : undefined, // nur, wenn das Original mit Turbo entstand
    turbo_modell: !video && i.turbo_modell === true ? true : undefined, // offizielles Turbo-Modell (seit 11.10.2026)
    durchsichtig: i.art === 'bild' && i.durchsichtig === true ? true : undefined,
    schnell: i.schnell === true ? true : undefined, // ältere Bilder und Videos ohne sie bleiben bei „Nochmal“ gleich
    int8: !video && i.int8 === true ? true : undefined, // ebenso: nur, wenn das Original mit INT8 entstand
    verfahren: i.art === 'freistellen' && i.verfahren === 'schnell' ? 'schnell' : undefined,
    ausformulieren: i.art === 'bild' && i.ausformulieren === true ? true : undefined, // gleiche Nummer = gleicher Text
    personen: i.art === 'pose' && i.personen === true ? true : undefined, // ältere Skelette: nur eine Person
    realismus: video && i.realismus === true ? true : undefined, // nur mit Realism-LoRA entstandene Videos (Stufe 3o)
    tauschen: i.art === 'video_referenz' && i.tauschen === true ? true : undefined, // Person tauschen (Stufe 3q)
    acc8: i.art === 'video_referenz' && i.acc8 === true ? true : undefined, // nur, wenn das Original mit ihr entstand
    dmad: ['video_text', 'video_bild'].includes(i.art) && i.dmad === true ? true : undefined, // ebenso (seit 11.10.2026)
    stufe: i.art === 'modell3d' ? i.stufe : undefined, modus: i.art === 'modell3d' ? i.modus : undefined, // 3D-Modell
  };
  if (i.art === 'verbessern') {
    // Die Markierung steht in der Begleitdatei; die Bibliothek liefert sie nur auf Nachfrage.
    daten.maske = (await studio({ aktion: 'maske', pfad: e.pfad })).maske;
    daten.staerke = i.staerke;
  }
  if (i.art === 'video_weiter') {
    // Dieselbe Clip-Länge ohne neue Rundung; die Prüfsummen fangen einen inzwischen ersetzten Clip ab.
    Object.assign(daten, { modus: i.modus, clip_bilder: i.clip_bilder, schnitt_ende: i.schnitt_ende || 0,
      schnitt_anfang: i.schnitt_anfang || 0,
      pruefsummen: Object.fromEntries((i.quellen || []).filter((q) => q.pfad && q.sha256).map((q) => [q.pfad, q.sha256])) });
  }
  return daten;
}

// Aus der Bibliothek: dieses Video weiterführen (Stufe 3m). Beim Verbinden bleibt der andere schon gewählte Clip stehen,
// sonst zählt nur dieser; der Prompt des Clips wird vorgeschlagen.
function weiterAus(e, modus, rolle) {
  const i = e.info || {};
  const clips = stArt() === 'video_weiter' ? ST.vorlagen.filter((v) => ['ausgang', 'ziel'].includes(v.rolle)) : [];
  const andere = modus === 'verbinden' ? clips.filter((v) => v.rolle !== rolle && v.pfad !== e.pfad) : [];
  document.querySelector('input[name="st-art"][value="video_weiter"]').checked = true;
  modusSetzen();
  $('#st-modus').value = modus;
  ST.vorlagen = ST.vorlagen.filter((v) => !['ausgang', 'ziel'].includes(v.rolle))
    .concat(andere, [{ art: 'bibliothek', pfad: e.pfad, rolle }]);
  // Ein Schnitt gehört zu seinem Clip: bei neuer Wahl zurücksetzen.
  $(rolle === 'ausgang' ? '#st-schnitt-ende' : '#st-schnitt-anfang').value = 0;
  // Beim zweiten Clip den schon geschriebenen Text behalten.
  if (!andere.length || !$('#st-prompt').value.trim()) $('#st-prompt').value = i.prompt ? `${i.prompt}\n\n` : '';
  ST.extra = { quelle: e.pfad };
  const ziel = zielProjekt(e);
  if ([...$('#st-projekt').options].some((o) => o.value === ziel)) $('#st-projekt').value = ziel;
  const beide = modus === 'verbinden' && andere.length;
  formZeigen({
    verlaengern: 'Clip übernommen. Beschreibe, wie es weitergeht (der Prompt des Clips steht schon da), dann „Erstellen“.',
    davor: 'Clip übernommen. Beschreibe, was davor geschieht; das neue Stück endet genau auf dem ersten Bild des Clips. Dann „Erstellen“.',
    schleife: 'Clip übernommen. Beschreibe die Bewegung zurück zum Anfang, dann „Erstellen“.',
    verbinden: beide ? 'Beide Clips gewählt. Beschreibe den Übergang, dann „Erstellen“.'
      : rolle === 'ausgang' ? 'Erster Clip übernommen. Wähle den zweiten in seiner Großansicht mit „Als Clip danach“.'
        : 'Zweiter Clip übernommen. Fehlt noch der erste: in seiner Großansicht „Verbinden …“.',
  }[modus]);
}

// Aus der Bibliothek: dieses Bild verbessern (auch ein schon verbessertes). Öffnet gleich das Markieren.
async function stelleVerbessern(e) {
  alsEinzige(e, 'verbessern', 'original');
  ST.vorlagen = ST.vorlagen.filter((v) => v.rolle !== 'vorbild'); // neues Bild, neue Stelle: kein altes Vorbild
  ST.maske = null;
  $('#st-prompt').value = '';
  formAnpassen();
  await markieren();
  if (!aktuelleMaske()) formZeigen('Bild übernommen. Markiere die Stelle, die neu entstehen soll.');
  else $('.st-form').scrollIntoView({ block: 'start', behavior: 'smooth' });
}

// Aus der Bibliothek: Art wählen und dieses Bild als einzige Vorlage der Rolle übernehmen.
function alsEinzige(e, art, rolle) {
  document.querySelector(`input[name="st-art"][value="${art}"]`).checked = true;
  modusSetzen();
  ST.vorlagen = ST.vorlagen.filter((v) => v.rolle !== rolle);
  ST.vorlagen.push({ art: 'bibliothek', pfad: e.pfad, rolle });
  ST.extra = { quelle: e.pfad };
  const ziel = zielProjekt(e);
  if ([...$('#st-projekt').options].some((o) => o.value === ziel)) $('#st-projekt').value = ziel;
}

function freistellenAus(e) {
  alsEinzige(e, 'freistellen', 'original');
  $('#st-motiv').value = '';
  formZeigen('Bild übernommen. Ohne Angabe bleibt das Hauptmotiv; sonst sagen, was bleiben soll. Dann „Erstellen“.');
}

// Pose-Skelett aus diesem Bild (Stufe 3l).
// 3D-Modell (Stufe 3t): Detailstufen aus der Einstellung in die Auswahl, die Standardstufe vorgewählt.
function modellStufenFuellen() {
  const sel = $('#st-modell-stufe');
  const stufen = EIN()?.modell3d_stufen || [];
  if (sel.dataset.stand === JSON.stringify(stufen.map((s) => s.id))) return;
  const vorher = sel.value;
  sel.replaceChildren(...stufen.map((s) => option(s.id, s.name)));
  sel.dataset.stand = JSON.stringify(stufen.map((s) => s.id));
  sel.value = stufen.some((s) => s.id === vorher) ? vorher : (stufen.find((s) => s.standard) || stufen[0] || {}).id || '';
}

// Aus der Bibliothek: dieses Bild (Drehblatt oder Einzelbild) als Vorlage für ein 3D-Modell.
function modellAus(e) {
  alsEinzige(e, 'modell3d', 'vorlage');
  const blatt = (e.info?.breite || 0) >= 3 * (e.info?.hoehe || 1);
  formZeigen(blatt ? 'Drehblatt übernommen. „Erstellen“ rechnet daraus ein 3D-Modell (einige Minuten).'
    : EIN()?.modell3d_bild_verfuegbar
      ? 'Bild übernommen. „Erstellen“ rechnet daraus ein 3D-Modell (einige Minuten); für Figuren ist ein Drehblatt mit vier Ansichten genauer.'
      : 'Bild übernommen. „3D aus einem Bild“ ist nicht eingerichtet – zuerst beim Bearbeiten den Vorschlag „Drehblatt“ rechnen.');
}

// Großansicht eines 3D-Modells: die 3D-Datei liegt neben dem Vorschau-Video, gleicher Stamm.
function modellZeilen(e, i) {
  if (!i.modell_3d) return [];
  const rel = `${e.pfad.slice(0, e.pfad.lastIndexOf('/') + 1)}${i.modell_3d}`;
  return [['3D-Datei:',
    h('a', { class: 'knopf knopf-klein', href: `/studio/datei?p=${encodeURIComponent(rel)}`, download: i.modell_3d,
      title: 'GLB mit Texturen herunterladen (für Blender, Web-Betrachter, Spiele-Engines)' }, 'GLB speichern …'),
    stKnopf('Im Ordner zeigen', async () => studio({ aktion: 'zeigen', pfad: rel }), { titel: 'Die 3D-Datei im Explorer markieren' }),
    stKnopf('In ComfyUI ansehen', async () => window.open(ST.stand?.comfy?.url || 'http://127.0.0.1:8188/', '_blank'),
      { titel: 'ComfyUI öffnen; dort die GLB-Datei auf die Fläche ziehen, der Load-3D-Knoten zeigt sie drehbar' })]];
}

function poseAus(e) {
  alsEinzige(e, 'pose', 'original');
  formZeigen('Bild übernommen. „Erstellen“ macht daraus ein Pose-Skelett (etwa 2 s); danach in der Bibliothek „Als Pose-Vorlage“.');
}

// Ein Pose-Skelett als Bild 1 zum Bearbeiten, mit dem Vorschlag „Pose übernehmen“ (die Person kommt als Bild 2 dazu).
function alsPoseVorlage(e) {
  document.querySelector('input[name="st-art"][value="bearbeiten"]').checked = true;
  modusSetzen();
  ST.vorlagen = [{ art: 'bibliothek', pfad: e.pfad, rolle: 'vorlage' },
    ...ST.vorlagen.filter((v) => !(v.rolle === 'vorlage' && v.pfad === e.pfad))];
  ST.extra = { quelle: e.pfad };
  $('#dialog').close();
  vorschlagEinsetzen('pose');
  $('.st-form').scrollIntoView({ block: 'start', behavior: 'smooth' });
}

// Hochskalieren: Bearbeiten wie Vorlage 1 in der nächsten Stufe, die größer ist als das Bild.
function hochskalierenAus(e) {
  const pixel = (e.info?.breite || 0) * (e.info?.hoehe || 0);
  const stufe = (EIN().bearbeiten_aufloesungen || []).filter((a) => a.wert > standardAufl()).find((a) => a.wert * a.wert > pixel * 1.2);
  if (!stufe) {
    stMelden(`Das Bild ist schon ${etwaMP(Math.sqrt(pixel))} groß; größer rechnet das Studio nicht.`);
    return;
  }
  alsEinzige(e, 'bearbeiten', 'vorlage');
  $('#st-prompt').value = HOCHSKALIEREN;
  $('#st-details').checked = false; // bleibt nah am Original; für schwache Fotos gibt es „Foto auffrischen“
  setze('#st-groesse', `vorlage_${stufe.wert}`, 'vorlage');
  formZeigen(`Bild übernommen, Größe ${etwaMP(stufe.wert)} im gleichen Seitenverhältnis. Gesichter zeichnet Qwen dabei leicht neu; dann „Erstellen“.`);
}

function formZeigen(text) {
  $('#dialog').close();
  formAnpassen();
  stMelden(text, true);
  const p = stArt() === 'freistellen' ? $('#st-motiv') : $('#st-prompt');
  p.focus();
  p.setSelectionRange(p.value.length, p.value.length);
  $('.st-form').scrollIntoView({ block: 'start', behavior: 'smooth' });
}

async function mitAenderungen(e, ausformuliertNehmen = false) {
  const i = e.info || {};
  const art = ART[i.art] && i.art !== 'video' ? i.art : (e.medium === 'video' ? 'video_text' : 'bild');
  const video = istVideo(art);
  document.querySelector(`input[name="st-art"][value="${art}"]`).checked = true;
  modusSetzen();
  if (art === 'freistellen') $('#st-motiv').value = i.motiv || '';
  else if (art !== 'pose') $('#st-prompt').value = i.prompt || '';
  if (['verbessern', 'freistellen', 'pose'].includes(art)) {
    // Original und beim Verbessern auch das Vorbild für die Stelle (Stufe 3n) übernehmen.
    const vs = vorlagenAus(i);
    ST.vorlagen = ST.vorlagen.filter((v) => !['original', 'vorbild'].includes(v.rolle))
      .concat(vs.slice(0, 1), art === 'verbessern' ? vs.slice(1).filter((v) => v.rolle === 'vorbild') : []);
  }
  if (art === 'verbessern') {
    // Original und Markierung übernehmen (auch eine per Wort gefundene); fehlt sie, wird neu markiert oder gesucht.
    $('#st-stelle').value = i.stelle || '';
    ST.maske = null;
    const o = original();
    if (o && i.hat_maske) {
      try {
        const m = (await studio({ aktion: 'maske', pfad: e.pfad })).maske;
        ST.maske = { ...m, anteil: maskeAnteil(m), pfad: o.pfad };
      } catch { /* dann neu markieren */ }
    }
    if (i.staerke != null) setze('#st-staerke', i.staerke, $('#st-staerke').value);
  } else if (art === 'modell3d') {
    ST.vorlagen = ST.vorlagen.filter((v) => v.rolle !== 'vorlage').concat(vorlagenAus(i).slice(0, 1));
    modellStufenFuellen();
    setze('#st-modell-stufe', i.stufe, $('#st-modell-stufe').value);
  } else if (art === 'bearbeiten') {
    // Eigenes Format nur, wenn das Original eines hatte; sonst wie Vorlage 1 (auch hochskaliert).
    const f = i.groesse_von === 'format' && formatListe().find((x) => x.breite === i.breite && x.hoehe === i.hoehe);
    const stufe = i.aufloesung && i.aufloesung !== standardAufl() ? `vorlage_${i.aufloesung}` : 'vorlage';
    setze('#st-groesse', i.groesse_von !== 'format' ? stufe : f ? f.id : 'eigen', 'vorlage');
    if (i.groesse_von === 'format' && !f) { $('#st-breite').value = i.breite; $('#st-hoehe').value = i.hoehe; }
    $('#st-details').checked = i.details === true;
  } else if (art === 'video_weiter') {
    // Modus, Länge des neuen Stücks und Schnitte wie beim Original; Größe und Clips kommen aus den Clips (unten).
    setze('#st-modus', i.modus, 'verlaengern');
    const m = WEITER[weiterModus()];
    if (WEITER_LAENGEN.includes(i.clip_bilder)) ST.weiterNeu = i.clip_bilder - m.kontext - m.ende;
    $('#st-neu').dataset.modus = ''; // neu füllen, damit die Länge des Originals gewählt wird
    const fps = VID()?.fps || 24;
    $('#st-schnitt-ende').value = Math.round(((i.schnitt_ende || 0) / fps) * 1000) / 1000;
    $('#st-schnitt-anfang').value = Math.round(((i.schnitt_anfang || 0) / fps) * 1000) / 1000;
  } else if (i.breite && i.hoehe) {
    const f = formatListe().find((x) => x.breite === i.breite && x.hoehe === i.hoehe);
    $('#st-format').value = f ? f.id : 'eigen';
    if (!f) { $('#st-breite').value = i.breite; $('#st-hoehe').value = i.hoehe; }
  }
  if (art === 'bild') {
    $('#st-durchsichtig').checked = i.durchsichtig === true;
    $('#st-ausformulieren').checked = i.ausformulieren === true;
  }
  // „Ausformuliert übernehmen“: der Text des Prompt-Enhancers wird selbst zum Prompt, damit man ihn gezielt ändern kann;
  // nochmals ausformulieren würde ihn neu erfinden, deshalb ist das Häkchen dann aus.
  const ausformuliert = ausformuliertNehmen && art === 'bild' && !!i.prompt_ausformuliert;
  if (ausformuliert) {
    $('#st-prompt').value = i.prompt_ausformuliert;
    $('#st-ausformulieren').checked = false;
  }
  if (i.schritte) {
    const q = $('#st-qualitaet');
    // Turbo-Bilder (6 Schritte LoRA bzw. 8 Schritte Turbo-Modell) kommen in die Stufe „Turbo“.
    const ziel = !video && i.turbo ? (EIN()?.qualitaet.find((x) => x.turbo)?.schritte ?? i.schritte) : i.schritte;
    if (![...q.options].some((o) => +o.value === ziel)) q.append(option(ziel, `${ziel} Schritte (wie das Original)`));
    q.value = ziel;
  }
  if (video && i.laenge_bilder && art !== 'video_weiter') {
    const l = $('#st-laenge');
    if (![...l.options].some((o) => +o.value === i.laenge_bilder)) l.append(option(i.laenge_bilder, `${sekundenVon(i.laenge_bilder)} s (wie das Original)`));
    l.value = i.laenge_bilder;
  }
  if (art === 'video_referenz') ST.referenz = { genau: i.referenz_genau === 'max' ? 'max' : 'match', ton: i.ton_behalten !== false };
  if (video) $('#st-realismus').checked = i.realismus === true;
  if (art === 'video_referenz') $('#st-tauschen').checked = i.tauschen === true;
  $('#st-zufall').checked = i.variation == null;
  $('#st-variation').value = i.variation ?? '';
  const ziel = zielProjekt(e);
  if ([...$('#st-projekt').options].some((o) => o.value === ziel)) $('#st-projekt').value = ziel;
  if (ROLLEN[art] && !['verbessern', 'freistellen', 'pose'].includes(art) && !wiederholbar(e)) ST.vorlagen = vorlagenAus(i);
  ST.extra = { cfg: video ? undefined : i.cfg || undefined, quelle: e.pfad };
  formZeigen(art === 'verbessern' && !aktuelleMaske() ? 'Einstellungen übernommen. Markiere die Stelle neu, dann „Erstellen“.'
    : ausformuliert ? 'Ausformulierten Text als Prompt übernommen (Ausformulieren ist aus). Text ändern, dann „Erstellen“.'
      : 'Einstellungen übernommen. Ändern und „Erstellen“ drücken.');
}

function zuVideo(e) {
  const i = e.info || {};
  document.querySelector('input[name="st-art"][value="video_bild"]').checked = true;
  modusSetzen();
  ST.vorlagen = ST.vorlagen.filter((v) => v.rolle !== 'start');
  ST.vorlagen.push({ art: 'bibliothek', pfad: e.pfad, rolle: 'start' });
  // Format nach dem Seitenverhältnis des Bildes; die gewählte Auflösungsstufe (schnell/nativ) bleibt.
  if (i.breite && i.hoehe) {
    const r = i.breite / i.hoehe;
    const lage = r > 1.2 ? 'breit' : r < 0.83 ? 'hoch' : 'quadrat';
    const nativ = $('#st-format').value.endsWith('_nativ') ? '_nativ' : '';
    if ([...$('#st-format').options].some((o) => o.value === lage + nativ)) $('#st-format').value = lage + nativ;
  }
  $('#st-prompt').value = i.prompt ? `${i.prompt}\n\n` : '';
  ST.extra = { quelle: e.pfad };
  formZeigen('Startbild übernommen. Beschreibe, was im Video passieren soll (Bewegung, Kamera, Gesprochenes), dann „Erstellen“.');
}

function verwenden(e, rolle, zielArt, text) {
  const bleiben = stArt() === 'video_szenen' && ['start', 'bild'].includes(rolle); // Szenenfolge: dort einsetzen
  vorlageDazu({ art: 'bibliothek', pfad: e.pfad, rolle }, bleiben ? null : zielArt);
  formZeigen(text);
}

function vorlagenText(i) {
  return vorlagenAus(i).map((v) => `${i.herkunft === 'studio' ? `${ROLLENNAME[v.rolle]}: ` : ''}${v.pfad.split(/[\\/]/).pop()}`).join(', ');
}

function detailOeffnen(pfad) {
  const liste = ST.liste;
  const index = liste.findIndex((x) => x.pfad === pfad);
  const e = liste[index] || ST.bib?.eintraege.find((x) => x.pfad === pfad);
  if (!e) return;
  ST.detail = pfad;
  const i = e.info || {};
  const video = e.medium === 'video';
  const d = $('#dialog');
  d.className = 'gross st-detail';
  const medium = video
    ? h('video', { src: dateiUrl(e), controls: '', autoplay: '', loop: '', playsinline: '' })
    : h('img', { src: dateiUrl(e), alt: anzeigePrompt(i) || e.name, class: durchsichtig(i) });
  const zeilen = [];
  const zeile = (name, wert) => { if (wert != null && wert !== '') zeilen.push(h('dt', { text: name }), h('dd', { text: String(wert) })); };
  zeile('Art', (ART[i.art] || (video ? 'Video' : 'Bild')) + (i.durchsichtig ? ' · durchsichtiger Hintergrund' : '')
    + (i.art === 'video_weiter' && WEITER[i.modus] ? ` · ${WEITER[i.modus].erledigt}` : ''));
  zeile('Projekt', projektName(e.projekt));
  const hoch = i.art === 'bearbeiten' && i.aufloesung && i.aufloesung !== standardAufl() ? ' · hochskaliert' : '';
  zeile('Größe', i.breite && i.hoehe ? `${i.breite} × ${i.hoehe}${hoch}` : null);
  if (i.laenge_bilder) zeile('Länge', `${sekundenVon(i.laenge_bilder)} s (${i.laenge_bilder} Bilder)`);
  const turbo = (istVideo(i.art) && i.schritte && i.schritte <= (VID()?.turbo_bis_schritte || 8)) || (!istVideo(i.art) && i.turbo)
    ? (!istVideo(i.art) && i.turbo_modell ? ', mit Turbo-Modell' : ', mit Turbo') : '';
  const lora = `${i.acc8 ? ', mit 8-Schritt-LoRA' : i.dmad ? ', mit DMAD (4 Schritte)' : turbo}${i.details ? ', mit Detail-LoRA' : ''}${i.realismus ? ', mit Realism-LoRA' : ''}${i.tauschen ? ', Person getauscht' : ''}`;
  const ohneStufe = i.art === 'pose' || i.verfahren === 'schnell'; // ohne Qwen gerechnet: keine Qualitätsstufe
  zeile('Qualität', i.schritte && !ohneStufe ? (i.qualitaet ? `${i.qualitaet} (${i.schritte} Schritte${lora})` : `${i.schritte} Schritte${lora}`) : null);
  if (i.art === 'verbessern') {
    const s = EIN()?.verbessern.staerken.find((x) => Math.abs(x.wert - i.staerke) < 1e-6);
    zeile('Wie viel ändern', s ? `${s.name}: ${s.text}` : i.staerke);
    zeile('Markiert', i.markiert != null ? `${prozentText(i.markiert)} des Bildes` : null);
    zeile('Stelle per Wort', i.stelle ? `„${i.stelle}“ (gefunden mit SAM3)` : null);
  }
  if (i.art === 'freistellen') zeile('Verfahren', i.verfahren === 'schnell' ? 'schnell (BiRefNet), Hauptmotiv' : 'Qwen');
  if (i.art === 'pose') zeile('Personen', i.personen ? 'alle (einzeln gesucht mit SAM3)' : 'eine (ganzes Bild)');
  zeile('Ausformuliert', i.prompt_ausformuliert);
  zeile('Szenenfolge', i.szenenfolge ? `Szene ${i.szenenfolge.szene} von ${i.szenenfolge.szenen}` : null);
  if (i.art === 'video_weiter') {
    zeile('Neues Stück', i.neu_bilder ? `${sekundenVon(i.neu_bilder)} s (${i.neu_bilder} Bilder)` : null);
    const weg = (n) => `${stZahl(Math.round((n / (VID()?.fps || 24)) * 100) / 100)} s (${n} Bilder)`;
    zeile('Gekürzt', [i.schnitt_ende ? `Ende des Clips davor um ${weg(i.schnitt_ende)}` : '',
      i.schnitt_anfang ? `Anfang des Clips danach um ${weg(i.schnitt_anfang)}` : ''].filter(Boolean).join(', '));
  }
  if (i.art === 'video_referenz' && i.herkunft === 'studio') {
    zeile('Wie genau', i.referenz_genau === 'max' ? 'so genau wie möglich' : 'normal');
    if (vorlagenAus(i).some((v) => v.rolle === 'clip')) zeile('Ton des ersten Clips', i.ton_behalten === false ? 'weggelassen' : 'behalten');
  }
  if (i.art === 'video_zeitlupe') zeile('Zeitlupe', `${stZahl(i.faktor)}-fach so lang (${i.quell_bilder} → ${i.laenge_bilder} Bilder, ohne Ton)`);
  if (i.art === 'video_freistellen') zeile('Freigestellt', `„${i.motiv}“ (${i.verfahren === 'kombi' ? 'SAM3 wählt aus, BiRefNet zieht die Kanten' : i.verfahren}), WebM mit Transparenz`);
  if (!VIDEO_HILFEN.includes(i.art)) zeile('Variationsnummer', i.variation);
  zeile('Modell', i.modell ? i.modell + (i.int8 ? ' · INT8' : '') : null);
  zeile('Vorlagen', vorlagenText(i));
  zeile('Rechenzeit', i.rechenzeit_s ? dauer(i.rechenzeit_s) : null);
  zeile('Erstellt', i.erstellt ? new Date(i.erstellt).toLocaleString('de-DE') : stDatum(e.zeit));
  zeile('Herkunft', HERKUNFT[i.herkunft]);
  zeile('Datei', e.pfad);
  if (i.art === 'modell3d') {
    zeile('3D-Datei', i.modell_3d ? `${i.modell_3d}${i.modell_3d_bytes ? ` (${stZahl(Math.round((i.modell_3d_bytes / 1048576) * 10) / 10)} MB)` : ''}` : 'nicht gefunden');
    zeile('Aus', { drehblatt: 'Drehblatt (vier Ansichten)', bild: 'einem Bild (Pixal3D Einzelbild, Blickwinkel von MoGe)', ansichten: 'Einzelansichten' }[i.modus] || i.modus);
    zeile('Detailstufe', (EIN()?.modell3d_stufen || []).find((s) => s.id === i.stufe)?.name || i.stufe);
  }
  const grund = wiederholbar(e);
  const was = video ? 'Video' : 'Bild';
  const ziel = h('select', { 'aria-label': 'Zielprojekt' }, option('', 'Ohne Projekt'),
    ...(ST.stand?.projekte || []).filter((p) => !p.aus_2wild).map((p) => option(p.name, p.name)));
  const geh = (schritt) => { const n = liste[index + schritt]; if (n) detailOeffnen(n.pfad); };
  // Zeitlupe und Freistellen (seit 09.10.2026) direkt aus der Großansicht; das Original bleibt unverändert.
  const hilfe = (art, extra, text) => async () => {
    await studio({ aktion: 'erzeugen', projekt: zielProjekt(e), art, quelle: e.pfad,
      vorlagen: [{ art: 'bibliothek', pfad: e.pfad, rolle: 'original' }], ...extra });
    stMelden(text, true);
    d.close();
  };
  const hilfeZeile = video && /\.(mp4|mov)$/i.test(e.pfad) && (EIN()?.zeitlupe_verfuegbar || EIN()?.video_freistellen_verfuegbar)
    ? [['Bearbeiten:',
      ...(EIN()?.zeitlupe_verfuegbar ? [
        stKnopf('Zeitlupe 1,5×', hilfe('video_zeitlupe', { faktor: 1.5 }, 'Zeitlupe wird erstellt (1,5-fach so lang, ohne Ton).'),
          { titel: 'Langsamer und länger ohne neu zu rechnen: Zwischenbilder (RIFE), in Sekunden fertig. Für ruhige Videos ohne Ton, etwa Hintergründe' }),
        stKnopf('Zeitlupe 2×', hilfe('video_zeitlupe', { faktor: 2 }, 'Zeitlupe wird erstellt (doppelt so lang, ohne Ton).'),
          { titel: 'Halbe Geschwindigkeit, doppelte Länge; Zwischenbilder (RIFE), ohne Ton' })] : []),
      ...(EIN()?.video_freistellen_verfuegbar ? [
        stKnopf('Person freistellen', hilfe('video_freistellen', { motiv: EIN().video_freistellen_motiv || 'person' },
          'Das Video wird freigestellt (WebM mit durchsichtigem Hintergrund).'),
        { titel: 'Personen behalten, alles andere wird durchsichtig (WebM mit Transparenz, ohne Ton); andere Motive über den Skill' })] : [])]]
    : [];
  const verwendenZeilen = video && i.art === 'modell3d' ? modellZeilen(e, i)
    : video && /\.webm$/i.test(e.pfad) ? []
    : video
    ? [...hilfeZeile, ['Verwenden:', stKnopf('Als Referenz-Clip', async () => verwenden(e, 'clip', 'video_referenz', 'Clip als Referenz übernommen. Beschreibe das neue Video, dann „Erstellen“.'),
      { titel: 'Bewegung und Timing dieses Clips in ein neues Video übernehmen' })],
    // Stufe 3m: der Clip bleibt unverändert, ein neues Stück kommt dazu.
    ['Weiterführen:',
      stKnopf('Verlängern …', async () => weiterAus(e, 'verlaengern', 'ausgang'),
        { titel: 'Ein neues Stück ans Ende setzen; es setzt die letzten 1,6 s mit Bewegung und Ton fort' }),
      stKnopf('Davor setzen …', async () => weiterAus(e, 'davor', 'ziel'),
        { titel: 'Ein neues Stück an den Anfang setzen; es endet genau auf dem ersten Bild' }),
      stKnopf('Schleife schließen …', async () => weiterAus(e, 'schleife', 'ausgang'),
        { titel: 'Ein neues Stück, das vom Ende zurück zum Anfang führt, etwa für ein Hintergrundvideo in Dauerschleife' }),
      stKnopf('Verbinden …', async () => weiterAus(e, 'verbinden', 'ausgang'),
        { titel: 'Dieses Video als ersten Clip; ein neues Stück führt in den zweiten (dort „Als Clip danach“)' }),
      stKnopf('Als Clip danach', async () => weiterAus(e, 'verbinden', 'ziel'),
        { titel: 'Dieses Video als zweiten Clip beim Verbinden' })]]
    : i.art === 'pose'
      // Pose-Skelett: nur als Bild 1 zum Bearbeiten sinnvoll (Vorschlag „Pose übernehmen“).
      ? [['Verwenden:', stKnopf('Als Pose-Vorlage', async () => alsPoseVorlage(e),
        { haupt: true, titel: 'Beim Bearbeiten als Bild 1 mit dem Vorschlag „Pose übernehmen“; die Person kommt als Bild 2 dazu' })]]
      : [['Bearbeiten:',
      // Freigestellt oder mit durchsichtigem Hintergrund erzeugt: Verbessern und Hochskalieren lieferten meist ein Bild
      // auf Weiß, einmal Transparenz ohne Aufräumen (Lila darunter); dafür das Original nehmen bzw. neu erzeugen.
      ...(durchsichtig(i) ? [] : [
        stKnopf('Stelle verbessern …', async () => stelleVerbessern(e), { titel: 'Eine Stelle markieren und neu entstehen lassen, etwa eine Hand reparieren oder etwas entfernen' }),
        stKnopf('Freistellen', async () => freistellenAus(e), { titel: 'Das Motiv behalten, alles andere wird durchsichtig (PNG)' }),
        stKnopf('Hochskalieren', async () => hochskalierenAus(e), { titel: 'Größer und schärfer neu rechnen, im gleichen Seitenverhältnis' }),
        ...(EIN()?.pose_verfuegbar ? [stKnopf('Pose-Skelett', async () => poseAus(e),
          { titel: 'Die Haltung der Person als Strichfigur, um sie beim Bearbeiten auf eine andere Person zu übertragen' })] : [])]),
      // 3D-Modell (Stufe 3t): aus einem Drehblatt (vier Ansichten) oder, wenn eingerichtet, aus diesem einen Bild.
      ...(EIN()?.modell3d_verfuegbar ? [stKnopf('3D-Modell', async () => modellAus(e),
        { titel: 'Pixal3D rechnet daraus ein 3D-Modell (GLB): aus einem Drehblatt mit vier Ansichten oder aus einem einzelnen Bild' })] : []),
      stKnopf('Als Vorlage', async () => verwenden(e, 'vorlage', 'bearbeiten', 'Vorlage übernommen. Beschreibe die Änderung, dann „Erstellen“.'),
        { titel: durchsichtig(i) ? 'Das Motiv auf Weiß als Vorlage, etwa um es in eine neue Szene zu setzen' : 'Dieses Bild mit eigener Beschreibung bearbeiten' }),
      // Stufe 3n: nur, wenn gerade eine Stelle in einem anderen Bild verbessert wird.
      ...(stArt() === 'verbessern' && maxVorbilder() && original() && original().pfad !== e.pfad ? [
        stKnopf('Für die Stelle', async () => verwenden(e, 'vorbild', null, 'Als Vorbild für die Stelle übernommen. Im Text als „Bild 2“ ansprechen, dann „Erstellen“.'),
          { titel: 'Beim Verbessern: Person, Logo oder Gegenstand aus diesem Bild an die markierte Stelle setzen (Bild 2)' })] : [])],
    ['Für Video:',
      stKnopf('Zu Video', async () => zuVideo(e), { titel: 'Ein Video, das mit diesem Bild beginnt' }),
      stKnopf('Als Endbild', async () => verwenden(e, 'ende', 'video_bild', 'Endbild übernommen. Fehlt noch ein Startbild, wähle es in der Bibliothek mit „Zu Video“.'),
        { titel: 'Ein Video, das auf diesem Bild endet' }),
      stKnopf('Als Referenz', async () => verwenden(e, 'bild', 'video_referenz', 'Referenzbild übernommen. Im Text als „Bild 1“ ansprechen.'),
        { titel: 'Person oder Ding aus diesem Bild in ein Video übernehmen' })]];
  // Verbessert, freigestellt oder wie Vorlage 1 bearbeitet: zwischen Vorher und Ergebnis umschalten (auch mit V),
  // in gleicher Anzeigegröße, auch wenn das Original kleiner ist.
  const mediumBox = h('div', { class: 'st-detail-medium' }, medium);
  let vorher = null;
  const vergleichbar = ['verbessern', 'freistellen', 'pose'].includes(i.art) || (i.art === 'bearbeiten' && i.groesse_von !== 'format');
  const o = !video && vergleichbar && i.herkunft === 'studio' ? vorlagenAus(i)[0] : null;
  if (o && (o.art === 'datei' || ST.bib?.eintraege.some((x) => x.pfad === o.pfad))) {
    const nachher = medium.src;
    const vorherUrl = bildUrl(o, e.pfad);
    vorher = h('button', { type: 'button', id: 'st-vorher', class: 'knopf knopf-klein', 'aria-pressed': 'false',
      title: `Zwischen ${i.art === 'bearbeiten' ? 'Vorlage 1' : 'Original'} und Ergebnis wechseln (V)` }, 'Vorher zeigen');
    vorher.addEventListener('click', () => {
      const an = vorher.getAttribute('aria-pressed') !== 'true';
      vorher.setAttribute('aria-pressed', String(an));
      vorher.textContent = an ? 'Nachher zeigen' : 'Vorher zeigen';
      if (an) {
        const r = medium.getBoundingClientRect();
        Object.assign(medium.style, { width: `${r.width}px`, height: `${r.height}px` });
      } else {
        Object.assign(medium.style, { width: '', height: '' });
      }
      medium.src = an ? vorherUrl : nachher;
      medium.classList.toggle('durchsichtig', !an && !!durchsichtig(i));
      mediumBox.classList.toggle('vorher', an);
    });
  }
  d.replaceChildren(
    h('div', { class: 'st-detail-kopf' },
      h('h2', { id: 'dialog-titel', text: e.name }),
      h('div', { class: 'st-zeile' }, vorher,
        h('button', { type: 'button', class: 'knopf knopf-klein knopf-symbol', title: 'Vorherige (←)', 'aria-label': 'Vorherige', disabled: index <= 0, onclick: () => geh(-1) }, '‹'),
        h('button', { type: 'button', class: 'knopf knopf-klein knopf-symbol', title: 'Nächste (→)', 'aria-label': 'Nächste', disabled: index < 0 || index >= liste.length - 1, onclick: () => geh(1) }, '›'),
        h('button', { type: 'button', class: 'knopf knopf-klein', onclick: () => d.close() }, 'Schließen'))),
    h('div', { class: 'st-detail-raster' },
      mediumBox,
      h('div', { class: 'st-detail-info' },
        h('p', { class: 'st-detail-prompt', text: anzeigePrompt(i) || 'Zu dieser Datei ist kein Prompt bekannt.' }),
        h('div', { class: 'st-zeile' },
          stKnopf('Nochmal', async () => { await studio(await wiederAnfrage(e, false)); stMelden(`Dasselbe ${was} wird noch einmal erstellt.`, true); d.close(); },
            { haupt: true, aus: !!grund, titel: grund || 'Gleiche Einstellungen und gleiche Variationsnummer' }),
          stKnopf('Variation', async () => { await studio(await wiederAnfrage(e, true)); stMelden(`Eine neue Variation wird erstellt.`, true); d.close(); },
            { aus: !!grund || ohneStufe,
              titel: grund || (ohneStufe ? 'Ohne Qwen gerechnet: jede Nummer ergibt dasselbe Ergebnis' : 'Gleiche Einstellungen, neue Variationsnummer') }),
          stKnopf('Mit Änderungen …', async () => mitAenderungen(e),
            { aus: !i.prompt, titel: 'Alle Einstellungen ins Formular übernehmen' }),
          stKnopf('Prompt kopieren', async () => { await navigator.clipboard.writeText(i.prompt || ''); stMelden('Prompt kopiert.', true); },
            { aus: !i.prompt || i.art === 'pose' }),
          ...(i.art === 'bild' && i.prompt_ausformuliert ? [stKnopf('Ausformuliert übernehmen …', async () => mitAenderungen(e, true),
            { titel: 'Den ausformulierten Text als Prompt ins Formular übernehmen, um ihn gezielt zu ändern' })] : [])),
        ...verwendenZeilen.map(([titel, ...knoepfe]) => h('div', { class: 'st-zeile st-verwenden' },
          h('span', { class: 'leise', text: titel }), ...knoepfe)),
        h('dl', { class: 'st-detail-werte' }, ...zeilen),
        h('div', { class: 'st-zeile st-detail-ablage' }, ziel,
          stKnopf('Verschieben', async () => { await verschieben([e.pfad], ziel.value); d.close(); }),
          stKnopf('Im Ordner zeigen', () => studio({ aktion: 'zeigen', pfad: e.pfad })),
          stKnopf('In den Papierkorb …', async () => papierkorbFragen([e.pfad]))))));
  if (!d.open) d.showModal();
}

document.addEventListener('keydown', (ev) => {
  const d = $('#dialog');
  if (!d.open || !d.classList.contains('st-detail') || /^(INPUT|SELECT|TEXTAREA|VIDEO)$/.test(document.activeElement?.tagName)) return;
  if (ev.key.toLowerCase() === 'v' && !ev.ctrlKey && !ev.metaKey && !ev.altKey && $('#st-vorher')) {
    ev.preventDefault();
    $('#st-vorher').click();
    return;
  }
  const index = ST.liste.findIndex((x) => x.pfad === ST.detail);
  const n = ev.key === 'ArrowRight' ? ST.liste[index + 1] : ev.key === 'ArrowLeft' ? ST.liste[index - 1] : null;
  if (n) { ev.preventDefault(); detailOeffnen(n.pfad); }
});
$('#dialog').addEventListener('close', () => {
  $('#dialog video')?.pause();
  ST.detail = null;
});

// ------------------------------------------------------------------ Ablauf

async function stBibLaden(neu = false) {
  try {
    ST.bib = await api(`/api/studio/bibliothek${neu ? '?neu=1' : ''}`);
    ST.bibStand = ST.bib.stand;
  } catch { /* nächster Versuch beim nächsten Durchlauf */ }
}

async function stAktualisieren() {
  try {
    ST.stand = await api('/api/studio');
  } catch {
    ST.stand = null;
  }
  if (ST.stand) {
    formEinrichten();
    projekteFuellen();
    if (ST.stand.bibliothek_stand !== ST.bibStand) await stBibLaden();
  }
  comfyHinweis();
  rasterZeichnen();
}

function stSchleife() {
  const offen = ST.stand?.auftraege.some((a) => a.zustand === 'laeuft' || a.zustand === 'wartet');
  const weiter = () => setTimeout(stSchleife, offen ? 1500 : 4000);
  if (!ST.sichtbar) return weiter();
  stAktualisieren().finally(weiter);
}

$('#st-erstellen').addEventListener('click', erstellen);
$('#st-prompt').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) erstellen(); });
$('#st-projekt-neu').addEventListener('click', projektNeu);
// Szenenfolge: eine Szene anhängen und gleich in ihr Textfeld springen.
$('#st-szene-dazu').addEventListener('click', () => {
  ST.szenen.push({ text: '', sekunden: null, realismus: ST.szenen[ST.szenen.length - 1]?.realismus === true });
  $('#st-szenen-liste').dataset.anzahl = '';
  formAnpassen();
  const felder = $('#st-szenen-liste').querySelectorAll('textarea');
  felder[felder.length - 1]?.focus();
});
for (const r of document.querySelectorAll('input[name="st-art"]')) r.addEventListener('change', () => { modusSetzen(); formAnpassen(); });
for (const sel of ['#st-format', '#st-groesse', '#st-qualitaet', '#st-laenge', '#st-zufall', '#st-anzahl', '#st-breite', '#st-hoehe', '#st-projekt', '#st-staerke', '#st-details', '#st-durchsichtig', '#st-ausformulieren', '#st-realismus', '#st-tauschen', '#st-pruefen']) {
  $(sel).addEventListener('change', formAnpassen);
}
// Weiterführen: Die gewählte Länge gilt als Wunsch auch für andere Modi. Ein einzelner Clip wechselt beim Moduswechsel
// seine Rolle (etwa Verlängern → Davor setzen); ein Schnitt, der zu einem anderen Clip gehörte, fällt dabei weg.
$('#st-neu').addEventListener('change', () => {
  const m = WEITER[weiterModus()];
  ST.weiterNeu = +$('#st-neu').value - m.kontext - m.ende;
  formAnpassen();
});
$('#st-modus').addEventListener('change', () => {
  const rollen = WEITER[weiterModus()].rollen;
  const clips = ST.vorlagen.filter((v) => ['ausgang', 'ziel'].includes(v.rolle));
  if (rollen.length === 1 && clips.length && !clips.some((v) => v.rolle === rollen[0])) {
    clips[0].rolle = rollen[0];
    $(rollen[0] === 'ausgang' ? '#st-schnitt-ende' : '#st-schnitt-anfang').value = 0;
  }
  formAnpassen();
});
for (const id of ['#st-schnitt-ende', '#st-schnitt-anfang']) $(id).addEventListener('change', formAnpassen);
$('#st-prompt').addEventListener('input', rezeptHinweis); // vor formMerken, damit eine beendete Zuordnung mitgespeichert wird
for (const id of ['#st-prompt', '#st-variation']) $(id).addEventListener('input', formMerken);
// Beim Freistellen entscheidet der Text über das Verfahren (leer: schnell), also auch über Qualität und Zeitschätzung.
$('#st-motiv').addEventListener('input', formAnpassen);
$('#st-stelle').addEventListener('input', erstellenKnopf);
for (const id of ['#st-motiv', '#st-stelle']) $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); erstellen(); } });
$('#st-suche').addEventListener('input', () => { ST.filter.suche = $('#st-suche').value; rasterZeichnen(); });
$('#st-filter-projekt').addEventListener('change', () => { ST.filter.projekt = $('#st-filter-projekt').value; formMerken(); rasterZeichnen(); });
for (const b of document.querySelectorAll('[data-st-medium]')) {
  b.addEventListener('click', () => {
    ST.filter.medium = b.dataset.stMedium;
    for (const x of document.querySelectorAll('[data-st-medium]')) x.classList.toggle('aktiv', x === b);
    rasterZeichnen();
  });
}
$('#st-auswaehlen').addEventListener('click', () => { ST.auswaehlen = true; rasterZeichnen(); });
$('#st-auswahl-ende').addEventListener('click', auswahlBeenden);
$('#st-verschieben').addEventListener('click', async () => {
  try { await verschieben([...ST.auswahl], $('#st-ziel-projekt').value); auswahlBeenden(); } catch (err) { stMelden(err.message); }
});
$('#st-papierkorb').addEventListener('click', () => papierkorbFragen([...ST.auswahl], auswahlBeenden));
$('#st-ordner').addEventListener('click', () => {
  const p = ST.filter.projekt === '*' ? '' : ST.filter.projekt;
  studio({ aktion: 'zeigen', projekt: p }).catch((err) => stMelden(err.message));
});

window.studioSichtbar = (an) => {
  ST.sichtbar = an;
  if (an) stAktualisieren();
};
stSchleife();
