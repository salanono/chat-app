# backend/app/models.py
from datetime import datetime
import uuid
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Enum as SAEnum,
    Text,
    text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship  # ⭐ 追加

from .db import Base


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


class SessionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SenderType(str, Enum):
    VISITOR = "VISITOR"
    OPERATOR = "OPERATOR"
    SYSTEM = "SYSTEM"


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    users = relationship(
        "User",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    sessions = relationship(
        "Session",
        back_populates="company",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    role = Column(
        SAEnum(UserRole, name="user_roles"),
        nullable=False,
        default=UserRole.ADMIN,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ★ どの会社に属しているか
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company = relationship("Company", back_populates="users")

    # このユーザーがオーナーになっているセッション
    owned_sessions = relationship("Session", back_populates="owner_user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visitor_identifier = Column(String(255), nullable=False, index=True)
    visitor_name = Column(String(255), nullable=True)
    status = Column(
        SAEnum(SessionStatus, name="session_statuses"),
        nullable=False,
        default=SessionStatus.OPEN,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ★ どの会社のセッションか
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company = relationship("Company", back_populates="sessions")

    # このセッションを持っているオペレーター（User）
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner_user = relationship("User", back_populates="owned_sessions")

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    sender_type = Column(SAEnum(SenderType, name="sender_types"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    attachment_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_read = Column(Boolean, nullable=False, server_default=text("false"))
    read_at = Column(DateTime(timezone=False), nullable=True)

    session = relationship("Session", back_populates="messages")

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="api_keys")
    company = relationship("Company", backref="api_keys")