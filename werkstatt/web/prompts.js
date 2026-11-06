'use strict';

// Ablage und Suche. Die gemeinsame Wissenssammlung bleibt schreibgeschützt.
const P = { eintraege: [], gewaehlt: null, anfrage: 0 };

function pFehler(err) { $('#p-rueck').textContent = err.message; }

async function pLaden() {
  try {
    const d = await api('/api/prompts');
    P.eintraege = d.eintraege;
    $('#p-rueck').textContent = d.fehler.join(' · ');
    pListe();
    if (P.gewaehlt) await pWaehlen(P.gewaehlt);
  } catch (err) { pFehler(err); }
}

function pListe() {
  const suche = $('#p-suche').value.toLocaleLowerCase('de');
  const herkunft = $('#p-herkunft').value;
  const status = $('#p-status').value;
  const liste = P.eintraege.filter((e) => (!herkunft || e.herkunft === herkunft)
    && (!status || e.getestet === (status === 'getestet'))
    && [e.titel, e.schlagworte, e.quelle, ...e.fassungen.map((f) => f.text)]
      .join('\n').toLocaleLowerCase('de').includes(suche));
  $('#p-liste').replaceChildren(...liste.map((e) => h('li', {}, h('button', {
    type: 'button', class: e.id === P.gewaehlt ? 'aktiv' : '',
    onclick: () => pWaehlen(e.id), 'aria-pressed': String(e.id === P.gewaehlt),
  }, h('strong', { text: e.titel }), h('span', { class: 'leise',
    text: [e.herkunft === 'sammlung' ? 'Sammlung' : 'Ordner', e.getestet ? 'getestet' : 'ungetestet', e.fehler].filter(Boolean).join(' · ') })))));
  if (!liste.length) $('#p-liste').append(h('li', { class: 'leise', text: 'Keine passenden Prompts.' }));
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
  const anfrage = ++P.anfrage;
  try {
    const e = await api(`/api/prompt?id=${encodeURIComponent(id)}`);
    if (anfrage !== P.anfrage) return;
    P.gewaehlt = id;
    pListe();
    const knoepfe = [pKnopf(e.herkunft === 'ordner' || id.startsWith('schatten:')
      ? 'Im Ordner öffnen' : 'In der Sammlung öffnen', () => pOeffnen(e,
      e.herkunft === 'ordner' || id.startsWith('schatten:') ? 'ordner' : 'sammlung'))];
    if (e.bearbeitbar) knoepfe.push(pKnopf('Kopfzeilen bearbeiten …', () => pDialog(e, 'kopf')),
      pKnopf('Neue Fassung …', () => pDialog(e, 'fassung_neu')));
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
      if (f.text.split('\n').length > 20) karte.append(h('details', {}, h('summary', { text: 'Fassung anzeigen' }), pre));
      else karte.append(pre);
      if (e.bearbeitbar) karte.append(h('div', { class: 'p-knoepfe' },
        pKnopf('Bearbeiten …', () => pDialog(e, 'fassung_speichern', f)),
        pKnopf('Als bevorzugt', () => pAktion({ aktion: 'bevorzugt', id, name: f.name, kopf_stand: e.kopf_stand }))));
      inhalt.push(karte);
    }
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Tests' }));
    for (const t of e.tests) {
      inhalt.push(h('article', { class: 'p-fassung' }, h('p', { text: [t.erstellt, t.fassung,
        t.geaendert ? 'seit dem Test geändert' : '', t.auswerter, dauer(Number(t.dauer_s)),
        t.tokens != null ? `${t.tokens} Token` : '', t.kosten_usd != null ? `${t.kosten_usd} USD` : '',
        t.zustand, t.urteil, t.notiz, t.fehler].filter(Boolean).join(' · ') }),
      pKnopf('Öffnen', () => pOeffnen(e, 'beleg', t.datei)),
      t.html === 'ja' ? pKnopf('Im Browser öffnen', () => pOeffnen(e, 'html', t.datei.replace(/\.md$/i, '.html'))) : null));
    }
    if (!e.tests.length) inhalt.push(h('p', { class: 'leise', text: 'Noch keine Testbelege.' }));
    $('#p-inhalt').replaceChildren(...inhalt);
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

$('#p-suche').addEventListener('input', pListe);
$('#p-herkunft').addEventListener('change', pListe);
$('#p-status').addEventListener('change', pListe);
$('#p-neu').addEventListener('click', () => pDialog(null, 'neu'));
$('#p-laden').addEventListener('click', pLaden);
window.promptsAktiv = (aktiv) => { if (aktiv) pLaden(); };
