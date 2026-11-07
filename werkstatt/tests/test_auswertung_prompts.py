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
        self.assertIn(' – Schärfen – Fake', a['datei'])
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


if __name__ == '__main__':
    unittest.main()
