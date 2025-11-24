from fastapi import FastAPI
from .socket import app as socket_app
from .api.routes import router

from .db import engine, Base
import asyncio

app = FastAPI()

app.include_router(router)
app.mount("/ws", socket_app)

@app.get("/health")
def health():
    return {"status": "ok"}