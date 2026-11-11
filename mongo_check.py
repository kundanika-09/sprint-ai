"""Checks the MongoDB connection and prints what is stored.   Run: python mongo_check.py"""
import sys
sys.path.insert(0, "backend")
import database as db
d = db.get_db()                       # exits with a clear message if MongoDB is not reachable
print("Connected to MongoDB database:", d.name)
for name in ["stories", "sprint_stats", "predictions", "model_runs"]:
    print(f"  {name:<14} {d[name].count_documents({})} documents")
print("\nLatest 3 predictions:")
for p in db.recent_predictions(3):
    print(" ", p["created_at"], p["type"], "->", {k: v for k, v in p["output"].items() if k != "reasons"})
