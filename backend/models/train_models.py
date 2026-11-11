"""Train + evaluate + persist the three ML models.   Run: python backend/models/train_models.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error, mean_squared_error,
                             r2_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from models.features import *

OUT = ROOT / "saved_models"


def train_all(verbose=True):
    OUT.mkdir(exist_ok=True)
    log = print if verbose else (lambda *a, **k: None)
    df = load_dataset()                                    # 1. dedupe, trim, numeric conversion
    log(f"Loaded {len(df)} rows, {df['key'].nunique()} unique issues, {df['sprint'].nunique()} sprints")
    median_pts = float(df["storyPoint"].dropna().median())
    df["points"] = df["storyPoint"].fillna(median_pts)     # 2. missing values (only for aggregate features)
    meta = {"median_points": median_pts}

    # ---------------- Module 1: Story points (Random Forest Regressor) ----------------
    s = df.dropna(subset=["storyPoint"]).drop_duplicates("key")   # one row per issue -> no leakage across split
    X = pd.DataFrame([story_features(r.summary, r.description, r.priority, r.issueType) for r in s.itertuples()])
    y = s["storyPoint"].values
    pre = ColumnTransformer([
        ("tfidf", TfidfVectorizer(max_features=500, ngram_range=(1, 2), stop_words="english"), "text"),
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["issue_type"]),
        ("num", "passthrough", STORY_NUM)])
    sp = Pipeline([("pre", pre), ("rf", RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42))])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    sp.fit(Xtr, ytr)
    p = sp.predict(Xte)
    cv = -cross_val_score(sp, X, y, cv=5, scoring="neg_mean_absolute_error").mean()
    meta["story_point_metrics"] = {
        "train_size": len(Xtr), "test_size": len(Xte),
        "MAE": round(mean_absolute_error(yte, p), 3),
        "RMSE": round(float(np.sqrt(mean_squared_error(yte, p))), 3),
        "R2": round(r2_score(yte, p), 3), "CV_MAE_5fold": round(float(cv), 3),
        "baseline_MAE_median": round(mean_absolute_error(yte, np.full_like(yte, np.median(ytr))), 3)}
    log("Story point model:", meta["story_point_metrics"])
    sp.fit(X, y)                                           # refit on all labelled data for serving
    joblib.dump(sp, OUT / "story_point_model.pkl")

    # ---------------- Module 2: Sprint success (Random Forest Classifier) ----------------
    st = sprint_table(df)
    meta["avg_velocity"] = round(float(st["completed_points"].tail(8).mean()), 1)
    meta["workload_p75"] = float(st["total_points"].quantile(.75))
    meta["workload_p90"] = float(st["total_points"].quantile(.90))
    A, b = st[SPRINT_FEATS], st["success"]
    strat = b if b.value_counts().min() >= 2 else None
    Atr, Ate, btr, bte = train_test_split(A, b, test_size=0.25, random_state=42, stratify=strat)
    sc = RandomForestClassifier(n_estimators=300, max_depth=5, class_weight="balanced", random_state=42).fit(Atr, btr)
    pr = sc.predict(Ate)
    m = {"sprints": len(st), "success_rate": round(float(b.mean()), 3),
         "accuracy": round(accuracy_score(bte, pr), 3), "f1": round(f1_score(bte, pr, zero_division=0), 3)}
    if bte.nunique() > 1:
        m["roc_auc"] = round(roc_auc_score(bte, sc.predict_proba(Ate)[:, 1]), 3)
    meta["sprint_success_metrics"] = m
    log("Sprint success model:", m)
    sc.fit(A, b)
    joblib.dump(sc, OUT / "sprint_success_model.pkl")

    # ---------------- Module 3: Risk (Decision Tree Classifier) ----------------
    wl = df.groupby("sprint")["points"].transform("sum")
    R = pd.DataFrame({"story_points": df["points"], "priority": df["priority"],
                      "blocked_issues": df["blockedBy"],
                      "dependency_count": df["dependedOn"] + df["dependedOnBy"] + df["blocks"],
                      "sprint_workload": wl})
    sc_ = [risk_score(r.story_points, r.priority, r.blocked_issues, r.dependency_count, r.sprint_workload,
                      meta["workload_p75"], meta["workload_p90"]) for r in R.itertuples()]
    lab = pd.Series([risk_level_from_score(v) for v in sc_])
    log("Risk label distribution (real rows):", lab.value_counts().to_dict())
    # The real data has very few high-risk cases, so training is augmented with synthetic scenarios that span the
    # realistic input ranges (labelled with the same rubric). Evaluation uses only held-out REAL stories.
    rng = np.random.default_rng(42)
    n = 2500
    S = pd.DataFrame({"story_points": rng.choice(FIB, n), "priority": rng.integers(1, 5, n),
                      "blocked_issues": rng.integers(0, 7, n), "dependency_count": rng.integers(0, 11, n),
                      "sprint_workload": rng.uniform(5, meta["workload_p90"] * 1.6, n)})
    Slab = pd.Series([risk_level_from_score(risk_score(r.story_points, r.priority, r.blocked_issues, r.dependency_count,
                      r.sprint_workload, meta["workload_p75"], meta["workload_p90"])) for r in S.itertuples()])
    tr, te = next(GroupShuffleSplit(test_size=0.25, random_state=42).split(R, lab, groups=df["key"]))
    rm = DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=42).fit(
        pd.concat([R.iloc[tr], S]), pd.concat([lab.iloc[tr], Slab]))
    pr = rm.predict(R.iloc[te])
    meta["risk_metrics"] = {"accuracy": round(accuracy_score(lab.iloc[te], pr), 3),
                            "f1_macro": round(f1_score(lab.iloc[te], pr, average="macro", zero_division=0), 3),
                            "label_distribution": {k: int(v) for k, v in lab.value_counts().items()}, "synthetic_augmentation": n}
    log("Risk model:", meta["risk_metrics"])
    rm.fit(pd.concat([R, S]), pd.concat([lab, Slab]))
    joblib.dump(rm, OUT / "risk_model.pkl")

    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    log("Models saved to", OUT)
    return meta


if __name__ == "__main__":
    train_all()
