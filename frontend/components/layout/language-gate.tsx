"use client";
import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import { ArrowRight, Check, Globe2 } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { languages } from "@/lib/i18n/languages";
import { translate } from "@/lib/i18n/catalog";
export function LanguageGate({ children }: { children: ReactNode }) {
  const { language, previewLanguage, confirmLanguage, ready, needsLanguage, t, dir, storageError } = useI18n();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (ready && needsLanguage) heading.current?.focus(); }, [ready, needsLanguage]);
  if (ready && !needsLanguage) return <div className="command-entrance">{children}</div>;
  return <main className="language-onboarding" dir={dir} aria-labelledby="language-title"><section className="language-card">
    <div className="onboarding-identity"><span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span><strong>ReliefMesh</strong><Globe2 size={24} aria-hidden="true" /></div>
    <h1 id="language-title" ref={heading} tabIndex={-1}>{t("onboarding.title")}</h1>
    <div className="language-cues">{(["en", "hi", "kn", "ta"] as const).filter(code => code !== language).slice(0,3).map(code => <p key={code} lang={code} dir="ltr">{translate(code,"onboarding.title")}</p>)}</div>
    <form onSubmit={event => { event.preventDefault(); if (ready) confirmLanguage(); }}>
      <fieldset className="language-options"><legend className="sr-only">{t("app.language")}</legend>{languages.map((option,index) => <label key={option.code} className={`language-option ${language === option.code ? "language-selected" : ""}`} style={{ "--choice-index": index } as CSSProperties}>
        <input type="radio" name="preferred-language" value={option.code} checked={language === option.code} onChange={() => previewLanguage(option.code)} />
        <span lang={option.code} dir={option.dir}>{option.label}</span><Check size={17} aria-hidden="true" />
      </label>)}</fieldset>
      <div className="onboarding-footer"><p>{t("onboarding.hint")}</p><button className="button primary" type="submit" disabled={!ready}>{t("actions.continue")}<ArrowRight className="directional-icon" size={17} /></button></div>
      {storageError && <p className="onboarding-warning" role="status">{t("error.storage")}</p>}
    </form>
  </section></main>;
}
