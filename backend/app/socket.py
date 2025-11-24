import socketio

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

app = socketio.ASGIApp(sio)

@sio.event
async def connect(sid, environ):
    print("Client connected", sid)

@sio.event
async def disconnect(sid):
    print("Client disconnected", sid)

@sio.event
async def visitor_join(sid, payload):
    print("visitor joined", payload)

@sio.event
async def visitor_message(sid, payload):
    print("msg from visitor:", payload)
    await sio.emit("visitor_message", payload)