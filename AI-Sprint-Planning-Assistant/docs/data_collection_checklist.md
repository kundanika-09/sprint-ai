# Data Collection and Verification Checklist

## 1. Dataset Selection

| Item | Status |
|---|---|
| Dataset identified | Completed |
| Dataset relevance to project checked | Completed |
| Dataset downloaded | Completed |
| Dataset source recorded | Completed |
| Dataset stored in raw-data folder | Completed |

---

## 2. Dataset Information

**Dataset Name:** Mesos Stories 176 Dataset

**Dataset File:**

`Mesos Stories 176.csv`

**Number of Records:** 176

**Number of Attributes:** 22

**Primary Target Attribute:**

`storyPoint`

The `storyPoint` attribute can be used by the machine-learning team for the Story Point Prediction module.

---

## 3. Data Organization

The raw dataset is stored separately from the processed dataset.

```text
data/
├── raw/
│   └── Mesos Stories 176.csv
│
└── processed/
    └── Mesos Stories 176_cleaned.csv