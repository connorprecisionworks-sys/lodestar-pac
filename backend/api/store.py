"""In-memory store over the enriched parquet: load once, query per request.

Loaded a single time at import. Holds the dataframe, a stable integer id per
row, a precomputed display diameter, and the dataset-level normalization ranges
the ranking uses. 41k rows filter/sort in a few ms, so we query in pandas.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from backend.ranking.score import access_norm, composite, value_norm
from backend.ranking.value import effective_diameter

STORE_PATH = Path("data/processed/asteroids_enriched.parquet")

# Fields returned in the list view (compact).
LIST_FIELDS = [
    "id", "full_name", "value_complex", "spec_type", "spec_is_assumed",
    "value_usd", "value_low", "value_high", "dv_kms", "dv_source",
    "display_diameter_km", "score",
]


class Store:
    def __init__(self, path: Path = STORE_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run the pipeline first: "
                "ingest.sbdb, ingest.asterank, ingest.normalize, ranking.enrich."
            )
        df = pd.read_parquet(path)
        df = df[df["value_usd"].notna() & df["dv_kms"].notna()].reset_index(drop=True)
        df["id"] = df.index.astype(int)

        # display diameter (same provenance logic the value model uses)
        diam = []
        for _, r in df.iterrows():
            cx = r["value_complex"] if pd.notna(r["value_complex"]) else "S"
            d, _ = effective_diameter(
                float(r["diameter_km"]) if pd.notna(r["diameter_km"]) else None,
                float(r["H_mag"]) if pd.notna(r["H_mag"]) else None,
                float(r["albedo"]) if pd.notna(r["albedo"]) else None,
                cx,
            )
            diam.append(d)
        df["display_diameter_km"] = diam

        # normalization ranges (global, stable across requests)
        lv = np.log10(df.loc[df["value_usd"] > 0, "value_usd"])
        self.lv_min, self.lv_max = float(lv.min()), float(lv.max())
        self.dv_min = float(df["dv_kms"].min())
        self.dv_max = float(df["dv_kms"].max())
        self.df = df

    # -- ranking -----------------------------------------------------------
    def _scored(self, weight: float) -> pd.Series:
        vn = self.df["value_usd"].map(lambda v: value_norm(v, self.lv_min, self.lv_max))
        an = self.df["dv_kms"].map(lambda d: access_norm(d, self.dv_min, self.dv_max))
        return pd.Series(
            [composite(v, a, weight) for v, a in zip(vn, an, strict=True)],
            index=self.df.index,
        )

    def rank(
        self,
        weight: float = 0.5,
        spec: str = "all",
        dv_max: float | None = None,
        q: str = "",
        sort: str = "score",
        page: int = 0,
        page_size: int = 50,
    ) -> dict:
        df = self.df
        score = self._scored(weight)
        view = df.assign(score=score)

        if dv_max is not None:
            view = view[view["dv_kms"] <= dv_max]
        if spec == "measured":
            view = view[~view["spec_is_assumed"].fillna(True)]
        elif spec in ("C", "S", "M"):
            view = view[view["value_complex"] == spec]
        if q:
            view = view[view["full_name"].str.contains(q, case=False, na=False)]

        ascending = sort in ("dv_kms", "full_name")
        sort_col = sort if sort in view.columns else "score"
        view = view.sort_values(sort_col, ascending=ascending, kind="mergesort")

        total = len(view)
        start = page * page_size
        page_df = view.iloc[start : start + page_size]
        items = [_clean(r) for r in page_df[LIST_FIELDS].to_dict("records")]
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    # -- detail ------------------------------------------------------------
    def detail(self, obj_id: int) -> dict | None:
        hit = self.df[self.df["id"] == obj_id]
        if hit.empty:
            return None
        return _clean(hit.iloc[0].to_dict())

    def meta(self) -> dict:
        df = self.df
        n = len(df)
        return {
            "n": n,
            "measured_spec": int((~df["spec_is_assumed"].fillna(True)).sum()),
            "benner_dv": int((df["dv_source"] == "asterank-benner").sum()),
            "value_log_range": [self.lv_min, self.lv_max],
            "dv_range": [self.dv_min, self.dv_max],
        }


def _clean(d: dict) -> dict:
    """Make a record JSON-safe: NaN/inf -> None, numpy scalars -> python."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating, float)):
            out[k] = None if (v is None or math.isnan(v) or math.isinf(v)) else float(v)
        elif isinstance(v, (np.bool_, bool)):
            out[k] = bool(v)
        elif v is None or (isinstance(v, float) and math.isnan(v)):
            out[k] = None
        else:
            out[k] = v if not pd.isna(v) else None
    return out


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
