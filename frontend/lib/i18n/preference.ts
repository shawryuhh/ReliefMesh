import { languages } from "./languages.ts";
import type { Language } from "../../types/index.ts";
export const languageStorageKey = "reliefmesh.language";
export function isLanguage(value: string | null): value is Language { return languages.some(language => language.code === value); }
export function startupLanguage(saved: string | null, browserLocales: readonly string[]) {
  if (isLanguage(saved)) return { language: saved, needsConfirmation: false };
  for (const locale of browserLocales) { const code = locale.toLowerCase().split(/[-_]/)[0]; if (isLanguage(code)) return { language: code, needsConfirmation: true }; }
  return { language: "en" as Language, needsConfirmation: true };
}
