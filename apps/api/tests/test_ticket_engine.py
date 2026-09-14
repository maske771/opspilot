from datetime import datetime, timezone
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import DATABASE_URL, app

client = TestClient(app)

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
PROPERTY_ID = UUID("00000000-0000-0000-0000-000000000100")
UNIT_ID = UUID("00000000-0000-0000-0000-000000000101")


@pytest.fixture(scope="module", autouse=True)
def database_fixtures():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO organizations (id, name)
                VALUES (%s, 'OpsPilot Test Organization')
                ON CONFLICT (id) DO NOTHING""",
                (ORG_ID,),
            )
            cur.execute(
                """INSERT INTO properties (id, organization_id, name, address)
                VALUES (%s, %s, 'Test Villa', 'Test Address')
                ON CONFLICT (id) DO NOTHING""",
                (PROPERTY_ID, ORG_ID),
            )
            cur.execute(
                """INSERT INTO units (id, organization_id, property_id, name)
                VALUES (%s, %s, %s, '304')
                ON CONFLICT (id) DO NOTHING""",
                (UNIT_ID, ORG_ID, PROPERTY_ID),
            )
        conn.commit()

    yield

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tickets WHERE organization_id = %s", (ORG_ID,))
            cur.execute("DELETE FROM units WHERE id = %s", (UNIT_ID,))
            cur.execute("DELETE FROM properties WHERE id = %s", (PROPERTY_ID,))
            cur.execute("DELETE FROM organizations WHERE id = %s", (ORG_ID,))
        conn.commit()


def test_create_high_priority_ticket_with_sla():
    before = datetime.now(timezone.utc)

    response = client.post(
        "/internal/tickets/from-intake",
        json={
            "organization_id": str(ORG_ID),
            "text": "Air conditioner is leaking in room 304. Water on the floor.",
            "language": "en",
            "property_id": str(PROPERTY_ID),
            "unit": "304",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert UUID(body["id"])
    assert body["organization_id"] == str(ORG_ID)
    assert body["property_id"] == str(PROPERTY_ID)
    assert body["unit_id"] == str(UNIT_ID)
    assert body["category"] == "air_conditioning"
    assert body["priority"] == "high"
    assert body["status"] == "open"
    assert body["requires_human_review"] is False

    response_due = datetime.fromisoformat(body["response_due_at"])
    resolution_due = datetime.fromisoformat(body["resolution_due_at"])
    assert response_due >= before
    assert resolution_due >= response_due
    assert (response_due - before).total_seconds() <= 31 * 60
    assert (resolution_due - before).total_seconds() <= 241 * 60


def test_create_critical_ticket_requires_human_review():
    response = client.post(
        "/internal/tickets/from-intake",
        json={
            "organization_id": str(ORG_ID),
            "text": "Emergency: gas smell in room 304",
            "property_id": str(PROPERTY_ID),
            "unit": "304",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "critical"
    assert body["requires_human_review"] is True
    assert body["status"] == "open"


def test_ticket_rejects_unknown_property():
    response = client.post(
        "/internal/tickets/from-intake",
        json={
            "organization_id": str(ORG_ID),
            "text": "AC is broken",
            "property_id": str(UUID("00000000-0000-0000-0000-000000000999")),
            "unit": "304",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "property_id not found in organization"
