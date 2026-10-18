"""Öffnet die Modellzentrale in einem eigenen Fenster und startet vorher bei Bedarf ihren Dienst."""
import os
import sys

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)
from gemeinsam import starter  # noqa: E402

if __name__ == '__main__':
    starter.main(os.path.dirname(os.path.abspath(__file__)), 'modellzentrale', 'Modellzentrale', 'dienst')
