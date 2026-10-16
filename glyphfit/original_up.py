"""Compatibility alias for ki_ocr.original_up."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.original_up")
