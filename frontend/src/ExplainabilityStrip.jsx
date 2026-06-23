import { useEffect, useState } from "react";
import { api } from "./api";

const COMPONENT_META = {
  volume: { label: "Volume", color: "#3b82f6" },
  severity: { label: "Severity", color: "#dc2626" },
  time_concentration: { label: "Time Concentration", color: "#f59e0b" },
  recency: { label: "Recency", color: "#22c55e" },
};

export default function ExplainabilityStrip({ hotspotId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!hotspotId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .get(`/api/hotspots/${encodeURIComponent(hotspotId)}/explain`)
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error(err);
        setError("Could not load explanation for this hotspot.");
      })
      .finally(() => setLoading(false));
  }, [hotspotId]);

  if (!hotspotId) {
    return (
      <div className="explain-strip placeholder">
        Select a hotspot to see exactly how its score was calculated.
      </div>
    );
  }
  if (loading) return <div className="explain-strip placeholder">Loading breakdown…</div>;
  if (error) return <div className="explain-strip placeholder">{error}</div>;
  if (!data) return null;

  const { point_contributions, congestion_impact_score, dominant_junction, dominant_station, plain_language, is_consistent } = data;
  const total = congestion_impact_score;

  return (
    <div className="explain-strip">
      <div className="explain-header">
        <h3>Why this score? — {dominant_junction === "No Junction" ? dominant_station : dominant_junction}</h3>
        {!is_consistent && (
          <span className="explain-warning" title="Recomputed total doesn't match stored score">
            ⚠ inconsistent
          </span>
        )}
      </div>

      <div className="explain-bar">
        {Object.entries(point_contributions).map(([key, value]) => {
          const widthPct = (value / total) * 100;
          const meta = COMPONENT_META[key];
          return (
            <div
              key={key}
              className="explain-bar-segment"
              style={{ width: `${widthPct}%`, background: meta.color }}
              title={`${meta.label}: ${value} pts`}
            />
          );
        })}
      </div>

      <div className="explain-legend">
        {Object.entries(point_contributions).map(([key, value]) => {
          const meta = COMPONENT_META[key];
          return (
            <div className="explain-legend-item" key={key}>
              <span className="explain-dot" style={{ background: meta.color }} />
              <span className="explain-legend-label">{meta.label}</span>
              <span className="explain-legend-value">{value} pts</span>
            </div>
          );
        })}
        <div className="explain-legend-item total">
          <span className="explain-legend-label">Total Score</span>
          <span className="explain-legend-value">{total} / 100</span>
        </div>
      </div>

      <p className="explain-plain-language">{plain_language}</p>
    </div>
  );
}