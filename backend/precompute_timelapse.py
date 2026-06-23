"""
ParkPulse - Precompute Timelapse Data

Follows the same memory-optimization pattern as precompute_summary.py:
extracts just ONE day's worth of violation points (lat/lon/time/severity)
from the full violations_clean.parquet, once, offline, into a tiny
dedicated file. main.py then loads only this small file -- never the
full 298K-row dataset -- keeping the Render free-tier memory budget
intact while still powering the animated 24-hour replay feature.

Default day: 2023-11-18, the single busiest day in the dataset (2,858
violations), chosen because the night/day enforcement gap is most
visually dramatic on a high-volume day.

Run this once (or again if you want to feature a different day):
    python precompute_timelapse.py
    python precompute_timelapse.py --date 2024-01-21
"""

import pandas as pd
import argparse

CLEAN_PATH = "data/violations_clean.parquet"
OUT_PATH = "data/timelapse_day.parquet"

DEFAULT_DATE = "2023-11-18"


def main(date: str):
    print(f"Loading {CLEAN_PATH} (one-time, offline -- not loaded by main.py at runtime)...")
    df = pd.read_parquet(CLEAN_PATH, columns=["latitude", "longitude", "created_datetime", "severity_score"])
    df["created_datetime"] = pd.to_datetime(df["created_datetime"])

    day_df = df[df["created_datetime"].dt.strftime("%Y-%m-%d") == date].copy()
    if day_df.empty:
        available_dates = df["created_datetime"].dt.strftime("%Y-%m-%d").value_counts().head(5)
        print(f"No violations found on {date}. Busiest available dates:\n{available_dates}")
        return

    day_df = day_df.sort_values("created_datetime")
    day_df["time_str"] = day_df["created_datetime"].dt.strftime("%H:%M:%S")
    day_df["minute_of_day"] = day_df["created_datetime"].dt.hour * 60 + day_df["created_datetime"].dt.minute

    hourly_counts = day_df.groupby(day_df["created_datetime"].dt.hour).size()
    hourly_array = [int(hourly_counts.get(h, 0)) for h in range(24)]

    out = day_df[["latitude", "longitude", "time_str", "minute_of_day", "severity_score"]].rename(
        columns={"latitude": "lat", "longitude": "lon", "time_str": "time", "severity_score": "severity"}
    )
    out.attrs["date"] = date
    out.attrs["hourly_counts"] = hourly_array

    out.to_parquet(OUT_PATH, index=False)

    # Also save the small metadata (date + hourly_counts) as a sidecar,
    # since parquet attrs don't always survive round-trips reliably
    import json
    with open(OUT_PATH.replace(".parquet", "_meta.json"), "w") as f:
        json.dump({"date": date, "total_violations": len(out), "hourly_counts": hourly_array}, f)

    print(f"Saved {len(out)} points for {date} -> {OUT_PATH} ({out.memory_usage(deep=True).sum() / 1024:.1f} KB)")
    print(f"Hourly distribution: {hourly_array}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DEFAULT_DATE, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()
    main(args.date)