"""Enriched taxonomy model: trains on albedo + dynamics PLUS the new infrared and
colour features, and reports how much they helped versus the albedo-only model.

Uses HistGradientBoosting, which handles missing features natively, so an object
without SDSS colours or a NEOWISE albedo is still scored on whatever it does have.

    uv run python -m backend.ml.taxonomy_enriched

Reads  data/processed/asteroids.parquet (after enrich_features)
Writes data/models/taxonomy_predictions.parquet  (desig_key, ml_complex, ml_confidence)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneOut

from backend.ml import taxonomy as T

OUT = Path("data/models/taxonomy_predictions.parquet")
OPTIONAL = ["ir_albedo", "nir_v_ratio", "sdss_a_star", "sdss_i_z", "sdss_g_i"]
MIN_COV = 20  # need at least this many labelled objects with the feature to include it


def _hgb():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, max_iter=300,
                                          class_weight="balanced", random_state=42)


def _loo(model_fn, X, y):
    loo = LeaveOneOut(); preds = np.empty(len(y), object); conf = np.empty(len(y))
    for tr, te in loo.split(X):
        m = model_fn().fit(X[tr], y[tr]); p = m.predict_proba(X[te])[0]
        preds[te[0]] = m.classes_[p.argmax()]; conf[te[0]] = p.max()
    return preds, conf


def main() -> None:
    df = T.add_derived(pd.read_parquet(T.STORE))
    df["_label"] = df["spec_type"].map(lambda s: T.complex_of(None if pd.isna(s) else str(s)))
    feat_ok = df[T.FEATURES_BASE].notna().all(axis=1)
    labeled = df[feat_ok & df["_label"].notna()].copy()
    y = labeled["_label"].to_numpy()

    available = [c for c in OPTIONAL if c in df.columns and int(labeled[c].notna().sum()) >= MIN_COV]
    feats = T.FEATURES_EXT + available
    print(f"[enriched] labelled objects: {len(labeled)} (was 116 at albedo-only baseline)")
    print(f"[enriched] new features in play: {available or 'NONE yet — run the ingestion + enrich_features first'}")

    # baseline: albedo + dynamics, random forest (the current production model)
    Xb = labeled[T.FEATURES_EXT].to_numpy(float)
    pb, _ = _loo(T._model, Xb, y)
    acc_base = float((pb == y).mean())

    if available:
        Xe = labeled[feats].to_numpy(float)
        pe, ce = _loo(_hgb, Xe, y)
        acc_ext = float((pe == y).mean())
        preds, conf, model_fn, use = pe, ce, _hgb, feats
    else:
        pe, ce = pb, None
        acc_ext = acc_base
        preds, conf, model_fn, use = pb, None, T._model, T.FEATURES_EXT

    labels = [c for c in T.CLASSES if c in set(y)]
    cm = confusion_matrix(y, preds, labels=labels)
    print(f"\n[enriched] LOO accuracy  albedo-only {acc_base:.0%}  ->  enriched {acc_ext:.0%}  "
          f"({'+' if acc_ext >= acc_base else ''}{(acc_ext - acc_base) * 100:.1f} pts)")
    print("  per-class recall:")
    for i, c in enumerate(labels):
        tot = cm[i].sum()
        print(f"    {c}: {cm[i][i] / tot:.0%}" if tot else f"    {c}: n/a")

    # fit on all labelled, predict the albedo-only-known objects
    model = model_fn().fit(labeled[use].to_numpy(float), y)
    predict = df[feat_ok & df["_label"].isna()].copy()
    proba = model.predict_proba(predict[use].to_numpy(float))
    classes = list(model.classes_)
    out = pd.DataFrame({
        "desig_key": predict["desig_key"].to_numpy(),
        "ml_complex": [classes[i] for i in proba.argmax(axis=1)],
        "ml_confidence": proba.max(axis=1).round(3),
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"\n[enriched] wrote {OUT}: {len(out)} predictions "
          f"(median conf {out['ml_confidence'].median():.2f})")


if __name__ == "__main__":
    main()
