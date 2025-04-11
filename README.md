# Robomeans Gateway

This is the backend for a real-time robot control system using **FastAPI** and **Socket.IO**.

┌─────────────┐      WebSocket       ┌──────────────┐       WebSocket       ┌────────────┐
│ React App   │  <---------------->  │ FastAPI EC2  │  <---------------->   │  Robot     │
│ (Client)    │     (socket.io)      │ (socket.io)  │      (socket.io)      │ (Client)   │
└─────────────┘                      └──────────────┘                        └────────────┘
     UI Events & Commands                Relay Commands                        Send Status
         (e.g., "start")                 to matching robot                  (e.g., "Running")


## 📦 Project Structure

```
robomeans-gateway/
├── main.py              # FastAPI + Socket.IO entry point
├── robot_manager.py     # Tracks robot socket connections
├── requirements.txt     # Python dependencies
```

## 🚀 Getting Started

### 1. Clone and Enter the Project

```bash
git clone https://github.com/Jouybari7/robomeans-gateway.git
cd robomeans-gateway
```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
uvicorn main:socket_app --host 0.0.0.0 --port 8000
```

Your server will be accessible at: `http://<your-ec2-ip>:8000`

## 📡 Socket.IO Events

### From React Dashboard
- `register_ui`: Registers the UI for a specific robot
- `command_to_robot`: Sends commands (start, dock, etc.)

### From Python Robot Client
- `register_robot`: Registers the robot
- `status_update`: Sends status back to UI(s)

## 🔄 Handles
- Multiple UIs per robot
- One robot per ID
- Out-of-order connections
- Last-known status sync to UI

## 📜 License
MIT