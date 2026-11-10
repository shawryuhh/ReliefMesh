import assert from "node:assert/strict";
import test from "node:test";
import { isSnapshotEnvelope } from "../lib/services/snapshot-contract.ts";

const valid = () => ({
  schema_version: 1, revision: null, complete: true,
  generated_at: "2026-11-10T12:00:00Z",
  incidents: [], resources: [], assignments: [],
  recommendations: [], reports: [], activity: [],
});
test("accepts a complete development snapshot envelope", () => {
  assert.equal(isSnapshotEnvelope(valid()),true);
});
test("rejects incomplete or unsupported snapshots", () => {
  assert.equal(isSnapshotEnvelope({...valid(),complete:false}),false);
  assert.equal(isSnapshotEnvelope({...valid(),schema_version:2}),false);
  assert.equal(isSnapshotEnvelope({...valid(),revision:"unverified"}),false);
});
test("rejects invalid timestamps and missing collections", () => {
  assert.equal(isSnapshotEnvelope({...valid(),generated_at:"not-a-date"}),false);
  const missing = valid() as Partial<ReturnType<typeof valid>>;
  delete missing.reports;
  assert.equal(isSnapshotEnvelope(missing),false);
});
