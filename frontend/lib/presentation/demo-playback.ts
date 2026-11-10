import { demoSteps, type DashboardSnapshot } from "../../types/index.ts";
// Scheduling eligibility only. Service validation still owns every transition.
export function nextAutomaticDemoStep(data: DashboardSnapshot | null, running: boolean) {
  if (!running || !data || data.scenario !== "normal" || data.demoIndex >= demoSteps.length || data.demoIndex < 0) return undefined;
  if (data.recommendations.some(plan => plan.incident === "INC-1042" && plan.state === "rejected")) return undefined;
  if (data.incidents.some(incident => incident.id === "INC-1042" && incident.status === "resolved")) return undefined;
  const step = demoSteps[data.demoIndex];
  return step === "approve" || step === "approveReplacement" ? undefined : step;
}

export function shouldResetOnDemoStart(data: DashboardSnapshot | null): boolean {
  if (!data) return true;
  if (data.demoIndex >= demoSteps.length || data.demoIndex < 0) return true;
  if (data.recommendations.some(plan => plan.incident === "INC-1042" && plan.state === "rejected")) return true;
  const incident = data.incidents.find(item => item.id === "INC-1042");
  if (incident && ["rejected", "resolved"].includes(incident.status)) return true;
  if (data.demoIndex === 5 && incident?.status === "awaiting_approval") return true;
  return false;
}
