"""quality.controlla_sintesi: le riconciliazioni sbagliate del revisore lasciano il numero non
dimostrato (correzione della sintesi), invece di far fallire tutta la verifica."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import quality  # noqa: E402

ABSTRACT = ("Seven studies (n = 1551), met the inclusion criteria. CPAP was associated with a significantly "
            "lower risk of intubation within 30 days than HFNO (RR 0.75 [0.65-0.86], p < 0.0001; I = 33%; "
            "moderate certainty of evidence).")
EVIDENZA = "CPAP was associated with a significantly lower risk of intubation within 30 days than HFNO"


def articolo(sintesi):
    return {"pmid": "43034002", "bibliografia_verificata": True, "abstract": ABSTRACT,
            "sintesi_it": sintesi, "rilevanza": "Rilevante in PS.", "limite": "Eterogeneità."}


def revisore(riconciliati, esito="pass", errori=None):
    risposta = {"pmid": "43034002", "esito": esito, "errori": errori or [], "avvisi": [],
                "numeri_riconciliati": riconciliati, "evidenze": [EVIDENZA]}
    return lambda prompt, max_tokens=0, system="": json.dumps(risposta)


# "25%" nella sintesi (da RR 0,75): l'abstract non lo scrive, e "RR 0.75" non contiene il 25
SINTESI_25 = "Sette studi, 1551 pazienti: CPAP riduce l'intubazione a 30 giorni del 25% (RR 0,75)."


class Riconciliazione(unittest.TestCase):
    def test_estratto_senza_il_numero_lascia_il_numero_non_dimostrato(self):
        v = quality.controlla_sintesi(articolo(SINTESI_25), revisore(
            [{"numero": "25%", "motivo": "equivalente", "evidenza": "RR 0.75 [0.65-0.86]"}]))
        self.assertEqual(v["verifica_ai"], "pass")          # la verifica c'e': la correzione puo' partire
        self.assertFalse(v["approvato"])                     # ma il numero non e' dimostrato
        self.assertIn("Numeri senza riconciliazione documentata: 25%", v["errori"])
        self.assertTrue(any("Riconciliazione respinta per 25%" in a for a in v["avvisi"]))
        self.assertEqual(v["numeri_non_supportati"], ["25%"])

    def test_estratto_non_rintracciabile_motivo_errato_voce_non_oggetto(self):
        for voce in ({"numero": "25%", "motivo": "equivalente", "evidenza": "a 25% reduction"},
                     {"numero": "25%", "motivo": "plausibile", "evidenza": "RR 0.75"},
                     "25%"):
            with self.subTest(voce=voce):
                v = quality.controlla_sintesi(articolo(SINTESI_25), revisore([voce]))
                self.assertEqual(v["verifica_ai"], "pass")
                self.assertIn("Numeri senza riconciliazione documentata: 25%", v["errori"])

    def test_conteggio_strutturale_non_giustifica_percentuali(self):
        v = quality.controlla_sintesi(articolo(SINTESI_25), revisore(
            [{"numero": "25%", "motivo": "strutturale", "evidenza": "RR 0.75"}]))
        self.assertIn("Numeri senza riconciliazione documentata: 25%", v["errori"])
        self.assertFalse(v["approvato"])

    def test_riconciliazione_corretta_approva(self):
        sintesi = "Sette studi, 1551 pazienti: CPAP riduce l'intubazione a 30 giorni (RR 0,75)."
        v = quality.controlla_sintesi(articolo(sintesi), revisore(
            [{"numero": "7", "motivo": "equivalente", "evidenza": "Seven studies (n = 1551)"}]))
        self.assertTrue(v["approvato"], v["errori"])

    def test_voce_superflua_ignorata(self):
        sintesi = "1551 pazienti, RR 0,75."
        v = quality.controlla_sintesi(articolo(sintesi), revisore(
            [{"numero": "1551", "motivo": "equivalente", "evidenza": "n = 1551"}]))
        self.assertTrue(v["approvato"], v["errori"])
        self.assertTrue(any("superflua" in a for a in v["avvisi"]))

    def test_risposta_illeggibile_resta_verifica_non_disponibile(self):
        v = quality.controlla_sintesi(articolo(SINTESI_25), lambda *a, **k: "non json")
        self.assertEqual(v["verifica_ai"], "errore")
        self.assertFalse(v["approvato"])

    def test_riconciliazioni_non_lista_resta_errore(self):
        v = quality.controlla_sintesi(articolo(SINTESI_25), revisore({"numero": "25%"}))
        self.assertEqual(v["verifica_ai"], "errore")


class RegoleDelRevisore(unittest.TestCase):
    """27/11: esclusi due articoli per un IC che esclude 1 detto "statisticamente significativo" e
    per una rilevanza che applicava i risultati al Pronto Soccorso. Il prompt ora lo consente."""

    def _prompt(self):
        visto = {}

        def chiama(prompt, max_tokens=0, system=""):
            visto["p"] = prompt
            return "non json"
        quality.controlla_sintesi(articolo(SINTESI_25), chiama)
        return visto["p"]

    def test_ic_che_esclude_il_valore_nullo_sostiene_la_significativita(self):
        p = self._prompt()
        self.assertIn('non include il valore nullo', p)
        self.assertIn('sostiene "statisticamente significativo"', p)

    def test_rilevanza_puo_applicare_i_risultati_al_ps(self):
        p = self._prompt()
        self.assertIn("può applicare i\nrisultati al Pronto Soccorso", p)
        self.assertIn('attribuisce allo studio un setting', p)


if __name__ == "__main__":
    unittest.main()
