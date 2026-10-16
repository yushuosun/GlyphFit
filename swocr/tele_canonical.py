"""Strict shared JSON projection for GEN and full-input identities."""
import enum,json,math
def plain(v):
    if isinstance(v,enum.Enum):return plain(v.value)
    if v is None or isinstance(v,(str,bool,int)):return v
    if isinstance(v,float):
        if not math.isfinite(v):raise ValueError('NONFINITE_CANONICAL_NUMBER')
        return v
    if isinstance(v,dict):
        if not all(isinstance(k,str) for k in v):raise TypeError('NONSTRING_CANONICAL_DICT_KEY')
        return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if isinstance(v,(set,frozenset)):
        values=[plain(x) for x in v]
        return sorted(values,key=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False))
    # Only actual msgspec Structs qualify; unrelated objects cannot duck-type fields.
    try:import msgspec
    except ImportError:msgspec=None
    if msgspec is not None and isinstance(v,msgspec.Struct):
        return {k:plain(getattr(v,k)) for k in v.__struct_fields__}
    raise TypeError('UNREVIEWED_METADATA_TYPE:'+type(v).__module__+'.'+type(v).__qualname__)
def canonical(v):return json.dumps(plain(v),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
