"""
ParkPulse - Day 2, Step 2: Congestion Impact Score (CIS)

The Congestion Impact Score is a composite, hotspot-level metric combining:
  1. Violation Volume      - raw scale of the problem at this hotspot
  2. Severity Weight       - not all parking violations obstruct traffic
                             equally; footpath/junction/main-road parking
                             chokes flow far more than generic no-parking
  3. Time Concentration    - a hotspot where violations cluster tightly
                             into specific hours (e.g. evening peak) has
                             more *predictable*, actionable real-world
                             impact than one spread evenly across the day
  4. Recency               - hotspots trending upward recently matter
                             more for *today's* deployment decision than
                             ones that were bad in November but have cooled

Each sub-score is normalized to 0-100 before combining, so the weights in
FINAL_WEIGHTS directly express relative importance and are easy to justify
in a pitch deck.
"""
import pandas as pd
import numpy as np

HOTSPOTS_PATH = "data/hotspots.parquet"
SUMMARY_PATH = "data/hotspot_summary.parquet"
SCORED_OUT = "data/hotspot_scored.parquet"

# --- Severity weights (1-10 scale) ---
# Rationale: violations that physically narrow a carriageway or block a
# junction/crossing/footpath have outsized impact on flow versus generic
# "no parking" in a low-traffic side street. Weights are a deliberate,
# documented judgment call -- not learned from data, since we have no
# ground-truth congestion measurements to fit against in this dataset.
SEVERITY_WEIGHTS = {
    "PARKING ON FOOTPATH": 9,
    "PARKING NEAR ROAD CROSSING": 9,
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS": 9,
    "PARKING IN A MAIN ROAD": 8,
    "DOUBLE PARKING": 8,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 8,
    "PARKING OTHER THAN BUS STOP": 7,
    "PARKING OPPOSITE TO ANOTHER PARKED VEHICLE": 7,
    "WRONG PARKING": 6,
    "NO PARKING": 5,
    "AGAINST ONE WAY/NO ENTRY": 8,
    "OBSTRUCTING DRIVER": 6,
    "VIOLATING LANE DISIPLINE": 6,
    "H T V PROHIBITED": 5,
    # Non-congestion violations present in the data but not relevant to
    # parking-induced congestion; weighted low so they barely affect CIS
    "DEFECTIVE NUMBER PLATE": 1,
    "REFUSE TO GO FOR HIRE": 1,
    "USING BLACK FILM/OTHER MATERIALS": 1,
    "DEMANDING EXCESS FARE": 1,
    "WITHOUT SIDE MIRROR": 1,
    "FAIL TO USE SAFETY BELTS": 1,
}
DEFAULT_WEIGHT = 4  # fallback for any violation type not explicitly listed

# --- Final composite weights (must sum to 1.0) ---
# NOTE: weights were rebalanced after testing against the real dataset.
# time_concentration has an inherent structural anti-correlation with
# volume (a hotspot active for 5 months naturally spreads across more
# hours/weeks than one seen for 3 weeks), so its original 0.20 weight
# was enough to let small, sparse hotspots consistently outrank massive,
# chronic ones like Elite Junction (15,484 violations) and Safina Plaza
# (12,599 violations) -- the opposite of what a deployment-priority tool
# should surface. Volume and severity (the two components that directly
# reflect real-world scale of the problem) now carry more weight; time
# concentration is kept as a smaller modifier rather than a primary driver.
FINAL_WEIGHTS = {
    "volume": 0.45,
    "severity": 0.30,
    "time_concentration": 0.10,
    "recency": 0.15,
}


def normalize_0_100(series, log_scale=False):
    if log_scale:
        series = np.log1p(series)
    if series.max() == series.min():
        return pd.Series(50.0, index=series.index)  # flat series -> neutral score
    return (series - series.min()) / (series.max() - series.min()) * 100


# Hotspots below this volume are too sparse for time-concentration/recency
# to be statistically meaningful (e.g. 5 violations all in one hour just
# by chance) and would otherwise distort rankings disproportionately to
# their real-world traffic impact. They're kept in the output for
# completeness but excluded from the top-N ranking used for deployment.
#
# NOTE: 30 was the original threshold but testing against the real data
# showed it's nowhere near high enough -- hotspots with 30-100 violations
# still regularly hit 80-100 on time_concentration/recency by pure chance
# (e.g. all violations happening to fall in one recent week), which let
# tiny hotspots outrank Elite Junction (15,484 violations) and Safina
# Plaza (12,599 violations) in the original run. Raised to 150, which is
# roughly the point where the time/recency components stop swinging
# wildly in spot-checks below.
MIN_VOLUME_FOR_RANKING = 150

# Beyond just raising the eligibility floor, sparse hotspots' time/recency
# scores are shrunk toward a neutral midpoint (50) proportional to how
# little data backs them up, using a simple confidence multiplier. This
# stops, e.g., a 150-violation hotspot from still swinging to 100 on
# recency purely by chance while contributing full weight to the final
# score. Hotspots with CONFIDENCE_FULL_AT or more violations are
# unaffected; the shrinkage phases in below that.
CONFIDENCE_FULL_AT = 1000


def confidence_weight(volume):
    return np.minimum(volume / CONFIDENCE_FULL_AT, 1.0)


def compute_time_concentration(group):
    """
    Returns a 0-1 score: how concentrated this hotspot's violations are
    into a narrow band of hours, using normalized entropy over the 24
    hourly bins. Low entropy (concentrated) -> high score.
    """
    hour_counts = group["hour"].value_counts(normalize=True)
    # Shannon entropy over the 24 possible hours
    entropy = -(hour_counts * np.log(hour_counts)).sum()
    max_entropy = np.log(24)  # entropy if perfectly uniform across 24 hours
    concentration = 1 - (entropy / max_entropy)
    return concentration


def compute_recency(group, dataset_max_date):
    """
    Returns a 0-1+ trend ratio: average weekly volume in the most recent
    30 days vs. the prior 30-60 day window. >1 means the hotspot is
    trending up recently; <1 means it's cooling off.

    NOTE: an earlier version of this used raw "share of all-time
    violations falling in the last 30 days." That structurally penalized
    chronic, persistently bad hotspots -- a junction hit constantly for
    5 months naturally has a SMALLER share of its total in any single
    recent window than a hotspot that only appeared 3 weeks ago, even
    though the chronic one is the bigger real-world problem. Using a
    trend ratio instead measures actual momentum without that bias.
    """
    recent_cutoff = dataset_max_date - pd.Timedelta(days=30)
    prior_cutoff = dataset_max_date - pd.Timedelta(days=60)

    recent_count = (group["created_datetime"] > recent_cutoff).sum()
    prior_count = (
        (group["created_datetime"] > prior_cutoff)
        & (group["created_datetime"] <= recent_cutoff)
    ).sum()

    if prior_count == 0:
        # Brand new hotspot with no prior-window history: treat as
        # moderately trending-up rather than infinite/undefined.
        return 1.5 if recent_count > 0 else 1.0
    return recent_count / prior_count


def main():
    df = pd.read_parquet(HOTSPOTS_PATH)
    df = df[~df["hotspot_id"].str.contains("noise")].copy()
    summary = pd.read_parquet(SUMMARY_PATH)

    dataset_max_date = df["created_datetime"].max()
    print(f"Dataset max date: {dataset_max_date}")

    # --- Severity: average weight per record, exploded across violation types ---
    exploded = df.explode("violation_list").rename(columns={"violation_list": "violation"})
    exploded["violation"] = exploded["violation"].str.strip()
    exploded["severity_w"] = exploded["violation"].map(SEVERITY_WEIGHTS).fillna(DEFAULT_WEIGHT)
    severity_per_hotspot = exploded.groupby("hotspot_id")["severity_w"].mean().rename("avg_severity")

    # --- Time concentration per hotspot ---
    time_conc = df.groupby("hotspot_id").apply(compute_time_concentration).rename("time_concentration")

    # --- Recency per hotspot ---
    recency = df.groupby("hotspot_id").apply(
        lambda g: compute_recency(g, dataset_max_date)
    ).rename("recency_share")

    scored = summary.set_index("hotspot_id").join([severity_per_hotspot, time_conc, recency])
    scored = scored.reset_index()

    # Normalize each component to 0-100 (volume log-scaled to handle the
    # heavy right-skew: a few junctions have 15K+ violations while the
    # median hotspot has ~30, so raw min-max would crush almost every
    # hotspot's volume score toward zero)
    scored["volume_norm"] = normalize_0_100(scored["violation_count"], log_scale=True)
    scored["severity_norm"] = normalize_0_100(scored["avg_severity"])
    scored["time_conc_norm"] = normalize_0_100(scored["time_concentration"])
    scored["recency_norm"] = normalize_0_100(scored["recency_share"])

    # Shrink time-concentration and recency toward neutral (50) for
    # low-volume hotspots, proportional to confidence_weight. Severity is
    # NOT shrunk since it's an average over actual recorded violations and
    # doesn't suffer the same "all in one lucky week" noise problem.
    conf = confidence_weight(scored["violation_count"])
    scored["time_conc_norm"] = conf * scored["time_conc_norm"] + (1 - conf) * 50
    scored["recency_norm"] = conf * scored["recency_norm"] + (1 - conf) * 50

    scored["congestion_impact_score"] = (
        FINAL_WEIGHTS["volume"] * scored["volume_norm"]
        + FINAL_WEIGHTS["severity"] * scored["severity_norm"]
        + FINAL_WEIGHTS["time_concentration"] * scored["time_conc_norm"]
        + FINAL_WEIGHTS["recency"] * scored["recency_norm"]
    ).round(2)

    scored["is_ranking_eligible"] = scored["violation_count"] >= MIN_VOLUME_FOR_RANKING

    scored = scored.sort_values("congestion_impact_score", ascending=False).reset_index(drop=True)
    scored["rank_overall"] = scored.index + 1

    # Separate, deployment-facing ranking that excludes statistically
    # noisy low-volume hotspots
    eligible = scored[scored["is_ranking_eligible"]].copy()
    eligible = eligible.sort_values("congestion_impact_score", ascending=False).reset_index(drop=True)
    eligible["rank_eligible"] = eligible.index + 1
    scored = scored.merge(eligible[["hotspot_id", "rank_eligible"]], on="hotspot_id", how="left")

    scored.to_parquet(SCORED_OUT, index=False)
    print(f"Saved {len(scored)} scored hotspots to {SCORED_OUT}")
    print(f"({scored['is_ranking_eligible'].sum()} are ranking-eligible with >= {MIN_VOLUME_FOR_RANKING} violations)")
    print("\nTop 15 hotspots by Congestion Impact Score (ranking-eligible only):")
    top15 = scored[scored["is_ranking_eligible"]].sort_values("rank_eligible").head(15)
    print(top15[[
        "rank_eligible", "hotspot_id", "dominant_junction", "violation_count",
        "avg_severity", "congestion_impact_score"
    ]].to_string(index=False))


if __name__ == "__main__":
    main()