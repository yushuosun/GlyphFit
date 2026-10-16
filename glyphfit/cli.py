"""Compatibility alias for swocr.cli."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("swocr.cli")
