'use strict';

// Reiter Zusammenfassung. Nutzt die Hilfen aus app.js ($, h, api, dauer, knopf).

const ZF = {
  transkripte: [], stand: null, katalog: null, gewaehlt: null, texte: new Map(), zeilen: new Map(), aktiv: false,
  auswerterWahl: new Set(), anweisungWahl: new Set(),
};

function zfMerken() {
  try {
    localStorage.setItem('werkstatt.zf', JSON.stringify({
      auswerter: [...ZF.auswerterWahl], anweisungen: [...ZF.anweisungWahl],
      anordnung: document.querySelector('.umschalter .aktiv')?.dataset.anordnung,
    }));
  } catch { /* egal */ }
}

function zfLaden() {
  try {
    const d = JSON.parse(localStorage.getItem('werkstatt.zf') || '{}');
    (d.auswerter || []).forEach((x) => ZF.auswerterWahl.add(x));
    (d.anweisungen || []).forEach((x) => ZF.anweisungWahl.add(x));
    if (d.anordnung) anordnungSetzen(d.anordnung);
  } catch { /* egal */ }
}

const ZF_ZUSTAND = { wartet: 'Wartet', laeuft: 'Läuft', fertig: 'Fertig', fehler: 'Fehlgeschlagen', abgebrochen: 'Abgebrochen' };

// ------------------------------------------------------------------ Markdown (einfach und sicher)

function markdown(text) {
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  text = text.replace(/\r\n/g, '\n').replace(/^---\n[\s\S]*?\n---\n/, '');
  const out = [];
  let liste = null;
  let absatz = [];
  let tabelle = [];
  const absatzEnde = () => { if (absatz.length) { out.push(`<p>${absatz.map(inline).join('<br>')}</p>`); absatz = []; } };
  const listeEnde = () => { if (liste) { out.push(`</${liste}>`); liste = null; } };
  const tabelleEnde = () => {
    if (!tabelle.length) return;
    const zellen = (z) => z.replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()));
    const zeilen = tabelle.filter((z) => !/^\|?\s*:?-{2,}/.test(z));
    out.push(`<table>${zeilen.map((z, i) => `<tr>${zellen(z).map((c) => (i ? `<td>${c}</td>` : `<th>${c}</th>`)).join('')}</tr>`).join('')}</table>`);
    tabelle = [];
  };
  for (const zeile of text.split('\n')) {
    const t = zeile.trim();
    let m;
    if (t.startsWith('|')) { absatzEnde(); listeEnde(); tabelle.push(t); continue; }
    tabelleEnde();
    if (!t) { absatzEnde(); listeEnde(); continue; }
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) { absatzEnde(); listeEnde(); const n = Math.min(4, m[1].length); out.push(`<h${n}>${inline(m[2])}</h${n}>`); continue; }
    if (/^(-{3,}|\*{3,})$/.test(t)) { absatzEnde(); listeEnde(); out.push('<hr>'); continue; }
    if ((m = t.match(/^>\s?(.*)$/))) { absatzEnde(); listeEnde(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
    if ((m = t.match(/^([-*+]|\d+[.)])\s+(.*)$/))) {
      absatzEnde();
      const art = /\d/.test(m[1]) ? 'ol' : 'ul';
      if (liste !== art) { listeEnde(); out.push(`<${art}>`); liste = art; }
      out.push(`<li>${inline(m[2])}</li>`);
      continue;
    }
    listeEnde();
    absatz.push(t);
  }
  tabelleEnde(); absatzEnde(); listeEnde();
  return out.join('');
}

// ------------------------------------------------------------------ Transkripte

async function transkripteLaden(neu = false) {
  try {
    ZF.transkripte = await api(`/api/transkripte${neu ? '?neu=1' : ''}`);
  } catch (err) {
    ZF.transkripte = [];
    $('#zf-transkripte').replaceChildren(h('li', { class: 'leer', text: err.message }));
    return;
  }
  transkripteZeichnen();
}

function transkripteZeichnen() {
  const suche = $('#zf-suche').value.trim().toLowerCase();
  const treffer = ZF.transkripte.filter((t) => !suche || t.titel.toLowerCase().includes(suche));
  $('#zf-transkripte').replaceChildren(...(treffer.length ? treffer.slice(0, 300).map((t) => h('li', {},
    h('button', {
      type: 'button', 'aria-current': ZF.gewaehlt?.ordner === t.ordner ? 'true' : 'false', title: t.titel,
      onclick: () => transkriptWaehlen(t.ordner),
    }, h('b', { text: t.titel }),
    h('span', { text: [dauer(t.dauer), t.quelle.startsWith('http') ? 'YouTube' : 'Datei', t.fassungen ? `${t.fassungen} Fassungen` : ''].filter(Boolean).join(' · ') })))) : [h('li', { class: 'leer', text: suche ? 'Kein Titel passt.' : 'Noch keine Transkripte.' })]));
}

function transkriptWaehlen(ordner) {
  ZF.gewaehlt = ZF.transkripte.find((t) => t.ordner === ordner) || null;
  transkripteZeichnen();
  $('#zf-leer').hidden = !!ZF.gewaehlt;
  $('#zf-inhalt').hidden = !ZF.gewaehlt;
  if (!ZF.gewaehlt) return;
  const t = ZF.gewaehlt;
  $('#zf-titel').textContent = t.titel;
  $('#zf-meta').textContent = [t.quelle, dauer(t.dauer), t.sprache ? `Sprache ${t.sprache}` : ''].filter(Boolean).join(' · ');
  $('#zf-rueck').replaceChildren();
  zfZeichnen();
}

// Aus dem Reiter Transkription: „Zusammenfassen“ bei einem fertigen Auftrag.
window.zusammenfassungOeffnen = async (ordner) => {
  reiterZeigen('zusammenfassung');
  if (!ZF.transkripte.some((t) => t.ordner === ordner)) await transkripteLaden(true);
  transkriptWaehlen(ordner);
};

// ------------------------------------------------------------------ Auswahl

function auswahlZeichnen() {
  const s = ZF.stand;
  const box = $('#zf-auswerter');
  box.replaceChildren(...s.auswerter.map((p) => {
    const cb = h('input', { type: 'checkbox', disabled: !p.verfuegbar });
    cb.checked = p.verfuegbar && ZF.auswerterWahl.has(p.id);
    cb.addEventListener('change', () => { if (cb.checked) ZF.auswerterWahl.add(p.id); else ZF.auswerterWahl.delete(p.id); zfMerken(); startZeichnen(); });
    const kontext = p.kontext ? `${Math.round(p.kontext / 1000)}K Kontext` : '';
    return h('label', { class: `wahl${p.verfuegbar ? '' : ' aus'}` }, cb,
      h('span', { class: 'wahl-text' }, h('b', { text: p.name }),
        p.verfuegbar ? (kontext ? h('small', { text: kontext }) : null) : h('small', { class: 'grund', text: p.grund })),
      h('span', { class: `ort ${p.cloud ? 'cloud' : 'lokal'}`, text: p.cloud ? `Cloud · ${p.cloud}` : 'lokal' }));
  }));
  if (!s.auswerter.length) box.replaceChildren(h('p', { class: 'leise', text: 'Noch keine Auswerter angelegt.' }));

  const sammlung = s.sammlung;
  const anw = $('#zf-anweisungen');
  if (!sammlung.abschnitt) {
    anw.replaceChildren(h('p', { class: 'leise', text: sammlung.fehler || 'In der Promptsammlung fehlt der Abschnitt für die Werkstatt.' }),
      knopf('Standardanweisungen anlegen', async () => { await api('/api/anweisung', { aktion: 'einrichten' }); await zfAktualisieren(); }));
  } else {
    anw.replaceChildren(...sammlung.anweisungen.map((a) => {
      const cb = h('input', { type: 'checkbox' });
      cb.checked = ZF.anweisungWahl.has(a.name);
      cb.addEventListener('change', () => { if (cb.checked) ZF.anweisungWahl.add(a.name); else ZF.anweisungWahl.delete(a.name); zfMerken(); startZeichnen(); });
      const erste = a.text.split('\n').find((z) => z.trim()) || '';
      return h('label', { class: 'wahl' }, cb,
        h('span', { class: 'wahl-text' }, h('b', { text: a.name }), h('small', { text: erste.length > 90 ? `${erste.slice(0, 88)} …` : erste })),
        h('button', { class: 'knopf knopf-klein', type: 'button', onclick: (e) => { e.preventDefault(); anweisungDialog(a); } }, 'Ansehen'));
    }));
  }
  startZeichnen();
}

function gewaehlteAuswerter() {
  return (ZF.stand?.auswerter || []).filter((p) => p.verfuegbar && ZF.auswerterWahl.has(p.id));
}

function gewaehlteAnweisungen() {
  return (ZF.stand?.sammlung.anweisungen || []).filter((a) => ZF.anweisungWahl.has(a.name));
}

function startZeichnen() {
  const aus = gewaehlteAuswerter();
  const anw = gewaehlteAnweisungen();
  const n = aus.length * anw.length;
  const frage = anw.some((a) => a.frage);
  $('#zf-frage-feld').hidden = !frage;
  const knopfStart = $('#zf-auswerten');
  knopfStart.disabled = !n || !ZF.gewaehlt;
  knopfStart.textContent = n ? `Auswerten · ${n} ${n === 1 ? 'Fassung' : 'Fassungen'}` : 'Auswerten';
  const clouds = [...new Set(aus.map((p) => p.cloud).filter(Boolean))];
  $('#zf-hinweis').textContent = !n ? 'Mindestens einen Auswerter und eine Anweisung anhaken.'
    : clouds.length ? `Das Transkript geht an: ${clouds.join(', ')}.${aus.some((p) => !p.cloud) ? ' Lokale Auswerter bleiben auf diesem Rechner.' : ''}`
      : 'Alles bleibt auf diesem Rechner.';
}

async function auswerten() {
  const knopfStart = $('#zf-auswerten');
  knopfStart.disabled = true;
  try {
    const e = await api('/api/auswerten', {
      ordner: ZF.gewaehlt.ordner, auswerter: gewaehlteAuswerter().map((p) => p.id),
      anweisungen: gewaehlteAnweisungen().map((a) => a.name), frage: $('#zf-frage').value,
    });
    const kinder = [];
    if (e.neu) kinder.push(h('p', { class: 'ok', text: `${e.neu} ${e.neu === 1 ? 'Fassung wird' : 'Fassungen werden'} erstellt.` }));
    if (e.abgelehnt?.length) kinder.push(h('ul', {}, ...e.abgelehnt.map((x) => h('li', { text: x }))));
    $('#zf-rueck').replaceChildren(...kinder);
  } catch (err) {
    $('#zf-rueck').replaceChildren(h('ul', {}, h('li', { text: err.message })));
  }
  await zfAktualisieren();
}

// ------------------------------------------------------------------ Fassungen

function fassungStatus(f) {
  if (f.zustand === 'laeuft') return `Läuft seit ${dauer(f.sekunden)}${f.meldung ? ` · ${f.meldung}` : ''}`;
  if (f.zustand === 'fertig') {
    const teile = [`Fertig in ${dauer(f.dauer_s)}`];
    if (f.pruefung) teile.push(`Prüfung: ${f.pruefung}`);
    if (f.tokens) teile.push(`${f.tokens.toLocaleString('de-DE')} Token`);
    if (f.kosten_usd != null) teile.push(`${f.kosten_usd.toLocaleString('de-DE', { maximumFractionDigits: 4 })} $`);
    return teile.join(' · ');
  }
  return [ZF_ZUSTAND[f.zustand], f.meldung].filter(Boolean).join(': ');
}

function fassungKnoepfe(f) {
  const aktion = (was) => () => api('/api/fassung', { id: f.id, aktion: was }).then(zfAktualisieren);
  const out = [];
  if (f.zustand === 'fertig') {
    out.push(knopf('Datei öffnen', aktion('oeffnen')), knopf('Kopieren', async () => {
      await navigator.clipboard.writeText((ZF.texte.get(f.id) || '').replace(/^---\n[\s\S]*?\n---\n/, ''));
    }));
  }
  if (f.zustand === 'laeuft' || f.zustand === 'wartet') out.push(knopf('Abbrechen', aktion('abbrechen')));
  if (f.zustand === 'fehler' || f.zustand === 'abgebrochen') out.push(knopf('Wiederholen', aktion('wiederholen'), { haupt: true }));
  if (f.zustand !== 'laeuft') out.push(knopf('Aus der Liste', aktion('entfernen'), { titel: 'Nur aus der Liste nehmen; die Datei bleibt erhalten.' }));
  return out;
}

async function fassungText(f, r) {
  if (f.zustand !== 'fertig') { r.text.replaceChildren(); r.text.hidden = true; return; }
  r.text.hidden = false;
  if (!ZF.texte.has(f.id)) {
    try {
      ZF.texte.set(f.id, (await api(`/api/fassung?id=${encodeURIComponent(f.id)}`)).text || '');
    } catch {
      ZF.texte.set(f.id, '_Die Datei ließ sich nicht lesen._');
    }
    r.gezeichnet = '';
  }
  if (r.gezeichnet !== f.id) {
    r.text.innerHTML = markdown(ZF.texte.get(f.id));
    r.gezeichnet = f.id;
  }
}

function fassungenZeichnen() {
  const box = $('#zf-fassungen');
  if (!ZF.gewaehlt) return;
  const liste = ZF.stand.auswertungen.filter((f) => f.ordner === ZF.gewaehlt.ordner).reverse();
  const ids = new Set(liste.map((f) => f.id));
  for (const [id, r] of ZF.zeilen) if (!ids.has(id)) { r.el.remove(); ZF.zeilen.delete(id); }
  if (!liste.length) {
    box.replaceChildren(h('p', { class: 'leer', text: 'Für dieses Transkript gibt es noch keine Fassungen.' }));
    return;
  }
  box.querySelector('.leer')?.remove();
  liste.forEach((f, i) => {
    let r = ZF.zeilen.get(f.id);
    if (!r) {
      r = { titel: h('h4'), status: h('p', { class: 'f-meldung' }), knoepfe: h('div', { class: 'f-knoepfe' }), text: h('div', { class: 'f-text' }), schluessel: '' };
      r.el = h('article', { class: 'fassung' }, h('div', { class: 'f-kopf' }, r.titel, r.status), r.knoepfe, r.text);
      ZF.zeilen.set(f.id, r);
    }
    r.el.dataset.zustand = f.zustand;
    r.titel.textContent = `${f.anweisung.name} · ${f.auswerter.name}`;
    r.titel.title = f.frage ? `Frage: ${f.frage}` : '';
    r.status.textContent = fassungStatus(f);
    const schluessel = f.zustand;
    if (schluessel !== r.schluessel) { r.schluessel = schluessel; r.knoepfe.replaceChildren(...fassungKnoepfe(f)); }
    fassungText(f, r);
    if (box.children[i] !== r.el) box.insertBefore(r.el, box.children[i] || null);
  });
}

function zfZeichnen() {
  if (!ZF.stand) return;
  auswahlZeichnen();
  fassungenZeichnen();
}

async function zfAktualisieren() {
  try {
    ZF.stand = await api('/api/zusammenfassung');
    zfZeichnen();
  } catch (err) {
    $('#zf-rueck').replaceChildren(h('ul', {}, h('li', { text: err.message })));
  }
}

function zfSchleife() {
  const laeuft = ZF.stand?.auswertungen.some((f) => f.zustand === 'laeuft' || f.zustand === 'wartet');
  const weiter = () => setTimeout(zfSchleife, laeuft ? 1500 : 4000);
  if (!ZF.aktiv || document.querySelector('dialog[open]')) return weiter();
  zfAktualisieren().finally(weiter);
}

function anordnungSetzen(art) {
  for (const b of document.querySelectorAll('.umschalter button')) b.classList.toggle('aktiv', b.dataset.anordnung === art);
  const box = $('#zf-fassungen');
  box.classList.toggle('nebeneinander', art === 'nebeneinander');
  box.classList.toggle('untereinander', art === 'untereinander');
}

// ------------------------------------------------------------------ Dialog: Anweisung

function dialogOeffnen(titel, inhalt, knoepfe, gross = false) {
  const d = $('#dialog');
  d.classList.toggle('gross', gross);
  d.replaceChildren(h('h2', { id: 'dialog-titel', text: titel }), ...inhalt, h('div', { class: 'dialog-knoepfe' }, ...knoepfe));
  d.showModal();
  return d;
}

function anweisungDialog(a, rahmen = false) {
  const neu = !a;
  const name = h('input', { type: 'text', value: a?.name || '', maxlength: '60', disabled: rahmen });
  const text = h('textarea', { spellcheck: 'false' });
  text.value = a?.text || '';
  const fehler = h('p', { class: 'warnung' });
  const pfad = ZF.stand.sammlung.pfad;
  const d = dialogOeffnen(rahmen ? 'Rahmen für alle Anweisungen' : neu ? 'Neue Anweisung' : `Anweisung: ${a.name}`, [
    rahmen ? h('p', { class: 'leise', text: 'Wird jeder Anweisung vorangestellt, bei allen Auswertern gleich.' }) : h('label', { class: 'dialog-feld' }, 'Name', name),
    h('label', { class: 'dialog-feld' }, 'Anweisung', text),
    rahmen ? null : h('p', { class: 'platzhalter' }, 'Platzhalter:', ...['[Titel]', '[Quelle]', '[Dauer]', '[Frage]', '[Transkript]'].map((p) => h('code', { text: p })),
      'Ohne [Transkript] wird das Transkript angehängt.'),
    h('p', { class: 'leise', text: `Gespeichert in ${pfad} (Abschnitt „Werkstatt: Anweisungen für Zusammenfassungen“).` }),
    fehler,
  ], [
    !neu && !rahmen ? h('button', {
      class: 'knopf links', type: 'button',
      onclick: async () => {
        try { await api('/api/anweisung', { aktion: 'loeschen', name: a.name, stand: a.stand }); ZF.anweisungWahl.delete(a.name); d.close(); await zfAktualisieren(); } catch (err) { fehler.textContent = err.message; }
      },
    }, 'Löschen') : null,
    h('button', { class: 'knopf', type: 'button', onclick: () => d.close() }, 'Abbrechen'),
    !neu && !rahmen ? h('button', {
      class: 'knopf', type: 'button',
      onclick: async () => {
        try {
          const n = name.value.trim() === a.name ? `${a.name} (Variante)` : name.value.trim();
          await api('/api/anweisung', { aktion: 'neu', name: n, text: text.value });
          d.close(); await zfAktualisieren();
        } catch (err) { fehler.textContent = err.message; }
      },
    }, 'Als neue Anweisung speichern') : null,
    h('button', {
      class: 'knopf knopf-haupt', type: 'button',
      onclick: async () => {
        try {
          if (neu) await api('/api/anweisung', { aktion: 'neu', name: name.value, text: text.value });
          else {
            await api('/api/anweisung', { aktion: 'speichern', name: a.name, neuer_name: rahmen ? null : name.value.trim(), text: text.value, stand: a.stand });
            if (!rahmen && name.value.trim() !== a.name && ZF.anweisungWahl.delete(a.name)) ZF.anweisungWahl.add(name.value.trim());
          }
          d.close(); await zfAktualisieren();
        } catch (err) { fehler.textContent = err.message; }
      },
    }, neu ? 'Anlegen' : 'Speichern'),
  ].filter(Boolean), true);
  (rahmen || !neu ? text : name).focus();
}

// ------------------------------------------------------------------ Dialog: Auswerter

async function auswerterDialog() {
  if (!ZF.katalog) ZF.katalog = await api('/api/katalog');
  const kat = ZF.katalog;
  const liste = h('ul', { class: 'profil-liste' });
  const zeichneListe = () => liste.replaceChildren(...ZF.stand.auswerter.map((p) => h('li', {},
    h('span', { text: p.name }),
    h('button', {
      class: 'knopf knopf-klein', type: 'button',
      onclick: async () => { await api('/api/auswerter', { aktion: 'loeschen', id: p.id }); ZF.auswerterWahl.delete(p.id); await zfAktualisieren(); zeichneListe(); },
    }, 'Entfernen'))));
  zeichneListe();
  const anbieter = h('select', {}, ...kat.anbieter.map((a) => h('option', { value: a.anbieter, text: a.cloud ? `${a.name} (Cloud)` : `${a.name} (auf diesem Rechner)` })));
  const modell = h('select');
  const stufe = h('select');
  const info = h('p', { class: 'leise' });
  const fehler = h('p', { class: 'warnung' });
  const modelle = () => kat.anbieter.find((a) => a.anbieter === anbieter.value)?.modelle || [];
  const stufenFuellen = () => {
    const m = modelle().find((x) => x.modell === modell.value);
    stufe.replaceChildren(h('option', { value: '', text: 'Standard' }), ...(m?.stufen || []).map((s) => h('option', { value: s, text: kat.stufen_text[s] || s })));
    stufe.disabled = !m?.stufen.length;
    if (m?.stufe_standard) stufe.value = m.stufe_standard;
    info.textContent = [m?.beschreibung, m?.kontext ? `${Math.round(m.kontext / 1000)}K Kontext` : ''].filter(Boolean).join(' · ');
  };
  const modelleFuellen = () => {
    modell.replaceChildren(...modelle().map((m) => h('option', { value: m.modell, text: m.name })));
    if (!modelle().length) modell.replaceChildren(h('option', { value: '', text: 'Keine Modelle gefunden' }));
    stufenFuellen();
  };
  anbieter.addEventListener('change', modelleFuellen);
  modell.addEventListener('change', stufenFuellen);
  modelleFuellen();
  const d = dialogOeffnen('Auswerter verwalten', [
    h('p', { class: 'leise', text: 'Ein Auswerter ist Anbieter, Modell und Denkstufe. Im Auftrag erscheinen die Auswerter als Kästchen.' }),
    liste,
    h('div', { class: 'profil-neu' },
      h('label', { class: 'dialog-feld' }, 'Anbieter', anbieter),
      h('label', { class: 'dialog-feld' }, 'Modell', modell),
      h('label', { class: 'dialog-feld' }, 'Denkstufe', stufe),
      h('button', {
        class: 'knopf', type: 'button',
        onclick: async () => {
          try {
            fehler.textContent = '';
            await api('/api/auswerter', { aktion: 'neu', anbieter: anbieter.value, modell: modell.value, stufe: stufe.value || null });
            await zfAktualisieren(); zeichneListe();
          } catch (err) { fehler.textContent = err.message; }
        },
      }, 'Hinzufügen')),
    info, fehler,
  ], [h('button', { class: 'knopf knopf-haupt', type: 'button', onclick: () => d.close() }, 'Fertig')], true);
}

// ------------------------------------------------------------------ Start

$('#zf-suche').addEventListener('input', transkripteZeichnen);
$('#zf-neu-laden').addEventListener('click', () => transkripteLaden(true));
$('#zf-auswerten').addEventListener('click', auswerten);
$('#zf-ordner').addEventListener('click', () => api('/api/transkript-oeffnen', { ordner: ZF.gewaehlt.ordner }).catch((err) => $('#zf-rueck').replaceChildren(h('ul', {}, h('li', { text: err.message })))));
$('#zf-anweisung-neu').addEventListener('click', () => anweisungDialog(null));
$('#zf-rahmen').addEventListener('click', () => { const r = ZF.stand?.sammlung.rahmen; if (r) anweisungDialog(r, true); });
$('#zf-auswerter-verwalten').addEventListener('click', () => auswerterDialog().catch((err) => $('#zf-rueck').replaceChildren(h('ul', {}, h('li', { text: err.message })))));
for (const b of document.querySelectorAll('.umschalter button')) b.addEventListener('click', () => { anordnungSetzen(b.dataset.anordnung); zfMerken(); });
zfLaden();

window.zusammenfassungAktiv = async (aktiv) => {
  ZF.aktiv = aktiv;
  if (!aktiv) return;
  if (!ZF.transkripte.length) transkripteLaden();
  await zfAktualisieren();
};
zfSchleife();
