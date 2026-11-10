import { canonicalIncident, canonicalRecommendation, seedSnapshot } from "./data.ts";
import { ServiceError, type DemoService, type ReliefService } from "../services/contracts.ts";
import { demoSteps, type ActivityEvent, type Assignment, type DashboardSnapshot, type DemoStep, type EventType, type Scenario } from "../../types/index.ts";
import { translateMockReport } from "./translations.ts";

export function createMockService(): ReliefService & DemoService {
  let state = seedSnapshot();
  let serial = 0;
  const listeners = new Set<() => void>();
  const now = () => new Date().toISOString();
  const emit = () => { state.health.lastSync = now(); listeners.forEach(fn => fn()); };
  const requireOperational = () => {
    if (state.scenario === "api_failure" || state.scenario === "loading") throw new ServiceError("error.api");
    if (state.scenario === "empty_resources") throw new ServiceError("empty.resources");
    if (state.scenario === "empty_incidents") throw new ServiceError("empty.incidents");
    if (state.scenario === "offline") throw new ServiceError("notice.offline");
  };
  function addEvent(type: EventType, incidentId = "INC-1042", metadata: ActivityEvent["metadata"] = {}, source: ActivityEvent["source"] = "ai") {
    state.activity.push({ id: `EVT-${++serial}`, timestamp: now(), source, type, incidentId,
      title: `events.${type}`, description: `eventDescriptions.${type}`, metadata: { id: incidentId, ...metadata } });
  }
  function snapshot(): DashboardSnapshot {
    if (state.scenario === "api_failure") throw new ServiceError("error.api");
    const result = structuredClone(state);
    if (state.scenario === "empty_incidents") { result.incidents = []; result.recommendations = []; }
    if (state.scenario === "empty_resources") result.resources.forEach(r => { if (r.status === "available") r.status = "unavailable"; });
    const active = result.incidents.filter(i => !["resolved", "rejected"].includes(i.status));
    result.metrics = {
      criticalIncidents: active.filter(i => i.severity === 5).length,
      activeIncidents: active.length,
      availableAmbulances: result.resources.filter(r => r.type === "ambulance" && r.status === "available").length,
      availableRescueTeams: result.resources.filter(r => r.type === "rescue" && r.status === "available").length,
    };
    result.incidents.sort((a,b) => b.priority - a.priority);
    if (state.scenario === "stale") { result.health.stale = true; result.health.lastSync = new Date(Date.now() - 12 * 60000).toISOString(); }
    result.health.automation = state.scenario === "offline" ? "offline" : "simulated";
    return result;
  }
  function pending(id: string, version: number) {
    requireOperational();
    const incident = state.incidents.find(i => i.id === id);
    const plan = state.recommendations.find(r => r.incident === id);
    if (!incident || !plan || plan.state !== "pending" || plan.version !== version || !["awaiting_approval", "awaiting_replacement"].includes(incident.status)) throw new ServiceError("error.stalePlan");
    return { incident, plan };
  }
  function validateResources(ids: string[], incidentId: string) {
    if (!ids.length || new Set(ids).size !== ids.length) throw new ServiceError("error.resources");
    const resources = ids.map(id => state.resources.find(r => r.id === id));
    if (resources.some(r => !r || !["ambulance", "rescue"].includes(r.type) || !(r.status === "available" || (r.assignedIncident === incidentId && r.status === "dispatched")))) throw new ServiceError("error.resources");
    if (!resources.some(r => r?.type === "ambulance") || !resources.some(r => r?.capabilities.includes("water_rescue"))) throw new ServiceError("error.coverage");
  }
  function assign(incidentId: string, resourceId: string): Assignment {
    const resource = state.resources.find(r => r.id === resourceId);
    if (!resource) throw new ServiceError("error.resources");
    const existing = state.assignments.find(a => a.resourceId === resourceId && a.incidentId === incidentId && a.status === "dispatched");
    if (existing) return existing;
    if (resource.status !== "available") throw new ServiceError("error.resources");
    const assignment: Assignment = { id: `ASN-${++serial}`, incidentId, resourceId, approvedBy: "coordinator", createdAt: now(), status: "dispatched" };
    state.assignments.push(assignment);
    resource.status = "dispatched"; resource.assignedIncident = incidentId;
    addEvent("resource_dispatched", incidentId, { resources: resourceId, eta: resource.eta ?? 0 }, "automation");
    return assignment;
  }
  function approve(id: string, version: number) {
    const { incident, plan } = pending(id, version);
    validateResources(plan.recommended_resources, id);
    const replacement = Boolean(plan.replacementFor);
    addEvent(replacement ? "replacement_approved" : "approved", id, { resources: plan.recommended_resources.join(" + ") }, "coordinator");
    if (replacement) {
      // Only release responders removed from the approved plan. Keep water rescue on scene.
      state.resources.filter(r => r.assignedIncident === id && !plan.recommended_resources.includes(r.id)).forEach(r => {
        r.status = "available"; delete r.assignedIncident;
        state.assignments.filter(a => a.resourceId === r.id && a.status === "dispatched").forEach(a => { a.status = "released"; });
      });
    }
    plan.recommended_resources.forEach(resourceId => assign(id, resourceId));
    plan.state = "approved"; plan.approval_required = false; incident.status = "dispatched";
    if (replacement) addEvent("redispatched", id, { resources: plan.recommended_resources.join(" + "), eta: 9 }, "automation");
    if (id === "INC-1042") state.demoIndex = replacement ? 10 : 6;
    emit();
  }
  const service: ReliefService & DemoService = {
    async getDashboard() { return snapshot(); },
    async getIncidents() { return snapshot().incidents; },
    async getIncident(id) { return snapshot().incidents.find(i => i.id === id); },
    async getResources() { return snapshot().resources; },
    async getActivityLog() { return snapshot().activity; },
    async getRecommendation(id) { return snapshot().recommendations.find(r => r.incident === id); },
    async approveRecommendation(id, version) { approve(id, version); },
    async modifyRecommendation(id, ids, version) {
      const { plan } = pending(id, version); validateResources(ids, id);
      if (plan.replacementFor && ids.includes(plan.replacementFor)) throw new ServiceError("error.resources");
      plan.recommended_resources = [...ids]; plan.version += 1; plan.reason = "plan.modified";
      plan.explanation = ids.map(resourceId => ({ key: "explain.selected", params: { id: resourceId } }));
      addEvent("modified", id, { resources: ids.join(" + ") }, "coordinator"); emit();
    },
    async rejectRecommendation(id, reason, version) {
      const { plan, incident } = pending(id, version); plan.state = "rejected"; plan.approval_required = false;
      incident.status = plan.replacementFor ? "blocked" : "rejected";
      addEvent("rejected", id, { reason: reason.trim().slice(0, 500) }, "coordinator"); emit();
    },
    async createAssignment(incidentId, resourceId) {
      requireOperational();
      const plan = state.recommendations.find(p => p.incident === incidentId && p.state === "approved");
      if (!plan?.recommended_resources.includes(resourceId) || state.incidents.find(i => i.id === incidentId)?.status !== "dispatched") throw new ServiceError("error.approval");
      const result = structuredClone(assign(incidentId, resourceId)); emit(); return result;
    },
    translateReport: translateMockReport,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    async reset(forRun = false) {
      state = seedSnapshot(); serial = 0;
      if (forRun) { state.incidents = state.incidents.filter(i => i.id !== "INC-1042"); state.recommendations = []; state.activity = []; state.demoIndex = 0; }
      emit();
    },
    async setScenario(scenario: Scenario) { state.scenario = scenario; emit(); },
    async step(step: DemoStep) {
      requireOperational();
      if (demoSteps[state.demoIndex] !== step) throw new ServiceError("error.order");
      let incident = state.incidents.find(i => i.id === "INC-1042");
      if (step === "receive") {
        if (incident) throw new ServiceError("error.order"); // Canonical ID must be unique, even if a caller repeats intake.
        incident = canonicalIncident(now()); incident.status = "analyzing"; incident.priority = 0; incident.duplicates = 0;
        state.incidents.push(incident); addEvent("incident_received", incident.id, {}, "intake");
      }
      if (!incident) throw new ServiceError("empty.incidents");
      const plan = state.recommendations.find(r => r.incident === incident.id);
      switch (step) {
        case "merge": incident.duplicates = 2; addEvent("duplicates_merged", incident.id, { count: 2 }, "intake"); break;
        case "priority": incident.priority = 94; incident.status = "prioritized"; addEvent("priority_updated", incident.id, { priority: 94 }); break;
        case "recommend": state.recommendations.push(canonicalRecommendation()); incident.status = "recommended"; addEvent("recommendation_generated", incident.id, { resources: "AMB-02 + RESCUE-01" }); break;
        case "request": incident.status = "awaiting_approval"; addEvent("approval_requested"); break;
        case "approve": if (!plan) throw new ServiceError("error.stalePlan"); approve(incident.id, plan.version); return;
        case "block": {
          const ambulance = state.resources.find(r => r.assignedIncident === incident.id && r.type === "ambulance");
          if (!ambulance || ambulance.id !== "AMB-02") throw new ServiceError("error.canonical");
          ambulance.eta = 24; incident.status = "blocked"; addEvent("road_block_detected", incident.id, { resources: "AMB-02", old: 6, eta: 24 }, "automation"); break;
        }
        case "replan": incident.status = "replanning"; addEvent("replanning_started"); break;
        case "replace": {
          const replacement = canonicalRecommendation(true);
          replacement.version = (plan?.version ?? 0) + 1;
          state.recommendations = state.recommendations.filter(r => r.incident !== incident.id);
          state.recommendations.push(replacement); incident.status = "awaiting_replacement";
          addEvent("replacement_recommended", incident.id, { resources: "AMB-05", eta: 9 }); addEvent("approval_requested"); break;
        }
        case "approveReplacement": if (!plan) throw new ServiceError("error.stalePlan"); approve(incident.id, plan.version); return;
        case "resolve":
          incident.status = "resolved";
          state.resources.filter(r => r.assignedIncident === incident.id).forEach(r => { r.status = "available"; delete r.assignedIncident; });
          state.assignments.filter(a => a.incidentId === incident.id && a.status === "dispatched").forEach(a => { a.status = "completed"; });
          addEvent("incident_resolved", incident.id, { people: 3 }, "coordinator"); break;
      }
      state.demoIndex += 1; emit();
    },
  };
  return service;
}
