# backend/app/schemas.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import UserRole


# ---- Token ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- User ----
class UserOut(BaseModel):
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
    company_name: Optional[str] = None


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


# ---- User ----
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
    sender_type: str = "OPERATOR"
    attachment_url: Optional[str] = None


class MessageRead(BaseModel):
    id: int
    session_id: UUID
    sender_type: str
    content: Optional[str] = None
    attachment_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BotOptionRead(BaseModel):
    id: int
    label: str
    reply_text: str | None
    action: str | None
    link_url: str | None
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BotSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    welcome_message: str
    options: List[BotOptionRead]


class BotSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    welcome_message: Optional[str] = None


class BotOptionCreate(BaseModel):
    label: str
    reply_text: str | None = None
    action: str | None = None
    link_url: str | None = None
    sort_order: int = 0
    is_active: bool = True


class BotOptionUpdate(BaseModel):
    label: str | None = None
    reply_text: str | None = None
    action: str | None = None
    link_url: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None

class ApiKeyRead(BaseModel):
    id: int
    key: str
    name: str | None = None
    is_active: bool
    created_at: datetime

class ApiKeyCreate(BaseModel):
    name: str | None = None

class ApiKeyUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None