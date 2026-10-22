import copy
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import texterkennung as te  # noqa: E402

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASIS, 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)
with open(os.path.join(os.path.dirname(BASIS), 'zentrale', 'config.json'), encoding='utf-8') as f:
    ZKONFIG = json.load(f)


class Seiten(unittest.TestCase):
    def test_seiten_lesen(self):
        self.assertEqual(te.seiten_lesen('', 3), [1, 2, 3])
        self.assertEqual(te.seiten_lesen('1-3, 7; 2', 9), [1, 2, 3, 7])
        self.assertEqual(te.seiten_lesen('4–5', 9), [4, 5])
        for falsch, text in (('0', 'gültige'), ('5-3', 'gültige'), ('a', 'keine Seitenangabe'), ('10', 'Seite 10 gibt es nicht')):
            with self.subTest(falsch=falsch), self.assertRaisesRegex(ValueError, text):
                te.seiten_lesen(falsch, 9)

    def test_seiten_text(self):
        self.assertEqual(te.seiten_text([1, 2, 3, 7, 9, 10]), '1–3, 7, 9–10')
        self.assertEqual(te.seiten_text([4]), '4')


class Ablauf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = copy.deepcopy(KONFIG)
        self.cfg['texterkennung']['ausgabe_ordner'] = os.path.join(self.tmp, 'Texterkennung')
        self.pdf = os.path.join(self.tmp, 'Befund Knie.pdf')
        with open(self.pdf, 'wb') as f:
            f.write(b'%PDF-1.7 Test')
        self.zentrale = mock.Mock()
        self.zentrale.stand.return_value = (200, {'gruende': [], 'karten': []})
        self.zentrale.status.return_value = {'stand': {'eintraege': {
            'lightonocr': {'zustand': 'bereit', 'karte': 'RTX 3090'}}}}
        with mock.patch('threading.Thread'):
            self.t = te.Texterkennung(self.cfg, ZKONFIG, os.path.join(self.tmp, 'daten'), lambda text: None,
                                      self.zentrale)
        self.seiten_pdf = 3
        self.hilfe_aufrufe = []
        p = mock.patch('werkstatt.texterkennung.subprocess.run', side_effect=self._hilfe)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch('werkstatt.texterkennung.winapi.lauschende_ports', return_value=[('127.0.0.1', 8096, 1)])
        self.ports = p.start()
        self.addCleanup(p.stop)
        self.anfragen = []
        self.antworten = {}
        p = mock.patch.object(te._OHNE_PROXY, 'open', side_effect=self._http)
        p.start()
        self.addCleanup(p.stop)

    def _hilfe(self, argv, **kw):
        self.hilfe_aufrufe.append(argv)
        self.assertEqual(argv[:3], [self.cfg['texterkennung']['pdf_python'], '-I', te.HILFE])
        if argv[3] == 'info':
            aus = json.dumps({'seiten': self.seiten_pdf, 'art': 'pdf'})
        else:
            aus = '\n'.join(json.dumps({'seite': int(n), 'breite': 1448, 'hoehe': 2048, 'mime': 'image/png',
                                        'daten': 'QUJD'}) for n in argv[5:-2])
        return mock.Mock(returncode=0, stdout=aus.encode(), stderr=b'')

    def _http(self, anfrage, timeout=None):
        url = anfrage if isinstance(anfrage, str) else anfrage.full_url
        if url.endswith('/v1/models'):
            return io.BytesIO(json.dumps({'data': [{'id': 'lightonocr-3-4b'}]}).encode())
        daten = json.loads(anfrage.data)
        self.anfragen.append(daten)
        n = len(self.anfragen)
        ende = self.antworten.get(n, 'stop')
        if isinstance(ende, Exception):
            raise ende
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': f'# Text {n}\n'},
                                                   'finish_reason': ende}]}).encode())

    def _auftrag(self, seiten=''):
        code, e = self.t.hinzufuegen({'text': self.pdf, 'seiten': seiten})
        self.assertEqual((code, e['neu']), (200, 1))
        a = self.t._naechster()
        self.t._ausfuehren(a)
        return a

    def test_ganzes_pdf_markdown_je_seite_volltext_und_lauf(self):
        a = self._auftrag()
        self.assertEqual(a['zustand'], 'fertig', a['meldung'])
        self.assertEqual(a['ordner'], os.path.join(self.cfg['texterkennung']['ausgabe_ordner'], 'Befund Knie'))
        self.assertEqual(sorted(os.listdir(a['ordner'])),
                         ['Seite 001.md', 'Seite 002.md', 'Seite 003.md', 'Volltext.md', 'lauf.json'])
        with open(a['volltext'], encoding='utf-8') as f:
            voll = f.read()
        self.assertTrue(voll.startswith('---\nquelle: '))
        self.assertIn('seiten: "1–3"\n', voll)
        self.assertIn('status: automatisch erkannt, nicht geprüft', voll)
        self.assertIn('## Seite 1\n\n# Text 1\n', voll)
        self.assertIn('## Seite 3\n\n# Text 3\n', voll)
        lauf = te._json_lesen(os.path.join(a['ordner'], 'lauf.json'))
        self.assertEqual((lauf['zustand'], lauf['seiten'], lauf['fertig']), ('fertig', [1, 2, 3], 3))
        self.assertEqual(set(lauf['je_seite']), {'1', '2', '3'})
        self.assertIsNone(a['hinweis'])
        self.assertIn('Stichproben', self.t.stand()['hinweis_pruefen'])
        # Anfrage wie Modellkarte: nur das Bild, kein Text; Thinking aus, feste Abtastung.
        d = self.anfragen[0]
        self.assertEqual(d['messages'][0]['content'],
                         [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,QUJD'}}])
        self.assertEqual((d['model'], d['temperature'], d['top_p'], d['max_tokens'], d['seed']),
                         ('lightonocr-3-4b', 0.2, 0.9, 4096, 1))
        self.assertEqual(d['chat_template_kwargs'], {'enable_thinking': False})
        self.assertIn('--kante', self.hilfe_aufrufe[1])

    def test_seitenwahl_und_stapel(self):
        self.seiten_pdf = 12
        a = self._auftrag('2-7, 10')
        self.assertEqual(a['zustand'], 'fertig', a['meldung'])
        seiten_aufrufe = [x[5:-2] for x in self.hilfe_aufrufe if x[3] == 'seiten']
        self.assertEqual(seiten_aufrufe, [['2', '3', '4', '5'], ['6', '7', '10']])
        with open(a['volltext'], encoding='utf-8') as f:
            self.assertIn('seiten: "2–7, 10" # von 12\n', f.read())

    def test_ohne_modell_kein_ordner(self):
        self.ports.return_value = []
        a = self._auftrag()
        self.assertEqual(a['zustand'], 'fehler')
        self.assertIn('Bitte in der Modellzentrale starten', a['meldung'])
        self.assertFalse(os.path.exists(self.cfg['texterkennung']['ausgabe_ordner']))
        self.assertEqual(self.anfragen, [])

    def test_fehler_mittendrin_und_fortsetzen(self):
        import urllib.error
        self.antworten[2] = urllib.error.URLError('weg')
        a = self._auftrag()
        self.assertEqual(a['zustand'], 'fehler')
        self.assertEqual(a['fertig'], [1])
        lauf = te._json_lesen(os.path.join(a['ordner'], 'lauf.json'))
        self.assertEqual(lauf['zustand'], 'unvollstaendig')
        self.assertFalse(os.path.exists(os.path.join(a['ordner'], 'Volltext.md')))
        ordner = a['ordner']
        self.assertEqual(self.t.aktion(a['id'], 'wiederholen')[0], 200)
        self.t._ausfuehren(self.t._naechster())
        self.assertEqual(a['zustand'], 'fertig', a['meldung'])
        self.assertEqual(a['ordner'], ordner)
        # Seite 1 wurde nicht noch einmal gelesen: 1 + (fehlgeschlagene 2) + 2 + 3
        self.assertEqual(len(self.anfragen), 4)
        self.assertEqual(sorted(a['fertig']), [1, 2, 3])

    def test_abgeschnittene_seite_wird_vermerkt(self):
        self.antworten[2] = 'length'
        a = self._auftrag()
        self.assertEqual(a['abgeschnitten'], [2])
        self.assertIn('Seite 2 an der Längengrenze abgeschnitten', a['meldung'])
        with open(a['volltext'], encoding='utf-8') as f:
            self.assertIn('Die Seite wurde an der Längengrenze abgeschnitten', f.read())

    def test_wartet_auf_gruende_der_zentrale(self):
        antworten = [(200, {'gruende': ['Die Modellzentrale ist gerade beschäftigt: Ornith wird geladen']}),
                     (200, {'gruende': []})]
        self.zentrale.stand.side_effect = lambda: antworten.pop(0) if antworten else (200, {'gruende': []})
        meldungen = []
        with mock.patch.object(self.t, '_warten', side_effect=lambda a, s: meldungen.append(a['meldung'])):
            a = self._auftrag()
        self.assertEqual(a['zustand'], 'fertig', a['meldung'])
        self.assertEqual(meldungen, ['Wartet: Die Modellzentrale ist gerade beschäftigt: Ornith wird geladen'])

    def test_liest_neben_comfyui_ohne_gpu_sperre(self):
        # Seit 16.10.2026 keine gemeinsame GPU-Sperre: LightOnOCR ist geladen, ein ComfyUI-Auftrag hält es nicht auf.
        self.zentrale.stand.return_value = (200, {'gruende': ['In ComfyUI läuft gerade ein Auftrag.']})
        self.assertFalse(hasattr(self.t, 'gpu_sperre'))
        with mock.patch.object(self.t, '_warten', side_effect=AssertionError('Darf nicht warten')):
            a = self._auftrag()
        self.assertEqual(a['zustand'], 'fertig', a['meldung'])

    def test_aufnehmen_ordner_doppelt_und_fremdes(self):
        bild = os.path.join(self.tmp, 'scan.JPG')
        text = os.path.join(self.tmp, 'notiz.txt')
        for p in (bild, text):
            open(p, 'wb').close()
        code, e = self.t.hinzufuegen({'text': f'"{self.tmp}"\n{text}\nC:\\gibt\\es\\nicht.pdf'})
        self.assertEqual(e['neu'], 2)
        self.assertEqual([x['neu'] for x in e['auftraege']], [True, True])
        self.assertTrue(any('Kein PDF oder Bild' in f and 'notiz.txt' in f for f in e['fehler']))
        self.assertTrue(any('nicht gefunden' in f for f in e['fehler']))
        pdf_id = next(x['id'] for x in e['auftraege'] if x['quelle'] == self.pdf)
        code, e = self.t.hinzufuegen({'text': self.pdf})
        self.assertEqual((e['neu'], e['doppelt']), (0, ['Befund Knie.pdf']))
        # Skripte bekommen auch beim Doppelten die ID des offenen Auftrags, um darauf zu warten.
        self.assertEqual(e['auftraege'], [{'id': pdf_id, 'quelle': self.pdf, 'neu': False}])
        code, e = self.t.hinzufuegen({'text': bild, 'seiten': 'x'})
        self.assertEqual(e['neu'], 0)
        self.assertIn('keine Seitenangabe', e['fehler'][0])

    def test_oeffnen_nur_im_ausgabeordner(self):
        code, e = self.t.hinzufuegen({'text': self.pdf})
        a = self.t.auftraege[0]
        a['ordner'] = self.tmp  # liegt nicht in Arbeitsmaterial\Texterkennung
        with mock.patch('werkstatt.texterkennung.os.startfile', create=True) as starten:
            self.assertEqual(self.t.aktion(a['id'], 'ordner')[0], 404)
        starten.assert_not_called()

    def test_stand_zeigt_zaehler_und_modell(self):
        self._auftrag()
        s = self.t.stand()
        self.assertEqual((s['auftraege'][0]['fertig'], s['auftraege'][0]['seiten']), (3, 3))
        self.assertTrue(s['modell']['bereit'])
        self.assertEqual(s['modell']['karte'], 'RTX 3090')
        self.assertEqual(s['modell']['karten'], 'auf einer RTX 3080 oder RTX 3090')
        self.assertEqual(self.t.aufraeumen()[0], 200)
        self.assertEqual(self.t.stand()['auftraege'], [])
        self.assertTrue(os.path.isdir(os.path.join(self.cfg['texterkennung']['ausgabe_ordner'], 'Befund Knie')))

    def test_nicht_bereit_zeigt_keine_karte_nur_wunschtext(self):
        self.ports.return_value = []
        m = self.t.stand()['modell']
        self.assertFalse(m['bereit'])
        self.assertIsNone(m['karte'])
        self.assertEqual(m['karten'], 'auf einer RTX 3080 oder RTX 3090')
        self.zentrale.status.assert_not_called()

    def test_karte_hoechstens_alle_fuenf_sekunden_und_fehler(self):
        with mock.patch('werkstatt.texterkennung.time.time', return_value=100) as zeit:
            self.assertEqual(self.t.stand()['modell']['karte'], 'RTX 3090')
            self.zentrale.status.return_value['stand']['eintraege']['lightonocr']['karte'] = 'RTX 3080'
            zeit.return_value = 104.9
            self.assertEqual(self.t.stand()['modell']['karte'], 'RTX 3090')
            self.assertEqual(self.zentrale.status.call_count, 1)
            zeit.return_value = 105
            self.assertEqual(self.t.stand()['modell']['karte'], 'RTX 3080')
            self.assertEqual(self.zentrale.status.call_count, 2)
            self.zentrale.status.side_effect = te.platz.NichtErreichbar('nicht erreichbar')
            zeit.return_value = 110
            self.assertIsNone(self.t.stand()['modell']['karte'])
            zeit.return_value = 114
            self.assertIsNone(self.t.stand()['modell']['karte'])
            self.assertEqual(self.zentrale.status.call_count, 3)

    def test_karte_nicht_messbar_oder_zentrale_meldet_aus(self):
        for status in ({}, {'stand': {'eintraege': {'lightonocr': {'zustand': 'aus', 'karte': 'RTX 3090'}}}},
                       {'stand': {'eintraege': {'lightonocr': {'zustand': 'bereit', 'karte': None}}}}):
            with self.subTest(status=status):
                self.t._karte = (0, None)
                self.zentrale.status.return_value = status
                self.assertIsNone(self.t.stand()['modell']['karte'])

    def test_neustart_waehrend_lauf(self):
        self.t.hinzufuegen({'text': self.pdf})
        self.t.auftraege[0]['zustand'] = 'laeuft'
        self.t._speichern()
        with mock.patch('threading.Thread'):
            t2 = te.Texterkennung(self.cfg, ZKONFIG, os.path.join(self.tmp, 'daten'), lambda text: None,
                                  self.zentrale)
        self.assertEqual(t2.auftraege[0]['zustand'], 'abgebrochen')


class ZentraleStatus(unittest.TestCase):
    def test_get_ohne_autostart(self):
        starten = mock.Mock()
        z = te.platz.Zentrale(3894, starten)
        daten = {'stand': {'eintraege': {'lightonocr': {'karte': 'RTX 3090'}}}}
        with mock.patch.object(te.platz._OHNE_PROXY, 'open',
                               return_value=io.BytesIO(json.dumps(daten).encode())) as http:
            self.assertEqual(z.status(), daten)
        http.assert_called_once_with('http://127.0.0.1:3894/api/status', timeout=3)
        starten.assert_not_called()

    def test_fehler_ohne_autostart(self):
        starten = mock.Mock()
        z = te.platz.Zentrale(3894, starten)
        with mock.patch.object(te.platz._OHNE_PROXY, 'open', side_effect=OSError('nicht erreichbar')):
            with self.assertRaises(te.platz.NichtErreichbar):
                z.status()
        starten.assert_not_called()


class OcrSkill(unittest.TestCase):
    def setUp(self):
        pfad = r'C:\Workstation\Skills\aktiv\texterkennung\scripts\ocr.py'
        spec = importlib.util.spec_from_file_location('ocr_skill', pfad)
        self.ocr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ocr)
        self.plan = {'schritte': [], 'genug_platz': True, 'hinweise': [], 'gruende': [],
                     'karte': 0, 'karte_kurz': 'RTX 3090', 'bedarf_mib': {'0': 4700}}
        for name in ('dienste_sicherstellen', 'te_stand', 'modell_zustand', 'zentrale_post', 'warten_bis', 'melden'):
            p = mock.patch.object(self.ocr, name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.te_stand.return_value = {'modell': {'bereit': False}}
        self.modell_zustand.return_value = ('aus', None)
        self.zentrale_post.side_effect = lambda pfad, daten: self.plan if pfad == '/api/plan' else {'ok': True}

    def test_start_meldet_gewaehlte_3090_ohne_freigabe(self):
        self.assertTrue(self.ocr.start())
        self.melden.assert_called_once_with('Starte LightOnOCR über die Modellzentrale (RTX 3090) …')
        self.assertEqual(self.zentrale_post.call_args_list, [
            mock.call('/api/plan', {'id': 'lightonocr', 'aktion': 'starten'}),
            mock.call('/api/starten', {'id': 'lightonocr', 'schritte': []})])

    def test_kein_platz_meldet_kurzname_hinweise_und_gruende(self):
        self.plan.update(genug_platz=False, gruende=['Auftrag läuft.'],
                         hinweise=[{'karte': 0, 'fehlend_mib': 1024, 'belegt_von': ['Programm']}],
                         schritte=[{'id': 'beenden:strata', 'text': 'Strata beenden'}])
        with self.assertRaises(self.ocr.Abbruch) as ex:
            self.ocr.start()
        self.assertEqual(ex.exception.code, 3)
        for text in ('auf keiner der Karten (RTX 3090 FE, RTX 3090 Suprim)', 'RTX 3090: es fehlen',
                     'Programm', 'Auftrag läuft.', 'Strata beenden', 'Sascha fragen'):
            self.assertIn(text, str(ex.exception))
        self.assertNotIn('Karte 0', str(ex.exception))
        self.zentrale_post.assert_called_once_with('/api/plan', {'id': 'lightonocr', 'aktion': 'starten'})

    def test_keine_wunschkarte_meldet_grund(self):
        self.plan.update(genug_platz=False, karte=None, karte_kurz=None,
                         gruende=['Keine der Karten RTX 3080, RTX 3090 ist erkannt.'])
        with self.assertRaises(self.ocr.Abbruch) as ex:
            self.ocr.start()
        self.assertEqual(ex.exception.code, 3)
        self.assertIn(self.plan['gruende'][0], str(ex.exception))
        self.zentrale_post.assert_called_once()

    def test_status_karte_aus_zentrale_sonst_null(self):
        with mock.patch.object(self.ocr, 'erreichbar', return_value=True), \
                mock.patch.object(self.ocr, 'anfrage') as anfrage:
            self.te_stand.return_value = {'modell': {'bereit': True, 'karte': 'Falsche Karte'}}
            for zustand, karte, erwartet in (('bereit', 'RTX 3090 · Nr. 1', 'RTX 3090 · Nr. 1'),
                                             ('bereit', None, None), ('aus', 'RTX 3080', None)):
                with self.subTest(zustand=zustand, karte=karte):
                    anfrage.return_value = {'stand': {'eintraege': {
                        'lightonocr': {'zustand': zustand, 'karte': karte}}}}
                    self.assertEqual(self.ocr.status()['karte'], erwartet)
            anfrage.assert_called_with(self.ocr.ZENTRALE + '/api/status')
            anfrage.side_effect = self.ocr.Abbruch('Status nicht erreichbar', 3)
            self.assertIsNone(self.ocr.status()['karte'])
        with mock.patch.object(self.ocr, 'erreichbar', return_value=False):
            self.assertIsNone(self.ocr.status()['karte'])


if __name__ == '__main__':
    unittest.main()
