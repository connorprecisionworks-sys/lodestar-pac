"""Build the self-contained preview dashboard from the enriched store.

Reads data/processed/asteroids_enriched.parquet, embeds a compact copy of the
data into template.html, and writes lodestar-preview.html (open in any browser,
no server needed). Re-run to refresh the dashboard after re-enriching.

    uv run python -m frontend.preview.build_preview
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from backend.ranking.value import effective_diameter

HERE = Path(__file__).parent
STORE = Path("data/processed/asteroids_enriched.parquet")
TEMPLATE = HERE / "template.html"
OUT = HERE / "lodestar-preview.html"


def _sig(x, n=3):
    """Round to n significant figures, JSON-friendly (None stays None)."""
    if x is None or pd.isna(x):
        return None
    x = float(x)
    if x == 0:
        return 0
    from math import floor, log10
    return round(x, -int(floor(log10(abs(x)))) + (n - 1))


def build() -> None:
    df = pd.read_parquet(STORE)
    df = df[df["value_usd"].notna() & df["dv_kms"].notna()].copy()

    rows = []
    for _, r in df.iterrows():
        complex_ = r["value_complex"] if pd.notna(r["value_complex"]) else "S"
        diam, _src = effective_diameter(
            float(r["diameter_km"]) if pd.notna(r["diameter_km"]) else None,
            float(r["H_mag"]) if pd.notna(r["H_mag"]) else None,
            float(r["albedo"]) if pd.notna(r["albedo"]) else None,
            complex_,
        )
        spec = r["spec_type"] if pd.notna(r["spec_type"]) else ""
        rows.append([
            r["full_name"],
            complex_,
            str(spec),
            1 if bool(r["spec_is_assumed"]) else 0,
            _sig(r["value_usd"]),
            _sig(r["value_low"]),
            _sig(r["value_high"]),
            round(float(r["dv_kms"]), 2),
            1 if r["dv_source"] == "asterank-benner" else 0,
            _sig(diam, 3),
            round(float(r["a_au"]), 3) if pd.notna(r["a_au"]) else None,
            round(float(r["e"]), 3) if pd.notna(r["e"]) else None,
            round(float(r["i_deg"]), 2) if pd.notna(r["i_deg"]) else None,
        ])

    measured = int((~df["spec_is_assumed"].fillna(True)).sum())
    benner = int((df["dv_source"] == "asterank-benner").sum())
    payload = {
        "rows": rows,
        "meta": {
            "n": len(rows),
            "measured": measured,
            "benner": benner,
            "built": dt.date.today().isoformat(),
        },
    }

    html = TEMPLATE.read_text()
    html = html.replace("__LODESTAR_DATA__", json.dumps(payload, separators=(",", ":")))
    OUT.write_text(html)
    size_mb = OUT.stat().st_size / 1e6
    print(f"[preview] wrote {OUT} ({len(rows):,} objects, {size_mb:.1f} MB)")


if __name__ == "__main__":
    build()
