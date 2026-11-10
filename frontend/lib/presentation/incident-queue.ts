import type { Incident } from "../../types/index.ts";
export type QueueFilter = "active" | "pending" | "critical" | "history" | "all";
export function isActiveIncident(incident: Incident) {
  return incident.status !== "resolved" && incident.status !== "rejected";
}
export function matchesQueue(incident: Incident, filter: QueueFilter) {
  if (filter === "all") return true;
  if (filter === "history") return !isActiveIncident(incident);
  if (!isActiveIncident(incident)) return false;
  if (filter === "pending") return ["awaiting_approval", "awaiting_replacement"].includes(incident.status);
  return filter !== "critical" || incident.severity === 5;
}
export function queueIncidents(incidents: Incident[], filter: QueueFilter) {
  return incidents.filter(incident => matchesQueue(incident, filter)).sort((a,b) => b.priority-a.priority || a.id.localeCompare(b.id));
}
export function nextActiveIncidentId(incidents: Incident[]) {
  return queueIncidents(incidents,"active")[0]?.id ?? "";
}
