from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_intake_classifies_ac_request():
    response = client.post(
        "/internal/ai/intake",
        json={"text": "AC is leaking in room 304", "unit": "304"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "maintenance_request"
    assert body["category"] == "air_conditioning"
    assert body["location"]["unit"] == "304"
    assert body["suggested_priority"] == "high"


def test_intake_flags_critical_request():
    response = client.post(
        "/internal/ai/intake",
        json={"text": "Emergency: gas smell in the apartment"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggested_priority"] == "critical"
    assert body["requires_human_review"] is True
