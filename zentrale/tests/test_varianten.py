"""Varianten (Kontextgröße) je Eintrag, seit 14.10.2026: Ornith Q4 256K/32K, Strata 128K mit Bildern/256K."""
import copy
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale import planung  # noqa: E402
from zentrale.aktionen import Aktionen  # noqa: E402
from zentrale.erfassung import Erfassung  # noqa: E402
from zentrale.server import Zentrale  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8') as f:
    KONFIG = json.load(f)
E = {e['id']: e for e in KONFIG['eintraege']}


class Auswahl(unittest.TestCase):
    def test_standard_gewaehlt_und_unbekannt(self):
        q4 = E['ornith-q4']
        self.assertEqual(planung.variante(q4)['variante'], '256k')
        self.assertEqual(planung.variante(q4)['ollama_optionen'], {'num_batch': 256, 'num_ctx': 262144})
        v = planung.variante(q4, '32k')
        self.assertEqual((v['bedarf_gesamt_mib'], v['ollama_optionen']['num_ctx'], v['variante_name']),
                         (23000, 32768, '32K Kontext (weniger Speicher)'))
        self.assertNotIn('variante', q4)  # der Eintrag selbst bleibt unverändert
        with self.assertRaisesRegex(ValueError, 'Unbekannte Variante'):
            planung.variante(q4, '1m')
        self.assertIs(planung.variante(E['ninfer']), E['ninfer'])
        with self.assertRaisesRegex(ValueError, 'keine Varianten'):
            planung.variante(E['ninfer'], '32k')

    def test_konfiguration(self):
        self.assertEqual([(v['id'], v.get('standard', False)) for v in E['ornith-q4']['varianten']],
                         [('256k', True), ('32k', False)])
        self.assertNotIn('varianten', E['ornith-q5'])  # Hermes fragt Q5 ohne Optionen an: fest 128K
        s = {v['id']: v for v in E['flash-next-strata']['varianten']}
        self.assertTrue(s['128k']['konfig'].endswith('strata-iq3_xxs-2gpu-128k.json'))
        # Seit 01.11.2026 ist Q4 Standard (weniger Arbeitsspeicher als IQ3_XXS, Wunsch Sascha).
        self.assertEqual([v['id'] for v in E['flash-next-strata']['varianten'] if v.get('standard')], ['q4'])
        self.assertTrue(s['256k']['konfig'].endswith('strata-iq3_xxs-2gpu-256k.json'))
        # Q4 (16.10.2026): eigene Strata-Einstellung, weniger RAM-Bedarf als IQ3_XXS (Rahmen 32 GiB statt alle Experten).
        q4 = planung.variante(E['flash-next-strata'], 'q4')
        self.assertTrue(q4['konfig'].endswith('strata-unsloth-ud-iq4_xs-2gpu-128k.json'))
        self.assertEqual((q4['ram_bedarf_gib'], q4['kontext'], q4['modell']),
                         (40, 131072, 'qwen3.8-flash-next-unsloth-ud-iq4_xs'))
        self.assertEqual(planung.variante(E['flash-next-strata'])['ram_bedarf_gib'], 40)
        self.assertEqual(planung.variante(E['flash-next-strata'], '128k')['ram_bedarf_gib'], 42)
        # Q4 mit 256K (01.11.2026): eigene Einstellung, Kontextspeicher im RAM (--kv-resident), Bilder bleiben.
        q4_256 = planung.variante(E['flash-next-strata'], 'q4-256k')
        self.assertTrue(q4_256['konfig'].endswith('strata-unsloth-ud-iq4_xs-2gpu-256k.json'))
        self.assertEqual((q4_256['kontext'], q4_256['modell']), (262144, 'qwen3.8-flash-next-unsloth-ud-iq4_xs'))
        # Jede Strata-Variante nennt Modell und Kontext, damit die Anzeige die laufende Fassung erkennt.
        paare = [(v['modell'], v['kontext']) for v in E['flash-next-strata']['varianten']]
        self.assertEqual(len(paare), len(set(paare)))


class Server(unittest.TestCase):
    def setUp(self):
        self.z = Zentrale.__new__(Zentrale)
        self.z.cfg = KONFIG
        self.z.eintraege = dict(E)
        self.z.laufend = {}
        self.roh = {'karten': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3090', 'bus': 2, 'gesamt': 24576, 'belegt': 1000},
                               {'index': 1, 'name': 'NVIDIA GeForce RTX 3090', 'bus': 4, 'gesamt': 24576, 'belegt': 1000}],
                    'verbraucher': []}
        self.z._aktuell = Mock(return_value=self.roh)
        self.z._anmeldung_rest = Mock(return_value=({}, 'Werkstatt', '#000'))
        self.z.akt = Mock()
        self.z._schritte_ausfuehren = Mock()
        self.z._im_hintergrund = Mock(side_effect=lambda text, fn: (self.texte.append(text), fn(), True)[2])
        self.texte = []

    def test_plan_rechnet_mit_dem_bedarf_der_variante(self):
        # Frei sind zusammen 24.616 MiB (nach Reserve): 256K (26,5 GiB) passt nicht, 32K (23 GiB) schon.
        self.roh['karten'][0]['belegt'] = 11500
        self.roh['karten'][1]['belegt'] = 11500
        self.assertFalse(self.z.plan('ornith-q4', 'starten')['genug_platz'])
        self.assertTrue(self.z.plan('ornith-q4', 'starten', '32k')['genug_platz'])
        with self.assertRaises(ValueError):
            self.z.plan('ornith-q4', 'starten', '1m')

    def test_start_gibt_die_variante_weiter(self):
        self.assertEqual(self.z.starten('ornith-q4', [], False, '32k'), (202, {'ok': True}))
        self.z.akt.starten.assert_called_once_with('ornith-q4', variante='32k')
        self.assertEqual(self.texte, ['Ornith 1.5 · Q4 (32K Kontext (weniger Speicher)) wird geladen …'])
        self.z.akt.reset_mock()
        self.assertEqual(self.z.starten('ornith-q4', [], False), (202, {'ok': True}))
        self.z.akt.starten.assert_called_once_with('ornith-q4', variante='256k')
        self.z.akt.reset_mock()
        self.assertEqual(self.z.starten('ornith-q5', [], False)[0], 202)
        self.z.akt.starten.assert_called_once_with('ornith-q5')  # ohne Varianten wie bisher
        self.assertEqual(self.z.starten('ornith-q4', [], False, '1m'), (400, {'fehler': 'Unbekannte Variante: 1m'}))

    def test_konfig_nennt_varianten_mit_kontext(self):
        self.z.erf = Mock()
        e = next(x for x in self.z.konfig()['eintraege'] if x['id'] == 'ornith-q4')
        self.assertEqual([(v['id'], v['kontext'], v['bedarf_gesamt_mib']) for v in e['varianten']],
                         [('256k', 262144, 26500), ('32k', 32768, 23000)])
        s = next(x for x in self.z.konfig()['eintraege'] if x['id'] == 'flash-next-strata')
        self.assertEqual([(v['id'], v['kontext']) for v in s['varianten']],
                         [('128k', 131072), ('256k', 262144), ('q4', 131072), ('q4-256k', 262144)])
        self.assertNotIn('konfig', s['varianten'][0])  # Pfade bleiben im Dienst


class Aktion(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(KONFIG)
        with patch('gemeinsam.winapi.VramJeProzess'), patch('gemeinsam.winapi.adapter_pci_busse', return_value={}):
            self.erf = Erfassung(self.cfg)
        self.akt = Aktionen(self.cfg, self.erf, 'logs', Mock())

    def test_ollama_laedt_mit_dem_kontext_der_variante(self):
        geladen = []
        with patch.object(self.akt, '_ollama_bereit'), \
                patch.object(self.akt, '_ollama_geladen', side_effect=lambda: list(geladen)), \
                patch('zentrale.aktionen.http_json', side_effect=lambda url, d, timeout: geladen.append(d['model'])) as h:
            text = self.akt.starten('ornith-q4', variante='32k')
        self.assertEqual(h.call_args.args[1]['options'], {'num_batch': 256, 'num_ctx': 32768})
        self.assertTrue(text.startswith('Ornith 1.5 · Q4 (32K Kontext (weniger Speicher)) geladen'))

    def test_strata_startet_mit_der_einstellung_der_variante(self):
        self.erf.messen = Mock(return_value={'dienste': {'strata': {'zustand': 'aus'}}})
        with patch('zentrale.aktionen.os.path.exists', return_value=True), \
                patch('gemeinsam.winapi.freier_arbeitsspeicher_mib', return_value=50 * 1024), \
                patch('gemeinsam.winapi.starte_losgeloest') as start, \
                patch('zentrale.aktionen.http_json', return_value={'loaded': True, 'max_context': 262144}):
            start.return_value.poll.return_value = None
            self.assertIn('Kontext 262.144', self.akt.starten('flash-next-strata', variante='256k'))
        argv = start.call_args.args[0]
        self.assertTrue(argv[argv.index('--config') + 1].endswith('strata-iq3_xxs-2gpu-256k.json'))

    def test_strata_q4_startet_mit_eigener_einstellung_und_ram_pruefung(self):
        self.erf.messen = Mock(return_value={'dienste': {'strata': {'zustand': 'aus'}}})
        with patch('zentrale.aktionen.os.path.exists', return_value=True), \
                patch('gemeinsam.winapi.freier_arbeitsspeicher_mib', return_value=41 * 1024), \
                patch('gemeinsam.winapi.starte_losgeloest') as start, \
                patch('zentrale.aktionen.http_json', return_value={'loaded': True, 'max_context': 131072}):
            start.return_value.poll.return_value = None
            self.akt.starten('flash-next-strata', variante='q4')  # 41 GiB frei reichen für Q4 (40), nicht für IQ3_XXS (42)
            with self.assertRaisesRegex(Exception, 'braucht etwa 42,0 GiB'):
                self.akt.starten('flash-next-strata', variante='128k')
        argv = start.call_args_list[0].args[0]
        self.assertTrue(argv[argv.index('--config') + 1].endswith('strata-unsloth-ud-iq4_xs-2gpu-128k.json'))
        self.assertEqual(argv[argv.index('--port') + 1], '8095')


if __name__ == '__main__':
    unittest.main()
