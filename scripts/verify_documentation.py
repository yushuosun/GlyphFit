"""Check local document links and ensure project links stay within one release."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
import posixpath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'swocr-repro-r5'
LINK = re.compile(r'\]\(([^)]+)\)')


def verify_text(name, text, exists, package=False):
    count = 0
    for url in LINK.findall(text):
        parts = urlparse(url)
        if parts.scheme:
            if parts.netloc == 'github.com' and parts.path.startswith('/yushuosun/SWOCR/'):
                route = parts.path.split('/', 5)
                if len(route) >= 5 and route[3] in ('tree', 'blob', 'raw'):
                    assert route[4] == TAG, (name, 'Outdated release link', url)
                    if len(route) == 6:
                        assert (ROOT/unquote(route[5])).exists(), (name, url)
        elif parts.path:
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parts.path)))
            assert exists(target), (name, 'Missing relative target', target)
        count += 1
    for checkout in re.findall(r'^git checkout (\S+)', text, re.M):
        if name.startswith('README') and not package:
            assert checkout == TAG, (name, 'README checkout points to another release', checkout)
    return count


if __name__ == '__main__':
    count = 0
    for path in sorted(ROOT.rglob('*.md')):
        relative = path.relative_to(ROOT).as_posix()
        if any(part in ('build', 'dist', 'outputs', '.git') or part.startswith('.venv') for part in path.relative_to(ROOT).parts):
            continue
        count += verify_text(relative, path.read_text(encoding='utf-8'), lambda n: (ROOT/n).exists())
    with zipfile.ZipFile(ROOT/'artifacts/submission/SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip') as z:
        names = set(z.namelist())
        for name in names:
            if name.endswith('.md'):
                count += verify_text(name, z.read(name).decode('utf-8'), lambda n: n in names, package=True)
    print(json.dumps({'status': 'MATCH', 'release_tag': TAG, 'document_links_checked': count}))
