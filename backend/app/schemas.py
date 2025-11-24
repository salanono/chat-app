# backend/app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: str
    password: str

# ---- Sessions ----
class SessionCreate(BaseModel):
    visitor_identifier: str
    visitor_name: Optional[str] = None


class SessionSummary(BaseModel):
    id: uuid.UUID
    visitor_identifier: str
    status: str
    last_active_at: datetime

    class Config:
        orm_mode = True


# ---- Messages ----
class MessageCreate(BaseModel):
    content: str
    sender_type: str = "operator"  # とりあえず operator 前提（管理画面から）


class MessageRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    sender_type: str
    content: str
    created_at: datetime

    class Config:
        orm_mode = True