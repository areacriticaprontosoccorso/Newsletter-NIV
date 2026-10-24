"""Integrazione degli avvisi corsi in newsletter_NIV: mail e Telegram."""
import unittest
from datetime import date
from unittest.mock import patch

import newsletter_NIV as niv


def un_corso():
    return {"titolo": "Corso base di ecografia", "inizio": date(2026, 11, 14),
            "fine": date(2026, 11, 15), "ora": "9:00–17:00", "luogo": "Torino",
            "descrizione": "Parte pratica.", "posti": "", "link": "https://esempio.it/x",
            "iscrizioni_fino": None}


def un_articolo():
    return {"pmid": "1", "titolo": "NIV study", "autori": "A B", "rivista": "Respir Care",
            "nlmta": "Respir Care", "data": "2026 Oct 14", "abstract": "x" * 300, "doi": "",
            "url": "https://pubmed.ncbi.nlm.nih.gov/1/", "tipo": "conferma", "origine": "niv",
            "categoria": "non-invasiva", "sintesi_it": "Sintesi.", "rilevanza": "Rilevante.",
            "limite": "Limite.", "pubtypes": [], "pubdate_dt": None}


STATO = {"n_niv": 1, "n_em": 0, "filtro_ko": False}


class MailTest(unittest.TestCase):
    def test_avviso_in_cima_prima_degli_articoli(self):
        h = niv.build_html([un_articolo()], STATO, [un_corso()])
        self.assertIn("Corso base di ecografia", h)
        self.assertLess(h.index("Corso base di ecografia"), h.index("NIV study"))

    def test_nessun_avviso_senza_corsi(self):
        self.assertNotIn("Corso in programma", niv.build_html([un_articolo()], STATO))
        self.assertNotIn("Corso in programma", niv.build_html([un_articolo()], STATO, []))


class TelegramTest(unittest.TestCase):
    def invia(self, corsi):
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}), \
                patch.object(niv, "telegram_send_message", return_value=True) as m, \
                patch.object(niv.time, "sleep"):
            ok = niv.invia_telegram([un_articolo()], STATO, corsi)
        return ok, [c.args[2] for c in m.call_args_list]

    def test_messaggio_corsi_dopo_intestazione(self):
        ok, msgs = self.invia([un_corso()])
        self.assertTrue(ok)
        self.assertEqual(len(msgs), 4)
        self.assertIn("Corso base di ecografia", msgs[1])

    def test_senza_corsi_come_prima(self):
        ok, msgs = self.invia([])
        self.assertTrue(ok)
        self.assertEqual(len(msgs), 3)


if __name__ == "__main__":
    unittest.main()
