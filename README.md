# AI-Based Sprint Planning Assistant using Agile Analytics and MLOps

Flask + scikit-learn + SQLite + Bootstrap 5 + Chart.js. Trained on the Apache Mesos stories dataset (176 rows, 75 unique issues, 61 sprints).

## Run
```bash
pip install -r requirements.txt
python backend/models/train_models.py   # optional: retrains and rewrites saved_models/ (auto-runs if models are missing)
python backend/app.py                   # http://127.0.0.1:5000
```
The SQLite DB (`data/sprint_planner.db`) is created and seeded from the dataset on first launch. Delete it to reset the board.

## Pages
| Route | Page |
|---|---|
| `/` | Dashboard - 6 KPI cards, risk doughnut, points per stage, high-risk table |
| `/board` | Kanban board (6 columns, drag & drop, create story with ML point estimate) |
| `/analytics` | 5 Chart.js charts |
| `/insights` | Story-point, sprint-success, risk and recommendation cards + model metrics |

## ML pipeline (`backend/models/`)
| Module | Model | Notes |
|---|---|---|
| Story points | RandomForestRegressor + TF-IDF (title, description), issue type, priority, length/keyword features | one row per issue to avoid train/test leakage; output snapped to 1,2,3,5,8,13; confidence from tree-prediction spread |
| Sprint success | RandomForestClassifier | features: stories, points, velocity, blocked, pending; label = completed points >= 80% of committed |
| Risk | DecisionTreeClassifier | features: points, priority, blocked, dependencies, sprint workload |
| Recommendations | rule engine (`recommendation.py`) | the 4 rules from the brief; "Story Points > Capacity" is applied against remaining sprint capacity (priority order) |

Preprocessing: duplicate removal, whitespace trim, numeric conversion, lowercase text, TF-IDF, train/test split, evaluation, Joblib export.

## Honest limitations (state these in your viva)
1. **Tiny dataset.** The story-point model only slightly beats a median baseline (see `saved_models/meta.json`). Expect modest accuracy; estimates are indicative. The sample story from the brief predicts ~3 pts, not 8, because Mesos stories are mostly 1-5 pts.
2. **Derived labels.** The dataset has no sprint-success or risk column. Sprint success is derived from completion ratio; risk from a transparent scoring rubric (`risk_score` in `features.py`). The risk tree is trained on real rows plus 2,500 synthetic scenarios labelled by the same rubric - it learns the rubric, it is not validated against real-world outcomes.
3. **Sprint-success leakage.** `pending_tasks` is correlated with the completion label, so its 1.0 hold-out score on 61 sprints should not be read as real predictive power. Collect pre-sprint snapshots for a proper evaluation.
4. Missing story points (18) are never filled with 0; they are ML-estimated when seeding the board (shown in amber on cards).
5. Dataset priority is numeric (1=Highest ... 4=Low); the UI maps it to labels.

---
## MongoDB (current database)
Collections in database `sprint_planner`: `stories`, `sprint_stats`, `predictions` (log of every ML prediction), `model_runs`, `counters`.
1. Install MongoDB Community Server (+ Compass) **or** create a free MongoDB Atlas cluster.
2. `pip install -r requirements.txt`
3. (Atlas only) `set MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net`   (PowerShell: `$env:MONGO_URI="..."`)
4. `python mongo_check.py` -> confirms the connection.
5. `python backend/app.py` -> seeds the database on first run.

## Benchmark vs baselines (public Deep-SE dataset)
`python ml/benchmark_story_points.py` downloads 16 open-source projects (~23k issues), evaluates 7 estimators with a time-ordered split
and writes `docs/story_point_benchmark.csv`. Our pre-computed run is in `docs/story_point_benchmark_results.csv`.
