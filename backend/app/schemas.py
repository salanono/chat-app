# backend/app/schemas.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import UserRole  # SQLAlchemy側の Enum をそのまま使う


# ---- Token ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- User ----
class UserOut(BaseModel):
    # Pydantic v2: from_attributes=True（旧 orm_mode）
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    role: UserRole
    created_at: datetime
    company_id: Optional[int] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    company_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- Company ----
class CompanyBase(BaseModel):
    name: str


class CompanyRead(CompanyBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- User (管理画面一覧用とかに使う想定) ----
class UserRead(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    role: str
    company_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Sessions ----
class SessionCreate(BaseModel):
    visitor_identifier: str
    visitor_name: Optional[str] = None


class SessionSummary(BaseModel):
    id: UUID
    visitor_name: Optional[str] = None
    status: str
    last_active_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Messages ----
class MessageCreate(BaseModel):
    content: str
    sender_type: str = "OPERATOR"  # 管理画面から送る想定
    attachment_url: Optional[str] = None


class MessageRead(BaseModel):
    id: int
    session_id: UUID
    sender_type: str
    content: str
    created_at: datetime
    attachment_url: Optional[str] = None

    # ★ タイポ修正: from_attibutes → from_attributes
    model_config = ConfigDict(from_attributes=True)

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    company_name: Optional[str] = None