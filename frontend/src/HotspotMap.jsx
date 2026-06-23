import { useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, Popup, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchRiskAtPoint } from "./api";

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

function RiskOracleLayer() {
  const [query, setQuery] = useState(null); // { lat, lon, loading, result, error }

  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      setQuery({ lat, lon: lng, loading: true, result: null, error: null });
      fetchRiskAtPoint(lat, lng)
        .then((result) => setQuery((q) => (q ? { ...q, loading: false, result } : q)))
        .catch((err) => {
          console.error(err);
          setQuery((q) => (q ? { ...q, loading: false, error: "Could not compute risk for this point." } : q));
        });
    },
  });

  if (!query) return null;

  return (
    <Popup position={[query.lat, query.lon]} eventHandlers={{ remove: () => setQuery(null) }}>
      <div className="risk-oracle-popup">
        {query.loading && <div>Computing risk score…</div>}
        {query.error && <div>{query.error}</div>}
        {query.result && (
          <>
            <div className={`risk-oracle-score risk-${query.result.risk_label.toLowerCase()}`}>
              {query.result.risk_score}
              <span className="risk-oracle-label">{query.result.risk_label} RISK</span>
            </div>
            <div className="risk-oracle-detail">
              {query.result.is_exact_match ? (
                <>Exact match: <strong>{query.result.nearest_hotspot.name}</strong></>
              ) : (
                <>
                  Nearest known hotspot: <strong>{query.result.nearest_hotspot.name}</strong>
                  <br />
                  {query.result.nearest_hotspot.distance_km} km away (score: {query.result.nearest_hotspot.actual_score})
                </>
              )}
            </div>
          </>
        )}
      </div>
    </Popup>
  );
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
              <strong>{h.display_name ?? h.dominant_junction}</strong>
              <br />
              CIS: {h.congestion_impact_score} | Violations: {h.violation_count.toLocaleString()}
              <br />
              Next-week forecast: {h.forecast_next_week ?? "N/A"}
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
      <RiskOracleLayer />
    </MapContainer>
  );
}