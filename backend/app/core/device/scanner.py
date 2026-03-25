"""ADB Device Scanner - Auto-discover and register connected Android devices."""
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.device import Device
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ADBDevice:
    """ADB connected device info."""

    def __init__(self, serial: str, status: str, product: str = None, model: str = None):
        self.serial = serial
        self.status = status
        self.product = product
        self.model = model


class ADBDeviceScanner:
    """Periodically scans for connected ADB devices and auto-registers them."""

    def __init__(
        self,
        db_session_factory,
        scan_interval: int = 10,
        device_name_prefix: str = "ADB Device",
    ):
        """
        Initialize ADB device scanner.

        Args:
            db_session_factory: Database session factory (e.g., async_sessionmaker)
            scan_interval: Interval between scans in seconds
            device_name_prefix: Prefix for auto-created device names
        """
        self.db_session_factory = db_session_factory
        self.scan_interval = scan_interval
        self.device_name_prefix = device_name_prefix
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._known_devices: set[str] = set()

    async def start(self):
        """Start the scanner background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info(f"ADB device scanner started (interval: {self.scan_interval}s)")

    async def stop(self):
        """Stop the scanner background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ADB device scanner stopped")

    async def _scan_loop(self):
        """Main scanning loop."""
        while self._running:
            try:
                await self._scan_devices()
            except Exception as e:
                logger.error(f"ADB scan error: {e}")

            await asyncio.sleep(self.scan_interval)

    async def _scan_devices(self):
        """Scan for connected ADB devices and register them."""
        devices = await self._list_adb_devices()

        # Find newly connected devices
        current_serials = {d.serial for d in devices if d.status == "device"}

        # Register new devices
        for device in devices:
            if device.status == "device" and device.serial not in self._known_devices:
                await self._register_device(device)
                self._known_devices.add(device.serial)

        # Mark disconnected devices as offline
        for serial in self._known_devices - current_serials:
            await self._mark_device_offline(serial)
            self._known_devices.discard(serial)

        if current_serials:
            logger.debug(f"ADB devices: {current_serials}")

    async def _list_adb_devices(self) -> list[ADBDevice]:
        """List devices connected via ADB."""
        import subprocess

        devices = []

        try:
            result = await asyncio.create_subprocess_exec(
                "adb", "devices", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            output = stdout.decode()

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

                    devices.append(ADBDevice(
                        serial=device_info.get("serial"),
                        status=device_info.get("status"),
                        product=device_info.get("product"),
                        model=device_info.get("model"),
                    ))

        except FileNotFoundError:
            logger.warning("ADB not found - is Android SDK installed?")
        except Exception as e:
            logger.error(f"Failed to list ADB devices: {e}")

        return devices

    async def _register_device(self, device: ADBDevice):
        """Register a new device or update existing one."""
        async with self.db_session_factory() as db:
            try:
                # Check if device already exists
                result = await db.execute(
                    select(Device).where(Device.device_id == device.serial)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing device status
                    existing.status = "online"
                    existing.last_heartbeat = datetime.utcnow()
                    if device.model:
                        existing.model = device.model
                    logger.info(f"Device {device.serial} came online")
                else:
                    # Create new device
                    device_name = f"{self.device_name_prefix} ({device.serial[:8]})"
                    if device.model:
                        device_name = f"{device.model} ({device.serial[:8]})"

                    # Get detailed device info
                    os_version = "Unknown"
                    try:
                        import subprocess
                        result = await asyncio.create_subprocess_exec(
                            "adb", "-s", device.serial, "shell", "getprop", "ro.build.version.release",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, _ = await result.communicate()
                        os_version = stdout.decode().strip() or "Unknown"
                    except Exception:
                        pass

                    new_device = Device(
                        device_id=device.serial,
                        device_name=device_name,
                        model=device.model,
                        os_version=os_version,
                        status="online",
                    )
                    db.add(new_device)
                    logger.info(f"Auto-registered device: {device.serial} ({device.model})")

                await db.commit()

            except Exception as e:
                logger.error(f"Failed to register device {device.serial}: {e}")
                await db.rollback()

    async def _mark_device_offline(self, device_id: str):
        """Mark a device as offline."""
        async with self.db_session_factory() as db:
            try:
                result = await db.execute(
                    select(Device).where(Device.device_id == device_id)
                )
                device = result.scalar_one_or_none()

                if device:
                    device.status = "offline"
                    device.last_heartbeat = datetime.utcnow()
                    await db.commit()
                    logger.info(f"Device {device_id} went offline")

            except Exception as e:
                logger.error(f"Failed to mark device {device_id} offline: {e}")
                await db.rollback()

    async def discover_now(self) -> list[ADBDevice]:
        """Manually trigger a device discovery scan.

        Returns:
            List of discovered ADB devices
        """
        return await self._list_adb_devices()

    async def get_device_info(self, serial: str) -> dict:
        """Get detailed info about a connected ADB device.

        Args:
            serial: Device serial number

        Returns:
            Dict with device info
        """
        import subprocess

        info = {"serial": serial}

        try:
            # Get device model
            result = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "shell", "getprop", "ro.product.model",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            info["model"] = stdout.decode().strip()

            # Get Android version
            result = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "shell", "getprop", "ro.build.version.release",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            info["android_version"] = stdout.decode().strip()

            # Get screen resolution
            result = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "shell", "wm", "size",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            size_output = stdout.decode().strip()
            if "Physical" in size_output:
                info["resolution"] = size_output.split(":")[1].strip()

        except Exception as e:
            logger.error(f"Failed to get device info for {serial}: {e}")

        return info


# Global scanner instance
_scanner: Optional[ADBDeviceScanner] = None


def get_device_scanner() -> Optional[ADBDeviceScanner]:
    """Get the global device scanner instance."""
    return _scanner


async def start_device_scanner(db_session_factory):
    """Start the global device scanner."""
    global _scanner

    if _scanner is None:
        _scanner = ADBDeviceScanner(db_session_factory, scan_interval=10)
        await _scanner.start()

    return _scanner


async def stop_device_scanner():
    """Stop the global device scanner."""
    global _scanner

    if _scanner:
        await _scanner.stop()
        _scanner = None
