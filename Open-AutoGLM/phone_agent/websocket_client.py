"""WebSocket client for connecting to backend server."""

import asyncio
import json
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any

import websockets

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.device_factory import DeviceType, set_device_type
from phone_agent.model import ModelConfig


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket client."""

    ws_url: str
    device_id: str
    base_url: str
    model: str
    apikey: str
    max_steps: int = 100
    lang: str = "cn"
    verbose: bool = True


class WebSocketClient:
    """
    WebSocket client for receiving tasks from backend server.

    Connects to the backend WebSocket server and listens for commands.
    Executes tasks using the PhoneAgent and reports results back.
    """

    def __init__(self, config: WebSocketConfig):
        self.config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """Start the WebSocket client in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                asyncio.sleep(0), self._loop
            )
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        """Main loop with reconnection logic."""
        while self._running:
            try:
                asyncio.run(self._connect_and_handle_messages())
            except Exception as e:
                if not self._running:
                    break
                print(f"WebSocket error: {e}")
                traceback.print_exc()

            if self._running:
                print(f"Reconnecting in {self._reconnect_delay:.1f} seconds...")
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    async def _connect_and_handle_messages(self) -> None:
        """Connect to WebSocket and handle messages."""
        try:
            async with websockets.connect(self.config.ws_url) as ws:
                self._reconnect_delay = 1.0
                self._loop = asyncio.get_running_loop()
                print(f"Connected to {self.config.ws_url}")
                # Send registration message
                await self._send_register(ws)
                await self._handle_messages(ws)
        except Exception as e:
            if self._running:
                raise
            raise

    async def _send_register(self, ws) -> None:
        """Send registration message to backend."""
        print(f"[DEBUG] Sending registration: device_id={self.config.device_id}")
        await self._send_message(ws, {
            "type": "register",
            "device_id": self.config.device_id,
            "device_name": self.config.device_id,  # TODO: get actual device name
            "capabilities": {
                "max_steps": self.config.max_steps,
                "lang": self.config.lang,
            }
        })
        print(f"[DEBUG] Registration sent successfully")

    async def _handle_messages(self, ws) -> None:
        """Handle incoming WebSocket messages."""
        while self._running:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "ping":
                    await self._handle_ping(ws)
                elif msg_type == "command":
                    await self._handle_command(ws, data)
                else:
                    print(f"Unknown message type: {msg_type}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if not self._running:
                    break
                print(f"Error handling message: {e}")
                traceback.print_exc()

    async def _handle_ping(self, ws) -> None:
        """Respond to ping with pong."""
        await self._send_message(ws, {
            "type": "pong",
            "device_id": self.config.device_id,
        })

    async def _handle_command(self, ws, data: dict[str, Any]) -> None:
        """Handle command from backend."""
        action = data.get("action")
        if action == "run_task":
            params = data.get("params", {})
            task = params.get("task")
            task_id = params.get("task_id")
            if task and task_id:
                await self._execute_task(ws, task_id, task)
            else:
                error_msg = "Missing task or task_id in run_task command"
                print(error_msg)
                await self._send_message(
                    ws,
                    {"type": "error", "error": error_msg, "task_id": task_id},
                )
        else:
            print(f"Unknown command action: {action}")
            await self._send_message(
                ws, {"type": "error", "error": f"Unknown action: {action}"}
            )

    async def _execute_task(self, ws, task_id: str, task: str) -> None:
        """Execute a task using PhoneAgent."""
        print(f"Executing task {task_id}: {task}")

        try:
            # Set device type
            device_type = DeviceType.ADB
            set_device_type(device_type)

            # Create configurations
            model_config = ModelConfig(
                base_url=self.config.base_url,
                model_name=self.config.model,
                api_key=self.config.apikey,
                lang=self.config.lang,
            )

            agent_config = AgentConfig(
                max_steps=self.config.max_steps,
                device_id=self.config.device_id,
                verbose=self.config.verbose,
                lang=self.config.lang,
            )

            # Send status update - starting
            await self._send_message(
                ws,
                {
                    "type": "status_update",
                    "device_id": self.config.device_id,
                    "status": "running",
                    "task_id": task_id,
                    "progress": 0,
                },
            )

            # Run the task in a thread to not block
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._run_agent_task, model_config, agent_config, task
            )

            # Unpack result (message, step_history)
            result_message, step_history = result

            # Determine completion status
            finished_status = "completed" if result_message and result_message != "Max steps reached" else "completed"

            # Format steps for task_result
            formatted_steps = []
            for step in step_history:
                step_data = {
                    "action": step.action.get("action") if step.action else None,
                    "success": step.success,
                    "ai_thought_process": step.thinking,
                }
                # Include action parameters (like text for Type action)
                if step.action:
                    action_params = {k: v for k, v in step.action.items() if k != "action"}
                    if action_params:
                        step_data["action_data"] = action_params
                if step.element_info:
                    step_data["element_info"] = step.element_info.to_dict()
                if step.message:
                    step_data["message"] = step.message
                formatted_steps.append(step_data)

            await self._send_message(
                ws,
                {
                    "type": "task_result",
                    "task_id": task_id,
                    "result": {
                        "status": finished_status,
                        "message": result_message,
                        "steps": formatted_steps,
                    },
                },
            )
            print(f"Task {task_id} completed: {result_message}")

        except Exception as e:
            error_msg = str(e)
            print(f"Task {task_id} failed: {error_msg}")
            traceback.print_exc()
            await self._send_message(
                ws,
                {
                    "type": "task_result",
                    "task_id": task_id,
                    "result": {"status": "failed", "message": error_msg},
                },
            )

    def _run_agent_task(self, model_config: ModelConfig, agent_config: AgentConfig, task: str) -> tuple[str, list]:
        """Run agent task (synchronous, called in executor).

        Returns:
            Tuple of (message, step_history)
        """
        agent = PhoneAgent(model_config=model_config, agent_config=agent_config)
        return agent.run(task)

    async def _send_message(self, ws, message: dict[str, Any]) -> None:
        """Send JSON message to WebSocket."""
        try:
            await ws.send(json.dumps(message))
        except Exception as e:
            print(f"Error sending message: {e}")
