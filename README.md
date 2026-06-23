# ParkPulse

**AI-Driven Intelligence for Illegal Parking Hotspot Detection & Congestion-Impact Scoring**

Built for the parking-induced congestion problem statement, using real anonymized Bengaluru Traffic Police violation data.

## What it does

ParkPulse turns 298,450 real Bengaluru traffic-police parking violation records into a deployable enforcement decision-support system:

- **Hotspot detection** — DBSCAN spatial clustering finds 1,348 violation hotspots from raw GPS coordinates, independent of administrative junction labels (49.6% of violations have no junction tagged in the source data).
- **Congestion Impact Score (CIS)** — a composite, weighted score combining violation volume, severity, time-concentration, and recency, ranking 245 high-priority hotspots.
- **Forecasting** — LightGBM panel model predicts next-week violation volume per hotspot, validated by held-out backtest (37-100% relative error depending on volume tier, reported transparently by tier rather than as a single blended number).
- **Patrol route optimization** — Google OR-Tools solves a real Capacitated Vehicle Routing Problem to generate optimal multi-officer patrol routes, covering ~96% of predicted violations across ~67km of driving.
- **Anomaly detection** — robust z-score statistical method flags hotspots whose latest week deviates sharply from their own historical baseline, independent of the forecasting model.
- **Backtested validation** — a genuine temporal holdout test (rank on the first 90 days, evaluate on the held-out remaining 60) shows the ranking covers 16.8% more high-severity violations than a naive volume-only ranking would, while honestly reporting where it trades off raw-count coverage to do so.
- **Digital Twin simulator** — live "what-if" interface that re-solves the actual routing optimizer with user-adjusted vehicle count and distance budget, typically in 1-3 seconds.
- **Explainability** — every score is broken down into its exact point-contribution from each component, verified to sum back to the displayed total.
- **Intelligence Digest** — auto-generated executive summary synthesized live from the same data every other tab serves.

## Architecture

```
backend/
  clean_data.py            # Day 1: ingest + clean raw CSV
  eda.py                    # Day 1: exploratory analysis + charts
  cluster_hotspots.py       # Day 2: DBSCAN hotspot clustering
  score_hotspots.py         # Day 2: Congestion Impact Score
  forecast_hotspots.py      # Day 2: LightGBM next-week forecast
  optimize_routes.py        # Day 4: OR-Tools patrol route optimization
                             #        + reusable run_simulation() for the Digital Twin
  backtest_roi.py           # Day 4: temporal holdout validation
  detect_anomalies.py       # Day 4: robust z-score anomaly detection
  add_confidence_tags.py    # Day 4: forecast confidence calibration
  main.py                   # FastAPI backend serving all endpoints
  data/                     # Pre-computed outputs (parquet/json)

frontend/
  src/
    App.jsx                 # Main dashboard, tab navigation
    HotspotMap.jsx          # Leaflet map with hotspot markers
    PatrolRoutesMap.jsx     # Optimized route visualization
    DigitalTwinSimulator.jsx # Live what-if simulator
    ExplainabilityStrip.jsx # Score breakdown UI
    AnomalyPanel.jsx
    ROIPanel.jsx
    IntelligenceDigest.jsx
    ...
```

## Tech stack

Python (pandas, scikit-learn, LightGBM, Google OR-Tools, FastAPI) · React + Vite + Leaflet + Recharts · file-based Parquet pipeline, no database required.

Chosen deliberately to run on an 8GB RAM / RTX 2050 laptop with no GPU dependency for any part of the pipeline.

## Running locally

See `INSTRUCTIONS_TO_RUN.txt` for full setup steps and troubleshooting. Quick version:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. The dashboard works immediately using the pre-computed data already included in `backend/data/` — no need to re-run the pipeline scripts unless you want to regenerate everything from the raw dataset.

## Live Demo

- Frontend: _add your deployed Vercel URL here_
- Backend API docs: _add your deployed Render URL here_ + `/docs`

## Dataset

Real anonymized Bengaluru Traffic Police parking violation data (298,450 records, Nov 2023–Apr 2024 collection window), provided as the dataset for Problem Statement 1: "Poor Visibility on Parking-Induced Congestion."
