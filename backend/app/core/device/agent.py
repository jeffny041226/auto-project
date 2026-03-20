"""Device Agent handler for WebSocket connections."""
import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.db.database import get_db_context
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DeviceConnection:
    """Manages a single device agent connection."""

    def __init__(self, device_id: str, websocket: WebSocket):
        self.device_id = device_id
        self.ws = websocket
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.is_connected = True
        self.current_task_id: Optional[str] = None

    async def start_heartbeat(self, interval: int = 30):
        """Start sending periodic heartbeats."""

        async def heartbeat():
            while self.is_connected:
                try:
                    await self.ws.send_json({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    await asyncio.sleep(interval)
                except Exception:
                    break

        self.heartbeat_task = asyncio.create_task(heartbeat())

    async def stop_heartbeat(self):
        """Stop heartbeat task."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

    async def send_command(self, command: dict):
        """Send command to device agent."""
        await self.ws.send_json({
            "type": "command",
            "command_id": command.get("command_id"),
            "action": command.get("action"),
            "params": command.get("params", {}),
        })

    async def receive(self) -> Optional[dict]:
        """Receive message from device."""
        try:
            data = await self.ws.receive_text()
            return json.loads(data)
        except Exception:
            return None


class DeviceAgentManager:
    """Manages all connected device agents."""

    def __init__(self):
        self._connections: dict[str, DeviceConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, device_id: str, ws: WebSocket) -> DeviceConnection:
        """Register a new device connection."""
        async with self._lock:
            # Close existing connection if any
            if device_id in self._connections:
                await self.disconnect(device_id)

            connection = DeviceConnection(device_id, ws)
            self._connections[device_id] = connection

            # Update device status in database
            await self._update_device_status(device_id, "online")

            logger.info(f"Device {device_id} connected")
            return connection

    async def disconnect(self, device_id: str):
        """Disconnect a device."""
        async with self._lock:
            if device_id in self._connections:
                conn = self._connections[device_id]
                conn.is_connected = False
                await conn.stop_heartbeat()
                await conn.ws.close()
                del self._connections[device_id]

                # Update device status
                await self._update_device_status(device_id, "offline")
                logger.info(f"Device {device_id} disconnected")

    async def get_connection(self, device_id: str) -> Optional[DeviceConnection]:
        """Get connection by device ID."""
        return self._connections.get(device_id)

    async def send_command(self, device_id: str, command: dict) -> bool:
        """Send command to specific device."""
        conn = self._connections.get(device_id)
        if conn and conn.is_connected:
            try:
                await conn.send_command(command)
                return True
            except Exception as e:
                logger.error(f"Failed to send command to {device_id}: {e}")
        return False

    async def broadcast_command(self, command: dict) -> int:
        """Broadcast command to all connected devices."""
        count = 0
        for device_id in list(self._connections.keys()):
            if await self.send_command(device_id, command):
                count += 1
        return count

    async def list_online_devices(self) -> list[str]:
        """List all online device IDs."""
        return [
            device_id
            for device_id, conn in self._connections.items()
            if conn.is_connected
        ]

    async def _update_device_status(self, device_id: str, status: str):
        """Update device status in database."""
        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(Device).where(Device.device_id == device_id)
                )
                device = result.scalar_one_or_none()

                if device:
                    device.status = status
                    device.last_heartbeat = datetime.utcnow()
                    await db.commit()
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")


# Global manager instance
device_agent_manager = DeviceAgentManager()


async def handle_device_websocket(websocket: WebSocket, device_id: str):
    """Handle device agent WebSocket connection.

    Connect: ws://host/ws/devices/{device_id}?token=<device_token>
    """
    await websocket.accept()

    # Verify device token (simplified - should be proper auth)
    # token = websocket.query_params.get("token")

    conn = await device_agent_manager.register(device_id, websocket)

    try:
        # Start heartbeat
        await conn.start_heartbeat()

        # Handle messages
        while conn.is_connected:
            message = await conn.receive()
            if not message:
                break

            msg_type = message.get("type")

            if msg_type == "pong":
                # Heartbeat response
                await device_agent_manager._update_device_status(device_id, "online")

            elif msg_type == "task_result":
                # Device reported task result
                await handle_task_result(message)

            elif msg_type == "status_update":
                # Device status update
                await handle_status_update(message)

            elif msg_type == "error":
                # Device error report
                logger.error(f"Device {device_id} error: {message.get('error')}")

    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")

    except Exception as e:
        logger.error(f"Device {device_id} error: {e}")

    finally:
        await device_agent_manager.disconnect(device_id)


async def handle_task_result(message: dict):
    """Handle task result from device."""
    task_id = message.get("task_id")
    result = message.get("result", {})

    logger.info(f"Received result for task {task_id}: {result.get('status')}")
    # TODO: Update task in database, trigger next steps


async def handle_status_update(message: dict):
    """Handle device status update from agent."""
    device_id = message.get("device_id")
    status = message.get("status")

    logger.debug(f"Device {device_id} status: {status}")
