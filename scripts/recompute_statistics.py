"""Reconstruct released page macros, paired bootstrap and content-token totals (CPU)."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('OFFICIAL_ORIGINAL', 'GLYPHFIT_FULL')


def compute(evidence, replicates=20000, seed=20261014):
    metrics_path = evidence / 'per_page_metrics.json'
    tokens_path = evidence / 'per_page_tokens.json'
    metrics = json.loads(metrics_path.read_bytes())
    tokens = json.loads(tokens_path.read_bytes())
    names = sorted(metrics['arms'][ARMS[0]])
    assert len(names) == 1651 and set(names) == set(metrics['arms'][ARMS[1]])
    arrays, means, denominators = {}, {arm: {} for arm in ARMS}, {}
    for metric in metrics['metric_page_denominators']:
        values = np.array([[np.nan if metrics['arms'][arm][name][metric] is None
                            else metrics['arms'][arm][name][metric] for name in names]
                           for arm in ARMS], dtype=np.float64)
        valid = np.isfinite(values)
        assert np.array_equal(valid[0], valid[1]), metric
        denominators[metric] = int(valid[0].sum())
        assert denominators[metric] == metrics['metric_page_denominators'][metric]
        for i, arm in enumerate(ARMS):
            means[arm][metric] = float(np.nanmean(values[i]))
        arrays[metric] = np.nan_to_num(values), valid.astype(np.int64)
    overall = {arm: 100 * ((1 - means[arm]['Text_ED']) + means[arm]['Formula_CDM']
                          + means[arm]['Table_TEDS']) / 3 for arm in ARMS}
    rng = np.random.Generator(np.random.PCG64(seed))
    draws = []
    for start in range(0, replicates, 250):
        index = rng.integers(0, len(names), size=(min(250, replicates-start), len(names)))
        sample = {}
        for metric in ('Text_ED', 'Formula_CDM', 'Table_TEDS'):
            data, valid = arrays[metric]
            denominator = valid[0, index].sum(axis=1)
            assert (denominator > 0).all()
            sample[metric] = data[:, index].sum(axis=2) / denominator[None, :]
        score = 100 * ((1-sample['Text_ED']) + sample['Formula_CDM'] + sample['Table_TEDS']) / 3
        draws.append(score[1]-score[0])
    token_summary = {}
    for arm in ARMS:
        rows = [r for r in tokens['rows'] if r['arm'] == arm]
        assert len(rows) == len(names) and {r['page_id'] for r in rows} == {Path(n).stem for n in names}
        assert all(isinstance(r['content_visual_tokens'], int) and r['content_visual_tokens'] >= 0 for r in rows)
        total = sum(r['content_visual_tokens'] for r in rows)
        token_summary[arm] = {'pages': len(rows), 'content_visual_tokens_total': total,
                              'content_visual_tokens_per_page': total/len(rows),
                              'content_ROIs': sum(r['content_ROI_count'] for r in rows)}
    return {'schema': 'KI_OCR_RECOMPUTED_STATISTICS_V1', 'numpy_version': np.__version__,
            'input_SHA256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (metrics_path, tokens_path)},
            'script_SHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'metric_page_denominators': denominators, 'components_raw': means, 'Overall_percent': overall,
            'Overall_delta_pp': overall[ARMS[1]]-overall[ARMS[0]],
            'bootstrap': {'seed': seed, 'replicates': replicates, 'RNG': 'numpy.PCG64',
                          'unit': 'Paired page; finite-page denominators recomputed for each component in each replicate',
                          'CI': 'Two-sided percentile 95%, linear quantile',
                          'Overall_delta_pp_percentile95': np.quantile(np.concatenate(draws), [.025, .975], method='linear').tolist(),
                          'scope': 'Conditional uncertainty for these evaluated pages; document/source clusters are unavailable. This does not establish generalization to unseen datasets.'},
            'tokens': token_summary,
            'content_visual_token_reduction_percent': 100*(1-token_summary[ARMS[1]]['content_visual_tokens_total']/token_summary[ARMS[0]]['content_visual_tokens_total']),
            'new_model_inference': False, 'new_official_scoring': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT/'artifacts/evidence')
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/recomputed_statistics.json')
    args = parser.parse_args()
    result = compute(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2, allow_nan=False)+'\n').encode('utf-8'))
    print(json.dumps({'output': str(args.output), 'Overall_delta_pp': result['Overall_delta_pp'],
                      'CI95': result['bootstrap']['Overall_delta_pp_percentile95'],
                      'tokens': result['tokens'], 'reduction_percent': result['content_visual_token_reduction_percent']}, indent=2))
