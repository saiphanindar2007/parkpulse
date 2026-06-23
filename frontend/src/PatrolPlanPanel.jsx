const VEHICLE_COLORS = ["#3b82f6", "#22c55e", "#f97316", "#a855f7", "#ec4899"];

export default function PatrolPlanPanel({ routesData }) {
  if (!routesData) return <div className="trend-panel placeholder">Loading patrol plan…</div>;

  const { routes, summary } = routesData;

  return (
    <div className="patrol-panel">
      <h3>Optimized Patrol Plan — Next Shift</h3>
      <p className="enforcement-sub">
        Solved as a vehicle routing problem (OR-Tools CVRP) across the top forecasted hotspots —
        not just a ranked list, an actual drivable plan.
      </p>

      <div className="patrol-summary-row">
        <div className="patrol-stat">
          <div className="patrol-stat-value">{summary.total_distance_km} km</div>
          <div className="patrol-stat-label">Total Distance</div>
        </div>
        <div className="patrol-stat">
          <div className="patrol-stat-value">{summary.n_hotspots_covered}</div>
          <div className="patrol-stat-label">Hotspots Covered</div>
        </div>
        <div className="patrol-stat highlight">
          <div className="patrol-stat-value">{summary.coverage_efficiency}</div>
          <div className="patrol-stat-label">Violations / km</div>
        </div>
      </div>

      <div className="vehicle-list">
        {routes.map((r) => {
          const color = VEHICLE_COLORS[r.vehicle_id % VEHICLE_COLORS.length];
          const stopCount = r.stops.filter((s) => s.label !== "DEPOT").length;
          return (
            <div className="vehicle-row" key={r.vehicle_id}>
              <span className="vehicle-dot" style={{ background: color }} />
              <span className="vehicle-name">Vehicle {r.vehicle_id + 1}</span>
              <span className="vehicle-detail">
                {stopCount} stops · {r.total_distance_km} km · ~{Math.round(r.covered_forecast)} violations/wk
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}