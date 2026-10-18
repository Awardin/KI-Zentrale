'use strict';

// ------------------------------------------------------------------ Hilfen

const $ = (sel) => document.querySelector(sel);

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
const uhrzeit = (d = new Date()) => d.toLocaleTimeString('de-DE');
const dauer = (s) => {
  if (s == null) return '';
  s = Math.round(s);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min ${String(s % 60).padStart(2, '0')} s` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min`;
};
const ungefaehr = (s) => (s < 60 ? 'unter einer Minute' : `etwa ${Math.round(s / 60)} min`);

async function api(pfad, daten) {
  const opt = daten === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Werkstatt': '1' },
    body: JSON.stringify(daten),
  };
  const r = await fetch(pfad, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.fehler || `Der Dienst antwortete mit Fehler ${r.status}.`);
  return j;
}

let STAND = null;
const zeilen = new Map();

function modus() { return document.querySelector('input[name="modus"]:checked').value; }
function sprache() { return $('#sprache').value; }

// Die letzte Auswahl bleibt für das nächste Öffnen erhalten (nur in diesem Fenster).
function auswahlLaden() {
  try {
    const m = localStorage.getItem('werkstatt.modus');
    const s = localStorage.getItem('werkstatt.sprache');
    if (m) document.querySelector(`input[name="modus"][value="${m}"]`)?.click();
    if (s) $('#sprache').value = s;
  } catch { /* ohne Speicher geht es auch */ }
}
function auswahlMerken() {
  try {
    localStorage.setItem('werkstatt.modus', modus());
    localStorage.setItem('werkstatt.sprache', sprache());
  } catch { /* egal */ }
}

// ------------------------------------------------------------------ Rückmeldung

function rueckmeldung(e) {
  const box = $('#rueckmeldung');
  const teile = [];
  if (e.neu) {
    const echt = e.neu - (e.erledigt || 0);
    if (echt) teile.push(`${echt} ${echt === 1 ? 'Auftrag' : 'Aufträge'} hinzugefügt`);
    if (e.erledigt) teile.push(`${e.erledigt} bereits erledigt und übersprungen`);
  }
  if (e.doppelt?.length) teile.push(`${e.doppelt.length} ${e.doppelt.length === 1 ? 'stand' : 'standen'} schon in der Warteschlange`);
  const kinder = [];
  if (teile.length) kinder.push(h('p', { class: e.neu ? 'ok' : '', text: `${teile.join(' · ')}.` }));
  if (e.nicht_gefunden?.length) {
    kinder.push(h('p', {},
      `Nicht zugeordnet: ${e.nicht_gefunden.join(', ')}. Die Werkstatt erkennt abgelegte Dateien an ihrer Markierung im Explorer; `
      + 'vom Desktop, aus Suchergebnissen oder ZIP-Dateien geht das nicht. ',
      h('button', { class: 'knopf knopf-klein', type: 'button', onclick: waehlen }, 'Dateien wählen …')));
  }
  if (e.fehler?.length) kinder.push(h('ul', {}, ...e.fehler.map((f) => h('li', { text: f }))));
  if (!kinder.length && e.abgebrochen) return;
  if (!kinder.length) kinder.push(h('p', { text: 'Nichts hinzugefügt.' }));
  box.replaceChildren(...kinder);
}

function fehlerMelden(text) {
  const ziel = !$('#reiter-texterkennung').hidden ? '#te-rueck'
    : $('#reiter-zusammenfassung').hidden ? ($('#reiter-messungen').hidden ? '#rueckmeldung' : '#m-zustand') : '#zf-rueck';
  $(ziel).replaceChildren(h('ul', {}, h('li', { text })));
}

const REITER = ['transkription', 'zusammenfassung', 'bildvideo', 'texterkennung', 'messungen'];

// ------------------------------------------------------------------ Reiter

function reiterZeigen(name) {
  for (const b of document.querySelectorAll('.reiter button[data-reiter]')) {
    const aktiv = b.dataset.reiter === name;
    b.classList.toggle('aktiv', aktiv);
    if (aktiv) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  }
  for (const r of REITER) $(`#reiter-${r}`).hidden = r !== name;
  if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  window.zusammenfassungAktiv?.(name === 'zusammenfassung');
  window.bildvideoAktiv?.(name === 'bildvideo');
  window.messungenAktiv?.(name === 'messungen');
  window.texterkennungAktiv?.(name === 'texterkennung');
}

// ------------------------------------------------------------------ Hinzufügen

async function hinzufuegen() {
  const text = $('#text').value;
  if (!text.trim()) return $('#text').focus();
  auswahlMerken();
  try {
    const e = await api('/api/hinzufuegen', { text, modus: modus(), sprache: sprache() });
    rueckmeldung(e);
    if (e.neu && !e.fehler.length) $('#text').value = '';
  } catch (err) {
    fehlerMelden(err.message);
  }
  aktualisieren();
}

async function waehlen() {
  auswahlMerken();
  const knopf = $('#waehlen');
  knopf.disabled = true;
  try {
    rueckmeldung(await api('/api/waehlen', { modus: modus(), sprache: sprache() }));
  } catch (err) {
    fehlerMelden(err.message);
  } finally {
    knopf.disabled = false;
  }
  aktualisieren();
}

async function ablegen(eintraege) {
  if (!eintraege.length) return;
  auswahlMerken();
  $('#rueckmeldung').replaceChildren(h('p', { class: 'leise', text: 'Abgelegte Dateien werden im Explorer gesucht …' }));
  try {
    rueckmeldung(await api('/api/ablegen', { eintraege, modus: modus(), sprache: sprache() }));
  } catch (err) {
    fehlerMelden(err.message);
  }
  aktualisieren();
}

// Beim Ablegen liefert das Fenster Namen, Größe und Änderungszeit, aber keinen Speicherort.
// Im Reiter Texterkennung gehen abgelegte Dateien dorthin, sonst in die Transkription.
function einrichtenAblegen() {
  const ueberall = $('#ueberall');
  const texterkennung = () => !$('#reiter-texterkennung').hidden;
  let ablage = $('#ablage');
  let tiefe = 0;
  const hatDateien = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
  document.addEventListener('dragenter', (e) => {
    if (!hatDateien(e)) return;
    tiefe += 1;
    ueberall.hidden = false;
    ablage = texterkennung() ? $('#te-ablage') : $('#ablage');
    ablage.classList.add('ueber');
  });
  document.addEventListener('dragleave', () => {
    tiefe = Math.max(0, tiefe - 1);
    if (!tiefe) { ueberall.hidden = true; ablage.classList.remove('ueber'); }
  });
  document.addEventListener('dragover', (e) => {
    if (!hatDateien(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  document.addEventListener('drop', (e) => {
    if (!hatDateien(e)) return;
    e.preventDefault();
    tiefe = 0;
    ueberall.hidden = true;
    ablage.classList.remove('ueber');
    const zurTexterkennung = texterkennung();
    if (!zurTexterkennung && $('#reiter-transkription').hidden) reiterZeigen('transkription');
    const eintraege = [];
    for (const item of e.dataTransfer.items) {
      if (item.kind !== 'file') continue;
      const eintrag = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
      const datei = item.getAsFile();
      if (eintrag?.isDirectory) eintraege.push({ name: eintrag.name, ordner: true });
      else if (datei) eintraege.push({ name: datei.name, groesse: datei.size, geaendert: datei.lastModified });
    }
    if (zurTexterkennung) window.texterkennungAblegen?.(eintraege);
    else ablegen(eintraege);
  });
}

// ------------------------------------------------------------------ Kopf

function kopfZeichnen(verbunden) {
  const stand = $('#stand');
  stand.classList.toggle('getrennt', !verbunden);
  stand.textContent = verbunden ? `Stand ${uhrzeit()}` : 'Keine Verbindung zum Dienst der Werkstatt.';
  const mini = $('#gpu-mini');
  const k = STAND?.karten;
  if (!verbunden || !k) return mini.replaceChildren();
  if (k.erreichbar === false) {
    return mini.replaceChildren(h('p', { class: 'gk-aus', text: 'Modellzentrale läuft nicht. Sie startet beim nächsten Auftrag mit.' }));
  }
  // Kartenband (Bernstein-Design, 16.10.2026): je RTX 3090 Verbraucher, Belegung, Auslastung als Segmentleiste und
  // Verlauf. Alles aus dem echten Stand der Zentrale (`/api/platz`, alle 5 s); der Verlauf merkt sich die letzten Werte.
  const verbraucher = k.verbraucher || [];
  if (k.zeit && k.zeit !== VERLAUF.zeit) {
    VERLAUF.zeit = k.zeit;
    for (const c of k.karten) {
      const liste = VERLAUF.last[c.index] || (VERLAUF.last[c.index] = []);
      liste.push(Math.max(0, Math.min(100, Number(c.last) || 0)));
      if (liste.length > 72) liste.shift();
    }
  }
  const aktiv = k.karten.filter((c) => (c.last ?? 0) >= 30);
  const parallel = aktiv.length >= 2 ? 'Beide Karten rechnen parallel'
    : aktiv.length === 1 ? `${aktiv[0].kurz} rechnet` : 'Beide Karten sind frei';
  mini.replaceChildren(...k.karten.map((c) => {
    const last = Math.round(c.last ?? 0);
    const wer = verbraucher
      .map((v) => ({ name: v.name, farbe: v.farbe || '#BDB4A5', mib: Number(v.mib_je_karte?.[String(c.index)] || 0) }))
      .filter((v) => v.mib >= 256)
      .sort((x, y) => y.mib - x.mib)
      .slice(0, 3)
      .map((v) => h('li', { style: `--f:${v.farbe}` }, h('span', { text: v.name }), h('em', { text: `${gib(v.mib)} GiB` })));
    const segmente = Array.from({ length: 24 }, (_, i) => h('i', { class: i < Math.round(last / 100 * 24) ? 'an' : '' }));
    return h('div', { class: `gk${last >= 30 ? ' aktiv' : ''}`,
      title: `${c.kurz}: ${gib(c.frei)} GiB frei für neue Aufträge (nach der Reserve der Modellzentrale).` },
      h('div', { class: 'gk-kopf' }, h('b', { text: c.kurz }),
        h('span', { class: 'gk-speicher', text: `${gib(c.belegt)} / ${gib(c.gesamt)} GiB` })),
      h('ul', { class: 'gk-wer' }, ...(wer.length ? wer : [h('li', { text: 'nichts geladen' })])),
      h('div', { class: 'gk-last' }, h('span', {}, 'Auslastung', h('em', { text: `${last} %` })),
        kurve(VERLAUF.last[c.index] || [])),
      h('div', { class: 'gk-meter', 'aria-label': `Auslastung ${last} %` }, ...segmente));
  }), h('p', { class: `gk-parallel${aktiv.length >= 2 ? ' beide' : ''}`, text: parallel }));
}

// Verlauf der Auslastung als kleine Kurve (SVG, 0–100 %).
const VERLAUF = { zeit: null, last: {} };
function kurve(werte) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', 'gk-kurve');
  svg.setAttribute('viewBox', '0 0 100 34');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('aria-hidden', 'true');
  if (werte.length < 2) return svg;
  const x = (i) => (i / (werte.length - 1) * 100).toFixed(2);
  const y = (w) => (32 - w / 100 * 30).toFixed(2);
  const linie = werte.map((w, i) => `${i ? 'L' : 'M'}${x(i)},${y(w)}`).join(' ');
  const flaeche = document.createElementNS(ns, 'path');
  flaeche.setAttribute('class', 'flaeche');
  flaeche.setAttribute('d', `${linie} L100,34 L0,34 Z`);
  const pfad = document.createElementNS(ns, 'path');
  pfad.setAttribute('d', linie);
  svg.append(flaeche, pfad);
  return svg;
}

// ------------------------------------------------------------------ Warteschlange

const ZUSTAND = {
  wartet: 'Wartet', laeuft: 'Läuft', fertig: 'Fertig', uebersprungen: 'Bereits erledigt',
  fehler: 'Fehlgeschlagen', abgebrochen: 'Abgebrochen',
};

function schrittListe(a) {
  const s = [['pruefen', 'Prüfen']];
  if (a.art === 'youtube') s.push(['laden', 'Laden']);
  s.push(['transkription', 'Transkription']);
  if (a.modus === '0b') s.push(['bilder', 'Bilder']);
  return s;
}

function laufText(a) {
  const f = a.fortschritt || {};
  switch (a.schritt) {
    case 'pruefen':
      return { text: f.anteil != null ? `Datei wird geprüft · ${Math.round(f.anteil * 100)} %` : a.meldung, anteil: f.anteil };
    case 'laden':
      return { text: `${a.meldung} ${f.mb ? `· ${f.mb.toLocaleString('de-DE')} MB` : ''}`, anteil: null };
    case 'platz':
      return { text: a.meldung, anteil: null };
    case 'transkription': {
      const wo = a.karten ? ` · ${a.karten}` : '';
      if (f.phase !== 'abschnitte') return { text: `Bereitet vor (Pausen suchen, Abschnitte schneiden) · ${dauer(f.sekunden)}${wo}`, anteil: null };
      const rest = f.rest_s != null && f.fertig < f.gesamt ? ` · noch ${ungefaehr(f.rest_s)}` : '';
      const ersatz = f.ersatz ? ' · Wiederholung mit einem Worker' : '';
      return { text: `Abschnitt ${f.fertig} von ${f.gesamt} fertig${rest}${wo}${ersatz}`, anteil: f.anteil ?? 0 };
    }
    case 'bilder': {
      const teil = f.teile > 1 ? ` · Teil ${f.teil} von ${f.teile}` : '';
      return { text: `Originalbilder werden gewonnen · ${f.bilder ?? 0} Bilder${teil}`, anteil: null };
    }
    default:
      return { text: a.meldung || '', anteil: null };
  }
}

function zeileAnlegen(a) {
  const r = {
    titel: h('h3'), herkunft: h('p', { class: 'a-herkunft' }), pille: h('span', { class: 'pille' }),
    schritte: h('ol', { class: 'schritte', 'aria-hidden': 'true' }), balken: h('div', { class: 'balken' }, h('i')),
    meldung: h('p', { class: 'a-meldung' }), hinweis: h('p', { class: 'a-hinweis' }),
    knoepfe: h('div', { class: 'a-knoepfe' }), schluessel: '',
  };
  r.el = h('li', { class: 'auftrag' },
    h('div', { class: 'a-kennung' }),
    h('div', { class: 'a-text' }, r.titel, r.herkunft),
    h('div', { class: 'a-zustand', 'aria-live': 'polite' }, r.pille, r.schritte, r.balken, r.meldung, r.hinweis),
    r.knoepfe);
  return r;
}

function knopf(text, fn, { titel, haupt, klein = true, symbol } = {}) {
  return h('button', {
    type: 'button', title: titel, 'aria-label': titel,
    class: `knopf${klein ? ' knopf-klein' : ''}${haupt ? ' knopf-haupt' : ''}${symbol ? ' knopf-symbol' : ''}`,
    onclick: async (e) => {
      e.currentTarget.disabled = true;
      try { await fn(); } catch (err) { fehlerMelden(err.message); }
      aktualisieren();
    },
  }, text);
}

const auftrag = (a, aktion, wert) => api('/api/auftrag', { id: a.id, aktion, wert });

function abbrechenFragen(a) {
  const d = $('#dialog');
  d.classList.remove('gross');
  d.replaceChildren(
    h('h2', { id: 'dialog-titel', text: 'Auftrag abbrechen?' }),
    h('p', { text: `„${a.titel}“ wird sofort beendet, auch alle Whisper-Worker. Bereits Erzeugtes bleibt im Ordner; ein neuer Versuch schreibt in einen eigenen Unterordner.` }),
    h('div', { class: 'dialog-knoepfe' },
      h('button', { class: 'knopf', type: 'button', onclick: () => d.close() }, 'Weiterlaufen lassen'),
      h('button', {
        class: 'knopf knopf-haupt', type: 'button',
        onclick: async () => { d.close(); try { await auftrag(a, 'abbrechen'); } catch (err) { fehlerMelden(err.message); } aktualisieren(); },
      }, 'Abbrechen')));
  d.showModal();
}

function knoepfeFuer(a, istErsterWartender, istLetzterWartender) {
  const out = [];
  const oeffnen = a.ordner ? knopf('Ordner öffnen', () => api('/api/ordner', { id: a.id })) : null;
  switch (a.zustand) {
    case 'wartet': {
      const wahl = h('select', { 'aria-label': 'Modus', title: 'Modus' },
        h('option', { value: '0', text: '0 · Transkript' }), h('option', { value: '0b', text: '0b · mit Bildern' }));
      wahl.value = a.modus;
      wahl.addEventListener('change', async () => {
        try { await auftrag(a, 'modus', wahl.value); } catch (err) { fehlerMelden(err.message); }
        aktualisieren();
      });
      out.push(wahl,
        knopf('↑', () => auftrag(a, 'hoch'), { titel: 'Nach vorn', symbol: true }),
        knopf('↓', () => auftrag(a, 'runter'), { titel: 'Nach hinten', symbol: true }),
        knopf('Entfernen', () => auftrag(a, 'entfernen')));
      out[1].disabled = istErsterWartender;
      out[2].disabled = istLetzterWartender;
      break;
    }
    case 'laeuft':
      if (a.schritt === 'platz') out.push(knopf('Jetzt erneut prüfen', () => auftrag(a, 'erneut')));
      if (oeffnen) out.push(oeffnen);
      out.push(knopf('Abbrechen …', () => abbrechenFragen(a)));
      break;
    case 'fehler':
    case 'abgebrochen':
      out.push(knopf('Wiederholen', () => auftrag(a, 'wiederholen'), { haupt: true }));
      if (oeffnen) out.push(oeffnen);
      out.push(knopf('Entfernen', () => auftrag(a, 'entfernen')));
      break;
    default:
      if (a.ordner) out.push(knopf('Zusammenfassen', () => window.zusammenfassungOeffnen(a.ordner), { haupt: true }));
      if (oeffnen) out.push(oeffnen);
      out.push(knopf('Entfernen', () => auftrag(a, 'entfernen')));
  }
  return out;
}

function zeileFuellen(r, a, wartende) {
  r.el.dataset.zustand = a.zustand;
  r.titel.textContent = a.titel || a.quelle;
  r.titel.title = a.titel || a.quelle;
  const herkunft = [];
  herkunft.push(h('span', { class: `marke${a.modus === '0b' ? ' bild' : ''}`, title: a.modus === '0b' ? 'Transkript + Originalbilder' : 'Nur Transkript', text: a.modus }));
  if (a.sprache && a.sprache !== 'auto') herkunft.push(h('span', { class: 'marke', text: a.sprache }));
  if (a.art === 'youtube') herkunft.push(h('span', { text: `YouTube · ${a.video_id}` }));
  else herkunft.push(h('span', { class: 'pfad', title: a.quelle, text: a.quelle }));
  if (a.dauer) herkunft.push(h('span', { text: dauer(a.dauer) }));
  r.herkunft.replaceChildren(...herkunft);

  r.pille.textContent = ZUSTAND[a.zustand] || a.zustand;
  const laeuft = a.zustand === 'laeuft';
  r.schritte.hidden = !laeuft;
  r.balken.hidden = !laeuft;
  if (laeuft) {
    const liste = schrittListe(a);
    const jetzt = a.schritt === 'platz' ? 'transkription' : a.schritt;
    const pos = liste.findIndex(([id]) => id === jetzt);
    r.schritte.replaceChildren(...liste.map(([, name], i) => h('li', { class: i < pos ? 'fertig' : i === pos ? 'jetzt' : '', text: name })));
    const { text, anteil } = laufText(a);
    r.balken.classList.toggle('offen', anteil == null);
    r.balken.firstChild.style.width = `${Math.round((anteil ?? 0) * 100)}%`;
    r.meldung.textContent = text;
  } else {
    let text = a.meldung || '';
    if (a.zustand === 'wartet') text = 'Wartet auf die vorherigen Aufträge.';
    if (a.zustand === 'fertig' && a.karten) text += ` ${a.karten}.`;
    r.meldung.textContent = text;
  }
  r.hinweis.textContent = a.hinweis || '';
  r.hinweis.hidden = !a.hinweis;

  const i = wartende.indexOf(a.id);
  const schluessel = [a.zustand, a.schritt === 'platz', !!a.ordner, a.modus, i === 0, i === wartende.length - 1].join('|');
  if (schluessel !== r.schluessel) {
    r.schluessel = schluessel;
    r.knoepfe.replaceChildren(...knoepfeFuer(a, i === 0, i === wartende.length - 1));
  }
}

// Oben das Laufende, dann die Warteschlange in ihrer Reihenfolge, darunter Erledigtes, neuestes zuerst.
function anzeigeReihenfolge(liste) {
  const rang = (a) => ({ laeuft: 0, wartet: 1 }[a.zustand] ?? 2);
  return liste.map((a, i) => ({ a, i }))
    .sort((x, y) => rang(x.a) - rang(y.a) || (rang(x.a) < 2 ? x.i - y.i : (y.a.beendet || 0) - (x.a.beendet || 0)))
    .map((x) => x.a);
}

function schlangeZeichnen() {
  const liste = $('#auftraege');
  const auftraege = anzeigeReihenfolge(STAND.auftraege);
  const wartende = auftraege.filter((a) => a.zustand === 'wartet').map((a) => a.id);
  const ids = new Set(auftraege.map((a) => a.id));
  for (const [id, r] of zeilen) if (!ids.has(id)) { r.el.remove(); zeilen.delete(id); }
  if (!auftraege.length) {
    liste.replaceChildren(h('li', { class: 'leer', text: 'Noch keine Aufträge. Ziehe Dateien hierher oder füge YouTube-Links ein.' }));
  } else {
    liste.querySelector('.leer')?.remove();
    auftraege.forEach((a, i) => {
      let r = zeilen.get(a.id);
      if (!r) { r = zeileAnlegen(a); zeilen.set(a.id, r); }
      zeileFuellen(r, a, wartende);
      if (liste.children[i] !== r.el) liste.insertBefore(r.el, liste.children[i] || null);
    });
  }
  const n = (z) => auftraege.filter((a) => a.zustand === z).length;
  const teile = [];
  if (n('laeuft')) teile.push('1 läuft');
  if (n('wartet')) teile.push(`${n('wartet')} ${n('wartet') === 1 ? 'wartet' : 'warten'}`);
  if (n('fertig') + n('uebersprungen')) teile.push(`${n('fertig') + n('uebersprungen')} erledigt`);
  if (n('fehler')) teile.push(`${n('fehler')} fehlgeschlagen`);
  if (STAND.angehalten) teile.push('angehalten: nach dem laufenden Auftrag beginnt kein neuer');
  $('#zaehler').textContent = teile.join(' · ');
  const knopfAnhalten = $('#anhalten');
  knopfAnhalten.textContent = STAND.angehalten ? 'Fortsetzen' : 'Anhalten';
  knopfAnhalten.classList.toggle('knopf-haupt', STAND.angehalten);
  $('#aufraeumen').disabled = !(n('fertig') + n('uebersprungen'));
}

// ------------------------------------------------------------------ Ablauf

async function aktualisieren() {
  try {
    STAND = await api('/api/stand');
    kopfZeichnen(true);
    schlangeZeichnen();
  } catch {
    kopfZeichnen(false);
  }
}

function schleife() {
  const laeuft = STAND?.auftraege.some((a) => a.zustand === 'laeuft');
  aktualisieren().finally(() => setTimeout(schleife, laeuft ? 1000 : 2500));
}

$('#hinzufuegen').addEventListener('click', hinzufuegen);
$('#text').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) hinzufuegen(); });
$('#waehlen').addEventListener('click', waehlen);
$('#anhalten').addEventListener('click', async () => {
  try { await api('/api/warteschlange', { aktion: STAND?.angehalten ? 'fortsetzen' : 'anhalten' }); } catch (err) { fehlerMelden(err.message); }
  aktualisieren();
});
$('#aufraeumen').addEventListener('click', async () => {
  try { await api('/api/warteschlange', { aktion: 'aufraeumen' }); } catch (err) { fehlerMelden(err.message); }
  aktualisieren();
});
$('#zentrale').addEventListener('click', () => api('/api/zentrale', {}).catch((err) => fehlerMelden(err.message)));
for (const r of document.querySelectorAll('input[name="modus"], #sprache')) r.addEventListener('change', auswahlMerken);
for (const b of document.querySelectorAll('.reiter button[data-reiter]')) b.addEventListener('click', () => reiterZeigen(b.dataset.reiter));
auswahlLaden();
einrichtenAblegen();
schleife();
window.addEventListener('load', () => reiterZeigen(REITER.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'transkription'));
