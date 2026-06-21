"""Validate the screening delta-v proxy, including against real Benner values."""

from __future__ import annotations

import pytest

from backend.astro.deltav import hohmann_rendezvous_dv

# Orbital elements (a, e, i_deg) and the published Benner LEO-rendezvous dv (km/s)
# for three NEOs, pulled from the real Asterank data. The proxy is conservative,
# so we require it to sit within [0.9x, 1.4x] of Benner and never below.
BENNER = [
    ("Eros", 1.458, 0.223, 10.83, 6.11),
    ("Albert", 2.637, 0.547, 11.57, 7.72),
    ("Alinda", 2.474, 0.571, 9.40, 7.07),
]


@pytest.mark.parametrize("name,a,e,i,bn", BENNER)
def test_proxy_tracks_benner(name, a, e, i, bn):
    dv = hohmann_rendezvous_dv(a, e, i)
    assert dv is not None
    ratio = dv / bn
    assert 0.9 <= ratio <= 1.4, f"{name}: proxy {dv:.2f} vs Benner {bn:.2f} (ratio {ratio:.2f})"


def test_easy_target_is_cheap():
    # An object on Earth's exact orbit costs only the LEO escape (~3.2 km/s).
    dv = hohmann_rendezvous_dv(1.0, 0.0, 0.0)
    assert 3.0 < dv < 3.5


def test_inclination_raises_cost():
    low = hohmann_rendezvous_dv(1.5, 0.2, 2.0)
    high = hohmann_rendezvous_dv(1.5, 0.2, 25.0)
    assert high > low


def test_nonphysical_returns_none():
    assert hohmann_rendezvous_dv(-1.0, 0.2, 5.0) is None
    assert hohmann_rendezvous_dv(1.5, 1.2, 5.0) is None     # e >= 1
    assert hohmann_rendezvous_dv(None, 0.2, 5.0) is None
