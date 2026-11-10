import { ServiceError, type DemoService, type ReliefService } from "../services/contracts.ts";
import type {
  Assignment,
  DashboardSnapshot,
  DemoStep,
  EmergencyReport,
  Language,
  Scenario,
} from "../../types/index.ts";

export function createBackendDemoService(
  fetchImpl: typeof fetch = fetch,
  endpoint = "/api/backend-demo"
): ReliefService & DemoService {
  const listeners = new Set<() => void>();
  const emit = () => {
    listeners.forEach(fn => fn());
  };

  async function fetchSnapshot(): Promise<DashboardSnapshot> {
    let response: Response;
    try {
      response = await fetchImpl(endpoint, {
        method: "GET",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
    } catch {
      throw new ServiceError("error.api");
    }

    const body = (await response.json().catch(() => ({}))) as {
      ok?: boolean;
      snapshot?: DashboardSnapshot;
      errorCode?: string;
    };
    if (!response.ok || !body.ok || !body.snapshot) {
      throw new ServiceError(body.errorCode || "error.api");
    }
    return structuredClone(body.snapshot);
  }

  async function postAction<T = DashboardSnapshot>(
    action: string,
    params: Record<string, unknown> = {}
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(endpoint, {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action, ...params }),
      });
    } catch {
      throw new ServiceError("error.api");
    }

    const body = (await response.json().catch(() => ({}))) as {
      ok?: boolean;
      data?: T;
      errorCode?: string;
    };
    if (!response.ok || !body.ok || body.data === undefined) {
      throw new ServiceError(body.errorCode || "error.api");
    }
    return body.data;
  }

  return {
    async getDashboard() {
      return fetchSnapshot();
    },
    async getIncidents() {
      const snap = await fetchSnapshot();
      return structuredClone(snap.incidents);
    },
    async getIncident(id: string) {
      const snap = await fetchSnapshot();
      return snap.incidents.find(i => i.id === id);
    },
    async getResources() {
      const snap = await fetchSnapshot();
      return structuredClone(snap.resources);
    },
    async getActivityLog() {
      const snap = await fetchSnapshot();
      return structuredClone(snap.activity);
    },
    async getRecommendation(incidentId: string) {
      const snap = await fetchSnapshot();
      return snap.recommendations.find(r => r.incident === incidentId);
    },
    async approveRecommendation(incidentId: string, version: number) {
      await postAction("approve", { incidentId, version });
      emit();
    },
    async modifyRecommendation(incidentId: string, resourceIds: string[], version: number) {
      await postAction("modify", { incidentId, resourceIds, version });
      emit();
    },
    async rejectRecommendation(incidentId: string, reason: string, version: number) {
      await postAction("reject", { incidentId, reason, version });
      emit();
    },
    async createAssignment(incidentId: string, resourceId: string) {
      const result = await postAction<Assignment>("createAssignment", {
        incidentId,
        resourceId,
      });
      emit();
      return result;
    },
    async translateReport(report: EmergencyReport, language: Language) {
      return postAction<EmergencyReport>("translate", {
        id: report.id,
        originalText: report.originalText,
        originalLanguage: report.originalLanguage,
        targetLanguage: language,
        receivedAt: report.receivedAt,
      });
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    async reset(forRun = false) {
      await postAction("reset", { forRun });
      emit();
    },
    async setScenario(scenario: Scenario) {
      await postAction("setScenario", { scenario });
      emit();
    },
    async step(step: DemoStep) {
      await postAction("step", { step });
      emit();
    },
  };
}
