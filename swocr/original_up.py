from fractions import Fraction
import math

class MissingActualFeature(ValueError):
    pass

def num(x):
    return Fraction(str(x))

def select(cands, T, L, max_scale=2, supported_domain=False, protected=False, original_h=None, original_support=None):
    native = next((c for c in cands if num(c['scale']) == 1), None)
    if native is None:
        raise MissingActualFeature('native metadata')
    H = max(num(T), num(L)) if L is not None else None

    def out(c, reason, met=False):
        return dict(selected_id=c['id'], selected_scale=float(c['scale']), reason=reason, H=None if H is None else float(H), target_reached=met, triggered=False)
    if protected:
        return out(native, 'ORIGINAL_CAP_PROTECTED_TYPE')
    if not supported_domain or L is None:
        return out(native, 'C_UNSUPPORTED_L_OR_SOURCE_DOMAIN')

    def valid_h(c):
        return isinstance(c.get('h'), (int, float)) and math.isfinite(c['h']) and (c['h'] > 0) and (c.get('support') is not None) and (c['support'] >= 3)
    if not valid_h(native):
        return out(native, 'NATIVE_ESTIMATOR_INVALID_OR_SUPPORT_INSUFFICIENT')
    if not valid_h(dict(h=original_h, support=original_support)):
        return out(native, 'ORIGINAL_ESTIMATOR_INVALID_OR_SUPPORT_INSUFFICIENT_CAP')
    if num(original_h) >= num(10.5):
        return out(native, 'ORIGINAL_H_GE10_5_UP_NOT_TRIGGERED', num(native['h']) >= H)
    for c in cands:
        if num(c['scale']) > 1 and num(c['scale']) <= num(max_scale):
            for k in ['h', 'support', 'V', 'P', 'context', 'reserve', 'resource_admitted']:
                if k not in c:
                    raise MissingActualFeature(c['id'] + ':' + k)
    valid = []
    for c in cands:
        s = num(c['scale'])
        if not 1 < s <= num(max_scale) or not valid_h(c):
            continue
        if not (num(c['h']) > num(native['h']) and num(c['h']) >= H):
            continue
        if any((c.get(k) is None for k in ['V', 'P', 'context', 'reserve'])):
            raise MissingActualFeature(c['id'] + ':missing resource evidence')
        if type(c['resource_admitted']) is not bool or not c['resource_admitted']:
            continue
        if c['P'] + c['reserve'] > c['context']:
            continue
        valid.append(c)
    if not valid:
        z = out(native, 'UNMET_H_NO_ADMISSIBLE_UP_REACH_NATIVE_FALLBACK')
        z['triggered'] = True
        return z
    c = min(valid, key=lambda c: (c['V'], num(c['scale']) != 1, abs(num(c['scale']) - 1), abs(num(c['h']) - num(native['h'])), c['id']))
    z = out(c, 'ACTUAL_MIN_V_UP_REACH_H', True)
    z['triggered'] = True
    return z

def select_up_original(cands,original_h,original_support,max_scale=2,protected=False):
 return select(cands,T=11,L=11,max_scale=max_scale,supported_domain=True,protected=protected,original_h=original_h,original_support=original_support)
