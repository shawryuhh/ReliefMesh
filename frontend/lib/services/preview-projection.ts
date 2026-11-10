/** Strict validation of the read-only projected snapshot response. */
type Dict = Record<string, unknown>;
const obj = (v: unknown): v is Dict => v !== null && typeof v === "object" && !Array.isArray(v);
const str = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const nullableNumber = (v: unknown) => v === null || (typeof v === "number" && Number.isFinite(v));
const strings = (v: unknown) => Array.isArray(v) && v.every(str);
const unique = (rows: unknown[], key: (v: Dict) => string) => {
  const ids = new Set<string>();
  for (const row of rows) {
    if (!obj(row)) return false;
    const id = key(row);
    if (!id || ids.has(id)) return false;
    ids.add(id);
  }
  return true;
};
export function validPreviewProjection(value: unknown): boolean {
  if (!obj(value) || value.mode !== "read_only_preview" ||
      !Number.isSafeInteger(value.revision) || (value.revision as number) < 0 ||
      !str(value.generated_at) || !Number.isFinite(Date.parse(value.generated_at)))
    return false;
  const { incidents, resources, assignments, recommendations } = value;
  if (![incidents, resources, assignments, recommendations].every(Array.isArray)) return false;
  const i = incidents as unknown[], r = resources as unknown[];
  const a = assignments as unknown[], rec = recommendations as unknown[];
  return unique(i,x=>String(x.id ?? "")) && i.every(x=>obj(x) && str(x.id) &&
      str(x.location) && str(x.type) && str(x.severity) && str(x.operational_phase) &&
      nullableNumber(x.priority_score) && nullableNumber(x.people_affected)) &&
    unique(r,x=>String(x.id ?? "")) && r.every(x=>obj(x) && str(x.id) &&
      str(x.location) && str(x.type) && str(x.status) && nullableNumber(x.capacity)) &&
    unique(a,x=>String(x.id ?? "")) && a.every(x=>obj(x) && str(x.id) &&
      str(x.incident_id) && str(x.resource_id) && str(x.status) && str(x.assigned_at)) &&
    unique(rec,x=>String(x.incident ?? "") + ":" + String(x.version ?? "")) &&
    rec.every(x=>obj(x) && str(x.incident) && Number.isSafeInteger(x.version) &&
      (x.version as number) > 0 && str(x.state) && strings(x.recommended_resources));
}
