"use client";
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import type { Language } from "@/types";
import { languageStorageKey, startupLanguage } from "./preference";
import { translate } from "./catalog";
interface I18nContextValue { ready: boolean; needsLanguage: boolean; previewLanguage: (language: Language) => void; confirmLanguage: () => void; language: Language; setLanguage: (language: Language) => void; t: (key: string, params?: Record<string,string|number>) => string; dir: "ltr" | "rtl"; storageError: boolean }
const I18nContext = createContext<I18nContextValue | null>(null);
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, set] = useState<Language>("en");
  const [storageError, setStorageError] = useState(false);
  const [ready, setReady] = useState(false);
  const [needsLanguage, setNeedsLanguage] = useState(true);
  useEffect(() => {
    let saved: string | null = null;
    try { saved = localStorage.getItem(languageStorageKey); } catch { setStorageError(true); }
    const preference = startupLanguage(saved, navigator.languages?.length ? navigator.languages : [navigator.language]);
    set(preference.language); setNeedsLanguage(preference.needsConfirmation); setReady(true);
  }, []);
  const dir = language === "ur" ? "rtl" : "ltr";
  useEffect(() => { document.documentElement.lang = language; document.documentElement.dir = dir; }, [language, dir]);
  const setLanguage = useCallback((value: Language) => { set(value); try { localStorage.setItem(languageStorageKey, value); setStorageError(false); } catch { setStorageError(true); } }, []);
  const confirmLanguage = useCallback(() => { setLanguage(language); setNeedsLanguage(false); }, [language, setLanguage]);
  const t = useCallback((key: string, params?: Record<string,string|number>) => translate(language, key, params), [language]);
  return <I18nContext.Provider value={{ language, setLanguage, previewLanguage: set, confirmLanguage, ready, needsLanguage, t, dir, storageError }}>{children}</I18nContext.Provider>;
}
export function useI18n() { const ctx = useContext(I18nContext); if (!ctx) throw new Error("I18nProvider missing"); return ctx; }
