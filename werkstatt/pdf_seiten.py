"""Seitenbilder für die Texterkennung der Werkstatt.

Läuft NICHT im Python der Werkstatt, sondern in der Umgebung des vorhandenen PDF-Werkzeugs
(C:\\Workstation\\Werkzeuge\\PDF\\venv, PyMuPDF), als externer Aufruf wie watch:
  <PDF-venv>\\Scripts\\python.exe -I pdf_seiten.py info <datei>
  <PDF-venv>\\Scripts\\python.exe -I pdf_seiten.py seiten <datei> <nr> [<nr> …] [--kante 2048]

Liest die Quelle nur und schreibt nichts auf die Platte. `info` gibt eine JSON-Zeile aus
({"seiten", "art"}); `seiten` je Seite eine JSON-Zeile {"seite", "breite", "hoehe", "mime", "daten"}
mit dem Bild als Base64. PDF-Seiten werden mit der längsten Kante = `--kante` gerendert (Modellkarte
LightOnOCR: 2048 px), Bilder nur verkleinert, wenn sie größer sind.
"""
import argparse
import base64
import json
import os
import sys

import pymupdf

BILDER = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def fehler(text):
    print(json.dumps({'fehler': text}, ensure_ascii=False), flush=True)
    sys.exit(2)


def oeffnen(pfad):
    try:
        doc = pymupdf.open(pfad)
    except Exception as e:  # beschädigt oder kein PDF
        fehler(f'Die Datei lässt sich nicht öffnen ({type(e).__name__}).')
    if doc.needs_pass:
        fehler('Das PDF ist mit einem Passwort geschützt.')
    return doc


def info(pfad):
    endung = os.path.splitext(pfad)[1].lower()
    if endung in BILDER:
        try:
            pix = pymupdf.Pixmap(pfad)
        except Exception as e:
            fehler(f'Das Bild lässt sich nicht lesen ({type(e).__name__}).')
        return {'seiten': 1, 'art': 'bild', 'breite': pix.width, 'hoehe': pix.height}
    doc = oeffnen(pfad)
    return {'seiten': doc.page_count, 'art': 'pdf'}


def bild_seite(pfad, kante):
    endung = os.path.splitext(pfad)[1].lower()
    pix = pymupdf.Pixmap(pfad)
    if max(pix.width, pix.height) <= kante and not pix.alpha and pix.n in (1, 3):
        with open(pfad, 'rb') as f:
            return pix.width, pix.height, BILDER[endung], f.read()
    if pix.colorspace and pix.colorspace.n not in (1, 3):
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    faktor = min(1.0, kante / max(pix.width, pix.height))
    if faktor < 1.0:
        pix = pymupdf.Pixmap(pix, round(pix.width * faktor), round(pix.height * faktor), None)
    return pix.width, pix.height, 'image/png', pix.tobytes('png')


def seiten(pfad, nummern, kante):
    endung = os.path.splitext(pfad)[1].lower()
    if endung in BILDER:
        b, h, mime, daten = bild_seite(pfad, kante)
        yield {'seite': 1, 'breite': b, 'hoehe': h, 'mime': mime, 'daten': base64.b64encode(daten).decode('ascii')}
        return
    doc = oeffnen(pfad)
    for n in nummern:
        if not 1 <= n <= doc.page_count:
            fehler(f'Seite {n} gibt es nicht (das PDF hat {doc.page_count} Seiten).')
        seite = doc[n - 1]
        zoom = kante / max(seite.rect.width, seite.rect.height)
        pix = seite.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        yield {'seite': n, 'breite': pix.width, 'hoehe': pix.height, 'mime': 'image/png',
               'daten': base64.b64encode(pix.tobytes('png')).decode('ascii')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('befehl', choices=('info', 'seiten'))
    ap.add_argument('datei')
    ap.add_argument('nummern', nargs='*', type=int)
    ap.add_argument('--kante', type=int, default=2048)
    a = ap.parse_args()
    if not os.path.isfile(a.datei):
        fehler('Die Datei gibt es nicht (mehr).')
    if a.befehl == 'info':
        print(json.dumps(info(a.datei)), flush=True)
        return
    for zeile in seiten(a.datei, a.nummern or [1], a.kante):
        print(json.dumps(zeile), flush=True)


if __name__ == '__main__':
    main()
