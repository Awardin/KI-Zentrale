'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { kinder, keinFremdText } = require('./dom_nachbau');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.value = ''; this.textContent = ''; }
  append(...k) { this.children.push(...kinder(...k)); }
  replaceChildren(...k) { this.children = kinder(...k); }
  setAttribute(k, v) { this[k] = v; }
  addEventListener(k, f) { this.events[k] = f; }
  alle() { return [this, ...this.children.flatMap((k) => k.alle ? k.alle() : [k])]; }
}
let dialog, aenderungen = 0;
const anfragen = [], stand = { auswerter: [] };
const ctx = vm.createContext({ console,
  document: { createElement: (tag) => new Element(tag) },
  fetch: async (pfad, opt) => {
    const d = opt?.body ? JSON.parse(opt.body) : null;
    anfragen.push([pfad, d]);
    let wert;
    if (pfad === '/api/katalog') wert = {anbieter: [{anbieter:'lokal',name:'Lokal',modelle:[
      {modell:'qwen27-unsloth',name:'Qwen 27B',stufen:[],kontext:131072}]}],stufen_text:{}};
    else if (pfad === '/api/auswerter' && d.aktion === 'neu') {
      stand.auswerter.push({id:'neu',name:'Qwen 27B'}); wert = {ok:true};
    } else if (pfad === '/api/auswerter' && d.aktion === 'loeschen') {
      stand.auswerter = []; wert = {ok:true};
    } else throw Error('Unerwartet: ' + pfad);
    return {ok:true,json:async()=>wert};
  },
  dialogOeffnen(titel, inhalt, knoepfe) {
    dialog = new Element('dialog'); dialog.append(...inhalt, ...knoepfe);
    dialog.close = () => {}; return dialog;
  },
  stand, geaendert: async () => { aenderungen++; return stand; },
});
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
vm.runInContext(app.split('let STAND =')[0], ctx);
vm.runInContext('const ZF = {stand:null,katalog:null,auswerterWahl:new Set()}; function zfAktualisieren(){throw Error("ZF darf nicht laden");}', ctx);
const zf = fs.readFileSync('werkstatt/web/zusammenfassung.js', 'utf8');
vm.runInContext(zf.slice(zf.indexOf('async function auswerterDialog('), zf.indexOf('// ------------------------------------------------------------------ Start')), ctx);
const button = (text) => dialog.alle().find((e) => e.tag === 'button' && e.children.some((k) => k.textContent === text));
(async () => {
  await vm.runInContext('auswerterDialog(stand, geaendert)', ctx);
  await button('Hinzufügen').events.click();
  assert.equal(aenderungen, 1);
  assert(dialog.alle().some((e) => e.textContent === 'Qwen 27B'));
  await button('Entfernen').events.click();
  assert.equal(aenderungen, 2);
  assert(!dialog.alle().some((e) => e.tag === 'span' && e.textContent === 'Qwen 27B'));
  assert.equal(vm.runInContext('ZF.stand', ctx), null);
  assert(!anfragen.some(([p]) => p === '/api/zusammenfassung'));
  keinFremdText(dialog);
  // Bisheriger Aufruf aus der Zusammenfassung behält seinen Aktualisierungsweg.
  vm.runInContext('ZF.stand = stand; async function zfAktualisieren(){ ZF.stand = stand; }', ctx);
  await vm.runInContext('auswerterDialog()', ctx);
  await button('Hinzufügen').events.click();
  assert.equal(stand.auswerter.length, 1);
  assert(!anfragen.some(([p]) => p === '/api/zusammenfassung'));
  console.log('Profilverwaltung ohne ZF-Stand: OK');
})().catch((e) => { console.error(e); process.exitCode = 1; });
