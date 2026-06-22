"""Layer 1b ingestion: SDSS Moving Object Catalog (visible colours).

Adds visible-light colour features (the famous SDSS asteroid a*-vs-(i-z) plane
that splits taxonomic complexes). Complements NEOWISE infrared: together they are
what break the metallic/carbonaceous albedo degeneracy.

Run on a machine with open internet:

    uv run python -m backend.ingest.sdss_moc
    uv run python -m backend.ingest.sdss_moc --file ~/Downloads/ADR4.dat       # local fallback

Source: SDSS Moving Object Catalog, 4th release (ADR4), Ivezic et al.
The ADR4 file is whitespace-delimited with NO header. Column positions follow the
published ADR4 readme; they are listed in COLS below. If the match count comes out
near zero, the layout differs from this build, paste me the first data line and I
will fix the indices in one edit.

Output: data/raw/sdss_colors.parquet  (desig_key, sdss_a_star, sdss_i_z, sdss_g_i, n_obs)
"""
from __future__ import annotations

import argparse
import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd

from backend.ingest.schema import desig_key

SOURCE_URL = "https://faculty.washington.edu/ivezic/sdssmoc/ADR4.dat.gz"
RAW_PATH = Path("data/raw/sdss_colors.parquet")

# 0-based token indices in an ADR4 row (per the ADR4 readme). Verify if matches fail.
COLS = {
    "numeration": 4,   # asteroid number, 0 if unnumbered
    "designation": 5,  # provisional designation, '-' if none
    "u": 20, "g": 22, "r": 24, "i": 26, "z": 28,  # PSF magnitudes (errors sit in 21,23,25,27,29)
}


def _download(url: str) -> bytes:
    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def go() -> bytes:
        with httpx.Client(timeout=600.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.content

    return go()


def _lines(src) -> list[str]:
    if isinstance(src, (str, Path)) and Path(str(src)).exists():
        data = Path(src).read_bytes()
    else:
        data = src
    if isinstance(data, bytes) and data[:2] == b"\x1f\x8b":  # gzip magic
        data = gzip.decompress(data)
    if isinstance(data, bytes):
        data = data.decode("latin-1", errors="replace")
    return data.splitlines()


def parse(src) -> pd.DataFrame:
    rows = []
    need = max(COLS.values())
    for ln in _lines(src):
        t = ln.split()
        if len(t) <= need:
            continue
        try:
            num = int(t[COLS["numeration"]]); des = t[COLS["designation"]]
            ident = str(num) if num > 0 else des.replace("_", " ")
            key = desig_key(ident)
            if not key:
                continue
            u, g, r, i, z = (float(t[COLS[k]]) for k in ("u", "g", "r", "i", "z"))
            if min(u, g, r, i, z) < -90:  # MOC uses -99.99 for missing bands
                continue
            rows.append((key, g, r, i, z))
        except (ValueError, IndexError):
            continue
    df = pd.DataFrame(rows, columns=["desig_key", "g", "r", "i", "z"])
    if df.empty:
        raise SystemExit("[sdss_moc] parsed 0 rows. The column layout likely differs, "
                         "paste me the first data line of the file.")
    # SDSS asteroid colours: a* principal colour, plus i-z and g-i
    df["sdss_a_star"] = 0.89 * (df["g"] - df["r"]) + 0.45 * (df["r"] - df["i"]) - 0.57
    df["sdss_i_z"] = df["i"] - df["z"]
    df["sdss_g_i"] = df["g"] - df["i"]
    agg = df.groupby("desig_key").agg(
        sdss_a_star=("sdss_a_star", "median"), sdss_i_z=("sdss_i_z", "median"),
        sdss_g_i=("sdss_g_i", "median"), n_obs=("sdss_a_star", "size")).reset_index()
    return agg


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest SDSS Moving Object Catalog colours.")
    ap.add_argument("--url", default=SOURCE_URL)
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=RAW_PATH)
    args = ap.parse_args()

    src = args.file if args.file else _download(args.url)
    df = parse(src)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[sdss_moc] wrote {args.out}: {len(df)} asteroids with colours "
          f"(median {int(df['n_obs'].median())} obs each)")


if __name__ == "__main__":
    main()
