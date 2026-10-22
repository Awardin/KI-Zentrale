'use strict';

// Reiter Bild & Video: Zustandszeile über dem Studio (studio.js). Starten und Beenden von ComfyUI bleiben in der
// Modellzentrale (Platzprüfung, Bestätigung). 2Wild ist seit Stufe 3c stillgelegt und wird nicht mehr eingebettet.

const BV = { aktiv: false, stand: null };

function bvZeichnen() {
  const s = BV.stand;
  const zustand = $('#bv-zustand');
  if (!s) { zustand.textContent = 'Der Dienst der Werkstatt antwortet nicht.'; return; }
  // Seit Stufe 8 mehrere ComfyUI-Prozesse: je einer rechnet einen Auftrag, gleichzeitig.
  const weitere = s.weitere || [];
  const laufend = (s.laufend || 0) + weitere.reduce((n, w) => n + (w.laufend || 0), 0);
  const an = (s.comfy ? 1 : 0) + weitere.filter(w => w.an).length;
  const alle = 1 + weitere.length;
  const zahlwort = (n) => ({ 1: 'ein', 2: 'zwei', 3: 'drei' }[n] || String(n));
  const Zahlwort = (n) => ({ 1: 'Ein', 2: 'Zwei', 3: 'Drei' }[n] || String(n));
  let text = 'Bild & Video ist aus.';
  if (s.comfy && laufend >= 2) text = `${Zahlwort(laufend)} Aufträge rechnen gleichzeitig.`;
  else if (s.comfy && laufend === 1) text = an > 1 ? 'Ein Auftrag rechnet, weitere können daneben starten.' : 'ComfyUI rechnet gerade.';
  else if (laufend === 0 && an === alle && alle > 1) text = `Bereit: ${zahlwort(alle)} Aufträge können gleichzeitig rechnen.`;
  else if (s.comfy && an < alle) text = `Bereit, aber nur ${zahlwort(an)} von ${zahlwort(alle)} ComfyUI-Prozessen laufen: Bild & Video in der Modellzentrale starten, dann rechnen ${zahlwort(alle)} Aufträge gleichzeitig.`;
  else if (s.comfy) text = 'ComfyUI bereit.';
  zustand.textContent = text;
  zustand.dataset.an = s.comfy ? '1' : '0';
  $('#bv-comfy').hidden = !s.comfy;
  $('#bv-comfy').href = s.comfy_url;
}

async function bvAktualisieren() {
  try {
    BV.stand = await api('/api/bildvideo');
  } catch {
    BV.stand = null;
  }
  bvZeichnen();
}

function bvSchleife() {
  const weiter = () => setTimeout(bvSchleife, 5000);
  if (!BV.aktiv) return weiter();
  bvAktualisieren().finally(weiter);
}

$('#bv-zentrale').addEventListener('click', () => api('/api/zentrale', {}).catch(() => {}));

window.bildvideoAktiv = (aktiv) => {
  BV.aktiv = aktiv;
  window.studioSichtbar?.(aktiv);
  if (aktiv) bvAktualisieren();
};
bvZeichnen();
bvSchleife();
