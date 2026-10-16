"""GT-free line-height estimator v4 (= v3 without small-gap band merging, which fused tightly-leaded lines): projection bands computed inside vertical strips (so rows that touch in one
column do not merge the whole table), merged-band rejection, plus a character-height statistic for formulas.
estimate(img) -> (line_h or None, n_bands); char_height(img) -> median connected-component height of glyph-like CCs."""
import cv2
import numpy as np


def _binarize(g):
    g = cv2.GaussianBlur(g, (0, 0), 0.6) if min(g.shape) >= 8 else g
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw if (bw > 0).mean() < 0.5 else 255 - bw


def _clean(bw):
    H, W = bw.shape
    for k in [(max(40, W // 4), 1), (1, max(40, H // 2))]:
        lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
        bw = cv2.subtract(bw, cv2.dilate(lines, np.ones((3, 3), np.uint8)))
    return bw


def _bands(col):
    H, W = col.shape
    ink = (col > 0).sum(1) > max(1, 0.004 * W)
    bands, y = [], 0
    while y < H:
        if ink[y]:
            y0 = y
            while y < H and ink[y]:
                y += 1
            bands.append([y0, y])
        else:
            y += 1
    merged = []
    for b in bands:
        if merged:
            p = merged[-1]; gap, hb = b[0] - p[1], max(p[1] - p[0], b[1] - b[0])
            if gap <= 1 and (b[1] - p[0]) <= 1.3 * max(hb, 1) + 1:
                p[1] = b[1]; continue
        merged.append(list(b))
    return [b[1] - b[0] for b in merged if b[1] - b[0] >= 3]


def estimate(img, n_strips=4):
    g = np.array(img.convert('L')) if not isinstance(img, np.ndarray) else img
    H, W = g.shape
    if H < 6 or W < 6:
        return None, 0
    bw = _clean(_binarize(g))
    k = max(1, min(n_strips, W // max(40, H // 4 if H < W else 40)))
    hs = []
    for i in range(k):
        hs += _bands(bw[:, i * W // k:(i + 1) * W // k])
    if not hs:
        return None, 0
    hs = np.array(hs, dtype=float)
    q25 = np.percentile(hs, 25)
    hs = hs[(hs <= 3.0 * q25 + 2) & (hs >= 0.5 * q25)]
    if len(hs) == 0:
        return None, 0
    return float(np.median(hs)), int(len(hs))


def char_height(img):
    g = np.array(img.convert('L')) if not isinstance(img, np.ndarray) else img
    if min(g.shape) < 6:
        return None
    bw = _clean(_binarize(g))
    n, _, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    h, w, a = st[1:, cv2.CC_STAT_HEIGHT], st[1:, cv2.CC_STAT_WIDTH], st[1:, cv2.CC_STAT_AREA]
    keep = (h >= 3) & (a >= 6) & (w <= 4 * h + 2)
    if keep.sum() < 3:
        return None
    return float(np.median(h[keep]))
