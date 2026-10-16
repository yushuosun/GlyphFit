"""Verify release ZIPs, paired prediction bytes and optional checkout manifest (CPU)."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_configuration(root):
    mapping = json.loads((root/'metadata/configuration_equivalence.json').read_bytes())
    original_bytes = (root/mapping['original_path']).read_bytes()
    release_bytes = (root/mapping['release_path']).read_bytes()
    assert sha(original_bytes) == mapping['original_SHA256'] == '98285622f04fc61eb05a5abbce7d3579adcf3b8f8971f033548edef694a94fb6'
    assert sha(release_bytes) == mapping['release_SHA256']
    original, release = json.loads(original_bytes), json.loads(release_bytes)
    descriptive_keys = {'method', 'scientific_freeze_UTC', 'final_score'}
    assert set(mapping['changed_metadata_keys']) == descriptive_keys
    assert {k: v for k, v in original.items() if k not in descriptive_keys} == {k: v for k, v in release.items() if k not in descriptive_keys}, 'Computational configuration changed'
    assert set(original)-set(release) == {'scientific_freeze_UTC', 'final_score'}
    assert not set(release)-set(original)
    return mapping


def verify(root, check_source=True):
    submission = root/'artifacts/submission'
    report = {}
    for filename in ('SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip',):
        with zipfile.ZipFile(submission/filename) as z:
            assert z.testzip() is None
            files = json.loads(z.read('FILES_SHA256.json'))['files']
            assert set(z.namelist()) == set(files) | {'FILES_SHA256.json'}
            for name, expected in files.items():
                data = z.read(name)
                assert len(data) == expected['bytes'] and sha(data) == expected['SHA256'], name
            report['evaluation_members_verified'] = len(files)
    release = json.loads((submission/'SWOCR_RELEASE_MANIFEST_R5.json').read_bytes())
    for key in ('prediction_attachment', 'baseline_prediction_attachment', 'evaluation_attachment'):
        expected = release[key]
        data = (submission/expected['filename']).read_bytes()
        assert len(data) == expected['bytes'] and sha(data) == expected['SHA256'], key
    manifests = json.loads((root/'artifacts/evidence/prediction_manifest.json').read_bytes())['files']
    for arm, filename in [('OFFICIAL_ORIGINAL', 'SWOCR_same_generation_baseline_predictions.zip'),
                          ('GLYPHFIT_FULL', 'SWOCR_OmniDocBench_v1.6_predictions.zip')]:
        rows = [row for row in manifests if row['arm'] == arm]
        with zipfile.ZipFile(submission/filename) as z:
            assert len(rows) == 1651 and len(z.namelist()) == 1651
            assert set(z.namelist()) == {row['filename'] for row in rows}
            for row in rows:
                data = z.read(row['filename'])
                assert len(data) == row['bytes'] and sha(data) == row['SHA256'], row['filename']
        report[arm+'_predictions_verified'] = len(rows)
    frozen = json.loads((root/'results/frozen_full1651.json').read_bytes())
    recomputed = json.loads((root/'results/recomputed_statistics.json').read_bytes())
    for arm, key in [('OFFICIAL_ORIGINAL', 'baseline'), ('GLYPHFIT_FULL', 'GlyphFit')]:
        assert abs(frozen[key]['Overall']-recomputed['Overall_percent'][arm]) < 2e-12
        for metric, value in frozen[key]['components'].items():
            assert abs(value-recomputed['components_raw'][arm][metric]) < 2e-12, metric
    for a, b in zip(frozen['Overall_delta_pp_percentile95'], recomputed['bootstrap']['Overall_delta_pp_percentile95']):
        assert abs(a-b) < 2e-12
    for name, digest in recomputed['input_SHA256'].items():
        assert sha((root/'artifacts/evidence'/name).read_bytes()) == digest
    assert sha((root/'scripts/recompute_statistics.py').read_bytes()) == recomputed['script_SHA256']
    mapping = verify_configuration(root)
    completion = json.loads((root/'artifacts/evidence/run_completion.json').read_bytes())
    assert completion['inference_config_SHA256'] == mapping['original_SHA256']
    assert release['release_configuration']['SHA256'] == mapping['release_SHA256']
    report['computational_configuration'] = 'IDENTICAL_TO_RECORDED_RUN'
    if check_source:
        files = json.loads((root/'metadata/SOURCE_PAYLOAD_MANIFEST.json').read_bytes())['files']
        for name, expected in files.items():
            data = (root/name).read_bytes()
            assert len(data) == expected['bytes'] and sha(data) == expected['SHA256'], name
        report['source_files_verified'] = len(files)
    report['status'] = 'MATCH'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-source', action='store_true', help='For maintainers before regenerating the source manifest')
    args = parser.parse_args()
    print(json.dumps(verify(ROOT, not args.skip_source), indent=2))
