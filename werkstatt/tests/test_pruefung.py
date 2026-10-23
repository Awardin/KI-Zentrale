"""Automatische Nachprüfung: Zeitmarken, Abdeckung, fremde Schriftzeichen und Ablauf."""
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import auswertung, pruefung  # noqa: E402


def hms(s):
    return f'{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02}'


def transkript(*abschnitte):
    return '\n'.join(f'[{hms(sekunde)}] ' + ' '.join(['wort'] * woerter) for sekunde, woerter in abschnitte)


class Nachpruefen(unittest.TestCase):
    def test_gueltige_zeitmarken_mit_toleranz(self):
        t = transkript((0, 5), (10, 5), (1200, 5))
        r = pruefung.nachpruefen('[00:00:04] A [00:00:15] B [00:20:05] C', t, False)
        self.assertEqual((r['zeitmarken_geprueft'], r['zeitmarken_ungueltig']), (3, []))
        self.assertIn('- Zeitmarken: 3 geprüft, alle im Transkript.', r['block'])

    def test_ungueltige_zeitmarken_werden_genannt(self):
        t = transkript((0, 5), (10, 5), (1200, 5))
        r = pruefung.nachpruefen('[00:00:20] A [00:20:06] B', t, False)
        self.assertEqual(r['zeitmarken_ungueltig'], ['[00:00:20]', '[00:20:06]'])
        self.assertIn('- Zeitmarken: 2 nicht im Transkript: [00:00:20], [00:20:06]', r['block'])

    def test_zeitbereiche_werden_geprueft(self):
        t = transkript((0, 5), (1200, 5))
        r = pruefung.nachpruefen('Bereich [00:00:00]–[00:20:05]', t, False)
        self.assertEqual((r['zeitmarken_geprueft'], r['zeitmarken_ungueltig']), (2, []))

    def test_hoechstens_zehn_ungueltige_werden_genannt(self):
        t = transkript((0, 5))
        text = ' '.join(f'[{hms(3000 + i * 10)}]' for i in range(12))
        r = pruefung.nachpruefen(text, t, False)
        self.assertEqual(len(r['zeitmarken_ungueltig']), 12)
        self.assertEqual(r['block'].split(': ', 1)[1].count('['), 10)

    def test_ohne_zeitmarke_im_ergebnis(self):
        r = pruefung.nachpruefen('Nur Text', transkript((0, 5)), False)
        self.assertTrue(r['keine_zeitmarke'])
        self.assertIn('- Zeitmarken: keine im Ergebnis', r['block'])


class Abdeckung(unittest.TestCase):
    def setUp(self):
        self.t = transkript((0, 60), (300, 60), (600, 60), (900, 60))

    def test_luecke_wird_als_minutenbereich_gemeldet(self):
        r = pruefung.nachpruefen('[00:00:00] A [00:10:00] B [00:15:00] C', self.t, True)
        self.assertEqual(r['abdeckung_fehlt'], ['Minute 5–10'])
        self.assertIn('- Abdeckung: ohne Stichpunkt: Minute 5–10', r['block'])

    def test_zusammenhaengende_luecke(self):
        r = pruefung.nachpruefen('[00:00:00] A', self.t, True)
        self.assertEqual(r['abdeckung_fehlt'], ['Minute 5–20'])

    def test_duennes_fenster_wird_nicht_gemeldet(self):
        t = transkript((0, 60), (300, 10), (600, 60))
        r = pruefung.nachpruefen('[00:00:00] A [00:10:00] B', t, True)
        self.assertEqual(r['abdeckung_fehlt'], [])

    def test_ohne_abdeckungspruefung_keine_zeile(self):
        r = pruefung.nachpruefen('[00:00:00] A', self.t, False)
        self.assertIsNone(r['abdeckung_fehlt'])
        self.assertNotIn('Abdeckung:', r['block'])

    def test_alle_inhaltlichen_fenster_belegt(self):
        r = pruefung.nachpruefen('[00:00:00] A [00:05:00] B [00:10:00] C [00:15:00] D', self.t, True)
        self.assertEqual(r['abdeckung_fehlt'], [])
        self.assertIn('- Abdeckung: alle inhaltlichen Abschnitte haben Stichpunkte.', r['block'])


class FremdeSchriftzeichen(unittest.TestCase):
    def test_cjk_zeichen_werden_gezaehlt(self):
        r = pruefung.nachpruefen('Deutsch 中文 한국어 カタカナ', transkript((0, 5)), False)
        self.assertEqual(r['fremde_schriftzeichen'], 9)
        self.assertIn('- Fremde Schriftzeichen: 9 Stellen – ‚Wiederholen‘ empfohlen', r['block'])
        self.assertIn('fremde Schriftzeichen', r['kurz'])

    def test_ohne_fremde_zeichen(self):
        r = pruefung.nachpruefen('Nur Deutsch', transkript((0, 5)), False)
        self.assertEqual(r['fremde_schriftzeichen'], 0)
        self.assertIn('- Fremde Schriftzeichen: keine.', r['block'])
        self.assertEqual(r['kurz'], 'in Ordnung')


class Kurzfassung(unittest.TestCase):
    def test_in_ordnung_und_hinweise(self):
        t = transkript((0, 60), (300, 60), (600, 60))
        self.assertEqual(pruefung.nachpruefen('[00:00:00] A [00:05:00] B [00:10:00] C', t, True)['kurz'],
                         'in Ordnung')
        r = pruefung.nachpruefen('[00:00:00] A [00:00:20] B 中', t, True)
        self.assertEqual(r['kurz'], 'Hinweise: 1 Zeitmarke, Minute 5–15, fremde Schriftzeichen')


class Fake:
    schluessel, name, cloud = 'fake', 'Fake', None

    def __init__(self, text):
        self.text = text
        self.prompts = []

    def verfuegbar(self, profil, frisch=False):
        return True, ''

    def ausfuehren(self, profil, prompt, lauf):
        self.prompts.append(prompt)
        return {'text': self.text, 'tokens': 42}


class Ablauf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = os.path.join(self.tmp.name, 'Titel [abc]')
        self.lauf = os.path.join(self.video, 'lauf')
        os.makedirs(self.lauf)
        for n, inhalt in (('transcript-timestamps.txt', transkript((0, 60), (300, 60), (600, 60))),
                          ('transcript.txt', 'wort ' * 800), ('transcript.json', ''), ('transcript.srt', '')):
            with open(os.path.join(self.lauf, n), 'w', encoding='utf-8') as f:
                f.write(inhalt)
        cfg = {'watch': {'arbeitsordner': os.path.join(self.tmp.name, 'watch')},
               'promptsammlung': os.path.join(self.tmp.name, 'prompts.md'),
               'auswerter_vorschlag': [], 'cloud_parallel': 0,
               'zentrale_config': os.path.join(self.tmp.name, 'zentrale.json')}
        self.au = auswertung.Auswertungen(cfg, os.path.join(self.tmp.name, 'daten'), lambda text: None)
        self.au.sammlung.lesen = self.sammlung

    def sammlung(self, text='Umfang: [Zielumfang]\n\n[Transkript]', frage=False):
        return {'rahmen': None, 'anweisungen': [
            {'name': 'Kurzzusammenfassung', 'text': text, 'stand': 'x', 'frage': frage}]}

    def ablauf(self, text, frage=None):
        fake = Fake(text)
        self.au.anbieter['fake'] = fake
        a = {'id': 'x', 'transkript': self.lauf, 'ordner': self.video, 'titel': 'Titel', 'quelle': 'Quelle',
             'dauer': 600, 'auswerter': {'id': 'p', 'anbieter': 'fake', 'modell': 'x', 'stufe': None,
                                         'name': 'Fake · x'},
             'anweisung': {'name': 'Kurzzusammenfassung', 'stand': 'x'}, 'frage': frage, 'begonnen': time.time()}
        self.au._abbruch['x'] = threading.Event()
        self.au._ausfuehren(a)
        return a, fake

    def test_block_und_kopf_stehen_in_der_fassung(self):
        a, fake = self.ablauf('[00:00:00] Anfang\n[00:05:00] Mitte\n[00:10:00] Ende')
        with open(a['datei'], encoding='utf-8') as f:
            roh = f.read()
        self.assertIn('**Prüfung der Werkstatt (automatisch):**', roh)
        self.assertIn('- Zeitmarken: 3 geprüft, alle im Transkript.', roh)
        self.assertIn('- Abdeckung: alle inhaltlichen Abschnitte haben Stichpunkte.', roh)
        self.assertIn('pruefung: "in Ordnung"', roh)
        self.assertEqual(a['pruefung'], 'in Ordnung')
        self.assertIn('etwa 400 Wörter (rund 16 Stichpunkte)', fake.prompts[0])  # aus transcript.txt
        self.assertIn('pruefung', auswertung.FELDER)

    def test_hinweise_stehen_im_dateikopf(self):
        a, _ = self.ablauf('[00:00:00] A\n[00:05:00] B\n[00:10:00] C\n[00:20:06] D')
        with open(a['datei'], encoding='utf-8') as f:
            roh = f.read()
        self.assertEqual(a['pruefung'], 'Hinweise: 1 Zeitmarke')
        self.assertIn('pruefung: "Hinweise: 1 Zeitmarke"', roh)

    def test_anweisung_mit_frage_ohne_abdeckungszeile(self):
        self.au.sammlung.lesen = lambda: self.sammlung('Beantworte [Frage]\n\n[Transkript]', True)
        a, _ = self.ablauf('Antwort ohne Zeitmarke', frage='Warum?')
        with open(a['datei'], encoding='utf-8') as f:
            roh = f.read()
        self.assertIn('- Zeitmarken: keine im Ergebnis', roh)
        self.assertNotIn('Abdeckung:', roh)


if __name__ == '__main__':
    unittest.main()
