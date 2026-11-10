import assert from "node:assert/strict";
import test from "node:test";
import { decideRevision } from "../lib/services/revision-guard.ts";

test("first and newer snapshots are accepted", () => {
  assert.equal(decideRevision(null,0),"accept");
  assert.equal(decideRevision(2,3),"accept");
  assert.equal(decideRevision(3,3),"accept");
});
test("older snapshots are rejected", () => {
  assert.equal(decideRevision(5,4),"stale");
  assert.equal(decideRevision(100,0),"stale");
});
test("invalid revisions are rejected", () => {
  assert.equal(decideRevision(null,-1),"invalid");
  assert.equal(decideRevision(1,1.5),"invalid");
  assert.equal(decideRevision(1,Number.NaN),"invalid");
  assert.equal(decideRevision(1,Number.MAX_SAFE_INTEGER+1),"invalid");
});
