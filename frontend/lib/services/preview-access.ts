// Development-only hostname guard, not user authentication.
function localHost(value: string | null): boolean {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return /^(localhost|127\.0\.0\.1)(:[0-9]{1,5})?$/.test(normalized) ||
    /^\[::1\](:[0-9]{1,5})?$/.test(normalized);
}
export function previewAllowed(
  env: string | undefined,
  enabled: string | undefined,
  host: string | null,
  forwardedHost: string | null,
): boolean {
  if (env !== "development" || enabled !== "true" || !localHost(host)) return false;
  // Next.js may set X-Forwarded-Host for legitimate local requests.
  // Never trust a different forwarded hostname or a comma-separated chain.
  return forwardedHost === null || (localHost(forwardedHost) &&
    forwardedHost.trim().toLowerCase() === host!.trim().toLowerCase());
}
