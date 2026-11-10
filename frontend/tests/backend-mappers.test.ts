import assert from "node:assert/strict";
import test from "node:test";
import { ContractMismatch, mapAssignment, mapIncident, mapRecommendation, mapResource } from "../lib/services/backend-mappers.ts";

test("resource maps valid backend statuses and preserves coordinates", () => {
  const r = mapResource({id:"AMB-02",type:"ambulance",location:"Depot",latitude:12.9,longitude:77.6,
    capabilities:["medical"],status:"AVAILABLE",capacity:2});
  assert.equal(r.status,"available");
  assert.equal(r.latitude,12.9);
});
test("resource rejects missing coordinates rather than inventing locations", () => {
  assert.throws(() => mapResource({id:"AMB-02",type:"ambulance",location:"Depot",latitude:null,longitude:null,
    capabilities:[],status:"AVAILABLE",capacity:2}),ContractMismatch);
});
test("incident refuses absent reports and vulnerability data", () => {
  assert.throws(() => mapIncident({id:"INC-1",location:"Example",latitude:12,longitude:77,type:"flood",
    severity:"CRITICAL",priority_score:94,people_affected:4,needs:[],confidence:0.9,
    operational_phase:"awaiting_approval"}),/reports\/vulnerabilities\/duplicates/);
});
test("incident maps backend severity label when complete fields exist", () => {
  const i=mapIncident({id:"INC-1",location:"Example",latitude:12,longitude:77,type:"flood",
    severity:"CRITICAL",priority_score:94,people_affected:4,needs:[],confidence:0.9,
    operational_phase:"awaiting_approval",reports:[],vulnerabilities:[],duplicates:0});
  assert.equal(i.severity,4);
});
test("recommendation rejects null scores instead of fabricating confidence", () => {
  assert.throws(()=>mapRecommendation({incident:"INC-1",priority_score:null,
    recommended_resources:["AMB-02"],reason:"plan.reason",approval_required:true,confidence:0.9,
    explanation:[],version:1,state:"pending"}),ContractMismatch);
});
test("recommendation maps valid versioned pending plan", () => {
  const r=mapRecommendation({incident:"INC-1",priority_score:94,
    recommended_resources:["AMB-02"],reason:"plan.reason",approval_required:true,confidence:0.9,
    explanation:[{key:"explain.water",params:{id:"AMB-02"}}],version:1,state:"pending"});
  assert.equal(r.version,1);
  assert.equal(r.state,"pending");
});
test("assignment maps superseded to released", () => {
  const a=mapAssignment({id:"ASG-1",incident_id:"INC-1",resource_id:"AMB-02",
    approved_by:"coordinator",assigned_at:"2026-09-20T10:00:00Z",status:"SUPERSEDED"});
  assert.equal(a.status,"released");
});
