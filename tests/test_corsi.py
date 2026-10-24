"""Test offline degli avvisi corsi (corsi.py + integrazione nella newsletter)."""
import json
import os
import tempfile
import unittest
from datetime import date

import config as cfg
import corsi

OGGI = date(2026, 10, 24)


def scrivi(voci):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"corsi": voci} if isinstance(voci, list) else voci, f)
    f.close()
    return f.name


def corso(**kw):
    base = {"titolo": "Corso POCUS", "data_inizio": "2026-11-14"}
    base.update(kw)
    return base


class CaricamentoTest(unittest.TestCase):
    def carica(self, voci, nl="pocus", **kw):
        p = scrivi(voci)
        try:
            return corsi.carica_corsi(nl, oggi=OGGI, percorso=p, **kw)
        finally:
            os.unlink(p)

    def test_corso_futuro_mostrato(self):
        r = self.carica([corso()])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["titolo"], "Corso POCUS")

    def test_corso_passato_sparisce(self):
        self.assertEqual(self.carica([corso(data_inizio="2026-10-23")]), [])

    def test_corso_di_oggi_e_ultimo_giorno_inclusi(self):
        self.assertEqual(len(self.carica([corso(data_inizio="2026-10-24")])), 1)
        self.assertEqual(len(self.carica([corso(data_inizio="2026-10-22", data_fine="2026-10-24")])), 1)
        self.assertEqual(self.carica([corso(data_inizio="2026-10-22", data_fine="2026-10-23")]), [])

    def test_attivo_false_e_newsletter(self):
        self.assertEqual(self.carica([corso(attivo=False)]), [])
        self.assertEqual(self.carica([corso(newsletter=["pocus"])], nl="niv"), [])
        self.assertEqual(len(self.carica([corso(newsletter=["niv"])], nl="niv")), 1)
        self.assertEqual(len(self.carica([corso()], nl="niv")), 1)     # senza campo: tutte

    def test_mostra_dal(self):
        self.assertEqual(self.carica([corso(mostra_dal="2026-11-01")]), [])
        self.assertEqual(len(self.carica([corso(mostra_dal="2026-10-24")])), 1)

    def test_voci_non_valide_ignorate_le_altre_restano(self):
        r = self.carica([{"titolo": "senza data"}, corso(data_inizio="14/11/2026"), "stringa",
                         None, corso(titolo="Valido")])
        self.assertEqual([c["titolo"] for c in r], ["Valido"])

    def test_massimo_due_in_ordine_di_data(self):
        r = self.carica([corso(titolo="C", data_inizio="2026-12-01"),
                         corso(titolo="A", data_inizio="2026-11-01"),
                         corso(titolo="B", data_inizio="2026-11-20")])
        self.assertEqual([c["titolo"] for c in r], ["A", "B"])

    def test_file_assente_o_rotto_non_solleva(self):
        self.assertEqual(corsi.carica_corsi("pocus", oggi=OGGI, percorso="/non/esiste.json"), [])
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write("{ non json"); f.close()
        try:
            self.assertEqual(corsi.carica_corsi("pocus", oggi=OGGI, percorso=f.name), [])
        finally:
            os.unlink(f.name)

    def test_link_non_http_scartato(self):
        r = self.carica([corso(link="javascript:alert(1)")])
        self.assertEqual(r[0]["link"], "")

    def test_iscrizioni_scadute_non_mostrate(self):
        r = self.carica([corso(iscrizioni_fino="2026-10-01")])
        self.assertIsNone(r[0]["iscrizioni_fino"])

    def test_file_del_repo_e_valido_e_vuoto_o_con_corsi_validi(self):
        self.assertIsInstance(corsi.carica_corsi("pocus", oggi=OGGI), list)
        esempio = os.path.join(os.path.dirname(corsi.__file__), "corsi.esempio.json")
        self.assertEqual(len(corsi.carica_corsi("pocus", oggi=date(2026, 10, 24), percorso=esempio)), 1)


class VerificaTest(unittest.TestCase):
    def test_file_valido_senza_problemi(self):
        p = scrivi([corso(link="https://esempio.it", newsletter=["pocus", "niv"])])
        try:
            self.assertEqual(corsi.verifica(p), [])
        finally:
            os.unlink(p)

    def test_problemi_segnalati(self):
        p = scrivi([{"titolo": "x", "data_inizio": "14/11/2026", "link": "ftp://a",
                     "newsletter": ["fb"]}, 3, corso(data_fine="boh")])
        try:
            testo = " | ".join(corsi.verifica(p))
        finally:
            os.unlink(p)
        for atteso in ("data_inizio", "https://", "newsletter 'fb'", "non e' un oggetto", "data_fine"):
            self.assertIn(atteso, testo)

    def test_json_rotto(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write("{ rotto"); f.close()
        try:
            self.assertTrue(corsi.verifica(f.name)[0].startswith("file non leggibile"))
        finally:
            os.unlink(f.name)

    def test_file_di_esempio_senza_problemi(self):
        # NB: corsi.json vero NON si controlla qui: un refuso nel file non deve
        # bloccare l'invio della newsletter (se ne occupa lo step "Controlla corsi.json").
        self.assertEqual(corsi.verifica(os.path.join(os.path.dirname(corsi.__file__),
                                                     "corsi.esempio.json")), [])


class FormattazioneTest(unittest.TestCase):
    def c(self, **kw):
        p = scrivi([corso(**kw)])
        try:
            return corsi.carica_corsi("pocus", oggi=OGGI, percorso=p)[0]
        finally:
            os.unlink(p)

    def test_date_in_italiano(self):
        self.assertEqual(corsi.data_leggibile(self.c()), "sabato 14 novembre 2026")
        self.assertEqual(corsi.data_leggibile(self.c(data_fine="2026-11-15")), "14–15 novembre 2026")
        self.assertEqual(corsi.data_leggibile(self.c(data_inizio="2026-11-30", data_fine="2026-12-01")),
                         "30 novembre – 1 dicembre 2026")

    def test_html_escape_e_link(self):
        c = self.c(titolo='<script>alert("x")</script>', link="https://esempio.it/?a=1&b=2",
                   descrizione="Parte <b>pratica</b> & teoria")
        h = corsi.html_corsi([c])
        self.assertNotIn("<script>", h)
        self.assertNotIn("<b>pratica</b>", h)
        self.assertIn("&amp;b=2", h)
        self.assertIn("Programma e iscrizioni", h)

    def test_html_vuoto_senza_corsi(self):
        self.assertEqual(corsi.html_corsi([]), "")
        self.assertEqual(corsi.html_corsi(None), "")

    def test_telegram_escape_e_lunghezza(self):
        c = self.c(titolo="A & B <i>", descrizione="x" * 1000)
        t = corsi.testo_telegram([c])
        self.assertIn("A &amp; B &lt;i&gt;", t)
        self.assertLessEqual(len(t), 4096)
        self.assertEqual(corsi.testo_telegram([]), "")

    def test_facebook_testo(self):
        t = corsi.testo_facebook(self.c(luogo="Torino", link="https://esempio.it"))
        self.assertIn("sabato 14 novembre 2026", t)
        self.assertIn("Torino", t)
        self.assertIn("https://esempio.it", t)


if __name__ == "__main__":
    unittest.main()
