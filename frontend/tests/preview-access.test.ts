import assert from "node:assert/strict";
import test from "node:test";
import { previewAllowed } from "../lib/services/preview-access.ts";

test("local development preview must be explicitly enabled", () => {
  assert.equal(previewAllowed("development","true","localhost:3000",null),true);
  assert.equal(previewAllowed("development","true","127.0.0.1:3000",null),true);
  assert.equal(previewAllowed("development","true","[::1]:3000",null),true);
  assert.equal(previewAllowed("development",undefined,"localhost:3000",null),false);
});
test("production and preview proxies are denied", () => {
  assert.equal(previewAllowed("production","true","localhost:3000",null),false);
  assert.equal(previewAllowed("development","true","localhost:3000","public.example"),false);
  assert.equal(previewAllowed("development","true","localhost:3000","localhost:3000"),true);
  assert.equal(previewAllowed("development","true","127.0.0.1:3000","127.0.0.1:3000"),true);
  assert.equal(previewAllowed("development","true","example.com",null),false);
  assert.equal(previewAllowed("development","true","localhost.evil.com",null),false);
});
