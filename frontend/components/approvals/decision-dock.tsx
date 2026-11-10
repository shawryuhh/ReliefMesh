"use client";
import { useEffect, useRef, useState } from "react";
import { Check, ShieldCheck, ArrowRight, Radio, LoaderCircle } from "lucide-react";
import type { Incident, Recommendation } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { reliefService } from "@/lib/api";
import { incidentPresentation } from "@/lib/presentation/incident-state";
import { ApprovalModal } from "./approval-modal";
export function DecisionDock({ incident, plan }: { incident: Incident; plan?: Recommendation }) {
  const { data, act, busy } = useResponse(); const { t } = useI18n();
  const [modal,setModal] = useState<"modify" | "reject" | null>(null);
  const [approving,setApproving] = useState(false);
  const state = incidentPresentation(incident,plan);
  const dock = useRef<HTMLDivElement>(null); const returnFocus = useRef(false);
  useEffect(() => { if (!state.decision && returnFocus.current) { dock.current?.focus({ preventScroll: true }); returnFocus.current = false; } }, [state.decision]);
  const obstruction = data?.activity.findLast(e => e.incidentId === incident.id && e.type === "road_block_detected");
  const ambulance = data?.resources.find(r => r.type === "ambulance" && plan?.recommended_resources.includes(r.id));
  const responders = data?.resources.filter(r => r.assignedIncident === incident.id) ?? [];
  const released = data?.assignments.filter(a => a.incidentId === incident.id && a.status === "released").map(a => a.resourceId) ?? [];
  const approve = async () => {
    if (!plan) return;
    returnFocus.current = true; setApproving(true);
    try { const ok = await act(() => reliefService.approveRecommendation(incident.id,plan.version),"notice.approved"); if (!ok) returnFocus.current = false; }
    finally { setApproving(false); }
  };
  return <div className={`decision-dock dock-${state.emphasis}`} ref={dock} tabIndex={-1} role="region" aria-label={t("story.decision")}>
    {state.decision && plan ? <>
      <div className="dock-label"><ShieldCheck size={16} /><strong>{t(plan.replacementFor ? "decision.replacement" : "decision.initial")}</strong></div>
      {plan.replacementFor && ambulance ? <div className="dock-replacement" dir="ltr" key={plan.version}>
        <div className="dock-previous"><span>{t("route.previous")}</span><b>{plan.replacementFor}</b><small>{t("resources.eta")}: <s>{obstruction?.metadata?.old ?? "—"}</s> → <strong>{obstruction?.metadata?.eta ?? "—"}</strong> {t("resources.minutes")}</small></div>
        <ArrowRight size={18} aria-hidden="true" />
        <div className="dock-updated"><span>{t("route.updated")}</span><b>{ambulance.id}</b><small>{t("resources.eta")}: <strong>{ambulance.eta ?? "—"}</strong> {t("resources.minutes")}</small></div>
      </div> : <div className="dock-plan" dir="ltr">{plan.recommended_resources.join(" + ")}</div>}
      <p className="dock-facts">{t("incident.priority")} <b>{incident.priority}</b><span>·</span>{t("incident.confidence")} <b>{Math.round(plan.confidence*100)}%</b>{plan.replacementFor && <><span>·</span><b dir="ltr">{plan.recommended_resources.filter(id => id !== ambulance?.id).join(" + ")}</b></>}</p>
      <button className="button approve-button" onClick={approve} disabled={busy || data?.health.automation === "offline" || data?.scenario === "empty_resources"} aria-busy={approving}>{approving ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />}{t(approving ? "decision.processing" : plan.replacementFor ? "demo.approveReplacement" : "actions.approve")}</button>
      <div className="approval-secondary"><button className="button secondary" onClick={() => setModal("modify")} disabled={busy}>{t("actions.modify")}</button><button className="button reject-button" onClick={() => setModal("reject")} disabled={busy}>{t("actions.reject")}</button></div>
    </> : <div className="dock-followup" key={`${incident.status}-${plan?.version}`} role="status" aria-atomic="true">
      {incident.status === "dispatched" || incident.status === "resolved" ? <Check size={20} /> : <Radio size={20} />}
      <div><strong>{t(incident.status === "dispatched" ? plan?.replacementFor ? "decision.replacementApproved" : "decision.approved" : state.next)}</strong>
        {obstruction && ["blocked","replanning"].includes(incident.status) && <p className="dock-eta"><b dir="ltr">{obstruction.metadata?.resources}</b> · {t("resources.eta")}: <s>{obstruction.metadata?.old}</s> → <strong className="disrupted-eta">{obstruction.metadata?.eta} {t("resources.minutes")}</strong></p>}
        {responders.length > 0 && <p>{t("decision.responders")}: <b dir="ltr">{responders.map(r => r.id).join(" + ")}</b></p>}
        {released.length > 0 && <p>{t("decision.released")}: <b dir="ltr">{[...new Set(released)].join(", ")}</b></p>}
      </div>
    </div>}
    {modal && plan && <ApprovalModal mode={modal} plan={plan} close={() => setModal(null)} />}
  </div>;
}
