"use client";
import { Ambulance, LifeBuoy, TriangleAlert, Radio } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { useChangeFeedback } from "@/hooks/use-change-feedback";
function MetricValue({value}:{value?:number}) { const changed = useChangeFeedback(value); return <strong className={changed ? "value-changed" : ""}>{String(value ?? 0).padStart(2,"0")}</strong>; }
export function Metrics() {
  const { data } = useResponse(); const { t } = useI18n();
  const items = [
    { label: "metrics.critical", value: data?.metrics.criticalIncidents, Icon: TriangleAlert, color: "red", suffix: "severity.critical" },
    { label: "metrics.active", value: data?.metrics.activeIncidents, Icon: Radio, color: "blue", suffix: "status.active" },
    { label: "metrics.ambulances", value: data?.metrics.availableAmbulances, Icon: Ambulance, color: "green", suffix: "status.available" },
    { label: "metrics.rescue", value: data?.metrics.availableRescueTeams, Icon: LifeBuoy, color: "teal", suffix: "status.available" },
  ];
  return <section className="metrics-grid" aria-label={t("nav.overview")}>{items.map(({ label, value, Icon, color, suffix }) => <div className={`metric metric-${color}`} key={label}><div className="metric-top"><span>{t(label)}</span><Icon size={19} /></div><div className="metric-bottom"><MetricValue value={value} /><span><i />{t(suffix)}</span></div></div>)}</section>;
}
