"""Compatibility alias for ki_ocr.pipeline."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("ki_ocr.pipeline")
