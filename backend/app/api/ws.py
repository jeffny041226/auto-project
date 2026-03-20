"""WebSocket handler for real-time updates."""
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.redis import redis_client
from app.models.user import User
from app.services.auth import AuthService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept and register WebSocket connection."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove WebSocket connection."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send message to specific user."""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            # Clean up disconnected
            for conn in disconnected:
                self.disconnect(conn, user_id)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws?token=<jwt_token>
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Validate token
    auth_service = AuthService(None)
    payload = auth_service.decode_token(token)

    if not payload:
        await websocket.close(code=4002, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token payload")
        return

    # Accept connection
    await manager.connect(websocket, user_id)

    # Subscribe to Redis channel for this user
    pubsub = redis_client.client.pubsub()
    await pubsub.subscribe(f"user:{user_id}:tasks")

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
        })

        # Listen for messages
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "subscribe":
                    # Subscribe to specific task updates
                    task_id = message.get("task_id")
                    if task_id:
                        await pubsub.subscribe(f"task:{task_id}")

                elif msg_type == "unsubscribe":
                    task_id = message.get("task_id")
                    if task_id:
                        await pubsub.unsubscribe(f"task:{task_id}")

                else:
                    logger.warning(f"Unknown WebSocket message type: {msg_type}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        await pubsub.unsubscribe()

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_id)


async def notify_task_update(task_id: str, user_id: str, update: dict) -> None:
    """Send task update notification to user.

    Args:
        task_id: Task ID
        user_id: User ID
        update: Update data
    """
    message = {
        "type": "task_update",
        "task_id": task_id,
        "data": update,
    }

    # Send via WebSocket
    await manager.send_to_user(user_id, message)

    # Also publish to Redis for distributed systems
    await redis_client.publish(f"user:{user_id}:tasks", json.dumps(message))


async def notify_task_complete(task_id: str, user_id: str, result: dict) -> None:
    """Send task completion notification.

    Args:
        task_id: Task ID
        user_id: User ID
        result: Completion result
    """
    message = {
        "type": "task_completed",
        "task_id": task_id,
        "result": result,
    }

    await manager.send_to_user(user_id, message)
    await redis_client.publish(f"user:{user_id}:tasks", json.dumps(message))


# Device Agent WebSocket Endpoint
@router.websocket("/ws/devices/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for device agent connections.

    Device agents connect to this endpoint to receive commands
    and report task results.

    Connect with: ws://host/ws/devices/{device_id}?token=<device_token>
    """
    from app.core.device.agent import handle_device_websocket

    await handle_device_websocket(websocket, device_id)


# Device Discovery Endpoint
@router.get("/devices/discover")
async def discover_devices():
    """Discover available ADB devices.

    Returns list of connected Android devices.
    """
    from app.core.device.maestro import MaestroDeviceConnector

    devices = await MaestroDeviceConnector.list_available_devices()
    return {
        "devices": devices,
        "count": len(devices),
    }


@router.post("/devices/connect")
async def connect_device(device_ip: str, device_port: int = 5555):
    """Connect to a network Android device.

    Args:
        device_ip: Device IP address
        device_port: ADB port (default 5555)

    Returns:
        Connection result
    """
    from app.core.device.maestro import MaestroDeviceConnector

    connector = MaestroDeviceConnector()
    connected = await connector.connect(device_ip, device_port)

    if connected:
        device_info = await connector.get_device_info()
        return {
            "success": True,
            "device": device_info,
        }
    else:
        return {
            "success": False,
            "error": "Failed to connect to device",
        }
