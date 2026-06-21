"""Porkchop sweep: real launch windows from Lambert transfers.

For a target's orbital elements, sweep a grid of departure dates x flight times,
solve Lambert for each, and compute the total mission delta-v (LEO departure +
rendezvous match). The grid's minimum is the optimal launch window. This is the
Phase 2 capability that replaces the Phase 1 screening proxy with computed values.

Screening grade: two-body analytic ephemerides (kepler.py), not Horizons.
"""

from __future__ import annotations

import math

import numpy as np

from backend.astro import lambert
from backend.astro.kepler import MU_SUN, earth_state, propagate

AU_DAY_TO_KMS = 1731.456837  # 1 AU/day in km/s
V_LEO = 7.726                # 300 km circular LEO velocity, km/s


def _leo_departure(vinf_kms: float) -> float:
    """Delta-v from a 300 km LEO to a given hyperbolic excess speed (km/s)."""
    return math.sqrt(vinf_kms**2 + 2 * V_LEO**2) - V_LEO


def transfer_dv(elements: dict, dep_jd: float, tof_days: float) -> dict | None:
    """One transfer: LEO-departure + rendezvous delta-v for a dep date + flight time."""
    arr_jd = dep_jd + tof_days
    r_earth, v_earth = earth_state(dep_jd)
    r_ast, v_ast = propagate(elements, arr_jd)
    sol = lambert.solve(r_earth, r_ast, tof_days, MU_SUN, prograde=True)
    if sol is None:
        return None
    v1, v2 = sol
    vinf_dep = np.linalg.norm(v1 - v_earth) * AU_DAY_TO_KMS
    dv_arrive = np.linalg.norm(v2 - v_ast) * AU_DAY_TO_KMS
    dv_launch = _leo_departure(vinf_dep)
    return {
        "dep_jd": dep_jd,
        "tof_days": tof_days,
        "dv_launch_kms": dv_launch,
        "dv_arrive_kms": dv_arrive,
        "dv_total_kms": dv_launch + dv_arrive,
    }


def porkchop(
    elements: dict,
    start_jd: float,
    dep_span_days: int = 730,
    dep_step: int = 10,
    tof_min: int = 60,
    tof_max: int = 900,
    tof_step: int = 15,
) -> dict:
    """Sweep departure x time-of-flight; return the grid and the optimal window."""
    deps = np.arange(0, dep_span_days + 1, dep_step)
    tofs = np.arange(tof_min, tof_max + 1, tof_step)
    grid = np.full((len(tofs), len(deps)), np.nan)
    best = None
    for ci, d in enumerate(deps):
        for ri, t in enumerate(tofs):
            res = transfer_dv(elements, start_jd + float(d), float(t))
            if res is None or not math.isfinite(res["dv_total_kms"]):
                continue
            grid[ri, ci] = res["dv_total_kms"]
            if best is None or res["dv_total_kms"] < best["dv_total_kms"]:
                best = res
    return {
        "start_jd": start_jd,
        "dep_offsets": deps.tolist(),
        "tofs": tofs.tolist(),
        "grid_kms": [[None if math.isnan(v) else round(float(v), 3) for v in row] for row in grid],
        "optimal": None if best is None else {
            "dep_offset_days": round(float(best["dep_jd"] - start_jd), 1),
            "tof_days": round(float(best["tof_days"]), 1),
            "dv_launch_kms": round(float(best["dv_launch_kms"]), 3),
            "dv_arrive_kms": round(float(best["dv_arrive_kms"]), 3),
            "dv_total_kms": round(float(best["dv_total_kms"]), 3),
        },
    }
