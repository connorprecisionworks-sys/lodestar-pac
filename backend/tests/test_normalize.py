"""Network-free verification of the normalization layer.

Fixtures mimic the raw shapes SBDB and Asterank return, so the join, type
coercion, derived fields, and provenance flags are all exercised without any
live data. The live pull itself is verified by Connor on his Mac.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.ingest.normalize import merge, normalize_asterank, normalize_sbdb
from backend.ingest.schema import INGEST_COLUMNS, desig_key, est_diameter_from_h


@pytest.fixture
def sbdb_raw() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "full_name": "433 Eros (A898 PA)", "pdes": "433", "neo": "Y", "pha": "N",
                "class": "AMO", "H": "10.4", "diameter": "16.84", "albedo": "0.25",
                "spec_B": "S", "spec_T": "S", "a": "1.458", "e": "0.223", "i": "10.83",
                "om": "304.3", "w": "178.9", "ma": "320.2", "per": "643.0",
                "moid": "0.149", "q": "1.133",
            },
            {
                "full_name": "(2010 AB)", "pdes": "2010 AB", "neo": "Y", "pha": "N",
                "class": "APO", "H": "22.1", "diameter": None, "albedo": "0.15",
                "spec_B": None, "spec_T": None, "a": "1.92", "e": "0.51", "i": "3.2",
                "om": "120.0", "w": "45.0", "ma": "10.0", "per": "970.0",
                "moid": "0.03", "q": "0.94",
            },
        ]
    )


@pytest.fixture
def asterank_raw() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"full_name": "433 Eros", "price": 1e16, "profit": 5e15, "dv": 5.0, "spec_B": "S"},
            {"full_name": "(2011 XY)", "price": 1e12, "profit": 1e11, "dv": 4.0, "spec_B": "C"},
        ]
    )


def test_desig_key_numbered_forms_agree():
    assert desig_key("433 Eros (A898 PA)") == "n:433"
    assert desig_key("433 Eros") == "n:433"
    assert desig_key("(433) Eros") == "n:433"


def test_desig_key_provisional():
    assert desig_key("(2010 AB)") == "p:2010ab"
    assert desig_key("2010 AB") == "p:2010ab"
    assert desig_key("2010 AB1") == "p:2010ab1"


def test_desig_key_numbered_with_embedded_provisional():
    # SBDB appends the historical provisional in parens for numbered bodies;
    # the leading number must still win.
    assert desig_key("4179 Toutatis (1989 AC)") == "n:4179"
    assert desig_key("101955 Bennu (1999 RQ36)") == "n:101955"
    assert desig_key("2001 Einstein") == "n:2001"   # numbered, not provisional


def test_desig_key_none():
    assert desig_key(None) is None
    assert desig_key("") is None


def test_est_diameter_relation():
    d = est_diameter_from_h(22.1, 0.15)
    assert d is not None and d > 0
    # matches D = 1329/sqrt(p) * 10^(-H/5)
    assert math.isclose(d, 1329 / math.sqrt(0.15) * 10 ** (-22.1 / 5), rel_tol=1e-9)


def test_est_diameter_guards():
    assert est_diameter_from_h(None, 0.2) is None
    assert est_diameter_from_h(15.0, 0.0) is None
    assert est_diameter_from_h(15.0, None) is None


def test_normalize_sbdb_fields(sbdb_raw):
    out = normalize_sbdb(sbdb_raw)
    eros = out[out["desig_key"] == "n:433"].iloc[0]
    assert eros["number"] == 433
    assert eros["neo"] is True or eros["neo"] == True  # noqa: E712
    assert eros["orbit_class"] == "AMO"
    assert math.isclose(eros["a_au"], 1.458, rel_tol=1e-6)
    assert eros["spec_type"] == "S"
    assert eros["spec_source"] == "measured:bus-demeo"
    # measured diameter present -> no estimate filled
    assert pd.isna(eros["est_diameter_km"])

    ab = out[out["desig_key"] == "p:2010ab"].iloc[0]
    assert pd.isna(ab["diameter_km"])
    assert ab["est_diameter_km"] > 0          # derived from H + albedo
    assert ab["spec_source"] == "none"


def test_merge_asterank_baseline(sbdb_raw, asterank_raw):
    df = merge(normalize_sbdb(sbdb_raw), normalize_asterank(asterank_raw))
    assert list(df.columns) == INGEST_COLUMNS

    eros = df[df["desig_key"] == "n:433"].iloc[0]
    assert eros["asterank_value_usd"] == 1e16   # baseline only, untrusted
    assert eros["asterank_dv_kms"] == 5.0       # Benner reference

    ab = df[df["desig_key"] == "p:2010ab"].iloc[0]
    assert pd.isna(ab["asterank_value_usd"])    # no Asterank match
    assert pd.isna(ab["asterank_dv_kms"])


def test_merge_does_not_inflate_rows(sbdb_raw, asterank_raw):
    # left join on a deduped right side must preserve the SBDB row count
    df = merge(normalize_sbdb(sbdb_raw), normalize_asterank(asterank_raw))
    assert len(df) == len(sbdb_raw)
