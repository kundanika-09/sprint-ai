"""Benchmarks story-point estimators on the public Deep-SE dataset (16 open-source projects, ~23k issues).
Protocol: per project, issues sorted by key number; train on the oldest 80%, test on the newest 20%.
Metric: Mean Absolute Error (lower is better). Median / Mean baselines = predict the training median / mean.

Run from project root:   python ml/benchmark_story_points.py            (all projects, ~4 min)
                         python ml/benchmark_story_points.py mesos usergrid bamboo   (a few projects)
Output: docs/story_point_benchmark.csv  + printed summary.
Data source: https://github.com/morakotch/datasets (Choetkiertikul et al., IEEE TSE 2018)."""
import sys, urllib.request, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np, pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors
from models.features import clean_text, COMPLEX_KW

BASE = "https://raw.githubusercontent.com/morakotch/datasets/master/storypoint/IEEE%20TSE2018/dataset/"
ALL = ["appceleratorstudio", "aptanastudio", "bamboo", "clover", "datamanagement", "duracloud", "jirasoftware", "mesos",
       "moodle", "mule", "mulestudio", "springxd", "talenddataquality", "talendesb", "titanium", "usergrid"]
DATA = ROOT / "data" / "external" / "deep_se"; DATA.mkdir(parents=True, exist_ok=True)


def num(df):
    t, d = df.title.map(clean_text), df.description.map(clean_text)
    return np.c_[t.str.split().str.len(), np.minimum(d.str.split().str.len(), 500), d.str.len() > 0,
                 [sum(k in (a + " " + b) for k in COMPLEX_KW) for a, b in zip(t, d)]].astype(float)


rows = []
for name in (sys.argv[1:] or ALL):
    f = DATA / f"{name}.csv"
    if not f.exists():
        urllib.request.urlretrieve(BASE + f"{name}.csv", f)
    df = pd.read_csv(f).dropna(subset=["storypoint"])
    df["n"] = df.issuekey.str.extract(r"(\d+)$").astype(float)
    df = df.sort_values("n").reset_index(drop=True)
    cut = int(len(df) * .8); tr, te = df.iloc[:cut], df.iloc[cut:]
    txt = lambda d: d.title.map(clean_text) + " " + d.title.map(clean_text) + " " + d.description.map(clean_text)
    tf = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), stop_words="english", sublinear_tf=True, min_df=2).fit(txt(tr))
    A, T = tf.transform(txt(tr)), tf.transform(txt(te))
    Xtr, Xte = hstack([A, csr_matrix(num(tr))]).tocsr(), hstack([T, csr_matrix(num(te))]).tocsr()
    ytr, yte = tr.storypoint.values, te.storypoint.values
    mae = lambda p: float(np.abs(p - yte).mean())
    r = {"project": name, "issues": len(df), "Baseline Median": mae(np.median(ytr)), "Baseline Mean": mae(ytr.mean()),
         "TF-IDF + Ridge": mae(Ridge(alpha=1.5).fit(Xtr, ytr).predict(Xte)),
         "TF-IDF + Random Forest (ours v1)": mae(RandomForestRegressor(200, min_samples_leaf=2, max_features=.3, n_jobs=-1, random_state=42).fit(Xtr, ytr).predict(Xte))}
    _, idx = NearestNeighbors(n_neighbors=min(15, len(tr)), metric="cosine").fit(A).kneighbors(T)
    knn = np.median(ytr[idx], axis=1)
    r["Similar-stories kNN (analogy)"] = mae(knn)
    r["kNN + Median blend"] = mae(.5 * knn + .5 * np.median(ytr))
    svd = TruncatedSVD(60, random_state=0).fit(A)
    r["SVD + Gradient Boosting (abs loss)"] = mae(HistGradientBoostingRegressor(loss="absolute_error", max_depth=3, learning_rate=.05, max_iter=150, random_state=0)
                                                  .fit(svd.transform(A), ytr).predict(svd.transform(T)))
    rows.append(r); print(name, {k: round(v, 2) for k, v in r.items() if k not in ("project", "issues")}, flush=True)

R = pd.DataFrame(rows).set_index("project")
out = ROOT / "docs" / "story_point_benchmark.csv"; R.round(3).to_csv(out)
m = [c for c in R.columns if c != "issues"]
print("\nAverage MAE over projects:\n", R[m].mean().round(3).sort_values())
print("\nProjects where each model beats the Median baseline:")
for c in m[1:]:
    print(f"  {c:<38} {(R[c] < R['Baseline Median']).sum()} / {len(R)}")
print("\nSaved", out)
