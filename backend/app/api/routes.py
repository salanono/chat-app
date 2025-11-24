from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from ..db import get_db
from .. import models, schemas
from ..auth import (
    authenticate_user,
    create_access_token,
    # get_current_user  ← いったん使わないのでコメントアウトでもOK
)

router = APIRouter(prefix="/api")


# ---------- 認証系 ----------

@router.post("/auth/login", response_model=schemas.Token)
async def login(payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(payload.email, payload.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


# ---------- セッション系 ----------

# 訪問者側：セッション作成 or 既存取得（認証なし）
@router.post("/sessions", response_model=schemas.SessionSummary)
async def create_or_get_session(
    payload: schemas.SessionCreate,
    db: AsyncSession = Depends(get_db),
):
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

    sess = models.Session(
        visitor_identifier=payload.visitor_identifier,
        visitor_name=payload.visitor_name,
        status="open",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


# 管理画面：セッション一覧（いったん認証なしにする）
@router.get("/sessions", response_model=list[schemas.SessionSummary])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    # current_user: models.User = Depends(get_current_user),  ← 一旦外す
):
    q = select(models.Session).order_by(models.Session.last_active_at.desc())
    result = await db.execute(q)
    sessions = result.scalars().all()
    return sessions


# 誰でも：メッセージ一覧（認証なし）
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


# メッセージ送信（オペレーター想定だけど、いったん認証なし）
@router.post("/sessions/{session_id}/messages", response_model=schemas.MessageRead)
async def post_message(
    session_id: uuid.UUID,
    payload: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
    # current_user: models.User = Depends(get_current_user),  ← 一旦外す
):
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

    sess.last_active_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg