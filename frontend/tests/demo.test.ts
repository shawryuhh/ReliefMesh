import { test } from "node:test";
import assert from "node:assert/strict";
import { createMockService } from "../lib/mocks/service.ts";
import { createBackendDemoService, getDemoDataSource, setDemoDataSource } from "../lib/api/index.ts";
import { demoSteps } from "../types/index.ts";

test("canonical crisis: initial approval, obstruction, replacement approval, resolution, reset", async () => {
  const service = createMockService();
  const initial = await service.getDashboard();
  assert.equal(initial.incidents.length, 10);
  assert.equal(initial.resources.length, 19);
  assert.equal(initial.metrics.availableAmbulances, 5);
  await service.reset(true);
  for (const step of demoSteps.slice(0, 5)) await service.step(step);
  let state = await service.getDashboard();
  assert.equal(state.incidents.find(i => i.id === "INC-1042")?.status, "awaiting_approval");
  assert.equal(state.resources.find(r => r.id === "AMB-02")?.status, "available");
  await assert.rejects(service.createAssignment("INC-1042", "AMB-02"), /error.approval/);
  await service.approveRecommendation("INC-1042", 1);
  state = await service.getDashboard();
  assert.equal(state.metrics.availableAmbulances, 4);
  assert.equal(state.resources.find(r => r.id === "RESCUE-01")?.status, "dispatched");
  await assert.rejects(service.approveRecommendation("INC-1042", 1), /error.stalePlan/);
  const assignment = await service.createAssignment("INC-1042", "AMB-02");
  assert.equal((await service.createAssignment("INC-1042", "AMB-02")).id, assignment.id);
  for (const step of demoSteps.slice(6, 9)) await service.step(step);
  state = await service.getDashboard();
  assert.equal(state.resources.find(r => r.id === "AMB-02")?.eta, 24);
  assert.equal(state.resources.find(r => r.id === "AMB-05")?.status, "available");
  assert.equal(state.incidents.find(i => i.id === "INC-1042")?.status, "awaiting_replacement");
  await service.approveRecommendation("INC-1042", 2);
  state = await service.getDashboard();
  assert.equal(state.resources.find(r => r.id === "AMB-05")?.status, "dispatched");
  assert.equal(state.resources.find(r => r.id === "AMB-02")?.status, "available");
  assert.equal(state.resources.find(r => r.id === "RESCUE-01")?.status, "dispatched");
  assert.equal(state.assignments.filter(a => a.resourceId === "RESCUE-01" && a.status === "dispatched").length, 1);
  await service.step("resolve");
  state = await service.getDashboard();
  assert.equal(state.incidents.find(i => i.id === "INC-1042")?.status, "resolved");
  assert.equal(state.resources.find(r => r.id === "AMB-05")?.status, "available");
  assert.ok(state.activity.some(e => e.type === "replacement_approved"));
  assert.ok(state.activity.some(e => e.type === "redispatched"));
  assert.equal(state.assignments.filter(a => a.incidentId === "INC-1042" && a.status === "dispatched").length, 0);
  await service.reset();
  state = await service.getDashboard();
  assert.deepEqual(state.metrics, initial.metrics);
  assert.equal(state.demoIndex, 5);
  assert.equal(state.resources.find(r => r.id === "AMB-02")?.eta, 6);
});

test("modify validates availability, capability coverage, and version; reject does not dispatch", async () => {
  const s = createMockService();
  await assert.rejects(s.modifyRecommendation("INC-1042", ["AMB-03", "RESCUE-01"], 1), /error.resources/);
  await assert.rejects(s.modifyRecommendation("INC-1042", ["AMB-05"], 1), /error.coverage/);
  await assert.rejects(s.modifyRecommendation("INC-1042", ["AMB-02", "AMB-02"], 1), /error.resources/);
  await s.modifyRecommendation("INC-1042", ["AMB-05", "RESCUE-02"], 1);
  await assert.rejects(s.approveRecommendation("INC-1042", 1), /error.stalePlan/);
  await s.rejectRecommendation("INC-1042", "Need a different plan", 2);
  const state = await s.getDashboard();
  assert.equal(state.resources.find(r => r.id === "AMB-05")?.status, "available");
  assert.equal(state.assignments.filter(a => a.incidentId === "INC-1042").length, 0);
  assert.equal(state.activity.at(-1)?.metadata?.reason, "Need a different plan");
});

test("rejecting replacement leaves existing dispatched resources active", async () => {
  const s = createMockService();
  await s.approveRecommendation("INC-1042", 1);
  for (const step of demoSteps.slice(6,9)) await s.step(step);
  await s.rejectRecommendation("INC-1042", "Review route", 2);
  const state = await s.getDashboard();
  assert.equal(state.resources.find(r => r.id === "AMB-02")?.status, "dispatched");
  assert.equal(state.resources.find(r => r.id === "RESCUE-01")?.status, "dispatched");
  assert.equal(state.resources.find(r => r.id === "AMB-05")?.status, "available");
  assert.equal(state.incidents.find(i => i.id === "INC-1042")?.status, "blocked");
});

test("fault states cannot dispatch; snapshots cannot mutate internal state", async () => {
  const s = createMockService();
  for (const scenario of ["offline", "empty_resources", "empty_incidents", "loading"] as const) {
    await s.setScenario(scenario);
    await assert.rejects(s.approveRecommendation("INC-1042", 1));
  }
  await s.setScenario("api_failure");
  await assert.rejects(s.getDashboard(), /error.api/);
  await s.setScenario("normal");
  const snapshot = await s.getDashboard();
  snapshot.resources[0].status = "unavailable";
  assert.equal((await s.getResources())[0].status, "available");
  await assert.rejects(s.step("resolve"), /error.order/);
});

test("report translation preserves original, supports all 13 fixtures, rejects unknown text", async () => {
  const s = createMockService(); const report = (await s.getIncident("INC-1042"))!.reports[0];
  for (const language of ["en","hi","kn","ta","te","ml","mr","bn","gu","pa","ur","as","or"] as const) {
    const translated = await s.translateReport(report, language);
    assert.equal(translated.originalText, report.originalText);
    assert.equal(translated.originalLanguage, "en");
    assert.equal(translated.translatedLanguage, language);
    assert.ok(translated.translatedText);
  }
  await assert.rejects(s.translateReport({ ...report, originalText: "An unknown emergency message" }, "hi"), /error.translation/);
});

test("replacement versions stay newer than modified initial plans", async () => {
  const s = createMockService();
  await s.modifyRecommendation("INC-1042", ["AMB-02", "RESCUE-01"], 1);
  await s.approveRecommendation("INC-1042", 2);
  for (const step of demoSteps.slice(6,9)) await s.step(step);
  assert.equal((await s.getRecommendation("INC-1042"))?.version, 3);
  await assert.rejects(s.approveRecommendation("INC-1042", 2), /error.stalePlan/);
  await s.approveRecommendation("INC-1042", 3);
});

test("backend demo service never caches stale snapshots and switching modes never silently substitutes counts", async () => {
  let backendAmbulances = 4;
  let backendRescue = 2;
  let shouldFail = false;
  const mockSeed = await createMockService().getDashboard();

  const fakeFetch: typeof fetch = async () => {
    if (shouldFail) {
      return new Response(JSON.stringify({ ok: false, errorCode: "error.api" }), { status: 502 });
    }
    const snap = structuredClone(mockSeed);
    snap.metrics.availableAmbulances = backendAmbulances;
    snap.metrics.availableRescueTeams = backendRescue;
    return new Response(JSON.stringify({ ok: true, snapshot: snap }), { status: 200 });
  };

  const backendService = createBackendDemoService(fakeFetch);
  const first = await backendService.getDashboard();
  assert.equal(first.metrics.availableAmbulances, 4);
  assert.equal(first.metrics.availableRescueTeams, 2);

  // Subsequent reads reflect live backend changes rather than a cached snapshot
  backendAmbulances = 5;
  backendRescue = 3;
  const second = await backendService.getDashboard();
  assert.equal(second.metrics.availableAmbulances, 5);
  assert.equal(second.metrics.availableRescueTeams, 3);

  // Backend failure surfaces ServiceError and never substitutes mock data or changes data source
  const prevSource = getDemoDataSource();
  try {
    setDemoDataSource("backend");
    shouldFail = true;
    await assert.rejects(backendService.getDashboard(), /error.api/);
    assert.equal(getDemoDataSource(), "backend");
  } finally {
    setDemoDataSource(prevSource);
  }
});
