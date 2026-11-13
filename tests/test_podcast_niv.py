"""Podcast NIV: allegato alla mail degli iscritti, mai bloccante."""
import email
import os
import sys
import tempfile
import unittest
from unittest import mock

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)
import config as cfg  # noqa: E402
import newsletter_NIV as nl  # noqa: E402

ART = [{"pmid": "1", "titolo": "T", "titolo_it": "Titolo", "rivista": "Chest", "sintesi_it": "S",
        "rilevanza": "R", "limite": "L", "origine": "niv", "link": "https://pubmed.ncbi.nlm.nih.gov/1/", "data": "2026-11-01", "url": "https://pubmed.ncbi.nlm.nih.gov/1/", "autori": "Rossi M", "abstract": "A"}]
STATO = {"n_niv": 1, "n_em": 0, "filtro_ko": False}


class Config(unittest.TestCase):
    def test_blocco_podcast(self):
        self.assertEqual(cfg.PODCAST_TITOLO, "NIV Weekly Digest")
        self.assertEqual(cfg.PODCAST_CORSI, "niv")
        self.assertIn("ventilazione non invasiva", cfg.PODCAST_INTRO)
        self.assertIn("{blocchi}", cfg.PODCAST_PROMPT)
        self.assertFalse(cfg.PODCAST_RIPIEGO_CHATTERBOX)

    def test_podcast_py_usa_il_modulo_niv(self):
        import podcast
        self.assertIs(podcast.nr, nl)
        testo, n_invito, n_saluti = podcast.chiusura_podcast(True)
        self.assertTrue(testo.endswith("Alla prossima."))


class Mail(unittest.TestCase):
    def _spedita(self, media):
        with mock.patch.object(nl.smtplib, "SMTP_SSL") as smtp:
            ok = nl.invia_email("Oggetto", "<p>ciao</p>", ["a@example.org"], media=media)
        self.assertTrue(ok)
        return smtp.return_value.__enter__.return_value.send_message.call_args[0][0]

    def test_senza_podcast_come_prima(self):
        msg = self._spedita(None)
        self.assertEqual(msg.get_content_type(), "multipart/alternative")

    def test_video_allegato(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "podcast-s46-2026.mp4")
            with open(f, "wb") as fh:
                fh.write(b"\x00\x00\x00\x18ftypmp42" + b"x" * 100)
            msg = email.message_from_bytes(self._spedita(f).as_bytes())
        self.assertEqual(msg.get_content_type(), "multipart/mixed")
        parti = msg.get_payload()
        self.assertEqual(parti[0].get_content_type(), "multipart/alternative")
        self.assertEqual(parti[1].get_content_type(), "video/mp4")
        self.assertEqual(parti[1].get_filename(), "podcast-s46-2026.mp4")
        self.assertEqual(len(parti[1].get_payload(decode=True)), 112)

    def test_file_mancante_la_mail_parte_senza(self):
        msg = self._spedita("/non/esiste.mp4")
        self.assertEqual(msg.get_content_type(), "multipart/alternative")

    def test_riga_nella_mail_solo_con_il_podcast(self):
        self.assertNotIn(">Podcast<", nl.build_html(ART, STATO))
        h = nl.build_html(ART, STATO, podcast_allegato="podcast/podcast-s46-2026.mp4")
        self.assertIn(">Podcast<", h)
        self.assertIn("il video è in allegato", h)
        self.assertIn("podcast-s46-2026.mp4", h)


class Allegato(unittest.TestCase):
    def test_preferisce_il_video_e_rispetta_il_limite(self):
        with tempfile.TemporaryDirectory() as d:
            mp4, mp3 = os.path.join(d, "a.mp4"), os.path.join(d, "a.mp3")
            for f in (mp4, mp3):
                with open(f, "wb") as fh:
                    fh.write(b"x" * 2000)
            self.assertEqual(nl.allegato_podcast({"mp4": mp4, "mp3": mp3}), mp4)
            with mock.patch.object(cfg, "MAIL_MAX_MB", 0.001):
                self.assertIsNone(nl.allegato_podcast({"mp4": mp4, "mp3": mp3}))
            self.assertIsNone(nl.allegato_podcast(None))


class Genera(unittest.TestCase):
    WL = {"settimana": 46, "anno": 2026}

    def test_spento_o_senza_chiave_niente_podcast(self):
        with mock.patch.object(cfg, "PODCAST_ABILITATO", False):
            self.assertIsNone(nl.genera_podcast(ART, self.WL))
        with mock.patch.object(cfg, "GEMINI_API_KEY", ""), mock.patch.object(nl.subprocess, "run") as run:
            self.assertIsNone(nl.genera_podcast(ART, self.WL))
            run.assert_not_called()

    def test_esito_ok_restituisce_i_file_e_scrive_l_archivio(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            mp4 = os.path.join(d, "p.mp4")
            open(mp4, "wb").close()
            esito, arch = os.path.join(d, "esito.json"), os.path.join(d, "digest.json")

            def finto(*a, **k):
                with open(esito, "w") as f:
                    json.dump({"ok": True, "mp4": mp4, "mp3": os.path.join(d, "manca.mp3")}, f)

            with mock.patch.object(cfg, "PODCAST_DIR", d), mock.patch.object(cfg, "PODCAST_ESITO", esito), \
                    mock.patch.object(cfg, "PODCAST_ARCHIVIO", arch), \
                    mock.patch.object(cfg, "GEMINI_API_KEY", "k"), \
                    mock.patch.object(nl.instagram, "genera_schede", return_value=(["s1.png"], [10])), \
                    mock.patch.object(nl.subprocess, "run", side_effect=finto):
                self.assertEqual(nl.genera_podcast(ART, self.WL), {"mp4": mp4})
            with open(arch, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(doc["settimana"], 46)
            self.assertEqual(doc["pubblicati"][0]["pmid"], "1")
            self.assertEqual(len(doc["immagini"]), 1)

    def test_errore_non_blocca(self):
        with mock.patch.object(cfg, "GEMINI_API_KEY", "k"), \
                mock.patch.object(nl.instagram, "genera_schede", side_effect=RuntimeError("boom")):
            self.assertIsNone(nl.genera_podcast(ART, self.WL))


class SoloPodcast(unittest.TestCase):
    """SOLO_PODCAST: la mail col podcast va solo a AVVISI_EMAIL (o GMAIL_USER); niente iscritti,
    Telegram o Instagram."""

    def _corsa(self, media, avvisi="io@example.org"):
        art = dict(ART[0], sintesi_it="Sintesi", bibliografia_verificata=True)
        with mock.patch.object(cfg, "SOLO_PODCAST", True), mock.patch.object(cfg, "DRY_RUN", False), \
                mock.patch.object(cfg, "SOLO_PODCAST_A", avvisi), \
                mock.patch.object(cfg, "GMAIL_USER", "casella@example.org"), \
                mock.patch.object(cfg, "valida_config"), \
                mock.patch.object(nl, "carica_destinatari") as iscritti, \
                mock.patch.object(nl, "raccogli_candidati", return_value=[art] * 9), \
                mock.patch.object(nl, "componi_selezione", return_value=([art], dict(STATO))), \
                mock.patch.object(nl, "sintetizza_articoli", side_effect=lambda x: x), \
                mock.patch.object(nl, "controlla_sintesi", return_value={"approvato": True, "verifica_ai": "pass"}), \
                mock.patch.object(cfg, "MINIMO_ARTICOLI", 1), \
                mock.patch.object(nl.avvisi, "carica_corsi", return_value=[]), \
                mock.patch.object(nl, "genera_podcast", return_value={"mp4": "p.mp4"} if media else None), \
                mock.patch.object(nl, "allegato_podcast", return_value=media), \
                mock.patch.object(nl, "invia_email", return_value=True) as mail, \
                mock.patch.object(nl, "invia_telegram") as tg, \
                mock.patch.object(nl, "pubblica_instagram") as ig:
            ok = nl._main()
        return ok, iscritti, mail, tg, ig

    def test_mail_solo_a_te_niente_altro(self):
        ok, iscritti, mail, tg, ig = self._corsa("podcast/p.mp4")
        self.assertTrue(ok)
        iscritti.assert_not_called()
        tg.assert_not_called()
        ig.assert_not_called()
        oggetto, _, destinatari = mail.call_args[0]
        self.assertTrue(oggetto.startswith("[Prova podcast]"))
        self.assertEqual(destinatari, ["io@example.org"])
        self.assertEqual(mail.call_args[1]["media"], "podcast/p.mp4")

    def test_senza_avvisi_email_va_alla_casella(self):
        _, _, mail, _, _ = self._corsa("podcast/p.mp4", avvisi="")
        self.assertEqual(mail.call_args[0][2], ["casella@example.org"])

    def test_podcast_mancato_nessuna_mail(self):
        ok, _, mail, tg, _ = self._corsa(None)
        self.assertFalse(ok)
        mail.assert_not_called()
        tg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
