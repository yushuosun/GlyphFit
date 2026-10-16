"""Compatibility alias for ki_ocr.tele_canonical."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.tele_canonical")
