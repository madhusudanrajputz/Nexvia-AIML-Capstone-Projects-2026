import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(error, status) {
  return NextResponse.json({ error }, {
    status,
    headers: { "Cache-Control": "no-store" }
  });
}

function sameSecret(a, b) {
  return timingSafeEqual(
    createHash("sha256").update(a).digest(),
    createHash("sha256").update(b).digest()
  );
}

async function handle(request, context) {
  const base = process.env.AIML01_CASES_SERVICE_URL;
  const key = process.env.AIML01_CASES_API_KEY;
  const code = process.env.AIML01_DASHBOARD_ACCESS_CODE;

  if (!base || !key || !code ||
      key.length < 32 || code.length < 16) {
    return reply("Case service is not configured", 503);
  }

  let url;
  try {
    url = new URL(base);
  } catch {
    return reply("Invalid case service configuration", 503);
  }

  if (!["", "/"].includes(url.pathname) ||
      url.search || url.hash ||
      (url.protocol !== "https:" &&
       !(url.protocol === "http:" &&
         ["127.0.0.1", "localhost"].includes(url.hostname)))) {
    return reply("Invalid case service destination", 503);
  }

  if (!sameSecret(
    request.headers.get("x-demo-access-code") || "",
    code
  )) {
    return reply("Access denied", 401);
  }

  const { path = [] } = await context.params;
  const validId = path.length === 1 &&
    /^[1-9][0-9]*$/.test(path[0]);

  if (!(path.length === 0 || validId)) {
    return reply("Invalid case path", 404);
  }

  if ((request.method === "POST" && path.length !== 0) ||
      (request.method === "PATCH" && !validId)) {
    return reply("Unsupported operation", 405);
  }

  const destination = new URL(
    path.length === 0 ? "/cases" : `/cases/${path[0]}`,
    url.origin
  );

  if (request.method === "GET" && path.length === 0) {
    destination.searchParams.set("limit", "100");
  }

  let body;

  if (["POST", "PATCH"].includes(request.method)) {
    if (Number(request.headers.get("content-length") || 0) > 10000) {
      return reply("Request too large", 413);
    }

    try {
      body = await request.json();
      if (!body || typeof body !== "object" ||
          Array.isArray(body) ||
          JSON.stringify(body).length > 10000) {
        return reply("Invalid request", 400);
      }
    } catch {
      return reply("Invalid JSON", 400);
    }
  }

  try {
    const upstream = await fetch(destination, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": key
      },
      ...(body === undefined ? {} : {
        body: JSON.stringify(body)
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000)
    });

    const data = await upstream.json();

    if (!upstream.ok) {
      return reply(
        typeof data.detail === "string"
          ? data.detail
          : "Case service request failed",
        [400, 401, 404, 409, 422].includes(upstream.status)
          ? upstream.status
          : 502
      );
    }

    return NextResponse.json(data, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" }
    });
  } catch {
    return reply("Case service unavailable", 502);
  }
}

export async function GET(request, context) {
  return handle(request, context);
}
export async function POST(request, context) {
  return handle(request, context);
}
export async function PATCH(request, context) {
  return handle(request, context);
}
