"use client";
import { useEffect, useRef, useState } from "react";
import { Activity, Check, AlertTriangle, UserRound, Sparkles, ArrowRight } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { StateMessage } from "@/components/common/ui";
export function ActivityTimeline({ expanded = false, incidentId }: { expanded?: boolean; incidentId?: string }) {
  const { data, select } = useResponse(); const { t, language } = useI18n(); const [filter, setFilter] = useState("all");
  const seen = useRef<Set<string> | null>(null); const [fresh,setFresh] = useState<string[]>([]);
  useEffect(() => { if (!data) return; const ids = data.activity.map(e => `${e.id}-${e.timestamp}`); if (seen.current) setFresh(ids.filter(id => !seen.current!.has(id))); seen.current = new Set(ids); }, [data]);
  useEffect(() => { if (!fresh.length) return; const timer = setTimeout(() => setFresh([]),2400); return () => clearTimeout(timer); }, [fresh]);
  const events = [...(data?.activity ?? [])].reverse().filter(e => (!incidentId || e.incidentId === incidentId) && (filter === "all" || e.source === filter));
  return <section className={`panel timeline-panel ${expanded ? "expanded" : ""}`}><div className="panel-heading"><h2><Activity size={17} />{t("activity.title")} <span className="count">{events.length}</span></h2><span className="quiet-label">{t("activity.latest")}</span></div>{expanded && <div className="list-toolbar"><select aria-label={t("activity.source")} value={filter} onChange={e => setFilter(e.target.value)}><option value="all">{t("activity.all")}</option>{["intake","ai","coordinator","automation"].map(s => <option value={s} key={s}>{t(`source.${s}`)}</option>)}</select></div>}
    {events.length === 0 ? <StateMessage message="empty.activity" /> : <ol className="timeline-list">{events.slice(0, expanded ? 200 : 6).map(e => {
      const Icon = e.type === "road_block_detected" ? AlertTriangle : ["incident_resolved","approved","replacement_approved","resource_dispatched","redispatched"].includes(e.type) ? Check : e.source === "coordinator" ? UserRound : e.source === "ai" ? Sparkles : Activity;
      return <li key={e.id} className={`timeline-event event-${e.source} event-${e.type} ${fresh.includes(`${e.id}-${e.timestamp}`) ? "event-new" : ""}`}><time dateTime={e.timestamp}>{new Intl.DateTimeFormat(language, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(e.timestamp))}</time><span className="event-icon"><Icon size={14} /></span><div className="event-content"><div><strong>{t(e.title)}</strong>{fresh.includes(`${e.id}-${e.timestamp}`) && <small className="new-event-label">{t("activity.new")}</small>}<span className="event-source">{t(`source.${e.source}`)}</span></div><p><button className="text-link" onClick={() => select(e.incidentId)} dir="ltr">{e.incidentId}</button>{e.metadata?.resources && <span dir="ltr">{e.metadata.resources}</span>}{e.metadata?.eta && <span>{t("resources.eta")}: {e.metadata.old && <>{e.metadata.old} <ArrowRight size={11} /> </>}{e.metadata.eta} {t("resources.minutes")}</span>}{e.metadata?.count && <span>{t("incident.duplicates")}: {e.metadata.count}</span>}{e.metadata?.priority && <span>{t("incident.priority")}: {e.metadata.priority}</span>}{e.metadata?.people && <span>{t("incident.people")}: {e.metadata.people}</span>}{e.metadata?.reason && <span dir="auto">{e.metadata.reason}</span>}</p></div></li>;
    })}</ol>}
  </section>;
}
