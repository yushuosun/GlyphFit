"""Compatibility alias for swocr.diagnostics."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.diagnostics")
