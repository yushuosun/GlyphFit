"""Exact frozen menu functions extracted without changing the gate."""
import math

def valid(h,s):return isinstance(h,(int,float)) and math.isfinite(h) and h>0 and isinstance(s,(int,float)) and s>=3

def gf_menu_scales(native,source_h,source_support,supported,protected):
 if protected or not supported or not valid(native['h'],native['support']) or not valid(source_h,source_support) or source_h>=10.5:return [1]
 return [1,.7,.85,1.2,1.4,1.6,2]
