"""Run the taxonomy LOO eval once and dump real metrics to JSON for the
research page charts. Network-free; reads the same parquet the model uses."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from backend.ml import taxonomy as T

OUT = Path("data/models/ml_metrics.json")


def main() -> None:
    df, labeled, predict = T.load_frames()
    y = labeled["_label"].to_numpy()
    Xb = labeled[T.FEATURES_BASE].to_numpy(float)
    Xe = labeled[T.FEATURES_EXT].to_numpy(float)
    pb, cb = T._loo(Xb, y)
    pe, ce = T._loo(Xe, y)
    acc_b = float((pb == y).mean())
    acc_e = float((pe == y).mean())
    base = float(pd.Series(y).value_counts(normalize=True).max())
    use_ext = acc_e > acc_b
    preds, conf = (pe, ce) if use_ext else (pb, cb)
    acc = acc_e if use_ext else acc_b
    feats = T.FEATURES_EXT if use_ext else T.FEATURES_BASE

    labels = [c for c in T.CLASSES if c in set(y)]
    cm = confusion_matrix(y, preds, labels=labels).tolist()

    # calibration buckets
    calib = []
    for lo, hi in [(0.0, 0.5), (0.5, 0.7), (0.7, 1.01)]:
        mask = (conf >= lo) & (conf < hi)
        if mask.sum():
            calib.append({
                "lo": lo, "hi": min(hi, 1.0), "n": int(mask.sum()),
                "acc": float((np.asarray(preds)[mask] == y[mask]).mean()),
            })

    # feature importance from the full-fit model
    X = labeled[feats].to_numpy(float)
    model = T._model().fit(X, y)
    imp = sorted(
        [{"feature": f, "importance": float(i)} for f, i in zip(feats, model.feature_importances_)],
        key=lambda d: -d["importance"],
    )

    # predicted distribution on unmeasured objects
    pred_out = pd.read_parquet(T.OUT)
    dist = {k: int(v) for k, v in pred_out["ml_complex"].value_counts().items()}
    conf_pred = pred_out["ml_confidence"]

    out = {
        "n_train": int(len(labeled)),
        "n_predicted": int(len(pred_out)),
        "n_measured_before": int(len(labeled)),
        "accuracy": round(acc, 4),
        "accuracy_base": round(acc_b, 4),
        "accuracy_ext": round(acc_e, 4),
        "baseline": round(base, 4),
        "use_ext": bool(use_ext),
        "classes": labels,
        "confusion": cm,
        "per_class_recall": {
            labels[i]: round(cm[i][i] / sum(cm[i]), 4) if sum(cm[i]) else 0.0
            for i in range(len(labels))
        },
        "calibration": calib,
        "feature_importance": imp,
        "pred_distribution": dist,
        "pred_conf_median": round(float(conf_pred.median()), 3),
        "pred_conf_ge70_frac": round(float((conf_pred >= 0.7).mean()), 4),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print("WROTE", OUT)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
