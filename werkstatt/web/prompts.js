'use strict';

// Ablage und Suche. Die gemeinsame Wissenssammlung bleibt schreibgeschützt.
const P = { eintraege: [], gewaehlt: null, anfrage: 0 };

function pFehler(err) { $('#p-rueck').textContent = err.message; }

function pGeschuetzt() {
  return !!document.querySelector('dialog[open]')
    || !!document.activeElement?.matches('#p-inhalt textarea, #p-inhalt input');
}

function pLaeuft() {
  const aktiv = (a) => a.zustand === 'wartet' || a.zustand === 'laeuft';
  return (P.warteschlange || []).some(aktiv)
    || ['tests', 'schaerfen'].some((art) => (P.eintraege.find((e) => e.id === P.gewaehlt)?.[art] || []).some(aktiv));
}

function pLadenFaellig() {
  return P.letztesLaden == null || pLaeuft() || Date.now() - P.letztesLaden >= 30000;
}

async function pLaden() {
  if (pGeschuetzt()) return;
  P.letztesLaden = Date.now();
  try {
    const d = await api('/api/prompts');
    if (pGeschuetzt()) return;
    P.eintraege = d.eintraege;
    P.warteschlange = d.warteschlange || [];
    $('#p-rueck').textContent = d.fehler.join(' · ');
    pListe();
    if (P.gewaehlt) await pWaehlen(P.gewaehlt);
  } catch (err) { pFehler(err); }
}

function pListe() {
  if (pGeschuetzt()) return;
  const suche = $('#p-suche').value.toLocaleLowerCase('de');
  const herkunft = $('#p-herkunft').value;
  const status = $('#p-status').value;
  const liste = P.eintraege.filter((e) => (!herkunft || e.herkunft === herkunft)
    && (!status || e.getestet === (status === 'getestet'))
    && [e.titel, e.schlagworte, e.quelle, ...e.fassungen.map((f) => f.text)]
      .join('\n').toLocaleLowerCase('de').includes(suche));
  const stand = JSON.stringify([P.gewaehlt, liste.map((e) => ({ id: e.id, titel: e.titel,
    herkunft: e.herkunft, getestet: e.getestet, fehler: e.fehler }))]);
  if (stand === P.listeStand) return;
  const box = $('#p-liste');
  const oben = box.scrollTop;
  const links = box.scrollLeft;
  $('#p-liste').replaceChildren(...liste.map((e) => h('li', {}, h('button', {
    type: 'button', class: e.id === P.gewaehlt ? 'aktiv' : '',
    onclick: () => pWaehlen(e.id), 'aria-pressed': String(e.id === P.gewaehlt),
  }, h('strong', { text: e.titel }), h('span', { class: 'leise',
    text: [e.herkunft === 'sammlung' ? 'Sammlung' : 'Ordner', e.getestet ? 'getestet' : 'ungetestet', e.fehler].filter(Boolean).join(' · ') })))));
  if (!liste.length) $('#p-liste').append(h('li', { class: 'leise', text: 'Keine passenden Prompts.' }));
  box.scrollTop = oben;
  box.scrollLeft = links;
  P.listeStand = stand;
}

function pKnopf(text, aktion) {
  const b = knopf(text, async () => {
    try { await aktion(); } catch (err) { pFehler(err); }
    finally { b.disabled = false; }
  });
  return b;
}

async function pAktion(daten) {
  const d = await api('/api/prompt', daten);
  if (d.id) P.gewaehlt = d.id;
  await pLaden();
}

function pOeffnen(e, was, datei = '') {
  return api('/api/prompt', { aktion: 'oeffnen', id: e.id, was, datei });
}

async function pWaehlen(id) {
  if (pGeschuetzt()) return;
  const anfrage = ++P.anfrage;
  try {
    const e = await api(`/api/prompt?id=${encodeURIComponent(id)}`);
    if (anfrage !== P.anfrage || pGeschuetzt()) return;
    P.gewaehlt = id;
    pListe();
    const { warteschlange, ...eintrag } = e;
    const stand = JSON.stringify({ eintrag, warteschlange: (warteschlange || [])
      .filter((a) => a.prompt?.eintrag === id && ['wartet', 'laeuft', 'fehler', 'abgebrochen'].includes(a.zustand))
      .map((a) => ({ id: a.id, fassung: a.prompt.fassung, beleg: a.prompt.beleg,
        auswerter: a.auswerter.name, zustand: a.zustand, meldung: a.meldung })) });
    if (stand === P.inhaltStand) return;
    const box = $('#p-inhalt');
    const gleicherEintrag = P.inhaltId === id;
    const offen = new Map(gleicherEintrag ? [...box.querySelectorAll('details[data-p-ansicht]')]
      .filter((d) => d.open).map((d) => [d.getAttribute('data-p-ansicht'), d.querySelector('.f-text')?.innerHTML || '']) : []);
    const position = { oben: box.scrollTop, links: box.scrollLeft, x: window.scrollX, y: window.scrollY };
    const knoepfe = [pKnopf(e.herkunft === 'ordner' || id.startsWith('schatten:')
      ? 'Im Ordner öffnen' : 'In der Sammlung öffnen', () => pOeffnen(e,
      e.herkunft === 'ordner' || id.startsWith('schatten:') ? 'ordner' : 'sammlung'))];
    if (e.bearbeitbar) knoepfe.push(pKnopf('Kopfzeilen bearbeiten …', () => pDialog(e, 'kopf')),
      pKnopf('Neue Fassung …', () => pDialog(e, 'fassung_neu')));
    if (!e.fehler && e.fassungen.length) knoepfe.push(pKnopf('Testen …', () => pTestdialog(e)), pSchaerfenMenue(e));
    const quelle = /^https?:\/\//i.test(e.quelle || '')
      ? h('a', { href: e.quelle, target: '_blank', rel: 'noopener', text: e.quelle })
      : h('span', { text: e.quelle || '' });
    const inhalt = [h('h2', { text: e.titel }), quelle,
      h('p', { class: 'leise', text: [e.schlagworte, e.bevorzugt ? `Bevorzugt: ${e.bevorzugt}` : '', e.hinweis].filter(Boolean).join(' · ') }),
      h('div', { class: 'p-knoepfe' }, ...knoepfe)];
    if (e.fehler) inhalt.push(h('p', { class: 'warnung', text: e.fehler }));
    for (const ziel of e.kandidaten || []) {
      inhalt.push(pKnopf(`Diesem Kasten zuordnen: ${P.eintraege.find((s) => s.id === ziel)?.titel || ziel}`,
        () => pAktion({ aktion: 'zuordnen', id, ziel })));
    }
    for (const f of e.fassungen) {
      const pre = h('pre', { class: 'p-text', text: f.text });
      const karte = h('article', { class: 'p-fassung' }, h('h3', { text: f.name }),
        h('p', { class: 'leise', text: f.stand }));
      if (f.text.split('\n').length > 20) karte.append(h('details', {
        'data-p-ansicht': JSON.stringify(['fassung', f.name]),
      }, h('summary', { text: 'Fassung anzeigen' }), pre));
      else karte.append(pre);
      if (e.bearbeitbar) karte.append(h('div', { class: 'p-knoepfe' },
        pKnopf('Bearbeiten …', () => pDialog(e, 'fassung_speichern', f)),
        pKnopf('Als bevorzugt', () => pAktion({ aktion: 'bevorzugt', id, name: f.name, kopf_stand: e.kopf_stand }))));
      if (!e.fehler) karte.append(pKnopf('Testen …', () => pTestdialog(e, f.name)), pSchaerfenMenue(e, f.name));
      inhalt.push(karte);
    }
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Tests' }));
    for (const t of e.tests) {
      const karte = h('article', { class: 'p-fassung' }, h('p', { text: [t.erstellt, t.fassung,
        t.geaendert ? 'seit dem Test geändert' : '', t.auswerter, t.dauer_s != null ? dauer(Number(t.dauer_s)) : '',
        t.tokens != null ? `${t.tokens} Token` : '', t.kosten_usd != null ? `${t.kosten_usd} USD` : '',
        ZUSTAND[t.zustand] || t.zustand, t.urteil ? `Urteil: ${t.urteil}` : '', t.notiz, t.fehler].filter(Boolean).join(' · ') }),
      pKnopf('Öffnen', () => pOeffnen(e, 'beleg', t.datei)),
      t.html === 'ja' ? pKnopf('Im Browser öffnen', () => pOeffnen(e, 'html', t.datei.replace(/\.md$/i, '.html'))) : null);
      karte.append(pKnopf('Gesendet anzeigen', async () => {
        const b = await pBeleg(e, t, 'gesendet');
        const d = dialogOeffnen('Gesendet', [h('pre', { class: 'p-text', text: b.text })],
          [pKnopf('Schließen', () => d.close())], true);
      }), !t.fehler ? pKnopf('Nochmal …', async () => pTestdialog(e, t.fassung, await pBeleg(e, t))) : null);
      const notiz = h('textarea', { 'aria-label': 'Notiz', rows: '2' });
      notiz.value = t.notiz || '';
      let ks = t.kopf_stand;
      const speichern = async (urteil) => {
        if (!ks) ks = (await pBeleg(e, t)).kopf_stand;
        const d = await api('/api/prompt', { aktion: 'urteil', id: e.id, datei: t.datei,
          kopf_stand: ks, urteil, notiz: notiz.value });
        ks = d.kopf_stand;
        t.urteil = urteil;
      };
      karte.append(h('div', { class: 'p-knoepfe' }, ...['offen', 'gut', 'schwach'].map((u) =>
        pKnopf(u, () => speichern(u)))), notiz);
      notiz.addEventListener('blur', () => speichern(t.urteil || 'offen').catch(pFehler));
      const antwort = h('div', { class: 'f-text' });
      const ansicht = JSON.stringify([t.datei, 'antwort']);
      if (offen.has(ansicht)) antwort.innerHTML = offen.get(ansicht);
      const details = h('details', { 'data-p-ansicht': ansicht }, h('summary', { text: 'Antwort anzeigen' }), antwort);
      details.addEventListener('toggle', async () => {
        if (details.open) {
          try { antwort.innerHTML = markdown((await pBeleg(e, t)).antwort || 'Noch keine Antwort.'); }
          catch (err) { antwort.textContent = err.message; }
        }
      });
      karte.append(details);
      if (!t.fehler && t.verwaist && ['abgebrochen', 'fehler'].includes(t.zustand)) karte.append(pKnopf('Wiederholen', () =>
        pAktion({ aktion: 'wiederholen_beleg', id: e.id, datei: t.datei })));
      inhalt.push(karte);
    }
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Schärfen' }));
    for (const t of e.schaerfen || []) {
      const antwort = h('div', { class: 'f-text' });
      const ansicht = JSON.stringify([t.datei, 'schaerfen']);
      if (offen.has(ansicht)) antwort.innerHTML = offen.get(ansicht);
      const details = h('details', { 'data-p-ansicht': ansicht }, h('summary', { text: 'Ergebnis anzeigen' }), antwort);
      details.addEventListener('toggle', async () => {
        if (details.open) {
          try { pSchaerfenErgebnis(antwort, await pBeleg(e, t, 'schaerfen')); }
          catch (err) { antwort.textContent = err.message; }
        }
      });
      inhalt.push(h('article', { class: 'p-fassung' }, h('p', { text: [t.erstellt, t.aktion, t.auswerter,
        t.zielmodell, ZUSTAND[t.zustand] || t.zustand, t.ergebnis, t.fehler].filter(Boolean).join(' · ') }),
      pKnopf('Öffnen', () => pOeffnen(e, 'schaerfen', t.datei)), details,
      !t.fehler && t.verwaist && ['abgebrochen', 'fehler'].includes(t.zustand) ? pKnopf('Wiederholen', () =>
        pAktion({ aktion: 'wiederholen_beleg', id: e.id, datei: t.datei, art_ordner: 'schaerfen' })) : null));
    }
    for (const a of (e.warteschlange || []).filter((a) => a.prompt?.eintrag === e.id
      && ['wartet', 'laeuft', 'fehler', 'abgebrochen'].includes(a.zustand))) {
      const aktion = (was) => async () => { await api('/api/fassung', { id: a.id, aktion: was }); await pLaden(); };
      inhalt.push(h('article', { class: 'p-fassung' }, h('p', { text:
        `${a.art === 'schaerfen' ? 'Schärfen · ' : ''}${a.prompt.fassung} · ${a.auswerter.name} · ${ZUSTAND[a.zustand] || a.zustand} · ${a.meldung || ''}` }),
      ...(['wartet', 'laeuft'].includes(a.zustand) ? [pKnopf('Abbrechen', aktion('abbrechen'))]
        : (a.art === 'schaerfen' ? e.schaerfen || [] : e.tests).some((t) => t.datei === `${a.prompt.beleg}.md` && t.fehler) ? []
          : [pKnopf('Wiederholen', aktion('wiederholen'))]),
      a.zustand !== 'laeuft' ? pKnopf('Entfernen', aktion('entfernen')) : null));
    }
    if (!e.tests.length) inhalt.push(h('p', { class: 'leise', text: 'Noch keine Testbelege.' }));
    box.replaceChildren(...inhalt);
    for (const d of box.querySelectorAll('details[data-p-ansicht]')) {
      if (offen.has(d.getAttribute('data-p-ansicht'))) d.open = true;
    }
    if (gleicherEintrag) {
      box.scrollTop = position.oben;
      box.scrollLeft = position.links;
      window.scrollTo({ left: position.x, top: position.y, behavior: 'instant' });
    }
    P.inhaltStand = stand;
    P.inhaltId = id;
  } catch (err) { if (anfrage === P.anfrage) pFehler(err); }
}

function pDialog(e, aktion, f = null) {
  const kopf = aktion === 'kopf' || aktion === 'neu';
  const felder = {};
  const inhalt = [];
  function feld(name, beschriftung, wert, mehrzeilig = false) {
    const input = h(mehrzeilig ? 'textarea' : 'input', mehrzeilig ? { spellcheck: 'false' } : { type: 'text' });
    input.value = wert || '';
    felder[name] = input;
    inhalt.push(h('label', { class: 'dialog-feld' }, beschriftung, input));
  }
  if (kopf) {
    feld('titel', 'Titel', e?.titel);
    feld('quelle', 'Quelle', e?.quelle);
    feld('schlagworte', 'Schlagworte', e?.schlagworte);
  } else if (aktion === 'fassung_neu') feld('name', 'Name der neuen Fassung', '');
  if (aktion !== 'kopf') feld('text', aktion === 'neu' ? 'Fassung 1' : 'Fassung', f?.text, true);
  const fehler = h('p', { class: 'warnung' });
  inhalt.push(fehler);
  const titel = { neu: 'Neuer Prompt', kopf: 'Kopfzeilen bearbeiten', fassung_neu: 'Neue Fassung',
    fassung_speichern: `Fassung bearbeiten: ${f?.name}` }[aktion];
  const d = dialogOeffnen(titel, inhalt, [
    pKnopf('Abbrechen', () => d.close()),
    pKnopf('Speichern', async () => {
      try {
        const daten = { aktion, id: e?.id, kopf_stand: e?.kopf_stand, stand: f?.stand, name: f?.name };
        for (const [name, input] of Object.entries(felder)) daten[name] = input.value;
        const neu = await api('/api/prompt', daten);
        P.gewaehlt = neu.id;
        d.close();
        await pLaden();
      } catch (err) { fehler.textContent = err.message; }
    }),
  ], true);
  Object.values(felder)[0].focus();
}

function pBeleg(e, t, was = 'beleg') {
  return api(`/api/prompt-datei?id=${encodeURIComponent(e.id)}&was=${was}&datei=${encodeURIComponent(t.datei)}`);
}

function pSchaerfenMenue(e, name) {
  const menue = h('span', { class: 'p-schaerfen-menue', hidden: true });
  const b = pKnopf('Schärfen ▾', () => {
    menue.hidden = !menue.hidden;
    b.setAttribute('aria-expanded', String(!menue.hidden));
  });
  b.setAttribute('aria-expanded', 'false');
  for (const aktion of ['Schärfen', 'Erst klären', 'Kürzen']) menue.append(pKnopf(aktion, async () => {
    menue.hidden = true; b.setAttribute('aria-expanded', 'false');
    await pSchaerfendialog(e, name, aktion);
  }));
  return h('span', {}, b, menue);
}

function pSchaerfenErgebnis(box, b) {
  if (b.aktion === 'Erst klären') {
    const fragen = h('div'); fragen.innerHTML = markdown(b.fragen || 'Noch keine Antwort.');
    box.replaceChildren(fragen); return;
  }
  const stichpunkte = h('div'); stichpunkte.innerHTML = markdown(b.stichpunkte || 'Noch keine Antwort.');
  box.replaceChildren(h('div', { class: 'p-vergleich' },
    h('section', {}, h('h4', { text: 'Original' }), h('pre', { class: 'p-text', text: b.original })),
    h('section', {}, h('h4', { text: 'Neue Fassung' }), h('pre', { class: 'p-text', text: b.neue_fassung || 'Keine gültige neue Fassung.' }))),
  // replaceChildren würde ein null als Text „null“ anhängen, darum vorher herausfiltern.
  ...[stichpunkte, b.neue_platzhalter?.length ? h('p', { text: `Neue Platzhalter: ${b.neue_platzhalter.map((n) => `[${n}]`).join(', ')}` }) : null].filter(Boolean));
}

async function pSchaerfendialog(e, name, aktion = 'Schärfen') {
  const stand = await api('/api/zusammenfassung');
  const auswahl = (beschriftung, optionen) => {
    const s = h('select', { 'aria-label': beschriftung }, ...optionen);
    return s;
  };
  const fassung = auswahl('Fassung', e.fassungen.map((f) => h('option', { value: f.name, text: f.name })));
  fassung.value = name || e.bevorzugt || e.fassungen[0].name;
  const art = auswahl('Aktion', ['Schärfen', 'Erst klären', 'Kürzen'].map((a) => h('option', { value: a, text: a })));
  art.value = aktion;
  const profile = () => stand.auswerter.map((p) => h('option', { value: p.id,
    text: `${p.name} · ${p.cloud ? `Cloud (${p.cloud})` : 'lokal'}${p.verfuegbar ? '' : ` · ${p.grund}`}` }));
  const schreibmodell = auswahl('Schreibmodell', profile());
  const zielmodell = auswahl('Zielmodell', profile());
  let zuletzt = '', tests = [];
  try {
    zuletzt = localStorage.getItem('werkstatt.prompt-schreibmodell') || '';
    tests = JSON.parse(localStorage.getItem('werkstatt.prompt-auswerter') || '[]');
  } catch { /* Ohne Speicher die Vorgaben verwenden. */ }
  schreibmodell.value = (stand.auswerter.find((p) => p.id === zuletzt && p.verfuegbar)
    || stand.auswerter.find((p) => p.verfuegbar && ['claude', 'codex'].includes(p.anbieter))
    || stand.auswerter.find((p) => p.verfuegbar) || stand.auswerter[0])?.id || '';
  zielmodell.value = stand.auswerter.find((p) => tests.includes(p.id))?.id || stand.auswerter[0]?.id || '';
  const hinweise = h('textarea', { rows: '4', maxlength: '2000', 'aria-label': 'Hinweise' });
  const material = auswahl('Letzte Antwort als Material', [h('option', { value: '', text: 'Kein Material' }),
    ...e.tests.filter((t) => t.antwort_vorhanden && !t.fehler).map((t) => h('option', { value: t.datei,
      text: `${t.erstellt} · ${t.fassung} · ${t.auswerter}` }))]);
  const rueck = h('p', { class: 'warnung', 'aria-live': 'polite' });
  const vorschauInhalt = h('div');
  const vorschau = h('details', {}, h('summary', { text: 'Vorschau' }), vorschauInhalt);
  let geprueft = null;
  const eingabe = () => ({ id: e.id, fassung: fassung.value, schaerfen_aktion: art.value,
    schreibmodell: schreibmodell.value, zielmodell: zielmodell.value, hinweise: hinweise.value, material: material.value });
  const feld = (text, input) => h('label', { class: 'dialog-feld' }, text, input);
  const d = dialogOeffnen(`Schärfen: ${e.titel}`, [feld('Fassung', fassung), feld('Aktion', art),
    feld('Schreibmodell', schreibmodell), feld('Zielmodell', zielmodell), feld('Hinweise', hinweise),
    feld('Letzte Antwort als Material', material), vorschau, rueck], [
    pKnopf('Abbrechen', () => d.close()), pKnopf('Vorschau berechnen', async () => {
      try {
        const daten = eingabe();
        const v = await api('/api/prompt', { ...daten, aktion: 'schaerfen_vorschau' });
        const p = v.schreibmodell;
        geprueft = p.verfuegbar ? { eingabe: JSON.stringify(daten), stand: v.gesendet_stand } : null;
        vorschauInhalt.replaceChildren(h('pre', { class: 'p-text', text: v.auftrag }),
          h('p', { text: `Stand: ${v.gesendet_stand}` }), h('p', { text:
            `${p.name} · ${p.verarbeitung} · etwa ${Math.ceil(p.geschaetzt || 0)} Token / ${p.kontext || 'unbekannt'} Kontext · ${p.kontext_quelle} · ${p.hinweis || ''} · ${p.grund || ''}` }));
        vorschau.open = true; rueck.textContent = p.verfuegbar ? '' : p.grund;
      } catch (err) { geprueft = null; rueck.textContent = err.message; }
    }), pKnopf('Start', async () => {
      try {
        const daten = eingabe();
        if (!geprueft || geprueft.eingabe !== JSON.stringify(daten)) throw Error('Bitte zuerst die aktuelle Vorschau prüfen.');
        await api('/api/prompt', { ...daten, aktion: 'schaerfen', gesendet_stand: geprueft.stand });
        try { localStorage.setItem('werkstatt.prompt-schreibmodell', daten.schreibmodell); } catch { /* egal */ }
        d.close(); await pLaden();
      } catch (err) { rueck.textContent = err.message; }
    }),
  ], true);
}

async function pTestdialog(e, name, beleg = null) {
  const stand = await api('/api/zusammenfassung');
  const gewaehlt = new Set();
  try { JSON.parse(localStorage.getItem('werkstatt.prompt-auswerter') || '[]').forEach((id) => gewaehlt.add(id)); }
  catch { /* Ohne Speicher bleibt die Auswahl leer. */ }
  if (beleg) {
    for (const p of stand.auswerter) if (p.name === beleg.auswerter) gewaehlt.add(p.id);
  }
  const fassungen = new Map();
  const auswerter = new Map();
  const felder = new Map();
  const rahmen = h('input', { type: 'checkbox' });
  rahmen.checked = beleg?.rahmen === 'ja';
  const rueck = h('p', { class: 'warnung', 'aria-live': 'polite' });
  const vorschau = h('details', { 'data-p-ansicht': JSON.stringify([beleg?.datei || '', 'vorschau']) },
    h('summary', { text: 'Vorschau' }));
  const vorschauInhalt = h('div');
  vorschau.append(vorschauInhalt);
  let geprueft = null;
  const start = pKnopf('Start', async () => {
    try {
      const daten = eingabe();
      if (!geprueft || geprueft.eingabe !== JSON.stringify(daten)) throw Error('Bitte zuerst die aktuelle Vorschau prüfen.');
      await api('/api/prompt', { ...daten, aktion: 'testen', gesendet_stand: geprueft.staende });
      try { localStorage.setItem('werkstatt.prompt-auswerter', JSON.stringify(daten.auswerter)); } catch { /* egal */ }
      d.close(); await pLaden();
    } catch (err) { rueck.textContent = err.message; }
  });
  const namen = [...new Set(e.fassungen.flatMap((f) => [...f.text.matchAll(/\[([^\[\]\n]{1,60})\](?!\()/g)]
    .map((m) => m[1]).filter((n) => !n.includes(':') && /\p{L}/u.test(n))).concat(Object.keys(beleg?.eingaben.felder || {})))];
  const feldBox = h('div');
  const auswahlBox = h('div', { class: 'p-test-auswahl' });
  for (const f of e.fassungen) {
    const cb = h('input', { type: 'checkbox' });
    cb.checked = f.name === (name || e.bevorzugt || e.fassungen[0].name);
    fassungen.set(f.name, cb);
    auswahlBox.append(h('label', { class: 'wahl' }, cb, f.name));
  }
  for (const p of stand.auswerter) {
    const cb = h('input', { type: 'checkbox', disabled: !p.verfuegbar });
    cb.checked = p.verfuegbar && gewaehlt.has(p.id);
    auswerter.set(p.id, cb);
    auswahlBox.append(h('label', { class: 'wahl' }, cb,
      `${p.name} · ${p.cloud ? `Cloud (${p.cloud})` : 'lokal'}${p.verfuegbar ? '' : ` · ${p.grund}`}`));
  }
  async function transkriptWahl(feld) {
    try {
      const ts = await api('/api/transkripte?prompts=1');
      const suche = h('input', { type: 'search', placeholder: 'Transkripttitel suchen', 'aria-label': 'Transkripttitel suchen' });
      const liste = h('div');
      const waehlen = h('div', { class: 'p-transkripte' }, suche, liste);
      feld.box.append(waehlen);
      const zeichnen = () => liste.replaceChildren(...ts.filter((t) => t.titel.toLocaleLowerCase('de')
        .includes(suche.value.toLocaleLowerCase('de'))).map((t) => pKnopf(`${t.titel} · ${t.zeichen} Zeichen`, () => {
        feld.quelle = { art: 'transkript', datei: t.datei, sha: t.sha, zeichen: t.zeichen };
        feld.text.value = `[Transkript: ${t.titel} · ${t.zeichen} Zeichen]`;
        waehlen.remove();
      })));
      suche.addEventListener('input', zeichnen); zeichnen(); suche.focus();
    } catch (err) { rueck.textContent = err.message; }
  }
  for (const n of namen) {
    const text = h('textarea', { rows: '5', 'data-prompt-feld': n, 'aria-label': n });
    const woertlich = h('input', { type: 'checkbox' });
    const alt = beleg?.eingaben.felder[n];
    woertlich.checked = alt?.art === 'woertlich';
    text.value = alt?.wert || (alt?.art === 'transkript' ? `[Transkript: ${alt.datei}]` : '');
    const feld = { text, woertlich, quelle: alt || null };
    felder.set(n, feld);
    text.promptEingabe = feld;
    text.addEventListener('input', () => { feld.quelle = null; });
    const pfad = h('input', { type: 'text', placeholder: 'Oder Dateipfad eingeben', 'aria-label': `Dateipfad für ${n}` });
    const ausDatei = async (waehlen) => {
      try {
        const datei = await api('/api/prompt', { aktion: waehlen ? 'datei_waehlen' : 'datei_lesen', pfad: pfad.value });
        if (!datei.abgebrochen) { feld.quelle = datei; text.value = datei.wert; }
      } catch (err) { rueck.textContent = err.message; }
    };
    feld.box = h('section', { class: 'p-test-feld' }, h('h3', { text: `[${n}]` }),
      h('label', {}, woertlich, 'wörtlich lassen'), text,
      h('div', { class: 'p-knoepfe' }, pKnopf('Aus Datei …', () => ausDatei(true)),
        pKnopf('Aus Transkript …', () => transkriptWahl(feld))), pfad,
      pKnopf('Pfad lesen', () => ausDatei(false)),
      beleg?.hinweise[n] ? h('p', { class: 'warnung', text: beleg.hinweise[n] }) : null);
    feldBox.append(feld.box);
  }
  function eingabe() {
    return { id: e.id, fassungen: [...fassungen].filter(([, cb]) => cb.checked).map(([n]) => n),
      auswerter: [...auswerter].filter(([, cb]) => cb.checked).map(([n]) => n), rahmen: rahmen.checked,
      eingaben: { felder: Object.fromEntries([...felder].map(([n, f]) => [n,
        f.woertlich.checked ? { art: 'woertlich' } : f.quelle || { art: 'text', wert: f.text.value }])) } };
  }
  const d = dialogOeffnen(`Testen: ${e.titel}`, [auswahlBox,
    h('label', { class: 'wahl' }, rahmen, 'Rahmen der Zusammenfassung voranstellen'), feldBox,
    vorschau, rueck], [pKnopf('Abbrechen', () => d.close()), pKnopf('Vorschau berechnen', async () => {
    try {
      const daten = eingabe();
      const v = await api('/api/prompt', { ...daten, aktion: 'vorschau' });
      geprueft = { eingabe: JSON.stringify(daten), staende: Object.fromEntries(v.fassungen.map((f) => [f.name, f.gesendet_stand])) };
      vorschauInhalt.replaceChildren(h('p', { text: `${v.leer} Felder leer` }), ...v.fassungen.map((f) =>
        h('section', {}, h('h3', { text: f.name }), h('pre', { class: 'p-text', text: f.auftrag }),
          h('p', { class: 'leise', text: `Stand: ${f.gesendet_stand}` }), ...f.auswerter.map((p) =>
            h('p', { text: `${p.modell} · ${p.verarbeitung} · etwa ${Math.ceil(p.geschaetzt)} Token / ${p.kontext || 'unbekannt'} Kontext · ${p.kontext_quelle} · ${p.hinweis}` })))));
      vorschau.open = true; rueck.textContent = '';
    } catch (err) { geprueft = null; rueck.textContent = err.message; }
  }), start], true);
  if (!beleg && felder.has('Transkript')) await transkriptWahl(felder.get('Transkript'));
}

window.promptsAblegen = async (e, feld) => {
  try {
    const datei = e.dataTransfer.files[0];
    if (!datei) return;
    const text = await datei.text();
    feld.value = text;
    feld.promptEingabe.quelle = { art: 'text', name: datei.name, wert: text };
  } catch (err) { pFehler(err); }
};

$('#p-suche').addEventListener('input', pListe);
$('#p-herkunft').addEventListener('change', pListe);
$('#p-status').addEventListener('change', pListe);
$('#p-neu').addEventListener('click', () => pDialog(null, 'neu'));
$('#p-laden').addEventListener('click', pLaden);
window.promptsAktiv = (aktiv) => {
  P.aktiv = aktiv;
  if (aktiv && pLadenFaellig()) pLaden();
  if (!P.timer && typeof setTimeout === 'function') {
    const weiter = () => {
      P.timer = setTimeout(async () => {
        if (P.aktiv && !pGeschuetzt() && pLadenFaellig()) await pLaden();
        weiter();
      }, 2500);
    };
    weiter();
  }
};
