import assert from "node:assert/strict";
import test from "node:test";
import { validPreviewProjection } from "../lib/services/preview-projection.ts";

const fixture=()=>({
  mode:"read_only_preview",revision:4,generated_at:"2026-11-10T12:00:00Z",
  incidents:[{id:"INC-1",location:"Synthetic",type:"flood",severity:"HIGH",
    operational_phase:"received",priority_score:null,people_affected:null}],
  resources:[{id:"AMB-1",location:"Depot",type:"ambulance",status:"AVAILABLE",capacity:null}],
  assignments:[],
  recommendations:[{incident:"INC-1",version:1,state:"pending",recommended_resources:["AMB-1"]}],
});
test("valid projected snapshot is accepted",()=>assert.equal(validPreviewProjection(fixture()),true));
test("duplicate incident IDs are rejected",()=>{
  const v=fixture();v.incidents.push({...v.incidents[0]});
  assert.equal(validPreviewProjection(v),false);
});
test("invalid recommendation versions are rejected",()=>{
  const v=fixture();v.recommendations[0].version=0;
  assert.equal(validPreviewProjection(v),false);
});
test("missing collections and invalid revisions are rejected",()=>{
  const v=fixture();
  assert.equal(validPreviewProjection({...v,resources:null}),false);
  assert.equal(validPreviewProjection({...v,revision:-1}),false);
});
