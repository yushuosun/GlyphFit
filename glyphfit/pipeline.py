"""Compatibility alias for swocr.pipeline."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.pipeline")
