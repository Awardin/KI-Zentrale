"""Stufe 8 (16.10.2026): zwei ComfyUI-Prozesse im Studio – Kartenwahl, Arbeiter, Namen, Hochladen, Begleitdateien."""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from werkstatt import studio  # noqa: E402
from test_studio import S  # noqa: E402

BILD = {'eine': 18432, 'haupt': 16384, 'neben': 2048}
VIDEO = {'haupt': 20480, 'neben': 7168}
VIDEO_EINE = dict(VIDEO, eine_ohne_monitor=22528)  # seit 16.10.2026 (H3 auf einer 3090 gemessen)


def antwort(frei0, frei1, comfy1=0, comfy2=0):
    verbraucher = []
    if comfy1:
        verbraucher.append({'schluessel': 'bild-video', 'name': 'ComfyUI', 'mib_je_karte': {'0': comfy1}})
    if comfy2:
        verbraucher.append({'schluessel': 'bild-video-2', 'name': 'ComfyUI 2', 'mib_je_karte': {'1': comfy2}})
    return {'karten': [{'index': 0, 'kurz': 'RTX 3090 FE', 'frei': frei0, 'monitor': True},
                       {'index': 1, 'kurz': 'RTX 3090 Suprim', 'frei': frei1}],
            'verbraucher': verbraucher, 'monitor_puffer_mib': 2048}


def instanzen():
    a = studio.Instanz(1, 8188, 'bild-video', 'ComfyUI')
    b = studio.Instanz(2, 8189, 'bild-video-2', 'ComfyUI 2', karten=[1], standard=1, zusatz='-2')
    a.andere, b.andere = [b], [a]
    return a, b


class Kartenwahl(unittest.TestCase):
    def test_zweiter_prozess_sieht_nur_seine_karte_und_seinen_cache(self):
        a, b = instanzen()
        # Prozess 1 hält 18.000 MiB auf der FE: das zählt für Prozess 2 nicht (Astra: sonst falsche Karte).
        v, fehlend, zusatz = studio.karten_waehlen(antwort(4000, 22000, comfy1=18000), BILD, b)
        self.assertEqual((v['mib'], fehlend, zusatz), ({1: 18432}, {}, {1: 18432}))
        self.assertEqual(studio.mit_geraeten(S, v['geraete'], b.lokal)['geraete'],
                         {'modell': 'gpu:0', 'clip': 'gpu:0', 'vae': 'gpu:0'})  # im Prozess heißt die Suprim gpu:0
        # Abläufe ohne Kartenwahl rechnen auf seiner Standardkarte.
        self.assertEqual(studio.karten_waehlen(antwort(22000, 22000), {'fest': 4096}, b)[0]['mib'], {1: 4096})

    def test_erster_prozess_meidet_die_karte_des_zweiten_solange_der_laeuft(self):
        a, b = instanzen()
        ohne = studio.karten_waehlen(antwort(15000, 22000), {'eine': 9000}, a)[0]['mib']
        b.zustand = (time.time(), {'laeuft': True})
        mit = studio.karten_waehlen(antwort(15000, 22000), {'eine': 9000}, a)[0]['mib']
        self.assertEqual((ohne, mit), ({0: 9000}, {0: 9000}))
        # Passt es nur auf die Suprim, wartet Prozess 1 auf die FE, solange Prozess 2 läuft (die Suprim gehört ihm) …
        v, fehlend, _ = studio.karten_waehlen(antwort(1000, 22000), {'eine': 9000}, a)
        self.assertEqual((v['mib'], fehlend), ({0: 9000}, {0: 8000}))
        # … und nimmt sie, wenn Prozess 2 nicht läuft.
        b.zustand = (time.time(), {'laeuft': False})
        self.assertEqual(studio.karten_waehlen(antwort(1000, 22000), {'eine': 9000}, a)[0]['mib'], {1: 9000})
        b.zustand = (time.time(), {'laeuft': True})
        # Videos über zwei Karten bleiben möglich.
        self.assertEqual(set(studio.karten_waehlen(antwort(22000, 22000), VIDEO, a)[0]['mib']), {0, 1})

    def test_wer_was_kann(self):
        a, b = instanzen()
        self.assertTrue(a.kann(VIDEO) and a.kann(BILD) and b.kann({'eine': 1}) and b.kann({'fest': 1}))
        self.assertFalse(b.kann(VIDEO))
        self.assertTrue(b.kann(BILD))  # Bilder haben „eine“ und die geteilte Variante: Prozess 2 nimmt sie
        self.assertTrue(b.kann(VIDEO_EINE) and b.bevorzugt(VIDEO_EINE))
        self.assertFalse(a.bevorzugt(VIDEO_EINE) or b.bevorzugt(BILD))
        b.auf_monitor = True  # hängt der Monitor an der Suprim, rechnet Prozess 2 keine Videos
        self.assertFalse(b.kann(VIDEO_EINE) or b.bevorzugt(VIDEO_EINE))

    def test_video_ganz_auf_einer_karte_aber_nie_auf_der_monitorkarte(self):
        a, b = instanzen()
        # Monitor an der FE (21,3 GiB frei): das Video geht allein auf die Suprim, die FE bleibt für Bilder frei.
        v, fehlend, _ = studio.karten_waehlen(antwort(21790, 23400), VIDEO_EINE, a)
        self.assertEqual((v['mib'], v['geraete']['modell'], v['geraete']['clip'], fehlend), ({1: 22528}, 'gpu:1', 'gpu:1', {}))
        self.assertEqual(studio.karten_waehlen(antwort(21790, 23400), VIDEO_EINE, b)[0]['mib'], {1: 22528})
        # Auch wenn auf der Monitorkarte genug frei wäre, kommt das Video dort nicht allein hin.
        mon = antwort(23400, 23400)
        self.assertEqual(studio.karten_waehlen(mon, VIDEO_EINE, a)[0]['mib'], {1: 22528})
        mon['karten'][0]['monitor'], mon['karten'][1]['monitor'] = False, True
        self.assertEqual(studio.karten_waehlen(mon, VIDEO_EINE, a)[0]['mib'], {0: 22528})
        mon['karten'][0]['frei'] = 1500  # FE belegt, Monitor an der Suprim: geteilt warten statt Monitorkarte füllen
        v, fehlend, _ = studio.karten_waehlen(mon, VIDEO_EINE, a)
        self.assertEqual((v['rang'], bool(fehlend)), (1, True))
        self.assertEqual(studio.verteilungen(VIDEO_EINE, [0])[0]['ohne_monitor'], True)


class StudioMitZweiProzessen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wurzel = os.path.join(self.tmp.name, 'Studio')
        os.makedirs(os.path.join(self.wurzel, 'Praxis'))
        self.comfy_ordner = os.path.join(self.tmp.name, 'ComfyUI')
        os.makedirs(os.path.join(self.comfy_ordner, 'input'))
        zc = {'eintraege': [{'art': 'comfy', 'comfy_port': 8188, 'comfy_port_2': 8189, 'comfy_karte_2': 1,
                             'comfy_name_2': 'ComfyUI 2 (Suprim)', 'name': 'ComfyUI', 'comfy_ordner': self.comfy_ordner,
                             'studio_ordner': os.path.join(self.tmp.name, '2wild'), 'bedarf_je_karte_mib': 20000}]}
        with mock.patch('threading.Thread') as faden:
            self.s = studio.Studio({'studio': dict(S, ordner=self.wurzel)}, zc, self.tmp.name, lambda t: None,
                                   mock.MagicMock())
        self.faeden = faden.call_args_list
        self.a, self.b = self.s.instanzen

    def test_zwei_arbeiter_und_ihre_prozesse(self):
        self.assertEqual([(i.nr, i.port, i.schluessel, i.karten, i.zusatz) for i in self.s.instanzen],
                         [(1, 8188, 'bild-video', None, ''), (2, 8189, 'bild-video-2', [1], '-2')])
        self.assertEqual([c.kwargs.get('args') for c in self.faeden if c.kwargs.get('target') == self.s._schleife],
                         [(self.a,), (self.b,)])
        self.assertEqual((self.b.andere, self.a.andere), ([self.a], [self.b]))

    def test_zweiter_arbeiter_nimmt_nur_was_er_kann_und_nur_wenn_sein_prozess_laeuft(self):
        self.s.auftraege = [{'id': 'v', 'art': 'video_text', 'zustand': 'wartet'},
                            {'id': 'b', 'art': 'bild', 'zustand': 'wartet', 'breite': 1328, 'hoehe': 1328}]
        aus = {'laeuft': False}
        an = {'laeuft': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=aus):
            self.assertIsNone(self.s._naechster(self.b))
        with mock.patch.object(self.s, 'comfy_zustand', return_value=an):
            self.assertEqual(self.s._naechster(self.b)['id'], 'b')
            self.assertEqual(self.s._naechster(self.a)['id'], 'v')

    def test_video_auf_einer_karte_geht_an_prozess_2_das_bild_an_prozess_1(self):
        # Saschas Wunsch: Video auf der einen Karte, Bild auf der anderen – egal in welcher Reihenfolge bestellt.
        self.s.bedarf_video = VIDEO_EINE
        an = {'laeuft': True}
        for reihe in (('b', 'v'), ('v', 'b')):
            self.s.auftraege = [{'id': i, 'art': 'video_text' if i == 'v' else 'bild', 'zustand': 'wartet',
                                 'breite': 1328, 'hoehe': 1328} for i in reihe]
            self.b.zustand = (time.time(), an)
            with mock.patch.object(self.s, 'comfy_zustand', return_value=an):
                self.assertEqual((self.s._naechster(self.b)['id'], self.s._naechster(self.a)['id']), ('v', 'b'))
        # Läuft Prozess 2 nicht, rechnet Prozess 1 das Video selbst (der Reihe nach).
        self.b.zustand = (time.time(), {'laeuft': False})
        self.assertEqual(self.s._naechster(self.a)['id'], 'v')
        # Erst ein Bild, beide frei (gemessen 16.10.2026: sonst nahm Prozess 2 das Bild, das Video wartete): Mit dem Stand
        # der Zentrale bekommt Prozess 1 das Bild (passt allein auf die FE), Prozess 2 bleibt frei für ein Video.
        self.b.zustand = (time.time(), an)
        self.s.auftraege = [{'id': 'b', 'art': 'bild', 'zustand': 'wartet', 'breite': 1328, 'hoehe': 1328}]
        self.s._stand_zentrale = (time.time(), antwort(21790, 23400))
        with mock.patch.object(self.s, 'comfy_zustand', return_value=an):
            self.assertEqual((self.s._naechster(self.b), self.s._naechster(self.a)['id']), (None, 'b'))
            # Rechnet Prozess 1 schon, nimmt Prozess 2 das nächste Bild.
            self.s.auftraege.insert(0, {'id': 'x', 'art': 'bild', 'zustand': 'laeuft', 'prozess': 1})
            self.assertEqual(self.s._naechster(self.b)['id'], 'b')
            # Passt ein großes Bild nicht allein auf die FE, nimmt es Prozess 2 (auch wenn Prozess 1 frei ist).
            self.s.auftraege = [{'id': 'g', 'art': 'bild', 'zustand': 'wartet', 'breite': 2752, 'hoehe': 1536}]
            self.s.bedarf_gross = {'eine': 22016, 'haupt': 18432, 'neben': 6144}
            self.assertEqual((self.s._naechster(self.a), self.s._naechster(self.b)['id']), (None, 'g'))
            # Alter Stand (über 15 s): wer zuerst kommt.
            self.s._stand_zentrale = (time.time() - 60, antwort(21790, 23400))
            self.assertEqual(self.s._naechster(self.a)['id'], 'g')
        # Hängt der Monitor an der Suprim, behält Prozess 1 die Videos.
        self.s.auftraege = [{'id': i, 'art': 'video_text' if i == 'v' else 'bild', 'zustand': 'wartet',
                             'breite': 1328, 'hoehe': 1328} for i in ('v', 'b')]
        self.s._stand_zentrale = (0, None)
        self.b.zustand, self.b.auf_monitor = (time.time(), an), True
        with mock.patch.object(self.s, 'comfy_zustand', return_value=an):
            self.assertEqual((self.s._naechster(self.b)['id'], self.s._naechster(self.a)['id']), ('b', 'v'))

    def test_zweiter_prozess_schreibt_mit_namenszusatz_und_lokalen_geraeten(self):
        bereit = {'laeuft': True, 'ordner_ok': True}
        with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), \
                mock.patch.object(self.s, '_modell_da', return_value=True):
            code, r = self.s.erzeugen({'art': 'bild', 'prompt': 'Hund', 'breite': 1328, 'hoehe': 1328,
                                       'projekt': 'Praxis', 'variation': 6})
        a = self.s._finden(r['neu'][0])
        gesehen = {}

        def rechnen(auftrag, graph, meta, anmeldung):
            gesehen['praefix'] = [n['inputs'].get('filename_prefix') for n in graph.values()
                                  if n['class_type'] == 'SaveImage']
            gesehen['geraete'] = {n['inputs']['device'] for n in graph.values() if 'device' in n['inputs']}
            raise studio.Fehler('nur der Ablauf zählt')
        self.s._ort.inst = self.b
        try:
            with mock.patch.object(self.s, 'comfy_zustand', return_value=bereit), \
                    mock.patch.object(self.s, '_comfy_rechnen', side_effect=rechnen), self.assertRaises(studio.Fehler):
                self.s._rechnen(a, None, dict.fromkeys(studio.GERAETE_ROLLEN, 'gpu:1'))
        finally:
            self.s._ort.inst = None
        self.assertEqual(gesehen['praefix'], ['Praxis/Bild-2'])
        self.assertEqual(gesehen['geraete'] - {'default'}, {'gpu:0'})  # 'default' = die einzige Karte des Prozesses
        self.assertEqual(self.s.comfy_url, 'http://127.0.0.1:8188')  # außerhalb des Arbeiters: Prozess 1

    def test_gleiche_markierung_wird_nicht_neu_geschrieben(self):
        name = 'werkstatt_maske_abc.png'
        with open(os.path.join(self.comfy_ordner, 'input', name), 'wb') as f:
            f.write(b'PNG-1')
        with mock.patch.object(self.s, '_hochladen_senden', return_value='neu.png') as senden:
            self.assertEqual(self.s._hochladen_daten(b'PNG-1', name, ueberschreiben=True), name)
            senden.assert_not_called()
            self.assertEqual(self.s._hochladen_daten(b'PNG-2', name, ueberschreiben=True), 'neu.png')
            self.assertEqual(self.s._hochladen_daten(b'PNG-1', 'vorlage.png'), 'neu.png')  # Vorlagen: wie bisher

    def test_bibliothek_legt_begleitdatei_nur_neu_an(self):
        pfad = os.path.join(self.wurzel, 'Praxis', 'Bild-2_00001_.png.json')
        with open(pfad, 'w', encoding='utf-8') as f:
            f.write('{"vom": "Auftrag"}')
        self.s._anlegen_exklusiv(pfad, {'vom': 'Bibliothek'})
        with open(pfad, encoding='utf-8') as f:
            self.assertEqual(f.read(), '{"vom": "Auftrag"}')
        self.assertEqual([n for n in os.listdir(os.path.dirname(pfad)) if n.endswith('.tmp')], [])
        neu = os.path.join(self.wurzel, 'Praxis', 'Bild_00009_.png.json')
        self.s._anlegen_exklusiv(neu, {'vom': 'Bibliothek'})
        self.assertTrue(os.path.isfile(neu))

    def test_stand_nennt_den_zweiten_prozess(self):
        with mock.patch.object(self.s, 'comfy_zustand', return_value={'laeuft': True}), \
                mock.patch.object(self.s, 'einstellungen', return_value={}), \
                mock.patch.object(self.s, '_bibliothek_stand', return_value=0):
            st = self.s.stand()
        self.assertEqual(st['comfy_weitere'], [{'laeuft': True, 'name': 'ComfyUI 2 (Suprim)', 'nr': 2}])

    def test_verlorene_antwort_auf_die_uebergabe_gibt_nicht_frei(self):
        # Antwortet ComfyUI auf /prompt nicht, läuft der Prozess aber noch, wartet das Studio mit der eigenen Kennung.
        a = {'id': 'x', 'art': 'bild', 'schritte': 6}
        aufrufe = []

        def anfrage(pfad, daten=None, timeout=10, inst=None):
            aufrufe.append(pfad)
            if pfad == '/prompt':
                kennung['wert'] = daten['prompt_id']
                raise studio.ComfyAus('Zeitüberschreitung')
            return {kennung['wert']: {'status': {'completed': True}, 'outputs': {}}}
        kennung = {}
        with mock.patch.object(self.s, '_comfy_anfrage', side_effect=anfrage), \
                mock.patch.object(studio.winapi, 'prozess_beendet', return_value=False), \
                mock.patch.object(self.s, '_erwartet', return_value=10), \
                mock.patch.object(studio.time, 'sleep'):
            eintrag = self.s._comfy_rechnen_mit(a, {}, {}, None, handle=1)
        self.assertEqual(eintrag['status'], {'completed': True})
        self.assertEqual(a['prompt_id'], kennung['wert'])
        self.assertEqual(aufrufe[:2], ['/prompt', f"/history/{kennung['wert']}"])


if __name__ == '__main__':
    unittest.main()
