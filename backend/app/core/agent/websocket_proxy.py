"""WebSocket proxy for real-time agent communication.

This module provides WebSocket endpoints that bridge communication between
the frontend and the local agent subprocess.
"""

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.status import WS_1000_NORMAL_CLOSURE

from app.core.agent.process_manager import agent_process_manager, TaskStatus
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(tags=["agent"])


class ConnectionManager:
    """Manages WebSocket connections for agent progress."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection for a task.

        Args:
            task_id: Task ID to subscribe to
            websocket: WebSocket connection
        """
        async with self._lock:
            if task_id not in self._connections:
                self._connections[task_id] = []
            self._connections[task_id].append(websocket)

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection.

        Args:
            task_id: Task ID
            websocket: WebSocket connection
        """
        async with self._lock:
            if task_id in self._connections:
                try:
                    self._connections[task_id].remove(websocket)
                    if not self._connections[task_id]:
                        del self._connections[task_id]
                except ValueError:
                    pass

    async def broadcast(self, task_id: str, message: dict[str, Any]) -> None:
        """Broadcast message to all connections for a task.

        Args:
            task_id: Task ID
            message: Message to broadcast
        """
        async with self._lock:
            connections = self._connections.get(task_id, [])

        if not connections:
            return

        dead_connections = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to websocket: {e}")
                dead_connections.append(websocket)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    try:
                        if task_id in self._connections:
                            self._connections[task_id].remove(ws)
                    except ValueError:
                        pass


# Global connection manager
agent_connection_manager = ConnectionManager()


async def _track_task_progress(task_id: str, websocket: WebSocket) -> None:
    """Track task progress and forward updates to WebSocket.

    This runs in the background while a task is executing.

    Args:
        task_id: Task ID to track
        websocket: WebSocket to send updates to
    """
    last_status: Optional[TaskStatus] = None

    try:
        while True:
            status = await agent_process_manager.get_task_status(task_id)

            if not status:
                await websocket.send_json({
                    "type": "error",
                    "message": "Task not found",
                })
                break

            # Only send if status changed
            if last_status is None or (
                status.status != last_status.status
                or status.current_step != last_status.current_step
                or status.progress != last_status.progress
                or status.message != last_status.message
                or status.error != last_status.error
            ):
                await websocket.send_json({
                    "type": "status",
                    "task_id": task_id,
                    "status": status.status,
                    "progress": status.progress,
                    "current_step": status.current_step,
                    "max_steps": status.max_steps,
                    "message": status.message,
                    "error": status.error,
                })
                last_status = status

            # Check if task finished
            if status.status in ("completed", "failed", "cancelled"):
                # Send final script if available
                if status.status == "completed":
                    script = await agent_process_manager.get_generated_script(task_id)
                    if script:
                        await websocket.send_json({
                            "type": "script",
                            "task_id": task_id,
                            "script": script,
                        })
                break

            await asyncio.sleep(0.5)  # Poll every 500ms

    except Exception as e:
        logger.error(f"Error tracking task {task_id}: {e}")


@router.websocket("/ws/{task_id}")
async def agent_websocket(
    websocket: WebSocket,
    task_id: str,
):
    """WebSocket endpoint for real-time agent progress.

    Connects to an existing task and streams progress updates.

    Args:
        websocket: WebSocket connection
        task_id: Task ID to track
    """
    await websocket.accept()

    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] WebSocket connected for task {task_id}")

    try:
        # Register connection
        await agent_connection_manager.connect(task_id, websocket)

        # Check if task exists
        status = await agent_process_manager.get_task_status(task_id)
        if not status:
            await websocket.send_json({
                "type": "error",
                "message": "Task not found",
            })
            return

        # Send current status
        await websocket.send_json({
            "type": "status",
            "task_id": task_id,
            "status": status.status,
            "progress": status.progress,
            "current_step": status.current_step,
            "max_steps": status.max_steps,
            "message": status.message,
        })

        # If task already completed, send the script
        if status.status == "completed":
            script = await agent_process_manager.get_generated_script(task_id)
            if script:
                await websocket.send_json({
                    "type": "script",
                    "task_id": task_id,
                    "script": script,
                })
            return

        # Start tracking in background
        track_task = asyncio.create_task(
            _track_task_progress(task_id, websocket)
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "stop":
                    # User requested stop
                    await agent_process_manager.stop_agent(task_id)
                    await websocket.send_json({
                        "type": "stopped",
                        "task_id": task_id,
                    })

                elif msg_type == "send_instruction":
                    # User wants to send additional instruction
                    instruction = message.get("instruction", "")
                    result = await agent_process_manager.send_instruction(task_id, instruction)
                    await websocket.send_json({
                        "type": "instruction_sent",
                        "result": result,
                    })

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[{trace_id}] WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"[{trace_id}] WebSocket error for task {task_id}: {e}")
    finally:
        await agent_connection_manager.disconnect(task_id, websocket)
        try:
            track_task.cancel()
        except NameError:
            pass
