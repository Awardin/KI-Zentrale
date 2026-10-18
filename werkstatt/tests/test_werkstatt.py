import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import platz, quellen, watch_lauf  # noqa: E402

W = 2800


def karte(i, frei, last=0):
    return {'index': i, 'kurz': ['RTX 3090', 'RTX 3080'][i], 'frei': frei, 'last': last}


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

    def test_begruendung(self):
        a = {'gruende': [], 'karten': [karte(0, 2000), karte(1, 1000)]}
        self.assertIn('es fehlen 0,8 GiB', platz.warum_nicht(a, W))
        a['karten'][0]['belegt_von'] = ['Ornith 1.5 · Q5', 'Windows & Programme']
        self.assertIn('belegt von Ornith 1.5 · Q5)', platz.warum_nicht(a, W))
        self.assertEqual(platz.warum_nicht({'gruende': ['ComfyUI arbeitet.'], 'karten': []}, W), 'ComfyUI arbeitet.')


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


if __name__ == '__main__':
    unittest.main()
