"use client";
import { AlertCircle, CheckCircle2, LoaderCircle, Inbox, X, Ambulance, LifeBuoy, Hospital, House, type LucideIcon } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import type { ResourceType } from "@/types";
import { useResponse } from "@/state/response-context";
import { useChangeFeedback } from "@/hooks/use-change-feedback";
export const resourceIcons: Record<ResourceType, LucideIcon> = { ambulance: Ambulance, rescue: LifeBuoy, hospital: Hospital, shelter: House };
export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n(); const changed = useChangeFeedback(status);
  return <span className={`badge status-${status} ${changed ? "status-changed" : ""}`}><span className="status-dot" />{t(`status.${status}`)}</span>;
}
export function SeverityBadge({ severity }: { severity: number }) {
  const { t } = useI18n(); const level = severity >= 5 ? "critical" : severity >= 4 ? "high" : "moderate";
  return <span className={`severity severity-${level}`}><span className="severity-bars" aria-hidden="true">{[1,2,3].map(n => <i key={n} />)}</span>{t(`severity.${level}`)}</span>;
}
export function StateMessage({ message, kind = "empty", action }: { message: string; kind?: "empty" | "loading" | "error"; action?: React.ReactNode }) {
  const { t } = useI18n(); const Icon = kind === "loading" ? LoaderCircle : kind === "error" ? AlertCircle : Inbox;
  return <div className={`state-message ${kind}`} role={kind === "error" ? "alert" : "status"}><Icon size={24} className={kind === "loading" ? "spin" : ""} /><p>{t(message)}</p>{action}</div>;
}
export function Toast() {
  const { notice, dismissNotice } = useResponse(); const { t } = useI18n();
  if (!notice) return null;
  const isError = notice.startsWith("error.") || notice.startsWith("empty.");
  return <div className={`toast ${isError ? "toast-error" : ""}`} role={isError ? "alert" : "status"}>{isError ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}<span>{t(notice)}</span><button className="icon-button" onClick={dismissNotice} aria-label={t("actions.close")}><X size={17} /></button></div>;
}
