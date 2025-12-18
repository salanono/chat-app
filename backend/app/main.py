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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(core_router)

fastapi_app.include_router(routes_upload.router)

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