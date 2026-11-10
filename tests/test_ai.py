import os
from fastapi.testclient import TestClient
from ai.main import app, provider_client

client = TestClient(app)


def test_health_check_without_and_with_mocked_provider():
    old_google = os.environ.pop("GOOGLE_API_KEY", None)
    old_gemini = os.environ.pop("GEMINI_API_KEY", None)
    try:
        provider_client.set_mock_reachable(None)
        response = client.get("/ai/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["api_key_configured"] is False

        os.environ["GEMINI_API_KEY"] = "test-synthetic-key"
        provider_client.set_mock_reachable(True)
        response_healthy = client.get("/ai/health")
        assert response_healthy.status_code == 200
        healthy_data = response_healthy.json()
        assert healthy_data["status"] == "healthy"
        assert healthy_data["provider_reachable"] is True
    finally:
        provider_client.set_mock_reachable(None)
        if old_google is not None:
            os.environ["GOOGLE_API_KEY"] = old_google
        else:
            os.environ.pop("GOOGLE_API_KEY", None)
        if old_gemini is not None:
            os.environ["GEMINI_API_KEY"] = old_gemini
        else:
            os.environ.pop("GEMINI_API_KEY", None)


def test_score_incident_critical_override():
    payload = {
        "location": "MG Road",
        "incident_type": "building_collapse",
        "people_affected": 10,
        "vulnerable_groups": ["children", "elderly"],
        "medical_urgency": True,
        "severity_score": 5,
        "environmental_threat": True,
        "time_sensitivity_hours": 1.0,
        "confidence_score": 0.95,
    }
    response = client.post("/ai/score-incident", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["priority_score"] >= 85
    assert data["risk_level"] == "Critical"


def test_extract_incident_mocked():
    async def mock_extract(_text: str):
        return {
            "location": "Andheri West",
            "incident_type": "flood_rescue",
            "people_affected": 4,
            "vulnerable_groups": ["elderly"],
            "medical_urgency": True,
            "severity_score": 4,
            "time_sensitivity_hours": 2.5,
            "environmental_threat": False,
            "confidence_score": 0.92,
        }

    provider_client.set_mock_extractor(mock_extract)
    try:
        payload = {"text": "Pani bhar gaya hai Andheri West mein, please help"}
        response = client.post("/ai/extract-incident", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Andheri West"
        assert data["incident_type"] == "flood_rescue"
    finally:
        provider_client.set_mock_extractor(None)
