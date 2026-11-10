/** Pure preview refresh state transitions; no operational actions. */
export type RefreshState = "empty" | "current" | "stale";
export type RefreshResult = { state: RefreshState; retainPrevious: boolean; warning: string | null };
export function refreshSucceeded(): RefreshResult {
  return { state: "current", retainPrevious: false, warning: null };
}
export function refreshFailed(hadPrevious: boolean): RefreshResult {
  return hadPrevious
    ? { state: "stale", retainPrevious: true, warning: "STALE / UNVERIFIED DATA — NOT CURRENT." }
    : { state: "empty", retainPrevious: false, warning: "No backend data is available." };
}
