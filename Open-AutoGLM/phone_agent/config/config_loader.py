"""Configuration loader for agent config file."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LLMConfig:
    """LLM configuration."""
    base_url: str = "http://localhost:8000/v1"
    model: str = "autoglm-phone-9b"
    api_key: str = "EMPTY"


@dataclass
class ServerConfig:
    """Server configuration."""
    ws_url: str = "ws://localhost:8000/ws/devices/{device_id}"
    heartbeat_interval: int = 30


@dataclass
class AgentConfig:
    """Agent configuration."""
    device_id: str = "auto"
    device_name: str = "我的手机"
    device_type: str = "adb"
    max_steps: int = 100
    lang: str = "cn"


@dataclass
class Config:
    """Full agent configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config file. If not provided, looks for default config.

    Returns:
        Config object with all settings.
    """
    if config_path is None:
        # Look for default config in phone_agent/config/ directory
        default_path = Path(__file__).parent / "agent_config.json"
        if default_path.exists():
            config_path = str(default_path)

    if config_path is None or not Path(config_path).exists():
        # Return default config if no file found
        return Config()

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    llm_data = data.get("llm", {})
    server_data = data.get("server", {})
    agent_data = data.get("agent", {})

    return Config(
        llm=LLMConfig(
            base_url=os.environ.get("PHONE_AGENT_BASE_URL", llm_data.get("base_url", "http://localhost:8000/v1")),
            model=os.environ.get("PHONE_AGENT_MODEL", llm_data.get("model", "autoglm-phone-9b")),
            api_key=os.environ.get("PHONE_AGENT_API_KEY", llm_data.get("api_key", "EMPTY")),
        ),
        server=ServerConfig(
            ws_url=os.environ.get("PHONE_AGENT_WS_URL", server_data.get("ws_url", "ws://localhost:8000/ws/devices/{device_id}")),
            heartbeat_interval=server_data.get("heartbeat_interval", 30),
        ),
        agent=AgentConfig(
            device_id=os.environ.get("PHONE_AGENT_DEVICE_ID", agent_data.get("device_id", "auto")),
            device_name=agent_data.get("device_name", "我的手机"),
            device_type=agent_data.get("device_type", "adb"),
            max_steps=int(os.environ.get("PHONE_AGENT_MAX_STEPS", agent_data.get("max_steps", 100))),
            lang=os.environ.get("PHONE_AGENT_LANG", agent_data.get("lang", "cn")),
        ),
    )


def resolve_device_id(config: Config, adb_devices: list[str] = None) -> str:
    """Resolve the device ID from config.

    Args:
        config: The Config object
        adb_devices: List of available ADB device IDs

    Returns:
        Resolved device ID string
    """
    device_id = config.agent.device_id

    if device_id == "auto":
        if adb_devices:
            # Use first available device
            return adb_devices[0]
        return "unknown_device"

    return device_id


def resolve_ws_url(config: Config, device_id: str) -> str:
    """Resolve the WebSocket URL with device_id placeholder.

    Args:
        config: The Config object
        device_id: The device ID to substitute

    Returns:
        Resolved WebSocket URL
    """
    return config.server.ws_url.format(device_id=device_id)
