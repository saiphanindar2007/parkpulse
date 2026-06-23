import { useEffect, useState } from "react";
import { api } from "./api";

export default function IntelligenceDigest() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/digest")
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error(err);
        setError("Digest unavailable — make sure anomalies and backtest have been generated.");
      });
  }, []);

  if (error) return null; // fail quietly, this is a supplementary panel
  if (!data) return <div className="digest-panel placeholder">Generating digest…</div>;

  return (
    <div className="digest-panel">
      <div className="digest-header">
        <h3>Intelligence Digest</h3>
        <span className="digest-badge">Auto-generated from live data</span>
      </div>
      <ul className="digest-list">
        {data.generated_summary.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    </div>
  );
}