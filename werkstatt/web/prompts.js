'use strict';

// Ablage und Suche. Die gemeinsame Wissenssammlung bleibt schreibgeschützt.
const P = { eintraege: [], gewaehlt: null, anfrage: 0 };

function pFehler(err) { $('#p-rueck').textContent = err.message; }

function pGeschuetzt() {
  return !!document.querySelector('dialog[open]')
    || !!document.activeElement?.matches('#p-inhalt textarea, #p-inhalt input, #p-composer textarea, #p-composer input, #p-composer select, #p-kontexte textarea, #p-kontexte input');
}

function pLaeuft() {
  const aktiv = (a) => a.zustand === 'wartet' || a.zustand === 'laeuft';
  return (P.warteschlange || []).some(aktiv)
    || ['tests', 'schaerfen'].some((art) => (P.eintraege.find((e) => e.id === P.gewaehlt)?.[art] || []).some(aktiv));
}

function pLadenFaellig() {
  // Takt und Reiterwechsel stellen keinen zweiten Abruf hinter einen laufenden; das tun nur Knopf und Aktionen.
  if (P.ladenLaeuft) return false;
  return P.ladenNoetig || P.letztesLaden == null || pLaeuft() || Date.now() - P.letztesLaden >= 30000;
}

async function pLaden() {
  if (P.ladenLaeuft) { P.ladenNachholen = true; return; }
  if (pGeschuetzt()) return;
  P.ladenLaeuft = true;
  P.ladenNoetig = true;
  pListe();
  try {
    const d = await api('/api/prompts');
    if (pGeschuetzt()) return;
    P.eintraege = d.eintraege;
    P.warteschlange = d.warteschlange || [];
    $('#p-rueck').textContent = d.fehler.join(' · ');
    P.ladenFehler = false;
    P.letztesLaden = Date.now();
    pListe();
    P.ladenNoetig = false;
    if (P.ui) { pEntdeckenZeichnen(); pZuletztZeichnen(); }
    if (P.gewaehlt) await pWaehlen(P.gewaehlt, false);
  } catch (err) {
    P.ladenFehler = true;
    P.ladenNoetig = true;
    pFehler(err);
    pListe();
    if (P.ui) pEntdeckenZeichnen();
  } finally {
    P.ladenLaeuft = false;
    if (P.ladenNachholen) {
      P.ladenNachholen = false;
      P.ladenNoetig = true;
      await pLaden();
    }
  }
}

function pListe() {
  if (pGeschuetzt()) return;
  if (P.letztesLaden == null || (P.ladenFehler && !P.eintraegeGezeigt)) {
    $('#p-liste').replaceChildren(h('li', { class: 'leise', text: P.ladenFehler
      ? 'Liste nicht geladen – neuer Versuch läuft.' : 'Prompts werden geladen …' }));
    P.listeStand = null;
    return;
  }
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
  if (liste.length) P.eintraegeGezeigt = true;
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

function pBeschriftung(...teile) {
  return [...new Set(teile.filter(Boolean).flatMap((t) => t.split(' · ').map((s) => s.trim())).filter(Boolean))].join(' · ');
}

async function pAktion(daten) {
  const d = await api('/api/prompt', daten);
  if (d.id) P.gewaehlt = d.id;
  await pLaden();
}

function pOeffnen(e, was, datei = '') {
  return api('/api/prompt', { aktion: 'oeffnen', id: e.id, was, datei });
}

function pBelegAuftrag(e, b, art) {
  return (e.warteschlange || []).find((a) => a.art === art && a.prompt?.eintrag === e.id
    && a.prompt.beleg + '.md' === b.datei);
}

function pLaufanzeige(b, a = null) {
  if (!['wartet', 'laeuft'].includes(b.zustand)) return null;
  const start = Number.isFinite(a?.begonnen) ? new Date(a.begonnen * 1000)
    : new Date(typeof b.erstellt === 'string' ? b.erstellt.replace(' ', 'T') : NaN);
  const zeit = Number.isNaN(start.getTime()) ? '' : start.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  return h('div', { class: 'p-laufanzeige' }, h('p', { class: 'p-laufzeile', role: 'status',
    'data-zustand': b.zustand, text: b.zustand === 'wartet' ? 'Wartet auf den Start …'
      : `Läuft${zeit ? ` seit ${zeit}` : ''} – das Modell arbeitet noch …` }),
  b.zustand === 'laeuft' ? h('div', { class: 'balken offen', 'aria-hidden': 'true' }, h('i')) : null);
}

async function pWaehlen(id, bewusst = true) {
  if (pGeschuetzt()) return;
  const anfrage = ++P.anfrage;
  try {
    const e = await api(`/api/prompt?id=${encodeURIComponent(id)}`);
    if (anfrage !== P.anfrage || pGeschuetzt()) return;
    P.gewaehlt = id;
    if (bewusst && P.ui) {
      P.zuletzt = [id, ...P.zuletzt.filter((x) => x !== id)].slice(0, 6);
      pAuswahlMerken(); pZuletztZeichnen(); pAnsichtZeigen('bibliothek');
    }
    pListe();
    const { warteschlange, ...eintrag } = e;
    const stand = JSON.stringify({ eintrag, warteschlange: (warteschlange || [])
      .filter((a) => a.prompt?.eintrag === id && ['wartet', 'laeuft', 'fehler', 'abgebrochen'].includes(a.zustand))
      .map((a) => ({ id: a.id, fassung: a.prompt.fassung, beleg: a.prompt.beleg,
        auswerter: a.auswerter.name, zustand: a.zustand, begonnen: a.begonnen, meldung: a.meldung })) });
    if (stand === P.inhaltStand) return;
    const box = $('#p-inhalt');
    const gleicherEintrag = P.inhaltId === id;
    const offen = new Map(gleicherEintrag ? [...box.querySelectorAll('details[data-p-ansicht]')]
      .filter((d) => d.open).map((d) => [d.getAttribute('data-p-ansicht'), d.querySelector('.f-text')]) : []);
    const position = { oben: box.scrollTop, links: box.scrollLeft, x: window.scrollX, y: window.scrollY };
    const knoepfe = [pKnopf(e.herkunft === 'ordner' || id.startsWith('schatten:')
      ? 'Im Ordner öffnen' : 'In der Sammlung öffnen', () => pOeffnen(e,
      e.herkunft === 'ordner' || id.startsWith('schatten:') ? 'ordner' : 'sammlung'))];
    if (e.bearbeitbar) knoepfe.push(pKnopf('Kopfzeilen bearbeiten …', () => pDialog(e, 'kopf')),
      pKnopf('Neue Fassung …', () => pDialog(e, 'fassung_neu')));
    const generator = ['bild', 'video'].includes(e.prompt_typ);
    if (!e.fehler && e.fassungen.length) {
      if (!generator) knoepfe.push(pKnopf('Testen …', () => pTestdialog(e)));
      knoepfe.push(pSchaerfenMenue(e), pKnopf('Im Composer schärfen', () => pComposerBasis(e)));
      if (generator) knoepfe.push(h('span', { class: 'leise', text: 'Im Reiter Bild & Video verwenden.' }));
    }
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
    const gruppe = (e.auftragsgruppen || []).find((g) => g.id === P.letzteGruppe) || (e.auftragsgruppen || []).at(-1);
    const gruppenBox = h('section', { class: 'p-ergebnisgruppe' });
    if (gruppe) inhalt.push(gruppenBox);
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Fassungen' }));
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
      if (!e.fehler) {
        if (!generator) karte.append(pKnopf('Testen …', () => pTestdialog(e, f.name)));
        karte.append(pSchaerfenMenue(e, f.name));
      }
      inhalt.push(karte);
    }
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Tests' }));
    for (const t of e.tests) {
      const laufanzeige = pLaufanzeige(t, pBelegAuftrag(e, t, 'prompt'));
      const karte = h('article', { class: 'p-fassung' }, h('p', { text: [t.erstellt, t.fassung,
        t.geaendert ? 'seit dem Test geändert' : '', t.auswerter, t.dauer_s != null ? dauer(Number(t.dauer_s)) : '',
        t.tokens != null ? `${t.tokens} Token` : '', t.kosten_usd != null ? `${t.kosten_usd} USD` : '',
        !laufanzeige ? ZUSTAND[t.zustand] || t.zustand : '', t.urteil ? `Urteil: ${t.urteil}` : '', t.notiz, t.fehler].filter(Boolean).join(' · ') }),
      laufanzeige,
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
      const antwort = offen.get(JSON.stringify([t.datei, 'antwort'])) || h('div', { class: 'f-text' });
      const ansicht = JSON.stringify([t.datei, 'antwort']);
      const details = h('details', { 'data-p-ansicht': ansicht }, h('summary', { text: 'Antwort anzeigen' }), antwort);
      details.addEventListener('toggle', async () => {
        if (details.open) {
          try { pTextDarstellen(antwort, (await pBeleg(e, t)).antwort || 'Noch keine Antwort.'); }
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
      const laufanzeige = pLaufanzeige(t, pBelegAuftrag(e, t, 'schaerfen'));
      const antwort = offen.get(JSON.stringify([t.datei, 'schaerfen'])) || h('div', { class: 'f-text' });
      const ansicht = JSON.stringify([t.datei, 'schaerfen']);
      const details = h('details', { 'data-p-ansicht': ansicht }, h('summary', { text: 'Ergebnis anzeigen' }), antwort);
      details.addEventListener('toggle', async () => {
        if (details.open) {
          try { pSchaerfenErgebnis(antwort, await pBeleg(e, t, 'schaerfen'), e, t); }
          catch (err) { antwort.textContent = err.message; }
        }
      });
      inhalt.push(h('article', { class: 'p-fassung' }, h('p', { text: [t.erstellt, t.aktion, t.auswerter,
        t.zielmodell, !laufanzeige ? ZUSTAND[t.zustand] || t.zustand : '',
        !laufanzeige ? t.ergebnis : '', t.fehler].filter(Boolean).join(' · ') }), laufanzeige,
      pKnopf('Öffnen', () => pOeffnen(e, 'schaerfen', t.datei)), details,
      !t.fehler && t.verwaist && ['abgebrochen', 'fehler'].includes(t.zustand) ? pKnopf('Wiederholen', () =>
        pAktion({ aktion: 'wiederholen_beleg', id: e.id, datei: t.datei, art_ordner: 'schaerfen' })) : null));
    }
    inhalt.push(h('h3', { class: 'abschnitt', text: 'Warteschlange' }));
    for (const a of (e.warteschlange || []).filter((a) => a.prompt?.eintrag === e.id
      && ['wartet', 'laeuft', 'fehler', 'abgebrochen'].includes(a.zustand))) {
      const aktion = (was) => async () => { await api('/api/fassung', { id: a.id, aktion: was }); await pLaden(); };
      const beleg = (a.art === 'schaerfen' ? e.schaerfen || [] : e.tests).find((b) => b.datei === a.prompt.beleg + '.md');
      const laufanzeige = pLaufanzeige({ zustand: a.zustand, erstellt: beleg?.erstellt }, a);
      inhalt.push(h('article', { class: 'p-fassung' }, h('p', { text:
        laufanzeige ? `${a.art === 'schaerfen' ? 'Schärfen · ' : ''}${a.prompt.fassung} · ${a.auswerter.name}`
          : `${a.art === 'schaerfen' ? 'Schärfen · ' : ''}${a.prompt.fassung} · ${a.auswerter.name} · ${ZUSTAND[a.zustand] || a.zustand} · ${a.meldung || ''}` }),
      laufanzeige,
      ...(['wartet', 'laeuft'].includes(a.zustand) ? [pKnopf('Abbrechen', aktion('abbrechen'))]
        : (a.art === 'schaerfen' ? e.schaerfen || [] : e.tests).some((t) => t.datei === `${a.prompt.beleg}.md` && t.fehler) ? []
          : [pKnopf('Wiederholen', aktion('wiederholen'))]),
      a.zustand !== 'laeuft' ? pKnopf('Entfernen', aktion('entfernen')) : null));
    }
    if (!e.tests.length) inhalt.push(h('p', { class: 'leise', text: 'Noch keine Testbelege.' }));
    box.replaceChildren(...inhalt);
    if (gruppe) await pGruppeZeichnen(gruppenBox, e, gruppe);
    if (anfrage !== P.anfrage) return;
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
  } else if (aktion === 'fassung_neu') feld('name', 'Name der neuen Fassung', e.fassung_vorschlag);
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
  if (aktion === 'fassung_neu') felder.name.select();
}

function pBeleg(e, t, was = 'beleg') {
  return api(`/api/prompt-datei?id=${encodeURIComponent(e.id)}&was=${was}&datei=${encodeURIComponent(t.datei)}`);
}

function pMenuesSchliessen(innerhalb) {
  for (const d of document.querySelectorAll('#p-composer details.p-auswahl')) {
    if (d.open && !d.contains(innerhalb)) d.open = false;
  }
  for (const m of document.querySelectorAll('.p-schaerfen-menue')) {
    // Der zugehörige Schärfen-Knopf gehört für Außenklick und Fokus zum Menü.
    if (!m.hidden && !m.parentElement.contains(innerhalb)) {
      m.hidden = true;
      m.parentElement.querySelector('button').setAttribute('aria-expanded', 'false');
    }
  }
}

function pMenueEreignis(e) {
  if (e.type === 'toggle') {
    if (e.target.matches('#p-composer details.p-auswahl') && e.target.open) pMenuesSchliessen(e.target);
  } else pMenuesSchliessen(e.target);
}

function pSchaerfenMenue(e, name) {
  const menue = h('span', { class: 'p-schaerfen-menue', hidden: true });
  const b = pKnopf('Schärfen ▾', () => {
    if (menue.hidden) pMenuesSchliessen(b);
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

function pTextDarstellen(box, text) {
  box.replaceChildren(h('div', { class: 'p-text', text }));
}

function pSchaerfenErgebnis(box, b, e = null, beleg = null, vergleich = false) {
  const fragen = b.aktion === 'Erst klären';
  if (fragen) {
    pTextDarstellen(box, b.fragen || 'Noch keine Antwort.');
  } else {
    const neu = h('section', {}, h('h4', { text: 'Neue Fassung' }),
      h('pre', { class: 'p-text', text: b.neue_fassung || 'Keine gültige neue Fassung.' }));
    const aenderungen = h('details', { 'data-p-ansicht': JSON.stringify([beleg?.datei || b.datei, 'aenderungen']) },
      h('summary', { text: 'Was geändert wurde' }), h('div', { class: 'p-text', text: b.stichpunkte || 'Noch keine Antwort.' }));
    box.replaceChildren(vergleich ? neu : h('div', { class: 'p-vergleich' },
      h('section', {}, h('h4', { text: 'Original' }), h('pre', { class: 'p-text', text: b.original })), neu), aenderungen);
    if (b.neue_platzhalter?.length) box.append(h('p', { text: `Neue Platzhalter: ${b.neue_platzhalter.map((n) => `[${n}]`).join(', ')}` }));
    if (b.grund) box.append(h('p', { class: 'warnung', text: b.grund }), h('pre', { class: 'p-text', text: b.antwort }));
    if (b.eingaben?.typ?.id === 'auto') box.append(h('p', { class: 'leise', text: 'Prompt-Typ: ' + b.typ_anzeige }));
  }
  const aktionen = h('div', { class: 'p-knoepfe' });
  if (!fragen && !vergleich) aktionen.append(pKnopf('Original kopieren', () => navigator.clipboard.writeText(b.original)));
  if (!fragen && b.neue_fassung && !b.grund) aktionen.append(pKnopf('Neue Fassung kopieren', () => navigator.clipboard.writeText(b.neue_fassung)));
  if (e && beleg) {
    const generator = ['bild', 'video'].includes(b.zielprofil_id);
    if (generator) box.append(h('p', { class: 'leise', text: 'Im Reiter Bild & Video verwenden.' }));
    else if (!fragen && b.neue_fassung && !b.grund) aktionen.append(pKnopf('Testen …', async () => {
      if (e.herkunft === 'sammlung') await pTestdialog(e, null, null,
        { schaerfen_beleg: beleg.datei, text: b.neue_fassung, testprofil: b.testprofil_id });
      else await pTestdialog(await api(`/api/prompt?id=${encodeURIComponent(e.id)}`),
        b.ergebnis_fassung || /^übernommen \((.*)\)$/.exec(b.ergebnis || '')?.[1], null,
        { testprofil: b.testprofil_id });
    }));
    const f = e.fassungen.find((f) => f.name === b.ergebnis_fassung);
    if (f && !beleg.ergebnis_fehlt) {
      if (beleg.ergebnis_geaendert) box.append(h('p', { class: 'leise',
        text: `Die übernommene Fassung „${f.name}“ wurde seitdem bearbeitet. Die Knöpfe verwenden ihren aktuellen Stand.` }));
      if (e.bearbeitbar) aktionen.append(e.bevorzugt === f.name ? h('span', { class: 'leise', text: 'Bevorzugt' })
        : pKnopf('Als bevorzugt', () => pAktion({ aktion: 'bevorzugt', id: e.id, name: f.name, kopf_stand: e.kopf_stand })));
      aktionen.append(pKnopf('Im Composer verfeinern', () => pComposerVerfeinern(e, b)));
    }
    if (!['wartet', 'laeuft'].includes(beleg.zustand)) aktionen.append(pKnopf('Nochmal …', () => pComposerNochmal(e, b)));
  }
  box.append(aktionen);
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
  const erlaubt = (p) => p.prompts_verfuegbar ?? p.verfuegbar;
  const profile = (schreiben = false) => stand.auswerter.map((p) => h('option', { value: p.id,
    disabled: schreiben && !erlaubt(p),
    text: pBeschriftung(p.name, p.zugang_text || (p.cloud ? `Cloud (${p.cloud})` : 'lokal'), erlaubt(p) ? '' : p.prompts_grund || p.grund) }));
  const schreibmodell = auswahl('Schreibmodell', profile(true));
  const zielmodell = auswahl('Zielmodell', profile());
  let zuletzt = '', tests = [];
  try {
    zuletzt = localStorage.getItem('werkstatt.prompt-schreibmodell') || '';
    tests = JSON.parse(localStorage.getItem('werkstatt.prompt-auswerter') || '[]');
  } catch { /* Ohne Speicher die Vorgaben verwenden. */ }
  schreibmodell.value = (stand.auswerter.find((p) => p.id === zuletzt && erlaubt(p))
    || stand.auswerter.find((p) => erlaubt(p) && ['claude', 'codex'].includes(p.anbieter))
    || stand.auswerter.find(erlaubt))?.id || '';
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
    feld('Letzte Antwort als Material', material),
    pKnopf('Modelle verwalten …', () => pModelleVerwalten(stand)), vorschau, rueck], [
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

async function pModelleVerwalten(stand = null) {
  await auswerterDialog(stand || await api('/api/zusammenfassung'), async () => {
    const neu = await api('/api/zusammenfassung');
    if (P.ui) await pOptionenLaden(true);
    await pLaden();
    return neu;
  });
}

async function pTestdialog(e, name, beleg = null, quelle = null) {
  const stand = await api('/api/zusammenfassung');
  const gewaehlt = new Set();
  try { JSON.parse(localStorage.getItem('werkstatt.prompt-auswerter') || '[]').forEach((id) => gewaehlt.add(id)); }
  catch { /* Ohne Speicher bleibt die Auswahl leer. */ }
  if (quelle && 'testprofil' in quelle) { gewaehlt.clear(); if (quelle.testprofil) gewaehlt.add(quelle.testprofil); }
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
  const testFassungen = quelle?.schaerfen_beleg ? [{ name: 'Sammlungsvorschlag', text: quelle.text }] : e.fassungen;
  const namen = [...new Set(testFassungen.flatMap((f) => [...f.text.matchAll(/\[([^\[\]\n]{1,60})\](?!\()/g)]
    .map((m) => m[1]).filter((n) => !n.includes(':') && /\p{L}/u.test(n))).concat(Object.keys(beleg?.eingaben.felder || {})))];
  const feldBox = h('div');
  const auswahlBox = h('div', { class: 'p-test-auswahl' });
  for (const f of testFassungen) {
    const cb = h('input', { type: 'checkbox' });
    cb.checked = !!quelle?.schaerfen_beleg || f.name === (name || e.bevorzugt || e.fassungen[0].name);
    cb.disabled = !!quelle?.schaerfen_beleg;
    fassungen.set(f.name, cb);
    auswahlBox.append(h('label', { class: 'wahl' }, cb, f.name));
  }
  for (const p of stand.auswerter) {
    const erlaubt = p.prompts_verfuegbar ?? p.verfuegbar;
    const cb = h('input', { type: 'checkbox', disabled: !erlaubt });
    cb.checked = erlaubt && gewaehlt.has(p.id);
    auswerter.set(p.id, cb);
    auswahlBox.append(h('label', { class: 'wahl' }, cb,
      pBeschriftung(p.name, p.zugang_text || (p.cloud ? `Cloud (${p.cloud})` : 'lokal'), erlaubt ? '' : p.prompts_grund || p.grund)));
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
      ...(quelle?.schaerfen_beleg ? { schaerfen_beleg: quelle.schaerfen_beleg } : {}),
      auswerter: [...auswerter].filter(([, cb]) => cb.checked).map(([n]) => n), rahmen: rahmen.checked,
      eingaben: { felder: Object.fromEntries([...felder].map(([n, f]) => [n,
        f.woertlich.checked ? { art: 'woertlich' } : f.quelle || { art: 'text', wert: f.text.value }])) } };
  }
  const d = dialogOeffnen(`Testen: ${e.titel}`, [auswahlBox,
    ...(quelle?.schaerfen_beleg ? [h('p', { class: 'leise', text: 'Sammlungsvorschlag · schreibgeschützte Testfassung' }),
      h('pre', { class: 'p-text', text: quelle.text })] : []),
    ...(quelle && !stand.auswerter.some((p) => p.id === quelle.testprofil && (p.prompts_verfuegbar ?? p.verfuegbar))
      ? [h('p', { class: 'leise', text: 'Für dieses Ziel ist kein verfügbares Testprofil gewählt. Wähle einen Auswerter oder lege ein Testprofil an.' }),
        pKnopf('Testprofil anlegen …', () => pModelleVerwalten())] : []),
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
$('#p-laden').addEventListener('click', async () => { if (P.ui) await pOptionenLaden(true); await pLaden(); });
window.promptsAktiv = (aktiv) => {
  P.aktiv = aktiv;
  if (aktiv && document.getElementById?.('p-composer')) {
    pComposerZeigen();
    if (!P.optionen && !P.optionenLaeuft) pOptionenLaden();
  }
  if (aktiv && pLadenFaellig()) pLaden();
  if (!P.timer && typeof setTimeout === 'function') {
    const weiter = () => {
      P.timer = setTimeout(async () => {
        if (P.aktiv && P.ui && !P.optionen && !P.optionenLaeuft) await pOptionenLaden();
        if (P.aktiv && !pGeschuetzt() && pLadenFaellig()) await pLaden();
        weiter();
      }, 2500);
    };
    weiter();
  }
};

// Composer und Katalog haben eigene Wurzeln. Bibliotheksabrufe ersetzen diese Elemente nicht.
function pAuswahlMerken() {
  try {
    localStorage.setItem('werkstatt.prompt-zuletzt', JSON.stringify(P.zuletzt));
    localStorage.setItem('werkstatt.prompt-schreibmodelle', JSON.stringify(P.entwurf.schreibmodelle));
    localStorage.setItem('werkstatt.prompt-auswahl', JSON.stringify({ prompt_typ: P.entwurf.prompt_typ,
      modus: P.entwurf.modus, ziele: P.entwurf.ziele }));
  } catch { /* Die Seite funktioniert auch ohne Browserablage. */ }
}

function pEntwurfNeu() {
  return { text: '', titel: '', hinweise: '', ablage: 'ordner', basis: null,
    prompt_typ: 'auto', modus: 'prompt', schreibmodelle: [],
    ziele: [{ zielprofil: 'qwen27', eintrag: 'qwen27-unsloth', testprofil: null }], materialien: [], kontexte: [] };
}

function pAnsichtZeigen(ansicht) {
  if (!P.ui) return;
  P.ansicht = ansicht;
  $('#p-composer').hidden = ansicht !== 'neu';
  $('#p-entdecken').hidden = !['neu', 'suche'].includes(ansicht);
  $('#p-inhalt').hidden = ansicht !== 'bibliothek';
  $('#p-bibliotheksliste').hidden = ansicht !== 'bibliothek';
  $('#p-zuletzt').hidden = ansicht === 'bibliothek';
  $('#p-kontexte').hidden = ansicht !== 'kontexte';
  for (const b of $('#p-navigation').querySelectorAll('button')) b.setAttribute('aria-current', b.ansicht === ansicht ? 'page' : 'false');
  if (ansicht === 'suche') $('#p-katalog-suche').focus();
}

function pFeld(name, text, el) {
  el.id = name;
  return h('label', { class: 'dialog-feld', for: name }, text, el);
}

function pPfeil(nachOben = false) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('width', '20'); svg.setAttribute('height', '20');
  svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  const pfad = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  pfad.setAttribute('d', nachOben ? 'M12 20V4m-7 7 7-7 7 7' : 'M4 12h16m-7-7 7 7-7 7');
  svg.append(pfad); return svg;
}

function pComposerZeigen() {
  if (P.ui) return;
  P.ui = true; P.entwurf = pEntwurfNeu(); P.zuletzt = []; P.zielMerker = new Map();
  try {
    const auswahl = JSON.parse(localStorage.getItem('werkstatt.prompt-auswahl') || '{}');
    if (['prompt', 'vorlage'].includes(auswahl.modus)) P.entwurf.modus = auswahl.modus;
    if (typeof auswahl.prompt_typ === 'string') P.entwurf.prompt_typ = auswahl.prompt_typ;
    if (Array.isArray(auswahl.ziele)) {
      const ziele = auswahl.ziele.filter((z) => z && typeof z === 'object' && typeof z.zielprofil === 'string').map((z) =>
        Object.fromEntries(['zielprofil', 'eintrag', 'testprofil', 'variante'].filter((k) => typeof z[k] === 'string' || (k === 'testprofil' && z[k] === null)).map((k) => [k, z[k]])));
      if (ziele.length) P.entwurf.ziele = ziele;
    }
    P.entwurf.schreibmodelle = pSchreibauswahlLaden();
    const zuletzt = JSON.parse(localStorage.getItem('werkstatt.prompt-zuletzt') || '[]');
    if (Array.isArray(zuletzt)) P.zuletzt = zuletzt.filter((x) => typeof x === 'string').slice(0, 6);
  } catch { /* Vorgaben verwenden. */ }
  const roh = h('textarea', { id: 'p-rohprompt', rows: '7', spellcheck: 'true',
    placeholder: 'Beschreibe die Aufgabe, das gewünschte Ergebnis und wichtige Grenzen …' });
  const titel = h('input', { id: 'p-composer-titel', type: 'text' });
  const hinweise = h('textarea', { id: 'p-composer-hinweise', rows: '3', maxlength: '2000' });
  const ablage = h('select', { id: 'p-ablage' }, h('option', { value: 'ordner', text: 'Eigener Prompt – Coding/Kreativ' }),
    h('option', { value: 'sammlung', text: 'Vorhandener Wissensprompt aus der Sammlung' }));
  const basis = h('select', { id: 'p-sammlungsbasis', 'aria-label': 'Sammlungseintrag', hidden: true });
  const typBox = h('div', { role: 'radiogroup', 'aria-label': 'Prompt-Typ', id: 'p-typen' });
  const typMenue = h('details', { class: 'p-auswahl', id: 'p-typmenue' }, h('summary', { id: 'p-typname', text: 'Prompt-Typ: Auto' }), typBox);
  const schreiben = h('details', { class: 'p-auswahl', id: 'p-schreibmenue' },
    h('summary', { id: 'p-schreibname', text: 'Schreibmodell wählen' }), h('div', { id: 'p-schreibmodelle' }));
  const senden = h('button', { type: 'button', class: 'knopf knopf-haupt p-senden', id: 'p-senden',
    title: 'Prompt schärfen', 'aria-label': 'Prompt schärfen', disabled: true, onclick: pComposerSenden }, pPfeil(true));
  const vorschau = h('details', { id: 'p-auftragsvorschau' }, h('summary', { text: 'Auftragsvorschau' }),
    pKnopf('Auftragsvorschau berechnen', pComposerVorschau), h('div', { id: 'p-vorschauinhalt' }));
  const material = pKnopf('Datei anhängen', () => pMaterialMenue());
  material.id = 'p-material-knopf'; material.title = 'Datei anhängen';
  const kontext = pKnopf('Kontext auswählen', () => pKontexteZeigen(true));
  kontext.id = 'p-kontext-knopf'; kontext.title = 'Kontext auswählen';
  const modus = h('fieldset', { class: 'p-modus' }, h('legend', { class: 'sr-only', text: 'Prompt oder Vorlage' }),
    ...['prompt', 'vorlage'].map((id) => {
      const radio = h('input', { type: 'radio', name: 'p-modus', value: id });
      radio.checked = P.entwurf.modus === id;
      radio.addEventListener('change', () => { if (radio.checked) { P.entwurf.modus = id; pAuswahlMerken(); } });
      return h('label', {}, radio, id === 'prompt' ? 'Prompt' : 'Vorlage');
    }));
  $('#p-composer').append(h('header', { class: 'p-einstieg' }, h('h2', { text: 'Prompts gezielt verbessern' }),
    h('p', { text: 'Schreibe deinen Rohprompt und wähle, für welche Modelle er passen soll.' })),
    h('section', { class: 'p-composer-karte', 'aria-label': 'Neuen Prompt schärfen' },
      h('p', { id: 'p-basis-hinweis', class: 'leise', hidden: true }), pFeld('p-rohprompt', 'Rohprompt', roh),
      h('fieldset', { class: 'p-zielauswahl' }, h('legend', { text: 'Für welches Modell?' }),
        h('p', { class: 'leise', text: 'Für jedes angekreuzte Modell entsteht eine eigene Fassung. Jedes Schreibmodell formuliert eine eigene.' }),
        h('div', { id: 'p-ziele' })),
      h('div', { class: 'p-composer-fuss' }, typMenue, schreiben, kontext, material, senden),
      h('p', { id: 'p-schreibhinweis', class: 'leise', text: 'Dieses Modell überarbeitet deinen Prompt.' }),
      h('div', { id: 'p-chips', class: 'p-knoepfe' }), h('p', { id: 'p-material-hinweis', class: 'leise' })), modus,
    h('details', { class: 'p-weitere' }, h('summary', { text: 'Weitere Angaben' }),
      pFeld('p-composer-titel', 'Titel, optional', titel), pFeld('p-composer-hinweise', 'Hinweise', hinweise),
      pFeld('p-ablage', 'Ablage', ablage), basis, vorschau),
    h('p', { id: 'p-composer-status', class: 'leise', 'aria-live': 'polite', text: 'Modelle und Prompt-Typen werden geladen …' }),
    h('div', { id: 'p-schreibgruende' }), pKnopf('Modelle verwalten …', () => pModelleVerwalten()),
    h('div', { id: 'p-sendungsaktionen', class: 'p-knoepfe' }));
  for (const [feld, key] of [[roh, 'text'], [titel, 'titel'], [hinweise, 'hinweise']]) feld.addEventListener('input', () => {
    P.entwurf[key] = feld.value;
  });
  ablage.addEventListener('change', () => {
    P.entwurf.ablage = ablage.value;
    basis.hidden = ablage.value !== 'sammlung';
    if (ablage.value === 'ordner') { P.entwurf.basis = null; roh.readOnly = false; }
  });
  basis.addEventListener('change', () => {
    const e = P.eintraege.find((x) => x.id === basis.value);
    if (e) pComposerBasis(e);
  });
  roh.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter' && !e.isComposing) { e.preventDefault(); return pComposerSenden(); }
  });
  for (const [id, name] of [['neu', 'Neuer Prompt'], ['bibliothek', 'Bibliothek'], ['kontexte', 'Kontextbausteine'], ['suche', 'Suche']]) {
    const b = pKnopf(name, () => id === 'kontexte' ? pKontexteZeigen(false) : pAnsichtZeigen(id));
    b.ansicht = id; $('#p-navigation').append(b);
  }
  const suche = h('input', { id: 'p-katalog-suche', type: 'search', placeholder: 'Prompts suchen …', 'aria-label': 'Entdecken durchsuchen' });
  suche.addEventListener('input', pEntdeckenZeichnen);
  $('#p-entdecken').append(h('div', { class: 'p-entdecken-kopf' }, h('div', {}, h('h2', { text: 'Entdecken' }),
    h('p', { class: 'leise', text: 'Wähle einen Prompt und passe ihn an deine Aufgabe an.' })), suche),
    h('div', { id: 'p-kategorien', class: 'p-kategorien', 'aria-label': 'Prompt-Kategorien' }), h('div', { id: 'p-karten' }));
  document.addEventListener?.('keydown', (e) => {
    if (e.key !== 'Escape' || document.querySelector('dialog[open]')) return;
    const offen = [...$('#p-composer').querySelectorAll('details.p-auswahl')].filter((d) => d.open).at(-1);
    if (offen) { offen.open = false; offen.querySelector('summary').focus(); e.preventDefault(); }
    else {
      const menue = [...document.querySelectorAll('.p-schaerfen-menue')].filter((m) => !m.hidden).at(-1);
      if (menue) { menue.hidden = true; const b = menue.parentElement.querySelector('button'); b.setAttribute('aria-expanded', 'false'); b.focus(); e.preventDefault(); }
    }
  });
  // Ein delegierter Handler bleibt auch nach dem Neuzeichnen der Auswahl gültig.
  for (const art of ['pointerdown', 'focusin', 'toggle']) document.addEventListener?.(art, pMenueEreignis, true);
  window.addEventListener?.('beforeunload', (e) => {
    if (P.entwurf.text.trim() || P.sendung) { e.preventDefault(); e.returnValue = ''; }
  });
  pAnsichtZeigen('neu'); pEntdeckenZeichnen(); pZuletztZeichnen();
}

async function pOptionenLaden(neu = false) {
  if (P.optionenLaeuft || (P.optionen && !neu)) return;
  P.optionenLaeuft = true;
  try {
    const d = await api('/api/prompt-optionen');
    const erstesLaden = !P.optionen;
    P.optionen = d;
    const typ = d.typen.find((x) => x.id === P.entwurf.prompt_typ) || d.typen[0];
    P.entwurf.prompt_typ = typ.id;
    const ziele = P.entwurf.ziele.filter((z) => d.zielprofile.some((p) => p.id === z.zielprofil) || z.zielprofil in d.generatoren);
    if (P.entwurf.ziele.length && !ziele.length) P.entwurf.ziele = pEntwurfNeu().ziele;
    else P.entwurf.ziele = ziele;
    $('#p-typen').replaceChildren(...d.typen.map((t) => {
      const radio = h('input', { type: 'radio', name: 'p-prompt-typ', value: t.id });
      radio.checked = typ.id === t.id;
      radio.addEventListener('change', () => { if (radio.checked) pTypWaehlen(t.id); });
      return h('label', { class: 'p-typoption' }, radio, h('span', {}, h('strong', { text: t.name }), h('small', { text: t.untertitel })));
    }));
    $('#p-typname').textContent = 'Prompt-Typ: ' + typ.name;
    pSchreibmodelleSetzen(P.entwurf.schreibmodelle, erstesLaden);
    if (erstesLaden && !P.entwurf.schreibmodelle.length) {
      const modell = d.schreibmodelle.find((p) => p.prompts_verfuegbar && ['claude', 'codex'].includes(p.anbieter))
        || d.schreibmodelle.find((p) => p.prompts_verfuegbar);
      pSchreibmodelleSetzen(modell ? [modell.id] : []);
    }
    pSchreibmodelleZeichnen();
    pZieleZeichnen(); pComposerZusammenfassung(); pEntdeckenZeichnen();
  } catch (err) { $('#p-composer-status').textContent = err.message; }
  finally { P.optionenLaeuft = false; }
}

function pSchreibauswahlLaden() {
  try {
    const liste = localStorage.getItem('werkstatt.prompt-schreibmodelle');
    const alt = localStorage.getItem('werkstatt.prompt-schreibmodell');
    const ids = liste === null ? (alt ? [alt] : []) : JSON.parse(liste);
    return Array.isArray(ids) ? ids.filter((id) => typeof id === 'string') : [];
  } catch { return []; }
}

function pSchreibmodelleSetzen(ids, nurVerfuegbar = false) {
  P.entwurf.schreibmodelle = (P.optionen?.schreibmodelle || [])
    .filter((p) => ids.includes(p.id) && (!nurVerfuegbar || p.prompts_verfuegbar)).slice(0, 3).map((p) => p.id);
  P.schreibmodellFehlt = false;
}

function pSchreibmodelleZeichnen() {
  const ids = P.entwurf.schreibmodelle;
  const profile = P.optionen?.schreibmodelle || [];
  $('#p-schreibmodelle').replaceChildren(...profile.map((p) => {
    const gewaehlt = ids.includes(p.id);
    const voll = !gewaehlt && ids.length >= 3;
    const cb = h('input', { type: 'checkbox', value: p.id, 'aria-label': p.name,
      disabled: voll || (!gewaehlt && !p.prompts_verfuegbar), ...(voll ? { title: 'Höchstens drei Schreibmodelle' } : {}) });
    cb.checked = gewaehlt;
    cb.addEventListener('change', () => {
      const auswahl = new Set(P.entwurf.schreibmodelle);
      if (cb.checked) auswahl.add(p.id);
      else if (auswahl.size > 1) auswahl.delete(p.id);
      pSchreibmodelleSetzen([...auswahl]);
      pSchreibmodelleZeichnen(); pAuswahlMerken(); pComposerZusammenfassung();
    });
    return h('label', { class: 'p-typoption' }, cb, h('span', { text: pBeschriftung(p.name, p.zugang_text,
      p.prompts_verfuegbar ? '' : p.prompts_grund || p.grund) }));
  }));
  const namen = profile.filter((p) => ids.includes(p.id)).map((p) => pBeschriftung(p.name, p.zugang_text));
  $('#p-schreibname').textContent = (namen.length > 1 ? 'Schreibmodelle: ' : 'Schreibmodell: ') + (namen.join(' + ') || 'Bitte wählen');
  $('#p-schreibhinweis').textContent = namen.length > 1 ? 'Jedes gewählte Modell schreibt eine eigene Fassung.' : 'Dieses Modell überarbeitet deinen Prompt.';
}

function pTypWaehlen(id) {
  const generatorAlt = ['bild', 'video'].includes(P.entwurf.prompt_typ);
  const generatorNeu = ['bild', 'video'].includes(id);
  if (!generatorAlt && generatorNeu) P.textziele = P.entwurf.ziele;
  P.entwurf.prompt_typ = id;
  if (generatorNeu) P.entwurf.ziele = [{ zielprofil: id }];
  else if (generatorAlt) P.entwurf.ziele = P.textziele || pEntwurfNeu().ziele;
  P.entwurf.realismus = false;
  $('#p-typname').textContent = 'Prompt-Typ: ' + P.optionen.typen.find((t) => t.id === id).name;
  $('#p-typmenue').open = false; $('#p-typmenue').querySelector('summary').focus();
  pZieleZeichnen(); pAuswahlMerken(); pComposerZusammenfassung();
}

function pZieleZeichnen() {
  const d = P.entwurf;
  if (['bild', 'video'].includes(d.prompt_typ)) {
    d.ziele = [{ zielprofil: d.prompt_typ }];
    const real = h('input', { type: 'checkbox', id: 'p-realismus' }); real.checked = !!d.realismus;
    real.addEventListener('change', () => { d.realismus = real.checked; });
    $('#p-ziele').replaceChildren(h('p', { text: P.optionen.generatoren[d.prompt_typ].name }),
      h('label', { class: 'wahl' }, real, 'Fotorealistische Menschen'));
    return;
  }
  $('#p-ziele').replaceChildren(...P.optionen.zielprofile.map((p) => {
    let wahl = d.ziele.find((z) => z.zielprofil === p.id) || P.zielMerker.get(p.id);
    const varianten = p.varianten || [];
    const lokal = p.anbieter === 'lokal';
    if (!wahl) wahl = lokal ? { zielprofil: p.id, eintrag: varianten[0]?.eintrag || '', testprofil: null }
      : { zielprofil: p.id, testprofil: varianten[0]?.testprofil || null };
    if (lokal && !varianten.some((v) => v.eintrag === wahl.eintrag)) wahl = { zielprofil: p.id, eintrag: varianten[0]?.eintrag || '', testprofil: null };
    if (!lokal && !varianten.some((v) => v.testprofil === wahl.testprofil)) wahl.testprofil = varianten[0]?.testprofil || null;
    P.zielMerker.set(p.id, wahl);
    const cb = h('input', { type: 'checkbox', 'aria-label': p.name });
    cb.checked = d.ziele.some((z) => z.zielprofil === p.id);
    cb.disabled = !varianten.length;
    if (cb.checked) d.ziele = d.ziele.map((z) => z.zielprofil === p.id ? wahl : z);
    const details = h('div', { class: 'p-ziel-details', hidden: !cb.checked });
    cb.addEventListener('change', () => {
      d.ziele = d.ziele.filter((z) => z.zielprofil !== p.id);
      if (cb.checked) d.ziele.push(wahl);
      details.hidden = !cb.checked; pAuswahlMerken(); pComposerZusammenfassung();
    });
    const select = h('select', { 'aria-label': 'Variante für ' + p.name }, ...varianten.map((v) => h('option', {
      value: lokal ? v.eintrag : v.testprofil, text: v.name })));
    select.value = lokal ? wahl.eintrag : wahl.testprofil || '';
    const lokalDetails = h('div');
    const ergaenzen = () => {
      if (!lokal) return;
      const v = varianten.find((x) => x.eintrag === wahl.eintrag);
      if (!v) return;
      const test = h('select', { 'aria-label': 'Testprofil für ' + p.name }, h('option', { value: '', text: 'Testprofil fehlt / später wählen' }),
        ...(v.testprofile || []).map((x) => h('option', { value: x.id, text: x.name })));
      if (!v.testprofile?.some((x) => x.id === wahl.testprofil)) wahl.testprofil = v.testprofile?.[0]?.id || null;
      test.value = wahl.testprofil || '';
      test.addEventListener('change', () => { wahl.testprofil = test.value || null; pAuswahlMerken(); pComposerZusammenfassung(); });
      lokalDetails.replaceChildren(test);
      if (v.varianten?.length) {
        if (wahl.variante && !v.varianten.some((x) => x.id === wahl.variante)) delete wahl.variante;
        const variante = h('select', { 'aria-label': 'Zentrale-Variante für ' + p.name },
          h('option', { value: '', text: 'In der Zentrale gewählte Variante' }),
          ...v.varianten.map((x) => h('option', { value: x.id, text: x.name })));
        variante.value = wahl.variante || '';
        variante.addEventListener('change', () => { if (variante.value) wahl.variante = variante.value; else delete wahl.variante; pAuswahlMerken(); });
        lokalDetails.append(variante);
      }
      if (v.hinweis) lokalDetails.append(h('p', { class: 'leise', text: v.hinweis }));
      if (!v.testprofile?.length) lokalDetails.append(pKnopf('Testprofil anlegen …', () => pModelleVerwalten()));
    };
    select.addEventListener('change', () => {
      if (lokal) { wahl.eintrag = select.value; wahl.testprofil = null; delete wahl.variante; ergaenzen(); }
      else wahl.testprofil = select.value;
      pAuswahlMerken(); pComposerZusammenfassung();
    });
    ergaenzen(); details.append(select, lokalDetails);
    return h('section', { class: 'p-ziel' }, h('label', { class: 'wahl' }, cb, p.name), details,
      ...(!varianten.length ? [h('p', { class: 'leise', text: 'Kein passendes Profil vorhanden.' }),
        pKnopf('Testprofil anlegen …', () => pModelleVerwalten())] : []));
  }));
}

function pComposerZusammenfassung(meldung = '') {
  const profile = (P.optionen?.schreibmodelle || []).filter((p) => P.entwurf.schreibmodelle.includes(p.id));
  const fehlt = profile.find((p) => !p.prompts_verfuegbar);
  $('#p-senden').disabled = !!P.sendenLaeuft || !!P.sendung || !profile.length || !!fehlt;
  if (!meldung && P.sendung?.unklar) meldung = 'Die Bestätigung fehlt. Prüfe den Auftragsstatus, bevor du erneut sendest.';
  const n = P.entwurf.ziele.length, m = profile.length;
  let status = 'Bitte ein Schreibmodell wählen.';
  if (fehlt) status = `${fehlt.name} ist gerade nicht verfügbar.`;
  else if (!m && P.schreibmodellFehlt) status = 'Das Schreibmodell dieses Laufs gibt es nicht mehr. Bitte neu wählen.';
  else if (m === 1) status = `${n} ${n === 1 ? 'Zielmodell' : 'Zielmodelle'} · ${n} ${n === 1 ? 'Schärfen-Lauf' : 'Schärfen-Läufe'} · Schreibmodell: ${pBeschriftung(profile[0].name, profile[0].zugang_text)}`;
  else if (m > 1) status = `${n} ${n === 1 ? 'Zielmodell' : 'Zielmodelle'} × ${m} Schreibmodelle · ${n * m} Schärfen-Läufe`;
  $('#p-composer-status').textContent = meldung || status;
  const cloud = profile.filter((p) => p.cloud).map((p) => p.name);
  $('#p-material-hinweis').textContent = cloud.length && (P.entwurf.materialien.length || P.entwurf.kontexte.length)
    ? `Ausgewähltes Material und Kontext werden an ${cloud.join(' und ')} mitgesendet.` : '';
  pProfilProblemeZeichnen();
}

function pProfilProblemeZeichnen() {
  const box = $('#p-schreibgruende');
  const offen = box.querySelector('details')?.open || false;
  const fehlt = (P.optionen?.schreibmodelle || []).filter((p) => !(p.prompts_verfuegbar ?? p.verfuegbar));
  const gewaehlt = new Set([...P.entwurf.schreibmodelle, ...P.entwurf.ziele.map((z) => z.testprofil)]);
  const zeile = (p) => h('p', { class: 'leise', text: pBeschriftung(p.name, p.prompts_grund || p.grund) });
  const details = h('details', {}, h('summary', { text: `Nicht verfügbare Modelle (${fehlt.length})` }), ...fehlt.map(zeile));
  details.open = offen;
  box.replaceChildren(...fehlt.filter((p) => gewaehlt.has(p.id)).map(zeile), ...(fehlt.length ? [details] : []));
}

function pComposerDaten() {
  return JSON.parse(JSON.stringify(P.entwurf));
}

async function pComposerVorschau() {
  try {
    const v = await api('/api/prompt', { ...pComposerDaten(), aktion: 'composer_vorschau' });
    const schreibmodelle = v.schreibmodelle || P.optionen.schreibmodelle.filter((p) => P.entwurf.schreibmodelle.includes(p.id));
    $('#p-vorschauinhalt').replaceChildren(...v.ziele.map((z) => h('section', {}, h('h3', { text: z.zielmodell.name }),
      h('pre', { class: 'p-text', text: z.auftrag }), h('p', { class: 'leise', text: z.gesendet_stand }),
      h('p', { class: 'leise', text: 'Geht an: ' + schreibmodelle.map((p) => p.name).join(', ') }))));
    $('#p-auftragsvorschau').open = true;
  } catch (err) { pComposerZusammenfassung(err.message); }
}

async function pComposerSenden(fortsetzen = false) {
  if (P.sendenLaeuft || (P.sendung && fortsetzen !== true)) return;
  if (!P.entwurf.schreibmodelle.length || P.entwurf.schreibmodelle.some((id) =>
    !P.optionen?.schreibmodelle.some((p) => p.id === id && p.prompts_verfuegbar))) {
    pComposerZusammenfassung(P.optionen ? '' : 'Modelle und Prompt-Typen werden geladen …');
    return;
  }
  P.sendenLaeuft = true;
  let gesendet = false;
  try {
    if (!P.sendung) {
      const daten = pComposerDaten();
      if (!daten.text.trim()) throw Error('Bitte einen Rohprompt eingeben.');
      if (!daten.ziele.length) throw Error('Bitte mindestens ein Zielmodell wählen.');
      P.sendung = { daten: { ...daten, anfrage_id: crypto.randomUUID() } };
    }
    pComposerZusammenfassung('Auftrag wird geprüft …');
    if (!P.sendung.daten.gesendet_staende) {
      const v = await api('/api/prompt', { ...P.sendung.daten, aktion: 'composer_vorschau' });
      P.sendung.daten.gesendet_staende = v.gesendet_staende;
    }
    P.sendung.abgelehnt = false;
    gesendet = true;
    const status = await api('/api/prompt', { ...P.sendung.daten, aktion: 'composer_senden' });
    await pSendungUebernommen(status);
  } catch (err) {
    if (gesendet && err.status >= 400 && err.status < 600) {
      P.sendung.abgelehnt = true; P.sendung.unklar = false;
      pComposerZusammenfassung(err.message); pSendungsaktionenZeichnen();
    } else if (gesendet) pSendungUnklar(err.message);
    else { P.sendung = null; pComposerZusammenfassung(err.message); }
  } finally {
    P.sendenLaeuft = false;
    pComposerZusammenfassung($('#p-composer-status').textContent);
  }
}

function pSendungsaktionenZeichnen() {
  $('#p-sendungsaktionen').replaceChildren(...(P.sendung.abgelehnt ? [h('p', { class: 'leise',
    text: 'Bereits angelegte Läufe der alten Sendung stehen unter ‚Schärfen‘ des Eintrags.' })] : []),
  pKnopf('Einreihung fortsetzen', () => pComposerSenden(true)),
  ...(P.sendung.abgelehnt ? [pKnopf('Als neue Sendung senden', () => {
    if (P.sendenLaeuft) return;
    P.sendung = null; $('#p-sendungsaktionen').replaceChildren(); return pComposerSenden();
  })] : []));
}

function pSendungUnklar(grund = '') {
  P.sendung.unklar = true;
  pComposerZusammenfassung('Die Bestätigung fehlt. Prüfe den Auftragsstatus, bevor du erneut sendest.');
  $('#p-sendungsaktionen').replaceChildren(h('p', { class: 'leise', text: grund }), pKnopf('Status prüfen', pSendungStatus));
}

async function pSendungStatus() {
  if (!P.sendung || P.sendenLaeuft) return;
  try {
    const s = await api('/api/prompt', { aktion: 'composer_status', anfrage_id: P.sendung.daten.anfrage_id });
    if (s.gefunden && s.vollstaendig) await pSendungUebernommen(s);
    else if (s.gefunden) pSendungsaktionenZeichnen();
    else { P.sendung = null; $('#p-sendungsaktionen').replaceChildren(); pComposerZusammenfassung('Die Sendung wurde nicht gefunden. Du kannst erneut senden.'); }
  } catch (err) { pSendungUnklar(err.message); }
}

async function pSendungUebernommen(s) {
  P.letzteGruppe = s.auftragsgruppe;
  const alt = P.sendung.daten;
  if (P.entwurf.text === alt.text && P.entwurf.hinweise === alt.hinweise) {
    P.entwurf.text = ''; P.entwurf.titel = ''; P.entwurf.hinweise = ''; P.entwurf.basis = null;
    P.entwurf.materialien = []; P.entwurf.kontexte = [];
    P.entwurf.ablage = 'ordner'; delete P.entwurf.schaerfen_aktion;
    $('#p-ablage').value = 'ordner'; $('#p-sammlungsbasis').hidden = true;
    for (const id of ['p-rohprompt', 'p-composer-titel', 'p-composer-hinweise']) $('#' + id).value = '';
    $('#p-rohprompt').readOnly = false; $('#p-basis-hinweis').hidden = true;
  }
  P.sendung = null; $('#p-sendungsaktionen').replaceChildren(); pComposerZusammenfassung('Schärfen wartet.');
  pChipsZeichnen();
  P.gewaehlt = s.id; pAnsichtZeigen('bibliothek'); $('#p-inhalt').tabIndex = -1; $('#p-inhalt').focus();
  await pWaehlen(s.id); P.ladenNoetig = true;
}

function pComposerBasis(e, name = null) {
  pComposerZeigen();
  const f = e.fassungen.find((x) => x.name === (name || e.bevorzugt)) || e.fassungen[0];
  P.entwurf.text = f.text; P.entwurf.basis = { id: e.id, fassung: f.name, stand: f.stand };
  P.entwurf.ablage = e.herkunft; P.entwurf.titel = e.titel;
  delete P.entwurf.schaerfen_aktion;
  $('#p-rohprompt').value = f.text; $('#p-rohprompt').readOnly = true;
  $('#p-composer-titel').value = e.titel; $('#p-ablage').value = e.herkunft;
  $('#p-sammlungsbasis').hidden = e.herkunft !== 'sammlung'; $('#p-sammlungsbasis').value = e.id;
  $('#p-basis-hinweis').textContent = `${e.titel} · ${f.name}. Änderungen am Auftrag trägst du unter Hinweise ein.`;
  $('#p-basis-hinweis').hidden = false;
  pAnsichtZeigen('neu'); $('#p-composer-hinweise').focus();
}

async function pComposerNochmal(e, b) {
  if (!b.auftragsgruppe || !b.zielschluessel) return pSchaerfendialog(e, b.fassung, b.aktion);
  pComposerZeigen();
  if (!P.optionen) await pOptionenLaden();
  const profile = P.optionen.schreibmodelle;
  const p = profile.find((p) => p.id === b.schreibmodell_id) || profile.find((p) => p.name === b.auswerter
    && p.anbieter === b.anbieter && p.modell === b.modell && (p.stufe ?? null) === (b.denkstufe ?? null));
  pComposerAusBeleg(e, b, b.fassung, p ? [p.id] : []);
  P.entwurf.text = b.original;
  P.entwurf.basis.stand = b.fassung_stand;
  $('#p-rohprompt').value = b.original;
  P.entwurf.hinweise = b.eingaben.hinweise;
  P.entwurf.schaerfen_aktion = b.eingaben.aktion;
  $('#p-composer-hinweise').value = b.eingaben.hinweise;
  P.schreibmodellFehlt = !p;
  pComposerZusammenfassung();
}

async function pComposerVerfeinern(e, b) {
  pComposerZeigen();
  if (!P.optionen) await pOptionenLaden();
  pComposerAusBeleg(e, b, b.ergebnis_fassung, pSchreibauswahlLaden());
}

function pComposerAusBeleg(e, b, name, schreibmodelle) {
  P.entwurf = pEntwurfNeu();
  P.zielMerker = new Map(); delete P.textziele;
  pComposerBasis(e, name);
  const eingaben = b.eingaben;
  P.entwurf.prompt_typ = eingaben.typ?.id || e.prompt_typ || 'auto';
  P.entwurf.modus = eingaben.modus?.id || e.modus || 'prompt';
  P.entwurf.realismus = !!eingaben.realismus;
  P.entwurf.schaerfen_aktion = 'Schärfen';
  P.entwurf.materialien = JSON.parse(JSON.stringify(eingaben.materialien || []));
  if (eingaben.material) P.entwurf.materialien.push({ art: 'antwort', eintrag: eingaben.material.eintrag, beleg: eingaben.material.beleg });
  P.entwurf.kontexte = (eingaben.kontexte || []).map((k) => ({ id: k.id, stand: k.stand }));
  const [zielprofil, eintrag, variante] = (b.zielschluessel || b.zielprofil_id || eingaben.zielmodell.anbieter).split(':');
  P.entwurf.ziele = [{ zielprofil, ...(eingaben.zielmodell.anbieter === 'lokal' ? { eintrag } : {}),
    ...(!['bild', 'video'].includes(zielprofil) ? { testprofil: b.testprofil_id || null } : {}), ...(variante ? { variante } : {}) }];
  pSchreibmodelleSetzen(schreibmodelle);
  $('#p-composer-hinweise').value = '';
  $('#p-typname').textContent = 'Prompt-Typ: ' + (eingaben.typ?.name || P.optionen.typen.find((t) => t.id === P.entwurf.prompt_typ)?.name);
  for (const el of $('#p-typen').querySelectorAll('input')) el.checked = el.value === P.entwurf.prompt_typ;
  for (const el of $('#p-composer').querySelectorAll('input[name="p-modus"]')) el.checked = el.value === P.entwurf.modus;
  pSchreibmodelleZeichnen(); pZieleZeichnen(); pChipsZeichnen(); pComposerZusammenfassung();
  $('#p-composer').querySelector('.p-weitere').open = true;
  $('#p-composer-hinweise').focus();
}

async function pGruppeZeichnen(box, e, gruppe) {
  box.append(h('h3', { text: 'Zuletzt gestarteter Auftrag' }));
  const belege = [...gruppe.ergebnisse].sort((a, b) => {
    const links = Number.isInteger(a.lauf_nr), rechts = Number.isInteger(b.lauf_nr);
    if (links && rechts) return a.lauf_nr - b.lauf_nr;
    return links ? -1 : rechts ? 1 : 0;
  });
  const ziele = new Map();
  for (const b of belege) {
    const schluessel = b.zielschluessel || b.zielmodell;
    if (!ziele.has(schluessel)) ziele.set(schluessel, []);
    ziele.get(schluessel).push(b);
  }
  for (const [schluessel, ergebnisse] of ziele) {
    const vergleich = ergebnisse.length > 1;
    const abschnitt = h('section', {}, h('h4', { text: ergebnisse[0].zielmodell }));
    const original = h('pre', { class: 'p-text' });
    if (vergleich) abschnitt.append(h('details', {
      'data-p-ansicht': JSON.stringify(['gruppe', gruppe.id, schluessel, 'original']),
    }, h('summary', { text: 'Original anzeigen' }), original));
    const spalten = h('div', { class: vergleich ? 'p-ergebnisspalten' : '' });
    abschnitt.append(spalten); box.append(abschnitt);
    for (const b of ergebnisse) {
      const inhalt = h('div');
      const a = pBelegAuftrag(e, b, 'schaerfen');
      const laufanzeige = pLaufanzeige(b, a);
      const aktionen = h('div', { class: 'p-knoepfe' });
      if (a && ['wartet', 'laeuft', 'fehler', 'abgebrochen'].includes(a.zustand)) {
        const aktiv = ['wartet', 'laeuft'].includes(a.zustand);
        if (aktiv || !b.fehler) aktionen.append(pKnopf(aktiv ? 'Abbrechen' : 'Wiederholen', async () => {
          await api('/api/fassung', { id: a.id, aktion: aktiv ? 'abbrechen' : 'wiederholen' });
          await pLaden();
        }));
      } else if (!a && b.verwaist && !b.fehler && ['fehler', 'abgebrochen'].includes(b.zustand)) {
        aktionen.append(pKnopf('Wiederholen', () => pAktion({ aktion: 'wiederholen_beleg', id: e.id,
          datei: b.datei, art_ordner: 'schaerfen' })));
      }
      spalten.append(h('article', { class: 'p-fassung' }, h('h5', { text: b.auswerter }),
        laufanzeige || h('p', { class: 'leise', text: [ZUSTAND[b.zustand] || b.zustand,
          b.dauer_s != null ? dauer(Number(b.dauer_s)) : '', b.tokens != null ? `${b.tokens} Token` : '',
          b.ergebnis, b.meldung, b.fehler].filter(Boolean).join(' · ') }),
        pKnopf('Schärfen-Beleg öffnen', () => pOeffnen(e, 'schaerfen', b.datei)), aktionen, inhalt));
      if (b.antwort_vorhanden || (vergleich && b === ergebnisse[0])) {
        try {
          const antwort = await pBeleg(e, b, 'schaerfen');
          if (vergleich && b === ergebnisse[0]) original.textContent = antwort.original;
          if (b.antwort_vorhanden) pSchaerfenErgebnis(inhalt, antwort, e, b, vergleich);
        } catch (err) { inhalt.textContent = err.message; }
      }
    }
  }
}

function pZuletztZeichnen() {
  if (!P.ui) return;
  $('#p-zuletzt').replaceChildren(h('h3', { class: 'abschnitt', text: 'Zuletzt' }), ...P.zuletzt
    .map((id) => P.eintraege.find((e) => e.id === id)).filter(Boolean).map((e) => {
      const b = pKnopf(e.titel, () => pWaehlen(e.id));
      b.replaceChildren(h('span', { class: 'p-zuletzt-titel', text: e.titel }));
      b.title = e.titel;
      return b;
    }));
}

function pKatalogTyp(e) {
  if (e.prompt_typ !== 'auto') return e.prompt_typ;
  const letzter = [...(e.schaerfen || [])].filter((b) => b.ergebnis_gueltig)
    .sort((a, b) => (b.erstellt || '').localeCompare(a.erstellt || '') || (b.datei || '').localeCompare(a.datei || '', 'de', { numeric: true }))[0];
  const typ = letzter?.prompt_typ_erkannt;
  return typ !== 'auto' && P.optionen?.typen.some((t) => t.id === typ) ? typ : null;
}

function pEntdeckenZeichnen() {
  if (!P.ui) return;
  const lesbar = P.eintraege.filter((e) => !e.fehler && e.fassungen.length);
  const abschnitte = [...new Map(lesbar.filter((e) => e.abschnitt).sort((a, b) => a.abschnitt_reihenfolge - b.abschnitt_reihenfolge)
    .map((e) => [e.abschnitt, e.abschnitt])).values()];
  const kategorien = ['Alle', 'Eigene Prompts', ...abschnitte];
  if (!kategorien.includes(P.kategorie)) P.kategorie = 'Alle';
  $('#p-kategorien').replaceChildren(...kategorien.map((name) => {
    const b = pKnopf(name, () => {
      P.kategorie = name; pEntdeckenZeichnen();
      [...$('#p-kategorien').querySelectorAll('button')].find((x) => x.textContent === name)?.focus();
    });
    b.setAttribute('aria-pressed', String(P.kategorie === name)); return b;
  }));
  if (P.letztesLaden == null && !P.eintraegeGezeigt) {
    $('#p-karten').replaceChildren(h('p', { class: 'leise', text: P.ladenFehler
      ? 'Liste nicht geladen – neuer Versuch läuft.' : 'Prompts werden geladen …' }));
    return;
  }
  const suche = $('#p-katalog-suche').value.toLocaleLowerCase('de');
  const gruppen = new Map();
  for (const e of lesbar) {
    if (P.kategorie === 'Eigene Prompts' && e.herkunft !== 'ordner') continue;
    if (!['Alle', 'Eigene Prompts'].includes(P.kategorie) && e.abschnitt !== P.kategorie) continue;
    if (![e.titel, e.schlagworte, e.quelle, ...e.fassungen.map((f) => f.text)].join('\n').toLocaleLowerCase('de').includes(suche)) continue;
    const typId = pKatalogTyp(e);
    const typ = P.optionen?.typen.find((t) => t.id === typId)?.name;
    const name = e.herkunft === 'sammlung' ? e.abschnitt || 'Sammlung' :
      typId && (e.prompt_typ_gespeichert || (e.prompt_typ && e.prompt_typ !== 'standard')) ? typ || typId : 'Weitere Prompts';
    if (!gruppen.has(name)) gruppen.set(name, []);
    gruppen.get(name).push(e);
  }
  $('#p-karten').replaceChildren(...[...gruppen].map(([name, liste]) => {
    liste.sort((a, b) => (a.reihenfolge || 0) - (b.reihenfolge || 0));
    const reihe = h('div', { class: 'p-kartenreihe', tabindex: '0', 'aria-label': name });
    for (const e of liste) reihe.append(h('button', { type: 'button', class: 'p-katalogkarte', onclick: () => pWaehlen(e.id) },
      h('strong', { text: e.titel }), h('span', { class: 'p-kurztext', text: e.kurztext || e.fassungen[0].text.split('\n').find((z) => z.trim())?.slice(0, 180) || '' }),
      h('small', { text: `${e.herkunft === 'sammlung' ? 'Sammlung' : 'Eigener Prompt'} · ${P.optionen?.typen.find((t) => t.id === pKatalogTyp(e))?.name || (e.prompt_typ === 'auto' ? 'Weitere Prompts' : 'Allgemein')}` }),
      pPfeil()));
    return h('section', { class: 'p-kataloggruppe' }, h('div', { class: 'p-entdecken-kopf' }, h('h3', { text: name }),
      h('div', { class: 'p-knoepfe' }, pKnopf('Vorherige Prompts aus ' + name, () => reihe.scrollBy({ left: -reihe.clientWidth, behavior: 'auto' })),
        pKnopf('Weitere Prompts aus ' + name, () => reihe.scrollBy({ left: reihe.clientWidth, behavior: 'auto' })))), reihe);
  }));
  if (!gruppen.size) $('#p-karten').append(h('p', { class: 'leise', text: suche ? 'Keine passenden Prompts.' : 'Noch keine eigenen Prompts. Schreibe deinen ersten Rohprompt.' }));
  const sammlung = lesbar.filter((e) => e.herkunft === 'sammlung');
  $('#p-sammlungsbasis').replaceChildren(h('option', { value: '', text: 'Sammlungseintrag wählen …' }),
    ...sammlung.map((e) => h('option', { value: e.id, text: e.titel })));
}

function pChipsZeichnen() {
  if (!P.ui) return;
  $('#p-chips').replaceChildren(...P.entwurf.materialien.map((m, i) => pKnopf(
    `${m.name || m.beleg} · ${m.zeichen ?? 0} Zeichen${m.gekuerzt ? ' · auf 30.000 Zeichen gekürzt' : ''} · Entfernen`,
    () => { P.entwurf.materialien.splice(i, 1); pChipsZeichnen(); })),
    ...P.entwurf.kontexte.map((k) => pKnopf(`${P.kontextNamen?.get(k.id) || k.id} · Kontext entfernen`, () => {
      P.entwurf.kontexte = P.entwurf.kontexte.filter((x) => x.id !== k.id); pChipsZeichnen();
    })));
  pComposerZusammenfassung();
}

async function pMaterialHinzufuegen(materialien) {
  const d = await api('/api/prompt', { aktion: 'material_pruefen', materialien: [...P.entwurf.materialien, ...materialien] });
  P.entwurf.materialien = d.materialien;
  pChipsZeichnen();
}

async function pMaterialBrowserHinzufuegen(dateien) {
  const grenze = P.optionen?.feld_max_zeichen || 400000;
  if (dateien.length + P.entwurf.materialien.length > 5) throw Error('Bitte höchstens fünf Materialien auswählen.');
  const materialien = [];
  for (const f of dateien) {
    if (!/\.(txt|md|markdown|json|csv|tsv|yaml|yml|log|html?|css|js|py|xml|rst|toml)$/i.test(f.name))
      throw Error('Bitte eine Textdatei auswählen. PDF, Office-Dateien, Bilder, Audio und Video sind hier nicht vorgesehen.');
    if (f.size > grenze * 4) throw Error('Die Textdatei überschreitet die Materialgrenze.');
    materialien.push({ art: 'text', name: f.name, wert: await f.text() });
  }
  await pMaterialHinzufuegen(materialien);
}

function pMaterialMenue() {
  const fehler = h('p', { class: 'warnung', 'aria-live': 'polite' });
  const browser = h('input', { type: 'file', multiple: true, accept: '.txt,.md,.markdown,.json,.csv,.tsv,.yaml,.yml,.log,.html,.css,.js,.py,.xml,.rst,.toml', 'aria-label': 'Textdatei auswählen …' });
  browser.addEventListener('change', async () => {
    try { await pMaterialBrowserHinzufuegen([...browser.files]); d.close(); }
    catch (err) { fehler.textContent = err.message; }
  });
  const antworten = P.eintraege.flatMap((e) => (e.tests || []).filter((b) => b.antwort_vorhanden && !b.fehler).map((b) => ({ eintrag: e.id, beleg: b.datei, name: `${e.titel} · ${b.erstellt || ''} · ${b.auswerter}` })));
  const antwort = h('select', { 'aria-label': 'Vorhandene Antwort auswählen …' }, h('option', { value: '', text: 'Vorhandene Antwort auswählen …' }),
    ...antworten.map((a, i) => h('option', { value: String(i), text: a.name })));
  const pfad = h('input', { type: 'text', 'aria-label': 'Material aus Dateipfad', placeholder: 'Dateipfad einer Textdatei' });
  const ausDatei = async (waehlen) => {
    try {
      const m = await api('/api/prompt', { aktion: waehlen ? 'material_datei_waehlen' : 'material_datei_lesen', pfad: pfad.value });
      if (!m.abgebrochen) { await pMaterialHinzufuegen([m]); d.close(); }
    } catch (err) { fehler.textContent = err.message; }
  };
  const d = dialogOeffnen('Textmaterial anhängen', [h('p', { class: 'leise', text: 'Bis zu fünf Textmaterialien. Neue Anhänge werden vollständig übernommen oder abgelehnt.' }),
    browser, pKnopf('Textdatei am Rechner wählen …', () => ausDatei(true)), pfad, pKnopf('Pfad lesen', () => ausDatei(false)),
    antwort, pKnopf('Antwort anhängen', async () => {
      try {
        const a = antworten[Number(antwort.value)];
        if (antwort.value === '' || !a) throw Error('Bitte eine vorhandene Antwort wählen.');
        await pMaterialHinzufuegen([{ art: 'antwort', eintrag: a.eintrag, beleg: a.beleg }]); d.close();
      } catch (err) { fehler.textContent = err.message; }
    }), fehler], [pKnopf('Fertig', () => d.close())], true);
}

window.promptsMaterialAblegen = async (e) => {
  try {
    if ([...(e.dataTransfer.items || [])].some((i) => i.webkitGetAsEntry?.()?.isDirectory)) throw Error('Bitte einzelne Textdateien auswählen.');
    await pMaterialBrowserHinzufuegen([...e.dataTransfer.files]);
    pAnsichtZeigen('neu');
  } catch (err) { pFehler(err); }
};

async function pKontexteZeigen(auswahl = false) {
  const d = await api('/api/prompt-kontexte');
  P.kontextNamen = new Map(d.kontexte.map((k) => [k.id, k.titel]));
  const liste = h('div', { class: 'p-kontextliste' });
  for (const k of d.kontexte) {
    const cb = h('input', { type: 'checkbox', disabled: !!k.fehler });
    cb.checked = P.entwurf.kontexte.some((x) => x.id === k.id);
    cb.addEventListener('change', () => {
      P.entwurf.kontexte = P.entwurf.kontexte.filter((x) => x.id !== k.id);
      if (cb.checked) P.entwurf.kontexte.push({ id: k.id, stand: k.stand });
      pChipsZeichnen();
    });
    liste.append(h('article', { class: 'p-fassung' }, h('label', { class: 'wahl' }, cb, k.titel),
      h('p', { class: 'leise', text: k.fehler || `${k.zeichen} Zeichen` }),
      ...(!k.fehler ? [pKnopf('Bearbeiten …', () => pKontextDialog(k, auswahl))] : [])));
  }
  if (!d.kontexte.length) liste.append(h('p', { class: 'leise', text: 'Noch keine Kontextbausteine.' }));
  const inhalt = [h('p', { class: 'leise', text: 'Wähle Projekt- und Sachkontext bewusst aus. Ausgewählte Bausteine werden mitgesendet.' }),
    pKnopf('Kontextbaustein anlegen …', () => pKontextDialog(null, auswahl)), liste];
  if (auswahl) {
    const dialog = dialogOeffnen('Kontext auswählen', inhalt, [pKnopf('Fertig', () => dialog.close())], true);
  } else { $('#p-kontexte').replaceChildren(h('h2', { text: 'Kontextbausteine' }), ...inhalt); pAnsichtZeigen('kontexte'); }
}

async function pKontextDialog(meta, auswahl) {
  const k = meta ? await api('/api/prompt', { aktion: 'kontext_lesen', id: meta.id }) : { titel: '', wert: '' };
  const titel = h('input', { type: 'text', 'aria-label': 'Titel des Kontextbausteins' }); titel.value = k.titel;
  const text = h('textarea', { rows: '12', maxlength: '20000', 'aria-label': 'Kontexttext' }); text.value = k.wert;
  const fehler = h('p', { class: 'warnung', 'aria-live': 'polite' });
  const d = dialogOeffnen(meta ? 'Kontextbaustein bearbeiten' : 'Kontextbaustein anlegen', [
    pFeld('p-kontext-titel', 'Titel', titel), pFeld('p-kontext-text', 'Projekt- und Sachkontext', text), fehler],
  [pKnopf('Abbrechen', () => d.close()), pKnopf('Speichern', async () => {
    try {
      const neu = await api('/api/prompt', { aktion: meta ? 'kontext_speichern' : 'kontext_neu',
        id: k.id, stand: k.stand, titel: titel.value, wert: text.value });
      P.entwurf.kontexte = P.entwurf.kontexte.map((x) => x.id === neu.id ? { id: neu.id, stand: neu.stand } : x);
      d.close(); await pKontexteZeigen(auswahl); pChipsZeichnen();
    } catch (err) { fehler.textContent = err.message; }
  })], true);
  titel.focus();
}
