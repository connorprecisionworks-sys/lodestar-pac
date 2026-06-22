"""Improvement experiments for the taxonomy classifier, written up in research
paper 02. All offline on the existing 116-object labelled set (albedo + dynamics).
Dumps data/models/experiments.json. Network-free.

  .venv/bin/python -m backend.ml.experiments
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import (
    cross_val_predict, cross_val_score, cross_validate, learning_curve, StratifiedKFold, RepeatedStratifiedKFold,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import f1_score, accuracy_score
from backend.ml import taxonomy as T

OUT = Path("data/models/experiments.json")
SEED = 42


def rf():
    return RandomForestClassifier(n_estimators=140, max_depth=4, min_samples_leaf=3,
                                  class_weight="balanced", random_state=SEED, n_jobs=1)


def ece(proba, classes, y_true, bins=10):
    """Expected calibration error on the top-1 prediction."""
    conf = proba.max(axis=1)
    pred = classes[proba.argmax(axis=1)]
    correct = (pred == y_true).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    e, n = 0.0, len(y_true)
    for i in range(bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1])
        if m.sum():
            e += (m.sum() / n) * abs(correct[m].mean() - conf[m].mean())
    return float(e)


def main():
    df, labeled, predict = T.load_frames()
    y = labeled["_label"].to_numpy()
    X = labeled[T.FEATURES_EXT].to_numpy(float)
    classes = np.array(sorted(set(y)))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    rkf = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED)
    out = {"n": int(len(y)), "features": T.FEATURES_EXT, "class_counts": {c: int((y == c).sum()) for c in classes}}

    # 1) model comparison (repeated stratified 5-fold): accuracy + macro-F1 in one pass
    cand = {
        "Most-frequent baseline": DummyClassifier(strategy="most_frequent"),
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random forest": rf(),
        "Gradient boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, max_iter=250, random_state=SEED),
    }
    models = []
    for name, m in cand.items():
        cv = cross_validate(m, X, y, cv=rkf, scoring=["accuracy", "f1_macro"], n_jobs=1)
        models.append({"name": name, "acc": round(float(cv["test_accuracy"].mean()), 4),
                       "acc_sd": round(float(cv["test_accuracy"].std()), 4),
                       "f1_macro": round(float(cv["test_f1_macro"].mean()), 4)})
    out["models"] = models

    rf_classes = np.array(sorted(set(y)))
    # 2/3) out-of-fold RF probabilities -> raw ECE, abstention curve, and calibration
    oof = cross_val_predict(rf(), X, y, cv=skf, method="predict_proba", n_jobs=1)
    conf = oof.max(axis=1)
    pred = rf_classes[oof.argmax(axis=1)]
    out["oof_accuracy"] = round(float((pred == y).mean()), 4)
    cal_block = {"ece_raw": round(ece(oof, rf_classes, y), 4)}
    try:  # sigmoid (Platt) + cv=2 tolerates the tiny metallic class
        cal = CalibratedClassifierCV(rf(), method="sigmoid", cv=2)
        oof_cal = cross_val_predict(cal, X, y, cv=StratifiedKFold(3, shuffle=True, random_state=SEED),
                                    method="predict_proba", n_jobs=1)
        cal_block["ece_calibrated"] = round(ece(oof_cal, rf_classes, y), 4)
    except Exception as ex:
        cal_block["ece_calibrated"] = None; cal_block["err"] = str(ex)[:80]
    out["calibration"] = cal_block

    abst = []
    for thr in [0.0, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]:
        keep = conf >= thr
        if keep.sum():
            abst.append({"thr": thr, "coverage": round(float(keep.mean()), 4),
                         "accuracy": round(float((pred[keep] == y[keep]).mean()), 4), "n": int(keep.sum())})
    out["abstention"] = abst
    OUT.write_text(json.dumps(out, indent=2))  # checkpoint

    # 4) learning curve (accuracy vs training size)
    try:
        sizes, _, test_sc = learning_curve(rf(), X, y, cv=skf, scoring="accuracy",
                                           train_sizes=np.linspace(0.35, 1.0, 5), n_jobs=1)
        out["learning_curve"] = [{"n": int(s), "cv_acc": round(float(test_sc[i].mean()), 4)} for i, s in enumerate(sizes)]
    except Exception as ex:
        out["learning_curve"] = []; out["lc_err"] = str(ex)[:80]
    OUT.write_text(json.dumps(out, indent=2))

    # 5) C-vs-S only (drop the albedo-unlearnable M): the learnable core
    mask = y != "M"
    accb = cross_val_score(rf(), X[mask], y[mask],
                           cv=RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED),
                           scoring="accuracy", n_jobs=1)
    out["c_vs_s"] = {"n": int(mask.sum()), "acc": round(float(accb.mean()), 4)}

    OUT.write_text(json.dumps(out, indent=2))
    print("WROTE", OUT)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
