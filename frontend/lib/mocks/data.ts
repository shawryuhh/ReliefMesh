import type { DashboardSnapshot, Incident, Resource, Recommendation, IncidentType } from "../../types/index.ts";

// Fictional operational data around Bengaluru. No real emergencies or responders.
export function canonicalIncident(now: string): Incident {
  return {
    id: "INC-1042", location: "Krishna Apartments Block C", latitude: 12.9347, longitude: 77.6269,
    type: "flood", severity: 5, priority: 94, people: 3, needs: ["ambulance", "water_rescue"],
    confidence: 0.91, status: "awaiting_approval", vulnerabilities: ["elderly_mobility"], duplicates: 2,
    reports: [{ id: "RPT-1042", originalText: "Water entering Krishna Apartments Block C. My grandmother cannot walk.", originalLanguage: "en", receivedAt: now }],
  };
}

export function canonicalRecommendation(replacement = false): Recommendation {
  return {
    incident: "INC-1042", priority_score: 94, recommended_resources: replacement ? ["AMB-05", "RESCUE-01"] : ["AMB-02", "RESCUE-01"],
    reason: replacement ? "plan.replacementReason" : "plan.reason", approval_required: true, confidence: 0.91,
    version: replacement ? 2 : 1, replacementFor: replacement ? "AMB-02" : undefined, state: "pending",
    explanation: replacement ? [
      { key: "explain.blocked", params: { id: "AMB-02", old: 6, eta: 24 } },
      { key: "explain.available", params: { id: "AMB-05" } },
      { key: "explain.eta", params: { id: "AMB-05", eta: 9 } },
      { key: "explain.continues", params: { id: "RESCUE-01" } },
    ] : [
      { key: "explain.distance", params: { id: "AMB-02", distance: 2.1 } },
      { key: "explain.available", params: { id: "AMB-02" } },
      { key: "explain.als", params: { id: "AMB-02" } },
      { key: "explain.eta", params: { id: "AMB-02", eta: 6 } },
      { key: "explain.water", params: { id: "RESCUE-01" } },
      { key: "explain.priority" },
    ],
  };
}

export function seedSnapshot(now = new Date().toISOString()): DashboardSnapshot {
  const rows: [string, string, number, number, IncidentType, number, number, number, string][] = [
    ["INC-1041", "Ejipura low-lying settlement", 12.942, 77.622, "evacuation", 5, 89, 18, "Water has reached the ground floor. Eighteen residents need help moving to a shelter."],
    ["INC-1040", "HSR Layout · Sector 2", 12.912, 77.642, "medical", 4, 85, 1, "पानी के कारण रास्ता बंद है। मेरे पिता को साँस लेने में तकलीफ़ हो रही है।"],
    ["INC-1039", "Bellandur service road", 12.928, 77.675, "flood", 4, 78, 6, "Six workers are stranded near the service road. Water is rising."],
    ["INC-1038", "Agara village", 12.925, 77.65, "supplies", 3, 64, 24, "We need drinking water and dry food at the community hall."],
    ["INC-1037", "Madiwala market", 12.919, 77.616, "evacuation", 3, 61, 8, "Eight shopkeepers cannot cross the flooded market entrance."],
    ["INC-1036", "Koramangala · 6th Block", 12.938, 77.613, "medical", 4, 81, 2, "Two people have minor injuries after a wall collapsed."],
    ["INC-1035", "Sarjapur junction", 12.918, 77.663, "landslide", 3, 57, 4, "Debris is blocking the approach road. Four residents are safe upstairs."],
    ["INC-1034", "BTM Layout · 2nd Stage", 12.907, 77.61, "supplies", 2, 42, 12, "Families at the school shelter need blankets and medication."],
    ["INC-1033", "Iblur community centre", 12.921, 77.666, "evacuation", 2, 35, 7, "Seven residents have reached the community centre safely."],
  ];
  const incidents: Incident[] = [canonicalIncident(now), ...rows.map((r, index): Incident => ({
    id: r[0], location: r[1], latitude: r[2], longitude: r[3], type: r[4], severity: r[5], priority: r[6], people: r[7],
    needs: r[4] === "medical" ? ["ambulance"] : r[4] === "supplies" ? ["supplies"] : ["water_rescue", "shelter"],
    confidence: 0.82 + index / 100, status: index === 8 ? "resolved" : index === 5 ? "dispatched" : "received",
    vulnerabilities: index === 1 ? ["elderly_mobility"] : [], duplicates: 0,
    reports: [{ id: `RPT-${r[0]}`, originalText: r[8], originalLanguage: index === 1 ? "hi" : "en", receivedAt: now,
      ...(index === 1 ? { translatedText: "The road is blocked by water. My father is having difficulty breathing.", translatedLanguage: "en" as const } : {}) }],
  }))];
  const resources: Resource[] = [
    ...Array.from({ length: 7 }, (_, i): Resource => ({
      id: `AMB-0${i + 1}`, type: "ambulance", latitude: [12.953,12.949,12.921,12.906,12.936,12.916,12.94][i],
      longitude: [77.64,77.614,77.605,77.655,77.664,77.674,77.649][i],
      capabilities: i % 3 === 0 ? ["basic_life_support"] : ["advanced_life_support"], capacity: 2,
      status: i === 2 ? "dispatched" : i === 5 ? "busy" : "available",
      assignedIncident: i === 2 ? "INC-1036" : undefined,
      eta: [8,6,7,12,9,14,11][i], distanceKm: [3.2,2.1,2.8,5.4,3.8,6,4.2][i],
    })),
    ...Array.from({ length: 5 }, (_, i): Resource => ({
      id: `RESCUE-0${i + 1}`, type: "rescue", latitude: 12.928 + i * .004, longitude: 77.602 + i * .017,
      capabilities: i < 3 ? ["water_rescue", "first_aid"] : ["evacuation", "first_aid"], capacity: 6,
      status: i === 3 ? "active" : i === 4 ? "unavailable" : "available", eta: 7 + i * 2,
    })),
    ...["South City Medical Centre", "District Emergency Hospital", "Community Care Hospital"].map((name, i): Resource => ({
      id: `HOSP-0${i + 1}`, name, type: "hospital", latitude: 12.914 + i * .019, longitude: 77.63 + i * .01,
      capabilities: ["emergency_care", "icu"], capacity: [18,32,12][i], status: i === 2 ? "busy" : "available",
    })),
    ...["Agara Relief Centre", "HSR Public School", "Koramangala Community Hall", "Bellandur Relief Camp"].map((name, i): Resource => ({
      id: `SHELTER-0${i + 1}`, name, type: "shelter", latitude: 12.904 + i * .012, longitude: 77.62 + i * .014,
      capabilities: ["shelter", "supplies"], capacity: [120,80,150,60][i], status: "available",
    })),
  ];
  return {
    incidents, resources, recommendations: [canonicalRecommendation()],
    assignments: [{ id: "ASN-SEED", incidentId: "INC-1036", resourceId: "AMB-03", approvedBy: "coordinator", createdAt: now, status: "dispatched" }],
    activity: ["incident_received", "duplicates_merged", "priority_updated", "recommendation_generated", "approval_requested"].map((type, i) => ({
      id: `EVT-SEED-${i}`, timestamp: new Date(Date.parse(now) - (5 - i) * 45000).toISOString(),
      source: i < 2 ? "intake" as const : "ai" as const, type: type as DashboardSnapshot["activity"][number]["type"],
      title: `events.${type}`, description: `eventDescriptions.${type}`, incidentId: "INC-1042",
      metadata: { id: "INC-1042", resources: "AMB-02 + RESCUE-01", priority: 94, count: 2 },
    })),
    metrics: { criticalIncidents: 0, activeIncidents: 0, availableAmbulances: 0, availableRescueTeams: 0 },
    health: { mode: "mock", automation: "simulated", stale: false, lastSync: now }, demoIndex: 5, scenario: "normal",
  };
}
