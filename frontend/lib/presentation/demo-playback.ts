import { demoSteps, type DashboardSnapshot } from "../../types/index.ts";
// Scheduling eligibility only. Service validation still owns every transition.
export function nextAutomaticDemoStep(data: DashboardSnapshot | null, running: boolean) {
  if (!running || !data || data.scenario !== "normal" || data.demoIndex >= demoSteps.length || data.demoIndex < 0) return undefined;
  if (data.recommendations.some(plan => plan.incident === "INC-1042" && plan.state === "rejected")) return undefined;
  if (data.incidents.some(incident => incident.id === "INC-1042" && incident.status === "resolved")) return undefined;
  const step = demoSteps[data.demoIndex];
  return step === "approve" || step === "approveReplacement" ? undefined : step;
}
