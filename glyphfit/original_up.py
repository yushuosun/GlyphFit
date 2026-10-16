"""Compatibility alias for swocr.original_up."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.original_up")
