import { Fragment } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Marker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const BENGALURU_CENTER = [12.9716, 77.5946];

const VEHICLE_COLORS = ["#3b82f6", "#22c55e", "#f97316", "#a855f7", "#ec4899"];

const depotIcon = L.divIcon({
  className: "depot-icon",
  html: `<div style="background:#f5a623;width:14px;height:14px;border-radius:3px;border:2px solid #0b0e11;box-shadow:0 0 6px rgba(245,166,35,0.8);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

export default function PatrolRoutesMap({ routesData }) {
  if (!routesData) return null;
  const { routes } = routesData;

  return (
    <MapContainer
      center={BENGALURU_CENTER}
      zoom={12}
      style={{ height: "100%", width: "100%", borderRadius: "12px" }}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {routes.map((route) => {
        const color = VEHICLE_COLORS[route.vehicle_id % VEHICLE_COLORS.length];
        const positions = route.stops.map((s) => [s.lat, s.lon]);

        return (
          <Fragment key={route.vehicle_id}>
            <Polyline
              positions={positions}
              pathOptions={{ color, weight: 3, opacity: 0.85, dashArray: "1, 8" }}
            />
            {route.stops.map((stop, i) => {
              if (stop.label === "DEPOT") {
                return i === 0 ? (
                  <Marker key="depot" position={[stop.lat, stop.lon]} icon={depotIcon}>
                    <Tooltip>Dispatch HQ</Tooltip>
                  </Marker>
                ) : null;
              }
              return (
                <CircleMarker
                  key={`${route.vehicle_id}-${stop.hotspot_id}`}
                  center={[stop.lat, stop.lon]}
                  radius={8}
                  pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 2 }}
                >
                  <Tooltip>
                    <div>
                      <strong>
                        Vehicle {route.vehicle_id + 1} · Stop {stop.stop_order}
                      </strong>
                      <br />
                      {stop.label}
                      <br />
                      Forecast: {stop.forecast_next_week} violations/wk
                      <br />
                      {stop.cumulative_distance_km} km into route
                    </div>
                  </Tooltip>
                </CircleMarker>
              );
            })}
          </Fragment>
        );
      })}
    </MapContainer>
  );
}