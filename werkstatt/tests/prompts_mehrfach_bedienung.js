'use strict';

const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');

const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
const code = fs.readFileSync('werkstatt/web/prompts.js', 'utf8');
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));
const kopie = (wert) => JSON.parse(JSON.stringify(wert));

async function starten(ablage = new Map(), speicherfehler = false) {
  const { dokument: document, Element } = dokumentBauen();
  const anfragen = [];
  const belege = new Map();
  const kopiert = [];
  const optionen = {
    ...kopie(regeln),
    schreibmodelle: [
      { id: 'sol', name: 'Codex · Sol · sehr hoch', anbieter: 'codex', modell: 'sol', stufe: 'xhigh',
        prompts_verfuegbar: true, zugang_text: 'Abo', cloud: 'OpenAI' },
      { id: 'opus', name: 'Claude · Opus · hoch', anbieter: 'claude', modell: 'opus', stufe: 'high',
        prompts_verfuegbar: true, zugang_text: 'Abo', cloud: 'Anthropic' },
      { id: 'drei', name: 'Drittes Modell', anbieter: 'lokal', modell: 'drei', prompts_verfuegbar: true },
      { id: 'vier', name: 'Viertes Modell', anbieter: 'lokal', modell: 'vier', prompts_verfuegbar: true },
      { id: 'aus', name: 'Unverfügbares Modell', anbieter: 'lokal', modell: 'aus',
        prompts_verfuegbar: false, prompts_grund: 'Modell ist nicht geladen.' },
    ],
    zielprofile: regeln.zielprofile.map((p) => ({ ...p, varianten: p.anbieter === 'lokal'
      ? [{ eintrag: p.eintraege[0], name: p.name, testprofile: [{ id: 'test', name: 'Testprofil' }], varianten: [] }]
      : [{ testprofil: p.id === 'claude' ? 'opus' : 'sol', name: p.name }] })),
  };
  const eintrag = {
    id: 'Eintrag', titel: 'Code-Ergebnis', herkunft: 'ordner', prompt_typ: 'code', modus: 'prompt',
    bearbeitbar: true, kopf_stand: 'kopf1', bevorzugt: 'Fassung 1', tests: [], schaerfen: [],
    auftragsgruppen: [], warteschlange: [], fassungen: [{ name: 'Fassung 1', text: 'Original [A]', stand: 'original' }],
  };
  const eintraege = new Map([[eintrag.id, eintrag]]);
  const server = { fehler: null, verloren: false, vollstaendig: false };
  let uuid = 0;
  let dialog;
  const ctx = vm.createContext({
    document, console, aktualisieren() {}, fehlerMelden(text) { throw Error(text); },
    window: { scrollX: 0, scrollY: 0, scrollTo({ left, top }) { this.scrollX = left; this.scrollY = top; }, addEventListener() {} },
    crypto: { randomUUID: () => 'sendung-' + (++uuid) },
    navigator: { clipboard: { writeText: async (text) => kopiert.push(text) } },
    localStorage: {
      getItem(key) { if (speicherfehler) throw Error('Browserablage gesperrt'); return ablage.get(key) ?? null; },
      setItem(key, wert) { if (speicherfehler) throw Error('Browserablage gesperrt'); ablage.set(key, wert); },
    },
    setTimeout() { throw Error('Dieser Test benötigt keine Zeitgeber.'); },
    dialogOeffnen(titel, inhalt, knoepfe) {
      dialog = new Element('dialog');
      dialog.titel = titel; dialog.open = true;
      dialog.append(...inhalt, ...knoepfe); document.append(dialog);
      dialog.close = () => dialog.remove();
      return dialog;
    },
    fetch: async (pfad, opt) => {
      const daten = opt?.body ? JSON.parse(opt.body) : null;
      anfragen.push([pfad, daten]);
      let wert;
      if (pfad === '/api/prompt-optionen') wert = optionen;
      else if (pfad === '/api/prompts') wert = { eintraege: [...eintraege.values()], fehler: [], warteschlange: eintrag.warteschlange };
      else if (pfad.startsWith('/api/prompt?id=')) wert = eintraege.get(decodeURIComponent(pfad.split('id=')[1]));
      else if (pfad === '/api/zusammenfassung') wert = { auswerter: optionen.schreibmodelle };
      else if (pfad.startsWith('/api/prompt-datei?')) {
        const datei = decodeURIComponent(pfad.split('datei=')[1]);
        assert(belege.has(datei), 'Unbekannter Fake-Beleg ' + datei);
        if (server.belegWarten) await server.belegWarten;
        wert = belege.get(datei);
      } else if (daten?.aktion === 'composer_vorschau') {
        wert = {
          schreibmodelle: optionen.schreibmodelle.filter((p) => daten.schreibmodelle.includes(p.id)),
          ziele: daten.ziele.map((z) => ({ zielmodell: { name: z.zielprofil }, auftrag: 'Fake-Auftrag', gesendet_stand: 'hash' })),
          gesendet_staende: { ziel: 'hash' },
        };
      } else if (daten?.aktion === 'composer_senden') {
        if (server.warten) await server.warten;
        if (server.verloren) throw Error('Failed to fetch');
        if (server.fehler) return { ok: false, status: server.fehler, json: async () => ({ fehler: 'Fortsetzung abgelehnt.' }) };
        wert = { gefunden: true, vollstaendig: server.vollstaendig, id: eintrag.id, auftragsgruppe: daten.anfrage_id };
      } else if (daten?.aktion === 'composer_status') {
        wert = { gefunden: true, vollstaendig: server.vollstaendig, id: eintrag.id, auftragsgruppe: daten.anfrage_id };
      } else if (daten?.aktion === 'bevorzugt') {
        assert.equal(daten.kopf_stand, eintrag.kopf_stand);
        eintrag.bevorzugt = daten.name; eintrag.kopf_stand = 'kopf2'; wert = eintrag;
      } else if (pfad === '/api/fassung' || daten?.aktion === 'wiederholen_beleg') wert = { ok: true };
      else throw Error('Unerwartete Fake-Anfrage ' + pfad + ' ' + daten?.aktion);
      return { ok: true, json: async () => kopie(wert) };
    },
  });
  vm.runInContext(app.split('let STAND =')[0], ctx);
  vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), ctx);
  vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='), app.indexOf('function schrittListe(')), ctx);
  vm.runInContext(code, ctx);
  const run = (text) => vm.runInContext(text, ctx);
  const $ = (selector) => document.querySelector(selector);
  const knopf = (text, wurzel = document) => wurzel.querySelectorAll('button').find((b) => b.textContent === text);
  const klicken = async (el) => {
    assert(el, 'Bedienelement fehlt');
    assert(!el.disabled, 'Bedienelement ist gesperrt');
    el.focus(); await el.ausloesen('click');
  };
  const waehlen = async (id, checked) => {
    const cb = $('#p-schreibmodelle').querySelector(`input[value="${id}"]`);
    assert(cb); assert(!cb.disabled);
    cb.checked = checked; await cb.ausloesen('change');
  };
  const auswahl = () => kopie(run('P.entwurf.schreibmodelle'));
  run('pComposerZeigen()');
  await run('pOptionenLaden()');
  return { document, Element, ctx, $, run, knopf, klicken, waehlen, auswahl,
    ablage, anfragen, belege, kopiert, optionen, eintrag, eintraege, server, get dialog() { return dialog; } };
}

function ergebnis(u, nr, ziel = 'qwen27:qwen27-unsloth') {
  const p = u.optionen.schreibmodelle[nr % 2];
  const name = 'Ergebnis ' + nr;
  u.eintrag.fassungen.push({ name, text: 'Aktuelle Fassung ' + nr + ' [A]', stand: 'aktuell-' + nr });
  const b = {
    datei: 'Lauf' + nr + '.md', lauf_nr: nr, auftragsgruppe: 'gruppe', auftrags_id: 'auftrag' + nr,
    zielschluessel: ziel, zielprofil_id: ziel.split(':')[0], zielmodell: ziel.startsWith('qwen') ? 'Qwen 27B' : 'Claude',
    schreibmodell_id: p.id, auswerter: p.name, anbieter: p.anbieter, modell: p.modell, denkstufe: p.stufe,
    zustand: 'fertig', antwort_vorhanden: true, ergebnis_fassung: name, dauer_s: 12, tokens: 42,
    fassung: 'Fassung 1', fassung_stand: 'original', original: 'Original [A]', neue_fassung: 'Neue Fassung ' + nr + ' [A]',
    stichpunkte: '- Klarer formuliert.\n- Grenzen ergänzt.', neue_platzhalter: ['Projektkontext'],
    aktion: 'Kürzen', typ_anzeige: 'Code',
    eingaben: {
      bau_version: 2, aktion: 'Kürzen', hinweise: 'Hinweise des Laufs',
      typ: { id: 'code', name: 'Code' }, modus: { id: 'vorlage' }, realismus: false,
      zielmodell: { anbieter: ziel.startsWith('qwen') ? 'lokal' : 'claude' },
      materialien: [{ art: 'text', name: 'Code.txt', wert: 'Code-Material' }],
      kontexte: [{ id: 'Code-Kontext', stand: 'kontext1' }],
    }, testprofil_id: 'test',
  };
  u.belege.set(b.datei, b);
  return b;
}

async function menueUndSenden() {
  const u = await starten();
  assert.deepEqual(u.auswahl(), ['sol']);
  assert.equal(u.$('#p-schreibmenue').className, 'p-auswahl');
  const nichtVerfuegbar = u.$('#p-schreibmodelle').querySelector('input[value="aus"]');
  assert(nichtVerfuegbar.disabled);
  assert(nichtVerfuegbar.parentElement.textContent.includes('Modell ist nicht geladen.'));
  await u.waehlen('sol', false);
  assert.deepEqual(u.auswahl(), ['sol'], 'Das letzte Schreibmodell bleibt gewählt');
  await u.waehlen('drei', true);
  await u.waehlen('opus', true);
  assert.deepEqual(u.auswahl(), ['sol', 'opus', 'drei'], 'Die Anzeigereihenfolge bestimmt die Sendereihenfolge');
  const vier = u.$('#p-schreibmodelle').querySelector('input[value="vier"]');
  assert(vier.disabled); assert.equal(vier.getAttribute('title'), 'Höchstens drei Schreibmodelle');
  assert.equal(u.$('#p-schreibmodelle').querySelector('input[value="opus"]').getAttribute('aria-label'), 'Claude · Opus · hoch');
  assert.equal(u.$('#p-composer-status').textContent, '1 Zielmodell × 3 Schreibmodelle · 3 Schärfen-Läufe');
  assert.equal(u.$('#p-schreibhinweis').textContent, 'Jedes gewählte Modell schreibt eine eigene Fassung.');
  assert(u.$('#p-schreibname').textContent.startsWith('Schreibmodelle: Codex · Sol · sehr hoch · Abo + Claude · Opus · hoch · Abo'));
  u.$('#p-schreibmenue').open = true;
  await u.document.ausloesen('keydown', { key: 'Escape' });
  assert(!u.$('#p-schreibmenue').open);
  assert.strictEqual(u.document.activeElement, u.$('#p-schreibname'));
  u.run("P.entwurf.text='Aufgabe [A]'; P.entwurf.materialien=[{art:'text',name:'Text.txt',wert:'Material'}]; pComposerZusammenfassung()");
  assert.equal(u.$('#p-material-hinweis').textContent,
    'Ausgewähltes Material und Kontext werden an Codex · Sol · sehr hoch und Claude · Opus · hoch mitgesendet.');
  await u.run('pComposerVorschau()');
  assert(u.$('#p-vorschauinhalt').textContent.includes('Geht an: Codex · Sol · sehr hoch, Claude · Opus · hoch, Drittes Modell'));
  const roh = u.$('#p-rohprompt');
  await roh.ausloesen('keydown', { key: 'Enter', ctrlKey: true });
  const daten = u.anfragen.find(([, d]) => d?.aktion === 'composer_senden')[1];
  assert.deepEqual(daten.schreibmodelle, ['sol', 'opus', 'drei']);
  assert(!('schreibmodell' in daten));
  assert.deepEqual(JSON.parse(u.ablage.get('werkstatt.prompt-schreibmodelle')), ['sol', 'opus', 'drei']);
  keinFremdText(u.document);
}

async function merkenUndNeuladen() {
  const ablage = new Map([['werkstatt.prompt-schreibmodelle', '["aus","opus","weg","sol"]']]);
  const u = await starten(ablage);
  assert.deepEqual(u.auswahl(), ['sol', 'opus']);
  u.optionen.schreibmodelle.find((p) => p.id === 'opus').prompts_verfuegbar = false;
  u.optionen.schreibmodelle.find((p) => p.id === 'opus').prompts_grund = 'Testweise nicht verfügbar';
  await u.run('pOptionenLaden(true)');
  assert.deepEqual(u.auswahl(), ['sol', 'opus']);
  assert(u.$('#p-senden').disabled);
  assert.equal(u.$('#p-composer-status').textContent, 'Claude · Opus · hoch ist gerade nicht verfügbar.');
  const cb = u.$('#p-schreibmodelle').querySelector('input[value="opus"]');
  assert(cb.checked); assert(!cb.disabled); assert(cb.parentElement.textContent.includes('Testweise nicht verfügbar'));
  assert(u.$('#p-schreibgruende').children.some((el) => el.tag === 'p' && el.textContent.includes('Claude · Opus')));
  u.run("P.entwurf.text='Kein Senden'");
  await u.run('pComposerSenden()');
  assert(!u.anfragen.some(([, d]) => d?.aktion === 'composer_senden'));
  await u.waehlen('opus', false);
  assert.deepEqual(u.auswahl(), ['sol']); assert(!u.$('#p-senden').disabled);
  assert.equal(u.$('#p-schreibhinweis').textContent, 'Dieses Modell überarbeitet deinen Prompt.');
  u.optionen.schreibmodelle = u.optionen.schreibmodelle.filter((p) => p.id !== 'sol');
  await u.run('pOptionenLaden(true)');
  assert.deepEqual(u.auswahl(), []); assert(u.$('#p-senden').disabled);
  assert.equal(u.$('#p-composer-status').textContent, 'Bitte ein Schreibmodell wählen.');
  const alt = await starten(new Map([['werkstatt.prompt-schreibmodell', 'opus']]));
  assert.deepEqual(alt.auswahl(), ['opus']);
  const rueckfall = await starten(new Map([['werkstatt.prompt-schreibmodelle', '["aus","weg"]']]));
  assert.deepEqual(rueckfall.auswahl(), ['sol']);
  const neu = await starten(new Map([['werkstatt.prompt-schreibmodell', 'opus'], ['werkstatt.prompt-schreibmodelle', '["drei"]']]));
  assert.deepEqual(neu.auswahl(), ['drei']);
  const gesperrt = await starten(new Map(), true);
  assert.deepEqual(gesperrt.auswahl(), ['sol']);
  await gesperrt.waehlen('opus', true);
  assert.deepEqual(gesperrt.auswahl(), ['sol', 'opus']);
}

async function gruppenUndAktionen() {
  const u = await starten(new Map([['werkstatt.prompt-schreibmodelle', '["opus","sol","weg"]']]));
  const bs = [ergebnis(u, 0), ergebnis(u, 1), ergebnis(u, 2, 'claude:opus'), ergebnis(u, 3, 'claude:opus')];
  const alt = ergebnis(u, 8, 'codex:sol');
  delete alt.lauf_nr;
  const gruppe = { id: 'gruppe', ergebnisse: [alt, bs[3], bs[1], bs[2], bs[0]] };
  u.ctx.e = u.eintrag; u.ctx.gruppe = gruppe; u.ctx.box = new u.Element('section');
  await u.run('pGruppeZeichnen(box,e,gruppe)');
  const box = u.ctx.box;
  assert.deepEqual(box.children.filter((el) => el.tag === 'section').map((el) => el.children[0].textContent),
    ['Qwen 27B', 'Claude', 'Claude']);
  const spalten = box.querySelectorAll('.p-ergebnisspalten');
  assert.equal(spalten.length, 2);
  for (const grid of spalten) {
    assert.deepEqual(grid.children.map((el) => el.querySelector('h5').textContent), ['Codex · Sol · sehr hoch', 'Claude · Opus · hoch']);
    assert.equal(grid.children.filter((el) => u.knopf('Als bevorzugt', el)).length, 2);
    assert.equal(grid.children.filter((el) => u.knopf('Im Composer verfeinern', el)).length, 2);
    assert(grid.textContent.includes('42 Token'));
  }
  assert.equal(box.querySelectorAll('summary').filter((el) => el.textContent === 'Original anzeigen').length, 2);
  assert.equal(box.querySelectorAll('pre').filter((el) => el.textContent === 'Original [A]').length, 3);
  const einzeln = box.children.filter((el) => el.tag === 'section')[2];
  assert(einzeln.querySelector('.p-vergleich'));
  assert(u.knopf('Als bevorzugt', einzeln)); assert(u.knopf('Im Composer verfeinern', einzeln));
  await u.klicken(u.knopf('Neue Fassung kopieren', spalten[0].children[0]));
  assert.deepEqual(u.kopiert, [bs[0].neue_fassung]);
  await u.klicken(u.knopf('Als bevorzugt', spalten[0].children[1]));
  assert.deepEqual(u.anfragen.find(([, d]) => d?.aktion === 'bevorzugt')[1],
    { aktion: 'bevorzugt', id: 'Eintrag', name: 'Ergebnis 1', kopf_stand: 'kopf1' });
  u.ctx.beleg = bs[1];
  u.run('box.replaceChildren(); pSchaerfenErgebnis(box,beleg,e,beleg)');
  assert(!u.knopf('Als bevorzugt', box)); assert(box.textContent.includes('Bevorzugt'));
  // Ein vollständiger Bild-Entwurf darf keine Angaben in das Code-Ergebnis tragen.
  u.run("pTypWaehlen('bild'); P.entwurf.realismus=true; P.entwurf.hinweise='Bildhinweis'; P.entwurf.materialien=[{name:'Bildmaterial'}]; P.entwurf.kontexte=[{id:'Bildkontext'}]");
  const bevorzugt = u.eintrag.bevorzugt;
  await u.klicken(u.knopf('Im Composer verfeinern', box));
  const entwurf = kopie(u.run('P.entwurf'));
  assert.equal(entwurf.prompt_typ, 'code'); assert.equal(entwurf.modus, 'vorlage'); assert.equal(entwurf.realismus, false);
  assert.deepEqual(entwurf.ziele, [{ zielprofil: 'qwen27', eintrag: 'qwen27-unsloth', testprofil: 'test' }]);
  assert.deepEqual(entwurf.materialien, bs[1].eingaben.materialien);
  assert.deepEqual(entwurf.kontexte, [{ id: 'Code-Kontext', stand: 'kontext1' }]);
  assert.deepEqual(entwurf.basis, { id: 'Eintrag', fassung: 'Ergebnis 1', stand: 'aktuell-1' });
  assert.deepEqual(entwurf.schreibmodelle, ['sol', 'opus']); assert.equal(entwurf.hinweise, '');
  assert.equal(entwurf.text, 'Aktuelle Fassung 1 [A]'); assert.equal(entwurf.titel, 'Code-Ergebnis');
  assert.equal(entwurf.ablage, 'ordner'); assert.equal(entwurf.schaerfen_aktion, 'Schärfen');
  assert(u.$('#p-rohprompt').readOnly); assert(u.$('.p-weitere').open);
  assert.equal(u.$('#p-typname').textContent, 'Prompt-Typ: Code');
  assert(u.$('#p-composer').querySelector('input[name="p-modus"][value="vorlage"]').checked);
  assert.strictEqual(u.document.activeElement, u.$('#p-composer-hinweise'));
  assert.equal(u.eintrag.bevorzugt, bevorzugt);
  assert(!JSON.stringify(entwurf).includes('Bild'));
  keinFremdText(box); keinFremdText(u.document);
}

async function offenBleibtOffenUndAktuelleFassung() {
  const u = await starten();
  const a = ergebnis(u, 0), b = ergebnis(u, 1);
  u.eintrag.schaerfen = [a, b];
  u.eintrag.auftragsgruppen = [{ id: 'gruppe', ergebnisse: [b, a] }];
  await u.run("pWaehlen('Eintrag')");
  const schluessel = JSON.stringify(['gruppe', 'gruppe', a.zielschluessel, 'original']);
  const details = (key) => u.$('#p-inhalt').querySelectorAll('details[data-p-ansicht]').find((d) => d.getAttribute('data-p-ansicht') === key);
  details(schluessel).open = true;
  details('["Lauf0.md","aenderungen"]').open = true;
  b.zustand = 'laeuft'; b.antwort_vorhanden = false;
  u.document.activeElement = null;
  await u.run("pWaehlen('Eintrag',false)");
  assert(details(schluessel).open);
  assert(details('["Lauf0.md","aenderungen"]').open);
  // Die Liste Schärfen verwendet dieselben Aktionen wie die Gruppe.
  const liste = details('["Lauf0.md","schaerfen"]');
  liste.open = true; await liste.ausloesen('toggle');
  assert(u.knopf('Als bevorzugt', liste)); assert(u.knopf('Im Composer verfeinern', liste));
  a.ergebnis_geaendert = true;
  const f = u.eintrag.fassungen.find((f) => f.name === a.ergebnis_fassung);
  f.stand = 'bearbeitet'; f.text = 'Bearbeiteter Text [A]';
  u.ctx.box = new u.Element('section'); u.ctx.e = u.eintrag; u.ctx.a = a;
  u.run('pSchaerfenErgebnis(box,a,e,a)');
  assert(u.ctx.box.textContent.includes('Die übernommene Fassung „Ergebnis 0“ wurde seitdem bearbeitet. Die Knöpfe verwenden ihren aktuellen Stand.'));
  await u.klicken(u.knopf('Im Composer verfeinern', u.ctx.box));
  assert.equal(u.run('P.entwurf.basis.stand'), 'bearbeitet'); assert.equal(u.run('P.entwurf.text'), f.text);
  u.eintrag.fassungen = u.eintrag.fassungen.filter((f) => f.name !== a.ergebnis_fassung);
  a.ergebnis_fehlt = true;
  u.run('pSchaerfenErgebnis(box,a,e,a)');
  assert(!u.knopf('Im Composer verfeinern', u.ctx.box)); assert(!u.knopf('Als bevorzugt', u.ctx.box));
}

async function neuereAuswahlWaehrendGruppenabruf() {
  const u = await starten();
  const a = ergebnis(u, 0), b = ergebnis(u, 1);
  u.eintrag.schaerfen = [a, b];
  u.eintrag.auftragsgruppen = [{ id: 'gruppe', ergebnisse: [a, b] }];
  await u.run("pWaehlen('Eintrag')");
  const box = u.$('#p-inhalt');
  box.scrollTop = 120; box.scrollLeft = 12;
  u.ctx.window.scrollX = 20; u.ctx.window.scrollY = 240;
  a.tokens = 99;
  let freigeben;
  u.server.belegWarten = new Promise((resolve) => { freigeben = resolve; });
  const anfragenVorher = u.anfragen.length;
  const alterAbruf = u.run("pWaehlen('Eintrag',false)");
  await new Promise(setImmediate);
  assert(u.anfragen.slice(anfragenVorher).some(([pfad]) => pfad.startsWith('/api/prompt-datei?')),
    'Der alte Gruppenabruf muss bereits auf den Beleg warten');
  u.eintraege.set('Neu', { ...kopie(u.eintrag), id: 'Neu', titel: 'Neuer Eintrag', schaerfen: [], auftragsgruppen: [] });
  await u.run("pWaehlen('Neu')");
  assert.equal(u.run('P.inhaltId'), 'Neu');
  const neuerStand = u.run('P.inhaltStand');
  box.scrollTop = 360; box.scrollLeft = 36;
  u.ctx.window.scrollX = 40; u.ctx.window.scrollY = 720;
  freigeben(); await alterAbruf;
  assert.equal(u.run('P.inhaltId'), 'Neu');
  assert.equal(u.run('P.gewaehlt'), 'Neu');
  assert.equal(u.run('P.inhaltStand'), neuerStand);
  assert.equal(box.scrollTop, 360); assert.equal(box.scrollLeft, 36);
  assert.equal(u.ctx.window.scrollX, 40); assert.equal(u.ctx.window.scrollY, 720);
  assert.equal(box.querySelector('h2').textContent, 'Neuer Eintrag');
}

async function nochmalUndErgebniszustaende() {
  const u = await starten();
  const b = ergebnis(u, 0);
  u.ctx.e = u.eintrag; u.ctx.b = b;
  b.schreibmodell_id = 'gelöscht';
  await u.run('pComposerNochmal(e,b)');
  assert.deepEqual(u.auswahl(), ['sol']); assert.equal(u.run('P.entwurf.schaerfen_aktion'), 'Kürzen');
  assert.equal(u.run('P.entwurf.hinweise'), 'Hinweise des Laufs');
  b.denkstufe = 'andere';
  await u.run('pComposerNochmal(e,b)');
  assert.deepEqual(u.auswahl(), []); assert(u.$('#p-senden').disabled);
  assert.equal(u.$('#p-composer-status').textContent, 'Das Schreibmodell dieses Laufs gibt es nicht mehr. Bitte neu wählen.');
  assert(!u.run('JSON.stringify(pComposerDaten())').includes('gelöscht'));
  const ohneStufe = u.optionen.schreibmodelle.find((p) => p.id === 'drei');
  Object.assign(b, { auswerter: ohneStufe.name, anbieter: ohneStufe.anbieter, modell: ohneStufe.modell, denkstufe: null });
  await u.run('pComposerNochmal(e,b)');
  assert.deepEqual(u.auswahl(), ['drei'], 'Eine fehlende und eine leere Denkstufe entsprechen sich wie auf dem Server');
  b.schreibmodell_id = 'opus';
  await u.run('pComposerNochmal(e,b)'); assert.deepEqual(u.auswahl(), ['opus'], 'Vorhandene Profil-ID hat Vorrang');
  delete b.zielschluessel;
  await u.run('pComposerNochmal(e,b)');
  assert(u.dialog.open); assert.equal(u.dialog.titel, 'Schärfen: Code-Ergebnis');
  u.dialog.close();
  u.ctx.box = new u.Element('section');
  b.aktion = 'Erst klären'; b.fragen = '1. Welche Grenzen gelten?'; delete b.ergebnis_fassung;
  u.run('pSchaerfenErgebnis(box,b,e,b,true)');
  assert(u.ctx.box.textContent.includes(b.fragen)); assert(!u.knopf('Neue Fassung kopieren', u.ctx.box));
  b.aktion = 'Schärfen'; b.grund = 'kein Kasten'; b.antwort = 'Ungültige Rohantwort';
  b.eingaben.typ.id = 'auto'; b.typ_anzeige = 'Code';
  u.run('pSchaerfenErgebnis(box,b,e,b,true)');
  assert(u.ctx.box.textContent.includes('Ungültige Rohantwort')); assert(u.ctx.box.textContent.includes('Prompt-Typ: Code'));
  assert(u.ctx.box.textContent.includes('Neue Platzhalter: [Projektkontext]'));
  assert(!u.knopf('Testen …', u.ctx.box));
  assert(!u.knopf('Neue Fassung kopieren', u.ctx.box));
}

async function ablehnungUndAntwortverlust() {
  for (const status of [409, 500]) {
    const u = await starten();
    u.run("P.entwurf.text='Erhaltener Rohprompt'; P.entwurf.hinweise='Erhaltene Hinweise'");
    const entwurf = u.run('JSON.stringify(P.entwurf)');
    // Zuerst ein Antwortverlust, dann eine vom Server beantwortete Fortsetzung.
    u.server.verloren = true;
    await u.run('pComposerSenden()');
    assert(u.knopf('Status prüfen')); assert(!u.knopf('Als neue Sendung senden'));
    const ersteId = u.run('P.sendung.daten.anfrage_id');
    u.server.verloren = false;
    await u.klicken(u.knopf('Status prüfen'));
    assert(u.knopf('Einreihung fortsetzen')); assert(!u.knopf('Als neue Sendung senden'));
    u.server.fehler = status;
    await u.klicken(u.knopf('Einreihung fortsetzen'));
    assert(u.knopf('Als neue Sendung senden')); assert(u.knopf('Einreihung fortsetzen'));
    assert(u.$('#p-sendungsaktionen').textContent.includes('Bereits angelegte Läufe der alten Sendung stehen unter ‚Schärfen‘ des Eintrags.'));
    assert.equal(u.run('JSON.stringify(P.entwurf)'), entwurf);
    await u.klicken(u.knopf('Als neue Sendung senden'));
    const posts = u.anfragen.filter(([, d]) => d?.aktion === 'composer_senden').map(([, d]) => d);
    assert.equal(posts[0].anfrage_id, posts[1].anfrage_id);
    assert.notEqual(posts[2].anfrage_id, ersteId);
    const ohneKennung = ({ anfrage_id, ...rest }) => rest;
    assert.deepEqual(ohneKennung(posts[0]), ohneKennung(posts[2]));
    assert.equal(u.run('JSON.stringify(P.entwurf)'), entwurf);
    assert(u.knopf('Als neue Sendung senden'), 'Auch die Ablehnung des ersten Sendens bietet den Neustart');
    // Ein zweiter Knopf darf eine gerade laufende Fortsetzung nicht verwerfen.
    let freigeben;
    u.server.warten = new Promise((resolve) => { freigeben = resolve; });
    const fortsetzung = u.klicken(u.knopf('Einreihung fortsetzen'));
    await new Promise(setImmediate);
    const laufendeId = u.run('P.sendung.daten.anfrage_id');
    await u.klicken(u.knopf('Als neue Sendung senden'));
    assert.equal(u.run('P.sendung.daten.anfrage_id'), laufendeId);
    freigeben(); await fortsetzung;
    u.server.warten = null; u.server.fehler = null; u.server.verloren = true;
    await u.klicken(u.knopf('Einreihung fortsetzen'));
    assert(u.knopf('Status prüfen')); assert(!u.knopf('Als neue Sendung senden'));
    u.server.verloren = false;
    await u.klicken(u.knopf('Status prüfen'));
    assert(u.knopf('Einreihung fortsetzen')); assert(!u.knopf('Als neue Sendung senden'));
  }
}

(async () => {
  await menueUndSenden();
  await merkenUndNeuladen();
  await gruppenUndAktionen();
  await offenBleibtOffenUndAktuelleFassung();
  await neuereAuswahlWaehrendGruppenabruf();
  await nochmalUndErgebniszustaende();
  await ablehnungUndAntwortverlust();
  assert.equal((code.match(/setTimeout\(/g) || []).length, 1);
  assert(!code.includes('setInterval('));
  console.log('Mehrfachauswahl, Laufreihenfolge, Ergebnisaktionen, Verfeinern, Altbelege und Sendungswiederaufnahme OK');
})().catch((err) => { console.error(err); process.exitCode = 1; });
