"""Compatibility alias for swocr.native_sourcecap."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.native_sourcecap")
