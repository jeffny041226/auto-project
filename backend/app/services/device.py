"""Device service for API endpoints."""
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DeviceService:
    """Service for device management API."""

    def __init__(self, db: AsyncSession):
        """Initialize device service."""
        self.db = db

    async def create_device(self, device_data: DeviceCreate) -> DeviceResponse:
        """Register a new device."""
        device = Device(
            device_id=device_data.device_id,
            device_name=device_data.device_name,
            os_version=device_data.os_version,
            model=device_data.model,
            status="offline",
        )

        self.db.add(device)
        await self.db.flush()
        await self.db.refresh(device)

        logger.info(f"Device registered: {device.device_id}")
        return DeviceResponse.model_validate(device)

    async def get_device(self, device_id: str) -> Optional[DeviceResponse]:
        """Get device by ID."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()
        if device:
            return DeviceResponse.model_validate(device)
        return None

    async def list_devices(
        self, skip: int = 0, limit: int = 20, status: str = None
    ) -> tuple[list[DeviceResponse], int]:
        """List devices with pagination."""
        query = select(Device)
        count_query = select(Device)

        if status:
            query = query.where(Device.status == status)
            count_query = count_query.where(Device.status == status)

        from sqlalchemy import func

        total_result = await self.db.execute(select(func.count(Device.id)))
        total = total_result.scalar() or 0

        query = query.order_by(Device.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        devices = result.scalars().all()

        return [DeviceResponse.model_validate(d) for d in devices], total

    async def update_device(
        self, device_id: str, device_data: DeviceUpdate
    ) -> Optional[DeviceResponse]:
        """Update device."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if not device:
            return None

        update_data = device_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "last_heartbeat" and value:
                value = datetime.fromisoformat(value) if isinstance(value, str) else value
            setattr(device, field, value)

        await self.db.flush()
        await self.db.refresh(device)

        logger.info(f"Device updated: {device_id}")
        return DeviceResponse.model_validate(device)

    async def update_heartbeat(self, device_id: str) -> None:
        """Update device last heartbeat time."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if device:
            device.last_heartbeat = datetime.utcnow()
            await self.db.flush()

    async def allocate_device(self, status: str = "busy") -> Optional[Device]:
        """Allocate an available device.

        Args:
            status: Status to set when allocated

        Returns:
            Available device or None
        """
        result = await self.db.execute(
            select(Device)
            .where(Device.status == "online")
            .order_by(Device.last_heartbeat.desc())
            .limit(1)
        )
        device = result.scalar_one_or_none()

        if device:
            device.status = status
            await self.db.flush()

        return device

    async def release_device(self, device_id: str) -> None:
        """Release a device back to the pool."""
        result = await self.db.execute(
            select(Device).where(Device.device_id == device_id)
        )
        device = result.scalar_one_or_none()

        if device:
            device.status = "online"
            device.current_task_id = None
            await self.db.flush()
