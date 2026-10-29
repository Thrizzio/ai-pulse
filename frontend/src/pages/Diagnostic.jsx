import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Diagnostic({ onDone, onBack }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});

  useEffect(() => {
    api("/diagnostic/questions").then(setQuestions);
  }, []);

  async function submit() {
    const payload = Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer }));
    await api("/diagnostic/submit", { method: "POST", body: JSON.stringify({ answers: payload }) });
    onDone();
  }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <h2 style={{ margin: 0 }}>Your AI diagnostic</h2>
        {onBack && <button onClick={onBack} style={{ background: "#666" }}>Back</button>}
      </div>
      {questions.map((q) => (
        <div key={q.id}>
          <p><b>{q.text}</b></p>
          {q.type === "mcq" ? (
            <select onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} defaultValue="">
              <option value="" disabled>Choose…</option>
              {q.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <textarea rows={4} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
          )}
        </div>
      ))}
      <button onClick={submit}>Submit</button>
    </div>
  );
}
