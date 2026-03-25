"""Agent Process Manager - Manages local Open-AutoGLM subprocess.

This module provides process management for the Open-AutoGLM agent running
as a local subprocess. Communication happens via stdin/stdout with JSON
messages for control and progress updates.
"""

import asyncio
import json
import os
import uuid
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


@dataclass
class AgentProcessConfig:
    """Configuration for the agent subprocess."""

    device_serial: str
    instruction: str
    autoglm_path: str = "Open-AutoGLM"
    max_steps: int = 100
    timeout: int = 600
    app_id: Optional[str] = None
    lang: str = "cn"


@dataclass
class TaskStatus:
    """Status of an agent task."""

    task_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: int = 0  # 0-100
    current_step: int = 0
    max_steps: int = 100
    message: str = ""
    generated_script: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentProcess:
    """Represents a running agent subprocess."""

    process_id: str
    config: AgentProcessConfig
    process: Optional[asyncio.subprocess.Process] = None
    task_id: Optional[str] = None
    status: TaskStatus = field(default_factory=lambda: TaskStatus(task_id="", status="pending"))
    _read_task: Optional[asyncio.Task] = None


class AgentProcessManager:
    """Manages local Open-AutoGLM agent subprocesses.

    This class handles:
    - Starting/stopping agent subprocesses
    - Sending instructions to agents
    - Capturing progress and script output
    - Managing multiple concurrent agent sessions

    Communication protocol (JSON over stdin/stdout):
    - To agent: {"type": "start|stop|ping", "task_id": "...", "instruction": "...", "device_serial": "..."}
    - From agent: {"type": "progress|step|script|finish|error", "task_id": "...", "data": {...}}
    """

    def __init__(self):
        """Initialize the process manager."""
        self._processes: dict[str, AgentProcess] = {}
        self._tasks: dict[str, TaskStatus] = {}
        self._lock = asyncio.Lock()
        self._agent_script_dir = Path(__file__).parent / "generated_scripts"
        self._agent_script_dir.mkdir(exist_ok=True)

    async def start_agent(
        self,
        device_serial: str,
        instruction: str,
        task_id: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> str:
        """Start a new agent subprocess.

        Args:
            device_serial: Device serial number
            instruction: Task instruction
            task_id: Optional task ID (generated if not provided)
            config: Optional configuration overrides

        Returns:
            task_id for tracking this task
        """
        async with self._lock:
            trace_id = get_trace_id()
            task_id = task_id or str(uuid.uuid4())
            process_id = str(uuid.uuid4())

            agent_config = AgentProcessConfig(
                device_serial=device_serial,
                instruction=instruction,
                autoglm_path=config.get("autoglm_path", "Open-AutoGLM") if config else "Open-AutoGLM",
                max_steps=config.get("max_steps", 100) if config else 100,
                timeout=config.get("timeout", 600) if config else 600,
                app_id=config.get("app_id"),
                lang=config.get("lang", "cn") if config else "cn",
            )

            logger.info(
                f"[{trace_id}] Starting agent process {process_id} for task {task_id} "
                f"on device {device_serial}"
            )

            # Create process record
            task_status = TaskStatus(
                task_id=task_id,
                status="starting",
                started_at=datetime.utcnow(),
            )
            agent_process = AgentProcess(
                process_id=process_id,
                config=agent_config,
                task_id=task_id,
                status=task_status,
            )
            self._processes[process_id] = agent_process
            self._tasks[task_id] = task_status

            # Start the subprocess
            await self._spawn_process(agent_process)

            return task_id

    async def _spawn_process(self, agent_process: AgentProcess) -> None:
        """Spawn the Open-AutoGLM subprocess.

        Args:
            agent_process: AgentProcess record
        """
        config = agent_process.config
        process_id = agent_process.process_id
        task_id = agent_process.task_id

        try:
            # Determine the Open-AutoGLM main script path - use absolute path
            backend_root = Path(__file__).parent.parent.parent.parent  # /app
            autoglm_main = backend_root / "Open-AutoGLM" / "main.py"
            if not autoglm_main.exists():
                raise FileNotFoundError(f"Open-AutoGLM main.py not found at {autoglm_main}")

            # Build command: python main.py -d <serial> "<instruction>"
            # The Open-AutoGLM will output JSON progress to stdout
            # Environment variables are used for model configuration
            cmd = [
                "python",
                str(autoglm_main),
                "-d", config.device_serial,
                "--max-steps", str(config.max_steps),
                "--lang", config.lang,
                "--quiet",  # Suppress verbose output, we capture it
            ]

            # Pass the task/instruction as positional argument
            cmd.append(config.instruction)

            # Build environment with model API settings
            import os
            env = os.environ.copy()
            # API config is passed via environment variables from host

            if config.app_id:
                cmd.extend(["--app-id", config.app_id])

            logger.info(f"Starting subprocess: {' '.join(cmd)}")

            # Start subprocess with stdin/stdout pipes
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=autoglm_main.parent,
                env=env,
            )

            agent_process.process = process
            agent_process.status.status = "running"

            # Start reading stdout in background
            agent_process._read_task = asyncio.create_task(
                self._read_process_output(agent_process)
            )

            # Also capture stderr
            asyncio.create_task(self._read_stderr(process, process_id))

            logger.info(f"Agent process {process_id} started with PID {process.pid}")

        except Exception as e:
            logger.error(f"Failed to spawn agent process: {e}")
            agent_process.status.status = "failed"
            agent_process.status.error = str(e)
            raise

    async def _read_process_output(self, agent_process: AgentProcess) -> None:
        """Read and parse output from agent subprocess.

        Args:
            agent_process: AgentProcess record
        """
        process = agent_process.process
        process_id = agent_process.process_id
        task_id = agent_process.task_id

        if not process or not process.stdout:
            return

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    # Process ended
                    break

                try:
                    text = line.decode("utf-8").strip()
                    if not text:
                        continue

                    logger.debug(f"Agent {process_id} output: {text[:200]}")

                    # Try to parse as JSON
                    if text.startswith("{"):
                        try:
                            data = json.loads(text)
                            await self._handle_agent_message(process_id, task_id, data)
                        except json.JSONDecodeError:
                            logger.debug(f"Non-JSON output from agent: {text[:100]}")
                    else:
                        # Non-JSON output - log it
                        logger.info(f"Agent {process_id}: {text}")

                except Exception as e:
                    logger.error(f"Error parsing agent output: {e}")

        except asyncio.CancelledError:
            logger.info(f"Read task cancelled for process {process_id}")
        except Exception as e:
            logger.error(f"Error reading process output: {e}")
            agent_process.status.status = "failed"
            agent_process.status.error = str(e)

    async def _read_stderr(
        self, process: asyncio.subprocess.Process, process_id: str
    ) -> None:
        """Read stderr from subprocess for error logging.

        Args:
            process: The subprocess
            process_id: Process ID for logging
        """
        if not process.stderr:
            return

        try:
            stderr_data = await process.stderr.read()
            if stderr_data:
                stderr_text = stderr_data.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    logger.warning(f"Agent {process_id} stderr: {stderr_text[:500]}")
        except Exception as e:
            logger.debug(f"Error reading stderr: {e}")

    async def _handle_agent_message(
        self, process_id: str, task_id: str, data: dict[str, Any]
    ) -> None:
        """Handle message from agent subprocess.

        Args:
            process_id: Agent process ID
            task_id: Task ID
            data: Parsed JSON message
        """
        msg_type = data.get("type", "")
        msg_data = data.get("data", {})

        async with self._lock:
            if task_id in self._tasks:
                task_status = self._tasks[task_id]
                agent_process = self._processes.get(process_id)

                if msg_type == "progress":
                    task_status.current_step = msg_data.get("step", 0)
                    task_status.max_steps = msg_data.get("max_steps", 100)
                    task_status.progress = int(
                        task_status.current_step / task_status.max_steps * 100
                    )
                    task_status.message = msg_data.get("message", "")
                    if agent_process:
                        agent_process.status = task_status

                elif msg_type == "step":
                    # Log step execution
                    action = msg_data.get("action", "")
                    target = msg_data.get("target", "")
                    logger.debug(f"Task {task_id} step: {action} -> {target}")

                elif msg_type == "script":
                    # Agent generated a script fragment
                    script_content = msg_data.get("script", "")
                    if script_content:
                        # Append to accumulated script
                        current = task_status.generated_script or ""
                        task_status.generated_script = current + script_content
                    if agent_process:
                        agent_process.status = task_status

                elif msg_type == "finish":
                    task_status.status = "completed"
                    task_status.progress = 100
                    task_status.message = msg_data.get("message", "Task completed")
                    task_status.generated_script = msg_data.get("script") or task_status.generated_script
                    task_status.completed_at = datetime.utcnow()
                    if agent_process:
                        agent_process.status = task_status
                    logger.info(f"Task {task_id} completed successfully")

                elif msg_type == "error":
                    task_status.status = "failed"
                    task_status.error = msg_data.get("message", "Unknown error")
                    task_status.completed_at = datetime.utcnow()
                    if agent_process:
                        agent_process.status = task_status
                    logger.error(f"Task {task_id} failed: {task_status.error}")

    async def send_instruction(
        self, task_id: str, instruction: str
    ) -> dict[str, Any]:
        """Send additional instruction to running agent.

        Args:
            task_id: Task ID
            instruction: Additional instruction

        Returns:
            Result dictionary
        """
        async with self._lock:
            task_status = self._tasks.get(task_id)
            if not task_status:
                return {"success": False, "error": "Task not found"}

            if task_status.status != "running":
                return {"success": False, "error": f"Task is not running: {task_status.status}"}

            # Find the process for this task
            for proc in self._processes.values():
                if proc.task_id == task_id and proc.process and proc.process.stdin:
                    try:
                        cmd = json.dumps({"type": "instruction", "instruction": instruction})
                        proc.process.stdin.write((cmd + "\n").encode())
                        await proc.process.stdin.drain()
                        return {"success": True}
                    except Exception as e:
                        return {"success": False, "error": str(e)}

            return {"success": False, "error": "Process not found"}

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get current status of a task.

        Args:
            task_id: Task ID

        Returns:
            TaskStatus or None if not found
        """
        async with self._lock:
            return self._tasks.get(task_id)

    async def stop_agent(self, task_id: str) -> dict[str, Any]:
        """Stop a running agent.

        Args:
            task_id: Task ID

        Returns:
            Result dictionary
        """
        async with self._lock:
            task_status = self._tasks.get(task_id)
            if not task_status:
                return {"success": False, "error": "Task not found"}

            # Find and kill the process
            for process_id, proc in list(self._processes.items()):
                if proc.task_id == task_id:
                    if proc.process:
                        try:
                            proc.process.terminate()
                            await asyncio.sleep(0.5)
                            if proc.process.returncode is None:
                                proc.process.kill()
                            if proc._read_task:
                                proc._read_task.cancel()
                        except Exception as e:
                            logger.error(f"Error stopping process {process_id}: {e}")

                    proc.status.status = "cancelled"
                    proc.status.completed_at = datetime.utcnow()
                    task_status.status = "cancelled"
                    task_status.completed_at = datetime.utcnow()

                    del self._processes[process_id]
                    logger.info(f"Agent task {task_id} stopped")
                    return {"success": True}

            return {"success": False, "error": "Process not found"}

    async def get_generated_script(self, task_id: str) -> Optional[str]:
        """Get the generated Maestro script for a task.

        Args:
            task_id: Task ID

        Returns:
            Generated script or None
        """
        async with self._lock:
            task_status = self._tasks.get(task_id)
            if not task_status:
                return None

            if task_status.generated_script:
                return task_status.generated_script

            # If script not in memory, try to load from file
            script_file = self._agent_script_dir / f"{task_id}.yaml"
            if script_file.exists():
                return script_file.read_text()

            return None

    async def save_script(self, task_id: str, script: str) -> dict[str, Any]:
        """Save generated script to file.

        Args:
            task_id: Task ID
            script: Script content

        Returns:
            Result with file path
        """
        try:
            script_file = self._agent_script_dir / f"{task_id}.yaml"
            script_file.write_text(script)
            return {"success": True, "path": str(script_file)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_tasks(self) -> list[TaskStatus]:
        """List all tasks.

        Returns:
            List of TaskStatus objects
        """
        async with self._lock:
            return list(self._tasks.values())

    async def get_process_for_device(self, device_serial: str) -> Optional[AgentProcess]:
        """Get a running process for a device if any.

        Args:
            device_serial: Device serial number

        Returns:
            AgentProcess or None
        """
        async with self._lock:
            for proc in self._processes.values():
                if proc.config.device_serial == device_serial and proc.status.status == "running":
                    return proc
            return None

    async def cleanup_finished_processes(self) -> int:
        """Clean up finished zombie processes.

        Returns:
            Number of processes cleaned up
        """
        cleaned = 0
        async with self._lock:
            for process_id, proc in list(self._processes.items()):
                if proc.process:
                    retcode = proc.process.returncode
                    if retcode is not None and retcode != 0:
                        # Process exited with error
                        logger.warning(f"Process {process_id} exited with code {retcode}")
                        if proc.task_id and proc.task_id in self._tasks:
                            self._tasks[proc.task_id].status = "failed"
                            self._tasks[proc.task_id].error = f"Process exited with code {retcode}"
                        del self._processes[process_id]
                        cleaned += 1

            return cleaned


# Global process manager instance
agent_process_manager = AgentProcessManager()
