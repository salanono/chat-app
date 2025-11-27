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

    - session_id があれば、そのセッション専用 room に参加
    - role が "operator" なら、共通 room "operators" にも参加
    """
    session_id = data.get("session_id")
    role = data.get("role")

    # ★ session_id があるときだけ、そのセッションの room に入る
    if session_id:
        await sio.enter_room(sid, str(session_id))

    # ★ オペレーターは必ず共通 room "operators" に参加させる
    if role and role.lower() == "operator":
        await sio.enter_room(sid, "operators")

    print("[socket] join_session:", sid, session_id, role)


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

        # セッションの最終アクティブ時間を更新 & クローズでも OPEN に戻す
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
            # フロント用には小文字で渡す（"visitor"）
            "sender_type": (
                msg.sender_type.value.lower()
                if hasattr(msg.sender_type, "value")
                else str(msg.sender_type).lower()
            ),
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

        # ★ そのセッションの room へ
        await sio.emit("new_message", payload, room=session_id_str)

        # ★ さらに、全オペレーターがいる "operators" ルームへも送る
        #    → Admin.vue 側の `new_message` ハンドラで、該当セッションが
        #       なければ `fetchSessions()` してくれるので、新規セッションも反映される
        await sio.emit("new_message", payload, room="operators")


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
            "sender_type": (
                msg.sender_type.value.lower()
                if hasattr(msg.sender_type, "value")
                else str(msg.sender_type).lower()
            ),
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

        # オペレーター・ビジター双方に配信
        await sio.emit("new_message", payload, room=session_id_str)
        # 必要であれば、他のオペレーターにも通知したいのであれば以下も有効のままでOK
        await sio.emit("new_message", payload, room="operators")