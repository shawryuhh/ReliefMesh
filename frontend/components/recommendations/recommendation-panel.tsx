"use client";
import { Check, Sparkles, ShieldCheck, ChevronDown, ArrowRight, Route, AlertTriangle } from "lucide-react";
import type { Incident, Recommendation } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { StateMessage, resourceIcons } from "@/components/common/ui";
import { RouteFeedback } from "./route-feedback";
export function RecommendationPanel({ incident, plan }: { incident: Incident; plan?: Recommendation }) {
  const { data } = useResponse(); const { t } = useI18n();
  return <section className="recommendation-section"><div className="detail-step"><span>03</span><h3>{t("plan.title")}</h3><Sparkles size={16} /></div>
    <RouteFeedback incident={incident} plan={plan} />
    {["analyzing","prioritized","replanning"].includes(incident.status) ? <StateMessage kind="loading" message={incident.status === "replanning" ? "status.replanning" : "loading.recommendation"} /> : !plan ? <StateMessage message="plan.none" /> : <>
      <div className="plan-caption"><span><Sparkles size={12} />{t("plan.mock")}</span><b>{Math.round(plan.confidence * 100)}% {t("incident.confidence")}</b></div>
      {plan.replacementFor && <div className="replacement-banner"><AlertTriangle size={17} /><div><strong>{t("plan.replacementReason")}</strong><p><b dir="ltr">{plan.replacementFor}</b><ArrowRight size={14} /><b dir="ltr">{plan.recommended_resources.find(id => id.startsWith("AMB"))}</b></p></div></div>}
      <p className="plan-reason">{t(plan.reason)}</p>
      <div className="recommendation-resources">{plan.recommended_resources.map(id => { const r = data?.resources.find(r => r.id === id); if (!r) return null; const Icon = resourceIcons[r.type]; return <div className="recommended-resource" key={id}><span className={`resource-icon resource-${r.type}`}><Icon size={20} /></span><div><strong dir="ltr">{id}</strong><small>{t(`cap.${r.capabilities[0]}`)}</small></div><div className="eta"><strong>{r.eta ?? "—"}<small>{t("resources.minutes")}</small></strong><span>{t("resources.eta")}</span></div></div>; })}</div>
      <details className="explanation" open><summary><ShieldCheck size={15} />{t("plan.why")}<ChevronDown size={15} /></summary><ul>{plan.explanation.map((e, index) => <li key={index}><Check size={13} /><span>{e.params?.id && <b dir="ltr">{e.params.id} · </b>}{e.key === "explain.distance" ? <>{t("resources.distance")}: {e.params?.distance} {t("resources.km")}</> : e.key === "explain.available" ? t("status.available") : e.key === "explain.als" ? t("cap.advanced_life_support") : e.key === "explain.eta" ? <>{t("resources.eta")}: {e.params?.eta} {t("resources.minutes")}</> : e.key === "explain.water" ? t("cap.water_rescue") : e.key === "explain.priority" ? t("plan.noHigher") : e.key === "explain.continues" ? t("plan.continues") : e.key === "explain.blocked" ? <>{t("status.blocked")}: {e.params?.old} → {e.params?.eta} {t("resources.minutes")}</> : t("plan.modified")}</span></li>)}</ul></details>
      {plan.state === "approved" && incident.status === "dispatched" && <div className="dispatch-confirm"><Check size={16} />{t("status.dispatched")}</div>}
    </>}
  </section>;
}
