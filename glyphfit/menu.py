"""Compatibility alias for ki_ocr.menu."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.menu")
