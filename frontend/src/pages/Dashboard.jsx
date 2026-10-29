import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Dashboard({ org, onBack, onViewInsights }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/dashboard")
      .then(setData)
      .catch((err) => setError(err.message));
  }, [org]);

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!data) return <div className="card"><p>Loading dashboard…</p></div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{data.organization} - Executive Dashboard</h2>
        <div>
          {onBack && <button onClick={onBack} style={{ background: "#666" }}>Back</button>}
        </div>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "16px" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #eee", textAlign: "left" }}>
            <th style={{ padding: "8px" }}>Department</th>
            <th style={{ padding: "8px" }}>Headcount</th>
            <th style={{ padding: "8px" }}>Responded</th>
            <th style={{ padding: "8px" }}>Average Score</th>
            <th style={{ padding: "8px" }}>Maturity Level</th>
            <th style={{ padding: "8px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {data.departments.map((d) => (
            <tr key={d.department} style={{ borderBottom: "1px solid #f0f0f0" }}>
              <td style={{ padding: "8px" }}><b>{d.department}</b></td>
              {d.suppressed ? (
                <td colSpan={4} style={{ padding: "8px", color: "#666", fontStyle: "italic" }}>
                  Suppressed for privacy
                </td>
              ) : (
                <>
                  <td style={{ padding: "8px" }}>{d.employees !== null ? d.employees : "—"}</td>
                  <td style={{ padding: "8px" }}>{d.responded !== null ? d.responded : "—"}</td>
                  <td style={{ padding: "8px" }}>{d.average_score !== null ? d.average_score : "—"}</td>
                  <td style={{ padding: "8px" }}>{d.level}</td>
                </>
              )}
              <td style={{ padding: "8px" }}>
                {d.id != null && onViewInsights && (
                  <button
                    onClick={() => onViewInsights(d)}
                    style={{ padding: "4px 10px", fontSize: "0.85rem" }}
                  >
                    Insights
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.hidden_small_groups && (
        <p style={{ color: "#666", fontSize: "0.9rem", fontStyle: "italic", marginTop: "12px" }}>
          Note: One or more departments with fewer than 5 completed diagnostics are hidden to protect employee anonymity.
        </p>
      )}

      <h3 style={{ marginTop: "24px" }}>Top Company Risks</h3>
      {data.top_risks && data.top_risks.length > 0 ? (
        <ul>
          {data.top_risks.map(([flag, count]) => (
            <li key={flag}>
              <code>{flag}</code> ({count} occurrences)
            </li>
          ))}
        </ul>
      ) : (
        <p>No risks flagged yet.</p>
      )}
    </div>
  );
}
