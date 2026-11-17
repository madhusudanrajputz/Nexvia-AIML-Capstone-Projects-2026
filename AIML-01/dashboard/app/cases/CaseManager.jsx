"use client";

import { useState } from "react";
import styles from "./cases.module.css";

const statuses = ["OPEN", "INVESTIGATING", "RESOLVED"];
const labels = ["", "FRAUD", "LEGITIMATE", "UNCERTAIN"];

export default function CasesPage() {
  const [code, setCode] = useState("");
  const [cases, setCases] = useState([]);
  const [eventId, setEventId] = useState("");
  const [probability, setProbability] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function call(path, method = "GET", body = undefined) {
    const response = await fetch(`/api/cases${path}`, {
      method,
      headers: {
        "x-demo-access-code": code,
        ...(body === undefined ? {} : {
          "Content-Type": "application/json"
        })
      },
      ...(body === undefined ? {} : {
        body: JSON.stringify(body)
      }),
      cache: "no-store"
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Case request failed");
    }
    return data;
  }

  async function refresh() {
    setBusy(true);
    setMessage("");
    try {
      const result = await call("");
      setCases(result.cases);
      setLoaded(true);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");

    try {
      const p = Number(probability);
      if (!Number.isFinite(p) || p < 0 || p > 1) {
        throw new Error("Probability must be between 0 and 1");
      }
      await call("", "POST", {
        event_id: eventId.trim(),
        fraud_probability: p
      });
      const result = await call("");
      setCases(result.cases);
      setLoaded(true);
      setEventId("");
      setProbability("");
      setMessage("Case created successfully");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function update(id, changes) {
    setBusy(true);
    setMessage("");
    try {
      await call(`/${id}`, "PATCH", changes);
      const result = await call("");
      setCases(result.cases);
      setLoaded(true);
      setMessage(`Case ${id} updated`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <a href="/" className={styles.back}>← Dashboard overview</a>
        <p className={styles.eyebrow}>AIML-01 / Analyst workspace</p>
        <h1>Fraud Investigation Cases</h1>
        <p className={styles.muted}>
          Review case status and record analyst feedback.
          Case records are served by a separate authenticated API.
        </p>

        <section className={styles.panel}>
          <label htmlFor="demo-code">Analyst demo access code</label>
          <div className={styles.row}>
            <input id="demo-code" type="password"
              autoComplete="off" value={code}
              onChange={e => setCode(e.target.value)}
              placeholder="Enter demo access code" />
            <button disabled={busy || !code} onClick={refresh}>
              {busy ? "Working..." : "Load cases"}
            </button>
          </div>
        </section>

        <section className={styles.panel}>
          <h2>Create investigation case</h2>
          <p className={styles.muted}>
            Manual demo entry. Automatic creation from fraud alerts
            is not connected yet.
          </p>
          <form className={styles.row} onSubmit={create}>
            <input aria-label="Event ID" required maxLength={128}
              placeholder="Event ID" value={eventId}
              onChange={e => setEventId(e.target.value)} />
            <input aria-label="Fraud probability" required
              type="number" min="0" max="1" step="any"
              placeholder="Probability (0–1)" value={probability}
              onChange={e => setProbability(e.target.value)} />
            <button disabled={busy || !code} type="submit">
              Create case
            </button>
          </form>
        </section>

        {message && <p className={styles.message} role="status">
          {message}
        </p>}

        <section className={styles.panel}>
          <h2>Analyst case queue</h2>
          {!loaded && <p className={styles.muted}>
            Enter the access code and load cases.
          </p>}
          {loaded && cases.length === 0 && <p>No cases found.</p>}
          {cases.map(item => (
            <article key={item.id} className={styles.case}>
              <div className={styles.caseHeader}>
                <strong>Case #{item.id}: {item.event_id}</strong>
                <span>Fraud risk: {
                  (item.fraud_probability * 100).toFixed(2)
                }%</span>
              </div>
              <div className={styles.row}>
                <label>
                  Case status
                  <select disabled={busy} value={item.status}
                    onChange={e => update(item.id, {
                      status: e.target.value
                    })}>
                    {statuses.map(value =>
                      <option key={value}>{value}</option>
                    )}
                  </select>
                </label>
                <label>
                  Feedback label
                  <select disabled={busy}
                    value={item.feedback_label || ""}
                    onChange={e => update(item.id, {
                      feedback_label: e.target.value
                    })}>
                    {labels.map(value =>
                      <option key={value} value={value}>
                        {value || "Not reviewed"}
                      </option>
                    )}
                  </select>
                </label>
              </div>
              <form className={styles.row}
                onSubmit={e => {
                  e.preventDefault();
                  const note = new FormData(e.currentTarget)
                    .get("analyst_note");
                  update(item.id, { analyst_note: String(note) });
                }}>
                <input name="analyst_note" disabled={busy}
                  key={`${item.id}-${item.updated_at}`}
                  defaultValue={item.analyst_note || ""}
                  maxLength={2000}
                  aria-label={`Analyst note for case ${item.id}`}
                  placeholder="Analyst note" />
                <button type="submit" disabled={busy}>
                  Save note
                </button>
              </form>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
