"""Layer 1c: merge the external catalogues into the processed store.

Runs AFTER normalize. Left-joins NEOWISE albedos, SDSS colours, and extra spectral
labels onto data/processed/asteroids.parquet by the canonical desig_key, then:
  - fills missing visible albedo from NEOWISE (expands the model's key feature),
  - adds infrared/colour feature columns (kept as NaN where unknown),
  - merges measured spectral classes the backbone was missing (grows the labels).

    uv run python -m backend.ingest.enrich_features

Re-run order for a full refresh:
    sbdb -> asterank -> normalize -> neowise/sdss_moc/spectra -> enrich_features -> ranking.enrich -> ml.taxonomy_enriched

Output: rewrites data/processed/asteroids.parquet with the new columns + labels.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

STORE = Path("data/processed/asteroids.parquet")
RAW = {
    "neowise": Path("data/raw/neowise.parquet"),
    "sdss": Path("data/raw/sdss_colors.parquet"),
    "spectra": Path("data/raw/spectra_labels.parquet"),
}
NEW_FEATURES = ["pv_neowise", "ir_albedo", "nir_v_ratio", "diameter_neowise_km",
                "sdss_a_star", "sdss_i_z", "sdss_g_i"]


def _load(p: Path) -> pd.DataFrame | None:
    return pd.read_parquet(p) if p.exists() else None


def run(store: Path = STORE) -> pd.DataFrame:
    df = pd.read_parquet(store)
    # idempotent: drop any external columns from a previous run so re-merging
    # never collides into _x/_y suffixes
    df = df.drop(columns=[c for c in NEW_FEATURES if c in df.columns])
    n = len(df)
    before_albedo = int(df["albedo"].notna().sum())
    before_spec = int(df["spec_source"].ne("none").sum()) if "spec_source" in df else 0

    nw = _load(RAW["neowise"])
    if nw is not None:
        df = df.merge(nw, on="desig_key", how="left", suffixes=("", "_nw"))
        # fill visible albedo gaps from the NEOWISE measurement
        gap = df["albedo"].isna() & df["pv_neowise"].notna()
        df.loc[gap, "albedo"] = df.loc[gap, "pv_neowise"]
        print(f"[enrich] NEOWISE: matched {int(df['pv_neowise'].notna().sum())}, "
              f"filled {int(gap.sum())} new albedos")

    sd = _load(RAW["sdss"])
    if sd is not None:
        df = df.merge(sd[["desig_key", "sdss_a_star", "sdss_i_z", "sdss_g_i"]], on="desig_key", how="left")
        print(f"[enrich] SDSS colours: matched {int(df['sdss_a_star'].notna().sum())}")

    sp = _load(RAW["spectra"])
    if sp is not None:
        m = df.merge(sp.rename(columns={"spec_type": "_new_spec", "spec_source": "_new_src"}),
                     on="desig_key", how="left")
        add = m["spec_type"].isna() & m["_new_spec"].notna()
        df.loc[add, "spec_type"] = m.loc[add, "_new_spec"].values
        if "spec_source" in df:
            df.loc[add, "spec_source"] = m.loc[add, "_new_src"].values
        print(f"[enrich] spectra: matched {int(m['_new_spec'].notna().sum())}, "
              f"added {int(add.sum())} new measured labels")

    for c in NEW_FEATURES:
        if c not in df.columns:
            df[c] = pd.NA

    after_albedo = int(df["albedo"].notna().sum())
    after_spec = int(df["spec_source"].ne("none").sum()) if "spec_source" in df else 0
    df.to_parquet(store, index=False)
    print(f"\n[enrich] store rewritten: {n} rows")
    print(f"  albedo coverage : {before_albedo} -> {after_albedo}  (+{after_albedo - before_albedo})")
    print(f"  measured labels : {before_spec} -> {after_spec}  (+{after_spec - before_spec})")
    print("  next: uv run python -m backend.ml.taxonomy_enriched")
    return df


if __name__ == "__main__":
    run()
