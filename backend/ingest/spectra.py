"""Layer 1b ingestion: extra spectral-class LABELS (grow the training set).

The learning curve says we are data-limited: more measured classes directly raise
accuracy. SBDB already gives us Bus-DeMeo + Tholen for ~1,100 objects; this pulls
additional published classifications (SMASS II / Bus, Bus-DeMeo, MITHNEOS NEO
survey) and merges any the backbone is missing.

Run on a machine with open internet:

    uv run python -m backend.ingest.spectra
    uv run python -m backend.ingest.spectra --file ~/Downloads/demeo2009.csv   # local fallback

These tables are small and their formats vary. The parser auto-detects a
designation column and a class/type column by name. If your download uses other
names, pass --id-col / --class-col, or send me the header.

Output: data/raw/spectra_labels.parquet  (desig_key, spec_type, spec_source)
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pandas as pd

from backend.ingest.schema import desig_key

# Public classification tables. Each is (name, url). Any that download + parse are
# merged; failures are skipped with a warning so one dead link does not block the rest.
SOURCES = [
    ("bus-demeo", "https://sbnarchive.psi.edu/pds3/non_mission/EAR_A_VARGBDET_5_BUSDEMEOTAX_V1_0/data/busdemeo_classifications.csv"),
]
RAW_PATH = Path("data/raw/spectra_labels.parquet")

ID_COLS = ["designation", "des", "number", "num", "name", "object", "full_name", "pdes", "ast"]
CLASS_COLS = ["class", "type", "taxon", "taxonomy", "spec_type", "bus_demeo", "demeo", "bus"]


def _download(url: str) -> str:
    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def go() -> str:
        with httpx.Client(timeout=120.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text

    return go()


def _pick(cols, options):
    low = {c.lower(): c for c in cols}
    for o in options:
        if o.lower() in low:
            return low[o.lower()]
    return None


def parse(text_or_path, source: str, id_col=None, class_col=None) -> pd.DataFrame:
    if isinstance(text_or_path, (str, Path)) and Path(str(text_or_path)).exists():
        raw = pd.read_csv(text_or_path, comment="#")
    else:
        raw = pd.read_csv(io.StringIO(text_or_path), comment="#")
    idc = id_col or _pick(raw.columns, ID_COLS)
    clc = class_col or _pick(raw.columns, CLASS_COLS)
    if idc is None or clc is None:
        raise SystemExit(f"[spectra] could not find id/class columns in {list(raw.columns)[:12]}")
    out = pd.DataFrame()
    out["desig_key"] = raw[idc].map(desig_key)
    out["spec_type"] = raw[clc].astype("string").str.strip()
    out["spec_source"] = f"measured:{source}"
    out = out.dropna(subset=["desig_key", "spec_type"])
    out = out[out["spec_type"].str.len() > 0].drop_duplicates(subset=["desig_key"], keep="first")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest extra spectral-class labels.")
    ap.add_argument("--file", type=Path, default=None, help="single local table to ingest")
    ap.add_argument("--source", default="catalog", help="provenance tag for --file")
    ap.add_argument("--id-col", default=None)
    ap.add_argument("--class-col", default=None)
    ap.add_argument("--out", type=Path, default=RAW_PATH)
    args = ap.parse_args()

    frames = []
    if args.file:
        frames.append(parse(args.file, args.source, args.id_col, args.class_col))
    else:
        for name, url in SOURCES:
            try:
                frames.append(parse(_download(url), name))
                print(f"[spectra] {name}: ok")
            except Exception as ex:  # noqa: BLE001
                print(f"[spectra] {name}: skipped ({str(ex)[:90]})")
    if not frames:
        raise SystemExit("[spectra] nothing ingested. Use --file with a downloaded table.")
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["desig_key"], keep="first")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[spectra] wrote {args.out}: {len(df)} classified objects")


if __name__ == "__main__":
    main()
