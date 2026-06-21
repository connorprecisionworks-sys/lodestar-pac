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
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import LeaveOneOut

from backend.ranking.value import complex_of

STORE = Path("data/processed/asteroids.parquet")  # normalized store (pre-enrich)
OUT = Path("data/models/taxonomy_predictions.parquet")
FEATURES = ["albedo", "H_mag", "a_au", "e", "i_deg"]
CLASSES = ["C", "S", "M"]


def _model() -> RandomForestClassifier:
    # shallow + balanced: the training set is small and S-heavy, so we cap depth
    # to avoid memorising and weight classes so C/M are not ignored.
    return RandomForestClassifier(
        n_estimators=400, max_depth=4, min_samples_leaf=3,
        class_weight="balanced", random_state=42,
    )


def load_frames():
    df = pd.read_parquet(STORE)
    df["_label"] = df["spec_type"].map(
        lambda s: complex_of(None if pd.isna(s) else str(s))
    )  # C/S/M or None (unmeasured)
    feat_ok = df[FEATURES].notna().all(axis=1)
    labeled = df[feat_ok & df["_label"].notna()].copy()
    predict = df[feat_ok & df["_label"].isna()].copy()
    return df, labeled, predict


def evaluate(X: np.ndarray, y: np.ndarray) -> None:
    """Leave-one-out cross-validation (honest for a tiny dataset)."""
    loo = LeaveOneOut()
    preds = np.empty(len(y), dtype=object)
    for tr, te in loo.split(X):
        m = _model().fit(X[tr], y[tr])
        preds[te[0]] = m.predict(X[te])[0]
    labels = [c for c in CLASSES if c in set(y)]
    print("\n[taxonomy] ---- leave-one-out cross-validation ----")
    print(f"  trained on {len(y)} labelled objects (features: {', '.join(FEATURES)})")
    base = pd.Series(y).value_counts(normalize=True).max()
    acc = (preds == y).mean()
    print(f"  accuracy: {acc:.0%}   (majority-class baseline: {base:.0%})")
    print("  confusion matrix (rows = true, cols = predicted):")
    cm = confusion_matrix(y, preds, labels=labels)
    print("        " + "  ".join(f"{c:>4}" for c in labels))
    for c, row in zip(labels, cm, strict=True):
        print(f"    {c:>3} " + "  ".join(f"{v:>4}" for v in row))
    print(classification_report(y, preds, labels=labels, zero_division=0))


def main() -> None:
    df, labeled, predict = load_frames()
    X = labeled[FEATURES].to_numpy(float)
    y = labeled["_label"].to_numpy()
    print(f"[taxonomy] labelled+albedo: {len(labeled)} | albedo-only to predict: {len(predict)}")

    evaluate(X, y)

    model = _model().fit(X, y)
    Xp = predict[FEATURES].to_numpy(float)
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
