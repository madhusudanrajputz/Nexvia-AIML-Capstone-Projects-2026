
import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import predictor from "../../../lib/netlify-score.cjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(message, status) {
  return NextResponse.json(
    { error: message },
    {
      status,
      headers: { "Cache-Control": "no-store" }
    }
  );
}

function sameSecret(a, b) {
  return timingSafeEqual(
    createHash("sha256").update(a).digest(),
    createHash("sha256").update(b).digest()
  );
}

export async function POST(request) {
  const accessCode = process.env.AIML01_DASHBOARD_ACCESS_CODE;

  if (!accessCode || accessCode.length < 16) {
    return reply("Demo access is not configured", 503);
  }

  if (!sameSecret(
    request.headers.get("x-demo-access-code") || "",
    accessCode
  )) {
    return reply("Access denied", 401);
  }

  if (Number(request.headers.get("content-length") || 0) > 10000) {
    return reply("Request too large", 413);
  }

  let body;

  try {
    const raw = await request.text();

    if (Buffer.byteLength(raw, "utf8") > 10000) {
      return reply("Request too large", 413);
    }

    body = JSON.parse(raw);
  } catch {
    return reply("Invalid JSON", 400);
  }

  try {
    const result = predictor.predictTransaction(body);

    return NextResponse.json(
      result,
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (error) {
    if (error.message === "INVALID_INPUT") {
      return reply("Invalid transaction", 400);
    }

    if (error.message === "HISTORY_UNAVAILABLE") {
      return reply(
        "Historical snapshot unavailable for this transaction",
        422
      );
    }

    return reply("Prediction unavailable", 500);
  }
}
