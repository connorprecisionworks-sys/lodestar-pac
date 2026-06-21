"""Tests for the transparent value model + its uncertainty handling."""

from __future__ import annotations

from backend.ranking.value import complex_of, mass_kg, resources, value_estimate


def test_complex_mapping():
    assert complex_of("M") == "M"
    assert complex_of("C") == "C"
    assert complex_of("S") == "S"
    assert complex_of("Ch") == "C"
    assert complex_of("V") == "S"
    assert complex_of(None) is None
    assert complex_of("???") is None


def test_metal_is_most_valuable_same_size():
    d = 1.0  # km
    m = value_estimate(d, "M")["value_usd"]
    s = value_estimate(d, "S")["value_usd"]
    c = value_estimate(d, "C")["value_usd"]
    # metallic dominates (dense + platinum-group); C and S are far lower
    assert m > s and m > c


def test_resources_match_composition():
    mass = mass_kg(1.0, "M")  # kg
    r_m = resources(mass, "M")
    r_c = resources(mass_kg(1.0, "C"), "C")
    # metallic has platinum-group + iron, ~no water; carbon has water, no PGM
    assert r_m["pgm_kg"] > 0 and r_m["metal_tons"] > 0 and r_m["water_tons"] == 0
    assert r_c["water_tons"] > 0 and r_c["pgm_kg"] == 0
    # resource tonnage scales with mass
    assert resources(2 * mass, "M")["metal_tons"] == 2 * r_m["metal_tons"]


def test_value_scales_with_volume():
    small = value_estimate(1.0, "S")["value_usd"]
    big = value_estimate(2.0, "S")["value_usd"]
    # diameter doubled -> mass (and value) ~8x
    assert abs(big / small - 8.0) < 1e-6


def test_measured_vs_assumed_band():
    measured = value_estimate(1.0, "S")
    assumed = value_estimate(1.0, None)
    assert measured["spec_is_assumed"] is False
    assert assumed["spec_is_assumed"] is True
    assert assumed["complex_used"] == "S"          # default complex
    # assumed type carries a strictly wider relative band
    m_ratio = measured["value_high"] / measured["value_low"]
    a_ratio = assumed["value_high"] / assumed["value_low"]
    assert a_ratio > m_ratio


def test_band_brackets_estimate():
    r = value_estimate(0.5, "M")
    assert r["value_low"] < r["value_usd"] < r["value_high"]


def test_size_provenance_tiers():
    # measured diameter wins
    assert value_estimate(1.0, "S", h_mag=18.0, albedo=0.2)["size_source"] == "measured"
    # no diameter but H + measured albedo
    r = value_estimate(None, "S", h_mag=18.0, albedo=0.2)
    assert r["size_source"] == "h+albedo"
    assert r["value_usd"] > 0
    # no diameter, no albedo: H + assumed albedo (this is what gives coverage)
    r = value_estimate(None, "S", h_mag=18.0, albedo=None)
    assert r["size_source"] == "h+assumed-albedo"
    assert r["value_usd"] > 0


def test_wider_band_when_size_assumed():
    measured = value_estimate(1.0, "S")
    h_sized = value_estimate(None, "S", h_mag=18.0, albedo=None)
    m_ratio = measured["value_high"] / measured["value_low"]
    h_ratio = h_sized["value_high"] / h_sized["value_low"]
    assert h_ratio > m_ratio


def test_no_size_no_value():
    # no diameter and no H -> nothing to size from
    r = value_estimate(None, "M", h_mag=None, albedo=None)
    assert r["value_usd"] is None
    assert r["value_low"] is None
