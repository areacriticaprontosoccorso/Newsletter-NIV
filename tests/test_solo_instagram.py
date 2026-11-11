"""Prova dell'invio su Instagram (SOLO_INSTAGRAM): solo Instagram, niente credenziali mail, didascalia normale."""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402
import instagram as ig  # noqa: E402

MODULO = next(m for m in ("newsletter_pocus", "newsletter_NIV") if os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), m + ".py")))
nl = importlib.import_module(MODULO)

ARTICOLI = [{"titolo": "T", "titolo_it": "Titolo di prova", "rivista": "J", "data": "2026", "pmid": "1",
             "rilevanza": "Conta.", "origine": "niv"}]
WL = {"settimana": "45", "anno": "2026"}


def chiama(*a, **k):
    # POCUS vuole (articoli, immagini, wl), NIV (articoli, wl)
    return nl.pubblica_instagram(ARTICOLI, [], WL, **k) if MODULO == "newsletter_pocus" \
        else nl.pubblica_instagram(ARTICOLI, WL, **k)


class SoloInstagram(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.salvati = {k: getattr(cfg, k) for k in ("SOLO_INSTAGRAM", "IG_DIR", "IG_REEL_SCHEDE")}
        cfg.IG_DIR = os.path.join(self.d, "instagram")
        cfg.IG_REEL_SCHEDE = False

    def tearDown(self):
        for k, v in self.salvati.items():
            setattr(cfg, k, v)
        shutil.rmtree(self.d, ignore_errors=True)

    def test_flag_letto_dall_ambiente(self):
        for valore, atteso in (("1", True), ("true", True), ("", False), ("0", False)):
            with mock.patch.dict(os.environ, {"SOLO_INSTAGRAM": valore}):
                importlib.reload(cfg)
                self.assertEqual(cfg.SOLO_INSTAGRAM, atteso, valore)
        importlib.reload(cfg)

    def test_senza_credenziali_mail(self):
        with mock.patch.object(cfg, "ANTHROPIC_API_KEY", "k"), mock.patch.object(cfg, "GMAIL_USER", ""), \
             mock.patch.object(cfg, "GMAIL_APP_PASSWORD", ""), mock.patch.object(cfg, "DRY_RUN", False), \
             mock.patch.object(cfg, "SOLO_INSTAGRAM", True):
            cfg.valida_config()                       # non solleva
        with mock.patch.object(cfg, "ANTHROPIC_API_KEY", "k"), mock.patch.object(cfg, "GMAIL_USER", ""), \
             mock.patch.object(cfg, "GMAIL_APP_PASSWORD", ""), mock.patch.object(cfg, "DRY_RUN", False), \
             mock.patch.object(cfg, "SOLO_INSTAGRAM", False):
            with self.assertRaises(RuntimeError):
                cfg.valida_config()

    @unittest.skipUnless(shutil.which("ffmpeg"), "serve ffmpeg")
    def test_didascalia_uguale_in_prova_e_no(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("Playwright non installato")
        for prova in (True, False):
            cfg.SOLO_INSTAGRAM = prova
            self.assertEqual(chiama(dry_run=True), "dry-run")
            testo = open(os.path.join(cfg.IG_DIR, "didascalia.txt"), encoding="utf-8").read()
            self.assertEqual(cfg.IG_PREFISSO_PROVA, "")
            self.assertNotIn("PROVA", testo)

    def test_pubblica_solo_su_instagram_e_senza_credenziali_non_fa_nulla(self):
        cfg.SOLO_INSTAGRAM = True
        with mock.patch.object(ig, "pubblica_carosello") as pc:
            with mock.patch.object(cfg, "IG_USER_ID", ""):
                self.assertIsNone(chiama())
        pc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
