"use client";
import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { LayoutDashboard, MapPinned, Boxes, Activity, Radio, Languages, ChevronDown, Wifi, ShieldCheck, CircleHelp, AlertTriangle, RefreshCw } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { languages } from "@/lib/i18n/languages";
import type { Language } from "@/types";
import { useResponse, recoverSimulation } from "@/state/response-context";
import { Metrics } from "@/components/dashboard/metrics";
import { MapPanel } from "@/components/map/map-panel";
import { IncidentList } from "@/components/incidents/incident-list";
import { IncidentDetail } from "@/components/incidents/incident-detail";
import { ResourceView } from "@/components/resources/resource-view";
import { ActivityTimeline } from "@/components/timeline/activity-timeline";
import { DemoControls } from "@/components/demo/demo-controls";
import { StateMessage, Toast } from "@/components/common/ui";
const sections = [{ id: "overview", Icon: LayoutDashboard }, { id: "incidents", Icon: MapPinned }, { id: "resources", Icon: Boxes }, { id: "activity", Icon: Activity }] as const;
export function CommandCenter() {
  const [view, setView] = useState<string>("overview");
  const { data, error, loading, act, refresh, dataSource, switchDataSource } = useResponse(); const { t, language, setLanguage, storageError } = useI18n();
  const navigation = useRef<HTMLElement>(null); const [indicator,setIndicator] = useState({top:0,height:42});
  useLayoutEffect(() => { const root = navigation.current; if (!root) return; const measure = () => { const button = root.querySelector<HTMLElement>('[aria-current="page"]'); if (button) setIndicator({top:button.offsetTop,height:button.offsetHeight}); }; measure(); const observer = new ResizeObserver(measure); observer.observe(root); return () => observer.disconnect(); },[view,language]);
  return <div className="app-shell"><a className="skip-link" href="#command-main">{t("common.skip")}</a><aside className="sidebar"><a href="#command-main" className="brand" onClick={() => setView("overview")} aria-label="ReliefMesh"><span className="brand-mark"><i /><i /><i /><i /></span><span>relief<span>mesh</span><small>{t("app.title")}</small></span></a><div className="sidebar-section-label">{t("app.live")}</div><nav ref={navigation} aria-label={t("app.title")}><i className="nav-indicator" aria-hidden="true" style={{"--nav-top":`${indicator.top}px`,height:indicator.height} as CSSProperties} />{sections.map(({ id, Icon }) => <button className={view === id ? "nav-active" : ""} key={id} aria-label={t(`nav.${id}`)} onClick={() => setView(id)} aria-current={view === id ? "page" : undefined}><Icon size={18} /><span>{t(`nav.${id}`)}</span>{id === "incidents" && <b>{data?.metrics.activeIncidents ?? 0}</b>}</button>)}</nav><div className="sidebar-bottom"><div className="sector-card"><span className="sector-icon"><ShieldCheck size={21} /></span><strong>{dataSource === "backend" ? "PostgreSQL + AI (Opt-In)" : t("app.demo")}</strong><p>{t("app.demoNotice")}</p></div><div className="operator"><span>OC</span><div><strong>{t("source.coordinator")}</strong><small>{t("app.subtitle")}</small></div></div></div></aside>
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><span>ReliefMesh</span><span>/</span><strong>{t(`nav.${view}`)}</strong></div><div className="header-tools"><span className="live-pill"><Radio size={13} />{t("app.live")}</span><div className="language-control"><Languages size={16} /><label className="sr-only" htmlFor="language-select">{t("app.language")}</label><select id="language-select" value={language} onChange={e => setLanguage(e.target.value as Language)}>{languages.map(l => <option key={l.code} value={l.code} lang={l.code}>{l.label}</option>)}</select><ChevronDown size={13} /></div><span className="avatar" title={t("source.coordinator")}>OC</span></div></header>
      <main className={`command-main view-${view}`} id="command-main" tabIndex={-1}><div className="page-heading"><div><div className="eyebrow"><span />{dataSource === "backend" ? "PostgreSQL + FastAPI + AI" : t("app.demo")}<b>RM / 01</b></div><h1>{t(view === "overview" ? "app.title" : `nav.${view}`)}</h1><p>{t("app.subtitle")}</p></div><div className="operational-status"><span><Wifi size={14} />{t(data?.health.automation === "offline" ? "scenario.offline" : "app.operational")}</span><button onClick={() => refresh()} title={t("actions.retry")}><RefreshCw size={12} />{t("app.sync")} {data?.health.lastSync ? new Intl.DateTimeFormat(language, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(data.health.lastSync)) : "—"}</button></div></div>
        {storageError && <div className="warning-strip" role="status">{t("error.storage")}</div>}{data?.health.stale && <div className="warning-strip" role="status"><AlertTriangle size={16} />{t("notice.stale")}</div>}{data?.health.automation === "offline" && <div className="warning-strip" role="status"><Wifi size={16} />{t("notice.offline")}</div>}
        <Metrics /><DemoControls />
        {loading ? <StateMessage message="loading.incidents" kind="loading" /> : error ? <section className="panel"><StateMessage message={error} kind="error" action={<div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", justifyContent: "center" }}><button className="button primary" onClick={() => act(recoverSimulation)}>{t("actions.retry")}</button>{dataSource === "backend" && <button className="button secondary" onClick={() => switchDataSource("mock")}>Use Simulated Fallback</button>}</div>} /></section> : view === "resources" ? <ResourceView /> : view === "activity" ? <ActivityTimeline expanded /> : <div className="operations-layout"><div className="operations-main">{view === "overview" && <MapPanel />}<IncidentList expanded={view === "incidents"} /><ActivityTimeline /></div><IncidentDetail /></div>}
        <footer className="page-footer"><span><CircleHelp size={13} />{t("app.demoNotice")}</span><span>ReliefMesh <b>v0.1</b></span></footer>
      </main>
    </div><Toast />
  </div>;
}
