"""Test offline degli avvisi corsi (corsi.py + integrazione nella newsletter)."""
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

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


class FrequenzaTest(unittest.TestCase):
    def mostrato(self, oggi, **kw):
        p = scrivi([corso(**kw)])
        try:
            return bool(corsi.carica_corsi("pocus", oggi=oggi, percorso=p))
        finally:
            os.unlink(p)

    def test_ogni_due_settimane_alterna(self):
        venerdi = [date(2026, 10, 30) + timedelta(weeks=k) for k in range(6)]
        esiti = [self.mostrato(v, data_inizio="2027-03-09", ogni_settimane=2) for v in venerdi]
        self.assertEqual(esiti, [True, False, True, False, True, False])

    def test_senza_campo_ogni_settimana(self):
        venerdi = [date(2026, 10, 30) + timedelta(weeks=k) for k in range(4)]
        self.assertTrue(all(self.mostrato(v, data_inizio="2027-03-09") for v in venerdi))

    def test_ultima_uscita_prima_del_corso_sempre(self):
        # 26/02/2027 sarebbe una settimana "saltata", ma il corso del 03/03 e' entro 7 giorni
        self.assertFalse(self.mostrato(date(2027, 2, 26), data_inizio="2027-03-09", ogni_settimane=2))
        self.assertTrue(self.mostrato(date(2027, 2, 26), data_inizio="2027-03-03", ogni_settimane=2))

    def test_conteggio_parte_da_mostra_dal(self):
        self.assertTrue(self.mostrato(date(2027, 3, 12), data_inizio="2027-11-09",
                                      mostra_dal="2027-03-11", ogni_settimane=2))
        self.assertFalse(self.mostrato(date(2027, 3, 19), data_inizio="2027-11-09",
                                       mostra_dal="2027-03-11", ogni_settimane=2))

    def test_valore_non_valido_diventa_ogni_settimana(self):
        self.assertTrue(self.mostrato(date(2026, 11, 6), data_inizio="2027-03-09", ogni_settimane="due"))

    def test_verifica_segnala_valore_non_valido(self):
        p = scrivi([corso(ogni_settimane=0), corso(ogni_settimane="2"), corso(ogni_settimane=2.5)])
        try:
            probl = corsi.verifica(p)
        finally:
            os.unlink(p)
        self.assertEqual(sum("ogni_settimane" in x for x in probl), 2)


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


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
       b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0"
       b"\x00\x00\x00\x00IEND\xaeB`\x82")


class ImmagineTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "locandine"))
        self.png = os.path.join(self.dir, "locandine", "corso uno.png")
        with open(self.png, "wb") as f:
            f.write(PNG)
        self.json = os.path.join(self.dir, "corsi.json")

    def carica(self, **kw):
        with open(self.json, "w", encoding="utf-8") as f:
            json.dump({"corsi": [corso(**kw)]}, f)
        r = corsi.carica_corsi("pocus", oggi=OGGI, percorso=self.json, base_url="https://x.it/repo/main/")
        return r[0]

    def test_percorso_nel_repo_diventa_file_e_url_pubblico(self):
        c = self.carica(immagine="locandine/corso uno.png")
        self.assertEqual(c["immagine_file"], self.png)
        self.assertEqual(c["immagine_url"], "https://x.it/repo/main/locandine/corso%20uno.png")
        self.assertEqual(self.carica(immagine="./locandine/corso uno.png")["immagine_file"], self.png)

    def test_url_https_usato_cosi_com_e(self):
        c = self.carica(immagine="https://esempio.it/l.jpg")
        self.assertIsNone(c["immagine_file"])
        self.assertEqual(c["immagine_url"], "https://esempio.it/l.jpg")

    def test_immagini_non_valide_scartate_ma_il_corso_resta(self):
        for img in ("locandine/non_esiste.png", "../segreto.png", "/etc/passwd.png",
                    "locandine/corso uno.exe", "javascript:alert(1)", "ftp://a/b.png"):
            c = self.carica(immagine=img)
            self.assertEqual((c["immagine_file"], c["immagine_url"]), (None, ""), img)
            self.assertEqual(c["titolo"], "Corso POCUS")

    def test_immagine_troppo_grande_scartata(self):
        with patch.object(corsi, "MAX_IMMAGINE", 10):
            c = self.carica(immagine="locandine/corso uno.png")
        self.assertIsNone(c["immagine_file"])

    def test_html_con_locandina_e_anteprima_locale(self):
        c = self.carica(immagine="locandine/corso uno.png", link="https://esempio.it")
        h = corsi.html_corsi([c])
        self.assertIn('src="https://x.it/repo/main/locandine/corso%20uno.png"', h)
        self.assertIn('alt="Locandina: Corso POCUS"', h)
        self.assertIn('<a href="https://esempio.it"><img', h)
        self.assertIn("data:image/png;base64,", corsi.html_corsi([c], anteprima_locale=True))

    def test_html_senza_locandina_se_manca_url_pubblico(self):
        with open(self.json, "w", encoding="utf-8") as f:
            json.dump({"corsi": [corso(immagine="locandine/corso uno.png")]}, f)
        c = corsi.carica_corsi("pocus", oggi=OGGI, percorso=self.json)[0]      # senza base_url
        self.assertNotIn("<img", corsi.html_corsi([c]))

    def test_verifica_segnala_immagine_mancante(self):
        with open(self.json, "w", encoding="utf-8") as f:
            json.dump({"corsi": [corso(immagine="locandine/manca.png")]}, f)
        self.assertIn("non trovato", " ".join(corsi.verifica(self.json)))
        with open(self.json, "w", encoding="utf-8") as f:
            json.dump({"corsi": [corso(immagine="locandine/corso uno.png")]}, f)
        self.assertEqual(corsi.verifica(self.json), [])

    def test_telegram_foto_con_didascalia(self):
        c = self.carica(immagine="locandine/corso uno.png")
        foto, testi = [], []
        ok, tot = corsi.invia_telegram("t", "c", [c], lambda t: testi.append(t) or True,
                                       lambda tok, ch, url, cap: foto.append((url, cap)) or True, pausa=0)
        self.assertEqual((ok, tot), (1, 1))
        self.assertEqual(testi, [])
        self.assertEqual(foto[0][0], c["immagine_url"])
        self.assertIn("Corso POCUS", foto[0][1])

    def test_telegram_didascalia_lunga_foto_poi_testo(self):
        c = self.carica(immagine="locandine/corso uno.png", descrizione="x" * 400, luogo="L" * 150,
                        posti="P" * 80, ora="O" * 60, titolo="T" * 160)
        foto, testi = [], []
        with patch.object(corsi, "CAPTION_TELEGRAM", 50):
            ok, _ = corsi.invia_telegram("t", "c", [c], lambda t: testi.append(t) or True,
                                         lambda tok, ch, url, cap: foto.append(cap) or True, pausa=0)
        self.assertEqual(ok, 1)
        self.assertEqual(foto, [""])
        self.assertEqual(len(testi), 1)

    def test_telegram_foto_fallita_ripiega_sul_testo(self):
        c = self.carica(immagine="locandine/corso uno.png")
        testi = []
        ok, _ = corsi.invia_telegram("t", "c", [c], lambda t: testi.append(t) or True,
                                     lambda *a: False, pausa=0)
        self.assertEqual((ok, len(testi)), (1, 1))

    def test_telegram_senza_immagine_solo_testo(self):
        c = self.carica()
        testi = []
        ok, _ = corsi.invia_telegram("t", "c", [c], lambda t: testi.append(t) or True,
                                     lambda *a: self.fail("nessuna foto attesa"), pausa=0)
        self.assertEqual((ok, len(testi)), (1, 1))


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
        t = corsi.testo_telegram_corso(c)
        self.assertIn("A &amp; B &lt;i&gt;", t)
        self.assertLessEqual(len(t), 4096)

    def test_facebook_testo(self):
        t = corsi.testo_facebook(self.c(luogo="Torino", link="https://esempio.it"))
        self.assertIn("sabato 14 novembre 2026", t)
        self.assertIn("Torino", t)
        self.assertIn("https://esempio.it", t)


if __name__ == "__main__":
    unittest.main()
