# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router as core_router
from .api import routes_upload
from .socket import sio
import socketio

fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 本番環境では適切に設定すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 既存 API
fastapi_app.include_router(core_router)

# 画像アップロード用 API を /api 配下に生やす
fastapi_app.include_router(routes_upload.router)

# 画像配信用の静的ファイル
# アップロードされたファイルを配信する
fastapi_app.mount(
    "/uploads",
    StaticFiles(directory="/app/uploads"),
    name="uploads",
)

app = socketio.ASGIApp(
    sio,
    other_asgi_app=fastapi_app,
    socketio_path="ws/socket.io",
)