import { test } from "node:test";
import assert from "node:assert/strict";
import { createMockService } from "../lib/mocks/service.ts";
import { demoSteps, eventTypes } from "../types/index.ts";
import { nextAutomaticDemoStep } from "../lib/presentation/demo-playback.ts";
import { incidentPresentation } from "../lib/presentation/incident-state.ts";
import { isActiveIncident, nextActiveIncidentId, queueIncidents } from "../lib/presentation/incident-queue.ts";
async function completeDemo() {
  const service = createMockService(); await service.reset(true);
  for (const step of demoSteps.slice(0,5)) await service.step(step);
  await service.approveRecommendation("INC-1042",1);
  for (const step of demoSteps.slice(6,9)) await service.step(step);
  await service.approveRecommendation("INC-1042",2);
  await service.step("resolve"); return service;
}
test("completion retains the case and lifecycle, finishes assignments and cannot schedule or execute more steps", async () => {
  const service = await completeDemo(); const final = await service.getDashboard();
  const incident = final.incidents.find(i=>i.id==="INC-1042")!;
  assert.equal(incident.status,"resolved"); assert.equal(final.demoIndex,demoSteps.length);
  for (const id of ["AMB-02","AMB-05","RESCUE-01"]) {
    const resource = final.resources.find(r=>r.id===id)!;
    assert.equal(resource.status,"available"); assert.equal(resource.assignedIncident,undefined);
  }
  const assignments = final.assignments.filter(a=>a.incidentId===incident.id);
  assert.deepEqual(assignments.filter(a=>a.status==="completed").map(a=>a.resourceId).sort(),["AMB-05","RESCUE-01"]);
  assert.equal(assignments.find(a=>a.resourceId==="AMB-02")?.status,"released");
  assert.equal(assignments.filter(a=>a.status==="dispatched").length,0);
  assert.equal(final.metrics.activeIncidents,8); assert.equal(final.metrics.availableAmbulances,5); assert.equal(final.metrics.availableRescueTeams,3);
  assert.equal(incidentPresentation(incident,final.recommendations[0]).decision,false);
  // Neither a still-running render nor later snapshot refresh may schedule work.
  for (let i=0;i<5;i++) assert.equal(nextAutomaticDemoStep(await service.getDashboard(),true),undefined);
  await assert.rejects(service.step("receive"),/error.order/);
  await assert.rejects(service.step("resolve"),/error.order/);
  await assert.rejects(service.approveRecommendation(incident.id,2),/error.stalePlan/);
  assert.deepEqual(await service.getDashboard(),final);
  for (const type of eventTypes.filter(type=>!["modified","rejected"].includes(type))) assert.ok(final.activity.some(e=>e.incidentId===incident.id && e.type===type),type);
  assert.equal(final.activity.filter(e=>e.type==="incident_resolved").length,1);
});
test("active, pending and critical queues exclude closed cases while history and all retain them", async () => {
  const service = await completeDemo(); const snapshot = await service.getDashboard();
  const rejected = {...snapshot.incidents[0],id:"REJECTED-TEST",status:"rejected" as const,severity:5};
  const incidents = [...snapshot.incidents,rejected];
  for(const filter of ["active","pending","critical"] as const) {
    assert.ok(queueIncidents(incidents,filter).every(isActiveIncident));
    assert.ok(!queueIncidents(incidents,filter).some(i=>["INC-1042","REJECTED-TEST"].includes(i.id)));
  }
  for(const filter of ["history","all"] as const) for(const id of ["INC-1042","REJECTED-TEST"]) assert.ok(queueIncidents(incidents,filter).some(i=>i.id===id));
  assert.equal(queueIncidents(incidents,"all").length,incidents.length);
});
test("selection after completion chooses the highest-priority active case or a clean empty selection", async () => {
  const data = await (await completeDemo()).getDashboard();
  const expected = data.incidents.filter(isActiveIncident).sort((a,b)=>b.priority-a.priority)[0];
  assert.equal(nextActiveIncidentId([...data.incidents].reverse()),expected.id);
  assert.equal(nextActiveIncidentId(data.incidents.filter(i=>!isActiveIncident(i))),"");
  assert.equal(nextActiveIncidentId([]),"");
});
test("autoplay eligibility excludes both approval gates, paused, faulted, rejected and resolved snapshots", async () => {
  const service = createMockService(); let data = await service.getDashboard();
  assert.equal(data.demoIndex,5); assert.equal(nextAutomaticDemoStep(data,true),undefined);
  await service.approveRecommendation("INC-1042",1); data = await service.getDashboard();
  assert.equal(nextAutomaticDemoStep(data,true),"block"); assert.equal(nextAutomaticDemoStep(data,false),undefined);
  assert.equal(nextAutomaticDemoStep({...data,scenario:"offline"},true),undefined);
  for(const step of demoSteps.slice(6,9)) await service.step(step);
  data = await service.getDashboard(); assert.equal(data.demoIndex,9); assert.equal(nextAutomaticDemoStep(data,true),undefined);
  await service.rejectRecommendation("INC-1042","Review route",2); data = await service.getDashboard();
  assert.equal(nextAutomaticDemoStep({...data,demoIndex:8},true),undefined);
  const completed = await (await completeDemo()).getDashboard();
  assert.equal(nextAutomaticDemoStep({...completed,demoIndex:0},true),undefined);
  const resolved = completed.incidents.find(i=>i.id==="INC-1042")!;
  assert.equal(incidentPresentation(resolved,{...completed.recommendations[0],state:"pending"}).decision,false);
});
test("intentional restart resets cleanly and concurrent repeated receive cannot duplicate INC-1042", async () => {
  const service = await completeDemo();
  assert.equal((await service.getIncidents()).filter(i=>i.id==="INC-1042").length,1);
  await service.reset(true); let data = await service.getDashboard();
  assert.equal(data.demoIndex,0); assert.equal(data.activity.length,0); assert.equal(data.incidents.filter(i=>i.id==="INC-1042").length,0);
  const results = await Promise.allSettled([service.step("receive"),service.step("receive"),service.step("receive")]);
  assert.equal(results.filter(r=>r.status==="fulfilled").length,1);
  data = await service.getDashboard(); assert.equal(data.demoIndex,1);
  assert.equal(data.incidents.filter(i=>i.id==="INC-1042").length,1);
  assert.equal(data.activity.filter(e=>e.type==="incident_received").length,1);
});
