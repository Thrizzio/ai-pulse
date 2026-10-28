import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// TODO: this is a placeholder. Leadership needs a real dashboard.
export default function Dashboard({ org }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    api("/dashboard").then(setData);
  }, [org]);

  return (
    <div className="card">
      <h2>Dashboard</h2>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
