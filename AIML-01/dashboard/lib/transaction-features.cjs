
"use strict";

const snapshot = require("./feast-history-snapshot.json");
const inference = require("./xgboost-inference.cjs");

const TYPES = [
  "CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"
];

function buildFeatures(tx) {
  if (!tx || typeof tx !== "object" || Array.isArray(tx)) {
    throw new Error("Invalid transaction");
  }

  const timestamp = Date.parse(tx.event_timestamp);

  if (!Number.isFinite(timestamp) ||
      !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(
        tx.event_timestamp || ""
      ) || timestamp % 1000 !== 0) {
    throw new Error("Invalid event timestamp");
  }

  if (!TYPES.includes(tx.type)) {
    throw new Error("Invalid transaction type");
  }

  for (const field of [
    "amount", "oldbalanceOrg", "oldbalanceDest"
  ]) {
    if (typeof tx[field] !== "number" ||
        !Number.isFinite(tx[field]) || tx[field] < 0) {
      throw new Error("Invalid transaction amount or balance");
    }
  }

  const origin = snapshot.origin[tx.nameOrig];
  const destination = snapshot.destination[tx.nameDest];

  if (!origin || !destination) {
    throw new Error("Historical account unavailable");
  }

  const eventSeconds = timestamp / 1000;

  if (origin.event_ts !== eventSeconds ||
      destination.event_ts !== eventSeconds) {
    throw new Error("Historical snapshot timestamp mismatch");
  }

  const h = {
    ...origin.features,
    ...destination.features
  };

  const amount = tx.amount;
  const ob = tx.oldbalanceOrg;
  const db = tx.oldbalanceDest;
  const om = h.origin_previous_mean;
  const dm = h.destination_previous_mean;

  const ratio = (a, b) => b > 0 ? a / b : 0;

  const f = {
    amount_log: Math.log1p(amount),
    origin_balance_log: Math.log1p(ob),
    destination_balance_log: Math.log1p(db),
    origin_previous_count: h.origin_previous_count,
    origin_previous_total_log: Math.log1p(h.origin_previous_total),
    origin_previous_mean_log: Math.log1p(om),
    origin_hours_since_previous: h.origin_hours_since_previous,
    destination_previous_count: h.destination_previous_count,
    destination_previous_total_log: Math.log1p(h.destination_previous_total),
    destination_previous_mean_log: Math.log1p(dm),
    destination_hours_since_previous: h.destination_hours_since_previous,
    amount_vs_origin_mean: ratio(amount, om),
    amount_vs_destination_mean: ratio(amount, dm),
    amount_to_origin_balance: amount / (ob + 1),
    amount_to_destination_balance: amount / (db + 1),
    origin_has_history: Number(h.origin_previous_count > 0),
    destination_has_history: Number(h.destination_previous_count > 0),
    origin_balance_insufficient: Number(amount > ob)
  };

  for (const type of TYPES) {
    f["type_" + type.toLowerCase()] = Number(tx.type === type);
  }

  const ordered = inference.featureNames.map(name => f[name]);

  if (ordered.some(value =>
      typeof value !== "number" || !Number.isFinite(value))) {
    throw new Error("Invalid model features");
  }

  return ordered;
}

function score(tx) {
  const probability = inference.predict(buildFeatures(tx));
  return {
    event_id: tx.event_id,
    fraud_probability: probability,
    fraud_alert: probability >= 0.48456997
  };
}

module.exports = { buildFeatures, score };
