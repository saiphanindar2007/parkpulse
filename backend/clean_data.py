"""
ParkPulse - Day 1: Data Cleaning & Preprocessing
Cleans the raw Bengaluru traffic police violation dataset and writes
a processed Parquet file for all downstream modeling/API work.
"""

import pandas as pd
import numpy as np
import ast
import json

RAW_PATH = "data/raw_violations.csv"
OUT_PARQUET = "data/violations_clean.parquet"
OUT_EXPLODED_PARQUET = "data/violations_exploded.parquet"  # one row per violation sub-type

# Severity weights: how much each violation type matters for congestion impact.
# Tuned by reasoning about real-world traffic flow disruption, not arbitrary.
SEVERITY_WEIGHTS = {
    "WRONG PARKING": 3,
    "NO PARKING": 2,
    "PARKING IN A MAIN ROAD": 4,
    "DEFECTIVE NUMBER PLATE": 1,
    "PARKING ON FOOTPATH": 3,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 5,
    "DOUBLE PARKING": 4,
    "PARKING NEAR ROAD CROSSING": 5,
    "REFUSE TO GO FOR HIRE": 1,
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS": 5,
    "PARKING OPPOSITE TO ANOTHER PARKED VEHICLE": 4,
    "USING BLACK FILM/OTHER MATERIALS": 1,
    "PARKING OTHER THAN BUS STOP": 2,
    "DEMANDING EXCESS FARE": 1,
    "WITHOUT SIDE MIRROR": 1,
    "H T V PROHIBITED": 3,
    "OBSTRUCTING DRIVER": 3,
    "AGAINST ONE WAY/NO ENTRY": 5,
    "FAIL TO USE SAFETY BELTS": 2,
    "VIOLATING LANE DISIPLINE": 3,
    "RIDER NOT WEARING HELMET": 2,
    "2W/3W - USING MOBILE PHONE": 2,
    "OTHER - USING MOBILE PHONE": 2,
    "CARRYING LENGHTY MATERIAL": 2,
    "JUMPING TRAFFIC SIGNAL": 5,
    "U TURN PROHIBITED": 4,
    "STOPING ON WHITE/STOP LINE": 3,
}
DEFAULT_WEIGHT = 2  # fallback for any unseen violation type


def parse_list_column(val):
    """Parse stringified JSON-ish list columns like '["NO PARKING"]' into real lists."""
    if pd.isna(val):
        return []
    try:
        parsed = ast.literal_eval(val)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except (ValueError, SyntaxError):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return [val]


def main():
    print("Loading raw CSV...")
    df = pd.read_csv(RAW_PATH, low_memory=False)
    print(f"Raw shape: {df.shape}")

    # --- Drop columns that are 100% null in this dataset (verified during EDA) ---
    fully_null_cols = [c for c in df.columns if df[c].isna().all()]
    print(f"Dropping fully-null columns: {fully_null_cols}")
    df = df.drop(columns=fully_null_cols)

    # --- Parse timestamps ---
    ts_cols = ["created_datetime", "modified_datetime",
               "data_sent_to_scita_timestamp", "validation_timestamp"]
    for col in ts_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # --- Parse list-like columns ---
    df["violation_list"] = df["violation_type"].apply(parse_list_column)
    df["offence_code_list"] = df["offence_code"].apply(parse_list_column)
    df["n_violations"] = df["violation_list"].apply(len)

    # --- Severity score per row (sum of weights across all violations in that record) ---
    df["severity_score"] = df["violation_list"].apply(
        lambda lst: sum(SEVERITY_WEIGHTS.get(v, DEFAULT_WEIGHT) for v in lst)
    )

    # --- Time features ---
    df["hour"] = df["created_datetime"].dt.hour
    df["day_of_week"] = df["created_datetime"].dt.day_name()
    df["is_weekend"] = df["created_datetime"].dt.dayofweek.isin([5, 6])
    df["date"] = df["created_datetime"].dt.date
    df["week"] = df["created_datetime"].dt.tz_localize(None).dt.to_period("W").astype(str)

    # --- Clean junction name: flag whether it's a real named junction or not ---
    df["has_named_junction"] = df["junction_name"].fillna("No Junction") != "No Junction"

    # --- Drop exact duplicate IDs if any ---
    before = len(df)
    df = df.drop_duplicates(subset=["id"])
    print(f"Dropped {before - len(df)} duplicate IDs")

    # --- Basic coordinate sanity filter (keep only plausible Bengaluru bounding box) ---
    bbox = {"lat_min": 12.7, "lat_max": 13.4, "lon_min": 77.3, "lon_max": 77.9}
    before = len(df)
    df = df[
        df["latitude"].between(bbox["lat_min"], bbox["lat_max"]) &
        df["longitude"].between(bbox["lon_min"], bbox["lon_max"])
    ]
    print(f"Dropped {before - len(df)} rows outside Bengaluru bounding box")

    print(f"Final cleaned shape: {df.shape}")

    # Save main cleaned file (list columns kept as Python objects; parquet handles this)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"Saved cleaned dataset -> {OUT_PARQUET}")

    # --- Also produce an EXPLODED version: one row per individual violation type ---
    # This is what you'll use for violation-type-level aggregation/charts.
    exploded = df.explode("violation_list").rename(columns={"violation_list": "violation"})
    exploded["violation"] = exploded["violation"].fillna("UNKNOWN")
    exploded.to_parquet(OUT_EXPLODED_PARQUET, index=False)
    print(f"Saved exploded dataset -> {OUT_EXPLODED_PARQUET} (shape: {exploded.shape})")

    print("\nDone. Summary:")
    print(df[["hour", "severity_score", "n_violations"]].describe())


if __name__ == "__main__":
    main()