/** Cross-record invariants for read-only snapshot preview. */
type Row = Record<string, unknown>;
const rows = (v: unknown): v is Row[] =>
  Array.isArray(v) && v.every(x => x && typeof x === "object" && !Array.isArray(x));
export function validSnapshotRelationships(v: unknown): boolean {
  if (!v || typeof v !== "object" || Array.isArray(v)) return false;
  const x = v as Record<string, unknown>;
  if (!rows(x.incidents) || !rows(x.resources) || !rows(x.assignments) || !rows(x.recommendations)) return false;
  const incidents = new Set(x.incidents.map(i => i.id));
  const resources = new Set(x.resources.map(r => r.id));
  const recommendations = new Map<string, Row>();
  for (const r of x.recommendations) {
    if (typeof r.incident !== "string" || !incidents.has(r.incident) ||
        !Number.isSafeInteger(r.version) || (r.version as number) < 1 ||
        !Array.isArray(r.recommended_resources) ||
        !r.recommended_resources.every(id => typeof id === "string" && resources.has(id)))
      return false;
    const key = r.incident + ":" + r.version;
    if (recommendations.has(key)) return false;
    recommendations.set(key, r);
  }
  for (const a of x.assignments) {
    if (typeof a.incident_id !== "string" || !incidents.has(a.incident_id) ||
        typeof a.resource_id !== "string" || !resources.has(a.resource_id))
      return false;
  }
  return true;
}
