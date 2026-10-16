"""Compatibility alias for ki_ocr.native_sourcecap."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.native_sourcecap")
