"""Build the deterministic R5 evaluation attachment from tracked public inputs."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'swocr-repro-r5'
BASE = 'https://github.com/yushuosun/SWOCR'


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8')


def record(data):
    return {'bytes': len(data), 'SHA256': hashlib.sha256(data).hexdigest()}


def build():
    members = {p.relative_to(ROOT/'artifacts/evaluation').as_posix(): p.read_bytes()
               for p in (ROOT/'artifacts/evaluation').rglob('*') if p.is_file()}
    members['configs/swocr_ab.json'] = (ROOT/'configs/swocr_ab.json').read_bytes()
    members['history/original_inference_config.json'] = (ROOT/'metadata/history/original_inference_config.json').read_bytes()
    members['history/README.md'] = b'# Original configuration\n\nThis file preserves the preparation-time configuration bytes. Use configs/swocr_ab.json for the release runtime settings and metadata/RELEASE_STATUS.json for completion status. The equivalence record verifies that all computational values match.\n'
    mapping = json.loads((ROOT/'metadata/configuration_equivalence.json').read_bytes())
    mapping['original_path'] = 'history/original_inference_config.json'
    members['metadata/configuration_equivalence.json'] = encode(mapping)
    status = json.loads((ROOT/'metadata/RELEASE_STATUS.json').read_bytes())
    status.update(completion_record='evidence/run_completion.json', results='results/RESULTS.json')
    members['metadata/RELEASE_STATUS.json'] = encode(status)
    for p in (ROOT/'artifacts/evidence').glob('*.json'):
        members['evidence/'+p.name] = p.read_bytes()
    for name in ('results/recomputed_statistics.json', 'scripts/recompute_statistics.py', 'LICENSE'):
        members[name] = (ROOT/name).read_bytes()
    evidence = (ROOT/'docs/EVIDENCE.md').read_text(encoding='utf-8')
    evidence = evidence.replace('../artifacts/evidence/', 'evidence/').replace('../results/', 'results/').replace('../scripts/', 'scripts/').replace('../configs/', 'configs/').replace('../metadata/', 'metadata/').replace('`metadata/history/`', '`history/`')
    members['EVIDENCE.md'] = evidence.encode('utf-8')
    rights = (ROOT/'THIRD_PARTY.md').read_text(encoding='utf-8').replace('(docs/DEPENDENCIES.md)', f'({BASE}/blob/{TAG}/docs/DEPENDENCIES.md)')
    members['THIRD_PARTY.md'] = rights.encode('utf-8')
    members['REPRODUCTION.md'] = f'''# Inference configuration and completion

The release runtime configuration is `configs/swocr_ab.json`. Its mapping to the original run configuration is recorded in `metadata/configuration_equivalence.json`; all computational values are exactly equal. The original bytes are preserved in `history/original_inference_config.json`. Completed page counts and source hashes are in `metadata/RELEASE_STATUS.json` and `evidence/run_completion.json`.

Both arms use the same model, processor and full generation profiles, with a requested output cap and context window of 32768. The 8192-token reserve is input admission headroom. The original-input control uses these settings; it is distinct from upstream author defaults. All thresholds, scale candidates, rendering rules, prompts and dependency hashes are recorded in the configuration.

To rerun inference, use the [R5 source checkout]({BASE}/tree/{TAG}) and its [inference guide]({BASE}/blob/{TAG}/docs/REPRODUCE.md) and [dependencies]({BASE}/blob/{TAG}/docs/DEPENDENCIES.md). This attachment supplies evaluation inputs and numerical evidence, not the external model or GPU dependencies.
'''.encode('utf-8')
    members['README.md'] = f'''# SWOCR evaluation package R5

This package contains the scoring configuration, recorded metrics, prediction manifests and paired evidence for all 1,651 pages of OmniDocBench v1.6_full. The [release index]({BASE}/blob/{TAG}/docs/RELEASE.md) links the matching code and both prediction archives. All project links use the same release tag, `{TAG}`. The prediction archives contain Markdown only; referenced image crops are not included.

SWOCR Overall is **98.40951176937257**; the same-generation original-input control obtains **97.61704895861511**. Exact component metrics and denominators are in `results/RESULTS.json`. Overall is a percentage; component values in that JSON are ratios. See [evidence](EVIDENCE.md) for token accounting and bootstrap scope, and [configuration details](REPRODUCTION.md) for inference settings.

## Evaluate predictions

Download [SWOCR predictions]({BASE}/raw/{TAG}/artifacts/submission/SWOCR_OmniDocBench_v1.6_predictions.zip) beside this extracted package. From the package directory:

```bash
mkdir -p predictions/GLYPHFIT_FULL
python -m zipfile -e ../SWOCR_OmniDocBench_v1.6_predictions.zip predictions/GLYPHFIT_FULL
```

Obtain the [official evaluator](https://github.com/opendatalab/OmniDocBench) at `f133a71e9e91c3621c7ce8994200a7b394a06eb3` and install its CDM/TeX/ImageMagick/Ghostscript dependencies. Obtain GT separately; the expected SHA256 is `a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`.

In `configs/end2end.yaml`, set the ground-truth and prediction data paths to absolute paths. Retain quick_match, timeouts 420/300 seconds, fallback span 10, order penalty 0.1 and 8 match/CDM/TEDS workers. Run from the evaluator checkout:

```bash
cd /absolute/path/OmniDocBench
git checkout f133a71e9e91c3621c7ce8994200a7b394a06eb3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python pdf_validation.py --config /absolute/path/extracted-package/configs/end2end.yaml
```

For the control, extract the [control ZIP]({BASE}/raw/{TAG}/artifacts/submission/SWOCR_same_generation_baseline_predictions.zip) separately and use its directory in a copy of the YAML. Both prediction sets can be checked against `evidence/prediction_manifest.json`; the SWOCR CLI additionally accepts `metadata/PREDICTION_FILES_SHA256.json` for SWOCR predictions.

## Recompute numerical summaries

From this extracted package, using Python 3.11 or newer:

```bash
python -m pip install numpy==2.4.5
python scripts/recompute_statistics.py --evidence evidence --output outputs/recomputed_statistics.json
```

This reconstructs statistics from recorded per-page values; the official evaluator above computes scores from GT and predictions. `FILES_SHA256.json` verifies package members. Source code and original documentation use the [MIT License](LICENSE); [third-party document rights](THIRD_PARTY.md) remain separate.
'''.encode('utf-8')
    manifest = {'schema': 'SWOCR_EVALUATION_RELEASE_V3', 'release_version': 'R5', 'release_tag': TAG,
                'repository': BASE, 'release_index': f'{BASE}/blob/{TAG}/docs/RELEASE.md',
                'dataset_pages': 1651, 'method_name_mapping': 'GlyphFit / GLYPHFIT_FULL identifiers refer to SWOCR.',
                'release_configuration': {'path': 'configs/swocr_ab.json', **record(members['configs/swocr_ab.json'])},
                'original_run_configuration': {'path': 'metadata/history/original_inference_config.json', **record(members['history/original_inference_config.json'])},
                'configuration_equivalence': 'metadata/configuration_equivalence.json',
                'new_model_inference': False, 'new_official_scoring': False}
    for key, filename in [('prediction_attachment', 'SWOCR_OmniDocBench_v1.6_predictions.zip'),
                          ('baseline_prediction_attachment', 'SWOCR_same_generation_baseline_predictions.zip')]:
        manifest[key] = {'filename': filename, 'MD_count': 1651, **record((ROOT/'artifacts/submission'/filename).read_bytes())}
    internal_manifest = dict(manifest, original_run_configuration={**manifest['original_run_configuration'], 'path': 'history/original_inference_config.json'})
    members['RELEASE_MANIFEST.json'] = encode(internal_manifest)
    members['FILES_SHA256.json'] = encode({'manifest_self_excluded': True, 'files': {n: record(b) for n,b in sorted(members.items())}})
    target = ROOT/'artifacts/submission/SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip'
    with zipfile.ZipFile(target, 'w') as z:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 16, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data, compresslevel=9)
    manifest['evaluation_attachment'] = {'filename': target.name, 'members': len(members), **record(target.read_bytes())}
    (ROOT/'artifacts/submission/SWOCR_RELEASE_MANIFEST_R5.json').write_bytes(encode(manifest))
    print(json.dumps(manifest['evaluation_attachment'], indent=2))


if __name__ == '__main__':
    build()
