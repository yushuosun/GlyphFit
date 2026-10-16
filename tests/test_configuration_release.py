import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_release import verify_configuration

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationReleaseTests(unittest.TestCase):
    def test_release_preserves_all_computational_settings(self):
        verify_configuration(ROOT)

    def test_gate_change_is_rejected_even_with_updated_file_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ['metadata/configuration_equivalence.json',
                     'metadata/history/original_inference_config.json', 'configs/swocr_ab.json']
            for name in names:
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT/name).read_bytes())
            path = root/'configs/swocr_ab.json'
            config = json.loads(path.read_bytes())
            config['gate']['T_text'] += 1
            path.write_bytes(json.dumps(config).encode())
            path = root/'metadata/configuration_equivalence.json'
            mapping = json.loads(path.read_bytes())
            mapping['release_SHA256'] = hashlib.sha256((root/'configs/swocr_ab.json').read_bytes()).hexdigest()
            path.write_bytes(json.dumps(mapping).encode())
            with self.assertRaisesRegex(AssertionError, 'Computational configuration changed'):
                verify_configuration(root)
