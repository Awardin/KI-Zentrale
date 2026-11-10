"""Promptläufe mit temporären Dateien und zählendem Fake; keine Modelle oder Dienste."""
import copy
import ctypes
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkstatt import auswertung, prompts


class ClaudeAblage(unittest.TestCase):
    """Nur temporäre Verzeichnisse durchsuchen; Claude wird nie ausgeführt."""
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.local = Path(tmp.name) / 'Local'
        self.roaming = Path(tmp.name) / 'Roaming'
        for name, pfad in [('LOCALAPPDATA', self.local), ('APPDATA', self.roaming)]:
            self.enterContext(patch.object(auswertung, name, str(pfad)))
        self.claude = auswertung.Claude({})

    def pfad(self, art, version, kennung='a33aa5518497'):
        if art == 'neu':
            return self.local / 'Claude-Data' / 'claude_test' / 'claude-code' / version / kennung / 'claude.exe'
        if art == 'paket':
            return (self.local / 'Packages' / 'Claude_test' / 'LocalCache' / 'Roaming' / 'Claude'
                    / 'claude-code' / version / 'claude.exe')
        return self.roaming / 'Claude' / 'claude-code' / version / 'claude.exe'

    def datei(self, art, version, kennung='a33aa5518497', zeit=100):
        pfad = self.pfad(art, version, kennung)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.touch()
        os.utime(pfad, (zeit, zeit))
        return str(pfad)

    def test_neues_layout_hoechste_version_statt_kennung_oder_zeit(self):
        self.datei('neu', '2.1.309', '999999999999', zeit=300)
        erwartet = self.datei('neu', '2.1.317', zeit=100)
        self.assertEqual(self.claude.exe(), erwartet)

    def test_neues_layout_version_numerisch(self):
        self.datei('neu', '2.1.99')
        erwartet = self.datei('neu', '2.1.317')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_gleiche_version_neueste_datei_in_beliebigem_app_ordner(self):
        self.datei('neu', '2.1.317', '999999999999', zeit=100)
        erwartet = self.datei('neu', '2.1.317', '000000000001', zeit=200)
        self.assertEqual(self.claude.exe(), erwartet)

    def test_altes_paketlayout_hoechste_version(self):
        self.datei('paket', '2.1.99')
        erwartet = self.datei('paket', '2.1.317')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_nur_appdata_layout(self):
        erwartet = self.datei('roaming', '2.1.317')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_neues_layout_hat_vorrang_vor_beiden_alten(self):
        erwartet = self.datei('neu', '2.1.99')
        self.datei('paket', '9.0.0')
        self.datei('roaming', '10.0.0')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_paket_vor_appdata(self):
        erwartet = self.datei('paket', '2.1.99')
        self.datei('roaming', '10.0.0')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_nur_dateien_zaehlen_auch_beim_rueckfall(self):
        for art in ['neu', 'paket', 'roaming']:
            with self.subTest(art=art):
                self.pfad(art, '99.0.0').parent.mkdir(parents=True)
                self.pfad(art, '98.0.0').mkdir(parents=True)
        self.assertIsNone(self.claude.exe())
        erwartet = self.datei('roaming', '2.1.317')
        self.assertEqual(self.claude.exe(), erwartet)

    def test_nichts_vorhanden(self):
        self.assertIsNone(self.claude.exe())


class AboZugang(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.basis = Path(tmp.name)
        self.enterContext(patch.object(auswertung, 'HOME', str(self.basis)))
        self.codex = auswertung.Codex({})
        self.claude = auswertung.Claude({})
        self.enterContext(patch.object(self.codex, 'exe', return_value='fake-codex.exe'))
        self.enterContext(patch.object(self.claude, 'exe', return_value='fake-claude.exe'))
        self.au = auswertung.Auswertungen.__new__(auswertung.Auswertungen)
        self.au.anbieter = {'codex': self.codex, 'claude': self.claude}
        self.p = {'id': 'c', 'name': 'Codex', 'anbieter': 'codex', 'modell': 'modell'}
        self.enterContext(patch.object(self.codex, 'kontext', return_value=131072))
        self.enterContext(patch.object(self.claude, 'kontext', return_value=131072))

    def auth(self, wert):
        datei = self.basis / '.codex/auth.json'
        datei.parent.mkdir(exist_ok=True)
        datei.write_text(json.dumps(wert), encoding='utf-8')

    def test_codex_abo_api_unbekannt_keiner_ohne_geheimnisse(self):
        self.assertEqual(self.codex.zugang(), 'keiner')
        for modus, erwartet in [('chatgpt', 'abo'), ('api', 'api'), ('neu', 'unklar'), ([], 'unklar'), (None, 'unklar')]:
            self.auth({'auth_mode': modus, 'tokens': {'access_token': 'GEHEIM-TEST'}})
            info = self.au.profil_info(self.p)
            self.assertEqual(info['zugang'], erwartet)
            self.assertEqual(info['prompts_verfuegbar'], erwartet == 'abo')
            self.assertTrue(info['verfuegbar'])  # Zusammenfassungsweg bleibt erhalten.
            self.assertNotIn('GEHEIM', json.dumps(info))
        self.auth({'tokens': {'access_token': 'GEHEIM-TEST'}})
        self.assertEqual(self.codex.zugang(), 'unklar')

    def test_claude_abo_api_keine_anmeldung(self):
        p = dict(self.p, anbieter='claude')
        for art, erwartet in [('claude.ai', 'abo'), ('api_key', 'api'), ('unbekannt', 'unklar'), (None, 'keiner')]:
            with patch.object(self.claude, 'anmeldung', return_value=art):
                info = self.au.profil_info(p)
                self.assertEqual(info['zugang'], erwartet)
                self.assertEqual(info['prompts_verfuegbar'], erwartet == 'abo')
                self.assertEqual(info['verfuegbar'], art is not None)

    def test_claude_frische_anmeldung_umgeht_cache(self):
        self.claude._cache['anmeldung'] = (auswertung.time.time(), 'claude.ai')
        with patch.object(auswertung, '_ausgabe', return_value='{"loggedIn":true,"authMethod":"api_key"}') as aufruf:
            self.assertEqual(self.claude.zugang(), 'abo')
            self.assertEqual(self.claude.zugang(frisch=True), 'api')
        self.assertEqual(aufruf.call_count, 1)

    def test_codex_kindprozess_ohne_api_overrides(self):
        from unittest.mock import Mock
        lauf = Mock(id='test', leer=str(self.basis))
        def programm(argv, text, env):
            Path(argv[argv.index('-o') + 1]).write_text('Antwort', encoding='utf-8')
            self.assertEqual(text, 'Test')
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('OPENAI_BASE_URL', env)
            self.assertNotIn('CODEX_API_KEY', env)
            self.assertEqual(env['TEST_BEHALTEN'], 'ja')
            return 0, '', ''
        lauf.programm.side_effect = programm
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fake', 'OPENAI_BASE_URL': 'fake',
                                     'CODEX_API_KEY': 'fake', 'TEST_BEHALTEN': 'ja'}):
            self.assertEqual(self.codex.ausfuehren(self.p, 'Test', lauf)['text'], 'Antwort')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'fake')
        self.assertEqual(lauf.programm.call_count, 1)


class Fake(auswertung.Anbieter):
    schluessel, name, cloud = 'fake', 'Fake', None

    def __init__(self):
        super().__init__({})
        self.aufrufe = 0
        self.kontextwert = 131072
        self.texte = []
        self.fehler = False
        self.waehrend = None

    def katalog(self):
        return [{'modell': 'modell', 'kontext': self.kontextwert}]

    def ausfuehren(self, profil, prompt, lauf):
        self.aufrufe += 1
        self.texte.append(prompt)
        if self.fehler:
            raise RuntimeError('MARKIERUNG-GEHEIM aus der Anbieterausgabe')
        if self.waehrend:
            self.waehrend()
        return {'text': f'```html\n<html>Antwort {self.aufrufe}</html>\n```', 'tokens': 19, 'kosten_usd': 0.2}


class Ende(BaseException):
    pass


class PromptLaeufe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.basis = Path(self.tmp.name)
        self.sammlung = self.basis / 'Sammlung.md'
        self.sammlung.write_text('### Wissen\n~~~text\nSammlung [A]\n~~~\n' + prompts.ABSCHNITT
                                 + '\n#### Rahmen\n~~~text\nRahmentext\n~~~\n', encoding='utf-8')
        self.cfg = {'watch': {'arbeitsordner': str(self.basis / 'watch')},
            'promptsammlung': str(self.sammlung), 'cloud_parallel': 0,
            'auswerter_vorschlag': [{'id': 'p', 'anbieter': 'fake', 'modell': 'modell', 'name': 'Fake'}],
            'prompts': {'ordner': str(self.basis / 'Prompts'), 'dateiwurzeln': [str(self.basis)],
                        'feld_max_zeichen': 400000}}
        self.logs = []
        self.au = self.neu()
        self.p = self.au.prompts
        self.e = self.p.neu('Hühnerfarm', '', 'html', 'Baue [A].')
        self.fake = self.au.anbieter['fake']
        self.daten = {'id': self.e['id'], 'fassungen': ['Fassung 1'], 'auswerter': ['p'],
                       'eingaben': {'felder': {'A': {'art': 'text', 'wert': 'HTML'}}}}

    def neu(self):
        au = auswertung.Auswertungen(self.cfg, str(self.basis / 'daten'), self.logs.append)
        au.anbieter['fake'] = Fake()
        return au

    def einreihen(self, daten=None):
        daten = copy.deepcopy(daten or self.daten)
        v = self.p.vorschau(daten)
        daten['gesendet_stand'] = {f['name']: f['gesendet_stand'] for f in v['fassungen']}
        ids = self.p.testen(daten)['auftraege']
        return [a for a in self.au.liste if a['id'] in ids]

    def test_abo_unmittelbar_vor_aufruf_erneut_pruefen(self):
        a = self.einreihen()[0]
        a['auswerter'] = dict(a['auswerter'], anbieter='codex')
        codex = self.au.anbieter['codex']
        auth = self.basis / '.codex/auth.json'
        auth.parent.mkdir()
        auth.write_text('{"auth_mode":"chatgpt"}', encoding='utf-8')
        def kontext(p):
            auth.write_text('{"auth_mode":"api"}', encoding='utf-8')
            return 131072, 'Fake', 'modell'
        with patch.object(auswertung, 'HOME', str(self.basis)), \
                patch.object(codex, 'exe', return_value='fake.exe'), \
                patch.object(codex, 'kontext_geladen', side_effect=kontext), \
                patch.object(codex, 'ausfuehren') as senden:
            self.assertTrue(self.au.prompt_verfuegbar(a['auswerter'])[0])
            self.arbeiten()
        senden.assert_not_called()
        self.assertEqual(a['zustand'], 'fehler')
        self.assertIn('Abo-Anmeldung nicht bestätigt', a['meldung'])
        self.assertNotIn('auth_mode', '\n'.join(self.logs))

    def arbeiten(self):
        """Echte Schleife in genau einem Faden bis zum Leerlauf; deterministisch beenden."""
        fehler = []
        def ende(*args):
            raise Ende()
        def laufen():
            try:
                self.au._schleife()
            except Ende:
                pass
            except BaseException as ex:
                fehler.append(ex)
        with patch.object(self.au._wecker, 'wait', side_effect=ende):
            t = threading.Thread(target=laufen)
            t.start()
            t.join(5)
            self.assertFalse(t.is_alive(), 'Arbeitsfaden hängt')
        self.assertEqual(fehler, [])

    def beleg(self, a):
        return prompts.beleg_lesen(self.au._belegpfad(a))

    def transkript(self, text='Text aus dem Transkript'):
        datei = self.basis / 'watch' / 'Film' / 'Lauf' / 'transcript-timestamps.txt'
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(text, encoding='utf-8')
        self.daten['eingaben']['felder']['A'] = {'art': 'transkript', 'datei': str(datei)}
        return datei

    def test_a_prompt_zweig_html_gesendet_und_oeffnen(self):
        a, = self.einreihen()
        self.assertEqual(self.beleg(a)['zustand'], 'wartet')
        with patch('werkstatt.auswertung.pruefung.nachpruefen', side_effect=AssertionError('Keine Nachprüfung')):
            self.arbeiten()
        b = self.beleg(a)
        self.assertEqual((a['art'], a['zustand'], b['zustand'], b['html'], b['tokens']),
                         ('prompt', 'fertig', 'fertig', 'ja', 19))
        self.assertIn('Antwort 1', Path(a['datei']).with_suffix('.html').read_text(encoding='utf-8'))
        self.assertEqual(self.p.datei_inhalt(self.e['id'], 'gesendet', b['datei'])['text'], 'Baue HTML.')
        with patch('werkstatt.prompts.os.startfile') as starten:
            self.p.oeffnen(self.e['id'], 'html', Path(a['datei']).with_suffix('.html').name)
            starten.assert_called_once_with(str(Path(a['datei']).with_suffix('.html')))

    def test_b_mehrfachlauf_identische_eingaben(self):
        self.transkript()
        prompts.Eintrag(self.basis / 'Prompts' / self.e['id'] / 'prompt.md').fassung_neu('Zwei', 'Anders [A]')
        self.daten['fassungen'].append('Zwei')
        a, b = self.einreihen()
        aa, bb = self.beleg(a), self.beleg(b)
        self.assertEqual(aa['eingaben'], bb['eingaben'])
        self.assertNotEqual(aa['fassung_stand'], bb['fassung_stand'])
        self.assertNotEqual(aa['gesendet_stand'], bb['gesendet_stand'])
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 2)

    def test_d_kontext_sinkt_vor_senden(self):
        a, = self.einreihen()
        self.fake.kontextwert = 64
        self.arbeiten()
        self.assertEqual((a['zustand'], a['code'], self.fake.aufrufe), ('fehler', 'kontext', 0))
        self.assertIn('64 Token', self.beleg(a)['meldung'])

    def test_vorschau_schaetzung_rahmen_leer_und_zu_lang(self):
        v = self.p.vorschau(self.daten)
        p = v['fassungen'][0]['auswerter'][0]
        self.assertEqual(p['geschaetzt'], (len('Baue HTML.') + 600) / 3)
        self.assertEqual(p['reserve'], 32768)
        self.assertEqual(v['leer'], 0)
        self.daten['eingaben']['felder']['A']['wert'] = ''
        self.daten['rahmen'] = True
        v = self.p.vorschau(self.daten)
        self.assertEqual(v['leer'], 1)
        self.assertEqual(v['fassungen'][0]['auftrag'], 'Rahmentext\n\nBaue [A].')
        self.transkript('x' * 310000)
        with self.assertRaisesRegex(prompts.PromptFehler, '131.072 Token Kontext'):
            self.p.vorschau(self.daten)

    def test_h_vorschau_veraltet_konflikt_ohne_beleg(self):
        v = self.p.vorschau(self.daten)
        self.daten['gesendet_stand'] = {f['name']: f['gesendet_stand'] for f in v['fassungen']}
        f = self.e['fassungen'][0]
        prompts.Eintrag(self.basis / 'Prompts' / self.e['id'] / 'prompt.md').fassung_speichern(
            f['name'], 'Geändert [A]', f['stand'])
        with self.assertRaises(prompts.Konflikt):
            self.p.testen(self.daten)
        self.assertEqual(self.au.liste, [])
        self.assertFalse((self.basis / 'Prompts' / self.e['id'] / 'tests').exists())

    def test_datei_utf8_ersatz_grenze_und_pfade(self):
        datei = self.basis / 'feld.txt'
        datei.write_bytes(b'a\xffb')
        feld = self.p.datei_lesen(str(datei))
        self.assertEqual((feld['wert'], feld['zeichen'], feld['sha']), ('a\ufffdb', 3, prompts.sha('a\ufffdb')))
        self.p.cfg['feld_max_zeichen'] = 2
        with self.assertRaises(ValueError):
            self.p.datei_lesen(str(datei))
        with self.assertRaises(ValueError):
            self.p.datei_lesen(str(datei) + ':strom')

    def test_datei_lesen_sperrt_zugangsdaten(self):
        geheim = self.basis / '00_Secrets' / 'OpenRouter'
        geheim.mkdir(parents=True)
        (geheim / 'api-key.txt').write_text('sk-geheim', encoding='utf-8')
        (self.basis / 'projekt.env').write_text('TOKEN=x', encoding='utf-8')
        self.p.cfg['gesperrt'] = [str(self.basis / '00_Secrets')]
        for pfad in (geheim / 'api-key.txt', self.basis / 'projekt.env'):
            with self.assertRaisesRegex(ValueError, 'Zugangsdaten'):
                self.p.datei_lesen(str(pfad))
        self.assertGreater(self.p.datei_lesen(str(self.sammlung))['zeichen'], 0)

    def test_transkriptwahl_pruefsumme_zeichen_ohne_text(self):
        datei = self.transkript('Inhalt')
        with patch('werkstatt.auswertung.transkripte_auflisten', return_value=[
                {'titel': 'Film', 'transkript': str(datei.parent)}]):
            t, = self.p.transkripte()
        self.assertEqual((t['datei'], t['sha'], t['zeichen']), (str(datei), prompts.sha('Inhalt'), 6))
        self.assertNotIn('wert', t)

    def test_e_nochmal_meldet_geaenderte_und_fehlende_dateien(self):
        datei = self.basis / 'kontext.txt'
        datei.write_text('alt', encoding='utf-8')
        self.daten['eingaben']['felder']['A'] = {'art': 'datei', 'pfad': str(datei)}
        a, = self.einreihen()
        datei.write_text('neu', encoding='utf-8')
        b = self.p.datei_inhalt(self.e['id'], 'beleg', Path(a['datei']).name)
        self.assertEqual(b['eingaben']['felder']['A']['wert'], 'alt')
        self.assertIn('geändert', b['hinweise']['A'])
        datei.unlink()
        self.assertIn('fehlt', self.p.datei_inhalt(self.e['id'], 'beleg', Path(a['datei']).name)['hinweise']['A'])

    def test_f_alt_eintraege_normalisiert_und_stand(self):
        self.au.liste = [{'id': str(i), 'zustand': 'fertig'} for i in range(8)]
        self.au._speichern()
        au = self.neu()
        self.assertEqual([a['art'] for a in au.stand()['auswertungen']], ['zusammenfassung'] * 8)

    def test_h_beleg_geaendert_kein_aufruf(self):
        a, = self.einreihen()
        datei = Path(a['datei'])
        datei.write_text(datei.read_text(encoding='utf-8').replace('Baue [A].', 'Andere [A].'), encoding='utf-8')
        self.arbeiten()
        self.assertEqual((a['zustand'], a['code'], self.fake.aufrufe), ('fehler', 'beleg_geaendert', 0))
        self.assertEqual(self.beleg(a)['zustand'], 'fehler')

    def test_i_zwei_belege_in_derselben_sekunde(self):
        with patch('werkstatt.prompts.datetime.datetime') as datum:
            datum.now.return_value.strftime.side_effect = lambda muster: '2026-11-06 14-32-07'
            a, = self.einreihen()
            b, = self.einreihen()
        self.assertNotEqual(a['datei'], b['datei'])
        self.assertIn(' (2).md', b['datei'])

    def test_j_neustart_laufend_und_verwaist_wiederholen(self):
        a, = self.einreihen()
        self.au._naechste()
        b, = self.einreihen()
        self.au.liste.remove(b)
        self.au._speichern()
        self.au = self.neu()
        self.p = self.au.prompts
        a = self.au.liste[0]
        self.assertEqual((a['zustand'], self.beleg(a)['zustand']), ('abgebrochen', 'abgebrochen'))
        bb = self.beleg(b)
        self.assertEqual((bb['zustand'], bb['meldung']), ('abgebrochen', 'Einreihung unvollständig'))
        self.au.aktion(a['id'], 'wiederholen')
        self.p.aktion({'aktion': 'wiederholen_beleg', 'id': self.e['id'], 'datei': bb['datei']})
        self.arbeiten()
        self.assertEqual([a['zustand'] for a in self.au.liste], ['fertig', 'fertig'])
        self.assertEqual(len(list((self.basis / 'Prompts' / self.e['id'] / 'tests').glob('*.md'))), 2)

    def test_j_transkript_geaendert_oder_fehlend(self):
        datei = self.transkript()
        a, = self.einreihen()
        datei.write_text('geändert', encoding='utf-8')
        self.arbeiten()
        self.assertEqual((a['code'], self.beleg(a)['zustand']), ('transkript_geaendert', 'fehler'))
        self.au.aktion(a['id'], 'wiederholen')
        datei.unlink()
        self.arbeiten()
        self.assertEqual((a['code'], self.beleg(a)['zustand'], self.fake.aufrufe),
                         ('transkript_geaendert', 'fehler', 0))

    def test_k_absturz_nach_antwort_kein_zweiter_modellaufruf(self):
        a, = self.einreihen()
        with patch('werkstatt.prompts.html_schreiben', side_effect=RuntimeError('Nacharbeit gescheitert')):
            self.arbeiten()
        self.assertEqual((a['zustand'], self.beleg(a)['zustand'], self.fake.aufrufe), ('fehler', 'fehler', 1))
        self.assertIn('Antwort 1', self.beleg(a)['antwort'])
        self.au.aktion(a['id'], 'wiederholen')
        self.arbeiten()
        self.assertEqual((a['zustand'], self.beleg(a)['html'], self.fake.aufrufe), ('fertig', 'ja', 1))

    def test_fehlerbehandlung_wirft_zweiter_auftrag_im_selben_faden(self):
        a, = self.einreihen()
        b, = self.einreihen()
        faeden = []
        def waehrend():
            faeden.append(threading.get_ident())
            if self.fake.aufrufe == 1:
                raise RuntimeError('Erster Auftrag gescheitert')
        self.fake.waehrend = waehrend
        behandeln = self.au._fehlgeschlagen
        def fehlerbehandlung(*args):
            if len(faeden) == 1:
                raise RuntimeError('Fehlerbehandlung gescheitert')
            return behandeln(*args)
        with patch.object(self.au, '_fehlgeschlagen', side_effect=fehlerbehandlung) as behandeln_mock:
            self.arbeiten()
        behandeln_mock.assert_called_once()
        self.assertEqual((a['zustand'], self.beleg(a)['zustand'], b['zustand']), ('fehler', 'fehler', 'fertig'))
        self.assertEqual((len(faeden), len(set(faeden))), (2, 1))
        self.assertIn('beendet', a)
        gespeichert = json.loads(Path(self.au.datei).read_text(encoding='utf-8'))['auswertungen']
        self.assertEqual([x['zustand'] for x in gespeichert], ['fehler', 'fertig'])

    def test_m_log_ohne_ausnahmetext_alle_arten(self):
        from werkstatt import server
        w = server.Werkstatt.__new__(server.Werkstatt)
        w._logdatei = str(self.basis / 'werkstatt.log')
        self.au.log = lambda text: (self.logs.append(text), w.log(text))
        a, = self.einreihen()
        self.fake.fehler = True
        self.arbeiten()
        self.assertIn('MARKIERUNG-GEHEIM', a['meldung'])
        self.assertIn('MARKIERUNG-GEHEIM', self.beleg(a)['meldung'])
        self.assertNotIn('MARKIERUNG', '\n'.join(self.logs))
        self.assertNotIn('MARKIERUNG', Path(w._logdatei).read_text(encoding='utf-8'))
        self.assertIn('MARKIERUNG-GEHEIM', Path(self.au.datei).read_text(encoding='utf-8'))
        self.assertIn('RuntimeError Code anbieter', '\n'.join(self.logs))
        a['art'] = 'zusammenfassung'
        self.au._fehlgeschlagen(a, RuntimeError('MARKIERUNG-GEHEIM'))
        self.assertNotIn('MARKIERUNG', '\n'.join(self.logs))

    def test_n_geloeschter_beleg_zweiter_laeuft_im_selben_faden(self):
        a, = self.einreihen()
        b, = self.einreihen()
        Path(a['datei']).unlink()
        self.arbeiten()
        self.assertEqual((a['zustand'], a['code'], b['zustand'], self.fake.aufrufe),
                         ('fehler', 'beleg_fehlt', 'fertig', 1))

    def test_n_exklusiv_gesperrter_beleg_zweiter_laeuft(self):
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        a, = self.einreihen()
        b, = self.einreihen()
        handle = kernel.CreateFileW(a['datei'], 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            self.arbeiten()
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual((a['zustand'], a['code'], b['zustand'], self.fake.aufrufe),
                         ('fehler', 'beleg_gesperrt', 'fertig', 1))

    def test_n_ohne_leere_oder_offene_antwort_ruft_modell(self):
        for zusatz in ('', '## Antwort\n~~~text\n\n~~~\n', '## Antwort\n~~~text\noffen'):
            with self.subTest(zusatz=zusatz):
                a, = self.einreihen()
                with open(a['datei'], 'a', encoding='utf-8') as f:
                    f.write(zusatz)
                self.au.aktion(a['id'], 'abbrechen')
                self.au.aktion(a['id'], 'wiederholen')
                vorher = self.fake.aufrufe
                self.arbeiten()
                self.assertEqual((a['zustand'], self.fake.aufrufe), ('fertig', vorher + 1))

    def test_beleg_waehrend_lauf_geaendert_antwort_trotzdem(self):
        a, = self.einreihen()
        def aendern():
            pfad = Path(a['datei'])
            pfad.write_text(pfad.read_text(encoding='utf-8').replace('Baue [A].', 'Handänderung'), encoding='utf-8')
        self.fake.waehrend = aendern
        self.arbeiten()
        self.assertEqual(a['zustand'], 'fertig')
        self.assertEqual(self.beleg(a)['hinweis'], 'Beleg während des Laufs von Hand geändert')
        self.assertIn('Antwort 1', self.beleg(a)['antwort'])

    def test_start_ohne_beleg_entfernen_unveraendert(self):
        a, = self.einreihen()
        vorher = Path(a['datei']).read_bytes()
        self.au.aktion(a['id'], 'entfernen')
        self.assertEqual(Path(a['datei']).read_bytes(), vorher)
        b, = self.einreihen()
        Path(b['datei']).unlink()
        self.au = self.neu()
        self.assertEqual((self.au.liste[0]['zustand'], self.au.liste[0]['code']), ('fehler', 'beleg_fehlt'))

    def test_sammlung_testen_schreibt_nur_schatten(self):
        vorher = self.sammlung.read_bytes()
        self.daten.update(id='sammlung:Wissen#1', fassungen=['Sammlung'])
        a, = self.einreihen()
        self.assertIn('_Sammlung', a['datei'])
        self.arbeiten()
        self.assertEqual(a['zustand'], 'fertig')
        self.assertEqual(self.sammlung.read_bytes(), vorher)

    def test_sammlung_nummer_verschoben_nach_einreihen(self):
        self.daten.update(id='sammlung:Wissen#1', fassungen=['Sammlung'])
        a, = self.einreihen()
        roh = self.sammlung.read_text(encoding='utf-8')
        self.sammlung.write_text(roh.replace('### Wissen\n', '### Wissen\n~~~text\nDavor\n~~~\n'), encoding='utf-8')
        with self.assertRaises(prompts.Konflikt):
            self.p.aktion({'aktion': 'wiederholen_beleg', 'id': 'sammlung:Wissen#2',
                           'datei': Path(a['datei']).name})
        self.arbeiten()
        self.assertEqual(a['zustand'], 'fertig')
        self.assertEqual(self.fake.texte, ['Sammlung HTML'])


class SchaerfenLaeufe(unittest.TestCase):
    # Dieselbe isolierte Warteschlange und derselbe zählende Fake wie bei Scheibe 2.
    setUp = PromptLaeufe.setUp
    neu = PromptLaeufe.neu
    arbeiten = PromptLaeufe.arbeiten

    def vorbereiten(self, aktion='Schärfen', eid=None, fassung='Fassung 1'):
        skill = self.basis / 'SKILL.md'
        skill.write_text('---\nname: Test\n---\nRegeln zum Schärfen\n', encoding='utf-8')
        self.cfg['prompts']['skill'] = str(skill)
        self.sd = {'id': eid or self.e['id'], 'fassung': fassung, 'schaerfen_aktion': aktion,
                   'schreibmodell': 'p', 'zielmodell': 'p', 'hinweise': ''}
        self.antwort = None
        def senden(profil, text, lauf):
            self.fake.aufrufe += 1
            self.fake.texte.append(text)
            if self.fake.waehrend:
                self.fake.waehrend()
            return {'text': self.antwort or f'~~~text\nBesser {self.fake.aufrufe} [A] [Projektkontext]\n~~~\n- Klarer formuliert.',
                    'tokens': 22, 'kosten_usd': 0.1}
        self.fake.ausfuehren = senden

    def schaerfen(self):
        v = self.p.schaerfen_vorschau(self.sd)
        self.p.schaerfen(dict(self.sd, gesendet_stand=v['gesendet_stand']))
        return self.au.liste[-1]

    def beleg(self, a):
        return prompts.schaerfen_lesen(self.au._belegpfad(a))

    def test_a_uebernahme_datei_index_und_anzeigedaten(self):
        self.vorbereiten()
        a = self.schaerfen()
        self.assertEqual((a['art'], a['prompt']['art_ordner'], self.beleg(a)['zustand']), ('schaerfen', 'schaerfen', 'wartet'))
        self.assertIn(' – Schärfen für Fake – Fake', a['datei'])
        with patch('werkstatt.auswertung.pruefung.nachpruefen', side_effect=AssertionError('Keine Nachprüfung')):
            self.arbeiten()
        b = self.beleg(a)
        self.assertEqual((a['zustand'], b['zustand'], b['tokens']), ('fertig', 'fertig', 22))
        self.assertIn('übernommen (Schärfen ', b['ergebnis'])
        d = self.p.lesen(self.e['id'])
        self.assertEqual(len(d['fassungen']), 2)
        self.assertEqual(len(d['schaerfen']), 1)
        self.assertEqual(d['tests'], [])
        self.assertNotIn('urteil', b)
        ansicht = self.p.datei_inhalt(d['id'], 'schaerfen', b['datei'])
        self.assertEqual((ansicht['original'], ansicht['neue_fassung']), ('Baue [A].', 'Besser 1 [A] [Projektkontext]'))
        self.assertIn('- Klarer formuliert.', ansicht['stichpunkte'])
        self.assertNotIn('~~~', ansicht['stichpunkte'])
        self.assertEqual(ansicht['neue_platzhalter'], ['Projektkontext'])
        self.assertEqual(b['skill_stand'], prompts.stand(b['eingaben']['skill']['wert']))

    def test_b_sammlung_bytegleich_nur_vorschlag(self):
        self.vorbereiten(eid='sammlung:Wissen#1', fassung='Sammlung')
        vorher = self.sammlung.read_bytes()
        a = self.schaerfen()
        self.arbeiten()
        self.assertEqual(self.sammlung.read_bytes(), vorher)
        self.assertEqual(self.beleg(a)['ergebnis'], 'Vorschlag, nicht übernommen')
        self.assertIn('_Sammlung', a['datei'])
        self.assertEqual(len(self.p.lesen(self.sd['id'])['schaerfen']), 1)
        self.assertFalse((Path(a['datei']).parent.parent / 'prompt.md').exists())

    def test_c_erst_klaeren_fragen_auch_bei_geliefertem_kasten(self):
        self.vorbereiten('Erst klären')
        for antwort in ('1. Welches Ziel?\n2. Welches Format?', '~~~text\n[A]\n~~~\n1. Welches Ziel?'):
            self.antwort = antwort
            a = self.schaerfen()
            self.arbeiten()
            self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 1)
            b = self.p.datei_inhalt(self.e['id'], 'schaerfen', Path(a['datei']).name)
            self.assertEqual((b['fragen'], b['neue_fassung']), (antwort, ''))
            self.assertIn('nicht übernommen', b['ergebnis'])

    def test_d_ungueltige_antworten_und_namen_dopplungen(self):
        self.vorbereiten()
        for antwort, grund in [('Text', 'kein Kasten'),
                ('```\n[A]\n```\n~~~text\n[A]\n~~~', 'mehrere Kästen'),
                ('```text\n[A]\n~~~\n```', '~~~'), ('~~~text\nOhne Feld\n~~~', 'Platzhalter verloren')]:
            self.antwort = antwort
            a = self.schaerfen()
            self.arbeiten()
            self.assertTrue(self.beleg(a)['ergebnis'].startswith('ungültig ('), self.beleg(a))
            self.assertIn(grund, self.beleg(a)['ergebnis'])
        self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 1)
        self.au.profile[0]['name'] = 'Fake\rName'
        self.antwort = '```text\nNeu [A]\n```'
        a = self.schaerfen()
        self.arbeiten()
        self.assertIn('Steuerzeichen', self.beleg(a)['ergebnis'])
        self.au.profile[0]['name'] = 'Fake'
        self.antwort = None
        a = self.schaerfen()
        self.arbeiten()
        b = self.schaerfen()
        self.arbeiten()
        self.assertIn(' (2))', self.beleg(b)['ergebnis'])
        self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 3)
        # Derselbe Kasten wird auch in einem weiteren Lauf über seinen Stand erkannt.
        self.antwort = self.beleg(a)['antwort']
        c = self.schaerfen()
        self.arbeiten()
        self.assertEqual(self.beleg(c)['ergebnis'], self.beleg(a)['ergebnis'])
        self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 3)

    def test_e_absturz_nach_anhaengen_wiederholen_ohne_aufruf(self):
        self.vorbereiten()
        a = self.schaerfen()
        setzen = prompts._kopf_setzen
        def absturz(datei, werte, *args, **kwargs):
            if 'ergebnis' in werte:
                raise RuntimeError('Absturz vor Ergebnis')
            return setzen(datei, werte, *args, **kwargs)
        with patch('werkstatt.prompts._kopf_setzen', side_effect=absturz):
            self.arbeiten()
        self.assertEqual((a['zustand'], self.fake.aufrufe, self.beleg(a)['ergebnis']), ('fehler', 1, 'offen'))
        self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 2)
        self.au.aktion(a['id'], 'wiederholen')
        self.arbeiten()
        self.assertEqual((a['zustand'], self.fake.aufrufe), ('fertig', 1))
        self.assertEqual((self.beleg(a)['tokens'], self.beleg(a)['kosten_usd']), (22, 0.1))
        self.assertEqual(len(self.p.lesen(self.e['id'])['fassungen']), 2)
        self.assertTrue(self.beleg(a)['ergebnis'].startswith('übernommen'))

    def test_f_skill_fehlt_vor_einreihen_und_vorschaukonflikt(self):
        self.vorbereiten()
        v = self.p.schaerfen_vorschau(self.sd)
        skill = Path(self.cfg['prompts']['skill'])
        skill.write_text('Andere Regeln', encoding='utf-8')
        with self.assertRaises(prompts.Konflikt):
            self.p.schaerfen(dict(self.sd, gesendet_stand=v['gesendet_stand']))
        skill.unlink()
        with self.assertRaises(prompts.PromptFehler) as ex:
            self.p.schaerfen(dict(self.sd, gesendet_stand=v['gesendet_stand']))
        self.assertEqual(ex.exception.code, 'skill_fehlt')
        self.assertEqual(self.au.liste, [])
        self.assertFalse((self.basis / 'Prompts' / self.e['id'] / 'schaerfen').exists())

    def test_g_claude_nicht_angemeldet_grund_und_kein_lauf(self):
        self.vorbereiten()
        self.au.profile[0]['anbieter'] = 'claude'
        claude = self.au.anbieter['claude']
        with patch.object(claude, 'exe', return_value='claude.exe'), patch.object(claude, 'anmeldung', return_value=None), \
                patch.object(claude, 'kontext', return_value=200000):
            v = self.p.schaerfen_vorschau(self.sd)
            self.assertFalse(v['schreibmodell']['verfuegbar'])
            self.assertIn('auth login', v['schreibmodell']['grund'])
            with self.assertRaisesRegex(prompts.PromptFehler, 'auth login'):
                self.p.schaerfen(dict(self.sd, gesendet_stand=v['gesendet_stand']))
        self.assertEqual(self.au.liste, [])

    def test_h_i_material_snapshot_geaendert_geloescht_und_skill_snapshot(self):
        self.vorbereiten()
        for loeschen in (False, True):
            datei = prompts.beleg_anlegen(str(self.basis / 'Prompts' / self.e['id'] / 'tests'),
                {'fassung': 'Fassung 1', 'auswerter': 'Fake', 'erstellt': '2026-11-06'}, 'Baue [A].', {'felder': {}})
            material = 'Material\n~~~\n  ~~~\n' + 'x' * 31000
            prompts.antwort_schreiben(datei, material)
            self.sd['material'] = Path(datei).name
            a = self.schaerfen()
            b = self.beleg(a)
            self.assertEqual(b['eingaben']['material']['wert'], material[:30000])
            if loeschen:
                Path(datei).unlink()
            else:
                prompts.antwort_schreiben(datei, 'Geändertes Material')
            Path(self.cfg['prompts']['skill']).write_text('Späterer Skill', encoding='utf-8')
            self.arbeiten()
            self.assertEqual(a['zustand'], 'fertig')
            self.assertIn(material[:30000], self.fake.texte[-1])
            self.assertNotIn('Geändertes Material', self.fake.texte[-1])
            self.assertIn('Kasten mit 4 Tilden', self.fake.texte[-1])

    def test_i_hand_geaendert_fehler_kein_modellaufruf(self):
        self.vorbereiten()
        for alt, neu in [('Baue [A].', 'Anders [A].'), ('Regeln zum Schärfen', 'Andere Regeln')]:
            a = self.schaerfen()
            pfad = Path(a['datei'])
            pfad.write_text(pfad.read_text(encoding='utf-8').replace(alt, neu), encoding='utf-8')
            self.arbeiten()
            self.assertEqual((a['zustand'], a['code'], self.fake.aufrufe), ('fehler', 'beleg_geaendert', 0))

    def test_neustart_verwaist_wiederholen_und_entfernen(self):
        self.vorbereiten()
        a = self.schaerfen()
        self.au._naechste()
        b = self.schaerfen()
        self.au.liste.remove(b)
        self.au._speichern()
        self.au = self.neu()
        self.p = self.au.prompts
        a = self.au.liste[0]
        self.assertEqual((a['zustand'], self.beleg(a)['zustand']), ('abgebrochen', 'abgebrochen'))
        self.assertEqual(self.beleg(b)['meldung'], 'Einreihung unvollständig')
        self.au.aktion(a['id'], 'wiederholen')
        self.p.aktion({'aktion': 'wiederholen_beleg', 'id': self.e['id'], 'datei': Path(b['datei']).name,
                       'art_ordner': 'schaerfen'})
        with self.assertRaises(prompts.Konflikt):
            self.p.aktion({'aktion': 'wiederholen_beleg', 'id': self.e['id'], 'datei': Path(b['datei']).name,
                           'art_ordner': 'schaerfen'})
        self.fake = self.au.anbieter['fake']
        self.vorbereiten()
        self.arbeiten()
        self.assertEqual([x['zustand'] for x in self.au.liste], ['fertig', 'fertig'])
        self.assertTrue(all(self.beleg(x)['ergebnis'].startswith('übernommen') for x in self.au.liste))
        self.assertEqual(self.fake.aufrufe, 2)
        vorher = Path(a['datei']).read_bytes()
        self.au.aktion(a['id'], 'entfernen')
        self.assertEqual(Path(a['datei']).read_bytes(), vorher)

    def test_kontext_und_anbieter_vor_senden_erneut_geprueft(self):
        self.vorbereiten()
        a = self.schaerfen()
        self.fake.kontextwert = 64
        self.arbeiten()
        self.assertEqual((a['code'], self.beleg(a)['zustand'], self.fake.aufrufe), ('kontext', 'fehler', 0))
        self.fake.kontextwert = 131072
        self.au.aktion(a['id'], 'wiederholen')
        with patch.object(self.fake, 'verfuegbar', return_value=(False, 'Nicht verfügbar')):
            self.arbeiten()
        self.assertEqual((a['code'], self.fake.aufrufe), ('anbieter', 0))


class GeladenerKontext(unittest.TestCase):
    def test_health_gleicher_name_zwei_varianten(self):
        lokal = auswertung.Lokal({})
        e = {'id': 'strata', 'art': 'strata', 'name': 'Strata', 'port': 8095,
             'varianten': [{'modell': 'gleich', 'kontext': 131072},
                           {'modell': 'gleich', 'kontext': 262144, 'standard': True}]}
        import io
        with patch.object(lokal, '_eintraege', return_value=({'strata': e}, {})), \
                patch.object(auswertung._OHNE_PROXY, 'open', return_value=io.BytesIO(
                    b'{"loaded": true, "model": "gleich", "max_context": 131072}')):
            self.assertEqual(lokal.kontext_geladen({'modell': 'strata'}), (131072, '/health', 'gleich'))

    def test_health_nicht_geladen_ollama_und_ninfer(self):
        import io
        lokal = auswertung.Lokal({})
        eintraege = {
            'poly': {'id': 'poly', 'art': 'polystrata', 'name': 'Poly', 'port': 8097, 'modell': 'gleich'},
            'ollama': {'id': 'ollama', 'art': 'ollama', 'name': 'Ollama', 'tag': 'tag'},
            'ninfer': {'id': 'ninfer', 'art': 'ninfer', 'name': 'NInfer', 'modell_id': 'modell', 'untertitel': '128K'}}
        with patch.object(lokal, '_eintraege', return_value=(eintraege, {})), \
                patch.object(lokal, '_ollama_kontexte', return_value={'tag': 65536}), \
                patch.object(auswertung._OHNE_PROXY, 'open', return_value=io.BytesIO(b'{"loaded": false}')):
            with self.assertRaisesRegex(RuntimeError, 'nicht geladen'):
                lokal.kontext_geladen({'modell': 'poly'})
            self.assertEqual(lokal.kontext_geladen({'modell': 'ollama'}), (65536, '/api/ps', 'tag'))
            self.assertEqual(lokal.kontext_geladen({'modell': 'ninfer'}), (131072, 'Katalog der Zentrale', 'modell'))

    def test_health_wert_steht_im_beleg_beim_einreihen_und_senden(self):
        import io
        basis = PromptLaeufe('test_d_kontext_sinkt_vor_senden')
        basis.setUp()
        try:
            lokal = auswertung.Lokal({})
            e = {'id': 'strata', 'art': 'strata', 'name': 'Strata', 'port': 8095,
                 'varianten': [{'modell': 'gleich', 'kontext': 131072},
                               {'modell': 'gleich', 'kontext': 262144, 'standard': True}]}
            basis.au.profile[0].update(anbieter='lokal', modell='strata')
            basis.au.anbieter['lokal'] = lokal
            with patch.object(lokal, '_eintraege', return_value=({'strata': e}, {})), \
                    patch.object(lokal, 'verfuegbar', return_value=(True, '')), \
                    patch.object(lokal, 'ausfuehren', side_effect=basis.fake.ausfuehren), \
                    patch.object(auswertung._OHNE_PROXY, 'open', side_effect=lambda *a, **kw: io.BytesIO(
                        b'{"loaded": true, "model": "gleich", "max_context": 131072}')):
                a, = basis.einreihen()
                self.assertEqual((basis.beleg(a)['kontext'], basis.beleg(a)['kontext_quelle']), (131072, '/health'))
                basis.arbeiten()
                self.assertEqual((a['zustand'], basis.beleg(a)['kontext_quelle']), ('fertig', '/health'))
        finally:
            basis.doCleanups()


class ComposerLaeufe(unittest.TestCase):
    neu = PromptLaeufe.neu
    arbeiten = PromptLaeufe.arbeiten
    beleg = SchaerfenLaeufe.beleg

    def setUp(self):
        import uuid
        PromptLaeufe.setUp(self)
        SchaerfenLaeufe.vorbereiten(self)
        self.regeln = self.basis / 'profile.json'
        self.regeln.write_bytes((Path(__file__).parent / 'werkstatt-profile.json').read_bytes())
        self.cfg['prompts']['profile'] = str(self.regeln)
        realismus = self.basis / 'Realismus.md'
        realismus.write_text('Fachregeln für fotorealistische Menschen', encoding='utf-8')
        self.cfg['prompts']['skill_realismus'] = str(realismus)
        self.zc = self.basis / 'zentrale.json'
        self.zc.write_text(json.dumps({'eintraege': [
            {'id': 'qwen27-unsloth', 'name': 'Qwen', 'art': 'llamacpp', 'modell_id': 'qwen-q4',
             'port': 8106, 'untertitel': '128K'},
            {'id': 'qwen27-iq3s', 'name': 'Qwen IQ3', 'art': 'llamacpp', 'modell_id': 'qwen-iq3',
             'port': 8103, 'untertitel': '128K'},
            {'id': 'flash-next-strata', 'name': 'Flash', 'art': 'strata', 'port': 8095,
             'varianten': [{'id': '128k', 'name': '128K', 'kontext': 131072, 'modell': 'flash', 'standard': True},
                           {'id': '256k', 'name': '256K', 'kontext': 262144, 'modell': 'flash'}]}]}), encoding='utf-8')
        self.cfg['zentrale_config'] = str(self.zc)
        self.au.profile.append({'id': 'c', 'anbieter': 'claude', 'modell': 'modell', 'name': 'Claude · Test'})
        self.au._speichern()
        self.cloud_fake()
        self.enterContext(patch.object(self.au.anbieter['lokal'], 'verfuegbar', return_value=(False, 'nicht geladen')))
        self.enterContext(patch.object(self.au.anbieter['lokal'], '_ollama_kontexte', return_value={}))
        self.enterContext(patch.object(auswertung._OHNE_PROXY, 'open', side_effect=AssertionError('Kein Modellnetz')))
        self.enterContext(patch.object(auswertung._NETZ, 'open', side_effect=AssertionError('Keine Cloud')))
        self.cd = {'anfrage_id': str(uuid.uuid4()), 'text': 'Baue [A].', 'titel': '', 'ablage': 'ordner',
                   'basis': None, 'prompt_typ': 'code', 'modus': 'prompt', 'schreibmodell': 'p',
                   'ziele': [{'zielprofil': 'qwen27', 'eintrag': 'qwen27-unsloth', 'testprofil': None},
                             {'zielprofil': 'flash_next', 'eintrag': 'flash-next-strata', 'testprofil': None},
                             {'zielprofil': 'claude', 'testprofil': 'c'}],
                   'hinweise': '', 'materialien': [], 'kontexte': []}

    def cloud_fake(self):
        class Abo(Fake):
            schluessel, cloud = 'claude', 'Anthropic'
            def zugang(self, frisch=False):
                return 'abo'
        self.au.anbieter['claude'] = Abo()

    def senden(self):
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        return self.p.composer_senden(self.cd)

    def neustart(self):
        self.au = self.neu()
        self.p = self.au.prompts
        self.fake = self.au.anbieter['fake']
        self.cloud_fake()
        self.enterContext(patch.object(self.au.anbieter['lokal'], 'verfuegbar', return_value=(False, 'nicht geladen')))
        self.enterContext(patch.object(self.au.anbieter['lokal'], '_ollama_kontexte', return_value={}))
        SchaerfenLaeufe.vorbereiten(self)

    def test_drei_ziele_ein_original_drei_belege_drei_aufrufe(self):
        vorher = len([e for e in self.p.alle()['eintraege'] if e['herkunft'] == 'ordner'])
        status = self.senden()
        self.assertTrue(status['vollstaendig'])
        self.assertEqual(len(status['auftraege']), 3)
        d = self.p.lesen(status['id'])
        self.assertEqual(len([e for e in self.p.alle()['eintraege'] if e['herkunft'] == 'ordner']), vorher + 1)
        self.assertEqual(d['titel'], 'Baue [A].')
        self.assertEqual(d['composer_auftrag'], self.cd['anfrage_id'])
        self.assertEqual(d['prompt_typ'], 'code')
        self.assertEqual(len(d['schaerfen']), 3)
        self.assertEqual(len(d['auftragsgruppen']), 1)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)
        self.assertEqual([a['zustand'] for a in self.au.liste], ['fertig']*3)
        d = self.p.lesen(d['id'])
        self.assertEqual(len(d['fassungen']), 4)
        self.assertEqual(d['bevorzugt'], 'Fassung 1')
        self.assertEqual(d['fassungen'][0]['text'], self.cd['text'])
        for a in self.au.liste:
            b = self.beleg(a)
            self.assertEqual(b['eingaben']['bau_version'], 2)
            self.assertEqual(b['auftragsgruppe'], self.cd['anfrage_id'])
            self.assertLessEqual(len(b['ergebnis_fassung']), 60)
            self.assertIn(' · ', b['ergebnis_fassung'])
            self.assertIn(b['zielmodell'].split(' · ')[0], b['ergebnis_fassung'])
            self.assertEqual(a['prompt']['zielschluessel'], b['zielschluessel'])
        verwaltung = self.p._sendung_pfad(self.cd['anfrage_id'])
        meta = json.loads(Path(verwaltung).read_text(encoding='utf-8'))
        self.assertEqual(set(meta), {'eingabe_stand', 'eintrag', 'beleg_eintrag', 'vollstaendig', 'ziele'})
        self.assertTrue(all(set(z) == {'zielschluessel', 'schreibmodell_id', 'beleg', 'auftrags_id', 'eingereiht'}
                            for z in meta['ziele']))
        self.assertNotIn('Regeln zum Schärfen', Path(verwaltung).read_text(encoding='utf-8'))
        self.assertNotIn('Baue [A]', '\n'.join(self.logs))

    def test_belegname_nennt_ziel_und_schreibmodell(self):
        self.senden()
        namen = []
        for a in self.au.liste:
            b = self.beleg(a)
            name = a['prompt']['beleg']
            self.assertIn(' – Schärfen für ' + prompts.dateiname(b['zielmodell'], 40) + ' – Fake', name)
            self.assertNotRegex(name, r' \(\d+\)$')
            namen.append(name)
        self.assertEqual(len(set(namen)), 3)

    def test_auftragskennung_aus_dem_beleg_nur_in_hexform(self):
        self.senden()
        a = self.au.liste[0]
        eid, datei = a['prompt']['eintrag'], a['prompt']['beleg'] + '.md'
        self.assertEqual(self.p.auftrag_aus_beleg(eid, datei, 'schaerfen')['id'], a['id'])
        echt = prompts.schaerfen_lesen
        for boese in ('..\\..\\x', 'ABCDEF12', 'a' * 17, 'abc', 7, None):
            with self.subTest(boese=boese), patch.object(
                    prompts, 'schaerfen_lesen', lambda p, b=boese: dict(echt(p), auftrags_id=b)):
                neu = self.p.auftrag_aus_beleg(eid, datei, 'schaerfen')['id']
                self.assertRegex(neu, r'^[0-9a-f]{8}$')

    def test_vorschau_legt_nichts_an_und_sendet_nicht(self):
        vorher = sorted(str(p) for p in Path(self.p.ordner).rglob('*'))
        v = self.p.composer_vorschau(self.cd)
        self.assertEqual(v['fassung']['text'], self.cd['text'])
        self.assertEqual(len(v['ziele']), 3)
        self.assertEqual(sorted(str(p) for p in Path(self.p.ordner).rglob('*')), vorher)
        self.assertEqual(self.fake.aufrufe, 0)
        for z in v['ziele']:
            self.assertEqual(z['gesendet_stand'], prompts.sha(z['auftrag']))

    def test_doppelpost_vor_und_nach_ausfuehrung(self):
        status = self.senden()
        vorher = sorted(str(p) for p in Path(self.p.ordner).rglob('*'))
        self.assertEqual(self.p.composer_senden(self.cd), status)
        self.assertEqual(sorted(str(p) for p in Path(self.p.ordner).rglob('*')), vorher)
        self.arbeiten()
        self.p.composer_senden(self.cd)
        self.assertEqual(self.fake.aufrufe, 3)
        self.assertEqual(len(self.au.liste), 3)
        self.assertEqual(len(self.p.lesen(status['id'])['fassungen']), 4)

    def test_gleiche_id_andere_eingabe_konflikt(self):
        self.senden()
        for aenderung in ({'text': 'Anderer Auftrag'}, {'hinweise': 'Neu'}, {'modus': 'vorlage'},
                          {'schreibmodell': 'c'}, {'ziele': self.cd['ziele'][:1]}):
            with self.assertRaisesRegex(prompts.Konflikt, 'anderen Eingabestand'):
                self.p.composer_senden(dict(self.cd, **aenderung))
        self.assertEqual(len(self.au.liste), 3)

    def test_hashkonflikt_vor_jeder_anlage(self):
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        self.regeln.write_text(self.regeln.read_text(encoding='utf-8').replace('Eine klare Hauptaufgabe', 'Andere Regel'), encoding='utf-8')
        with self.assertRaises(prompts.Konflikt):
            self.p.composer_senden(self.cd)
        self.assertFalse((Path(self.p.ordner) / '_Auftraege').exists())
        self.assertEqual(self.au.liste, [])

    def absturz_anlage(self, stelle):
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        objekt, name = {'reservierung': (self.p, '_sendung_schreiben'),
                        'original': (prompts.Eintrag, 'anlegen'),
                        'beleg': (prompts, 'schaerfen_anlegen'),
                        'einreihung': (self.au, 'einreihen')}[stelle]
        original = getattr(objekt, name)
        def abbrechen(*args, **kwargs):
            original(*args, **kwargs)
            raise Ende()
        with patch.object(objekt, name, new=abbrechen):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        aid = self.cd['anfrage_id']
        status = self.p.composer_status({'anfrage_id': aid})
        self.assertTrue(status['gefunden'])
        self.assertFalse(status['vollstaendig'])
        self.neustart()
        neu = self.p.composer_senden(self.cd)
        self.assertTrue(neu['vollstaendig'])
        self.assertEqual(neu['id'], status['id'])
        self.assertEqual(neu['auftraege'], status['auftraege'])
        self.assertEqual(len(self.au.liste), 3)
        self.assertEqual(len(self.p.lesen(neu['id'])['schaerfen']), 3)
        self.assertEqual(sum(e.get('composer_auftrag') == aid for e in self.p.alle()['eintraege']), 1)
        for a in self.au.liste:
            if a['zustand'] == 'abgebrochen':
                self.au.aktion(a['id'], 'wiederholen')
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)

    def test_absturz_nach_reservierung(self):
        self.absturz_anlage('reservierung')

    def test_absturz_nach_original(self):
        self.absturz_anlage('original')

    def test_absturz_nach_beleg(self):
        self.absturz_anlage('beleg')

    def test_absturz_nach_einreihung(self):
        self.absturz_anlage('einreihung')

    def test_absturz_nach_fassungsanhang_antwort_nicht_erneut_abrufen(self):
        status = self.senden()
        a = self.au._naechste()
        original = prompts.Eintrag.fassung_neu
        def abbrechen(*args, **kwargs):
            original(*args, **kwargs)
            raise Ende()
        with patch.object(prompts.Eintrag, 'fassung_neu', new=abbrechen):
            with self.assertRaises(Ende):
                self.au._ausfuehren(a)
        b = self.beleg(a)
        self.assertTrue(b['antwort'])
        self.assertTrue(b['ergebnis_fassung'])
        self.assertEqual(self.fake.aufrufe, 1)
        self.au._ausfuehren(a)
        self.assertEqual(self.fake.aufrufe, 1)
        self.assertEqual(sum(f['name'] == b['ergebnis_fassung'] for f in self.p.lesen(status['id'])['fassungen']), 1)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)

    def test_identische_antworten_verschiedener_ziele_bleiben_getrennt(self):
        self.antwort = '~~~text\nIdentisch [A]\n~~~'
        status = self.senden()
        self.arbeiten()
        d = self.p.lesen(status['id'])
        self.assertEqual(len(d['fassungen']), 4)
        self.assertEqual(len({f['name'] for f in d['fassungen']}), 4)
        self.assertEqual(len({f['stand'] for f in d['fassungen'][1:]}), 1)

    def test_ein_ziel_scheitert_andere_laufen_weiter(self):
        senden = self.fake.ausfuehren
        def einmal_fehler(p, text, lauf):
            if 'Zielregeln (flash_next)' in text:
                self.fake.aufrufe += 1
                raise RuntimeError('Gezielter Testfehler')
            return senden(p, text, lauf)
        self.fake.ausfuehren = einmal_fehler
        status = self.senden()
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)
        self.assertEqual([a['zustand'] for a in self.au.liste], ['fertig', 'fehler', 'fertig'])
        self.assertEqual(len(self.p.lesen(status['id'])['fassungen']), 3)
        self.fake.ausfuehren = senden
        a = self.au.liste[1]
        self.au.aktion(a['id'], 'wiederholen')
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 4)
        self.assertEqual(a['zustand'], 'fertig')

    def test_regeln_skill_und_material_bleiben_eingefroren(self):
        datei = prompts.beleg_anlegen(str(self.basis / 'Prompts' / self.e['id'] / 'tests'),
            {'fassung': 'Fassung 1', 'auswerter': 'Fake'}, 'Original', {'felder': {}})
        prompts.antwort_schreiben(datei, 'Altes Material')
        f = self.e['fassungen'][0]
        self.cd.update(basis={'id': self.e['id'], 'fassung': f['name'], 'stand': f['stand']}, material=Path(datei).name)
        v = self.p.composer_vorschau(self.cd)
        self.cd['gesendet_staende'] = v['gesendet_staende']
        self.p.composer_senden(self.cd)
        self.regeln.write_text('ungültig', encoding='utf-8')
        Path(self.cfg['prompts']['skill']).write_text('Ganz anderer Skill', encoding='utf-8')
        prompts.antwort_schreiben(datei, 'Neues Material')
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)
        self.assertEqual(self.fake.texte, [z['auftrag'] for z in v['ziele']])
        self.p.composer_senden(self.cd)
        self.assertEqual(self.fake.aufrufe, 3)

    def test_sammlung_schaerfen_und_vorschlag_testen_bleibt_bytegleich(self):
        eid = 'sammlung:Wissen#1'
        f = self.p.lesen(eid)['fassungen'][0]
        self.cd.update(text=f['text'], ablage='sammlung', basis={'id': eid, 'fassung': f['name'], 'stand': f['stand']})
        vorher = self.sammlung.read_bytes()
        status = self.senden()
        self.arbeiten()
        self.assertEqual(self.sammlung.read_bytes(), vorher)
        self.assertTrue(all(self.beleg(a)['ergebnis'] == 'Vorschlag, nicht übernommen' for a in self.au.liste))
        daten = {'id': eid, 'schaerfen_beleg': status['ziele'][0]['beleg'], 'auswerter': ['p'],
                 'eingaben': {'felder': {'A': {'art': 'text', 'wert': 'Testwert'}}}}
        v = self.p.vorschau(daten)
        self.assertIn('Besser 1 Testwert', v['fassungen'][0]['auftrag'])
        daten['gesendet_stand'] = {f['name']: f['gesendet_stand'] for f in v['fassungen']}
        self.p.testen(daten)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 4)
        self.assertEqual(self.sammlung.read_bytes(), vorher)
        self.assertFalse((Path(self.p._ordner(eid)) / 'prompt.md').exists())
        self.assertEqual(len(self.p.lesen(eid)['tests']), 1)

    def test_ungueltiger_sammlungskasten_nicht_testbar(self):
        eid = 'sammlung:Wissen#1'
        f = self.p.lesen(eid)['fassungen'][0]
        self.cd.update(text=f['text'], ablage='sammlung', basis={'id': eid, 'fassung': f['name'], 'stand': f['stand']})
        self.antwort = '~~~text\nOhne nötigen Platzhalter\n~~~'
        status = self.senden()
        self.arbeiten()
        with self.assertRaisesRegex(ValueError, 'gültigen Promptkasten'):
            self.p.vorschau({'id': eid, 'schaerfen_beleg': status['ziele'][0]['beleg'], 'auswerter': ['p']})
        self.assertTrue(self.beleg(self.au.liste[0])['ergebnis'].startswith('ungültig'))

    def test_namenskonflikt_ueberschreibt_keine_fassung(self):
        status = self.senden()
        a = self.au._naechste()
        prompts.antwort_schreiben(a['datei'], '~~~text\nNeue Fassung [A]\n~~~')
        prompts._kopf_setzen(a['datei'], {'ergebnis_fassung': 'Fassung 1'})
        with self.assertRaises(prompts.Konflikt):
            self.au._ausfuehren(a)
        self.assertEqual(self.p.lesen(status['id'])['fassungen'][0]['text'], self.cd['text'])
        self.assertEqual(self.fake.aufrufe, 0)

    def test_auto_typ_erkannt_oder_unbekannt_ohne_kopfveraenderung(self):
        import uuid
        self.cd.update(prompt_typ='auto', ziele=self.cd['ziele'][:1])
        for zeile, erwartet in [('Prompt-Typ: code', 'code'), ('Prompt-Typ: erfunden', None), ('', None)]:
            self.cd['anfrage_id'] = str(uuid.uuid4())
            self.antwort = '~~~text\nGültige Fassung [A]\n~~~\n' + zeile
            status = self.senden()
            self.arbeiten()
            z = status['ziele'][0]
            ansicht = self.p.datei_inhalt(status['id'], 'schaerfen', z['beleg'])
            self.assertEqual(ansicht['prompt_typ_erkannt'], erwartet)
            self.assertEqual(ansicht['typ_anzeige'], erwartet or 'Typ nicht erkannt')
            self.assertEqual(ansicht['neue_fassung'], 'Gültige Fassung [A]')
            self.assertEqual(self.p.lesen(status['id'])['prompt_typ'], 'auto')

    def test_katalog_typmetadaten_nur_aus_gueltiger_antwort_ohne_dateiaenderung(self):
        self.cd.update(prompt_typ='auto', ziele=self.cd['ziele'][:1])
        status = self.senden()
        self.arbeiten()
        a = self.au.liste[0]
        datei = Path(a['datei'])
        promptdatei = Path(self.p._ordner(status['id'])) / 'prompt.md'
        original = promptdatei.read_bytes()
        for antwort, gueltig, typ in [
                ('~~~text\nNeue Fassung [A]\n~~~\nPrompt-Typ: wissen', True, 'wissen'),
                ('~~~text\nPrompt-Typ: code\n[A]\n~~~', True, None),
                ('~~~text\nPlatzhalter fehlt\n~~~\nPrompt-Typ: code', False, None),
                ('Antwort ohne Kasten\nPrompt-Typ: code', False, None)]:
            prompts.antwort_schreiben(str(datei), antwort)
            beleg_vorher = datei.read_bytes()
            d = self.p.lesen(status['id'])
            b = d['schaerfen'][0]
            self.assertEqual(b['ergebnis_gueltig'], gueltig)
            self.assertEqual(b['prompt_typ_erkannt'], typ)
            self.assertEqual(d['prompt_typ'], 'auto')
            self.assertEqual(datei.read_bytes(), beleg_vorher)
            self.assertEqual(promptdatei.read_bytes(), original)

    def test_bild_video_mit_ohne_realismus_nur_schreibmodell(self):
        import uuid
        for typ in ('bild', 'video'):
            for realismus in (False, True):
                self.cd.update(anfrage_id=str(uuid.uuid4()), prompt_typ=typ, realismus=realismus,
                               ziele=[{'zielprofil': typ}])
                v = self.p.composer_vorschau(self.cd)
                auftrag = v['ziele'][0]['auftrag']
                self.assertIn('hat Vorrang vor dem Skilltext', auftrag)
                self.assertIn('Keine Erzeugung starten', auftrag)
                self.assertEqual('Fachregeln für fotorealistische Menschen' in auftrag, realismus)
                self.assertEqual('Regeln zum Schärfen' in auftrag, not realismus)
                self.senden()
                self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 4)
        self.assertEqual(self.au.anbieter['claude'].aufrufe, 0)

    def test_modus_vorlage_neue_felder_und_unveraendertes_original(self):
        self.cd.update(modus='vorlage', ziele=self.cd['ziele'][:1])
        v = self.p.composer_vorschau(self.cd)
        self.assertIn('Wechselnde Angaben als aussagekräftige [Platzhalter]', v['ziele'][0]['auftrag'])
        status = self.senden()
        self.arbeiten()
        a = self.au.liste[0]
        b = self.p.datei_inhalt(status['id'], 'schaerfen', Path(a['datei']).name)
        self.assertEqual(b['neue_platzhalter'], ['Projektkontext'])
        self.assertEqual(self.p.lesen(status['id'])['modus'], 'vorlage')

    def test_flash_ziel_nimmt_tatsaechlichen_kontext_bei_gleicher_kennung(self):
        lokal = self.au.anbieter['lokal']
        self.cd['ziele'] = self.cd['ziele'][1:2]
        for kontext in (131072, 262144):
            with patch.object(lokal, 'verfuegbar', return_value=(True, '')), \
                    patch.object(lokal, 'kontext_geladen', return_value=(kontext, '/health', 'flash')):
                ziel = self.p.composer_vorschau(self.cd)['ziele'][0]['zielmodell']
                self.assertEqual((ziel['kontext'], ziel['kontext_quelle'], ziel['modell_tatsaechlich']),
                                 (kontext, '/health', 'flash'))

    def test_eingabepruefung_und_keine_zweite_wissenssammlung(self):
        f = self.e['fassungen'][0]
        for d in (dict(self.cd, text=''), dict(self.cd, text='x'*20001), dict(self.cd, ziele=[]),
                  dict(self.cd, ziele=self.cd['ziele']*2), dict(self.cd, hinweise='x'*2001),
                  dict(self.cd, ablage='sammlung'), dict(self.cd, realismus=True),
                  dict(self.cd, prompt_typ='erfunden'), dict(self.cd, modus='erfunden'),
                  dict(self.cd, schreibmodell='fehlt'), dict(self.cd, skill='unerlaubt'),
                  dict(self.cd, text='~~~text\nkein Rohprompt\n~~~')):
            with self.assertRaises((ValueError, prompts.PromptFehler)):
                self.p.composer_vorschau(d)
        basis = {'id': self.e['id'], 'fassung': f['name'], 'stand': 'veraltet'}
        with self.assertRaises(prompts.Konflikt):
            self.p.composer_vorschau(dict(self.cd, basis=basis))
        basis['stand'] = f['stand']
        with self.assertRaises(prompts.Konflikt):
            self.p.composer_vorschau(dict(self.cd, basis=basis, text='Geändert'))
        self.assertEqual(self.au.liste, [])

    def test_titel_erste_acht_woerter_70_zeichen_und_status_unbekannt(self):
        import uuid
        self.cd['text'] = ' '.join('Wort' + str(i) for i in range(12))
        self.assertEqual(self.p.composer_vorschau(self.cd)['titel'], ' '.join(self.cd['text'].split()[:8]))
        self.cd['text'] = 'x'*200
        self.assertEqual(len(self.p.composer_vorschau(self.cd)['titel']), 70)
        self.assertEqual(self.p.composer_status({'anfrage_id': str(uuid.uuid4())})['gefunden'], False)
        for aid in ('../fremd', '', None, 'keine-uuid'):
            with self.assertRaises(ValueError):
                self.p.composer_status({'anfrage_id': aid})

    def test_legacy_schaerfen_optional_version_zwei_weiterhin_vorschaupflicht(self):
        d = dict(self.sd, prompt_typ='code', modus='vorlage', zielmodell='c')
        v = self.p.schaerfen_vorschau(d)
        self.assertEqual(v['eingaben']['bau_version'], 2)
        with self.assertRaises(prompts.Konflikt):
            self.p.schaerfen(d)
        self.p.schaerfen(dict(d, gesendet_stand=v['gesendet_stand']))
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 1)

    def test_fehlendes_lokales_testprofil_bewusst_anlegen_ohne_modellstart(self):
        vorher = copy.deepcopy(self.au.profile)
        optionen = self.p.optionen()
        qwen = optionen['zielprofile'][0]['varianten'][0]
        self.assertEqual(qwen['testprofile'], [])
        self.assertEqual(self.au.profile, vorher)
        self.assertEqual(self.au.profil_neu({'anbieter': 'lokal', 'modell': 'qwen27-unsloth', 'stufe': 'high'})[0], 400)
        self.assertEqual(self.au.profil_neu({'anbieter': 'lokal', 'modell': 'qwen27-unsloth'})[0], 200)
        qwen = self.p.optionen()['zielprofile'][0]['varianten'][0]
        self.assertEqual(len(qwen['testprofile']), 1)
        p = self.au.profile[-1]
        self.assertFalse(self.au.profil_info(p)['prompts_verfuegbar'])
        self.cd['ziele'][0]['testprofil'] = p['id']
        self.assertEqual(self.p.composer_vorschau(self.cd)['ziele'][0]['testprofil_id'], p['id'])
        self.assertEqual(self.fake.aufrufe, 0)

    def test_einreihung_speicherfehler_idempotent_erneut_sichern(self):
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        speichern = self.au._speichern
        anzahl = 0
        def fehlschlag():
            nonlocal anzahl
            anzahl += 1
            if anzahl == 1:
                raise OSError('Test: Speichern fehlgeschlagen')
            speichern()
        with patch.object(self.au, '_speichern', side_effect=fehlschlag):
            with self.assertRaises(OSError):
                self.p.composer_senden(self.cd)
            self.assertEqual(len(self.au.liste), 1)
            self.p.composer_senden(self.cd)
        self.assertEqual(len(self.au.liste), 3)
        self.assertEqual(len(json.loads(Path(self.au.datei).read_text(encoding='utf-8'))['auswertungen']), 3)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)

    def test_neue_bewusste_sendung_mit_gleichem_titel_bekommt_eigene_kennung(self):
        import uuid
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        schreiben = self.p._sendung_schreiben
        def reservieren_und_absturz(*args):
            schreiben(*args)
            raise Ende()
        with patch.object(self.p, '_sendung_schreiben', side_effect=reservieren_und_absturz):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        zuerst = self.p.composer_status(self.cd)['id']
        self.cd['anfrage_id'] = str(uuid.uuid4())
        danach = self.p.composer_senden(self.cd)['id']
        self.assertNotEqual(zuerst, danach)

    def test_zusaetzlicher_oder_offener_kasten_ist_ungueltig(self):
        for antwort in ('~~~text\nNeu [A]\n~~~\n```json\n{}\n```',
                        '~~~text\nNeu [A]\n~~~\n```\noffen'):
            a = prompts.schaerfen_auswerten(antwort, '[A]', 'Schärfen', 2)
            self.assertTrue(a['grund'])

    def test_material_und_gewaehlter_kontext_bleiben_nach_einreihung_eingefroren(self):
        material = self.basis / 'Material.txt'
        material.write_text('Material vor dem Senden', encoding='utf-8')
        k = self.p.kontext_neu({'titel': 'Kontext A', 'wert': 'Ausgewählter Kontext'})
        self.p.kontext_neu({'titel': 'Kontext B', 'wert': 'Ungewählter geheimer Sachtext'})
        self.cd.update(materialien=[{'art': 'datei', 'pfad': str(material)}], kontexte=[{'id': k['id'], 'stand': k['stand']}])
        v = self.p.composer_vorschau(self.cd)
        self.assertIn('Ausgewählter Kontext', v['ziele'][0]['auftrag'])
        self.assertNotIn('Ungewählter geheimer Sachtext', v['ziele'][0]['auftrag'])
        self.cd['gesendet_staende'] = v['gesendet_staende']
        self.p.composer_senden(self.cd)
        material.write_text('Material nach dem Senden', encoding='utf-8')
        self.p.kontext_speichern(dict(k, wert='Kontext nach dem Senden'))
        self.arbeiten()
        self.assertEqual(self.fake.texte, [z['auftrag'] for z in v['ziele']])
        self.assertNotIn('Material vor dem Senden', '\n'.join(self.logs))

    def test_material_entfernen_aendert_naechste_vorschau(self):
        self.cd['materialien'] = [{'art': 'text', 'name': 'Text.txt', 'wert': 'Textmaterial'}]
        vorher = self.p.composer_vorschau(self.cd)
        self.cd['materialien'] = []
        nachher = self.p.composer_vorschau(self.cd)
        self.assertNotEqual(vorher['gesendet_staende'], nachher['gesendet_staende'])

    def test_paralleler_doppelpost_einreihung_dedupliziert(self):
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        original = self.au.einreihen
        barriere = threading.Barrier(2)
        lokal = threading.local()
        def gleichzeitige_einreihung(a):
            if not getattr(lokal, 'gestartet', False):
                lokal.gestartet = True
                barriere.wait(timeout=3)
            original(a)
        ergebnisse, fehler = [], []
        def senden():
            try:
                ergebnisse.append(self.p.composer_senden(copy.deepcopy(self.cd)))
            except BaseException as ex:
                fehler.append(ex)
        with patch.object(self.au, 'einreihen', side_effect=gleichzeitige_einreihung):
            faeden = [threading.Thread(target=senden) for _ in range(2)]
            for t in faeden:
                t.start()
            for t in faeden:
                t.join(5)
                self.assertFalse(t.is_alive())
        self.assertEqual(fehler, [])
        self.assertEqual(ergebnisse[0]['auftraege'], ergebnisse[1]['auftraege'])
        self.assertEqual(len(self.au.liste), 3)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 3)


    def mehrfach(self, ziele=3):
        self.cd.pop('schreibmodell', None)
        self.cd['schreibmodelle'] = ['p', 'c']
        self.cd['ziele'] = self.cd['ziele'][:ziele]
        self.au.profile[0]['name'] = 'Codex · Sol · sehr hoch'
        self.au.profile[0]['stufe'] = 'xhigh'
        self.au.profile[-1].update(name='Claude · Opus · hoch', stufe='high')
        self.au.anbieter['claude'].ausfuehren = self.fake.ausfuehren
        self.au._speichern()

    def test_mehrfach_zwei_schreibmodelle_drei_ziele_sechs_laeufe(self):
        self.mehrfach()
        v = self.p.composer_vorschau(self.cd)
        self.assertNotIn('schreibmodell', v)
        self.assertEqual([p['id'] for p in v['schreibmodelle']], ['p', 'c'])
        erwartet = [(z['zielschluessel'], pid) for z in v['ziele'] for pid in ['p', 'c']]
        self.assertEqual([(l['zielschluessel'], l['schreibmodell_id']) for l in v['laeufe']], erwartet)
        self.assertTrue(all(set(l) == {'zielschluessel', 'schreibmodell_id', 'geschaetzt', 'reserve'}
                            for l in v['laeufe']))
        self.assertTrue(all('geschaetzt' not in z and 'reserve' not in z for z in v['ziele']))
        status = self.senden()
        self.assertTrue(status['vollstaendig'])
        self.assertEqual(len(status['auftraege']), 6)
        self.assertEqual(len(set(status['auftraege'])), 6)
        for nr, (a, z) in enumerate(zip(self.au.liste, status['ziele'])):
            p = v['schreibmodelle'][nr % 2]
            b = self.beleg(a)
            self.assertEqual(b['auftragsgruppe'], self.cd['anfrage_id'])
            self.assertEqual(b['lauf_nr'], nr)
            for feld, wert in {'auswerter': p['name'], 'anbieter': p['anbieter'], 'modell': p['modell'],
                               'schreibmodell_id': p['id'], 'denkstufe': p['stufe'],
                               'kontext': p['kontext'], 'kontext_quelle': p['kontext_quelle'],
                               'verarbeitung': p['verarbeitung']}.items():
                self.assertEqual(b[feld], wert)
            self.assertEqual((z['schreibmodell_id'], z['auswerter']), (p['id'], p['name']))
            self.assertEqual(b['gesendet_stand'], v['ziele'][nr // 2]['gesendet_stand'])
            self.assertNotRegex(Path(a['datei']).stem, r' \(\d+\)$')
        self.assertEqual(len({a['datei'] for a in self.au.liste}), 6)
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 6)
        self.assertEqual([a['zustand'] for a in self.au.liste], ['fertig'] * 6)
        self.assertEqual(len(self.p.lesen(status['id'])['fassungen']), 7)

    def test_mehrfach_auswahlfehler_ohne_anlage(self):
        faelle = [({'schreibmodelle': ['p']}, 'Bitte nur eine Schreibmodell-Angabe senden.'),
                  ({'schreibmodelle': []}, 'Bitte ein Schreibmodell wählen.'),
                  ({'schreibmodelle': ['p', 'p']}, 'Ein Schreibmodell wurde mehrfach ausgewählt.'),
                  ({'schreibmodelle': ['p', 'c', 'd', 'e']}, 'Höchstens drei Schreibmodelle auswählen.'),
                  ({'schreibmodelle': ['p', 7]}, 'Ungültige Schreibmodell-Auswahl.'),
                  ({'schreibmodelle': 'p'}, 'Ungültige Schreibmodell-Auswahl.')]
        vorher = sorted(str(p) for p in Path(self.p.ordner).rglob('*'))
        for nr, (auswahl, meldung) in enumerate(faelle):
            d = dict(self.cd)
            if nr:
                d.pop('schreibmodell')
            d.update(auswahl)
            with self.subTest(auswahl=auswahl), self.assertRaises(ValueError) as ex:
                self.p.composer_senden(d)
            self.assertEqual(str(ex.exception), meldung)
        self.assertEqual(sorted(str(p) for p in Path(self.p.ordner).rglob('*')), vorher)
        self.assertEqual(self.au.liste, [])

    def test_drei_schreibmodelle_vier_ziele_zwoelf_laeufe(self):
        self.mehrfach()
        self.au.profile.append({'id': 'd', 'anbieter': 'fake', 'modell': 'modell', 'name': 'Drittes Schreibmodell'})
        self.au.profile.append({'id': 'codex-ziel', 'anbieter': 'codex', 'modell': 'modell', 'name': 'Codex · Ziel'})
        self.au.anbieter['codex'] = self.au.anbieter['claude']
        self.cd['schreibmodelle'].append('d')
        self.cd['ziele'].append({'zielprofil': 'codex', 'testprofil': 'codex-ziel'})
        s = self.senden()
        self.assertEqual(len(s['ziele']), 12)
        self.assertTrue(s['vollstaendig'])
        self.assertEqual([b['schreibmodell_id'] for b in s['ziele']], ['p', 'c', 'd'] * 4)
        self.assertEqual([self.beleg(a)['lauf_nr'] for a in self.au.liste], list(range(12)))
        self.arbeiten()
        self.assertEqual(self.fake.aufrufe, 12)
        self.assertEqual([a['zustand'] for a in self.au.liste], ['fertig'] * 12)

    def test_mehrfach_unverfuegbar_oder_fehlend_mit_name_ohne_anlage(self):
        self.mehrfach()
        vorher = sorted(str(p) for p in Path(self.p.ordner).rglob('*'))
        with patch.object(self.au.anbieter['claude'], 'verfuegbar', return_value=(False, 'Testgrund')):
            with self.assertRaisesRegex(prompts.PromptFehler, 'Claude · Opus · hoch: Testgrund') as ex:
                self.p.composer_senden(self.cd)
            self.assertEqual(ex.exception.code, 'anbieter')
        self.cd['schreibmodelle'] = ['p', 'geloescht']
        with self.assertRaisesRegex(ValueError, 'geloescht:'):
            self.p.composer_senden(self.cd)
        self.assertEqual(sorted(str(p) for p in Path(self.p.ordner).rglob('*')), vorher)
        self.assertEqual(self.au.liste, [])

    def test_mehrfach_kontextpruefung_je_schreibmodell_ohne_anlage(self):
        self.mehrfach()
        vorher = sorted(str(p) for p in Path(self.p.ordner).rglob('*'))
        with patch.object(self.au.anbieter['claude'], 'kontext_geladen', return_value=(64, 'Fake', 'modell')):
            with self.assertRaisesRegex(prompts.PromptFehler, 'Claude · Opus · hoch: Der Auftrag ist zu lang') as ex:
                self.p.composer_senden(self.cd)
            self.assertEqual(ex.exception.code, 'kontext')
        self.assertEqual(sorted(str(p) for p in Path(self.p.ordner).rglob('*')), vorher)
        self.assertEqual(self.au.liste, [])

    def test_mehrfach_fortsetzung_nach_erster_von_vier_beleganlagen(self):
        self.mehrfach(2)
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        anlegen = prompts.schaerfen_anlegen
        def absturz(*args):
            anlegen(*args)
            raise Ende()
        with patch.object(prompts, 'schaerfen_anlegen', side_effect=absturz):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        s = self.p.composer_status(self.cd)
        self.assertEqual(len(self.p.lesen(s['id'])['schaerfen']), 1)
        self.assertEqual((s['ziele'][1]['schreibmodell_id'], s['ziele'][1]['auswerter']), ('c', ''))
        status = self.p.composer_senden(self.cd)
        self.assertTrue(status['vollstaendig'])
        self.assertEqual(len(self.p.lesen(status['id'])['schaerfen']), 4)
        self.assertEqual(len(self.au.liste), 4)
        self.assertEqual(self.p.composer_senden(self.cd), status)

    def test_mehrfach_geaenderte_regeln_blockieren_teilanlage_neue_sendung_moeglich(self):
        import uuid
        self.mehrfach(2)
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        anlegen = prompts.schaerfen_anlegen
        def absturz(*args):
            anlegen(*args)
            raise Ende()
        with patch.object(prompts, 'schaerfen_anlegen', side_effect=absturz):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        alt = self.p.composer_status(self.cd)
        self.regeln.write_text(self.regeln.read_text(encoding='utf-8').replace(
            'Eine klare Hauptaufgabe', 'Eine neue Hauptaufgabe'), encoding='utf-8')
        with self.assertRaisesRegex(prompts.Konflikt, 'Inhalt hat sich seit der Vorschau geändert'):
            self.p.composer_senden(self.cd)
        self.assertEqual(len(self.p.lesen(alt['id'])['schaerfen']), 1)
        self.assertEqual(self.au.liste, [])
        self.cd['anfrage_id'] = str(uuid.uuid4())
        neu = self.senden()
        self.assertNotEqual(neu['id'], alt['id'])
        self.assertTrue(neu['vollstaendig'])
        self.assertEqual(len(self.au.liste), 4)
        self.assertEqual(len(self.p.lesen(alt['id'])['schaerfen']), 1)

    def test_mehrfach_recovery_prueft_auftrags_id_ziel_und_schreibmodell(self):
        self.mehrfach(2)
        s = self.senden()
        meta = self.p._sendung_lesen(self.cd['anfrage_id'])
        meta['vollstaendig'] = False
        for z in meta['ziele']:
            z['eingereiht'] = False
        self.p._sendung_schreiben(self.cd['anfrage_id'], meta)
        a = self.au.liste[0]
        datei = Path(a['datei'])
        original = datei.read_text(encoding='utf-8')
        # Dasselbe Ziel mit anderem Schreibmodell und anderer Laufkennung gehört zum Geschwisterlauf.
        self.assertTrue(self.p.composer_senden(self.cd)['vollstaendig'])
        for feld, wert in [('zielschluessel', 'anderes-ziel'), ('schreibmodell_id', 'c')]:
            self.p._sendung_schreiben(self.cd['anfrage_id'], meta)
            prompts._kopf_setzen(str(datei), {feld: wert})
            with self.assertRaisesRegex(prompts.Konflikt, 'Ein Gruppenbeleg passt nicht zu seinem Lauf'):
                self.p.composer_senden(self.cd)
            datei.write_text(original, encoding='utf-8')
        self.p._sendung_schreiben(self.cd['anfrage_id'], meta)
        doppelt = datei.with_name('Doppelbeleg.md')
        doppelt.write_text(original, encoding='utf-8')
        with self.assertRaisesRegex(prompts.Konflikt, 'Mehrere Belege für denselben Lauf'):
            self.p.composer_senden(self.cd)
        self.assertEqual(len(self.au.liste), 4)
        self.assertEqual(len(s['auftraege']), 4)

    def test_altfortsetzung_zweite_unterbrechung_ohne_doppelbeleg(self):
        self.cd['ziele'] = self.cd['ziele'][:2]
        self.cd['gesendet_staende'] = self.p.composer_vorschau(self.cd)['gesendet_staende']
        # Alter Fingerabdruck wird direkt aus der unnormalisierten Eingabe berechnet.
        fingerabdruck = prompts.sha(json.dumps({k: v for k, v in self.cd.items()
            if k not in ('aktion', 'anfrage_id', 'gesendet_staende')}, ensure_ascii=False,
            sort_keys=True, separators=(',', ':')))
        anlegen = prompts.schaerfen_anlegen
        def absturz(*args):
            anlegen(*args)
            raise Ende()
        with patch.object(prompts, 'schaerfen_anlegen', side_effect=absturz):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        meta = self.p._sendung_lesen(self.cd['anfrage_id'])
        for z in meta['ziele']:
            z.pop('schreibmodell_id')
        self.p._sendung_schreiben(self.cd['anfrage_id'], meta)
        beleg = next(Path(self.p._ordner(meta['eintrag'])).glob('schaerfen/*.md'))
        roh = beleg.read_text(encoding='utf-8')
        beleg.write_text('\n'.join(z for z in roh.split('\n') if not z.startswith(('schreibmodell_id:', 'lauf_nr:'))),
                         encoding='utf-8')
        def zweiter_absturz(*args):
            migration = self.p._sendung_lesen(self.cd['anfrage_id'])
            self.assertTrue(all(z['schreibmodell_id'] == 'p' for z in migration['ziele']))
            self.assertEqual(migration['eingabe_stand'], fingerabdruck)
            return absturz(*args)
        with patch.object(prompts, 'schaerfen_anlegen', side_effect=zweiter_absturz):
            with self.assertRaises(Ende):
                self.p.composer_senden(self.cd)
        status = self.p.composer_senden(self.cd)
        self.assertTrue(status['vollstaendig'])
        self.assertEqual(len(self.p.lesen(status['id'])['schaerfen']), 2)
        self.assertEqual(len(self.au.liste), 2)
        self.assertEqual(self.p._sendung_lesen(self.cd['anfrage_id'])['eingabe_stand'], fingerabdruck)

    def test_einzelweg_erweiterte_vorschau_behaelt_antwortformat(self):
        v = self.p.schaerfen_vorschau(dict(self.sd, prompt_typ='code', modus='vorlage', zielmodell='c'))
        self.assertEqual(set(v), {'auftrag', 'gesendet_stand', 'fassung', 'eingaben', 'schreibmodell', 'zielmodell'})
        p = v['schreibmodell']
        self.assertEqual((p['id'], p['verfuegbar'], p['grund']), ('p', True, ''))
        self.assertEqual((p['geschaetzt'], p['reserve']), prompts.kontext_pruefen(v['auftrag'], p['kontext']))

    def test_mehrfach_ergebnisnamen_kurz_eindeutig_reserviert(self):
        self.mehrfach(1)
        s = self.senden()
        self.arbeiten()
        namen = [self.beleg(a)['ergebnis_fassung'] for a in self.au.liste]
        self.assertEqual(len(set(namen)), 2)
        for a, name, kurz in zip(self.au.liste, namen, ['Sol · sehr hoch', 'Opus · hoch']):
            b = self.beleg(a)
            self.assertLessEqual(len(name), 60)
            self.assertIn(b['zielmodell'].split(' · ')[0], name)
            self.assertTrue(name.endswith(' · ' + kurz))
        a = self.au.liste[0]
        prompts._kopf_setzen(a['datei'], {'ergebnis_fassung': 'Schon reserviert'})
        prompts.schaerfen_uebernehmen(prompts.Eintrag(Path(self.p._ordner(s['id'])) / 'prompt.md'), a['datei'])
        self.assertEqual(self.beleg(a)['ergebnis_fassung'], 'Schon reserviert')
        # Ein langer Zielzusatz wird vor dem Schreibmodell gekürzt.
        prompts._kopf_setzen(a['datei'], {'ergebnis_fassung': None, 'zielmodell': 'Qwen 27B Q4 · ' + 'Zusatz' * 30,
                                        'auswerter': 'Claude · ' + 'Modell' * 10})
        prompts.schaerfen_uebernehmen(prompts.Eintrag(Path(self.p._ordner(s['id'])) / 'prompt.md'), a['datei'])
        name = self.beleg(a)['ergebnis_fassung']
        self.assertLessEqual(len(name), 60)
        self.assertIn('Qwen 27B Q4', name)
        self.assertTrue(name.endswith('Modell' * 4))

    def test_ergebnisfassung_geaendert_oder_fehlend_in_liste(self):
        self.cd['ziele'] = self.cd['ziele'][:1]
        s = self.senden()
        self.arbeiten()
        d = self.p.lesen(s['id'])
        b = d['schaerfen'][0]
        self.assertFalse(b['ergebnis_geaendert'])
        self.assertFalse(b['ergebnis_fehlt'])
        f = next(f for f in d['fassungen'] if f['name'] == b['ergebnis_fassung'])
        eintrag = prompts.Eintrag(Path(self.p._ordner(s['id'])) / 'prompt.md')
        eintrag.fassung_speichern(f['name'], 'Bearbeitet [A]', f['stand'])
        b = self.p.lesen(s['id'])['schaerfen'][0]
        self.assertTrue(b['ergebnis_geaendert'])
        self.assertFalse(b['ergebnis_fehlt'])
        prompts._kopf_setzen(self.au.liste[0]['datei'], {'ergebnis_fassung': 'Nicht vorhanden'})
        b = self.p.lesen(s['id'])['schaerfen'][0]
        self.assertTrue(b['ergebnis_fehlt'])
        self.assertFalse(b['ergebnis_geaendert'])

    def test_ergebnisname_kuerzt_ziel_an_segmentgrenzen(self):
        self.cd['ziele'] = self.cd['ziele'][:1]
        status = self.senden()
        a = self.au.liste[0]
        prompts.antwort_schreiben(a['datei'], '~~~text\nNeue Fassung [A]\n~~~')
        eintrag = prompts.Eintrag(Path(self.p._ordner(status['id'])) / 'prompt.md')
        for ziel, erwartet in [
                ('Codex · GPT-6-Sol · mittel', 'Codex'),
                ('Qwen 27B Q4', 'Qwen 27B Q4'),
                ('Claude · Sonnet · Abo-Test', 'Claude · Sonnet'),
                ('EinsehrlangesZielmodell · Zusatz', 'EinsehrlangesZie')]:
            with self.subTest(ziel=ziel):
                prompts._kopf_setzen(a['datei'], {
                    'ergebnis_fassung': None, 'erstellt': '2026-11-09 12:00:00', 'zielmodell': ziel,
                    'auswerter': 'Codex · GPT-6.1-Sol · sehr hoch'})
                prompts.schaerfen_uebernehmen(eintrag, a['datei'])
                name = self.beleg(a)['ergebnis_fassung']
                self.assertEqual(name, f'Schärfen 09.11. · {erwartet} · GPT-6.1-Sol · sehr hoch')
                self.assertLessEqual(len(name), 60)
                self.assertFalse(any(teil.endswith('-') for teil in name.split(' · ')))


class ArbeitsflaecheServer(unittest.TestCase):
    setUp = ComposerLaeufe.setUp
    neu = PromptLaeufe.neu
    cloud_fake = ComposerLaeufe.cloud_fake
    arbeiten = PromptLaeufe.arbeiten
    beleg = SchaerfenLaeufe.beleg
    senden = ComposerLaeufe.senden

    def basis_waehlen(self, aktion='Rückfragen'):
        f = self.e['fassungen'][0]
        self.cd.update(text=f['text'], basis={'id': self.e['id'], 'fassung': f['name'], 'stand': f['stand']},
                       ziele=self.cd['ziele'][:1], schaerfen_aktion=aktion)

    def test_vertrag_und_grenzen_aller_einstiege(self):
        self.basis_waehlen()
        self.cd['prompt_typ'] = 'auto'
        auftrag = self.p.composer_vorschau(self.cd)['ziele'][0]['auftrag']
        self.assertIn('Stelle Sascha Rückfragen', auftrag)
        self.assertIn('{"fragen": []}', auftrag)
        self.assertNotIn('Bestimme den passenden Typ', auftrag)
        for a in ({'basis': None}, {'ziele': self.cd['ziele'] * 2}, {'schreibmodelle': ['p', 'c'], 'schreibmodell': None}):
            d = dict(self.cd, **a)
            if 'schreibmodelle' in d:
                d.pop('schreibmodell', None)
            for weg in (self.p.composer_vorschau, self.p.composer_senden):
                with self.assertRaisesRegex(ValueError, 'Rückfragen gibt es nur'):
                    weg(d)
        for weg in (self.p.schaerfen_vorschau, self.p.schaerfen):
            with self.assertRaisesRegex(ValueError, 'Rückfragen gibt es nur'):
                weg(dict(self.sd, schaerfen_aktion='Rückfragen', prompt_typ='auto'))

    def test_rueckfragen_ohne_fassung_liste_hash_und_anzeige(self):
        self.basis_waehlen()
        self.antwort = '~~~json\n{"fragen":[{"prioritaet":"hoch","frage":"Format?","warum":"Ausgabe.","vorschlaege":[]}]}\n~~~'
        self.senden()
        with patch.object(prompts, '_gruppenergebnis_uebernehmen', side_effect=AssertionError):
            self.arbeiten()
        d = self.p.lesen(self.e['id'])
        self.assertEqual(len(d['fassungen']), 1)
        b = d['auftragsgruppen'][0]['ergebnisse'][0]
        self.assertEqual((b['fragen_anzahl'], b['ergebnis']), (1, 'Fragen gestellt'))
        self.assertEqual(len(b['fragen_hash']), 64)
        a = self.p.datei_inhalt(d['id'], 'schaerfen', b['datei'])
        self.assertEqual(a['fragen'], '')
        self.assertEqual(a['fragenliste'][0]['frage'], 'Format?')

    def test_unlesbar_keine_fassung_erst_klaeren_bleibt_text(self):
        self.basis_waehlen()
        self.antwort = 'kaputt'
        self.senden()
        self.arbeiten()
        b = self.beleg(self.au.liste[-1])
        self.assertEqual(b['ergebnis'], 'Fragen nicht lesbar')
        a = self.p.datei_inhalt(self.e['id'], 'schaerfen', b['datei'])
        self.assertEqual(a['antwort'], 'kaputt')
        self.assertEqual(a['fragen_grund'], 'Fragen nicht lesbar')
        b['eingaben']['aktion'] = 'Erst klären'
        self.assertNotIn('fragenliste', prompts.schaerfen_anzeige(b))

    def test_antworten_normalisiert_reproduzierbar_ohne_fragenbeleg(self):
        self.basis_waehlen('Schärfen')
        self.cd['rueckfragen'] = [{'prioritaet': 'kritisch', 'frage': 'Format?', 'antwort': '  Kurz\r\nKlar\rEnde  '}]
        v = self.p.composer_vorschau(self.cd)
        e = v['ziele'][0]['eingaben']
        self.assertEqual(e['rueckfragen'][0]['antwort'], 'Kurz\nKlar\nEnde')
        self.assertIn('1. [kritisch] Format?\n   Antwort: Kurz\n   Klar\n   Ende\n', v['ziele'][0]['auftrag'])
        self.senden()
        a = self.au.liste[-1]
        b = self.beleg(a)
        neu, gs = prompts.schaerfen_bauen({'name': b['fassung'], 'text': b['fassung_text']}, b['eingaben'])
        self.assertEqual((neu, gs), (v['ziele'][0]['auftrag'], v['ziele'][0]['gesendet_stand']))
        self.assertEqual(self.p.datei_inhalt(self.e['id'], 'schaerfen', b['datei'])['rueckfragen'], e['rueckfragen'])
        self.assertEqual(self.p.auftrag_aus_beleg(self.e['id'], b['datei'], 'schaerfen')['id'], a['id'])

    def test_gespeicherte_antworten_nach_neuen_fragen_und_geloeschtem_beleg(self):
        import uuid
        self.basis_waehlen()
        self.antwort = '~~~json\n{"fragen":[{"prioritaet":"hoch","frage":"Welches Format?","warum":"Ausgabe.","vorschlaege":[]}]}\n~~~'
        self.senden()
        self.arbeiten()
        fragenpfad = self.au.liste[-1]['datei']
        self.cd.update(anfrage_id=str(uuid.uuid4()), schaerfen_aktion='Schärfen',
                       rueckfragen=[{'prioritaet': 'hoch', 'frage': 'Welches Format?', 'antwort': 'Als Liste'}])
        self.senden()
        lauf = self.au.liste[-1]
        def auftrag():
            b = self.beleg(lauf)
            return prompts.schaerfen_bauen({'name': b['fassung'], 'text': b['fassung_text']}, b['eingaben'])
        vorher = auftrag()
        prompts.antwort_schreiben(fragenpfad, '~~~json\n{"fragen":[]}\n~~~')
        self.assertEqual(auftrag(), vorher)
        Path(fragenpfad).unlink()
        self.assertEqual(auftrag(), vorher)
        self.antwort = '~~~text\nBesser [A]\n~~~'
        self.arbeiten()
        self.assertEqual(lauf['zustand'], 'fertig')
        self.assertFalse(any('Welches Format' in zeile or 'Als Liste' in zeile for zeile in self.logs))

    def test_antworten_formpruefung_vorschau_senden_lesen(self):
        self.basis_waehlen('Schärfen')
        f = {'prioritaet': 'hoch', 'frage': 'Format?', 'antwort': 'Kurz'}
        for wert in ([], [f] * 6, None, *([dict(f, **a)] for a in ({'prioritaet': 'falsch'}, {'frage': ''},
             {'frage': 'x' * 301}, {'frage': 'A\nB'}, {'antwort': ''}, {'antwort': 'x' * 601}, {'antwort': 'A\tB'}))):
            d = dict(self.cd, rueckfragen=wert)
            for weg in (self.p.composer_vorschau, self.p.composer_senden):
                with self.assertRaises(ValueError):
                    weg(d)
        for a in ({'basis': None}, {'schaerfen_aktion': 'Kürzen'}, {'schaerfen_aktion': 'Rückfragen'}):
            with self.assertRaisesRegex(ValueError, 'Antworten auf Rückfragen gibt es nur'):
                self.p.composer_vorschau(dict(self.cd, rueckfragen=[f], **a))
        self.cd['rueckfragen'] = [f]
        self.senden()
        a = self.au.liste[-1]
        b = self.beleg(a)
        b['eingaben']['rueckfragen'][0]['antwort'] = ''
        with patch.object(prompts, 'beleg_lesen', return_value=b):
            with self.assertRaises(ValueError):
                prompts.schaerfen_lesen(a['datei'])

    def test_fingerprint_fehlt_bleibt_alt_normalisierte_antworten(self):
        self.basis_waehlen('Schärfen')
        d = self.cd
        alt = prompts.sha(json.dumps({k: v for k, v in d.items() if k not in ('aktion', 'anfrage_id', 'gesendet_staende')},
                                    ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        self.assertEqual(self.p._composer_fingerabdruck(d), alt)
        f = [{'prioritaet': 'hoch', 'frage': 'Format?', 'antwort': 'Kurz\r\nKlar'}]
        neu = self.p._composer_fingerabdruck(dict(d, rueckfragen=f))
        self.assertNotEqual(alt, neu)
        f[0]['antwort'] = 'Kurz\nKlar'
        self.assertEqual(neu, self.p._composer_fingerabdruck(dict(d, rueckfragen=f)))

    def test_gruppen_stabil_nach_zeit_und_id(self):
        import uuid
        self.basis_waehlen('Schärfen')
        for aid in ('ffffffff-ffff-4fff-afff-ffffffffffff', '00000000-0000-4000-a000-000000000000'):
            self.cd['anfrage_id'] = aid
            self.senden()
        for a in self.au.liste:
            prompts._kopf_setzen(a['datei'], {'erstellt': '2026-11-10 12:00:00'})
        gruppen = self.p.lesen(self.e['id'])['auftragsgruppen']
        self.assertEqual([g['id'] for g in gruppen], sorted(g['id'] for g in gruppen))
        prompts._kopf_setzen(self.au.liste[0]['datei'], {'erstellt': '2026-11-09 12:00:00'})
        self.assertEqual(self.p.lesen(self.e['id'])['auftragsgruppen'][0]['id'], 'ffffffff-ffff-4fff-afff-ffffffffffff')


if __name__ == '__main__':
    unittest.main()
