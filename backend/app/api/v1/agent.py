"""Agent API endpoints for Open-AutoGLM integration.

This module provides REST endpoints for:
- Creating agent tasks
- Getting task status
- Getting generated scripts
- Managing agent processes
"""

import uuid
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.agent.process_manager import agent_process_manager, TaskStatus
from app.models.script import Script
from app.schemas.script import ScriptResponse, ScriptCreate
from app.services.script import ScriptService
from app.dependencies import get_current_user
from app.models.user import User
from app.utils.logger import get_trace_id

router = APIRouter(prefix="/agent", tags=["agent"])


# Request/Response Models

class AgentTaskCreate(BaseModel):
    """Request to create a new agent task."""

    instruction: str = Field(..., min_length=1, max_length=1000, description="Task instruction")
    device_serial: str = Field(..., description="Device serial number")
    app_id: Optional[str] = Field(None, description="Target app package ID")
    max_steps: int = Field(100, ge=1, le=500, description="Maximum steps")
    timeout: int = Field(600, ge=60, le=3600, description="Timeout in seconds")
    lang: str = Field("cn", description="Language: cn or en")
    autoglm_path: Optional[str] = Field(None, description="Path to Open-AutoGLM")


class AgentTaskResponse(BaseModel):
    """Response after creating an agent task."""

    task_id: str
    status: str
    message: str = ""


class AgentTaskStatus(BaseModel):
    """Task status information."""

    task_id: str
    status: str
    progress: int
    current_step: int
    max_steps: int
    message: str
    error: Optional[str] = None
    generated_script: Optional[str] = None


class AgentScriptReuseRequest(BaseModel):
    """Request to reuse an existing script with new instruction."""

    script_id: str = Field(..., description="Original script ID")
    new_instruction: str = Field(..., min_length=1, max_length=1000)
    device_serial: Optional[str] = Field(None, description="Device serial override")


# Endpoints

@router.post("/tasks", response_model=AgentTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_task(
    request: AgentTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent task.

    Starts an Open-AutoGLM subprocess to execute the task.
    Use WebSocket to get real-time progress updates.
    """
    trace_id = get_trace_id()

    try:
        # Check if device is already running an agent
        existing = await agent_process_manager.get_process_for_device(request.device_serial)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device {request.device_serial} already has a running agent task: {existing.task_id}",
            )

        # Save task to database first
        from app.models.task import Task
        task_id = str(uuid.uuid4())
        db_task = Task(
            task_id=task_id,
            user_id=current_user.id,
            instruction=request.instruction,
            device_id=request.device_serial,
            status="starting",
            total_steps=request.max_steps,
        )
        db.add(db_task)
        await db.commit()

        # Start the agent
        config = {
            "autoglm_path": request.autoglm_path,
            "max_steps": request.max_steps,
            "timeout": request.timeout,
            "app_id": request.app_id,
            "lang": request.lang,
            "user_id": current_user.id,
        }

        internal_task_id = await agent_process_manager.start_agent(
            device_serial=request.device_serial,
            instruction=request.instruction,
            task_id=task_id,  # Pass the database task_id
            config=config,
        )

        return AgentTaskResponse(
            task_id=task_id,
            status="started",
            message=f"Agent task started on device {request.device_serial}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}",
        )


@router.get("/tasks/{task_id}/status", response_model=AgentTaskStatus)
async def get_agent_task_status(task_id: str):
    """Get the current status of an agent task."""
    status = await agent_process_manager.get_task_status(task_id)

    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return AgentTaskStatus(
        task_id=status.task_id,
        status=status.status,
        progress=status.progress,
        current_step=status.current_step,
        max_steps=status.max_steps,
        message=status.message,
        error=status.error,
        generated_script=status.generated_script,
    )


@router.get("/tasks/{task_id}/script")
async def get_agent_generated_script(task_id: str):
    """Get the generated Maestro script for a completed task."""
    script = await agent_process_manager.get_generated_script(task_id)

    if script is None:
        # Try to get status to see if task exists
        status = await agent_process_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )
        if status.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task {task_id} is not completed yet: {status.status}",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not yet available",
        )

    return {"task_id": task_id, "script": script}


@router.post("/tasks/{task_id}/stop")
async def stop_agent_task(task_id: str):
    """Stop a running agent task."""
    result = await agent_process_manager.stop_agent(task_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to stop task"),
        )

    return result


@router.post("/tasks/{task_id}/send-instruction")
async def send_instruction_to_agent(task_id: str, request: dict):
    """Send additional instruction to a running agent."""
    instruction = request.get("instruction", "")
    result = await agent_process_manager.send_instruction(task_id, instruction)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to send instruction"),
        )

    return result


@router.post("/scripts/{script_id}/reuse", response_model=AgentTaskResponse)
async def reuse_script_with_new_instruction(
    request: AgentScriptReuseRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new task based on an existing script with a new instruction.

    This uses the existing script as a template/base and applies
    the new instruction to it.
    """
    # Get the original script
    db = await get_db().__anext__()
    try:
        script_service = ScriptService(db)
        original_script = await script_service.get_script(request.script_id)

        if not original_script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Script {request.script_id} not found",
            )

        # For now, just start a new agent task with the new instruction
        # In a more advanced implementation, we could analyze the original script
        # and modify it based on the new instruction
        device_serial = request.device_serial or "auto"  # Default to auto-select

        task_id = await agent_process_manager.start_agent(
            device_serial=device_serial,
            instruction=request.new_instruction,
        )

        return AgentTaskResponse(
            task_id=task_id,
            status="started",
            message=f"New agent task started based on script {request.script_id}",
        )

    finally:
        pass  # Session cleanup handled by dependency


@router.get("/tasks")
async def list_agent_tasks():
    """List all agent tasks."""
    tasks = await agent_process_manager.list_tasks()

    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "status": t.status,
                "progress": t.progress,
                "current_step": t.current_step,
                "max_steps": t.max_steps,
                "message": t.message,
                "error": t.error,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


# Cleanup endpoint for maintenance
@router.post("/cleanup")
async def cleanup_finished_processes():
    """Clean up finished zombie processes."""
    cleaned = await agent_process_manager.cleanup_finished_processes()
    return {"cleaned": cleaned}
