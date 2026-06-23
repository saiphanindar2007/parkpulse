import { useEffect, useRef, useState, useCallback } from "react";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchTimelapse } from "./api";

const BENGALURU_CENTER = [12.9716, 77.5946];
const SIM_MINUTES_PER_SECOND = 12; // 1 real second = 12 simulated minutes -> full 24h replay in ~2 minutes
const TRAIL_WINDOW_MINUTES = 25;    // how long a point stays bright before fading out
const FADE_TAIL_MINUTES = 60;       // how long a point lingers as a faint dot after that

function severityColor(sev) {
  if (sev >= 8) return "#dc2626";
  if (sev >= 5) return "#f97316";
  return "#eab308";
}

function formatClock(minuteOfDay) {
  const h = Math.floor(minuteOfDay / 60) % 24;
  const m = Math.floor(minuteOfDay % 60);
  const period = h < 12 ? "AM" : "PM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${String(h12).padStart(2, "0")}:${String(m).padStart(2, "0")} ${period}`;
}

export default function TimelapseReplay() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [currentMinute, setCurrentMinute] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [visiblePoints, setVisiblePoints] = useState([]);
  const [countSoFar, setCountSoFar] = useState(0);

  const rafRef = useRef(null);
  const lastTsRef = useRef(null);
  const pointsRef = useRef([]);

  useEffect(() => {
    fetchTimelapse()
      .then((res) => {
        setData(res);
        pointsRef.current = res.points;
      })
      .catch((err) => {
        console.error(err);
        setError("Timelapse data not available. Run `python precompute_timelapse.py` in the backend folder.");
      });
  }, []);

  const updateVisiblePoints = useCallback((minute) => {
    const pts = pointsRef.current;
    const visible = [];
    let count = 0;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      if (p.minute_of_day > minute) break; // points are time-sorted, can stop early
      count++;
      const age = minute - p.minute_of_day;
      if (age <= TRAIL_WINDOW_MINUTES) {
        visible.push({ ...p, opacity: 1, fresh: true });
      } else if (age <= TRAIL_WINDOW_MINUTES + FADE_TAIL_MINUTES) {
        const fadeProgress = (age - TRAIL_WINDOW_MINUTES) / FADE_TAIL_MINUTES;
        visible.push({ ...p, opacity: Math.max(0.08, 1 - fadeProgress), fresh: false });
      }
    }
    setVisiblePoints(visible);
    setCountSoFar(count);
  }, []);

  const tick = useCallback(
    (ts) => {
      if (lastTsRef.current === null) lastTsRef.current = ts;
      const deltaSeconds = (ts - lastTsRef.current) / 1000;
      lastTsRef.current = ts;

      setCurrentMinute((prev) => {
        const next = prev + deltaSeconds * SIM_MINUTES_PER_SECOND * speed;
        if (next >= 1440) {
          setPlaying(false);
          return 1440;
        }
        updateVisiblePoints(next);
        return next;
      });

      if (playing) rafRef.current = requestAnimationFrame(tick);
    },
    [playing, speed, updateVisiblePoints]
  );

  useEffect(() => {
    if (playing) {
      lastTsRef.current = null;
      rafRef.current = requestAnimationFrame(tick);
    } else if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  function handleScrub(e) {
    const minute = Number(e.target.value);
    setCurrentMinute(minute);
    updateVisiblePoints(minute);
  }

  function togglePlay() {
    if (currentMinute >= 1440) {
      setCurrentMinute(0);
      updateVisiblePoints(0);
    }
    setPlaying((p) => !p);
  }

  if (error) return <div className="trend-panel placeholder">{error}</div>;
  if (!data) return <div className="trend-panel placeholder">Loading 24-hour replay…</div>;

  const currentHour = Math.floor(currentMinute / 60) % 24;
  const isDaytimeGap = currentHour >= 10 && currentHour < 18;

  return (
    <div className="timelapse-panel">
      <div className="timelapse-header">
        <h2>24-Hour Replay — {data.date}</h2>
        <p className="roi-intro">
          Every one of {data.total_violations.toLocaleString()} violations recorded on Bengaluru's busiest day,
          replayed in real time-compressed motion. Watch what happens between 10am and 6pm.
        </p>
      </div>

      <div className="timelapse-stage">
        <div className="timelapse-map">
          <MapContainer center={BENGALURU_CENTER} zoom={11.5} zoomControl={false} attributionControl={false} style={{ height: "100%", width: "100%" }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {visiblePoints.map((p, i) => (
              <CircleMarker
                key={`${p.minute_of_day}-${i}`}
                center={[p.lat, p.lon]}
                radius={p.fresh ? 5 : 2.5}
                pathOptions={{
                  color: "none",
                  fillColor: severityColor(p.severity),
                  fillOpacity: p.opacity,
                }}
              />
            ))}
          </MapContainer>

          <div className={`timelapse-clock ${isDaytimeGap ? "gap-warning" : ""}`}>
            <div className="timelapse-clock-time">{formatClock(currentMinute)}</div>
            {isDaytimeGap && <div className="timelapse-clock-label">⚠ Daytime enforcement gap</div>}
          </div>

          <div className="timelapse-counter">
            <div className="timelapse-counter-value">{countSoFar.toLocaleString()}</div>
            <div className="timelapse-counter-label">violations so far</div>
          </div>
        </div>

        <div className="timelapse-hourly-strip">
          <div className="timelapse-hour-bars-row">
            {data.hourly_counts.map((count, h) => {
              const maxCount = Math.max(...data.hourly_counts);
              const heightPct = maxCount > 0 ? (count / maxCount) * 100 : 0;
              const isActive = h === currentHour;
              const isPast = h < currentHour;
              return (
                <div className="timelapse-hour-bar-wrap" key={h}>
                  <div
                    className={`timelapse-hour-bar ${isActive ? "active" : ""} ${isPast ? "past" : ""}`}
                    style={{ height: `${heightPct}%` }}
                    title={`${h}:00 — ${count} violations`}
                  />
                </div>
              );
            })}
          </div>
          <div className="timelapse-hour-labels-row">
            {data.hourly_counts.map((_, h) => (
              <div className="timelapse-hour-label-slot" key={h}>
                {h}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="timelapse-controls">
        <button className="timelapse-play-btn" onClick={togglePlay}>
          {playing ? "⏸ Pause" : currentMinute >= 1440 ? "↻ Replay" : "▶ Play"}
        </button>

        <input
          type="range"
          min="0"
          max="1440"
          step="1"
          value={currentMinute}
          onChange={handleScrub}
          className="timelapse-scrubber"
        />

        <div className="timelapse-speed">
          {[0.5, 1, 2, 4].map((s) => (
            <button
              key={s}
              className={speed === s ? "speed-btn active" : "speed-btn"}
              onClick={() => setSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}