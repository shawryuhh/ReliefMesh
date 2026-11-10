import type { Incident, Recommendation } from "../../types/index.ts";
// Presentation only; domain mutations remain in the service adapter.
export function incidentPresentation(incident: Incident, plan?: Recommendation) {
  if (incident.status === "resolved") return { emphasis: "resolved", next: "next.resolved", decision: false };
  if (plan?.state === "rejected") return { emphasis: incident.status === "blocked" ? "disruption" : "review", next: "next.rejected", decision: false };
  const decision = plan?.state === "pending" && ["awaiting_approval","awaiting_replacement"].includes(incident.status);
  if (decision) return { emphasis: "decision", next: plan.replacementFor ? "next.replacement" : "next.approve", decision: true };
  switch (incident.status) {
    case "dispatched": return { emphasis: "monitor", next: "next.monitor", decision: false };
    case "blocked": return { emphasis: "disruption", next: "next.disruption", decision: false };
    case "replanning": return { emphasis: "replan", next: "next.replan", decision: false };
    case "recommended": return { emphasis: "recommendation", next: "next.recommendation", decision: false };
    case "rejected": return { emphasis: "review", next: "next.rejected", decision: false };
    default: return { emphasis: "review", next: "next.review", decision: false };
  }
}
