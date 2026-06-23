import axios from "axios";

// In local dev, falls back to localhost:8000. In production (deployed),
// set VITE_API_BASE_URL in your hosting platform's environment variables
// to your deployed backend's URL (e.g. https://parkpulse-api.onrender.com) --
// otherwise the deployed frontend will try to call localhost on the
// VISITOR's machine, which silently fails with no data showing up.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE });

// main.py's endpoints return {count, hotspots} / {count, forecasts} wrappers,
// not raw arrays -- these helpers unwrap them so components just get arrays.
export async function fetchHotspots(limit = 300) {
  const { data } = await api.get("/api/hotspots", { params: { limit } });
  return data.hotspots;
}

export async function fetchForecast(limit = 20) {
  const { data } = await api.get("/api/forecast", { params: { limit } });
  return data.forecasts;
}

export async function fetchSummary() {
  const { data } = await api.get("/api/stats/summary");
  return data;
}

export async function fetchTrend(hotspotId) {
  const { data } = await api.get(`/api/hotspots/${encodeURIComponent(hotspotId)}/trend`);
  return data;
}

export async function fetchPatrolRoutes() {
  const { data } = await api.get("/api/patrol-routes");
  return data;
}

export async function fetchTimelapse() {
  const { data } = await api.get("/api/timelapse");
  return data;
}

export async function fetchRiskAtPoint(lat, lon) {
  const { data } = await api.get("/api/risk-at-point", { params: { lat, lon } });
  return data;
}