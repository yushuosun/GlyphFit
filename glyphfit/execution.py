"""Compatibility alias for swocr.execution."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.execution")
