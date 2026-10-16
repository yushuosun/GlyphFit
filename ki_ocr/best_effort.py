"""Only replace the frozen selector's no-reachable-candidate fallback.

Actual post-h is the existing CC q75 proxy, not glyph truth or OCR safety.
No scores or cache fields are used in selection. Menu limits are supplied by
the existing version (core<=2 or already-frozen extended<=4), never expanded.
"""
import hashlib
import importlib.util
import math
from pathlib import Path

from . import original_up as original
num = original.num


def valid_h(c):
    # Literal predicate in original.select; support policy is not changed.
    return isinstance(c.get('h'), (int, float)) and math.isfinite(c['h']) and c['h'] > 0 and c.get('support') is not None and c['support'] >= 3


def safe_progressive_ups(cands, max_scale):
    native = next(c for c in cands if num(c['scale']) == 1)
    if not valid_h(native):
        return []
    safe = []
    for c in cands:
        if not 1 < num(c['scale']) <= num(max_scale) or not valid_h(c):
            continue
        if not num(c['h']) > num(native['h']):
            continue
        if any(c.get(k) is None for k in ['V', 'P', 'context', 'reserve']):
            continue  # Missing admission evidence cannot become a candidate.
        if type(c.get('resource_admitted')) is not bool or not c['resource_admitted']:
            continue
        if c['P'] + c['reserve'] > c['context']:
            continue
        safe.append(c)
    return safe


def diagnose(cands, target, max_scale):
    native = next(c for c in cands if num(c['scale']) == 1)
    measured = [c for c in cands if 1 < num(c['scale']) <= num(max_scale) and valid_h(c)]
    admitted = [c for c in measured if all(c.get(k) is not None for k in ['V', 'P', 'context', 'reserve'])
                and type(c.get('resource_admitted')) is bool and c['resource_admitted'] and c['P'] + c['reserve'] <= c['context']]
    safe = safe_progressive_ups(cands, max_scale)
    reach = [c for c in safe if num(c['h']) >= num(target)]
    return {'native_h': native.get('h'), 'native_numeric_h_ge_target': valid_h(native) and num(native['h']) >= num(target),
            'measured_valid_up_N': len(measured), 'resource_admitted_valid_up_N': len(admitted),
            'safe_progressive_up_N': len(safe), 'safe_reaching_up_N': len(reach),
            'max_measured_valid_up_h': max((c['h'] for c in measured), default=None),
            'max_resource_admitted_valid_up_h': max((c['h'] for c in admitted), default=None),
            'max_safe_progressive_h': max((c['h'] for c in safe), default=None)}


def select(cands, T, L=11, max_scale=2, supported_domain=False, protected=False, original_h=None, original_support=None):
    old = original.select(cands, T=T, L=L, max_scale=max_scale, supported_domain=supported_domain,
                          protected=protected, original_h=original_h, original_support=original_support)
    out = dict(old)
    out.update(best_effort_applied=False, fallback_definition='MAX_ACTUAL_SAFE_PROGRESSIVE_POST_H_THEN_MIN_ACTUAL_V')
    if old['reason'] != 'UNMET_H_NO_ADMISSIBLE_UP_REACH_NATIVE_FALLBACK':
        return out  # All reachable/unknown/untriggered/protected routes identical.
    safe = safe_progressive_ups(cands, max_scale)
    if not safe:
        out.update(reason='UNMET_NO_SAFE_PROGRESSIVE_UP_KEEP_ORIGINAL_ROUTE', best_effort_no_candidate=True)
        return out
    native = next(c for c in cands if num(c['scale']) == 1)
    best = min(safe, key=lambda c: (-num(c['h']), c['V'], num(c['scale']) != 1,
                                   abs(num(c['scale']) - 1), abs(num(c['h']) - num(native['h'])), c['id']))
    assert num(best['h']) < num(old['H'])  # Otherwise original reachable branch would have selected a candidate.
    out.update(selected_id=best['id'], selected_scale=float(best['scale']),
               reason='BEST_EFFORT_MAX_SAFE_POST_H_TARGET_STILL_UNMET', target_reached=False,
               best_effort_applied=True, best_effort_no_candidate=False)
    return out
