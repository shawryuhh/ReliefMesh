"use client";
import { useEffect, useState } from "react";
import type { Recommendation } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { reliefService } from "@/lib/api";
import { Modal } from "@/components/common/modal";
import { resourceIcons, StatusBadge } from "@/components/common/ui";
export function ApprovalModal({ mode, plan, close }: { mode: "modify" | "reject"; plan: Recommendation; close: () => void }) {
  const { data, act, busy } = useResponse(); const { t } = useI18n();
  const [closing,setClosing] = useState(false);
  useEffect(() => { if (!closing) return; const timer = setTimeout(close,window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 170); return () => clearTimeout(timer); },[closing,close]);
  const requestClose = () => { if (!busy) setClosing(true); };
  const [selected, setSelected] = useState(plan.recommended_resources);
  const [reason, setReason] = useState("");
  const available = data?.resources.filter(r => ["ambulance","rescue"].includes(r.type) && r.id !== plan.replacementFor && (r.status === "available" || r.assignedIncident === plan.incident && r.status === "dispatched")) ?? [];
  const covered = available.some(r => selected.includes(r.id) && r.type === "ambulance") && available.some(r => selected.includes(r.id) && r.capabilities.includes("water_rescue"));
  const submit = async (e: React.FormEvent) => { e.preventDefault(); const ok = await act(() => mode === "modify" ? reliefService.modifyRecommendation(plan.incident, selected, plan.version) : reliefService.rejectRecommendation(plan.incident, reason, plan.version), mode === "modify" ? "notice.saved" : "notice.rejected"); if (ok) setClosing(true); };
  return <Modal title={`modal.${mode}`} close={requestClose} closing={closing} dismissDisabled={busy}><form onSubmit={submit}><p className="modal-intro">{t(mode === "modify" ? "modal.coverage" : "modal.rejectHelp")}</p>{mode === "modify" ? <div className="resource-options">{available.map(r => { const Icon = resourceIcons[r.type]; return <label className={`resource-option ${selected.includes(r.id) ? "checked" : ""}`} key={r.id}><input type="checkbox" disabled={busy || closing} checked={selected.includes(r.id)} onChange={e => setSelected(prev => e.target.checked ? [...prev,r.id] : prev.filter(id => id !== r.id))} /><Icon size={21} /><div><strong dir="ltr">{r.id}</strong><small>{r.capabilities.map(c => t(`cap.${c}`)).join(" · ")}</small></div><StatusBadge status={r.status} /></label>; })}</div> : <label className="reason-label">{t("modal.reason")}<textarea maxLength={500} rows={4} disabled={busy || closing} value={reason} onChange={e => setReason(e.target.value)} autoFocus /></label>}<div className="modal-footer"><button className="button secondary" type="button" onClick={requestClose} disabled={busy || closing}>{t("actions.cancel")}</button><button className={`button ${mode === "reject" ? "danger" : "primary"}`} disabled={busy || closing || mode === "modify" && !covered}>{t(mode === "modify" ? "actions.save" : "actions.confirmReject")}</button></div></form></Modal>;
}
