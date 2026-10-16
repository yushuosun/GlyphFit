"""Compatibility alias for ki_ocr.glyph_est5."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.glyph_est5")
