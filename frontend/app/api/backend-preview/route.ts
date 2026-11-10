import { NextResponse } from "next/server";
import { previewAllowed } from "../../../lib/services/preview-access";
import { BackendReadError } from "../../../lib/services/backend-read-client";
import { fetchSnapshotPreview } from "../../../lib/services/snapshot-read-client";

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
function assignment(v: unknown): v is Record<string, unknown> {
  return record(v) && text(v.id) && text(v.incident_id) && text(v.resource_id) &&
    ["ASSIGNED","ACTIVE","COMPLETED","CANCELLED","SUPERSEDED"].includes(String(v.status)) &&
    text(v.assigned_at);
}
function recommendation(v: unknown): v is Record<string, unknown> {
  return record(v) && text(v.incident) && typeof v.version === "number" &&
    Number.isInteger(v.version) && v.version > 0 &&
    ["pending","approved","rejected"].includes(String(v.state)) &&
    Array.isArray(v.recommended_resources) && v.recommended_resources.every(text);
}
export async function GET(request: Request) {
  if (!previewAllowed(process.env.NODE_ENV, process.env.RELIEFMESH_ENABLE_READ_PREVIEW,
    request.headers.get("host"), request.headers.get("x-forwarded-host"))) {
    return NextResponse.json({ error: "local_preview_only" }, { status: 403 });
  }
  // This preview must be explicitly enabled; avoid exposing incident/resource
  // details on a publicly deployed frontend by default.
  if (process.env.RELIEFMESH_ENABLE_READ_PREVIEW !== "true") {
    return NextResponse.json({ error: "preview_disabled" }, { status: 404 });
  }
  try {
    const snapshot = await fetchSnapshotPreview();
    const rawIncidents = snapshot.incidents;
    const rawResources = snapshot.resources;
    const rawAssignments = snapshot.assignments;
    const recommendations = snapshot.recommendations;
    if (!rawIncidents.every(incident) || !rawResources.every(resource) ||
        !rawAssignments.every(assignment) || !recommendations.every(recommendation)) {
      return NextResponse.json({ error: "contract_mismatch" }, { status: 502 });
    }
    // Explicitly return a limited projection; no raw reports, keys, or audit data.
    return NextResponse.json({
      mode: "read_only_preview",
      generated_at: snapshot.generated_at,
      revision: snapshot.revision,
      incidents: rawIncidents.map(i => ({
        id: i.id, location: i.location, type: i.type, severity: i.severity,
        status: i.status, operational_phase: i.operational_phase,
        priority_score: i.priority_score, people_affected: i.people_affected,
        latitude: i.latitude, longitude: i.longitude,
      })),
      assignments: rawAssignments.map(a => ({
        id: a.id, incident_id: a.incident_id, resource_id: a.resource_id,
        status: a.status, assigned_at: a.assigned_at,
      })),
      recommendations: recommendations.filter(r => r !== null).map(r => ({
        incident: r.incident, version: r.version, state: r.state,
        recommended_resources: r.recommended_resources,
      })),
      resources: rawResources.map(r => ({
        id: r.id, location: r.location, type: r.type, status: r.status,
        capacity: r.capacity, latitude: r.latitude, longitude: r.longitude,
      })),
    }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof BackendReadError && error.code === "not_configured")
      return NextResponse.json({ error: "backend_not_configured" }, { status: 503 });
    return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
  }
}
