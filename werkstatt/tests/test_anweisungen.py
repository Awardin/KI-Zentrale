import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from werkstatt import anweisungen  # noqa: E402

VORHER = ('# Meine Wissens-Prompts\r\n\r\nAktualisiert: 20.09.2026. Sammlung.\r\n\r\n'
          '## 3. Transkripte und Folien\r\n\r\n### Video lokal verarbeiten – watch\r\n\r\n~~~text\r\nNutze watch.\r\n~~~ \r\n\r\n'
          'Ein YouTube-Link allein ist noch kein gelesener Videoinhalt.\n\n'
          '## 4. Suchen und anwenden\r\n\r\n~~~text\r\nSuche.\r\n~~~\r\n')


class Sammlung(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pfad = os.path.join(self.tmp.name, 'Prompts.md')
        with open(self.pfad, 'w', encoding='utf-8', newline='') as f:
            f.write(VORHER)
        self.s = anweisungen.Sammlung(self.pfad)

    def tearDown(self):
        self.tmp.cleanup()

    def roh(self):
        with open(self.pfad, encoding='utf-8', newline='') as f:
            return f.read()

    def test_einrichten_fuegt_nur_hinzu(self):
        self.assertFalse(self.s.lesen()['abschnitt'])
        self.assertTrue(self.s.einrichten())
        self.assertFalse(self.s.einrichten())
        roh = self.roh()
        # Alles Bisherige ist Byte für Byte erhalten, nur das Datum ist neu.
        vorne, _, hinten = VORHER.partition('## 4. ')
        self.assertIn(vorne.replace('20.09.2026', roh[roh.index('Aktualisiert: ') + 14:][:10]), roh)
        self.assertTrue(roh.endswith('## 4. ' + hinten))
        self.assertLess(roh.index(anweisungen.ABSCHNITT), roh.index('## 4. '))
        d = self.s.lesen()
        self.assertEqual([a['name'] for a in d['anweisungen']], ['Kurzzusammenfassung', 'Ausführliche Analyse', 'Gezielte Frage'])
        self.assertTrue(d['rahmen']['text'].startswith('Dies ist eine eigenständige'))
        self.assertEqual([a['frage'] for a in d['anweisungen']], [False, False, True])

    def test_bearbeiten_umbenennen_neu_loeschen(self):
        self.s.einrichten()
        a = self.s.lesen()['anweisungen'][0]
        self.s.speichern(a['name'], 'Kurz!\n\n[Transkript]', a['stand'], neuer_name='Ganz kurz')
        d = self.s.lesen()
        self.assertEqual(d['anweisungen'][0]['name'], 'Ganz kurz')
        self.assertEqual(d['anweisungen'][0]['text'], 'Kurz!\n\n[Transkript]')
        with self.assertRaises(anweisungen.Konflikt):
            self.s.speichern('Ganz kurz', 'x', a['stand'])  # veralteter Stand
        self.s.neu('Meine Variante', 'Variante [Titel]')
        self.assertEqual(self.s.lesen()['anweisungen'][-1]['name'], 'Meine Variante')
        with self.assertRaises(ValueError):
            self.s.neu('Meine Variante', 'doppelt')
        with self.assertRaises(ValueError):
            self.s.neu('Kasten', 'a\n~~~\nb')
        n = self.s.lesen()['anweisungen'][-1]
        self.s.loeschen(n['name'], n['stand'])
        self.assertNotIn('Meine Variante', [x['name'] for x in self.s.lesen()['anweisungen']])
        with self.assertRaises(ValueError):
            self.s.loeschen(anweisungen.RAHMEN, 'x')
        # Außerhalb des Abschnitts hat sich nichts verändert.
        self.assertTrue(self.roh().endswith('## 4. Suchen und anwenden\r\n\r\n~~~text\r\nSuche.\r\n~~~\r\n'))
        self.assertIn('~~~text\r\nNutze watch.\r\n~~~ \r\n', self.roh())


class Zusammenbauen(unittest.TestCase):
    def test_platzhalter_und_transkript_zuletzt(self):
        p = anweisungen.zusammenbauen('Rahmen.', 'Titel: [Titel]\nFrage: [Frage]\n[Transkript]',
                                      {'Titel': 'Schulter', 'Frage': 'Wie oft?'}, '[00:00:01] Sag [Titel] nicht')
        self.assertEqual(p, 'Rahmen.\n\nTitel: Schulter\nFrage: Wie oft?\n[00:00:01] Sag [Titel] nicht')

    def test_ohne_platzhalter_wird_angehaengt(self):
        p = anweisungen.zusammenbauen('', 'Fasse zusammen.', {}, 'TEXT')
        self.assertTrue(p.endswith('Transkript mit Zeitmarken:\n\nTEXT'))


if __name__ == '__main__':
    unittest.main()
