"""Archivio della corsa: gli articoli scelti finiscono in un JSON per ripubblica.py."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import newsletter_NIV as nl  # noqa: E402


class Archivio(unittest.TestCase):
    def test_scrive_articoli_senza_date_python(self):
        wl = {"settimana": 7, "anno": 2026, "giorno": 1, "mese": "Febbraio"}
        art = [{"pmid": "1", "titolo": "T", "sintesi_it": "S", "pubdate_dt": datetime.now(timezone.utc)}]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(nl.cfg, "ARCHIVIO_DIR", d):
            p = nl.salva_archivio(wl, art)
            doc = json.load(open(p, encoding="utf-8"))
        self.assertTrue(p.endswith("digest-s07-2026.json"))
        self.assertEqual(doc["wl"], wl)
        self.assertEqual(doc["pubblicati"], [{"pmid": "1", "titolo": "T", "sintesi_it": "S"}])
        self.assertIn("dry_run", doc)

    def test_mai_bloccante(self):
        with mock.patch.object(nl.cfg, "ARCHIVIO_DIR", "/proc/vietato/x"):
            self.assertIsNone(nl.salva_archivio({"settimana": 1, "anno": 2026}, []))

    def test_spento(self):
        with mock.patch.object(nl.cfg, "ARCHIVIO_ABILITATO", False):
            self.assertIsNone(nl.salva_archivio({"settimana": 1, "anno": 2026}, []))


if __name__ == "__main__":
    unittest.main()
