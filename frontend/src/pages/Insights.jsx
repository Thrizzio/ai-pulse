import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const PRIORITY_STYLES = {
  high: { background: "#fee4e2", color: "#b42318", border: "1px solid #fecdca" },
  medium: { background: "#fef0c7", color: "#b54708", border: "1px solid #fedf89" },
  low: { background: "#f2f4f7", color: "#344054", border: "1px solid #eaecf0" },
};

export default function Insights({ org, department, onBack }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const query = department?.id != null ? `?department_id=${department.id}` : "";
    api(`/insights${query}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [org, department]);

  if (error) {
    return (
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>{department?.department ? `${department.department} Insights` : "Department Insights"}</h2>
          {onBack && <button onClick={onBack} style={{ background: "#666" }}>Back to Dashboard</button>}
        </div>
        <p className="error" style={{ marginTop: "16px" }}>Failed to generate insights: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card">
        <p>Analyzing aggregate patterns and generating recommendations…</p>
      </div>
    );
  }

  // Group insights by department
  const grouped = {};
  for (const item of data.insights || []) {
    const dept = item.department || "General";
    if (!grouped[dept]) grouped[dept] = [];
    grouped[dept].push(item);
  }
  const departments = Object.keys(grouped);
  const deptDisplayName = data.department || department?.department;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{data.organization} - {deptDisplayName ? `${deptDisplayName} Insights` : "Department Insights"}</h2>
        {onBack && <button onClick={onBack} style={{ background: "#666" }}>Back to Dashboard</button>}
      </div>

      {department && (
        <div style={{ background: "#f8f9fa", border: "1px solid #e9ecef", borderRadius: "6px", padding: "10px 14px", marginTop: "12px", marginBottom: "16px", display: "flex", gap: "24px", fontSize: "0.9rem", flexWrap: "wrap" }}>
          <span><b>Department:</b> {department.department}</span>
          <span><b>Headcount:</b> {department.employees}</span>
          <span><b>Completed respondents:</b> {department.responded}</span>
          <span><b>Average score:</b> {department.average_score !== null ? department.average_score : "—"}</span>
          <span><b>Maturity level:</b> {department.level}</span>
        </div>
      )}

      <p style={{ color: "#555", marginTop: "8px", marginBottom: "16px" }}>
        Actionable governance recommendations and risk mitigation steps derived from privacy-filtered aggregate patterns across eligible departments, never from individual employee answers.
      </p>

      {data.source && (
        <p style={{ fontSize: "0.85rem", color: "#666", marginBottom: "20px" }}>
          <b>Report engine:</b> {data.source === "ai" ? "AI Advisory Model" : data.source === "mock" ? "Mock Simulation" : "Deterministic Policy Rules"}
        </p>
      )}

      {departments.length === 0 ? (
        <div style={{ padding: "16px", background: "#f9fafb", borderRadius: "8px", border: "1px solid #eaecf0", marginTop: "12px" }}>
          <p style={{ margin: 0, fontWeight: "bold" }}>No eligible department insights available.</p>
          <p style={{ margin: "6px 0 0", color: "#666", fontSize: "0.95rem" }}>
            To protect employee anonymity under the k-anonymity policy, insights are only generated for departments with at least 5 completed diagnostics.
          </p>
        </div>
      ) : (
        <div>
          {departments.map((deptName) => (
            <div key={deptName} style={{ marginBottom: "24px", borderTop: "1px solid #eee", paddingTop: "16px" }}>
              <h3 style={{ margin: "0 0 12px 0", color: "#222" }}>{deptName}</h3>
              {grouped[deptName].map((insight, idx) => {
                const pStyle = PRIORITY_STYLES[insight.priority] || PRIORITY_STYLES.medium;
                return (
                  <div
                    key={idx}
                    style={{
                      background: "#fafafa",
                      border: "1px solid #eaeaea",
                      borderRadius: "8px",
                      padding: "16px",
                      marginBottom: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: "bold",
                          textTransform: "uppercase",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          ...pStyle,
                        }}
                      >
                        {insight.priority} priority
                      </span>
                    </div>

                    <p style={{ margin: "6px 0" }}>
                      <b>Observed pattern:</b> {insight.observed_pattern}
                    </p>
                    <p style={{ margin: "6px 0", color: "#1d2433" }}>
                      <b>Recommended action:</b> {insight.recommended_action}
                    </p>
                    <p style={{ margin: "6px 0", color: "#475467", fontSize: "0.95rem" }}>
                      <b>Reason:</b> {insight.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {data.hidden_small_groups && (
        <p style={{ color: "#666", fontSize: "0.9rem", fontStyle: "italic", marginTop: "20px" }}>
          Note: One or more departments with fewer than 5 completed diagnostics are hidden to protect employee anonymity.
        </p>
      )}
    </div>
  );
}

