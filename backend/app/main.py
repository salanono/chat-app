# backend/app/main.py
from fastapi import FastAPI

from .api.routes import router as api_router
from .db import Base, engine

app = FastAPI(title="Chat Support Backend")

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    # 起動時にテーブル自動作成（マイグレーション導入までの暫定）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)