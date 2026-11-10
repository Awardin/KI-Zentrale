'use strict';

// Echtes Oberflächenskript, kleines DOM und Fake-HTTP; keine Dienste oder Modelle.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { kinder, keinFremdText } = require('./dom_nachbau');
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.value = ''; this.textContent = ''; this.events = {};
  }
  append(...k) { const neu = kinder(...k); for (const el of neu) el.parentElement = this; this.children.push(...neu); }
  replaceChildren(...k) { this.children = []; this.append(...k); }
  setAttribute(k, v) { this[k] = v; }
  getAttribute(k) { return this[k] ?? null; }
  addEventListener(k, f) { this.events[k] = f; }
  focus() {}
  nachkommen() { return this.children.flatMap((k) => [k, ...(k.nachkommen?.() || [])]); }
  contains(el) { return el === this || this.nachkommen().includes(el); }
  querySelectorAll(s) { return this.nachkommen().filter((k) => s !== 'details[data-p-ansicht]'
    || (k.tag === 'details' && k['data-p-ansicht'] != null)); }
  querySelector(s) { return this.nachkommen().find((k) => s === 'button' ? k.tag === 'button'
    : s === '.f-text' && k.className === 'f-text') || null; }
}
const ids = new Map(), anfragen = [], speicher = new Map([['werkstatt.prompt-auswerter', '["ziel"]']]);
let dialog = null, verfuegbar = true, aboTest = false;
const fenster = { scrollTo() {} };
const document = {
  querySelector(s) {
    if (s === 'dialog[open]') return dialog?.offen ? dialog : null;
    if (!ids.has(s)) ids.set(s, new Element('div'));
    return ids.get(s);
  },
  createElement: (tag) => new Element(tag),
  querySelectorAll(s) {
    const alle = [...new Set([...ids.values()].flatMap((el) => [el, ...el.nachkommen()]))];
    return alle.filter((el) => s === '.p-schaerfen-menue' && el.className === 'p-schaerfen-menue');
  },
};
const e = {id: 'Test', titel: 'Test', herkunft: 'ordner', bearbeitbar: true, bevorzugt: 'Zwei',
  fassungen: [{name: 'Eins', text: 'Original <script> [A]', stand: 'a'}, {name: 'Zwei', text: 'Andere Fassung', stand: 'b'}],
  tests: [{datei: 'Antwort.md', fassung: 'Eins', antwort_vorhanden: true, auswerter: 'Ziel'},
    {datei: 'Leer.md', antwort_vorhanden: false}],
  schaerfen: [{datei: 'Schärfen.md', aktion: 'Schärfen', auswerter: 'Codex', zielmodell: 'Ziel',
    zustand: 'fertig', ergebnis: 'übernommen (Neu)'}],
  warteschlange: [{id: 'lauf', art: 'schaerfen', prompt: {eintrag: 'Test', fassung: 'Eins', beleg: 'Schärfen'},
    auswerter: {name: 'Codex'}, zustand: 'fehler', meldung: 'Nacharbeit fehlt'}],
};
const ergebnis = {aktion: 'Schärfen', original: 'Original <script> [A]', neue_fassung: 'Neu [A] [Projektkontext]',
  stichpunkte: '- Klarer.', neue_platzhalter: ['Projektkontext']};
const kontext = vm.createContext({document, window: fenster, console,
  localStorage: {getItem: (k) => speicher.get(k) || null, setItem: (k, v) => speicher.set(k, v)},
  aktualisieren() {}, fehlerMelden(t) { throw Error(t); }, markdown: (t) => 'Markdown: ' + t,
  dialogOeffnen(titel, inhalt, knoepfe) {
    dialog = new Element('dialog'); dialog.append(...inhalt, ...knoepfe); dialog.offen = true;
    keinFremdText(dialog);
    dialog.close = () => { dialog.offen = false; }; return dialog;
  },
  fetch: async (pfad, opt) => {
    const d = opt?.body ? JSON.parse(opt.body) : null;
    anfragen.push([pfad, d]);
    let wert;
    if (pfad === '/api/zusammenfassung') wert = {auswerter: [
      {id: 'ziel', name: 'Ziel', anbieter: 'lokal', verfuegbar: true},
      {id: 'claude', name: 'Claude', anbieter: 'claude', verfuegbar: false, grund: 'Bitte auth login'},
      {id: 'codex', name: 'Codex', anbieter: 'codex', verfuegbar: true, cloud: 'OpenAI'},
      ...(aboTest ? [{id:'api',name:'Claude API',anbieter:'claude',verfuegbar:true,prompts_verfuegbar:false,
        prompts_grund:'Abo-Anmeldung nicht bestätigt',zugang_text:'API'}] : [])]};
    else if (d?.aktion === 'schaerfen_vorschau') wert = {auftrag: 'Skill\nOriginal [A]', gesendet_stand: 'hash',
      schreibmodell: {name: 'Codex', verfuegbar, grund: verfuegbar ? '' : 'Bitte auth login',
        verarbeitung: 'Cloud (OpenAI)', kontext: 200000, kontext_quelle: 'Anbieter', geschaetzt: 123,
        hinweis: 'Sandbox nur lesend, kann Dateien lesen und Befehle ausführen, liest seine globale AGENTS.md mit'}};
    else if (pfad === '/api/prompts') wert = {eintraege: [e], fehler: [], warteschlange: e.warteschlange};
    else if (pfad.startsWith('/api/prompt?id=')) wert = e;
    else if (pfad.startsWith('/api/prompt-datei?')) wert = ergebnis;
    else if (d?.aktion === 'schaerfen' || pfad === '/api/fassung') wert = {ok: true};
    else throw Error('Unerwartete Anfrage: ' + pfad);
    return {ok: true, json: async () => wert};
  },
});
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
vm.runInContext(app.split('let STAND =')[0], kontext);
vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), kontext);
vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='), app.indexOf('function schrittListe(')), kontext);
vm.runInContext(fs.readFileSync('werkstatt/web/prompts.js', 'utf8'), kontext);
kontext.e = e; kontext.ergebnis = ergebnis;
const alle = (box) => [box, ...box.nachkommen()];
const knopf = (box, text) => alle(box).find((k) => k.tag === 'button'
  && k.children.some((kind) => kind.tag === '#text' && kind.textContent === text));
const feld = (text) => alle(dialog).find((k) => k['aria-label'] === text);
const klicken = async (b) => { assert(b); await b.events.click({currentTarget: b}); };
(async () => {
  await vm.runInContext('pSchaerfendialog(e)', kontext);
  assert.equal(feld('Fassung').value, 'Zwei');
  assert.equal(feld('Schreibmodell').value, 'codex');
  assert.equal(feld('Zielmodell').value, 'ziel');
  assert.equal(feld('Hinweise').maxlength, '2000');
  assert(alle(feld('Schreibmodell')).some((k) => k.textContent.includes('auth login')));
  assert.equal(alle(feld('Letzte Antwort als Material')).filter((k) => k.tag === 'option').length, 2);
  await klicken(knopf(dialog, 'Start'));
  assert(!anfragen.some(([, d]) => d?.aktion === 'schaerfen'));
  await klicken(knopf(dialog, 'Vorschau berechnen'));
  assert(alle(dialog).some((k) => k.tag === 'pre' && k.textContent === 'Skill\nOriginal [A]'));
  assert(alle(dialog).some((k) => k.textContent.includes('globale AGENTS.md')));
  feld('Hinweise').value = 'Änderung nach Vorschau';
  await klicken(knopf(dialog, 'Start'));
  assert(!anfragen.some(([, d]) => d?.aktion === 'schaerfen'));
  feld('Aktion').value = 'Kürzen'; feld('Letzte Antwort als Material').value = 'Antwort.md';
  await klicken(knopf(dialog, 'Vorschau berechnen'));
  await klicken(knopf(dialog, 'Start'));
  const gesendet = anfragen.find(([, d]) => d?.aktion === 'schaerfen')[1];
  assert.equal(gesendet.schaerfen_aktion, 'Kürzen'); assert.equal(gesendet.material, 'Antwort.md');
  assert.equal(gesendet.gesendet_stand, 'hash'); assert(!dialog.offen);
  assert.equal(speicher.get('werkstatt.prompt-schreibmodell'), 'codex');
  // Einstieg am Eintrag und jeder Fassung, einschließlich Sammlung.
  for (const herkunft of ['ordner', 'sammlung']) {
    e.herkunft = herkunft; e.bearbeitbar = herkunft === 'ordner';
    await vm.runInContext('pWaehlen(e.id)', kontext);
    const box = ids.get('#p-inhalt');
    keinFremdText(box);
    assert.equal(alle(box).filter((k) => k.tag === 'button'
      && k.children.some((kind) => kind.textContent === 'Schärfen ▾')).length, 3);
    await klicken(knopf(box, 'Schärfen ▾'));
    assert(alle(box).some((k) => k.className === 'p-schaerfen-menue' && !k.hidden));
    await klicken(knopf(box, 'Erst klären'));
    assert.equal(feld('Aktion').value, 'Erst klären');
    dialog.close();
  }
  const box = ids.get('#p-inhalt');
  const details = alle(box).find((k) => k.tag === 'details' && k['data-p-ansicht'] === '["Schärfen.md","schaerfen"]');
  details.open = true; await details.events.toggle();
  let pre = alle(details).filter((k) => k.tag === 'pre' && k.className === 'p-text');
  assert.equal(pre.length, 2); assert.equal(pre[0].textContent, ergebnis.original); assert.equal(pre[1].textContent, ergebnis.neue_fassung);
  assert(alle(details).some((k) => k.className === 'p-vergleich'));
  assert(alle(details).some((k) => k.textContent.includes('Neue Platzhalter: [Projektkontext]')));
  assert(alle(details).some((k) => k.textContent === '- Klarer.'));
  keinFremdText(details);
  // Regression: Ohne neue Platzhalter darf replaceChildren keinen null-Text anhängen.
  ergebnis.neue_platzhalter = [];
  await details.events.toggle();
  keinFremdText(details);
  assert(!alle(details).some((k) => k.textContent.includes('Neue Platzhalter:')));
  delete ergebnis.neue_platzhalter;
  await details.events.toggle();
  keinFremdText(details);
  await klicken(knopf(box, 'Wiederholen'));
  assert(anfragen.some(([pfad, d]) => pfad === '/api/fassung' && d.aktion === 'wiederholen'));
  ergebnis.aktion = 'Erst klären'; ergebnis.fragen = '1. Welches Ziel?';
  await details.events.toggle();
  assert.equal(alle(details).filter((k) => k.tag === 'pre').length, 0);
  assert(alle(details).some((k) => k.textContent === '1. Welches Ziel?'));
  // Aktive Schärfen-Dateien verwenden den bestehenden Ladepfad.
  e.warteschlange = []; e.schaerfen[0].zustand = 'wartet';
  await vm.runInContext('pLaden()', kontext);
  assert(vm.runInContext('pLaeuft()', kontext));
  // Ein nicht verfügbares Profil zeigt den Anmeldegrund und kann nicht starten.
  speicher.set('werkstatt.prompt-schreibmodell', 'ziel');
  await vm.runInContext('pSchaerfendialog(e)', kontext);
  assert.equal(feld('Schreibmodell').value, 'ziel');
  verfuegbar = false;
  const vorher = anfragen.filter(([, d]) => d?.aktion === 'schaerfen').length;
  await klicken(knopf(dialog, 'Vorschau berechnen')); await klicken(knopf(dialog, 'Start'));
  assert(alle(dialog).some((k) => k.textContent.includes('auth login')));
  assert.equal(anfragen.filter(([, d]) => d?.aktion === 'schaerfen').length, vorher);
  for (const wurzel of [...ids.values(), dialog]) keinFremdText(wurzel);
  aboTest = true; speicher.set('werkstatt.prompt-schreibmodell', 'api');
  await vm.runInContext('pSchaerfendialog(e)', kontext);
  assert.equal(feld('Schreibmodell').value, 'codex');
  const apiOption = feld('Schreibmodell').children.find((k) => k.value === 'api');
  assert(apiOption.disabled); assert(apiOption.textContent.includes('Abo-Anmeldung nicht bestätigt'));
  assert(!feld('Zielmodell').children.find((k) => k.value === 'api').disabled);
})().catch((err) => { console.error(err); process.exitCode = 1; });
