"""Normalized schema for the Lodestar asteroid store.

This module is the single contract every ingestion source maps onto. It defines
the columns of `data/processed/asteroids.parquet` and the helpers that keep the
join keys and honesty flags consistent across sources.

Design rule from the scope doc (sections 1 and 4): every value/composition figure
is an *estimate*, not a measurement. That is enforced here with explicit
`*_source` provenance columns and `*_is_estimate` flags, never hidden.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Column contract for data/processed/asteroids.parquet
# ---------------------------------------------------------------------------
# Identity
ID_COLUMNS = [
    "desig_key",     # canonical join key (see desig_key())
    "full_name",     # human-readable designation, e.g. "433 Eros (A898 PA)"
    "number",        # asteroid number when numbered, else None
    "pdes",          # primary designation, e.g. "433" or "2010 AB"
]

# Orbit + physical (authoritative source: JPL SBDB, current)
ORBIT_COLUMNS = [
    "a_au",          # semi-major axis (au)
    "e",             # eccentricity
    "i_deg",         # inclination (deg)
    "om_deg",        # longitude of ascending node (deg)
    "w_deg",         # argument of perihelion (deg)
    "ma_deg",        # mean anomaly (deg)
    "per_days",      # orbital period (days)
    "moid_au",       # minimum orbit intersection distance w/ Earth (au)
    "q_au",          # perihelion distance (au)
]
PHYSICAL_COLUMNS = [
    "H_mag",         # absolute magnitude
    "albedo",        # geometric albedo (measured where available)
    "diameter_km",   # measured diameter (km) where available
    "est_diameter_km",  # diameter derived from H+albedo when not measured
    "neo",           # near-Earth object flag
    "pha",           # potentially hazardous flag
    "orbit_class",   # SBDB orbit class code (AMO/APO/ATE/IEO ...)
]

# Spectral / taxonomy (measured for a small minority - this is the whole point of Layer 2)
SPECTRAL_COLUMNS = [
    "spec_type",     # Bus-DeMeo class preferred, else Tholen; None if unmeasured
    "spec_source",   # "measured:bus-demeo" | "measured:tholen" | "none"
]

# Asterank baseline, carried for sanity comparison only. Its value field is
# UNRELIABLE for near-Earth objects (returns ~1e-42 garbage); its delta-v is the
# Benner table and IS reliable where present. Neither is treated as authoritative.
ASTERANK_COLUMNS = [
    "asterank_value_usd",   # Asterank value field (unreliable for NEOs - baseline only)
    "asterank_dv_kms",      # Asterank delta-v (Benner; reliable where present)
]

# What the ingestion join (normalize.py) produces.
INGEST_COLUMNS = (
    ID_COLUMNS + ORBIT_COLUMNS + PHYSICAL_COLUMNS + SPECTRAL_COLUMNS + ASTERANK_COLUMNS
)

# Computed value + accessibility, added by the enrich step. Every figure is an
# estimate with an explicit uncertainty band and a provenance source.
VALUE_COLUMNS = [
    "value_usd",        # our computed value estimate (order-of-magnitude)
    "value_low",        # lower bound of the uncertainty band
    "value_high",       # upper bound of the uncertainty band
    "value_complex",    # compositional complex used (C/S/M)
    "size_source",      # "measured" | "h+albedo" | "h+assumed-albedo"
    "spec_is_assumed",  # True when taxonomy was assumed, not measured
    "value_source",     # "computed:spectral-model" | "none"
    "value_is_estimate",  # ALWAYS True - never a measurement
]
DELTAV_COLUMNS = [
    "dv_kms",           # best available delta-v (km/s)
    "dv_source",        # "asterank-benner" | "computed:hohmann-proxy" | "none"
    "dv_rel_unc",       # relative uncertainty on dv (0 for Benner table)
]

# Final enriched store the ranking engine + API serve.
ENRICHED_COLUMNS = INGEST_COLUMNS + VALUE_COLUMNS + DELTAV_COLUMNS

# Back-compat alias for the ingestion-stage column set.
ALL_COLUMNS = INGEST_COLUMNS

# Near-Earth orbit class codes per JPL SBDB.
NEO_ORBIT_CLASSES = ["IEO", "ATE", "APO", "AMO"]


# ---------------------------------------------------------------------------
# Join key
# ---------------------------------------------------------------------------
_YEAR = r"(?:1[89]\d{2}|20\d{2})"                           # plausible year 1800-2099
_BARE_NUM_RE = re.compile(r"^\(?(\d+)\)?$")                 # "433", "(433)"
_NUM_NAME_RE = re.compile(r"^\(?(\d+)\)?\s+\S")             # "433 Eros", "(433) Eros"
# A string that is ENTIRELY a provisional designation, e.g. "2010 AB", "(2010 AB)",
# "2010 AB1". Anchored, so "2001 Einstein" (a numbered body) does not match here.
_WHOLE_PROV_RE = re.compile(rf"^\(?({_YEAR}\s?[A-Za-z]{{2}}\d*)\)?$")
# A provisional embedded anywhere (last-resort), bounded so it won't grab a name.
_PROV_RE = re.compile(rf"({_YEAR}\s?[A-Za-z]{{2}}\d*)(?![A-Za-z\d])")


def desig_key(full_name: str | None) -> str | None:
    """Return a canonical join key from a designation string.

    Numbered objects key on their number ("n:433"); unnumbered objects key on a
    whitespace-stripped provisional designation ("p:2010ab"). Both sides of a
    join (SBDB and Asterank) pass through this function so keys agree even when
    the raw strings differ in punctuation.

    Order matters: a bare number first, then the provisional year-pattern, and
    only then number-plus-name, so "2010 AB" is read as provisional rather than
    as asteroid 2010.
    """
    if not full_name:
        return None
    s = str(full_name).strip()

    m = _BARE_NUM_RE.match(s)
    if m:
        return f"n:{int(m.group(1))}"

    m = _WHOLE_PROV_RE.match(s)
    if m:
        return "p:" + re.sub(r"\s+", "", m.group(1)).lower()

    m = _NUM_NAME_RE.match(s)
    if m:
        return f"n:{int(m.group(1))}"

    m = _PROV_RE.search(s)
    if m:
        return "p:" + re.sub(r"\s+", "", m.group(1)).lower()

    # Fallback: collapse to a slug so something is still joinable.
    slug = re.sub(r"[^a-z0-9]+", "", s.lower())
    return f"s:{slug}" if slug else None


def est_diameter_from_h(h_mag: float | None, albedo: float | None) -> float | None:
    """Estimate diameter (km) from absolute magnitude and albedo.

    Standard relation: D = 1329 / sqrt(albedo) * 10^(-H/5), in km.
    Used only to fill a gap when no measured diameter exists; the result lands in
    `est_diameter_km`, kept separate from the measured `diameter_km`.
    """
    if h_mag is None or albedo is None:
        return None
    try:
        h = float(h_mag)
        p = float(albedo)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return 1329.0 / (p**0.5) * (10.0 ** (-h / 5.0))
