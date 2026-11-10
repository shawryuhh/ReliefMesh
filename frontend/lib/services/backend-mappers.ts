import type { Incident, Resource, Recommendation, Assignment } from "../../types/index.ts";

// Strict mapping helpers for a future live adapter. No requests or writes.
export class ContractMismatch extends Error {
  constructor(field: string) { super("Backend contract mismatch: " + field); this.name = "ContractMismatch"; }
}
type Json = Record<string, unknown>;
function object(value: unknown, field: string): Json {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ContractMismatch(field);
  return value as Json;
}
function str(value: unknown, field: string): string {
  if (typeof value !== "string" || !value) throw new ContractMismatch(field);
  return value;
}
function num(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new ContractMismatch(field);
  return value;
}
function strings(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || !value.every(x => typeof x === "string")) throw new ContractMismatch(field);
  return value;
}
function optionalNum(value: unknown, field: string): number | undefined {
  return value == null ? undefined : num(value, field);
}
function oneOf<T extends string>(value: unknown, options: readonly T[], field: string): T {
  if (typeof value !== "string" || !options.includes(value as T)) throw new ContractMismatch(field);
  return value as T;
}
const incidentTypes = ["flood","medical","evacuation","landslide","supplies"] as const;
const resourceTypes = ["ambulance","rescue","hospital","shelter"] as const;
const phases = ["received","analyzing","prioritized","recommended","awaiting_approval","dispatched","blocked","replanning","awaiting_replacement","resolved","rejected"] as const;
function severityValue(value: unknown): number {
  const levels: Record<string, number> = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };
  if (typeof value !== "string" || !(value in levels)) throw new ContractMismatch("incident.severity");
  return levels[value];
}
const resourceStates = ["AVAILABLE","DISPATCHED","ACTIVE","UNAVAILABLE"] as const;

export function mapIncident(value: unknown): Incident {
  const v = object(value,"incident");
  // The current backend incident response does not include immutable reports,
  // vulnerabilities or duplicate count. Never synthesize these as real values.
  if (!Array.isArray(v.reports) || !Array.isArray(v.vulnerabilities) || typeof v.duplicates !== "number")
    throw new ContractMismatch("incident reports/vulnerabilities/duplicates not supplied");
  const reports = v.reports as Incident["reports"];
  if (!reports.every(r => r && typeof r.id === "string" && typeof r.originalText === "string" &&
    typeof r.originalLanguage === "string" && typeof r.receivedAt === "string"))
    throw new ContractMismatch("incident.reports");
  return {
    id:str(v.id,"incident.id"),location:str(v.location,"incident.location"),
    latitude:num(v.latitude,"incident.latitude"),longitude:num(v.longitude,"incident.longitude"),
    type:oneOf(v.type,incidentTypes,"incident.type"),
    severity:severityValue(v.severity),priority:num(v.priority_score,"incident.priority_score"),
    people:num(v.people_affected,"incident.people_affected"),
    needs:strings(v.needs,"incident.needs"),confidence:num(v.confidence,"incident.confidence"),
    status:oneOf(v.operational_phase,phases,"incident.operational_phase"),
    vulnerabilities:strings(v.vulnerabilities,"incident.vulnerabilities"),
    reports,duplicates:num(v.duplicates,"incident.duplicates"),
  };
}
export function mapResource(value: unknown): Resource {
  const v=object(value,"resource");
  const status=oneOf(v.status,resourceStates,"resource.status");
  return {
    id:str(v.id,"resource.id"),type:oneOf(v.type,resourceTypes,"resource.type"),
    latitude:num(v.latitude,"resource.latitude"),longitude:num(v.longitude,"resource.longitude"),
    capabilities:strings(v.capabilities,"resource.capabilities"),
    capacity:num(v.capacity,"resource.capacity"),
    status:({AVAILABLE:"available",DISPATCHED:"dispatched",ACTIVE:"active",UNAVAILABLE:"unavailable"} as const)[status],
    name:typeof v.name === "string" ? v.name : undefined,
    eta:optionalNum(v.eta_minutes,"resource.eta_minutes"),
    distanceKm:optionalNum(v.distance_km,"resource.distance_km"),
    assignedIncident:typeof v.assigned_incident === "string" ? v.assigned_incident : undefined,
  };
}
export function mapRecommendation(value: unknown): Recommendation {
  const v=object(value,"recommendation");
  const explanations=v.explanation;
  if (!Array.isArray(explanations) || !explanations.every(x => x && typeof x.key === "string" &&
    (x.params === undefined || (typeof x.params === "object" && x.params !== null && !Array.isArray(x.params) &&
    Object.values(x.params).every(p => typeof p === "string" || typeof p === "number")))))
    throw new ContractMismatch("recommendation.explanation");
  return {
    incident:str(v.incident,"recommendation.incident"),
    priority_score:num(v.priority_score,"recommendation.priority_score"),
    recommended_resources:strings(v.recommended_resources,"recommendation.recommended_resources"),
    reason:str(v.reason,"recommendation.reason"),
    approval_required:v.approval_required === true,
    confidence:num(v.confidence,"recommendation.confidence"),
    explanation:explanations as Recommendation["explanation"],
    version:num(v.version,"recommendation.version"),
    state:oneOf(v.state,["pending","approved","rejected"] as const,"recommendation.state"),
    replacementFor:typeof v.replacementFor === "string" ? v.replacementFor : undefined,
  };
}
export function mapAssignment(value: unknown): Assignment {
  const v=object(value,"assignment");
  const state=oneOf(v.status,["ASSIGNED","ACTIVE","COMPLETED","CANCELLED","SUPERSEDED"] as const,"assignment.status");
  return {
    id:str(v.id,"assignment.id"),incidentId:str(v.incident_id,"assignment.incident_id"),
    resourceId:str(v.resource_id,"assignment.resource_id"),
    approvedBy:str(v.approved_by,"assignment.approved_by"),
    createdAt:str(v.assigned_at,"assignment.assigned_at"),
    status:state==="COMPLETED"?"completed":state==="CANCELLED"||state==="SUPERSEDED"?"released":"dispatched",
  };
}
