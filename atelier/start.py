"""Öffnet das Atelier in einem eigenen Fenster und startet vorher bei Bedarf seinen Dienst."""
import os
import sys

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)
from gemeinsam import starter  # noqa: E402

if __name__ == '__main__':
    starter.main(os.path.dirname(os.path.abspath(__file__)), 'atelier', 'Atelier', 'atelier-dienst', '1440,920')
