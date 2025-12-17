# backend/app/socket.py
import socketio
from datetime import datetime
import uuid

from sqlalchemy import select

from .db import AsyncSessionLocal
from . import models

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(sid, environ):
    print(f"[socket] connect: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[socket] disconnect: {sid}")


@sio.event
async def join_session(sid, data):
    session_id = data.get("session_id")
    role = data.get("role")

    if not session_id:
        return

    await sio.enter_room(sid, str(session_id))

    if role and role.lower() == "operator":
        await sio.enter_room(sid, "operators")

    print("[socket] join_session:", sid, session_id, role)


@sio.event
async def visitor_message(sid, data):
    """
    data: {
      "session_id": "uuid-string",
      "content": "text...",
      "attachment_url": "/uploads/xxx.png" (optional),
      "bot_option_id": 123 (optional)
    }
    """
    session_id_str = data.get("session_id")
    content = (data.get("content") or "").strip()
    attachment_url = data.get("attachment_url")
    bot_option_id = data.get("bot_option_id")

    if not session_id_str:
        return

    if not content and not attachment_url and not bot_option_id:
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        q_sess = await db.execute(
            select(models.Session).where(models.Session.id == session_uuid)
        )
        sess = q_sess.scalar_one_or_none()
        if not sess:
            return

        option = None
        if bot_option_id is not None:
            q_opt = await db.execute(
                select(models.BotOption).where(
                    models.BotOption.id == int(bot_option_id),
                    models.BotOption.company_id == sess.company_id,
                    models.BotOption.is_active.is_(True),
                )
            )
            option = q_opt.scalar_one_or_none()
            if option:
                content = option.label

        msg = models.Message(
            session_id=session_uuid,
            sender_type=models.SenderType.VISITOR,
            content=content,
            attachment_url=attachment_url,
            created_at=datetime.utcnow(),
            is_read=False,
            read_at=None,
        )
        db.add(msg)

        await db.execute(
            models.Session.__table__.update()
            .where(models.Session.id == session_uuid)
            .values(last_active_at=datetime.utcnow(), status=models.SessionStatus.OPEN)
        )

        await db.commit()
        await db.refresh(msg)

        payload = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "sender_type": "visitor",
            "content": msg.content,
            "attachment_url": msg.attachment_url,
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)
        await sio.emit("new_message", payload, room="operators")

        if option is not None:
            q_setting = await db.execute(
                select(models.BotSetting).where(models.BotSetting.company_id == sess.company_id)
            )
            setting = q_setting.scalar_one_or_none()
            if setting and setting.enabled:
                bot_text = ""

                if option.action == "reply":
                    bot_text = option.reply_text or "承知しました。"
                elif option.action == "link":
                    if option.link_url:
                        bot_text = f"{option.reply_text or 'こちらをご覧ください。'}\n{option.link_url}"
                    else:
                        bot_text = option.reply_text or "こちらをご覧ください。"
                elif option.action == "handoff":
                    bot_text = option.reply_text or "担当者をお呼びします。少々お待ちください。"
                else:
                    bot_text = option.reply_text or "承知しました。"

                bot_msg = models.Message(
                    session_id=session_uuid,
                    sender_type=models.SenderType.SYSTEM,
                    content=bot_text,
                    attachment_url=None,
                    created_at=datetime.utcnow(),
                    is_read=True,
                    read_at=datetime.utcnow(),
                )
                db.add(bot_msg)

                await db.execute(
                    models.Session.__table__.update()
                    .where(models.Session.id == session_uuid)
                    .values(last_active_at=datetime.utcnow())
                )

                await db.commit()
                await db.refresh(bot_msg)

                bot_payload = {
                    "id": str(bot_msg.id),
                    "session_id": str(bot_msg.session_id),
                    "sender_type": "system",
                    "content": bot_msg.content,
                    "attachment_url": bot_msg.attachment_url,
                    "created_at": bot_msg.created_at.isoformat(),
                }

                await sio.emit("new_message", bot_payload, room=session_id_str)
                await sio.emit("new_message", bot_payload, room="operators")

@sio.event
async def operator_message(sid, data):
    """
    data: {
      "session_id": "uuid-string",
      "content": "text...",
      "attachment_url": "/uploads/xxx.png" (optional)
    }
    """
    session_id_str = data.get("session_id")
    content = (data.get("content") or "").strip()
    attachment_url = data.get("attachment_url")

    if not session_id_str:
        return

    if not content and not attachment_url:
        return

    session_uuid = uuid.UUID(session_id_str)

    async with AsyncSessionLocal() as db:
        q = await db.execute(
            select(models.Session).where(models.Session.id == session_uuid)
        )
        sess = q.scalar_one_or_none()
        if not sess:
            return

        msg = models.Message(
            session_id=session_uuid,
            sender_type=models.SenderType.OPERATOR,
            content=content,
            attachment_url=attachment_url,
            created_at=datetime.utcnow(),
            is_read=False,
            read_at=None,
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
            "sender_type": "operator",
            "content": msg.content,
            "attachment_url": msg.attachment_url,
            "created_at": msg.created_at.isoformat(),
        }

        await sio.emit("new_message", payload, room=session_id_str)
        await sio.emit("new_message", payload, room="operators")