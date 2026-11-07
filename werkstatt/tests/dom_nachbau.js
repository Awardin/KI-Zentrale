'use strict';

const assert = require('assert');

// Die kleinen DOM-Nachbauten kennzeichnen Elemente und Textknoten mit tag.
function kinder(...werte) {
  return werte.map((wert) => wert && typeof wert === 'object' && typeof wert.tag === 'string'
    ? wert : { tag: '#text', textContent: String(wert) });
}

function keinFremdText(wurzel) {
  if (!wurzel) return;
  assert(!['null', 'undefined', '[object Object]'].includes(wurzel.textContent),
    `Sichtbarer Fremdtext: ${wurzel.textContent}`);
  for (const kind of wurzel.children || []) keinFremdText(kind);
}

module.exports = { kinder, keinFremdText };
