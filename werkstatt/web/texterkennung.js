'use strict';

// Reiter Texterkennung („PDF/Scan lesen“) mit LightOnOCR aus der Modellzentrale.

const TE = { aktiv: false, stand: null, zeilen: new Map(), zeitgeber: null };

const TE_ZUSTAND = { wartet: 'Wartet', laeuft: 'Läuft', fertig: 'Fertig', fehler: 'Fehlgeschlagen', abgebrochen: 'Abgebrochen' };

function teRueck(e) {
  const kinder = [];
  if (e.neu) kinder.push(h('p', { class: 'ok', text: `${e.neu} ${e.neu === 1 ? 'Datei' : 'Dateien'} zum Lesen eingereiht.` }));
  if (e.doppelt?.length) kinder.push(h('p', { text: `Schon in der Warteschlange: ${e.doppelt.join(', ')}.` }));
  if (e.nicht_gefunden?.length) {
    kinder.push(h('p', {},
      `Nicht zugeordnet: ${e.nicht_gefunden.join(', ')}. Abgelegte Dateien werden an ihrer Markierung im Explorer erkannt; `
      + 'vom Desktop, aus Suchergebnissen oder ZIP-Dateien geht das nicht. ',
      h('button', { class: 'knopf knopf-klein', type: 'button', onclick: teWaehlen }, 'Dateien wählen …')));
  }
  if (e.fehler?.length) kinder.push(h('ul', {}, ...e.fehler.map((f) => h('li', { text: f }))));
  if (!kinder.length && e.abgebrochen) return;
  if (!kinder.length) kinder.push(h('p', { text: 'Nichts eingereiht.' }));
  $('#te-rueck').replaceChildren(...kinder);
}

function teFehler(text) {
  $('#te-rueck').replaceChildren(h('ul', {}, h('li', { text })));
}

const teApi = (daten) => api('/api/texterkennung', daten);

async function teHinzufuegen() {
  const text = $('#te-text').value;
  if (!text.trim()) return $('#te-text').focus();
  try {
    const e = await teApi({ aktion: 'hinzufuegen', text, seiten: $('#te-seiten').value });
    teRueck(e);
    if (e.neu && !e.fehler.length) $('#te-text').value = '';
  } catch (err) { teFehler(err.message); }
  teAktualisieren();
}

async function teWaehlen() {
  const knopf = $('#te-waehlen');
  knopf.disabled = true;
  try { teRueck(await teApi({ aktion: 'waehlen', seiten: $('#te-seiten').value })); } catch (err) { teFehler(err.message); }
  knopf.disabled = false;
  teAktualisieren();
}

window.texterkennungAblegen = async (eintraege) => {
  if (!eintraege.length) return;
  $('#te-rueck').replaceChildren(h('p', { class: 'leise', text: 'Abgelegte Dateien werden im Explorer gesucht …' }));
  try { teRueck(await teApi({ aktion: 'ablegen', eintraege, seiten: $('#te-seiten').value })); } catch (err) { teFehler(err.message); }
  teAktualisieren();
};

// ------------------------------------------------------------------ Liste

function teKnopf(text, fn, { haupt } = {}) {
  return h('button', {
    type: 'button', class: `knopf knopf-klein${haupt ? ' knopf-haupt' : ''}`,
    onclick: async (e) => {
      e.currentTarget.disabled = true;
      try { await fn(); } catch (err) { teFehler(err.message); }
      teAktualisieren();
    },
  }, text);
}

function teKnoepfe(a) {
  const tun = (aktion) => () => teApi({ aktion, id: a.id });
  const ordner = a.ordner ? teKnopf('Ordner öffnen', tun('ordner')) : null;
  switch (a.zustand) {
    case 'wartet':
      return [teKnopf('Entfernen', tun('entfernen'))];
    case 'laeuft':
      return [ordner, teKnopf('Abbrechen', tun('abbrechen'))];
    case 'fehler':
    case 'abgebrochen':
      return [teKnopf(a.fertig ? 'Fortsetzen' : 'Wiederholen', tun('wiederholen'), { haupt: true }), ordner,
        teKnopf('Entfernen', tun('entfernen'))];
    default:
      return [a.volltext ? teKnopf('Volltext öffnen', tun('volltext'), { haupt: true }) : null, ordner,
        teKnopf('Entfernen', tun('entfernen'))];
  }
}

function teZeileAnlegen() {
  const r = {
    titel: h('h3'), herkunft: h('p', { class: 'a-herkunft' }), pille: h('span', { class: 'pille' }),
    balken: h('div', { class: 'balken' }, h('i')), meldung: h('p', { class: 'a-meldung' }),
    hinweis: h('p', { class: 'a-hinweis' }), knoepfe: h('div', { class: 'a-knoepfe' }), schluessel: '',
  };
  r.el = h('li', { class: 'auftrag te-auftrag' },
    h('div', { class: 'a-kennung' }),
    h('div', { class: 'a-text' }, r.titel, r.herkunft),
    h('div', { class: 'a-zustand', 'aria-live': 'polite' }, r.pille, r.balken, r.meldung, r.hinweis),
    r.knoepfe);
  return r;
}

function teZeileFuellen(r, a) {
  r.el.dataset.zustand = a.zustand;
  r.titel.textContent = a.titel;
  r.titel.title = a.quelle;
  const herkunft = [h('span', { class: 'pfad', title: a.quelle, text: a.quelle })];
  if (a.seiten_wahl) herkunft.unshift(h('span', { class: 'marke', title: 'Gewählte Seiten', text: `S. ${a.seiten_wahl}` }));
  else if (a.seiten) herkunft.push(h('span', { text: `${a.seiten} ${a.seiten === 1 ? 'Seite' : 'Seiten'}` }));
  r.herkunft.replaceChildren(...herkunft);
  r.pille.textContent = TE_ZUSTAND[a.zustand] || a.zustand;
  const laeuft = a.zustand === 'laeuft';
  r.balken.hidden = !laeuft;
  if (laeuft) {
    const anteil = a.seiten ? a.fertig / a.seiten : null;
    r.balken.classList.toggle('offen', anteil == null);
    r.balken.firstChild.style.width = `${Math.round((anteil ?? 0) * 100)}%`;
    const rest = a.seiten ? (a.seiten - a.fertig) * (TE.stand?.sekunden_je_seite || 6.5) : null;
    r.meldung.textContent = a.meldung + (a.seiten ? ` · ${a.fertig} von ${a.seiten} fertig${rest ? ` · noch ${ungefaehr(rest)}` : ''}` : '');
  } else {
    r.meldung.textContent = a.zustand === 'wartet' ? 'Wartet auf die vorherigen Aufträge.' : (a.meldung || '');
  }
  r.hinweis.textContent = a.hinweis || '';
  r.hinweis.hidden = !a.hinweis;
  const schluessel = [a.zustand, !!a.ordner, !!a.volltext, !!a.fertig].join('|');
  if (schluessel !== r.schluessel) {
    r.schluessel = schluessel;
    r.knoepfe.replaceChildren(...teKnoepfe(a).filter(Boolean));
  }
}

function teZeichnen() {
  const s = TE.stand;
  const m = s.modell;
  const modell = $('#te-modell');
  modell.classList.toggle('aus', !m.bereit);
  modell.replaceChildren(m.bereit
    ? h('span', { text: `${m.name} ist bereit${m.karte ? ` (${m.karte})` : ''}.` })
    : h('span', {}, `${m.name} läuft nicht. Bitte in der Modellzentrale starten (${m.karten}). `,
      h('button', { class: 'knopf knopf-klein', type: 'button', onclick: () => api('/api/zentrale', {}).catch((e) => teFehler(e.message)) },
        'Modellzentrale öffnen')));
  $('#te-pruefen').textContent = s.hinweis_pruefen;

  const liste = $('#te-auftraege');
  const rang = (a) => ({ laeuft: 0, wartet: 1 }[a.zustand] ?? 2);
  const auftraege = s.auftraege.map((a, i) => ({ a, i }))
    .sort((x, y) => rang(x.a) - rang(y.a) || (rang(x.a) < 2 ? x.i - y.i : (y.a.beendet || 0) - (x.a.beendet || 0)))
    .map((x) => x.a);
  const ids = new Set(auftraege.map((a) => a.id));
  for (const [id, r] of TE.zeilen) if (!ids.has(id)) { r.el.remove(); TE.zeilen.delete(id); }
  if (!auftraege.length) {
    liste.replaceChildren(h('li', { class: 'leer', text: 'Noch nichts gelesen. Ziehe PDFs oder Bilder hierher.' }));
  } else {
    liste.querySelector('.leer')?.remove();
    auftraege.forEach((a, i) => {
      let r = TE.zeilen.get(a.id);
      if (!r) { r = teZeileAnlegen(); TE.zeilen.set(a.id, r); }
      teZeileFuellen(r, a);
      if (liste.children[i] !== r.el) liste.insertBefore(r.el, liste.children[i] || null);
    });
  }
  const n = (z) => auftraege.filter((a) => a.zustand === z).length;
  const teile = [];
  if (n('laeuft')) teile.push('1 läuft');
  if (n('wartet')) teile.push(`${n('wartet')} ${n('wartet') === 1 ? 'wartet' : 'warten'}`);
  if (n('fertig')) teile.push(`${n('fertig')} fertig`);
  if (n('fehler')) teile.push(`${n('fehler')} fehlgeschlagen`);
  $('#te-zaehler').textContent = teile.join(' · ');
  $('#te-aufraeumen').disabled = !n('fertig');
}

async function teAktualisieren() {
  try {
    TE.stand = await api('/api/texterkennung');
    teZeichnen();
  } catch { /* der Kopf zeigt die fehlende Verbindung */ }
}

function teSchleife() {
  clearTimeout(TE.zeitgeber);
  if (!TE.aktiv) return;
  const laeuft = TE.stand?.auftraege.some((a) => a.zustand === 'laeuft');
  teAktualisieren().finally(() => { TE.zeitgeber = setTimeout(teSchleife, laeuft ? 1000 : 3000); });
}

window.texterkennungAktiv = (aktiv) => {
  TE.aktiv = aktiv;
  if (aktiv) teSchleife();
};

$('#te-hinzufuegen').addEventListener('click', teHinzufuegen);
$('#te-text').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) teHinzufuegen(); });
$('#te-waehlen').addEventListener('click', teWaehlen);
$('#te-aufraeumen').addEventListener('click', async () => {
  try { await teApi({ aktion: 'aufraeumen' }); } catch (err) { teFehler(err.message); }
  teAktualisieren();
});
