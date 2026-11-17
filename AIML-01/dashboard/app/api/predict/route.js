import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function equalSecret(a, b) {
  const left = createHash("sha256").update(a).digest();
  const right = createHash("sha256").update(b).digest();
  return timingSafeEqual(left, right);
}

function reply(message, status) {
  return NextResponse.json(
    { error: message },
    { status, headers: { "Cache-Control": "no-store" } }
  );
}

export async function POST(request) {
  const backend = process.env.AIML01_BACKEND_URL;
  const apiKey = process.env.AIML01_BACKEND_API_KEY;
  const accessCode = process.env.AIML01_DASHBOARD_ACCESS_CODE;

  if (!backend || !apiKey || !accessCode ||
      apiKey.length < 32 || accessCode.length < 16) {
    return reply("Server configuration incomplete", 503);
  }

  let url;
  try {
    url = new URL(backend);
  } catch {
    return reply("Backend configuration invalid", 503);
  }

  if (url.protocol !== "https:" &&
      !(url.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(url.hostname))) {
    return reply("Secure backend connection required", 503);
  }

  const suppliedCode = request.headers.get("x-demo-access-code") || "";

  if (!equalSecret(suppliedCode, accessCode)) {
    return reply("Access denied", 401);
  }

  if (Number(request.headers.get("content-length") || 0) > 10000) {
    return reply("Request too large", 413);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return reply("Invalid JSON", 400);
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return reply("Invalid transaction", 400);
  }

  const requiredStrings = [
    "event_id", "event_timestamp", "type", "nameOrig", "nameDest"
  ];
  const requiredNumbers = [
    "transaction_id", "step", "amount",
    "oldbalanceOrg", "oldbalanceDest"
  ];

  if (requiredStrings.some(
    k => typeof body[k] !== "string" || !body[k].trim() ||
         body[k].length > 256
  ) || requiredNumbers.some(
    k => typeof body[k] !== "number" || !Number.isFinite(body[k])
  )) {
    return reply("Invalid transaction fields", 400);
  }

  if (!Number.isSafeInteger(body.transaction_id) ||
      body.transaction_id < 0 || body.step !== 377 ||
      body.amount < 0 || body.oldbalanceOrg < 0 ||
      body.oldbalanceDest < 0 ||
      !["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN", "DEBIT"]
        .includes(body.type)) {
    return reply("Transaction values outside demo contract", 400);
  }

  const allowed = [...requiredStrings, ...requiredNumbers];
  const event = Object.fromEntries(
    allowed.map(k => [k, body[k]])
  );

  try {
    const response = await fetch(
      new URL("/predict", url.origin),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey
        },
        body: JSON.stringify(event),
        signal: AbortSignal.timeout(15000),
        cache: "no-store"
      }
    );

    if (!response.ok) {
      return reply(
        "Fraud scoring service rejected the request",
        response.status === 422 ? 422 : 502
      );
    }

    const result = await response.json();
    if (typeof result.fraud_probability !== "number" ||
        !Number.isFinite(result.fraud_probability) ||
        result.fraud_probability < 0 ||
        result.fraud_probability > 1) {
      return reply("Invalid scoring service response", 502);
    }

    return NextResponse.json(
      {
        event_id: result.event_id,
        fraud_probability: result.fraud_probability,
        decision_threshold: result.decision_threshold,
        fraud_alert: result.fraud_alert,
        prediction_status: result.prediction_status,
        feature_count: result.feature_count,
        serving_mode: result.serving_mode,
        latency_ms: result.latency_ms
      },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch {
    return reply("Fraud scoring service unavailable", 502);
  }
}
