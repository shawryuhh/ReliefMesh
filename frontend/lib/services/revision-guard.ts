/** Monotonic snapshot acceptance for the development preview. */
export type RevisionDecision = "accept" | "stale" | "invalid";
export function decideRevision(current: number | null, incoming: number): RevisionDecision {
  if (!Number.isSafeInteger(incoming) || incoming < 0) return "invalid";
  if (current !== null && (!Number.isSafeInteger(current) || current < 0)) return "invalid";
  if (current !== null && incoming < current) return "stale";
  return "accept";
}
