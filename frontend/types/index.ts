export type Language = "en" | "hi" | "kn" | "ta" | "te" | "ml" | "mr" | "bn" | "gu" | "pa" | "ur" | "as" | "or";
export type IncidentStatus = "received" | "analyzing" | "prioritized" | "recommended" | "awaiting_approval" | "dispatched" | "blocked" | "replanning" | "awaiting_replacement" | "resolved" | "rejected";
export type ResourceType = "ambulance" | "rescue" | "hospital" | "shelter";
export type ResourceStatus = "available" | "recommended" | "dispatched" | "active" | "busy" | "unavailable";
export type IncidentType = "flood" | "medical" | "evacuation" | "landslide" | "supplies";
export interface EmergencyReport {
  id: string; originalText: string; originalLanguage: Language;
  translatedText?: string; translatedLanguage?: Language; receivedAt: string;
}
export interface Incident {
  id: string; location: string; latitude: number; longitude: number;
  type: IncidentType; severity: number; priority: number; people: number;
  needs: string[]; confidence: number; status: IncidentStatus;
  vulnerabilities: string[]; reports: EmergencyReport[]; duplicates: number;
}
export interface Resource {
  id: string; name?: string; type: ResourceType; latitude: number; longitude: number;
  capabilities: string[]; status: ResourceStatus; capacity: number;
  assignedIncident?: string; eta?: number; distanceKm?: number;
}
export interface RecommendationExplanation { key: string; params?: Record<string, string | number> }
export interface Recommendation {
  incident: string; priority_score: number; recommended_resources: string[];
  reason: string; approval_required: boolean; confidence: number;
  explanation: RecommendationExplanation[]; version: number; replacementFor?: string;
  state: "pending" | "approved" | "rejected";
}
export interface Assignment {
  id: string; incidentId: string; resourceId: string; approvedBy: string;
  createdAt: string; status: "dispatched" | "released" | "completed";
}
export const eventTypes = ["incident_received", "duplicates_merged", "priority_updated", "recommendation_generated", "approval_requested", "approved", "modified", "rejected", "resource_dispatched", "road_block_detected", "replanning_started", "replacement_recommended", "replacement_approved", "redispatched", "incident_resolved"] as const;
export type EventType = typeof eventTypes[number];
export interface ActivityEvent {
  id: string; timestamp: string; source: "intake" | "ai" | "coordinator" | "automation";
  type: EventType; title: string; description: string; incidentId: string;
  metadata?: Record<string, string | number>;
}
export interface DashboardMetrics { criticalIncidents: number; activeIncidents: number; availableAmbulances: number; availableRescueTeams: number }
export interface ServiceHealth { mode: "mock" | "backend"; automation: "simulated" | "n8n" | "offline"; lastSync: string; stale: boolean }
export type DemoStep = "receive" | "merge" | "priority" | "recommend" | "request" | "approve" | "block" | "replan" | "replace" | "approveReplacement" | "resolve";
export const demoSteps: DemoStep[] = ["receive", "merge", "priority", "recommend", "request", "approve", "block", "replan", "replace", "approveReplacement", "resolve"];
export type Scenario = "normal" | "api_failure" | "empty_incidents" | "empty_resources" | "offline" | "stale" | "loading";
export interface DashboardSnapshot {
  incidents: Incident[]; resources: Resource[]; recommendations: Recommendation[];
  assignments: Assignment[]; activity: ActivityEvent[]; metrics: DashboardMetrics;
  health: ServiceHealth; demoIndex: number; scenario: Scenario;
}
