"""Podcast sul canale Telegram: video, ripiego sull'MP3, limiti, mai eccezioni."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import telegram_podcast as tp  # noqa: E402


class Invio(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.mp4 = os.path.join(self.d, "podcast.mp4")
        self.mp3 = os.path.join(self.d, "podcast.mp3")
        for f in (self.mp4, self.mp3):
            with open(f, "wb") as fh:
                fh.write(b"x" * 100)
        self.chiamate = []

    def finto(self, esiti):
        def f(token, metodo, campi, campo_file, percorso, tipo):
            self.chiamate.append((metodo, campi, campo_file, os.path.basename(percorso)))
            e = esiti.pop(0)
            if isinstance(e, Exception):
                raise e
            return e
        return f

    def test_prima_il_video_in_streaming(self):
        with mock.patch.object(tp, "_invia", self.finto([7])):
            self.assertEqual(tp.invia_podcast({"mp4": self.mp4, "mp3": self.mp3}, "<b>ciao</b>", token="T", chat_id="C"), 7)
        metodo, campi, campo, nome = self.chiamate[0]
        self.assertEqual((metodo, campo, nome), ("sendVideo", "video", "podcast.mp4"))
        self.assertEqual(campi["supports_streaming"], "true")
        self.assertEqual(campi["parse_mode"], "HTML")

    def test_video_rifiutato_allora_mp3(self):
        with mock.patch.object(tp, "_invia", self.finto([RuntimeError("HTTP 413 Request Entity Too Large"), 9])):
            self.assertEqual(tp.invia_podcast({"mp4": self.mp4, "mp3": self.mp3}, "x", titolo="POCUS 47/2026",
                                              token="T", chat_id="C"), 9)
        metodo, campi, _, _ = self.chiamate[1]
        self.assertEqual(metodo, "sendAudio")
        self.assertEqual(campi["title"], "POCUS 47/2026")

    def test_video_troppo_grande_non_si_prova(self):
        with mock.patch.object(tp, "LIMITE_MB", 0.00005), mock.patch.object(tp, "_invia", self.finto([1])):
            with self.assertLogs("telegram_podcast", "ERROR"):
                self.assertIsNone(tp.invia_podcast({"mp4": self.mp4, "mp3": self.mp3}, "x", token="T", chat_id="C"))
        self.assertEqual(self.chiamate, [])

    def test_tutto_fallito_e_un_errore_non_un_eccezione(self):
        with mock.patch.object(tp, "_invia", self.finto([RuntimeError("a"), RuntimeError("b")])):
            with self.assertLogs("telegram_podcast", "ERROR") as lg:
                self.assertIsNone(tp.invia_podcast({"mp4": self.mp4, "mp3": self.mp3}, "x", token="T", chat_id="C"))
        self.assertIn("podcast non inviato", lg.output[-1])

    def test_senza_chiavi_o_senza_podcast_non_fa_nulla(self):
        with mock.patch.object(tp, "_invia") as inv:
            self.assertIsNone(tp.invia_podcast({"mp4": self.mp4}, "x", token="", chat_id="C"))
            self.assertIsNone(tp.invia_podcast(None, "x", token="T", chat_id="C"))
        inv.assert_not_called()

    def test_didascalia_entro_il_limite(self):
        with mock.patch.object(tp, "_invia", self.finto([1])):
            tp.invia_podcast({"mp4": self.mp4}, "a" * 3000, token="T", chat_id="C")
        self.assertEqual(len(self.chiamate[0][1]["caption"]), tp.DIDASCALIA_MAX)

    def test_multipart_contiene_campi_e_file(self):
        corpo, tipo = tp._multipart({"chat_id": "C"}, "video", self.mp4, "video/mp4")
        confine = tipo.split("boundary=")[1]
        self.assertIn(b'name="chat_id"\r\n\r\nC\r\n', corpo)
        self.assertIn(b'name="video"; filename="podcast.mp4"', corpo)
        self.assertTrue(corpo.endswith(f"--{confine}--\r\n".encode()))


if __name__ == "__main__":
    unittest.main()
