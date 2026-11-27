"""Riserva di medicina d'urgenza: il filtro la restituisce anche con 5 articoli NIV; se il controllo
di qualita' esclude articoli, i posti si riempiono dalla riserva (27/11: uscita con 3 su 5)."""
import contextlib
import json
import os
import tempfile
import unittest
from unittest import mock

import config as cfg
import newsletter_NIV as niv
from test_niv_pipeline import articolo, risposta, voce


class Filtro(unittest.TestCase):
    def setUp(self):
        self.c = [articolo(i) for i in range(10)]

    def test_cinque_niv_piu_riserva(self):
        r = risposta(*[voce(self.c[i]) for i in range(5)], *[voce(self.c[i], "B") for i in range(5, 9)])
        with mock.patch.object(niv, "chiama_claude", return_value=r) as m:
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual((stato["n_niv"], stato["n_em"]), (5, 0))
        self.assertEqual([a["pmid"] for a in stato["riserva"]], [self.c[i]["pmid"] for i in (5, 6, 7)])
        self.assertTrue(all(a["origine"] == "em" for a in stato["riserva"]))
        self.assertIn("PIÙ 3", m.call_args[0][0])                 # il prompt chiede la riserva

    def test_posti_liberi_prima_poi_riserva(self):
        r = risposta(*[voce(self.c[i]) for i in range(3)], *[voce(self.c[i], "B") for i in range(3, 9)])
        with mock.patch.object(niv, "chiama_claude", return_value=r):
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual((stato["n_niv"], stato["n_em"]), (3, 2))
        self.assertEqual([a["pmid"] for a in art][3:], [self.c[3]["pmid"], self.c[4]["pmid"]])
        self.assertEqual(len(stato["riserva"]), 3)

    def test_riserva_spenta(self):
        r = risposta(*[voce(self.c[i]) for i in range(5)], voce(self.c[5], "B"))
        with mock.patch.object(cfg, "RISERVA_EM", 0), mock.patch.object(niv, "chiama_claude", return_value=r) as m:
            _, stato = niv.componi_selezione(self.c)
        self.assertEqual(stato["riserva"], [])
        self.assertIn("PIÙ 0", m.call_args[0][0])


class Ripescaggio(unittest.TestCase):
    """main(): gli esclusi dal controllo vengono sostituiti dalla riserva, nell'ordine."""

    def _corsa(self, bocciati, riserva_n=3):
        niv_art = [dict(articolo(i), origine="niv") for i in range(5)]
        riserva = [dict(articolo(i), origine="em") for i in range(10, 10 + riserva_n)]
        stato = {"n_niv": 5, "n_em": 0, "filtro_ko": False, "riserva": riserva}
        sintetizzati = []

        def sintetizza(lista):
            sintetizzati.append([a["pmid"] for a in lista])
            return [dict(a, sintesi_it="S") for a in lista]

        def verifica(lista):
            return [a for a in lista if a["pmid"] not in bocciati]

        archiviati = {}
        with contextlib.ExitStack() as st:
            p = lambda *a, **k: st.enter_context(mock.patch.object(*a, **k))  # noqa: E731
            p(cfg, "DRY_RUN", True)
            p(cfg, "SOLO_PODCAST", False)
            p(cfg, "valida_config")
            p(niv, "raccogli_candidati", return_value=[articolo(i) for i in range(20)])
            p(niv, "componi_selezione", return_value=(niv_art, stato))
            p(niv, "sintetizza_articoli", side_effect=sintetizza)
            p(niv, "verifica_sintesi", side_effect=verifica)
            p(niv, "salva_archivio", side_effect=lambda wl, a: archiviati.update(pmid=[x["pmid"] for x in a]))
            p(niv.avvisi, "carica_corsi", return_value=[])
            p(niv, "genera_podcast", return_value=None)
            p(niv, "build_html", return_value="<p>x</p>")
            p(niv, "pubblica_instagram")
            for nome in ("salva_qualita", "scrivi_qualita", "salva_report_qualita"):
                if hasattr(niv, nome):
                    p(niv, nome)
            d = st.enter_context(tempfile.TemporaryDirectory())
            vecchia = os.getcwd()
            os.chdir(d)
            try:
                niv.main()
            finally:
                os.chdir(vecchia)
        return sintetizzati, archiviati.get("pmid", [])

    def test_due_esclusi_due_dalla_riserva(self):
        boc = {str(10000001), str(10000003)}
        sint, finali = self._corsa(boc)
        self.assertEqual(sint[1], [str(10000010), str(10000011)])      # solo 2, i primi della riserva
        self.assertEqual(len(finali), 5)
        self.assertEqual(finali[-2:], [str(10000010), str(10000011)])
        self.assertFalse(boc & set(finali))

    def test_se_un_ripescato_non_passa_si_prova_il_successivo(self):
        boc = {str(10000001), str(10000010)}
        sint, finali = self._corsa(boc)
        self.assertEqual(sint[1:], [[str(10000010)], [str(10000011)]])
        self.assertEqual(len(finali), 5)

    def test_riserva_finita_la_newsletter_esce_corta(self):
        boc = {str(10000000), str(10000001), str(10000002), str(10000010)}
        sint, finali = self._corsa(boc, riserva_n=2)
        self.assertEqual(len(finali), 3)                              # 2 NIV + 1 ripescato su 2

    def test_nessun_escluso_nessun_ripescaggio(self):
        sint, finali = self._corsa(set())
        self.assertEqual(len(sint), 1)
        self.assertEqual(len(finali), 5)


if __name__ == "__main__":
    unittest.main()
