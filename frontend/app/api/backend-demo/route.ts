import { NextResponse } from "next/server";

const NO_STORE = { "Cache-Control": "no-store" };

function isLoopbackHost(host: string | null): boolean {
  if (!host) return false;
  const hostname = host.replace(/^\[(.*)\](?::\d+)?$/, "$1").split(":")[0]?.toLowerCase() ?? "";
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function resolveDemoBackendUrl(rawUrl: string): string | null {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "http:" || parsed.username || parsed.password) return null;
    if (!["localhost", "127.0.0.1", "::1", "[::1]"].includes(parsed.hostname.toLowerCase())) {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

function resolveDemoConfig(request: Request) {
  const host = request.headers.get("host");
  if (!isLoopbackHost(host)) {
    return {
      ok: false as const,
      status: 403,
      code: "error.api",
      detail: "Backend demo proxy is restricted to localhost/loopback connections.",
    };
  }

  const enabled =
    process.env.RELIEFMESH_ENABLE_BACKEND_DEMO === "true" ||
    process.env.RELIEFMESH_ENABLE_INTEGRATION_PREVIEW === "true";
  if (!enabled) {
    return {
      ok: false as const,
      status: 503,
      code: "error.api",
      detail:
        "Opt-in backend demo mode is not enabled on the frontend server. Set RELIEFMESH_ENABLE_BACKEND_DEMO=true.",
    };
  }

  const rawUrl = process.env.RELIEFMESH_BACKEND_URL || "http://127.0.0.1:8000";
  const baseUrl = resolveDemoBackendUrl(rawUrl);
  if (!baseUrl) {
    return {
      ok: false as const,
      status: 503,
      code: "error.api",
      detail: "RELIEFMESH_BACKEND_URL must be an valid loopback URL (http://127.0.0.1:8000).",
    };
  }

  const readKey =
    process.env.RELIEFMESH_BACKEND_READ_KEY?.trim() ||
    process.env.RELIEFMESH_API_KEY?.trim() ||
    "";
  const coordinatorKey =
    process.env.RELIEFMESH_COORDINATOR_API_KEY?.trim() || readKey;
  const automationKey =
    process.env.RELIEFMESH_AUTOMATION_API_KEY?.trim() || readKey;

  return {
    ok: true as const,
    baseUrl,
    readKey,
    coordinatorKey,
    automationKey,
  };
}

function buildHeaders(apiKey: string, actor: "coordinator" | "automation") {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-Fixture-Actor": actor === "coordinator" ? "fixture-coordinator" : "automation",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

function mapBackendErrorCode(status: number, body: Record<string, unknown>): string {
  const code = typeof body.code === "string" ? body.code : "";
  if (code === "STALE_PLAN") return "error.stalePlan";
  if (code === "RESOURCE_UNAVAILABLE" || code === "INVALID_RESOURCES") return "error.resources";
  if (code === "INSUFFICIENT_COVERAGE") return "error.coverage";
  if (code === "APPROVAL_REQUIRED" || status === 401 || status === 403) return "error.approval";
  if (code === "STEP_OUT_OF_ORDER") return "error.order";
  if (code === "CANONICAL_MISMATCH") return "error.canonical";
  if (code === "TRANSLATION_UNAVAILABLE") return "error.translation";
  if (code === "AUTOMATION_OFFLINE") return "notice.offline";
  return "error.api";
}

export async function GET(request: Request) {
  const cfg = resolveDemoConfig(request);
  if (!cfg.ok) {
    return NextResponse.json(
      { ok: false, errorCode: cfg.code, detail: cfg.detail },
      { status: cfg.status, headers: NO_STORE }
    );
  }

  try {
    const response = await fetch(`${cfg.baseUrl}/integration/v1/demo/snapshot`, {
      cache: "no-store",
      headers: buildHeaders(cfg.readKey, "coordinator"),
      signal: AbortSignal.timeout(5000),
    });
    const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    if (!response.ok) {
      return NextResponse.json(
        {
          ok: false,
          errorCode: mapBackendErrorCode(response.status, payload),
          detail: typeof payload.detail === "string" ? payload.detail : "Backend snapshot error",
        },
        { status: response.status, headers: NO_STORE }
      );
    }
    return NextResponse.json({ ok: true, snapshot: payload }, { headers: NO_STORE });
  } catch {
    return NextResponse.json(
      {
        ok: false,
        errorCode: "error.api",
        detail: "FastAPI backend is unreachable at RELIEFMESH_BACKEND_URL.",
      },
      { status: 502, headers: NO_STORE }
    );
  }
}

export async function POST(request: Request) {
  const cfg = resolveDemoConfig(request);
  if (!cfg.ok) {
    return NextResponse.json(
      { ok: false, errorCode: cfg.code, detail: cfg.detail },
      { status: cfg.status, headers: NO_STORE }
    );
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json(
      { ok: false, errorCode: "error.api", detail: "Invalid JSON request body." },
      { status: 400, headers: NO_STORE }
    );
  }

  const action = typeof body.action === "string" ? body.action : "";
  let targetPath = "";
  let payload: Record<string, unknown> = {};
  let actor: "coordinator" | "automation" = "automation";

  switch (action) {
    case "reset":
      targetPath = "/integration/v1/demo/reset";
      payload = { for_run: Boolean(body.forRun) };
      actor = "coordinator";
      break;
    case "setScenario":
      targetPath = "/integration/v1/demo/scenario";
      payload = { scenario: String(body.scenario ?? "normal") };
      actor = "coordinator";
      break;
    case "step": {
      const step = String(body.step ?? "");
      targetPath = "/integration/v1/demo/step";
      payload = { step };
      actor = step === "approve" || step === "approveReplacement" ? "coordinator" : "automation";
      break;
    }
    case "approve":
      targetPath = `/integration/v1/demo/incidents/${encodeURIComponent(String(body.incidentId ?? ""))}/approve`;
      payload = { version: Number(body.version ?? 1) };
      actor = "coordinator";
      break;
    case "modify":
      targetPath = `/integration/v1/demo/incidents/${encodeURIComponent(String(body.incidentId ?? ""))}/modify`;
      payload = {
        version: Number(body.version ?? 1),
        recommended_resources: Array.isArray(body.resourceIds) ? body.resourceIds : [],
      };
      actor = "coordinator";
      break;
    case "reject":
      targetPath = `/integration/v1/demo/incidents/${encodeURIComponent(String(body.incidentId ?? ""))}/reject`;
      payload = {
        version: Number(body.version ?? 1),
        reason: String(body.reason ?? ""),
      };
      actor = "coordinator";
      break;
    case "createAssignment":
      targetPath = "/integration/v1/demo/assignments";
      payload = {
        incident_id: String(body.incidentId ?? ""),
        resource_id: String(body.resourceId ?? ""),
      };
      actor = "coordinator";
      break;
    case "translate":
      targetPath = "/integration/v1/demo/translate";
      payload = {
        id: String(body.id ?? ""),
        originalText: String(body.originalText ?? ""),
        originalLanguage: String(body.originalLanguage ?? "en"),
        targetLanguage: String(body.targetLanguage ?? "en"),
        receivedAt: String(body.receivedAt ?? ""),
      };
      actor = "coordinator";
      break;
    default:
      return NextResponse.json(
        { ok: false, errorCode: "error.api", detail: `Unsupported action '${action}'.` },
        { status: 400, headers: NO_STORE }
      );
  }

  const keyToUse = actor === "coordinator" ? cfg.coordinatorKey : cfg.automationKey;

  try {
    const response = await fetch(`${cfg.baseUrl}${targetPath}`, {
      method: "POST",
      cache: "no-store",
      headers: buildHeaders(keyToUse, actor),
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(6000),
    });
    const responseBody = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    if (!response.ok) {
      return NextResponse.json(
        {
          ok: false,
          errorCode: mapBackendErrorCode(response.status, responseBody),
          detail:
            typeof responseBody.detail === "string"
              ? responseBody.detail
              : "Backend request failed.",
        },
        { status: response.status, headers: NO_STORE }
      );
    }
    return NextResponse.json({ ok: true, data: responseBody }, { headers: NO_STORE });
  } catch {
    return NextResponse.json(
      {
        ok: false,
        errorCode: "error.api",
        detail: "FastAPI backend is unreachable at RELIEFMESH_BACKEND_URL.",
      },
      { status: 502, headers: NO_STORE }
    );
  }
}
