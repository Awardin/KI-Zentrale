'use strict';

// Echtes Prompts-Skript mit DOM und Fake-HTTP: keine Dienste, Modelle oder Zeitgeber.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { dokumentBauen, keinFremdText } = require('./dom_nachbau');
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
const code = fs.readFileSync('werkstatt/web/prompts.js', 'utf8');
const css = fs.readFileSync('werkstatt/web/style.css', 'utf8');
const regeln = JSON.parse(fs.readFileSync('werkstatt/tests/werkstatt-profile.json', 'utf8'));

async function starten() {
  const { dokument: document, Element } = dokumentBauen();
  const anfragen = [];
  const e = { id: 'Eintrag', titel: 'Anzeigeprüfung', herkunft: 'ordner', bearbeitbar: true,
    fassungen: [{ name: 'Fassung 1', text: 'Testtext', stand: 'stand' }], tests: [], schaerfen: [], warteschlange: [] };
  const optionen = { ...regeln, schreibmodelle: [
    { id: 'eins', name: 'Modell Eins', prompts_verfuegbar: true },
    { id: 'zwei', name: 'Modell Zwei', prompts_verfuegbar: true },
  ], zielprofile: regeln.zielprofile.map((p) => ({ ...p, varianten: [] })) };
  const ctx = vm.createContext({ document, console, aktualisieren() {}, fehlerMelden(text) { throw Error(text); },
    window: { addEventListener() {}, scrollTo() {} },
    localStorage: { getItem() { return null; }, setItem() {} },
    setTimeout() { throw Error('Keine neuen Zeitgeber für die Anzeige.'); },
    setInterval() { throw Error('Keine neuen Zeitgeber für die Anzeige.'); },
    fetch: async (pfad, opt) => {
      const daten = opt?.body ? JSON.parse(opt.body) : null;
      anfragen.push([pfad, daten]);
      let wert;
      if (pfad === '/api/prompt-optionen') wert = optionen;
      else if (pfad.startsWith('/api/prompt?id=')) wert = e;
      else if (pfad === '/api/prompts') wert = { eintraege: [e], warteschlange: e.warteschlange, fehler: [] };
      else if (pfad === '/api/fassung' || daten?.aktion === 'oeffnen') wert = { ok: true };
      else throw Error('Unerwartete Fake-Anfrage: ' + pfad);
      return { ok: true, json: async () => JSON.parse(JSON.stringify(wert)) };
    },
  });
  vm.runInContext(app.split('let STAND =')[0], ctx);
  vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), ctx);
  vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='), app.indexOf('function schrittListe(')), ctx);
  vm.runInContext(code, ctx);
  const run = (text) => vm.runInContext(text, ctx);
  const $ = (s) => document.querySelector(s);
  const ereignis = (type, target, extra = {}) => document.ausloesen(type, { target, ...extra });
  const fokus = async (target) => { target.focus(); await ereignis('focusin', target); };
  const druecken = async (target) => {
    let verhindert = false;
    await ereignis('pointerdown', target, { preventDefault() { verhindert = true; }, pointerType: 'touch' });
    assert(!verhindert, 'Außenklick darf die normale Bedienung nicht verhindern');
    await fokus(target);
    if (target.tag === 'summary') {
      const d = target.parentElement; d.open = !d.open;
      await ereignis('toggle', d);
    } else await target.ausloesen('click');
  };
  run('pComposerZeigen()');
  await run('pOptionenLaden()');
  return { document, Element, ctx, e, anfragen, run, $, ereignis, fokus, druecken };
}

async function menues() {
  const u = await starten();
  const schreiben = u.$('#p-schreibmenue'), typ = u.$('#p-typmenue');
  const roh = u.$('#p-rohprompt');
  const aktion = new u.Element('button');
  let geklickt = 0; aktion.addEventListener('click', () => geklickt++);
  u.$('#reiter-prompts').append(aktion);
  const pruefeHandler = () => {
    for (const art of ['pointerdown', 'focusin', 'toggle']) assert.equal(u.document.events[art].length, 1);
    assert.strictEqual(u.document.events.pointerdown[0], u.document.events.focusin[0]);
    assert.strictEqual(u.document.events.pointerdown[0], u.document.events.toggle[0]);
  };
  pruefeHandler();
  await u.druecken(schreiben.querySelector('summary')); assert(schreiben.open);
  await u.druecken(roh); assert(!schreiben.open); assert.strictEqual(u.document.activeElement, roh);
  await u.druecken(schreiben.querySelector('summary'));
  await u.druecken(aktion); assert(!schreiben.open); assert.equal(geklickt, 1);
  await u.druecken(schreiben.querySelector('summary'));
  await u.ereignis('pointerdown', u.$('#reiter-prompts')); assert(!schreiben.open);
  for (let i = 0; i < 3; i++) {
    await u.druecken(schreiben.querySelector('summary'));
    const cb = u.$('#p-schreibmodelle').querySelector('input[value="zwei"]');
    await u.druecken(cb); cb.checked = !cb.checked; await cb.ausloesen('change');
    assert(schreiben.open, 'Auswahl mit Neuzeichnen bleibt offen');
    await u.ereignis('pointerdown', u.$('#p-schreibmodelle')); // Scrollbereich und Scrollbar
    await u.ereignis('pointerdown', u.$('#p-schreibmodelle').querySelector('span'));
    assert(schreiben.open);
    await u.fokus(schreiben.querySelector('summary')); assert(schreiben.open);
    await u.fokus(aktion); assert(!schreiben.open, 'Tab hinaus schließt das Menü');
    u.run('pComposerZeigen()'); pruefeHandler();
  }
  await u.druecken(schreiben.querySelector('summary'));
  await u.druecken(schreiben.querySelector('summary')); assert(!schreiben.open, 'Kopfzeile schaltet weiter zu');
  // Auch Öffnen mit Tastatur/nativem toggle (ohne pointerdown) schließt die anderen.
  schreiben.open = true; await u.ereignis('toggle', schreiben);
  typ.open = true; await u.ereignis('toggle', typ); assert(!schreiben.open); assert(typ.open);
  await u.druecken(typ.querySelector('summary')); assert(!typ.open);
  await u.run("pWaehlen('Eintrag')");
  const menues = u.$('#p-inhalt').querySelectorAll('.p-schaerfen-menue');
  assert.equal(menues.length, 2);
  const taste = (m) => m.parentElement.querySelector('button');
  // Keyboard-Klick ohne Fokuswechsel muss ebenfalls die Einzelauswahl wahren.
  schreiben.open = true; await u.ereignis('toggle', schreiben);
  await taste(menues[0]).ausloesen('click'); assert(!schreiben.open); assert(!menues[0].hidden);
  await u.ereignis('pointerdown', menues[0].querySelector('button'));
  await u.fokus(menues[0].querySelector('button')); assert(!menues[0].hidden);
  await taste(menues[1]).ausloesen('click'); assert(menues[0].hidden); assert(!menues[1].hidden);
  assert.equal(taste(menues[0]).getAttribute('aria-expanded'), 'false');
  assert.equal(taste(menues[1]).getAttribute('aria-expanded'), 'true');
  await u.druecken(taste(menues[1])); assert(menues[1].hidden, 'Schärfen-Knopf schaltet weiter zu');
  await u.druecken(taste(menues[1]));
  await u.fokus(aktion); assert(menues[1].hidden);
  await u.druecken(taste(menues[0]));
  await u.druecken(aktion); assert(menues[0].hidden); assert.equal(geklickt, 2);
  await u.druecken(taste(menues[0]));
  typ.open = true; await u.ereignis('toggle', typ); assert(menues[0].hidden);
  // Bestehendes Escape einschließlich Dialogschutz und Fokusrückgabe.
  let verhindert = 0;
  const escape = () => u.ereignis('keydown', u.document.activeElement, { key: 'Escape', preventDefault() { verhindert++; } });
  await escape(); assert(!typ.open); assert.strictEqual(u.document.activeElement, typ.querySelector('summary'));
  await u.druecken(taste(menues[0]));
  const dialog = new u.Element('dialog'); dialog.open = true; u.document.append(dialog);
  await escape(); assert(!menues[0].hidden); assert.equal(verhindert, 1);
  dialog.remove(); await escape(); assert(menues[0].hidden); assert.equal(verhindert, 2);
  assert.strictEqual(u.document.activeElement, taste(menues[0]));
  // Der Eintrag samt Menüs wird ersetzt; die Dokument-Handler bleiben dieselben.
  u.e.titel = 'Neu gezeichnet'; u.document.activeElement = null;
  await u.run("pWaehlen('Eintrag', false)"); pruefeHandler();
  const neu = u.$('.p-schaerfen-menue'); assert.notStrictEqual(neu, menues[0]);
  await u.druecken(taste(neu)); await u.ereignis('pointerdown', roh); assert(neu.hidden);
  keinFremdText(u.document);
}

function pruefeLauf(karte, zustand, zeit = '') {
  const status = karte.querySelector('[role="status"]');
  assert(status, 'Laufzeile fehlt');
  assert.equal(status.getAttribute('data-zustand'), zustand);
  assert.equal(status.textContent, zustand === 'wartet' ? 'Wartet auf den Start …'
    : `Läuft${zeit ? ` seit ${zeit}` : ''} – das Modell arbeitet noch …`);
  assert(!status.textContent.includes('offen'));
  const balken = karte.querySelector('.balken');
  if (zustand === 'laeuft') {
    assert(balken); assert(balken.className.split(' ').includes('offen'));
    assert.equal(balken.getAttribute('aria-hidden'), 'true'); assert(balken.querySelector('i'));
  } else assert(!balken, 'Wartende Läufe haben keinen Balken');
}

async function laufanzeige() {
  const u = await starten();
  const erstellt = '2026-11-10 08:12:00';
  const beginn = new Date(2026, 10, 10, 15, 37).getTime() / 1000;
  const s = { datei: 'S.md', zustand: 'wartet', erstellt, fassung: 'Fassung 1', auswerter: 'Schreibmodell',
    zielmodell: 'Zielmodell', aktion: 'Schärfen', ergebnis: 'offen' };
  const t = { ...s, datei: 'T.md', auswerter: 'Testmodell', urteil: 'offen' };
  const auftrag = (b, art) => ({ id: art, art, zustand: b.zustand, begonnen: beginn, auswerter: { name: b.auswerter },
    prompt: { eintrag: u.e.id, beleg: b.datei.slice(0, -3), fassung: b.fassung } });
  u.e.tests = [t]; u.e.schaerfen = [s];
  u.e.auftragsgruppen = [{ id: 'gruppe', ergebnisse: [s] }];
  // Die bisherige Gruppenkarte wird als Vergleich innerhalb der Arbeitsfläche geprüft.
  u.run("P.af.Eintrag={runde:'gruppe',lauf:'S.md',bewusst:true,vergleich:true,reiter:'Fragen'}");
  u.e.warteschlange = [auftrag(s, 'schaerfen'), auftrag(t, 'prompt')];
  // Ein fremder Beleg mit gleichem Dateinamen darf nicht als Startzeit dienen.
  u.e.warteschlange.unshift({ ...auftrag(s, 'schaerfen'), begonnen: 0, prompt: { eintrag: 'Fremd', beleg: 'S' } });
  const karteMit = (text) => u.$('#p-inhalt').querySelectorAll('article').find((k) => k.textContent.includes(text));
  for (const zustand of ['wartet', 'laeuft']) {
    s.zustand = t.zustand = zustand;
    u.e.warteschlange.forEach((a) => { a.zustand = zustand; });
    await u.run("pWaehlen('Eintrag', false)");
    assert.equal(u.$('#p-rueck').textContent, '');
    const karten = [u.$('.p-ergebnisgruppe').querySelector('article'), karteMit('Ergebnis anzeigen'),
      karteMit('Antwort anzeigen'), ...u.$('#p-inhalt').querySelectorAll('article').filter((k) => k.textContent.includes('Abbrechen') && !k.querySelector('h5'))];
    assert.equal(karten.length, 5, 'Gruppe, Schärfen, Test und beide Warteschlangeneinträge');
    for (const k of karten) pruefeLauf(k, zustand, '15:37');
    assert(!karten[0].textContent.includes('offen')); assert(!karten[1].textContent.includes('offen'));
    assert(karten[0].textContent.includes('Schärfen-Beleg öffnen'));
    assert(karten[0].textContent.includes('Abbrechen'));
  }
  // Die neu gelieferte Startzeit muss auch ohne Zustandswechsel neu gezeichnet werden.
  u.e.warteschlange.filter((a) => a.prompt.eintrag === u.e.id).forEach((a) => { a.begonnen += 60; });
  await u.run("pWaehlen('Eintrag', false)");
  for (const status of u.$('#p-inhalt').querySelectorAll('[role="status"]')) assert(status.textContent.includes('15:38'));
  // Belegzeit bei fehlendem begonnen; keine Uhrzeit bei fehlenden/ungültigen Daten.
  for (const [datum, zeit] of [[erstellt, '08:12'], [undefined, ''], ['unbekannt', '']]) {
    s.erstellt = t.erstellt = datum;
    u.e.warteschlange.forEach((a) => { delete a.begonnen; });
    await u.run("pWaehlen('Eintrag', false)");
    for (const k of u.$('#p-inhalt').querySelectorAll('article').filter((k) => k.querySelector('[role="status"]'))) pruefeLauf(k, 'laeuft', zeit);
  }
  // Ohne Warteschlange greift der gemeinsame Renderer ebenfalls auf den Beleg zurück.
  u.e.warteschlange = []; s.erstellt = t.erstellt = erstellt;
  await u.run("pWaehlen('Eintrag', false)");
  for (const k of u.$('#p-inhalt').querySelectorAll('article').filter((k) => k.querySelector('[role="status"]'))) pruefeLauf(k, 'laeuft', '08:12');
  // Fertige und abgebrochene/fehlgeschlagene Belege behalten ihre bisherige Anzeige.
  for (const [zustand, text] of [['fertig', 'Fertig'], ['fehler', 'Fehlgeschlagen'], ['abgebrochen', 'Abgebrochen']]) {
    s.zustand = t.zustand = zustand; s.dauer_s = 29; s.tokens = 8286; s.ergebnis = 'übernommen (Fassung 2)';
    u.e.warteschlange = [auftrag(s, 'schaerfen'), auftrag(t, 'prompt')];
    await u.run("pWaehlen('Eintrag', false)");
    assert.equal(u.$('#p-inhalt').querySelectorAll('[role="status"]').length, 0);
    assert.equal(u.$('#p-inhalt').querySelectorAll('.balken').length, 0);
    assert(u.$('.p-ergebnisgruppe').textContent.includes(`${text} · 29 s · 8286 Token · übernommen (Fassung 2)`));
    assert(karteMit('Ergebnis anzeigen').textContent.includes(`${text} · übernommen (Fassung 2)`));
    assert(karteMit('Antwort anzeigen').textContent.includes(text));
    if (zustand !== 'fertig') assert(u.$('#p-inhalt').querySelectorAll('article').some((k) => k.textContent.includes(`Fassung 1 · Testmodell · ${text}`)));
  }
  // Öffnen und Abbrechen bleiben echte Aktionen an denselben Ergebniskarten.
  s.zustand = 'laeuft'; u.e.warteschlange = [auftrag(s, 'schaerfen')];
  await u.run("pWaehlen('Eintrag', false)");
  const gruppe = u.$('.p-ergebnisgruppe');
  await gruppe.querySelectorAll('button').find((b) => b.textContent === 'Schärfen-Beleg öffnen').ausloesen('click');
  assert(u.anfragen.some(([p, d]) => p === '/api/prompt' && d.aktion === 'oeffnen' && d.datei === 'S.md'));
  await gruppe.querySelectorAll('button').find((b) => b.textContent === 'Abbrechen').ausloesen('click');
  assert(u.anfragen.some(([p, d]) => p === '/api/fassung' && d.aktion === 'abbrechen' && d.id === 'schaerfen'));
  // Animationen verwenden die bestehenden Regeln; deren globale Reduktionsregel gilt auch hier.
  assert(css.includes('.p-laufzeile[data-zustand="laeuft"]::before { animation: puls 1.2s ease-in-out infinite; }'));
  assert(css.includes('.balken.offen i { width: 30% !important; animation: laufen 1.4s ease-in-out infinite; }'));
  assert(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before \{ animation: none !important; transition: none !important; \}/.test(css));
  assert.equal((code.match(/setTimeout\(/g) || []).length, 1); assert(!code.includes('setInterval('));
  keinFremdText(u.document);
}

(async () => {
  await menues(); await laufanzeige();
  console.log('Außenklick, Fokus, Menüwechsel, Neuzeichnen, Escape und Laufanzeigen in allen vier Ansichten: OK');
})().catch((err) => { console.error(err); process.exitCode = 1; });
