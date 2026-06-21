"""Taxonomy classifier sanity (skips if sklearn / the ml extra isn't installed)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("sklearn")

from backend.ml.taxonomy import FEATURES, _model  # noqa: E402


def _synth(n=40, seed=0):
    rng = np.random.default_rng(seed)
    # C-types: dark (low albedo); S-types: bright. Other features are noise.
    c = np.column_stack([rng.normal(0.05, 0.02, n), rng.normal(18, 1, n),
                         rng.normal(1.5, 0.3, n), rng.normal(0.3, 0.1, n), rng.normal(10, 5, n)])
    s = np.column_stack([rng.normal(0.30, 0.04, n), rng.normal(18, 1, n),
                         rng.normal(1.5, 0.3, n), rng.normal(0.3, 0.1, n), rng.normal(10, 5, n)])
    X = np.vstack([c, s])
    y = np.array(["C"] * n + ["S"] * n)
    return X, y


def test_model_uses_five_features():
    assert len(FEATURES) == 5 and FEATURES[0] == "albedo"


def test_learns_albedo_split():
    X, y = _synth()
    m = _model().fit(X, y)
    dark = m.predict([[0.04, 18, 1.5, 0.3, 10]])[0]
    bright = m.predict([[0.32, 18, 1.5, 0.3, 10]])[0]
    assert dark == "C"
    assert bright == "S"


def test_probabilities_are_valid():
    X, y = _synth()
    m = _model().fit(X, y)
    p = m.predict_proba([[0.2, 18, 1.5, 0.3, 10]])[0]
    assert abs(p.sum() - 1.0) < 1e-6
    assert all(0.0 <= v <= 1.0 for v in p)
