"""Lambert's problem: the orbit connecting two positions in a given time.

Universal-variable formulation (Curtis, Orbital Mechanics for Engineering
Students, Algorithm 5.2). Given r1, r2 and time of flight, returns the departure
and arrival velocity vectors. This is the engine behind launch-window and
transfer-feasibility computation.

Unit-agnostic: pass consistent units for r, dt, mu (km/s/km^3 or AU/day/AU^3).
"""

from __future__ import annotations

import math

import numpy as np


def _stumpff_c(z: float) -> float:
    if z > 1e-9:
        return (1 - math.cos(math.sqrt(z))) / z
    if z < -1e-9:
        return (math.cosh(math.sqrt(-z)) - 1) / (-z)
    return 0.5


def _stumpff_s(z: float) -> float:
    if z > 1e-9:
        sz = math.sqrt(z)
        return (sz - math.sin(sz)) / sz**3
    if z < -1e-9:
        sz = math.sqrt(-z)
        return (math.sinh(sz) - sz) / sz**3
    return 1.0 / 6.0


def solve(r1, r2, dt: float, mu: float, prograde: bool = True, tol: float = 1e-8):
    """Return (v1, v2) velocity vectors for the transfer, or None if no solution."""
    r1 = np.asarray(r1, dtype=float)
    r2 = np.asarray(r2, dtype=float)
    R1, R2 = np.linalg.norm(r1), np.linalg.norm(r2)

    cross = np.cross(r1, r2)
    cos_dnu = np.dot(r1, r2) / (R1 * R2)
    cos_dnu = max(min(cos_dnu, 1.0), -1.0)
    dnu = math.acos(cos_dnu)
    if prograde:
        if cross[2] < 0:
            dnu = 2 * math.pi - dnu
    else:
        if cross[2] >= 0:
            dnu = 2 * math.pi - dnu

    if abs(1 - math.cos(dnu)) < 1e-12:
        return None  # transfer angle ~0 or ~360 deg: singular
    A = math.sin(dnu) * math.sqrt(R1 * R2 / (1 - math.cos(dnu)))
    if abs(A) < 1e-12:
        return None

    def y(z):
        return R1 + R2 + A * (z * _stumpff_s(z) - 1) / math.sqrt(_stumpff_c(z))

    # solve F(z) = 0 by Newton's method
    z = 0.0
    converged = False
    for _ in range(100):
        if not math.isfinite(z) or z > 4 * math.pi**2 or z < -4 * math.pi**2:
            return None  # diverged / outside the single-rev bracket
        C, S = _stumpff_c(z), _stumpff_s(z)
        yz = y(z)
        if A > 0 and yz < 0:
            z += 0.1
            continue
        if yz <= 0 or C <= 0:
            return None
        chi = math.sqrt(yz / C)
        F = chi**3 * S + A * math.sqrt(yz) - math.sqrt(mu) * dt
        if abs(z) < 1e-9:
            dFdz = (math.sqrt(2) / 40) * yz**1.5 + (A / 8) * (
                math.sqrt(yz) + A * math.sqrt(1 / (2 * yz))
            )
        else:
            dFdz = (yz / C) ** 1.5 * (
                (1 / (2 * z)) * (C - 1.5 * S / C) + 0.75 * S**2 / C
            ) + (A / 8) * (3 * (S / C) * math.sqrt(yz) + A * math.sqrt(C / yz))
        if dFdz == 0:
            return None
        dz = F / dFdz
        z -= dz
        if abs(dz) < tol:
            converged = True
            break

    if not converged or not math.isfinite(z):
        return None

    yz = y(z)
    if yz <= 0:
        return None
    f = 1 - yz / R1
    g = A * math.sqrt(yz / mu)
    gdot = 1 - yz / R2
    v1 = (r2 - f * r1) / g
    v2 = (gdot * r2 - r1) / g
    return v1, v2
