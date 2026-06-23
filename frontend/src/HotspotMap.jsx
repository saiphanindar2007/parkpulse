import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const BENGALURU_CENTER = [12.9716, 77.5946];

function scoreColor(score) {
  if (score >= 55) return "#dc2626";
  if (score >= 45) return "#f97316";
  if (score >= 35) return "#eab308";
  return "#22c55e";
}

function radiusForVolume(count) {
  const r = Math.log10(count + 1) * 4;
  return Math.max(5, Math.min(r, 22));
}

export default function HotspotMap({ hotspots, onSelect, selectedId }) {
  return (
    <MapContainer
      center={BENGALURU_CENTER}
      zoom={12}
      style={{ height: "100%", width: "100%", borderRadius: "12px" }}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {hotspots.map((h) => (
        <CircleMarker
          key={h.hotspot_id}
          center={[h.centroid_lat, h.centroid_lon]}
          radius={radiusForVolume(h.violation_count)}
          pathOptions={{
            color: h.hotspot_id === selectedId ? "#1d4ed8" : scoreColor(h.congestion_impact_score),
            fillColor: scoreColor(h.congestion_impact_score),
            fillOpacity: 0.6,
            weight: h.hotspot_id === selectedId ? 3 : 1,
          }}
          eventHandlers={{ click: () => onSelect(h.hotspot_id) }}
        >
          <Tooltip>
            <div>
              <strong>{h.dominant_junction}</strong>
              <br />
              CIS: {h.congestion_impact_score} | Violations: {h.violation_count.toLocaleString()}
              <br />
              Next-week forecast: {h.forecast_next_week ?? "N/A"}
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}