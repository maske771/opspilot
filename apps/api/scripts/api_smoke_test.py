import os
import uuid

import httpx

BASE_URL = os.getenv("OPSPILOT_BASE_URL", "http://127.0.0.1:8000")


def expect(response: httpx.Response, status: int, label: str) -> None:
    if response.status_code != status:
        raise AssertionError(f"{label}: expected {status}, got {response.status_code}: {response.text}")


with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
    response = client.get("/health")
    expect(response, 200, "health")
    assert response.json() == {"status": "ok", "service": "opspilot-api"}

    response = client.get("/openapi.json")
    expect(response, 200, "openapi")
    openapi = response.json()
    for path in (
        "/auth/register",
        "/auth/login",
        "/auth/me",
        "/tickets",
        "/customers",
        "/properties",
        "/units",
        "/channels",
        "/conversations",
        "/webhooks/{provider}/{account_id}",
        "/internal/ai/intake",
    ):
        assert path in openapi["paths"], f"missing route: {path}"

    email = f"ci-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/auth/register",
        json={
            "organization_name": "CI Smoke Organization",
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    expect(response, 201, "register")
    registered = response.json()
    assert registered["email"] == email
    assert registered["role"] == "owner"

    response = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    expect(response, 200, "login")
    token = response.json()["access_token"]
    assert token

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    expect(response, 200, "current user")
    assert response.json()["id"] == registered["id"]

    response = client.post("/internal/ai/intake", json={"text": "There is a water leak"})
    expect(response, 200, "ai intake")
    ai = response.json()
    assert ai["category"] == "plumbing"
    assert ai["priority"] == "high"
    assert 0 < ai["confidence"] <= 1

print("API smoke test: PASS")
