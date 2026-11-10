// Pure, testable development-preview access policy.
// Host headers alone do not authenticate callers. Never deploy this as
// authorization for sensitive incident data.
export function previewAllowed(env: string | undefined, enabled: string | undefined, host: string | null, forwardedHost: string | null): boolean {
  if (env !== "development" || enabled !== "true" || forwardedHost !== null) return false;
  // IPv6 localhost may be bracketed and include a port.
  const normalized = (host ?? "").trim().toLowerCase();
  return /^(localhost|127\\.0\\.0\\.1)(:[0-9]{1,5})?$/.test(normalized) ||
    /^\\[::1\\](:[0-9]{1,5})?$/.test(normalized);
}
