'use strict';

// Reiter Bild & Video: Zustandszeile über dem Studio (studio.js). Starten und Beenden von ComfyUI bleiben in der
// Modellzentrale (Platzprüfung, Bestätigung). 2Wild ist seit Stufe 3c stillgelegt und wird nicht mehr eingebettet.

const BV = { aktiv: false, stand: null };

function bvZeichnen() {
  const s = BV.stand;
  const zustand = $('#bv-zustand');
  if (!s) { zustand.textContent = 'Der Dienst der Werkstatt antwortet nicht.'; return; }
  // Seit Stufe 8 zwei ComfyUI-Prozesse: je einer rechnet einen Auftrag, gleichzeitig.
  const laufend = s.laufend + (s.laufend2 || 0);
  const zwei = s.comfy && s.comfy2;
  let text = 'Bild & Video ist aus.';
  if (s.comfy && laufend) text = laufend > 1 ? 'Zwei Aufträge rechnen gleichzeitig.' : (zwei ? 'Ein Auftrag rechnet, ein zweiter kann daneben starten.' : 'ComfyUI rechnet gerade.');
  else if (zwei) text = 'Bereit: zwei Aufträge können gleichzeitig rechnen.';
  else if (s.comfy && s.comfy2_eingerichtet) text = 'Bereit, aber nur ein ComfyUI-Prozess läuft: Bild & Video in der Modellzentrale starten, dann rechnen zwei Aufträge gleichzeitig.';
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
