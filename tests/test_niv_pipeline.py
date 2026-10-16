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


def risposta(*articoli, categoria="non-invasiva"):
    return json.dumps([{"pmid": a["pmid"], "tema": f"tema {a['pmid']}",
                        "categoria": categoria, "perche": "pertinente"} for a in articoli])


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

    def test_niente_riempimento_con_meno_di_cinque(self):
        with patch.object(niv, "chiama_claude",
                          side_effect=[risposta(self.c[0]), risposta(self.c[1])]) as mock:
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual([a["pmid"] for a in art], [self.c[0]["pmid"], self.c[1]["pmid"]])
        self.assertEqual(mock.call_count, 2)           # filtro NIV + filtro EM
        self.assertEqual((stato["n_niv"], stato["n_em"]), (1, 1))

    def test_zero_articoli_validati_restano_zero(self):
        with patch.object(niv, "chiama_claude", side_effect=["[]", "[]"]):
            art, stato = niv.componi_selezione(self.c)
        self.assertEqual(art, [])
        self.assertFalse(stato["filtro_ko"])

    def test_un_solo_articolo_basta(self):
        with patch.object(niv, "chiama_claude", side_effect=[risposta(self.c[3]), "[]"]):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual([a["pmid"] for a in art], [self.c[3]["pmid"]])

    def test_pmid_inventato_ignorato(self):
        falso = json.dumps([{"pmid": "99999999", "tema": "x", "categoria": "non-invasiva", "perche": "x"}])
        with patch.object(niv, "chiama_claude", side_effect=[falso, "[]"]):
            art, _ = niv.componi_selezione(self.c)
        self.assertEqual(art, [])

    def test_minimo_articoli_senza_riempimento(self):
        self.assertEqual(cfg.MINIMO_ARTICOLI, 1)


class ParserJsonTest(unittest.TestCase):
    def test_virgolette_non_escapate_recuperate(self):
        testo = ('[{"pmid": "1", "sintesi": "Soglie "adattive" in 300 pazienti.", "rilevanza": "ok", '
                 '"limite": "ok", "tipo": "conferma"},\n {"pmid": "2", "sintesi": "Normale.", '
                 '"rilevanza": "ok", "limite": "ok", "tipo": "conferma"}]')
        r = niv._estrai_json_array(testo)
        self.assertEqual([x["pmid"] for x in r], ["1", "2"])


if __name__ == "__main__":
    unittest.main()
