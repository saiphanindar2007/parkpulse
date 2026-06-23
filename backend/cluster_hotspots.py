"""
ParkPulse - Day 2, Step 1: Hotspot Clustering
Runs DBSCAN on lat/long (haversine distance) to find emergent hotspots.
Large merged clusters (where multiple dense junctions chain together) are
automatically re-split with a tighter eps so each hotspot stays locally
meaningful instead of one giant blob covering several named junctions.
"""
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN

CLEAN_PATH = "data/violations_clean.parquet"
HOTSPOTS_OUT = "data/hotspots.parquet"          # per-record hotspot assignment
HOTSPOT_SUMMARY_OUT = "data/hotspot_summary.parquet"  # one row per hotspot

KMS_PER_RADIAN = 6371.0088

# Primary pass settings
PRIMARY_EPS_KM = 0.04      # 40 meters
PRIMARY_MIN_SAMPLES = 15

# Any primary cluster bigger than this gets re-split (handles dense
# commercial cores like KR Market / Upparpet where several junctions
# sit close enough to chain into one cluster under pure DBSCAN)
SPLIT_THRESHOLD = 2000
SUB_EPS_KM = 0.015         # 15 meters
SUB_MIN_SAMPLES = 10

# Second pass: if a sub-cluster is STILL oversized (continuous dense
# strips like the KR Market / Elite / Sagar Theatre corridor), split
# again with an even tighter eps. This caps any single hotspot at a
# size that's still meaningful for patrol deployment.
SECOND_SPLIT_THRESHOLD = 5000
SECOND_EPS_KM = 0.006      # 6 meters
SECOND_MIN_SAMPLES = 8


def run_dbscan(coords_deg, eps_km, min_samples):
    coords_rad = np.radians(coords_deg)
    eps_rad = eps_km / KMS_PER_RADIAN
    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    return db.fit(coords_rad).labels_


def main():
    df = pd.read_parquet(CLEAN_PATH)
    print(f"Loaded {len(df)} rows")

    coords = df[["latitude", "longitude"]].values
    primary_labels = run_dbscan(coords, PRIMARY_EPS_KM, PRIMARY_MIN_SAMPLES)
    df["cluster_raw"] = primary_labels

    n_primary = len(set(primary_labels)) - (1 if -1 in primary_labels else 0)
    print(f"Primary DBSCAN: {n_primary} clusters, {(primary_labels == -1).sum()} noise points")

    # Re-split oversized clusters
    sizes = df["cluster_raw"].value_counts()
    big_clusters = sizes[(sizes.index != -1) & (sizes > SPLIT_THRESHOLD)].index.tolist()
    print(f"Re-splitting {len(big_clusters)} oversized clusters (>{SPLIT_THRESHOLD} pts)")

    df["hotspot_id"] = df["cluster_raw"].astype(str)
    next_suffix = {}

    for c in big_clusters:
        mask = df["cluster_raw"] == c
        sub_coords = df.loc[mask, ["latitude", "longitude"]].values
        sub_labels = run_dbscan(sub_coords, SUB_EPS_KM, SUB_MIN_SAMPLES)
        # Build new hotspot IDs: "<cluster>_<sub>" or "<cluster>_noise" for sub-noise
        new_ids = [f"{c}_{lbl}" if lbl != -1 else f"{c}_noise" for lbl in sub_labels]
        df.loc[mask, "hotspot_id"] = new_ids

    # Second pass: re-split any sub-cluster still above SECOND_SPLIT_THRESHOLD
    sub_sizes = df.loc[~df["hotspot_id"].isin(["noise"]) & ~df["hotspot_id"].str.endswith("_noise"), "hotspot_id"].value_counts()
    still_big = sub_sizes[sub_sizes > SECOND_SPLIT_THRESHOLD].index.tolist()
    print(f"Second-pass re-splitting {len(still_big)} still-oversized hotspots (>{SECOND_SPLIT_THRESHOLD} pts)")

    for hid in still_big:
        mask = df["hotspot_id"] == hid
        sub_coords = df.loc[mask, ["latitude", "longitude"]].values
        sub_labels = run_dbscan(sub_coords, SECOND_EPS_KM, SECOND_MIN_SAMPLES)
        new_ids = [f"{hid}_{lbl}" if lbl != -1 else f"{hid}_noise2" for lbl in sub_labels]
        df.loc[mask, "hotspot_id"] = new_ids

    # Mark primary noise points clearly
    df.loc[df["cluster_raw"] == -1, "hotspot_id"] = "noise"

    n_final = df.loc[~df["hotspot_id"].str.contains("noise"), "hotspot_id"].nunique()
    n_noise_final = (df["hotspot_id"].str.contains("noise") | (df["hotspot_id"] == "noise")).sum()
    print(f"Final: {n_final} hotspots, {n_noise_final} noise points ({n_noise_final/len(df)*100:.1f}%)")

    df.to_parquet(HOTSPOTS_OUT, index=False)
    print(f"Saved per-record hotspot assignment to {HOTSPOTS_OUT}")

    # Build hotspot summary: one row per hotspot with centroid, dominant junction, counts
    valid = df[~df["hotspot_id"].str.contains("noise")].copy()

    summary = valid.groupby("hotspot_id").agg(
        violation_count=("id", "count"),
        centroid_lat=("latitude", "mean"),
        centroid_lon=("longitude", "mean"),
    ).reset_index()

    # Dominant junction name and police station per hotspot (mode)
    dominant_junction = valid.groupby("hotspot_id")["junction_name"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else "Unnamed"
    )
    dominant_station = valid.groupby("hotspot_id")["police_station"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"
    )
    summary = summary.merge(dominant_junction.rename("dominant_junction"), on="hotspot_id")
    summary = summary.merge(dominant_station.rename("dominant_station"), on="hotspot_id")

    summary = summary.sort_values("violation_count", ascending=False).reset_index(drop=True)
    summary.to_parquet(HOTSPOT_SUMMARY_OUT, index=False)
    print(f"Saved {len(summary)} hotspot summaries to {HOTSPOT_SUMMARY_OUT}")
    print("\nTop 10 hotspots by volume:")
    print(summary[["hotspot_id", "dominant_junction", "violation_count"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()