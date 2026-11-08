"""Automatisierte Gesamtabnahme, echte Logik und HTTP ausschließlich auf 3897."""
import copy
import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import uuid

from werkstatt import prompts
from werkstatt.tests.abnahme_harness import Harness, datenordner_pruefen, port_pruefen


class Abnahme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.h = Harness(self.root)
        self.addCleanup(self.h.au.beenden)
        self.enterContext(self.h.schutz())

    def auftrag(self, typ='code', realismus=False):
        ziele = [{'zielprofil': 'qwen27', 'eintrag': 'qwen27-unsloth', 'testprofil': 'qwen-q4'},
                 {'zielprofil': 'flash_next', 'eintrag': 'flash-next-strata', 'testprofil': 'flash'}]
        if typ in ('bild', 'video'):
            ziele = [{'zielprofil': typ}]
        d = {'text': 'Prüfe [Thema].', 'titel': 'Abnahme', 'prompt_typ': typ, 'modus': 'prompt',
             'ablage': 'ordner', 'basis': None, 'hinweise': '', 'schreibmodell': 'claude-abo',
             'ziele': ziele, 'materialien': [], 'kontexte': [], 'realismus': realismus,
             'anfrage_id': str(uuid.uuid4())}
        d['gesendet_staende'] = self.h.prompts.composer_vorschau(d)['gesendet_staende']
        return d

    def warten(self, ids):
        # Zustandswechsel abwarten. Ein Timeout lässt die Abnahme nachvollziehbar fehlschlagen.
        frist = time.monotonic() + 5
        while time.monotonic() < frist:
            with self.h.au._lock:
                auftraege = [a for a in self.h.au.liste if a['id'] in ids]
                if len(auftraege) == len(ids) and all(a['zustand'] in ('fertig', 'fehler', 'abgebrochen') for a in auftraege):
                    return auftraege
            self.h.au.stopp.wait(0.01)
        self.fail('Die Fake-Aufträge wurden nicht rechtzeitig fertig.')

    def test_isolation_profile_katalog_und_sperren(self):
        for port in (3894, 3895, 3896, 0, 8080):
            with self.assertRaises(ValueError):
                port_pruefen(port)
        for pfad in (Path('C:/Workstation/Arbeitsmaterial/Prompts'), Path('C:/Workstation/Skills/aktiv')):
            with self.assertRaises(ValueError):
                datenordner_pruefen(pfad)
        optionen = self.h.prompts.optionen()
        p = {x['id']: x for x in optionen['schreibmodelle']}
        self.assertTrue(p['claude-abo']['prompts_verfuegbar'])
        self.assertTrue(p['codex-abo']['prompts_verfuegbar'])
        for pid in ('claude-api', 'claude-aus', 'codex-api', 'codex-unklar', 'qwen-iq3'):
            self.assertFalse(p[pid]['prompts_verfuegbar'], pid)
            self.assertTrue(p[pid]['prompts_grund'])
        sammlung = [e for e in self.h.prompts.alle()['eintraege'] if e['herkunft'] == 'sammlung']
        self.assertEqual(len({e['abschnitt'] for e in sammlung}), 6)
        self.assertEqual(len(sammlung), 24)
        with self.assertRaises(AssertionError), socket.socket() as sock:
            sock.connect(('127.0.0.1', 3894))
        self.assertEqual(self.h.netzverstoesse, 1)

    def test_rohprompt_zwei_ziele_fassungen_ab_und_urteil(self):
        self.h.au.starten()
        d = self.auftrag()
        k = self.h.prompts.kontext_neu({'titel': 'Ausgewähltes Projekt', 'wert': 'Privater Sachtext für die Abnahme'})
        d['kontexte'] = [{'id': k['id'], 'stand': k['stand']}]
        d['materialien'] = [{'art': 'text', 'name': 'Material.txt', 'wert': 'Nur ausdrücklich ausgewähltes Material'}]
        d['gesendet_staende'] = self.h.prompts.composer_vorschau(d)['gesendet_staende']
        s = self.h.prompts.composer_senden(d)
        self.assertTrue(all(a['zustand'] == 'fertig' for a in self.warten(s['auftraege'])))
        e = self.h.prompts.lesen(s['id'])
        self.assertEqual(len(e['fassungen']), 3)
        self.assertNotEqual(e['fassungen'][1]['text'], e['fassungen'][2]['text'])
        test = {'id': e['id'], 'fassungen': [e['fassungen'][0]['name'], e['fassungen'][1]['name']],
                'auswerter': ['qwen-q4', 'codex-abo'], 'eingaben': {'felder': {'Thema': {'art': 'text', 'wert': 'Gleiche Testeingabe'}}}}
        v = self.h.prompts.vorschau(test)
        test['gesendet_stand'] = {f['name']: f['gesendet_stand'] for f in v['fassungen']}
        ids = self.h.prompts.testen(test)['auftraege']
        self.assertEqual(len(ids), 4)
        auftraege = self.warten(ids)
        self.assertTrue(all(a['zustand'] == 'fertig' for a in auftraege))
        datei = Path(auftraege[0]['datei']).name
        b = self.h.prompts.datei_inhalt(e['id'], 'beleg', datei)
        self.h.prompts.aktion({'aktion': 'urteil', 'id': e['id'], 'datei': datei, 'kopf_stand': b['kopf_stand'],
                              'urteil': 'gut', 'notiz': 'Geprüft in der automatisierten Abnahme'})
        self.assertEqual(self.h.prompts.datei_inhalt(e['id'], 'beleg', datei)['urteil'], 'gut')
        self.assertEqual(json.loads(self.h.pfad('aufrufe.json').read_text(encoding='utf-8'))['gesamt'], 6)
        logs = '\n'.join(self.h.logs)
        for inhalt in ('Privater Sachtext', 'ausgewähltes Material', 'Prüfe [Thema]'):
            self.assertNotIn(inhalt, logs)
        self.assertEqual(self.h.netzverstoesse, 0)

    def test_bild_video_mit_ohne_realismus_kein_generatoraufruf(self):
        self.h.au.starten()
        for typ in ('bild', 'video'):
            for realismus in (False, True):
                d = self.auftrag(typ, realismus)
                v = self.h.prompts.composer_vorschau(d)
                self.assertEqual('Fotorealistische Menschen' in v['ziele'][0]['auftrag'], realismus)
                s = self.h.prompts.composer_senden(d)
                self.assertEqual(self.warten(s['auftraege'])[0]['zustand'], 'fertig')
        self.assertEqual(json.loads(self.h.pfad('aufrufe.json').read_text(encoding='utf-8'))['gesamt'], 4)
        self.assertEqual(self.h.netzverstoesse, 0)

    def test_neustart_mit_laufend_markiertem_und_verwaistem_beleg(self):
        d = self.auftrag()
        s = self.h.prompts.composer_senden(d)
        a, verwaist = self.h.au.liste
        a['zustand'] = 'laeuft'
        self.h.au.liste.remove(verwaist)
        self.h.au._speichern()
        self.h.au.beenden()
        neu = Harness(self.root)
        self.addCleanup(neu.au.beenden)
        self.assertEqual(neu.au.liste[0]['zustand'], 'abgebrochen')
        b = prompts.schaerfen_lesen(verwaist['datei'])
        self.assertEqual(b['zustand'], 'abgebrochen')
        neu.au.aktion(a['id'], 'wiederholen')
        neu.prompts.aktion({'aktion': 'wiederholen_beleg', 'id': s['id'], 'datei': b['datei'], 'art_ordner': 'schaerfen'})
        self.h = neu
        neu.au.starten()
        self.assertTrue(all(a['zustand'] == 'fertig' for a in self.warten(s['auftraege'])))
        self.assertEqual(len(neu.au.liste), 2)
        self.assertEqual(json.loads(neu.pfad('aufrufe.json').read_text(encoding='utf-8'))['gesamt'], 2)

    def test_echte_http_routen_auf_3897_mit_verlorener_bestaetigung(self):
        self.h.au.starten()
        steuerung = copy.deepcopy(json.loads(self.h.pfad('steuerung.json').read_text(encoding='utf-8')))
        steuerung['http']['sendebestaetigung_verlieren'] = True
        self.h.pfad('steuerung.json').write_text(json.dumps(steuerung), encoding='utf-8')
        httpd = self.h.http_server()
        t = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
        t.start()
        def anfrage(pfad, daten=None):
            with contextlib_connection() as c:
                c.request('GET' if daten is None else 'POST', pfad, body=json.dumps(daten) if daten is not None else None,
                          headers={'X-Werkstatt': '1', 'Content-Type': 'application/json'})
                r = c.getresponse()
                return r.status, r.read()
        def contextlib_connection():
            from contextlib import closing
            return closing(http.client.HTTPConnection('127.0.0.1', 3897, timeout=3))
        try:
            self.assertEqual(anfrage('/')[0], 200)
            self.assertIn(b'p-composer', anfrage('/')[1])
            self.assertEqual(anfrage('/api/prompt-optionen')[0], 200)
            d = self.auftrag()
            with self.assertRaises(http.client.RemoteDisconnected):
                anfrage('/api/prompt', dict(d, aktion='composer_senden'))
            code, roh = anfrage('/api/prompt', {'aktion': 'composer_status', 'anfrage_id': d['anfrage_id']})
            self.assertEqual(code, 200)
            s = json.loads(roh)
            self.assertTrue(s['vollstaendig'])
            self.warten(s['auftraege'])
            self.assertEqual(len(self.h.au.liste), 2)
            self.assertEqual(self.h.netzverstoesse, 0)
        finally:
            httpd.shutdown()
            httpd.server_close()
            t.join(3)


if __name__ == '__main__':
    unittest.main()
