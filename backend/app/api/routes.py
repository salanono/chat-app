# backend/app/api/routes.py
from datetime import datetime
from uuid import UUID
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func, update
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
# 埋め込み用 API キー取得（なければ自動発行）
# GET /api/embed-key
# -----------------------------
@router.get("/embed-key")
async def get_or_create_embed_key(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 既存の有効なキーを探す
    result = await db.execute(
        select(models.ApiKey).where(
            models.ApiKey.user_id == current_user.id,
            models.ApiKey.company_id == current_user.company_id,
            models.ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalars().first()

    # なければ新しく発行
    if not api_key:
        key_str = secrets.token_hex(32)  # 64文字のランダムキー
        api_key = models.ApiKey(
            key=key_str,
            user_id=current_user.id,
            company_id=current_user.company_id,
            is_active=True,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

    return {"api_key": api_key.key}

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
# 自分の所属会社情報取得
# GET /api/company/me
# -----------------------------
@router.get("/company/me")
async def get_my_company(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # company_id が無い場合
    if not current_user.company_id:
        raise HTTPException(status_code=404, detail="Company not found")

    result = await db.execute(
        select(models.Company).where(models.Company.id == current_user.company_id)
    )
    company = result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "id": company.id,
        "name": company.name,
    }

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
      // どちらか一方を指定:
      // "owner_id": 1,
      // "api_key": "xxxxx",
      "visitor_name": "Foo"   // 任意
    }
    """
    visitor_identifier = payload.get("visitor_identifier")
    owner_id = payload.get("owner_id")
    api_key = payload.get("api_key")
    visitor_name = payload.get("visitor_name")

    if not visitor_identifier:
        raise HTTPException(
            status_code=400,
            detail="visitor_identifier は必須です",
        )

    # --- owner を決めるロジック ---
    owner = None

    # ① api_key があればそちらを優先
    if api_key:
        result_api = await db.execute(
            select(models.ApiKey).where(
                models.ApiKey.key == api_key,
                models.ApiKey.is_active.is_(True),
            )
        )
        api_obj = result_api.scalars().first()
        if not api_obj:
            raise HTTPException(
                status_code=400,
                detail="api_key が不正か無効です",
            )

        result_user = await db.execute(
            select(models.User).where(models.User.id == api_obj.user_id)
        )
        owner = result_user.scalars().first()
        if not owner:
            raise HTTPException(
                status_code=400,
                detail="api_key に紐づくユーザーが存在しません",
            )

    # ② api_key が無い場合は owner_id を使う
    else:
        if owner_id is None:
            raise HTTPException(
                status_code=400,
                detail="owner_id または api_key を指定してください",
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

    # ここまで来たら owner は必ず存在する
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
    # ★ ここを変更：
    #   「メッセージが1件以上あるセッションだけ」取得するようにする
    stmt = (
        select(models.Session)
        .join(models.Message, models.Session.id == models.Message.session_id)
        .where(
            models.Session.owner_user_id == current_user.id,
            models.Session.company_id == current_user.company_id,
            models.Session.handoff_requested.is_(True),   # ← これ追加
        )
        .distinct()  # 同じセッションが複数メッセージで重複しないように
        .order_by(models.Session.last_active_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    # 未読数をまとめて集計
    session_ids = [s.id for s in sessions]
    if session_ids:
        unread_stmt = (
            select(
                models.Message.session_id,
                func.count(models.Message.id).label("cnt"),
            )
            .where(
                models.Message.session_id.in_(session_ids),
                models.Message.sender_type == models.SenderType.VISITOR,
                models.Message.is_read.is_(False),
            )
            .group_by(models.Message.session_id)
        )
        unread_result = await db.execute(unread_stmt)
        unread_map = {row.session_id: row.cnt for row in unread_result}
    else:
        unread_map = {}

    return [
        {
            "id": str(s.id),
            "visitor_name": s.visitor_name,
            "visitor_identifier": s.visitor_identifier,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
            "unread_count": int(unread_map.get(s.id, 0)),
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

    # ビジターからのメッセージを既読に
    await db.execute(
        models.Message.__table__.update()
        .where(
            models.Message.session_id == session.id,
            models.Message.sender_type == models.SenderType.VISITOR,
            models.Message.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.utcnow())
    )
    await db.commit()

    return [
        {
            "id": m.id,
            "session_id": str(m.session_id),
            "sender_type": m.sender_type.value
            if hasattr(m.sender_type, "value")
            else str(m.sender_type),
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


# =============================
# ウィジェット用: セッション作成 or 取得
# POST /api/widget/sessions
# =============================
@router.post("/widget/sessions")
async def widget_create_or_get_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    body:
    {
      "visitor_identifier": "visitor_xxx",
      "owner_id": 2,              # 任意: 管理画面側の user.id
      "visitor_name": "Foo"       # 任意
    }

    owner_id が指定されていればそのユーザーに紐づける。
    指定されていなければ「最初の ADMIN ユーザー」に紐づける（従来動作）。
    """
    visitor_identifier = payload.get("visitor_identifier")
    owner_id_raw = payload.get("owner_id")
    visitor_name = payload.get("visitor_name")

    if not visitor_identifier:
        raise HTTPException(
            status_code=400,
            detail="visitor_identifier は必須です",
        )

    # --- owner を決める ---
    # 1) owner_id が来ていればそれを優先
    # 2) なければ最初の ADMIN ユーザーを使う（従来の挙動）
    owner = None
    if owner_id_raw is not None:
        try:
            owner_id_int = int(owner_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="owner_id が不正です",
            )

        result_user = await db.execute(
            select(models.User).where(models.User.id == owner_id_int)
        )
        owner = result_user.scalars().first()
        if not owner:
            raise HTTPException(
                status_code=404,
                detail="指定された owner ユーザーが存在しません",
            )
    else:
        # ★ フォールバック: 最初の ADMIN を使う
        result_user = await db.execute(
            select(models.User).where(models.User.role == models.UserRole.ADMIN)
        )
        owner = result_user.scalars().first()
        if not owner:
            raise HTTPException(
                status_code=500,
                detail="ADMIN ユーザーが存在しません",
            )

    # 同じ visitor_identifier & owner_user_id で OPEN を再利用
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
            company_id=owner.company_id,  # owner の会社に紐づけ
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

# =============================
# ウィジェット用: セッションのメッセージ一覧
# GET /api/widget/sessions/{session_id}/messages
# =============================
@router.get("/widget/sessions/{session_id}/messages")
async def widget_get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id が不正です")

    # セッションが存在するかだけ確認（会社・ユーザー制御はここではしない）
    result_session = await db.execute(
        select(models.Session).where(models.Session.id == session_uuid)
    )
    session = result_session.scalars().first()
    if not session:
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
            "sender_type": m.sender_type.value
            if hasattr(m.sender_type, "value")
            else str(m.sender_type),
            "sender_id": m.sender_id,
            "content": m.content,
            "attachment_url": m.attachment_url,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# -----------------------------
# 管理画面: セッションをクローズ
# POST /api/sessions/{session_id}/close
# -----------------------------
@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    # セッション取得
    q = await db.execute(
        select(models.Session).where(models.Session.id == session_id)
    )
    session = q.scalar_one_or_none()
    if (
        not session
        or session.owner_user_id != user.id
        or session.company_id != user.company_id
    ):
        raise HTTPException(status_code=404, detail="Session not found")

    # ステータス変更
    session.status = models.SessionStatus.CLOSED
    await db.commit()
    return {"status": "ok"}

@router.post("/widget/sessions/{session_id}/handoff")
async def widget_request_handoff(
    session_id: str,
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # api_key 検証
    q = await db.execute(
        select(models.ApiKey).where(
            models.ApiKey.key == api_key,
            models.ApiKey.is_active.is_(True),
        )
    )
    key = q.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=401, detail="invalid api_key")

    # session 検証
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="session_id が不正です")

    q2 = await db.execute(select(models.Session).where(models.Session.id == session_uuid))
    session = q2.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # ★ 会社一致チェック（これ超重要）
    if session.company_id != key.company_id:
        raise HTTPException(status_code=403, detail="forbidden")

    now = datetime.utcnow()
    session.handoff_requested = True
    session.handoff_requested_at = now
    session.last_active_at = now

    await db.commit()
    return {"ok": True}

@router.get("/embed/{owner_id}.js")
async def get_embed_script(owner_id: int):
    """
    会社ごとに変えたい「埋め込みスクリプト」を返すエンドポイント。
    例:
      <script src="http://localhost:8000/api/embed/1.js" async></script>

    owner_id ごとに iframe の URL に owner_id を埋め込んでいる。
    """
    js = f"""
    (function() {{
      var d = document;

      function init() {{
        // すでに iframe があれば何もしない
        if (d.getElementById('chat-widget-frame')) return;

        // iframe を作成
        var iframe = d.createElement('iframe');
        iframe.id = 'chat-widget-frame';
        iframe.src = 'http://localhost:5173/widget?owner_id={owner_id}';
        iframe.style.position = 'fixed';
        iframe.style.bottom = '20px';
        iframe.style.right = '20px';
        iframe.style.width = '360px';
        iframe.style.height = '520px';
        iframe.style.border = 'none';
        iframe.style.zIndex = '999999';
        iframe.style.borderRadius = '16px';
        iframe.style.boxShadow = '0 10px 30px rgba(15,23,42,0.25)';
        iframe.allow = 'clipboard-read; clipboard-write';

        d.body.appendChild(iframe);
      }}

      if (d.readyState === 'complete' || d.readyState === 'interactive') {{
        init();
      }} else {{
        d.addEventListener('DOMContentLoaded', init);
      }}
    }})();
    """.strip()

    return Response(content=js, media_type="application/javascript")

# -------------------------
# 管理画面: Bot設定取得
# GET /api/bot/settings
# -------------------------
@router.get("/bot/settings", response_model=schemas.BotSettingRead)
async def get_bot_settings(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.BotSetting).where(models.BotSetting.company_id == current_user.company_id)
    )
    setting = q.scalar_one_or_none()

    if not setting:
        # 初回は自動作成
        setting = models.BotSetting(company_id=current_user.company_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

    # options も返す（relationship lazy="selectin" 前提）
    return schemas.BotSettingRead(
        enabled=setting.enabled,
        welcome_message=setting.welcome_message or "",
        options=setting.options or [],
    )


# -------------------------
# 管理画面: Bot設定更新
# PUT /api/bot/settings
# -------------------------
@router.put("/bot/settings", response_model=schemas.BotSettingRead)
async def update_bot_settings(
    payload: schemas.BotSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.BotSetting).where(models.BotSetting.company_id == current_user.company_id)
    )
    setting = q.scalar_one_or_none()
    if not setting:
        setting = models.BotSetting(company_id=current_user.company_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

    if payload.enabled is not None:
        setting.enabled = payload.enabled
    if payload.welcome_message is not None:
        setting.welcome_message = payload.welcome_message

    setting.updated_at = models.datetime.utcnow() if hasattr(models, "datetime") else __import__("datetime").datetime.utcnow()

    await db.commit()
    await db.refresh(setting)

    return schemas.BotSettingRead(
        enabled=setting.enabled,
        welcome_message=setting.welcome_message or "",
        options=setting.options or [],
    )


# -------------------------
# 管理画面: 選択肢追加
# POST /api/bot/options
# -------------------------
@router.post("/bot/options", response_model=schemas.BotOptionRead)
async def create_bot_option(
    payload: schemas.BotOptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    # 会社の bot_settings を取得（なければ作成）
    q = await db.execute(
        select(models.BotSetting).where(models.BotSetting.company_id == current_user.company_id)
    )
    setting = q.scalar_one_or_none()
    if not setting:
        setting = models.BotSetting(company_id=current_user.company_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

    # ★ company_id じゃなく bot_setting_id で紐づける
    opt = models.BotOption(
        bot_setting_id=setting.id,
        label=payload.label,
        reply_text=payload.reply_text,
        action=payload.action,
        link_url=payload.link_url,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(opt)
    await db.commit()
    await db.refresh(opt)
    return opt

# -------------------------
# 管理画面: 選択肢更新
# PUT /api/bot/options/{id}
# -------------------------
@router.put("/bot/options/{option_id}", response_model=schemas.BotOptionRead)
async def update_bot_option(
    option_id: int,
    payload: schemas.BotOptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.BotOption)
        .join(models.BotSetting, models.BotOption.bot_setting_id == models.BotSetting.id)
        .where(
            models.BotOption.id == option_id,
            models.BotSetting.company_id == current_user.company_id,
        )
    )
    opt = q.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="option not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(opt, k, v)

    await db.commit()
    await db.refresh(opt)
    return opt


# -------------------------
# 管理画面: 選択肢削除
# DELETE /api/bot/options/{id}
# -------------------------
@router.delete("/bot/options/{option_id}")
async def delete_bot_option(
    option_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.BotOption)
        .join(models.BotSetting, models.BotOption.bot_setting_id == models.BotSetting.id)
        .where(
            models.BotOption.id == option_id,
            models.BotSetting.company_id == current_user.company_id,
        )
    )
    opt = q.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="option not found")

    await db.delete(opt)
    await db.commit()
    return {"ok": True}


# -------------------------
# ウィジェット: Bot設定取得（api_keyから会社特定）
# GET /api/widget/bot?api_key=...
# -------------------------
@router.get("/widget/bot", response_model=schemas.BotSettingRead)
async def get_widget_bot_settings(
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(models.ApiKey).where(
            models.ApiKey.key == api_key,
            models.ApiKey.is_active.is_(True),
        )
    )
    key = q.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=401, detail="invalid api_key")

    company_id = key.company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id not found")

    q2 = await db.execute(
        select(models.BotSetting).where(models.BotSetting.company_id == company_id)
    )
    setting = q2.scalar_one_or_none()

    if not setting:
        setting = models.BotSetting(company_id=company_id)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

    # active だけ返す
    options = [o for o in (setting.options or []) if o.is_active]

    return schemas.BotSettingRead(
        enabled=setting.enabled,
        welcome_message=setting.welcome_message or "",
        options=options,
    )

@router.get("/embed.js")
async def get_embed_js(
    api_key: str = Query(...),
):
    js = f"""
(function() {{
  var d = document;

  function init() {{
    if (d.getElementById('chat-widget-frame')) return;

    var iframe = d.createElement('iframe');
    iframe.id = 'chat-widget-frame';
    iframe.src = 'http://localhost:5173/widget?api_key={api_key}';
    iframe.style.position = 'fixed';
    iframe.style.right = '20px';
    iframe.style.bottom = '20px';
    iframe.style.width = '360px';
    iframe.style.height = '520px';
    iframe.style.border = 'none';
    iframe.style.zIndex = '999999';
    iframe.style.borderRadius = '16px';
    iframe.style.boxShadow = '0 10px 30px rgba(15,23,42,0.25)';
    iframe.allow = 'clipboard-read; clipboard-write';

    d.body.appendChild(iframe);
  }}

  if (d.readyState === 'complete' || d.readyState === 'interactive') {{
    init();
  }} else {{
    d.addEventListener('DOMContentLoaded', init);
  }}
}})();
""".strip()

    return Response(content=js, media_type="application/javascript")

# =============================
# APIキー管理（管理画面用）
# =============================

@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.ApiKey)
        .where(
            models.ApiKey.company_id == current_user.company_id,
            models.ApiKey.user_id == current_user.id,   # ← “自分のキーだけ” ならこれ
            # 会社の全員のキーも見たいなら上の行を消す
        )
        .order_by(models.ApiKey.id.desc())
    )
    keys = q.scalars().all()

    # ★一覧では key を全部返さない（漏洩しやすい）
    def mask(k: str):
        if not k:
            return ""
        return k[:6] + "..." + k[-4:]

    return [
        {
            "id": k.id,
            "name": getattr(k, "name", None),
            "key_masked": mask(k.key),
            "is_active": bool(k.is_active),
            "created_at": k.created_at.isoformat() if getattr(k, "created_at", None) else None,
        }
        for k in keys
    ]


@router.post("/api-keys")
async def create_api_key(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    key_str = secrets.token_hex(32)

    api_key = models.ApiKey(
        key=key_str,
        user_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "api_key": api_key.key,  # ★作成時だけフル返却
        "is_active": bool(api_key.is_active),
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@router.post("/api-keys/{api_key_id}/disable")
async def disable_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.ApiKey).where(
            models.ApiKey.id == api_key_id,
            models.ApiKey.company_id == current_user.company_id,
            models.ApiKey.user_id == current_user.id,  # 自分のキーだけ操作可
        )
    )
    key = q.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="api_key not found")

    key.is_active = False
    key.revoked_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/api-keys/{api_key_id}/rotate")
async def rotate_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    rotate = 古いの無効化 → 新しいの発行
    """
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="company_id not set")

    q = await db.execute(
        select(models.ApiKey).where(
            models.ApiKey.id == api_key_id,
            models.ApiKey.company_id == current_user.company_id,
            models.ApiKey.user_id == current_user.id,
        )
    )
    old = q.scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=404, detail="api_key not found")

    old.is_active = False
    old.revoked_at = datetime.utcnow()

    new_key_str = secrets.token_hex(32)
    new_key = models.ApiKey(
        key=new_key_str,
        user_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return {
        "id": new_key.id,
        "api_key": new_key.key,  # ★rotate時もフル返却は1回だけ
        "is_active": True,
        "created_at": new_key.created_at.isoformat() if new_key.created_at else None,
    }

@router.post("/sessions/{session_id}/handoff")
async def request_handoff(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(models.Session).where(models.Session.id == session_id))
    session = q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.handoff_requested = True
    session.handoff_requested_at = datetime.utcnow()
    session.last_active_at = datetime.utcnow()

    await db.commit()
    return {"ok": True}