"use client";
import { useState } from "react";
import type { ResourceType } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { StatusBadge, StateMessage, resourceIcons } from "@/components/common/ui";
export function ResourceView() {
  const { data } = useResponse(); const { t } = useI18n();
  const [filter, setFilter] = useState<ResourceType | "all">("all");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const rows = (data?.resources ?? []).filter(r => (filter === "all" || r.type === filter) && (!onlyAvailable || r.status === "available"));
  return <section className="panel resource-panel"><div className="panel-heading"><h2>{t("nav.resources")} <span className="count">{data?.resources.length}</span></h2><label className="check-label"><input type="checkbox" checked={onlyAvailable} onChange={e => setOnlyAvailable(e.target.checked)} />{t("status.available")}</label></div>
    <div className="resource-tabs" role="group" aria-label={t("incident.type")}>{(["all", "ambulance", "rescue", "hospital", "shelter"] as const).map(type => <button className={filter === type ? "active" : ""} aria-pressed={filter === type} key={type} onClick={() => setFilter(type)}>{t(type === "all" ? "incident.all" : `resources.${type}`)}</button>)}</div>
    {data?.scenario === "loading" ? <StateMessage message="loading.resources" kind="loading" /> : rows.length === 0 ? <StateMessage message="empty.resources" /> : <div className="resource-grid">{rows.map(r => { const Icon = resourceIcons[r.type]; const recommended = data?.recommendations.some(p => p.state === "pending" && p.recommended_resources.includes(r.id)); return <article className="resource-card" key={r.id}><div className="resource-top"><span className={`resource-icon resource-${r.type}`}><Icon size={21} /></span><div><strong dir="ltr">{r.id}</strong><small>{t(`resources.${r.type}`)}</small></div><StatusBadge status={r.status} /></div>{r.name && <h3>{r.name}</h3>}<div className="capability-list">{r.capabilities.map(c => <span key={c}>{t(`cap.${c}`)}</span>)}</div><dl className="resource-facts"><div><dt>{t("resources.capacity")}</dt><dd>{r.capacity}</dd></div><div><dt>{t("resources.eta")}</dt><dd>{r.eta ? `${r.eta} ${t("resources.minutes")}` : "—"}</dd></div></dl><div className="resource-footer">{r.assignedIncident ? <><span>{t("resources.assignment")}</span><b dir="ltr">{r.assignedIncident}</b></> : recommended ? <span className="text-blue">{t("status.recommended")}</span> : <span>{t("resources.assignment")}: {t("common.none")}</span>}</div></article>; })}</div>}
  </section>;
}
