def test_health_reports_status_and_db_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert "environment" in body
