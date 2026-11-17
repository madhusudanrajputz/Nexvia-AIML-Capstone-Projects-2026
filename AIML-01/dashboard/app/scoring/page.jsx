"use client";

import { useState } from "react";
import styles from "./scoring.module.css";

const initial = {
  transaction_id: "970000001",
  type: "TRANSFER",
  amount: "250",
  nameOrig: "C19423",
  nameDest: "M503669",
  oldbalanceOrg: "1000",
  oldbalanceDest: "500"
};

export default function Scoring() {
  const [form, setForm] = useState(initial);
  const [accessCode, setAccessCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(key, value) {
    setForm(current => ({ ...current, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);

    const transactionId = Number(form.transaction_id);
    const body = {
      event_id: `paysim:${transactionId}`,
      transaction_id: transactionId,
      step: 377,
      event_timestamp: new Date(
        Date.UTC(2026, 0, 1) + 377 * 3600000
      ).toISOString(),
      type: form.type,
      amount: Number(form.amount),
      nameOrig: form.nameOrig.trim(),
      nameDest: form.nameDest.trim(),
      oldbalanceOrg: Number(form.oldbalanceOrg),
      oldbalanceDest: Number(form.oldbalanceDest)
    };

    try {
      const response = await fetch("/api/netlify-score-and-review", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-demo-access-code": accessCode
        },
        body: JSON.stringify(body),
        cache: "no-store"
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Prediction failed");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setBusy(false);
    }
  }

  const fields = [
    ["transaction_id", "Transaction ID", "number"],
    ["amount", "Amount", "number"],
    ["nameOrig", "Origin account", "text"],
    ["nameDest", "Destination account", "text"],
    ["oldbalanceOrg", "Origin balance before", "number"],
    ["oldbalanceDest", "Destination balance before", "number"]
  ];

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <a href="/" className={styles.back}>← Dashboard overview</a>
        <p className={styles.eyebrow}>AIML-01 / Risk assessment</p>
        <h1>Transaction Fraud Scoring</h1>
        <p className={styles.subheading}>
          Hosted XGBoost inference using a frozen Feast history snapshot.
          Historical hour-377 demonstration, not a live banking service.
        </p>

        <div className={styles.layout}>
          <form onSubmit={submit} className={styles.panel}>
            <h2>Transaction details</h2>
            <label>
              Demo access code
              <input type="password" value={accessCode}
                autoComplete="off" required
                onChange={e => setAccessCode(e.target.value)}
                placeholder="Enter analyst demo access code" />
            </label>
            <label>
              Transaction type
              <select value={form.type}
                onChange={e => update("type", e.target.value)}>
                {["TRANSFER", "CASH_OUT", "PAYMENT",
                  "CASH_IN", "DEBIT"].map(t =>
                    <option key={t} value={t}>{t}</option>
                  )}
              </select>
            </label>
            {fields.map(([key, title, type]) => (
              <label key={key}>
                {title}
                <input type={type} value={form[key]} required
                  step={type === "number" ? "any" : undefined}
                  min={type === "number" ? "0" : undefined}
                  onChange={e => update(key, e.target.value)} />
              </label>
            ))}
            <button disabled={busy} type="submit">
              {busy ? "Scoring transaction..." : "Calculate fraud risk"}
            </button>
          </form>

          <section className={styles.panel} aria-live="polite">
            <h2>Fraud risk assessment</h2>
            {!result && !error && (
              <p className={styles.subheading}>
                Submit a transaction to calculate its fraud probability.
                Enter a verified historical transaction to calculate its fraud probability.
              </p>
            )}
            {error && <p className={styles.error}>{error}</p>}
            {result && (
              <div>
                <p className={styles.eyebrow}>Fraud probability</p>
                <p className={styles.probability}>
                  {(result.fraud_probability * 100).toFixed(4)}%
                </p>
                <div className={
                  result.fraud_alert ? styles.alert : styles.normal
                }>
                  {result.fraud_alert
                    ? "Flagged for analyst review"
                    : "Not flagged by current threshold"}
                </div>

                {result.case_creation_status === "CREATED" && (
                  <div className={styles.caseNotice} role="status">
                    Investigation case #{result.case_id} created.
                    <a href="/cases"> Review cases</a>
                  </div>
                )}
                {result.case_creation_status === "ALREADY_EXISTS" && (
                  <div className={styles.caseNotice} role="status">
                    This fraud alert already has an investigation case.
                    <a href="/cases"> Open case queue</a>
                  </div>
                )}
                {result.case_creation_status === "FAILED" && (
                  <div className={styles.caseWarning} role="alert">
                    Fraud risk detected. Persistent case storage is unavailable in this hosted demo.
                    {result.case_error && (
                      <p>{result.case_error}</p>
                    )}
                    This alert has not been confirmed as saved.
                  </div>
                )}
                {result.case_creation_status === "NOT_REQUIRED" && (
                  <div className={styles.caseNotice} role="status">
                    No automatic investigation case required.
                  </div>
                )}
                <dl className={styles.details}>
                  <dt>Event</dt><dd>{result.event_id}</dd>
                  <dt>Threshold</dt>
                  <dd>{result.decision_threshold}</dd>
                  <dt>Model features</dt>
                  <dd>{result.feature_count}</dd>
                  <dt>Prediction latency</dt>
                  <dd>{result.latency_ms} ms</dd>
                  <dt>Serving mode</dt>
                  <dd>{result.serving_mode}</dd>
                </dl>
                <p className={styles.subheading}>
                  Model predictions are decision-support signals,
                  not confirmed fraud labels.
                </p>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
