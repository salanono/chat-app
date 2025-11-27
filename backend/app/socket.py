# backend/app/socket.py
import socketio
from datetime import datetime
import uuid

from .db import AsyncSessionLocal
from . import models
from sqlalchemy import insert

# 非同期サーバー
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
)


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
            sender_type=models.SenderType.VISITOR,
            content=content,
            created_at=datetime.utcnow(),
            is_read=False,
            read_at=None,
        )
        db.add(msg)

        await db.execute(
            models.Session.__table__.update()
            .where(models.Session.id == session_uuid)
            .values(
                last_active_at=datetime.utcnow(),
                status=models.SessionStatus.OPEN,  # クローズしていても自動で再オープン
            )
        )

        await db.commit()
        await db.refresh(msg)

        payload = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            # ★ フロント用には小文字を渡す
            "sender_type": msg.sender_type.value.lower()
            if hasattr(msg.sender_type, "value")
            else str(msg.sender_type).lower(),
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
            sender_type=models.SenderType.OPERATOR,
            content=content,
            created_at=datetime.utcnow(),
            is_read=True,
            read_at=datetime.utcnow(),
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
            # フロント用に小文字で渡す（"operator"）
            "sender_type": msg.sender_type.value.lower()
            if hasattr(msg.sender_type, "value")
            else str(msg.sender_type).lower(),
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)