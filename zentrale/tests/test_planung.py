import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from zentrale import planung  # noqa: E402

KARTEN_LEER = [{'index': 0, 'belegt': 1200, 'gesamt': 24576}, {'index': 1, 'belegt': 50, 'gesamt': 20480}]
ORNITH_Q5 = {'id': 'ornith-q5', 'bedarf_mib': {'0': 15600, '1': 12500}}
NINFER = {'id': 'ninfer', 'bedarf_mib': {'0': 22300}}


def verbraucher(eintrag, name, mib, schritt=True, blockiert=None):
    return {'eintrag': eintrag, 'name': name, 'mib_je_karte': mib, 'blockiert': blockiert,
            'schritt': {'id': f'x:{name}', 'text': name} if schritt else None}


class PlanFuerStart(unittest.TestCase):
    def test_leere_karten_brauchen_keine_schritte(self):
        plan = planung.plan_fuer_start(KARTEN_LEER, [], ORNITH_Q5, 768)
        self.assertTrue(plan['genug_platz'])
        self.assertEqual(plan['schritte'], [])

    def test_ninfer_muss_fuer_ornith_weichen(self):
        karten = [{'index': 0, 'belegt': 23400, 'gesamt': 24576}, {'index': 1, 'belegt': 50, 'gesamt': 20480}]
        v = [verbraucher('ninfer', 'NInfer', {0: 22200}),
             verbraucher(None, 'Windows-Desktop', {0: 1200}, schritt=False)]
        plan = planung.plan_fuer_start(karten, v, ORNITH_Q5, 768)
        self.assertTrue(plan['genug_platz'])
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:NInfer'])

    def test_nur_so_viel_wie_noetig_freigeben(self):
        # Auf der 3080 fehlt nur wenig Platz: das kleinere Modell reicht nicht, das größere schon.
        karten = [{'index': 0, 'belegt': 1200, 'gesamt': 24576}, {'index': 1, 'belegt': 19000, 'gesamt': 20480}]
        v = [verbraucher(None, 'klein', {1: 3000}), verbraucher(None, 'gross', {1: 15000})]
        plan = planung.plan_fuer_start(karten, v, ORNITH_Q5, 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:gross'])

    def test_ziel_selbst_wird_nicht_entladen(self):
        karten = [{'index': 0, 'belegt': 17000, 'gesamt': 24576}, {'index': 1, 'belegt': 13000, 'gesamt': 20480}]
        v = [verbraucher('ornith-q5', 'Ornith Q5', {0: 15600, 1: 12500})]
        plan = planung.plan_fuer_start(karten, v, ORNITH_Q5, 768)
        self.assertEqual(plan['schritte'], [])
        self.assertFalse(plan['genug_platz'])

    def test_fremde_programme_werden_nur_genannt(self):
        karten = [{'index': 0, 'belegt': 8000, 'gesamt': 24576}]
        v = [verbraucher(None, 'Spiel.exe', {0: 7000}, schritt=False)]
        plan = planung.plan_fuer_start(karten, v, NINFER, 768)
        self.assertFalse(plan['genug_platz'])
        self.assertEqual(plan['schritte'], [])
        self.assertEqual(plan['hinweise'][0]['belegt_von'], ['Spiel.exe'])

    def test_blockierter_verbraucher_wird_uebersprungen_und_begruendet(self):
        karten = [{'index': 0, 'belegt': 21000, 'gesamt': 24576}]
        v = [verbraucher('bild-video', 'ComfyUI', {0: 20000}, blockiert='Auftrag läuft')]
        plan = planung.plan_fuer_start(karten, v, NINFER, 768)
        self.assertEqual(plan['schritte'], [])
        self.assertEqual(plan['gruende'], ['Auftrag läuft'])
        self.assertIn('ComfyUI', plan['hinweise'][0]['belegt_von'])


class Kartenliste(unittest.TestCase):
    """Einträge mit Kartenliste (NInfer, LightOnOCR, ComfyUI): Die Zentrale wählt die Karte (seit 14.10.2026 zwei RTX 3090)."""
    ZIEL = {'id': 'lightonocr', 'karten': ['RTX 3090'], 'bedarf_je_karte_mib': 4700}

    def karte(self, idx, name='RTX 3090', belegt=1000, gesamt=24576):
        return {'index': idx, 'name': 'NVIDIA GeForce ' + name, 'gesamt': gesamt, 'belegt': belegt}

    def plan(self, karten, v=None, ziel=None):
        ziel = ziel or self.ZIEL
        idx, grund = planung.karte_waehlen(karten, v or [], ziel, 768)
        self.assertIsNone(grund)
        p = planung.plan_fuer_start(karten, v or [], dict(ziel, bedarf_mib={idx: ziel['bedarf_je_karte_mib']}), 768)
        return idx, p

    def test_engste_passende_karte_teilt_sich_mit_anderen(self):
        # Auf Karte 1 liegt schon ein Modell, LightOnOCR passt daneben: die leere Karte bleibt für große Modelle frei.
        idx, p = self.plan([self.karte(0), self.karte(1, belegt=14000)])
        self.assertEqual(idx, 1)
        self.assertEqual(p['schritte'], [])
        self.assertTrue(p['genug_platz'])

    def test_gleich_frei_nimmt_die_kleinere_nummer(self):
        self.assertEqual(self.plan([self.karte(1), self.karte(0)])[0], 0)

    def test_monitor_karte_ist_enger(self):
        # Windows hält auf der Karte mit dem Monitor etwas Speicher: Sie ist die engere.
        self.assertEqual(self.plan([self.karte(0, belegt=0), self.karte(1, belegt=884)])[0], 1)

    def test_grosses_modell_nimmt_die_karte_auf_der_es_passt(self):
        ninfer = {'id': 'ninfer', 'karten': ['RTX 3090'], 'bedarf_je_karte_mib': 22300}
        idx, p = self.plan([self.karte(0, belegt=0), self.karte(1, belegt=5600)], ziel=ninfer)
        self.assertEqual(idx, 0)
        self.assertEqual(p['schritte'], [])

    def test_monitorkarte_nicht_bis_zum_rand(self):
        # NInfer (22,3 GiB) passt auf beide leeren Karten; auf der Monitorkarte blieben nur 1,4 GiB für Windows.
        ninfer = {'id': 'ninfer', 'karten': ['RTX 3090'], 'bedarf_je_karte_mib': 22300}
        k = [self.karte(0, belegt=0), dict(self.karte(1, belegt=862), monitor=True)]
        self.assertEqual(planung.karte_waehlen(k, [], ninfer, 768, 2048), (0, None))
        self.assertEqual(planung.karte_waehlen(k, [], ninfer, 768), (1, None))  # ohne Puffer: die engste
        # Kleine Modelle teilen sich weiter die Monitorkarte; ist die andere Karte voll, geht es trotzdem dorthin.
        self.assertEqual(planung.karte_waehlen(k, [], self.ZIEL, 768, 2048), (1, None))
        k[0]['belegt'] = 22300
        self.assertEqual(planung.karte_waehlen(k, [], ninfer, 768, 2048), (1, None))

    def test_volle_karten_wenigstes_freigeben(self):
        # Nirgends Platz: lieber das kleinere Modell beenden als das große.
        k = [self.karte(0, belegt=23500), self.karte(1, belegt=21000)]
        v = [verbraucher('ninfer', 'NInfer', {0: 22300}), verbraucher('ornith', 'Ornith', {1: 20000})]
        idx, p = self.plan(k, v)
        self.assertEqual(idx, 1)
        self.assertEqual([s['id'] for s in p['schritte']], ['x:Ornith'])
        self.assertTrue(p['genug_platz'])

    def test_volle_karten_ohne_freigebbares_nimmt_die_freigebbare(self):
        k = [self.karte(0, belegt=23500), self.karte(1, belegt=23000)]
        v = [verbraucher(None, 'Spiel.exe', {0: 22000}, schritt=False), verbraucher('strata', 'Strata', {1: 22000})]
        idx, p = self.plan(k, v)
        self.assertEqual(idx, 1)
        self.assertEqual([s['id'] for s in p['schritte']], ['x:Strata'])

    def test_beide_karten_von_strata_belegt(self):
        k = [self.karte(0, belegt=24000), self.karte(1, belegt=23800)]
        v = [verbraucher('strata', 'Strata', {0: 23500, 1: 22900})]
        idx, p = self.plan(k, v)
        self.assertEqual(idx, 0)
        self.assertEqual([s['id'] for s in p['schritte']], ['x:Strata'])
        self.assertTrue(p['genug_platz'])

    def test_keine_wunschkarte_erkannt(self):
        idx, grund = planung.karte_waehlen([self.karte(0, 'RTX 4090')], [], self.ZIEL, 768)
        self.assertIsNone(idx)
        self.assertEqual(grund, 'Keine der Karten RTX 3090 ist erkannt.')

    def test_anmeldung_zaehlt_als_belegt(self):
        k = [self.karte(0), self.karte(1, belegt=14000)]
        rest = planung.angemeldet_rest([{'bedarf_mib': {1: 6000}}], [])
        k, v = planung.mit_anmeldungen(k, [], rest, 'Werkstatt (angemeldet)', '#000')
        idx, p = self.plan(k, v)
        self.assertEqual(idx, 0)
        self.assertEqual(p['schritte'], [])

    def test_reserve_genau_an_der_grenze(self):
        k = [self.karte(0), self.karte(1, belegt=24576 - 4700 - 768)]
        self.assertEqual(self.plan(k)[0], 1)
        k[1]['belegt'] += 1
        self.assertEqual(self.plan(k)[0], 0)

    def test_wunschreihenfolge_ohne_doppelte_indizes(self):
        k = [self.karte(2, 'RTX 3080'), self.karte(1, 'RTX 3090'), self.karte(0, 'RTX 3090')]
        self.assertEqual(planung.wunschkarten(k, ['rtx 3080', 'rtx 3090', 'RTX']), [2, 0, 1])

    def test_gemischte_karten_engste_passende(self):
        # Käme die RTX 3080 wieder dazu: Mit beiden Namen in der Liste zählt nur, wo es passt und wie eng es ist.
        ziel = dict(self.ZIEL, karten=['RTX 3080', 'RTX 3090'])
        k = [self.karte(0), self.karte(1), self.karte(2, 'RTX 3080', gesamt=20480)]
        self.assertEqual(self.plan(k, ziel=ziel)[0], 2)

    def test_kurznamen_aus_messung_doppelte_und_rueckfall(self):
        k = [self.karte(0, 'RTX 3090'), self.karte(1, 'RTX 3090'), self.karte(2, 'RTX 3080'),
             {'index': 3, 'name': ''}, {'index': 4}, {'index': 5, 'name': 'NVIDIA RTX A6000'}]
        cfg = {'0': {'kurz': 'Falsche Karte'}, '3': {'kurz': 'Alte Karte'}}
        self.assertEqual(planung.kurznamen(k, cfg),
                         {0: 'RTX 3090 · Nr. 0', 1: 'RTX 3090 · Nr. 1', 2: 'RTX 3080',
                          3: 'Alte Karte', 4: 'Karte 4', 5: 'RTX A6000'})

    def test_kurznamen_nach_steckplatz(self):
        cfg = {'0': {'kurz': 'RTX 3090 FE', 'bus': 2, 'name': 'RTX 3090'},
               '1': {'kurz': 'RTX 3090 Suprim', 'bus': 4, 'name': 'RTX 3090'}}
        k = [dict(self.karte(0), bus=2), dict(self.karte(1), bus=4)]
        self.assertEqual(planung.kurznamen(k, cfg), {0: 'RTX 3090 FE', 1: 'RTX 3090 Suprim'})
        # Steckplätze getauscht oder eine andere Karte im Steckplatz: Der Name folgt der Messung, nicht der Nummer.
        k = [dict(self.karte(0), bus=4), dict(self.karte(1, 'RTX 3080'), bus=2)]
        self.assertEqual(planung.kurznamen(k, cfg), {0: 'RTX 3090 Suprim', 1: 'RTX 3080'})


class GesamtBedarf(unittest.TestCase):
    """Ollama verteilt ein Modell selbst: Es zählt der freie Platz aller Karten zusammen."""
    ORNITH = {'id': 'ornith-q5', 'bedarf_gesamt_mib': 29200}
    LEER = [{'index': 0, 'belegt': 0, 'gesamt': 24576}, {'index': 1, 'belegt': 884, 'gesamt': 24576}]

    def test_leere_karten_reichen_mit_verteilung_fuer_die_vorschau(self):
        plan = planung.plan_fuer_start(self.LEER, [], self.ORNITH, 768)
        self.assertTrue(plan['genug_platz'])
        self.assertEqual(plan['schritte'], [])
        self.assertAlmostEqual(sum(plan['bedarf_mib'].values()), 29200, delta=1)
        self.assertGreater(plan['bedarf_mib'][0], plan['bedarf_mib'][1])

    def test_kleinstes_einzelnes_modell_reicht(self):
        karten = [{'index': 0, 'belegt': 22300, 'gesamt': 24576}, {'index': 1, 'belegt': 884 + 4700, 'gesamt': 24576}]
        v = [verbraucher('ninfer', 'NInfer', {0: 22300}), verbraucher('lightonocr', 'LightOnOCR', {1: 4700})]
        plan = planung.plan_fuer_start(karten, v, {'id': 'ornith-q4', 'bedarf_gesamt_mib': 23000}, 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:LightOnOCR'])
        self.assertTrue(plan['genug_platz'])

    def test_sonst_die_groessten_zuerst(self):
        karten = [{'index': 0, 'belegt': 22300, 'gesamt': 24576}, {'index': 1, 'belegt': 884 + 18000, 'gesamt': 24576}]
        v = [verbraucher('ninfer', 'NInfer', {0: 22300}), verbraucher('bild-video', 'ComfyUI', {1: 18000})]
        plan = planung.plan_fuer_start(karten, v, self.ORNITH, 768)
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:NInfer', 'x:ComfyUI'])
        self.assertTrue(plan['genug_platz'])

    def test_fehlt_trotz_freigabe_mit_hinweis_ohne_karte(self):
        karten = [{'index': 0, 'belegt': 22300, 'gesamt': 24576}, {'index': 1, 'belegt': 884 + 20000, 'gesamt': 24576}]
        v = [verbraucher('ninfer', 'NInfer', {0: 22300}), verbraucher(None, 'Spiel.exe', {1: 20000}, schritt=False)]
        plan = planung.plan_fuer_start(karten, v, self.ORNITH, 768)
        self.assertFalse(plan['genug_platz'])
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:NInfer'])
        self.assertIsNone(plan['hinweise'][0]['karte'])
        self.assertEqual(plan['hinweise'][0]['fehlend_mib'], 29200 - (24576 - 768) - (24576 - 884 - 20000 - 768))
        self.assertEqual(plan['hinweise'][0]['belegt_von'], ['Spiel.exe'])

    def test_ziel_selbst_und_blockierte_werden_nicht_freigegeben(self):
        karten = [{'index': 0, 'belegt': 20000, 'gesamt': 24576}, {'index': 1, 'belegt': 20000, 'gesamt': 24576}]
        v = [verbraucher('ornith-q5', 'Ornith Q5', {0: 15000}),
             verbraucher('bild-video', 'ComfyUI', {1: 19000}, blockiert='In ComfyUI läuft gerade ein Auftrag.')]
        plan = planung.plan_fuer_start(karten, v, self.ORNITH, 768)
        self.assertEqual(plan['schritte'], [])
        self.assertFalse(plan['genug_platz'])
        self.assertEqual(plan['gruende'], ['In ComfyUI läuft gerade ein Auftrag.'])


class PlanFreigeben(unittest.TestCase):
    def test_trennt_freigebbar_und_unberuehrt(self):
        v = [verbraucher('ninfer', 'NInfer', {0: 22000}),
             verbraucher(None, 'Windows-Desktop', {0: 1200}, schritt=False),
             verbraucher(None, 'winzig', {0: 100}, schritt=False)]
        plan = planung.plan_freigeben(v)
        self.assertEqual([s['id'] for s in plan['schritte']], ['x:NInfer'])
        self.assertEqual(plan['schritte'][0]['mib'], 22000)
        self.assertEqual([u['name'] for u in plan['unberuehrt']], ['Windows-Desktop'])

    def test_schritte_gueltig(self):
        plan = {'schritte': [{'id': 'a'}, {'id': 'b'}]}
        self.assertTrue(planung.schritte_gueltig(['a'], plan))
        self.assertFalse(planung.schritte_gueltig(['a', 'c'], plan))


class Anmeldungen(unittest.TestCase):
    ANMELDUNG = [{'bedarf_mib': {1: 5600}}]

    def test_anmeldung_zaehlt_bis_die_transkription_misst(self):
        self.assertEqual(planung.angemeldet_rest(self.ANMELDUNG, []), {1: 5600})
        gemessen = [{'schluessel': 'transkription', 'mib_je_karte': {1: 4900}}]
        self.assertEqual(planung.angemeldet_rest(self.ANMELDUNG, gemessen), {1: 700})
        gemessen = [{'schluessel': 'transkription', 'mib_je_karte': {1: 6000}}]
        self.assertEqual(planung.angemeldet_rest(self.ANMELDUNG, gemessen), {})

    def test_studio_anmeldung_zaehlt_nur_den_zuwachs_von_comfyui(self):
        # Ohne GPU-Sperre (16.10.2026): ComfyUI hielt vorher 4.000 MiB auf Karte 1, der Auftrag meldet 12.000 an.
        studio = [{'bedarf_mib': {1: 12000}, 'schluessel': 'bild-video', 'basis': {1: 4000}}]
        comfy = lambda m: [{'schluessel': 'bild-video', 'mib_je_karte': {1: m}}]  # noqa: E731
        self.assertEqual(planung.angemeldet_rest(studio, comfy(4000)), {1: 12000})
        self.assertEqual(planung.angemeldet_rest(studio, comfy(10000)), {1: 6000})   # 6.000 schon geladen
        self.assertEqual(planung.angemeldet_rest(studio, comfy(17000)), {})
        # Eine Transkription daneben zählt getrennt; ihr Verbrauch mindert die Studio-Anmeldung nicht.
        beide = studio + [{'bedarf_mib': {0: 5000, 1: 3000}}]
        gemessen = comfy(10000) + [{'schluessel': 'transkription', 'mib_je_karte': {0: 2000}}]
        self.assertEqual(planung.angemeldet_rest(beide, gemessen), {0: 3000, 1: 9000})

    def test_ueberlappende_anmeldungen_eines_verbrauchers(self):
        # Astras Gegenbeispiele (16.10.2026). A: 12.000 bei Basis 4.000, B danach: 8.000 bei Basis 8.000, gemessen 16.000:
        # der Zuwachs (12.000) deckt A ganz, B bleibt voll reserviert.
        a = {'bedarf_mib': {0: 12000}, 'schluessel': 'bild-video', 'basis': {0: 4000}, 'seit': 1}
        b = {'bedarf_mib': {0: 8000}, 'schluessel': 'bild-video', 'basis': {0: 8000}, 'seit': 2}
        comfy = [{'schluessel': 'bild-video', 'mib_je_karte': {0: 16000}}]
        self.assertEqual(planung.angemeldet_rest([b, a], comfy), {0: 8000})
        # Fehlt eine Karte in der Basis, zählt dort 0: B auf Karte 1 mit Basis nur für Karte 0.
        a = {'bedarf_mib': {0: 18000}, 'schluessel': 'bild-video', 'basis': {}, 'seit': 1}
        b = {'bedarf_mib': {1: 18000}, 'schluessel': 'bild-video', 'basis': {0: 8000}, 'seit': 2}
        comfy = [{'schluessel': 'bild-video', 'mib_je_karte': {0: 18000}}]
        self.assertEqual(planung.angemeldet_rest([a, b], comfy), {1: 18000})

    def test_zweiter_comfy_prozess_zaehlt_getrennt(self):
        # Stufe 8: Was ComfyUI 2 lädt, deckt nicht die Anmeldung des ersten Prozesses.
        a = {'bedarf_mib': {0: 12000}, 'schluessel': 'bild-video', 'basis': {0: 500}, 'seit': 1}
        b = {'bedarf_mib': {1: 12000}, 'schluessel': 'bild-video-2', 'basis': {1: 500}, 'seit': 2}
        gemessen = [{'schluessel': 'bild-video', 'mib_je_karte': {0: 500}},
                    {'schluessel': 'bild-video-2', 'mib_je_karte': {1: 9500}}]
        self.assertEqual(planung.angemeldet_rest([a, b], gemessen), {0: 12000, 1: 3000})

    def test_anmeldung_verhindert_modellstart_in_denselben_platz(self):
        # Die 3080 hätte ohne Anmeldung genau Platz für Ornith Q5; mit Anmeldung fehlt es.
        karten = [{'index': 0, 'belegt': 1200, 'gesamt': 24576}, {'index': 1, 'belegt': 50, 'gesamt': 20480}]
        rest = planung.angemeldet_rest([{'bedarf_mib': {1: 9000}}], [])
        k, v = planung.mit_anmeldungen(karten, [], rest, 'Transkription (angemeldet)', '#000')
        plan = planung.plan_fuer_start(k, v, ORNITH_Q5, 768)
        self.assertFalse(plan['genug_platz'])
        self.assertEqual(plan['hinweise'][0]['belegt_von'], ['Transkription (angemeldet)'])
        self.assertEqual(plan['schritte'], [])
        self.assertIn('Transkription (angemeldet)', [u['name'] for u in planung.plan_freigeben(v)['unberuehrt']])

    def test_platz_pruefen_mit_reserve(self):
        karten = [{'index': 0, 'belegt': 17000, 'gesamt': 24576}, {'index': 1, 'belegt': 13000, 'gesamt': 20480}]
        v = [verbraucher('ornith-q5', 'Ornith Q5', {0: 16000, 1: 12500})]
        p = planung.platz_pruefen(karten, v, {1: 5600}, 768)
        self.assertTrue(p['genug'])
        self.assertEqual(p['frei_mib'], {0: 6808, 1: 6712})
        p = planung.platz_pruefen(karten, v, {1: 7000}, 768)
        self.assertFalse(p['genug'])
        self.assertEqual(p['hinweise'][0]['fehlend_mib'], 288)
        self.assertEqual(p['hinweise'][0]['belegt_von'], ['Ornith Q5'])


if __name__ == '__main__':
    unittest.main()
