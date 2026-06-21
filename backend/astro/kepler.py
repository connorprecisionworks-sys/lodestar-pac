"""Analytic two-body (Keplerian) propagation to heliocentric state vectors.

Phase 2 astrodynamics. Given an object's orbital elements at an epoch, compute
its heliocentric position and velocity at any Julian Date. This is screening
grade: pure two-body, no planetary perturbations. Horizons-precision ephemerides
are a later accuracy upgrade; for launch-window screening over a few-year window
this is a sound first cut.

Units: AU, days. Sun gravitational parameter mu in AU^3/day^2.
"""

from __future__ import annotations

import math

import numpy as np

# Gaussian gravitational constant k; mu_sun = k^2 in AU^3/day^2.
MU_SUN = 0.01720209895**2  # = 2.9591220828559e-4

# Earth heliocentric orbital elements at J2000 (epoch JD 2451545.0).
# Mean longitude L; argument of perihelion and node folded in. i ~ 0 in ecliptic.
EARTH_J2000 = {
    "a": 1.00000011, "e": 0.01671022, "i": 0.0,
    "om": 0.0, "w": 102.93768193, "ma": 100.46435 - 102.93768193,
    "epoch": 2451545.0, "period": 365.256363,
}


def _solve_kepler(M: float, e: float) -> float:
    """Solve M = E - e sin E for eccentric anomaly E (radians)."""
    E = M if e < 0.8 else math.pi
    for _ in range(80):
        d = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= d
        if abs(d) < 1e-12:
            break
    return E


def _rotation(om: float, i: float, w: float) -> np.ndarray:
    """Perifocal-to-ecliptic rotation matrix from node, inclination, arg-periapsis."""
    cO, sO = math.cos(om), math.sin(om)
    ci, si = math.cos(i), math.sin(i)
    cw, sw = math.cos(w), math.sin(w)
    return np.array([
        [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
        [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
        [sw * si, cw * si, ci],
    ])


def propagate(elements: dict, jd: float) -> tuple[np.ndarray, np.ndarray]:
    """Heliocentric (position AU, velocity AU/day) at Julian Date jd.

    elements: a (AU), e, i/om/w/ma (degrees), epoch (JD). period optional.
    """
    a = float(elements["a"])
    e = float(elements["e"])
    i = math.radians(float(elements["i"]))
    om = math.radians(float(elements["om"]))
    w = math.radians(float(elements["w"]))
    ma0 = math.radians(float(elements["ma"]))
    epoch = float(elements["epoch"])

    n = math.sqrt(MU_SUN / a**3)          # mean motion, rad/day
    M = ma0 + n * (jd - epoch)
    M = (M + math.pi) % (2 * math.pi) - math.pi
    E = _solve_kepler(M, e)

    # perifocal position + velocity
    cosE, sinE = math.cos(E), math.sin(E)
    x_p = a * (cosE - e)
    y_p = a * math.sqrt(1 - e * e) * sinE
    # velocity in perifocal (AU/day)
    edot = n / (1 - e * cosE)             # dE/dt
    vx_p = -a * sinE * edot
    vy_p = a * math.sqrt(1 - e * e) * cosE * edot

    R = _rotation(om, i, w)
    pos = R @ np.array([x_p, y_p, 0.0])
    vel = R @ np.array([vx_p, vy_p, 0.0])
    return pos, vel


def earth_state(jd: float) -> tuple[np.ndarray, np.ndarray]:
    """Earth heliocentric state at jd (AU, AU/day)."""
    return propagate(EARTH_J2000, jd)
