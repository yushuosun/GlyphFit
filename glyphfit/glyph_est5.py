"""Compatibility alias for swocr.glyph_est5."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.glyph_est5")
