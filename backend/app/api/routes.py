# backend/app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from ..db import get_db
from .. import models, schemas

router = APIRouter(prefix="/api")


# ---- セッション作成（訪問者側）----
@router.post("/sessions", response_model=schemas.SessionSummary)
async def create_or_get_session(
    payload: schemas.SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    # すでに open なセッションがあればそれを返す
    q = (
        select(models.Session)
        .where(
            models.Session.visitor_identifier == payload.visitor_identifier,
            models.Session.status == "open",
        )
        .order_by(models.Session.created_at.desc())
    )
    result = await db.execute(q)
    existing = result.scalars().first()
    if existing:
        return existing

    # なければ新規作成
    sess = models.Session(
        visitor_identifier=payload.visitor_identifier,
        visitor_name=payload.visitor_name,
        status="open",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


# ---- セッション一覧（管理画面用）----
@router.get("/sessions", response_model=list[schemas.SessionSummary])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    q = select(models.Session).order_by(models.Session.last_active_at.desc())
    result = await db.execute(q)
    sessions = result.scalars().all()
    return sessions


# ---- メッセージ一覧 ----
@router.get("/sessions/{session_id}/messages", response_model=list[schemas.MessageRead])
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(models.Message)
        .where(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
    )
    result = await db.execute(q)
    messages = result.scalars().all()
    return messages


# ---- メッセージ作成（オペレーター側から）----
@router.post("/sessions/{session_id}/messages", response_model=schemas.MessageRead)
async def post_message(
    session_id: uuid.UUID,
    payload: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    # セッション存在確認
    sess_result = await db.execute(
        select(models.Session).where(models.Session.id == session_id)
    )
    sess = sess_result.scalars().first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    msg = models.Message(
        session_id=session_id,
        sender_type=payload.sender_type,
        content=payload.content,
        created_at=datetime.utcnow(),
    )
    db.add(msg)

    # セッションの最終アクティブ更新
    sess.last_active_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg