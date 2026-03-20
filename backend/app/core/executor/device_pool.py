"""Device pool manager for allocating and managing devices."""
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.device import Device
from app.db.redis import redis_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DevicePool:
    """Manages device allocation and availability."""

    def __init__(self, db: AsyncSession):
        """Initialize device pool."""
        self.db = db
        self._locks = {}  # device_id -> asyncio.Lock
        self._heartbeat_tasks = {}

    async def get_available_device(self) -> Optional[Device]:
        """Get an available device from the pool.

        Returns:
            Available device or None
        """
        # Check Redis cache first
        cached = await redis_client.get_json("device:available")
        if cached:
            device_id = cached.get("device_id")
            if device_id:
                device = await self._get_and_validate_device(device_id)
                if device:
                    return device

        # Query database for online devices
        result = await self.db.execute(
            select(Device)
            .where(Device.status == "online")
            .order_by(Device.last_heartbeat.desc())
            .limit(1)
        )
        device = result.scalar_one_or_none()

        if device:
            # Cache the device
            await redis_client.set_json(
                "device:available",
                {"device_id": device.device_id},
                expire=60,
            )

        return device

    async def _get_and_validate_device(self, device_id: str) -> Optional[Device]:
        """Get device and validate it's still available."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if not device or device.status != "online":
            # Clear cache
            await redis_client.delete("device:available")
            return None

        # Check heartbeat is recent (within 2 minutes)
        if device.last_heartbeat:
            if datetime.utcnow() - device.last_heartbeat > timedelta(minutes=2):
                logger.warning(f"Device {device_id} heartbeat too old")
                return None

        return device

    async def allocate_device(self, task_id: str, device_id: str = None) -> Optional[Device]:
        """Allocate a device for a task.

        Args:
            task_id: Task to allocate for
            device_id: Specific device ID or None for auto-select

        Returns:
            Allocated device or None
        """
        if device_id:
            # Allocate specific device
            lock = self._locks.setdefault(device_id, asyncio.Lock())
            async with lock:
                result = await self.db.execute(
                    select(Device).where(
                        Device.device_id == device_id,
                        Device.status == "online",
                    )
                )
                device = result.scalar_one_or_none()

                if device:
                    device.status = "busy"
                    device.current_task_id = task_id
                    await self.db.flush()
                    logger.info(f"Allocated device {device_id} for task {task_id}")
        else:
            # Auto-select available device
            device = await self.get_available_device()
            if device:
                await self.allocate_device(task_id, device.device_id)

        return device

    async def release_device(self, device_id: str) -> None:
        """Release a device back to the pool.

        Args:
            device_id: Device to release
        """
        lock = self._locks.get(device_id)
        if not lock:
            lock = self._locks.setdefault(device_id, asyncio.Lock())

        async with lock:
            result = await self.db.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()

            if device:
                device.status = "online"
                device.current_task_id = None
                await self.db.flush()
                logger.info(f"Released device {device_id}")

                # Clear cache
                await redis_client.delete("device:available")

    async def mark_offline(self, device_id: str) -> None:
        """Mark a device as offline.

        Args:
            device_id: Device to mark offline
        """
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if device:
            device.status = "offline"
            await self.db.flush()
            logger.warning(f"Device {device_id} marked offline")

    async def update_heartbeat(self, device_id: str) -> None:
        """Update device heartbeat.

        Args:
            device_id: Device ID
        """
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if device:
            device.last_heartbeat = datetime.utcnow()
            await self.db.flush()
