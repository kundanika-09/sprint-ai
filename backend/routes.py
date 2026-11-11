from flask import Blueprint, jsonify, render_template, request
import database as db
import prediction as pr
from models.features import PRIORITY_LABELS, PRIORITY_VALUES
from recommendation import recommend

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__, url_prefix="/api")
RISK_RANK = {"High": 2, "Medium": 1, "Low": 0}


@pages.route("/")
def dashboard(): return render_template("dashboard.html", page="dashboard")
@pages.route("/board")
def board(): return render_template("sprint_board.html", page="board")
@pages.route("/analytics")
def analytics(): return render_template("analytics.html", page="analytics")
@pages.route("/insights")
def insights(): return render_template("recommendations.html", page="insights")


def _rows(sprint):
    return db.stories_for_sprint(sprint)


def _sprint_agg(rows):
    return dict(total_stories=len(rows), total_points=sum(r["points"] for r in rows),
                blocked_stories=sum(1 for r in rows if r["blocked"] > 0),
                pending_tasks=sum(1 for r in rows if r["column_name"] != "Done"))


def _prio(v):
    return PRIORITY_VALUES.get(v, v) if isinstance(v, str) else int(v)


@api.get("/sprints")
def sprints():
    return jsonify(sprints=db.all_sprints(), active=db.active_sprint())


@api.get("/meta")
def meta(): return jsonify(pr.meta())


@api.get("/kpis")
def kpis():
    sp = int(request.args.get("sprint", db.active_sprint()))
    rows, m = _rows(sp), pr.meta()
    if not rows: return jsonify(error="empty sprint"), 404
    a = _sprint_agg(rows)
    vel = m["avg_velocity"]
    prob = pr.predict_sprint_success(a["total_stories"], a["total_points"], vel, a["blocked_stories"], a["pending_tasks"])
    high = sum(1 for r in rows if r["risk"] == "High")
    n = len(rows)
    health = 100 * (0.5 * prob["probability"] / 100 + 0.3 * (1 - high / n) + 0.2 * (1 - a["blocked_stories"] / n))
    cols = {c: sum(1 for r in rows if r["column_name"] == c) for c in db.COLUMNS}
    risk = {k: sum(1 for r in rows if r["risk"] == k) for k in ("Low", "Medium", "High")}
    pts_by_col = {c: sum(r["points"] for r in rows if r["column_name"] == c) for c in db.COLUMNS}
    return jsonify(sprint=sp, total_stories=n, avg_points=round(a["total_points"] / n, 2), total_points=a["total_points"],
                   health=round(health, 1), high_risk=high, velocity=vel, success=prob, columns=cols, risk=risk,
                   points_by_column=pts_by_col,
                   high_risk_stories=[r for r in rows if r["risk"] == "High"][:8])


@api.get("/stories")
def stories():
    rows = _rows(int(request.args.get("sprint", db.active_sprint())))
    for r in rows: r["priority_label"] = PRIORITY_LABELS.get(r["priority"], "Medium")
    return jsonify(stories=rows, columns=db.COLUMNS)


@api.post("/stories")
def add_story():
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    if not title: return jsonify(error="Title is required"), 400
    prio, it = _prio(d.get("priority", 3)), d.get("issue_type", "Task")
    sp, desc = int(d.get("sprint", db.active_sprint())), d.get("description", "")
    pts, src = d.get("points"), "manual"
    if pts in (None, ""):
        pts, src = pr.predict_story_points(title, desc, prio, it)["story_points"], "predicted"
    rows = _rows(sp)
    wl = sum(r["points"] for r in rows) + float(pts)
    rk = pr.predict_risk(float(pts), prio, 0, 0, wl)
    sid, key = db.insert_story({"title": title, "description": desc, "issue_type": it, "priority": prio,
        "points": float(pts), "points_source": src, "column_name": d.get("column_name", "Product Backlog"),
        "sprint": sp, "assignee": d.get("assignee", "Unassigned"), "blocked": 0, "dependencies": 0, "comments": 0,
        "risk": rk["risk_level"], "risk_reasons": rk["reasons"]})
    db.log_prediction("risk", {"story_key": key, "points": float(pts), "priority": prio, "workload": wl}, rk)
    risk = rk["risk_level"]
    return jsonify(id=sid, key=key, points=pts, risk=risk), 201


@api.patch("/stories/<int:sid>")
def move_story(sid):
    col = (request.get_json(force=True) or {}).get("column_name")
    if col not in db.COLUMNS: return jsonify(error="Invalid column"), 400
    db.move_story(sid, col)
    return jsonify(ok=True)


@api.post("/predict/story-points")
def p_points():
    d = request.get_json(force=True)
    if not (d.get("title") or "").strip(): return jsonify(error="Story title is required"), 400
    res = pr.predict_story_points(d["title"], d.get("description", ""), _prio(d.get("priority", 3)), d.get("issue_type", "Task"))
    db.log_prediction("story_points", {"title": d["title"], "priority": _prio(d.get("priority", 3)),
                                       "issue_type": d.get("issue_type", "Task")}, res)
    return jsonify(res)


@api.post("/predict/sprint-success")
def p_success():
    d = request.get_json(force=True)
    try:
        keys = ("total_stories", "total_points", "team_velocity", "blocked_stories", "pending_tasks")
        vals = {k: float(d[k]) for k in keys}
        res = pr.predict_sprint_success(*vals.values())
        db.log_prediction("sprint_success", vals, res)
        return jsonify(res)
    except (KeyError, ValueError, TypeError):
        return jsonify(error="All five sprint inputs must be numeric"), 400


@api.post("/predict/risk")
def p_risk():
    d = request.get_json(force=True)
    try:
        vals = {"story_points": float(d["story_points"]), "priority": _prio(d["priority"]),
                "blocked_issues": float(d["blocked_issues"]), "dependency_count": float(d["dependency_count"]),
                "sprint_workload": float(d["sprint_workload"])}
        res = pr.predict_risk(*vals.values())
        db.log_prediction("risk", vals, res)
        return jsonify(res)
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Invalid risk inputs"), 400


@api.get("/recommendations")
def recs():
    sp = int(request.args.get("sprint", db.active_sprint()))
    cap = float(request.args.get("capacity") or pr.meta()["avg_velocity"])
    open_ = [dict(r, risk_rank=RISK_RANK[r["risk"]]) for r in _rows(sp) if r["column_name"] != "Done"]
    return jsonify(sprint=sp, **recommend(open_, cap))


@api.get("/analytics")
def analytics_data():
    return jsonify(db.analytics())


@api.get("/predictions")
def prediction_history():
    return jsonify(predictions=db.recent_predictions(int(request.args.get("limit", 50)), request.args.get("type")))
