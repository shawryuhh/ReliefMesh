import { test } from "node:test";
import assert from "node:assert/strict";
import { createMockService } from "../lib/mocks/service.ts";
import { incidentPresentation } from "../lib/presentation/incident-state.ts";
test("next actions follow real approval, disruption and rejection states", async () => {
 const service = createMockService();
 const view = async () => { const data = await service.getDashboard(); return incidentPresentation(data.incidents.find(i => i.id === "INC-1042")!,data.recommendations.find(p => p.incident === "INC-1042")); };
 assert.equal((await view()).next,"next.approve");
 await service.approveRecommendation("INC-1042",1);
 assert.equal((await view()).next,"next.monitor");
 await service.step("block"); assert.equal((await view()).next,"next.disruption");
 await service.step("replan"); assert.equal((await view()).next,"next.replan");
 await service.step("replace"); assert.equal((await view()).next,"next.replacement"); assert.equal((await view()).decision,true);
 await service.rejectRecommendation("INC-1042","Review route",2);
 assert.equal((await view()).next,"next.rejected"); assert.equal((await view()).decision,false);
 assert.equal((await service.getDashboard()).resources.find(r=>r.id==="RESCUE-01")?.status,"dispatched");
});
