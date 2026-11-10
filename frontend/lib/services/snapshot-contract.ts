/** Pure snapshot envelope validation, separate from network/credentials. */
export const snapshotCollections = ["incidents","resources","assignments","recommendations","reports","activity"] as const;
export type SnapshotEnvelope = {
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
export function isSnapshotEnvelope(data: unknown): data is SnapshotEnvelope {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  const v = data as Record<string, unknown>;
  return v.schema_version === 1 && v.complete === true && v.revision === null &&
    typeof v.generated_at === "string" &&
    Number.isFinite(Date.parse(v.generated_at)) &&
    snapshotCollections.every(k => Array.isArray(v[k]));
}
