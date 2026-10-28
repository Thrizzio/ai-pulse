import React, { useState, useEffect } from "react";
import Login from "./pages/Login.jsx";
import OrgPicker from "./pages/OrgPicker.jsx";
import Diagnostic from "./pages/Diagnostic.jsx";
import Report from "./pages/Report.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Insights from "./pages/Insights.jsx";
import { getToken } from "./api.js";

export default function App() {
  const [step, setStep] = useState("login");
  const [session, setSession] = useState(null);
  const [org, setOrg] = useState(null);
  const [selectedDept, setSelectedDept] = useState(null);

  useEffect(() => {
    // Read persistent session from localStorage on mount
    const savedToken = getToken();
    const savedSession = localStorage.getItem("session");
    const savedOrg = localStorage.getItem("active_org");
    const savedStep = localStorage.getItem("step");
    const savedDept = localStorage.getItem("selected_dept");

    if (savedDept) {
      try {
        setSelectedDept(JSON.parse(savedDept));
      } catch (e) {}
    }

    if (savedToken && savedSession) {
      try {
        const parsedSession = JSON.parse(savedSession);
        setSession(parsedSession);
        if (savedOrg) {
          const parsedOrg = JSON.parse(savedOrg);
          setOrg(parsedOrg);
          setStep(savedStep || (parsedOrg.role === "admin" ? "dashboard" : "report"));
        } else {
          setStep("org");
        }
      } catch (e) {
        logout();
      }
    }
  }, []);

  function handleLogin(s) {
    setSession(s);
    localStorage.setItem("session", JSON.stringify(s));
    setStep("org");
  }

  function handlePickOrg(o, targetStep) {
    setOrg(o);
    localStorage.setItem("active_org", JSON.stringify(o));
    const nextStep = targetStep || (o.role === "admin" ? "dashboard" : "diagnostic");
    setStep(nextStep);
    localStorage.setItem("step", nextStep);
  }

  function logout() {
    localStorage.clear();
    setSession(null);
    setOrg(null);
    setSelectedDept(null);
    setStep("login");
  }

  function goBackToOrgs() {
    localStorage.removeItem("active_org");
    localStorage.removeItem("step");
    localStorage.removeItem("selected_dept");
    setOrg(null);
    setSelectedDept(null);
    setStep("org");
  }

  return (
    <div className="wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>AI Pulse</h1>
        {session && (
          <div>
            <span style={{ marginRight: "12px", color: "#666" }}>
              {session.user?.name || session.email}
              {org ? ` (${org.org_name})` : ""}
            </span>
            {org && (
              <button onClick={goBackToOrgs} style={{ marginRight: "8px", background: "#555" }}>
                Switch Org
              </button>
            )}
            <button onClick={logout} style={{ background: "#777" }}>
              Logout
            </button>
          </div>
        )}
      </div>

      {step === "login" && <Login onDone={handleLogin} />}
      {step === "org" && session && (
        <OrgPicker orgs={session.organizations} onPick={handlePickOrg} />
      )}
      {step === "diagnostic" && (
        <Diagnostic
          onDone={() => { setStep("report"); localStorage.setItem("step", "report"); }}
          onBack={goBackToOrgs}
        />
      )}
      {step === "report" && (
        <Report
          onBack={goBackToOrgs}
        />
      )}
      {step === "dashboard" && (
        <Dashboard
          org={org}
          onBack={goBackToOrgs}
          onViewInsights={(dept) => {
            setSelectedDept(dept);
            localStorage.setItem("selected_dept", JSON.stringify(dept));
            setStep("insights");
            localStorage.setItem("step", "insights");
          }}
        />
      )}
      {step === "insights" && (
        <Insights
          org={org}
          department={selectedDept}
          onBack={() => {
            setSelectedDept(null);
            localStorage.removeItem("selected_dept");
            setStep("dashboard");
            localStorage.setItem("step", "dashboard");
          }}
        />
      )}
    </div>
  );
}
