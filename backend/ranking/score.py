"""Layer 4: composite ranking score from value and accessibility.

Pure functions so the scoring is testable in isolation. The dataset-level
normalization ranges are supplied by the caller (the store computes them once).

The composite is a weighted geometric mean of the two normalized axes, which
punishes a near-zero in either dimension: a worthless-but-easy rock should not
top the list, nor a priceless-but-unreachable one. The weight slides priority
from accessibility (0) to value (1).
"""

from __future__ import annotations

import math

_EPS = 1e-4


def value_norm(value: float | None, lv_min: float, lv_max: float) -> float:
    """Normalize value to 0..1 on a log scale (value spans many orders)."""
    if value is None or value <= 0 or lv_max <= lv_min:
        return 0.0
    x = (math.log10(value) - lv_min) / (lv_max - lv_min)
    return min(max(x, 0.0), 1.0)


def access_norm(dv: float | None, dv_min: float, dv_max: float) -> float:
    """Normalize accessibility to 0..1 (lower delta-v = higher score)."""
    if dv is None or dv_max <= dv_min:
        return 0.0
    x = 1.0 - (dv - dv_min) / (dv_max - dv_min)
    return min(max(x, 0.0), 1.0)


def composite(v_norm: float, a_norm: float, weight: float) -> float:
    """Weighted geometric mean of value and accessibility (weight 0..1)."""
    w = min(max(weight, 0.0), 1.0)
    vn = max(v_norm, _EPS)
    an = max(a_norm, _EPS)
    return vn**w * an ** (1.0 - w)
