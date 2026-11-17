
"use strict";

const { score } = require("./transaction-features.cjs");

const REQUIRED_STRINGS = [
  "event_id", "event_timestamp", "type",
  "nameOrig", "nameDest"
];

const REQUIRED_NUMBERS = [
  "transaction_id", "step", "amount",
  "oldbalanceOrg", "oldbalanceDest"
];

function predictTransaction(body) {
  if (!body || typeof body !== "object" ||
      Array.isArray(body)) {
    throw new Error("INVALID_INPUT");
  }

  for (const key of REQUIRED_STRINGS) {
    if (typeof body[key] !== "string" ||
        !body[key].trim() || body[key].length > 256) {
      throw new Error("INVALID_INPUT");
    }
  }

  for (const key of REQUIRED_NUMBERS) {
    if (typeof body[key] !== "number" ||
        !Number.isFinite(body[key])) {
      throw new Error("INVALID_INPUT");
    }
  }

  if (!Number.isSafeInteger(body.transaction_id) ||
      body.transaction_id < 0 ||
      body.step !== 377 ||
      body.amount < 0 ||
      body.oldbalanceOrg < 0 ||
      body.oldbalanceDest < 0 ||
      body.event_id !== `paysim:${body.transaction_id}` ||
      !["TRANSFER", "CASH_OUT", "PAYMENT",
        "CASH_IN", "DEBIT"].includes(body.type)) {
    throw new Error("INVALID_INPUT");
  }

  const start = performance.now();

  let prediction;

  try {
    prediction = score(body);
  } catch {
    throw new Error("HISTORY_UNAVAILABLE");
  }

  return {
    event_id: prediction.event_id,
    fraud_probability: prediction.fraud_probability,
    fraud_alert: prediction.fraud_alert,
    decision_threshold: 0.48456997,
    prediction_status: "SCORED",
    feature_count: 23,
    serving_mode: "frozen_feast_snapshot",
    latency_ms: Math.max(0, performance.now() - start)
  };
}

module.exports = { predictTransaction };
