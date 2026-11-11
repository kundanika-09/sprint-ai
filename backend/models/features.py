"""Shared preprocessing + feature engineering (used by training AND serving)."""
import re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "Mesos Stories 176_cleaned.csv"
RAW = ROOT / "data" / "raw" / "Mesos Stories 176.csv"

PRIORITY_LABELS = {1: "Highest", 2: "High", 3: "Medium", 4: "Low"}
PRIORITY_VALUES = {v: k for k, v in PRIORITY_LABELS.items()}
FIB = [1, 2, 3, 5, 8, 13]
COMPLEX_KW = ["refactor", "api", "design", "security", "authentication", "jwt", "integration",
              "migration", "database", "performance", "concurrent", "distributed",
              "framework", "architecture", "module", "login", "scheduler", "isolation"]
STORY_NUM = ["priority", "title_len", "desc_len", "has_desc", "kw_count"]
SPRINT_FEATS = ["total_stories", "total_points", "team_velocity", "blocked_stories", "pending_tasks"]
RISK_FEATS = ["story_points", "priority", "blocked_issues", "dependency_count", "sprint_workload"]


def clean_text(s):
    """Lower-case, strip URLs / punctuation, collapse whitespace."""
    s = str(s if s is not None and s == s else "").lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def story_features(title, description, priority, issue_type):
    t, d = clean_text(title), clean_text(description)
    text = f"{t} {t} {d}".strip()
    return {"text": text, "issue_type": issue_type or "Task", "priority": int(priority),
            "title_len": len(t.split()), "desc_len": min(len(d.split()), 500),
            "has_desc": int(len(d) > 0), "kw_count": sum(k in text for k in COMPLEX_KW)}


def load_dataset():
    """Load the processed CSV (falls back to raw) and apply the cleaning steps."""
    path = PROCESSED if PROCESSED.exists() else RAW
    df = pd.read_csv(path, encoding="utf-8-sig")
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith("str"):
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["storyPoint"] = pd.to_numeric(df["storyPoint"], errors="coerce")
    return df.drop_duplicates().reset_index(drop=True)


def sprint_table(df):
    """Aggregate story rows (needs 'points') into one row per sprint."""
    d = df.copy()
    d["done"] = d["status"].eq("Resolved")
    d["comp"] = d["points"] * d["done"]
    d["blk"] = (d["blockedBy"] > 0).astype(int)
    d["pend"] = (~d["done"]).astype(int)
    t = d.groupby("sprint").agg(total_stories=("key", "size"), total_points=("points", "sum"),
                                completed_points=("comp", "sum"), blocked_stories=("blk", "sum"),
                                pending_tasks=("pend", "sum")).reset_index().sort_values("sprint")
    t["team_velocity"] = (t["completed_points"].shift(1).rolling(3, min_periods=1).mean()
                          .fillna(t["completed_points"].median()))
    ratio = t["completed_points"] / t["total_points"].clip(lower=1)
    t["success"] = (ratio >= 0.8).astype(int)
    return t.reset_index(drop=True)


def risk_score(points, priority, blocked, deps, workload, p75, p90):
    """Transparent scoring rubric used to LABEL training data (dataset has no risk column)."""
    s = 2 if blocked > 2 else (1 if blocked >= 1 else 0)
    s += 2 if deps >= 5 else (1 if deps >= 3 else 0)
    s += 2 if points >= 8 else (1 if points >= 5 else 0)
    s += 2 if workload >= p90 else (1 if workload >= p75 else 0)
    s += 1 if (priority == 1 and blocked >= 1) else 0
    return s


def risk_level_from_score(s):
    return "High" if s >= 4 else ("Medium" if s >= 2 else "Low")
