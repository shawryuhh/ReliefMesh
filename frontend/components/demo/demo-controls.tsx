"use client";
import { Play, Pause, RotateCcw, SlidersHorizontal, Check, ChevronRight, ShieldCheck } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { useResponse } from "@/state/response-context";
import { useDemo } from "@/hooks/use-demo";
import { demoService } from "@/lib/api";
import { demoSteps, type Scenario } from "@/types";
export function DemoControls() {
  const { t } = useI18n(); const { data, act, busy, select } = useResponse();
  const incident = data?.incidents.find(i => i.id === "INC-1042");
  const demo = useDemo(); const index = data?.demoIndex ?? 0;
  return <div className={`demo-section ${demo.complete ? "demo-complete" : ""} ${demo.waiting ? "demo-waiting" : ""}`}><div className="demo-bar"><div className="demo-status" role="status" aria-atomic="true"><span className={`demo-status-icon ${demo.waiting ? "waiting" : ""}`}>{demo.waiting ? <ShieldCheck size={18} /> : demo.complete ? <Check size={18} /> : <Play size={17} />}</span><div><strong>{t(demo.waiting ? "demo.wait" : demo.complete ? "demo.complete" : demo.running ? "demo.running" : "demo.ready")}</strong><small>{t("demo.presentation")} · <bdi>{index} / {demoSteps.length}</bdi>{incident && <> · <span className="demo-current-state" key={incident.status}>{t(`status.${incident.status}`)}</span></>}</small></div></div><div className="demo-actions"><button className="button secondary" onClick={() => demo.reset()} disabled={busy}><RotateCcw size={15} />{t("demo.reset")}</button><button className="button primary" onClick={demo.running ? demo.stop : demo.start} disabled={busy}>{demo.running ? <Pause size={15} /> : <Play size={15} />}{t(demo.running ? "demo.stop" : demo.complete ? "demo.runAgain" : "demo.run")}</button></div></div>
    <progress className="presentation-progress" value={index} max={demoSteps.length} aria-label={t("demo.presentation")} />
    <details className="demo-settings"><summary><SlidersHorizontal size={14} />{t("demo.title")}<ChevronRight size={14} /><span className="demo-progress-label" dir="ltr">{index} / {demoSteps.length}</span></summary><div className="demo-settings-content"><div className="demo-steps">{demoSteps.map((step, i) => <button key={step} className={i < index ? "step-done" : i === index ? "step-current" : ""} disabled={busy || demo.running || i !== index || data?.scenario !== "normal"} onClick={() => { select("INC-1042"); void act(() => demoService.step(step)); }}><span>{i < index ? <Check size={12} /> : i + 1}</span>{t(`demo.${step}`)}</button>)}</div><div className="demo-tools"><button className="button secondary" onClick={() => demo.reset(true)} disabled={busy}>{t("demo.start")}</button><label>{t("demo.scenario")}<select value={data?.scenario ?? "normal"} onChange={e => { demo.stop(); void act(() => demoService.setScenario(e.target.value as Scenario)); }}>{(["normal","api_failure","empty_incidents","empty_resources","offline","stale","loading"] as const).map(s => <option value={s} key={s}>{t(`scenario.${s}`)}</option>)}</select></label></div></div></details>
  </div>;
}
