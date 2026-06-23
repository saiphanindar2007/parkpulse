import { useEffect, useState } from "react";
import { api } from "./api";

export default function ROIPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/backtest")
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error(err);
        setError("Backtest not generated yet. Run `python backtest_roi.py` in the backend folder.");
      });
  }, []);

  if (error) return <div className="trend-panel placeholder">{error}</div>;
  if (!data) return <div className="trend-panel placeholder">Loading backtest results…</div>;

  const hs = data.coverage_high_severity_only;

  return (
    <div className="roi-panel">
      <h2>Backtested Validation — Does This Actually Work?</h2>
      <p className="roi-intro">
        Hotspot rankings were computed using only the first {data.train_window.n_violations.toLocaleString()} violations
        ({data.train_window.start} to {data.train_window.end}), then tested against the{" "}
        {data.test_window.n_violations.toLocaleString()} violations that happened afterward
        ({data.test_window.start} to {data.test_window.end}) — a genuine held-out backtest, not a number computed
        and reported on the same data.
      </p>

      <div className="roi-headline">
        <div className="roi-headline-value">+{hs.cis_relative_improvement_pct}%</div>
        <div className="roi-headline-label">
          more high-severity violations covered (footpath / road-crossing / main-road / double-parking / one-way)
          vs. a naive volume-only ranking
        </div>
      </div>

      <div className="roi-grid">
        <div className="roi-card">
          <h4>High-Severity Coverage</h4>
          <div className="roi-bar-row">
            <span>ParkPulse CIS</span>
            <div className="roi-bar"><div className="roi-bar-fill cis" style={{ width: `${hs.parkpulse_cis_pct}%` }} /></div>
            <span>{hs.parkpulse_cis_pct}%</span>
          </div>
          <div className="roi-bar-row">
            <span>Naive Volume</span>
            <div className="roi-bar"><div className="roi-bar-fill naive" style={{ width: `${hs.naive_volume_pct}%` }} /></div>
            <span>{hs.naive_volume_pct}%</span>
          </div>
          <div className="roi-bar-row">
            <span>Random</span>
            <div className="roi-bar"><div className="roi-bar-fill random" style={{ width: `${hs.random_baseline_pct}%` }} /></div>
            <span>{hs.random_baseline_pct}%</span>
          </div>
        </div>

        <div className="roi-card">
          <h4>Overall Lift vs Random Patrol</h4>
          <div className="roi-stat-big">{data.lift_by_volume.vs_random}×</div>
          <p className="roi-card-note">
            Patrolling ParkPulse's top {data.top_k} hotspots (out of {data.total_grid_cells} candidate zones)
            catches {data.lift_by_volume.vs_random}× more violations than patrolling {data.top_k} random zones —
            strong evidence the underlying clustering finds real, persistent hotspots rather than noise.
          </p>
        </div>
      </div>

      <div className="roi-honesty-note">
        <strong>Methodological note:</strong> {data.roi_note}
      </div>
    </div>
  );
}