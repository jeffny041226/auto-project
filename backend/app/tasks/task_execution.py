"""Task execution async tasks."""
import asyncio
from datetime import datetime
from typing import Any

from app.tasks.celery_app import celery_app
from app.core.executor.scheduler import TaskScheduler
from app.core.script.manager import ScriptManager
from app.core.script.matcher import ScriptMatcher
from app.core.intention.parser import InstructionParser
from app.core.intention.intent_classifier import IntentClassifier
from app.core.script.generator import ScriptGenerator
from app.core.script.template import MaestroTemplate
from app.core.agent.executor import AgentExecutor
from app.db.database import get_db_context
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.task_execution.process_task")
def process_task(
    self,
    task_id: str,
    user_id: int,
    instruction: str,
    device_id: str = None,
) -> dict[str, Any]:
    """Process a task by sending to connected agent via WebSocket.

    Args:
        task_id: Task ID
        user_id: User ID
        instruction: Task instruction
        device_id: Optional device ID

    Returns:
        Processing result
    """
    logger.info(f"Processing task: {task_id}")

    async def _process():
        from app.core.device.agent import device_agent_manager
        from app.services.task import TaskService

        # Check if there's a connected device agent
        if not device_id:
            return {"success": False, "error": "No device_id provided"}

        device_conn = await device_agent_manager.get_connection(device_id)
        if not device_conn or not device_conn.is_connected:
            logger.warning(f"No connected agent for device {device_id}")
            return {"success": False, "error": f"No connected agent for device {device_id}"}

        # Update task status to running
        async with get_db_context() as db:
            task_service = TaskService(db)
            await task_service.update_task_by_id(task_id, {"status": "running"})

        # Send task to agent via WebSocket
        logger.info(f"Sending task {task_id} to agent {device_id} via WebSocket")
        await device_conn.send_command({
            "action": "run_task",
            "params": {
                "task": instruction,
                "task_id": task_id,
                "max_steps": 100,
                "lang": "cn",
                "app_id": None,
            }
        })

        return {
            "success": True,
            "task_id": task_id,
            "message": "Task sent to agent",
        }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_process())
    logger.info(f"Task processing completed: {task_id}, success: {result.get('success')}")
    return result


@celery_app.task(bind=True, name="app.tasks.task_execution.execute_task")
def execute_task(
    self,
    task_id: str,
    script_id: str,
    device_id: str = None,
) -> dict[str, Any]:
    """Execute a test task asynchronously.

    Args:
        task_id: Task ID
        script_id: Script ID to execute
        device_id: Optional device ID

    Returns:
        Execution result
    """
    logger.info(f"Starting task execution: {task_id}")

    async def _execute():
        async with get_db_context() as db:
            # Get script
            manager = ScriptManager(db)
            script = await manager.get(script_id)

            if not script:
                return {"success": False, "error": "Script not found"}

            # Execute via scheduler
            scheduler = TaskScheduler(db)

            result = await scheduler.execute_task(
                task_id=task_id,
                script_content=script.maestro_yaml,
                device_id=device_id,
            )

            return {
                "success": result.get("success", False),
                "task_id": task_id,
                "error": result.get("error"),
            }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_execute())
    logger.info(f"Task execution completed: {task_id}, success: {result.get('success')}")
    return result


@celery_app.task(bind=True, name="app.tasks.task_execution.execute_step")
def execute_step(
    self,
    task_id: str,
    step_index: int,
    step_action: str,
    step_target: str,
    step_value: Any,
    device_id: str,
) -> dict[str, Any]:
    """Execute a single task step.

    Args:
        task_id: Task ID
        step_index: Step index
        step_action: Action to perform
        step_target: Target element
        step_value: Action value
        device_id: Device ID

    Returns:
        Step execution result
    """
    logger.info(f"Executing step {step_index} for task {task_id}")

    step = {
        "action": step_action,
        "target": step_target,
        "value": step_value,
    }

    async def _execute():
        async with get_db_context() as db:
            scheduler = TaskScheduler(db)
            result = await scheduler.execute_step(
                task_id=task_id,
                step=step,
                device_id=device_id,
                step_index=step_index,
            )
            return result

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_execute())
    return result


@celery_app.task(bind=True, name="app.tasks.task_execution.update_progress")
def update_progress(
    self,
    task_id: str,
    completed_steps: int,
    total_steps: int = None,
) -> dict[str, Any]:
    """Update task progress.

    Args:
        task_id: Task ID
        completed_steps: Number of completed steps
        total_steps: Total number of steps (optional)

    Returns:
        Update result
    """
    async def _update():
        async with get_db_context() as db:
            from app.services.task import TaskService
            service = TaskService(db)
            await service.update_task_progress(
                task_id=task_id,
                completed_steps=completed_steps,
                total_steps=total_steps,
            )
            return {"success": True}

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_update())


@celery_app.task(bind=True, name="app.tasks.task_execution.process_task_agent")
def process_task_agent(
    self,
    task_id: str,
    user_id: int,
    instruction: str,
    device_id: str = None,
) -> dict[str, Any]:
    """Process a task using AI-driven agent executor (probe-style execution).

    This task uses the AgentExecutor which:
    1. Captures screenshot
    2. Analyzes via AutoGLM vision
    3. Decides next action via LLM
    4. Executes the action
    5. Loops until task completion
    6. Generates final Maestro YAML script

    Args:
        task_id: Task ID
        user_id: User ID
        instruction: Task instruction (e.g., "打开微信")
        device_id: Optional device ID

    Returns:
        Processing result with generated script
    """
    logger.info(f"Processing task with agent executor: {task_id}")

    async def _process():
        # Connect to Redis for device pool
        from app.db.redis import redis_client
        await redis_client.connect()

        # Load LLM configs
        llm_config = settings.llm_config
        qwen_config = llm_config.get("providers", {}).get("qwen", {})
        autoglm_config = llm_config.get("providers", {}).get("autoglm", {})

        # Use provided device_id or get from pool
        device_serial = device_id
        acquired_device = False

        if not device_serial:
            async with get_db_context() as db:
                from app.core.executor.device_pool import DevicePool
                pool = DevicePool(db)
                device = await pool.allocate_device(task_id)
                if not device:
                    return {"success": False, "error": "No device available"}
                device_serial = device.device_id
                acquired_device = True

        async with get_db_context() as db:
            from app.services.task import TaskService

            # Update task status to running
            task_service = TaskService(db)
            await task_service.update_task_by_id(task_id, {"status": "running"})

            try:
                # Create and run agent executor
                executor = AgentExecutor(
                    device_serial=device_serial,
                    llm_config=qwen_config,
                    autoglm_config=autoglm_config,
                )

                result = await executor.execute(
                    instruction=instruction,
                    task_id=task_id,
                )

                await executor.close()

                # Save generated script if successful
                if result.get("success") and result.get("generated_script"):
                    manager = ScriptManager(db)

                    # Parse instruction for intent
                    parser = InstructionParser()
                    parsed = parser.parse(instruction)
                    intent = parsed.app_name or "agent_generated"

                    script = await manager.save_generated(
                        user_id=user_id,
                        intent=intent,
                        structured_instruction={
                            "type": "agent_generated",
                            "instruction": instruction,
                            "iterations": result.get("iterations", 0),
                        },
                        pseudo_code=str(result.get("steps", [])),
                        maestro_yaml=result.get("generated_script", ""),
                    )

                    result["script_id"] = script.script_id

                    # Update task with script_id
                    await task_service.update_task_by_id(
                        task_id,
                        {"script_id": script.script_id}
                    )

                # Release device if we acquired one
                if acquired_device:
                    pool = DevicePool(db)
                    await pool.release_device(device_serial)

                return result

            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                # Release device on error
                if acquired_device:
                    pool = DevicePool(db)
                    await pool.release_device(device_serial)

                return {"success": False, "error": str(e)}

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_process())
    logger.info(f"Agent task processing completed: {task_id}, success: {result.get('success')}")
    return result
