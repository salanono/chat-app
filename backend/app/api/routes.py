# backend/app/api/routes.py
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,   # ★ 追加
)
from ..db import get_db

router = APIRouter(prefix="/api")

# -----------------------------
# 認証: 新規登録
# POST /api/auth/register
# -----------------------------
@router.post("/auth/register", response_model=schemas.LoginResponse)
async def register(payload: schemas.RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    body 例:
    {
      "email": "foo@example.com",
      "password": "password123",
      "display_name": "Foo Bar",
      "company_name": "Foo Inc."   // 任意。指定があればその会社を使う/作る
    }
    """

    # 既に同じメールが存在するかチェック
    result_user = await db.execute(
        select(models.User).where(models.User.email == payload.email)
    )
    existing_user = result_user.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このメールアドレスは既に登録されています",
        )

    # company_name が指定されていれば、その会社を検索 or 作成
    company = None
    if payload.company_name:
        result_company = await db.execute(
            select(models.Company).where(models.Company.name == payload.company_name)
        )
        company = result_company.scalars().first()
        if not company:
            company = models.Company(name=payload.company_name)
            db.add(company)
            await db.flush()  # company.id を確定
    else:
        # 無指定なら既存の会社を1件拾う or Default Company を作る
        result_company = await db.execute(select(models.Company))
        company = result_company.scalars().first()
        if not company:
            company = models.Company(name="Default Company")
            db.add(company)
            await db.flush()

    # ユーザー作成（最初のユーザー想定なので ADMIN にしておく）
    user = models.User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        display_name=payload.display_name,
        role=models.UserRole.ADMIN,
        company_id=company.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # そのままログインさせる（LoginResponse で返す）
    token = create_access_token({"sub": user.email})
    return schemas.LoginResponse(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
    )


# -----------------------------
# 認証: ログイン
# POST /api/auth/login
# -----------------------------
@router.post("/auth/login", response_model=schemas.LoginResponse)
async def login(payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    # ユーザー認証
    user = await authenticate_user(payload.email, payload.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user.email})

    return schemas.LoginResponse(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
    )


# -----------------------------
# 認証: 自分自身の情報取得
# GET /api/auth/me
# -----------------------------
@router.get("/auth/me", response_model=schemas.UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)):
    return schemas.UserOut.model_validate(current_user)


# -----------------------------
# ウィジェット用: セッション作成 or 取得
# POST /api/sessions
# -----------------------------
@router.post("/sessions")
async def create_or_get_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    body:
    {
      "visitor_identifier": "visitor_xxx",
      "owner_id": 1,          // 管理画面ユーザーID (int)
      "visitor_name": "Foo"   // 任意
    }
    """
    visitor_identifier = payload.get("visitor_identifier")
    owner_id = payload.get("owner_id")
    visitor_name = payload.get("visitor_name")

    if not visitor_identifier or owner_id is None:
        raise HTTPException(
            status_code=400,
            detail="visitor_identifier と owner_id は必須です",
        )

    try:
        owner_id_int = int(owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="owner_id が不正です")

    result_user = await db.execute(
        select(models.User).where(models.User.id == owner_id_int)
    )
    owner = result_user.scalars().first()
    if not owner:
        raise HTTPException(status_code=404, detail="owner user not found")

    result_session = await db.execute(
        select(models.Session).where(
            models.Session.visitor_identifier == visitor_identifier,
            models.Session.owner_user_id == owner.id,
            models.Session.status == models.SessionStatus.OPEN,
        )
    )
    session = result_session.scalars().first()

    now = datetime.utcnow()

    if not session:
        session = models.Session(
            visitor_identifier=visitor_identifier,
            visitor_name=visitor_name,
            status=models.SessionStatus.OPEN,
            created_at=now,
            last_active_at=now,
            owner_user_id=owner.id,
            company_id=owner.company_id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
    else:
        session.last_active_at = now
        if visitor_name and not session.visitor_name:
            session.visitor_name = visitor_name
        await db.commit()
        await db.refresh(session)

    return {"id": str(session.id)}


# -----------------------------
# 管理画面: ログイン中ユーザーのセッション一覧
# GET /api/sessions
# -----------------------------
@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = (
        select(models.Session)
        .where(
            models.Session.owner_user_id == current_user.id,
            models.Session.company_id == current_user.company_id,
        )
        .order_by(models.Session.last_active_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "visitor_name": s.visitor_name,
            "visitor_identifier": s.visitor_identifier,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
        }
        for s in sessions
    ]


# -----------------------------
# 管理画面: セッションのメッセージ一覧
# GET /api/sessions/{session_id}/messages
# -----------------------------
@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id が不正です")

    result = await db.execute(
        select(models.Session).where(models.Session.id == session_uuid)
    )
    session = result.scalars().first()

    if (
        not session
        or session.owner_user_id != current_user.id
        or session.company_id != current_user.company_id
    ):
        raise HTTPException(status_code=404, detail="Session not found")

    result_msg = await db.execute(
        select(models.Message)
        .where(models.Message.session_id == session.id)
        .order_by(models.Message.created_at.asc())
    )
    messages = result_msg.scalars().all()

    return [
        {
            "id": m.id,
            "session_id": str(m.session_id),
            "sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type),
            "sender_id": m.sender_id,
            "content": m.content,
            "attachment_url": m.attachment_url,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# -----------------------------
# 管理画面: メッセージ送信（オペレーター→ビジター）
# POST /api/sessions/{session_id}/messages
# -----------------------------
@router.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: str,
    payload: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id が不正です")

    result = await db.execute(
        select(models.Session).where(models.Session.id == session_uuid)
    )
    session = result.scalars().first()

    if (
        not session
        or session.owner_user_id != current_user.id
        or session.company_id != current_user.company_id
    ):
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.utcnow()

    try:
        sender_type_enum = models.SenderType(payload.sender_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="sender_type が不正です")

    msg = models.Message(
        session_id=session.id,
        sender_type=sender_type_enum,
        sender_id=current_user.id if sender_type_enum == models.SenderType.OPERATOR else None,
        content=payload.content,
        attachment_url=payload.attachment_url,
        created_at=now,
    )
    session.last_active_at = now

    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return {
        "id": msg.id,
        "session_id": str(msg.session_id),
        "sender_type": msg.sender_type.value,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "attachment_url": msg.attachment_url,
        "created_at": msg.created_at.isoformat(),
    }