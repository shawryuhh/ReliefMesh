import assert from "node:assert/strict";
import test from "node:test";
import { refreshFailed, refreshSucceeded } from "../lib/services/refresh-state.ts";

test("failed initial load has no operational data", () => {
  assert.deepEqual(refreshFailed(false), {
    state:"empty",retainPrevious:false,warning:"No backend data is available.",
  });
});
test("failed refresh retains previous data only as stale reference", () => {
  const result=refreshFailed(true);
  assert.equal(result.state,"stale");
  assert.equal(result.retainPrevious,true);
  assert.match(result.warning ?? "",/NOT CURRENT/);
});
test("successful refresh clears stale warning", () => {
  assert.deepEqual(refreshSucceeded(),{state:"current",retainPrevious:false,warning:null});
});
