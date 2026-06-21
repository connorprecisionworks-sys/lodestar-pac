"""Layer 1: normalize SBDB + Asterank into one clean parquet store.

SBDB is the backbone (current orbits + physical + measured taxonomy). Asterank
overlays precomputed value + delta-v estimates. We left-join Asterank onto SBDB
on a canonical designation key, coerce types, derive a couple of fields, and
stamp provenance/uncertainty flags.

    uv run python -m backend.ingest.normalize

Inputs : data/raw/sbdb_neo.parquet, data/raw/asterank.parquet
Output : data/processed/asteroids.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backend.ingest.schema import (
    INGEST_COLUMNS,
    desig_key,
    est_diameter_from_h,
)

SBDB_RAW = Path("data/raw/sbdb_neo.parquet")
ASTERANK_RAW = Path("data/raw/asterank.parquet")
OUT_PATH = Path("data/processed/asteroids.parquet")

_TRUE = {"y", "yes", "1", "true", "t"}


def _num(series: pd.Series) -> pd.Series:
    # Strip stray whitespace (incl. Unicode, e.g. thin spaces in Asterank data)
    # before coercion so "226 " parses as 226 rather than NaN.
    if series.dtype == object or str(series.dtype) == "string":
        series = series.astype("string").str.strip()
    return pd.to_numeric(series, errors="coerce")


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(_TRUE)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return a column if present, else an all-None series of the right length."""
    if name in df.columns:
        return df[name]
    return pd.Series([None] * len(df), index=df.index)


def normalize_sbdb(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw SBDB columns onto the schema's id/orbit/physical/spectral fields."""
    out = pd.DataFrame(index=df.index)
    out["full_name"] = _col(df, "full_name").astype("string")
    out["pdes"] = _col(df, "pdes").astype("string")
    out["desig_key"] = out["full_name"].map(desig_key)
    out["number"] = pd.to_numeric(out["pdes"], errors="coerce").astype("Int64")

    out["neo"] = _to_bool(_col(df, "neo"))
    out["pha"] = _to_bool(_col(df, "pha"))
    out["orbit_class"] = _col(df, "class").astype("string")

    out["a_au"] = _num(_col(df, "a"))
    out["e"] = _num(_col(df, "e"))
    out["i_deg"] = _num(_col(df, "i"))
    out["om_deg"] = _num(_col(df, "om"))
    out["w_deg"] = _num(_col(df, "w"))
    out["ma_deg"] = _num(_col(df, "ma"))
    out["per_days"] = _num(_col(df, "per"))
    out["moid_au"] = _num(_col(df, "moid"))
    out["q_au"] = _num(_col(df, "q"))
    out["epoch_jd"] = _num(_col(df, "epoch"))

    out["H_mag"] = _num(_col(df, "H"))
    out["albedo"] = _num(_col(df, "albedo"))
    out["diameter_km"] = _num(_col(df, "diameter"))
    out["est_diameter_km"] = [
        est_diameter_from_h(h, p) if pd.isna(d) else None
        for h, p, d in zip(out["H_mag"], out["albedo"], out["diameter_km"], strict=True)
    ]

    # Spectral type: prefer Bus-DeMeo, else Tholen. Measured only - sparse by design.
    spec_b = _col(df, "spec_B").astype("string").str.strip()
    spec_t = _col(df, "spec_T").astype("string").str.strip()
    spec_type = []
    spec_source = []
    for b, t in zip(spec_b, spec_t, strict=True):
        if isinstance(b, str) and b and b.lower() != "nan":
            spec_type.append(b)
            spec_source.append("measured:bus-demeo")
        elif isinstance(t, str) and t and t.lower() != "nan":
            spec_type.append(t)
            spec_source.append("measured:tholen")
        else:
            spec_type.append(None)
            spec_source.append("none")
    out["spec_type"] = pd.array(spec_type, dtype="string")
    out["spec_source"] = pd.array(spec_source, dtype="string")
    return out


def normalize_asterank(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw Asterank columns onto the baseline fields (value untrusted, dv=Benner)."""
    out = pd.DataFrame(index=df.index)
    out["desig_key"] = _col(df, "full_name").map(desig_key)
    out["asterank_value_usd"] = _num(_col(df, "price"))   # unreliable for NEOs
    out["asterank_dv_kms"] = _num(_col(df, "dv"))         # Benner; reliable
    # carry asterank spectral type as a last-resort fallback for the filter
    out["_ast_spec"] = (
        _col(df, "spec_B").astype("string").fillna(_col(df, "spec_T").astype("string"))
    )
    out = out.dropna(subset=["desig_key"]).drop_duplicates(subset=["desig_key"], keep="first")
    return out


def merge(sbdb: pd.DataFrame, asterank: pd.DataFrame) -> pd.DataFrame:
    """Left-join the Asterank baseline onto the SBDB backbone (ingestion stage)."""
    df = sbdb.merge(asterank, on="desig_key", how="left", suffixes=("", "_ast"))

    # Fill spectral gaps from Asterank only where SBDB had none.
    gap = df["spec_type"].isna() & df["_ast_spec"].notna() & (df["_ast_spec"].str.lower() != "nan")
    df.loc[gap, "spec_type"] = df.loc[gap, "_ast_spec"]
    df.loc[gap, "spec_source"] = "measured:catalog"

    df = df.reindex(columns=INGEST_COLUMNS)
    return df


def report(df: pd.DataFrame) -> None:
    n = len(df)
    benner = int(df["asterank_dv_kms"].notna().sum())
    spec = int(df["spec_source"].ne("none").sum())
    print("\n[normalize] ---- ingestion summary ----")
    print(f"  rows (NEAs)                 : {n}")
    if n:
        print(f"  with Asterank/Benner dv ref : {benner} ({benner / n:.0%})")
        print(f"  with measured spec type     : {spec} ({spec / n:.0%})")
        unmeasured = n - spec
        pct = unmeasured / n
        print(f"  no spectral measurement     : {unmeasured} ({pct:.0%}) <- value assumes a type")
    else:
        print("  empty store")
    print("  next: run backend.ranking.enrich to add computed value + delta-v")
    print("  -----------------------------------\n")


def run(
    sbdb_path: Path = SBDB_RAW,
    asterank_path: Path = ASTERANK_RAW,
    out: Path = OUT_PATH,
) -> pd.DataFrame:
    sbdb_raw = pd.read_parquet(sbdb_path)
    asterank_raw = pd.read_parquet(asterank_path)
    df = merge(normalize_sbdb(sbdb_raw), normalize_asterank(asterank_raw))
    report(df)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"[normalize] wrote {out} ({len(df)} rows, {len(df.columns)} cols)")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Join + normalize SBDB and Asterank to parquet.")
    parser.add_argument("--sbdb", type=Path, default=SBDB_RAW)
    parser.add_argument("--asterank", type=Path, default=ASTERANK_RAW)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    run(args.sbdb, args.asterank, args.out)


if __name__ == "__main__":
    main()
