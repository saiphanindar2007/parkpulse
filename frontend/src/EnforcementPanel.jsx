export default function EnforcementPanel({ forecasts }) {
  if (!forecasts || forecasts.length === 0) return null;

  const top5 = forecasts.slice(0, 5);

  return (
    <div className="enforcement-panel">
      <h3>Recommended Enforcement Zones — Next 7 Days</h3>
      <p className="enforcement-sub">
        Ranked by predicted violation volume for the upcoming week, not just historical totals.
      </p>
      <ol>
        {top5.map((f) => (
          <li key={f.hotspot_id}>
            <span className="zone-name">
              {f.dominant_junction === "No Junction" ? f.dominant_station : f.dominant_junction}
            </span>
            <span className="zone-forecast">~{Math.round(f.forecast_next_week)} violations expected</span>
          </li>
        ))}
      </ol>
    </div>
  );
}