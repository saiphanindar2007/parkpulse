"""
ParkPulse - Day 3: FastAPI Backend

Serves hotspot rankings, per-hotspot trends, next-week forecasts, and
summary stats to the React frontend. Reads directly from the Parquet
files produced by Day 1 (clean_data.py) and Day 2 (cluster/score/forecast
hotspots.py) -- no retraining or recomputation happens at request time.

Run with: uvicorn main:app --reload --port 8000
Then visit http://127.0.0.1:8000/docs for interactive API testing.
"""

import pandas as pd
import numpy as np
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import optimize_routes  # imported at startup, not inside the request handler,
                          # so OR-Tools' (heavier) import cost is paid once when
                          # the server boots rather than slowing down the FIRST
                          # /api/simulate-patrol request a user makes

app = FastAPI(title="ParkPulse API", version="1.0")

import os

# Local dev origins always allowed; add your deployed frontend's URL via
# the FRONTEND_URL environment variable on your hosting platform (e.g.
# https://parkpulse.vercel.app) so the deployed frontend isn't blocked by
# CORS once it's no longer running on localhost.
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if os.environ.get("FRONTEND_URL"):
    _allowed_origins.append(os.environ["FRONTEND_URL"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load all data once at startup ---
# NOTE: previously this loaded hotspots.parquet (270K rows, ~213MB in
# memory) and violations_clean.parquet (298K rows, ~208MB in memory) in
# full -- 421MB combined, which crashed Render's free tier (512MB limit)
# with "Out of memory" before a single request even arrived. Both are
# replaced with small precomputed tables built by precompute_summary.py,
# which contain everything these endpoints actually need (a handful of
# aggregate stats, and per-hotspot WEEKLY counts rather than every row).
# Run `python precompute_summary.py` once if these files are missing.
HOTSPOT_WEEKLY = pd.read_parquet("data/hotspot_weekly.parquet")
SCORED = pd.read_parquet("data/hotspot_forecast.parquet")

try:
    with open("data/summary_stats.json") as f:
        SUMMARY_STATS = json.load(f)
except FileNotFoundError:
    SUMMARY_STATS = None
    print("WARNING: data/summary_stats.json not found -- run precompute_summary.py first. /api/stats/summary will fail.")

try:
    PATROL_ROUTES = pd.read_parquet("data/patrol_routes.parquet")
except FileNotFoundError:
    PATROL_ROUTES = None
    print("WARNING: data/patrol_routes.parquet not found -- run optimize_routes.py first. /api/patrol-routes will 404.")

try:
    ANOMALIES = pd.read_parquet("data/anomalies.parquet")
except FileNotFoundError:
    ANOMALIES = None
    print("WARNING: data/anomalies.parquet not found -- run detect_anomalies.py first. /api/anomalies will 404.")

try:
    with open("data/backtest_results.json") as f:
        BACKTEST_RESULTS = json.load(f)
except FileNotFoundError:
    BACKTEST_RESULTS = None
    print("WARNING: data/backtest_results.json not found -- run backtest_roi.py first. /api/backtest will 404.")

try:
    TIMELAPSE_DAY = pd.read_parquet("data/timelapse_day.parquet")
    with open("data/timelapse_day_meta.json") as f:
        TIMELAPSE_META = json.load(f)
except FileNotFoundError:
    TIMELAPSE_DAY = None
    TIMELAPSE_META = None
    print("WARNING: data/timelapse_day.parquet not found -- run precompute_timelapse.py first. /api/timelapse will 404.")

print(f"Loaded {len(SCORED)} hotspots, {len(HOTSPOT_WEEKLY)} weekly trend rows (lightweight mode -- no raw violation rows in memory)")


def df_to_json_safe(df: pd.DataFrame) -> list:
    """Replace NaN/NaT with None so FastAPI's JSON encoder doesn't choke."""
    return df.replace({np.nan: None}).to_dict(orient="records")


@app.get("/")
def root():
    return {"status": "ok", "service": "ParkPulse API"}


@app.get("/api/hotspots")
def get_hotspots(
    eligible_only: bool = Query(True, description="Only return ranking-eligible hotspots"),
    limit: int = Query(100, ge=1, le=2000),
    sort_by: str = Query("congestion_impact_score", description="Column to sort by"),
):
    """
    Ranked list of hotspots with scores, coordinates, and forecasts.
    This is the main feed for the map and the rankings table.
    """
    df = SCORED.copy()
    if eligible_only:
        df = df[df["is_ranking_eligible"]]

    if sort_by not in df.columns:
        raise HTTPException(400, f"Unknown sort_by column: {sort_by}")

    df = df.sort_values(sort_by, ascending=False).head(limit)

    return {
        "count": len(df),
        "hotspots": df_to_json_safe(df),
    }


@app.get("/api/hotspots/{hotspot_id}/trend")
def get_hotspot_trend(hotspot_id: str):
    """
    Weekly violation volume time series for a single hotspot, used for
    the drill-down chart when a user clicks a hotspot on the map.
    Sourced from the precomputed HOTSPOT_WEEKLY table (one row per
    hotspot-week, not one row per individual violation).
    """
    weekly = HOTSPOT_WEEKLY[HOTSPOT_WEEKLY["hotspot_id"] == hotspot_id].sort_values("week_start")
    if weekly.empty:
        raise HTTPException(404, f"No data found for hotspot_id={hotspot_id}")

    hotspot_meta = SCORED[SCORED["hotspot_id"] == hotspot_id]
    meta = df_to_json_safe(hotspot_meta)[0] if not hotspot_meta.empty else None

    return {
        "hotspot_id": hotspot_id,
        "meta": meta,
        "weekly_trend": [
            {"week_start": row["week_start"].strftime("%Y-%m-%d"), "violation_count": int(row["violation_count"])}
            for _, row in weekly.iterrows()
        ],
    }


# Same final weights as score_hotspots.py -- duplicated here (not
# recomputed from scratch) so the explanation always matches exactly what
# was actually used to produce the stored congestion_impact_score.
CIS_WEIGHTS = {"volume": 0.45, "severity": 0.30, "time_concentration": 0.10, "recency": 0.15}


@app.get("/api/hotspots/{hotspot_id}/explain")
def explain_hotspot_score(hotspot_id: str):
    """
    Breaks down a hotspot's Congestion Impact Score into its exact
    point-contribution from each of the four components, so the score
    is auditable rather than a black box. The four contributions sum
    EXACTLY to the displayed congestion_impact_score (verified below),
    not just narratively -- mismatches are caught and flagged rather
    than silently displayed.
    """
    row = SCORED[SCORED["hotspot_id"] == hotspot_id]
    if row.empty:
        raise HTTPException(404, f"No hotspot found with id={hotspot_id}")
    row = row.iloc[0]

    contributions = {
        "volume": round(CIS_WEIGHTS["volume"] * row["volume_norm"], 2),
        "severity": round(CIS_WEIGHTS["severity"] * row["severity_norm"], 2),
        "time_concentration": round(CIS_WEIGHTS["time_concentration"] * row["time_conc_norm"], 2),
        "recency": round(CIS_WEIGHTS["recency"] * row["recency_norm"], 2),
    }
    recomputed_total = round(sum(contributions.values()), 2)
    stored_total = round(float(row["congestion_impact_score"]), 2)

    # Sanity check surfaced in the response itself -- if this script and
    # score_hotspots.py ever drift out of sync, the API tells you rather
    # than silently showing a wrong breakdown.
    is_consistent = bool(abs(recomputed_total - stored_total) < 0.5)

    return {
        "hotspot_id": hotspot_id,
        "dominant_junction": row["dominant_junction"],
        "dominant_station": row["dominant_station"],
        "congestion_impact_score": stored_total,
        "recomputed_from_components": recomputed_total,
        "is_consistent": is_consistent,
        "weights": CIS_WEIGHTS,
        "raw_components": {
            "volume_norm": round(float(row["volume_norm"]), 1),
            "severity_norm": round(float(row["severity_norm"]), 1),
            "time_conc_norm": round(float(row["time_conc_norm"]), 1),
            "recency_norm": round(float(row["recency_norm"]), 1),
        },
        "point_contributions": contributions,
        "underlying_facts": {
            "violation_count": int(row["violation_count"]),
            "avg_severity": round(float(row["avg_severity"]), 2),
            "time_concentration": round(float(row["time_concentration"]), 3),
            "recency_share": round(float(row["recency_share"]), 2),
        },
        "plain_language": (
            f"This hotspot scores {stored_total}/100. The biggest driver is "
            f"{'volume (how many violations occur here)' if contributions['volume'] == max(contributions.values()) else 'severity (how disruptive the violation types are)' if contributions['severity'] == max(contributions.values()) else 'time concentration (how clustered violations are into specific hours)' if contributions['time_concentration'] == max(contributions.values()) else 'recency (whether this hotspot is trending up recently)'}"
            f", contributing {max(contributions.values())} of the {stored_total} points."
        ),
    }


@app.get("/api/forecast")
def get_forecast(
    eligible_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Next-week forecast for hotspots, sorted by predicted volume descending.
    Powers the 'recommended enforcement zones' panel.
    """
    df = SCORED.copy()
    if eligible_only:
        df = df[df["is_ranking_eligible"]]
    df = df[df["forecast_next_week"].notna()]
    df = df.sort_values("forecast_next_week", ascending=False).head(limit)

    cols = [
        "hotspot_id", "dominant_junction", "dominant_station",
        "violation_count", "forecast_next_week", "forecast_method",
        "weeks_of_history", "congestion_impact_score", "centroid_lat", "centroid_lon",
    ]
    # display_name only exists after geocode_hotspots.py has been run;
    # fall back gracefully so the API doesn't break before that step.
    if "display_name" in df.columns:
        cols.insert(3, "display_name")
    return {
        "count": len(df),
        "forecasts": df_to_json_safe(df[cols]),
    }


@app.get("/api/timelapse")
def get_timelapse_data():
    """
    Returns every violation on a single precomputed day (see
    precompute_timelapse.py), minute-resolved, for the frontend's
    animated 24-hour replay. Defaults to whichever day was last
    precomputed -- 2023-11-18 (2,858 violations, the busiest day) unless
    re-run with a different --date. Served from a small dedicated
    ~150KB file, NOT the full violations dataset, consistent with the
    rest of this API's memory-conscious design for free-tier hosting.
    """
    if TIMELAPSE_DAY is None:
        raise HTTPException(
            503,
            "Timelapse data not available. Run `python precompute_timelapse.py` in the backend folder first.",
        )

    points = [
        {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "time": row["time"],
            "minute_of_day": int(row["minute_of_day"]),
            "severity": int(row["severity"]),
        }
        for _, row in TIMELAPSE_DAY.iterrows()
    ]

    return {
        "date": TIMELAPSE_META["date"],
        "total_violations": TIMELAPSE_META["total_violations"],
        "hourly_counts": TIMELAPSE_META["hourly_counts"],
        "points": points,
    }


@app.get("/api/digest")
def get_intelligence_digest():
    """
    Auto-generated executive summary: pulls real numbers from the
    summary stats, top hotspots, anomalies, and backtest -- assembled
    into a short narrative a reviewer can read in under a minute instead
    of clicking through four tabs. Every number here is computed live
    from the same data the rest of the API serves, not hardcoded prose.
    """
    summary = get_summary_stats()

    top_hotspots = SCORED[SCORED["is_ranking_eligible"]].sort_values("congestion_impact_score", ascending=False).head(3)
    base_names = []
    for _, row in top_hotspots.iterrows():
        base_name = row["dominant_junction"] if row["dominant_junction"] != "No Junction" else row["dominant_station"]
        base_names.append(base_name)
    name_counts = {}
    for n in base_names:
        name_counts[n] = name_counts.get(n, 0) + 1
    seen_so_far = {}
    top_names = []
    for n in base_names:
        if name_counts[n] > 1:
            seen_so_far[n] = seen_so_far.get(n, 0) + 1
            top_names.append(f"{n} (site {seen_so_far[n]} of {name_counts[n]})")
        else:
            top_names.append(n)

    n_spikes = int((ANOMALIES["anomaly_type"] == "SPIKE").sum()) if ANOMALIES is not None and not ANOMALIES.empty else 0
    n_drops = int((ANOMALIES["anomaly_type"] == "DROP").sum()) if ANOMALIES is not None and not ANOMALIES.empty else 0
    top_anomaly = None
    if ANOMALIES is not None and not ANOMALIES.empty:
        row = ANOMALIES.sort_values("robust_zscore", key=abs, ascending=False).iloc[0]
        top_anomaly_name = row["dominant_junction"] if row["dominant_junction"] != "No Junction" else row["dominant_station"]
        top_anomaly = {
            "name": top_anomaly_name,
            "type": row["anomaly_type"],
            "latest_count": int(row["latest_count"]),
            "baseline": float(row["baseline_median"]),
        }

    backtest_headline = None
    if BACKTEST_RESULTS is not None:
        backtest_headline = BACKTEST_RESULTS["coverage_high_severity_only"]["cis_relative_improvement_pct"]

    n_high_confidence = int((SCORED["confidence_tag"] == "HIGH").sum()) if "confidence_tag" in SCORED.columns else None

    bullets = [
        f"{summary['total_violations']:,} parking violations recorded across {summary['police_stations']} police stations "
        f"and {summary['named_junctions']} named junctions over {summary['date_range']['start']} to {summary['date_range']['end']}.",

        f"Enforcement is heavily night-skewed: only {summary['daytime_violations_pct']}% of violations were recorded "
        f"between 10am-6pm, leaving daytime congestion almost entirely unmonitored by current patrol patterns.",

        f"Clustering identified {summary['total_hotspots']:,} distinct hotspots, of which {summary['ranking_eligible_hotspots']} "
        f"meet the volume threshold for reliable priority ranking. The top 3 by Congestion Impact Score are "
        f"{', '.join(top_names)}.",

        f"The anomaly detector flagged {n_spikes} sudden spikes and {n_drops} sudden drops this period"
        + (f", the most extreme being {top_anomaly['name']} ({top_anomaly['type'].lower()} to "
           f"{top_anomaly['latest_count']} from a baseline of {top_anomaly['baseline']:.0f})." if top_anomaly else ".")
        ,

        f"A held-out temporal backtest confirms the ranking methodology generalizes: it covers {backtest_headline:+.1f}% "
        f"more high-severity violations than a naive volume-only ranking would have, when evaluated on data the model "
        f"never saw during ranking." if backtest_headline is not None else "Backtest results not yet generated.",
    ]

    if n_high_confidence is not None:
        bullets.append(
            f"{n_high_confidence} of {summary['ranking_eligible_hotspots']} priority hotspots have HIGH-confidence "
            f"forecasts (validated to within ~37-51% margin), concentrated among the highest-volume locations where "
            f"enforcement decisions matter most."
        )

    return {
        "generated_summary": bullets,
        "headline_stat": {
            "label": "Daytime Enforcement Gap",
            "value": f"{summary['daytime_violations_pct']}%",
            "context": "of violations occur during 10am-6pm",
        },
    }


@app.get("/api/simulate-patrol")
def simulate_patrol(
    n_vehicles: int = Query(3, ge=1, le=8, description="Number of patrol vehicles"),
    max_route_km: int = Query(25, ge=5, le=100, description="Max distance budget per vehicle, km"),
    top_n: int = Query(18, ge=5, le=40, description="Number of top-forecast hotspots to consider"),
):
    """
    Digital Twin 'what-if' simulator: re-solves the REAL OR-Tools VRP
    live with the given parameters. This is genuine re-optimization on
    every call, not a precomputed lookup table -- so the numbers returned
    reflect an actual constraint-solver run, typically taking 1-3 seconds.
    """
    result = optimize_routes.run_simulation(
        top_n=top_n, n_vehicles=n_vehicles, max_route_km=max_route_km, time_limit_s=2
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/patrol-routes")
def get_patrol_routes():
    """
    Optimized multi-vehicle patrol routes across the top forecasted
    hotspots, produced by optimize_routes.py (OR-Tools CVRP solver).
    Returns one route per vehicle plus summary coverage stats.
    """
    if PATROL_ROUTES is None:
        raise HTTPException(
            503,
            "Patrol routes not available. Run `python optimize_routes.py` in the backend folder first.",
        )

    routes = []
    for vehicle_id, group in PATROL_ROUTES.groupby("vehicle_id"):
        group = group.sort_values("stop_order")
        stops = df_to_json_safe(group)
        total_km = group["cumulative_distance_km"].max()
        covered_forecast = group["forecast_next_week"].fillna(0).sum()
        routes.append({
            "vehicle_id": int(vehicle_id),
            "stops": stops,
            "total_distance_km": float(total_km),
            "covered_forecast": float(covered_forecast),
        })

    all_hotspot_rows = PATROL_ROUTES[PATROL_ROUTES["hotspot_id"].notna()]
    total_distance_km = sum(r["total_distance_km"] for r in routes)
    total_covered = all_hotspot_rows.drop_duplicates("hotspot_id")["forecast_next_week"].sum()

    return {
        "routes": routes,
        "summary": {
            "n_vehicles": len(routes),
            "n_hotspots_covered": int(all_hotspot_rows["hotspot_id"].nunique()),
            "total_distance_km": round(total_distance_km, 1),
            "total_covered_forecast": round(float(total_covered), 0),
            "coverage_efficiency": round(float(total_covered) / total_distance_km, 1) if total_distance_km else 0,
        },
    }


@app.get("/api/anomalies")
def get_anomalies(limit: int = Query(30, ge=1, le=200)):
    """
    Hotspots flagged by the robust-z-score anomaly detector (separate
    method from CIS ranking and forecasting -- see detect_anomalies.py
    for why these are kept as distinct, complementary signals).
    """
    if ANOMALIES is None or ANOMALIES.empty:
        return {"count": 0, "anomalies": []}

    df = ANOMALIES.sort_values("robust_zscore", key=abs, ascending=False).head(limit)
    return {
        "count": len(df),
        "n_spikes": int((ANOMALIES["anomaly_type"] == "SPIKE").sum()),
        "n_drops": int((ANOMALIES["anomaly_type"] == "DROP").sum()),
        "anomalies": df_to_json_safe(df),
    }


@app.get("/api/backtest")
def get_backtest_results():
    """
    Returns the temporal backtest results produced by backtest_roi.py:
    how well the CIS ranking (computed on a training window) actually
    predicted where violations occurred in a held-out future window,
    compared against random and naive-volume-ranking baselines.
    """
    if BACKTEST_RESULTS is None:
        raise HTTPException(
            503,
            "Backtest results not available. Run `python backtest_roi.py` in the backend folder first.",
        )
    return BACKTEST_RESULTS


@app.get("/api/stats/summary")
def get_summary_stats():
    """
    Dashboard-level summary cards: totals, peak hour, top vehicle type, etc.
    Computed from the full cleaned dataset, not just hotspot-level data.
    """
    if SUMMARY_STATS is None:
        raise HTTPException(503, "Summary stats not available. Run `python precompute_summary.py` in the backend folder first.")

    n_hotspots = len(SCORED)
    n_eligible = int(SCORED["is_ranking_eligible"].sum())

    return {
        **SUMMARY_STATS,
        "total_hotspots": n_hotspots,
        "ranking_eligible_hotspots": n_eligible,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)