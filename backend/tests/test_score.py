"""Tests for the composite ranking score."""

from __future__ import annotations

from backend.ranking.score import access_norm, composite, value_norm


def test_value_norm_bounds_and_monotonic():
    assert value_norm(0, 6, 18) == 0.0
    assert value_norm(None, 6, 18) == 0.0
    lo = value_norm(1e8, 6, 18)
    hi = value_norm(1e17, 6, 18)
    assert 0.0 <= lo < hi <= 1.0


def test_access_norm_lower_dv_scores_higher():
    easy = access_norm(4.0, 3.0, 30.0)
    hard = access_norm(20.0, 3.0, 30.0)
    assert easy > hard
    assert 0.0 <= hard < easy <= 1.0


def test_composite_weight_extremes():
    v, a = 0.9, 0.2
    assert abs(composite(v, a, 1.0) - v) < 1e-6      # pure value
    assert abs(composite(v, a, 0.0) - a) < 1e-6      # pure accessibility


def test_composite_punishes_near_zero_axis():
    # high value but near-zero accessibility should not beat a balanced object
    lopsided = composite(1.0, 0.001, 0.5)
    balanced = composite(0.5, 0.5, 0.5)
    assert balanced > lopsided
