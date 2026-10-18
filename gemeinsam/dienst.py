"""Grundgerüst für die lokalen Dienste der KI-Zentrale (Modellzentrale und Werkstatt).

Nur 127.0.0.1, fremde Host-Namen werden abgewiesen. Eingreifende Aufrufe (POST)
brauchen eine eigene Kopfzeile der Oberfläche; fremde Webseiten können sie ohne
CORS-Freigabe nicht setzen.
"""
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Server(ThreadingHTTPServer):
    # Unter Windows erlaubt SO_REUSEADDR einen zweiten Dienst auf demselben Port; das verhindern wir.
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Anfrage(BaseHTTPRequestHandler):
    """Gemeinsame Prüfungen und Antworten. Unterklassen setzen `kopfzeile` und `statisch`."""
    kopfzeile = 'X-Zentrale'
    web_ordner = ''
    statisch = {}
    server_version = 'KI-Zentrale/1'

    def log_message(self, *args):
        pass

    def _erlaubte_hosts(self):
        port = self.server.server_address[1]
        return {f'127.0.0.1:{port}', f'localhost:{port}'}

    def _senden(self, code, inhalt, typ='application/json; charset=utf-8'):
        daten = inhalt if isinstance(inhalt, bytes) else json.dumps(inhalt, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(daten)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(daten)

    def _host_ok(self):
        return self.headers.get('Host') in self._erlaubte_hosts()

    def _post_ok(self):
        herkunft = self.headers.get('Origin')
        return (self._host_ok() and self.headers.get(self.kopfzeile) == '1'
                and not (herkunft and herkunft.split('//', 1)[-1] not in self._erlaubte_hosts()))

    def _json_lesen(self, grenze=65536):
        laenge = int(self.headers.get('Content-Length', '0'))
        return json.loads(self.rfile.read(min(laenge, grenze)) or b'{}')

    def _statisch_senden(self, pfad):
        """True, wenn `pfad` eine Datei der Oberfläche war und gesendet wurde."""
        if pfad not in self.statisch:
            return False
        datei, typ = self.statisch[pfad]
        with open(os.path.join(self.web_ordner, datei), 'rb') as f:
            self._senden(200, f.read(), typ)
        return True


STATISCH_STANDARD = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
