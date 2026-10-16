"""Compatibility alias for ki_ocr.best_effort."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.best_effort")
