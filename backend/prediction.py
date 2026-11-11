"""Inference layer for the three trained models."""
import json
import joblib
import numpy as np
import pandas as pd
from models.features import (ROOT, FIB, SPRINT_FEATS, RISK_FEATS, PRIORITY_LABELS, story_features)

MD = ROOT / "saved_models"
_c = {}


def _m(name):
    if name not in _c:
        _c[name] = joblib.load(MD / name)
    return _c[name]


def meta():
    return json.loads((MD / "meta.json").read_text())


def predict_story_points(title, description, priority, issue_type):
    pipe = _m("story_point_model.pkl")
    X = pd.DataFrame([story_features(title, description, priority, issue_type)])
    pre, rf = pipe.named_steps["pre"], pipe.named_steps["rf"]
    Z = pre.transform(X)
    trees = np.array([t.predict(Z)[0] for t in rf.estimators_])
    raw, std = float(trees.mean()), float(trees.std())
    pts = min(FIB, key=lambda f: abs(f - raw))                 # snap to Fibonacci scale
    conf = float(np.clip(100 * (1 - std / max(raw, 1.0)), 35, 98))
    return {"story_points": pts, "raw_estimate": round(raw, 2), "confidence": round(conf, 1)}


def predict_sprint_success(total_stories, total_points, team_velocity, blocked_stories, pending_tasks):
    clf = _m("sprint_success_model.pkl")
    X = pd.DataFrame([[total_stories, total_points, team_velocity, blocked_stories, pending_tasks]], columns=SPRINT_FEATS)
    proba = clf.predict_proba(X)[0]
    p = float(proba[list(clf.classes_).index(1)]) if 1 in clf.classes_ else 0.0
    # transparent, human-readable drivers
    drivers = []
    if total_points > team_velocity * 1.25:
        drivers.append(f"Committed {total_points:g} pts exceeds velocity ({team_velocity:g} pts)")
    if total_stories and blocked_stories / total_stories > 0.3:
        drivers.append(f"{blocked_stories} of {total_stories} stories are blocked")
    if total_stories and pending_tasks / total_stories > 0.7:
        drivers.append(f"{pending_tasks} tasks still pending")
    if not drivers:
        drivers.append("Workload, blockers and pending tasks are within healthy ranges")
    ok = p >= 0.5
    return {"probability": round(p * 100, 1), "success": ok,
            "label": "Sprint Likely To Succeed" if ok else "Sprint Likely To Fail", "drivers": drivers}


def predict_risk(story_points, priority, blocked_issues, dependency_count, sprint_workload, team_velocity=None):
    clf = _m("risk_model.pkl")
    X = pd.DataFrame([[story_points, priority, blocked_issues, dependency_count, sprint_workload]], columns=RISK_FEATS)
    level = str(clf.predict(X)[0])
    vel = team_velocity or meta()["avg_velocity"]
    reasons = []
    if blocked_issues > 2:
        reasons.append("Too many blocked tasks")
    elif blocked_issues >= 1:
        reasons.append(f"Blocked by {int(blocked_issues)} issue(s)")
    if sprint_workload > vel * 1.25:
        reasons.append("Sprint overload (workload exceeds team velocity)")
    if dependency_count >= 3:
        reasons.append("High dependency count")
    if story_points >= 8:
        reasons.append("Large story - consider splitting")
    if priority == 1 and blocked_issues >= 1:
        reasons.append("Highest-priority story is blocked")
    if not reasons:
        reasons.append("No significant risk factors detected" if level == "Low" else "Combined moderate risk factors")
    return {"risk_level": level, "label": f"{level} Risk Detected", "reasons": reasons}
