"""Compatibility alias for swocr.tele_canonical."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.tele_canonical")
