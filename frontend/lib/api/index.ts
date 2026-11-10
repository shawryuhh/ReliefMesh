import { createMockService } from "../mocks/service.ts";
import { createBackendDemoService } from "./backend-demo-service.ts";
import type { DemoService, ReliefService } from "../services/contracts.ts";

export type DemoDataSource = "mock" | "backend";

const mockService = createMockService();
const backendDemoService = createBackendDemoService();

let activeSource: DemoDataSource =
  typeof process !== "undefined" &&
  process.env?.NEXT_PUBLIC_RELIEFMESH_DEMO_MODE === "backend"
    ? "backend"
    : "mock";

const listeners = new Set<() => void>();
const notify = () => {
  listeners.forEach(fn => fn());
};

mockService.subscribe(notify);
backendDemoService.subscribe(notify);

function current(): ReliefService & DemoService {
  return activeSource === "backend" ? backendDemoService : mockService;
}

export function getDemoDataSource(): DemoDataSource {
  return activeSource;
}

export function setDemoDataSource(nextSource: DemoDataSource): void {
  if (activeSource !== nextSource) {
    activeSource = nextSource;
    notify();
  }
}

export const reliefService: ReliefService & DemoService = {
  getDashboard: () => current().getDashboard(),
  getIncidents: () => current().getIncidents(),
  getIncident: id => current().getIncident(id),
  getResources: () => current().getResources(),
  getActivityLog: () => current().getActivityLog(),
  getRecommendation: incidentId => current().getRecommendation(incidentId),
  approveRecommendation: (incidentId, version) =>
    current().approveRecommendation(incidentId, version),
  modifyRecommendation: (incidentId, resourceIds, version) =>
    current().modifyRecommendation(incidentId, resourceIds, version),
  rejectRecommendation: (incidentId, reason, version) =>
    current().rejectRecommendation(incidentId, reason, version),
  createAssignment: (incidentId, resourceId) =>
    current().createAssignment(incidentId, resourceId),
  translateReport: (report, language) =>
    current().translateReport(report, language),
  subscribe(listener) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  reset: forRun => current().reset(forRun),
  setScenario: scenario => current().setScenario(scenario),
  step: step => current().step(step),
};

export const demoService = reliefService;

export * from "../services/contracts.ts";
export { createBackendDemoService } from "./backend-demo-service.ts";
