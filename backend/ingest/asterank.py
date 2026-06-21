"""Layer 1 ingestion: Asterank precomputed value + delta-v.

Asterank ships precomputed estimates - body value, profit, and a one-way
delta-v lower bound - derived from spectral-type-inferred composition. Phase 1
uses these PRECOMPUTED figures directly (no trajectory math yet, per the scope).

These are order-of-magnitude ESTIMATES, not measurements. That caveat is carried
into the store as `value_is_estimate=True` and `dv_source="asterank-precomputed"`.

API: https://www.asterank.com/api/asterank?query=<mongo-json>&limit=<n>

The public API can be slow or intermittently down. If it fails, download a JSON
or CSV export manually and pass it with --input.

    uv run python -m backend.ingest.asterank --limit 50000      # live API
    uv run python -m backend.ingest.asterank --input dump.json  # offline fallback

Output: data/raw/asterank.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

ASTERANK_URL = "https://www.asterank.com/api/asterank"
RAW_PATH = Path("data/raw/asterank.parquet")

# Fields we rely on downstream. Asterank returns many more; we keep these plus
# whatever else comes back, and let normalize select.
KEY_FIELDS = ["full_name", "price", "profit", "dv", "spec_B", "spec_T", "neo"]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get(params: dict) -> list[dict]:
    with httpx.Client(timeout=180.0) as client:
        resp = client.get(ASTERANK_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_asterank(query: str = "{}", limit: int = 50000) -> pd.DataFrame:
    """Fetch ranked asteroid value/delta-v rows from the live Asterank API."""
    params = {"query": query, "limit": str(limit)}
    rows = _get(params)
    df = pd.DataFrame(rows)
    print(f"[asterank] fetched {len(df)} rows from live API ({len(df.columns)} fields)")
    if len(df) == 1000 and limit > 1000:
        print("[asterank] NOTE: hit the API's hard 1000-row cap. Use a tighter --query "
              "(or an offline --input dump) to broaden coverage beyond 1000 objects.")
    _warn_missing(df)
    return df


def load_asterank_file(path: Path) -> pd.DataFrame:
    """Load a manually-downloaded Asterank export (.json array or .csv)."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        with open(path) as fh:
            data = json.load(fh)
        df = pd.DataFrame(data)
    print(f"[asterank] loaded {len(df)} rows from {path}")
    _warn_missing(df)
    return df


def _warn_missing(df: pd.DataFrame) -> None:
    missing = [c for c in KEY_FIELDS if c not in df.columns]
    if missing:
        print(f"[asterank] WARNING: expected fields absent from response: {missing}")


def sanitize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Make Asterank's messy response safe to write to parquet.

    Asterank mixes numbers and number-like strings (with stray Unicode
    whitespace, e.g. '226\\u2009') in the same column, which breaks Arrow's type
    inference. We strip whitespace and cast every object column to string. The
    few fields normalize actually uses (price, profit, dv) are re-coerced there,
    so nothing of value is lost.
    """
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x).astype("string")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Asterank value/delta-v estimates.")
    parser.add_argument("--limit", type=int, default=50000, help="max rows from live API")
    parser.add_argument(
        "--query", type=str, default=None,
        help='Mongo-style JSON filter. Default: auto - try NEO-only {"neo":1}, '
             "then fall back to unfiltered if that returns nothing.",
    )
    parser.add_argument("--input", type=Path, default=None, help="offline .json/.csv fallback")
    parser.add_argument("--out", type=Path, default=RAW_PATH, help="output parquet path")
    args = parser.parse_args()

    if args.input is not None:
        df = load_asterank_file(args.input)
    elif args.query is not None:
        df = fetch_asterank(query=args.query, limit=args.limit)
    else:
        # Default: NEO-only so all rows overlap the SBDB near-Earth backbone.
        # Asterank stores the flag as the string "Y" (not 1).
        df = fetch_asterank(query='{"neo":"Y"}', limit=args.limit)
        if len(df) == 0:
            print('[asterank] {"neo":"Y"} returned 0 rows; falling back to unfiltered query')
            df = fetch_asterank(query="{}", limit=args.limit)

    df = sanitize_for_parquet(df)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[asterank] wrote {args.out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
