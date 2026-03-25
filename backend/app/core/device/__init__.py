"""Device management module."""
from app.core.device.agent import (
    DeviceAgentManager,
    DeviceConnection,
    device_agent_manager,
    handle_device_websocket,
)
from app.core.device.adb import ADBConnector, ADBDevice
from app.core.device.maestro import MaestroDeviceConnector, MaestroServerMode
from app.core.device.scanner import (
    ADBDeviceScanner,
    get_device_scanner,
    start_device_scanner,
    stop_device_scanner,
)

__all__ = [
    "DeviceAgentManager",
    "DeviceConnection",
    "device_agent_manager",
    "handle_device_websocket",
    "ADBConnector",
    "ADBDevice",
    "MaestroDeviceConnector",
    "MaestroServerMode",
    "ADBDeviceScanner",
    "get_device_scanner",
    "start_device_scanner",
    "stop_device_scanner",
]
