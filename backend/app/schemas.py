# backend/app/schemas.py
from datetime import datetime
from typing import Optional, List
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
    # 会社名は任意にしておく（必要なら str にして必須にしてもOK）
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
    # 管理画面から送る想定（テキスト必須なら str のままでOK）
    content: str
    sender_type: str = "OPERATOR"
    attachment_url: Optional[str] = None


class MessageRead(BaseModel):
    id: int
    session_id: UUID
    sender_type: str
    # 画像だけのメッセージも扱えるように Optional にしておく
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