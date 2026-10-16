"""Compatibility alias for swocr.best_effort."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.best_effort")
