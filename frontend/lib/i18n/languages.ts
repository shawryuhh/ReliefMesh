import type { Language } from "../../types/index.ts";
export const languages: { code: Language; label: string; dir: "ltr" | "rtl" }[] = [
  { code: "en", label: "English", dir: "ltr" }, { code: "hi", label: "हिन्दी", dir: "ltr" },
  { code: "kn", label: "ಕನ್ನಡ", dir: "ltr" }, { code: "ta", label: "தமிழ்", dir: "ltr" },
  { code: "te", label: "తెలుగు", dir: "ltr" }, { code: "ml", label: "മലയാളം", dir: "ltr" },
  { code: "mr", label: "मराठी", dir: "ltr" }, { code: "bn", label: "বাংলা", dir: "ltr" },
  { code: "gu", label: "ગુજરાતી", dir: "ltr" }, { code: "pa", label: "ਪੰਜਾਬੀ", dir: "ltr" },
  { code: "ur", label: "اردو", dir: "rtl" }, { code: "as", label: "অসমীয়া", dir: "ltr" },
  { code: "or", label: "ଓଡ଼ିଆ", dir: "ltr" },
];
