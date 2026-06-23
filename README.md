# ParkPulse

**AI-Driven Spatiotemporal Intelligence for Illegal Parking Hotspot Detection & Congestion-Impact Scoring**

Built for Flipkart GRID Hackathon — Problem Statement 1: *"Poor Visibility on Parking-Induced Congestion"* — by team **Sh4kt1^X**.

Repo: [github.com/saiphanindar2007/parkpulse](https://github.com/saiphanindar2007/parkpulse)

---

## Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [What ParkPulse Does](#what-parkpulse-does)
- [Live Demo](#live-demo)
- [Architecture](#architecture)
- [Data Pipeline (Day-by-Day Build)](#data-pipeline-day-by-day-build)
- [API Reference](#api-reference)
- [Frontend Tabs](#frontend-tabs)
- [Tech Stack](#tech-stack)
- [Running Locally](#running-locally)
- [Deployment](#deployment)
- [Validation & Honesty Notes](#validation--honesty-notes)
- [Dataset](#dataset)
- [Repository Structure](#repository-structure)
- [Known Limitations & Next Steps](#known-limitations--next-steps)
- [Team](#team)

---

## Overview

ParkPulse turns **298,450 real Bengaluru Traffic Police parking violation records** into a working enforcement decision-support system — not a static heatmap, but a full pipeline that detects hotspots, scores their congestion impact, forecasts near-term risk, flags anomalies, optimizes patrol routes, and lets a user simulate "what-if" deployment scenarios live, all backed by a genuine held-out backtest rather than assumed accuracy.

It's designed end-to-end to run on an **8GB RAM laptop with no GPU dependency**, and is also deployed live on free-tier hosting with a memory-optimized data layer.

## The Problem

On-street and spillover illegal parking near commercial areas, metro stations, and event venues chokes Bengaluru's carriageways daily. Enforcement today is patrol-based and reactive — officers respond to complaints rather than anticipating where violations will occur — and there is no existing system connecting violation density to actual congestion impact, making it difficult to prioritize limited enforcement resources.

One finding from the raw data sets the whole project's framing: **99.1% of all recorded violations fall outside the 10am–6pm window.** Enforcement today is almost entirely a night-shift activity, meaning daytime congestion is essentially unmonitored by the current system. ParkPulse is built to close exactly that visibility gap.

## What ParkPulse Does

- **24-Hour Time-Lapse Replay** — an animated, scrubbable replay of Bengaluru's single busiest real day (Nov 18, 2023 — 2,858 violations), sweeping minute-by-minute across the actual map at 1×–4× speed. Built entirely from data already in the pipeline; visually proves the daytime-gap finding rather than just stating it — scrub to 1pm and watch the map empty out while the system flags its own blind spot live.
- **"Click Anywhere" Risk Oracle** — click any point on the map, not just a precomputed hotspot, and get a real, computed congestion-risk score within milliseconds. A Gaussian-weighted spatial interpolation over a `scipy.spatial.cKDTree` index (built once at startup) blends the nearest hotspots' Congestion Impact Scores, calibrated against the real ~430m median spacing between hotspots: clicking within ~80m of a known hotspot returns its exact score, clicking between two hotspots returns a genuinely interpolated value, and clicking far from everything decays toward a low background score. This turns the map from a list of discrete dots into a continuous, explorable risk surface — and it's a moment a reviewer can interact with directly, not just watch.
- **Hotspot detection** — DBSCAN spatial clustering (haversine distance, automatic two-pass re-split for dense corridors) finds **1,348 violation hotspots** from raw GPS coordinates, independent of administrative junction labels — 49.6% of violations have no junction tagged at all in the source data, and DBSCAN finds these hotspots from density alone.
- **Congestion Impact Score (CIS)** — a transparent, composite score combining violation volume, severity weight, time-concentration, and a recency/trend component, ranking **245 high-priority hotspots** (eligibility floor: 150+ violations, to avoid statistical noise from sparse locations).
- **Forecasting** — a LightGBM panel model predicts next-week violation volume per hotspot, with accuracy reported honestly *by volume tier* (≈37% relative error at 200+/week, up to ≈100% at under 10/week) rather than a single misleading blended number.
- **Forecast Confidence Tags** — every forecast carries a HIGH/MEDIUM/LOW confidence label, calibrated directly from the validated tier-accuracy table above — not an arbitrary threshold.
- **Anomaly detection** — a robust MAD-based z-score method flags hotspots whose latest week deviates sharply from their own historical baseline, independent of and complementary to the forecasting model (catches sudden emerging problems too recent/sparse to rank highly otherwise).
- **Patrol route optimization** — Google OR-Tools solves a real Capacitated Vehicle Routing Problem (the same problem class used in logistics dispatch) to generate optimal multi-vehicle patrol routes — **~96% of predicted next-week violations covered across ~67km of total driving** with 3 vehicles, while explicitly surfacing any hotspot that doesn't fit within a vehicle's distance budget.
- **Digital Twin simulator** — a live "what-if" interface that re-solves the actual routing optimizer with a user-adjusted vehicle count and distance budget, typically in 1–3 seconds — genuine re-optimization, not a precomputed lookup table.
- **Backtested validation** — a genuine temporal holdout test (rank hotspots using only the first 90 days of data, evaluate against the held-out remaining 60 days the model never saw) shows the ranking covers **+16.8% more high-severity violations** than a naive volume-only ranking, and beats random patrol selection by **~19x** — reported alongside the honest finding that it trades a small amount of raw-count coverage to achieve this, exactly as designed.
- **Explainability Strip** — every Congestion Impact Score is broken down into its exact point-contribution from each component (volume / severity / time-concentration / recency), self-verified to sum back to the displayed total.
- **Intelligence Digest** — an auto-generated executive summary synthesized live from the same data every other tab serves — a 30-second briefing instead of five tab-clicks.

## Live Demo

- **Frontend (Vercel):** _add your deployed Vercel URL here_
- **Backend API + docs (Render):** _add your deployed Render URL here_ — Swagger UI at `/docs`
- **Recorded walkthrough video:** _add your demo video link here_

## Architecture

A four-layer architecture, fully decoupled so each layer can scale or move independently:

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────┐    ┌──────────────────────┐
│   Data Layer     │ →  │  Intelligence Layer   │ →  │  API Layer  │ →  │  Presentation Layer   │
├─────────────────┤    ├──────────────────────┤    ├─────────────┤    ├──────────────────────┤
│ Raw CSV (298K)   │    │ DBSCAN Clustering     │    │ FastAPI     │    │ React + Vite          │
│ Parquet (clean / │    │ CIS Scoring Engine    │    │ REST/JSON   │    │ Leaflet (maps)        │
│  exploded)        │    │ LightGBM Forecaster   │    │ over HTTPS  │    │ Recharts (charts)     │
│ Precomputed        │    │ Anomaly Detector       │    │             │    │                       │
│  summaries (free-  │    │ OR-Tools VRP Solver    │    │             │    │                       │
│  tier hosting)      │    │ Confidence Calibration │    │             │    │                       │
└─────────────────┘    └──────────────────────┘    └─────────────┘    └──────────────────────┘
```

Runs fully local on an 8GB RTX 2050 laptop for development, and is deployed live with **Render** (backend) + **Vercel** (frontend). The backend's data-loading layer was deliberately refactored to a precomputed, memory-light footprint (summary JSON + weekly-aggregated Parquet instead of the full 298K-row dataframe in memory) to fit comfortably within free-tier hosting RAM limits.

## Data Pipeline (Day-by-Day Build)

The project was built incrementally over a 4-day hackathon timeline, with every stage verified against the real dataset before moving to the next:

| Day | Stage | Scripts | Output |
|---|---|---|---|
| 1 | Ingest & clean, EDA | `clean_data.py`, `eda.py` | `violations_clean.parquet`, charts, findings |
| 2 | Cluster, score, forecast | `cluster_hotspots.py`, `score_hotspots.py`, `forecast_hotspots.py` | `hotspots.parquet`, `hotspot_scored.parquet`, `hotspot_forecast.parquet` |
| 3 | Backend API + frontend dashboard | `main.py`, React app | Full working dashboard against real data |
| 4 | Standout upgrades | `optimize_routes.py`, `backtest_roi.py`, `detect_anomalies.py`, `add_confidence_tags.py`, `precompute_timelapse.py`, `precompute_summary.py` | Routing, backtest, anomalies, confidence tags, time-lapse replay, deployment-ready memory footprint |

Each stage's output was sanity-checked against the previous day's known findings (e.g., DBSCAN clusters validated against Day 1's known top junctions) before being built upon — see commit history for the iterative debugging trail, including a real design flaw caught and fixed in the original CIS formula (it initially let small, sparse hotspots outrank the city's three biggest chronic problem junctions — fixed by redefining the recency component as a trend ratio and adding confidence-shrinkage for low-volume hotspots).

## API Reference

All endpoints are served from `backend/main.py`. Full interactive docs at `/docs` (Swagger UI) once running.

| Endpoint | Description |
|---|---|
| `GET /api/hotspots` | Ranked list of all hotspots with CIS, confidence tag, coordinates |
| `GET /api/hotspots/{id}/trend` | Weekly violation trend for one hotspot |
| `GET /api/hotspots/{id}/explain` | Exact point-contribution breakdown of that hotspot's CIS |
| `GET /api/forecast` | Next-week forecast for all eligible hotspots |
| `GET /api/anomalies` | Statistically flagged spikes/drops vs. each hotspot's baseline |
| `GET /api/patrol-routes` | Precomputed optimal multi-vehicle patrol plan |
| `GET /api/simulate-patrol` | Live re-solved routing — query params: `n_vehicles`, `max_route_km` |
| `GET /api/backtest` | Temporal holdout validation results |
| `GET /api/digest` | Auto-generated executive summary |
| `GET /api/timelapse` | Minute-resolved violation points for the 24-hour replay |
| `GET /api/risk-at-point?lat=&lon=` | Live spatial interpolation — real-time congestion-risk score for any arbitrary coordinate, not just a precomputed hotspot |
| `GET /api/stats/summary` | Headline dashboard stats |

## Frontend Tabs

| Tab | What it shows |
|---|---|
| ⏱ **24-Hour Replay** | Animated map replay of the busiest real day, with live clock, counter, hourly bar chart, and scrub control |
| **Hotspot Intelligence** | Map + ranked table + trend chart + Explainability Strip + Intelligence Digest. Click any empty point on the map to trigger the live Click-Anywhere Risk Oracle. |
| **Optimized Patrol Plan** | Multi-vehicle routes overlaid on the map, with per-vehicle distance/coverage breakdown |
| **Anomaly Detector** | List of statistically flagged hotspots, click-through into their trend/explanation |
| **Backtested ROI** | Headline validation numbers, methodology, and the honest tradeoff discussion |
| **Digital Twin** | Sliders for vehicle count / distance budget, live re-optimization on demand |

## Tech Stack

**Data & Modeling:** Python 3, pandas, NumPy, scikit-learn (DBSCAN), LightGBM, Google OR-Tools (VRP), scipy (spatial KD-tree for the Risk Oracle)
**Backend & Storage:** FastAPI, Uvicorn, Parquet / SQLite, REST JSON API, deployed on Render
**Frontend & Visualization:** React + Vite, Leaflet.js, Recharts, deployed via GitHub + Vercel CI/CD

Chosen deliberately to run comfortably on an 8GB RAM / RTX 2050 laptop with **zero GPU dependency** for any part of the pipeline — clustering and gradient-boosted forecasting at this data scale don't need one, and OR-Tools' solver is compiled C++ under a thin Python layer.

## Running Locally

See `INSTRUCTIONS_TO_RUN.txt` for full setup steps and troubleshooting. Quick version:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. The dashboard works immediately using the pre-computed data already included in `backend/data/` — no need to re-run the pipeline scripts unless you want to regenerate everything from the raw dataset.

If you do want to regenerate everything from scratch, run the pipeline scripts in this order from inside `backend/`:

```bash
python clean_data.py
python cluster_hotspots.py
python score_hotspots.py
python forecast_hotspots.py
python optimize_routes.py
python backtest_roi.py
python detect_anomalies.py
python add_confidence_tags.py
python precompute_timelapse.py
python precompute_summary.py   # required for the memory-optimized deployment build
```

## Deployment

The backend is deployed on **Render** and the frontend on **Vercel**, connected via GitHub for continuous deployment on push.

- The backend's data-loading layer is intentionally lightweight for free-tier hosting: `precompute_summary.py` converts the full 298,450-row dataset into a small `summary_stats.json` and a weekly-aggregated `hotspot_weekly.parquet` (a ~95% size reduction), so `main.py` never loads the full raw dataframe into memory at runtime.
- The 24-Hour Replay similarly reads from a tiny ~150KB precomputed file (`precompute_timelapse.py`) rather than querying the full dataset live.
- CORS is configured in `main.py` to allow the deployed frontend origin; update the allowed-origins list there if you redeploy to a different domain.
- Frontend API base URL is configurable via the `VITE_API_BASE_URL` environment variable, so the same build can point at `localhost:8000` in development and the deployed Render URL in production.

## Validation & Honesty Notes

A deliberate design principle throughout this project: report what the data actually shows, including where a method doesn't win on every metric.

- The Congestion Impact Score is **not** simply "biggest hotspot wins" — it's a deliberate tradeoff that sacrifices a small amount of raw violation-count coverage (~3 percentage points) in exchange for prioritizing high-severity violations specifically (the ones that actually obstruct traffic flow: footpath, road-crossing, main-road, double-parking). The backtest reports both sides of this tradeoff rather than only the favorable number.
- Forecast accuracy is reported **by volume tier**, not as one blended figure, because a single number would obscure that the model is far more reliable for high-volume hotspots — exactly where enforcement decisions matter most — than for sparse, low-history ones.
- Confidence tags (HIGH/MEDIUM/LOW) are derived directly from this same validated tier-accuracy table, not invented thresholds.

## Dataset

Real anonymized Bengaluru Traffic Police parking violation data — **298,450 records**, spanning a **Nov 2023–Apr 2024** collection window, across **169 named junctions** and **54 police stations**, each with exact GPS coordinates and second-level timestamps. Provided as the dataset for Problem Statement 1: *"Poor Visibility on Parking-Induced Congestion."* Over 95% of records are parking-violation subtypes (WRONG PARKING, NO PARKING, PARKING IN A MAIN ROAD, etc.).

## Repository Structure

```
backend/
  clean_data.py              # Day 1: ingest + clean raw CSV
  eda.py                     # Day 1: exploratory analysis + charts
  cluster_hotspots.py        # Day 2: DBSCAN hotspot clustering
  score_hotspots.py          # Day 2: Congestion Impact Score
  forecast_hotspots.py       # Day 2: LightGBM next-week forecast
  optimize_routes.py         # Day 4: OR-Tools patrol route optimization
                              #        + reusable run_simulation() for the Digital Twin
  backtest_roi.py            # Day 4: temporal holdout validation
  detect_anomalies.py        # Day 4: robust z-score anomaly detection
  add_confidence_tags.py     # Day 4: forecast confidence calibration
  precompute_timelapse.py    # Day 4: lightweight payload for the 24-hour replay
  precompute_summary.py      # Day 4: memory-optimized summary for deployment
  main.py                    # FastAPI backend serving all endpoints
  requirements.txt
  data/                      # Pre-computed outputs (parquet/json)

frontend/
  src/
    App.jsx                  # Main dashboard, tab navigation
    TimelapseReplay.jsx      # 24-hour animated replay (default landing tab)
    HotspotMap.jsx           # Leaflet map with hotspot markers + Click-Anywhere Risk Oracle layer
    HotspotTable.jsx         # Ranked priority hotspot table
    TrendPanel.jsx           # Per-hotspot weekly trend chart
    SummaryCards.jsx         # Headline dashboard stat cards
    EnforcementPanel.jsx     # Recommended enforcement zones
    PatrolRoutesMap.jsx      # Optimized route visualization
    PatrolPlanPanel.jsx      # Per-vehicle route breakdown
    DigitalTwinSimulator.jsx # Live what-if simulator
    ExplainabilityStrip.jsx  # Score breakdown UI
    AnomalyPanel.jsx         # Flagged spikes/drops list
    ROIPanel.jsx             # Backtest validation results
    IntelligenceDigest.jsx   # Auto-generated executive summary
    ConfidenceTag.jsx        # HIGH/MEDIUM/LOW badge component
    api.js                   # API client
    App.css
  package.json

INSTRUCTIONS_TO_RUN.txt
README.md
```

## Known Limitations & Next Steps

Named explicitly rather than hidden, since judges and contributors alike will probe these:

- **Routing uses straight-line (haversine) distance**, not real road-network distance — a routing API or OSM road-graph integration is the natural next step for production accuracy.
- **No real-time camera feed integration** — the system is built entirely on historical violation records; live camera-triggered detection is a logical extension once an enforcement-camera data feed is available.
- **Sparse hotspots have wider forecast error bands** — by design, the system is most confident exactly where enforcement decisions matter most (high-volume hotspots), and is transparent about lower confidence elsewhere rather than hiding it behind a single blended accuracy number.
- **Production roadmap:** PostGIS for proper geospatial indexing at scale, real-time camera feed ingestion, and a mobile companion app for patrol officers to consume route plans directly in the field.

## Team

**Sh4kt1^X**
Venkata Sai Phanindar Damaraju

Built for the Flipkart GRID Hackathon, Problem Statement 1.