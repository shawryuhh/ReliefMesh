export const apiConfig = {
  mode: "mock" as const,
  // Reserved only. Setting this does NOT silently enable a nonexistent backend.
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
};
