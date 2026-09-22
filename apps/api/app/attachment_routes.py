import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .media import read_bytes
from .models import MessageAttachment, User

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}")
def get_attachment(attachment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attachment = db.get(MessageAttachment, attachment_id)
    if attachment is None or attachment.organization_id != user.organization_id:
        raise HTTPException(404, "Attachment not found")
    try:
        content = read_bytes(attachment.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, "Attachment file missing on disk")
    return Response(content=content, media_type=attachment.content_type)
