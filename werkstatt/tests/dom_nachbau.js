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

// DOM für die Composer-Bedientests. Selektoren werden auf dem aktuellen Baum ausgewertet.
function dokumentBauen() {
  let dokument;
  class Element {
    constructor(tag) {
      this.tag = tag; this.children = []; this.events = {}; this.attrs = {}; this.parentElement = null;
      this._text = ''; this._value = null; this.className = ''; this.hidden = false; this.disabled = false;
      this.scrollTop = 0; this.scrollLeft = 0; this.clientWidth = 800;
      this.classList = { add: (c) => this.klasse(c, true), remove: (c) => this.klasse(c, false),
        toggle: (c, an) => this.klasse(c, an ?? !this.className.split(' ').includes(c)) };
    }
    klasse(c, an) { const s = new Set(this.className.split(' ').filter(Boolean)); if (an) s.add(c); else s.delete(c); this.className = [...s].join(' '); }
    get textContent() { return this._text + this.children.map((k) => k.textContent).join(''); }
    set textContent(v) { this.children = []; this._text = String(v); }
    set innerHTML(v) { throw Error('innerHTML darf keine Prompt- oder Modelltexte übernehmen.'); }
    get value() { return this._value ?? (this.tag === 'select' ? this.children.find((x) => !x.disabled)?.value || '' : this.attrs.value || ''); }
    set value(v) { this._value = String(v); }
    append(...werte) {
      for (let k of kinder(...werte)) {
        if (!(k instanceof Element)) { const text = new Element('#text'); text.textContent = k.textContent; k = text; }
        if (k.parentElement) k.remove();
        k.parentElement = this; this.children.push(k);
      }
    }
    replaceChildren(...k) { for (const x of this.children) x.parentElement = null; this.children = []; this._text = ''; this.append(...k); }
    setAttribute(k, v) { this.attrs[k] = String(v); if (['id', 'name', 'type', 'value'].includes(k)) this[k] = String(v); if (['hidden', 'disabled', 'open'].includes(k)) this[k] = true; }
    getAttribute(k) { return this.attrs[k] ?? (k === 'id' ? this.id : null); }
    addEventListener(k, f) { (this.events[k] ||= []).push(f); }
    async ausloesen(k, e = {}) { for (const f of this.events[k] || []) await f({ target: this, currentTarget: this, preventDefault() {}, ...e }); }
    focus() { dokument.activeElement = this; }
    blur() { if (dokument.activeElement === this) dokument.activeElement = null; }
    select() {}
    scrollBy({left}) { this.scrollLeft += left; }
    remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((x) => x !== this); this.parentElement = null; }
    alle() { return this.children.flatMap((k) => [k, ...k.alle()]); }
    matches(selector) {
      return selector.split(',').some((s) => {
        const teile = s.trim().split(/\s+/); const selbst = teile.pop();
        const pruefen = (el, t) => {
          const tag = t.match(/^[a-z][a-z0-9-]*/i)?.[0]; if (tag && el.tag !== tag) return false;
          const id = t.match(/#([\w-]+)/)?.[1]; if (id && el.id !== id) return false;
          const klasse = t.match(/\.([\w-]+)/)?.[1]; if (klasse && !el.className.split(' ').includes(klasse)) return false;
          for (const m of t.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
            const wert = el.getAttribute(m[1]);
            if (m[1] === 'open' ? !el.open : m[2] === undefined ? wert === null : wert !== m[2]) return false;
          }
          return true;
        };
        if (!pruefen(this, selbst)) return false;
        let el = this.parentElement;
        while (teile.length) { const t = teile.pop(); while (el && !pruefen(el, t)) el = el.parentElement; if (!el) return false; el = el.parentElement; }
        return true;
      });
    }
    querySelectorAll(s) { return this.alle().filter((k) => k.matches(s)); }
    querySelector(s) { return this.querySelectorAll(s)[0] || null; }
    closest(s) { return this.matches(s) ? this : this.parentElement?.closest(s) || null; }
  }
  dokument = new Element('document');
  dokument.createElement = (tag) => new Element(tag);
  dokument.createElementNS = (_, tag) => new Element(tag);
  dokument.getElementById = (id) => dokument.querySelector('#' + id);
  dokument.activeElement = null;
  const wurzel = new Element('main'); wurzel.id = 'reiter-prompts'; dokument.append(wurzel);
  for (const id of ['p-navigation', 'p-zuletzt', 'p-bibliotheksliste', 'p-composer', 'p-entdecken', 'p-kontexte', 'p-inhalt', 'p-liste', 'p-rueck', 'p-suche', 'p-herkunft', 'p-status', 'p-neu', 'p-laden']) {
    const el = new Element('div'); el.id = id; wurzel.append(el);
  }
  return { dokument, Element };
}
module.exports.dokumentBauen = dokumentBauen;
