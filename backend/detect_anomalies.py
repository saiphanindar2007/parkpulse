"""
ParkPulse - Day 4: Anomaly Detector

THE QUESTION THIS ANSWERS: "Is something unusual happening RIGHT NOW at
any hotspot, that the static ranking/forecast wouldn't catch until next
week's report?"

CIS (score_hotspots.py) ranks hotspots by their OVERALL profile across
the whole dataset. The forecast (forecast_hotspots.py) predicts next
week's expected volume. Neither is designed to flag "this specific
hotspot just did something it's never done before" -- that's a distinct
problem (anomaly detection), solved here with a separate, simpler,
more interpretable method on purpose: rolling robust z-scores.

METHOD (deliberately simple and explainable, not a black-box model):
For each hotspot with enough history, compute its most recent week's
violation count, then compare against the MEDIAN and MAD (median
absolute deviation) of its own PRIOR weeks (excluding the most recent
week itself, to avoid leakage). MAD-based z-score is used instead of
mean/std because weekly counts are spiky and right-skewed (a single
unusual week shouldn't distort the very baseline it's being compared
against, which is exactly what happens with mean/std on small samples).

A hotspot is flagged anomalous if |robust z-score| > ANOMALY_THRESHOLD,
separately reported as a SPIKE (sudden increase -- possible new
construction, event, or enforcement gap) or a DROP (sudden decrease --
possible enforcement actually working, or a sensor/reporting gap worth
checking).

This is intentionally NOT the same model as forecast_hotspots.py (LightGBM
regression). Using a separate, simpler statistical method for anomaly
flagging is a deliberate design choice: forecasting and anomaly detection
are different problems (predicting a number vs. flagging "is this number
weird"), and conflating them into one model would make both worse at
their actual job.
"""

import pandas as pd
import numpy as np

HOTSPOTS_PATH = "data/hotspots.parquet"
SCORED_PATH = "data/hotspot_forecast.parquet"
ANOMALIES_OUT = "data/anomalies.parquet"

MIN_PRIOR_WEEKS = 5       # need at least this many prior weeks to establish a baseline
ANOMALY_Z_THRESHOLD = 2.5  # |z| beyond this is flagged (robust z-score, MAD-based)


def robust_zscore(latest_value, prior_values):
    """MAD-based robust z-score. Returns None if prior_values has no spread
    (MAD=0) since a z-score is meaningless against a perfectly flat baseline."""
    prior = np.array(prior_values)
    median = np.median(prior)
    mad = np.median(np.abs(prior - median))
    if mad == 0:
        # Fallback: if MAD is exactly 0 (e.g. every prior week had the same
        # count), use a tiny epsilon scaled to the median so we don't divide
        # by zero, but still flag genuinely large jumps.
        mad = max(median * 0.1, 0.5)
    # 0.6745 scales MAD to be comparable to standard deviation under
    # normality -- standard convention for robust z-scores.
    return 0.6745 * (latest_value - median) / mad, median, mad


def build_weekly_panel(hotspots):
    weekly = hotspots.groupby(["hotspot_id", "week"]).size().reset_index(name="violation_count")
    weekly["week_start"] = pd.to_datetime(weekly["week"].str.split("/").str[0])
    return weekly.sort_values(["hotspot_id", "week_start"]).reset_index(drop=True)


def main():
    hotspots = pd.read_parquet(HOTSPOTS_PATH)
    hotspots = hotspots[~hotspots["hotspot_id"].str.contains("noise")].copy()
    scored = pd.read_parquet(SCORED_PATH)

    weekly = build_weekly_panel(hotspots)

    # Drop the final partial week (same reasoning as forecast_hotspots.py:
    # the dataset cuts off mid-week, which would look like a fake "drop")
    max_week_start = weekly["week_start"].max()
    weekly = weekly[weekly["week_start"] < max_week_start].copy()

    results = []
    for hotspot_id, grp in weekly.groupby("hotspot_id"):
        grp = grp.sort_values("week_start")
        counts = grp["violation_count"].tolist()
        if len(counts) < MIN_PRIOR_WEEKS + 1:
            continue  # not enough history to establish a baseline safely

        latest = counts[-1]
        prior = counts[:-1]
        z, median, mad = robust_zscore(latest, prior)

        if abs(z) >= ANOMALY_Z_THRESHOLD:
            results.append({
                "hotspot_id": hotspot_id,
                "latest_week": grp["week"].iloc[-1],
                "latest_count": int(latest),
                "baseline_median": round(float(median), 1),
                "baseline_mad": round(float(mad), 1),
                "robust_zscore": round(float(z), 2),
                "anomaly_type": "SPIKE" if z > 0 else "DROP",
                "weeks_of_baseline": len(prior),
            })

    anomalies = pd.DataFrame(results)
    if anomalies.empty:
        print("No anomalies found at the current threshold.")
        anomalies = pd.DataFrame(columns=[
            "hotspot_id", "latest_week", "latest_count", "baseline_median",
            "baseline_mad", "robust_zscore", "anomaly_type", "weeks_of_baseline",
            "dominant_junction", "dominant_station", "congestion_impact_score",
        ])
    else:
        anomalies = anomalies.merge(
            scored[["hotspot_id", "dominant_junction", "dominant_station", "congestion_impact_score"]],
            on="hotspot_id", how="left",
        )
        anomalies = anomalies.sort_values("robust_zscore", key=abs, ascending=False).reset_index(drop=True)

    anomalies.to_parquet(ANOMALIES_OUT, index=False)

    n_spikes = (anomalies["anomaly_type"] == "SPIKE").sum() if not anomalies.empty else 0
    n_drops = (anomalies["anomaly_type"] == "DROP").sum() if not anomalies.empty else 0
    print(f"Evaluated {weekly['hotspot_id'].nunique()} hotspots, {(weekly.groupby('hotspot_id').size() >= MIN_PRIOR_WEEKS + 1).sum()} had enough history")
    print(f"Flagged {len(anomalies)} anomalies at |z| >= {ANOMALY_Z_THRESHOLD}: {n_spikes} spikes, {n_drops} drops")

    if not anomalies.empty:
        print("\nTop anomalies by |z-score|:")
        print(anomalies[["hotspot_id", "dominant_junction", "anomaly_type", "latest_count",
                          "baseline_median", "robust_zscore"]].head(15).to_string(index=False))

    print(f"\nSaved to {ANOMALIES_OUT}")


if __name__ == "__main__":
    main()