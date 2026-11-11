"""MongoDB persistence + seeding from the Mesos dataset.

Collections
-----------
stories        one document per story card (incl. ML story points, confidence, risk level + reasons)
sprint_stats   one document per sprint (aggregates + ML sprint-success probability)
predictions    log of EVERY ML prediction made (type, inputs, outputs, timestamp)
model_runs     training runs (algorithm, metrics) read from saved_models/meta.json
counters       auto-increment ids so the UI can keep using numeric story ids
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd
from pymongo import ASCENDING, MongoClient

import prediction as pr
from models.features import ROOT, load_dataset, sprint_table

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "sprint_planner")
COLUMNS = ["Product Backlog", "Sprint Backlog", "To Do", "In Progress", "Testing", "Done"]
_db = None


def get_db():
    global _db
    if _db is None:
        if os.getenv("USE_MONGOMOCK") == "1":          # in-memory fake Mongo, used only for automated tests
            import mongomock
            _db = mongomock.MongoClient()[DB_NAME]
        else:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
            try:
                client.admin.command("ping")
            except Exception as e:
                raise SystemExit(f"\nCannot connect to MongoDB at {MONGO_URI}\n"
                                 "Start MongoDB (service 'MongoDB Server') or set MONGO_URI to your Atlas string.\n"
                                 f"Details: {e}\n")
            _db = client[DB_NAME]
    return _db


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_id(name="stories"):
    r = get_db().counters.find_one_and_update({"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return int(r["seq"])


def _column_for(status, i):
    return {"Resolved": "Done", "Reviewable": "Testing", "Open": "Product Backlog" if i % 2 else "Sprint Backlog",
            "Accepted": "To Do" if i % 2 else "In Progress"}.get(status, "To Do")


def init_db():
    d = get_db()
    d.stories.create_index([("id", ASCENDING)], unique=True)
    d.stories.create_index([("sprint", ASCENDING)])
    d.predictions.create_index([("created_at", ASCENDING)])
    meta = json.loads((ROOT / "saved_models" / "meta.json").read_text())
    if d.model_runs.count_documents({}) == 0:
        d.model_runs.insert_one({"created_at": now(), "metrics": meta, "models": {
            "story_points": "RandomForestRegressor + TF-IDF", "sprint_success": "RandomForestClassifier",
            "risk": "DecisionTreeClassifier"}})
    if d.stories.count_documents({}):
        return
    df = load_dataset()
    med = float(df["storyPoint"].dropna().median())
    df["points"] = df["storyPoint"].fillna(med)
    wl = df.groupby("sprint")["points"].sum().to_dict()
    docs = []
    for i, r in enumerate(df.itertuples()):
        src, conf, pts = "dataset", None, float(r.points)
        if pd.isna(r.storyPoint):
            est = pr.predict_story_points(r.summary, r.description, r.priority, r.issueType)
            pts, src, conf = float(est["story_points"]), "predicted", float(est["confidence"])
        deps = int(r.dependedOn + r.dependedOnBy + r.blocks)
        rk = pr.predict_risk(pts, int(r.priority), int(r.blockedBy), deps, float(wl[r.sprint]))
        docs.append({"id": next_id(), "story_key": r.key, "title": r.summary, "description": r.description,
                     "issue_type": r.issueType, "priority": int(r.priority), "points": pts, "points_source": src,
                     "confidence": conf, "column_name": _column_for(r.status, i), "sprint": int(r.sprint),
                     "assignee": r.assignee or "Unassigned", "blocked": int(r.blockedBy), "dependencies": deps,
                     "comments": int(r.commentCount), "risk": rk["risk_level"], "risk_reasons": rk["reasons"],
                     "created_at": now()})
    d.stories.insert_many(docs)
    for r in sprint_table(df).itertuples():
        p = pr.predict_sprint_success(r.total_stories, r.total_points, r.team_velocity, r.blocked_stories, r.pending_tasks)
        d.sprint_stats.replace_one({"sprint": int(r.sprint)}, {
            "sprint": int(r.sprint), "total_stories": int(r.total_stories), "total_points": float(r.total_points),
            "completed_points": float(r.completed_points), "blocked_stories": int(r.blocked_stories),
            "pending_tasks": int(r.pending_tasks), "team_velocity": float(r.team_velocity),
            "success_prob": float(p["probability"]), "prediction": p["label"], "drivers": p["drivers"]}, upsert=True)


# ---------------------------- queries used by routes.py ----------------------------
def stories_for_sprint(sprint):
    return list(get_db().stories.find({"sprint": int(sprint)}, {"_id": 0}).sort([("priority", 1), ("id", 1)]))


def all_sprints():
    return sorted(get_db().stories.distinct("sprint"))


def active_sprint():
    """Sprint with the most unfinished stories (ties -> latest)."""
    r = list(get_db().stories.aggregate([{"$match": {"column_name": {"$ne": "Done"}}},
             {"$group": {"_id": "$sprint", "n": {"$sum": 1}}}, {"$sort": {"n": -1, "_id": -1}}, {"$limit": 1}]))
    if r:
        return int(r[0]["_id"])
    s = all_sprints()
    return s[-1] if s else None


def insert_story(doc):
    doc.update({"id": next_id(), "created_at": now()})
    doc["story_key"] = f"SPR-{doc['id']}"
    get_db().stories.insert_one(dict(doc))
    return doc["id"], doc["story_key"]


def move_story(sid, col):
    get_db().stories.update_one({"id": int(sid)}, {"$set": {"column_name": col, "updated_at": now()}})


def log_prediction(kind, inputs, output):
    """Store every ML prediction (story points / sprint success / risk) for audit and analytics."""
    get_db().predictions.insert_one({"type": kind, "inputs": inputs, "output": output, "created_at": now()})


def recent_predictions(limit=50, kind=None):
    q = {"type": kind} if kind else {}
    return list(get_db().predictions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit))


def analytics():
    d = get_db()
    dist = {str(int(r["_id"])): r["n"] for r in d.stories.aggregate(
        [{"$group": {"_id": "$points", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])}
    risk = {r["_id"]: r["n"] for r in d.stories.aggregate([{"$group": {"_id": "$risk", "n": {"$sum": 1}}}])}
    team = [{"assignee": r["_id"], "stories": r["stories"], "done_points": r["done_points"]} for r in d.stories.aggregate([
        {"$match": {"assignee": {"$ne": "Unassigned"}}},
        {"$group": {"_id": "$assignee", "stories": {"$sum": 1},
                    "done_points": {"$sum": {"$cond": [{"$eq": ["$column_name", "Done"]}, "$points", 0]}}}},
        {"$sort": {"done_points": -1}}, {"$limit": 8}])]
    sprints = list(d.sprint_stats.find({}, {"_id": 0}).sort("sprint", 1))
    return {"distribution": dist, "sprints": sprints, "risk": risk, "team": team}
