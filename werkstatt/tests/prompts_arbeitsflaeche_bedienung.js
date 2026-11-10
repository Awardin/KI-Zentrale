'use strict';

const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
const code = fs.readFileSync('werkstatt/web/prompts.js', 'utf8');
const css = fs.readFileSync('werkstatt/web/style.css', 'utf8');
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));
const kopie = (v) => JSON.parse(JSON.stringify(v));

async function starten() {
  const { dokument: document, Element } = dokumentBauen();
  const anfragen = [], belege = new Map(), storage = new Map(), kopiert = [];
  let nummer = 0;
  const e = { id: 'A', titel: 'Testprompt', herkunft: 'ordner', bearbeitbar: true, prompt_typ: 'code', modus: 'prompt',
    bevorzugt: 'Fassung 1', kopf_stand: 'kopf', fassungen: [{ name: 'Fassung 1', text: 'Original [A]', stand: 's1' }],
    auftragsgruppen: [], schaerfen: [], tests: [], warteschlange: [] };
  const eintraege = new Map([[e.id, e]]);
  const steuerung = {};
  const optionen = { ...kopie(regeln), schreibmodelle: [
    { id: 'eins', name: 'Claude · Eins', anbieter: 'claude', modell: 'eins', prompts_verfuegbar: true },
    { id: 'zwei', name: 'Codex · Zwei', anbieter: 'codex', modell: 'zwei', prompts_verfuegbar: true },
    { id: 'aus', name: 'Nicht geladen', anbieter: 'lokal', prompts_verfuegbar: false }],
    zielprofile: regeln.zielprofile.map((p) => ({ ...p, varianten: p.anbieter === 'lokal'
      ? [{ eintrag: p.eintraege[0], name: p.name, testprofile: [] }] : [{ testprofil: 'eins', name: p.name }] })) };
  const ctx = vm.createContext({ document, console, crypto: { randomUUID: () => 'uuid-' + (++nummer) },
    window: { addEventListener() {}, scrollTo() {} }, aktualisieren() {}, fehlerMelden(m) { throw Error(m); },
    localStorage: { getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v) },
    navigator: { clipboard: { writeText: async (v) => kopiert.push(v) } },
    setTimeout() { throw Error('Kein zusätzlicher Zeitgeber'); }, setInterval() { throw Error('Kein zusätzlicher Zeitgeber'); },
    dialogOeffnen(titel, inhalt, knoepfe) { const d = new Element('dialog'); d.open = true; d.append(...inhalt, ...knoepfe);
      document.append(d); d.close = () => d.remove(); return d; },
    fetch: async (pfad, opt) => {
      const d = opt?.body ? JSON.parse(opt.body) : null;
      anfragen.push([pfad, d]);
      let wert;
      if (pfad === '/api/prompt-optionen') wert = optionen;
      else if (pfad.startsWith('/api/prompt?id=')) {
        if (steuerung.laden) await steuerung.laden;
        wert = eintraege.get(decodeURIComponent(pfad.split('=')[1]));
      } else if (pfad.startsWith('/api/prompt-datei?')) {
        if (steuerung.beleg) await steuerung.beleg;
        wert = belege.get(new URLSearchParams(pfad.split('?')[1]).get('datei'));
        if (!wert) throw Error('Beleg fehlt');
      } else if (pfad === '/api/prompts') wert = { eintraege: [...eintraege.values()], fehler: [], warteschlange: [] };
      else if (d?.aktion === 'fassung_bearbeitet') {
        if (steuerung.speichern) await steuerung.speichern;
        if (steuerung.speicherfehler) return { ok: false, status: 409, json: async () => ({ fehler: 'Herkunftsdatei beschädigt' }) };
        const ziel = eintraege.get(d.id), quelle = ziel.fassungen.find((f) => f.name === d.von_fassung);
        const f = { name: 'Bearbeitet 10.11. · Test ' + (++nummer), text: d.text, stand: 's' + nummer,
          herkunft_gueltig: quelle?.stand === d.von_stand,
          herkunft: { von_fassung: d.von_fassung, von_stand: d.von_stand,
            quell_beleg: quelle?.herkunft?.quell_beleg || ziel.schaerfen.find((b) => b.ergebnis_fassung === d.von_fassung)?.datei } };
        ziel.fassungen.push(f); wert = { ...ziel, neue_fassung: f.name };
      } else if (d?.aktion === 'bevorzugt') {
        const ziel = eintraege.get(d.id); ziel.bevorzugt = d.name; wert = ziel;
      } else if (d?.aktion === 'composer_vorschau') {
        if (steuerung.vorschaufehler) return { ok: false, status: 409, json: async () => ({ fehler: 'Kontext wurde geändert' }) };
        wert = { gesendet_staende: { ziel: 'hash' } };
      } else if (d?.aktion === 'composer_senden') {
        if (steuerung.senden) await steuerung.senden;
        if (steuerung.verloren) throw Error('Failed to fetch');
        if (steuerung.sendeFehler) return { ok: false, status: 409, json: async () => ({ fehler: 'Einreihung unvollständig' }) };
        wert = sendung(d);
      } else if (d?.aktion === 'composer_status') {
        if (steuerung.statusWarten) await steuerung.statusWarten;
        wert = steuerung.status || sendung(steuerung.statusdaten);
      }
      else if (d?.aktion === 'kontext_lesen') {
        if (steuerung.kontextfehler) return { ok: false, status: 409, json: async () => ({ fehler: 'Kontext fehlt' }) };
        wert = { id: d.id, stand: 'aktuell' };
      } else if (pfad === '/api/fassung') wert = { ok: true };
      else throw Error('Unerwartete Anfrage ' + pfad + ' ' + d?.aktion);
      return { ok: true, json: async () => kopie(wert) };
    },
  });
  function sendung(d) {
    const ziel = eintraege.get(d.basis?.id || e.id), aid = d.anfrage_id;
    let g = ziel.auftragsgruppen.find((g) => g.id === aid);
    if (!g) {
      const b = { datei: aid + '.md', auftragsgruppe: aid, aktion: d.schaerfen_aktion || 'Schärfen',
        fassung: d.basis?.fassung || 'Fassung 1', fassung_stand: d.basis?.stand || 's1', zustand: 'wartet',
        zielschluessel: 'qwen27:qwen27-unsloth', zielmodell: 'Qwen', schreibmodell_id: d.schreibmodelle[0],
        auswerter: 'Claude · Eins', erstellt: '2026-11-10 10:01:00', lauf_nr: 0, eingaben: { ...d, aktion: d.schaerfen_aktion } };
      ziel.schaerfen.push(b); g = { id: aid, ergebnisse: [b] }; ziel.auftragsgruppen.push(g); belege.set(b.datei, b);
    }
    return { gefunden: true, vollstaendig: true, id: ziel.id, auftragsgruppe: aid, ziele: g.ergebnisse.map((b) => ({ beleg: b.datei })) };
  }
  vm.runInContext(app.split('let STAND =')[0], ctx);
  vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), ctx);
  vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='), app.indexOf('function schrittListe(')), ctx);
  vm.runInContext(code, ctx);
  const run = (s) => vm.runInContext(s, ctx), $ = (s) => document.querySelector(s);
  run('pComposerZeigen()'); await run('pOptionenLaden()');
  ctx.e = e;
  const af = () => $('.p-arbeitsflaeche');
  const rechts = () => $('.p-af-rechts');
  const links = () => $('.p-af-links');
  const knopf = (t, box = af()) => box.querySelectorAll('button').find((b) => b.textContent === t);
  const klick = async (b) => { assert(b, 'Knopf fehlt'); assert(!b.disabled, 'Knopf gesperrt'); b.focus(); await b.ausloesen('click'); };
  const input = async (el, text) => { assert(el); assert(!el.readOnly); el.value = text; el.focus(); await el.ausloesen('input'); };
  const zeichnen = async () => { document.activeElement = null; run('P.inhaltStand=null'); await run("pWaehlen('A', false)"); };
  const ergebnis = (nr, gid = 'runde', ziel = 'qwen27:qwen27-unsloth') => {
    const f = { name: 'Ergebnis ' + nr, text: 'Ergebnistext ' + nr + ' [A]', stand: 'r' + nr };
    e.fassungen.push(f);
    const b = { datei: 'Lauf' + nr + '.md', auftragsgruppe: gid, aktion: 'Schärfen', zustand: 'fertig', lauf_nr: nr,
      erstellt: '2026-11-10 10:00:00', fassung: 'Fassung 1', fassung_stand: 's1', ergebnis_fassung: f.name,
      schreibmodell_id: nr % 2 ? 'zwei' : 'eins', auswerter: nr % 2 ? 'Codex · Zwei' : 'Claude · Eins',
      zielschluessel: ziel, zielmodell: ziel, original: 'Original [A]', neue_fassung: f.text, stichpunkte: '- Klarer',
      grund: '', antwort: 'Antwort', testprofil_id: 'test', dauer_s: 29, tokens: 8286,
      eingaben: { typ: { id: 'code' }, modus: { id: 'vorlage' }, realismus: false, hinweise: 'Laufhinweis',
        aktion: 'Schärfen', zielmodell: { anbieter: 'lokal' }, materialien: [{ art: 'text', name: 'M', wert: 'Material' }],
        kontexte: [{ id: 'Kontext', stand: 'alt' }] } };
    e.schaerfen.push(b); belege.set(b.datei, b);
    let g = e.auftragsgruppen.find((g) => g.id === gid);
    if (!g) { g = { id: gid, ergebnisse: [] }; e.auftragsgruppen.push(g); }
    g.ergebnisse.push(b); return b;
  };
  const fragen = (f = e.fassungen[0], n = 2, datei = 'Fragen.md') => {
    const b = { datei, auftragsgruppe: datei, aktion: 'Rückfragen', zustand: 'fertig', fassung: f.name,
      fassung_stand: f.stand, erstellt: '2026-11-10 10:02:00', fragen_hash: 'hash1', fragen_anzahl: n,
      auswerter: 'Claude · Eins', schreibmodell_id: 'eins', fragen_grund: '', antwort: 'JSON',
      fragenliste: Array.from({ length: n }, (_, i) => ({ prioritaet: i ? 'hoch' : 'kritisch', frage: 'Frage ' + i + '?',
        warum: 'Ändert das Format.', vorschlaege: ['Kurz', 'Lang'] })) };
    e.schaerfen.push(b); belege.set(datei, b); return b;
  };
  return { e, eintraege, belege, ctx, document, anfragen, optionen, steuerung, kopiert, storage, run, $, af, rechts, links,
    knopf, klick, input, zeichnen, ergebnis, fragen, kopie, neuesteSendung: () => anfragen.filter(([, d]) => d?.aktion === 'composer_senden').at(-1)?.[1] };
}

async function vorgabenUndNavigation() {
  const u = await starten();
  u.ergebnis(0, 'alt'); const b = u.ergebnis(1, 'neu');
  u.e.bevorzugt = 'Ergebnis 0'; await u.zeichnen();
  assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 0 [A]');
  u.e.fassungen.push({ name: 'Bearbeitet', text: 'Handfassung', stand: 'hand' });
  u.e.bevorzugt = 'Bearbeitet'; u.run('delete P.af.A'); await u.zeichnen();
  assert.equal(u.$('.p-af-editor').value, 'Handfassung');
  u.run("Object.assign(pAfZustand(e),{bewusst:false,fest:false,eigeneRunde:'neu'})"); await u.zeichnen();
  assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 1 [A]');
  b.zustand = 'laeuft'; u.ergebnis(2, 'spaeter'); await u.zeichnen();
  assert.equal(u.run('P.af.A.runde'), 'neu', 'Ein fertiger Text hält die Vorgabe fest');
  await u.klick(u.knopf('Versionen', u.links()));
  const zeile = u.links().querySelectorAll('div').find((d) => d.textContent.startsWith('Fassung 1'));
  await u.klick(u.knopf('Anzeigen', zeile));
  assert.equal(u.$('.p-af-editor').value, 'Original [A]');
  b.zustand = 'fertig'; await u.zeichnen(); assert.equal(u.run('P.af.A.fassung'), 'Fassung 1');
  assert(u.$('.p-af-dein').textContent.includes('Dein Prompt'));
  keinFremdText(u.document);
}

async function ersterErfolgReiterUndZiele() {
  const u = await starten();
  const a = u.ergebnis(0); const b = u.ergebnis(1); u.ergebnis(2, 'runde', 'claude');
  a.ergebnis_fassung = null; a.zustand = 'fehler'; a.meldung = 'A scheitert';
  await u.zeichnen(); assert.equal(u.run('P.af.A.lauf'), b.datei);
  const tabs = u.rechts().querySelectorAll('[role="tab"]');
  assert.equal(tabs.length, 2); assert.equal(tabs[1].getAttribute('aria-selected'), 'true');
  await u.klick(tabs[0]); assert(u.rechts().textContent.includes('A scheitert'));
  await u.klick(u.knopf('claude', u.rechts())); assert.equal(u.run('P.af.A.ziel'), 'claude');
  await u.klick(u.knopf('Nebeneinander vergleichen')); assert(u.$('.p-ergebnisgruppe'));
}

async function alleLaufzustaendeUndNeuSenden() {
  const u = await starten(); const b = u.ergebnis(0); b.ergebnis_fassung = null;
  b.eingaben.rueckfragen = [{ prioritaet: 'hoch', frage: 'Format?', antwort: 'Kurz' }];
  for (const zustand of ['wartet', 'laeuft', 'fehler', 'abgebrochen', 'fertig']) {
    b.zustand = zustand; await u.zeichnen();
    if (['wartet', 'laeuft'].includes(zustand)) {
      assert(u.rechts().textContent.includes('Verbessert wird: Fassung 1'));
      assert(!u.$('.p-af-editor')); assert(u.knopf('Abbrechen'));
    } else { assert(u.knopf('Neu senden')); assert(u.knopf('Basis anzeigen')); }
  }
  await u.klick(u.knopf('Neu senden'));
  const d = u.neuesteSendung(); assert.equal(d.schaerfen_aktion, 'Schärfen');
  assert.equal(d.hinweise, 'Laufhinweis'); assert.deepEqual(d.rueckfragen, b.eingaben.rueckfragen);
  assert.deepEqual(d.schreibmodelle, ['eins']); assert.notEqual(d.anfrage_id, b.auftragsgruppe);
  assert.equal(d.kontexte[0].stand, 'aktuell');
  b.fassung = 'Fehlt'; u.run("Object.assign(pAfZustand(e),{runde:'runde',lauf:'Lauf0.md',bewusst:true})");
  await u.zeichnen(); assert(!u.knopf('Neu senden')); assert(u.rechts().textContent.includes('Versionen'));
}

async function entwurfUeberlebtUndKonflikt() {
  const u = await starten(); u.ergebnis(0); u.ergebnis(1); await u.zeichnen();
  await u.input(u.$('.p-af-editor'), 'Mein Entwurf');
  await u.zeichnen(); assert.equal(u.$('.p-af-editor').value, 'Mein Entwurf');
  await u.klick(u.rechts().querySelectorAll('[role="tab"]')[1]);
  await u.klick(u.rechts().querySelectorAll('[role="tab"]')[0]);
  assert.equal(u.$('.p-af-editor').value, 'Mein Entwurf');
  const f = u.e.fassungen[1]; f.text = 'Fremd'; f.stand = 'fremd'; await u.zeichnen();
  assert(u.rechts().textContent.includes('Diese Fassung wurde inzwischen geändert. Dein Entwurf ist erhalten.'));
  await u.klick(u.knopf('Aktuelle Fassung zeigen')); assert.equal(u.$('.p-af-editor').value, 'Fremd');
  assert(u.run("P.afEntwurf.has('A|Ergebnis 0')"));
  await u.klick(u.knopf('Entwurf als neue Fassung speichern'));
  const d = u.anfragen.find(([, d]) => d?.aktion === 'fassung_bearbeitet')[1];
  assert.equal(d.von_stand, 'r0'); assert.equal(d.text, 'Mein Entwurf');
  assert.equal(u.$('.p-af-editor').value, 'Mein Entwurf');
}

async function speichernVorFragenUndNavigation() {
  const u = await starten(); u.ergebnis(0); u.ergebnis(1); await u.zeichnen();
  u.run("P.entwurf.text='Composer bleibt'; P.entwurf.hinweise='Eigen';"); const composer = u.run('JSON.stringify(P.entwurf)');
  await u.input(u.$('.p-af-editor'), 'Sichtbar geändert [A]');
  let fertig; u.steuerung.speichern = new Promise((r) => { fertig = r; });
  const senden = u.klick(u.knopf('Prompt verbessern')); await new Promise(setImmediate);
  assert(u.$('.p-af-editor').readOnly); assert(u.rechts().textContent.includes('Wird gespeichert …'));
  await u.klick(u.rechts().querySelectorAll('[role="tab"]')[1]);
  fertig(); await senden; u.steuerung.speichern = null;
  const daten = u.neuesteSendung();
  assert.equal(daten.text, 'Sichtbar geändert [A]'); assert(daten.basis.fassung.startsWith('Bearbeitet'));
  assert.equal(daten.schaerfen_aktion, 'Rückfragen'); assert.deepEqual(daten.schreibmodelle, ['eins']);
  assert.equal(daten.prompt_typ, 'code'); assert.equal(daten.modus, 'vorlage'); assert.equal(daten.materialien[0].wert, 'Material');
  assert.equal(daten.kontexte[0].stand, 'aktuell');
  assert.equal(u.run('P.af.A.lauf'), 'Lauf1.md'); assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 1 [A]');
  assert.equal(u.run('JSON.stringify(P.entwurf)'), composer);
  assert(u.run('P.af.A.fragen')); assert.equal(u.run('P.af.A.eigeneRunde'), null);
}

async function fragenAntwortenUndBearbeitetKette() {
  const u = await starten(); u.ergebnis(0); const q = u.fragen(u.e.fassungen[1]); await u.zeichnen();
  await u.klick(u.knopf('Kurz', u.links()));
  assert.equal(u.$('.p-af-antwort').value, 'Kurz');
  await u.klick(u.knopf('Lang', u.links())); assert.equal(u.$('.p-af-antwort').value, 'Kurz; Lang');
  assert(u.links().textContent.includes('(1/2)'));
  await u.klick(u.knopf('Überspringen', u.links())); assert(u.links().textContent.includes('(0/2)'));
  await u.klick(u.knopf('Doch beantworten', u.links()));
  await u.input(u.links().querySelector('[aria-label="Weitere Wünsche (optional)"]'), 'Wünsche');
  await u.input(u.$('.p-af-editor'), 'Erste Änderung [A]');
  await u.klick(u.knopf('Als bevorzugt', u.rechts()));
  assert(u.links().textContent.includes('du hast den Text danach bearbeitet'));
  await u.input(u.$('.p-af-editor'), 'Zweite Änderung [A]');
  await u.klick(u.knopf('Mit Antworten verbessern', u.links()));
  const d = u.neuesteSendung(); assert.equal(d.text, 'Zweite Änderung [A]');
  assert.equal(d.hinweise, 'Wünsche');
  assert.deepEqual(d.rueckfragen, [{ prioritaet: q.fragenliste[0].prioritaet, frage: q.fragenliste[0].frage, antwort: 'Kurz; Lang' }]);
  assert(u.run('P.af.A.eigeneRunde')); assert(u.rechts().textContent.includes('Verbessert wird: Bearbeitet'));
}

async function neueFragenUndBewussterBeleg() {
  const u = await starten(); const q = u.fragen(); await u.zeichnen();
  await u.input(u.$('.p-af-antwort'), 'Bleibt'); await u.zeichnen(); assert.equal(u.$('.p-af-antwort').value, 'Bleibt');
  q.fragen_hash = 'hash2'; q.fragenliste[0].frage = 'Neue Frage'; await u.zeichnen();
  assert.equal(u.$('.p-af-antwort').value, '');
  const zweite = u.fragen(u.e.fassungen[0], 1, 'Spaeter.md'); zweite.erstellt = '2026-11-10 11:00:00';
  await u.zeichnen(); assert.equal(u.$('.p-af-antwort').getAttribute('aria-label'), zweite.fragenliste[0].frage);
  u.ctx.q = q; await u.run('pAfFragenOeffnen(e,q)'); assert.equal(u.run('P.af.A.fragen'), 'Fragen.md');
  assert.equal(u.$('.p-af-antwort').getAttribute('aria-label'), 'Neue Frage');
  const box = new (u.document.constructor)('section'); u.ctx.box = box;
  u.run('pSchaerfenErgebnis(box,q,e,q)'); assert(box.textContent.includes('In der Arbeitsfläche öffnen'));
  assert(!box.textContent.includes('Keine gültige neue Fassung')); assert(!u.knopf('Testen …', box));
}

async function fragenZustaende() {
  const u = await starten(); const q = u.fragen();
  const begonnen = new Date(2026, 10, 10, 15, 37).getTime() / 1000;
  u.e.warteschlange.push({ art: 'schaerfen', begonnen, prompt: { eintrag: u.e.id, beleg: 'Fragen' } });
  for (const zustand of ['wartet', 'laeuft', 'fertig', 'fehler', 'abgebrochen']) {
    q.zustand = zustand; await u.zeichnen();
    if (['wartet', 'laeuft'].includes(zustand)) {
      assert.equal(u.links().querySelector('[role="status"]').textContent, zustand === 'wartet'
        ? 'Wartet auf den Start …' : 'Läuft seit 15:37 – Fragen werden gestellt …');
      assert(u.knopf('Prompt verbessern').disabled);
    } else if (zustand === 'fertig') assert(u.knopf('Mit Antworten verbessern'));
    else assert(u.knopf('Nochmal fragen'));
  }
  q.zustand = 'fertig'; q.fragenliste = []; q.fragen_anzahl = 0; q.fragen_hash = 'leer'; await u.zeichnen();
  assert(u.links().textContent.includes('Keine Rückfragen nötig')); assert(u.knopf('Jetzt verbessern'));
  q.fragen_grund = 'Fragen nicht lesbar'; await u.zeichnen(); assert(u.links().textContent.includes('Die Fragen ließen sich nicht lesen.'));
  q.fragen_grund = ''; q.fassung_stand = 'anders'; await u.zeichnen();
  assert(u.links().textContent.includes('Die Fassung wurde seit den Fragen geändert.'));
}

async function composerAntwortenUndBasiswechsel() {
  const u = await starten(); const b = u.ergebnis(0); const q = u.fragen(u.e.fassungen[1], 5); await u.zeichnen();
  for (const feld of u.links().querySelectorAll('.p-af-antwort')) await u.input(feld, 'x'.repeat(600));
  await u.input(u.links().querySelector('[aria-label="Weitere Wünsche (optional)"]'), 'w'.repeat(2000));
  u.steuerung.kontextfehler = true; await u.klick(u.knopf('Mit Antworten verbessern'));
  assert(u.knopf('Im Composer öffnen')); await u.klick(u.knopf('Im Composer öffnen'));
  assert.equal(u.run('P.entwurf.hinweise.length'), 2000); assert.equal(u.run('P.entwurf.rueckfragen.length'), 5);
  assert(u.$('#p-composer-antworten').textContent.includes('Antworten auf Rückfragen (5)'));
  b.eingaben.rueckfragen = [{ prioritaet: 'hoch', frage: 'Wieder?', antwort: 'Ja' }]; u.ctx.b = b;
  await u.run('pComposerNochmal(e,b)'); assert.deepEqual(kopie(u.run('pComposerDaten().rueckfragen')), b.eingaben.rueckfragen);
  u.ctx.eB = { ...kopie(u.e), id: 'B' }; u.eintraege.set('B', u.ctx.eB);
  await u.run('pComposerBasis(eB)'); assert.equal(u.run('pComposerDaten().rueckfragen'), undefined);
  u.steuerung.kontextfehler = false;
  await u.run('pComposerSenden()');
  assert.equal(u.neuesteSendung().basis.id, 'B'); assert(!('rueckfragen' in u.neuesteSendung()));
  u.run("P.entwurf.rueckfragen=[{frage:'F',antwort:'A',prioritaet:'hoch'}];pComposerBasisSetzen({...P.entwurf.basis,stand:'anderer'});");
  assert.equal(u.run('P.entwurf.rueckfragen'), undefined);
  u.run("P.entwurf.rueckfragen=[{frage:'F',antwort:'A',prioritaet:'hoch'}];pComposerAktionSetzen('Kürzen')");
  assert.equal(u.run('P.entwurf.rueckfragen'), undefined);
  u.run("P.entwurf.rueckfragen=[{frage:'F',antwort:'A',prioritaet:'hoch'}];pComposerBasisSetzen(null)");
  assert.equal(u.run('P.entwurf.rueckfragen'), undefined);
  await u.run('pComposerVerfeinern(e,b)'); assert.equal(u.run('P.entwurf.rueckfragen'), undefined);
}

async function sendebestaetigungNavigationUndVerlust() {
  const u = await starten(); u.ergebnis(0); u.ergebnis(1); await u.zeichnen();
  let fertig; u.steuerung.senden = new Promise((r) => { fertig = r; });
  const sendung = u.klick(u.knopf('Direkt verbessern')); await new Promise(setImmediate);
  await u.klick(u.rechts().querySelectorAll('[role="tab"]')[1]);
  fertig(); await sendung; u.steuerung.senden = null;
  assert.equal(u.run('P.af.A.lauf'), 'Lauf1.md'); assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 1 [A]');
  assert.equal(u.af().scrollIntoViewOptions, undefined, 'Der bewusste Ansichtswechsel bekommt keinen nachträglichen Scrollsprung');
  assert(u.run('P.af.A.eigeneRunde'));
  u.steuerung.verloren = true; await u.klick(u.knopf('Direkt verbessern'));
  assert(u.knopf('Status prüfen')); assert(u.run('P.afSendung.unklar'));
  u.steuerung.statusdaten = u.neuesteSendung(); u.steuerung.verloren = false;
  await u.klick(u.knopf('Status prüfen')); assert.equal(u.run('P.afSendung'), null);
}

async function fehlerEntwurfUndComposerUnabhaengig() {
  const u = await starten(); u.ergebnis(0); await u.zeichnen();
  await u.input(u.$('.p-af-editor'), 'Bleibt bei Fehler'); u.steuerung.speicherfehler = true;
  await u.klick(u.knopf('Prompt verbessern')); assert(u.run("P.afEntwurf.has('A|Ergebnis 0')"));
  assert.equal(u.neuesteSendung(), undefined); assert(u.rechts().textContent.includes('Herkunftsdatei beschädigt'));
  u.steuerung.speicherfehler = false; await u.klick(u.knopf('Verwerfen'));
  u.run("P.sendung={daten:{text:'Composer separat'},unklar:true};P.sendenLaeuft=true");
  await u.klick(u.knopf('Prompt verbessern')); assert.equal(u.neuesteSendung().schaerfen_aktion, 'Rückfragen');
  assert.equal(u.run('P.sendung.daten.text'), 'Composer separat');
}

async function fehlendesZielUndModelle() {
  const u = await starten(); await u.zeichnen();
  await u.klick(u.knopf('Prompt verbessern')); assert(u.knopf('Im Composer öffnen'));
  await u.klick(u.knopf('Im Composer öffnen')); assert.equal(u.run('P.entwurf.basis.id'), 'A');
  u.optionen.schreibmodelle.forEach((p) => { p.prompts_verfuegbar = false; }); await u.run('pOptionenLaden(true)');
  await u.zeichnen(); assert(u.rechts().textContent.includes('Kein Schreibmodell verfügbar'));
  const gewahlt = u.rechts().querySelector('input[aria-label="Claude · Eins"]');
  assert(gewahlt.checked); assert(!gewahlt.disabled); gewahlt.checked = false; await gewahlt.ausloesen('change');
  assert(!u.run("P.entwurf.schreibmodelle.includes('eins')"));
}

async function sammlungUndKopieren() {
  const u = await starten(); u.e.herkunft = 'sammlung'; u.e.bearbeitbar = false; await u.zeichnen();
  assert(u.$('.p-af-editor').readOnly); assert(!u.knopf('Prompt verbessern')); assert(!u.knopf('Als bevorzugt'));
  assert(!u.knopf('Testen …', u.af()));
  await u.klick(u.knopf('Kopieren', u.rechts())); assert.deepEqual(u.kopiert, ['Original [A]']);
  u.e.herkunft = 'ordner'; u.e.bearbeitbar = true; await u.zeichnen();
  await u.input(u.$('.p-af-editor'), 'Ungespeichert'); await u.klick(u.knopf('Kopieren', u.rechts()));
  assert.equal(u.kopiert.at(-1), 'Ungespeichert'); assert(!u.anfragen.some(([, d]) => d?.aktion === 'fassung_bearbeitet'));
}

async function verzoegertesLadenUndEintragswechsel() {
  const u = await starten(); u.ergebnis(0); u.fragen(u.e.fassungen[1]); await u.zeichnen();
  await u.input(u.$('.p-af-antwort'), 'Antwort bleibt');
  await u.input(u.links().querySelector('[aria-label="Weitere Wünsche (optional)"]'), 'Wünsche bleiben');
  let frei; u.steuerung.beleg = new Promise((r) => { frei = r; });
  u.document.activeElement = null; u.run('P.inhaltStand=null'); const laden = u.run("pWaehlen('A',false)");
  await new Promise(setImmediate); frei(); await laden; u.steuerung.beleg = null;
  assert.equal(u.$('.p-af-antwort').value, 'Antwort bleibt');
  assert.equal(u.links().querySelector('[aria-label="Weitere Wünsche (optional)"]').value, 'Wünsche bleiben');
  await u.input(u.$('.p-af-editor'), 'Entwurf bleibt');
  const b = { ...kopie(u.e), id: 'B', titel: 'B' }; u.eintraege.set('B', b);
  await u.run("pWaehlen('B')"); assert.equal(u.run('P.gewaehlt'), 'B');
  await u.run("pWaehlen('A')"); assert.equal(u.$('.p-af-editor').value, 'Entwurf bleibt');
}

async function frageAntwortDirektUndTesten() {
  const u = await starten(); u.ergebnis(0); u.fragen(u.e.fassungen[1]); await u.zeichnen();
  await u.input(u.$('.p-af-antwort'), 'Kurz');
  await u.input(u.$('.p-af-editor'), 'Eine Änderung [A]');
  await u.klick(u.knopf('Mit Antworten verbessern'));
  assert.equal(u.neuesteSendung().rueckfragen[0].antwort, 'Kurz');
  assert.equal(u.neuesteSendung().text, 'Eine Änderung [A]');
  await u.run("pAfWahl(e,{runde:null,fassung:'Ergebnis 0'})");
  await u.klick(u.knopf('Ohne Antworten verbessern'));
  assert(!('rueckfragen' in u.neuesteSendung()));
  await u.run("pAfWahl(e,{runde:null,fassung:'Ergebnis 0'})");
  await u.klick(u.knopf('Direkt verbessern')); assert(!('rueckfragen' in u.neuesteSendung()));
  await u.run("pAfWahl(e,{runde:null,fassung:'Ergebnis 0'})");
  u.run('pTestdialog=async (e,name) => { window.testName=name; }');
  await u.input(u.$('.p-af-editor'), 'Vor dem Test gespeichert [A]');
  await u.klick(u.knopf('Testen …', u.rechts()));
  assert(u.ctx.window.testName.startsWith('Bearbeitet'));
}

async function bevorzugteFassungSofortSpeicherbar() {
  const u = await starten(); u.ergebnis(0); u.e.bevorzugt = 'Ergebnis 0'; await u.zeichnen();
  assert(u.knopf('Als bevorzugt', u.rechts()).hidden);
  await u.input(u.$('.p-af-editor'), 'Geändert und bevorzugt [A]');
  assert(!u.knopf('Als bevorzugt', u.rechts()).hidden);
  await u.klick(u.knopf('Als bevorzugt', u.rechts())); assert(u.e.bevorzugt.startsWith('Bearbeitet'));
  assert.equal(u.e.fassungen.at(-1).text, 'Geändert und bevorzugt [A]');
}

async function fortsetzenNeueSendungUndVorschaufehler() {
  const u = await starten(); u.ergebnis(0); await u.zeichnen();
  u.steuerung.sendeFehler = true; await u.klick(u.knopf('Direkt verbessern'));
  const erste = u.neuesteSendung(); assert(u.knopf('Einreihung fortsetzen')); assert(u.knopf('Als neue Sendung senden'));
  u.steuerung.sendeFehler = false; await u.klick(u.knopf('Einreihung fortsetzen'));
  assert.equal(u.neuesteSendung().anfrage_id, erste.anfrage_id);
  await u.run("pAfWahl(e,{runde:null,fassung:'Ergebnis 0'})");
  u.steuerung.sendeFehler = true; await u.klick(u.knopf('Direkt verbessern'));
  const zweite = u.neuesteSendung(); u.steuerung.sendeFehler = false;
  await u.klick(u.knopf('Als neue Sendung senden'));
  assert.notEqual(u.neuesteSendung().anfrage_id, zweite.anfrage_id);
  assert.equal(u.neuesteSendung().text, zweite.text);
  await u.run("pAfWahl(e,{runde:null,fassung:'Ergebnis 0'})");
  u.steuerung.vorschaufehler = true; const n = u.anfragen.length;
  await u.klick(u.knopf('Prompt verbessern'));
  assert(!u.anfragen.slice(n).some(([, d]) => d?.aktion === 'composer_senden'));
  assert(u.knopf('Im Composer öffnen')); assert(u.rechts().textContent.includes('Kontext wurde geändert'));
}

async function herkunftKetteGrenzeUndSchleife() {
  const u = await starten(); const q = u.fragen(); let vorher = u.e.fassungen[0];
  for (let i = 0; i < 11; i++) {
    const f = { name: 'Bearbeitet ' + i, text: 'x', stand: 'b' + i, herkunft_gueltig: true,
      herkunft: { von_fassung: vorher.name, von_stand: vorher.stand } };
    u.e.fassungen.push(f); vorher = f;
  }
  u.ctx.q = q; u.ctx.f = u.e.fassungen.at(-2);
  assert(u.run('pAfFragenGelten(e,f,q)'));
  u.ctx.f = u.e.fassungen.at(-1); assert(!u.run('pAfFragenGelten(e,f,q)'));
  u.e.fassungen[1].herkunft_gueltig = false; u.ctx.f = u.e.fassungen[2]; assert(!u.run('pAfFragenGelten(e,f,q)'));
  u.e.fassungen[1].herkunft_gueltig = true;
  u.e.fassungen[1].herkunft = { von_fassung: u.e.fassungen[2].name, von_stand: u.e.fassungen[2].stand };
  assert(!u.run('pAfFragenGelten(e,f,q)'));
}

async function modelleUndZielMitTeilfehler() {
  const u = await starten(); u.ergebnis(0); const schlecht = u.ergebnis(1, 'runde', 'claude');
  schlecht.ergebnis_fassung = null; schlecht.zustand = 'fehler'; const gut = u.ergebnis(2, 'runde', 'claude');
  await u.zeichnen(); await u.klick(u.knopf('claude', u.rechts()));
  assert.equal(u.run('P.af.A.lauf'), gut.datei);
  assert.equal(u.links().querySelector('select').value, 'eins');
  const modelle = u.rechts().querySelector('details.p-auswahl');
  const cb = modelle.querySelector('input[aria-label="Codex · Zwei"]'); cb.checked = true; await cb.ausloesen('change');
  assert.deepEqual(kopie(u.run('P.entwurf.schreibmodelle')), ['eins', 'zwei']);
  assert.deepEqual(JSON.parse(u.storage.get('werkstatt.prompt-schreibmodelle')), ['eins', 'zwei']);
  gut.zustand = 'fehler'; await u.zeichnen(); assert(!u.$('.p-af-editor')); assert(u.knopf('Neu senden'));
}

async function entwurfNachLoeschenDerQuelle() {
  const u = await starten(); await u.zeichnen();
  await u.input(u.$('.p-af-editor'), 'Entwurf ohne Quelle');
  u.e.fassungen = []; await u.zeichnen();
  assert.equal(u.$('.p-af-editor').value, 'Entwurf ohne Quelle');
  assert(u.knopf('Entwurf als neue Fassung speichern'));
  await u.klick(u.knopf('Entwurf als neue Fassung speichern'));
  assert.equal(u.e.fassungen[0].text, 'Entwurf ohne Quelle');
}

async function composerSendungFolgtNeuerRunde() {
  for (const vorherAngesehen of [false, true]) {
    const u = await starten();
    if (vorherAngesehen) {
      u.ergebnis(0, 'alteRunde');
      u.e.bevorzugt = 'Ergebnis 0';
      await u.zeichnen();
      assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 0 [A]');
      assert(u.run('P.af.A.fest'));
    }
    await u.run('pComposerBasis(e)');
    await u.run('pComposerSenden()');
    const d = u.neuesteSendung();
    assert.equal(u.run('P.af.A.eigeneRunde'), d.anfrage_id);
    assert.equal(u.run('P.af.A.runde'), d.anfrage_id);
    assert(!u.run('P.af.A.bewusst')); assert(!u.run('P.af.A.fest'));
    assert.equal(u.rechts().querySelector('.p-laufzeile').textContent, 'Wartet auf den Start …');
    const g = u.e.auftragsgruppen.find((g) => g.id === d.anfrage_id), b = g.ergebnisse[0];
    b.zustand = 'laeuft'; await u.zeichnen();
    assert(u.rechts().querySelector('.p-laufzeile').textContent.includes('das Modell arbeitet noch …'));
    const f = { name: 'Neues Composer-Ergebnis', text: 'Neuer Text [A]', stand: 'neu' };
    u.e.fassungen.push(f); b.ergebnis_fassung = f.name; b.zustand = 'fertig';
    await u.zeichnen();
    assert.equal(u.$('.p-af-editor').value, f.text);
    assert.equal(u.run('P.af.A.runde'), d.anfrage_id);
  }
}

async function feldgroessenNurInArbeitsflaeche() {
  const u = await starten(); await u.zeichnen();
  assert.equal(u.$('.p-af-editor').getAttribute('rows'), '12');
  assert.match(css, /\.p-arbeitsflaeche \.p-af-editor\s*\{[^}]*min-height:\s*20em;[^}]*max-height:\s*60vh;[^}]*overflow-y:\s*auto;/);
  assert.match(css, /@container \(min-width: 860px\)\s*\{[^@]*\.p-arbeitsflaeche \.p-af-editor\s*\{\s*max-height:\s*none;/);
  assert.equal(u.$('.p-af-wuensche').getAttribute('rows'), '2');
  assert.match(css, /\.p-arbeitsflaeche \.p-af-wuensche\s*\{\s*min-height:\s*0;\s*resize:\s*vertical;/);
  assert.match(css, /\.dialog-feld textarea\s*\{\s*min-height:\s*340px;/);
  assert.match(css, /\.p-fassung > textarea\s*\{[^}]*min-height:\s*70px;/);
}

async function laufFehlermeldungVorAllgemeinemGrund() {
  const u = await starten(); const b = u.ergebnis(0); b.ergebnis_fassung = null;
  b.zustand = 'fehler'; b.meldung = 'Anbieter hat den Lauf abgelehnt'; b.fehler = 'Belegfehler'; b.grund = 'kein Kasten';
  await u.zeichnen();
  assert.equal(u.rechts().querySelector('.warnung').textContent, b.meldung);
  b.meldung = ''; await u.zeichnen();
  assert.equal(u.rechts().querySelector('.warnung').textContent, b.fehler);
  b.fehler = ''; await u.zeichnen();
  assert.equal(u.rechts().querySelector('.warnung').textContent, b.grund);
  b.zustand = 'fertig'; b.meldung = 'Allgemeine Meldung'; await u.zeichnen();
  assert.equal(u.rechts().querySelector('.warnung').textContent, b.grund);
}

async function nachAntwortenBeiArbeitsflaecheBleiben() {
  const u = await starten(); u.ergebnis(0); u.fragen(u.e.fassungen[1]); await u.zeichnen();
  u.ctx.window.scrollX = 0; u.ctx.window.scrollY = 1400;
  u.ctx.window.scrollTo = ({ left, top }) => { u.ctx.window.scrollX = left; u.ctx.window.scrollY = top; };
  await u.input(u.$('.p-af-antwort'), 'Kurze Liste');
  await u.klick(u.knopf('Mit Antworten verbessern'));
  assert.strictEqual(u.document.activeElement, u.af());
  assert.equal(u.af().tabIndex, -1);
  assert.deepEqual(kopie(u.af().focusOptions), { preventScroll: true });
  assert.deepEqual(kopie(u.af().scrollIntoViewOptions), { block: 'start', behavior: 'instant' });
  assert.match(css, /\.p-arbeitsflaeche\s*\{[^}]*scroll-margin-top:\s*var\(--oben\);/);
  assert(u.rechts().querySelector('.p-laufzeile'));
}

async function fragestellerVorgabeVerfuegbar() {
  const u = await starten(); const b = u.ergebnis(0); b.schreibmodell_id = 'aus'; await u.zeichnen();
  assert.equal(u.links().querySelector('select').value, 'eins');
  u.run("pAfZustand(e).fragestellerBewusst=true;pAfZustand(e).fragesteller='zwei'");
  await u.zeichnen(); assert.equal(u.links().querySelector('select').value, 'zwei');
  u.run("pAfZustand(e).fragestellerBewusst=false;P.entwurf.schreibmodelle=['aus']");
  await u.run("pAfWahl(e,{runde:null,fassung:'Fassung 1'})");
  assert.equal(u.links().querySelector('select').value, 'eins');
  u.run('P.optionen.schreibmodelle.forEach((p) => { p.prompts_verfuegbar=false; })');
  await u.zeichnen(); assert.equal(u.links().querySelector('select').value, 'aus');
}

async function fremdeSendungEntscheidungErreichbar() {
  for (const zustand of ['sendeFehler', 'verloren']) {
    const u = await starten(); u.ergebnis(0); await u.zeichnen();
    u.steuerung[zustand] = true; await u.klick(u.knopf('Direkt verbessern'));
    const b = { ...kopie(u.e), id: 'B', titel: 'Anderer Eintrag' }; u.eintraege.set('B', b);
    await u.run("pWaehlen('B')");
    assert(u.knopf('Prompt verbessern').disabled);
    assert(u.rechts().textContent.includes('Im Eintrag „Testprompt“ wartet eine Sendung auf deine Entscheidung.'));
    await u.klick(u.knopf('Dorthin wechseln'));
    assert.equal(u.run('P.gewaehlt'), 'A');
    assert(u.knopf(zustand === 'verloren' ? 'Status prüfen' : 'Einreihung fortsetzen'));
  }
}

async function fragenHinweisPasstZuFehlendemErgebnis() {
  const u = await starten(); const b = u.ergebnis(0); b.ergebnis_fassung = null; b.zustand = 'fehler';
  await u.zeichnen();
  assert(u.knopf('Neu senden')); assert(!u.knopf('Prompt verbessern'));
  assert(u.links().textContent.includes('Fragen gibt es, sobald rechts ein neuer Prompt steht.'));
  assert(!u.links().textContent.includes('Klicke rechts auf'));
  await u.klick(u.knopf('Basis anzeigen'));
  assert(u.knopf('Prompt verbessern'));
  assert(u.links().textContent.includes('Klicke rechts auf „Prompt verbessern“.'));
}

async function sendungNachRueckkehrWiederaufnehmen() {
  for (const aktion of ['Schärfen', 'Rückfragen']) {
    for (const knopf of ['Status prüfen', 'Einreihung fortsetzen', 'Als neue Sendung senden']) {
      for (const waehrendAntwortWechseln of [false, true]) {
        const u = await starten(); const alt = u.ergebnis(0, 'alteRunde');
        if (aktion === 'Schärfen') {
          alt.ergebnis_fassung = null; alt.zustand = 'fehler'; alt.meldung = 'Alter Lauf fehlgeschlagen';
        }
        await u.zeichnen();
        await u.run("pAfWahl(e,{runde:'alteRunde',lauf:'Lauf0.md',reiter:'Versionen'})");
        u.steuerung[knopf === 'Status prüfen' ? 'verloren' : 'sendeFehler'] = true;
        await u.klick(u.knopf(aktion === 'Schärfen' ? 'Neu senden' : 'Prompt verbessern'));
        const daten = u.neuesteSendung();
        const y = { ...kopie(u.e), id: 'B', titel: 'Eintrag Y' }; u.eintraege.set(y.id, y);
        await u.run("pWaehlen('B')");
        assert(u.rechts().textContent.includes('Im Eintrag „Testprompt“ wartet eine Sendung auf deine Entscheidung.'));
        await u.klick(u.knopf('Dorthin wechseln'));
        assert.equal(u.run('P.gewaehlt'), 'A');
        assert.equal(u.run('P.af.A.runde'), 'alteRunde');

        if (knopf === 'Status prüfen') {
          const neu = aktion === 'Schärfen' ? u.ergebnis(1, daten.anfrage_id)
            : u.fragen(u.e.fassungen[1], 1, daten.anfrage_id + '.md');
          u.steuerung.status = { gefunden: true, vollstaendig: true, id: 'A', auftragsgruppe: daten.anfrage_id,
            ziele: [{ beleg: neu.datei }] };
        }
        u.steuerung.verloren = false; u.steuerung.sendeFehler = false;
        let freigeben;
        if (waehrendAntwortWechseln) {
          u.steuerung[knopf === 'Status prüfen' ? 'statusWarten' : 'senden'] = new Promise((r) => { freigeben = r; });
        }
        const antwort = u.klick(u.knopf(knopf));
        if (waehrendAntwortWechseln) {
          await new Promise(setImmediate);
          await u.run("pWaehlen('B')");
          freigeben();
        }
        await antwort;
        assert.equal(u.run('P.afSendung'), null);
        const aid = knopf === 'Status prüfen' ? daten.anfrage_id : u.neuesteSendung().anfrage_id;
        if (knopf === 'Als neue Sendung senden') assert.notEqual(aid, daten.anfrage_id);
        else assert.equal(aid, daten.anfrage_id);
        if (waehrendAntwortWechseln) {
          assert.equal(u.run('P.gewaehlt'), 'B', 'Die verspätete Bestätigung darf nicht zu X zurückholen');
          assert.equal(u.af().scrollIntoViewOptions, undefined);
          assert.equal(u.run('P.af.A.reiter'), 'Versionen');
          continue;
        }
        assert.equal(u.run('P.gewaehlt'), 'A');
        if (aktion === 'Rückfragen') {
          assert.equal(u.run('P.af.A.fragen'), knopf === 'Status prüfen' ? u.steuerung.status.ziele[0].beleg : aid + '.md');
          assert.equal(u.run('P.af.A.reiter'), 'Fragen');
          assert.equal(u.$('.p-af-editor').value, 'Ergebnistext 0 [A]');
        } else {
          assert.equal(u.run('P.af.A.runde'), aid);
          assert.equal(u.run('P.af.A.eigeneRunde'), aid);
          if (knopf !== 'Status prüfen') {
            assert(u.rechts().querySelector('.p-laufzeile'));
            const lauf = u.e.auftragsgruppen.find((g) => g.id === aid).ergebnisse[0];
            u.e.fassungen.push({ name: 'Neues Ergebnis', text: 'Neu bestätigter Text [A]', stand: 'neu' });
            lauf.zustand = 'fertig'; lauf.ergebnis_fassung = 'Neues Ergebnis';
            await u.zeichnen();
          }
          assert.equal(u.$('.p-af-editor').value, knopf === 'Status prüfen' ? 'Ergebnistext 1 [A]' : 'Neu bestätigter Text [A]');
        }
      }
    }
  }
}

(async () => {
  const tests = [vorgabenUndNavigation, ersterErfolgReiterUndZiele, alleLaufzustaendeUndNeuSenden, entwurfUeberlebtUndKonflikt,
    speichernVorFragenUndNavigation, fragenAntwortenUndBearbeitetKette, neueFragenUndBewussterBeleg, fragenZustaende,
    composerAntwortenUndBasiswechsel, sendebestaetigungNavigationUndVerlust, fehlerEntwurfUndComposerUnabhaengig,
    fehlendesZielUndModelle, sammlungUndKopieren, verzoegertesLadenUndEintragswechsel, frageAntwortDirektUndTesten,
    bevorzugteFassungSofortSpeicherbar, fortsetzenNeueSendungUndVorschaufehler, herkunftKetteGrenzeUndSchleife, modelleUndZielMitTeilfehler,
    entwurfNachLoeschenDerQuelle, composerSendungFolgtNeuerRunde, feldgroessenNurInArbeitsflaeche,
    laufFehlermeldungVorAllgemeinemGrund, nachAntwortenBeiArbeitsflaecheBleiben, fragestellerVorgabeVerfuegbar,
    fremdeSendungEntscheidungErreichbar, fragenHinweisPasstZuFehlendemErgebnis, sendungNachRueckkehrWiederaufnehmen];
  for (const test of tests) { await test(); console.log(test.name + ' OK'); }
  console.log(tests.length + ' Arbeitsflächen-Bedienungstests OK');
})().catch((err) => { console.error(err); process.exitCode = 1; });
