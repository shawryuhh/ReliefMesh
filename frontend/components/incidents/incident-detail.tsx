"use client";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, MapPin, Languages, Users, ArrowDown, MessageSquareText, HeartHandshake } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { languages } from "@/lib/i18n/languages";
import { reliefService } from "@/lib/api";
import { ServiceError } from "@/lib/services/contracts";
import type { EmergencyReport } from "@/types";
import { SeverityBadge, StatusBadge, StateMessage } from "@/components/common/ui";
import { RecommendationPanel } from "@/components/recommendations/recommendation-panel";
import { DecisionDock } from "@/components/approvals/decision-dock";
import { ActivityTimeline } from "@/components/timeline/activity-timeline";
import { incidentPresentation } from "@/lib/presentation/incident-state";
import { useIncidentStory, storyStages } from "@/hooks/use-incident-story";
import { isActiveIncident } from "@/lib/presentation/incident-queue";
import { ResolutionSummary } from "./resolution-summary";
export function IncidentDetail() {
  const { data, selectedId, queueFilter } = useResponse(); const { t, language } = useI18n();
  const incident = data?.incidents.find(i => i.id === selectedId);
  const plan = data?.recommendations.find(r => r.incident === selectedId);
  const [translated, setTranslated] = useState<EmergencyReport | null>(null); const [translating, setTranslating] = useState(false); const [translationError, setTranslationError] = useState<string | null>(null);
  const request = useRef(0); const story = useIncidentStory(incident?.id);
  useEffect(() => { request.current++; setTranslated(null); setTranslationError(null); setTranslating(false); }, [selectedId, language]);
  if (!incident) return <aside className="panel detail-panel empty-operational">{queueFilter === "active" && !data?.incidents.some(isActiveIncident) ? <div className="state-message"><CheckCircle2 size={26} /><p>{t("queue.emptyActive")}</p></div> : <StateMessage message="empty.selection" />}</aside>;
  const historical = !isActiveIncident(incident);
  const report = incident.reports[0];
  const translation = translated?.id === report.id && translated.translatedLanguage === language ? translated : report.translatedLanguage === language ? report : null;
  const translate = async () => { const token = ++request.current; setTranslating(true); setTranslationError(null); try { const result = await reliefService.translateReport(report, language); if (token === request.current) setTranslated(result); } catch (err) { if (token === request.current) setTranslationError(err instanceof ServiceError ? err.key : "error.translation"); } finally { if (token === request.current) setTranslating(false); } };
  const presentation = incidentPresentation(incident, plan);
  return <aside className={`panel detail-panel ${historical ? "detail-history" : ""}`} aria-label={`${selectedId} ${t("incident.structured")}`}><div className="detail-header"><div className="detail-status-row"><span className="incident-id" dir="ltr">{incident.id}</span><StatusBadge status={incident.status} />{historical ? <span className="history-marker">{t("history.readOnly")}</span> : <SeverityBadge severity={incident.severity} />}</div><h2>{incident.location}</h2><p><MapPin size={13} />{incident.latitude.toFixed(4)}, {incident.longitude.toFixed(4)}<span>·</span>{t(`type.${incident.type}`)}</p><div className={`next-action next-${presentation.emphasis}`} aria-live="polite"><small>{t(historical ? "history.readOnly" : "next.label")}</small><strong>{t(presentation.next)}</strong></div></div>
    <nav className="story-nav" aria-label={t("story.navigation")}>{storyStages.map((stage,index) => <button key={stage} aria-current={story.active === stage ? "step" : undefined} onClick={() => story.go(stage)}><span>0{index+1}</span>{t(`story.${stage}`)}</button>)}</nav>
    <div className="detail-scroll" ref={story.scroll} tabIndex={0} role="region" aria-label={t("incident.structured")}>
    <section data-stage="report" className={`report-section story-section ${story.active === "report" ? "stage-current" : ""}`}><div className="detail-step"><span>01</span><h3>{t("incident.original")}</h3><MessageSquareText size={16} /></div><blockquote lang={report.originalLanguage} dir={report.originalLanguage === "ur" ? "rtl" : "auto"}>{report.originalText}</blockquote><div className="report-meta"><span>{t("incident.detected")}: {languages.find(l => l.code === report.originalLanguage)?.label}</span><span>{t("incident.duplicates")}: {incident.duplicates}</span></div>{report.originalLanguage !== language && <button className="translate-button" onClick={translate} disabled={translating}><Languages size={14} />{t(translating ? "loading.translation" : "actions.translate")}</button>}{translation?.translatedText && <div className="translated-report"><small>{t("incident.translation")} · {languages.find(l => l.code === translation.translatedLanguage)?.label}</small><p lang={translation.translatedLanguage} dir={translation.translatedLanguage === "ur" ? "rtl" : "auto"}>{translation.translatedText}</p></div>}{translationError && <p className="inline-error" role="alert">{t(translationError)}</p>}</section>
    <div className="detail-connector"><ArrowDown size={13} /></div>
    <section data-stage="details" className={`structured-section story-section ${story.active === "details" ? "stage-current" : ""}`}><div className="detail-step"><span>02</span><h3>{t("incident.structured")}</h3><Users size={16} /></div><dl className="incident-facts"><div><dt>{t("incident.priority")}</dt><dd className={incident.priority >= 90 && !historical ? "text-red" : ""}>{incident.priority}<small>/ 100</small></dd></div><div><dt>{t("incident.people")}</dt><dd>{incident.people}</dd></div><div><dt>{t("incident.severity")}</dt><dd>{incident.severity}<small>/ 5</small></dd></div><div><dt>{t("incident.confidence")}</dt><dd>{Math.round(incident.confidence * 100)}<small>%</small></dd></div></dl>{incident.vulnerabilities.length > 0 && <div className="vulnerability"><HeartHandshake size={16} /><div><small>{t("incident.vulnerabilities")}</small>{incident.vulnerabilities.map(v => <strong key={v}>{t(`cap.${v}`)}</strong>)}</div></div>}<div className="needs"><span>{t("incident.needs")}</span>{incident.needs.map(n => <b key={n}>{t(`cap.${n}`)}</b>)}</div></section>
    <div className="detail-connector"><ArrowDown size={13} /></div><div data-stage="recommendation" className={`story-section ${story.active === "recommendation" ? "stage-current" : ""}`}><RecommendationPanel key={`${incident.id}-${plan?.version}`} incident={incident} plan={plan} /></div>
    <section data-stage="decision" className={`decision-story story-section ${story.active === "decision" ? "stage-current" : ""}`}><div className="detail-step"><span>04</span><h3>{t("story.decision")}</h3></div><p>{t(presentation.next)}</p><StatusBadge status={incident.status} /></section>
    <div data-stage="activity" className={`story-section ${story.active === "activity" ? "stage-current" : ""}`}><ActivityTimeline incidentId={incident.id} expanded={historical} /></div>
    </div>{incident.status === "resolved" ? <ResolutionSummary incident={incident} /> : <DecisionDock key={incident.id} incident={incident} plan={plan} />}
  </aside>;
}
