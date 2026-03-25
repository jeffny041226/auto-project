"""Agent system for Open-AutoGLM subprocess management.

This module provides:
- ProcessManager: Manages local Open-AutoGLM subprocess
- WebSocketProxy: Bridges frontend WebSocket to subprocess stdin/stdout
- AgentExecutor: AI-driven probe-style executor using Qwen (legacy)

Architecture:
- process_manager + websocket_proxy: Local Open-AutoGLM subprocess approach
- executor + step_executor: Qwen-based AI-driven approach (legacy)
"""

from app.core.agent.executor import AgentExecutor, AgentDecision, ExecutionStep, ExecutionHistory
from app.core.agent.step_executor import StepExecutor, MaestroScriptBuilder
from app.core.agent.prompt import AgentPromptTemplate
from app.core.agent.process_manager import (
    AgentProcessManager,
    AgentProcessConfig,
    TaskStatus,
    AgentProcess,
    agent_process_manager,
)
from app.core.agent.websocket_proxy import router as agent_ws_router

__all__ = [
    # Agent Executor (legacy - uses Qwen directly)
    "AgentExecutor",
    "AgentDecision",
    "ExecutionStep",
    "ExecutionHistory",
    "StepExecutor",
    "MaestroScriptBuilder",
    "AgentPromptTemplate",
    # Process Manager (new - Open-AutoGLM subprocess)
    "AgentProcessManager",
    "AgentProcessConfig",
    "TaskStatus",
    "AgentProcess",
    "agent_process_manager",
    # WebSocket router for subprocess
    "agent_ws_router",
]
