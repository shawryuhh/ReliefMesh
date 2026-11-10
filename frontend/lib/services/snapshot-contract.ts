/** Pure snapshot envelope validation, separate from network/credentials. */
export const snapshotCollections = ["incidents","resources","assignments","recommendations","reports","activity"] as const;
export type SnapshotEnvelope = {
  schema_version: 1;
  revision: number;
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
  return v.schema_version === 1 && v.complete === true && typeof v.revision === "number" && Number.isSafeInteger(v.revision) && v.revision >= 0 &&
    typeof v.generated_at === "string" &&
    Number.isFinite(Date.parse(v.generated_at)) &&
    snapshotCollections.every(k => Array.isArray(v[k]));
}
