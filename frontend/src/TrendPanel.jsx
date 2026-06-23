import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import ConfidenceTag from "./ConfidenceTag";

export default function TrendPanel({ trendData, loading }) {
  if (loading) {
    return <div className="trend-panel placeholder">Loading trend…</div>;
  }
  if (!trendData) {
    return (
      <div className="trend-panel placeholder">
        Click a hotspot on the map or table to see its weekly trend.
      </div>
    );
  }

  const { meta, weekly_trend } = trendData;

  return (
    <div className="trend-panel">
      <h3>{meta?.display_name ?? (meta?.dominant_junction === "No Junction" ? `${meta?.dominant_station} (unnamed hotspot)` : meta?.dominant_junction)}</h3>
      <div className="trend-meta">
        <span>CIS: <strong>{meta?.congestion_impact_score}</strong></span>
        <span>Total violations: <strong>{meta?.violation_count?.toLocaleString()}</strong></span>
        <span>
          Next-week forecast: <strong>{meta?.forecast_next_week ?? "N/A"}</strong>{" "}
          <ConfidenceTag tag={meta?.confidence_tag} explanation={meta?.confidence_explanation} />
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={weekly_trend}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
          <XAxis dataKey="week_start" tick={{ fontSize: 11 }} minTickGap={20} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="violation_count" stroke="#dc2626" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}