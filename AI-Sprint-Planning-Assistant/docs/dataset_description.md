# Dataset Description

## 1. Dataset Name

Mesos Stories 176 Dataset

## 2. Dataset Purpose

The dataset contains Agile software-development issue/story information.

It is being used as the initial dataset for the AI-Based Sprint Planning Assistant project.

The dataset is particularly useful for the project's story-level analysis and Story Point Prediction module.

## 3. Dataset File Information

| Property | Value |
|---|---|
| Dataset name | Mesos Stories 176 |
| File format | CSV |
| Number of rows | 176 |
| Number of columns | 22 |
| Exact duplicate rows | 0 |
| Raw dataset location | data/raw/ |
| Processed dataset location | data/processed/ |

## 4. Dataset Attributes

| Attribute | Description |
|---|---|
| key | Unique issue/story identifier |
| issueType | Type of issue |
| sprint | Sprint associated with the issue |
| status | Current status of the issue |
| summary | Short description of the issue |
| description | Detailed description of the issue |
| storyPoint | Story-point value |
| priority | Priority assigned to the issue |
| watchcount | Number of watchers |
| fixVersions | Fix-version information |
| affectedVersions | Affected-version information |
| assignee | Person assigned to the issue |
| creator | Person who created the issue |
| reporter | Person who reported the issue |
| commentCount | Number of comments |
| votes | Number of votes |
| issueLinks | Links to related issues |
| blockedBy | Issues blocking this issue |
| blocks | Issues blocked by this issue |
| dependedOnBy | Issues depending on this issue |
| dependedOn | Issues this issue depends on |
| subtasks | Subtask information |

## 5. Data Quality Analysis

The original dataset was inspected for missing values and duplicate records.

### Missing Values

| Column | Missing Values |
|---|---:|
| description | 41 |
| storyPoint | 18 |
| assignee | 24 |

All remaining columns contain no missing values.

### Duplicate Records

The dataset contains:

**0 exact duplicate rows.**

Repeated issue keys were not automatically treated as duplicate records because an issue can be associated with different sprint information.

## 6. Data Cleaning

A Python preprocessing script was created at:

`ml/preprocessing/clean_dataset.py`

The cleaning process:

- Removes unnecessary surrounding whitespace from text fields.
- Standardizes text formatting.
- Converts `storyPoint` values to numeric values.
- Removes exact duplicate rows.
- Preserves missing story-point values instead of replacing them with zero.
- Saves the cleaned dataset separately from the original dataset.

## 7. Raw and Processed Data

The original dataset is stored in:

`data/raw/Mesos Stories 176.csv`

The cleaned dataset is stored in:

`data/processed/Mesos Stories 176_cleaned.csv`

The original raw dataset is preserved and is not modified during preprocessing.

## 8. Data Limitations

The dataset contains missing values in description, storyPoint, and assignee fields.

Missing story-point values should be considered when preparing training data for the Story Point Prediction model.

The dataset should not be assumed to contain all information required for every proposed module of the Sprint Planning Assistant. Additional sprint-level data may be required for comprehensive sprint success, risk detection, and backlog recommendation tasks.

## 9. Dataset Workflow

Raw Dataset

↓

Data Quality Checking

↓

Data Cleaning

↓

Processed Dataset

↓

Machine Learning Preprocessing

↓

Model Development

## 10. Deliverable

The current dataset deliverables are:

- Original raw CSV
- Cleaned processed CSV
- Data cleaning report
- Reproducible preprocessing script
- Dataset description