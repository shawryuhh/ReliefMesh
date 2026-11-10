"use client";
import { useState } from "react";
import { Search, History, ArrowDownWideNarrow, ArrowUpRight, Users } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { SeverityBadge, StatusBadge, StateMessage } from "@/components/common/ui";
import { queueIncidents, type QueueFilter } from "@/lib/presentation/incident-queue";
export function IncidentList({ expanded = false }: { expanded?: boolean }) {
  const { data, selectedId, select, queueFilter: filter, setQueueFilter: setFilter } = useResponse(); const { t } = useI18n();
  const [query, setQuery] = useState("");
  const incidents = queueIncidents(data?.incidents ?? [],filter).filter(i => `${i.id} ${i.location} ${t(`type.${i.type}`)}`.toLowerCase().includes(query.toLowerCase()));

  return <section className={`panel incident-panel ${expanded ? "expanded" : ""}`} aria-labelledby="incident-queue-title">
    <div className="panel-heading"><h2 id="incident-queue-title">{t("incident.queue")} <span className="count">{incidents.length}</span></h2><span className="quiet-label"><ArrowDownWideNarrow size={15} />{t("incident.priority")}</span></div>
    <div className="list-toolbar"><label className="search-box"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t("incident.search")} aria-label={t("incident.search")} /></label><select aria-label={t("incident.status")} value={filter} onChange={e => setFilter(e.target.value as QueueFilter)}><option value="active">{t("queue.active")}</option><option value="history">{t("queue.history")}</option><option value="all">{t("incident.all")}</option><option value="critical">{t("severity.critical")}</option><option value="pending">{t("status.awaiting_approval")}</option></select></div>
    {data?.scenario === "loading" ? <StateMessage message="loading.incidents" kind="loading" /> : incidents.length === 0 ? <StateMessage message={filter === "active" && !query ? "queue.emptyActive" : "empty.incidents"} action={query || filter !== "active" ? <button className="button secondary" onClick={() => { setQuery(""); setFilter("active"); }}>{t("actions.clear")}</button> : undefined} /> : <div className="incident-scroll"><table className="incident-table"><thead><tr><th>{t("incident.location")}</th><th>{t("incident.severity")}</th><th>{t("incident.priority")}</th><th>{t("incident.status")}</th><th><Users size={15} aria-label={t("incident.people")} /></th></tr></thead><tbody>{incidents.map(i => <tr key={i.id} className={selectedId === i.id ? "selected-row" : ""}>
      <td><button className="incident-select" onClick={() => select(i.id)} aria-pressed={selectedId === i.id}><span className="incident-id" dir="ltr">{i.id}<ArrowUpRight size={12} /></span><strong>{i.location}</strong><small>{t(`type.${i.type}`)}</small></button></td><td>{["resolved","rejected"].includes(i.status) ? <span className="history-marker"><History size={13} />{t("history.readOnly")}</span> : <SeverityBadge severity={i.severity} />}</td><td><strong className={`priority-number ${i.priority >= 90 && !["resolved","rejected"].includes(i.status) ? "text-red" : ""}`}>{i.priority}</strong></td><td><StatusBadge status={i.status} /></td><td className="tabular">{i.people}</td>
    </tr>)}</tbody></table></div>}
  </section>;
}
