'use strict';

// ------------------------------------------------------------------ Hilfen

const $ = (sel) => document.querySelector(sel);
const SVG = 'http://www.w3.org/2000/svg';

function h(tag, attrs = {}, ...kinder) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kind of kinder) if (kind != null) el.append(kind);
  return el;
}

const gib = (mib) => (mib / 1024).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const zahl = (x, einheit) => (x == null ? '–' : `${Math.round(x)}${einheit}`);
const uhrzeit = (d = new Date()) => d.toLocaleTimeString('de-DE');

async function api(pfad, daten) {
  const opt = daten === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Zentrale': '1' },
    body: JSON.stringify(daten),
  };
  const r = await fetch(pfad, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.fehler || `Der Dienst antwortete mit Fehler ${r.status}.`);
  return j;
}

// ------------------------------------------------------------------ Zustand

let KONFIG = null;
let STAND = null;
let AKTION = null;
let PROTOKOLL = [];
let VERLAUF = [];
const lokaleMeldungen = [];
const karten = new Map();
const zeilen = new Map();

const kartenName = (i) => STAND?.karten.find((k) => k.index === Number(i))?.kurz
  || KONFIG?.karten_namen?.[String(i)] || `Karte ${i}`;

function melden(text) {
  lokaleMeldungen.unshift({ zeit: uhrzeit(), text, art: 'fehler' });
  lokaleMeldungen.splice(5);
  protokollZeichnen();
}

// ------------------------------------------------------------------ Belegungsleiste

function segmente(belegung) {
  let pos = 0;
  return belegung.map((b) => {
    const s = { von: pos, bis: pos + b.mib / 1024, farbe: b.farbe, name: b.name };
    pos = s.bis;
    return s;
  });
}

function leisteFuellen(leiste, gesamtMib, seg) {
  const n = Math.round(gesamtMib / 1024);
  if (leiste.childElementCount !== n) {
    leiste.replaceChildren(...Array.from({ length: n }, () => h('span', { class: 'zelle' })));
    leiste.style.setProperty('--n', n);
  }
  [...leiste.children].forEach((zelle, i) => {
    const teile = seg
      .filter((s) => s.bis > i && s.von < i + 1)
      .map((s) => ({ a: Math.max(0, s.von - i), b: Math.min(1, s.bis - i), farbe: s.farbe, name: s.name }));
    if (!teile.length) {
      zelle.style.backgroundImage = '';
      zelle.title = `GiB ${i + 1}: frei`;
      return;
    }
    const stops = teile.map((t) => `${t.farbe} ${(t.a * 100).toFixed(1)}% ${(t.b * 100).toFixed(1)}%`);
    const ende = teile[teile.length - 1].b;
    if (ende < 0.999) stops.push(`transparent ${(ende * 100).toFixed(1)}%`);
    zelle.style.backgroundImage = `linear-gradient(to right, ${stops.join(', ')})`;
    zelle.title = `GiB ${i + 1}: ${[...new Set(teile.map((t) => t.name))].join(', ')}${ende < 0.999 ? ', teils frei' : ''}`;
  });
}

// ------------------------------------------------------------------ Karten

function karteAnlegen(index) {
  const werte = {};
  const mw = (schluessel, titel) => {
    werte[schluessel] = h('dd');
    return h('div', { class: 'mw' }, h('dt', { text: titel }), werte[schluessel]);
  };
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 300 40');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('aria-hidden', 'true');
  const pfadVram = document.createElementNS(SVG, 'path');
  const pfadTemp = document.createElementNS(SVG, 'path');
  pfadVram.setAttribute('class', 'v-vram');
  pfadTemp.setAttribute('class', 'v-temp');
  svg.append(pfadVram, pfadTemp);
  const name = h('h2');
  const sub = h('p', { class: 'karte-sub' });
  const leiste = h('div', { class: 'leiste', role: 'img' });
  const legende = h('ul', { class: 'legende' });
  const el = h('article', { class: 'karte' },
    h('div', { class: 'karte-name' }, name, sub),
    leiste, legende,
    h('dl', { class: 'messwerte' }, mw('temp', 'Temperatur'), mw('last', 'Auslastung'), mw('watt', 'Leistung'), mw('luefter', 'Lüfter')),
    h('figure', { class: 'verlauf' }, svg,
      h('figcaption', {}, 'Letzte 10 Minuten', h('i'), 'Temperatur', h('i', { class: 'v' }), 'Belegung')));
  const r = { el, name, sub, leiste, legende, werte, pfadVram, pfadTemp };
  karten.set(index, r);
  $('#karten').append(el);
  return r;
}

function verlaufZeichnen(r, k) {
  const punkte = VERLAUF.map((v) => v.k.find((x) => x[0] === k.index)).filter(Boolean);
  if (punkte.length < 2) return;
  const B = 300, H = 40, MAX = 300;
  const x = (i) => B - (punkte.length - 1 - i) * (B / (MAX - 1));
  const yTemp = (t) => H - 2 - Math.max(0, Math.min(1, ((t ?? 20) - 20) / 70)) * (H - 4);
  const yVram = (m) => H - Math.min(1, (m ?? 0) / k.gesamt) * H;
  r.pfadTemp.setAttribute('d', punkte.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${yTemp(p[2]).toFixed(1)}`).join(''));
  r.pfadVram.setAttribute('d', `M${x(0).toFixed(1)},${H}${punkte.map((p, i) => `L${x(i).toFixed(1)},${yVram(p[1]).toFixed(1)}`).join('')}L${x(punkte.length - 1).toFixed(1)},${H}Z`);
}

function kartenZeichnen() {
  for (const k of STAND.karten) {
    const r = karten.get(k.index) || karteAnlegen(k.index);
    r.name.textContent = k.kurz;
    r.sub.textContent = `${Math.round(k.gesamt / 1024)} GiB · Steckplatz ${k.bus ?? '?'}${k.monitor ? ' · Monitor' : ''}`;
    leisteFuellen(r.leiste, k.gesamt, segmente(k.belegung));
    const frei = Math.max(0, k.gesamt - k.belegt - (k.angemeldet || 0));
    r.leiste.setAttribute('aria-label', `${k.kurz}: ${gib(k.belegt)} von ${gib(k.gesamt)} GiB belegt. `
      + k.belegung.map((b) => `${b.name} ${gib(b.mib)} GiB`).join(', '));
    r.legende.replaceChildren(
      ...k.belegung.filter((b) => b.mib >= 52).map((b) => h('li', { title: b.details?.length ? `Darin: ${b.details.join(', ')}` : null },
        h('i', { style: `--f:${b.farbe}` }), h('span', { text: b.name }), h('b', { text: `${gib(b.mib)} GiB` }))),
      h('li', { class: 'frei' }, h('i'), h('span', { text: 'frei' }), h('b', { text: `${gib(frei)} GiB` })));
    r.werte.temp.textContent = zahl(k.temp, ' °C');
    r.werte.temp.className = k.temp >= 83 ? 'heiss' : k.temp >= 70 ? 'warm' : '';
    r.werte.last.textContent = zahl(k.last, ' %');
    r.werte.watt.replaceChildren(zahl(k.watt, ' W'), k.watt_limit ? h('small', { text: ` / ${Math.round(k.watt_limit)}` }) : '');
    r.werte.luefter.textContent = zahl(k.luefter, ' %');
    verlaufZeichnen(r, k);
  }
}

// ------------------------------------------------------------------ Einträge

const TEXTE = {
  aus: 'Aus', startet: 'Startet …', bereit: 'Bereit', stoppt: 'Wird beendet …',
  fremd: 'Port belegt', teilweise: 'Teilweise bereit', laeuft: 'Läuft',
};
const TEXTE_OLLAMA = { startet: 'Lädt …', bereit: 'Geladen', stoppt: 'Wird entladen …' };

function zustandText(e, z) {
  return (e.art === 'ollama' && TEXTE_OLLAMA[z]) || TEXTE[z] || z;
}

// Eintrag mit den Angaben der gewählten Variante (Kontextgröße), sonst der Standardvariante.
function mitVariante(e, vid) {
  if (!e.varianten?.length) return e;
  const v = e.varianten.find((x) => x.id === vid) || e.varianten.find((x) => x.standard) || e.varianten[0];
  const neu = { ...e, variante: v.id, variante_name: v.name };
  for (const f of ['bedarf_mib', 'bedarf_gesamt_mib', 'bedarf_je_karte_mib']) if (v[f] != null) neu[f] = v[f];
  return neu;
}

function bedarfText(e) {
  if (e.bedarf_hinweis) return e.bedarf_hinweis;
  if (e.karten) return `Braucht etwa ${gib(e.bedarf_je_karte_mib)} GiB auf einer ${e.karten.join(' oder ')}; es startet auf der Karte, auf der es passt.`;
  if (e.bedarf_gesamt_mib) return `Braucht etwa ${gib(e.bedarf_gesamt_mib)} GiB auf den Karten zusammen; Ollama verteilt es selbst.`;
  if (!e.bedarf_mib) return null;
  const teile = Object.entries(e.bedarf_mib).map(([i, m]) => `${gib(m)} GiB auf der ${kartenName(i)}`);
  const art = e.art === 'comfy' ? 'Braucht während eines Auftrags bis zu' : `Braucht ${e.bedarf_geschaetzt ? 'geschätzt' : 'etwa'}`;
  return `${art} ${teile.join(' und ')}.`;
}

function zeilenAnlegen() {
  const gruppen = new Map();
  for (const e of KONFIG.eintraege) {
    if (!gruppen.has(e.gruppe)) gruppen.set(e.gruppe, []);
    gruppen.get(e.gruppe).push(e);
  }
  for (const [titel, liste] of gruppen) {
    const abschnitt = h('section', { class: 'gruppe' }, h('h2', { text: titel }));
    for (const e of liste) {
      const pille = h('span', { class: 'pille' });
      const detail = h('p', { class: 'e-detail' });
      const knoepfe = h('div', { class: 'e-knoepfe' });
      const bedarf = bedarfText(mitVariante(e));
      const bedarfZeile = bedarf ? h('p', { class: 'e-bedarf', text: bedarf }) : null;
      let wahl = null;
      if (e.varianten?.length) {
        wahl = h('select', { class: 'e-wahl', 'aria-label': `Variante für ${e.name}` },
          ...e.varianten.map((v) => h('option', { value: v.id, selected: !!v.standard, text: v.name })));
        wahl.addEventListener('change', () => { bedarfZeile.textContent = bedarfText(mitVariante(e, wahl.value)); });
      }
      const el = h('article', { class: 'eintrag', style: `--farbe:${e.farbe}` },
        h('div', { class: 'e-kennung', 'aria-hidden': 'true' }),
        h('div', { class: 'e-text' },
          h('h3', {}, e.name, h('span', { class: 'e-unter', text: e.untertitel || '' })),
          h('p', { class: 'e-wofuer', text: e.wofuer }),
          bedarfZeile,
          wahl ? h('label', { class: 'e-variante' }, e.art === 'ollama' ? 'Laden mit ' : 'Starten mit ', wahl) : null),
        h('div', { class: 'e-zustand', 'aria-live': 'polite' }, pille, detail),
        knoepfe);
      zeilen.set(e.id, { e, pille, detail, knoepfe, wahl, schluessel: '' });
      abschnitt.append(el);
    }
    $('#gruppen').append(abschnitt);
  }
}

function knoepfeFuer(e, s, beschaeftigt) {
  const knopf = (text, fn, haupt = false) => h('button',
    { class: `knopf${haupt ? ' knopf-zeile' : ''}`, type: 'button', disabled: beschaeftigt, onclick: fn }, text);
  const z = s.zustand;
  if (e.art === 'programm') {
    return z === 'laeuft'
      ? [knopf('Nach vorn holen', () => starten(e)), knopf('Beenden', () => stoppen(e, s))]
      : [knopf('Öffnen', () => starten(e), true)];
  }
  const out = [];
  if ((e.art === 'comfy' && (z === 'bereit' || z === 'teilweise')) || (e.art === 'strata' && z === 'bereit')) {
    for (const l of e.links) {
      if (z === 'bereit' || l.art === 'comfy') out.push(h('a', { class: 'knopf', href: l.url, target: '_blank', rel: 'noopener' }, l.text));
    }
  }
  if (z === 'aus' || z === 'teilweise') out.push(knopf(e.art === 'ollama' ? 'Laden' : 'Starten', () => starten(e), true));
  if (z === 'bereit' || z === 'teilweise' || (z === 'startet' && ['ninfer', 'strata', 'llamacpp'].includes(e.art))) {
    out.push(knopf(e.art === 'ollama' ? 'Entladen' : 'Beenden', () => stoppen(e, s)));
  }
  return out;
}

function zeilenZeichnen() {
  for (const [id, z] of zeilen) {
    const s = STAND.eintraege[id] || { zustand: 'aus', detail: '' };
    z.pille.textContent = zustandText(z.e, s.zustand);
    z.pille.dataset.zustand = s.zustand;
    z.detail.textContent = s.detail || '';
    // Wählbar nur, solange der Eintrag aus ist; was geladen ist, zeigt die Zeile (Kontext aus dem Programm selbst).
    if (z.wahl) z.wahl.disabled = s.zustand !== 'aus' || !!AKTION;
    const schluessel = `${s.zustand}|${!!AKTION}|${s.auftrag}`;
    if (schluessel !== z.schluessel) {
      z.schluessel = schluessel;
      z.knoepfe.replaceChildren(...knoepfeFuer(z.e, s, !!AKTION));
    }
  }
}

// ------------------------------------------------------------------ Dialoge

function zeigeDialog(titel, inhalt, knoepfe, abbrechen = 'Abbrechen') {
  const d = $('#dialog');
  d.replaceChildren(
    h('h2', { id: 'dialog-titel', text: titel }),
    ...inhalt,
    h('div', { class: 'dialog-knoepfe' },
      h('button', { class: 'knopf', type: 'button', onclick: () => d.close() }, abbrechen),
      ...knoepfe.map((k) => h('button', {
        class: `knopf${k.haupt ? ' knopf-haupt' : ''}`, type: 'button',
        onclick: () => { d.close(); k.fn(); },
      }, k.text))));
  d.showModal();
}

function schluesselAusSchritt(id) {
  const [art, ...rest] = id.split(':');
  const ziel = rest.join(':');
  return art === 'entladen' ? `ollama:${ziel}` : ziel;
}

function projektion(e, plan) {
  const schritte = plan.schritte;
  const weg = new Set(schritte.map((s) => schluesselAusSchritt(s.id)));
  const block = h('div', { class: 'projektion' });
  for (const [i, bedarf] of Object.entries(plan.bedarf_mib || e.bedarf_mib || {})) {
    const k = STAND.karten.find((x) => x.index === Number(i));
    if (!k) continue;
    const jetzt = h('div', { class: 'leiste mini' });
    const danach = h('div', { class: 'leiste mini' });
    leisteFuellen(jetzt, k.gesamt, segmente(k.belegung));
    const neu = [{ name: e.name, farbe: e.farbe, mib: bedarf }, ...k.belegung.filter((b) => !weg.has(b.schluessel))];
    leisteFuellen(danach, k.gesamt, segmente(neu));
    block.append(
      h('p', { class: 'p-titel', text: k.kurz }),
      h('div', { class: 'p-zeile' }, h('span', { text: 'Jetzt' }), jetzt),
      h('div', { class: 'p-zeile' }, h('span', { text: 'Danach (geschätzt)' }), danach));
  }
  return block;
}

function hinweisText(plan) {
  return plan.hinweise.map((x) => `${x.karte == null ? 'Auf den Karten zusammen' : `Auf der ${kartenName(x.karte)}`} fehlen noch etwa ${gib(x.fehlend_mib)} GiB`
    + (x.belegt_von.length ? `, belegt von ${x.belegt_von.join(', ')}.` : '.')).join(' ');
}

// ------------------------------------------------------------------ Aktionen

async function starten(e) {
  const vid = zeilen.get(e.id)?.wahl?.value || undefined;
  e = mitVariante(e, vid);
  try {
    const plan = await api('/api/plan', { id: e.id, aktion: 'starten', variante: vid });
    if (!plan.schritte.length && plan.genug_platz) return await ausfuehren(e, [], false);
    const verb = e.art === 'ollama' ? 'laden' : 'starten';
    const inhalt = [];
    if (plan.schritte.length) {
      inhalt.push(h('p', { text: 'Dafür muss Platz auf den Grafikkarten geschaffen werden:' }),
        h('ul', { class: 'schritte' }, ...plan.schritte.map((s) => h('li', { text: s.text }))),
        projektion(e, plan));
    }
    if (!plan.genug_platz) inhalt.push(h('p', { class: 'warnung', text: hinweisText(plan) }));
    for (const g of plan.gruende || []) inhalt.push(h('p', { class: 'warnung', text: g }));
    const knoepfe = [];
    if (plan.schritte.length) {
      knoepfe.push({ text: `Ohne Freigabe ${verb}`, fn: () => ausfuehren(e, [], true) });
      knoepfe.push({ text: `Freigeben und ${verb}`, haupt: true, fn: () => ausfuehren(e, plan.schritte.map((s) => s.id), false) });
    } else {
      knoepfe.push({ text: `Trotzdem ${verb}`, fn: () => ausfuehren(e, [], true) });
    }
    zeigeDialog(`${e.name}${e.variante_name ? ` (${e.variante_name})` : ''} ${verb}`, inhalt, knoepfe);
  } catch (err) {
    melden(err.message);
  }
}

async function ausfuehren(e, schritte, ohneFreigabe) {
  try {
    await api('/api/starten', { id: e.id, schritte, ohne_freigabe: ohneFreigabe, variante: e.variante });
  } catch (err) {
    melden(err.message);
  }
  aktualisieren();
}

async function stoppen(e, s) {
  const senden = async (erzwingen) => {
    try {
      await api('/api/stoppen', { id: e.id, erzwingen });
    } catch (err) {
      melden(err.message);
    }
    aktualisieren();
  };
  if (e.art === 'programm') {
    zeigeDialog(`${e.name} beenden?`, [h('p', { text: `Laufende Aufgaben und nicht gesendete Eingaben in ${e.name} gehen verloren.` })],
      [{ text: 'Beenden', haupt: true, fn: () => senden(false) }]);
    return;
  }
  if (e.art === 'comfy' && s.auftrag) {
    zeigeDialog('Auftrag läuft', [h('p', { text: 'In ComfyUI wird gerade ein Bild oder Video erzeugt. Beim Beenden geht dieser Auftrag verloren.' })],
      [{ text: 'Auftrag abbrechen und beenden', haupt: true, fn: () => senden(true) }]);
    return;
  }
  senden(false);
}

async function gpuFreigeben() {
  let plan;
  try {
    plan = await api('/api/plan', { aktion: 'freigeben' });
  } catch (err) {
    return melden(err.message);
  }
  const boxen = plan.schritte.map((s) => h('label', { class: 'wahl' },
    h('input', { type: 'checkbox', checked: '', 'data-id': s.id }),
    h('span', { text: s.text }), h('b', { text: `${gib(s.mib)} GiB` })));
  const inhalt = boxen.length
    ? [h('p', { text: 'Diese Modelle belegen gerade Grafikspeicher:' }), h('div', { class: 'wahlen' }, ...boxen)]
    : [h('p', { text: 'Gerade ist nichts geladen, was die Modellzentrale freigeben kann.' })];
  for (const g of plan.gruende) inhalt.push(h('p', { class: 'warnung', text: g }));
  if (plan.unberuehrt.length) {
    inhalt.push(h('p', { class: 'leise', text: `Bleibt unberührt: ${plan.unberuehrt.map((u) => `${u.name} (${gib(u.mib)} GiB)`).join(', ')}.` }));
  }
  const knoepfe = boxen.length ? [{
    text: 'Freigeben', haupt: true,
    fn: async () => {
      const ids = boxen.map((b) => b.querySelector('input')).filter((c) => c.checked).map((c) => c.dataset.id);
      if (!ids.length) return;
      try {
        await api('/api/freigeben', { schritte: ids });
      } catch (err) {
        melden(err.message);
      }
      aktualisieren();
    },
  }] : [];
  zeigeDialog('GPU freigeben', inhalt, knoepfe, boxen.length ? 'Abbrechen' : 'Schließen');
}

// ------------------------------------------------------------------ Kopf und Protokoll

function kopfZeichnen(verbunden) {
  const stand = $('#stand');
  stand.classList.toggle('getrennt', !verbunden);
  if (!verbunden) {
    stand.textContent = 'Keine Verbindung zum Dienst der Modellzentrale.';
  } else if (STAND) {
    stand.textContent = `Stand ${uhrzeit(new Date(STAND.zeit * 1000))}`
      + (KONFIG.vram_je_prozess ? '' : ' · Belegung je Programm nicht verfügbar');
  }
  $('#aktion').hidden = !AKTION;
  $('#aktion-text').textContent = AKTION ? AKTION.text : '';
  $('#freigeben').disabled = !!AKTION || !verbunden;
}

function protokollZeichnen() {
  const alle = [...lokaleMeldungen, ...PROTOKOLL].sort((a, b) => (a.zeit < b.zeit ? 1 : -1)).slice(0, 12);
  $('#protokoll').replaceChildren(...(alle.length
    ? alle.map((p) => h('li', { class: p.art }, h('time', { text: p.zeit }), h('span', { text: p.text })))
    : [h('li', { class: 'leer', text: 'Noch keine Aktionen seit dem Start des Dienstes.' })]));
}

// ------------------------------------------------------------------ Ablauf

async function aktualisieren() {
  try {
    const s = await api('/api/status');
    if (s.stand) {
      const t = Math.round(s.stand.zeit);
      if (!VERLAUF.length || VERLAUF[VERLAUF.length - 1].t !== t) {
        VERLAUF.push({ t, k: s.stand.karten.map((k) => [k.index, k.belegt, k.temp, k.last, k.watt]) });
        if (VERLAUF.length > 300) VERLAUF.shift();
      }
      STAND = s.stand;
    }
    AKTION = s.aktion;
    PROTOKOLL = s.protokoll;
    kopfZeichnen(true);
    if (STAND) {
      kartenZeichnen();
      zeilenZeichnen();
    }
    protokollZeichnen();
  } catch {
    kopfZeichnen(false);
  }
}

function schleife() {
  aktualisieren().finally(() => setTimeout(schleife, AKTION ? 1000 : 2000));
}

async function beginnen() {
  try {
    KONFIG = await api('/api/konfig');
    VERLAUF = await api('/api/verlauf');
  } catch {
    kopfZeichnen(false);
    return setTimeout(beginnen, 3000);
  }
  zeilenAnlegen();
  $('#freigeben').addEventListener('click', gpuFreigeben);
  schleife();
}

beginnen();
