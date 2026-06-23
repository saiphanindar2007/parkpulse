import { useEffect, useState } from "react";
import { api } from "./api";

export default function AnomalyPanel({ onSelectHotspot }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/anomalies", { params: { limit: 25 } })
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error(err);
        setError("Anomalies not generated yet. Run `python detect_anomalies.py` in the backend folder.");
      });
  }, []);

  if (error) return <div className="trend-panel placeholder">{error}</div>;
  if (!data) return <div className="trend-panel placeholder">Loading anomalies…</div>;

  return (
    <div className="anomaly-panel">
      <h3>Anomaly Detector — Live Deviations</h3>
      <p className="enforcement-sub">
        Hotspots whose latest week deviates sharply from their own historical baseline
        (robust z-score, independent of the ranking/forecast models).
      </p>

      <div className="anomaly-summary-row">
        <div className="anomaly-stat spike">
          <div className="anomaly-stat-value">{data.n_spikes}</div>
          <div className="anomaly-stat-label">Spikes Detected</div>
        </div>
        <div className="anomaly-stat drop">
          <div className="anomaly-stat-value">{data.n_drops}</div>
          <div className="anomaly-stat-label">Drops Detected</div>
        </div>
      </div>

      <div className="anomaly-list">
        {data.anomalies.map((a) => (
          <div
            className={`anomaly-row ${a.anomaly_type === "SPIKE" ? "spike" : "drop"}`}
            key={a.hotspot_id}
            onClick={() => onSelectHotspot && onSelectHotspot(a.hotspot_id)}
          >
            <span className={`anomaly-badge ${a.anomaly_type === "SPIKE" ? "spike" : "drop"}`}>
              {a.anomaly_type === "SPIKE" ? "▲ SPIKE" : "▼ DROP"}
            </span>
            <span className="anomaly-name">
              {a.dominant_junction === "No Junction" ? a.dominant_station : a.dominant_junction}
            </span>
            <span className="anomaly-detail">
              {a.latest_count} vs baseline {a.baseline_median} · z={a.robust_zscore}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}