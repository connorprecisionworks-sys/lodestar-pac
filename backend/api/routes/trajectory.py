"""Trajectory 'task' endpoint.

Phase 1: returns a screening-grade delta-v breakdown + transfer geometry derived
from orbital elements (no ephemerides, no Lambert). The frontend's "Compute
trajectory" button calls this. Phase 2 swaps the internals for a real
Horizons + Lambert + porkchop solve behind the SAME response shape, so the UI
does not change.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.store import get_store
from backend.astro.deltav import rendezvous_breakdown

router = APIRouter()


@router.get("/trajectory/{obj_id}")
def trajectory(obj_id: int) -> dict:
    rec = get_store().detail(obj_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="asteroid not found")

    bd = rendezvous_breakdown(rec.get("a_au"), rec.get("e"), rec.get("i_deg"))
    if bd is None:
        raise HTTPException(status_code=422, detail="non-physical orbital elements")

    # Prefer the measured Benner delta-v for the headline if we have it.
    headline = rec.get("dv_kms")
    return {
        "id": obj_id,
        "full_name": rec.get("full_name"),
        "elements": {
            "a_au": rec.get("a_au"), "e": rec.get("e"), "i_deg": rec.get("i_deg"),
            "om_deg": rec.get("om_deg"), "w_deg": rec.get("w_deg"),
            "ma_deg": rec.get("ma_deg"), "per_days": rec.get("per_days"),
        },
        "dv_headline_kms": headline,
        "dv_source": rec.get("dv_source"),
        "breakdown": bd,
        "phase2_note": "Schematic transfer only. Real launch windows (porkchop) and "
                       "optimized transfer arcs arrive in Phase 2.",
    }
