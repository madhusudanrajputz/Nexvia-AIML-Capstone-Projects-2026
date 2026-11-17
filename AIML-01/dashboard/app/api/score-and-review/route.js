import { NextResponse } from "next/server";
import { POST as predict } from "../predict/route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function validServiceURL(raw) {
  try {
    const url = new URL(raw);

    const local = (
      url.protocol === "http:" &&
      ["127.0.0.1", "localhost"].includes(url.hostname)
    );

    const secure = url.protocol === "https:";

    if ((!local && !secure) ||
        !["", "/"].includes(url.pathname) ||
        url.search || url.hash ||
        url.username || url.password) {
      return null;
    }

    return url.origin;
  } catch {
    return null;
  }
}

function output(prediction, status, extra = {}) {
  return NextResponse.json(
    {
      ...prediction,
      case_creation_status: status,
      ...extra
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}

export async function POST(request) {
  // Reuse the existing authenticated model-scoring route.
  // Do not accept client-provided fraud decisions.
  const scored = await predict(request);

  if (!scored.ok) {
    return scored;
  }

  let prediction;

  try {
    prediction = await scored.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid scoring response" },
      { status: 502 }
    );
  }

  if (typeof prediction.fraud_alert !== "boolean" ||
      typeof prediction.event_id !== "string" ||
      !prediction.event_id ||
      typeof prediction.fraud_probability !== "number" ||
      !Number.isFinite(prediction.fraud_probability) ||
      prediction.fraud_probability < 0 ||
      prediction.fraud_probability > 1) {
    return NextResponse.json(
      { error: "Invalid model decision" },
      { status: 502 }
    );
  }

  if (!prediction.fraud_alert) {
    return output(prediction, "NOT_REQUIRED");
  }

  const service = validServiceURL(
    process.env.AIML01_CASES_SERVICE_URL
  );
  const key = process.env.AIML01_CASES_API_KEY;

  if (!service || !key || key.length < 32) {
    return output(prediction, "FAILED", {
      case_error: "Case service not configured"
    });
  }

  try {
    const response = await fetch(
      `${service}/cases`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": key
        },
        body: JSON.stringify({
          event_id: prediction.event_id,
          fraud_probability: prediction.fraud_probability,
          description:
            "Automatically created from XGBoost fraud alert"
        }),
        cache: "no-store",
        signal: AbortSignal.timeout(15000)
      }
    );

    if (response.status === 409) {
      return output(prediction, "ALREADY_EXISTS");
    }

    if (!response.ok) {
      return output(prediction, "FAILED", {
        case_error: "Case service rejected alert"
      });
    }

    const created = await response.json();

    if (!Number.isSafeInteger(created.id) ||
        created.id < 1 ||
        created.event_id !== prediction.event_id) {
      return output(prediction, "FAILED", {
        case_error: "Case service returned invalid confirmation"
      });
    }

    return output(prediction, "CREATED", {
      case_id: created.id
    });

  } catch {
    return output(prediction, "FAILED", {
      case_error: "Case service unavailable"
    });
  }
}
