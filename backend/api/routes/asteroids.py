"""Ranked / filterable asteroid endpoints (Layer 5 serving Layer 4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.store import get_store

router = APIRouter()


@router.get("/meta")
def meta() -> dict:
    """Coverage stats + normalization ranges for the UI."""
    return get_store().meta()


@router.get("/asteroids")
def asteroids(
    weight: float = Query(0.5, ge=0.0, le=1.0, description="0 = accessibility, 1 = value"),
    spec: str = Query("all", description="all | measured | C | S | M"),
    dv_max: float | None = Query(None, ge=0.0, description="max delta-v km/s"),
    q: str = Query("", description="name/designation search"),
    sort: str = Query("score", description="score | value_usd | dv_kms | full_name | display_diameter_km"),  # noqa: E501
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=500),
) -> dict:
    """Live-ranked, filtered, paginated list."""
    return get_store().rank(
        weight=weight, spec=spec, dv_max=dv_max, q=q,
        sort=sort, page=page, page_size=page_size,
    )


@router.get("/asteroids/{obj_id}")
def asteroid_detail(obj_id: int) -> dict:
    """Full record for one object, including Keplerian elements for the 3D view."""
    rec = get_store().detail(obj_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="asteroid not found")
    return rec
