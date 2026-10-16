"""Test offline: non chiamano API, non inviano email/Telegram."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import unquote

import config as cfg
import newsletter_NIV as niv


def articolo(i, abstract=None):
    return {"pmid": str(10000000 + i), "titolo": f"NIV study {i}",
            "abstract": abstract or "Noninvasive ventilation in acute respiratory failure. " * 12,
            "pubtypes": [], "rivista": "Respir Care", "nlmta": "Respir Care",
            "data": "2026 Oct 14", "pubdate_dt": datetime(2026, 10, 14, tzinfo=timezone.utc),
            "doi": "", "url": "", "fonti": []}


def voce(a, stadio="A", categoria="non-invasiva"):
    d = {"pmid": a["pmid"], "stadio": stadio, "tema": f"tema {a['pmid']}", "perche": "pertinente"}
    if stadio == "A":
        d["categoria"] = categoria
    return d


def risposta(*voci):
    return json.dumps(list(voci))


class RicercaTest(unittest.TestCase):
    def test_esearch_usa_edat_e_query_tematica(self):
        payload = json.dumps({"esearchresult": {"count": "2", "idlist": ["111", "222"]}}).encode()
        with patch.object(niv, "fetch_url", return_value=payload) as mock, \
                patch.object(niv.time, "sleep"):
            r = niv.cerca_pubmed(7)
        self.assertEqual([a["pmid"] for a in r], ["111", "222"])
        url = unquote(mock.call_args.args[0]).replace("+", " ")
        self.assertIn("datetype=edat", url)
        self.assertIn("reldate=7", url)
        self.assertIn("noninvasive ventilation", url)


class SelezioneTest(unittest.TestCase):
    def setUp(self):
        self.c = [articolo(i) for i in range(8)]

    def test_filtro_fallito_non_pubblica_nulla(self):
        with patch.object(niv, "chiama_claude", side_effect=RuntimeError("API non disponibile")):
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual(art, [])
        self.assertTrue(stato["filtro_ko"])

    def test_una_sola_chiamata_per_i_due_stadi(self):
        r = risposta(voce(self.c[0]), voce(self.c[1], "B"))
        with patch.object(niv, "chiama_claude", return_value=r) as mock:
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual([a["pmid"] for a in art], [self.c[0]["pmid"], self.c[1]["pmid"]])
        self.assertEqual((stato["n_niv"], stato["n_em"]), (1, 1))
        self.assertEqual([a["origine"] for a in art], ["niv", "em"])

    def test_niente_riempimento_con_meno_di_cinque(self):
        with patch.object(niv, "chiama_claude", return_value=risposta(voce(self.c[0]))):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual(len(art), 1)

    def test_zero_articoli_validati_restano_zero(self):
        with patch.object(niv, "chiama_claude", return_value="[]"):
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual(art, [])
        self.assertFalse(stato["filtro_ko"])

    def test_stadio_b_limitato_alle_posizioni_residue(self):
        a_ = [voce(self.c[i]) for i in range(4)]            # 4 NIV -> resta 1 posizione
        b_ = [voce(self.c[i], "B") for i in range(4, 8)]
        with patch.object(niv, "chiama_claude", return_value=risposta(*a_, *b_)):
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual((stato["n_niv"], stato["n_em"]), (4, 1))
        self.assertEqual(len(art), 5)

    def test_stadio_b_non_riproduce_articoli_dello_stadio_a(self):
        r = risposta(voce(self.c[0]), voce(self.c[0], "B"), voce(self.c[1], "B"))
        with patch.object(niv, "chiama_claude", return_value=r):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual([a["pmid"] for a in art], [self.c[0]["pmid"], self.c[1]["pmid"]])

    def test_tetto_articoli_collegati(self):
        a_ = [voce(self.c[i], categoria="collegata") for i in range(4)]
        with patch.object(niv, "chiama_claude", return_value=risposta(*a_)):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual(len(art), cfg.MAX_COLLEGATI)

    def test_pmid_inventato_ignorato(self):
        falso = risposta({"pmid": "99999999", "stadio": "A", "tema": "x",
                          "categoria": "non-invasiva", "perche": "x"})
        with patch.object(niv, "chiama_claude", return_value=falso):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual(art, [])

    def test_solo_niv_se_integrazione_spenta(self):
        with patch.object(cfg, "INTEGRA_CON_EM", False), \
                patch.object(niv, "chiama_claude", return_value=risposta(voce(self.c[0]))) as mock:
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual((stato["n_niv"], stato["n_em"]), (1, 0))

    def test_minimo_articoli_senza_riempimento(self):
        self.assertEqual(cfg.MINIMO_ARTICOLI, 1)


class SintesiTest(unittest.TestCase):
    def sintesi(self, *articoli):
        return json.dumps([{"pmid": a["pmid"], "sintesi": f"Sintesi {a['pmid']}.", "rilevanza": "r",
                            "limite": "l", "tipo": "conferma"} for a in articoli])

    def test_niv_ed_em_in_una_sola_chiamata(self):
        a1, a2 = articolo(1), articolo(2)
        a1["origine"], a2["origine"] = "niv", "em"
        for a in (a1, a2):
            a.update(autori="X", sintesi_it="")
        with patch.object(niv, "chiama_claude", return_value=self.sintesi(a1, a2)) as mock:
            niv.sintetizza_articoli([a1, a2])
        self.assertEqual(mock.call_count, 1)
        prompt = mock.call_args.args[0]
        self.assertIn("AMBITO: NIV", prompt)
        self.assertIn("AMBITO: EM", prompt)
        self.assertEqual(a1["sintesi_it"], f"Sintesi {a1['pmid']}.")
        self.assertEqual(a2["sintesi_it"], f"Sintesi {a2['pmid']}.")

    def test_solo_niv_usa_il_prompt_niv(self):
        a1 = articolo(1)
        a1.update(origine="niv", autori="X", sintesi_it="")
        with patch.object(niv, "chiama_claude", return_value=self.sintesi(a1)) as mock:
            niv.sintetizza_articoli([a1])
        self.assertNotIn("AMBITO:", mock.call_args.args[0])


class PromptTest(unittest.TestCase):
    def test_il_filtro_misto_contiene_i_criteri_dei_due_filtri(self):
        misto = cfg.PROMPT_FILTRO_MISTO
        for frase in ("SOGLIA: nel dubbio, ESCLUDI", "CATEGORIA \"collegata\"",
                      "IMPATTO DECISIONALE", "Massimo 2 articoli sullo stesso tema clinico",
                      "Case report e case series"):
            self.assertIn(frase, misto)
        self.assertEqual(misto.format(n=5, articoli="X").count("X"), 1)

    def test_regola_virgolette_nei_prompt_di_formato(self):
        for nome in ("PROMPT_FILTRO_MISTO", "PROMPT_SINTESI_MULTI_MISTO"):
            self.assertIn("NON usare mai virgolette doppie", getattr(cfg, nome))


class ParserJsonTest(unittest.TestCase):
    def test_virgolette_non_escapate_recuperate(self):
        testo = ('[{"pmid": "1", "sintesi": "Soglie "adattive" in 300 pazienti.", "rilevanza": "ok", '
                 '"limite": "ok", "tipo": "conferma"},\n {"pmid": "2", "sintesi": "Normale.", '
                 '"rilevanza": "ok", "limite": "ok", "tipo": "conferma"}]')
        r = niv._estrai_json_array(testo)
        self.assertEqual([x["pmid"] for x in r], ["1", "2"])


if __name__ == "__main__":
    unittest.main()
