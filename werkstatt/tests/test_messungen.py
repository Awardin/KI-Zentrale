import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import messungen  # noqa: E402


class Transkription(unittest.TestCase):
    def test_kennzahlen_eines_laufs(self):
        with tempfile.TemporaryDirectory() as t:
            with open(os.path.join(t, 'run.json'), 'w', encoding='utf-8') as f:
                json.dump({'status': 'complete', 'workers_used': 2,
                           'signature': {'model': 'C:/x/faster-whisper-medium', 'workers': 2},
                           'chunks': [{'start': 0, 'end': 300, 'status': 'complete', 'gpu': 0, 'started': 100, 'finished': 110},
                                      {'start': 300, 'end': 600, 'status': 'complete', 'gpu': 1, 'started': 100, 'finished': 120}]}, f)
            k = messungen.transkription_lauf(t)
        self.assertEqual((k['modell'], k['ton_s'], k['laufzeit_s'], k['tempo']), ('medium', 600, 20, 30.0))
        self.assertEqual(k['aufbau'], '2 Karten, je ein Worker')

    def test_unvollstaendig_zaehlt_nicht(self):
        with tempfile.TemporaryDirectory() as t:
            with open(os.path.join(t, 'run.json'), 'w', encoding='utf-8') as f:
                json.dump({'status': 'running', 'chunks': []}, f)
            self.assertIsNone(messungen.transkription_lauf(t))


class Zusammenfassung(unittest.TestCase):
    def test_kosten_nur_wenn_gemeldet(self):
        liste = [
            {'zustand': 'fertig', 'dauer_s': 10, 'tokens': 1000, 'auswerter': {'name': 'Codex'}, 'cloud': 'OpenAI'},
            {'zustand': 'fertig', 'dauer_s': 30, 'tokens': 3000, 'auswerter': {'name': 'Codex'}, 'cloud': 'OpenAI'},
            {'zustand': 'fertig', 'dauer_s': 20, 'tokens': 2000, 'kosten_usd': 0.002, 'auswerter': {'name': 'OR'}, 'cloud': 'OpenRouter'},
            {'zustand': 'fehler', 'dauer_s': 5, 'auswerter': {'name': 'OR'}},
        ]
        g = {x['auswerter']: x for x in messungen.zusammenfassung(liste)['gruppen']}
        self.assertEqual((g['Codex']['anzahl'], g['Codex']['dauer_median'], g['Codex']['kosten_usd']), (2, 20, None))
        self.assertEqual((g['OR']['anzahl'], g['OR']['kosten_usd'], g['OR']['token_je_s']), (1, 0.002, 100))


class BildVideo(unittest.TestCase):
    def test_studio_auftraege_mit_angaben(self):
        auftraege = [
            {'zustand': 'fertig', 'art': 'bild', 'breite': 1328, 'hoehe': 1328, 'schritte': 40, 'rechenzeit_s': 70.0,
             'beendet': 1790000000, 'prompt_id': 'a'},
            {'zustand': 'fertig', 'art': 'bild', 'breite': 1328, 'hoehe': 1328, 'schritte': 40, 'rechenzeit_s': 80.0,
             'beendet': 1790000100, 'prompt_id': 'b'},
            {'zustand': 'fertig', 'art': 'bild', 'rechenzeit_s': None, 'hinweis': 'gab es schon'},
            {'zustand': 'fehler', 'art': 'bild', 'rechenzeit_s': 5.0},
        ]
        with tempfile.TemporaryDirectory() as d:
            b = messungen.bild_video(os.path.join(d, 'fehlt.json'), 1, auftraege)
        self.assertEqual(b['anzahl'], 2)
        g = b['gruppen'][0]
        self.assertEqual((g['quelle'], g['art'], g['aufloesung'], g['schritte'], g['dauer_median']),
                         ('Studio', 'Bild', '1328×1328', 40, 75.0))

    def test_neue_arten_und_int8(self):
        auftraege = [
            {'zustand': 'fertig', 'art': 'pose', 'schritte': 1, 'rechenzeit_s': 1.5, 'beendet': 1790000000},
            {'zustand': 'fertig', 'art': 'freistellen', 'verfahren': 'schnell', 'schritte': 1, 'rechenzeit_s': 1.2,
             'beendet': 1790000001},
            {'zustand': 'fertig', 'art': 'bild', 'breite': 1328, 'hoehe': 1328, 'schritte': 6, 'turbo': True, 'int8': True,
             'schnell': True, 'rechenzeit_s': 7.1, 'beendet': 1790000002},
        ]
        with tempfile.TemporaryDirectory() as d:
            b = messungen.bild_video(os.path.join(d, 'fehlt.json'), 1, auftraege)
        modelle = {g['art']: g['modell'] for g in b['gruppen']}
        self.assertEqual((modelle['Pose-Skelett'], modelle['Freistellen'], modelle['Bild']),
                         ('SDPose', 'BiRefNet', 'Qwen-Image 2.1 · Turbo · schnell · INT8'))
        with tempfile.TemporaryDirectory() as d:
            b = messungen.bild_video(os.path.join(d, 'fehlt.json'), 1, [dict(auftraege[0], personen=True)])
        self.assertEqual([g['modell'] for g in b['gruppen']], ['SDPose · alle Personen'])

    def test_weitergefuehrtes_video(self):
        # gezählt wird der neu gerechnete Clip (bilder = L), nicht das fertige Video
        a = {'zustand': 'fertig', 'art': 'video_weiter', 'breite': 960, 'hoehe': 544, 'bilder': 175, 'laenge_bilder': 260,
             'schritte': 8, 'turbo': True, 'rechenzeit_s': 90.0, 'beendet': 1790000000}
        with tempfile.TemporaryDirectory() as d:
            g = messungen.bild_video(os.path.join(d, 'fehlt.json'), 1, [a])['gruppen'][0]
        self.assertEqual((g['art'], g['modell'], g['aufloesung']), ('Video weiterführen', 'MiniMax-H3', '960×544 · 7,3 s'))


class GpuLab(unittest.TestCase):
    def test_import_und_verdichtung(self):
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, 'd.sqlite3')
            c = sqlite3.connect(db)
            c.execute('create table runs (id text primary key, created_at text, capture_id text, data_json text)')
            for i, dec in enumerate((40, 44, 42)):
                c.execute('insert into runs values (?,?,?,?)', (f'r{i}', f'2026-09-14T16:0{i}:00Z', None, json.dumps(
                    {'type': 'llm', 'gpu': 'rtx3080', 'model': 'Qwen', 'quant': 'Q3', 'runtime': 'llama.cpp',
                     'decode': str(dec), 'prefill': '1000', 'ttft': '480'})))
            c.execute('insert into runs values (?,?,?,?)', ('x', '2026-09-15T10:00:00Z', None,
                                                             json.dumps({'type': 'bench', 'test_name': '3DMark'})))
            c.commit()
            c.close()
            ziel = os.path.join(t, 'hist.json')
            self.assertEqual(messungen.gpu_lab_importieren(db, ziel), 4)
            h = messungen.historisch(ziel)
        self.assertEqual((h['anzahl'], h['andere'], len(h['gruppen'])), (4, 1, 1))
        self.assertEqual((h['gruppen'][0]['anzahl'], h['gruppen'][0]['decode']), (3, 42))


class Messtext(unittest.TestCase):
    def test_messtext_ohne_wiederholte_absaetze(self):
        absaetze = [a for a in messungen.MESSTEXT.split('\n\n') if a.strip()]
        self.assertGreater(len(absaetze), 8)
        self.assertEqual(len(absaetze), len(set(absaetze)))


if __name__ == '__main__':
    unittest.main()
