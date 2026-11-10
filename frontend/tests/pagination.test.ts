import assert from "node:assert/strict";
import test from "node:test";

// Test the pagination algorithm independently of server-only credentials.
import { collectPages } from "../lib/services/pagination.ts";

test("collects consecutive pages and stops at a short page", async () => {
  const offsets: number[] = [];
  const result = await collectPages(async (limit, offset) => {
    offsets.push(offset);
    return offset === 0 ? [{id:"A"},{id:"B"}] : [{id:"C"}];
  },2,3);
  assert.deepEqual(offsets,[0,2]);
  assert.deepEqual(result.map(x=>x.id),["A","B","C"]);
});
test("rejects duplicate ids across pages", async () => {
  await assert.rejects(()=>collectPages(async (_,offset)=>
    offset===0?[{id:"A"},{id:"B"}]:[{id:"A"}],2,3),/invalid_page/);
});
test("rejects malformed pages", async () => {
  await assert.rejects(()=>collectPages(async ()=>[{name:"missing id"}],2,3),/invalid_page/);
});
test("rejects a full final page rather than claiming completeness", async () => {
  await assert.rejects(()=>collectPages(async (_,offset)=>
    [{id:"X"+offset},{id:"Y"+offset}],2,2),/page_limit/);
});
test("empty collection is valid", async () => {
  assert.deepEqual(await collectPages(async ()=>[],2,3),[]);
});
