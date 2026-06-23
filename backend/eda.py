"""
ParkPulse - Day 1: Exploratory Data Analysis
Generates the core charts and a findings.txt summary used later in the
pitch deck. Run this AFTER clean_data.py.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")

df = pd.read_parquet("data/violations_clean.parquet")
exploded = pd.read_parquet("data/violations_exploded.parquet")

FIG_DIR = "data/figures"
import os
os.makedirs(FIG_DIR, exist_ok=True)

findings = []

# ---------------------------------------------------------------
# 1. Violation type frequency
# ---------------------------------------------------------------
top_violations = exploded["violation"].value_counts().head(15)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_violations.values, y=top_violations.index, color="#2563eb")
plt.title("Top 15 Violation Types")
plt.xlabel("Count")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/top_violation_types.png", dpi=150)
plt.close()

findings.append(
    f"Top violation: '{top_violations.index[0]}' with {top_violations.iloc[0]:,} occurrences "
    f"({top_violations.iloc[0] / len(exploded) * 100:.1f}% of all violation instances)."
)

# ---------------------------------------------------------------
# 2. Hour-of-day distribution (the night-skew finding)
# ---------------------------------------------------------------
hourly = df["hour"].value_counts().sort_index()
plt.figure(figsize=(10, 5))
sns.barplot(x=hourly.index, y=hourly.values, color="#dc2626")
plt.title("Violations by Hour of Day")
plt.xlabel("Hour (0-23)")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/hourly_distribution.png", dpi=150)
plt.close()

daytime = df[df["hour"].between(10, 17)].shape[0]
night = df[~df["hour"].between(10, 17)].shape[0]
findings.append(
    f"Only {daytime:,} records ({daytime/len(df)*100:.1f}%) occur between 10am-6pm, vs "
    f"{night:,} ({night/len(df)*100:.1f}%) outside that window — enforcement is heavily "
    f"night/early-morning skewed, likely reflecting patrol/camera deployment timing rather "
    f"than actual daytime violation rates. This is a key gap ParkPulse should highlight."
)

# ---------------------------------------------------------------
# 3. Day-of-week distribution
# ---------------------------------------------------------------
dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow = df["day_of_week"].value_counts().reindex(dow_order)
plt.figure(figsize=(8, 5))
sns.barplot(x=dow.index, y=dow.values, color="#059669")
plt.title("Violations by Day of Week")
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/day_of_week.png", dpi=150)
plt.close()

# ---------------------------------------------------------------
# 4. Top police stations and junctions
# ---------------------------------------------------------------
top_stations = df["police_station"].value_counts().head(10)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_stations.values, y=top_stations.index, color="#7c3aed")
plt.title("Top 10 Police Stations by Violation Count")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/top_police_stations.png", dpi=150)
plt.close()

named_junctions = df[df["has_named_junction"]]
top_junctions = named_junctions["junction_name"].value_counts().head(10)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_junctions.values, y=top_junctions.index, color="#ea580c")
plt.title("Top 10 Named Junctions by Violation Count")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/top_junctions.png", dpi=150)
plt.close()

findings.append(
    f"{df['police_station'].nunique()} unique police stations and "
    f"{named_junctions['junction_name'].nunique()} named junctions are represented. "
    f"{(~df['has_named_junction']).sum():,} records ({(~df['has_named_junction']).mean()*100:.1f}%) "
    f"have no specific junction tagged — these will rely purely on lat/long clustering."
)

# ---------------------------------------------------------------
# 5. Vehicle type breakdown
# ---------------------------------------------------------------
top_vehicles = df["vehicle_type"].value_counts().head(10)
plt.figure(figsize=(9, 5))
sns.barplot(x=top_vehicles.values, y=top_vehicles.index, color="#0891b2")
plt.title("Top 10 Vehicle Types Involved")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/vehicle_types.png", dpi=150)
plt.close()

findings.append(
    f"Most common vehicle type: {top_vehicles.index[0]} ({top_vehicles.iloc[0]:,} records, "
    f"{top_vehicles.iloc[0]/len(df)*100:.1f}%)."
)

# ---------------------------------------------------------------
# 6. Daily trend over the full date range
# ---------------------------------------------------------------
daily = df.groupby("date").size()
plt.figure(figsize=(12, 5))
daily.plot(color="#1d4ed8")
plt.title("Daily Violation Volume Over Time")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/daily_trend.png", dpi=150)
plt.close()

findings.append(
    f"Data spans {df['created_datetime'].min().date()} to {df['created_datetime'].max().date()} "
    f"({df['date'].nunique()} distinct days)."
)

# ---------------------------------------------------------------
# 7. Validation status breakdown (data quality signal)
# ---------------------------------------------------------------
val_status = df["validation_status"].value_counts()
findings.append(
    f"Validation status breakdown: {dict(val_status)}. "
    f"{df['validation_status'].isna().sum():,} records have no validation status recorded."
)

# ---------------------------------------------------------------
# Write findings.txt
# ---------------------------------------------------------------
with open("data/findings.txt", "w") as f:
    f.write("ParkPulse — Day 1 EDA Findings\n")
    f.write("=" * 40 + "\n\n")
    for i, line in enumerate(findings, 1):
        f.write(f"{i}. {line}\n\n")

print("EDA complete. Charts saved to data/figures/, findings saved to data/findings.txt")
for line in findings:
    print("-", line)