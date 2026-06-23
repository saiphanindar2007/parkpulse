import ConfidenceTag from "./ConfidenceTag";

export default function HotspotTable({ hotspots, onSelect, selectedId }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Location</th>
            <th>CIS</th>
            <th>Violations</th>
            <th>Next Wk</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {hotspots.map((h) => (
            <tr
              key={h.hotspot_id}
              onClick={() => onSelect(h.hotspot_id)}
              className={h.hotspot_id === selectedId ? "selected-row" : ""}
            >
              <td>{h.rank_eligible}</td>
              <td title={h.display_name || h.dominant_junction}>
                {h.display_name ?? (h.dominant_junction === "No Junction"
                  ? `${h.dominant_station} (unnamed)`
                  : h.dominant_junction)}
              </td>
              <td>
                <span className="score-pill">{h.congestion_impact_score}</span>
              </td>
              <td>{h.violation_count.toLocaleString()}</td>
              <td>{h.forecast_next_week ?? "—"}</td>
              <td>
                <ConfidenceTag tag={h.confidence_tag} explanation={h.confidence_explanation} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}