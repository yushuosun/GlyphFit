"""Compatibility alias for swocr.menu."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.menu")
