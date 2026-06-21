"""Layer 3 (screening-grade): a transparent delta-v estimate from orbital elements.

SCOPE FENCE: this is NOT the trajectory math of Phase 2. There is no Lambert
solve and no porkchop optimization here. This is a patched-conic, two-impulse
Hohmann-rendezvous APPROXIMATION computed purely from (a, e, i), used only to
give every object a first-order accessibility number for ranking. Phase 2
replaces it with real ephemeris-based transfers.

Model:
  1. Depart a 300 km circular LEO onto a Hohmann transfer between Earth's orbit
     (1 AU, treated as circular) and the asteroid's relevant apsis.
  2. At arrival, match the asteroid's heliocentric velocity, paying the plane
     change at the slower apsis of the transfer (where it is cheapest).
  3. Earth departure cost folds the required hyperbolic excess through the LEO
     parking orbit (Oberth-correct).

Honesty: eccentricity enters only through the chosen apsis, so this runs
CONSERVATIVE (typically ~20-35% high) versus the optimized Shoemaker-Helin /
Benner delta-v. Where a measured Benner value exists (via Asterank), prefer it.
This proxy is flagged `computed:hohmann-proxy` and carries a wide uncertainty.

All velocities in km/s.
"""

from __future__ import annotations

import math

V_EARTH = 29.784   # Earth mean orbital (circular) velocity, km/s
V_LEO = 7.726      # circular velocity at 300 km altitude, km/s
# Relative uncertainty we attach to the proxy (it is order-tens-of-percent).
PROXY_REL_UNC = 0.35


def _vis_viva(r_au: float, a_au: float) -> float:
    """Heliocentric speed (km/s) at radius r on an orbit of semi-major axis a."""
    return V_EARTH * math.sqrt(max(2.0 / r_au - 1.0 / a_au, 0.0))


def hohmann_rendezvous_dv(a_au: float, e: float, i_deg: float) -> float | None:
    """Screening-grade total rendezvous delta-v (km/s) from a 300 km LEO.

    Returns None if the elements are non-physical (a<=0, e<0, e>=1).
    """
    if a_au is None or e is None or i_deg is None:
        return None
    if a_au <= 0 or e < 0 or e >= 1:
        return None
    i = math.radians(i_deg)

    r1 = 1.0  # Earth orbit (AU)
    # Target the apsis we would naturally rendezvous at: aphelion for outer
    # orbits (a>=1), perihelion for inner Atens (a<1).
    r2 = a_au * (1.0 + e) if a_au >= 1.0 else a_au * (1.0 - e)
    if r2 <= 0:
        return None

    a_t = (r1 + r2) / 2.0          # transfer ellipse semi-major axis
    v_dep_circ = V_EARTH / math.sqrt(r1)          # Earth's speed
    vt_dep = _vis_viva(r1, a_t)                    # transfer speed at departure
    vt_arr = _vis_viva(r2, a_t)                    # transfer speed at arrival
    v_ast_arr = _vis_viva(r2, a_au)                # asteroid's own speed at r2

    if r2 >= r1:
        # Slower apsis is arrival (aphelion of transfer): pay plane change there.
        vinf_dep = abs(vt_dep - v_dep_circ)
        dv_arrive = math.sqrt(
            v_ast_arr**2 + vt_arr**2 - 2.0 * v_ast_arr * vt_arr * math.cos(i)
        )
    else:
        # Slower apsis is departure (1 AU): pay plane change at departure.
        vinf_dep = math.sqrt(
            v_dep_circ**2 + vt_dep**2 - 2.0 * v_dep_circ * vt_dep * math.cos(i)
        )
        dv_arrive = abs(v_ast_arr - vt_arr)

    # Earth departure from 300 km LEO to the required hyperbolic excess.
    dv_launch = math.sqrt(vinf_dep**2 + 2.0 * V_LEO**2) - V_LEO
    return dv_launch + dv_arrive


def rendezvous_breakdown(a_au: float, e: float, i_deg: float) -> dict | None:
    """Itemized screening delta-v for the 'compute trajectory' task.

    Returns the departure burn, arrival/match burn, total, and the transfer
    geometry (target radius + transfer semi-major axis) so the UI can draw a
    schematic arc. None for non-physical elements. This is screening-grade; the
    Phase 2 endpoint will return a Lambert/porkchop-optimized transfer instead.
    """
    if a_au is None or e is None or i_deg is None:
        return None
    if a_au <= 0 or e < 0 or e >= 1:
        return None
    i = math.radians(i_deg)

    r1 = 1.0
    r2 = a_au * (1.0 + e) if a_au >= 1.0 else a_au * (1.0 - e)
    if r2 <= 0:
        return None
    a_t = (r1 + r2) / 2.0
    v_dep_circ = V_EARTH / math.sqrt(r1)
    vt_dep = _vis_viva(r1, a_t)
    vt_arr = _vis_viva(r2, a_t)
    v_ast_arr = _vis_viva(r2, a_au)

    if r2 >= r1:
        vinf_dep = abs(vt_dep - v_dep_circ)
        dv_arrive = math.sqrt(
            v_ast_arr**2 + vt_arr**2 - 2.0 * v_ast_arr * vt_arr * math.cos(i)
        )
    else:
        vinf_dep = math.sqrt(
            v_dep_circ**2 + vt_dep**2 - 2.0 * v_dep_circ * vt_dep * math.cos(i)
        )
        dv_arrive = abs(v_ast_arr - vt_arr)

    dv_launch = math.sqrt(vinf_dep**2 + 2.0 * V_LEO**2) - V_LEO
    return {
        "dv_launch_kms": round(dv_launch, 3),
        "dv_arrive_kms": round(dv_arrive, 3),
        "dv_total_kms": round(dv_launch + dv_arrive, 3),
        "transfer_target_au": round(r2, 4),
        "transfer_sma_au": round(a_t, 4),
        "rel_uncertainty": PROXY_REL_UNC,
        "grade": "screening (patched-conic Hohmann); Phase 2 replaces with Lambert/porkchop",
    }
