"""Compatibility alias for ki_ocr.execution."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.execution")
