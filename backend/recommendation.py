"""Rule-based backlog recommendation engine."""


def recommend(stories, capacity):
    """stories: list of dict rows (not-done only). capacity: story points the team can commit."""
    ordered = sorted(stories, key=lambda s: (s["priority"], -s["risk_rank"], s["points"]))
    used, recs = 0.0, []
    for s in ordered:
        base = {"story_id": s["id"], "key": s["story_key"], "title": s["title"], "points": s["points"]}
        if s["priority"] == 1:                                              # Rule 3
            recs.append({**base, "type": "keep", "severity": "info", "action": f"Keep {s['title']} in Current Sprint",
                         "reason": "Highest priority story"})
            used += s["points"]
        elif used + s["points"] > capacity:                                 # Rule 1
            recs.append({**base, "type": "move", "severity": "warning", "action": f"Move {s['title']} to Next Sprint",
                         "reason": f"{s['points']:g} pts exceeds remaining capacity ({max(capacity-used,0):g} pts)"})
        else:
            used += s["points"]
        if s["risk"] == "High":                                             # Rule 2
            recs.append({**base, "type": "split", "severity": "danger", "action": f"Split {s['title']} Story",
                         "reason": "High risk level detected"})
        if s["blocked"] > 2:                                                # Rule 4
            recs.append({**base, "type": "dependency", "severity": "danger",
                         "action": f"Resolve Dependencies Before Sprint Start for {s['title']}",
                         "reason": f"{s['blocked']} blocking issues"})
    return {"capacity": capacity, "committed": round(used, 1), "open_stories": len(stories),
            "overload": round(max(used - capacity, 0), 1), "recommendations": recs}
