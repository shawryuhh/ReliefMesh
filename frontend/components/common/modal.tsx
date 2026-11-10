"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
export function Modal({ title, children, close, closing = false, dismissDisabled = false }: { title: string; children: ReactNode; close: () => void; closing?: boolean; dismissDisabled?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null); const { t } = useI18n();
  useEffect(() => { const target = document.activeElement as HTMLElement | null; ref.current?.showModal(); return () => { if (target?.isConnected) target.focus({ preventScroll: true }); else document.querySelector<HTMLElement>(".decision-dock")?.focus({ preventScroll: true }); }; }, []);
  return <dialog className={`modal ${closing ? "modal-closing" : ""}`} ref={ref} aria-labelledby="modal-title" onKeyDown={e => { if (e.key !== "Tab") return; const nodes = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]') ?? []).filter(el => el.getClientRects().length); const first = nodes[0], last = nodes.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); } }} onCancel={e => { e.preventDefault(); if (!dismissDisabled) close(); }} onClick={e => { if (!dismissDisabled && e.target === ref.current) { const r = ref.current.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) close(); } }}>
    <div className="modal-header"><h2 id="modal-title">{t(title)}</h2><button className="icon-button" disabled={dismissDisabled || closing} onClick={close} aria-label={t("actions.close")}><X size={20} /></button></div>{children}
  </dialog>;
}
