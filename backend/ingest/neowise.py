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
import io
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from backend.ingest.schema import desig_key

# IRSA TAP. The catalogue table is `neowisesbpropv2` (NEOWISE Diameters & Albedos v2).
ADQL = ("SELECT asteroid_number,prov_desig,v_albedo,ir_albedo,diameter,beaming_param "
        "FROM neowisesbpropv2")
SOURCE_URL = ("https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY="
              + quote(ADQL))
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
    if text.lstrip().startswith("<"):  # VOTable/XML error from IRSA
        raise SystemExit("[neowise] IRSA returned an error:\n" + text.strip()[:700])
    if any(l.startswith("|") for l in text.splitlines()[:50]):  # IPAC table (e.g. a Gator --file)
        raw = _read_ipac(text)
    else:  # TAP CSV
        raw = pd.read_csv(io.StringIO(text), comment="#", low_memory=False)
    raw.columns = [c.lower() for c in raw.columns]
    if "v_albedo" not in raw.columns:
        raise SystemExit(f"[neowise] unexpected columns {list(raw.columns)[:12]} ... send me this list")
    num = pd.to_numeric(raw.get("asteroid_number"), errors="coerce")
    des = raw["prov_desig"].astype("string") if "prov_desig" in raw.columns else pd.Series([pd.NA] * len(raw))
    keys = []
    for n, d in zip(num.tolist(), des.tolist()):
        if pd.notna(n):
            keys.append(f"n:{int(n)}")
        elif isinstance(d, str) and d.strip() and d.strip().lower() != "nan":
            keys.append(desig_key(d.strip()))
        else:
            keys.append(None)
    out = pd.DataFrame({
        "desig_key": keys,
        "pv_neowise": pd.to_numeric(raw["v_albedo"], errors="coerce").to_numpy(),
        "ir_albedo": pd.to_numeric(raw.get("ir_albedo"), errors="coerce").to_numpy(),
        "diameter_neowise_km": pd.to_numeric(raw.get("diameter"), errors="coerce").to_numpy(),
    })
    out = out.dropna(subset=["desig_key", "pv_neowise"])
    out = out[out["pv_neowise"] > 0]
    out = out.groupby("desig_key", as_index=False).median(numeric_only=True)
    out["nir_v_ratio"] = (out["ir_albedo"] / out["pv_neowise"]).where(out["pv_neowise"] > 0)
    return out


def list_catalogs() -> None:
    """Ask IRSA what the NEOWISE small-body catalogue is actually called, both in
    the TAP service and in Gator. Run with --list, then paste me the output."""
    kw = ("neowise", "albedo", "diam", "sbprop", "small")
    print("=== IRSA TAP tables ===")
    try:
        tap = _download("https://irsa.ipac.caltech.edu/TAP/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv"
                        "&QUERY=" + quote("SELECT table_name FROM TAP_SCHEMA.tables"))
        hits = [l for l in tap.splitlines() if any(k in l.lower() for k in kw)]
        print("\n".join(hits) or "(no matching TAP tables)")
    except Exception as ex:  # noqa: BLE001
        print(f"(TAP list failed: {str(ex)[:80]})")
    print("\n=== Gator catalogues ===")
    try:
        scan = _download("https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-scan?mode=ascii")
        hits = [l for l in scan.splitlines() if any(k in l.lower() for k in kw)]
        print("\n".join(hits[:40]) or "(no matching Gator catalogues)")
    except Exception as ex:  # noqa: BLE001
        print(f"(Gator scan failed: {str(ex)[:80]})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest NEOWISE diameters + albedos via IRSA.")
    ap.add_argument("--list", action="store_true", help="discover the real IRSA catalogue name")
    ap.add_argument("--url", default=SOURCE_URL)
    ap.add_argument("--file", type=Path, default=None, help="local table instead of querying IRSA")
    ap.add_argument("--out", type=Path, default=RAW_PATH)
    args = ap.parse_args()
    if args.list:
        list_catalogs()
        return

    src = args.file if args.file else _download(args.url)
    try:
        df = parse(src)
    except SystemExit:
        raise
    except Exception as ex:  # noqa: BLE001 - keep the failure to one clean line
        raise SystemExit(f"[neowise] parse failed: {type(ex).__name__}: {str(ex)[:300]}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[neowise] wrote {args.out}: {len(df)} objects with albedo "
          f"({int(df['ir_albedo'].notna().sum())} with near-IR albedo, "
          f"{int(df['diameter_neowise_km'].notna().sum())} with diameter)")


if __name__ == "__main__":
    main()
