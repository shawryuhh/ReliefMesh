"use client";
import { CheckCircle2 } from "lucide-react";
import type { Incident } from "@/types";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
export function ResolutionSummary({ incident }: { incident: Incident }) {
  const { data, resolutionId, setQueueFilter } = useResponse(); const { t } = useI18n();
  // Completed assignments record responders released on resolution. Earlier
  // replacement releases remain in the audit trail, not this completion claim.
  const released = [...new Set(data?.assignments.filter(a => a.incidentId === incident.id && a.status === "completed").map(a => a.resourceId) ?? [])];
  return <section className="resolution-summary" aria-label={t("resolution.complete")}>
    <div role="status" aria-atomic="true"><h3><CheckCircle2 size={21} />{t("status.resolved")} · {t("resolution.complete")}</h3>
      <p>{t("resolution.people")}: <strong>{incident.people}</strong></p>
      {released.length > 0 && <p>{t("decision.released")}: <strong dir="ltr">{released.join(" + ")}</strong></p>}
    </div>
    {resolutionId === incident.id ? <p className="resolution-next">{t("resolution.next")}</p> : <button className="text-link" onClick={() => setQueueFilter("active")}>{t("queue.active")}</button>}
  </section>;
}
