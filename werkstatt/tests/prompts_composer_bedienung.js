'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));
const { dokument: document, Element } = dokumentBauen();
const speicher = new Map(), kopiert = [], anfragen = [], zeitgeber = [];
let uuid = 0, dialog, sendAntwort, postVerloren = false, kontextKonflikt = false, transkription = 0;
const e = { id:'Test',titel:'Eigener Code',herkunft:'ordner',prompt_typ:'code',prompt_typ_gespeichert:true,
  bevorzugt:'Fassung 1',bearbeitbar:true,fassungen:[{name:'Fassung 1',text:'Original [A]',stand:'alt'}],tests:[],schaerfen:[],warteschlange:[] };
const sammlung = Array.from({length:6}, (_,i) => ({id:'sammlung:P'+i+'#1',titel:'Prompt '+i,herkunft:'sammlung',
  abschnitt:'Bereich '+(i+1),abschnitt_reihenfolge:i,reihenfolge:i, fassungen:[{name:'Sammlung',text:'Quellentext '+i,stand:'s'+i}],tests:[],schaerfen:[]}));
const writer = [{id:'api',name:'Claude API',anbieter:'claude',prompts_verfuegbar:false,prompts_grund:'Abo-Anmeldung nicht bestätigt',zugang_text:'API'},
  {id:'abo',name:'Claude · Sonnet',anbieter:'claude',prompts_verfuegbar:true,zugang_text:'Abo',cloud:'Anthropic'},
  {id:'q',name:'Qwen lokal',anbieter:'lokal',prompts_verfuegbar:true,zugang_text:'lokal'}];
const optionen = {...regeln,schreibmodelle:writer,zielprofile:regeln.zielprofile.map((p) => ({...p,varianten:p.anbieter === 'lokal'
  ? [{eintrag:p.eintraege[0],name:p.name,testprofile:[],varianten:[]}]
  : [{testprofil:'abo',name:'Claude · Sonnet'}]}))};
const status = {gefunden:true,vollstaendig:true,id:e.id,auftragsgruppe:'gruppe',ziele:[]};
const window = {scrollTo(){},events:{},addEventListener(k,f){this.events[k]=f;}};
const ctx = vm.createContext({document, window, console, aktualisieren(){}, fehlerMelden(e){throw Error(e);}, crypto:{randomUUID:()=> 'uuid-'+(++uuid)},
  navigator:{clipboard:{writeText:async(t)=>kopiert.push(t)}},
  localStorage:{getItem:(k)=>speicher.get(k)||null,setItem:(k,v)=>speicher.set(k,v)},
  setTimeout(fn,ms){assert.equal(ms,2500);zeitgeber.push(fn);return 1;},
  ablegen(){transkription++;},reiterZeigen(){transkription++;},
  dialogOeffnen(titel, inhalt, knoepfe) { const vorher=document.activeElement; dialog?.remove();dialog=new Element('dialog');dialog.open=true;
    dialog.append(...inhalt,...knoepfe);document.append(dialog);dialog.close=()=>{dialog.remove();vorher?.focus();};return dialog; },
  fetch:async(pfad,opt)=>{
    const d=opt?.body?JSON.parse(opt.body):null;anfragen.push([pfad,d]);
    let wert;
    if(pfad==='/api/prompt-optionen') wert=optionen;
    else if(pfad==='/api/zusammenfassung') wert={auswerter:writer};
    else if(pfad==='/api/prompts') wert={eintraege:[e,...sammlung],fehler:[],warteschlange:[]};
    else if(pfad.startsWith('/api/prompt?id=')) wert=e;
    else if(d?.aktion==='composer_vorschau') wert={ziele:d.ziele.map((z)=>({zielmodell:{name:z.zielprofil},auftrag:'Auftrag '+d.text,gesendet_stand:'hash'})),gesendet_staende:{ziel:'hash'}};
    else if(d?.aktion==='composer_senden') { if(postVerloren) throw Error('Failed to fetch'); if(sendAntwort) await sendAntwort; wert=status; }
    else if(d?.aktion==='composer_status') wert=status;
    else if(d?.aktion==='material_pruefen') wert={materialien:d.materialien.map((m)=>({...m,zeichen:m.wert.length,sha:'serverhash'}))};
    else if(pfad==='/api/prompt-kontexte') wert={kontexte:[{id:'Projekt',titel:'Projektkontext',stand:'v1',zeichen:10}]};
    else if(d?.aktion==='kontext_lesen') wert={id:'Projekt',titel:'Projektkontext',wert:'Sachkontext',stand:'v1'};
    else if(d?.aktion==='kontext_speichern') {
      if(kontextKonflikt) return {ok:false,status:409,json:async()=>({fehler:'Der Kontextbaustein wurde inzwischen geändert, bitte neu laden.'})};
      wert={id:'Projekt',titel:d.titel,wert:d.wert,stand:'v2'};
    }
    else throw Error('Unerwartete Anfrage '+pfad+' '+d?.aktion);
    return {ok:true,json:async()=>wert};
  },
});
const app=fs.readFileSync('werkstatt/web/app.js','utf8');
vm.runInContext(app.split('let STAND =')[0],ctx);
vm.runInContext(app.slice(app.indexOf('function knopf('),app.indexOf('const auftrag =')),ctx);
vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='),app.indexOf('function schrittListe(')),ctx);
vm.runInContext(fs.readFileSync('werkstatt/web/prompts.js','utf8'),ctx);
const run=(s)=>vm.runInContext(s,ctx), $=(s)=>document.querySelector(s);
const knopf=(text,wurzel=document)=>wurzel.querySelectorAll('button').find((b)=>b.textContent===text);
const klick=async(b)=>{assert(b);b.focus();await b.ausloesen('click');};
const input=async(el,text)=>{el.value=text;el.focus();await el.ausloesen('input');};
(async()=>{
  run('window.promptsAktiv(true)'); await new Promise(setImmediate);
  assert.equal(zeitgeber.length,1);
  assert.equal($('#p-schreibmodell').value,'abo');
  assert($('#p-schreibmodell').children[0].disabled);
  assert($('#p-schreibgruende').textContent.includes('Abo-Anmeldung nicht bestätigt'));
  assert.equal($('#p-typen').querySelectorAll('input').length,11);
  assert($('#p-typen').textContent.includes('Passenden Typ aus der Aufgabe bestimmen'));
  assert.equal($('#p-kategorien').querySelectorAll('button').length,8);
  await input($('#p-rohprompt'),'Mein unveröffentlichter Entwurf <script>');
  const roh=$('#p-rohprompt');roh.selectionStart=3;roh.selectionEnd=6;
  await run('pLaden()');assert.strictEqual($('#p-rohprompt'),roh);assert.equal(roh.selectionStart,3);
  run('window.promptsAktiv(false);window.promptsAktiv(true)');
  assert.equal(roh.value,'Mein unveröffentlichter Entwurf <script>');assert.equal(zeitgeber.length,1);
  let verhindert=false;
  await roh.ausloesen('keydown',{key:'Enter',ctrlKey:false,preventDefault(){verhindert=true;}});assert(!verhindert);
  await roh.ausloesen('keydown',{key:'Enter',ctrlKey:true,isComposing:true});
  assert(!anfragen.some(([,d])=>d?.aktion==='composer_senden'));
  $('#p-typmenue').open=true;
  await document.ausloesen('keydown',{key:'Escape'});
  assert(!$('#p-typmenue').open);assert.strictEqual(document.activeElement,$('#p-typmenue').querySelector('summary'));
  await klick(document.querySelector('.p-katalogkarte'));
  assert.equal(run('P.ansicht'),'bibliothek');assert.equal(roh.value,'Mein unveröffentlichter Entwurf <script>');
  assert.deepEqual(JSON.parse(speicher.get('werkstatt.prompt-zuletzt')),[e.id]);
  document.activeElement=null;await run('pLaden()');
  assert.deepEqual(JSON.parse(speicher.get('werkstatt.prompt-zuletzt')),[e.id]);
  await klick(knopf('Neuer Prompt'));
  assert.equal(run('P.ansicht'),'neu');
  run("pTypWaehlen('bild')");assert.equal(run('P.entwurf.ziele[0].zielprofil'),'bild');
  assert($('#p-ziele').textContent.includes('Qwen-Image 2.1'));
  run("pTypWaehlen('code')");assert.equal(run('P.entwurf.ziele[0].zielprofil'),'qwen27');
  document.activeElement=null;await run('pComposerVorschau()');
  assert($('#p-vorschauinhalt').textContent.includes('Mein unveröffentlichter Entwurf'));
  for(const v of speicher.values()) assert(!v.includes('unveröffentlichter') && !v.includes('<script>'));
  let freigabe;sendAntwort=new Promise((r)=>{freigabe=r;});
  const erst=roh.ausloesen('keydown',{key:'Enter',ctrlKey:true}); await new Promise(setImmediate);
  await run('pComposerSenden()');
  assert.equal(anfragen.filter(([,d])=>d?.aktion==='composer_senden').length,1);
  assert($('#p-senden').disabled);freigabe();await erst;sendAntwort=null;
  assert.equal(run('P.letzteGruppe'),'gruppe');assert.equal(roh.value,'');
  await klick(knopf('Neuer Prompt'));await input(roh,'Verbindung verloren');
  postVerloren=true;document.activeElement=null;await run('pComposerSenden()');
  assert($('#p-composer-status').textContent.includes('Die Bestätigung fehlt.'));
  run('pComposerZusammenfassung()');assert($('#p-composer-status').textContent.includes('Die Bestätigung fehlt.'));
  const anfrage=run('P.sendung.daten.anfrage_id');
  const vorher=anfragen.filter(([,d])=>d?.aktion==='composer_senden').length;
  await run('pComposerSenden()');assert.equal(anfragen.filter(([,d])=>d?.aktion==='composer_senden').length,vorher);
  await klick(knopf('Status prüfen'));assert.equal(anfragen.at(-2)[1].anfrage_id,anfrage);
  assert.equal(run('P.sendung'),null);postVerloren=false;
  const box=new Element('div');ctx.box=box;ctx.b={original:'Nur Original [A]',neue_fassung:'Nur neu [A]',stichpunkte:'- Erläuterung',neue_platzhalter:[]};
  run('pSchaerfenErgebnis(box,b)');await klick(knopf('Original kopieren',box));await klick(knopf('Neue Fassung kopieren',box));
  assert.deepEqual(kopiert,['Nur Original [A]','Nur neu [A]']);
  ctx.e=e;ctx.beleg={datei:'Ergebnis.md',zustand:'fertig'};
  ctx.b={...ctx.b,aktion:'Schärfen',fassung:'Fassung 1',fassung_stand:'alt',zielschluessel:'qwen27:qwen27-unsloth',
    zielprofil_id:'qwen27',testprofil_id:null,auswerter:'Claude · Sonnet',typ_anzeige:'Typ nicht erkannt',
    eingaben:{bau_version:2,typ:{id:'auto',name:'Auto'},modus:{id:'prompt'},hinweise:'Übernommener Hinweis',aktion:'Schärfen',materialien:[],kontexte:[]}};
  run('pSchaerfenErgebnis(box,b,e,beleg)');assert(box.textContent.includes('Typ nicht erkannt'));
  const vorNochmal=uuid;const aufrufeVorNochmal=anfragen.length;
  await klick(knopf('Nochmal …',box));
  assert.equal(uuid,vorNochmal);assert.equal(anfragen.length,aufrufeVorNochmal);
  assert.equal(run('P.entwurf.text'),ctx.b.original);assert.equal(run('P.entwurf.basis.stand'),'alt');assert(roh.readOnly);
  ctx.beleg.zustand='laeuft';run('pSchaerfenErgebnis(box,b,e,beleg)');assert(!knopf('Nochmal …',box));
  ctx.beleg.zustand='fertig';ctx.b.zielprofil_id='bild';run('pSchaerfenErgebnis(box,b,e,beleg)');
  assert(!knopf('Testen …',box));assert(box.textContent.includes('Im Reiter Bild & Video verwenden.'));
  ctx.b.zielprofil_id='qwen27';ctx.b.grund='kein Kasten';ctx.b.antwort='Vollständige ungültige Antwort';
  run('pSchaerfenErgebnis(box,b,e,beleg)');assert(!knopf('Neue Fassung kopieren',box));assert(!knopf('Testen …',box));
  assert(box.textContent.includes('Vollständige ungültige Antwort'));delete ctx.b.grund;
  speicher.set('werkstatt.prompt-auswerter','["abo"]');
  await run('pTestdialog(e,"Fassung 1",null,{testprofil:null})');
  assert(dialog.textContent.includes('kein verfügbares Testprofil'));
  assert.equal(dialog.querySelectorAll('input[type="checkbox"]').filter((c)=>c.checked).length,1);
  dialog.close();
  ctx.sammlungseintrag={...e,herkunft:'sammlung'};
  run('pSchaerfenErgebnis(box,b,sammlungseintrag,beleg)');await klick(knopf('Testen …',box));
  assert(dialog.textContent.includes('schreibgeschützte Testfassung'));assert(dialog.textContent.includes(ctx.b.neue_fassung));dialog.close();
  await run('pMaterialBrowserHinzufuegen([{name:"Browser.txt",size:8,text:async()=>"Material"}])');
  const m=run('P.entwurf.materialien[0]');assert.equal(m.name,'Browser.txt');assert(!('pfad' in m));
  assert.equal(m.sha,'serverhash');assert($('#p-material-hinweis').textContent.includes('mitgesendet'));
  const vorschauVorher=run('JSON.stringify(pComposerDaten())');
  await klick(knopf('Browser.txt · 8 Zeichen · Entfernen'));
  assert.notEqual(run('JSON.stringify(pComposerDaten())'),vorschauVorher);
  await assert.rejects(run('pMaterialBrowserHinzufuegen([{name:"Bild.png",text:async()=>{throw Error("Darf nicht gelesen werden");}}])'),/Bitte eine Textdatei/);
  await run('pKontexteZeigen(true)');
  const cb=dialog.querySelector('input');assert(!cb.checked);cb.checked=true;await cb.ausloesen('change');
  assert.equal(run('P.entwurf.kontexte[0].id'),'Projekt');
  assert(!anfragen.some(([,d])=>d?.aktion==='kontext_lesen'));
  assert($('#p-chips').textContent.includes('Projektkontext'));
  await klick(knopf('Bearbeiten …',dialog));
  const editor=$('#p-kontext-text');await input(editor,'Eigene Änderung');kontextKonflikt=true;
  await klick(knopf('Speichern',dialog));assert.equal(editor.value,'Eigene Änderung');
  assert(dialog.textContent.includes('inzwischen geändert'));dialog.close();
  await klick(knopf('Projektkontext · Kontext entfernen'));assert.equal(run('P.entwurf.kontexte.length'),0);
  for(const id of ['ueberall','ablage','te-ablage','reiter-transkription','reiter-texterkennung']) {
    const el=new Element('div');el.id=id;el.hidden=true;document.append(el);
  }
  vm.runInContext(app.slice(app.indexOf('function einrichtenAblegen('),app.indexOf('// ------------------------------------------------------------------ Kopf')),ctx);
  run('einrichtenAblegen()');
  const dataTransfer={types:['Files'],items:[],files:[{name:'Nicht erlaubt.pdf',text:async()=> 'Verbotener Anhang'}]};
  await document.ausloesen('drop',{target:$('#p-rohprompt'),dataTransfer});await new Promise(setImmediate);
  assert.equal(transkription,0);assert($('#p-rueck').textContent.includes('Bitte eine Textdatei'));
  dataTransfer.files=[{name:'Drop.txt',size:4,text:async()=> 'Drop'}];
  await document.ausloesen('drop',{target:$('#p-rohprompt'),dataTransfer});await new Promise(setImmediate);
  assert.equal(transkription,0);assert.equal(run('P.entwurf.materialien[0].wert'),'Drop');
  const testfeld=new Element('textarea');testfeld.setAttribute('data-prompt-feld','A');testfeld.promptEingabe={};document.append(testfeld);
  await document.ausloesen('drop',{target:testfeld,dataTransfer});await new Promise(setImmediate);
  assert.equal(testfeld.value,'Drop');assert.equal(testfeld.promptEingabe.quelle.art,'text');
  assert.equal(transkription,0);
  e.prompt_typ='bild';document.activeElement=null;run('P.inhaltStand=null');await run('pWaehlen(e.id,false)');
  assert(!knopf('Testen …',$('#p-inhalt')));assert($('#p-inhalt').textContent.includes('Im Reiter Bild & Video verwenden.'));
  delete e.prompt_typ;
  keinFremdText(document);keinFremdText(box);
  assert(!fs.readFileSync('werkstatt/web/prompts.js','utf8').includes('innerHTML'));
  assert.equal((fs.readFileSync('werkstatt/web/prompts.js','utf8').match(/setTimeout\(/g)||[]).length,1);
  // Nur fetch-Netzfehler werden übersetzt. HTTP-Fehler behalten die konkrete Meldung.
  ctx.fetch=async()=>({ok:false,status:409,json:async()=>({fehler:'Der Stand wurde geändert.'})});
  await assert.rejects(run("api('/api/prompt',{})"),/Der Stand wurde geändert/);
  ctx.fetch=async()=>{throw Error('Failed to fetch');};
  await assert.rejects(run("api('/api/prompts')"),/Die Werkstatt antwortet gerade nicht/);
  console.log('Composer, Katalog, Fokus, Tastatur, Idempotenz, Textmaterial, Kontexte, Drop, Kopieren und Netzfehler: OK');
})().catch((e)=>{console.error(e);process.exitCode=1;});
