'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
const code = fs.readFileSync('werkstatt/web/prompts.js', 'utf8');
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));
const fertig = () => new Promise(setImmediate);

function start() {
  const { dokument: document, Element } = dokumentBauen();
  for (const id of ['transkription', 'zusammenfassung', 'bildvideo', 'texterkennung', 'messungen']) {
    const el = new Element('main'); el.id = 'reiter-' + id; document.append(el);
  }
  let anzahl = 0, fehler = false, langsam = false, freigabe;
  const timer = [], location = { hash: '#prompts' };
  const e = { id: 'Test', titel: 'Test', herkunft: 'ordner', fassungen: [{name:'Fassung 1',text:'Bestand',stand:'s'}], tests:[],schaerfen:[] };
  const optionen = {...regeln,schreibmodelle:[{id:'w',name:'Testmodell',prompts_verfuegbar:true,zugang_text:'lokal'}],
    zielprofile:regeln.zielprofile.map((p)=>({...p,varianten:[]}))};
  const ctx = vm.createContext({ document, window:{addEventListener(){},scrollTo(){}}, console,
    location, history:{replaceState(_,__,hash){location.hash=hash;}},
    localStorage:{getItem(){return null;},setItem(){}}, setTimeout(fn,ms){assert.equal(ms,2500);timer.push(fn);return 1;},
    fetch:async(pfad)=>{
      if(pfad==='/api/prompt-optionen') return {ok:true,json:async()=>optionen};
      assert.equal(pfad,'/api/prompts');anzahl++;
      if(langsam) await new Promise((r)=>{freigabe=r;});
      if(fehler) return {ok:false,status:503,json:async()=>({fehler:'Dienst vorübergehend nicht erreichbar.'})};
      return {ok:true,json:async()=>({eintraege:[e],fehler:[],warteschlange:[]})};
    },
  });
  vm.runInContext(app.split('let STAND =')[0],ctx);
  vm.runInContext(app.slice(app.indexOf('const REITER ='),app.indexOf('// ------------------------------------------------------------------ Hinzufügen')),ctx);
  vm.runInContext(app.slice(app.indexOf('function knopf('),app.indexOf('const auftrag =')),ctx);
  vm.runInContext(code,ctx);
  const run=(s)=>vm.runInContext(s,ctx);
  run('reiterZeigen(location.hash.slice(1))');
  return {document,run,timer,get anzahl(){return anzahl;},
    fehler(v){fehler=v;},langsam(v){langsam=v;},freigeben(){freigabe();}};
}

(async()=>{
  for(let i=0;i<5;i++) {
    const u=start();await fertig();
    assert.equal(u.run('P.ansicht'),'neu');
    assert.equal(u.document.getElementById('reiter-prompts').hidden,false);
    assert.equal(u.document.getElementById('p-rohprompt').value,'');
    assert.equal(u.timer.length,1);assert.equal(u.anzahl,1);
    assert.equal(u.document.getElementById('p-typen').querySelectorAll('input').length,11);
    keinFremdText(u.document);
  }
  const u=start();await fertig();
  const roh=u.document.getElementById('p-rohprompt');roh.value='Erhaltener Entwurf';await roh.ausloesen('input');
  u.run("reiterZeigen('zusammenfassung');reiterZeigen('prompts')");
  assert.equal(roh.value,'Erhaltener Entwurf');
  u.fehler(true);await u.run('pLaden()');assert.equal(roh.value,'Erhaltener Entwurf');
  assert(u.document.getElementById('p-liste').textContent.includes('Test'));
  u.fehler(false);await u.timer.shift()();assert.equal(roh.value,'Erhaltener Entwurf');
  assert.strictEqual(u.document.getElementById('p-rohprompt'),roh);
  u.langsam(true);const lauf=u.run('pLaden()');await fertig();const anzahl=u.anzahl;
  for(let i=0;i<6;i++) await u.timer.shift()();
  assert.equal(u.anzahl,anzahl);assert(!u.run('P.ladenNachholen'));
  u.langsam(false);u.freigeben();await lauf;
  assert.equal(roh.value,'Erhaltener Entwurf');
  keinFremdText(u.document);
  console.log('Fünf Starts auf #prompts, Wiederkehr, Reiterwechsel und langsamer Index: OK');
})().catch((e)=>{console.error(e);process.exitCode=1;});
