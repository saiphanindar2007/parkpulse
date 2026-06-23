"""
ParkPulse - Day 4: Forecast Confidence Tags

THE QUESTION THIS ANSWERS: "How much should I trust this specific
forecast number?" A bare number like '767.1 violations next week' implies
false precision -- this assigns an honest confidence tier to every
forecast, calibrated against forecast_hotspots.py's OWN validation
results (the tier-accuracy table printed when that script runs), not an
arbitrary or invented rule.

WHY VOLUME TIER, NOT JUST forecast_method OR weeks_of_history:
Checking the actual data: ALL 245 ranking-eligible hotspots use the
LightGBM method with 11+ weeks of history (the average_fallback path is
only ever used by hotspots BELOW the ranking-eligibility volume floor,
which never reach the dashboard's main views anyway). So tagging by
method or history-length alone would label every visible hotspot
identically -- useless. What actually varies, and what
forecast_hotspots.py's own validation already measured, is accuracy BY
VOLUME TIER:

    <10/wk     -> MAE is ~100% of the average value (essentially a coin flip
                  on the exact number, though the hotspot itself is real)
    10-50/wk   -> MAE is ~69% of average
    50-200/wk  -> MAE is ~51% of average
    200+/wk    -> MAE is ~37% of average (most reliable forecasts)

This script reads that exact calibration (duplicated here as constants,
sourced directly from a real run of forecast_hotspots.py -- documented
below so it doesn't silently drift if the model is retrained) and assigns
each hotspot's forecast a confidence tier based on which volume bucket
it falls into, plus a plain-language explanation of WHY.
"""

import pandas as pd
import numpy as np

SCORED_PATH = "data/hotspot_forecast.parquet"
OUT_PATH = "data/hotspot_forecast.parquet"  # adds columns in place

# --- Calibration table: copied directly from a real run of
# forecast_hotspots.py's printed "Forecast accuracy by hotspot volume
# tier" output. If you retrain the forecaster, re-run that script and
# update these numbers to match -- they are NOT re-derived here so this
# script stays fast and doesn't require re-running the full model. ---
ACCURACY_BY_TIER = {
    "<10/wk":    {"mae_pct_of_avg": 100.6, "n_obs": 1857},
    "10-50/wk":  {"mae_pct_of_avg": 68.9,  "n_obs": 469},
    "50-200/wk": {"mae_pct_of_avg": 51.3,  "n_obs": 139},
    "200+/wk":   {"mae_pct_of_avg": 37.1,  "n_obs": 14},
}

TIER_BINS = [0, 10, 50, 200, float("inf")]
TIER_LABELS = ["<10/wk", "10-50/wk", "50-200/wk", "200+/wk"]


def assign_confidence(mae_pct):
    """Maps the validated MAE% for a tier to a simple HIGH/MEDIUM/LOW tag.
    Thresholds chosen so the four real tiers split sensibly across three
    labels (50%/37% -> HIGH, 69% -> MEDIUM, 100% -> LOW), not arbitrary
    round numbers picked to look good."""
    if mae_pct <= 55:
        return "HIGH"
    elif mae_pct <= 80:
        return "MEDIUM"
    else:
        return "LOW"


def main():
    df = pd.read_parquet(SCORED_PATH)

    df["volume_tier"] = pd.cut(
        df["forecast_next_week"].fillna(0), bins=TIER_BINS, labels=TIER_LABELS
    )

    def get_mae_pct(tier):
        if pd.isna(tier):
            return None
        return ACCURACY_BY_TIER[tier]["mae_pct_of_avg"]

    df["forecast_mae_pct"] = df["volume_tier"].apply(get_mae_pct)
    df["confidence_tag"] = df["forecast_mae_pct"].apply(
        lambda x: assign_confidence(x) if x is not None else None
    )

    def plain_language(row):
        if pd.isna(row["volume_tier"]) or row["forecast_next_week"] is None:
            return "Insufficient data for a confidence estimate."
        tier = row["volume_tier"]
        mae_pct = row["forecast_mae_pct"]
        n_obs = ACCURACY_BY_TIER[tier]["n_obs"]
        return (
            f"Validated against {n_obs} similar-volume hotspots held out during testing: "
            f"forecasts in this volume range ({tier}) are typically off by about "
            f"{mae_pct:.0f}% of the predicted value."
        )

    df["confidence_explanation"] = df.apply(plain_language, axis=1)

    df.to_parquet(OUT_PATH, index=False)

    print("Confidence tag distribution among ranking-eligible hotspots:")
    eligible = df[df["is_ranking_eligible"]]
    print(eligible["confidence_tag"].value_counts())
    print("\nSample:")
    print(eligible[["hotspot_id", "dominant_junction", "forecast_next_week", "volume_tier", "confidence_tag"]].head(10).to_string(index=False))
    print(f"\nUpdated {OUT_PATH} with volume_tier, forecast_mae_pct, confidence_tag, confidence_explanation columns")


if __name__ == "__main__":
    main()