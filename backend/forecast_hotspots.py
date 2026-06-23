"""
ParkPulse - Day 2, Step 3: Hotspot-Week Forecasting

Predicts next-week violation volume per hotspot so patrol deployment can
be planned ahead of time instead of reactively.

Approach: a single LightGBM model trained across ALL hotspots' weekly
time series (a "panel" model), rather than one model per hotspot. This
is the right choice here because the median hotspot only has ~8 weeks
of history -- nowhere near enough to fit a standalone per-hotspot model
(e.g. Prophet) reliably. A panel model lets data-rich hotspots (Elite
Junction, 23 weeks) help the model learn general weekly patterns that
transfer to data-sparse hotspots.

The last week in the raw data (2024-04-08 to 2024-04-14) is a PARTIAL
week (only 1 day of data, since the dataset cuts off on 2024-04-08) and
is excluded from training/evaluation to avoid teaching the model a fake
"volume always drops" pattern.
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error

HOTSPOTS_PATH = "data/hotspots.parquet"
SCORED_PATH = "data/hotspot_scored.parquet"
FORECAST_OUT = "data/hotspot_forecast.parquet"
MODEL_OUT = "data/forecast_model.txt"

N_LAGS = 3            # how many previous weeks to use as features
MIN_WEEKS_REQUIRED = 5  # hotspots with fewer weeks than this are forecast with a simple fallback


def build_weekly_panel(hotspots):
    weekly = (
        hotspots.groupby(["hotspot_id", "week"])
        .size()
        .reset_index(name="violation_count")
    )
    # week column looks like "2023-11-06/2023-11-12" -- convert to a sortable start date
    weekly["week_start"] = pd.to_datetime(weekly["week"].str.split("/").str[0])
    weekly = weekly.sort_values(["hotspot_id", "week_start"]).reset_index(drop=True)
    return weekly


def drop_partial_last_week(weekly):
    max_week_start = weekly["week_start"].max()
    weekly = weekly[weekly["week_start"] < max_week_start].copy()
    return weekly, max_week_start


def add_lag_features(weekly):
    weekly = weekly.copy()
    for lag in range(1, N_LAGS + 1):
        weekly[f"lag_{lag}"] = weekly.groupby("hotspot_id")["violation_count"].shift(lag)
    weekly["rolling_mean_3"] = (
        weekly.groupby("hotspot_id")["violation_count"]
        .shift(1)
        .rolling(3)
        .mean()
        .reset_index(level=0, drop=True)
    )
    weekly["week_index"] = weekly.groupby("hotspot_id").cumcount()
    return weekly


def main():
    hotspots = pd.read_parquet(HOTSPOTS_PATH)
    hotspots = hotspots[~hotspots["hotspot_id"].str.contains("noise")].copy()

    weekly = build_weekly_panel(hotspots)
    weekly, partial_week_start = drop_partial_last_week(weekly)
    print(f"Excluded partial week starting {partial_week_start.date()} from training")

    weekly = add_lag_features(weekly)

    feature_cols = [f"lag_{i}" for i in range(1, N_LAGS + 1)] + ["rolling_mean_3", "week_index"]
    model_data = weekly.dropna(subset=feature_cols).copy()
    print(f"Training rows after lag dropna: {len(model_data)} (hotspots with >= {N_LAGS+1} weeks history)")

    # Time-based split: last 3 available weeks per hotspot held out as a rough validation set
    cutoff_index = model_data.groupby("hotspot_id")["week_index"].transform("max") - 2
    train = model_data[model_data["week_index"] < cutoff_index]
    val = model_data[model_data["week_index"] >= cutoff_index]
    print(f"Train rows: {len(train)}, validation rows: {len(val)}")

    train_set = lgb.Dataset(train[feature_cols], label=train["violation_count"])
    val_set = lgb.Dataset(val[feature_cols], label=val["violation_count"], reference=train_set)

    params = {
        "objective": "regression",
        "metric": "mae",
        "verbosity": -1,
        "num_leaves": 15,
        "learning_rate": 0.05,
        "min_data_in_leaf": 10,
    }

    model = lgb.train(
        params,
        train_set,
        num_boost_round=200,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(20, verbose=False)],
    )

    val_pred = model.predict(val[feature_cols])
    mae = mean_absolute_error(val["violation_count"], val_pred)
    print(f"Validation MAE (blended across all hotspots): {mae:.2f} violations/week")
    print(f"(for context, median weekly volume per hotspot is {model_data['violation_count'].median():.0f})")

    # A single blended MAE is misleading here: hotspots range from ~3 to
    # 480+ violations/week on average, so report error relative to each
    # hotspot's own scale instead -- this is the honest way to present
    # forecast accuracy across such a wide volume range.
    val_eval = val.copy()
    val_eval["pred"] = val_pred
    val_eval["abs_err"] = (val_eval["pred"] - val_eval["violation_count"]).abs()
    hotspot_avg_vol = model_data.groupby("hotspot_id")["violation_count"].mean()
    val_eval["avg_vol_tier"] = val_eval["hotspot_id"].map(hotspot_avg_vol)
    val_eval["tier"] = pd.cut(
        val_eval["avg_vol_tier"], bins=[0, 10, 50, 200, 1e6],
        labels=["<10/wk", "10-50/wk", "50-200/wk", "200+/wk"]
    )
    tier_report = val_eval.groupby("tier").agg(
        mae=("abs_err", "mean"), n_obs=("abs_err", "count"), avg_actual=("violation_count", "mean")
    )
    tier_report["mae_pct_of_avg"] = (tier_report["mae"] / tier_report["avg_actual"] * 100).round(1)
    print("\nForecast accuracy by hotspot volume tier (more honest than one blended number):")
    print(tier_report)

    model.save_model(MODEL_OUT)

    # --- Build next-week forecast for every hotspot using its most recent weeks ---
    latest = weekly.sort_values("week_start").groupby("hotspot_id").tail(N_LAGS + 1)
    forecast_rows = []
    for hid, grp in latest.groupby("hotspot_id"):
        grp = grp.sort_values("week_start")
        counts = grp["violation_count"].tolist()
        n_weeks_history = grp["week_index"].max() + 1 if len(grp) else 0

        if len(counts) >= N_LAGS and n_weeks_history >= MIN_WEEKS_REQUIRED:
            # Use the model
            lag_feats = {f"lag_{i}": counts[-i] for i in range(1, N_LAGS + 1)}
            lag_feats["rolling_mean_3"] = np.mean(counts[-3:])
            lag_feats["week_index"] = grp["week_index"].max() + 1
            x = pd.DataFrame([lag_feats])[feature_cols]
            pred = max(0, model.predict(x)[0])
            method = "lightgbm"
        else:
            # Fallback for sparse-history hotspots: simple average of available weeks
            pred = np.mean(counts) if counts else 0
            method = "average_fallback"

        forecast_rows.append({
            "hotspot_id": hid,
            "forecast_next_week": round(pred, 1),
            "forecast_method": method,
            "weeks_of_history": n_weeks_history,
        })

    forecast_df = pd.DataFrame(forecast_rows)

    scored = pd.read_parquet(SCORED_PATH)
    merged = scored.merge(forecast_df, on="hotspot_id", how="left")
    merged.to_parquet(FORECAST_OUT, index=False)
    print(f"\nSaved forecasts for {len(forecast_df)} hotspots to {FORECAST_OUT}")
    print(f"  - via LightGBM: {(forecast_df['forecast_method']=='lightgbm').sum()}")
    print(f"  - via average fallback (sparse history): {(forecast_df['forecast_method']=='average_fallback').sum()}")

    print("\nTop 10 ranking-eligible hotspots with next-week forecast:")
    top = merged[merged["is_ranking_eligible"]].sort_values("rank_eligible").head(10)
    print(top[[
        "rank_eligible", "hotspot_id", "dominant_junction",
        "violation_count", "forecast_next_week", "forecast_method"
    ]].to_string(index=False))


if __name__ == "__main__":
    main()