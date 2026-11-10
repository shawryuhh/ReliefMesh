import { test } from "node:test";
import assert from "node:assert/strict";
import {
  createBackendDemoService,
  getDemoDataSource,
  setDemoDataSource,
  reliefService,
} from "../lib/api/index.ts";
import { seedSnapshot } from "../lib/mocks/data.ts";

test("default demo data source is mock (simulated fallback) and can opt-in to backend and revert", async () => {
  assert.equal(getDemoDataSource(), "mock");
  const initial = await reliefService.getDashboard();
  assert.equal(initial.health.mode, "mock");

  setDemoDataSource("backend");
  assert.equal(getDemoDataSource(), "backend");

  // Revert back to simulated fallback
  setDemoDataSource("mock");
  assert.equal(getDemoDataSource(), "mock");
  const restored = await reliefService.getDashboard();
  assert.equal(restored.health.mode, "mock");
});

test("createBackendDemoService maps snapshot, lifecycle actions, and backend error codes", async () => {
  const backendSnap = seedSnapshot();
  backendSnap.health.mode = "backend";
  backendSnap.health.automation = "n8n";

  const calls: { url: string; method: string; body?: Record<string, unknown> }[] = [];

  const mockFetch: typeof fetch = async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : undefined;
    calls.push({ url, method, body });

    if (method === "GET") {
      return new Response(JSON.stringify({ ok: true, snapshot: backendSnap }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (body?.action === "approve" && body?.version === 99) {
      return new Response(
        JSON.stringify({ ok: false, errorCode: "error.stalePlan", detail: "Stale plan" }),
        { status: 409, headers: { "Content-Type": "application/json" } }
      );
    }

    if (body?.action === "translate") {
      return new Response(
        JSON.stringify({
          ok: true,
          data: {
            id: body.id,
            originalText: body.originalText,
            originalLanguage: body.originalLanguage,
            receivedAt: body.receivedAt,
            translatedText: "Translated text",
            translatedLanguage: body.targetLanguage,
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(JSON.stringify({ ok: true, data: backendSnap }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  const service = createBackendDemoService(mockFetch);
  const snap = await service.getDashboard();
  assert.equal(snap.health.mode, "backend");
  assert.equal(snap.health.automation, "n8n");

  await service.approveRecommendation("INC-1042", 1);
  assert.equal(calls.at(-1)?.body?.action, "approve");

  await assert.rejects(
    service.approveRecommendation("INC-1042", 99),
    /error\.stalePlan/
  );

  const translated = await service.translateReport(snap.incidents[0].reports[0], "hi");
  assert.equal(translated.translatedLanguage, "hi");
  assert.equal(translated.translatedText, "Translated text");
});
