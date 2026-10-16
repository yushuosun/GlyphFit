"""Compatibility alias for ki_ocr.api."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.api")
