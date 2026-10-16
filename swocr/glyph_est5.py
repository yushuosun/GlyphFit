"""GT-free glyph-height estimator v5: character-level connected components (independent of line leading).
After removing rules, keep glyph-like CCs (h>=3 px, area>=6, not long horizontal strokes) and return the 75th percentile
of their heights (full-height glyphs: digits, capitals, CJK characters dominate the upper quartile).
estimate(img) -> (h or None, n_cc)."""
import cv2
import numpy as np

from .glyph_est4 import _binarize, _clean


def estimate(img, q=75):
    g = np.array(img.convert('L')) if not isinstance(img, np.ndarray) else img
    if min(g.shape) < 6:
        return None, 0
    bw = _clean(_binarize(g))
    n, _, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    h, w, a = st[1:, cv2.CC_STAT_HEIGHT], st[1:, cv2.CC_STAT_WIDTH], st[1:, cv2.CC_STAT_AREA]
    keep = (h >= 3) & (a >= 6) & (w <= 3 * h + 2) & (h <= 0.9 * g.shape[0])
    if keep.sum() < 3:
        return None, int(keep.sum())
    return float(np.percentile(h[keep], q)), int(keep.sum())
