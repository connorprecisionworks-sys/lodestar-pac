"""Phase 2 astrodynamics: Lambert, Kepler, and porkchop validation."""

from __future__ import annotations

import math

import numpy as np

from backend.astro import lambert
from backend.astro.kepler import EARTH_J2000, earth_state, propagate
from backend.astro.porkchop import porkchop


def test_lambert_matches_curtis_example():
    # Curtis, Orbital Mechanics, Example 5.2 (km, s, mu_earth)
    v1, v2 = lambert.solve([5000, 10000, 2100], [-14600, 2500, 7000], 3600, 398600)
    assert np.allclose(v1, [-5.9925, 1.9254, 3.2456], atol=1e-3)
    assert np.allclose(v2, [-3.3125, -4.1966, -0.38529], atol=1e-3)


def test_lambert_returns_none_on_degenerate():
    # identical points -> no transfer
    assert lambert.solve([1, 0, 0], [1, 0, 0], 100, 1.0) is None


def test_earth_distance_and_period_closure():
    r, _ = earth_state(2451545.0)
    assert 0.97 < np.linalg.norm(r) < 1.02          # ~1 AU, near perihelion in Jan
    r2, _ = earth_state(2451545.0 + EARTH_J2000["period"])
    assert np.linalg.norm(r - r2) < 1e-3            # returns after one period


def test_circular_orbit_radius_invariant():
    circ = {"a": 1.5, "e": 0.0, "i": 0, "om": 0, "w": 0, "ma": 0, "epoch": 2451545.0}
    radii = [np.linalg.norm(propagate(circ, 2451545.0 + d)[0]) for d in range(0, 400, 50)]
    assert max(radii) - min(radii) < 1e-6
    assert math.isclose(radii[0], 1.5, rel_tol=1e-9)


def test_porkchop_recovers_eros_benner_dv():
    # Eros optimal rendezvous dv is ~6.1 km/s (Benner). The Lambert porkchop
    # should land close, validating the whole engine end to end.
    eros = {"a": 1.458, "e": 0.2229, "i": 10.83, "om": 304.3, "w": 178.9,
            "ma": 320.0, "epoch": 2451545.0}
    pc = porkchop(eros, 2451545.0, dep_span_days=900, dep_step=20,
                  tof_min=80, tof_max=760, tof_step=25)
    opt = pc["optimal"]
    assert opt is not None
    assert 5.5 < opt["dv_total_kms"] < 7.0
    # result must be JSON-safe python floats, not numpy scalars
    assert isinstance(opt["dv_total_kms"], float)
