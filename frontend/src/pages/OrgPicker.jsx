import React, { useEffect, useState } from "react";
import { api, setToken } from "../api.js";

export default function OrgPicker({ orgs, onPick }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadReports();
  }, []);

  async function loadReports() {
    try {
      const data = await api("/reports");
      setReports(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function pick(o) {
    const data = await api("/auth/select-org", { method: "POST", body: JSON.stringify({ org_id: o.org_id }) });
    setToken(data.token);
    onPick(o);
  }

  async function handleViewReport(reportEntry) {
    const data = await api("/auth/select-org", { method: "POST", body: JSON.stringify({ org_id: reportEntry.org_id }) });
    setToken(data.token);
    const fullOrg = orgs.find((o) => o.org_id === reportEntry.org_id) || {
      org_id: reportEntry.org_id,
      org_name: reportEntry.organization,
      role: reportEntry.role || "employee",
    };
    onPick(fullOrg, "report");
  }

  async function handleDelete(reportEntry) {
    if (!window.confirm(`Are you sure you want to delete your diagnostic report for ${reportEntry.organization}?`)) {
      return;
    }
    try {
      await api(`/reports/me?org_id=${reportEntry.org_id}`, { method: "DELETE" });
      setReports((prev) => prev.filter((r) => r.org_id !== reportEntry.org_id));
    } catch (err) {
      alert("Failed to delete report: " + err.message);
    }
  }

  return (
    <div className="card">
      <h2>Choose an organization</h2>
      {orgs.map((o) => (
        <p key={o.org_id}>
          <button onClick={() => pick(o)}>{o.org_name}</button> <small>({o.role})</small>
        </p>
      ))}

      <div style={{ marginTop: "28px", paddingTop: "16px", borderTop: "1px solid #eee" }}>
        <h3>Previous Reports</h3>
        {loading ? (
          <p style={{ color: "#666" }}>Loading previous reports…</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : reports.length === 0 ? (
          <p style={{ color: "#666" }}>No previous reports yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {reports.map((r) => (
              <li
                key={r.org_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  background: "#f9fafb",
                  border: "1px solid #eaecf0",
                  borderRadius: "6px",
                  marginBottom: "8px",
                }}
              >
                <div>
                  <b>{r.organization}</b>{" "}
                  <span style={{ color: "#027a48", fontSize: "0.85rem", marginLeft: "8px" }}>
                    ✓ Report Available ({r.level})
                  </span>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    onClick={() => handleViewReport(r)}
                    style={{ padding: "4px 10px", fontSize: "0.85rem" }}
                  >
                    View Report
                  </button>
                  <button
                    onClick={() => handleDelete(r)}
                    style={{ padding: "4px 10px", fontSize: "0.85rem", background: "#b42318" }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
