"""Maintain the source inventory after staging intended changes with git add."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'metadata/SOURCE_PAYLOAD_MANIFEST.json'

if __name__ == '__main__':
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = {}
    for name in sorted(n for n in names if n and n != TARGET):
        data = (ROOT/name).read_bytes()
        files[name] = {'bytes': len(data), 'SHA256': hashlib.sha256(data).hexdigest()}
    payload = {'schema': 'KI_OCR_CHECKOUT_FILE_MANIFEST_V1', 'manifest_self_excluded': True,
               'scope': 'Files listed in the Git index when generated; local build/cache/output files are excluded. The original run configuration is under metadata/history.',
               'files': files}
    (ROOT/TARGET).write_bytes((json.dumps(payload, indent=2)+'\n').encode('utf-8'))
    print('Manifest files:', len(files))
