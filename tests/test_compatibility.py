import importlib
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityTests(unittest.TestCase):
    def test_legacy_modules_share_the_actual_implementation(self):
        for name in ("api", "cli", "pipeline", "diagnostics", "execution", "menu",
                     "best_effort", "native_sourcecap", "original_up", "tele_canonical"):
            self.assertIs(importlib.import_module("glyphfit." + name),
                          importlib.import_module("swocr." + name))

    def test_new_and_legacy_CLI_help(self):
        for module in ("swocr", "glyphfit"):
            for args in (["--help"], ["prepare", "--help"], ["run-standalone", "--help"]):
                result = subprocess.run([sys.executable, "-m", module, *args],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
