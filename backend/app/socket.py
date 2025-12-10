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


@sio.event
async def connect(sid, environ):
    print(f"[socket] connect: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[socket] disconnect: {sid}")


@sio.event
async def join_session(sid, data):
    """
    data: { "session_id": "...", "role": "operator" or "visitor" }
    """
    session_id = data.get("session_id")
    role = data.get("role")

    if not session_id:
        return

    # セッションごとの room に参加
    await sio.enter_room(sid, str(session_id))

    # ★ オペレーターは共通 room "operators" にも入れる
    if role and role.lower() == "operator":
        await sio.enter_room(sid, "operators")

    print("[socket] join_session:", sid, session_id, role)


@sio.event
async def visitor_message(sid, data):
    print("[socket] visitor_message received:", data)  # ★ まずここで絶対ログ出す

    """
    data: {
      "session_id": "uuid-string",
      "content": "text...",
      "attachment_url": "http://.../xxx.png"
    }
    """
    session_id_str = data.get("session_id")
    content = data.get("content", "") or ""
    attachment_url = data.get("attachment_url")

    # ★ 両方カラだったら捨てる
    if not session_id_str or (not content and not attachment_url):
        print("[socket] visitor_message: empty content & attachment_url, skip")
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        msg = models.Message(
            session_id=session_uuid,
            sender_type=models.SenderType.VISITOR,
            content=content,
            attachment_url=attachment_url,  # ★ ここ超重要
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
                status=models.SessionStatus.OPEN,
            )
        )

        await db.commit()
        await db.refresh(msg)

        payload = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "sender_type": msg.sender_type.value.lower()
            if hasattr(msg.sender_type, "value")
            else str(msg.sender_type).lower(),
            "content": msg.content,
            "attachment_url": msg.attachment_url,  # ★ ここも大事（フロントに返す）
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)
        await sio.emit("new_message", payload, room="operators")

@sio.event
async def operator_message(sid, data):
    """
    data: {
      "session_id": "uuid-string",
      "content": "text...",         // 任意
      "attachment_url": "/uploads/xxx.png"  // 任意
    }
    """
    session_id_str = data.get("session_id")
    content = (data.get("content") or "").strip()
    attachment_url = data.get("attachment_url")

    # ★ テキストも画像も両方空なら無視
    if not session_id_str or (not content and not attachment_url):
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        msg = models.Message(
            session_id=session_uuid,
            sender_type=models.SenderType.OPERATOR,
            content=content,
            attachment_url=attachment_url,
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
            "attachment_url": msg.attachment_url,
            "created_at": msg.created_at.isoformat(),
        }

        # オペレーター・ビジター双方に配信
        await sio.emit("new_message", payload, room=session_id_str)
        await sio.emit("new_message", payload, room="operators")