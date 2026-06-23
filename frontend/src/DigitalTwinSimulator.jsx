import { useState } from "react";
import { api } from "./api";

export default function DigitalTwinSimulator() {
  const [nVehicles, setNVehicles] = useState(3);
  const [maxRouteKm, setMaxRouteKm] = useState(25);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [baseline, setBaseline] = useState(null);

  function runSimulation() {
    setLoading(true);
    setError(null);
    api
      .get("/api/simulate-patrol", {
        params: { n_vehicles: nVehicles, max_route_km: maxRouteKm },
        timeout: 15000, // solver typically takes 1-3s; 15s is a generous ceiling
      })
      .then((res) => {
        setResult(res.data);
        // First run becomes the baseline for comparison
        if (!baseline) setBaseline(res.data);
      })
      .catch((err) => {
        console.error(err);
        if (err.code === "ECONNABORTED") {
          setError("Simulation took longer than expected (>15s). The backend may be busy — try again.");
        } else if (err.code === "ERR_NETWORK" || !err.response) {
          setError("Could not reach the backend. Make sure uvicorn is running on http://localhost:8000.");
        } else {
          setError(err.response?.data?.detail || "Simulation failed. Try different parameters.");
        }
      })
      .finally(() => setLoading(false));
  }

  const delta = result && baseline && result !== baseline
    ? {
        coverage: result.summary.coverage_pct - baseline.summary.coverage_pct,
        distance: result.summary.total_distance_km - baseline.summary.total_distance_km,
      }
    : null;

  return (
    <div className="twin-panel">
      <h2>Digital Twin — Patrol Deployment Simulator</h2>
      <p className="roi-intro">
        Adjust resources below and re-run the actual OR-Tools route optimizer live — this re-solves the
        real constraint problem each time (typically 1-3 seconds), it isn't a precomputed lookup or animation.
      </p>

      <div className="twin-controls">
        <div className="twin-control">
          <label>Patrol Vehicles: <strong>{nVehicles}</strong></label>
          <input
            type="range"
            min="1"
            max="8"
            value={nVehicles}
            onChange={(e) => setNVehicles(Number(e.target.value))}
          />
        </div>
        <div className="twin-control">
          <label>Max Distance per Vehicle: <strong>{maxRouteKm} km</strong></label>
          <input
            type="range"
            min="5"
            max="100"
            step="5"
            value={maxRouteKm}
            onChange={(e) => setMaxRouteKm(Number(e.target.value))}
          />
        </div>
        <button className="twin-run-btn" onClick={runSimulation} disabled={loading}>
          {loading ? "Solving…" : "Run Simulation"}
        </button>
      </div>

      {error && <div className="twin-error">{error}</div>}

      {result && (
        <div className="twin-results">
          <div className="twin-stat-grid">
            <div className="twin-stat">
              <div className="twin-stat-value">
                {result.summary.hotspots_visited}/{result.summary.hotspots_total}
              </div>
              <div className="twin-stat-label">Hotspots Covered</div>
            </div>
            <div className="twin-stat">
              <div className="twin-stat-value">{result.summary.coverage_pct}%</div>
              <div className="twin-stat-label">Forecast Coverage</div>
              {delta && (
                <div className={`twin-delta ${delta.coverage >= 0 ? "up" : "down"}`}>
                  {delta.coverage >= 0 ? "▲" : "▼"} {Math.abs(delta.coverage).toFixed(1)}pp vs first run
                </div>
              )}
            </div>
            <div className="twin-stat">
              <div className="twin-stat-value">{result.summary.total_distance_km} km</div>
              <div className="twin-stat-label">Total Distance</div>
              {delta && (
                <div className={`twin-delta ${delta.distance <= 0 ? "up" : "down"}`}>
                  {delta.distance >= 0 ? "▲" : "▼"} {Math.abs(delta.distance).toFixed(1)} km vs first run
                </div>
              )}
            </div>
            <div className="twin-stat highlight">
              <div className="twin-stat-value">{result.summary.efficiency_violations_per_km}</div>
              <div className="twin-stat-label">Violations / km</div>
            </div>
          </div>

          <div className="twin-routes">
            {result.routes.map((r) => (
              <div className="twin-route-row" key={r.vehicle_id}>
                <strong>Vehicle {r.vehicle_id + 1}</strong>
                <span>{r.n_stops} stops · {r.distance_km} km</span>
                <span className="twin-route-stops">{r.stop_names.join(" → ") || "(no stops assigned)"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="twin-placeholder">Set your parameters and click "Run Simulation" to see results.</div>
      )}
    </div>
  );
}