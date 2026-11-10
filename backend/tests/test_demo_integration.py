"""End-to-end integration tests for the PostgreSQL + FastAPI + AI + n8n demo lifecycle."""

from app.core.config import Settings, get_settings
from app.main import app


def _with_auth(monkeypatch):
    base = get_settings().model_dump()
    base.update(
        {
            "auth_enabled": True,
            "coordinator_api_key": "coord-test-key",
            "automation_api_key": "auto-test-key",
            "api_key": "read-test-key",
        }
    )
    app.dependency_overrides[get_settings] = lambda: Settings(**base)


def test_complete_incident_lifecycle_with_ai_and_human_gates(client):
    # Reset for live run (step 0)
    reset_resp = client.post("/integration/v1/demo/reset", json={"for_run": True})
    assert reset_resp.status_code == 200
    snap = reset_resp.json()
    assert snap["demoIndex"] == 0
    assert snap["health"]["mode"] == "backend"
    assert snap["aiEngine"]["approval_required"] is True
    assert not any(i["id"] == "INC-1042" for i in snap["incidents"])

    # Steps 0..4: receive -> merge -> priority -> recommend -> request
    for expected_idx, step_name in enumerate(
        ["receive", "merge", "priority", "recommend", "request"], start=1
    ):
        resp = client.post(
            "/integration/v1/demo/step",
            json={"step": step_name},
            headers={"X-Fixture-Actor": "automation"},
        )
        assert resp.status_code == 200, resp.text
        snap = resp.json()
        assert snap["demoIndex"] == expected_idx

    inc = next(i for i in snap["incidents"] if i["id"] == "INC-1042")
    assert inc["status"] == "awaiting_approval"
    assert inc["priority"] == 94
    assert inc["duplicates"] == 2
    rec = next(r for r in snap["recommendations"] if r["incident"] == "INC-1042")
    assert rec["version"] == 1
    assert rec["state"] == "pending"
    assert rec["recommended_resources"] == ["AMB-02", "RESCUE-01"]
    assert rec["approval_required"] is True

    # Automation actor MUST NOT be allowed to approve
    forbidden_auto = client.post(
        "/integration/v1/demo/step",
        json={"step": "approve"},
        headers={"X-Fixture-Actor": "automation"},
    )
    assert forbidden_auto.status_code == 403

    # Human coordinator approves v1
    approve_v1 = client.post(
        "/integration/v1/demo/incidents/INC-1042/approve",
        json={"version": 1},
    )
    assert approve_v1.status_code == 200
    snap = approve_v1.json()
    assert snap["demoIndex"] == 6
    assert next(i for i in snap["incidents"] if i["id"] == "INC-1042")["status"] == "dispatched"
    assert next(r for r in snap["resources"] if r["id"] == "AMB-02")["status"] == "dispatched"
    assert next(r for r in snap["resources"] if r["id"] == "RESCUE-01")["status"] == "dispatched"

    # Idempotent assignment check does not duplicate dispatch
    asg1 = client.post(
        "/integration/v1/demo/assignments",
        json={"incident_id": "INC-1042", "resource_id": "AMB-02"},
    )
    asg2 = client.post(
        "/integration/v1/demo/assignments",
        json={"incident_id": "INC-1042", "resource_id": "AMB-02"},
    )
    assert asg1.status_code == 200
    assert asg2.status_code == 200
    assert asg1.json()["id"] == asg2.json()["id"]

    # Steps 6..8: block -> replan -> replace
    for expected_idx, step_name in enumerate(["block", "replan", "replace"], start=7):
        resp = client.post(
            "/integration/v1/demo/step",
            json={"step": step_name},
            headers={"X-Fixture-Actor": "automation"},
        )
        assert resp.status_code == 200, resp.text
        snap = resp.json()
        assert snap["demoIndex"] == expected_idx

    inc = next(i for i in snap["incidents"] if i["id"] == "INC-1042")
    assert inc["status"] == "awaiting_replacement"
    assert next(r for r in snap["resources"] if r["id"] == "AMB-02")["eta"] == 24
    assert next(r for r in snap["resources"] if r["id"] == "AMB-05")["status"] == "available"
    rec2 = next(r for r in snap["recommendations"] if r["incident"] == "INC-1042")
    assert rec2["version"] == 2
    assert rec2["state"] == "pending"
    assert rec2["replacementFor"] == "AMB-02"
    assert rec2["recommended_resources"] == ["AMB-05", "RESCUE-01"]

    # Automation actor MUST NOT be allowed to approve replacement
    forbidden_replace = client.post(
        "/integration/v1/demo/step",
        json={"step": "approveReplacement"},
        headers={"X-Fixture-Actor": "automation"},
    )
    assert forbidden_replace.status_code == 403

    # Human coordinator approves replacement v2
    approve_v2 = client.post(
        "/integration/v1/demo/incidents/INC-1042/approve",
        json={"version": 2},
    )
    assert approve_v2.status_code == 200
    snap = approve_v2.json()
    assert snap["demoIndex"] == 10
    assert next(r for r in snap["resources"] if r["id"] == "AMB-02")["status"] == "available"
    assert next(r for r in snap["resources"] if r["id"] == "AMB-05")["status"] == "dispatched"
    assert next(r for r in snap["resources"] if r["id"] == "RESCUE-01")["status"] == "dispatched"
    live_rescue = [
        a
        for a in snap["assignments"]
        if a["incidentId"] == "INC-1042"
        and a["resourceId"] == "RESCUE-01"
        and a["status"] == "dispatched"
    ]
    assert len(live_rescue) == 1

    # Step 10 -> 11: resolve
    resolve_resp = client.post(
        "/integration/v1/demo/step",
        json={"step": "resolve"},
        headers={"X-Fixture-Actor": "automation"},
    )
    assert resolve_resp.status_code == 200
    snap = resolve_resp.json()
    assert snap["demoIndex"] == 11
    assert next(i for i in snap["incidents"] if i["id"] == "INC-1042")["status"] == "resolved"
    for rid in ("AMB-02", "AMB-05", "RESCUE-01"):
        res_state = next(r for r in snap["resources"] if r["id"] == rid)
        assert res_state["status"] == "available"
        assert "assignedIncident" not in res_state


def test_modify_and_reject_recommendation_enforces_rules_and_auth(client, monkeypatch):
    client.post("/integration/v1/demo/reset", json={"for_run": False})

    # Unavailable resource (AMB-03 is dispatched to INC-1036) is rejected
    bad_avail = client.post(
        "/integration/v1/incidents/INC-1042/recommendation/modify",
        json={"version": 1, "recommended_resources": ["AMB-03", "RESCUE-01"]},
    )
    assert bad_avail.status_code == 409
    assert bad_avail.json()["code"] == "RESOURCE_UNAVAILABLE"

    # Missing water rescue coverage is rejected
    bad_cov = client.post(
        "/integration/v1/incidents/INC-1042/recommendation/modify",
        json={"version": 1, "recommended_resources": ["AMB-05"]},
    )
    assert bad_cov.status_code == 422
    assert bad_cov.json()["code"] == "INSUFFICIENT_COVERAGE"

    # Valid modification increments version to 2 and stays pending
    mod_ok = client.post(
        "/integration/v1/incidents/INC-1042/recommendation/modify",
        json={"version": 1, "recommended_resources": ["AMB-05", "RESCUE-02"]},
    )
    assert mod_ok.status_code == 200
    assert mod_ok.json()["version"] == 2
    assert mod_ok.json()["state"] == "pending"
    assert mod_ok.json()["recommended_resources"] == ["AMB-05", "RESCUE-02"]

    # Rejecting replacement leaves existing dispatched responders active
    client.post("/integration/v1/demo/reset", json={"for_run": False})
    client.post("/integration/v1/demo/incidents/INC-1042/approve", json={"version": 1})
    for step_name in ("block", "replan", "replace"):
        client.post("/integration/v1/demo/step", json={"step": step_name})

    rej_resp = client.post(
        "/integration/v1/demo/incidents/INC-1042/reject",
        json={"version": 2, "reason": "Keep existing unit while route clears"},
    )
    assert rej_resp.status_code == 200
    snap = rej_resp.json()
    assert next(i for i in snap["incidents"] if i["id"] == "INC-1042")["status"] == "blocked"
    assert next(r for r in snap["resources"] if r["id"] == "AMB-02")["status"] == "dispatched"
    assert next(r for r in snap["resources"] if r["id"] == "RESCUE-01")["status"] == "dispatched"
    assert next(r for r in snap["resources"] if r["id"] == "AMB-05")["status"] == "available"

    # Verify automation key cannot modify or reject when auth is enabled
    client.post("/integration/v1/demo/reset", json={"for_run": False})
    _with_auth(monkeypatch)
    try:
        auto_mod = client.post(
            "/integration/v1/incidents/INC-1042/recommendation/modify",
            json={"version": 1, "recommended_resources": ["AMB-05", "RESCUE-01"]},
            headers={"X-API-Key": "auto-test-key"},
        )
        assert auto_mod.status_code == 403
        auto_rej = client.post(
            "/integration/v1/incidents/INC-1042/recommendation/reject",
            json={"version": 1, "reason": "Auto reject attempt"},
            headers={"X-API-Key": "auto-test-key"},
        )
        assert auto_rej.status_code == 403
        auto_step_approve = client.post(
            "/integration/v1/demo/step",
            json={"step": "approve"},
            headers={"X-API-Key": "auto-test-key"},
        )
        assert auto_step_approve.status_code == 403
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_n8n_sync_and_translation_endpoints(client):
    client.post("/integration/v1/demo/n8n-sync", json={"workflow": "reset"})
    # Repeated intake sync is idempotent
    s1 = client.post("/integration/v1/demo/n8n-sync", json={"workflow": "intake"})
    s2 = client.post("/integration/v1/demo/n8n-sync", json={"workflow": "intake"})
    assert s1.status_code == 200
    assert s2.status_code == 200
    assert s2.json()["demoIndex"] == 5
    assert sum(1 for i in s2.json()["incidents"] if i["id"] == "INC-1042") == 1

    # Translation works for canonical report and rejects arbitrary unverified text
    ok_tr = client.post(
        "/integration/v1/demo/translate",
        json={
            "id": "RPT-1042",
            "originalText": "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
            "originalLanguage": "en",
            "targetLanguage": "kn",
        },
    )
    assert ok_tr.status_code == 200
    assert ok_tr.json()["translatedLanguage"] == "kn"
    assert ok_tr.json()["translatedText"]

    bad_tr = client.post(
        "/integration/v1/demo/translate",
        json={
            "id": "RPT-UNKNOWN",
            "originalText": "Unverified arbitrary text",
            "originalLanguage": "en",
            "targetLanguage": "hi",
        },
    )
    assert bad_tr.status_code == 422
    assert bad_tr.json()["code"] == "TRANSLATION_UNAVAILABLE"
