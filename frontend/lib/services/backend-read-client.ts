import "server-only";

// Internal read-only backend client. Never import this module in client components.
export class BackendReadError extends Error {
  constructor(public readonly code: "not_configured" | "unavailable" | "invalid_response") {
    super(code);
    this.name = "BackendReadError";
  }
}
function configuredOrigin(): string {
  const value = process.env.RELIEFMESH_BACKEND_URL;
  if (!value) throw new BackendReadError("not_configured");
  let url: URL;
  try { url = new URL(value); } catch { throw new BackendReadError("not_configured"); }
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/")
    throw new BackendReadError("not_configured");
  const loopback = url.hostname === "localhost" || url.hostname === "127.0.0.1" ||
    url.hostname === "[::1]";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback))
    throw new BackendReadError("not_configured");
  return url.origin;
}
async function getJson(origin: string, path: string): Promise<unknown> {
  const key = process.env.RELIEFMESH_BACKEND_READ_KEY;
  let response: Response;
  try {
    response = await fetch(origin + path, {
      method: "GET", cache: "no-store", redirect: "error",
      headers: key ? { "X-API-Key": key, Accept: "application/json" } : { Accept: "application/json" },
      signal: AbortSignal.timeout(5000),
    });
  } catch { throw new BackendReadError("unavailable"); }
  if (!response.ok) throw new BackendReadError("unavailable");
  const size = Number(response.headers.get("content-length") ?? "0");
  if (size > 2_000_000) throw new BackendReadError("invalid_response");
  let body: string;
  try { body = await response.text(); } catch { throw new BackendReadError("unavailable"); }
  if (body.length > 2_000_000) throw new BackendReadError("invalid_response");
  try { return JSON.parse(body) as unknown; }
  catch { throw new BackendReadError("invalid_response"); }
}
export async function fetchBackendCollections(): Promise<{ incidents: unknown; resources: unknown }> {
  const origin = configuredOrigin();
  const [incidents, resources] = await Promise.all([
    getJson(origin, "/incidents?limit=100"),
    getJson(origin, "/resources?limit=100"),
  ]);
  return { incidents, resources };
}
