'use strict';

/*
 * Atelier – Ebenen-Editor (Scheibe 2, ohne KI-Aktionen).
 * Leinwand: Fabric.js 6.4.3 (lokal, MIT). Projekte liegen beim Atelier-Dienst.
 */
(function () {
  const FIBO_AUS = 'aus – in der Modellzentrale starten';
  const CUSTOM = ['atelierArt', 'atelierName', 'quelle', 'atelierGesperrt'];
  const FALLBACK_FORMATE = [
    {id: 'youtube', name: 'YouTube-Thumbnail', breite: 1280, hoehe: 720},
    {id: 'instagram', name: 'Instagram', breite: 1080, hoehe: 1080},
    {id: 'story', name: 'Story', breite: 1080, hoehe: 1920},
    {id: 'flyer_a5', name: 'Flyer A5 hoch', breite: 1748, hoehe: 2480},
    {id: 'flyer_a4', name: 'Flyer A4 hoch', breite: 2480, hoehe: 3508},
    {id: 'eigenes', name: 'Eigenes', breite: 1280, hoehe: 720, eigen: true}
  ];
  const FALLBACK_SCHRIFTEN = ['Arial Black', 'Impact', 'Bahnschrift', 'Segoe UI', 'Georgia',
    'Arial', 'Verdana', 'Trebuchet MS', 'Times New Roman', 'Courier New'];

  const Z = {
    cfg: null,
    formate: [],
    schriften: [],
    maxSeite: 4096,
    maxHochladenMb: 40,
    projekte: [],
    projekt: null,
    format: null,
    canvas: null,
    zoom: 1,
    zoomEinpassen: true,
    verlauf: [],
    zeiger: -1,
    verlaufTimer: null,
    speicherTimer: null,
    schmutzig: false,
    fassung: 0,
    stumm: false,
    laden: false,
    dragObjekt: null,
    fiboBereit: false,
    exportLaeuft: false
  };

  const el = {};

  function $(id) {
    return document.getElementById(id);
  }

  function alle(wahl) {
    return Array.from(document.querySelectorAll(wahl));
  }

  function setzeText(knoten, text) {
    if (knoten) knoten.textContent = text;
  }

  function alsZahl(wert, ersatz) {
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? zahl : ersatz;
  }

  function begrenze(zahl, min, max) {
    return Math.min(max, Math.max(min, zahl));
  }

  function farbeFuerInput(wert, ersatz) {
    const text = typeof wert === 'string' ? wert : '';
    if (/^#[0-9a-f]{6}$/i.test(text)) return text;
    if (/^#[0-9a-f]{3}$/i.test(text)) {
      return '#' + text[1] + text[1] + text[2] + text[2] + text[3] + text[3];
    }
    return ersatz;
  }

  function farbeFuerCanvas(wert) {
    const text = typeof wert === 'string' ? wert : '';
    return /^#[0-9a-f]{3,8}$/i.test(text) ? text : '#ffffff';
  }

  function artVon(obj) {
    if (obj && obj.atelierArt) return obj.atelierArt;
    if (!obj) return 'form';
    if (obj.type === 'image') return 'bild';
    if (obj.type === 'textbox' || obj.type === 'text' || obj.type === 'i-text') return 'text';
    return 'form';
  }

  function nameVon(obj) {
    if (obj && obj.atelierName) return obj.atelierName;
    const art = artVon(obj);
    if (art === 'bild') return 'Bild';
    if (art === 'text') return 'Text';
    return obj && obj.type === 'circle' ? 'Kreis' : 'Rechteck';
  }

  function typName(obj) {
    const art = artVon(obj);
    if (art === 'bild') return 'Bild';
    if (art === 'text') return 'Text';
    return obj && obj.type === 'circle' ? 'Form · Kreis' : 'Form · Rechteck';
  }

  function istFibo(obj) {
    return !!(obj && obj.quelle && obj.quelle.art === 'fibo');
  }

  function fiboQuelle(quelle) {
    return quelle && quelle.art === 'fibo';
  }

  function uhrzeit(text) {
    try {
      const datum = new Date(text);
      if (Number.isNaN(datum.getTime())) return '';
      return datum.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'});
    } catch (fehler) {
      return '';
    }
  }

  function bildUrl(datei) {
    if (!Z.projekt) return '';
    return '/api/bild?projekt=' + encodeURIComponent(Z.projekt.name) +
      '&datei=' + encodeURIComponent(datei);
  }

  async function ruf(pfad, optionen) {
    const opt = optionen || {};
    const methode = opt.methode || 'GET';
    const kopf = {};
    let koerper;
    if (methode !== 'GET') {
      kopf['Content-Type'] = 'application/json';
      kopf['X-Atelier'] = '1';
      koerper = JSON.stringify(opt.koerper || {});
    }
    const antwort = await fetch(pfad, {method: methode, headers: kopf, body: koerper, cache: 'no-store'});
    const typ = antwort.headers.get('content-type') || '';
    let daten = null;
    if (typ.indexOf('application/json') >= 0) {
      daten = await antwort.json();
    } else {
      daten = await antwort.text();
    }
    if (!antwort.ok) {
      const fehler = daten && daten.fehler ? daten.fehler : 'Der Dienst antwortete mit ' + antwort.status + '.';
      throw new Error(fehler);
    }
    return daten;
  }

  function setzeStatus(text, art) {
    if (!el.status) return;
    el.status.textContent = text;
    el.status.classList.remove('fehler', 'ok');
    if (art) el.status.classList.add(art);
  }

  let toastTimer = null;
  function toast(text, art) {
    if (!el.toast) return;
    el.toast.textContent = text;
    el.toast.hidden = false;
    el.toast.classList.remove('fehler', 'ok');
    if (art) el.toast.classList.add(art);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.toast.hidden = true;
    }, 4600);
  }

  function merkenLokal(schluessel, wert) {
    try {
      localStorage.setItem(schluessel, wert);
    } catch (fehler) {
      /* Lokale Speicherung ist Komfort, kein Muss. */
    }
  }

  function lesenLokal(schluessel) {
    try {
      return localStorage.getItem(schluessel);
    } catch (fehler) {
      return null;
    }
  }

  // ------------------------------------------------------------ Start

  document.addEventListener('DOMContentLoaded', function () {
    start().catch(function (fehler) {
      const status = $('status');
      if (status) {
        status.textContent = 'Das Atelier konnte nicht starten: ' + fehler.message;
        status.classList.add('fehler');
      }
    });
  });

  async function start() {
    const ids = ['status', 'fibo-anzeige', 'fibo-text', 'projekt-wahl', 'projekt-neu', 'projekt-oeffnen',
      'projekt-umbenennen', 'format-wahl', 'format-eigen', 'eigen-breite', 'eigen-hoehe', 'eigen-anwenden',
      'rueckgaengig', 'wiederholen', 'speichern', 'exportieren', 'ebenen-liste', 'ebenen-leer', 'ebenen-anzahl',
      'bild-waehlen', 'text-hinzufuegen', 'rechteck-hinzufuegen', 'kreis-hinzufuegen', 'studio-oeffnen',
      'test-import', 'datei-wahl', 'hintergrund-farbe', 'hintergrund-wert', 'buehne', 'leinwand-rahmen',
      'leinwand-huelle', 'leinwand', 'linie-v', 'linie-h', 'zeitstempel-flaeche', 'zeitstempel-wahl', 'hinweis-zeit',
      'zoom-aus', 'zoom-ein', 'zoom-anzeige', 'zoom-einpassen', 'zoom-100', 'leinwand-groesse',
      'eig-leer', 'eig-mehrfach', 'eig-formular', 'eig-name', 'eig-x', 'eig-y', 'eig-breite', 'eig-hoehe',
      'eig-drehung', 'eig-deckkraft', 'eig-deckkraft-wert', 'eig-spiegeln-x', 'eig-spiegeln-y',
      'eig-links', 'eig-mitte', 'eig-rechts', 'eig-oben', 'eig-unten', 'eig-fibo-hinweis',
      'eig-text', 'text-inhalt', 'text-schrift', 'text-groesse', 'text-farbe', 'text-kontur-farbe',
      'text-kontur-breite', 'text-ausrichtung', 'text-zeilenabstand', 'text-fett', 'text-kursiv',
      'text-schatten', 'text-schatten-felder', 'text-schatten-versatz', 'text-schatten-farbe',
      'text-schatten-unschaerfe', 'text-schatten-x', 'text-schatten-y',
      'eig-form', 'form-art', 'form-radius-feld', 'form-radius', 'form-kontur-breite', 'form-fuellung', 'form-kontur',
      'eig-bild', 'bild-quelle', 'bild-lizenz',
      'dialog-neu', 'neu-name', 'neu-format', 'neu-fehler', 'neu-ok',
      'dialog-oeffnen', 'oeffnen-liste', 'oeffnen-neu',
      'dialog-umbenennen', 'umbenennen-name', 'umbenennen-fehler', 'umbenennen-ok',
      'dialog-export', 'export-dateiformat', 'export-qualitaet-feld', 'export-qualitaet', 'export-qualitaet-wert',
      'export-fibo-warnung', 'export-ok',
      'dialog-studio', 'studio-status', 'studio-liste', 'studio-neu-laden',
      'willkommen', 'willkommen-neu', 'ablegen-hinweis', 'toast'];
    ids.forEach(function (id) {
      el[id.replace(/-([a-zA-Z0-9])/g, function (treffer, zeichen) {
        return zeichen.toUpperCase();
      })] = $(id);
    });

    await konfigurationLaden();
    if (!window.fabric) {
      setzeStatus('Fabric.js wurde nicht geladen.', 'fehler');
      return;
    }
    formateFuellen();
    schriftenFuellen();
    canvasInitialisieren();
    ereignisseBinden();
    Z.format = formatAusId(Z.formate[0] ? Z.formate[0].id : 'youtube');
    formatAnzeigen(Z.format);
    leinwandAnpassen();
    await fiboAktualisieren();
    setInterval(fiboAktualisieren, 5000);
    await projekteLaden(true);
    steuerungAktualisieren();
  }

  async function konfigurationLaden() {
    try {
      Z.cfg = await ruf('/api/konfig');
    } catch (fehler) {
      Z.cfg = {formate: FALLBACK_FORMATE, schriften: FALLBACK_SCHRIFTEN,
        max_seite: 4096, max_hochladen_mb: 40};
      setzeStatus('Der Dienst antwortet nicht: ' + fehler.message, 'fehler');
    }
    Z.formate = Array.isArray(Z.cfg.formate) && Z.cfg.formate.length ? Z.cfg.formate : FALLBACK_FORMATE;
    Z.schriften = Array.isArray(Z.cfg.schriften) && Z.cfg.schriften.length ? Z.cfg.schriften : FALLBACK_SCHRIFTEN;
    Z.maxSeite = Math.max(32, alsZahl(Z.cfg.max_seite, 4096));
    Z.maxHochladenMb = Math.max(1, alsZahl(Z.cfg.max_hochladen_mb, 40));
  }

  function formateFuellen() {
    [el.formatWahl, el.neuFormat].forEach(function (wahl) {
      if (!wahl) return;
      wahl.textContent = '';
      Z.formate.forEach(function (format) {
        const option = document.createElement('option');
        option.value = format.id;
        option.textContent = format.name;
        wahl.appendChild(option);
      });
    });
  }

  function schriftenFuellen() {
    if (!el.textSchrift) return;
    el.textSchrift.textContent = '';
    Z.schriften.forEach(function (name) {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      el.textSchrift.appendChild(option);
    });
  }

  function formatAusId(id) {
    const quelle = Z.formate.find(function (f) { return f.id === id; }) || Z.formate[0] || FALLBACK_FORMATE[0];
    return {id: quelle.id, name: quelle.name, breite: alsZahl(quelle.breite, 1280),
      hoehe: alsZahl(quelle.hoehe, 720), eigen: !!quelle.eigen};
  }

  function formatAnzeigen(format) {
    const sicher = {
      id: format && format.id ? format.id : 'eigenes',
      name: format && format.name ? format.name : 'Eigenes',
      breite: begrenze(Math.round(alsZahl(format && format.breite, 1280)), 32, Z.maxSeite),
      hoehe: begrenze(Math.round(alsZahl(format && format.hoehe, 720)), 32, Z.maxSeite),
      eigen: !!(format && format.eigen)
    };
    Z.format = sicher;
    const bekannt = Z.formate.some(function (f) { return f.id === sicher.id; });
    const wahlId = bekannt ? sicher.id : 'eigenes';
    if (el.formatWahl) el.formatWahl.value = wahlId;
    const eigen = wahlId === 'eigenes';
    el.formatEigen.hidden = !eigen;
    if (eigen) {
      el.eigenBreite.value = String(sicher.breite);
      el.eigenHoehe.value = String(sicher.hoehe);
    }
    el.hinweisZeit.checked = sicher.id === 'youtube' && lesenLokal('atelier.zeitstempel') === '1';
    el.zeitstempelWahl.hidden = sicher.id !== 'youtube';
  }

  // ------------------------------------------------------------ Leinwand

  function canvasInitialisieren() {
    fabric.FabricObject.customProperties = CUSTOM;
    fabric.FabricObject.prototype.borderColor = '#FF8A00';
    fabric.FabricObject.prototype.cornerColor = '#FF8A00';
    fabric.FabricObject.prototype.cornerStrokeColor = '#050606';
    fabric.FabricObject.prototype.cornerStyle = 'circle';
    fabric.FabricObject.prototype.transparentCorners = false;
    Z.canvas = new fabric.Canvas('leinwand', {
      backgroundColor: '#ffffff',
      preserveObjectStacking: true,
      selection: true,
      stopContextMenu: true
    });
    Z.canvas.selectionColor = 'rgba(255, 138, 0, .12)';
    Z.canvas.selectionBorderColor = '#FF8A00';
    Z.canvas.selectionLineWidth = 1.5;
    Z.canvas.on('selection:created', auswahlGeaendert);
    Z.canvas.on('selection:updated', auswahlGeaendert);
    Z.canvas.on('selection:cleared', auswahlGeaendert);
    Z.canvas.on('object:moving', function (ereignis) { einrasten(ereignis.target); });
    Z.canvas.on('mouse:up', hilfslinienAus);
    Z.canvas.on('object:modified', function () {
      if (Z.stumm) return;
      aenderung({eigenschaften: true});
    });
    Z.canvas.on('text:changed', function () {
      if (Z.stumm) return;
      aenderung({liste: false});
    });
    Z.canvas.on('editing:exited', function () {
      if (Z.stumm) return;
      aenderung({eigenschaften: true});
    });
    const beobachter = new ResizeObserver(function () {
      if (Z.zoomEinpassen) leinwandAnpassen();
      positioniereZeitstempel();
    });
    beobachter.observe(el.leinwandRahmen);
  }

  function auswahlGeaendert() {
    eigenschaftenAktualisieren();
    zeichneEbenen();
  }

  function formatGroesse() {
    const format = Z.format || {breite: 1280, hoehe: 720};
    return {breite: Math.max(32, Math.round(format.breite)), hoehe: Math.max(32, Math.round(format.hoehe))};
  }

  function leinwandAnpassen() {
    if (!Z.canvas) return;
    const groesse = formatGroesse();
    if (Z.zoomEinpassen && el.leinwandRahmen) {
      const rahmen = el.leinwandRahmen.getBoundingClientRect();
      const verfuegbarBreit = Math.max(120, rahmen.width - 48);
      const verfuegbarHoch = Math.max(120, rahmen.height - 48);
      Z.zoom = begrenze(Math.min(verfuegbarBreit / groesse.breite, verfuegbarHoch / groesse.hoehe, 2), 0.03, 4);
    }
    Z.zoom = begrenze(Z.zoom, 0.03, 4);
    Z.canvas.setDimensions({
      width: Math.max(1, Math.round(groesse.breite * Z.zoom)),
      height: Math.max(1, Math.round(groesse.hoehe * Z.zoom))
    });
    Z.canvas.setViewportTransform([Z.zoom, 0, 0, Z.zoom, 0, 0]);
    Z.canvas.requestRenderAll();
    setzeText(el.zoomAnzeige, Math.round(Z.zoom * 100) + ' %');
    setzeText(el.leinwandGroesse, groesse.breite + ' × ' + groesse.hoehe + ' px');
    positioniereZeitstempel();
  }

  function setzeZoom(zahl) {
    Z.zoomEinpassen = false;
    Z.zoom = begrenze(zahl, 0.03, 4);
    leinwandAnpassen();
  }

  function positioniereZeitstempel() {
    const youtube = Z.format && Z.format.id === 'youtube';
    el.zeitstempelWahl.hidden = !youtube;
    const anzeigen = youtube && el.hinweisZeit.checked;
    el.zeitstempelFlaeche.hidden = !anzeigen;
    if (anzeigen) {
      const faktor = begrenze(Z.zoom, 0.3, 2);
      el.zeitstempelFlaeche.style.right = (14 * faktor) + 'px';
      el.zeitstempelFlaeche.style.bottom = (14 * faktor) + 'px';
      el.zeitstempelFlaeche.style.minWidth = (130 * faktor) + 'px';
      el.zeitstempelFlaeche.style.minHeight = (34 * faktor) + 'px';
      el.zeitstempelFlaeche.style.fontSize = (11 * faktor) + 'px';
    }
  }

  function einrasten(obj) {
    if (!obj) return;
    hilfslinienAus();
    const groesse = formatGroesse();
    const grenze = 7 / Math.max(Z.zoom, 0.03);
    const rahmen = obj.getBoundingRect();
    const kantenX = [
      {wert: rahmen.left, ziel: 0},
      {wert: rahmen.left + rahmen.width / 2, ziel: groesse.breite / 2},
      {wert: rahmen.left + rahmen.width, ziel: groesse.breite}
    ];
    const kantenY = [
      {wert: rahmen.top, ziel: 0},
      {wert: rahmen.top + rahmen.height / 2, ziel: groesse.hoehe / 2},
      {wert: rahmen.top + rahmen.height, ziel: groesse.hoehe}
    ];
    let bestX = null;
    let bestY = null;
    kantenX.forEach(function (kante) {
      [{ziel: 0}, {ziel: groesse.breite / 2}, {ziel: groesse.breite}].forEach(function (ziel) {
        const abstand = ziel.ziel - kante.wert;
        if (Math.abs(abstand) <= grenze && (!bestX || Math.abs(abstand) < Math.abs(bestX.abstand))) {
          bestX = {abstand: abstand, ziel: ziel.ziel};
        }
      });
    });
    kantenY.forEach(function (kante) {
      [{ziel: 0}, {ziel: groesse.hoehe / 2}, {ziel: groesse.hoehe}].forEach(function (ziel) {
        const abstand = ziel.ziel - kante.wert;
        if (Math.abs(abstand) <= grenze && (!bestY || Math.abs(abstand) < Math.abs(bestY.abstand))) {
          bestY = {abstand: abstand, ziel: ziel.ziel};
        }
      });
    });
    if (bestX) {
      obj.left += bestX.abstand;
      obj.setCoords();
      el.linieV.style.left = (bestX.ziel * Z.zoom) + 'px';
      el.linieV.hidden = false;
    }
    if (bestY) {
      obj.top += bestY.abstand;
      obj.setCoords();
      el.linieH.style.top = (bestY.ziel * Z.zoom) + 'px';
      el.linieH.hidden = false;
    }
  }

  function hilfslinienAus() {
    if (el.linieV) el.linieV.hidden = true;
    if (el.linieH) el.linieH.hidden = true;
  }

  // ------------------------------------------------------------ Projektliste und Projekt laden

  async function projekteLaden(start) {
    try {
      const daten = await ruf('/api/projekte');
      Z.projekte = Array.isArray(daten.projekte) ? daten.projekte : [];
    } catch (fehler) {
      setzeStatus('Projekte konnten nicht gelesen werden: ' + fehler.message, 'fehler');
      Z.projekte = [];
      zeigeWillkommen(true);
      return;
    }
    projektWahlFuellen();
    if (!start) return;
    if (!Z.projekte.length) {
      zeigeWillkommen(true);
      return;
    }
    let name = lesenLokal('atelier.projekt');
    if (!Z.projekte.some(function (p) { return p.name === name; })) name = Z.projekte[0].name;
    try {
      await projektOeffnen(name, true);
    } catch (fehler) {
      setzeStatus('Das Projekt konnte nicht geöffnet werden: ' + fehler.message, 'fehler');
      zeigeWillkommen(true);
    }
  }

  function projektWahlFuellen() {
    if (!el.projektWahl) return;
    el.projektWahl.textContent = '';
    if (!Z.projekte.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Kein Projekt';
      el.projektWahl.appendChild(option);
    } else {
      Z.projekte.forEach(function (projekt) {
        const option = document.createElement('option');
        option.value = projekt.name;
        option.textContent = projekt.name;
        el.projektWahl.appendChild(option);
      });
    }
    if (Z.projekt && Z.projekte.some(function (p) { return p.name === Z.projekt.name; })) {
      el.projektWahl.value = Z.projekt.name;
    } else if (Z.projekte.length) {
      el.projektWahl.value = Z.projekte[0].name;
    }
    el.projektWahl.disabled = Z.projekte.length === 0;
  }

  function zeigeWillkommen(anzeigen) {
    if (!el.willkommen) return;
    el.willkommen.hidden = !anzeigen;
    if (anzeigen) {
      setzeStatus('Noch kein Projekt – Neu anlegen oder Öffnen.');
      document.title = 'Atelier';
    }
  }

  async function bilderquellenAktualisieren() {
    const objekte = Z.canvas.getObjects().filter(function (obj) {
      return obj.type === 'image' && obj.quelle && obj.quelle.datei;
    });
    for (let i = 0; i < objekte.length; i += 1) {
      const obj = objekte[i];
      const ziel = bildUrl(obj.quelle.datei);
      if (obj.getSrc && obj.getSrc() !== ziel) {
        await obj.setSrc(ziel);
      }
    }
    Z.canvas.requestRenderAll();
  }

  async function projektOeffnen(name, erst) {
    if (!name) return false;
    if (!erst && Z.projekt && Z.projekt.name === name && !Z.schmutzig) return true;
    if (!erst && Z.projekt && Z.schmutzig) {
      const gespeichert = await speichern(true);
      if (!gespeichert) return false;
    }
    setzeStatus('Öffne „' + name + '“ …');
    let daten;
    try {
      daten = await ruf('/api/projekt?name=' + encodeURIComponent(name));
    } catch (fehler) {
      toast('Projekt nicht geöffnet: ' + fehler.message, 'fehler');
      setzeStatus(fehler.message, 'fehler');
      return false;
    }
    Z.laden = true;
    Z.stumm = true;
    let gelungen = false;
    try {
      Z.projekt = {name: daten.name || name, gespeichert: daten.gespeichert || null};
      formatAnzeigen(daten.format || formatAusId('youtube'));
      const ebenen = daten.ebenen && typeof daten.ebenen === 'object' ? daten.ebenen : {objects: []};
      const vorbereitet = jsonVorbereiten(ebenen);
      Z.canvas.clear();
      await Z.canvas.loadFromJSON(vorbereitet);
      Z.canvas.backgroundColor = farbeFuerCanvas(daten.hintergrund);
      customFelderSetzen(vorbereitet);
      Z.canvas.discardActiveObject();
      el.hintergrundFarbe.value = farbeFuerInput(daten.hintergrund, '#ffffff');
      setzeText(el.hintergrundWert, el.hintergrundFarbe.value);
      Z.zoomEinpassen = true;
      leinwandAnpassen();
      Z.canvas.requestRenderAll();
      eigenschaftenAktualisieren();
      zeichneEbenen();
      zeigeWillkommen(false);
      el.projektWahl.value = Z.projekt.name;
      document.title = 'Atelier – ' + Z.projekt.name;
      merkenLokal('atelier.projekt', Z.projekt.name);
      Z.schmutzig = false;
      Z.fassung = 0;
      const zeit = uhrzeit(daten.gespeichert);
      setzeStatus(zeit ? 'Gespeichert ' + zeit : 'Bereit', 'ok');
      gelungen = true;
    } catch (fehler) {
      Z.projekt = null;
      setzeStatus('Das Projekt ist beschädigt oder ein Bild fehlt: ' + fehler.message, 'fehler');
      toast('Projekt nicht geöffnet: ' + fehler.message, 'fehler');
      zeigeWillkommen(true);
      return false;
    } finally {
      Z.stumm = false;
      Z.laden = false;
      steuerungAktualisieren();
    }
    if (gelungen) verlaufZuruecksetzen();
    return true;
  }

  function jsonVorbereiten(ebenen) {
    let kopie;
    try {
      kopie = JSON.parse(JSON.stringify(ebenen || {objects: []}));
    } catch (fehler) {
      kopie = {objects: []};
    }
    if (!Array.isArray(kopie.objects)) kopie.objects = [];
    kopie.objects.forEach(function (o) {
      if (o && o.type === 'image' && o.quelle && o.quelle.datei) {
        o.src = bildUrl(o.quelle.datei);
      }
    });
    return kopie;
  }

  function customFelderSetzen(vorlage) {
    const objekte = Z.canvas.getObjects();
    const daten = vorlage && Array.isArray(vorlage.objects) ? vorlage.objects : [];
    objekte.forEach(function (obj, index) {
      const o = daten[index] || {};
      obj.atelierArt = o.atelierArt || artVon(obj);
      obj.atelierName = o.atelierName || nameVon(obj);
      obj.quelle = o.quelle && typeof o.quelle === 'object' ? o.quelle : null;
      obj.atelierGesperrt = !!o.atelierGesperrt;
      sperreAnwenden(obj);
    });
  }

  function projektDaten() {
    const ebenen = Z.canvas.toJSON(CUSTOM);
    if (!Array.isArray(ebenen.objects)) ebenen.objects = [];
    ebenen.objects.forEach(function (o) {
      if (o && o.type === 'image' && o.quelle && o.quelle.datei) {
        o.src = bildUrl(o.quelle.datei);
      }
    });
    return {
      format: Z.format,
      hintergrund: farbeFuerCanvas(Z.canvas.backgroundColor),
      ebenen: ebenen
    };
  }

  // ------------------------------------------------------------ Speichern und Verlauf

  function planeSpeichern() {
    if (!Z.projekt || Z.stumm) return;
    Z.schmutzig = true;
    Z.fassung += 1;
    setzeStatus('Änderungen …');
    clearTimeout(Z.speicherTimer);
    Z.speicherTimer = setTimeout(function () { speichern(true); }, 2000);
  }

  function aenderung(optionen) {
    const opt = optionen || {};
    if (!Z.projekt || Z.stumm) return;
    Z.schmutzig = true;
    Z.fassung += 1;
    setzeStatus('Änderungen …');
    clearTimeout(Z.speicherTimer);
    Z.speicherTimer = setTimeout(function () { speichern(true); }, 2000);
    verlaufMerken(!!opt.sofort);
    if (opt.liste !== false) zeichneEbenen();
    if (opt.eigenschaften) eigenschaftenAktualisieren();
  }

  async function speichern(leise) {
    if (!Z.projekt) return false;
    clearTimeout(Z.speicherTimer);
    if (!leise) setzeStatus('Speichere …');
    const fassung = Z.fassung;
    try {
      const antwort = await ruf('/api/projekt/speichern', {
        methode: 'POST',
        koerper: {name: Z.projekt.name, projekt: projektDaten()}
      });
      Z.projekt.gespeichert = antwort.gespeichert;
      if (Z.fassung === fassung) {
        Z.schmutzig = false;
        const zeit = uhrzeit(antwort.gespeichert);
        setzeStatus(zeit ? 'Gespeichert ' + zeit : 'Gespeichert', 'ok');
        if (!leise) toast('Projekt gespeichert.', 'ok');
      } else {
        setzeStatus('Änderungen …');
        if (!Z.speicherTimer) Z.speicherTimer = setTimeout(function () { speichern(true); }, 2000);
      }
      return true;
    } catch (fehler) {
      setzeStatus('Nicht gespeichert: ' + fehler.message, 'fehler');
      if (!leise) toast('Nicht gespeichert: ' + fehler.message, 'fehler');
      return false;
    }
  }

  function verlaufMerken(sofort) {
    if (!Z.projekt || Z.stumm) return;
    clearTimeout(Z.verlaufTimer);
    const tun = function () {
      if (!Z.projekt) return;
      let text;
      try {
        text = JSON.stringify(projektDaten());
      } catch (fehler) {
        return;
      }
      if (Z.zeiger >= 0 && Z.verlauf[Z.zeiger] === text) return;
      Z.verlauf = Z.verlauf.slice(0, Z.zeiger + 1);
      Z.verlauf.push(text);
      if (Z.verlauf.length > 50) Z.verlauf.shift();
      Z.zeiger = Z.verlauf.length - 1;
      verlaufKnoepfe();
    };
    if (sofort) tun();
    else Z.verlaufTimer = setTimeout(tun, 250);
  }

  function verlaufKnoepfe() {
    el.rueckgaengig.disabled = !(Z.projekt && Z.zeiger > 0);
    el.wiederholen.disabled = !(Z.projekt && Z.zeiger >= 0 && Z.zeiger < Z.verlauf.length - 1);
  }

  function verlaufZuruecksetzen() {
    clearTimeout(Z.verlaufTimer);
    Z.verlauf = [];
    Z.zeiger = -1;
    verlaufMerken(true);
    verlaufKnoepfe();
  }

  async function standAnwenden(text) {
    const stand = JSON.parse(text);
    Z.stumm = true;
    Z.laden = true;
    try {
      if (stand.format) formatAnzeigen(stand.format);
      const vorbereitet = jsonVorbereiten(stand.ebenen);
      Z.canvas.clear();
      await Z.canvas.loadFromJSON(vorbereitet);
      Z.canvas.backgroundColor = farbeFuerCanvas(stand.hintergrund);
      customFelderSetzen(vorbereitet);
      Z.canvas.discardActiveObject();
      el.hintergrundFarbe.value = farbeFuerInput(stand.hintergrund, '#ffffff');
      setzeText(el.hintergrundWert, el.hintergrundFarbe.value);
      leinwandAnpassen();
      Z.canvas.requestRenderAll();
      eigenschaftenAktualisieren();
      zeichneEbenen();
    } finally {
      Z.stumm = false;
      Z.laden = false;
    }
    planeSpeichern();
    verlaufKnoepfe();
  }

  async function rueckgaengig() {
    if (!Z.projekt) return;
    clearTimeout(Z.verlaufTimer);
    verlaufMerken(true);
    if (Z.zeiger <= 0) return;
    Z.zeiger -= 1;
    await standAnwenden(Z.verlauf[Z.zeiger]);
  }

  async function wiederholen() {
    if (!Z.projekt) return;
    clearTimeout(Z.verlaufTimer);
    verlaufMerken(true);
    if (Z.zeiger < 0 || Z.zeiger >= Z.verlauf.length - 1) return;
    Z.zeiger += 1;
    await standAnwenden(Z.verlauf[Z.zeiger]);
  }

  function steuerungAktualisieren() {
    const hat = !!Z.projekt;
    if (el.projektUmbenennen) el.projektUmbenennen.disabled = !hat;
    if (el.exportieren) el.exportieren.disabled = !hat;
    if (el.speichern) el.speichern.disabled = !hat;
    if (el.hintergrundFarbe) el.hintergrundFarbe.disabled = !hat;
    if (el.projektWahl) el.projektWahl.disabled = !Z.projekte.length;
    verlaufKnoepfe();
  }

  // ------------------------------------------------------------ Ebenenliste

  function zeichneEbenen() {
    if (!el.ebenenListe) return;
    const objekte = Z.canvas ? Z.canvas.getObjects().slice().reverse() : [];
    const aktiv = new Set(Z.canvas ? Z.canvas.getActiveObjects() : []);
    el.ebenenListe.textContent = '';
    objekte.forEach(function (obj) {
      el.ebenenListe.appendChild(ebeneZeile(obj, aktiv.has(obj)));
    });
    el.ebenenLeer.hidden = objekte.length > 0;
    setzeText(el.ebenenAnzahl, objekte.length ? objekte.length + (objekte.length === 1 ? ' Ebene' : ' Ebenen') : '');
  }

  function ebeneZeile(obj, aktiv) {
    const li = document.createElement('li');
    li.className = 'ebene';
    li._obj = obj;
    if (aktiv) li.classList.add('aktiv');
    if (obj.visible === false) li.classList.add('versteckt');
    if (obj.atelierGesperrt) li.classList.add('gesperrt');

    const griff = document.createElement('span');
    griff.className = 'griff';
    griff.textContent = '≡';
    griff.title = 'Ziehen zum Umsortieren';
    griff.draggable = true;
    griff.addEventListener('dragstart', function (ereignis) {
      Z.dragObjekt = obj;
      li.classList.add('aktiv');
      if (ereignis.dataTransfer) {
        ereignis.dataTransfer.effectAllowed = 'move';
        ereignis.dataTransfer.setData('text/plain', nameVon(obj));
      }
    });
    griff.addEventListener('dragend', function () {
      Z.dragObjekt = null;
      hilfslinienAus();
    });
    li.appendChild(griff);

    const sicht = document.createElement('button');
    sicht.type = 'button';
    sicht.className = 'symbol ' + (obj.visible === false ? 'aus' : 'an');
    sicht.textContent = obj.visible === false ? '○' : '◉';
    sicht.title = obj.visible === false ? 'Anzeigen' : 'Ausblenden';
    sicht.setAttribute('aria-label', sicht.title);
    sicht.addEventListener('click', function (ereignis) {
      ereignis.stopPropagation();
      obj.visible = obj.visible === false;
      sperreAnwenden(obj);
      if (obj.visible === false && Z.canvas.getActiveObjects().indexOf(obj) >= 0) {
        Z.canvas.discardActiveObject();
      }
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });
    li.appendChild(sicht);

    const sperre = document.createElement('button');
    sperre.type = 'button';
    sperre.className = 'symbol ' + (obj.atelierGesperrt ? 'an' : 'aus');
    sperre.textContent = obj.atelierGesperrt ? '🔒' : '🔓';
    sperre.title = obj.atelierGesperrt ? 'Entsperren' : 'Sperren';
    sperre.setAttribute('aria-label', sperre.title);
    sperre.addEventListener('click', function (ereignis) {
      ereignis.stopPropagation();
      obj.atelierGesperrt = !obj.atelierGesperrt;
      sperreAnwenden(obj);
      if (obj.atelierGesperrt && Z.canvas.getActiveObjects().indexOf(obj) >= 0) {
        Z.canvas.discardActiveObject();
      }
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });
    li.appendChild(sperre);

    const vorschau = document.createElement('span');
    vorschau.className = 'ebene-vorschau';
    const art = artVon(obj);
    if (art === 'bild') {
      const quelle = obj.quelle || {};
      const bild = document.createElement('img');
      bild.alt = '';
      bild.loading = 'lazy';
      if (quelle.datei && Z.projekt) bild.src = bildUrl(quelle.datei);
      vorschau.appendChild(bild);
    } else if (art === 'text') {
      vorschau.textContent = 'T';
    } else {
      vorschau.textContent = obj.type === 'circle' ? '◯' : '▭';
    }
    li.appendChild(vorschau);

    const mitte = document.createElement('div');
    mitte.className = 'ebene-mitte';
    const name = document.createElement('input');
    name.type = 'text';
    name.className = 'ebene-name';
    name.value = nameVon(obj);
    name.maxLength = 80;
    name.setAttribute('aria-label', 'Ebenenname');
    name.addEventListener('change', function () {
      obj.atelierName = name.value.trim() || typName(obj);
      name.value = obj.atelierName;
      aenderung({eigenschaften: true});
    });
    name.addEventListener('click', function (ereignis) { ereignis.stopPropagation(); });
    mitte.appendChild(name);

    const meta = document.createElement('span');
    meta.className = 'ebene-meta';
    const typ = document.createElement('span');
    typ.textContent = typName(obj);
    meta.appendChild(typ);
    if (istFibo(obj)) {
      const fibo = document.createElement('span');
      fibo.className = 'fibo';
      fibo.textContent = 'Fibo · nicht-kommerziell';
      meta.appendChild(fibo);
    }
    mitte.appendChild(meta);
    const kraftZeile = document.createElement('span');
    kraftZeile.className = 'ebene-meta kraft';
    const deckkraft = document.createElement('input');
    deckkraft.type = 'range';
    deckkraft.className = 'deckkraft';
    deckkraft.min = '0';
    deckkraft.max = '100';
    deckkraft.step = '1';
    deckkraft.value = String(Math.round((obj.opacity === undefined ? 1 : obj.opacity) * 100));
    deckkraft.setAttribute('aria-label', 'Deckkraft');
    const ausgabe = document.createElement('output');
    ausgabe.textContent = deckkraft.value + ' %';
    deckkraft.addEventListener('input', function () {
      obj.opacity = alsZahl(deckkraft.value, 100) / 100;
      ausgabe.textContent = deckkraft.value + ' %';
      obj.dirty = true;
      Z.canvas.requestRenderAll();
    });
    deckkraft.addEventListener('change', function () {
      aenderung({liste: false});
      eigenschaftenAktualisieren();
    });
    deckkraft.addEventListener('click', function (ereignis) { ereignis.stopPropagation(); });
    kraftZeile.appendChild(deckkraft);
    kraftZeile.appendChild(ausgabe);
    mitte.appendChild(kraftZeile);
    li.appendChild(mitte);

    const duplizieren = document.createElement('button');
    duplizieren.type = 'button';
    duplizieren.className = 'symbol duplizieren';
    duplizieren.textContent = '⧉';
    duplizieren.title = 'Duplizieren';
    duplizieren.setAttribute('aria-label', 'Ebene duplizieren');
    duplizieren.addEventListener('click', function (ereignis) {
      ereignis.stopPropagation();
      dupliziere(obj);
    });
    li.appendChild(duplizieren);

    const loeschen = document.createElement('button');
    loeschen.type = 'button';
    loeschen.className = 'symbol loeschen';
    loeschen.textContent = '✕';
    loeschen.title = 'Löschen';
    loeschen.setAttribute('aria-label', 'Ebene löschen');
    loeschen.addEventListener('click', function (ereignis) {
      ereignis.stopPropagation();
      loeschenObjekte([obj]);
    });
    li.appendChild(loeschen);

    li.addEventListener('click', function (ereignis) {
      if (ereignis.target.closest('button, input, textarea, select, .griff')) return;
      waehle(obj);
    });
    li.addEventListener('dragover', function (ereignis) {
      if (!Z.dragObjekt || Z.dragObjekt === obj) return;
      ereignis.preventDefault();
      if (ereignis.dataTransfer) ereignis.dataTransfer.dropEffect = 'move';
    });
    li.addEventListener('drop', function (ereignis) {
      if (!Z.dragObjekt || Z.dragObjekt === obj) return;
      ereignis.preventDefault();
      sortiereUm(Z.dragObjekt, obj);
      Z.dragObjekt = null;
    });
    return li;
  }

  function sortiereUm(quelle, ziel) {
    const reihenfolge = Array.from(el.ebenenListe.children).map(function (li) { return li._obj; });
    const von = reihenfolge.indexOf(quelle);
    const nach = reihenfolge.indexOf(ziel);
    if (von < 0 || nach < 0) return;
    reihenfolge.splice(von, 1);
    reihenfolge.splice(nach, 0, quelle);
    const untenNachOben = reihenfolge.slice().reverse();
    untenNachOben.forEach(function (obj, index) {
      if (Z.canvas.moveObjectTo) Z.canvas.moveObjectTo(obj, index);
    });
    Z.canvas.requestRenderAll();
    aenderung({eigenschaften: true});
  }

  function waehle(obj) {
    if (!Z.canvas || !obj) return;
    Z.canvas.setActiveObject(obj);
    Z.canvas.requestRenderAll();
    eigenschaftenAktualisieren();
    zeichneEbenen();
  }

  function sperreAnwenden(obj) {
    const gesperrt = !!obj.atelierGesperrt;
    obj.lockMovementX = gesperrt;
    obj.lockMovementY = gesperrt;
    obj.lockScalingX = gesperrt;
    obj.lockScalingY = gesperrt;
    obj.lockRotation = gesperrt;
    obj.selectable = obj.visible !== false && !gesperrt;
    obj.evented = obj.visible !== false && !gesperrt;
    obj.hoverCursor = gesperrt ? 'default' : 'move';
  }

  async function dupliziere(obj) {
    if (!obj) return;
    try {
      const kopie = await obj.clone(CUSTOM);
      kopie.set({
        left: (obj.left || 0) + 24,
        top: (obj.top || 0) + 24,
        atelierName: nameVon(obj) + ' Kopie',
        atelierGesperrt: false
      });
      sperreAnwenden(kopie);
      Z.canvas.add(kopie);
      Z.canvas.setActiveObject(kopie);
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    } catch (fehler) {
      toast('Ebene konnte nicht dupliziert werden: ' + fehler.message, 'fehler');
    }
  }

  function loeschenObjekte(objekte) {
    if (!objekte || !objekte.length) return;
    objekte.forEach(function (obj) { Z.canvas.remove(obj); });
    Z.canvas.discardActiveObject();
    Z.canvas.requestRenderAll();
    aenderung({eigenschaften: true});
  }

  // ------------------------------------------------------------ Ebenen hinzufügen

  function mitProjektOderDialog() {
    if (Z.projekt) return true;
    oeffneNeuesProjekt();
    return false;
  }

  function textHinzufuegen() {
    if (!mitProjektOderDialog()) return;
    const groesse = formatGroesse();
    const breite = Math.min(groesse.breite * 0.72, 900);
    const schriftgroesse = Math.max(22, Math.round(Math.min(groesse.breite, groesse.hoehe) * 0.075));
    const text = new fabric.Textbox('Text', {
      left: (groesse.breite - breite) / 2,
      top: Math.round(groesse.hoehe * 0.36),
      width: breite,
      fontSize: schriftgroesse,
      fontFamily: Z.schriften.indexOf('Impact') >= 0 ? 'Impact' : Z.schriften[0],
      fontWeight: 'normal',
      fill: '#1B2025',
      textAlign: 'center',
      lineHeight: 1.1,
      stroke: null,
      strokeWidth: 0,
      strokeUniform: true,
      paintFirst: 'stroke'
    });
    ebeneHinzufuegen(text, 'text', 'Text', null);
  }

  function formHinzufuegen(art) {
    if (!mitProjektOderDialog()) return;
    const groesse = formatGroesse();
    const seite = Math.round(Math.min(groesse.breite, groesse.hoehe) * 0.36);
    let form;
    if (art === 'kreis') {
      form = new fabric.Circle({
        left: (groesse.breite - seite) / 2,
        top: (groesse.hoehe - seite) / 2,
        radius: seite / 2,
        fill: '#FF8A00',
        stroke: '#3A2410',
        strokeWidth: 0
      });
    } else {
      form = new fabric.Rect({
        left: (groesse.breite - seite) / 2,
        top: (groesse.hoehe - seite) / 2,
        width: seite,
        height: Math.round(seite * 0.72),
        rx: 24,
        ry: 24,
        fill: '#FF8A00',
        stroke: '#3A2410',
        strokeWidth: 0
      });
    }
    ebeneHinzufuegen(form, 'form', art === 'kreis' ? 'Kreis' : 'Rechteck', null);
  }

  function ebeneHinzufuegen(obj, art, name, quelle) {
    obj.atelierArt = art;
    obj.atelierName = name;
    obj.quelle = quelle || null;
    obj.atelierGesperrt = false;
    sperreAnwenden(obj);
    Z.canvas.add(obj);
    Z.canvas.setActiveObject(obj);
    Z.canvas.requestRenderAll();
    aenderung({eigenschaften: true});
  }

  async function bildHinzufuegen(datei, name, quelle) {
    if (!Z.projekt) return;
    try {
      const bild = await fabric.FabricImage.fromURL(bildUrl(datei));
      const groesse = formatGroesse();
      const breite = alsZahl(bild.width, 1);
      const hoehe = alsZahl(bild.height, 1);
      const faktor = Math.min((groesse.breite * 0.82) / breite, (groesse.hoehe * 0.82) / hoehe, 1);
      bild.set({
        left: (groesse.breite - breite * faktor) / 2,
        top: (groesse.hoehe - hoehe * faktor) / 2,
        scaleX: faktor,
        scaleY: faktor
      });
      ebeneHinzufuegen(bild, 'bild', name || 'Bild', quelle || {art: 'datei', datei: datei, name: name || datei});
    } catch (fehler) {
      toast('Bild konnte nicht geladen werden: ' + fehler.message, 'fehler');
    }
  }

  function dateiLesen(datei) {
    return new Promise(function (aufloesen, ablehnen) {
      const leser = new FileReader();
      leser.onload = function () { aufloesen(String(leser.result || '')); };
      leser.onerror = function () { ablehnen(new Error('Die Datei ließ sich nicht lesen.')); };
      leser.readAsDataURL(datei);
    });
  }

  async function dateienHochladen(dateien) {
    if (!dateien || !dateien.length) return;
    if (!mitProjektOderDialog()) return;
    const erlaubt = ['image/png', 'image/jpeg', 'image/webp'];
    for (let i = 0; i < dateien.length; i += 1) {
      const datei = dateien[i];
      if (erlaubt.indexOf(datei.type) < 0) {
        toast('Nur PNG, JPEG oder WebP: ' + datei.name, 'fehler');
        continue;
      }
      if (datei.size > Z.maxHochladenMb * 1024 * 1024) {
        toast('Das Bild ist zu groß (höchstens ' + Z.maxHochladenMb + ' MB): ' + datei.name, 'fehler');
        continue;
      }
      try {
        const daten = await dateiLesen(datei);
        const antwort = await ruf('/api/hochladen', {
          methode: 'POST',
          koerper: {projekt: Z.projekt.name, name: datei.name, daten: daten}
        });
        await bildHinzufuegen(antwort.datei, datei.name, {art: 'datei', datei: antwort.datei, name: datei.name});
      } catch (fehler) {
        toast('Hochladen fehlgeschlagen: ' + fehler.message, 'fehler');
      }
    }
  }

  async function testImport() {
    if (!mitProjektOderDialog()) return;
    try {
      const flaeche = document.createElement('canvas');
      flaeche.width = 640;
      flaeche.height = 400;
      const stift = flaeche.getContext('2d');
      const verlauf = stift.createLinearGradient(0, 0, 640, 400);
      verlauf.addColorStop(0, '#FF8A00');
      verlauf.addColorStop(0.55, '#9A5208');
      verlauf.addColorStop(1, '#1A201E');
      stift.fillStyle = verlauf;
      stift.fillRect(0, 0, 640, 400);
      stift.fillStyle = 'rgba(5, 6, 6, .82)';
      stift.fillRect(44, 250, 552, 96);
      stift.fillStyle = '#F5F1E8';
      stift.font = '700 42px Impact, sans-serif';
      stift.textAlign = 'center';
      stift.fillText('Fibo · Test', 320, 312);
      stift.font = '600 15px Segoe UI, sans-serif';
      stift.fillText('nur zum Prüfen der Kennzeichnung', 320, 338);
      const daten = flaeche.toDataURL('image/png');
      const antwort = await ruf('/api/hochladen', {
        methode: 'POST',
        koerper: {projekt: Z.projekt.name, name: 'Fibo-Testbild', daten: daten}
      });
      await bildHinzufuegen(antwort.datei, 'Fibo-Testbild', {
        art: 'fibo',
        datei: antwort.datei,
        name: 'Fibo-Testbild',
        lizenz: 'CC BY-NC 4.0'
      });
      toast('Test-Ebene mit Fibo-Kennzeichnung hinzugefügt (nur nicht-kommerziell).', 'ok');
    } catch (fehler) {
      toast('Test-Import fehlgeschlagen: ' + fehler.message, 'fehler');
    }
  }

  // ------------------------------------------------------------ Eigenschaften

  function aktivesObjekt() {
    if (!Z.canvas) return null;
    const objekte = Z.canvas.getActiveObjects();
    return objekte.length === 1 ? objekte[0] : null;
  }

  function eigenschaftenAktualisieren() {
    if (!Z.canvas) return;
    const aktive = Z.canvas.getActiveObjects();
    const obj = aktive.length === 1 ? aktive[0] : null;
    if (!obj) {
      el.eigLeer.hidden = aktive.length > 0;
      el.eigMehrfach.hidden = aktive.length < 2;
      el.eigFormular.hidden = true;
      return;
    }
    el.eigLeer.hidden = true;
    el.eigMehrfach.hidden = true;
    el.eigFormular.hidden = false;
    el.eigName.value = nameVon(obj);
    el.eigX.value = String(Math.round(alsZahl(obj.left, 0)));
    el.eigY.value = String(Math.round(alsZahl(obj.top, 0)));
    el.eigBreite.value = String(Math.round(obj.getScaledWidth()));
    el.eigHoehe.value = String(Math.round(obj.getScaledHeight()));
    el.eigDrehung.value = String(Math.round(alsZahl(obj.angle, 0)));
    const deckkraft = Math.round((obj.opacity === undefined ? 1 : obj.opacity) * 100);
    el.eigDeckkraft.value = String(deckkraft);
    setzeText(el.eigDeckkraftWert, deckkraft + ' %');

    const art = artVon(obj);
    el.eigText.hidden = art !== 'text';
    el.eigForm.hidden = art !== 'form';
    el.eigBild.hidden = art !== 'bild';

    const quelle = obj.quelle || null;
    const fibo = istFibo(obj);
    let hinweis = '';
    if (fibo) {
      hinweis = 'Fibo · nicht-kommerziell – nur nicht-kommerziell nutzbar.';
      if ((Z.format && (Z.format.id === 'flyer_a5' || Z.format.id === 'flyer_a4')) &&
          (Math.abs(alsZahl(obj.scaleX, 1)) > 1.0001 || Math.abs(alsZahl(obj.scaleY, 1)) > 1.0001)) {
        hinweis += ' Bei dieser Vergrößerung: unscharf beim Druck.';
      }
    }
    el.eigFiboHinweis.hidden = !hinweis;
    setzeText(el.eigFiboHinweis, hinweis);

    if (art === 'text') {
      el.textInhalt.value = obj.text || '';
      const schrift = obj.fontFamily || Z.schriften[0];
      if (!Array.from(el.textSchrift.options).some(function (o) { return o.value === schrift; })) {
        const option = document.createElement('option');
        option.value = schrift;
        option.textContent = schrift;
        el.textSchrift.appendChild(option);
      }
      el.textSchrift.value = schrift;
      el.textGroesse.value = String(Math.round(alsZahl(obj.fontSize, 48)));
      el.textFarbe.value = farbeFuerInput(obj.fill, '#1B2025');
      el.textKonturFarbe.value = farbeFuerInput(obj.stroke, '#000000');
      el.textKonturBreite.value = String(alsZahl(obj.strokeWidth, 0));
      el.textAusrichtung.value = obj.textAlign || 'left';
      el.textZeilenabstand.value = String(alsZahl(obj.lineHeight, 1.1));
      el.textFett.checked = String(obj.fontWeight).toLowerCase() === 'bold' || alsZahl(obj.fontWeight, 0) >= 700;
      el.textKursiv.checked = String(obj.fontStyle).toLowerCase() === 'italic';
      el.textSchatten.checked = !!obj.shadow;
      el.textSchattenFelder.hidden = !obj.shadow;
      el.textSchattenVersatz.hidden = !obj.shadow;
      if (obj.shadow) {
        el.textSchattenFarbe.value = farbeFuerInput(obj.shadow.color, '#000000');
        el.textSchattenUnschaerfe.value = String(alsZahl(obj.shadow.blur, 8));
        el.textSchattenX.value = String(alsZahl(obj.shadow.offsetX, 4));
        el.textSchattenY.value = String(alsZahl(obj.shadow.offsetY, 4));
      }
    }

    if (art === 'form') {
      const kreis = obj.type === 'circle';
      setzeText(el.formArt, kreis ? 'Kreis' : 'Rechteck');
      el.formRadiusFeld.hidden = kreis;
      el.formRadius.value = String(Math.round(alsZahl(obj.rx, 0)));
      el.formFuellung.value = farbeFuerInput(obj.fill, '#FF8A00');
      el.formKontur.value = farbeFuerInput(obj.stroke, '#3A2410');
      el.formKonturBreite.value = String(alsZahl(obj.strokeWidth, 0));
    }

    if (art === 'bild') {
      const teile = [];
      if (quelle && quelle.name) teile.push(quelle.name);
      if (quelle && quelle.datei) teile.push(quelle.datei);
      if (quelle && quelle.pfad) teile.push(quelle.pfad);
      setzeText(el.bildQuelle, teile.length ? teile.join(' · ') : 'Bild ohne Quellenangabe');
      el.bildLizenz.hidden = !fibo;
      setzeText(el.bildLizenz, fibo ? 'Fibo · nicht-kommerziell (CC BY-NC 4.0)' : '');
    }
  }

  function eigenschaftenBinden() {
    el.eigName.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.atelierName = el.eigName.value.trim() || typName(obj);
      el.eigName.value = obj.atelierName;
      aenderung({liste: true});
    });

    [[el.eigX, 'left'], [el.eigY, 'top']].forEach(function (paar) {
      paar[0].addEventListener('change', function () {
        const obj = aktivesObjekt();
        if (!obj) return;
        obj.set(paar[1], alsZahl(paar[0].value, obj[paar[1]]));
        obj.setCoords();
        Z.canvas.requestRenderAll();
        aenderung({eigenschaften: true});
      });
    });

    el.eigBreite.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      const breite = Math.max(1, alsZahl(el.eigBreite.value, obj.getScaledWidth()));
      if (obj.width > 0) obj.set('scaleX', breite / obj.width);
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });

    el.eigHoehe.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      const hoehe = Math.max(1, alsZahl(el.eigHoehe.value, obj.getScaledHeight()));
      if (obj.height > 0) obj.set('scaleY', hoehe / obj.height);
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });

    el.eigDrehung.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.rotate(alsZahl(el.eigDrehung.value, 0));
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });

    el.eigDeckkraft.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      const wert = alsZahl(el.eigDeckkraft.value, 100);
      obj.opacity = wert / 100;
      setzeText(el.eigDeckkraftWert, wert + ' %');
      obj.dirty = true;
      Z.canvas.requestRenderAll();
    });
    el.eigDeckkraft.addEventListener('change', function () {
      aenderung({liste: false});
    });

    el.eigSpiegelnX.addEventListener('click', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.flipX = !obj.flipX;
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });
    el.eigSpiegelnY.addEventListener('click', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.flipY = !obj.flipY;
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });

    const ausrichtungen = {
      links: 'links', mitte: 'mitte', rechts: 'rechts', oben: 'oben', unten: 'unten'
    };
    Object.keys(ausrichtungen).forEach(function (schluessel) {
      el['eig' + schluessel.charAt(0).toUpperCase() + schluessel.slice(1)].addEventListener('click', function () {
        ausrichten(ausrichtungen[schluessel]);
      });
    });

    el.textInhalt.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('text', el.textInhalt.value);
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.textSchrift.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fontFamily', el.textSchrift.value);
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false, eigenschaften: true});
    });
    el.textGroesse.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fontSize', begrenze(alsZahl(el.textGroesse.value, 48), 4, 600));
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false, eigenschaften: true});
    });
    el.textFarbe.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fill', el.textFarbe.value);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.textKonturBreite.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      const breite = begrenze(alsZahl(el.textKonturBreite.value, 0), 0, 30);
      obj.set('strokeWidth', breite);
      obj.set('stroke', breite > 0 ? el.textKonturFarbe.value : null);
      obj.set('paintFirst', 'stroke');
      obj.set('strokeUniform', true);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.textKonturFarbe.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      if (alsZahl(obj.strokeWidth, 0) > 0) obj.set('stroke', el.textKonturFarbe.value);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.textAusrichtung.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('textAlign', el.textAusrichtung.value);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.textZeilenabstand.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('lineHeight', begrenze(alsZahl(el.textZeilenabstand.value, 1.1), 0.6, 3));
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false, eigenschaften: true});
    });
    el.textFett.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fontWeight', el.textFett.checked ? 'bold' : 'normal');
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false, eigenschaften: true});
    });
    el.textKursiv.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fontStyle', el.textKursiv.checked ? 'italic' : 'normal');
      obj.setCoords();
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false, eigenschaften: true});
    });
    el.textSchatten.addEventListener('change', function () {
      el.textSchattenFelder.hidden = !el.textSchatten.checked;
      el.textSchattenVersatz.hidden = !el.textSchatten.checked;
      textSchattenSetzen();
    });
    [el.textSchattenFarbe, el.textSchattenUnschaerfe, el.textSchattenX, el.textSchattenY].forEach(function (feld) {
      feld.addEventListener('change', textSchattenSetzen);
    });

    el.formRadius.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj || obj.type !== 'rect') return;
      const radius = begrenze(alsZahl(el.formRadius.value, 0), 0, 1000);
      obj.set({rx: radius, ry: radius});
      obj.setCoords();
      Z.canvas.requestRenderAll();
      aenderung({eigenschaften: true});
    });
    el.formFuellung.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('fill', el.formFuellung.value);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.formKontur.addEventListener('input', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('stroke', el.formKontur.value);
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.formKonturBreite.addEventListener('change', function () {
      const obj = aktivesObjekt();
      if (!obj) return;
      obj.set('strokeWidth', begrenze(alsZahl(el.formKonturBreite.value, 0), 0, 100));
      obj.dirty = true;
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
  }

  function textSchattenSetzen() {
    const obj = aktivesObjekt();
    if (!obj || artVon(obj) !== 'text') return;
    if (!el.textSchatten.checked) {
      obj.shadow = null;
    } else {
      obj.shadow = new fabric.Shadow({
        color: el.textSchattenFarbe.value,
        blur: begrenze(alsZahl(el.textSchattenUnschaerfe.value, 8), 0, 80),
        offsetX: alsZahl(el.textSchattenX.value, 4),
        offsetY: alsZahl(el.textSchattenY.value, 4)
      });
    }
    obj.dirty = true;
    Z.canvas.requestRenderAll();
    aenderung({liste: false});
  }

  function ausrichten(richtung) {
    const objekte = Z.canvas.getActiveObjects();
    if (!objekte.length) return;
    const groesse = formatGroesse();
    objekte.forEach(function (obj) {
      const rahmen = obj.getBoundingRect();
      let dx = 0;
      let dy = 0;
      if (richtung === 'links') dx = -rahmen.left;
      if (richtung === 'mitte') dx = (groesse.breite - rahmen.width) / 2 - rahmen.left;
      if (richtung === 'rechts') dx = groesse.breite - rahmen.width - rahmen.left;
      if (richtung === 'oben') dy = -rahmen.top;
      if (richtung === 'unten') dy = groesse.hoehe - rahmen.height - rahmen.top;
      obj.left += dx;
      obj.top += dy;
      obj.setCoords();
    });
    Z.canvas.requestRenderAll();
    aenderung({eigenschaften: true});
  }

  // ------------------------------------------------------------ Export

  async function oeffneExport() {
    if (!Z.projekt) {
      toast('Bitte zuerst ein Projekt anlegen.', 'fehler');
      return;
    }
    exportWarnungAktualisieren();
    exportQualitaetAnzeigen();
    el.dialogExport.showModal();
  }

  function exportWarnungAktualisieren() {
    const sichtbar = Z.canvas.getObjects().filter(function (obj) {
      return obj.visible !== false && istFibo(obj);
    });
    if (sichtbar.length) {
      el.exportFiboWarnung.hidden = false;
      el.exportFiboWarnung.textContent = 'Achtung: ' + sichtbar.length + ' sichtbare Fibo-' +
        (sichtbar.length === 1 ? 'Ebene ist' : 'Ebenen sind') + ' nur nicht-kommerziell nutzbar.';
    } else {
      el.exportFiboWarnung.hidden = true;
    }
  }

  function exportQualitaetAnzeigen() {
    const jpeg = el.exportDateiformat.value === 'jpeg';
    el.exportQualitaetFeld.hidden = !jpeg;
    setzeText(el.exportQualitaetWert, el.exportQualitaet.value + ' %');
  }

  async function exportieren() {
    if (!Z.projekt || Z.exportLaeuft) return;
    Z.exportLaeuft = true;
    el.exportOk.disabled = true;
    setzeStatus('Exportiere …');
    try {
      const dateiformat = el.exportDateiformat.value === 'jpeg' ? 'jpeg' : 'png';
      const qualitaet = dateiformat === 'jpeg' ? begrenze(alsZahl(el.exportQualitaet.value, 92), 50, 100) / 100 : 1;
      const gespeichert = await speichern(true);
      if (!gespeichert) throw new Error('Das Projekt ließ sich nicht speichern.');
      const groesse = formatGroesse();
      const alterZoom = Z.canvas.getZoom();
      const alteBreite = Z.canvas.getWidth();
      const alteHoehe = Z.canvas.getHeight();
      let daten;
      try {
        Z.canvas.setDimensions({width: groesse.breite, height: groesse.hoehe});
        Z.canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
        daten = Z.canvas.toDataURL({format: dateiformat, quality: qualitaet, multiplier: 1});
      } finally {
        Z.canvas.setDimensions({width: alteBreite, height: alteHoehe});
        Z.canvas.setViewportTransform([alterZoom, 0, 0, alterZoom, 0, 0]);
        Z.canvas.requestRenderAll();
        positioniereZeitstempel();
      }
      const antwort = await ruf('/api/export', {
        methode: 'POST',
        koerper: {projekt: Z.projekt.name, bild: daten}
      });
      el.dialogExport.close();
      const bildPfad = '/api/export-datei?projekt=' + encodeURIComponent(Z.projekt.name) +
        '&datei=' + encodeURIComponent(antwort.datei);
      const jsonPfad = '/api/export-datei?projekt=' + encodeURIComponent(Z.projekt.name) +
        '&datei=' + encodeURIComponent(antwort.json);
      ladeHerunter(bildPfad, antwort.datei);
      setTimeout(function () { ladeHerunter(jsonPfad, antwort.json); }, 500);
      const zeit = uhrzeit(new Date().toISOString());
      setzeStatus(zeit ? 'Exportiert ' + zeit : 'Exportiert', 'ok');
      toast('Export gespeichert: ' + antwort.datei + ' und ' + antwort.json, 'ok');
    } catch (fehler) {
      setzeStatus('Export fehlgeschlagen: ' + fehler.message, 'fehler');
      toast('Export fehlgeschlagen: ' + fehler.message, 'fehler');
    } finally {
      Z.exportLaeuft = false;
      el.exportOk.disabled = false;
    }
  }

  function ladeHerunter(pfad, name) {
    const a = document.createElement('a');
    a.href = pfad;
    a.download = name || '';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // ------------------------------------------------------------ Studio-Bibliothek

  async function oeffneStudio() {
    if (!mitProjektOderDialog()) return;
    el.dialogStudio.showModal();
    await studioLaden();
  }

  async function studioLaden() {
    el.studioListe.textContent = '';
    setzeText(el.studioStatus, 'Wird geladen …');
    try {
      const daten = await ruf('/api/studio/bibliothek');
      const eintraege = Array.isArray(daten.eintraege) ? daten.eintraege : [];
      if (!eintraege.length) {
        setzeText(el.studioStatus, 'Die Studio-Bibliothek ist leer. In der Werkstatt Bilder erzeugen, dann neu einlesen.');
        return;
      }
      setzeText(el.studioStatus, eintraege.length + ' Bild' + (eintraege.length === 1 ? '' : 'er') +
        ' in der Bibliothek. Anklicken zum Übernehmen.');
      eintraege.forEach(function (eintrag) {
        const karte = document.createElement('button');
        karte.type = 'button';
        karte.className = 'studio-karte';
        const bild = document.createElement('img');
        bild.alt = '';
        bild.loading = 'lazy';
        bild.src = '/api/studio/bild?pfad=' + encodeURIComponent(eintrag.pfad || '');
        const titel = document.createElement('span');
        titel.textContent = eintrag.name || 'Bild';
        const klein = document.createElement('small');
        klein.textContent = eintrag.projekt || '';
        karte.appendChild(bild);
        karte.appendChild(titel);
        karte.appendChild(klein);
        karte.addEventListener('click', function () { studioUebernehmen(eintrag); });
        el.studioListe.appendChild(karte);
      });
    } catch (fehler) {
      setzeText(el.studioStatus, fehler.message);
      toast(fehler.message, 'fehler');
    }
  }

  async function studioUebernehmen(eintrag) {
    if (!Z.projekt || !eintrag || !eintrag.pfad) return;
    setzeText(el.studioStatus, '„' + (eintrag.name || 'Bild') + '“ wird übernommen …');
    try {
      const antwort = await ruf('/api/studio/uebernehmen', {
        methode: 'POST',
        koerper: {projekt: Z.projekt.name, pfad: eintrag.pfad}
      });
      await bildHinzufuegen(antwort.datei, eintrag.name, {
        art: 'studio',
        datei: antwort.datei,
        name: eintrag.name,
        projekt: eintrag.projekt,
        pfad: eintrag.pfad
      });
      el.dialogStudio.close();
      toast('Bild aus der Studio-Bibliothek hinzugefügt.', 'ok');
    } catch (fehler) {
      setzeText(el.studioStatus, fehler.message);
      toast(fehler.message, 'fehler');
    }
  }

  // ------------------------------------------------------------ Fibo-Anzeige

  async function fiboAktualisieren() {
    try {
      const daten = await ruf('/api/fibo/health');
      Z.fiboBereit = !!daten.bereit;
      setzeText(el.fiboText, daten.bereit ? 'bereit' : (daten.text || FIBO_AUS));
      el.fiboAnzeige.classList.toggle('bereit', !!daten.bereit);
      el.fiboAnzeige.classList.toggle('startet', daten.status === 'loading');
      el.fiboAnzeige.classList.toggle('aus', !daten.bereit && daten.status !== 'loading');
    } catch (fehler) {
      Z.fiboBereit = false;
      setzeText(el.fiboText, FIBO_AUS);
      el.fiboAnzeige.classList.remove('bereit', 'startet');
      el.fiboAnzeige.classList.add('aus');
    }
  }

  // ------------------------------------------------------------ Dialoge

  function oeffneNeuesProjekt() {
    el.neuFehler.hidden = true;
    el.neuName.value = '';
    const id = Z.format && Z.formate.some(function (f) { return f.id === Z.format.id; }) ? Z.format.id : Z.formate[0].id;
    el.neuFormat.value = id;
    el.dialogNeu.showModal();
    setTimeout(function () { el.neuName.focus(); }, 40);
  }

  async function neuesProjektAnlegen() {
    const name = el.neuName.value.trim();
    if (!name) {
      el.neuFehler.hidden = false;
      setzeText(el.neuFehler, 'Bitte einen Projektnamen angeben.');
      el.neuName.focus();
      return;
    }
    const format = formatAusId(el.neuFormat.value);
    el.neuOk.disabled = true;
    el.neuFehler.hidden = true;
    try {
      if (Z.projekt && Z.schmutzig) {
        const gespeichert = await speichern(true);
        if (!gespeichert) throw new Error('Das laufende Projekt ließ sich nicht speichern.');
      }
      await ruf('/api/projekt/neu', {methode: 'POST', koerper: {name: name, format: format}});
      el.dialogNeu.close();
      await projekteLaden(false);
      await projektOeffnen(name, true);
      toast('Projekt „' + name + '“ angelegt.', 'ok');
    } catch (fehler) {
      el.neuFehler.hidden = false;
      setzeText(el.neuFehler, fehler.message);
    } finally {
      el.neuOk.disabled = false;
    }
  }

  async function oeffneProjektListe() {
    el.oeffnenListe.textContent = '';
    try {
      const daten = await ruf('/api/projekte');
      Z.projekte = Array.isArray(daten.projekte) ? daten.projekte : [];
    } catch (fehler) {
      toast(fehler.message, 'fehler');
      return;
    }
    if (!Z.projekte.length) {
      const leer = document.createElement('p');
      leer.className = 'leise';
      leer.textContent = 'Noch kein Projekt vorhanden.';
      el.oeffnenListe.appendChild(leer);
    }
    Z.projekte.forEach(function (projekt) {
      const eintrag = document.createElement('button');
      eintrag.type = 'button';
      eintrag.className = 'oeffnen-eintrag';
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = projekt.name;
      const meta = document.createElement('span');
      meta.className = 'meta';
      const format = projekt.format || {};
      const teile = [];
      if (format.breite && format.hoehe) teile.push(format.breite + ' × ' + format.hoehe);
      const wann = projekt.gespeichert || projekt.zeit;
      if (wann) {
        const datum = new Date(typeof wann === 'number' ? wann * 1000 : wann);
        if (!Number.isNaN(datum.getTime())) teile.push(datum.toLocaleDateString('de-DE'));
      }
      if (typeof projekt.anzahl_ebenen === 'number') teile.push(projekt.anzahl_ebenen + ' Ebenen');
      meta.textContent = teile.join(' · ');
      eintrag.appendChild(name);
      eintrag.appendChild(meta);
      eintrag.addEventListener('click', function () {
        el.dialogOeffnen.close();
        projektOeffnen(projekt.name, false).catch(function (fehler) {
          toast(fehler.message, 'fehler');
        });
      });
      el.oeffnenListe.appendChild(eintrag);
    });
    el.dialogOeffnen.showModal();
  }

  function oeffneUmbenennen() {
    if (!Z.projekt) return;
    el.umbenennenName.value = Z.projekt.name;
    el.umbenennenFehler.hidden = true;
    el.dialogUmbenennen.showModal();
    setTimeout(function () { el.umbenennenName.select(); }, 40);
  }

  async function umbenennen() {
    if (!Z.projekt) return;
    const alt = Z.projekt.name;
    const neu = el.umbenennenName.value.trim();
    if (!neu) {
      el.umbenennenFehler.hidden = false;
      setzeText(el.umbenennenFehler, 'Bitte einen neuen Namen angeben.');
      return;
    }
    el.umbenennenOk.disabled = true;
    try {
      const antwort = await ruf('/api/projekt/umbenennen', {methode: 'POST', koerper: {name: alt, neu: neu}});
      if (Z.projekt) Z.projekt.name = antwort.name;
      merkenLokal('atelier.projekt', antwort.name);
      el.dialogUmbenennen.close();
      await projekteLaden(false);
      el.projektWahl.value = antwort.name;
      document.title = 'Atelier – ' + antwort.name;
      await bilderquellenAktualisieren();
      await speichern(true);
      toast('Projekt umbenannt in „' + antwort.name + '“.', 'ok');
    } catch (fehler) {
      el.umbenennenFehler.hidden = false;
      setzeText(el.umbenennenFehler, fehler.message);
    } finally {
      el.umbenennenOk.disabled = false;
    }
  }

  function dialogSchliessenKnopf(ereignis) {
    const knopf = ereignis.currentTarget;
    const dialog = knopf.closest('dialog');
    if (dialog) dialog.close();
  }

  // ------------------------------------------------------------ Ereignisse

  function ereignisseBinden() {
    el.projektWahl.addEventListener('change', function () {
      if (!el.projektWahl.value) return;
      projektOeffnen(el.projektWahl.value, false).then(function (gelungen) {
        if (!gelungen && Z.projekt) el.projektWahl.value = Z.projekt.name;
      }).catch(function (fehler) {
        toast(fehler.message, 'fehler');
        if (Z.projekt) el.projektWahl.value = Z.projekt.name;
      });
    });
    el.projektNeu.addEventListener('click', oeffneNeuesProjekt);
    el.projektOeffnen.addEventListener('click', oeffneProjektListe);
    el.projektUmbenennen.addEventListener('click', oeffneUmbenennen);
    el.willkommenNeu.addEventListener('click', oeffneNeuesProjekt);
    el.oeffnenNeu.addEventListener('click', function () {
      el.dialogOeffnen.close();
      oeffneNeuesProjekt();
    });
    el.neuOk.addEventListener('click', neuesProjektAnlegen);
    el.neuName.addEventListener('keydown', function (ereignis) {
      if (ereignis.key === 'Enter') {
        ereignis.preventDefault();
        neuesProjektAnlegen();
      }
    });
    el.umbenennenOk.addEventListener('click', umbenennen);
    el.umbenennenName.addEventListener('keydown', function (ereignis) {
      if (ereignis.key === 'Enter') {
        ereignis.preventDefault();
        umbenennen();
      }
    });

    el.formatWahl.addEventListener('change', function () {
      const id = el.formatWahl.value;
      if (id === 'eigenes') {
        el.formatEigen.hidden = false;
        el.eigenBreite.value = String(formatGroesse().breite);
        el.eigenHoehe.value = String(formatGroesse().hoehe);
        return;
      }
      formatAnzeigen(formatAusId(id));
      Z.zoomEinpassen = true;
      leinwandAnpassen();
      aenderung({eigenschaften: true, sofort: true});
    });
    el.eigenAnwenden.addEventListener('click', function () {
      const breite = Math.round(alsZahl(el.eigenBreite.value, 1280));
      const hoehe = Math.round(alsZahl(el.eigenHoehe.value, 720));
      if (breite < 32 || hoehe < 32 || breite > Z.maxSeite || hoehe > Z.maxSeite) {
        toast('Das eigene Format muss zwischen 32 und ' + Z.maxSeite + ' Pixel je Seite liegen.', 'fehler');
        return;
      }
      formatAnzeigen({id: 'eigenes', name: 'Eigenes', breite: breite, hoehe: hoehe, eigen: true});
      Z.zoomEinpassen = true;
      leinwandAnpassen();
      aenderung({eigenschaften: true, sofort: true});
    });
    [el.eigenBreite, el.eigenHoehe].forEach(function (feld) {
      feld.addEventListener('keydown', function (ereignis) {
        if (ereignis.key === 'Enter') {
          ereignis.preventDefault();
          el.eigenAnwenden.click();
        }
      });
    });

    el.rueckgaengig.addEventListener('click', function () { rueckgaengig(); });
    el.wiederholen.addEventListener('click', function () { wiederholen(); });
    el.speichern.addEventListener('click', function () { speichern(false); });
    el.exportieren.addEventListener('click', oeffneExport);

    el.zoomAus.addEventListener('click', function () { setzeZoom(Z.zoom / 1.2); });
    el.zoomEin.addEventListener('click', function () { setzeZoom(Z.zoom * 1.2); });
    el.zoomEinpassen.addEventListener('click', function () {
      Z.zoomEinpassen = true;
      leinwandAnpassen();
    });
    el.zoom100.addEventListener('click', function () { setzeZoom(1); });
    el.hinweisZeit.addEventListener('change', function () {
      merkenLokal('atelier.zeitstempel', el.hinweisZeit.checked ? '1' : '0');
      positioniereZeitstempel();
    });

    el.bildWaehlen.addEventListener('click', function () {
      if (!mitProjektOderDialog()) return;
      el.dateiWahl.click();
    });
    el.dateiWahl.addEventListener('change', function () {
      const dateien = Array.from(el.dateiWahl.files || []);
      el.dateiWahl.value = '';
      dateienHochladen(dateien);
    });
    el.textHinzufuegen.addEventListener('click', textHinzufuegen);
    el.rechteckHinzufuegen.addEventListener('click', function () { formHinzufuegen('rechteck'); });
    el.kreisHinzufuegen.addEventListener('click', function () { formHinzufuegen('kreis'); });
    el.studioOeffnen.addEventListener('click', oeffneStudio);
    el.studioNeuLaden.addEventListener('click', studioLaden);
    el.testImport.addEventListener('click', testImport);

    el.hintergrundFarbe.addEventListener('input', function () {
      Z.canvas.backgroundColor = el.hintergrundFarbe.value;
      setzeText(el.hintergrundWert, el.hintergrundFarbe.value);
      Z.canvas.requestRenderAll();
      aenderung({liste: false});
    });
    el.hintergrundFarbe.addEventListener('change', function () {
      aenderung({liste: false, sofort: true});
    });

    el.exportDateiformat.addEventListener('change', exportQualitaetAnzeigen);
    el.exportQualitaet.addEventListener('input', function () {
      setzeText(el.exportQualitaetWert, el.exportQualitaet.value + ' %');
    });
    el.exportOk.addEventListener('click', exportieren);

    alle('[data-schliessen]').forEach(function (knopf) {
      knopf.addEventListener('click', dialogSchliessenKnopf);
    });
    alle('dialog').forEach(function (dialog) {
      dialog.addEventListener('click', function (ereignis) {
        if (ereignis.target === dialog) dialog.close();
      });
    });

    let ziehTiefe = 0;
    function hatDateien(ereignis) {
      return !!(ereignis.dataTransfer && Array.from(ereignis.dataTransfer.types || []).indexOf('Files') >= 0);
    }
    el.buehne.addEventListener('dragenter', function (ereignis) {
      if (!hatDateien(ereignis)) return;
      ziehTiefe += 1;
      el.ablegenHinweis.hidden = false;
    });
    el.buehne.addEventListener('dragleave', function (ereignis) {
      if (!hatDateien(ereignis)) return;
      ziehTiefe = Math.max(0, ziehTiefe - 1);
      if (!ziehTiefe) el.ablegenHinweis.hidden = true;
    });
    el.buehne.addEventListener('dragover', function (ereignis) {
      if (!hatDateien(ereignis)) return;
      ereignis.preventDefault();
      ereignis.dataTransfer.dropEffect = 'copy';
    });
    el.buehne.addEventListener('drop', function (ereignis) {
      if (!hatDateien(ereignis)) return;
      ereignis.preventDefault();
      ziehTiefe = 0;
      el.ablegenHinweis.hidden = true;
      dateienHochladen(Array.from(ereignis.dataTransfer.files || []));
    });

    eigenschaftenBinden();

    document.addEventListener('keydown', function (ereignis) {
      const ziel = ereignis.target;
      if (ziel && ziel.closest && ziel.closest('input, textarea, select, [contenteditable="true"]')) return;
      const strg = ereignis.ctrlKey || ereignis.metaKey;
      if (strg) {
        const taste = String(ereignis.key).toLowerCase();
        if (taste === 'z') {
          ereignis.preventDefault();
          if (ereignis.shiftKey) wiederholen(); else rueckgaengig();
          return;
        }
        if (taste === 'y') {
          ereignis.preventDefault();
          wiederholen();
          return;
        }
        if (taste === 's') {
          ereignis.preventDefault();
          speichern(false);
          return;
        }
        if (taste === 'd') {
          const obj = aktivesObjekt();
          if (obj) {
            ereignis.preventDefault();
            dupliziere(obj);
          }
          return;
        }
      }
      if (ereignis.key === 'Delete' || ereignis.key === 'Backspace') {
        const objekte = Z.canvas.getActiveObjects();
        if (objekte.length) {
          ereignis.preventDefault();
          loeschenObjekte(objekte);
        }
        return;
      }
      if (ereignis.key === 'Escape') {
        Z.canvas.discardActiveObject();
        Z.canvas.requestRenderAll();
        auswahlGeaendert();
        return;
      }
      const pfeile = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
      if (pfeile[ereignis.key]) {
        const objekte = Z.canvas.getActiveObjects();
        if (!objekte.length) return;
        ereignis.preventDefault();
        const schritt = ereignis.shiftKey ? 10 : 1;
        objekte.forEach(function (obj) {
          obj.left += pfeile[ereignis.key][0] * schritt;
          obj.top += pfeile[ereignis.key][1] * schritt;
          obj.setCoords();
        });
        Z.canvas.requestRenderAll();
        aenderung({eigenschaften: true});
      }
    });

    document.addEventListener('visibilitychange', function () {
      if (document.hidden && Z.schmutzig) speichern(true);
    });
  }
})();
