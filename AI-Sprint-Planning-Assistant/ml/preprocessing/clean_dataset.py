import pandas as pd
from pathlib import Path

# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "Mesos Stories 176.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PROCESSED_FILE = PROCESSED_DIR / "Mesos Stories 176_cleaned.csv"
REPORT_FILE = PROCESSED_DIR / "data_cleaning_report.txt"


# --------------------------------------------------
# Create processed folder if needed
# --------------------------------------------------

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Load raw dataset
# --------------------------------------------------

df = pd.read_csv(RAW_FILE, encoding="utf-8-sig")


# --------------------------------------------------
# Original dataset information
# --------------------------------------------------

original_rows = len(df)
original_columns = len(df.columns)

print("========== ORIGINAL DATASET ==========")
print("Rows:", original_rows)
print("Columns:", original_columns)

print("\nColumns:")
for column in df.columns:
    print("-", column)


# --------------------------------------------------
# Missing values BEFORE cleaning
# --------------------------------------------------

missing_before = df.isnull().sum()

print("\n========== MISSING VALUES ==========")

for column, count in missing_before.items():
    if count > 0:
        print(f"{column}: {count}")


# --------------------------------------------------
# Duplicate rows BEFORE cleaning
# --------------------------------------------------

duplicate_rows = df.duplicated().sum()

print("\n========== DUPLICATES ==========")
print("Exact duplicate rows:", duplicate_rows)


# --------------------------------------------------
# Text cleaning
# --------------------------------------------------

text_columns = [
    "key",
    "issueType",
    "sprint",
    "status",
    "summary",
    "description",
    "priority",
    "fixVersions",
    "affectedVersions",
    "assignee",
    "creator",
    "reporter",
    "issueLinks",
    "blockedBy",
    "blocks",
    "dependedOnBy",
    "dependedOn",
    "subtasks"
]

for column in text_columns:
    if column in df.columns:
        df[column] = df[column].fillna("")
        df[column] = df[column].astype(str).str.strip()


# --------------------------------------------------
# Standardize common categorical text
# --------------------------------------------------

if "status" in df.columns:
    df["status"] = df["status"].str.strip()

if "priority" in df.columns:
    df["priority"] = df["priority"].str.strip()

if "issueType" in df.columns:
    df["issueType"] = df["issueType"].str.strip()


# --------------------------------------------------
# Keep missing story points as missing
# --------------------------------------------------
# We DO NOT fill missing story points with 0.
# Missing story points are documented for the ML team.

if "storyPoint" in df.columns:
    df["storyPoint"] = pd.to_numeric(
        df["storyPoint"], errors="coerce"
    )


# --------------------------------------------------
# Remove exact duplicate rows
# --------------------------------------------------

df = df.drop_duplicates()


# --------------------------------------------------
# Save processed dataset
# --------------------------------------------------

df.to_csv(
    PROCESSED_FILE,
    index=False,
    encoding="utf-8-sig"
)


# --------------------------------------------------
# Final information
# --------------------------------------------------

final_rows = len(df)
final_columns = len(df.columns)

missing_after = df.isnull().sum()


# --------------------------------------------------
# Create cleaning report
# --------------------------------------------------

with open(REPORT_FILE, "w", encoding="utf-8") as report:

    report.write("DATA CLEANING REPORT\n")
    report.write("====================\n\n")

    report.write("Dataset: Mesos Stories 176.csv\n\n")

    report.write("ORIGINAL DATASET\n")
    report.write("----------------\n")
    report.write(f"Rows: {original_rows}\n")
    report.write(f"Columns: {original_columns}\n")
    report.write(f"Exact duplicate rows: {duplicate_rows}\n\n")

    report.write("MISSING VALUES BEFORE CLEANING\n")
    report.write("------------------------------\n")

    for column, count in missing_before.items():
        if count > 0:
            report.write(f"{column}: {count}\n")

    report.write("\nCLEANING PERFORMED\n")
    report.write("------------------\n")
    report.write("- Trimmed whitespace from text fields.\n")
    report.write("- Standardized text fields by removing surrounding spaces.\n")
    report.write("- Converted storyPoint to numeric values.\n")
    report.write("- Exact duplicate rows were removed.\n")
    report.write("- Missing storyPoint values were NOT replaced with 0.\n")
    report.write("- Missing storyPoint values are retained for ML-team handling.\n")

    report.write("\nFINAL DATASET\n")
    report.write("-------------\n")
    report.write(f"Rows: {final_rows}\n")
    report.write(f"Columns: {final_columns}\n")

    report.write("\nMISSING VALUES AFTER CLEANING\n")
    report.write("-----------------------------\n")

    for column, count in missing_after.items():
        if count > 0:
            report.write(f"{column}: {count}\n")


print("\n========== COMPLETED ==========")
print("Cleaned dataset saved to:")
print(PROCESSED_FILE)

print("\nCleaning report saved to:")
print(REPORT_FILE)