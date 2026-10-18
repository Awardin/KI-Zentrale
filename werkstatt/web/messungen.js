'use strict';

// Reiter Messungen. Alle Werte stammen aus echten Läufen; nichts wird geschätzt.

const M = { aktiv: false, stand: null, hiSuche: '' };

const zahlDe = (x, stellen = 1) => (x == null ? '–' : Number(x).toLocaleString('de-DE', { maximumFractionDigits: stellen }));

// Tabelle; Spalten mit `balken` bekommen einen dünnen Balken relativ zum größten Wert der Spalte.
function mTabelle(spalten, zeilen, leer = 'Noch keine Werte.') {
  if (!zeilen.length) return h('p', { class: 'leise', text: leer });
  const maxima = spalten.map((s) => (s.balken ? Math.max(...zeilen.map((z) => s.balken(z) || 0)) : 0));
  return h('table', { class: 'm-tab' },
    h('thead', {}, h('tr', {}, ...spalten.map((s) => h('th', { class: s.zahl || s.balken ? 'r' : '', scope: 'col', text: s.titel })))),
    h('tbody', {}, ...zeilen.map((z) => h('tr', {}, ...spalten.map((s, i) => {
      const text = s.wert(z);
      if (!s.balken) return h('td', { class: s.zahl ? 'r' : (s.klasse || ''), text, title: s.titelWert ? s.titelWert(z) : null });
      const v = s.balken(z);
      const anteil = v && maxima[i] ? Math.max(0.02, v / maxima[i]) : 0;
      return h('td', { class: 'bz' },
        h('span', { class: 'bz-balken', title: `${s.titel}: ${text}` }, h('i', { style: `width:${(anteil * 100).toFixed(1)}%` })),
        h('span', { class: 'bz-wert', text }));
    })))));
}

function mKachel(gross, einheit, zeile1, zeile2) {
  return h('div', { class: 'm-kachel' },
    h('p', { class: 'm-gross' }, gross, h('small', { text: einheit })),
    h('p', { class: 'm-z1', text: zeile1 }), h('p', { class: 'leise', text: zeile2 }));
}

// ------------------------------------------------------------------ LLM-Messlauf

function mMesslaufZeichnen() {
  const s = M.stand;
  const wahl = $('#m-modell');
  const vorher = wahl.value;
  wahl.replaceChildren(...s.lokale_modelle.map((m) => h('option', {
    value: m.id, disabled: !m.geladen, title: m.grund || null,
    text: m.geladen ? m.name : `${m.name} (nicht geladen)`,
  })));
  const erste = s.lokale_modelle.find((m) => m.geladen);
  wahl.value = s.lokale_modelle.some((m) => m.id === vorher && m.geladen) ? vorher : (erste?.id || '');
  const laeuft = s.messlauf_laeuft;
  $('#m-starten').disabled = !erste || !!laeuft;
  $('#m-zustand').textContent = laeuft
    ? `${laeuft.modell}: ${laeuft.meldung} (${dauer(Date.now() / 1000 - laeuft.seit)})`
    : (erste ? '' : 'Kein lokales Sprachmodell geladen. In der Modellzentrale laden, dann hier messen.');
  const spitze = (l) => Object.entries(l.sensoren || {}).filter(([, v]) => v.last > 5)
    .map(([k, v]) => `${v.name || (Number(k) === 0 ? '3090' : '3080')}: ${Math.round(v.watt)} W, ${Math.round(v.temp)} °C`).join(' · ');
  $('#m-laeufe').replaceChildren(mTabelle([
    { titel: 'Datum', wert: (l) => l.datum },
    { titel: 'Modell', wert: (l) => l.modell },
    { titel: 'Laufzeit', wert: (l) => l.laufzeit || '–' },
    { titel: 'Prefill tok/s', wert: (l) => (l.fehler ? 'Fehler' : zahlDe(l.prefill, 0)), balken: (l) => l.prefill },
    { titel: 'Decode tok/s', wert: (l) => (l.fehler ? '–' : zahlDe(l.decode)), balken: (l) => l.decode },
    { titel: 'Erste Antwort', wert: (l) => (l.ttft_ms != null ? `${zahlDe(l.ttft_ms, 0)} ms` : '–'), zahl: true },
    { titel: 'Spitze je Karte', wert: (l) => l.fehler || spitze(l) || '–', klasse: 'klein' },
  ], s.messlaeufe, 'Noch keine eigenen Messläufe.'));
}

async function mStarten() {
  try {
    await api('/api/messlauf', { modell: $('#m-modell').value });
  } catch (err) {
    $('#m-zustand').textContent = err.message;
  }
  mAktualisieren();
}

// ------------------------------------------------------------------ Übersichten

function mTranskriptionZeichnen() {
  const t = M.stand.transkription;
  $('#m-tr-quelle').textContent = `Aus ${t.anzahl} vollständigen watch-Läufen in Arbeitsmaterial\\watch. `
    + 'Tempo = Tondauer ÷ Laufzeit der Abschnitte (inklusive Modellladen). Läufe mit weniger als 40 Wörtern je Minute '
    + '(Musik, Stille) gelten als „wenig Sprache“ und zählen nicht im Median.';
  $('#m-tr-kacheln').replaceChildren(...t.gruppen.map((g) => mKachel(zahlDe(g.tempo_median), '× Echtzeit (Median)',
    `Whisper ${g.modell} · ${g.aufbau}`, `${g.anzahl} ${g.anzahl === 1 ? 'Lauf' : 'Läufe'} · ${zahlDe(g.ton_h)} h Ton`
      + (g.ausgelassen ? ` · ${g.ausgelassen} mit wenig Sprache nicht im Median` : ''))));
  $('#m-tr-letzte').replaceChildren(h('h3', { class: 'abschnitt', text: 'Letzte Läufe' }), mTabelle([
    { titel: 'Datum', wert: (k) => k.datum },
    { titel: 'Quelle', wert: (k) => (k.wenig_sprache ? `${k.titel} · wenig Sprache` : k.titel), klasse: 'kappen',
      titelWert: (k) => (k.wenig_sprache ? `${k.titel}: nur ${k.woerter_je_min} Wörter je Minute, zählt nicht im Median` : k.titel) },
    { titel: 'Aufbau', wert: (k) => `${k.modell} · ${k.aufbau}` },
    { titel: 'Ton', wert: (k) => dauer(k.ton_s), zahl: true },
    { titel: 'Laufzeit', wert: (k) => dauer(k.laufzeit_s), zahl: true },
    { titel: 'Tempo', wert: (k) => `${zahlDe(k.tempo)} ×`, balken: (k) => (k.wenig_sprache ? null : k.tempo) },
  ], t.letzte.slice(0, 12)));
}

function mZusammenfassungZeichnen() {
  const z = M.stand.zusammenfassung;
  $('#m-zf').replaceChildren(mTabelle([
    { titel: 'Auswerter', wert: (g) => g.auswerter },
    { titel: 'Wo', wert: (g) => (g.cloud ? `Cloud · ${g.cloud}` : 'lokal') },
    { titel: 'Fassungen', wert: (g) => String(g.anzahl), zahl: true },
    { titel: 'Dauer (Median)', wert: (g) => dauer(g.dauer_median), balken: (g) => g.dauer_median },
    { titel: 'Token/s', wert: (g) => zahlDe(g.token_je_s, 0), zahl: true },
    { titel: 'Kosten', wert: (g) => (g.kosten_usd == null ? '–' : `${zahlDe(g.kosten_usd, 4)} $`), zahl: true,
      titelWert: (g) => (g.kosten_usd == null ? 'Keine Einzelkosten: Abo oder eigener Rechner' : null) },
  ], z.gruppen, 'Noch keine fertigen Fassungen.'));
}

function mBildVideoZeichnen() {
  const b = M.stand.bild_video;
  $('#m-bv').replaceChildren(mTabelle([
    { titel: 'Quelle', wert: (g) => g.quelle },
    { titel: 'Art', wert: (g) => g.art },
    { titel: 'Modell', wert: (g) => g.modell || '–', klasse: 'kappen', titelWert: (g) => g.modell },
    { titel: 'Auflösung', wert: (g) => g.aufloesung || '–' },
    { titel: 'Schritte', wert: (g) => (g.schritte == null ? '–' : String(g.schritte)), zahl: true },
    { titel: 'Aufträge', wert: (g) => String(g.anzahl), zahl: true },
    { titel: 'Dauer (Median)', wert: (g) => dauer(g.dauer_median), balken: (g) => g.dauer_median },
  ], b.gruppen, 'Noch keine fertigen Bild- oder Videoaufträge gefunden.'));
}

function mHistorischZeichnen() {
  const hi = M.stand.historisch;
  if (!hi) {
    $('#m-hi-quelle').textContent = M.stand.gpu_lab_da ? 'Die GPU-Lab-Messungen sind noch nicht übernommen.' : 'GPU-Lab wurde nicht gefunden.';
    $('#m-hi').replaceChildren(M.stand.gpu_lab_da ? knopf('Aus GPU-Lab übernehmen', async () => {
      await api('/api/historisch-uebernehmen', {});
      await mAktualisieren(true);
    }, { haupt: true, klein: false }) : '');
    $('#m-hi-suche').hidden = true;
    return;
  }
  $('#m-hi-suche').hidden = false;
  $('#m-hi-quelle').textContent = `${hi.hinweis} ${hi.anzahl} Läufe, übernommen am ${hi.uebernommen.replace('T', ' ')}`
    + `${hi.andere ? `; davon ${hi.andere} allgemeine Leistungstests ohne LLM-Werte` : ''}. Median je Modell, Quantisierung, Laufzeit und Karte.`;
  const suche = M.hiSuche.toLowerCase();
  const zeilen = hi.gruppen.filter((g) => !suche || [g.modell, g.quant, g.runtime, g.gpu].join(' ').toLowerCase().includes(suche));
  $('#m-hi').replaceChildren(mTabelle([
    { titel: 'Modell', wert: (g) => g.modell },
    { titel: 'Quant.', wert: (g) => g.quant || '–' },
    { titel: 'Laufzeit', wert: (g) => g.runtime || '–', klasse: 'kappen klein', titelWert: (g) => g.runtime },
    { titel: 'Karte', wert: (g) => g.gpu || '–' },
    { titel: 'Läufe', wert: (g) => String(g.anzahl), zahl: true },
    { titel: 'Decode tok/s', wert: (g) => zahlDe(g.decode), balken: (g) => g.decode },
    { titel: 'Prefill tok/s', wert: (g) => zahlDe(g.prefill, 0), zahl: true },
    { titel: 'Erste Antwort', wert: (g) => (g.ttft_ms != null ? `${zahlDe(g.ttft_ms, 0)} ms` : '–'), zahl: true },
  ], zeilen, 'Kein Eintrag passt zum Filter.'));
}

function mZeichnen() {
  if (!M.stand) return;
  mMesslaufZeichnen();
  mTranskriptionZeichnen();
  mZusammenfassungZeichnen();
  mBildVideoZeichnen();
  mHistorischZeichnen();
}

async function mAktualisieren(neu = false) {
  try {
    M.stand = await api(`/api/messungen${neu ? '?neu=1' : ''}`);
    mZeichnen();
  } catch (err) {
    $('#m-zustand').textContent = err.message;
  }
}

function mSchleife() {
  const weiter = () => setTimeout(mSchleife, M.stand?.messlauf_laeuft ? 1500 : 8000);
  if (!M.aktiv) return weiter();
  mAktualisieren().finally(weiter);
}

$('#m-starten').addEventListener('click', mStarten);
$('#m-hi-suche').addEventListener('input', (e) => { M.hiSuche = e.target.value; mHistorischZeichnen(); });

window.messungenAktiv = (aktiv) => {
  M.aktiv = aktiv;
  if (aktiv) mAktualisieren(true);
};
mSchleife();
