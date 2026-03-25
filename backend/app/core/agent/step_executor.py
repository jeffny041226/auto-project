"""Step executor for performing individual UI actions."""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from app.core.device.adb import ADBConnector
from app.core.executor.driver import MaestroDriver
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


class MaestroScriptBuilder:
    """Builds Maestro YAML scripts incrementally during agent execution.

    This class collects actions during the exploration loop and generates
    a valid Maestro YAML script at the end.
    """

    def __init__(self, app_id: str = "com.example.app"):
        """Initialize script builder.

        Args:
            app_id: App package ID for the Maestro script
        """
        self.app_id = app_id
        self.flow_name = ""
        self.steps: list[dict[str, Any]] = []

    def set_flow_name(self, name: str):
        """Set the flow name."""
        self.flow_name = name

    def set_app_id(self, app_id: str):
        """Set the app package ID."""
        self.app_id = app_id

    def add_launch(self, app_id: str):
        """Add a launchApp step."""
        self.steps.append({"action": "launchApp", "app_id": app_id})

    def add_tap(self, x: int, y: int):
        """Add a tapOn step with coordinates."""
        self.steps.append({"action": "tapOn", "x": x, "y": y})

    def add_tap_element(self, element_desc: str):
        """Add a tapOn step with element description."""
        self.steps.append({"action": "tapOnElement", "element": element_desc})

    def add_input_text(self, text: str):
        """Add an inputText step."""
        self.steps.append({"action": "inputText", "text": text})

    def add_swipe(self, start_x: int, start_y: int, end_x: int, end_y: int):
        """Add a swipe step."""
        self.steps.append({
            "action": "swipe",
            "startX": start_x,
            "startY": start_y,
            "endX": end_x,
            "endY": end_y,
        })

    def add_back(self):
        """Add a pressKey BACK step."""
        self.steps.append({"action": "pressKey", "key": "BACK"})

    def add_home(self):
        """Add a pressKey HOME step."""
        self.steps.append({"action": "pressKey", "key": "HOME"})

    def add_wait(self, seconds: int):
        """Add a wait step."""
        self.steps.append({"action": "waitForAnimationToEnd", "duration": seconds})

    def add_stop_app(self, app_id: str):
        """Add a stopApp step."""
        self.steps.append({"action": "stopApp", "app_id": app_id})

    def add_screenshot(self):
        """Add a takeScreenshot step."""
        self.steps.append({"action": "takeScreenshot"})

    def render(self, app_id: Optional[str] = None) -> str:
        """Render the accumulated steps as Maestro YAML.

        Args:
            app_id: Optional app ID override

        Returns:
            Maestro YAML script string
        """
        target_app = app_id or self.app_id
        if not target_app:
            target_app = "com.example.app"

        lines = [f"appId: {target_app}", "---"]

        if self.flow_name:
            lines.append(f"# Flow: {self.flow_name}")

        for step in self.steps:
            action = step.get("action")

            if action == "launchApp":
                lines.append(f"- launchApp:")
                lines.append(f"    appId: {step.get('app_id', '')}")
            elif action == "tapOn":
                x = step.get("x")
                y = step.get("y")
                if x is not None and y is not None:
                    lines.append(f"- tapOn:")
                    lines.append(f"    point: {x},{y}")
                else:
                    lines.append(f"- tapOn:")
                    lines.append(f"    {step.get('element', 'unknown')}")
            elif action == "tapOnElement":
                lines.append(f"- tapOn:")
                lines.append(f"    {step.get('element', 'unknown')}")
            elif action == "inputText":
                lines.append(f"- inputText:")
                lines.append(f"    text: {step.get('text', '')}")
            elif action == "swipe":
                lines.append(f"- swipe:")
                lines.append(f"    startX: {step.get('startX', 0)}")
                lines.append(f"    startY: {step.get('startY', 0)}")
                lines.append(f"    endX: {step.get('endX', 0)}")
                lines.append(f"    endY: {step.get('endY', 0)}")
                lines.append(f"    duration: {step.get('duration', 500)}")
            elif action == "pressKey":
                lines.append(f"- pressKey:")
                lines.append(f"    key: {step.get('key', '')}")
            elif action == "waitForAnimationToEnd":
                lines.append("- waitForAnimationToEnd")
            elif action == "stopApp":
                lines.append(f"- stopApp:")
                lines.append(f"    appId: {step.get('app_id', '')}")
            elif action == "takeScreenshot":
                lines.append("- takeScreenshot")
            else:
                lines.append(f"# Unknown action: {action}")

        return "\n".join(lines)


class StepExecutor:
    """Executes individual UI automation steps via ADB or Maestro."""

    # Action to ADB command mapping
    ADB_COMMANDS = {
        "tap": "input tap {x} {y}",
        "swipe": "input swipe {start_x} {start_y} {end_x} {end_y} {duration}",
        "inputText": "input text '{text}'",
        "pressKey": "input keyevent {keycode}",
        "launchApp": "monkey -p {package} -c android.intent.category.LAUNCHER 1",
        "stopApp": "am force-stop {package}",
    }

    # Key name to keycode mapping
    KEY_CODES = {
        "BACK": 4,
        "HOME": 3,
        "ENTER": 66,
        "MENU": 82,
        "VOLUME_UP": 24,
        "VOLUME_DOWN": 25,
        "POWER": 26,
    }

    def __init__(self, device_serial: str):
        """Initialize step executor.

        Args:
            device_serial: Device serial number for ADB connection
        """
        self.device_serial = device_serial
        self.adb = ADBConnector()
        self.adb.set_device(device_serial)
        self.maestro = MaestroDriver()

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single automation step.

        Args:
            step: Step dict with action, target, value

        Returns:
            Execution result dict
        """
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")

        trace_id = get_trace_id()
        logger.info(f"[{trace_id}] Executing step: {action} target={target} value={value}")

        try:
            if action == "launchApp":
                return await self._launch_app(target)
            elif action == "tapOn":
                return await self._tap_on(target, value)
            elif action == "inputText":
                return await self._input_text(value)
            elif action == "swipe":
                return await self._swipe(value)
            elif action == "pressKey":
                return await self._press_key(target or value)
            elif action == "waitForAnimationToEnd":
                return await self._wait()
            elif action == "stopApp":
                return await self._stop_app(target)
            elif action == "done":
                return {"success": True, "action": "done"}
            else:
                logger.warning(f"Unknown action: {action}")
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"[{trace_id}] Step execution error: {e}")
            return {"success": False, "error": str(e)}

    async def tap_at(self, x: int, y: int, description: str = "") -> dict[str, Any]:
        """Tap at specific coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            description: Optional description for logging

        Returns:
            Execution result dict
        """
        desc = f" ({description})" if description else ""
        logger.info(f"Tapping at ({x}, {y}){desc}")
        try:
            await self.adb.tap(x, y)
            return {"success": True, "action": "tapOn", "x": x, "y": y}
        except Exception as e:
            logger.error(f"Tap at ({x}, {y}) failed: {e}")
            return {"success": False, "error": f"Tap failed: {e}"}

    async def _launch_app(self, package: str) -> dict[str, Any]:
        """Launch an app by package name."""
        if not package:
            return {"success": False, "error": "No package specified"}

        try:
            # Use monkey to launch the app
            await self.adb.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
            await asyncio.sleep(1)  # Wait for app to start
            logger.info(f"Launched app: {package}")
            return {"success": True, "action": "launchApp", "package": package}
        except Exception as e:
            return {"success": False, "error": f"Failed to launch {package}: {e}"}

    async def _stop_app(self, package: str) -> dict[str, Any]:
        """Stop an app by package name."""
        if not package:
            return {"success": False, "error": "No package specified"}

        try:
            await self.adb.shell(f"am force-stop {package}")
            logger.info(f"Stopped app: {package}")
            return {"success": True, "action": "stopApp", "package": package}
        except Exception as e:
            return {"success": False, "error": f"Failed to stop {package}: {e}"}

    async def _tap_on(self, target: str, value: Any = None) -> dict[str, Any]:
        """Tap on an element described by target.

        Args:
            target: Element description (e.g., "text:发布" or "id:com.tencent.mm:id/btn")
            value: Optional coordinates (x, y) for direct tap
        """
        # If coordinates are provided directly, use them
        if value and isinstance(value, dict):
            x = value.get("x")
            y = value.get("y")
            if x is not None and y is not None:
                return await self._tap_coordinates(x, y)

        # Parse target to get element info
        # Format: "text:xxx" or "id:xxx" or "point:x,y"
        if target.startswith("text:"):
            text = target[5:]
            coords = await self._find_element_by_text(text)
            if coords:
                return await self._tap_coordinates(coords[0], coords[1])
            return {"success": False, "error": f"Element not found: {text}"}
        elif target.startswith("id:"):
            resource_id = target[3:]
            coords = await self._find_element_by_id(resource_id)
            if coords:
                return await self._tap_coordinates(coords[0], coords[1])
            return {"success": False, "error": f"Element not found: {resource_id}"}
        elif target.startswith("point:"):
            # Direct coordinates: "point:100,200"
            parts = target[6:].split(",")
            if len(parts) == 2:
                x, y = int(parts[0]), int(parts[1])
                return await self._tap_coordinates(x, y)
        elif target.startswith("bounds:"):
            # Bounds format: "bounds:100,100,200,200" -> center tap
            parts = target[7:].split(",")
            if len(parts) == 4:
                x = (int(parts[0]) + int(parts[2])) // 2
                y = (int(parts[1]) + int(parts[3])) // 2
                return await self._tap_coordinates(x, y)

        return {"success": False, "error": f"Cannot parse target: {target}"}

    async def _tap_coordinates(self, x: int, y: int) -> dict[str, Any]:
        """Tap at specific coordinates."""
        try:
            await self.adb.tap(x, y)
            logger.info(f"Tapped at ({x}, {y})")
            return {"success": True, "action": "tapOn", "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": f"Tap failed: {e}"}

    async def _find_element_by_text(self, text: str) -> Optional[tuple[int, int]]:
        """Find element center coordinates by text using UI automator."""
        try:
            # Use UI automator to find element bounds
            cmd = (
                f'uiautomator dump /sdcard/ui.xml && '
                f'cat /sdcard/ui.xml | grep -i "{text}" | head -1'
            )
            output = await self.adb.shell(cmd)

            # Alternative: use dumpsys to find element
            if not output.strip():
                # Try with mInjection or get from node info
                cmd2 = (
                    f"uiconsole `uiwhoami '{text}'` 2>/dev/null || "
                    f"dumpsys ui | grep -A5 -B5 '{text}' | head -20"
                )
                output = await self.adb.shell(cmd2)

            # For now, return None to indicate we need vision-based approach
            # The actual element finding will be done by AI analysis of screenshot
            return None
        except Exception as e:
            logger.debug(f"Element find error: {e}")
            return None

    async def _find_element_by_id(self, resource_id: str) -> Optional[tuple[int, int]]:
        """Find element center coordinates by resource ID."""
        # This would require UI automator - simplified for now
        return None

    async def _input_text(self, text: str) -> dict[str, Any]:
        """Input text into focused field."""
        if not text:
            return {"success": False, "error": "No text provided"}

        try:
            # Escape special characters for shell
            escaped = text.replace(" ", "%s").replace("'", "\\'")
            await self.adb.shell(f"input text '{escaped}'")
            logger.info(f"Input text: {text[:50]}...")
            return {"success": True, "action": "inputText", "text": text}
        except Exception as e:
            return {"success": False, "error": f"Input text failed: {e}"}

    async def _swipe(self, value: Any) -> dict[str, Any]:
        """Perform swipe gesture.

        Args:
            value: Dict with startX, startY, endX, endY (0-1 normalized) and duration
        """
        if not value:
            return {"success": False, "error": "No swipe params provided"}

        # Get screen resolution
        width, height = await self.adb.get_screen_resolution()
        if width == 0 or height == 0:
            return {"success": False, "error": "Could not get screen resolution"}

        # Parse swipe params (normalize 0-1 to pixels)
        start_x = int(value.get("startX", 0.5) * width)
        start_y = int(value.get("startY", 0.8) * height)
        end_x = int(value.get("endX", 0.5) * height)
        end_y = int(value.get("endY", 0.2) * height)
        duration = int(value.get("duration", 300))

        try:
            await self.adb.swipe(start_x, start_y, end_x, end_y, duration)
            logger.info(f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            return {
                "success": True,
                "action": "swipe",
                "from": (start_x, start_y),
                "to": (end_x, end_y),
            }
        except Exception as e:
            return {"success": False, "error": f"Swipe failed: {e}"}

    async def _press_key(self, key_name: str) -> dict[str, Any]:
        """Press a hardware key."""
        if not key_name:
            return {"success": False, "error": "No key name provided"}

        keycode = self.KEY_CODES.get(key_name.upper())
        if not keycode:
            # Try parsing as numeric keycode
            try:
                keycode = int(key_name)
            except ValueError:
                return {"success": False, "error": f"Unknown key: {key_name}"}

        try:
            await self.adb.press_key(keycode)
            logger.info(f"Pressed key: {key_name} ({keycode})")
            return {"success": True, "action": "pressKey", "key": key_name, "keycode": keycode}
        except Exception as e:
            return {"success": False, "error": f"Press key failed: {e}"}

    async def _wait(self, seconds: float = 1.0) -> dict[str, Any]:
        """Wait for animations/transitions."""
        await asyncio.sleep(seconds)
        return {"success": True, "action": "waitForAnimationToEnd", "waited": seconds}

    async def screenshot(self) -> bytes:
        """Capture screenshot from device.

        Returns:
            Screenshot bytes (PNG)
        """
        try:
            # Create temp file on device
            device_path = "/sdcard/agent_screenshot.png"

            # Take screenshot
            await self.adb.shell(f"screencap -p {device_path}")

            # Pull to temp local file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                local_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", self.device_serial, "pull", device_path, local_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Read screenshot bytes
            screenshot_bytes = Path(local_path).read_bytes()

            # Cleanup
            Path(local_path).unlink(missing_ok=True)
            await self.adb.shell(f"rm {device_path}")

            return screenshot_bytes

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return b""