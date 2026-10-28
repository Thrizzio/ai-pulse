import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report({ onRetake, onBack }) {
  const [report, setReport] = useState(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const data = await api("/reports/me");
      setReport(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Are you sure you want to delete all your diagnostic answers and report?")) {
      return;
    }
    try {
      await api("/reports/me", { method: "DELETE" });
      setMsg("Your diagnostic responses and report have been permanently deleted.");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!report) return <div className="card"><p>Loading…</p></div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{report.name}: {report.level}</h2>
        <div>
          {onRetake && <button onClick={onRetake} style={{ marginRight: "8px" }}>Retake Diagnostic</button>}
          {onBack && <button onClick={onBack} style={{ background: "#666" }}>Back</button>}
        </div>
      </div>

      {msg && <p style={{ color: "green" }}>{msg}</p>}

      <p><b>Organization:</b> {report.organization}</p>
      <p><b>Answered questions:</b> {report.answered}</p>
      <p><b>Average score:</b> {report.average_score !== null ? report.average_score : "Not assessed"}</p>
      {report.source && (
        <p><small><b>Assessment source:</b> {report.source === "mock" ? "Mock Simulation" : "AI Assessment"}</small></p>
      )}

      <h3>Risks</h3>
      {report.risks && report.risks.length > 0 ? (
        <ul>{report.risks.map((r) => <li key={r}>{r}</li>)}</ul>
      ) : (
        <p>No risks flagged.</p>
      )}

      <h3>Next steps</h3>
      <ul>{report.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>

      {report.answered > 0 && (
        <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #eee" }}>
          <button onClick={handleDelete} style={{ background: "#b42318" }}>
            Delete My Data
          </button>
        </div>
      )}
    </div>
  );
}
