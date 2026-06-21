"""Enrich the ingested store with computed value + delta-v (Layers 3-4 input).

Reads the normalized ingestion store, adds:
  - our transparent value estimate with an uncertainty band (backend.ranking.value)
  - a best-available delta-v: Asterank's Benner value where present, else our
    screening-grade Hohmann proxy (backend.astro.deltav), each flagged

and writes the enriched store the ranking engine + API serve. Every computed
figure carries a source and an uncertainty so an estimate is never mistaken for
a measurement.

    uv run python -m backend.ranking.enrich

Input  : data/processed/asteroids.parquet
Output : data/processed/asteroids_enriched.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backend.astro.deltav import PROXY_REL_UNC, hohmann_rendezvous_dv
from backend.ingest.schema import ENRICHED_COLUMNS
from backend.ranking.value import value_estimate

IN_PATH = Path("data/processed/asteroids.parquet")
OUT_PATH = Path("data/processed/asteroids_enriched.parquet")
PRED_PATH = Path("data/models/taxonomy_predictions.parquet")


def _load_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Merge ML taxonomy predictions (if present) onto the store by desig_key."""
    if PRED_PATH.exists():
        pred = pd.read_parquet(PRED_PATH)
        return df.merge(pred, on="desig_key", how="left")
    df["ml_complex"] = pd.NA
    df["ml_confidence"] = pd.NA
    return df


def add_value(df: pd.DataFrame) -> pd.DataFrame:
    """Add computed value columns, using confident ML taxonomy where available."""
    df = _load_predictions(df)
    records = []
    for _, row in df.iterrows():
        spec = row.get("spec_type")
        spec = None if pd.isna(spec) else str(spec)
        diam = row.get("diameter_km")
        diam = float(diam) if pd.notna(diam) else None
        h = row.get("H_mag")
        h = float(h) if pd.notna(h) else None
        alb = row.get("albedo")
        alb = float(alb) if pd.notna(alb) else None
        mlc = row.get("ml_complex")
        mlc = None if pd.isna(mlc) else str(mlc)
        mlconf = row.get("ml_confidence")
        mlconf = None if pd.isna(mlconf) else float(mlconf)
        records.append(value_estimate(diam, spec, h_mag=h, albedo=alb,
                                      ml_complex=mlc, ml_confidence=mlconf))
    v = pd.DataFrame.from_records(records, index=df.index)

    df["value_usd"] = v["value_usd"]
    df["value_low"] = v["value_low"]
    df["value_high"] = v["value_high"]
    df["water_tons"] = v["water_tons"]
    df["metal_tons"] = v["metal_tons"]
    df["pgm_kg"] = v["pgm_kg"]
    df["value_complex"] = v["complex_used"].astype("string")
    df["size_source"] = v["size_source"].astype("string")
    df["spec_is_assumed"] = v["spec_is_assumed"]
    df["type_source"] = v["type_source"].astype("string")
    df["ml_complex"] = df["ml_complex"].astype("string")
    df["ml_confidence"] = pd.to_numeric(df["ml_confidence"], errors="coerce")
    has_value = df["value_usd"].notna()
    df["value_source"] = pd.array(
        ["computed:spectral-model" if x else "none" for x in has_value], dtype="string"
    )
    df["value_is_estimate"] = has_value  # never a measurement
    return df


def add_delta_v(df: pd.DataFrame) -> pd.DataFrame:
    """Add best-available delta-v: Benner (Asterank) where present, else proxy."""
    dv_kms, dv_source, dv_unc = [], [], []
    for _, row in df.iterrows():
        benner = row.get("asterank_dv_kms")
        if pd.notna(benner):
            dv_kms.append(float(benner))
            dv_source.append("asterank-benner")
            dv_unc.append(0.0)
            continue
        proxy = hohmann_rendezvous_dv(
            row.get("a_au"), row.get("e"), row.get("i_deg")
        )
        if proxy is not None:
            dv_kms.append(proxy)
            dv_source.append("computed:hohmann-proxy")
            dv_unc.append(PROXY_REL_UNC)
        else:
            dv_kms.append(None)
            dv_source.append("none")
            dv_unc.append(None)

    df["dv_kms"] = dv_kms
    df["dv_source"] = pd.array(dv_source, dtype="string")
    df["dv_rel_unc"] = dv_unc
    return df


def report(df: pd.DataFrame) -> None:
    n = len(df)
    if not n:
        print("[enrich] empty store")
        return
    val = int(df["value_usd"].notna().sum())
    ts = df["type_source"]
    measured = int(ts.eq("measured").sum())
    predicted = int(ts.eq("ml-predicted").sum())
    assumed = int(ts.eq("assumed").sum())
    benner = int(df["dv_source"].eq("asterank-benner").sum())
    proxy = int(df["dv_source"].eq("computed:hohmann-proxy").sum())
    print("\n[enrich] ---- enriched store summary ----")
    print(f"  rows                        : {n}")
    print(f"  with a value estimate       : {val} ({val / n:.0%})")
    print(f"  type: measured              : {measured}")
    print(f"  type: ML-predicted          : {predicted} (confident albedo classifier)")
    print(f"  type: assumed (default S)   : {assumed}")
    print(f"  delta-v from Benner table   : {benner} ({benner / n:.0%})")
    print(f"  delta-v from Hohmann proxy  : {proxy} ({proxy / n:.0%})")
    if val:
        v = df.loc[df["value_usd"].notna(), "value_usd"]
        print(f"  value_usd range (ESTIMATES) : {v.min():.2e} .. {v.max():.2e}")
    dv = df.loc[df["dv_kms"].notna(), "dv_kms"]
    if len(dv):
        print(f"  dv_kms range                : {dv.min():.2f} .. {dv.max():.2f} km/s")
    print("  ----------------------------------------\n")


def run(in_path: Path = IN_PATH, out: Path = OUT_PATH) -> pd.DataFrame:
    df = pd.read_parquet(in_path)
    df = add_value(df)
    df = add_delta_v(df)
    df = df.reindex(columns=ENRICHED_COLUMNS)
    report(df)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"[enrich] wrote {out} ({len(df)} rows, {len(df.columns)} cols)")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Add computed value + delta-v to the store.")
    parser.add_argument("--in", dest="in_path", type=Path, default=IN_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    run(args.in_path, args.out)


if __name__ == "__main__":
    main()
