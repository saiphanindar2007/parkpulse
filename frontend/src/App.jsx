import { useEffect, useState } from "react";
import { fetchHotspots, fetchForecast, fetchSummary, fetchTrend, fetchPatrolRoutes } from "./api";
import SummaryCards from "./SummaryCards";
import HotspotMap from "./HotspotMap";
import HotspotTable from "./HotspotTable";
import TrendPanel from "./TrendPanel";
import EnforcementPanel from "./EnforcementPanel";
import PatrolRoutesMap from "./PatrolRoutesMap";
import PatrolPlanPanel from "./PatrolPlanPanel";
import ExplainabilityStrip from "./ExplainabilityStrip";
import AnomalyPanel from "./AnomalyPanel";
import ROIPanel from "./ROIPanel";
import IntelligenceDigest from "./IntelligenceDigest";
import DigitalTwinSimulator from "./DigitalTwinSimulator";
import TimelapseReplay from "./TimelapseReplay";
import "./App.css";

export default function App() {
  const [summary, setSummary] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [view, setView] = useState("timelapse"); // "timelapse" | "intelligence" | "patrol" | ...
  const [patrolData, setPatrolData] = useState(null);
  const [patrolError, setPatrolError] = useState(null);

  useEffect(() => {
    Promise.all([fetchSummary(), fetchHotspots(300), fetchForecast(20)])
      .then(([summaryRes, hotspotsRes, forecastRes]) => {
        setSummary(summaryRes);
        setHotspots(hotspotsRes);
        setForecasts(forecastRes);
      })
      .catch((err) => {
        console.error(err);
        setLoadError(
          "Could not reach ParkPulse API."
        );
      });
  }, []);

  function handleSelect(hotspotId) {
    setSelectedId(hotspotId);
    setTrendLoading(true);
    fetchTrend(hotspotId)
      .then(setTrendData)
      .catch((err) => console.error(err))
      .finally(() => setTrendLoading(false));
  }

  function switchView(nextView) {
    setView(nextView);
    if (nextView === "patrol" && !patrolData && !patrolError) {
      fetchPatrolRoutes()
        .then(setPatrolData)
        .catch((err) => {
          console.error(err);
          setPatrolError(
            "Patrol routes not generated yet. Run `python optimize_routes.py` in the backend folder, then reload."
          );
        });
    }
  }

  if (loadError) {
    return <div className="error-banner">{loadError}</div>;
  }

  return (
    <div className="app-root">
      <header>
        <h1>ParkPulse</h1>
        <p>AI-Driven Spatiotemporal Intelligence for Illegal Parking Hotspots — Bengaluru</p>
      </header>

      <SummaryCards summary={summary} />

      <IntelligenceDigest />

      <div className="view-tabs">
        <button
          className={view === "timelapse" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("timelapse")}
        >
          ⏱ 24-Hour Replay
        </button>
        <button
          className={view === "intelligence" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("intelligence")}
        >
          Hotspot Intelligence
        </button>
        <button
          className={view === "patrol" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("patrol")}
        >
          Optimized Patrol Plan
        </button>
        <button
          className={view === "anomalies" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("anomalies")}
        >
          Anomaly Detector
        </button>
        <button
          className={view === "roi" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("roi")}
        >
          Backtested ROI
        </button>
        <button
          className={view === "twin" ? "view-tab active" : "view-tab"}
          onClick={() => switchView("twin")}
        >
          Digital Twin
        </button>
      </div>

      {view === "timelapse" && <TimelapseReplay />}

      {view === "intelligence" && (
        <>
          <div className="main-grid">
            <div className="map-col">
              <HotspotMap hotspots={hotspots} onSelect={handleSelect} selectedId={selectedId} />
            </div>
            <div className="side-col">
              <EnforcementPanel forecasts={forecasts} />
              <TrendPanel trendData={trendData} loading={trendLoading} />
              <ExplainabilityStrip hotspotId={selectedId} />
            </div>
          </div>

          <div className="table-section">
            <h2>All Priority Hotspots ({hotspots.length})</h2>
            <HotspotTable hotspots={hotspots} onSelect={handleSelect} selectedId={selectedId} />
          </div>
        </>
      )}

      {view === "patrol" && (
        <div className="main-grid">
          <div className="map-col">
            {patrolError ? (
              <div className="trend-panel placeholder">{patrolError}</div>
            ) : (
              <PatrolRoutesMap routesData={patrolData} />
            )}
          </div>
          <div className="side-col">
            <PatrolPlanPanel routesData={patrolData} />
          </div>
        </div>
      )}

      {view === "anomalies" && (
        <AnomalyPanel
          onSelectHotspot={(id) => {
            handleSelect(id);
            switchView("intelligence");
          }}
        />
      )}

      {view === "roi" && <ROIPanel />}

      {view === "twin" && <DigitalTwinSimulator />}
    </div>
  );
}