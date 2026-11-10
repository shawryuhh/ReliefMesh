"use client";
import { useEffect, useRef, useState } from "react";
export const storyStages = ["report","details","recommendation","decision","activity"] as const;
export type StoryStage = typeof storyStages[number];
export function useIncidentStory(incidentId?: string) {
  const scroll = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<StoryStage>("report");
  useEffect(() => {
    const root = scroll.current; if (!root) return;
    root.scrollTop = 0; setActive("report");
    const visible = new Set<Element>();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target));
      const first = [...visible].sort((a,b) => a.getBoundingClientRect().top-b.getBoundingClientRect().top)[0] as HTMLElement | undefined;
      if (first) setActive(first.dataset.stage as StoryStage);
    }, { root, rootMargin: "-4px 0px -45% 0px", threshold: 0 });
    root.querySelectorAll("[data-stage]").forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [incidentId]);
  const go = (stage: StoryStage) => {
    const root = scroll.current; const target = root?.querySelector<HTMLElement>(`[data-stage="${stage}"]`);
    if (!root || !target) return;
    root.scrollTo({ top: root.scrollTop+target.getBoundingClientRect().top-root.getBoundingClientRect().top, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" }); setActive(stage);
  };
  return { scroll, active, go };
}
