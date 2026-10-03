import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import media
from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Organization, Ticket, TicketStatus, User, UserRole
from app.ticket_note_routes import add_note, get_note_attachment, list_notes

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 100


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)


def setup(db_session, status=TicketStatus.IN_PROGRESS):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    tech = User(organization_id=org.id, email=f"tech-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=UserRole.TECHNICIAN)
    ticket = Ticket(organization_id=org.id, title="AC broken", description="x", status=status)
    db_session.add_all([tech, ticket])
    db_session.commit()
    return org, tech, ticket


def test_a_comment_with_photos_is_stored_and_listed(db_session):
    _, tech, ticket = setup(db_session)

    note = add_note(db_session, tech, ticket.id, "  Replaced the capacitor.  ", [JPEG, PNG, WEBP])

    assert note.body == "Replaced the capacitor."
    assert note.author_email == tech.email
    assert [a.content_type for a in note.attachments] == ["image/jpeg", "image/png", "image/webp"]
    listed = list_notes(ticket.id, user=tech, db=db_session)
    assert [n.id for n in listed] == [note.id]


def test_photo_bytes_are_served_back_only_inside_the_organization(db_session):
    _, tech, ticket = setup(db_session)
    _, outsider, _ = setup(db_session)
    note = add_note(db_session, tech, ticket.id, None, [PNG])

    response = get_note_attachment(note.attachments[0].id, user=tech, db=db_session)
    assert response.body == PNG and response.media_type == "image/png"
    with pytest.raises(HTTPException) as exc:
        get_note_attachment(note.attachments[0].id, user=outsider, db=db_session)
    assert exc.value.status_code == 404


def test_a_photo_only_entry_is_allowed_but_an_empty_one_is_not(db_session):
    _, tech, ticket = setup(db_session)

    assert add_note(db_session, tech, ticket.id, "", [JPEG]).body is None
    with pytest.raises(HTTPException) as exc:
        add_note(db_session, tech, ticket.id, "   ", [])
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "photos, status_code",
    [
        ([b"%PDF-1.4 not an image"], 415),
        ([b"GIF89a" + b"0" * 10], 415),
        ([JPEG] * 6, 422),
        ([b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024)], 413),
    ],
)
def test_invalid_photos_are_rejected(db_session, photos, status_code):
    _, tech, ticket = setup(db_session)
    with pytest.raises(HTTPException) as exc:
        add_note(db_session, tech, ticket.id, "x", photos)
    assert exc.value.status_code == status_code


def test_closed_tickets_take_no_new_entries(db_session):
    _, tech, ticket = setup(db_session, status=TicketStatus.CLOSED)
    with pytest.raises(HTTPException) as exc:
        add_note(db_session, tech, ticket.id, "late", [])
    assert exc.value.status_code == 409


def test_tickets_of_another_organization_are_not_found(db_session):
    _, tech, _ = setup(db_session)
    _, _, foreign_ticket = setup(db_session)
    with pytest.raises(HTTPException) as exc:
        add_note(db_session, tech, foreign_ticket.id, "x", [])
    assert exc.value.status_code == 404


def test_multipart_upload_over_http(db_session):
    _, tech, ticket = setup(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {create_access_token(tech)}"}
        response = client.post(
            f"/tickets/{ticket.id}/notes",
            data={"body": "Done, see photos"},
            files=[("photos", ("before.jpg", JPEG, "image/jpeg")), ("photos", ("after.png", PNG, "image/png"))],
            headers=headers,
        )
        assert response.status_code == 201, response.text
        attachment_id = response.json()["attachments"][1]["id"]
        image = client.get(f"/ticket-attachments/{attachment_id}", headers=headers)
        assert image.status_code == 200 and image.content == PNG
    finally:
        app.dependency_overrides.clear()
