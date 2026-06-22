"""Layer 1b ingestion: NEOWISE infrared diameters + albedos.

Adds the strongest new feature for the taxonomy model. Albedo is what separates
dark carbonaceous from bright stony rock, and NEOWISE measured it for tens of
thousands of asteroids, far more than the ~1,200 we currently have. The same
thermal data also gives an infrared albedo that helps with metallic objects,
which are albedo-degenerate in the visible.

Run on a machine with open internet (the Cowork sandbox cannot reach the archive):

    uv run python -m backend.ingest.neowise
    uv run python -m backend.ingest.neowise --file ~/Downloads/neowise.csv   # local fallback

Source: NEOWISE Diameters and Albedos (Mainzer et al.), NASA PDS Small Bodies Node.
If the auto-download URL 404s, download the per-object diameters/albedos table by
hand, drop it in data/raw/, and pass it with --file. The parser auto-detects the
number/designation, albedo (pV) and diameter columns by name, so most CSV deliveries
of this catalogue work as-is. Paste me the run output if the match count looks low.

Output: data/raw/neowise.parquet  (desig_key, pv_neowise, diameter_neowise_km)
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pandas as pd

from backend.ingest.schema import desig_key

# Best-known machine-readable mirror. Override with --url or --file if it moves.
SOURCE_URL = "https://sbnarchive.psi.edu/pds4/non_mission/gbo.ast.neowise.diam-albedo/data/neowise_diameters_albedos.csv"
RAW_PATH = Path("data/raw/neowise.parquet")

# Column-name candidates we accept from whatever delivery format shows up.
ID_COLS = ["designation", "des", "name", "full_name", "object", "pdes", "number", "num", "ast_number"]
ALBEDO_COLS = ["albedo", "pv", "p_v", "pV", "albedo_v", "geometric_albedo"]
DIAM_COLS = ["diameter", "diameter_km", "d_km", "diam", "diameter_value"]


def _download(url: str) -> str:
    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def go() -> str:
        with httpx.Client(timeout=300.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text

    return go()


def _pick(cols: list[str], options: list[str]) -> str | None:
    low = {c.lower(): c for c in cols}
    for o in options:
        if o.lower() in low:
            return low[o.lower()]
    return None


def parse(text_or_path) -> pd.DataFrame:
    raw = pd.read_csv(text_or_path, comment="#", low_memory=False) if isinstance(text_or_path, (str, Path)) and Path(str(text_or_path)).exists() \
        else pd.read_csv(io.StringIO(text_or_path), comment="#", low_memory=False)
    cols = list(raw.columns)
    idc = _pick(cols, ID_COLS)
    pvc = _pick(cols, ALBEDO_COLS)
    dmc = _pick(cols, DIAM_COLS)
    if idc is None or pvc is None:
        raise SystemExit(f"[neowise] could not find id/albedo columns in {cols[:12]} ... "
                         f"open the file and tell me the real column names")
    out = pd.DataFrame()
    out["desig_key"] = raw[idc].map(desig_key)
    out["pv_neowise"] = pd.to_numeric(raw[pvc], errors="coerce")
    out["diameter_neowise_km"] = pd.to_numeric(raw[dmc], errors="coerce") if dmc else pd.NA
    out = out.dropna(subset=["desig_key", "pv_neowise"])
    # one row per object: median across multiple apparitions
    out = out.groupby("desig_key", as_index=False).median(numeric_only=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest NEOWISE diameters + albedos.")
    ap.add_argument("--url", default=SOURCE_URL)
    ap.add_argument("--file", type=Path, default=None, help="local catalogue file instead of downloading")
    ap.add_argument("--out", type=Path, default=RAW_PATH)
    args = ap.parse_args()

    src = args.file if args.file else _download(args.url)
    df = parse(src)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[neowise] wrote {args.out}: {len(df)} objects with albedo "
          f"({int(df['diameter_neowise_km'].notna().sum())} with diameter)")


if __name__ == "__main__":
    main()
