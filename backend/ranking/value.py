"""Transparent asteroid value estimate from size + spectral type.

Replaces Asterank's value field (which returns garbage for near-Earth objects).
The model is deliberately simple and AUDITABLE: map taxonomy to a compositional
complex, assume a bulk density and a coarse value-per-kg for that complex, and
multiply by mass. These are ORDER-OF-MAGNITUDE class factors, not an appraisal
(scope section 1), so every estimate ships with an explicit low/high band.

Two honesty mechanisms, both first-class outputs:
  - `value_is_estimate` is always True; value is never a measurement.
  - objects with NO measured spectrum (the ~99% majority) fall back to a default
    complex with a much wider band and `spec_is_assumed=True`. This is exactly
    the gap Phase 4's ML narrows.
"""

from __future__ import annotations

import math

from backend.ingest.schema import est_diameter_from_h

# Map Bus-DeMeo and Tholen classes to a compositional complex.
#   C = carbonaceous/primitive (water, volatiles, organics)
#   S = stony (silicates + minor metal)
#   M = metallic (iron-nickel + platinum-group metals) - the high-value target
_COMPLEX_OF = {
    # C-complex / primitive
    "B": "C", "C": "C", "Cb": "C", "Cg": "C", "Cgh": "C", "Ch": "C",
    "D": "C", "F": "C", "G": "C", "P": "C", "T": "C", "Xc": "C",
    # S-complex / stony
    "A": "S", "K": "S", "L": "S", "Q": "S", "R": "S", "S": "S", "Sa": "S",
    "Sq": "S", "Sr": "S", "Sv": "S", "V": "S", "O": "S", "E": "S", "Xe": "S",
    # M / metallic
    "M": "M", "Xk": "M",
    # bare X is ambiguous (E/M/P degenerate without albedo) - treat conservatively
    "X": "C",
}

# Bulk density by complex (kg/m^3).
_DENSITY = {"C": 1300.0, "S": 2700.0, "M": 5300.0}

# Coarse value-per-kg (USD). Order-of-magnitude, rationale:
#   M: iron-nickel bulk plus platinum-group metals at trace concentration.
#   S: silicates with minor recoverable metal / PGM.
#   C: water and volatiles, valued for in-space propellant, not Earth markets.
_VALUE_PER_KG = {"C": 100.0, "S": 200.0, "M": 5000.0}

# Default complex for objects with no measured taxonomy (most common NEO type).
DEFAULT_COMPLEX = "S"

# Typical geometric albedo by complex, used to turn absolute magnitude H into a
# diameter when no albedo is measured. Dark C, brighter S, intermediate M.
_ASSUMED_ALBEDO = {"C": 0.05, "S": 0.20, "M": 0.15}

# Multiplicative uncertainty factors, combined as type_factor * size_factor.
# value_low = value / U, value_high = value * U.
_UNC_TYPE = {                            # keyed on type_source
    "measured": 2.5,
    "ml-predicted": 3.5,
    "assumed": 5.0,
}
_UNC_SIZE = {                            # keyed on size_source
    "measured": 1.3,
    "h+albedo": 1.7,
    "h+assumed-albedo": 2.6,
}


def complex_of(spec_type: str | None) -> str | None:
    """Return the compositional complex (C/S/M) for a taxonomy string, or None."""
    if not spec_type:
        return None
    return _COMPLEX_OF.get(str(spec_type).strip())


def mass_kg(diameter_km: float | None, complex_: str) -> float | None:
    """Mass (kg) of a sphere of the given diameter at the complex's bulk density."""
    if diameter_km is None or diameter_km <= 0:
        return None
    radius_m = diameter_km * 1000.0 / 2.0
    volume_m3 = (4.0 / 3.0) * math.pi * radius_m**3
    return volume_m3 * _DENSITY[complex_]


def effective_diameter(
    diameter_km: float | None,
    h_mag: float | None,
    albedo: float | None,
    complex_: str,
) -> tuple[float | None, str | None]:
    """Best available diameter (km) and its provenance.

    Preference: measured diameter, then H + measured albedo, then H + an albedo
    assumed from the compositional complex. The last tier is what lets us size
    (and therefore value) nearly the whole catalogue, at a wider uncertainty.
    """
    if diameter_km is not None and diameter_km > 0:
        return float(diameter_km), "measured"
    if albedo is not None and albedo > 0:
        d = est_diameter_from_h(h_mag, albedo)
        if d is not None:
            return d, "h+albedo"
    d = est_diameter_from_h(h_mag, _ASSUMED_ALBEDO[complex_])
    if d is not None:
        return d, "h+assumed-albedo"
    return None, None


def resolve_complex(
    spec_type: str | None,
    ml_complex: str | None = None,
    ml_confidence: float | None = None,
    ml_threshold: float = 0.6,
) -> tuple[str, str]:
    """Resolve the compositional complex and its provenance.

    Priority: a measured spectral type, then a confident ML prediction, then the
    default assumption. Returns (complex, type_source) where type_source is one of
    "measured" / "ml-predicted" / "assumed".
    """
    measured = complex_of(spec_type)
    if measured is not None:
        return measured, "measured"
    if ml_complex in ("C", "S", "M") and (ml_confidence or 0) >= ml_threshold:
        return ml_complex, "ml-predicted"
    return DEFAULT_COMPLEX, "assumed"


def value_estimate(
    diameter_km: float | None,
    spec_type: str | None,
    h_mag: float | None = None,
    albedo: float | None = None,
    ml_complex: str | None = None,
    ml_confidence: float | None = None,
    ml_threshold: float = 0.6,
) -> dict:
    """Estimate body value (USD) with an uncertainty band and full provenance.

    A confident ML taxonomy prediction (>= ml_threshold) is used when no measured
    spectral type exists, at a wider uncertainty than measured but tighter than a
    blanket assumption. Returns value + band, complex_used, size_source,
    type_source, and spec_is_assumed (True for ml-predicted and assumed alike).
    """
    used_complex, type_source = resolve_complex(spec_type, ml_complex, ml_confidence, ml_threshold)
    assumed = type_source != "measured"

    diameter, size_source = effective_diameter(diameter_km, h_mag, albedo, used_complex)
    none_result = {
        "value_usd": None, "value_low": None, "value_high": None,
        "complex_used": used_complex, "size_source": None,
        "spec_is_assumed": assumed, "type_source": type_source,
    }
    if diameter is None:
        return none_result

    m = mass_kg(diameter, used_complex)
    if m is None:
        return none_result

    value = m * _VALUE_PER_KG[used_complex]
    unc = _UNC_TYPE[type_source] * _UNC_SIZE[size_source]
    return {
        "value_usd": value,
        "value_low": value / unc,
        "value_high": value * unc,
        "complex_used": used_complex,
        "size_source": size_source,
        "spec_is_assumed": assumed,
        "type_source": type_source,
    }
