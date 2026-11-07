'use strict';

// Echtes prompts.js mit verzögerten Fake-Antworten und dem von Hand ausgelösten Bestandstakt.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { kinder, keinFremdText } = require('./dom_nachbau');
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
const prompts = fs.readFileSync('werkstatt/web/prompts.js', 'utf8');
const fertig = () => new Promise(setImmediate);
const eintraege = (titel = 'Test') => [{id: 'Test', titel, herkunft: 'ordner', fassungen: [], getestet: false}];
const daten = (titel) => ({eintraege: eintraege(titel), fehler: [], warteschlange: []});

function umgebung() {
  const ids = new Map(), offen = [], zeitgeber = [];
  let jetzt = 100000, dialog = null, anzahl = 0, parallel = 0, hoechstens = 0, timerId = 0;
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; this.value = ''; this.events = {}; }
    append(...k) { this.children.push(...kinder(...k)); }
    replaceChildren(...k) { this.children = kinder(...k); }
    setAttribute(k, v) { this[k] = v; }
    addEventListener(k, fn) { this.events[k] = fn; }
    focus() { this.fokussiert = true; }
    select() { this.markiert = [0, this.value.length]; }
  }
  const document = {
    querySelector(s) {
      if (s === 'dialog[open]') return dialog?.offen ? dialog : null;
      if (!ids.has(s)) ids.set(s, new Element('div'));
      return ids.get(s);
    },
    createElement: (tag) => new Element(tag),
  };
  const kontext = vm.createContext({document, window: {}, console,
    Date: class extends Date { static now() { return jetzt; } },
    setTimeout(fn, ms) { assert.equal(ms, 2500); zeitgeber.push(fn); return ++timerId; },
    dialogOeffnen(titel, inhalt, knoepfe) {
      dialog = new Element('dialog'); dialog.titel = titel; dialog.offen = true;
      dialog.append(...inhalt, ...knoepfe);
      dialog.close = () => { dialog.offen = false; };
      keinFremdText(dialog);
      return dialog;
    },
    fetch(pfad) {
      assert.equal(pfad, '/api/prompts');
      anzahl++; parallel++; hoechstens = Math.max(hoechstens, parallel);
      return new Promise((resolve, reject) => offen.push({
        antwort(d = daten()) { parallel--; resolve({ok: true, json: async () => d}); },
        fehler() { parallel--; reject(Error('Dienst startet noch.')); },
      }));
    },
  });
  vm.runInContext(app.split('let STAND =')[0], kontext);
  vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), kontext);
  vm.runInContext(prompts, kontext);
  const aus = (code) => vm.runInContext(code, kontext);
  return {ids, aus,
    aktiv() { aus('window.promptsAktiv(true)'); },
    laden() { return aus('pLaden()'); },
    antwort(d) { assert(offen.length); offen.shift().antwort(d); },
    fehler() { assert(offen.length); offen.shift().fehler(); },
    takt(ms = 2500) { jetzt += ms; assert.equal(zeitgeber.length, 1); return zeitgeber.shift()(); },
    get anzahl() { return anzahl; },
    get hoechstens() { return hoechstens; },
    get dialog() { return dialog; },
    get liste() { return ids.get('#p-liste'); },
    get rueck() { return ids.get('#p-rueck').textContent; },
    get zeitgeber() { return zeitgeber.length; },
    schutz(art) {
      dialog = art === 'dialog' ? {offen: true} : null;
      document.activeElement = art === 'fokus' ? {matches: () => true} : null;
    },
    pruefen() { for (const wurzel of [...ids.values(), dialog]) keinFremdText(wurzel); },
  };
}

(async () => {
  const u = umgebung();
  u.aktiv();
  assert.equal(u.anzahl, 1);
  assert.equal(u.liste.children[0].textContent, 'Prompts werden geladen …');
  u.pruefen();
  u.fehler(); await fertig();
  assert.equal(u.liste.children[0].textContent, 'Liste nicht geladen – neuer Versuch läuft.');
  assert.equal(u.rueck, 'Dienst startet noch.');
  assert.equal(u.aus('P.letztesLaden'), undefined);
  u.pruefen();
  const neuerVersuch = u.takt();
  assert.equal(u.anzahl, 2);
  u.antwort(); await neuerVersuch;
  assert.equal(u.liste.children[0].children[0].children[0].textContent, 'Test');
  assert.equal(u.rueck, '');
  assert(!JSON.stringify(u.liste).includes('werden geladen'));
  assert(!JSON.stringify(u.liste).includes('neuer Versuch'));
  u.pruefen();
  // Erfolgreicher Leerlauf: auch kurz vor 30 s kein Abruf.
  await u.takt(2500); assert.equal(u.anzahl, 2);
  await u.takt(27499); assert.equal(u.anzahl, 2);
  const nach30s = u.takt(1); assert.equal(u.anzahl, 3);
  u.antwort(); await nach30s;
  assert.equal(u.zeitgeber, 1);

  // Verwerfen bei Dialog oder Fokus, sowohl vor als auch nach einem früheren Erfolg.
  for (const art of ['dialog', 'fokus']) for (const schonGeladen of [false, true]) {
    const v = umgebung(); v.aktiv();
    if (schonGeladen) { v.antwort(daten('Alter Stand')); await fertig(); }
    const letzterErfolg = v.aus('P.letztesLaden');
    const lauf = schonGeladen ? v.laden() : fertig();
    v.schutz(art); v.antwort(daten('Verworfen')); await lauf; await fertig();
    assert.equal(v.aus('P.letztesLaden'), letzterErfolg);
    assert(!JSON.stringify(v.liste).includes('Verworfen'));
    const vorher = v.anzahl;
    await v.takt(); assert.equal(v.anzahl, vorher);
    await v.laden(); assert.equal(v.anzahl, vorher);
    v.schutz(null);
    const takt = v.takt(); assert.equal(v.anzahl, vorher + 1);
    v.antwort(daten('Frischer Stand')); await takt;
    assert(JSON.stringify(v.liste).includes('Frischer Stand'));
    v.pruefen();
  }

  // Mehrere Aufrufe während eines Abrufs ergeben genau einen anschließenden Abruf.
  for (const scheitert of [false, true]) {
    const v = umgebung(); v.aktiv();
    await v.laden();
    await v.ids.get('#p-laden').events.click();
    await v.ids.get('#p-laden').events.click();
    assert.equal(v.anzahl, 1);
    if (scheitert) v.fehler(); else v.antwort(daten('Erster Stand'));
    await fertig();
    assert.equal(v.anzahl, 2);
    assert.equal(v.hoechstens, 1);
    v.antwort(daten('Neuester Stand')); await fertig();
    assert.equal(v.anzahl, 2);
    assert(JSON.stringify(v.liste).includes('Neuester Stand'));
    assert(!JSON.stringify(v.liste).includes('Erster Stand'));
    v.pruefen();
  }

  // Ein Takt während eines langsamen Abrufs stellt keinen zweiten dahinter (sonst Daueranfragen ab 2,5 s Antwortzeit).
  const langsam = umgebung(); langsam.aktiv();
  await langsam.takt(); assert.equal(langsam.anzahl, 1);
  langsam.aus('window.promptsAktiv(true)'); assert.equal(langsam.anzahl, 1);
  langsam.antwort(); await fertig();
  assert.equal(langsam.anzahl, 1);
  assert(JSON.stringify(langsam.liste).includes('Test'));
  langsam.pruefen();

  // Ein nachzuholender Klick bleibt beim inzwischen geöffneten Dialog für den nächsten Takt fällig.
  const geschuetzt = umgebung(); geschuetzt.aktiv(); await geschuetzt.laden();
  geschuetzt.schutz('dialog'); geschuetzt.antwort(); await fertig();
  assert.equal(geschuetzt.anzahl, 1);
  geschuetzt.schutz(null);
  const nachDialog = geschuetzt.takt(); assert.equal(geschuetzt.anzahl, 2);
  geschuetzt.antwort(); await nachDialog; geschuetzt.pruefen();

  // Späterer Fehler erhält die gezeigten Knoten und wird trotz frischem Ladezeitpunkt erneut versucht.
  const v = umgebung(); v.aktiv(); v.antwort(); await fertig();
  const vorher = [...v.liste.children], letzterErfolg = v.aus('P.letztesLaden');
  const lauf = v.laden(); v.fehler(); await lauf;
  assert(v.liste.children.every((k, i) => k === vorher[i]));
  assert.equal(v.aus('P.letztesLaden'), letzterErfolg);
  assert.equal(v.rueck, 'Dienst startet noch.');
  const takt = v.takt(); assert.equal(v.anzahl, 3);
  v.antwort({...daten(), fehler: ['Hinweis aus der Liste']}); await takt;
  assert.equal(v.rueck, 'Hinweis aus der Liste'); v.pruefen();

  // Auch nach einer leeren Liste verschwindet ein Fehlerhinweis beim nächsten leeren Erfolg.
  const leer = umgebung(); leer.aktiv(); leer.antwort({eintraege: [], fehler: []}); await fertig();
  const leerLauf = leer.laden(); leer.fehler(); await leerLauf;
  assert.equal(leer.liste.children[0].textContent, 'Liste nicht geladen – neuer Versuch läuft.');
  const leerTakt = leer.takt(); leer.antwort({eintraege: [], fehler: []}); await leerTakt;
  assert.equal(leer.liste.children[0].textContent, 'Keine passenden Prompts.'); leer.pruefen();

  // Der neue Fassungsdialog übernimmt ausschließlich den Servervorschlag und markiert ihn zum Ersetzen.
  const dialog = umgebung();
  dialog.aus('pDialog({id: "Test", fassung_vorschlag: "Fassung 8"}, "fassung_neu")');
  assert.equal(dialog.dialog.titel, 'Neue Fassung');
  const name = dialog.dialog.children[0].children[1];
  assert.equal(name.value, 'Fassung 8');
  assert(name.fokussiert); assert.deepEqual(name.markiert, [0, 9]);
  name.value = 'Eigene Fassung'; assert.equal(name.value, 'Eigene Fassung');
  dialog.pruefen();
})().catch((err) => { console.error(err); process.exitCode = 1; });
