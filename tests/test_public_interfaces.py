import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ki_ocr.api import source_render_scale
from ki_ocr.diagnostics import verify_predictions
from ki_ocr import native_sourcecap

TEST_ROOT = Path(__file__).resolve().parents[2]


class InterfaceTests(unittest.TestCase):
    def test_a_matches_frozen_renderer_scale(self):
        class Page:
            def get_size(self): return (612, 792)
        original = native_sourcecap.SOURCE_RASTER_WH
        try:
            for wh in [(600, 800), (2400, 3200), (100, 3000)]:
                native_sourcecap.SOURCE_RASTER_WH = wh
                expected = native_sourcecap.capped_scale(Page(), min(200 / 72, 3500 / 792))
                self.assertEqual(source_render_scale((612, 792), wh), expected)
        finally:
            native_sourcecap.SOURCE_RASTER_WH = original

    def test_a_rejects_invalid_dimensions(self):
        for wh in [(0, 20), (-2, 20), (float("nan"), 20)]:
            with self.assertRaises(ValueError): source_render_scale((612, 792), wh)

    def test_prediction_verification_detects_mutation_missing_and_extra(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
            p = Path(d); raw = b"<table><tr><td>kept</td></tr></table>\n"
            (p / "one.md").write_bytes(raw)
            manifest = p / "manifest.json"
            manifest.write_text(json.dumps({"count": 1, "files": [{"filename": "one.md", "bytes": len(raw), "SHA256": hashlib.sha256(raw).hexdigest()}]}))
            self.assertEqual(verify_predictions(p, manifest)["status"], "MATCH")
            (p / "one.md").write_bytes(raw + b"changed")
            self.assertEqual(verify_predictions(p, manifest)["failures"][0]["reason"], "BYTES_OR_SHA_DIFFER")
            (p / "one.md").unlink()
            self.assertEqual(verify_predictions(p, manifest)["failures"][0]["reason"], "MISSING")
            (p / "extra.md").write_text("extra")
            self.assertEqual(verify_predictions(p, manifest)["extra_MD"], ["extra.md"])

    def test_prediction_verification_rejects_path_escape(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as d:
            p = Path(d); manifest = p / "manifest.json"
            manifest.write_text(json.dumps({"count": 1, "files": [{"filename": "../outside.md", "bytes": 0, "SHA256": "x"}]}))
            with self.assertRaises(ValueError): verify_predictions(p, manifest)
