# Data Cleaning and Quality Report

## 1. Dataset

Dataset: Mesos Stories 176.csv

The original dataset is stored in:

`data/raw/Mesos Stories 176.csv`

The cleaned dataset is stored in:

`data/processed/Mesos Stories 176_cleaned.csv`

---

## 2. Initial Dataset Statistics

| Metric | Value |
|---|---:|
| Rows | 176 |
| Columns | 22 |
| Exact duplicate rows | 0 |

---

## 3. Missing Value Analysis

The following missing values were identified:

| Column | Missing Values |
|---|---:|
| description | 41 |
| storyPoint | 18 |
| assignee | 24 |

All other columns contain zero missing values.

---

## 4. Duplicate Analysis

An exact duplicate-row check was performed.

Result:

**0 exact duplicate rows were found.**

Repeated values in the `key` column were not automatically removed because the same issue can appear with different sprint information.

---

## 5. Cleaning Operations

The following preprocessing operations were performed:

### Text fields

- Leading and trailing whitespace was removed.
- Missing text fields were handled without modifying the original raw dataset.
- Common categorical fields were standardized by removing unnecessary surrounding spaces.

### Story points

The `storyPoint` column was converted to a numeric format.

Missing story-point values were preserved.

They were **not replaced with zero**, because a missing story point does not mean that the story has zero effort.

### Duplicate rows

Exact duplicate rows were removed during preprocessing.

Since the original dataset contained zero exact duplicate rows, no rows were removed for this reason.

---

## 6. Raw Dataset Preservation

The original dataset was not modified.

```text
data/raw/
└── Mesos Stories 176.csv