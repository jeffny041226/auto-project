"""Maestro driver for executing test scripts."""
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Default Maestro path - use HOME env var for local Mac installation
DEFAULT_MAESTRO_PATH = os.path.expanduser("~/.maestro/bin/maestro")

# Package names for common apps
APP_PACKAGE_MAP = {
    "wechat": "com.tencent.mm",
    "weixin": "com.tencent.mm",
    "alipay": "com.eg.android.AlipayGphone",
    "taobao": "com.taobao.taobao",
    "jd": "com.jingdong.app.mall",
    "douyin": "com.ss.android.ugc.aweme",
    "instagram": "com.instagram.android",
    "whatsapp": "com.whatsapp",
    "telegram": "org.telegram.messenger",
    "twitter": "com.twitter.android",
    "facebook": "com.facebook.katana",
    "sina": "com.sina.weibo",
    "weibo": "com.sina.weibo",
    "shanhai": "com.shanhai.app",  # Placeholder - need actual package name
}


class MaestroDriver:
    """Driver for executing Maestro test scripts."""

    def __init__(self, binary_path: str = None):
        """Initialize Maestro driver."""
        self.binary_path = binary_path or DEFAULT_MAESTRO_PATH

    def is_installed(self) -> bool:
        """Check if Maestro is installed."""
        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return False

    def are_maestro_apks_installed(self, device_serial: str) -> bool:
        """Check if Maestro agent APKs are installed on device.

        Args:
            device_serial: Device serial number

        Returns:
            True if both APKs are installed
        """
        try:
            result = subprocess.run(
                ["adb", "-s", device_serial, "shell", "pm list packages"],
                capture_output=True,
                timeout=10,
            )
            packages = result.stdout.decode() if result.stdout else ""
            return "dev.mobile.maestro" in packages and "dev.mobile.maestro.test" in packages
        except Exception as e:
            logger.warning(f"Failed to check Maestro APKs: {e}")
            return False

    def install(self) -> tuple[bool, Optional[str]]:
        """Install Maestro CLI.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            logger.info("Installing Maestro CLI...")

            # Download and run installer
            install_cmd = [
                "curl", "-sL", "https://get.maestro.mobile.dev", "|", "bash"
            ]

            result = subprocess.run(
                " ".join(install_cmd),
                shell=True,
                capture_output=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.info("Maestro CLI installed successfully")
                return True, None
            else:
                error = result.stderr.decode() if result.stderr else "Installation failed"
                logger.error(f"Maestro installation failed: {error}")
                return False, error

        except subprocess.TimeoutExpired:
            error = "Installation timed out"
            logger.error(error)
            return False, error
        except Exception as e:
            error = str(e)
            logger.error(f"Maestro installation error: {e}")
            return False, error

    async def execute(
        self,
        yaml_content: str,
        device_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Execute a Maestro YAML script.

        Args:
            yaml_content: Maestro YAML script content
            device_id: Device ID to execute on
            task_id: Task ID for tracking

        Returns:
            Dict with execution results
        """
        logger.info(f"Executing Maestro script for task {task_id} on device {device_id}")

        # Check if Maestro is installed
        if not self.is_installed():
            logger.warning(f"Maestro not found at {self.binary_path}, attempting to install...")
            success, error = self.install()
            if not success:
                return {
                    "success": False,
                    "error": f"Maestro installation failed: {error}",
                }

        # Check if Maestro APKs are already installed
        if self.are_maestro_apks_installed(device_id):
            logger.info(f"Maestro APKs already installed on device {device_id}, skipping installation")
        else:
            logger.info(f"Maestro APKs not found on device {device_id}, will be installed by Maestro")

        # Write YAML to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Build command - Maestro version doesn't support JSON format
            # Add --no-reinstall-driver to skip APK reinstallation if already installed
            cmd = [
                self.binary_path,
                "test",
                "--no-reinstall-driver",
                "--device", device_id,
                yaml_path,
            ]

            # Execute with timeout
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=300,  # 5 minute timeout
            )

            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""

            if result.returncode != 0:
                logger.error(f"Maestro execution failed. returncode={result.returncode}, error={error}, output={output[:500] if output else 'empty'}")
                return {
                    "success": False,
                    "returncode": result.returncode,
                    "error": error or output[:500] if output else "Unknown error",
                    "output": output,
                }

            # Parse JSON output if available
            parsed = None
            if output:
                try:
                    parsed = json.loads(output)
                except json.JSONDecodeError:
                    pass

            logger.info(f"Maestro execution completed for task {task_id}")
            return {
                "success": True,
                "returncode": result.returncode,
                "output": output,
                "parsed": parsed,
            }

        except asyncio.TimeoutError:
            logger.error(f"Maestro execution timed out for task {task_id}")
            return {
                "success": False,
                "error": "Execution timed out",
                "timeout": True,
            }
        except Exception as e:
            logger.error(f"Maestro execution error for task {task_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            # Cleanup temp file
            Path(yaml_path).unlink(missing_ok=True)

    async def record(self, device_id: str) -> dict[str, Any]:
        """Start Maestro recording session.

        Args:
            device_id: Device ID to record on

        Returns:
            Dict with recording session info
        """
        cmd = [
            self.binary_path,
            "record",
            "--device", device_id,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait a moment for recording to start
            await asyncio.sleep(2)

            return {
                "success": True,
                "session_id": str(process.pid),
                "running": process.returncode is None,
            }

        except Exception as e:
            logger.error(f"Maestro record error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def stop_recording(self, session_id: str) -> dict[str, Any]:
        """Stop Maestro recording session.

        Args:
            session_id: Recording session ID

        Returns:
            Dict with recorded YAML
        """
        try:
            # Send SIGTERM to stop recording
            process = subprocess.run(
                ["kill", session_id],
                capture_output=True,
            )

            return {
                "success": process.returncode == 0,
            }

        except Exception as e:
            logger.error(f"Maestro stop recording error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of connected devices.

        Returns:
            List of device info dicts
        """
        cmd = [self.binary_path, "devices"]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await result.communicate()
            output = stdout.decode()

            # Parse device list
            devices = []
            for line in output.split("\n"):
                if line.strip() and not line.startswith("INFO"):
                    devices.append({"id": line.strip()})

            return devices

        except Exception as e:
            logger.error(f"Maestro devices error: {e}")
            return []

    def validate_yaml(self, yaml_content: str) -> tuple[bool, Optional[str]]:
        """Validate Maestro YAML syntax.

        Args:
            yaml_content: YAML content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        cmd = [self.binary_path, "validate", "-"]

        try:
            result = subprocess.run(
                cmd,
                input=yaml_content.encode(),
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Validation failed"
                return False, error

            return True, None

        except subprocess.TimeoutExpired:
            return False, "Validation timed out"
        except Exception as e:
            return False, str(e)

    async def execute_step(
        self,
        step: dict[str, Any],
        device_id: str,
    ) -> dict[str, Any]:
        """Execute a single Maestro step.

        Args:
            step: Step dict with action, target, value
            device_id: Device serial

        Returns:
            Execution result
        """
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")

        # Build a minimal YAML for single step
        yaml_content = self._build_step_yaml(action, target, value)

        # Validate
        is_valid, error = self.validate_yaml(yaml_content)
        if not is_valid:
            return {"success": False, "error": f"Invalid step: {error}"}

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            cmd = [
                self.binary_path,
                "test",
                "--no-reinstall-driver",
                "--device", device_id,
                yaml_path,
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=60,  # 1 minute timeout per step
            )

            if result.returncode != 0:
                error = stderr.decode() if stderr else "Unknown error"
                return {"success": False, "error": error}

            return {"success": True, "action": action, "target": target}

        except asyncio.TimeoutError:
            return {"success": False, "error": "Step execution timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def _build_step_yaml(self, action: str, target: Any, value: Any) -> str:
        """Build a minimal YAML for a single step.

        Args:
            action: Step action
            target: Target element
            value: Step value

        Returns:
            YAML string
        """
        lines = ["appId: com.example.app", "---"]

        if action == "launchApp":
            lines.append(f"- launchApp:\n    appId: {target}")
        elif action == "tapOn":
            target_str = target if target else "text:Unknown"
            lines.append(f"- tapOn:\n    {target_str}")
        elif action == "inputText":
            lines.append(f"- inputText:\n    text: {value}")
        elif action == "swipe":
            if isinstance(value, dict):
                lines.append(f"- swipe:")
                lines.append(f"    startX: {value.get('startX', 0.5)}")
                lines.append(f"    startY: {value.get('startY', 0.8)}")
                lines.append(f"    endX: {value.get('endX', 0.5)}")
                lines.append(f"    endY: {value.get('endY', 0.2)}")
                lines.append(f"    duration: {value.get('duration', 500)}")
        elif action == "waitForAnimationToEnd":
            lines.append("- waitForAnimationToEnd")
        elif action == "pressKey":
            lines.append(f"- pressKey:\n    key: {value}")
        elif action == "stopApp":
            lines.append(f"- stopApp:\n    appId: {target}")
        else:
            lines.append(f"# Unknown action: {action}")

        return "\n".join(lines)

    @staticmethod
    def get_package_for_app(app_name: str) -> Optional[str]:
        """Get package name for common app name.

        Args:
            app_name: App name (e.g., "wechat", "alipay")

        Returns:
            Package name or None
        """
        return APP_PACKAGE_MAP.get(app_name.lower())
