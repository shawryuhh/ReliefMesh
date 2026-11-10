import assert from "node:assert/strict";
import test from "node:test";
import { classifyPreviewStatus, previewStatusMessage } from "../lib/services/preview-connection-status.ts";

test("classifies successful and restricted responses", () => {
  assert.equal(classifyPreviewStatus(200,null),"connected");
  assert.equal(classifyPreviewStatus(403,"local_preview_only"),"restricted");
  assert.equal(classifyPreviewStatus(404,"preview_disabled"),"disabled");
});
test("distinguishes backend configuration and data failures", () => {
  assert.equal(classifyPreviewStatus(503,"backend_not_configured"),"unconfigured");
  assert.equal(classifyPreviewStatus(502,"contract_mismatch"),"invalid_data");
  assert.equal(classifyPreviewStatus(502,"backend_unavailable"),"unavailable");
});
test("status messages contain no credentials", () => {
  assert.match(previewStatusMessage("invalid_data"),/validation/);
});
