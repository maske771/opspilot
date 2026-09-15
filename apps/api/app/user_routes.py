import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import get_current_user, hash_password, require_roles
from .db import get_db
from .models import User, UserRole

router = APIRouter(prefix="/users", tags=["users"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: UserRole


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.STAFF


class UserRoleUpdate(BaseModel):
    role: UserRole


@router.get("", response_model=list[UserRead])
def list_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(User).where(User.organization_id == user.organization_id).order_by(User.email)).all())


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    if payload.role == UserRole.OWNER:
        raise HTTPException(403, "Owner users cannot be created through this endpoint")
    if user.role == UserRole.ADMIN and payload.role == UserRole.ADMIN:
        raise HTTPException(403, "Only the owner can create an admin")

    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(422, "Email cannot be empty")

    item = User(
        organization_id=user.organization_id,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User with this email already exists")
    db.refresh(item)
    return item


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None or target.organization_id != user.organization_id:
        raise HTTPException(404, "User not found")
    if target.id == user.id:
        raise HTTPException(400, "Use another account to change your own role")
    if payload.role == UserRole.OWNER:
        raise HTTPException(403, "Owner role cannot be assigned")
    if user.role == UserRole.ADMIN and target.role == UserRole.ADMIN:
        raise HTTPException(403, "Only the owner can change an admin role")
    if user.role == UserRole.ADMIN and payload.role == UserRole.ADMIN:
        raise HTTPException(403, "Only the owner can assign admin role")

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None or target.organization_id != user.organization_id:
        raise HTTPException(404, "User not found")
    if target.id == user.id:
        raise HTTPException(400, "You cannot delete your own account")
    if target.role == UserRole.OWNER:
        raise HTTPException(403, "Owner user cannot be deleted")
    if user.role == UserRole.ADMIN and target.role == UserRole.ADMIN:
        raise HTTPException(403, "Only the owner can delete an admin")

    db.delete(target)
    db.commit()
