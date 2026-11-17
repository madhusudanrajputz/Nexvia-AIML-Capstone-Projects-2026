
import { NextResponse } from "next/server";
import { POST as predict } from "../netlify-predict/route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request) {
  const response = await predict(request);

  if (!response.ok) {
    return response;
  }

  const prediction = await response.json();

  if (
    typeof prediction.event_id !== "string" ||
    typeof prediction.fraud_probability !== "number" ||
    !Number.isFinite(prediction.fraud_probability) ||
    typeof prediction.fraud_alert !== "boolean"
  ) {
    return NextResponse.json(
      { error: "Invalid model prediction" },
      { status: 502 }
    );
  }

  const caseAvailable = !prediction.fraud_alert;

  return NextResponse.json(
    {
      ...prediction,
      case_creation_status: caseAvailable
        ? "NOT_REQUIRED"
        : "FAILED",
      ...(caseAvailable ? {} : {
        case_error:
          "Persistent case management is unavailable in this hosted demo."
      })
    },
    {
      headers: {
        "Cache-Control": "no-store"
      }
    }
  );
}
