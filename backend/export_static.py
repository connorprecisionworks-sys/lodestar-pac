"""Export the enriched store to a compact static JSON for the frontend.

This is what makes the Vercel deploy backend-free: the React app loads this file
and does ranking / filtering / the screening trajectory client-side. Re-run
after re-enriching, then commit the JSON.

    uv run python -m backend.export_static

Output: frontend/public/data/asteroids.json
"""

from __future__ import annotations

import json
from math import floor, log10
from pathlib import Path

import pandas as pd

from backend.api.store import get_store

OUT = Path("frontend/public/data/asteroids.json")

# Column order embedded in the JSON (kept compact as array-of-arrays).
FIELDS = [
    "id", "full_name", "value_complex", "spec_type", "spec_is_assumed",
    "value_usd", "value_low", "value_high", "dv_kms", "dv_source",
    "display_diameter_km", "a_au", "e", "i_deg", "om_deg", "w_deg",
    "ma_deg", "per_days", "epoch_jd", "type_source", "ml_confidence",
]


def _sig(x, n=3):
    if x is None or pd.isna(x):
        return None
    x = float(x)
    if x == 0:
        return 0
    return round(x, -int(floor(log10(abs(x)))) + (n - 1))


def _r(x, n):
    return None if (x is None or pd.isna(x)) else round(float(x), n)


def build() -> None:
    store = get_store()
    df = store.df
    rows = []
    for _, r in df.iterrows():
        rows.append([
            int(r["id"]),
            r["full_name"],
            r["value_complex"] if pd.notna(r["value_complex"]) else "S",
            str(r["spec_type"]) if pd.notna(r["spec_type"]) else "",
            1 if bool(r["spec_is_assumed"]) else 0,
            _sig(r["value_usd"]), _sig(r["value_low"]), _sig(r["value_high"]),
            _r(r["dv_kms"], 3),
            "benner" if r["dv_source"] == "asterank-benner" else "proxy",
            _sig(r["display_diameter_km"], 3),
            _r(r["a_au"], 4), _r(r["e"], 4), _r(r["i_deg"], 3),
            _r(r["om_deg"], 2), _r(r["w_deg"], 2), _r(r["ma_deg"], 2),
            _r(r["per_days"], 1),
            _r(r["epoch_jd"], 4) if "epoch_jd" in r else None,
            (r["type_source"] if "type_source" in r and pd.notna(r["type_source"]) else "assumed"),
            _r(r["ml_confidence"], 2) if "ml_confidence" in r else None,
        ])

    payload = {"fields": FIELDS, "rows": rows, "meta": store.meta()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"[export] wrote {OUT} ({len(rows):,} objects, {OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    build()
