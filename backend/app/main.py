# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from .api.routes import router as api_router
from .db import Base, engine
from .socket import sio  # ← さっきの AsyncServer を import
from .auth import ensure_default_admin

from . import models
# ---- FastAPI 本体（REST 用） ----
fastapi_app = FastAPI(title="Chat Support Backend")

origins = [
    "http://localhost:5173",
]

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(api_router)


@fastapi_app.get("/health")
async def health():
  return {"status": "ok"}


@fastapi_app.on_event("startup")
async def on_startup():
    # 起動時にテーブル自動作成
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_default_admin()

# ---- FastAPI + Socket.IO を合体させた ASGI アプリ ----
# socketio_path="ws/socket.io" → クライアント側は path: "/ws/socket.io"
app = socketio.ASGIApp(
    sio,
    other_asgi_app=fastapi_app,
    socketio_path="ws/socket.io",
)