"""Small CPU interfaces to the frozen A and B input rules."""
import math
from .best_effort import select
from .menu import gf_menu_scales


def source_render_scale(page_points, source_pixels, dpi=200, max_edge=3500):
    """A: choose the pre-render scale; callers retain their native renderer."""
    values = (*page_points, *source_pixels, dpi, max_edge)
    if len(page_points) != 2 or len(source_pixels) != 2:
        raise ValueError("Expected width/height pairs")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Dimensions, dpi and max_edge must be finite and positive")
    pw, ph = page_points
    sw, sh = source_pixels
    return min(dpi / 72, max_edge / max(pw, ph), sw / pw, sh / ph)


def candidate_scales(native, original_h, original_support, *, supported=True, protected=False):
    """B: the frozen menu and strict original-height/support trigger."""
    return gf_menu_scales(native, original_h, original_support, supported, protected)


def select_measured_candidates(candidates, *, kind, original_h, original_support, supported=True, protected=False):
    """B: select only from caller-supplied actual processor measurements."""
    if kind not in ("text", "table"):
        raise ValueError("kind must be text or table")
    return select(candidates, T=12 if kind == "text" else 11, L=11, max_scale=2,
                  supported_domain=supported, protected=protected,
                  original_h=original_h, original_support=original_support)
