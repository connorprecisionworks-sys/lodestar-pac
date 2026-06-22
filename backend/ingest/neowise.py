"""Layer 1b ingestion: NEOWISE infrared diameters + albedos (via IRSA TAP).

Adds the strongest new features for the taxonomy model:
  - visible albedo (V_ALBEDO): fills our biggest feature for far more objects,
  - near-infrared albedo (IR_ALBEDO) and the IR/visible ratio: the thermal-emission
    signal that separates metallic from carbonaceous, which albedo alone cannot.

Pulled from IRSA's "NEOWISE Derived Diameters and Albedos of Solar System Small
Bodies" catalogue (Mainzer / Masiero et al.) over the standard VO TAP service,
which returns CSV directly. No account needed.

Run on a machine with open internet (the Cowork sandbox cannot reach IRSA):

    uv run python -m backend.ingest.neowise
    uv run python -m backend.ingest.neowise --file ~/Downloads/neowise.csv   # local fallback

Output: data/raw/neowise.parquet
        (desig_key, pv_neowise, ir_albedo, nir_v_ratio, diameter_neowise_km)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backend.ingest.schema import desig_key

# IRSA Gator native query for the whole `neowisesbprop` catalogue, IPAC-table output.
# (IRSA's TAP service does not expose this catalogue, but Gator does.)
_SELCOLS = "asteroid_number,prov_desig,v_albedo,ir_albedo,diameter,beaming_param"
SOURCE_URL = ("https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=neowisesbprop"
              "&spatial=NONE&outfmt=1&selcols=" + _SELCOLS)
RAW_PATH = Path("data/raw/neowise.parquet")


def _download(url: str) -> str:
    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def go() -> str:
        with httpx.Client(timeout=600.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text

    return go()


def _key(row) -> str | None:
    num = row.get("asteroid_number")
    if pd.notna(num):
        try:
            return f"n:{int(num)}"
        except (ValueError, TypeError):
            pass
    des = row.get("prov_desig")
    return desig_key(str(des)) if pd.notna(des) and str(des).strip() else None


def _read_ipac(text: str) -> pd.DataFrame:
    """Parse an IRSA Gator IPAC table: fixed-width columns delimited by the bar
    positions in the first |-header line (so values with spaces survive)."""
    lines = text.splitlines()
    hdrs = [i for i, l in enumerate(lines) if l.startswith("|")]
    if not hdrs:
        raise SystemExit("[neowise] Gator returned no IPAC table. Server said:\n"
                         + text.strip()[:700] + "\n\nPaste that to me and I will fix the query.")
    bars = [i for i, ch in enumerate(lines[hdrs[0]]) if ch == "|"]
    names = [lines[hdrs[0]][bars[k] + 1:bars[k + 1]].strip() for k in range(len(bars) - 1)]
    rows = []
    for l in lines[hdrs[-1] + 1:]:
        if not l.strip() or l[0] in "\\|":
            continue
        rows.append([l[bars[k] + 1:bars[k + 1]].strip() for k in range(len(bars) - 1)])
    return pd.DataFrame(rows, columns=names)


def parse(text_or_path) -> pd.DataFrame:
    is_path = isinstance(text_or_path, (str, Path)) and Path(str(text_or_path)).exists()
    text = Path(text_or_path).read_text() if is_path else str(text_or_path)
    raw = _read_ipac(text)
    raw.columns = [c.lower() for c in raw.columns]
    raw = raw.replace({"null": None, "": None})
    if "v_albedo" not in raw.columns:
        raise SystemExit(f"[neowise] unexpected columns {list(raw.columns)[:12]} ... send me this list")
    out = pd.DataFrame()
    out["desig_key"] = raw.apply(_key, axis=1)
    out["pv_neowise"] = pd.to_numeric(raw["v_albedo"], errors="coerce")
    out["ir_albedo"] = pd.to_numeric(raw.get("ir_albedo"), errors="coerce")
    out["diameter_neowise_km"] = pd.to_numeric(raw.get("diameter"), errors="coerce")
    out = out.dropna(subset=["desig_key", "pv_neowise"])
    out = out[out["pv_neowise"] > 0]
    # one row per object: median across apparitions
    out = out.groupby("desig_key", as_index=False).median(numeric_only=True)
    out["nir_v_ratio"] = (out["ir_albedo"] / out["pv_neowise"]).where(out["pv_neowise"] > 0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest NEOWISE diameters + albedos via IRSA TAP.")
    ap.add_argument("--url", default=SOURCE_URL)
    ap.add_argument("--file", type=Path, default=None, help="local CSV instead of querying IRSA")
    ap.add_argument("--out", type=Path, default=RAW_PATH)
    args = ap.parse_args()

    src = args.file if args.file else _download(args.url)
    df = parse(src)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[neowise] wrote {args.out}: {len(df)} objects with albedo "
          f"({int(df['ir_albedo'].notna().sum())} with near-IR albedo, "
          f"{int(df['diameter_neowise_km'].notna().sum())} with diameter)")


if __name__ == "__main__":
    main()
