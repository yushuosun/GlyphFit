"""Compatibility alias for swocr.api."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.api")
