import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from robot_manager import robot_connections
import boto3
import jwt  # PyJWT
import redis
import json
import ssl

# === Redis (Valkey) Setup ===
redis_client = redis.Redis(
    host='robomeans-cache-v2-i8vsax.serverless.cac1.cache.amazonaws.com',
    port=6379,
    ssl=True,
    ssl_cert_reqs=None,
    decode_responses=True,
    socket_connect_timeout=5
)

# === FastAPI and Socket.IO setup ===
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = FastAPI()
socket_app = socketio.ASGIApp(sio, app)

# === Allow CORS for frontend ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === In-memory session tracking for UI sessions ===
active_ui_sessions = {}  # email -> sid

# === Utility Functions ===
def set_robot_state(robot_id, data):
    redis_client.set(f"robot:{robot_id}:state", json.dumps(data))

def get_robot_state(robot_id):
    data = redis_client.get(f"robot:{robot_id}:state")
    return json.loads(data) if data else None

# === WebSocket Events ===

@sio.event
async def connect(sid, environ):
    print(f"✅ WebSocket client connected: {sid}")

@sio.event
async def register_robot(sid, data):
    robot_id = data.get("robot_id")
    if robot_id:
        robot_connections[robot_id] = sid
        state = get_robot_state(robot_id) or {}
        state["connection_status"] = 1
        state["connection"] = "connected"  # ✅ Add connection field
        set_robot_state(robot_id, state)
        print(f"🤖 Robot registered: {robot_id} (SID: {sid})")
        await sio.emit("status", state)  # ✅ Emit updated status with connection field

@sio.event
async def register_ui(sid, data):
    email = data.get("email")
    robot_ids = data.get("robot_ids", [])

    if not email:
        print("❌ UI tried to register without email.")
        return

    previous_sid = active_ui_sessions.get(email)
    if previous_sid and previous_sid != sid:
        print(f"⚠️ Duplicate login for {email}. Kicking old session {previous_sid}")
        await sio.emit("force_logout", {}, to=previous_sid)
        await sio.disconnect(previous_sid)

    active_ui_sessions[email] = sid
    print(f"🧑 UI registered: {email} (SID: {sid})")

    for rid in robot_ids:
        print(f"📡 UI controls robot: {rid}")
        state = get_robot_state(rid)
        if state:
            print(f"📥 Last known status for {rid}: {state}")
            await sio.emit("status", state, to=sid)

@sio.event
async def command_to_robot(sid, data):
    robot_id = data.get("robot_id")
    command = data.get("command")
    target_sid = robot_connections.get(robot_id)

    if target_sid:
        await sio.emit("command", {"command": command}, to=target_sid)
        print(f"📤 Sent '{command}' to {robot_id}")
    else:
        print(f"⚠️ Robot {robot_id} not connected")

@sio.event
async def status_update(sid, data):
    robot_id = data.get("robot_id")
    if not robot_id:
        return

    data["connection"] = "connected"  # ✅ Ensure connection field is present
    set_robot_state(robot_id, data)
    print(f"📥 Status from {robot_id}: {data}")
    await sio.emit("status", data)

@sio.event
async def disconnect(sid):
    for rid, rsid in list(robot_connections.items()):
        if rsid == sid:
            del robot_connections[rid]
            state = get_robot_state(rid) or {}
            state["connection_status"] = 0
            state["connection"] = "disconnected"  # ✅ Mark as disconnected
            set_robot_state(rid, state)
            print(f"❌ Robot disconnected: {rid}")
            await sio.emit("status", state)  # ✅ Broadcast disconnect status

    for email, esid in list(active_ui_sessions.items()):
        if esid == sid:
            del active_ui_sessions[email]
            print(f"❌ UI session disconnected for {email}")

# === REST API ===

@app.get("/api/myrobots")
async def get_my_robots(request: Request):
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise ValueError("Missing or invalid Authorization header")
        token = auth_header.split(" ")[1]

        decoded = jwt.decode(token, options={"verify_signature": False})
        user_email = decoded.get("email")
        if not user_email:
            raise ValueError("Email not found in token")

        dynamodb = boto3.client("dynamodb", region_name="ca-central-1")
        response = dynamodb.query(
            TableName="UserRobotMapping",
            KeyConditionExpression="email = :e",
            ExpressionAttributeValues={":e": {"S": user_email}},
        )

        items = response.get("Items", [])
        robots = [
            {
                "robot_id": item["robot_id"]["S"],
                "ui_type": item.get("ui_type", {}).get("S", "default")
            }
            for item in items
        ]

        return JSONResponse(content={"robots": robots})

    except Exception as e:
        print("🚨 Error in /api/myrobots:", e)
        return JSONResponse(status_code=401, content={"error": str(e)})

@app.get("/api/robot_state/{robot_id}")
async def get_robot_state_route(robot_id: str):
    state = get_robot_state(robot_id)
    if state:
        return JSONResponse(content=state)
    return JSONResponse(status_code=404, content={"error": "Robot state not found"})
