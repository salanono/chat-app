# backend/app/socket.py
import socketio
from datetime import datetime
import uuid

from .db import AsyncSessionLocal
from . import models

# 非同期サーバー
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
)

# ここでは ASGIApp は作らない！


@sio.event
async def connect(sid, environ):
    print(f"[socket] connect: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[socket] disconnect: {sid}")


@sio.event
async def join_session(sid, data):
    """
    data: { "session_id": "uuid-string", "role": "visitor" | "operator" }
    """
    session_id = str(data.get("session_id"))
    role = data.get("role", "visitor")

    print(f"[socket] {sid} join_session: {session_id}, role={role}")
    await sio.enter_room(sid, session_id)


@sio.event
async def visitor_message(sid, data):
    """
    data: { "session_id": "uuid-string", "content": "text..." }
    """
    session_id_str = data.get("session_id")
    content = data.get("content", "")

    if not session_id_str or not content:
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        msg = models.Message(
            session_id=session_uuid,
            sender_type="visitor",
            content=content,
            created_at=datetime.utcnow(),
        )
        db.add(msg)

        await db.execute(
            models.Session.__table__.update()
            .where(models.Session.id == session_uuid)
            .values(last_active_at=datetime.utcnow())
        )

        await db.commit()
        await db.refresh(msg)

        payload = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "sender_type": msg.sender_type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)


@sio.event
async def operator_message(sid, data):
    """
    data: { "session_id": "uuid-string", "content": "text..." }
    """
    session_id_str = data.get("session_id")
    content = data.get("content", "")

    if not session_id_str or not content:
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        msg = models.Message(
            session_id=session_uuid,
            sender_type="operator",
            content=content,
            created_at=datetime.utcnow(),
        )
        db.add(msg)

        await db.execute(
            models.Session.__table__.update()
            .where(models.Session.id == session_uuid)
            .values(last_active_at=datetime.utcnow())
        )

        await db.commit()
        await db.refresh(msg)

        payload = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "sender_type": msg.sender_type,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)