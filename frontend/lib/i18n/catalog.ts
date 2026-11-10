import { en, type TranslationKey } from "./en.ts";
import hi from "./locales/hi.json";
import kn from "./locales/kn.json";
import ta from "./locales/ta.json";
import te from "./locales/te.json";
import ml from "./locales/ml.json";
import mr from "./locales/mr.json";
import bn from "./locales/bn.json";
import gu from "./locales/gu.json";
import pa from "./locales/pa.json";
import ur from "./locales/ur.json";
import asLocale from "./locales/as.json";
import or from "./locales/or.json";
import type { Language } from "../../types/index.ts";
export const catalogs: Record<Language, Record<TranslationKey, string>> = { en, hi, kn, ta, te, ml, mr, bn, gu, pa, ur, as: asLocale, or };
const eventAliases: Record<string, TranslationKey> = {
  incident_received: "demo.receive", duplicates_merged: "demo.merge", priority_updated: "demo.priority",
  recommendation_generated: "demo.recommend", approval_requested: "demo.request", approved: "notice.approved",
  modified: "plan.modified", rejected: "notice.rejected", resource_dispatched: "status.dispatched",
  road_block_detected: "status.blocked", replanning_started: "status.replanning", replacement_recommended: "demo.replace",
  replacement_approved: "demo.approveReplacement", redispatched: "status.dispatched", incident_resolved: "status.resolved",
};
export function translate(language: Language, key: string, params: Record<string, string | number> = {}): string {
  const event = key.replace(/^(events|eventDescriptions)\./, "");
  const resolved = eventAliases[event] ?? key as TranslationKey;
  const value = catalogs[language][resolved] ?? en[resolved] ?? key;
  return value.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}
