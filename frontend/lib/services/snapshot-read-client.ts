import "server-only";
import { BackendReadError } from "./backend-read-client";

type Snapshot = {
  schema_version: 1;
  revision: null;
  generated_at: string;
  complete: true;
  incidents: unknown[];
  resources: unknown[];
  assignments: unknown[];
  recommendations: unknown[];
  reports: unknown[];
  activity: unknown[];
};
const collections = ["incidents","resources","assignments","recommendations","reports","activity"] as const;

export async function fetchSnapshotPreview(): Promise<Snapshot> {
  const base = process.env.RELIEFMESH_BACKEND_URL;
  if (!base) throw new BackendReadError("not_configured");
  let origin: string;
  try {
    const url = new URL(base);
    const loopback = ["localhost","127.0.0.1","[::1]"].includes(url.hostname);
    if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
        (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)))
      throw new Error("invalid");
    origin = url.origin;
  } catch { throw new BackendReadError("not_configured"); }

  // This route is intended only for the isolated local development preview.
  if (process.env.NODE_ENV !== "development" || process.env.RELIEFMESH_ENABLE_READ_PREVIEW !== "true")
    throw new BackendReadError("not_configured");
  const key = process.env.RELIEFMESH_BACKEND_READ_KEY;
  if (!key) throw new BackendReadError("not_configured");
  let response: Response;
  try {
    response = await fetch(origin + "/integration/v1/snapshot-preview", {
      method: "GET", cache: "no-store", redirect: "error",
      headers: { "X-API-Key": key, Accept: "application/json" },
      signal: AbortSignal.timeout(8000),
    });
  } catch { throw new BackendReadError("unavailable"); }
  if (!response.ok) throw new BackendReadError("unavailable");
  const length = Number(response.headers.get("content-length") ?? "0");
  if (length > 2_000_000) throw new BackendReadError("invalid_response");
  let body: string;
  try { body = await response.text(); } catch { throw new BackendReadError("unavailable"); }
  if (body.length > 2_000_000) throw new BackendReadError("invalid_response");
  let data: unknown;
  try { data = JSON.parse(body); } catch { throw new BackendReadError("invalid_response"); }
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw new BackendReadError("invalid_response");
  const v = data as Record<string, unknown>;
  if (v.schema_version !== 1 || v.complete !== true || v.revision !== null ||
      typeof v.generated_at !== "string" || !Number.isFinite(Date.parse(v.generated_at)) ||
      collections.some(k => !Array.isArray(v[k])))
    throw new BackendReadError("invalid_response");
  return v as Snapshot;
}
