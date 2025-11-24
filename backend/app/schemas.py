from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_type: str
    content: str
    created_at: datetime

    class Config:
        orm_mode = True


class SessionResponse(BaseModel):
    id: uuid.UUID
    visitor_identifier: str
    status: str
    last_active_at: datetime

    class Config:
        orm_mode = True