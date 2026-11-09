'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');
const { dokument: document, Element } = dokumentBauen();
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));
const grund = 'Abo-Anmeldung nicht bestätigt';
const profile = [
  {id:'writer',name:'Claude · Sonnet',zugang_text:'Abo',prompts_verfuegbar:true,anbieter:'claude'},
  {id:'api',name:'OpenAI/Codex · Unbekanntes Format · '+grund,zugang_text:grund,prompts_grund:grund,prompts_verfuegbar:false},
  {id:'iq3',name:'Qwen IQ3',zugang_text:'lokal',prompts_grund:'Das Modell ist nicht geladen.',prompts_verfuegbar:false},
  {id:'off',name:'Ungewähltes Profil',zugang_text:'API',prompts_grund:'Nicht verfügbar.',prompts_verfuegbar:false},
];
const optionen = {...regeln,schreibmodelle:profile,zielprofile:regeln.zielprofile.map((p)=>({...p,
  varianten:p.anbieter==='lokal'?[{eintrag:p.eintraege[0],name:p.name,testprofile:p.id==='qwen27'?[profile[2]]:[],varianten:[]}]
    :[{name:'Claude',testprofil:'writer'},{name:'Problemprofil',testprofil:'api'}]}))};
const eintrag = {id:'Test',titel:'Schreibe mir eine kurze Checkliste, wie ich einen sehr langen Titel innerhalb der linken Spalte lesen kann.',
  herkunft:'ordner',prompt_typ:'auto',prompt_typ_gespeichert:true,fassungen:[{name:'Fassung 1',text:'Original',stand:'s'}],tests:[],schaerfen:[],warteschlange:[]};
const anfragen = [];
const ctx = vm.createContext({document,window:{addEventListener(){},scrollTo(){}},console,
  aktualisieren(){},fehlerMelden(t){throw Error(t);},localStorage:{getItem(){return null;},setItem(){}},
  fetch:async(pfad,opt)=>{
    const d=opt?.body?JSON.parse(opt.body):null;anfragen.push([pfad,d]);
    let wert;
    if(pfad==='/api/prompt-optionen') wert=optionen;
    else if(pfad==='/api/zusammenfassung') wert={auswerter:profile};
    else if(pfad==='/api/prompts') wert={eintraege:[eintrag],fehler:[],warteschlange:[]};
    else if(pfad.startsWith('/api/prompt?id=')) wert=eintrag;
    else if(pfad==='/api/fassung'||d?.aktion==='wiederholen_beleg') wert={ok:true};
    else throw Error('Unerwartete Anfrage '+pfad);
    return {ok:true,json:async()=>wert};
  },
  dialogOeffnen(titel,inhalt,knoepfe){const d=new Element('dialog');d.append(...inhalt,...knoepfe);document.append(d);d.open=true;d.close=()=>d.remove();return d;},
});
const app=fs.readFileSync('werkstatt/web/app.js','utf8');
vm.runInContext(app.split('let STAND =')[0],ctx);
vm.runInContext(app.slice(app.indexOf('function knopf('),app.indexOf('const auftrag =')),ctx);
vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='),app.indexOf('function schrittListe(')),ctx);
vm.runInContext(fs.readFileSync('werkstatt/web/prompts.js','utf8'),ctx);
const run=(s)=>vm.runInContext(s,ctx), $=(s)=>document.querySelector(s);
const knopf=(box,text)=>box.querySelectorAll('button').find((b)=>b.textContent===text);
const klicken=async(b)=>{assert(b);b.focus();await b.ausloesen('click');};
ctx.eintrag=eintrag;
(async()=>{
  run('pComposerZeigen()');await run('pOptionenLaden()');await run('pLaden()');
  run('P.zuletzt=[eintrag.id];pZuletztZeichnen()');
  const zuletzt=$('#p-zuletzt button');assert.equal(zuletzt.title,eintrag.titel);
  assert.equal(zuletzt.querySelector('.p-zuletzt-titel').textContent,eintrag.titel);
  // Die fünf Zustände verwenden die vorhandenen Queue-/Belegaktionen am konkreten Ziel.
  for(const zustand of ['fehler','abgebrochen','wartet','laeuft','fertig']) {
    const beleg={datei:'Ziel.md',zielmodell:'Qwen',zustand};
    eintrag.warteschlange=[{id:'zielauftrag',art:'schaerfen',zustand,prompt:{eintrag:eintrag.id,beleg:'Ziel'}}];
    const box=new Element('section');ctx.box=box;ctx.gruppe={ergebnisse:[beleg]};
    await run('pGruppeZeichnen(box,eintrag,gruppe)');
    const aktiv=['wartet','laeuft'].includes(zustand);
    const name=aktiv?'Abbrechen':'Wiederholen';
    if(zustand==='fertig') { assert(!knopf(box,'Wiederholen'));assert(!knopf(box,'Abbrechen'));continue; }
    await klicken(knopf(box,name));
    const gesendet=anfragen.findLast(([p])=>p==='/api/fassung')[1];
    assert.deepEqual(gesendet,{id:'zielauftrag',aktion:aktiv?'abbrechen':'wiederholen'});
    assert(!knopf(box,aktiv?'Wiederholen':'Abbrechen'));
  }
  eintrag.warteschlange=[];
  for(const zustand of ['fehler','abgebrochen']) {
    ctx.box=new Element('section');ctx.gruppe={ergebnisse:[{datei:'Verwaist.md',zielmodell:'Qwen',zustand,verwaist:true}]};
    await run('pGruppeZeichnen(box,eintrag,gruppe)');await klicken(knopf(ctx.box,'Wiederholen'));
    assert.deepEqual(anfragen.findLast(([,d])=>d?.aktion==='wiederholen_beleg')[1],
      {aktion:'wiederholen_beleg',id:eintrag.id,datei:'Verwaist.md',art_ordner:'schaerfen'});
  }
  // Neuere ungültige Belege und reine Rückfragen verdrängen keinen gültigen Typ.
  const header=JSON.stringify({prompt_typ:eintrag.prompt_typ,prompt_typ_gespeichert:eintrag.prompt_typ_gespeichert});
  eintrag.schaerfen=[
    {datei:'Alt.md',erstellt:'2026-11-08 10:00:00',ergebnis_gueltig:true,prompt_typ_erkannt:'wissen'},
    {datei:'Neu (2).md',erstellt:'2026-11-08 11:00:00',ergebnis_gueltig:true,prompt_typ_erkannt:'code'},
    {datei:'Ungültig.md',erstellt:'2026-11-08 12:00:00',ergebnis_gueltig:false,prompt_typ_erkannt:'planung'},
  ];
  run('pEntdeckenZeichnen()');
  assert($('#p-karten').querySelector('h3'), $('#p-karten').textContent + ' / ' + $('#p-rueck').textContent);
  assert($('#p-karten').querySelector('h3').textContent==='Code');
  assert(!$('#p-karten').textContent.includes('Auto'));
  assert.equal($('#p-karten').querySelector('small').textContent,'Eigener Prompt · Code');
  eintrag.schaerfen.push({datei:'Neuster.md',erstellt:'2026-11-08 13:00:00',ergebnis_gueltig:true,prompt_typ_erkannt:null});
  run('pEntdeckenZeichnen()');assert.equal($('#p-karten').querySelector('h3').textContent,'Weitere Prompts');
  eintrag.schaerfen=[];run('pEntdeckenZeichnen()');assert.equal($('#p-karten').querySelector('h3').textContent,'Weitere Prompts');
  assert.equal(JSON.stringify({prompt_typ:eintrag.prompt_typ,prompt_typ_gespeichert:eintrag.prompt_typ_gespeichert}),header);
  assert(!anfragen.some(([,d])=>d?.aktion==='kopf'));
  // Nur gewählte Problemprofile stehen offen, die vollständige Liste startet eingeklappt.
  run('pComposerZusammenfassung()');
  const box=$('#p-schreibgruende');const offeneProbleme=()=>box.children.filter((el)=>el.tag==='p').map((el)=>el.textContent);
  assert.deepEqual(offeneProbleme(),['Qwen IQ3 · Das Modell ist nicht geladen.']);
  assert.equal(box.querySelector('summary').textContent,'Nicht verfügbare Modelle (3)');assert(!box.querySelector('details').open);
  assert(box.querySelector('details').textContent.includes('Ungewähltes Profil'));
  const qwen=$('#p-ziele').querySelectorAll('input').find((el)=>el.getAttribute('aria-label')==='Qwen 27B (lokal)');
  qwen.checked=false;await qwen.ausloesen('change');assert.deepEqual(offeneProbleme(),[]);
  const claude=$('#p-ziele').querySelectorAll('input').find((el)=>el.getAttribute('aria-label')==='Claude');
  claude.checked=true;await claude.ausloesen('change');
  const ziel=$('#p-ziele').querySelectorAll('select').find((el)=>el.getAttribute('aria-label')==='Variante für Claude');
  ziel.value='api';await ziel.ausloesen('change');
  assert.equal(offeneProbleme().length,1);assert(offeneProbleme()[0].startsWith('OpenAI/Codex'));
  box.querySelector('details').open=true;
  ziel.value='writer';await ziel.ausloesen('change');assert.deepEqual(offeneProbleme(),[]);assert(box.querySelector('details').open);
  run("pSchreibmodelleSetzen(['api']);pSchreibmodelleZeichnen();pComposerZusammenfassung()");assert.equal(offeneProbleme().length,1);
  for(const el of [$('#p-schreibmodelle').querySelector('input[value="api"]').parentElement,...box.querySelectorAll('p')]) {
    assert((el.textContent.match(/Abo-Anmeldung nicht bestätigt/g)||[]).length<=1);
  }
  const dialogProfile={...eintrag,bevorzugt:'Fassung 1'};ctx.dialogProfile=dialogProfile;
  await run('pSchaerfendialog(dialogProfile)');
  const dialog=document.querySelector('dialog[open]');
  for(const el of dialog.querySelectorAll('option')) assert((el.textContent.match(/Abo-Anmeldung nicht bestätigt/g)||[]).length<=1);
  dialog.close();
  await run('pTestdialog(dialogProfile)');
  for(const el of document.querySelector('dialog[open]').querySelectorAll('label')) assert((el.textContent.match(/Abo-Anmeldung nicht bestätigt/g)||[]).length<=1);
  keinFremdText(document);
  console.log('Fixrunde 1: Zuletzt, Zielaktionen, Auto-Katalog, Auswahlprobleme und Beschriftungen OK');
})().catch((e)=>{console.error(e);process.exitCode=1;});
