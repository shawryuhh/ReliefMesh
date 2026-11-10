import assert from "node:assert/strict";
import test from "node:test";
import { validSnapshotRelationships } from "../lib/services/snapshot-relationships.ts";

const fixture=()=>({
 incidents:[{id:"INC-1"}],resources:[{id:"AMB-1"}],
 assignments:[{id:"ASG-1",incident_id:"INC-1",resource_id:"AMB-1"}],
 recommendations:[
  {incident:"INC-1",version:1,recommended_resources:["AMB-1"]},
  {incident:"INC-1",version:2,recommended_resources:["AMB-1"]},
 ],
});
test("accepts multiple historical recommendation versions",()=>assert.equal(validSnapshotRelationships(fixture()),true));
test("rejects duplicate recommendation versions",()=>{
 const v=fixture();v.recommendations[1].version=1;
 assert.equal(validSnapshotRelationships(v),false);
});
test("rejects orphaned historical assignments",()=>{
 const v=fixture();v.assignments[0].resource_id="REMOVED";
 assert.equal(validSnapshotRelationships(v),false);
});
