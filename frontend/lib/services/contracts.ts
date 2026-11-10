import type { DashboardSnapshot, Incident, Resource, ActivityEvent, Recommendation, Assignment, EmergencyReport, Language, DemoStep, Scenario } from "../../types/index.ts";

export class ServiceError extends Error {
  key: string;
  constructor(key: string) { super(key); this.name = "ServiceError"; this.key = key; }
}
export interface ReliefService {
  getDashboard(): Promise<DashboardSnapshot>;
  getIncidents(): Promise<Incident[]>;
  getIncident(id: string): Promise<Incident | undefined>;
  getResources(): Promise<Resource[]>;
  getActivityLog(): Promise<ActivityEvent[]>;
  getRecommendation(incidentId: string): Promise<Recommendation | undefined>;
  approveRecommendation(incidentId: string, version: number): Promise<void>;
  modifyRecommendation(incidentId: string, resourceIds: string[], version: number): Promise<void>;
  rejectRecommendation(incidentId: string, reason: string, version: number): Promise<void>;
  createAssignment(incidentId: string, resourceId: string): Promise<Assignment>;
  translateReport(report: EmergencyReport, language: Language): Promise<EmergencyReport>;
  subscribe(listener: () => void): () => void;
}
export interface DemoService {
  step(step: DemoStep): Promise<void>;
  reset(forRun?: boolean): Promise<void>;
  setScenario(scenario: Scenario): Promise<void>;
}
