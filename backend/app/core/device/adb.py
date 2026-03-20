"""ADB connector for Android device control."""
import asyncio
import re
import subprocess
from dataclasses import dataclass
from typing import Optional, List

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ADBDevice:
    """Android device info from ADB."""
    serial: str
    status: str
    product: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    transport_id: Optional[str] = None


class ADBConnector:
    """Connector for ADB (Android Debug Bridge) operations."""

    def __init__(self, host: str = None, port: int = 5555):
        """
        Initialize ADB connector.

        Args:
            host: Device IP (for network ADB), None for local
            port: ADB port
        """
        self.host = host
        self.port = port
        self._device_serial = f"{host}:{port}" if host else None

    @staticmethod
    async def devices() -> List[ADBDevice]:
        """List all connected ADB devices."""
        try:
            result = await asyncio.create_subprocess_exec(
                "adb", "devices", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            output = stdout.decode()

            devices = []
            # Parse: "serial product:xxx model:xxx device:xxx transport_id:xxx"
            for line in output.split("\n")[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    status = parts[1]

                    device_info = {"serial": serial, "status": status}
                    for part in parts[2:]:
                        if ":" in part:
                            key, value = part.split(":", 1)
                            device_info[key] = value

                    devices.append(ADBDevice(**device_info))

            return devices

        except Exception as e:
            logger.error(f"Failed to list ADB devices: {e}")
            return []

    async def connect(self, device_ip: str, device_port: int = 5555) -> bool:
        """Connect to a device over network."""
        try:
            result = await asyncio.create_subprocess_exec(
                "adb", "connect", f"{device_ip}:{device_port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            output = stdout.decode().strip()

            if "connected" in output.lower() or "already connected" in output.lower():
                logger.info(f"Connected to {device_ip}:{device_port}")
                self.host = device_ip
                self.port = device_port
                self._device_serial = f"{device_ip}:{device_port}"
                return True

            logger.warning(f"Failed to connect: {output}")
            return False

        except Exception as e:
            logger.error(f"ADB connect error: {e}")
            return False

    async def disconnect(self, device_ip: str = None, device_port: int = 5555) -> bool:
        """Disconnect from a network device."""
        target = device_ip or self.host
        port = device_port or self.port

        try:
            result = await asyncio.create_subprocess_exec(
                "adb", "-s", f"{target}:{port}", "disconnect",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            return True

        except Exception as e:
            logger.error(f"ADB disconnect error: {e}")
            return False

    async def shell(self, command: str, timeout: int = 30) -> str:
        """Execute shell command on device."""
        serial = self._device_serial
        if not serial:
            raise ValueError("No device connected")

        try:
            result = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "shell", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=timeout,
            )
            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=timeout + 5,
            )

            if result.returncode != 0:
                logger.warning(f"Shell command returned {result.returncode}: {stderr.decode()}")

            return stdout.decode()

        except asyncio.TimeoutExpired:
            logger.error(f"Shell command timed out: {command}")
            raise
        except Exception as e:
            logger.error(f"ADB shell error: {e}")
            raise

    async def get_screen_resolution(self) -> tuple[int, int]:
        """Get device screen resolution."""
        output = await self.shell("wm size")
        # Parse: "Physical size: 1080x1920" or "Override size: 1080x1920"
        match = re.search(r"(\d+)x(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    async def get_android_version(self) -> str:
        """Get Android version."""
        return await self.shell("getprop ro.build.version.release")

    async def get_device_model(self) -> str:
        """Get device model."""
        return await self.shell("getprop ro.product.model")

    async def get_package_version(self, package: str) -> str:
        """Get installed app version."""
        output = await self.shell(f"dumpsys package {package} | grep versionName")
        match = re.search(r"versionName=([^\s]+)", output)
        return match.group(1) if match else None

    async def is_screen_on(self) -> bool:
        """Check if screen is on."""
        output = await self.shell("dumpsys power | grep 'mScreenOn'")
        return "mScreenOn=true" in output

    async def tap(self, x: int, y: int):
        """Tap at coordinates."""
        await self.shell(f"input tap {x} {y}")

    async def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 300):
        """Swipe from start to end coordinates."""
        await self.shell(f"input swipe {start_x} {start_y} {end_x} {end_y} {duration}")

    async def input_text(self, text: str):
        """Input text."""
        # Escape special characters
        text = text.replace(" ", "%s")
        await self.shell(f"input text '{text}'")

    async def press_key(self, keycode: int):
        """Press key code (e.g., 4=back, 3=home, 82=menu)."""
        await self.shell(f"input keyevent {keycode}")

    async def start_activity(self, package: str, activity: str = None):
        """Start an app activity."""
        if activity:
            await self.shell(f"am start -n {package}/{activity}")
        else:
            await self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    async def screenshot(self, output_path: str = "/sdcard/screenshot.png") -> bytes:
        """Take screenshot."""
        await self.shell(f"screencap -p {output_path}")
        # Pull file
        serial = self._device_serial
        result = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "pull", output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await result.communicate()
        return stdout

    async def install_apk(self, apk_path: str, reinstall: bool = False) -> bool:
        """Install APK."""
        serial = self._device_serial
        cmd = ["adb", "-s", serial, "install"]
        if reinstall:
            cmd.append("-r")
        cmd.append(apk_path)

        result = await asyncio.create_subprocess_exec(*cmd)
        stdout, _ = await result.communicate()
        return result.returncode == 0

    async def uninstall_package(self, package: str) -> bool:
        """Uninstall package."""
        serial = self._device_serial
        result = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "uninstall", package,
        )
        await result.communicate()
        return result.returncode == 0

    async def get_top_activity(self) -> tuple[Optional[str], Optional[str]]:
        """Get current top activity (package, activity)."""
        output = await self.shell("dumpsys activity activities | grep mResumedActivity")
        match = re.search(r"(\S+)/(\S+)", output)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def set_device(self, serial: str):
        """Set target device by serial."""
        self._device_serial = serial
