import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ki_ocr._resources import read_binding, resource_path
from ki_ocr.pipeline import CONFIG

ROOT = Path(__file__).resolve().parents[1]


class ResourceTests(unittest.TestCase):
    def test_frozen_resource_bytes_match(self):
        self.assertEqual(CONFIG.name, "ki_ocr_ab.json")
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(CONFIG.read_bytes(), (ROOT / "configs/ki_ocr_ab.json").read_bytes())
        for name, digest in cfg["private_runtime_pins"].items():
            self.assertEqual(hashlib.sha256(resource_path("runtime_helpers") .joinpath(name).read_bytes()).hexdigest(), digest)
        self.assertEqual(resource_path("inference_ab.py").read_bytes(), (ROOT / "inference_ab.py").read_bytes())

    def test_binding_paths_are_independent_of_current_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary:
            base = Path(temporary)
            path = base / "binding.json"
            path.write_text(json.dumps({"source": "source", "model": "model",
                "runtime_helpers": "bundled", "execution_policy": "managed"}), encoding="utf-8")
            binding = read_binding(path)
            self.assertEqual(Path(binding["source"]), base / "source")
            self.assertEqual(Path(binding["model"]), base / "model")
            self.assertEqual(Path(binding["runtime_helpers"]), resource_path("runtime_helpers"))
