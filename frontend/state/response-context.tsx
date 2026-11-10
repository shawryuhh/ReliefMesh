"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { DashboardSnapshot } from "@/types";
import { reliefService, demoService } from "@/lib/api";
import { matchesQueue, nextActiveIncidentId, queueIncidents, type QueueFilter } from "@/lib/presentation/incident-queue";
import { ServiceError } from "@/lib/services/contracts";
interface ResponseContextValue {
  data: DashboardSnapshot | null; loading: boolean; error: string | null; selectedId: string;
  queueFilter: QueueFilter; setQueueFilter: (filter: QueueFilter) => void; resolutionId: string | null;
  select: (id: string) => void; refresh: () => Promise<void>; busy: boolean;
  act: (fn: () => Promise<void>, success?: string) => Promise<boolean>;
  notice: string | null; dismissNotice: () => void;
}
const ResponseContext = createContext<ResponseContextValue | null>(null);
export function ResponseProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("INC-1042");
  const [queueFilter, setFilter] = useState<QueueFilter>("active");
  const [resolutionId, setResolutionId] = useState<string | null>(null);
  const latest = useRef<DashboardSnapshot | null>(null);
  const previous = useRef<DashboardSnapshot | null>(null);
  const selected = useRef("INC-1042");
  const handoff = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelHandoff = useCallback(() => { if (handoff.current !== null) clearTimeout(handoff.current); handoff.current = null; setResolutionId(null); }, []);
  const select = useCallback((id: string) => {
    cancelHandoff(); selected.current = id; setSelectedId(id);
    const incident = latest.current?.incidents.find(i => i.id === id);
    setFilter(current => incident && matchesQueue(incident,current) ? current : incident && !matchesQueue(incident,"active") ? "history" : "active");
  }, [cancelHandoff]);
  const setQueueFilter = useCallback((filter: QueueFilter) => {
    cancelHandoff(); setFilter(filter);
    const incidents = latest.current?.incidents ?? [];
    if (!incidents.some(i => i.id === selected.current && matchesQueue(i,filter))) {
      const id = queueIncidents(incidents,filter)[0]?.id ?? "";
      selected.current = id; setSelectedId(id);
    }
  }, [cancelHandoff]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const version = useRef(0); const actionLock = useRef(false);
  const refresh = useCallback(async () => {
    const request = ++version.current;
    try { const result = await reliefService.getDashboard(); if (request !== version.current) return; latest.current = result; setData(result); setError(null); }
    catch (err) { if (request === version.current) setError(err instanceof ServiceError ? err.key : "error.api"); }
    finally { if (request === version.current) setLoading(false); }
  }, []);
  useEffect(() => { const unsubscribe = reliefService.subscribe(() => { void refresh(); }); void refresh(); return () => { unsubscribe(); version.current++; }; }, [refresh]);
  useEffect(() => {
    const before = previous.current; previous.current = data;
    if (!data || !before) return;
    const incident = data.incidents.find(i => i.id === selected.current);
    if (incident?.status !== "resolved" || !before.incidents.some(i => i.id === incident.id && i.status !== "resolved")) return;
    cancelHandoff(); setNotice(null); setResolutionId(incident.id);
    // A one-time transition, never triggered merely by opening a historical case.
    handoff.current = setTimeout(() => {
      handoff.current = null; setResolutionId(null);
      const current = latest.current;
      if (selected.current !== incident.id || current?.incidents.find(i => i.id === incident.id)?.status !== "resolved") return;
      const id = nextActiveIncidentId(current.incidents);
      selected.current = id; setSelectedId(id); setFilter("active");
    },5000);
  }, [data,cancelHandoff]);
  useEffect(() => () => { if (handoff.current !== null) clearTimeout(handoff.current); }, []);
  useEffect(() => { if (!notice) return; const timeout = setTimeout(() => setNotice(null), 6500); return () => clearTimeout(timeout); }, [notice]);
  const act = useCallback(async (fn: () => Promise<void>, success?: string) => {
    if (actionLock.current) return false;
    actionLock.current = true; setBusy(true);
    try { await fn(); await refresh(); if (success) setNotice(success); return true; }
    catch (err) { setNotice(err instanceof ServiceError ? err.key : "error.api"); return false; }
    finally { actionLock.current = false; setBusy(false); }
  }, [refresh]);
  return <ResponseContext.Provider value={{ data, loading, error, selectedId, queueFilter, setQueueFilter, resolutionId, select, refresh, busy, act, notice, dismissNotice: () => setNotice(null) }}>{children}</ResponseContext.Provider>;
}
export function useResponse() { const ctx = useContext(ResponseContext); if (!ctx) throw new Error("ResponseProvider missing"); return ctx; }
export async function recoverSimulation() { await demoService.setScenario("normal"); }
