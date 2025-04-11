import socketio
from fastapi import FastAPI
from robot_manager import robot_connections

# Store UI connections and last known statuses
ui_connections = {}         # {robot_id: [sid, sid, ...]}
last_known_status = {}      # {robot_id: "status"}

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = FastAPI()
socket_app = socketio.ASGIApp(sio, app)

# === EVENTS ===

@sio.event
async def connect(sid, environ):
    print(f"✅ Client connected: {sid}")

@sio.event
async def register_robot(sid, data):
    robot_id = data.get("robot_id")
    if robot_id:
        robot_connections[robot_id] = sid
        print(f"🤖 Robot registered: {robot_id} (SID: {sid})")

@sio.event
async def register_ui(sid, data):
    robot_id = data.get("robot_id")
    if robot_id:
        ui_connections.setdefault(robot_id, []).append(sid)
        print(f"🧑‍💻 UI registered for {robot_id} (SID: {sid})")

        # Send last known status (if any)
        if robot_id in last_known_status:
            await sio.emit("status", {
                "robot_id": robot_id,
                "status": last_known_status[robot_id]
            }, to=sid)
            print(f"↩️ Sent last known status to UI for {robot_id}")

@sio.event
async def command_to_robot(sid, data):
    robot_id = data.get("robot_id")
    command = data.get("command")
    target_sid = robot_connections.get(robot_id)

    if target_sid:
        await sio.emit("command", {"command": command}, to=target_sid)
        print(f"📤 Sent command '{command}' to {robot_id}")
    else:
        print(f"⚠️ Robot {robot_id} is not connected")

@sio.event
async def status_update(sid, data):
    robot_id = data.get("robot_id")
    status = data.get("status")
    last_known_status[robot_id] = status
    print(f"📥 Status from {robot_id}: {status}")

    # Send to all registered UIs for this robot
    for ui_sid in ui_connections.get(robot_id, []):
        await sio.emit("status", data, to=ui_sid)

@sio.event
async def disconnect(sid):
    # Remove from robot list
    for rid, rsid in list(robot_connections.items()):
        if rsid == sid:
            del robot_connections[rid]
            print(f"❌ Robot disconnected: {rid}")

    # Remove from UI list
    for rid, sid_list in list(ui_connections.items()):
        if sid in sid_list:
            sid_list.remove(sid)
            print(f"❌ UI disconnected from {rid}")
