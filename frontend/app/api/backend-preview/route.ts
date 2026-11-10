import { NextResponse } from "next/server";

// Read-only integration preview. This endpoint does not replace the mock
// ReliefService or expose privileged coordinator credentials to the browser.
export const dynamic = "force-dynamic";

type IncidentPreview = {
  id: string; location: string; type: string; severity: string;
  status: string; operational_phase: string;
  priority_score: number | null; people_affected: number | null;
  latitude: number | null; longitude: number | null;
};
type ResourcePreview = {
  id: string; type: string; location: string; status: string;
  latitude: number | null; longitude: number | null;
  capacity: number | null;
};
const text = (v: unknown): v is string => typeof v === "string";
const numberOrNull = (v: unknown): v is number | null =>
  v === null || (typeof v === "number" && Number.isFinite(v));
const record = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const phases = new Set([
  "received", "analyzing", "prioritized", "recommended",
  "awaiting_approval", "dispatched", "blocked", "replanning",
  "awaiting_replacement", "resolved", "rejected",
]);
const incidentStatuses = new Set(["UNASSIGNED", "ASSIGNED", "ACTIVE", "RESOLVED", "CANCELLED"]);
const resourceStatuses = new Set(["AVAILABLE", "DISPATCHED", "ACTIVE", "UNAVAILABLE"]);
const severities = new Set(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);

function incident(v: unknown): v is IncidentPreview {
  return record(v) && text(v.id) && text(v.location) && text(v.type) &&
    severities.has(String(v.severity)) && incidentStatuses.has(String(v.status)) &&
    phases.has(String(v.operational_phase)) && numberOrNull(v.priority_score) &&
    numberOrNull(v.people_affected) && numberOrNull(v.latitude) &&
    numberOrNull(v.longitude);
}
function resource(v: unknown): v is ResourcePreview {
  return record(v) && text(v.id) && text(v.location) && text(v.type) &&
    resourceStatuses.has(String(v.status)) && numberOrNull(v.latitude) &&
    numberOrNull(v.longitude) && numberOrNull(v.capacity);
}
function origin(): string | null {
  const configured = process.env.RELIEFMESH_BACKEND_URL;
  if (!configured) return null;
  try {
    const u = new URL(configured);
    if (u.username || u.password || u.search || u.hash || u.pathname !== "/") return null;
    if (u.protocol !== "https:" && !(u.protocol === "http:" &&
      ["localhost", "127.0.0.1", "::1", "[::1]"].includes(u.hostname))) return null;
    return u.origin;
  } catch { return null; }
}
async function read(origin: string, path: string): Promise<unknown> {
  const key = process.env.RELIEFMESH_BACKEND_READ_KEY;
  const response = await fetch(origin + path, {
    headers: key ? { "X-API-Key": key } : {},
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error("backend_unavailable");
  const body = await response.text();
  if (body.length > 2_000_000) throw new Error("response_too_large");
  return JSON.parse(body) as unknown;
}
export async function GET() {
  // This preview must be explicitly enabled; avoid exposing incident/resource
  // details on a publicly deployed frontend by default.
  if (process.env.RELIEFMESH_ENABLE_READ_PREVIEW !== "true") {
    return NextResponse.json({ error: "preview_disabled" }, { status: 404 });
  }
  const base = origin();
  if (!base) return NextResponse.json({ error: "backend_not_configured" }, { status: 503 });
  try {
    const [rawIncidents, rawResources] = await Promise.all([
      read(base, "/incidents?limit=100"), read(base, "/resources?limit=100"),
    ]);
    if (!Array.isArray(rawIncidents) || !rawIncidents.every(incident) ||
        !Array.isArray(rawResources) || !rawResources.every(resource)) {
      return NextResponse.json({ error: "contract_mismatch" }, { status: 502 });
    }
    // Explicitly return a limited projection; no raw reports, keys, or audit data.
    return NextResponse.json({
      mode: "read_only_preview",
      incidents: rawIncidents.map(i => ({
        id: i.id, location: i.location, type: i.type, severity: i.severity,
        status: i.status, operational_phase: i.operational_phase,
        priority_score: i.priority_score, people_affected: i.people_affected,
        latitude: i.latitude, longitude: i.longitude,
      })),
      resources: rawResources.map(r => ({
        id: r.id, location: r.location, type: r.type, status: r.status,
        capacity: r.capacity, latitude: r.latitude, longitude: r.longitude,
      })),
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
  }
}
