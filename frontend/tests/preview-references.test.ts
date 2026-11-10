import assert from "node:assert/strict";
import test from "node:test";
import { validPreviewReferences } from "../lib/services/preview-references.ts";

const sample=()=>({
  incidents:[{id:"INC-1"}],resources:[{id:"AMB-1"}],
  assignments:[{id:"ASG-1",incident_id:"INC-1",resource_id:"AMB-1"}],
  recommendations:[{incident:"INC-1",recommended_resources:["AMB-1"]}],
});
test("accepts consistent incident-resource relationships",()=>{
  assert.equal(validPreviewReferences(sample()),true);
});
test("rejects orphaned assignments",()=>{
  const v=sample();v.assignments[0].resource_id="MISSING";
  assert.equal(validPreviewReferences(v),false);
});
test("rejects orphaned recommendations",()=>{
  const v=sample();v.recommendations[0].incident="MISSING";
  assert.equal(validPreviewReferences(v),false);
});
test("rejects unknown recommended resources",()=>{
  const v=sample();v.recommendations[0].recommended_resources=["MISSING"];
  assert.equal(validPreviewReferences(v),false);
});
