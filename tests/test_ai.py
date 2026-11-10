from unittest.mock import patch
from fastapi.testclient import TestClient
from ai.main import app, ExtractedIncident

client = TestClient(app)

def test_health_check():
    response = client.get("/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

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
        "confidence_score": 0.95
    }
    response = client.post("/ai/score-incident", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["priority_score"] >= 85
    assert data["risk_level"] == "Critical"

@patch("ai.main.ChatGoogleGenerativeAI")
def test_extract_incident_mocked(mock_chat_ai):
    mock_structured_llm = mock_chat_ai.return_value.with_structured_output.return_value
    
    expected_result = ExtractedIncident(
        location="Andheri West",
        incident_type="flood_rescue",
        people_affected=4,
        vulnerable_groups=["elderly"],
        medical_urgency=True,
        severity_score=4,
        time_sensitivity_hours=2.5,
        environmental_threat=False,
        confidence_score=0.92
    )
    
    # THE FIX: Tell the mock to return our result regardless of how LangChain triggers it
    mock_structured_llm.return_value = expected_result  # Handles __call__
    mock_structured_llm.invoke.return_value = expected_result  # Handles .invoke()

    payload = {"text": "Pani bhar gaya hai Andheri West mein, please help"}
    response = client.post("/ai/extract-incident", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Andheri West"
    assert data["incident_type"] == "flood_rescue"