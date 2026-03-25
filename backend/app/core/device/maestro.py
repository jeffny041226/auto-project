"""Maestro device integration."""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

from app.core.device.adb import ADBConnector
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MaestroDeviceConnector:
    """Connects Maestro execution to real Android devices via ADB."""

    def __init__(self, device_serial: str = None):
        """
        Initialize Maestro device connector.

        Args:
            device_serial: ADB serial (e.g., "192.168.1.100:5555" or "RFCAM123456")
        """
        self.device_serial = device_serial
        self.adb = ADBConnector()

    async def connect(self, device_ip: str, device_port: int = 5555) -> bool:
        """Connect to device via network ADB.

        Args:
            device_ip: Device IP address
            device_port: ADB port (default 5555)

        Returns:
            True if connected successfully
        """
        connected = await self.adb.connect(device_ip, device_port)
        if connected:
            self.device_serial = f"{device_ip}:{device_port}"
            self.adb.set_device(self.device_serial)
        return connected

    async def execute_flow(
        self,
        yaml_content: str,
        timeout: int = 300,
    ) -> dict:
        """Execute Maestro flow on connected device.

        Args:
            yaml_content: Maestro YAML flow definition
            timeout: Execution timeout in seconds

        Returns:
            Execution result dict
        """
        if not self.device_serial:
            return {
                "success": False,
                "error": "No device connected",
            }

        # Write YAML to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Execute Maestro
            cmd = [
                "maestro",
                "test",
                "--device", self.device_serial,
                yaml_path,
                "--format", "json",
            ]

            logger.info(f"Executing Maestro: {' '.join(cmd)}")

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=timeout,
                )

                output = stdout.decode() if stdout else ""
                error = stderr.decode() if stderr else ""

                if result.returncode != 0:
                    return {
                        "success": False,
                        "returncode": result.returncode,
                        "error": error or "Maestro execution failed",
                        "output": output,
                    }

                # Parse JSON output if available
                parsed = None
                if output:
                    try:
                        parsed = json.loads(output)
                    except json.JSONDecodeError:
                        pass

                return {
                    "success": True,
                    "returncode": 0,
                    "output": output,
                    "parsed": parsed,
                }

            except TimeoutError:
                result.kill()
                return {
                    "success": False,
                    "error": "Maestro execution timed out",
                    "timeout": True,
                }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "Maestro not installed. Install from https://maestro.mobile.dev/",
            }

        except Exception as e:
            logger.error(f"Maestro execution error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

        finally:
            # Cleanup temp file
            Path(yaml_path).unlink(missing_ok=True)

    async def get_device_info(self) -> dict:
        """Get device information."""
        if not self.device_serial:
            return {}

        self.adb.set_device(self.device_serial)

        try:
            resolution = await self.adb.get_screen_resolution()
            android_version = await self.adb.get_android_version()
            model = await self.adb.get_device_model()

            return {
                "serial": self.device_serial,
                "model": model.strip() if model else None,
                "android_version": android_version.strip() if android_version else None,
                "resolution": {
                    "width": resolution[0],
                    "height": resolution[1],
                },
            }

        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {}

    async def get_current_app(self) -> Optional[str]:
        """Get currently running app package name."""
        if not self.device_serial:
            return None

        self.adb.set_device(self.device_serial)

        try:
            package, activity = await self.adb.get_top_activity()
            return package

        except Exception as e:
            logger.error(f"Failed to get current app: {e}")
            return None

    async def take_screenshot(self) -> Optional[bytes]:
        """Take screenshot of current screen."""
        if not self.device_serial:
            return None

        self.adb.set_device(self.device_serial)

        try:
            return await self.adb.screenshot()

        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None

    @staticmethod
    async def list_available_devices() -> list[dict]:
        """List all ADB-available devices.

        Returns:
            List of device info dicts
        """
        devices = await ADBConnector.devices()
        return [
            {
                "serial": d.serial,
                "status": d.status,
                "model": d.model,
                "product": d.product,
            }
            for d in devices
            if d.status == "device"
        ]


class MaestroServerMode:
    """Maestro Server mode for remote device control."""

    def __init__(self, host: str = "0.0.0.0", port: int = 7000):
        self.host = host
        self.port = port
        self._process: Optional[asyncio.subprocess.Process] = None

    async def start(self):
        """Start Maestro server."""
        cmd = [
            "maestro", "server",
            "--host", self.host,
            "--port", str(self.port),
        ]

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        logger.info(f"Maestro server started on {self.host}:{self.port}")

    async def stop(self):
        """Stop Maestro server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            logger.info("Maestro server stopped")

    async def is_running(self) -> bool:
        """Check if server is running."""
        if not self._process:
            return False

        try:
            return self._process.returncode is None
        except Exception:
            return False
