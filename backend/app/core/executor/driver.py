"""Maestro driver for executing test scripts."""
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MaestroDriver:
    """Driver for executing Maestro test scripts."""

    def __init__(self, binary_path: str = "/usr/local/bin/maestro"):
        """Initialize Maestro driver."""
        self.binary_path = binary_path

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

        # Write YAML to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Build command
            cmd = [
                self.binary_path,
                "test",
                "--device", device_id,
                yaml_path,
                "--format", "json",
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
                logger.error(f"Maestro execution failed: {error}")
                return {
                    "success": False,
                    "returncode": result.returncode,
                    "error": error,
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
