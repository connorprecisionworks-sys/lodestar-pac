"""Layer 2 (Phase 4) baseline: albedo-based taxonomy classifier.

Predicts compositional complex (C / S / M) + calibrated confidence for objects
that have a measured albedo but no measured spectrum, trained on the small set
with both a label and an albedo. This is the honest first cut of the ML layer:

  - Albedo is the one physically strong feature we have (dark C vs bright S).
  - The training set is tiny (~116) and imbalanced; metallic (M) is essentially
    unlearnable from albedo (X-complex is albedo-degenerate) and is reported as
    unreliable, not hidden.
  - The real differentiator needs colour/spectral data (Rubin / SDSS); this
    pipeline is built to extend to those features when they are ingested.

    uv run --extra ml python -m backend.ml.taxonomy

Input  : data/processed/asteroids_enriched.parquet
Output : data/models/taxonomy_predictions.parquet  (desig_key, ml_complex, ml_confidence)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneOut

from backend.ranking.value import complex_of

STORE = Path("data/processed/asteroids.parquet")  # normalized store (pre-enrich)
OUT = Path("data/models/taxonomy_predictions.parquet")
FEATURES_BASE = ["albedo", "H_mag", "a_au", "e", "i_deg"]
DERIVED = ["tisserand", "q_au", "Q_au"]
FEATURES_EXT = FEATURES_BASE + DERIVED
FEATURES = FEATURES_BASE  # kept for the test import
CLASSES = ["C", "S", "M"]
A_JUP = 5.204  # AU


def _model() -> RandomForestClassifier:
    # shallow + balanced: the training set is small and S-heavy, so we cap depth
    # to avoid memorising and weight classes so C/M are not ignored.
    return RandomForestClassifier(
        n_estimators=200, max_depth=4, min_samples_leaf=3,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Dynamical features: Tisserand parameter wrt Jupiter, perihelion, aphelion."""
    a, e = df["a_au"], df["e"]
    i = np.radians(df["i_deg"])
    df["tisserand"] = A_JUP / a + 2 * np.cos(i) * np.sqrt((a / A_JUP) * (1 - e**2))
    df["q_au"] = a * (1 - e)
    df["Q_au"] = a * (1 + e)
    return df


def load_frames():
    df = pd.read_parquet(STORE)
    df["_label"] = df["spec_type"].map(
        lambda s: complex_of(None if pd.isna(s) else str(s))
    )  # C/S/M or None (unmeasured)
    df = add_derived(df)
    feat_ok = df[FEATURES_BASE].notna().all(axis=1)
    labeled = df[feat_ok & df["_label"].notna()].copy()
    predict = df[feat_ok & df["_label"].isna()].copy()
    return df, labeled, predict


def _loo(X: np.ndarray, y: np.ndarray):
    """Leave-one-out predictions + out-of-fold max-probabilities."""
    loo = LeaveOneOut()
    preds = np.empty(len(y), dtype=object)
    conf = np.empty(len(y), dtype=float)
    for tr, te in loo.split(X):
        m = _model().fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[0]
        preds[te[0]] = m.classes_[p.argmax()]
        conf[te[0]] = p.max()
    return preds, conf


def evaluate(X: np.ndarray, y: np.ndarray, name: str):
    preds, conf = _loo(X, y)
    acc = (preds == y).mean()
    base = pd.Series(y).value_counts(normalize=True).max()
    print(f"  [{name:9}] LOO accuracy {acc:.0%}  (baseline {base:.0%})")
    return acc, preds, conf


def reliability(y, preds, conf) -> None:
    print("  confidence reliability (LOO):")
    for lo, hi in [(0.0, 0.5), (0.5, 0.7), (0.7, 1.01)]:
        mask = (conf >= lo) & (conf < hi)
        if mask.sum():
            a = (preds[mask] == y[mask]).mean()
            top = min(hi, 1.0)
            print(f"    conf {lo:.1f}-{top:.1f}: {int(mask.sum()):>3} objs, accuracy {a:.0%}")


def main() -> None:
    df, labeled, predict = load_frames()
    y = labeled["_label"].to_numpy()
    print(f"[taxonomy] labelled+albedo: {len(labeled)} | albedo-only to predict: {len(predict)}")

    print("\n[taxonomy] ---- feature-set comparison (leave-one-out) ----")
    Xb = labeled[FEATURES_BASE].to_numpy(float)
    Xe = labeled[FEATURES_EXT].to_numpy(float)
    acc_b, pb, cb = evaluate(Xb, y, "albedo+orb")
    acc_e, pe, ce = evaluate(Xe, y, "+dynamical")

    # keep the dynamical features only if they actually help (reuse the LOO above)
    use_ext = acc_e > acc_b
    feats, preds, conf = (FEATURES_EXT, pe, ce) if use_ext else (FEATURES_BASE, pb, cb)
    print("  -> using " + ("extended (dynamical features help)" if use_ext
                            else "base (dynamical features did not help)"))

    X = labeled[feats].to_numpy(float)
    labels = [c for c in CLASSES if c in set(y)]
    print("  confusion (rows=true, cols=pred): " + " ".join(labels))
    cm = confusion_matrix(y, preds, labels=labels)
    for c, row in zip(labels, cm, strict=True):
        print(f"    {c:>3} " + "  ".join(f"{v:>3}" for v in row))
    reliability(y, np.asarray(preds), conf)

    model = _model().fit(X, y)
    Xp = predict[feats].to_numpy(float)
    proba = model.predict_proba(Xp)
    classes = list(model.classes_)
    idx = proba.argmax(axis=1)
    out = pd.DataFrame({
        "desig_key": predict["desig_key"].to_numpy(),
        "ml_complex": [classes[i] for i in idx],
        "ml_confidence": proba.max(axis=1).round(3),
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    print("\n[taxonomy] ---- predictions for albedo-only objects ----")
    vc = out["ml_complex"].value_counts()
    print("  predicted complex distribution:")
    print("    " + " ".join(f"{k}:{v}" for k, v in vc.items()))
    conf = out["ml_confidence"]
    print(f"  confidence: median {conf.median():.2f}, "
          f">=0.7 on {int((conf >= 0.7).sum())} objects ({(conf >= 0.7).mean():.0%})")
    print("  NOTE: M (metallic) predictions are not reliable from albedo alone "
          "(needs radar/spectra) - treat as a weak prior only.")
    print(f"[taxonomy] wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()
