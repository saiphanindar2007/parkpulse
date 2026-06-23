"""
ParkPulse - Memory Optimization: Precompute Summary Tables

WHY THIS EXISTS: main.py was loading violations_clean.parquet (298,450
rows, ~208MB in memory) and hotspots.parquet (270,674 rows, ~213MB in
memory) in full, just to serve a handful of aggregate stats and a
per-hotspot weekly trend chart. That's 421MB before FastAPI, uvicorn,
pandas, OR-Tools, and LightGBM even finish loading -- which is why
deployment on Render's free tier (512MB limit) crashed with "Out of
memory."

THE FIX: precompute the SMALL summary tables the API actually needs,
once, offline. main.py then loads only these (a few hundred KB combined)
instead of the full 421MB of row-level data. Nothing about what the API
returns changes -- /api/stats/summary and /api/hotspots/{id}/trend
produce IDENTICAL responses, just sourced from pre-aggregated tables
instead of aggregating 298K rows on every server startup.

Run this once after the existing Day 1-4 pipeline (needs
violations_clean.parquet and hotspots.parquet to exist), then main.py
no longer needs to load either of those large files at all.
"""

import pandas as pd
import json

CLEAN_PATH = "data/violations_clean.parquet"
HOTSPOTS_PATH = "data/hotspots.parquet"

SUMMARY_STATS_OUT = "data/summary_stats.json"
HOTSPOT_WEEKLY_OUT = "data/hotspot_weekly.parquet"


def precompute_summary_stats():
    """Everything /api/stats/summary needs, as a tiny static JSON file."""
    df = pd.read_parquet(CLEAN_PATH)

    total_violations = len(df)
    date_min = df["created_datetime"].min()
    date_max = df["created_datetime"].max()
    peak_hour = int(df["hour"].value_counts().idxmax())
    top_vehicle = df["vehicle_type"].value_counts().idxmax()
    top_vehicle_count = int(df["vehicle_type"].value_counts().max())
    daytime_count = int(df["hour"].between(10, 17).sum())
    daytime_pct = round(daytime_count / total_violations * 100, 1)
    n_named_junctions = int(df[df["has_named_junction"]]["junction_name"].nunique())
    n_police_stations = int(df["police_station"].nunique())

    stats = {
        "total_violations": total_violations,
        "date_range": {
            "start": date_min.strftime("%Y-%m-%d"),
            "end": date_max.strftime("%Y-%m-%d"),
        },
        "peak_hour": peak_hour,
        "top_vehicle_type": top_vehicle,
        "top_vehicle_type_count": top_vehicle_count,
        "daytime_violations_pct": daytime_pct,
        "named_junctions": n_named_junctions,
        "police_stations": n_police_stations,
    }

    with open(SUMMARY_STATS_OUT, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Saved summary stats -> {SUMMARY_STATS_OUT}")
    print(f"  (precomputed from {total_violations:,} rows; main.py will no longer load this file)")


def precompute_hotspot_weekly():
    """Everything /api/hotspots/{id}/trend needs: one row per (hotspot_id,
    week) with the count, instead of every individual violation record."""
    df = pd.read_parquet(HOTSPOTS_PATH)
    df = df[~df["hotspot_id"].str.contains("noise")].copy()

    weekly = (
        df.groupby(["hotspot_id", "week"])
        .size()
        .reset_index(name="violation_count")
    )
    weekly["week_start"] = pd.to_datetime(weekly["week"].str.split("/").str[0])
    weekly = weekly.sort_values(["hotspot_id", "week_start"]).reset_index(drop=True)

    weekly.to_parquet(HOTSPOT_WEEKLY_OUT, index=False)
    before_rows = len(df)
    after_rows = len(weekly)
    print(f"Saved hotspot weekly trend table -> {HOTSPOT_WEEKLY_OUT}")
    print(f"  ({before_rows:,} raw rows compressed to {after_rows:,} weekly summary rows, "
          f"~{(1 - after_rows/before_rows)*100:.1f}% reduction)")


if __name__ == "__main__":
    precompute_summary_stats()
    precompute_hotspot_weekly()
    print("\nDone. main.py can now skip loading violations_clean.parquet and "
          "hotspots.parquet entirely -- see the updated main.py.")