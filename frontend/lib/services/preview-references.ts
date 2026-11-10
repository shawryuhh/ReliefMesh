/** Check relationships in a complete read-only snapshot projection. */
type Row = Record<string, unknown>;
const rows = (value: unknown): value is Row[] =>
  Array.isArray(value) && value.every(x => x !== null && typeof x === "object" && !Array.isArray(x));
export function validPreviewReferences(value: unknown): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  if (!rows(v.incidents) || !rows(v.resources) || !rows(v.assignments) || !rows(v.recommendations)) return false;
  const incidents = new Set(v.incidents.map(i => i.id));
  const resources = new Set(v.resources.map(r => r.id));
  return v.assignments.every(a =>
    typeof a.incident_id === "string" && incidents.has(a.incident_id) &&
    typeof a.resource_id === "string" && resources.has(a.resource_id)) &&
    v.recommendations.every(r =>
      typeof r.incident === "string" && incidents.has(r.incident) &&
      Array.isArray(r.recommended_resources) &&
      r.recommended_resources.every(id => typeof id === "string" && resources.has(id)));
}
