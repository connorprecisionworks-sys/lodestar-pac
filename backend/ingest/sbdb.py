"""Layer 1 ingestion: JPL Small-Body Database (SBDB) Query API.

Pulls current orbital elements + physical params + measured spectral type for
near-Earth asteroids. This is the authoritative backbone every object hangs on.

API docs: https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html

Run on a machine with open internet (the Cowork sandbox cannot reach ssd-api):

    uv run python -m backend.ingest.sbdb                 # all NEAs
    uv run python -m backend.ingest.sbdb --limit 500     # quick smoke test

Output: data/raw/sbdb_neo.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

SBDB_QUERY_URL = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"

# Fields requested from SBDB. Order is irrelevant; the API echoes a `fields` list
# we align the rows against.
SBDB_FIELDS = [
    "spkid", "full_name", "pdes", "name",
    "neo", "pha", "class",
    "H", "diameter", "albedo",
    "spec_B", "spec_T",          # Bus-DeMeo and Tholen taxonomy (measured, sparse)
    "e", "a", "q", "i", "om", "w", "ma", "per", "moid", "epoch",
]

RAW_PATH = Path("data/raw/sbdb_neo.parquet")


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get(params: dict) -> dict:
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(SBDB_QUERY_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_sbdb(group: str = "neo", limit: int | None = None) -> pd.DataFrame:
    """Fetch near-Earth asteroids from SBDB into a raw dataframe.

    `group="neo"` + `kind=a` returns every near-Earth asteroid in one request.
    Columns are kept as returned (mostly strings); coercion happens in normalize.
    """
    params = {
        "fields": ",".join(SBDB_FIELDS),
        "sb-group": group,
        "sb-kind": "a",
        "full-prec": "false",
    }
    if limit is not None:
        params["limit"] = str(limit)

    payload = _get(params)
    fields = payload.get("fields", SBDB_FIELDS)
    rows = payload.get("data", [])
    df = pd.DataFrame(rows, columns=fields)
    print(f"[sbdb] fetched {len(df)} near-Earth asteroids ({len(fields)} fields)")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull NEA orbital/physical data from JPL SBDB.")
    parser.add_argument("--limit", type=int, default=None, help="cap rows (smoke test)")
    parser.add_argument("--out", type=Path, default=RAW_PATH, help="output parquet path")
    args = parser.parse_args()

    df = fetch_sbdb(limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[sbdb] wrote {args.out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
