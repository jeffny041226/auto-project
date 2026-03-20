#!/usr/bin/env python3
"""
Device Agent - Simple agent to run on Android devices

This script runs on an Android device (via Termux or similar)
and connects to the platform to receive and execute test commands.

Usage:
    python device_agent.py --device-id <device-id> --server http://your-server:8000
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("DeviceAgent")


class DeviceAgent:
    """Lightweight agent for Android devices."""

    def __init__(self, device_id: str, server_url: str, api_key: str = None):
        self.device_id = device_id
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.ws_url = f"ws://{server_url.split('://')[1]}/ws/devices/{device_id}"
        self.ws = None
        self.running = True

    async def connect(self):
        """Connect to the platform WebSocket."""
        try:
            import websockets

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.ws = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
            )
            logger.info(f"Connected to platform: {self.ws_url}")

            # Send initial registration
            await self.send_message({
                "type": "register",
                "device_id": self.device_id,
            })

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    async def send_message(self, message: dict):
        """Send message to platform."""
        if self.ws:
            await self.ws.send(json.dumps(message))

    async def receive_message(self) -> dict:
        """Receive message from platform."""
        if self.ws:
            data = await self.ws.recv()
            return json.loads(data)
        return {}

    async def run(self):
        """Main agent loop."""
        while self.running:
            try:
                message = await self.receive_message()
                await self.handle_message(message)
            except Exception as e:
                logger.error(f"Error: {e}")
                break

    async def handle_message(self, message: dict):
        """Handle incoming message."""
        msg_type = message.get("type")

        if msg_type == "ping":
            await self.send_message({"type": "pong"})

        elif msg_type == "command":
            await self.handle_command(message)

        elif msg_type == "disconnect":
            logger.info("Received disconnect command")
            self.running = False

    async def handle_command(self, message: dict):
        """Handle test command from platform."""
        command = message.get("command", {})
        action = command.get("action")
        params = command.get("params", {})
        command_id = message.get("command_id")

        logger.info(f"Executing command: {action}")

        try:
            result = await self.execute_action(action, params)
            await self.send_message({
                "type": "command_result",
                "command_id": command_id,
                "success": True,
                "result": result,
            })
        except Exception as e:
            logger.error(f"Command failed: {e}")
            await self.send_message({
                "type": "command_result",
                "command_id": command_id,
                "success": False,
                "error": str(e),
            })

    async def execute_action(self, action: str, params: dict):
        """Execute an action on the device."""
        if action == "shell":
            cmd = params.get("command", "")
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", cmd],
                capture_output=True,
                timeout=30,
            )
            return {
                "stdout": result.stdout.decode(),
                "stderr": result.stderr.decode(),
                "returncode": result.returncode,
            }

        elif action == "tap":
            x, y = params.get("x"), params.get("y")
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", "input", "tap", str(x), str(y)],
                check=True,
            )
            return {"success": True}

        elif action == "swipe":
            start_x = params.get("start_x", 0)
            start_y = params.get("start_y", 0)
            end_x = params.get("end_x", 0)
            end_y = params.get("end_y", 0)
            duration = params.get("duration", 300)
            subprocess.run(
                [
                    "adb", "-s", self.device_id, "shell", "input", "swipe",
                    str(start_x), str(start_y), str(end_x), str(end_y), str(duration),
                ],
                check=True,
            )
            return {"success": True}

        elif action == "input_text":
            text = params.get("text", "")
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", "input", "text", text],
                check=True,
            )
            return {"success": True}

        elif action == "screenshot":
            temp_path = tempfile.mktemp(suffix=".png")
            subprocess.run(
                [
                    "adb", "-s", self.device_id, "shell", "screencap", "-p", temp_path
                ],
                check=True,
            )
            # Read and return as base64 would be too large, just confirm success
            return {"path": temp_path}

        elif action == "start_app":
            package = params.get("package", "")
            activity = params.get("activity", "")
            if activity:
                subprocess.run(
                    [
                        "adb", "-s", self.device_id, "shell", "am", "start", "-n",
                        f"{package}/{activity}",
                    ],
                    check=True,
                )
            else:
                subprocess.run(
                    [
                        "adb", "-s", self.device_id, "shell", "monkey", "-p", package, "-c",
                        "android.intent.category.LAUNCHER", "1",
                    ],
                    check=True,
                )
            return {"success": True}

        elif action == "press_key":
            keycode = params.get("keycode", 4)  # 4 = BACK
            subprocess.run(
                ["adb", "-s", self.device_id, "shell", "input", "keyevent", str(keycode)],
                check=True,
            )
            return {"success": True}

        else:
            raise ValueError(f"Unknown action: {action}")

    async def send_heartbeat(self):
        """Send periodic heartbeat."""
        while self.running:
            try:
                await self.send_message({
                    "type": "heartbeat",
                    "device_id": self.device_id,
                    "status": "online",
                })
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    async def start(self):
        """Start the agent."""
        # Setup signal handlers
        loop = asyncio.get_event_loop()

        def signal_handler():
            logger.info("Received shutdown signal")
            self.running = False

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        # Connect and run
        await self.connect()

        await asyncio.gather(
            self.run(),
            self.send_heartbeat(),
        )

    async def stop(self):
        """Stop the agent."""
        self.running = False
        if self.ws:
            await self.ws.close()


async def main():
    parser = argparse.ArgumentParser(description="Device Agent for Auto Test Platform")
    parser.add_argument("--device-id", required=True, help="Unique device ID")
    parser.add_argument("--server", required=True, help="Platform server URL")
    parser.add_argument("--api-key", help="API key for authentication")

    args = parser.parse_args()

    agent = DeviceAgent(
        device_id=args.device_id,
        server_url=args.server,
        api_key=args.api_key,
    )

    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await agent.stop()


if __name__ == "__main__":
    # Check for ADB
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ADB not found. Install Android SDK platform tools.")
        sys.exit(1)

    asyncio.run(main())
