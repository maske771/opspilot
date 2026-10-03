import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .audit import record_ticket
from .auth import get_current_user
from .db import get_db
from .media import read_bytes, save_bytes
from .models import Ticket, TicketNote, TicketNoteAttachment, TicketStatus, User

router = APIRouter(tags=["ticket-notes"])

MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_BODY_CHARS = 5000


class NoteAttachmentRead(BaseModel):
    id: uuid.UUID
    content_type: str


class TicketNoteRead(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID | None
    author_email: str | None
    body: str | None
    created_at: datetime
    attachments: list[NoteAttachmentRead]


def image_type(content: bytes) -> tuple[str, str] | None:
    """(content type, extension) from the file's own bytes — the client's filename and declared
    type aren't trusted."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _get_ticket(db: Session, user: User, ticket_id: uuid.UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != user.organization_id:
        raise HTTPException(404, "Ticket not found")
    return ticket


def _read(db: Session, note: TicketNote) -> TicketNoteRead:
    author = db.get(User, note.author_id) if note.author_id else None
    return TicketNoteRead(
        id=note.id,
        author_id=note.author_id,
        author_email=author.email if author else None,
        body=note.body,
        created_at=note.created_at,
        attachments=[NoteAttachmentRead(id=a.id, content_type=a.content_type) for a in note.attachments],
    )


def add_note(db: Session, user: User, ticket_id: uuid.UUID, body: str | None, photos: list[bytes]) -> TicketNoteRead:
    ticket = _get_ticket(db, user, ticket_id)
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(409, "The ticket is closed")
    body = (body or "").strip() or None
    if body is None and not photos:
        raise HTTPException(422, "Add a comment or at least one photo")
    if body is not None and len(body) > MAX_BODY_CHARS:
        raise HTTPException(422, f"A comment can be at most {MAX_BODY_CHARS} characters")
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(422, f"At most {MAX_PHOTOS} photos per entry")
    typed = []
    for content in photos:
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "A photo can be at most 10 MB")
        kind = image_type(content)
        if kind is None:
            raise HTTPException(415, "Only JPEG, PNG or WebP photos are accepted")
        typed.append((content, kind))

    note = TicketNote(organization_id=ticket.organization_id, ticket_id=ticket.id, author_id=user.id, body=body)
    db.add(note)
    db.flush()
    for content, (content_type, extension) in typed:
        path = save_bytes(ticket.organization_id, content, extension)
        note.attachments.append(TicketNoteAttachment(organization_id=ticket.organization_id, storage_path=path, content_type=content_type))
    record_ticket(db, ticket, user, "note_added", {"note_id": note.id, "photos": len(typed)})
    db.commit()
    db.refresh(note)
    return _read(db, note)


@router.get("/tickets/{ticket_id}/notes", response_model=list[TicketNoteRead])
def list_notes(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _get_ticket(db, user, ticket_id)
    notes = db.scalars(
        select(TicketNote).options(selectinload(TicketNote.attachments)).where(TicketNote.ticket_id == ticket.id).order_by(TicketNote.created_at)
    ).all()
    return [_read(db, note) for note in notes]


@router.post("/tickets/{ticket_id}/notes", response_model=TicketNoteRead, status_code=201)
async def create_note(
    ticket_id: uuid.UUID,
    body: str = Form(default=""),
    photos: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contents = []
    for photo in photos[: MAX_PHOTOS + 1]:  # one extra so add_note can report "too many"
        contents.append(await photo.read(MAX_PHOTO_BYTES + 1))
    return add_note(db, user, ticket_id, body, contents)


@router.get("/ticket-attachments/{attachment_id}")
def get_note_attachment(attachment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attachment = db.get(TicketNoteAttachment, attachment_id)
    if attachment is None or attachment.organization_id != user.organization_id:
        raise HTTPException(404, "Attachment not found")
    try:
        content = read_bytes(attachment.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, "Attachment file missing on disk")
    return Response(content=content, media_type=attachment.content_type)
