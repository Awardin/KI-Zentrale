import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import prompts  # noqa: E402


class Zaun(unittest.TestCase):
    def test_rundlauf(self):
        for text in ('', 'Text', 'Text\n', 'Text\r\n',
                     '~~~\n ~~~\n  ~~~\n   ~~~\n~~~~\n```\n#### kein Kopf',
                     'Anfang\r\n   ~~~~~text\r\nEnde'):
            for zeichen in ('~', '`'):
                with self.subTest(text=text, zeichen=zeichen):
                    b, = prompts.bloecke(prompts.block_schreiben(text, 'text', zeichen))
                    self.assertEqual(b['text'], text)
                    self.assertTrue(b['geschlossen'])

    def test_commonmark_zaunzustand(self):
        text = '  ~~~~text\n#### innen\n~~~\n```\n   ~~~~~ \n```python\na\n```\n~~~\noffen'
        a, b, c = prompts.bloecke(text)
        self.assertEqual((a['auf'], a['zu'], a['laenge']), (0, 4, 4))
        self.assertIn('#### innen', a['text'])
        self.assertEqual((b['zeichen'], b['kennung']), ('`', 'python'))
        self.assertFalse(c['geschlossen'])
        self.assertEqual(prompts.bloecke('    ~~~text\nx\n    ~~~'), [])
        self.assertEqual(prompts.bloecke('```a`b\nx'), [])


class Kennungen(unittest.TestCase):
    def test_geraete_reserviert_und_dopplungen(self):
        for name in ('CON', 'con.txt', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT9.md'):
            wert = prompts.kennung(name)
            self.assertIn('_', wert)
            self.assertFalse(wert.startswith('_'))
            self.assertNotEqual(wert.split('.')[0].upper(), name.split('.')[0].upper())
        self.assertEqual(prompts.kennung('A/B'), 'A B')
        self.assertEqual(prompts.kennung('A:B', ['A B']), 'A B (2)')
        self.assertEqual(prompts.kennung('hallo', ['Hallo', 'HALLO (2)']), 'hallo (3)')
        self.assertLessEqual(len(prompts.kennung('a' * 100, ['a' * 70])), 70)
        with self.assertRaises(ValueError):
            prompts.kennung('_Sammlung')


class FelderUndAuftrag(unittest.TestCase):
    def test_regex_links_zeitmarken_dopplung_und_woertlich(self):
        text = '[A] [A] [red, blue] [x] [ref] [00:12:34] [hh:mm:ss] [123] [Link](https://x) [Ärger]'
        self.assertEqual(prompts.felder_erkennen(text), ['A', 'red, blue', 'x', 'ref', 'Ärger'])
        self.assertEqual(prompts.felder_erkennen('[a\nb] [] [' + 'x' * 61 + ']'), [])

    def test_ein_durchgang_leer_woertlich_zwei_transkripte_rahmen(self):
        eingaben = {'felder': {'A': {'art': 'text', 'wert': '[B] [Klammern]'},
            'B': {'art': 'text', 'wert': 'ersetzt'}, 'x': {'art': 'woertlich'},
            'T1': {'art': 'transkript'}, 'T2': {'art': 'transkript'}}, 'leer': ['Leer'],
            'rahmen': {'art': 'text', 'wert': 'Rahmen'}}
        text, sha = prompts.auftrag_bauen('[A] [B] [x] [Leer] [T1] [T2]', eingaben,
                                          {'T1': '[B] Transkript 1', 'T2': 'Transkript 2'})
        self.assertEqual(text, 'Rahmen\n\n[B] [Klammern] ersetzt [x] [Leer] [B] Transkript 1 Transkript 2')
        self.assertEqual(sha, prompts.sha(text))
        self.assertEqual(len(sha), 64)


class Belege(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.datei = prompts.beleg_anlegen(self.tmp.name,
            {'fassung': 'Fassung 1', 'auswerter': 'Fake', 'zustand': 'wartet', 'urteil': 'offen', 'notiz': ''},
            'Fassung', {'felder': {'A': {'art': 'text', 'wert': '  ~~~~\n~~~\n```'}}})

    def test_rundlauf_verlaengerter_zaun_abgeschnittene_antwort(self):
        antwort = 'Anfang\n```html\n<html>offen\n  ~~~~~\n'
        prompts.antwort_schreiben(self.datei, antwort)
        b = prompts.beleg_lesen(self.datei)
        self.assertEqual(b['antwort'], antwort)
        self.assertEqual(b['fassung_text'], 'Fassung')
        self.assertEqual(b['eingaben']['felder']['A']['wert'], '  ~~~~\n~~~\n```')
        self.assertTrue(all(k['geschlossen'] for k in prompts.bloecke(Path(self.datei).read_text(encoding='utf-8'))))

    def test_offener_oder_leerer_antwortblock_ist_keine_antwort(self):
        roh = Path(self.datei).read_text(encoding='utf-8')
        for antwort in ('', '## Antwort\n~~~text\noffen', '## Antwort\n~~~text\n\n~~~\n'):
            Path(self.datei).write_text(roh + antwort, encoding='utf-8')
            self.assertFalse(prompts.beleg_lesen(self.datei)['antwort'].strip())
        for pflicht in ('## Fassung', '## Eingaben'):
            Path(self.datei).write_text(roh.replace(pflicht, '## Entfernt'), encoding='utf-8')
            with self.assertRaises(ValueError):
                prompts.beleg_lesen(self.datei)

    def test_urteil_kopfstand_und_zustand_rest_bytegleich(self):
        roh = Path(self.datei).read_text(encoding='utf-8').replace('\n', '\r\n')
        Path(self.datei).write_bytes(roh.encode('utf-8'))
        b = prompts.beleg_lesen(self.datei)
        vorher = Path(self.datei).read_bytes()
        prompts._kopf_setzen(self.datei, {'urteil': 'gut', 'notiz': 'Notiz\nmit Zeile'}, b['kopf_stand'])
        nachher = Path(self.datei).read_bytes()
        self.assertEqual(vorher.split(b'---\r\n', 2)[2], nachher.split(b'---\r\n', 2)[2])
        self.assertEqual(vorher.replace(b'urteil: offen', b'urteil: gut').replace(
            b'notiz: ""', b'notiz: "Notiz\\nmit Zeile"'), nachher)
        with self.assertRaises(prompts.Konflikt):
            prompts._kopf_setzen(self.datei, {'urteil': 'schwach'}, b['kopf_stand'])
        prompts.beleg_zustand(self.datei, 'fehler', 'Fehler\nText', tokens=123)
        self.assertEqual(nachher.split(b'---\r\n', 2)[2], Path(self.datei).read_bytes().split(b'---\r\n', 2)[2])

    def test_html_groesster_block_und_dokument(self):
        self.assertEqual(prompts.html_erkennen('```html\nklein\n```\n~~~html\nviel größer\n~~~'), 'viel größer')
        self.assertEqual(prompts.html_erkennen('<!DOCTYPE html>\n<html>x</html>'), '<!DOCTYPE html>\n<html>x</html>')
        self.assertEqual(prompts.html_erkennen('<html>x</html>'), '<html>x</html>')
        self.assertEqual(prompts.html_erkennen('```html\noffen'), 'offen')
        self.assertEqual(prompts.html_erkennen('```text\n<html>x</html>\n```'), '')


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.basis = Path(self.tmp.name)
        self.sammlung = self.basis / 'Sammlung.md'
        self.sammlung.write_text('### Wissen\n~~~text\nSuche\n~~~\n', encoding='utf-8')
        self.cfg = {'ordner': str(self.basis / 'Prompts'), 'dateiwurzeln': [str(self.basis)]}
        self.index = prompts.Index(self.cfg, str(self.sammlung))
        self.d = self.index.neu('Hühnerfarm', 'https://example.org', 'html, spiel', 'Baue HTML.')
        self.pfad = Path(self.cfg['ordner']) / self.d['id'] / 'prompt.md'
        self.e = prompts.Eintrag(self.pfad)

    def tearDown(self):
        self.tmp.cleanup()

    def schreiben(self, text):
        with self.pfad.open('w', encoding='utf-8', newline='') as f:
            f.write(text)

    def roh(self):
        with self.pfad.open(encoding='utf-8', newline='') as f:
            return f.read()

class Ablage(Basis):
    def test_anlegen_index_sammlung_suchfelder(self):
        self.index.neu('Videoanalyse', '', 'Video', '[Transkript]\n[Projektkontext]')
        alle = self.index.alle()['eintraege']
        self.assertEqual(len(alle), 3)
        self.assertEqual(sum(d['herkunft'] == 'sammlung' for d in alle), 1)
        self.assertIn('html', self.d['schlagworte'])
        self.assertEqual(self.d['bevorzugt'], 'Fassung 1')
        self.assertEqual(len(list((self.basis / 'Prompts').iterdir())), 2)

    def test_stand_kopfstand_und_neuladen(self):
        alt = self.e.lesen()
        self.e.fassung_speichern('Fassung 1', 'Neu', alt['fassungen'][0]['stand'])
        with self.assertRaises(prompts.Konflikt):
            self.e.fassung_speichern('Fassung 1', 'Alt', alt['fassungen'][0]['stand'])
        self.schreiben(self.roh().replace('# Hühnerfarm', '# Geänderter Titel'))
        with self.assertRaises(prompts.Konflikt):
            self.e.kopf('Titel', '', '', alt['kopf_stand'])
        frisch = self.e.lesen()
        self.e.kopf('Titel', 'Quelle', 'neu', frisch['kopf_stand'])
        self.e.fassung_speichern('Fassung 1', 'Nach Neuladen', self.e.lesen()['fassungen'][0]['stand'])
        self.assertEqual(self.e.lesen()['titel'], 'Titel')

    def test_fremde_notiz_nach_laden_bytegleich_crlf(self):
        self.e.fassung_neu('Zweite', 'Text zwei')
        self.schreiben(self.roh().replace('\n', '\r\n'))
        geladen = self.e.lesen()
        notiz = '\r\nNotiz mit ä, zwei  Leerzeichen.\r\n\r\n'
        self.schreiben(self.roh().replace('#### Zweite', notiz + '#### Zweite'))
        vorher = self.pfad.read_bytes()
        f = geladen['fassungen'][0]
        self.e.fassung_speichern(f['name'], 'Neu\nzweite Zeile', f['stand'])
        nachher = self.pfad.read_bytes()
        self.assertIn(notiz.encode(), nachher)
        self.assertEqual(vorher.split(notiz.encode())[1], nachher.split(notiz.encode())[1])
        self.assertNotIn(b'\n', nachher.replace(b'\r\n', b''))
        self.assertFalse(Path(str(self.pfad) + '.werkstatt.tmp').exists())

    def test_kopf_unbekannte_zeilen_und_notizen_bleiben(self):
        self.schreiben(self.roh().replace('Quelle:', 'Unbekannt: bleibt\nQuelle:') + '\nNotiz\n')
        d = self.e.lesen()
        self.e.kopf('Neu', 'frei', 'Tag', d['kopf_stand'])
        self.assertIn('Unbekannt: bleibt\n', self.roh())
        self.assertTrue(self.roh().endswith('\nNotiz\n'))
        self.e.fassung_neu('Zwei', 'Anderer Text')
        self.e.bevorzugt('Zwei', self.e.lesen()['kopf_stand'])
        self.assertEqual(self.e.lesen()['bevorzugt'], 'Zwei')
        with self.assertRaises(prompts.Konflikt):
            self.e.bevorzugt('Fassung 1', d['kopf_stand'])

    def test_unlesbar_mehrdeutig_und_notizbloecke(self):
        roh = self.roh()
        for zusatz in ('\n~~~text\nzweiter\n~~~\n', '\n~~~python\noffen'):
            self.schreiben(roh + zusatz)
            d = self.e.lesen()
            self.assertEqual(d['fehler'], 'nicht eindeutig lesbar')
            with self.assertRaises(ValueError):
                self.e.fassung_neu('Neu', 'x')
        self.schreiben(roh + '\n```\n#### falsch\n```\n~~~python\n#### auch falsch\n~~~\n')
        self.assertTrue(self.e.lesen()['bearbeitbar'])
        self.schreiben('Kein Titel')
        self.assertEqual(self.index.lesen(self.d['id'])['fehler'], 'nicht lesbar')
        self.pfad.write_bytes(b'\xff')
        self.assertEqual(self.index.lesen(self.d['id'])['fehler'], 'nicht lesbar')

    def test_validierung_und_sammlung_schreibgeschuetzt(self):
        for name in ('a\rb', 'a\tb', 'a\x00b', 'a\u2028#### b', 'a\x85b', 'a' * 61, 'Fassung 1'):
            with self.assertRaises(ValueError):
                self.e.fassung_neu(name, 'x')
        with self.assertRaises(ValueError):
            self.e.kopf('Titel\u2029#### X', '', '', self.e.lesen()['kopf_stand'])
        for text in ('', 'x' * 20001, 'Text\n ~~~\nEnde'):
            with self.assertRaises(ValueError):
                self.e.fassung_neu('Neu', text)
        vorher = self.sammlung.read_bytes()
        with self.assertRaises(ValueError):
            self.index.aktion({'aktion': 'fassung_neu', 'id': 'sammlung:Wissen#1', 'name': 'Neu', 'text': 'x'})
        self.assertEqual(vorher, self.sammlung.read_bytes())

    def test_index_frisch_und_belegkoepfe_nur_lesen(self):
        tests = self.pfad.parent / 'tests'
        tests.mkdir()
        beleg = tests / 'test.md'
        beleg.write_text('---\nerstellt: "2026-11-06"\nfassung: "Fassung 1"\nfassung_stand: '
                         + self.d['fassungen'][0]['stand'] + '\nzustand: fertig\n---\nAntwort', encoding='utf-8')
        vorher = beleg.read_bytes()
        d = self.index.lesen(self.d['id'])
        self.assertTrue(d['getestet'])
        self.assertFalse(d['tests'][0]['geaendert'])
        self.e.fassung_speichern('Fassung 1', 'Andere Fassung', self.d['fassungen'][0]['stand'])
        self.assertTrue(self.index.lesen(self.d['id'])['tests'][0]['geaendert'])
        self.assertEqual(vorher, beleg.read_bytes())
        self.schreiben(self.roh().replace('# Hühnerfarm', '# Editor'))
        self.assertEqual(self.index.lesen(self.d['id'])['titel'], 'Editor')

    def test_pfade_und_junction(self):
        self.assertTrue(prompts.pfad_erlaubt(self.pfad, [self.basis]))
        self.assertFalse(prompts.pfad_erlaubt(str(self.basis) + '-andere\\x', [self.basis]))
        for pfad in ('\\\\?\\C:\\x', '\\\\.\\C:\\x', '\\\\server\\x', str(self.pfad) + ':strom'):
            self.assertFalse(prompts.pfad_erlaubt(pfad, [self.basis]), pfad)
        import _winapi
        with tempfile.TemporaryDirectory() as ausserhalb:
            junction = self.basis / 'Junction'
            _winapi.CreateJunction(ausserhalb, str(junction))
            try:
                self.assertFalse(prompts.pfad_erlaubt(junction / 'neu.md', [self.basis]))
                self.assertTrue(prompts.pfad_erlaubt(Path(ausserhalb) / 'neu.md', [junction]))
            finally:
                os.rmdir(junction)

    def test_schreiben_serialisiert_ueber_instanzgrenzen(self):
        import threading
        fehler = []
        def neu(n):
            try:
                prompts.Eintrag(self.pfad).fassung_neu(f'Parallel {n}', f'Text {n}')
            except Exception as ex:
                fehler.append(ex)
        faeden = [threading.Thread(target=neu, args=(n,)) for n in range(8)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join()
        self.assertEqual(fehler, [])
        self.assertEqual(len(self.e.lesen()['fassungen']), 9)


class Sammlung(Basis):
    def sammlung_setzen(self, texte, titel='Wissen'):
        text = f'### {titel}\n' + ''.join(prompts.block_schreiben(t, 'text') for t in texte)
        self.sammlung.write_text(text, encoding='utf-8')

    def schatten(self, name, text, nummer, anzahl, titel='Wissen'):
        ordner = self.basis / 'Prompts' / '_Sammlung' / name
        ordner.mkdir(parents=True)
        meta = {'ueberschrift': titel, 'nummer': nummer, 'stand': prompts.stand(text),
                'kaesten_vorher': anzahl, 'aktualisiert': ''}
        (ordner / 'eintrag.json').write_text(json.dumps(meta), encoding='utf-8')
        return ordner / 'eintrag.json'

    def test_werkstatt_ausgeschlossen_zaunzustand_nummern(self):
        self.sammlung.write_text('### Vorne\n~~~text\n### innen\n~~~\n~~~text\nZwei\n~~~\n'
                                 + prompts.ABSCHNITT + '\n#### Rahmen\n~~~text\nWerkstatt\n~~~\n'
                                 '### Danach\n```\n### falscher Kopf\n```\n~~~text\nEnde\n~~~\n', encoding='utf-8')
        kaesten = prompts.sammlung_kaesten(self.sammlung)
        self.assertEqual([k['id'] for k in kaesten], ['sammlung:Vorne#1', 'sammlung:Vorne#2', 'sammlung:Danach#1'])
        self.assertEqual(kaesten[1]['titel'], 'Vorne (Kasten 2)')

    def test_nummer_verschoben_ueber_stand(self):
        self.sammlung_setzen(['A', 'B'])
        meta = self.schatten('B', 'B', 2, 2)
        self.sammlung_setzen(['Neu', 'A', 'B'])
        d = self.index.lesen('sammlung:Wissen#3')
        self.assertEqual(d['schatten'], 'B')
        self.assertEqual(json.loads(meta.read_text())['nummer'], 3)
        self.assertEqual(json.loads(meta.read_text())['kaesten_vorher'], 2)

    def test_einkasten_bearbeitet(self):
        self.schatten('A', 'Alt', 1, 1)
        self.sammlung_setzen(['Neu'])
        self.assertEqual(self.index.lesen('sammlung:Wissen#1')['hinweis'], 'seit dem Test geändert')

    def test_mehrkaesten_unklar_und_manuelle_zuordnung(self):
        meta = self.schatten('B', 'B', 2, 2)
        self.sammlung_setzen(['Davor', 'A', 'Bearbeitet'])
        d = self.index.lesen('schatten:B')
        self.assertEqual(d['fehler'], 'Zuordnung ungeklärt')
        self.assertEqual(len(d['kandidaten']), 3)
        vorher = self.sammlung.read_bytes()
        self.index.zuordnen('schatten:B', 'sammlung:Wissen#3')
        m = json.loads(meta.read_text())
        self.assertEqual((m['stand'], m['kaesten_vorher'], m['nummer']), (prompts.stand('Bearbeitet'), 3, 3))
        self.assertEqual(self.index.lesen('sammlung:Wissen#3')['schatten'], 'B')
        self.assertEqual(vorher, self.sammlung.read_bytes())

    def test_a_geloescht_nie_b_zuweisen(self):
        self.schatten('A', 'A', 1, 2)
        self.schatten('B', 'B', 2, 2)
        self.sammlung_setzen(['B'])
        self.assertEqual(self.index.lesen('sammlung:Wissen#1')['schatten'], 'B')
        self.assertEqual(self.index.lesen('schatten:A')['fehler'], 'Zuordnung ungeklärt')

    def test_ueberschrift_geloescht_und_kollision(self):
        self.schatten('A', 'Suche', 1, 1)
        self.schatten('B', 'Suche', 1, 1)
        self.assertEqual(self.index.lesen('schatten:A')['fehler'], 'Zuordnung ungeklärt')
        self.assertEqual(self.index.lesen('schatten:B')['fehler'], 'Zuordnung ungeklärt')
        self.sammlung_setzen([], 'Andere Überschrift')
        self.assertEqual(self.index.lesen('schatten:A')['fehler'], 'Sammlungseintrag nicht mehr gefunden')


class Oberflaeche(unittest.TestCase):
    def test_testdialog_nochmal_vorschau_start_ablegen_und_markdown(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node für den JavaScript-Bedientest nicht vorhanden.')
        skript = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.textContent = ''; this.events = {}; this.dataset = {}; this.classList = {add() {}, remove() {}}; }
  append(...k) { this.children.push(...k); }
  replaceChildren(...k) { this.children = k; }
  setAttribute(k, v) { this[k] = v; }
  addEventListener(k, f) { this.events[k] = f; }
  focus() {}
  remove() { this.entfernt = true; }
  querySelector() { return null; }
  insertBefore(kind, vor) { this.children.splice(vor ? this.children.indexOf(vor) : this.children.length, 0, kind); }
}
const ids = new Map(), anfragen = [];
const document = {
  querySelector: (s) => { if (!ids.has(s)) ids.set(s, new Element('div')); return ids.get(s); },
  createElement: (t) => new Element(t),
  events: {}, addEventListener(art, fn) { this.events[art] = fn; },
};
const e = {id: 'Test', titel: 'Test', herkunft: 'ordner', tests: [], fassungen: [
  {name: 'Eins', text: 'Test [A] [B] [red, blue]'}, {name: 'Zwei', text: 'Test [A]'}], bevorzugt: 'Zwei'};
const beleg = {fassung: 'Eins', auswerter: 'Fake', rahmen: 'ja', hinweise: {B: 'Datei seit dem Test geändert.'},
  eingaben: {felder: {A: {art: 'text', wert: 'Alt'}, B: {art: 'datei', pfad: 'C:/feld.txt', wert: 'Datei alt'},
    'red, blue': {art: 'woertlich'}}}};
const kontext = vm.createContext({document, window: {}, console,
  localStorage: {getItem() { return '["p"]'; }, setItem() {}}, aktualisieren() {},
  fehlerMelden(t) { throw Error(t); },
  fetch: async (pfad, opt) => {
    const d = opt?.body ? JSON.parse(opt.body) : null; anfragen.push([pfad, d]);
    let wert;
    if (pfad === '/api/zusammenfassung') wert = {auswerter: [
      {id: 'p', name: 'Fake', verfuegbar: true}, {id: 'aus', name: 'Aus', verfuegbar: false, grund: 'Nicht geladen'}]};
    else if (d?.aktion === 'vorschau') wert = {leer: 0, fassungen: [{name: 'Eins', auftrag: '<html>nur Text</html>',
      gesendet_stand: 'hash', auswerter: [{modell: 'Fake', verarbeitung: 'lokal', geschaetzt: 200, kontext: 128000,
        kontext_quelle: '/health', hinweis: ''}]}]};
    else if (d?.aktion === 'testen') wert = {neu: 1};
    else if (pfad === '/api/prompts') wert = {eintraege: [], fehler: []};
    else if (d?.aktion === 'datei_waehlen') wert = {art: 'datei', pfad: 'C:/neu.txt', wert: 'Neue Datei'};
    else if (pfad === '/api/transkripte?prompts=1') wert = [{titel: 'Film', datei: 'C:/watch/transcript-timestamps.txt', zeichen: 123, sha: 'sha'}];
    else throw Error('Unerwartete Anfrage: ' + pfad + ' ' + JSON.stringify(d));
    return {ok: true, json: async () => wert};
  },
});
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
vm.runInContext(app.split('let STAND =')[0], kontext);
vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), kontext);
const zf = fs.readFileSync('werkstatt/web/zusammenfassung.js', 'utf8');
vm.runInContext(zf.slice(zf.indexOf('function markdown('), zf.indexOf('// ------------------------------------------------------------------ Transkripte')), kontext);
vm.runInContext(`function dialogOeffnen(titel, inhalt, knoepfe) {
  const d = {titel, children: [...inhalt, ...knoepfe], close() { this.geschlossen = true; }};
  window.dialog = d; return d;
}`, kontext);
vm.runInContext(fs.readFileSync('werkstatt/web/prompts.js', 'utf8'), kontext);
function alle(e) { return [e, ...e.children.flatMap((k) => k && typeof k === 'object' ? alle(k) : [])]; }
function knopf(text, wurzel = kontext.window.dialog) { return alle(wurzel).find((k) => k.children?.includes(text)); }
async function klicken(b) { assert(b); await b.events.click({currentTarget: b}); }
kontext.e = e; kontext.beleg = beleg;
(async () => {
  const md = vm.runInContext('markdown("Vorher\\n```html\\n  <script>**roh**</script>  \\n\\n```\\nNachher")', kontext);
  assert(md.includes('<pre><code>  &lt;script&gt;**roh**&lt;/script&gt;  \n\n</code></pre>'));
  assert(!md.includes('<script>'));
  assert(vm.runInContext('markdown("~~~\\n  offen  ")', kontext).includes('  offen  </code>'));
  await vm.runInContext('pTestdialog(e, null)', kontext);
  let d = kontext.window.dialog;
  assert(alle(d).some((k) => k.children?.includes('Zwei') && k.children[0].checked));
  assert(alle(d).some((k) => k.disabled && k.type === 'checkbox'));
  assert(alle(d).find((k) => k.children?.includes('Rahmen der Zusammenfassung voranstellen')).children[0].checked === false);
  await vm.runInContext('pTestdialog(e, "Eins", beleg)', kontext);
  d = kontext.window.dialog;
  let a = alle(d).find((k) => k['data-prompt-feld'] === 'A');
  let b = alle(d).find((k) => k['data-prompt-feld'] === 'B');
  assert.equal(a.value, 'Alt'); assert.equal(b.value, 'Datei alt');
  assert(alle(d).some((k) => k.textContent === 'Datei seit dem Test geändert.'));
  assert(alle(d).find((k) => k['data-prompt-feld'] === 'red, blue').promptEingabe.woertlich.checked);
  await klicken(knopf('Vorschau berechnen'));
  const pre = alle(d).find((k) => k.tag === 'pre'); assert.equal(pre.textContent, '<html>nur Text</html>');
  a.value = 'Geändert'; a.events.input();
  await klicken(knopf('Start'));
  assert(!anfragen.some(([, d]) => d?.aktion === 'testen'));
  kontext.dropE = {dataTransfer: {files: [{name: 'gezogen.txt', text: async () => 'Gezogener Inhalt'}]}};
  kontext.feld = a;
  await vm.runInContext('window.promptsAblegen(dropE, feld)', kontext);
  assert.equal(a.promptEingabe.quelle.name, 'gezogen.txt');
  await klicken(knopf('Vorschau berechnen'));
  await klicken(knopf('Start'));
  assert(d.geschlossen);
  const gesendet = anfragen.find(([, d]) => d?.aktion === 'testen')[1];
  assert.equal(gesendet.eingaben.felder.A.art, 'text');
  assert.equal(gesendet.eingaben.felder.A.wert, 'Gezogener Inhalt');
  assert.equal(gesendet.gesendet_stand.Eins, 'hash');
  await vm.runInContext('pTestdialog(e, "Eins")', kontext);
  await klicken(knopf('Aus Datei …'));
  assert.equal(alle(kontext.window.dialog).find((k) => k['data-prompt-feld'] === 'A').value, 'Neue Datei');
  await klicken(knopf('Aus Transkript …'));
  await klicken(knopf('Film · 123 Zeichen'));
  assert.equal(alle(kontext.window.dialog).find((k) => k['data-prompt-feld'] === 'A').promptEingabe.quelle.art, 'transkript');
  // Der zentrale Drop-Handler bleibt im Reiter Prompts und räumt das Overlay auf.
  vm.runInContext(app.slice(app.indexOf('function einrichtenAblegen()'), app.indexOf('// ------------------------------------------------------------------ Kopf')), kontext);
  vm.runInContext('einrichtenAblegen()', kontext);
  let abgelegt = false;
  kontext.window.promptsAblegen = (ev, feld) => { abgelegt = feld === a; };
  document.querySelector('#reiter-prompts').hidden = false;
  document.querySelector('#ueberall').hidden = false;
  document.events.drop({preventDefault() {}, target: {closest() { return a; }}, dataTransfer: {types: ['Files']}});
  assert(abgelegt); assert(document.querySelector('#ueberall').hidden);
  // Acht alte Zusammenfassungen ohne art bleiben sichtbar; Promptläufe werden ausgefiltert.
  vm.runInContext(`const ZF = {gewaehlt: {ordner: 'Film'}, zeilen: new Map(), stand: {auswertungen:
    Array.from({length: 8}, (_, i) => ({id: String(i), ordner: 'Film', zustand: 'fertig',
      anweisung: {name: 'Alt'}, auswerter: {name: 'Fake'}})).concat([{id: 'prompt', art: 'prompt', ordner: 'Film'}])}};
    function fassungStatus() { return 'fertig'; }
    function fassungKnoepfe() { return []; }
    function fassungText(f) { (window.gezeigt ||= []).push(f.id); }`, kontext);
  vm.runInContext(zf.slice(zf.indexOf('function fassungenZeichnen()'), zf.indexOf('function zfZeichnen()')), kontext);
  vm.runInContext('fassungenZeichnen()', kontext);
  assert.equal(kontext.window.gezeigt.length, 8);
  assert(!kontext.window.gezeigt.includes('prompt'));
})().catch((e) => { console.error(e); process.exitCode = 1; });
'''
        lauf = subprocess.run([node, '-'], input=skript, text=True, encoding='utf-8', capture_output=True,
                              cwd=Path(__file__).resolve().parents[2], timeout=15)
        self.assertEqual(lauf.returncode, 0, lauf.stdout + lauf.stderr)

    def test_laden_suche_filter_und_fassungstext(self):
        """Echtes prompts.js mit app.js-Hilfen gegen ein kleines DOM und Fake-HTTP."""
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node für den JavaScript-Bedientest nicht vorhanden.')
        skript = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.textContent = ''; this.scrollTop = 0; this.scrollLeft = 0; }
  append(...k) { this.children.push(...k); }
  replaceChildren(...k) {
    this.children = k; this.scrollTop = 0; this.scrollLeft = 0;
    if (this === ids.get('#p-inhalt')) fenster.scrollY = 0;
  }
  setAttribute(k, v) { this[k] = v; }
  getAttribute(k) { return this[k] ?? null; }
  addEventListener(k, f) { (this.events ||= {})[k] = f; }
  nachkommen() { return this.children.filter((k) => k && typeof k === 'object').flatMap((k) => [k, ...k.nachkommen()]); }
  querySelectorAll(s) { return this.nachkommen().filter((k) => s !== 'details[data-p-ansicht]'
    || (k.tag === 'details' && k['data-p-ansicht'] != null)); }
  querySelector(s) { return this.nachkommen().find((k) => s === '.f-text' && k.className === 'f-text') || null; }
}
const ids = new Map();
let dialogOffen = false, jetzt = 0, schlange = [];
const zeitgeber = [];
const fenster = {scrollX: 0, scrollY: 0, scrollTo(p) { this.scrollX = p.left; this.scrollY = p.top; }};
const document = {
  querySelector: (s) => {
    if (s === 'dialog[open]') return dialogOffen ? new Element('dialog') : null;
    if (!ids.has(s)) ids.set(s, new Element('div')); return ids.get(s);
  },
  createElement: (t) => new Element(t),
};
const eintraege = [
  {id: 'Hühnerfarm', titel: 'Hühnerfarm', quelle: 'https://example.org', schlagworte: 'HTML',
   herkunft: 'ordner', bearbeitbar: true, bevorzugt: 'Fassung 1', tests: [], getestet: false,
   fassungen: [{name: 'Fassung 1', stand: '123', text: '<script>unverändert</script>\n' + 'Zeile\n'.repeat(21)}]},
  {id: 'Video', titel: 'Videoanalyse', herkunft: 'ordner', tests: [], getestet: false,
   fassungen: [{name: 'Fassung 1', stand: '456', text: '[Transkript]\n[Projektkontext]'}]},
  {id: 'sammlung:Wissen#1', titel: 'Wissen', herkunft: 'sammlung', tests: [], getestet: false,
   fassungen: [{name: 'Sammlung', stand: '789', text: 'Suche'}]},
];
let anfragen = [];
const kontext = vm.createContext({document, window: fenster, console,
  Date: class extends Date { static now() { return jetzt; } },
  setTimeout(fn, ms) { zeitgeber.push({fn, ms}); return zeitgeber.length; },
  markdown: (text) => text,
  fetch: async (pfad) => {
    anfragen.push(pfad);
    if (pfad === '/api/prompts') return {ok: true, json: async () => JSON.parse(JSON.stringify({eintraege, fehler: [], warteschlange: schlange}))};
    if (pfad.startsWith('/api/prompt?id=')) return {ok: true,
      json: async () => JSON.parse(JSON.stringify(eintraege.find((e) => e.id === decodeURIComponent(pfad.split('=')[1]))))};
    throw Error('Unerwartete Anfrage: ' + pfad);
  }, aktualisieren() {}, fehlerMelden(t) { throw Error(t); },
});
const app = fs.readFileSync('werkstatt/web/app.js', 'utf8');
vm.runInContext(app.split('let STAND =')[0], kontext);
vm.runInContext(app.slice(app.indexOf('function knopf('), app.indexOf('const auftrag =')), kontext);
vm.runInContext(app.slice(app.indexOf('const ZUSTAND ='), app.indexOf('function schrittListe(')), kontext);
vm.runInContext(fs.readFileSync('werkstatt/web/prompts.js', 'utf8'), kontext);
function elemente(e, tag) { return [e, ...e.children.flatMap((k) => typeof k === 'object' ? elemente(k, tag) : [])]
  .filter((k) => k.tag === tag); }
(async () => {
  await vm.runInContext('pLaden()', kontext);
  assert.equal(ids.get('#p-liste').children.length, 3);
  assert.equal(ids.get('#p-rueck').textContent, '');
  ids.get('#p-suche').value = 'html';
  vm.runInContext('pListe()', kontext);
  assert.equal(ids.get('#p-liste').children.length, 1);
  ids.get('#p-suche').value = '';
  ids.get('#p-herkunft').value = 'sammlung';
  vm.runInContext('pListe()', kontext);
  assert.equal(ids.get('#p-liste').children.length, 1);
  assert.equal(elemente(ids.get('#p-liste'), 'strong')[0].textContent, 'Wissen');
  ids.get('#p-herkunft').value = '';
  ids.get('#p-status').value = 'getestet';
  vm.runInContext('pListe()', kontext);
  assert.equal(ids.get('#p-liste').children[0].textContent, 'Keine passenden Prompts.');
  ids.get('#p-status').value = '';
  await vm.runInContext("pWaehlen('Hühnerfarm')", kontext);
  assert.equal(elemente(ids.get('#p-inhalt'), 'pre')[0].textContent, eintraege[0].fassungen[0].text);
  assert.equal(elemente(ids.get('#p-inhalt'), 'details').length, 1);
  assert.equal(ids.get('#p-rueck').textContent, '');
  assert.equal(anfragen.length, 2);
  // Gleiche JSON-Daten erhalten die tatsächlichen Knoten und offene Kästen.
  const box = ids.get('#p-inhalt'), liste = ids.get('#p-liste');
  let vorher = [...box.children], listenknoten = [...liste.children];
  elemente(box, 'details')[0].open = true;
  await vm.runInContext('pLaden();', kontext);
  await vm.runInContext('pLaden();', kontext);
  assert(box.children.every((k, i) => k === vorher[i]));
  assert(liste.children.every((k, i) => k === listenknoten[i]));
  assert(elemente(box, 'details')[0].open);
  // Auch Antworten bleiben offen; beim echten Neuzeichnen werden sie anhand der Datei zugeordnet.
  eintraege[0].tests = [{datei: 'Beleg.md', fassung: 'Fassung 1', auswerter: 'Fake', zustand: 'laeuft',
    urteil: 'gut', notiz: '', kopf_stand: 'stand'}];
  eintraege[0].warteschlange = [{id: 'lauf', prompt: {eintrag: 'Hühnerfarm', fassung: 'Fassung 1', beleg: 'Beleg'},
    auswerter: {name: 'Fake'}, zustand: 'laeuft', meldung: '', sekunden: 1}];
  await vm.runInContext('pLaden()', kontext);
  let antwort = elemente(box, 'details').find((k) => k['data-p-ansicht'] === '["Beleg.md","antwort"]');
  antwort.open = true;
  antwort.querySelector('.f-text').innerHTML = 'Vorhandene Antwort';
  vorher = [...box.children];
  await vm.runInContext('pLaden()', kontext);
  assert(box.children.every((k, i) => k === vorher[i]));
  assert(antwort.open);
  eintraege[0].warteschlange[0].sekunden = 2;
  await vm.runInContext('pLaden()', kontext);
  assert(box.children.every((k, i) => k === vorher[i]), 'Nicht angezeigte Sekunden dürfen kein Neuzeichnen auslösen');
  box.scrollTop = 123; box.scrollLeft = 12; liste.scrollTop = 234; fenster.scrollY = 456;
  eintraege[0].tests[0].tokens = 42;
  await vm.runInContext('pLaden()', kontext);
  assert.notStrictEqual(box.children[0], vorher[0]);
  antwort = elemente(box, 'details').find((k) => k['data-p-ansicht'] === '["Beleg.md","antwort"]');
  assert(antwort.open); assert.equal(antwort.querySelector('.f-text').innerHTML, 'Vorhandene Antwort');
  assert.equal(box.scrollTop, 123); assert.equal(box.scrollLeft, 12);
  assert.equal(liste.scrollTop, 234); assert.equal(fenster.scrollY, 456);
  // Nutzertexte in Beleg und Warteschlange stammen aus ZUSTAND.
  for (const [roh, deutsch] of Object.entries({wartet: 'Wartet', laeuft: 'Läuft', fertig: 'Fertig',
      fehler: 'Fehlgeschlagen', abgebrochen: 'Abgebrochen'})) {
    eintraege[0].tests[0].zustand = roh;
    eintraege[0].warteschlange[0].zustand = roh;
    await vm.runInContext('pLaden()', kontext);
    const texte = elemente(box, 'p').map((k) => k.textContent);
    assert(texte.some((t) => t.includes(deutsch) && t.includes('Urteil: gut')));
    if (roh !== 'fertig') assert(texte.some((t) => t.startsWith('Fassung 1 · Fake · ' + deutsch)));
    assert(!texte.some((t) => t.split(' · ').includes(roh)));
  }
  // Im Leerlauf nur alle 30 s, mit aktiver Warteschlange oder aktivem Beleg alle 2,5 s.
  vm.runInContext('window.promptsAktiv(true)', kontext);
  await new Promise(setImmediate);
  let anzahl = anfragen.length;
  jetzt = 2500; await zeitgeber.shift().fn(); assert.equal(anfragen.length, anzahl);
  jetzt = 30000; await zeitgeber.shift().fn(); assert.equal(anfragen.length, anzahl + 2);
  schlange = [{zustand: 'wartet'}]; await vm.runInContext('pLaden()', kontext);
  anzahl = anfragen.length; jetzt = 32500; await zeitgeber.shift().fn(); assert.equal(anfragen.length, anzahl + 2);
  schlange = []; eintraege[0].tests[0].zustand = 'laeuft'; await vm.runInContext('pLaden()', kontext);
  anzahl = anfragen.length; jetzt = 35000; await zeitgeber.shift().fn(); assert.equal(anfragen.length, anzahl + 2);
  // Dialog und fokussiertes Textfeld schützen auch direkte Neuladeaufrufe.
  vorher = [...box.children]; dialogOffen = true;
  anzahl = anfragen.length; jetzt = 70000; await zeitgeber.shift().fn();
  await vm.runInContext('pLaden(); pListe(); pWaehlen("Video");', kontext);
  assert.equal(anfragen.length, anzahl); assert(box.children.every((k, i) => k === vorher[i]));
  assert(antwort.open);
  dialogOffen = false; document.activeElement = {matches() { return true; }};
  await vm.runInContext('pLaden(); pListe(); pWaehlen("Video");', kontext);
  assert.equal(anfragen.length, anzahl); assert(box.children.every((k, i) => k === vorher[i]));
})().catch((e) => { console.error(e); process.exitCode = 1; });
'''
        lauf = subprocess.run([node, '-'], input=skript, text=True, encoding='utf-8',
                              capture_output=True, cwd=Path(__file__).resolve().parents[2], timeout=15)
        self.assertEqual(lauf.returncode, 0, lauf.stdout + lauf.stderr)


if __name__ == '__main__':
    unittest.main()
