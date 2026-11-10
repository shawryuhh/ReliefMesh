/** Human-readable, non-sensitive status for development preview failures. */
export type PreviewConnectionStatus =
  | "connected" | "disabled" | "restricted" | "unconfigured"
  | "unavailable" | "invalid_data";
export function classifyPreviewStatus(status: number, code: string | null): PreviewConnectionStatus {
  if (status >= 200 && status < 300) return "connected";
  if (status === 403) return "restricted";
  if (status === 404 && code === "preview_disabled") return "disabled";
  if (status === 503 && code === "backend_not_configured") return "unconfigured";
  if (status === 502 && (code === "contract_mismatch" || code === "invalid_response"))
    return "invalid_data";
  return "unavailable";
}
export function previewStatusMessage(status: PreviewConnectionStatus): string {
  switch (status) {
    case "connected": return "Backend snapshot connected.";
    case "disabled": return "Development preview is disabled.";
    case "restricted": return "Development preview access is restricted.";
    case "unconfigured": return "Backend connection is not configured.";
    case "invalid_data": return "Backend data failed validation.";
    case "unavailable": return "Backend is unavailable or the request failed.";
  }
}
