export default function SummaryCards({ summary }) {
  if (!summary) return null;

  const cards = [
    { label: "Total Violations", value: summary.total_violations.toLocaleString() },
    { label: "Hotspots Identified", value: summary.total_hotspots.toLocaleString() },
    { label: "Priority Hotspots", value: summary.ranking_eligible_hotspots.toLocaleString() },
    { label: "Peak Hour", value: `${summary.peak_hour}:00` },
    { label: "Top Vehicle Type", value: summary.top_vehicle_type },
    { label: "Daytime Coverage Gap", value: `${summary.daytime_violations_pct}%`, highlight: true },
  ];

  return (
    <div className="summary-grid">
      {cards.map((c) => (
        <div key={c.label} className={`summary-card ${c.highlight ? "highlight" : ""}`}>
          <div className="summary-value">{c.value}</div>
          <div className="summary-label">{c.label}</div>
        </div>
      ))}
    </div>
  );
}