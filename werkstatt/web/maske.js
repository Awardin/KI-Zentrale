'use strict';

// Studio, Stelle verbessern: die Stelle markieren, die neu entstehen soll. Pinsel, Radierer, Zoom, Verschieben,
// Rückgängig. Die Markierung hat die volle Bildgröße und geht als Lauflängen-Kodierung an den Dienst: zeilenweise
// über alle Pixel, abwechselnd frei und markiert, beginnend mit frei.

const MK_BILDER = new Map();

function mkBild(url) {
  if (!MK_BILDER.has(url)) {
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    const fertig = img.decode().then(() => img);
    fertig.catch(() => MK_BILDER.delete(url));
    MK_BILDER.set(url, fertig);
    if (MK_BILDER.size > 12) MK_BILDER.delete(MK_BILDER.keys().next().value);
  }
  return MK_BILDER.get(url);
}

// Die Markierung erscheint in der Farbe von Bild & Video.
function mkFarbe() {
  const wert = getComputedStyle(document.documentElement).getPropertyValue('--studio').trim();
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(wert);
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [177, 64, 124];
}

// Markierung in eine Leinwand ihrer Größe zeichnen (ersetzt den Inhalt).
function maskeMalen(ctx, m, [r, g, b]) {
  const bild = ctx.createImageData(m.breite, m.hoehe);
  const d = bild.data;
  let pos = 0;
  m.rle.forEach((n, i) => {
    if (i % 2) {
      for (let p = pos * 4, ende = (pos + n) * 4; p < ende; p += 4) {
        d[p] = r; d[p + 1] = g; d[p + 2] = b; d[p + 3] = 255;
      }
    }
    pos += n;
  });
  ctx.putImageData(bild, 0, 0);
}

// Leinwand -> Markierung. Kanten mit halber Deckkraft (Kantenglättung) zählen ab 50 % als markiert.
function maskeLesen(ctx, breite, hoehe) {
  const d = ctx.getImageData(0, 0, breite, hoehe).data;
  const rle = [];
  let wert = false;
  let n = 0;
  let markiert = 0;
  for (let i = 3; i < d.length; i += 4) {
    const an = d[i] >= 128;
    if (an !== wert) { rle.push(n); wert = an; n = 0; }
    n += 1;
    if (an) markiert += 1;
  }
  rle.push(n);
  return { breite, hoehe, rle, anteil: markiert / (breite * hoehe) };
}

function maskeAnteil(m) {
  let markiert = 0;
  for (let i = 1; i < m.rle.length; i += 2) markiert += m.rle[i];
  return markiert / (m.breite * m.hoehe);
}

function prozentText(anteil) {
  const p = anteil * 100;
  if (p > 0 && p < 0.1) return 'unter 0,1 %';
  return `${p < 10 ? p.toLocaleString('de-DE', { maximumFractionDigits: 1 }) : Math.round(p)} %`;
}

// Kleines Vorschaubild mit Markierung (für das Formular).
async function maskeVorschau(leinwand, url, m, hoehe = 220) {
  const img = await mkBild(url);
  const W = img.naturalWidth;
  const H = img.naturalHeight;
  const platz = leinwand.parentElement?.clientWidth || 320;
  const s = Math.min(platz / W, hoehe / H, 1);
  const dpr = window.devicePixelRatio || 1;
  leinwand.width = Math.max(1, Math.round(W * s * dpr));
  leinwand.height = Math.max(1, Math.round(H * s * dpr));
  leinwand.style.width = `${Math.round(W * s)}px`;
  leinwand.style.height = `${Math.round(H * s)}px`;
  const ctx = leinwand.getContext('2d');
  ctx.drawImage(img, 0, 0, leinwand.width, leinwand.height);
  if (m && m.breite === W && m.hoehe === H) {
    const voll = document.createElement('canvas');
    voll.width = W;
    voll.height = H;
    maskeMalen(voll.getContext('2d'), m, mkFarbe());
    ctx.globalAlpha = 0.6;
    ctx.drawImage(voll, 0, 0, leinwand.width, leinwand.height);
    ctx.globalAlpha = 1;
  }
  return { breite: W, hoehe: H };
}

// Das Markier-Fenster -> Promise mit {breite, hoehe, rle, anteil} oder null (abgebrochen).
async function maskeBearbeiten({ url, maske = null, titel = 'Stelle markieren' }) {
  const img = await mkBild(url);
  const W = img.naturalWidth;
  const H = img.naturalHeight;
  const farbe = mkFarbe();
  const css = `rgb(${farbe.join(', ')})`;
  const basis = maske && maske.breite === W && maske.hoehe === H ? maske : null;
  const lang = Math.max(W, H);
  const minPx = 2;
  const maxPx = Math.max(8, Math.round(lang * 0.35));
  const ausRegler = (v) => Math.exp(Math.log(minPx) + ((Math.log(maxPx) - Math.log(minPx)) * v) / 100);
  const zuRegler = (px) => Math.round((100 * (Math.log(px) - Math.log(minPx))) / (Math.log(maxPx) - Math.log(minPx)));
  let gemerkt = 0.05;
  try { gemerkt = +localStorage.getItem('werkstatt.maske.pinsel') || 0.05; } catch { /* egal */ }
  const S = { werkzeug: 'pinsel', groesse: 0, z: 1, z0: 1, tx: 0, ty: 0, ops: [], pos: 0, strich: null,
    schieben: null, leertaste: false, letzte: null };

  const d = $('#dialog');
  d.className = 'gross mk';
  const bild = h('img', { src: url, alt: '', draggable: 'false' });
  const leinwand = h('canvas', { class: 'mk-maske' });
  leinwand.width = W;
  leinwand.height = H;
  const ctx = leinwand.getContext('2d', { willReadFrequently: true });
  const buehne = h('div', { class: 'mk-buehne' }, bild, leinwand);
  buehne.style.width = `${W}px`;
  buehne.style.height = `${H}px`;
  const pinsel = h('div', { class: 'mk-pinsel', hidden: true });
  const flaeche = h('div', { class: 'mk-flaeche', tabindex: '0', 'aria-label': 'Bild zum Markieren' }, buehne, pinsel);
  const knopf = (text, titel2) => h('button', { type: 'button', class: 'knopf knopf-klein', title: titel2 }, text);
  const knopfPinsel = h('button', { type: 'button', title: 'Malen (B)' }, 'Pinsel');
  const knopfRadierer = h('button', { type: 'button', title: 'Wegradieren (E)' }, 'Radierer');
  const regler = h('input', { type: 'range', min: '0', max: '100', step: '1', 'aria-label': 'Pinselgröße' });
  const groesseText = h('output', { class: 'mk-wert' });
  const zurueck = knopf('Rückgängig', 'Rückgängig (Strg+Z)');
  const vor = knopf('Wiederholen', 'Wiederholen (Strg+Y)');
  const leeren = knopf('Alles löschen', 'Die ganze Markierung entfernen');
  const umkehren = knopf('Umkehren', 'Markiertes und Freies tauschen');
  const einpassen = knopf('Einpassen', 'Ganzes Bild zeigen (0)');
  const zoomText = h('output', { class: 'mk-wert' });
  const anteilText = h('span', { class: 'mk-anteil' });
  const fehler = h('span', { class: 'st-fehler' });
  const abbrechen = h('button', { class: 'knopf', type: 'button' }, 'Abbrechen');
  const uebernehmen = h('button', { class: 'knopf knopf-haupt', type: 'button' }, 'Übernehmen');

  d.replaceChildren(
    h('div', { class: 'mk-kopf' },
      h('h2', { id: 'dialog-titel', text: titel }),
      h('p', { class: 'leise', text: 'Male über die Stelle, die neu entstehen soll, lieber etwas großzügig. Alles andere bleibt, wie es ist.' })),
    h('div', { class: 'mk-leiste' },
      h('div', { class: 'umschalter', role: 'group', 'aria-label': 'Werkzeug' }, knopfPinsel, knopfRadierer),
      h('label', { class: 'mk-regler' }, 'Größe', regler, groesseText),
      zurueck, vor, leeren, umkehren, einpassen, zoomText),
    flaeche,
    h('div', { class: 'mk-fuss' },
      h('p', { class: 'leise mk-tipp', text: 'Mausrad: zoomen · rechte Maustaste oder Leertaste: verschieben · [ ]: Pinselgröße · B/E: Pinsel/Radierer' }),
      anteilText, fehler, abbrechen, uebernehmen));

  // ---------------------------------------------------------------- Ansicht

  const setzen = () => {
    buehne.style.transform = `translate(${S.tx}px, ${S.ty}px) scale(${S.z})`;
    buehne.classList.toggle('pixel', S.z >= 3);
    zoomText.textContent = `${Math.round(S.z * 100)} %`;
    pinselZeigen(S.letzte);
  };
  const einpassenJetzt = () => {
    const r = flaeche.getBoundingClientRect();
    S.z0 = Math.min(r.width / W, r.height / H) || 1;
    S.z = S.z0;
    S.tx = (r.width - W * S.z) / 2;
    S.ty = (r.height - H * S.z) / 2;
    setzen();
  };
  const zoomen = (neu, cx, cy) => {
    const r = flaeche.getBoundingClientRect();
    const z = Math.min(Math.max(neu, S.z0 * 0.5), Math.max(S.z0 * 16, 8));
    const px = (cx ?? r.left + r.width / 2) - r.left;
    const py = (cy ?? r.top + r.height / 2) - r.top;
    S.tx = px - (px - S.tx) * (z / S.z);
    S.ty = py - (py - S.ty) * (z / S.z);
    S.z = z;
    setzen();
  };
  const punkt = (ev) => {
    const r = flaeche.getBoundingClientRect();
    return [(ev.clientX - r.left - S.tx) / S.z, (ev.clientY - r.top - S.ty) / S.z];
  };
  function pinselZeigen(ev) {
    if (!ev) return;
    const r = flaeche.getBoundingClientRect();
    const g = S.groesse * S.z;
    pinsel.style.width = `${g}px`;
    pinsel.style.height = `${g}px`;
    pinsel.style.transform = `translate(${ev.clientX - r.left - g / 2}px, ${ev.clientY - r.top - g / 2}px)`;
    pinsel.classList.toggle('radierer', S.werkzeug === 'radierer');
    pinsel.hidden = !!S.schieben || S.leertaste;
  }

  // ---------------------------------------------------------------- Malen

  const strichTeil = (s, x0, y0, x1, y1) => {
    ctx.save();
    ctx.globalCompositeOperation = s.radieren ? 'destination-out' : 'source-over';
    ctx.strokeStyle = css;
    ctx.fillStyle = css;
    ctx.lineWidth = s.groesse;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    if (x0 === x1 && y0 === y1) {
      ctx.arc(x0, y0, s.groesse / 2, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
    }
    ctx.restore();
  };
  const strichGanz = (s) => {
    const p = s.punkte;
    strichTeil(s, p[0], p[1], p[0], p[1]);
    for (let i = 2; i < p.length; i += 2) strichTeil(s, p[i - 2], p[i - 1], p[i], p[i + 1]);
  };
  const umkehrenJetzt = () => {
    const daten = ctx.getImageData(0, 0, W, H);
    const px = daten.data;
    for (let i = 0; i < px.length; i += 4) {
      const an = px[i + 3] < 128;
      px[i] = farbe[0]; px[i + 1] = farbe[1]; px[i + 2] = farbe[2]; px[i + 3] = an ? 255 : 0;
    }
    ctx.putImageData(daten, 0, 0);
  };
  const neuZeichnen = () => {
    ctx.clearRect(0, 0, W, H);
    if (basis) maskeMalen(ctx, basis, farbe);
    for (const op of S.ops.slice(0, S.pos)) {
      if (op.typ === 'leeren') ctx.clearRect(0, 0, W, H);
      else if (op.typ === 'umkehren') umkehrenJetzt();
      else strichGanz(op);
    }
  };
  const stand = () => {
    zurueck.disabled = S.pos === 0;
    vor.disabled = S.pos >= S.ops.length;
    const px = ctx.getImageData(0, 0, W, H).data;
    let n = 0;
    for (let i = 3; i < px.length; i += 4) if (px[i] >= 128) n += 1;
    anteilText.textContent = n ? `${prozentText(n / (W * H))} des Bildes markiert` : 'Noch nichts markiert';
    uebernehmen.disabled = !n;
    fehler.textContent = '';
  };
  const merken = (op) => {
    S.ops = S.ops.slice(0, S.pos);
    S.ops.push(op);
    S.pos = S.ops.length;
    stand();
  };
  const rueckgaengig = () => { if (S.pos > 0) { S.pos -= 1; neuZeichnen(); stand(); } };
  const wiederholen = () => { if (S.pos < S.ops.length) { S.pos += 1; neuZeichnen(); stand(); } };
  const werkzeugWaehlen = (w) => {
    S.werkzeug = w;
    for (const [k, name] of [[knopfPinsel, 'pinsel'], [knopfRadierer, 'radierer']]) {
      k.classList.toggle('aktiv', w === name);
      k.setAttribute('aria-pressed', String(w === name));
    }
    pinselZeigen(S.letzte);
  };
  const groesseSetzen = (px) => {
    S.groesse = Math.min(maxPx, Math.max(minPx, Math.round(px)));
    regler.value = String(zuRegler(S.groesse));
    groesseText.textContent = `${S.groesse} px`;
    try { localStorage.setItem('werkstatt.maske.pinsel', String(S.groesse / lang)); } catch { /* egal */ }
    pinselZeigen(S.letzte);
  };

  // ---------------------------------------------------------------- Bedienung

  const tasten = new AbortController();
  const an = { signal: tasten.signal };
  knopfPinsel.addEventListener('click', () => werkzeugWaehlen('pinsel'));
  knopfRadierer.addEventListener('click', () => werkzeugWaehlen('radierer'));
  regler.addEventListener('input', () => groesseSetzen(ausRegler(+regler.value)));
  zurueck.addEventListener('click', rueckgaengig);
  vor.addEventListener('click', wiederholen);
  leeren.addEventListener('click', () => { ctx.clearRect(0, 0, W, H); merken({ typ: 'leeren' }); });
  umkehren.addEventListener('click', () => { umkehrenJetzt(); merken({ typ: 'umkehren' }); });
  einpassen.addEventListener('click', einpassenJetzt);

  flaeche.addEventListener('contextmenu', (ev) => ev.preventDefault());
  flaeche.addEventListener('pointerdown', (ev) => {
    if (S.strich || S.schieben) return;
    flaeche.focus({ preventScroll: true });
    flaeche.setPointerCapture(ev.pointerId);
    S.letzte = ev;
    if (ev.button === 1 || ev.button === 2 || (ev.button === 0 && S.leertaste)) {
      ev.preventDefault();
      S.schieben = { x: ev.clientX, y: ev.clientY, tx: S.tx, ty: S.ty, id: ev.pointerId };
      flaeche.classList.add('schiebt');
      pinselZeigen(ev);
      return;
    }
    if (ev.button !== 0) return;
    const [x, y] = punkt(ev);
    S.strich = { typ: 'strich', radieren: S.werkzeug === 'radierer', groesse: S.groesse, punkte: [x, y], id: ev.pointerId };
    strichTeil(S.strich, x, y, x, y);
  });
  flaeche.addEventListener('pointermove', (ev) => {
    S.letzte = ev;
    if (S.schieben && ev.pointerId === S.schieben.id) {
      S.tx = S.schieben.tx + ev.clientX - S.schieben.x;
      S.ty = S.schieben.ty + ev.clientY - S.schieben.y;
      setzen();
    } else if (S.strich && ev.pointerId === S.strich.id) {
      const s = S.strich;
      const genau = ev.getCoalescedEvents?.();
      for (const e of genau?.length ? genau : [ev]) {
        const [x, y] = punkt(e);
        const p = s.punkte;
        const lx = p[p.length - 2];
        const ly = p[p.length - 1];
        if (Math.hypot(x - lx, y - ly) >= Math.max(0.75, s.groesse / 10)) {
          p.push(x, y);
          strichTeil(s, lx, ly, x, y);
        }
      }
    }
    pinselZeigen(ev);
  });
  const loslassen = (ev) => {
    if (S.schieben && ev.pointerId === S.schieben.id) {
      S.schieben = null;
      flaeche.classList.remove('schiebt');
    }
    if (S.strich && ev.pointerId === S.strich.id) {
      const s = S.strich;
      S.strich = null;
      delete s.id;
      merken(s);
    }
    pinselZeigen(ev);
  };
  flaeche.addEventListener('pointerup', loslassen);
  flaeche.addEventListener('pointercancel', loslassen);
  flaeche.addEventListener('pointerleave', () => { if (!S.strich && !S.schieben) pinsel.hidden = true; });
  flaeche.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    zoomen(S.z * Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0015)), ev.clientX, ev.clientY);
  }, { passive: false });

  const kuerzel = {
    b: () => werkzeugWaehlen('pinsel'),
    e: () => werkzeugWaehlen('radierer'),
    '[': () => groesseSetzen(S.groesse * 0.8),
    ']': () => groesseSetzen(S.groesse * 1.25),
    0: einpassenJetzt,
    '+': () => zoomen(S.z * 1.25),
    '-': () => zoomen(S.z / 1.25),
    ' ': () => {
      if (S.leertaste) return;
      S.leertaste = true;
      flaeche.classList.add('schiebbar');
      pinsel.hidden = true;
    },
  };
  d.addEventListener('keydown', (ev) => {
    if (ev.target instanceof HTMLInputElement && ev.target.type !== 'range') return;
    const k = ev.key.toLowerCase();
    if (ev.ctrlKey || ev.metaKey) {
      if (k === 'z' || k === 'y') {
        ev.preventDefault();
        if (k === 'y' || ev.shiftKey) wiederholen(); else rueckgaengig();
      }
      return;
    }
    if (ev.altKey || !kuerzel[k]) return;
    ev.preventDefault();
    kuerzel[k]();
  }, an);
  d.addEventListener('keyup', (ev) => {
    if (ev.key === ' ') { S.leertaste = false; flaeche.classList.remove('schiebbar'); pinselZeigen(S.letzte); }
  }, an);
  window.addEventListener('resize', () => { if (Math.abs(S.z - S.z0) < 1e-9) einpassenJetzt(); }, an);

  return new Promise((fertig) => {
    let erledigt = false;
    const schliessen = (ergebnis) => {
      if (erledigt) return;
      erledigt = true;
      tasten.abort();
      fertig(ergebnis);
    };
    d.addEventListener('close', () => schliessen(null), an);
    abbrechen.addEventListener('click', () => d.close());
    uebernehmen.addEventListener('click', () => {
      const m = maskeLesen(ctx, W, H);
      if (!m.anteil) { fehler.textContent = 'Noch nichts markiert.'; return; }
      schliessen(m);
      d.close();
    });
    neuZeichnen();
    werkzeugWaehlen('pinsel');
    groesseSetzen(lang * gemerkt);
    stand();
    if (!d.open) d.showModal();
    requestAnimationFrame(() => { einpassenJetzt(); flaeche.focus({ preventScroll: true }); });
  });
}
