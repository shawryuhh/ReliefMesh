"use client";
import { ArrowRight, Route, RefreshCw } from "lucide-react";
import type { Incident, Recommendation } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
export function RouteFeedback({ incident, plan }: { incident: Incident; plan?: Recommendation }) {
  const { data } = useResponse(); const { t } = useI18n();
  const event = data?.activity.findLast(e => e.incidentId === incident.id && e.type === "road_block_detected");
  if (!event || !["blocked","replanning","awaiting_replacement","dispatched"].includes(incident.status)) return null;
  const replacement = plan?.replacementFor && plan.state !== "rejected" ? data?.resources.find(r => r.type === "ambulance" && plan.recommended_resources.includes(r.id)) : undefined;
  return <div className={`route-feedback ${replacement ? "route-updated" : ""}`} key={`${incident.status}-${plan?.version}`}>
    <div className="route-title"><Route size={16} /><strong>{t("route.disruption")}</strong></div>
    <div className="route-comparison"><div><small>{t("route.previous")}</small><b dir="ltr">{event.metadata?.resources}</b><span>{t("resources.eta")}: <s>{event.metadata?.old}</s><ArrowRight size={13} /><strong>{event.metadata?.eta} {t("resources.minutes")}</strong></span></div>
      {replacement && <><ArrowRight size={18} className="directional-icon" /><div><small>{t("route.updated")}</small><b dir="ltr">{replacement.id}</b><span>{t("resources.eta")}: <strong>{replacement.eta} {t("resources.minutes")}</strong></span></div></>}
    </div>
    {incident.status === "replanning" && <p className="route-processing"><RefreshCw size={15} />{t("route.replanning")}</p>}
  </div>;
}
