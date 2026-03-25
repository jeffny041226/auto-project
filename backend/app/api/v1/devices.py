"""Devices API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceListResponse
from app.services.device import DeviceService

router = APIRouter()


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(device_data: DeviceCreate, db: AsyncSession = Depends(get_db)):
    """Register a new device."""
    service = DeviceService(db)
    device = await service.create_device(device_data)
    return device


@router.get("/", response_model=DeviceListResponse)
async def list_devices(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List all devices."""
    service = DeviceService(db)
    devices, total = await service.list_devices(skip, limit)
    return {"items": devices, "total": total}


@router.get("/discover")
async def discover_adb_devices():
    """Discover and auto-register available ADB devices.

    Scans for connected Android devices via ADB and automatically
    registers any new devices in the database.

    Returns:
        List of discovered ADB devices with their registration status.
    """
    from app.core.device.scanner import get_device_scanner

    scanner = get_device_scanner()
    if scanner:
        # Trigger immediate scan
        devices = await scanner.discover_now()
        device_list = [
            {
                "serial": d.serial,
                "status": d.status,
                "model": d.model,
                "product": d.product,
            }
            for d in devices
        ]
    else:
        # Fallback to Maestro connector
        from app.core.device.maestro import MaestroDeviceConnector
        device_list = await MaestroDeviceConnector.list_available_devices()

    return {
        "devices": device_list,
        "count": len(device_list),
        "auto_registered": scanner is not None,
    }


@router.post("/connect")
async def connect_to_device(device_ip: str, device_port: int = 5555):
    """Connect to a network Android device via ADB.

    Args:
        device_ip: Device IP address
        device_port: ADB port (default 5555)
    """
    from app.core.device.maestro import MaestroDeviceConnector

    connector = MaestroDeviceConnector()
    connected = await connector.connect(device_ip, device_port)

    if connected:
        device_info = await connector.get_device_info()
        return {
            "success": True,
            "device": device_info,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect to device",
        )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get device by ID."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: str, device_data: DeviceUpdate, db: AsyncSession = Depends(get_db)):
    """Update device."""
    service = DeviceService(db)
    device = await service.update_device(device_id, device_data)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.get("/{device_id}/info")
async def get_device_info(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed device information via ADB."""
    from app.core.device.maestro import MaestroDeviceConnector

    service = DeviceService(db)
    device = await service.get_device(device_id)

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # Get live info from device
    connector = MaestroDeviceConnector(device_id)
    connector.adb.set_device(device_id)

    info = await connector.get_device_info()
    current_app = await connector.get_current_app()

    return {
        "device": device,
        "live_info": info,
        "current_app": current_app,
    }


@router.post("/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, db: AsyncSession = Depends(get_db)):
    """Receive device heartbeat."""
    service = DeviceService(db)
    await service.update_heartbeat(device_id)
    return {"status": "ok"}


@router.post("/{device_id}/commands")
async def send_command_to_device(device_id: str, command: dict):
    """Send a command to a connected device agent via WebSocket.

    Args:
        device_id: Device ID
        command: Command to send, e.g. {"action": "run_task", "params": {"task": "...", "task_id": "..."}}
    """
    from app.core.device.agent import device_agent_manager

    success = await device_agent_manager.send_command(device_id, command)
    if success:
        return {"status": "sent", "device_id": device_id}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not connected or command failed",
        )
