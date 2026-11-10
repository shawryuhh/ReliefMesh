"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { demoSteps } from "@/types";
import { demoService } from "@/lib/api";
import { nextAutomaticDemoStep } from "@/lib/presentation/demo-playback";
import { useResponse } from "@/state/response-context";
export function useDemo() {
  const { data, act, select } = useResponse();
  const [running, setRunning] = useState(false);
  const generation = useRef(0);
  const starting = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const index = data?.demoIndex ?? 0;
  const waiting = index === 5 || index === 9;
  const stop = useCallback(() => {
    generation.current++;
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null; setRunning(false);
  }, []);
  const start = async () => {
    if (starting.current || running) return;
    starting.current = true; stop(); const current = generation.current;
    try {
      const ok = await act(() => demoService.reset(true));
      // A pause/reset/unmount while a future network adapter is awaiting must
      // not allow its late reset response to resurrect playback.
      if (ok && current === generation.current) { select("INC-1042"); setRunning(true); }
    } finally { starting.current = false; }
  };
  const reset = async (forRun = false) => {
    stop(); const current = generation.current;
    const ok = await act(() => demoService.reset(forRun));
    if (ok && current === generation.current) select("INC-1042");
  };
  useEffect(() => {
    if (!running || !data) return;
    if (index >= demoSteps.length || data.scenario !== "normal" || data.incidents.some(i => i.id === "INC-1042" && i.status === "resolved") || data.recommendations.some(r => r.incident === "INC-1042" && r.state === "rejected")) { stop(); return; }
    const step = nextAutomaticDemoStep(data,running);
    if (!step) return; // Both human approvals are deliberately unscheduled.
    const current = generation.current;
    const timeout = setTimeout(async () => {
      if (current !== generation.current) return;
      timer.current = null;
      const ok = await act(() => demoService.step(step));
      if (!ok && current === generation.current) stop();
    }, index === 6 || index === 10 ? 3600 : 1900);
    timer.current = timeout;
    return () => { clearTimeout(timeout); if (timer.current === timeout) timer.current = null; };
  }, [running, index, data, act, stop]);
  useEffect(() => () => { generation.current++; if (timer.current !== null) clearTimeout(timer.current); timer.current = null; }, []);
  return { running, waiting: running && waiting, start, stop, reset, complete: index === demoSteps.length };
}
