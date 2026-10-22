import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASIS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASIS)
from atelier import server  # noqa: E402

VERBOTEN = {3894, 3895, 3896, 8095, 8096, 8097, 8098}


def freier_port():
    for _ in range(20):
        s = socket.socket()
        try:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        finally:
            s.close()
        if port not in VERBOTEN:
            return port
    raise RuntimeError('Kein freier Prüfport gefunden.')


def png_bytes():
    def stueck(art, daten):
        return struct.pack('>I', len(daten)) + art + daten + struct.pack('>I', zlib.crc32(art + daten) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'
            + stueck(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + stueck(b'IDAT', zlib.compress(b'\x00\xff\x00\x00'))
            + stueck(b'IEND', b''))


def jpeg_bytes():
    return b'\xff\xd8\xff\xe0' + b'0' * 64 + b'\xff\xd9'


def webp_bytes():
    return b'RIFF' + struct.pack('<I', 16) + b'WEBP' + b'VP8 ' + b'0' * 16


def dataurl(roh, typ='image/png'):
    import base64
    return f'data:{typ};base64,' + base64.b64encode(roh).decode('ascii')


def projekt_daten(breite=800, hoehe=600, objekte=None, hintergrund='#ffffff'):
    return {'format': {'id': 'eigenes', 'name': 'Eigenes', 'breite': breite, 'hoehe': hoehe, 'eigen': True},
            'hintergrund': hintergrund,
            'ebenen': {'version': '6.4.3', 'objects': objekte or []}}


class StillerHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Klient:
    def __init__(self, port):
        self.basis = f'http://127.0.0.1:{port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def anfrage(self, pfad, methode='GET', daten=None, kopf=True):
        kopfzeilen = {'Accept': 'application/json'}
        roh = None
        if daten is not None:
            roh = json.dumps(daten, ensure_ascii=False).encode('utf-8')
            kopfzeilen['Content-Type'] = 'application/json'
        if kopf and methode == 'POST':
            kopfzeilen['X-Atelier'] = '1'
        req = urllib.request.Request(self.basis + pfad, data=roh, method=methode, headers=kopfzeilen)
        try:
            with self.opener.open(req, timeout=10) as r:
                code, inhalt, typ = r.status, r.read(), r.headers.get('Content-Type', '')
        except urllib.error.HTTPError as e:
            code, inhalt, typ = e.code, e.read(), e.headers.get('Content-Type', '')
        if 'application/json' in typ:
            return code, json.loads(inhalt or b'{}')
        return code, inhalt

    def get(self, pfad):
        return self.anfrage(pfad)

    def post(self, pfad, daten, kopf=True):
        return self.anfrage(pfad, 'POST', daten, kopf)


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(BASIS, 'atelier', 'config.json'), encoding='utf-8') as f:
            self.cfg = json.load(f)
        self.cfg['ablage'] = self.tmp.name
        self.cfg['werkstatt_port'] = freier_port()
        self.cfg['fibo_port'] = freier_port()
        self.cfg['max_hochladen_mb'] = 1
        self.cfg['max_export_mb'] = 2
        self.fakes = []
        self.server = self.atelier = None
        for _ in range(8):
            self.server, self.atelier = server.starte(self.cfg, 0)
            if self.server.server_address[1] not in VERBOTEN:
                break
            self.server.shutdown()
            self.server.server_close()
        else:
            self.fail('Der Prüfdienst landete immer auf einem gesperrten Port.')
        self.port = self.server.server_address[1]
        self.k = Klient(self.port)

    def tearDown(self):
        for fake in self.fakes:
            fake.shutdown()
            fake.server_close()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.tmp.cleanup()

    def fake_starten(self, handler):
        fake = ThreadingHTTPServer(('127.0.0.1', freier_port()), handler)
        fake.daemon_threads = True
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.fakes.append(fake)
        return fake

    def projekt_neu(self, name='Testprojekt', format=None):
        daten = {'name': name}
        if format is not None:
            daten['format'] = format
        code, antwort = self.k.post('/api/projekt/neu', daten)
        self.assertEqual(code, 200, antwort)
        return antwort['projekt']


class KennungUndNamen(unittest.TestCase):
    def test_health_und_startseite(self):
        tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(BASIS, 'atelier', 'config.json'), encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['ablage'] = tmp.name
        cfg['werkstatt_port'] = freier_port()
        cfg['fibo_port'] = freier_port()
        s, a = server.starte(cfg, 0)
        try:
            k = Klient(s.server_address[1])
            code, daten = k.get('/api/health')
            self.assertEqual(code, 200)
            self.assertEqual((daten['dienst'], daten['app']), ('ki-zentrale', 'atelier'))
            code, roh = k.get('/')
            self.assertEqual(code, 200)
            self.assertIn(b'<title>Atelier</title>', roh)
            code, konfig = k.get('/api/konfig')
            self.assertEqual(code, 200)
            self.assertEqual([f['id'] for f in konfig['formate']],
                             ['youtube', 'instagram', 'story', 'flyer_a5', 'flyer_a4', 'eigenes'])
            self.assertIn('Impact', konfig['schriften'])
        finally:
            s.shutdown()
            s.server_close()
            tmp.cleanup()

    def test_namen_saeubern(self):
        self.assertEqual(server.projektname_saeubern('  Flyer: Herbst?  '), 'Flyer- Herbst')
        self.assertEqual(server.projektname_saeubern('Story 2026'), 'Story 2026')
        for boese in ('', '   ', '../boese', 'C:\\boese', 'a/b', '_fibo', 'CON', 'NUL', 'x' * 81):
            with self.assertRaises(ValueError, msg=boese):
                server.projektname_saeubern(boese)
        self.assertEqual(server.dateiname_saeubern('../../Bild: Test?.png', 'png'), 'Bild- Test.png')

    def test_403_ohne_kopfzeile(self):
        tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(BASIS, 'atelier', 'config.json'), encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['ablage'] = tmp.name
        cfg['werkstatt_port'] = freier_port()
        cfg['fibo_port'] = freier_port()
        s, a = server.starte(cfg, 0)
        try:
            k = Klient(s.server_address[1])
            code, daten = k.post('/api/projekt/neu', {'name': 'Ohne Kopf'}, kopf=False)
            self.assertEqual(code, 403)
            self.assertIn('Atelier', daten['fehler'])
            req = urllib.request.Request(
                f'http://127.0.0.1:{s.server_address[1]}/api/projekt/neu',
                data=json.dumps({'name': 'Fremd'}).encode(), method='POST',
                headers={'X-Atelier': '1', 'Origin': 'https://fremd.example'})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5)
            self.assertEqual(e.exception.code, 403)
        finally:
            s.shutdown()
            s.server_close()
            tmp.cleanup()


class Projekte(Basis):
    def test_anlegen_speichern_laden_umbenennen(self):
        p = self.projekt_neu('Herbst: Flyer?')
        self.assertEqual(p['name'], 'Herbst- Flyer')
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, 'Herbst- Flyer', 'ebenen')))
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, 'Herbst- Flyer', 'export')))

        daten = projekt_daten(objekte=[{'type': 'textbox', 'atelierArt': 'text', 'atelierName': 'Titel',
                                        'text': 'Hallo', 'visible': True}])
        code, antwort = self.k.post('/api/projekt/speichern', {'name': 'Herbst- Flyer', 'projekt': daten})
        self.assertEqual(code, 200, antwort)
        code, geladen = self.k.get('/api/projekt?name=' + urllib.parse.quote('Herbst- Flyer'))
        self.assertEqual(code, 200)
        self.assertEqual(geladen['hintergrund'], '#ffffff')
        self.assertEqual(geladen['format']['breite'], 800)
        self.assertEqual(geladen['ebenen']['objects'][0]['text'], 'Hallo')
        self.assertTrue(geladen['gespeichert'])

        code, liste = self.k.get('/api/projekte')
        self.assertEqual(code, 200)
        self.assertEqual([x['name'] for x in liste['projekte']], ['Herbst- Flyer'])
        self.assertEqual(liste['projekte'][0]['anzahl_ebenen'], 1)

        code, antwort = self.k.post('/api/projekt/umbenennen', {'name': 'Herbst- Flyer', 'neu': 'Frühling'})
        self.assertEqual(code, 200, antwort)
        self.assertEqual(antwort['name'], 'Frühling')
        self.assertEqual(self.k.get('/api/projekt?name=' + urllib.parse.quote('Herbst- Flyer'))[0], 404)
        code, geladen = self.k.get('/api/projekt?name=' + urllib.parse.quote('Frühling'))
        self.assertEqual(code, 200)
        self.assertEqual(geladen['name'], 'Frühling')
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, 'Frühling', 'ebenen')))

    def test_kollision_und_ungueltige_angaben(self):
        self.projekt_neu('Doppelt')
        self.assertEqual(self.k.post('/api/projekt/neu', {'name': 'Doppelt'})[0], 409)
        self.assertEqual(self.k.post('/api/projekt/speichern',
                                     {'name': 'Fehlt', 'projekt': projekt_daten()})[0], 404)
        self.assertEqual(self.k.post('/api/projekt/neu', {'name': 'Format', 'format': {'breite': 2, 'hoehe': 2}})[0], 400)
        self.assertEqual(self.k.get('/api/projekt')[0], 404)

    def test_pfadschutz(self):
        self.projekt_neu('Sicher')
        for name in ('../boese', 'C:\\boese', '_fibo', 'a/b'):
            code, daten = self.k.get('/api/projekt?name=' + urllib.parse.quote(name))
            self.assertEqual(code, 400, name)
            if name != '_fibo':
                self.assertIn('Pfad', daten['fehler'])
        code, daten = self.k.get('/api/bild?projekt=Sicher&datei=' + urllib.parse.quote('../projekt.json'))
        self.assertEqual(code, 400)
        self.assertIn('Dateiname', daten['fehler'])
        code, daten = self.k.get('/api/bild?projekt=Sicher&datei=' + urllib.parse.quote('C:\\projekt.json'))
        self.assertEqual(code, 400)
        code, daten = self.k.get('/api/export-datei?projekt=Sicher&datei=' + urllib.parse.quote('../../x.png'))
        self.assertEqual(code, 400)

    def test_leere_liste_ohne_ablage(self):
        self.assertEqual(self.atelier.projekte(), [])


class Hochladen(Basis):
    def test_png_jpeg_webp_und_ansicht(self):
        self.projekt_neu('Bilder')
        for name, roh, typ in (('Test.png', png_bytes(), 'image/png'),
                               ('Foto.jpg', jpeg_bytes(), 'image/jpeg'),
                               ('Grafik.webp', webp_bytes(), 'image/webp')):
            code, antwort = self.k.post('/api/hochladen',
                                        {'projekt': 'Bilder', 'name': name, 'daten': dataurl(roh, typ)})
            self.assertEqual(code, 200, antwort)
            self.assertEqual(antwort['typ'], typ)
            self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, 'Bilder', 'ebenen', antwort['datei'])))
        code, antwort = self.k.post('/api/hochladen',
                                    {'projekt': 'Bilder', 'name': 'Test.png', 'daten': dataurl(png_bytes())})
        self.assertEqual(code, 200)
        self.assertNotEqual(antwort['datei'], 'Test.png')
        code, roh = self.k.get('/api/bild?projekt=Bilder&datei=' + urllib.parse.quote(antwort['datei']))
        self.assertEqual(code, 200)
        self.assertTrue(roh.startswith(b'\x89PNG'))

    def test_groesse_typ_und_projekt(self):
        self.projekt_neu('Grenzen')
        code, daten = self.k.post('/api/hochladen',
                                  {'projekt': 'Grenzen', 'name': 'gross.png',
                                   'daten': dataurl(b'\x89PNG\r\n\x1a\n' + b'x' * (1024 * 1024))})
        self.assertEqual(code, 413)
        self.assertIn('zu groß', daten['fehler'])
        code, daten = self.k.post('/api/hochladen',
                                  {'projekt': 'Grenzen', 'name': 'gif.gif', 'daten': dataurl(b'GIF89a' + b'0' * 32)})
        self.assertEqual(code, 400)
        self.assertIn('PNG, JPEG oder WebP', daten['fehler'])
        code, daten = self.k.post('/api/hochladen',
                                  {'projekt': 'Fehlt', 'name': 'a.png', 'daten': dataurl(png_bytes())})
        self.assertEqual(code, 404)

    def test_dateiname_kein_ausbruch(self):
        self.projekt_neu('Namen')
        code, antwort = self.k.post('/api/hochladen',
                                    {'projekt': 'Namen', 'name': '../../boese.png', 'daten': dataurl(png_bytes())})
        self.assertEqual(code, 200)
        self.assertNotIn('..', antwort['datei'])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'boese.png')))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, 'Namen', 'ebenen', antwort['datei'])))


class Export(Basis):
    def test_export_mit_quellen_und_fibo_warnung(self):
        self.projekt_neu('Export')
        objekte = [
            {'type': 'image', 'atelierArt': 'bild', 'atelierName': 'Fibo-Bild', 'visible': True,
             'quelle': {'art': 'fibo', 'datei': 'fibo.png', 'lizenz': 'CC BY-NC 4.0'}},
            {'type': 'textbox', 'atelierArt': 'text', 'atelierName': 'Titel', 'text': 'Hallo Welt', 'visible': True},
        ]
        self.assertEqual(self.k.post('/api/projekt/speichern',
                                     {'name': 'Export', 'projekt': projekt_daten(objekte=objekte)})[0], 200)
        code, antwort = self.k.post('/api/export', {'projekt': 'Export', 'bild': dataurl(png_bytes())})
        self.assertEqual(code, 200, antwort)
        self.assertTrue(antwort['fibo_sichtbar'])
        self.assertTrue(antwort['nicht_kommerziell'])
        ordner = os.path.join(self.tmp.name, 'Export', 'export')
        self.assertTrue(os.path.isfile(os.path.join(ordner, antwort['datei'])))
        self.assertTrue(os.path.isfile(os.path.join(ordner, antwort['json'])))
        with open(os.path.join(ordner, antwort['json']), encoding='utf-8') as f:
            begleit = json.load(f)
        self.assertTrue(begleit['nicht_kommerziell'])
        self.assertEqual(len(begleit['quellen']), 2)
        self.assertIn('CC BY-NC 4.0', [q.get('quelle', {}).get('lizenz') for q in begleit['quellen']])
        self.assertIn('Hallo Welt', [q.get('text') for q in begleit['quellen']])
        code, roh = self.k.get('/api/export-datei?projekt=Export&datei=' + urllib.parse.quote(antwort['datei']))
        self.assertEqual(code, 200)
        self.assertTrue(roh.startswith(b'\x89PNG'))

        for o in objekte:
            o['visible'] = False
        self.assertEqual(self.k.post('/api/projekt/speichern',
                                     {'name': 'Export', 'projekt': projekt_daten(objekte=objekte)})[0], 200)
        code, antwort = self.k.post('/api/export', {'projekt': 'Export', 'bild': dataurl(png_bytes())})
        self.assertEqual(code, 200)
        self.assertFalse(antwort['fibo_sichtbar'])

    def test_export_ohne_projekt_und_ungueltiges_bild(self):
        code, daten = self.k.post('/api/export', {'projekt': 'Fehlt', 'bild': dataurl(png_bytes())})
        self.assertEqual(code, 404)
        self.projekt_neu('Export2')
        code, daten = self.k.post('/api/export', {'projekt': 'Export2', 'bild': 'kein bild'})
        self.assertEqual(code, 400)
        self.assertTrue(daten['fehler'])


class FremdeDienste(Basis):
    def test_werkstatt_aus_ist_verstaendlich(self):
        code, daten = self.k.get('/api/studio/bibliothek')
        self.assertEqual(code, 503)
        self.assertIn('Werkstatt ist aus', daten['fehler'])
        self.assertIn('starten', daten['fehler'])
        self.projekt_neu('Werkstatt')
        code, daten = self.k.post('/api/studio/uebernehmen',
                                  {'projekt': 'Werkstatt', 'pfad': 'Bilder/Test.png'})
        self.assertEqual(code, 503)
        self.assertIn('Werkstatt ist aus', daten['fehler'])

    def test_werkstatt_liefert_bibliothek_und_datei(self):
        png = png_bytes()

        class Werkstatt(StillerHandler):
            def do_GET(self):
                if self.path.startswith('/api/studio/bibliothek'):
                    inhalt = {'eintraege': [
                        {'pfad': 'Bilder/Test.png', 'name': 'Test.png', 'projekt': 'Probe', 'medium': 'bild'},
                        {'pfad': 'Videos/Film.mp4', 'name': 'Film.mp4', 'projekt': 'Probe', 'medium': 'video'}],
                        'projekte': ['Probe']}
                    roh = json.dumps(inhalt).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(roh)))
                    self.end_headers()
                    self.wfile.write(roh)
                elif self.path.startswith('/studio/datei'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(png)))
                    self.end_headers()
                    self.wfile.write(png)
                else:
                    self.send_response(404)
                    self.end_headers()

        fake = self.fake_starten(Werkstatt)
        self.atelier.werkstatt = f'http://127.0.0.1:{fake.server_address[1]}'
        code, daten = self.k.get('/api/studio/bibliothek')
        self.assertEqual(code, 200, daten)
        self.assertEqual(len(daten['eintraege']), 1)
        self.assertEqual(daten['eintraege'][0]['medium'], 'bild')
        code, roh = self.k.get('/api/studio/bild?pfad=' + urllib.parse.quote('Bilder/Test.png'))
        self.assertEqual(code, 200)
        self.assertTrue(roh.startswith(b'\x89PNG'))
        self.projekt_neu('Bibliothek')
        code, antwort = self.k.post('/api/studio/uebernehmen',
                                    {'projekt': 'Bibliothek', 'pfad': 'Bilder/Test.png'})
        self.assertEqual(code, 200, antwort)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, 'Bibliothek', 'ebenen', antwort['datei'])))

    def test_fibo_aus_und_bereit(self):
        code, daten = self.k.get('/api/fibo/health')
        self.assertEqual(code, 200)
        self.assertFalse(daten['bereit'])
        self.assertEqual(daten['text'], 'aus – in der Modellzentrale starten')

        class Fibo(StillerHandler):
            antwort = {'status': 'ok', 'modell': 'fibo-2.0', 'aktiv': 'dev', 'warteschlange': 0, 'laufend': None}

            def do_GET(self):
                roh = json.dumps(self.antwort).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(roh)))
                self.end_headers()
                self.wfile.write(roh)

        fake = self.fake_starten(Fibo)
        self.atelier.fibo = f'http://127.0.0.1:{fake.server_address[1]}'
        code, daten = self.k.get('/api/fibo/health')
        self.assertEqual(code, 200)
        self.assertTrue(daten['bereit'])
        self.assertEqual(daten['text'], 'bereit')
        self.assertEqual(daten['aktiv'], 'dev')
        Fibo.antwort = {'status': 'loading'}
        code, daten = self.k.get('/api/fibo/health')
        self.assertFalse(daten['bereit'])
        self.assertIn('startet', daten['text'])


if __name__ == '__main__':
    unittest.main()
