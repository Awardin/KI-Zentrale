import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auftraege, platz, quellen, watch_lauf  # noqa: E402

W = 2800


def karte(i, frei, last=0, nebenkarte=False):
    return {'index': i, 'kurz': ['RTX 3090', 'RTX 3080'][i], 'frei': frei, 'last': last,
            'nebenkarte': nebenkarte}


class Verteilen(unittest.TestCase):
    def test_beide_karten_frei_je_ein_worker(self):
        v = platz.verteilen([karte(0, 22000), karte(1, 19000)], W, 2)
        self.assertEqual(v['gpus'], [0, 1])
        self.assertEqual(v['worker'], 2)
        # Jede Karte muss beide Worker tragen können (watch kann kurz beide auf eine Karte legen).
        self.assertEqual(v['bedarf_mib'], {0: 2 * W, 1: 2 * W})

    def test_ornith_q5_geladen_reicht_fuer_beide_karten(self):
        # Gemessen: Q5 belegt 16,2 + 12,2 GiB; übrig bleiben gut 6 GiB je Karte.
        v = platz.verteilen([karte(0, 6900), karte(1, 6800)], W, 2)
        self.assertEqual(v['gpus'], [0, 1])

    def test_nur_eine_karte_hat_platz_fuer_zwei(self):
        v = platz.verteilen([karte(0, 1200), karte(1, 9000)], W, 2)
        self.assertEqual((v['gpus'], v['worker'], v['bedarf_mib']), ([1], 2, {1: 2 * W}))

    def test_knapp_ein_worker(self):
        v = platz.verteilen([karte(0, 3000), karte(1, 1000)], W, 2)
        self.assertEqual((v['gpus'], v['worker']), ([0], 1))

    def test_kein_platz(self):
        self.assertIsNone(platz.verteilen([karte(0, 2000), karte(1, 1000)], W, 2))

    def test_kurze_quelle_ein_worker(self):
        self.assertEqual(platz.worker_noetig(370, 300), 1)
        self.assertEqual(platz.worker_noetig(380, 300), 2)
        v = platz.verteilen([karte(0, 22000), karte(1, 19000)], W, 1)
        self.assertEqual((v['gpus'], v['worker'], v['bedarf_mib']), ([0], 1, {0: W}))

    def test_beschaeftigte_karte_nachrangig(self):
        v = platz.verteilen([karte(0, 20000, last=95), karte(1, 9000)], W, 2)
        self.assertEqual(v['gpus'], [1])

    def test_nebenkarte_reicht_fuer_zwei_worker(self):
        v = platz.verteilen([karte(0, 22000), karte(1, 7000, nebenkarte=True)], W, 2)
        self.assertEqual((v['gpus'], v['worker'], v['text']), ([1], 2, 'RTX 3080, zwei Worker'))

    def test_nebenkarte_reicht_nur_fuer_einen_worker(self):
        v = platz.verteilen([karte(0, 1000), karte(1, 3000, nebenkarte=True)], W, 2)
        self.assertEqual((v['gpus'], v['worker'], v['text']), ([1], 1, 'RTX 3080, ein Worker'))
        # Trägt eine 3090 beide Worker, geht die Transkription dorthin statt mit einem Worker auf die 3080.
        v = platz.verteilen([karte(0, 22000), karte(1, 3000, nebenkarte=True)], W, 2)
        self.assertEqual((v['gpus'], v['worker']), ([0], 2))

    def test_volle_nebenkarte_bleibt_bei_der_3090(self):
        v = platz.verteilen([karte(0, 22000), karte(1, 1000, nebenkarte=True)], W, 2)
        self.assertEqual((v['gpus'], v['worker']), ([0], 2))

    def test_ausgelastete_nebenkarte_geht_nicht_vor(self):
        v = platz.verteilen([karte(0, 9000), karte(1, 20000, last=95, nebenkarte=True)], W, 2)
        self.assertEqual(v['gpus'], [0])

    def test_begruendung(self):
        a = {'gruende': [], 'karten': [karte(0, 2000), karte(1, 1000)]}
        self.assertIn('es fehlen 0,8 GiB', platz.warum_nicht(a, W))
        a['karten'][0]['belegt_von'] = ['Ornith 1.5 · Q5', 'Windows & Programme']
        self.assertIn('belegt von Ornith 1.5 · Q5)', platz.warum_nicht(a, W))
        self.assertEqual(platz.warum_nicht({'gruende': ['ComfyUI arbeitet.'], 'karten': []}, W), 'ComfyUI arbeitet.')


class AusfuehrenUmgebung(unittest.TestCase):
    def test_karten_werden_fuer_watch_ausdruecklich_sichtbar(self):
        w = auftraege.Warteschlange.__new__(auftraege.Warteschlange)
        w.w = {'python': 'python.exe', 'skript': os.path.join('C:', 'Watch', 'watch.py')}
        w._lock = threading.RLock()
        w._gruppe = None
        w._abbruch = set()
        gruppe = Mock()
        gruppe.prozess.returncode = 0
        gruppe.prozess.communicate.return_value = (b'', b'')
        with patch('werkstatt.auftraege.winapi.Prozessgruppe', return_value=gruppe) as pg:
            code, aus, err = w._ausfuehren({'id': 'x'}, ['transcribe', 'datei'], karten=[2])
        self.assertEqual((code, aus, err), (0, '', ''))
        env = pg.call_args.args[2]
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '0,1,2')
        self.assertEqual(env['CUDA_DEVICE_ORDER'], 'PCI_BUS_ID')


class YouTube(unittest.TestCase):
    def test_formen(self):
        for url in ('https://www.youtube.com/watch?v=aiS5IUE42G8', 'https://youtu.be/aiS5IUE42G8?t=10',
                    'https://m.youtube.com/watch?feature=share&v=aiS5IUE42G8', 'https://www.youtube.com/shorts/aiS5IUE42G8',
                    'https://www.youtube.com/live/aiS5IUE42G8', 'https://www.youtube.com/watch?v=aiS5IUE42G8&list=PL123'):
            self.assertEqual(watch_lauf.youtube_id(url), 'aiS5IUE42G8', url)

    def test_abgelehnt(self):
        for url, grund in (('https://www.youtube.com/playlist?list=PL123', 'Playlists'),
                           ('https://www.youtube.com/@kanal', 'Kanäle'),
                           ('https://vimeo.com/12345', 'kein YouTube')):
            with self.assertRaises(ValueError) as e:
                watch_lauf.youtube_id(url)
            self.assertIn(grund, str(e.exception))

    def test_text_zerlegen(self):
        teile = quellen.text_zerlegen('https://youtu.be/aiS5IUE42G8 https://youtu.be/neKG823h_FA\n'
                                      '"C:\\Kurs\\Modul 1.mp4"\nhallo\nhttps://www.youtube.com/@kanal')
        self.assertEqual([t[0] for t in teile], ['youtube', 'youtube', 'pfad', 'fehler', 'fehler'])
        self.assertEqual(teile[0][1], 'https://www.youtube.com/watch?v=aiS5IUE42G8')
        self.assertEqual(teile[2][1], 'C:\\Kurs\\Modul 1.mp4')


class Vorhandenes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.o = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def lauf(self, ordner, start=0, ende=270.6, status='complete', sha='abc'):
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, 'run.json'), 'w', encoding='utf-8') as f:
            json.dump({'status': status, 'signature': {'start': start, 'end': ende, 'source_sha256': sha,
                                                       'language': 'de', 'model': 'x/faster-whisper-medium'},
                       'chunks': [{'index': 0, 'start': 0, 'end': 150, 'status': 'complete'},
                                  {'index': 1, 'start': 150, 'end': ende, 'status': 'pending'}]}, f)
        for n in watch_lauf.TRANSKRIPT_DATEIEN:
            open(os.path.join(ordner, n), 'w').close()

    def test_videoordner_mit_titel_und_alt(self):
        os.makedirs(os.path.join(self.o, 'Titel [aiS5IUE42G8]'))
        os.makedirs(os.path.join(self.o, 'neKG823h_FA'))
        self.assertTrue(watch_lauf.videoordner(self.o, 'aiS5IUE42G8').endswith('Titel [aiS5IUE42G8]'))
        self.assertTrue(watch_lauf.videoordner(self.o, 'neKG823h_FA').endswith('neKG823h_FA'))
        self.assertIsNone(watch_lauf.videoordner(self.o, 'xxxxxxxxxxx'))

    def test_transkript_im_unterordner_und_nur_ganze_quelle(self):
        v = os.path.join(self.o, 'Titel [aiS5IUE42G8]')
        self.lauf(os.path.join(v, 'transkript-medium-2w', 'gpu0-chunk-000-300'), start=0, ende=150)
        self.assertIsNone(watch_lauf.transkript_passend(watch_lauf.transkripte(v), 271))
        self.lauf(os.path.join(v, 'transkript-medium-2w'))
        self.assertIsNotNone(watch_lauf.transkript_passend(watch_lauf.transkripte(v), 271))

    def test_unvollstaendiger_lauf_zaehlt_nicht(self):
        self.lauf(self.o, status='running')
        self.assertEqual(watch_lauf.transkripte(self.o), [])

    def test_lokale_datei_nur_mit_gleicher_pruefsumme(self):
        self.lauf(self.o, sha='abc')
        self.assertIsNone(watch_lauf.transkript_passend(watch_lauf.transkripte(self.o), 270.6, sha='def'))
        self.assertIsNotNone(watch_lauf.transkript_passend(watch_lauf.transkripte(self.o), 270.6, sha='abc'))

    def test_fortschritt_und_ersatzlauf(self):
        self.lauf(self.o, status='running')
        f = watch_lauf.fortschritt_transkription(self.o)
        self.assertEqual((f['fertig'], f['gesamt'], f['ersatz']), (1, 2, False))
        self.assertAlmostEqual(f['sek_fertig'] / f['sek_gesamt'], 150 / 270.6)
        self.lauf(os.path.join(self.o, 'single-worker'))
        self.assertTrue(watch_lauf.ergebnis_transkription(self.o).endswith('single-worker'))

    def test_bildabdeckung(self):
        ab = [(0, 1800, 'a'), (1800, 3600, 'b')]
        self.assertTrue(watch_lauf.bilder_vollstaendig(ab, 3600))
        self.assertFalse(watch_lauf.bilder_vollstaendig(ab, 4000))
        self.assertFalse(watch_lauf.bilder_vollstaendig([(0, 1000, 'a'), (1800, 3600, 'b')], 3600))
        self.assertTrue(watch_lauf.bereich_abgedeckt(ab, 1800, 3600))

    def test_bildfenster(self):
        self.assertEqual(watch_lauf.bildfenster(1900, 1800), [(0.0, 1900)])
        self.assertEqual(watch_lauf.bildfenster(4000, 1800), [(0, 1800), (1800, 3600), (3600, 4000)])

    def test_transkript_ziel_bei_abgebrochenem_lauf(self):
        self.assertEqual(watch_lauf.transkript_ziel(self.o), self.o)
        self.lauf(self.o, status='running')
        self.assertIn('transkript-', watch_lauf.transkript_ziel(self.o))

    def test_fehlertext(self):
        t = watch_lauf.fehlertext('{"error": "CUDA failed with error out of memory"}')
        self.assertTrue(t.startswith('Der Grafikspeicher reichte nicht.'))

    def test_lokaler_ordner_nutzt_benennung_von_watch(self):
        skript = r'C:\Workstation\Skills\aktiv\watch\scripts\watch.py'
        if not os.path.exists(skript):
            self.skipTest('watch nicht vorhanden')
        o = watch_lauf.lokaler_ordner('C:\\A', 'C:\\Kurs\\Modul: 1?.mp4', 'f' * 64, skript)
        self.assertEqual(o, 'C:\\A\\Modul - 1 [datei-ffffffffffff]')


class Abgleich(unittest.TestCase):
    def test_name_groesse_und_zeit_muessen_passen(self):
        with tempfile.TemporaryDirectory() as t:
            a = os.path.join(t, 'Vortrag.mp4')
            with open(a, 'wb') as f:
                f.write(b'x' * 100)
            os.makedirs(os.path.join(t, 'Kurs'))
            mtime = os.stat(a).st_mtime * 1000
            gefunden, offen = quellen.abgleichen(
                [{'name': 'Vortrag.mp4', 'groesse': 100, 'geaendert': mtime},
                 {'name': 'Vortrag.mp4', 'groesse': 99, 'geaendert': mtime},
                 {'name': 'Kurs', 'ordner': True},
                 {'name': 'Desktop.mp4', 'groesse': 1}],
                [a, os.path.join(t, 'Kurs')])
            self.assertEqual(gefunden, [a, os.path.join(t, 'Kurs')])
            self.assertEqual(offen, ['Vortrag.mp4', 'Desktop.mp4'])

    def test_ordner_ausklappen(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ('Teil 10.mp4', 'Teil 2.mp4', 'notiz.txt', os.path.join('sub', 'a.mp3')):
                os.makedirs(os.path.dirname(os.path.join(t, n)), exist_ok=True)
                open(os.path.join(t, n), 'w').close()
            dateien, zu_viele = quellen.ordner_ausklappen(t, ['.mp4', '.mp3'], 10)
            self.assertEqual([os.path.relpath(d, t) for d in dateien], ['sub\\a.mp3', 'Teil 2.mp4', 'Teil 10.mp4'])
            self.assertFalse(zu_viele)


class PromptRouten(unittest.TestCase):
    """HTTP-Handler direkt ausführen: kein Dienst, kein Zugriff auf echte Arbeitsdaten."""
    def setUp(self):
        from werkstatt import prompts, server
        self.tmp = tempfile.TemporaryDirectory()
        sammlung = os.path.join(self.tmp.name, 'Sammlung.md')
        with open(sammlung, 'w', encoding='utf-8') as f:
            f.write('### Wissen\n~~~text\nSuchen\n~~~\n')
        self.p = prompts.Index({'ordner': os.path.join(self.tmp.name, 'Prompts'),
                                'dateiwurzeln': [self.tmp.name]}, sammlung)
        self.h = server.Anfrage.__new__(server.Anfrage)
        self.h.server = Mock(server_address=('127.0.0.1', 3895))
        self.h.headers = {'Host': '127.0.0.1:3895', 'X-Werkstatt': '1'}
        self.h.werkstatt = Mock(prompts=self.p)
        self.h._senden = Mock(side_effect=lambda code, daten: (code, daten))
        self.h._statisch_senden = Mock(return_value=False)

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, daten):
        self.h.path = '/api/prompt'
        self.h._json_lesen = Mock(return_value=daten)
        return self.h.do_POST()

    def get(self, pfad):
        self.h.path = pfad
        return self.h.do_GET()

    def test_neu_liste_detail_und_alle_schreibaktionen(self):
        code, e = self.post({'aktion': 'neu', 'titel': 'Test', 'quelle': '', 'schlagworte': 'html', 'text': 'HTML'})
        self.assertEqual(code, 200)
        eid = e['id']
        self.assertEqual(self.get('/api/prompts')[0], 200)
        self.assertEqual(self.get('/api/prompt?id=' + eid)[1]['titel'], 'Test')
        code, e = self.post({'aktion': 'kopf', 'id': eid, 'titel': 'Titel', 'quelle': 'Quelle',
                             'schlagworte': 'Tag', 'kopf_stand': e['kopf_stand']})
        self.assertEqual(code, 200)
        code, e = self.post({'aktion': 'fassung_speichern', 'id': eid, 'name': 'Fassung 1',
                             'text': 'Neu', 'stand': e['fassungen'][0]['stand']})
        self.assertEqual(code, 200)
        code, e = self.post({'aktion': 'fassung_neu', 'id': eid, 'name': 'Zwei', 'text': 'Zweite'})
        self.assertEqual(code, 200)
        code, e = self.post({'aktion': 'bevorzugt', 'id': eid, 'name': 'Zwei', 'kopf_stand': e['kopf_stand']})
        self.assertEqual((code, e['bevorzugt']), (200, 'Zwei'))

    def test_conflict_kopf_inklusive_titel_und_fassung(self):
        e = self.p.neu('Test', '', '', 'Alt')
        daten = {'aktion': 'fassung_speichern', 'id': e['id'], 'name': 'Fassung 1',
                 'text': 'Neu', 'stand': e['fassungen'][0]['stand']}
        self.assertEqual(self.post(daten)[0], 200)
        code, fehler = self.post(daten)
        self.assertEqual(code, 409)
        self.assertIn('neu laden', fehler['fehler'])
        pfad = os.path.join(self.p.ordner, e['id'], 'prompt.md')
        with open(pfad, encoding='utf-8') as f:
            text = f.read()
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write(text.replace('# Test', '# Extern'))
        self.assertEqual(self.post({'aktion': 'kopf', 'id': e['id'], 'titel': 'Neu',
                                    'kopf_stand': e['kopf_stand']})[0], 409)

    def test_oeffnen_unzulaessig_startet_nichts(self):
        e = self.p.neu('Test', '', '', 'Text')
        with patch('werkstatt.prompts.os.startfile') as starten:
            for was in ('beleg', 'schaerfen', 'html'):
                for name in ('..\\x.cmd', 'C:\\x.md', 'x.cmd', '..\\x.md', 'C:/x.html', 'x.md:strom'):
                    code, d = self.post({'aktion': 'oeffnen', 'id': e['id'], 'was': was, 'datei': name})
                    self.assertEqual(code, 400, (was, name))
                    self.assertIn('fehler', d)
            starten.assert_not_called()
            self.assertEqual(self.post({'aktion': 'oeffnen', 'id': e['id'], 'was': 'ordner'})[0], 200)
            starten.assert_called_once_with(os.path.join(self.p.ordner, e['id']))

    def test_oeffnen_erlaubte_dateien_und_sammlung(self):
        e = self.p.neu('Test', '', '', 'Text')
        for unterordner, datei, was in (('tests', 'Beleg.md', 'beleg'), ('tests', 'Beleg.html', 'html'),
                                       ('schaerfen', 'Vorschlag.md', 'schaerfen')):
            ordner = os.path.join(self.p.ordner, e['id'], unterordner)
            os.makedirs(ordner, exist_ok=True)
            pfad = os.path.join(ordner, datei)
            with open(pfad, 'w', encoding='utf-8') as f:
                f.write('Test')
            with patch('werkstatt.prompts.os.startfile') as starten:
                self.assertEqual(self.post({'aktion': 'oeffnen', 'id': e['id'], 'was': was, 'datei': datei})[0], 200)
                starten.assert_called_once_with(pfad)
        with patch('werkstatt.prompts.os.startfile') as starten:
            self.assertEqual(self.post({'aktion': 'oeffnen', 'id': 'sammlung:Wissen#1', 'was': 'sammlung',
                                        'pfad': 'C:\\beliebig.cmd'})[0], 200)
            starten.assert_called_once_with(self.p.sammlung)

    def test_herkunft_fehler_und_statische_freigabe(self):
        from werkstatt import server
        self.assertIn('/prompts.js', server.Anfrage.statisch)
        del self.h.headers['X-Werkstatt']
        for aktion in ('neu', 'kopf', 'fassung_speichern', 'fassung_neu', 'bevorzugt', 'oeffnen', 'zuordnen'):
            self.assertEqual(self.post({'aktion': aktion})[0], 403)
        self.h.headers['X-Werkstatt'] = '1'
        self.h.headers['Origin'] = 'http://fremd.example'
        self.assertEqual(self.post({'aktion': 'neu'})[0], 403)
        del self.h.headers['Origin']
        self.assertEqual(self.post({'aktion': 'unbekannt', 'id': 'fehlt'})[0], 400)
        self.assertEqual(self.get('/api/prompt?id=fehlt')[0], 400)
        with patch.object(self.p, 'alle', side_effect=RuntimeError('MARKIERUNG')):
            self.assertEqual(self.get('/api/prompts')[0], 400)
        self.h.werkstatt.log.assert_not_called()

    def test_oeffnen_junction_ausserhalb(self):
        import _winapi
        e = self.p.neu('Test', '', '', 'Text')
        with tempfile.TemporaryDirectory() as ausserhalb:
            pfad = os.path.join(ausserhalb, 'Beleg.md')
            with open(pfad, 'w', encoding='utf-8') as f:
                f.write('Text')
            junction = os.path.join(self.p.ordner, e['id'], 'tests')
            _winapi.CreateJunction(ausserhalb, junction)
            try:
                with patch('werkstatt.prompts.os.startfile') as starten:
                    self.assertEqual(self.post({'aktion': 'oeffnen', 'id': e['id'], 'was': 'beleg',
                                                'datei': 'Beleg.md'})[0], 400)
                    starten.assert_not_called()
            finally:
                os.rmdir(junction)

    def test_sammlung_zuordnen_route(self):
        from werkstatt import prompts
        ordner = os.path.join(self.p.ordner, '_Sammlung', 'Wissen')
        os.makedirs(ordner)
        pfad = os.path.join(ordner, 'eintrag.json')
        with open(pfad, 'w', encoding='utf-8') as f:
            json.dump({'ueberschrift': 'Wissen', 'nummer': 2, 'stand': 'alt', 'kaesten_vorher': 2}, f)
        code, d = self.post({'aktion': 'zuordnen', 'id': 'schatten:Wissen', 'ziel': 'sammlung:Wissen#1'})
        self.assertEqual((code, d['schatten']), (200, 'Wissen'))
        with open(pfad, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['stand'], prompts.stand('Suchen'))

    def test_testen_vorschau_beleg_urteil_gesendet_und_konflikte(self):
        from werkstatt import auswertung
        from werkstatt.tests.test_auswertung_prompts import Fake
        cfg = {'watch': {'arbeitsordner': self.tmp.name}, 'promptsammlung': self.p.sammlung,
               'prompts': self.p.cfg, 'auswerter_vorschlag': [
                   {'id': 'p', 'anbieter': 'fake', 'modell': 'modell', 'name': 'Fake'}], 'cloud_parallel': 0}
        au = auswertung.Auswertungen(cfg, os.path.join(self.tmp.name, 'daten'), lambda text: None)
        au.anbieter['fake'] = Fake()
        self.p = au.prompts
        self.h.werkstatt.prompts = self.p
        self.h.werkstatt.auswertung = au
        e = self.p.neu('Test', '', '', 'Teste [A]')
        daten = {'id': e['id'], 'fassungen': ['Fassung 1'], 'auswerter': ['p'],
                 'eingaben': {'felder': {'A': {'art': 'text', 'wert': 'Text'}}}}
        code, v = self.post(dict(daten, aktion='vorschau'))
        self.assertEqual(code, 200)
        self.assertEqual(self.post(dict(daten, aktion='testen', gesendet_stand={}))[0], 409)
        staende = {f['name']: f['gesendet_stand'] for f in v['fassungen']}
        code, antwort = self.post(dict(daten, aktion='testen', gesendet_stand=staende))
        self.assertEqual((code, antwort['neu']), (200, 1))
        self.assertEqual(len(self.get('/api/prompts')[1]['warteschlange']), 1)
        a = au.liste[0]
        datei = os.path.basename(a['datei'])
        from urllib.parse import urlencode
        url = '/api/prompt-datei?' + urlencode({'id': e['id'], 'was': 'beleg', 'datei': datei})
        code, b = self.get(url)
        self.assertEqual((code, b['fassung_text']), (200, 'Teste [A]'))
        self.assertEqual(self.get(url.replace('was=beleg', 'was=gesendet'))[1]['text'], 'Teste Text')
        urteil = {'aktion': 'urteil', 'id': e['id'], 'datei': datei,
                  'kopf_stand': b['kopf_stand'], 'urteil': 'gut', 'notiz': 'Notiz'}
        self.assertEqual(self.post(urteil)[0], 200)
        self.assertEqual(self.post(urteil)[0], 409)
        for name in ('..\\x.md', 'C:\\x.md', 'x.cmd', 'x.md:strom', '..', '../x.md'):
            self.assertEqual(self.get('/api/prompt-datei?' + urlencode(
                {'id': e['id'], 'was': 'gesendet', 'datei': name}))[0], 400)
        au.aktion(a['id'], 'entfernen')
        self.assertTrue(self.get('/api/prompts')[1]['eintraege'][0]['tests'][0]['verwaist'])
        self.assertEqual(self.post({'aktion': 'wiederholen_beleg', 'id': e['id'], 'datei': datei})[0], 200)
        self.assertEqual(self.post({'aktion': 'wiederholen_beleg', 'id': e['id'], 'datei': datei})[0], 409)
        with patch('werkstatt.prompts.os.startfile') as starten:
            self.assertEqual(self.p.oeffnen(e['id'], 'beleg', datei), {'ok': True})
            starten.assert_called_once_with(a['datei'])

    def test_neue_aktionen_ohne_herkunft_und_dateidialog(self):
        for aktion in ('vorschau', 'testen', 'urteil', 'datei_lesen', 'datei_waehlen', 'wiederholen_beleg',
                       'schaerfen_vorschau', 'schaerfen'):
            del self.h.headers['X-Werkstatt']
            self.assertEqual(self.post({'aktion': aktion})[0], 403)
            self.h.headers['X-Werkstatt'] = '1'
        datei = os.path.join(self.tmp.name, 'feld.txt')
        with open(datei, 'w', encoding='utf-8') as f:
            f.write('Feldinhalt')
        self.assertEqual(self.post({'aktion': 'datei_lesen', 'pfad': datei})[1]['wert'], 'Feldinhalt')
        with patch('werkstatt.quellen.textdatei_waehlen', return_value=[datei]):
            self.assertEqual(self.post({'aktion': 'datei_waehlen'})[1]['wert'], 'Feldinhalt')
        with patch('werkstatt.quellen.textdatei_waehlen', return_value=[]):
            self.assertTrue(self.post({'aktion': 'datei_waehlen'})[1]['abgebrochen'])
        with patch.object(self.p, 'transkripte', return_value=[{'titel': 'Film', 'sha': 'sha', 'zeichen': 10}]):
            self.assertEqual(self.get('/api/transkripte?prompts=1')[1][0]['zeichen'], 10)
        with patch.object(self.p, 'transkripte', side_effect=RuntimeError('MARKIERUNG')):
            self.assertEqual(self.get('/api/transkripte?prompts=1')[0], 400)
        self.h.werkstatt.log.assert_not_called()

    def test_schaerfen_routen_datei_herkunft_und_oeffnen(self):
        from pathlib import Path
        from urllib.parse import urlencode
        from werkstatt import server, prompts
        from werkstatt.tests.test_auswertung_prompts import SchaerfenLaeufe
        basis = SchaerfenLaeufe('test_a_uebernahme_datei_index_und_anzeigedaten')
        basis.setUp()
        try:
            basis.vorbereiten()
            self.p = basis.p
            self.h.werkstatt.prompts = self.p
            self.h.werkstatt.auswertung = basis.au
            code, v = self.post(dict(basis.sd, aktion='schaerfen_vorschau'))
            self.assertEqual(code, 200)
            self.assertIn('Regeln zum Schärfen', v['auftrag'])
            self.assertEqual(self.post(dict(basis.sd, aktion='schaerfen', gesendet_stand='alt'))[0], 409)
            code, r = self.post(dict(basis.sd, aktion='schaerfen', gesendet_stand=v['gesendet_stand']))
            self.assertEqual((code, r['neu']), (200, 1))
            a = basis.au.liste[0]
            url = '/api/prompt-datei?' + urlencode({'id': basis.e['id'], 'was': 'schaerfen', 'datei': Path(a['datei']).name})
            self.assertEqual(self.get(url)[1]['original'], 'Baue [A].')
            basis.arbeiten()
            code, b = self.get(url)
            self.assertEqual((code, b['neue_fassung']), (200, 'Besser 1 [A] [Projektkontext]'))
            self.assertIn('- Klarer', b['stichpunkte'])
            for pfad in ('/api/prompts', '/api/prompt?' + urlencode({'id': basis.e['id']})):
                code, d = self.get(pfad)
                e = d['eintraege'][0] if 'eintraege' in d else d
                self.assertEqual((code, len(e['schaerfen']), d['warteschlange'][0]['art']), (200, 1, 'schaerfen'))
            w = server.Werkstatt.__new__(server.Werkstatt)
            w.auswertung = basis.au
            for was, ziel in [('oeffnen', a['datei']), ('ordner', str(Path(a['datei']).parent))]:
                with patch('werkstatt.server.os.startfile') as starten:
                    self.assertEqual(w.fassung_oeffnen(a['id'], was)[0], 200)
                    starten.assert_called_once_with(ziel)
            for name in ('../x.md', 'C:\\x.md', 'x.cmd', 'x.md:strom'):
                self.assertEqual(self.get('/api/prompt-datei?' + urlencode(
                    {'id': basis.e['id'], 'was': 'schaerfen', 'datei': name}))[0], 400)
            basis.au.aktion(a['id'], 'entfernen')
            d = self.get('/api/prompt?' + urlencode({'id': basis.e['id']}))[1]
            self.assertTrue(d['schaerfen'][0]['verwaist'])
            daten = {'aktion': 'wiederholen_beleg', 'id': basis.e['id'], 'datei': b['datei'], 'art_ordner': 'schaerfen'}
            self.assertEqual(self.post(daten)[0], 200)
            self.assertEqual(self.post(daten)[0], 409)
        finally:
            basis.doCleanups()

    def test_prompt_fassung_oeffnen_sicher_und_messungen_filter(self):
        from werkstatt import server
        w = server.Werkstatt.__new__(server.Werkstatt)
        w.prompts = self.p
        e = self.p.neu('Test', '', '', 'Text')
        datei = os.path.join(self.p.ordner, e['id'], 'tests', 'Test.md')
        os.makedirs(os.path.dirname(datei))
        with open(datei, 'w', encoding='utf-8') as f:
            f.write('Beleg')
        a = {'id': 'p', 'art': 'prompt', 'prompt': {'eintrag': e['id'], 'beleg': 'Test'}, 'datei': 'C:\\x.cmd'}
        w.auswertung = Mock(liste=[a])
        w.auswertung._belegpfad.side_effect = lambda a: self.p.beleg_pfad(a['prompt']['eintrag'], a['prompt']['beleg'] + '.md')
        with patch('werkstatt.prompts.os.startfile') as starten:
            self.assertEqual(w.fassung_oeffnen('p', 'oeffnen')[0], 200)
            starten.assert_called_once_with(datei)
            starten.reset_mock()
            self.assertEqual(w.fassung_oeffnen('p', 'ordner')[0], 200)
            starten.assert_called_once_with(os.path.dirname(datei))
        w._messungen = (1e20, {})
        lokal = Mock()
        lokal._eintraege.return_value = ({}, {})
        lokal.katalog.return_value = []
        w.auswertung.anbieter = {'lokal': lokal}
        w.messlauf = Mock(laufend=None)
        w.messlauf.liste.return_value = []
        alt = {'id': 'z', 'zustand': 'fertig', 'dauer_s': 1, 'auswerter': {'name': 'Zusammenfassung'}}
        a.update(zustand='fertig', dauer_s=1, auswerter={'name': 'Prompt'})
        w.auswertung.liste.append(alt)
        self.assertEqual(w.messungen()['zusammenfassung']['anzahl'], 1)


if __name__ == '__main__':
    unittest.main()
