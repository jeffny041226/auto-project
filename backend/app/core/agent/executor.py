"""Agent executor - AI-driven probe-style task execution.

This module implements the probe-style execution architecture where:
1. AI analyzes the current screen via vision
2. AI decides the next action (Open-AutoGLM style do(action=...))
3. The action is executed with relative-to-absolute coordinate conversion
4. Feedback is collected and loop continues until task completion
5. Maestro script is generated incrementally during exploration
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.agent.prompt import AgentPromptTemplate
from app.core.agent.step_executor import StepExecutor, MaestroScriptBuilder
from app.core.device.adb import ADBConnector
from app.core.intention.parser import InstructionParser
from app.llm.factory import LLMFactory
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


@dataclass
class ExecutionStep:
    """A single execution step with result."""
    action: str
    target: Optional[str] = None
    value: Any = None
    success: bool = False
    error: Optional[str] = None
    screenshot_before: Optional[bytes] = None
    screenshot_after: Optional[bytes] = None
    x: Optional[int] = None  # Tap X coordinate (absolute)
    y: Optional[int] = None  # Tap Y coordinate (absolute)
    # Open-AutoGLM style fields
    element: Optional[list[int]] = None  # Relative coords [x, y] from AI
    app: Optional[str] = None  # App package for Launch action
    text: Optional[str] = None  # Text for Type action
    start: Optional[list[int]] = None  # Swipe start relative coords
    end: Optional[list[int]] = None  # Swipe end relative coords


@dataclass
class ExecutionHistory:
    """History of execution steps."""
    steps: list[ExecutionStep] = field(default_factory=list)

    def add(self, step: ExecutionStep):
        """Add a step to history."""
        self.steps.append(step)

    def last(self) -> Optional[ExecutionStep]:
        """Get last step."""
        return self.steps[-1] if self.steps else None

    def to_list(self) -> list[dict[str, Any]]:
        """Convert to list of dicts for AI prompt."""
        return [
            {
                "action": s.action,
                "target": s.target,
                "value": s.value,
                "success": s.success,
                "x": s.x,
                "y": s.y,
                "element": s.element,
                "app": s.app,
                "text": s.text,
            }
            for s in self.steps
        ]


@dataclass
class AgentDecision:
    """AI decision for next action (Open-AutoGLM format)."""
    action: str
    target: Optional[str] = None
    value: Any = None
    reasoning: Optional[str] = None
    # Relative coordinates from AI (0-999 system)
    element: Optional[list[int]] = None
    app: Optional[str] = None
    text: Optional[str] = None
    start: Optional[list[int]] = None
    end: Optional[list[int]] = None
    duration: Optional[str] = None
    # For finish action
    finish_message: Optional[str] = None


class AgentExecutor:
    """AI-driven probe-style task executor.

    This executor analyzes the current screen state using vision AI,
    decides the next action using LLM (Open-AutoGLM format), and executes it,
    repeating until the task is complete. Maestro scripts are generated
    incrementally during exploration.
    """

    # Maximum iterations before giving up
    MAX_ITERATIONS = 20

    # Wait time between actions for animations
    WAIT_AFTER_ACTION = 1.5

    # Wait time after tap for UI to respond
    WAIT_AFTER_TAP = 2.0

    def __init__(
        self,
        device_serial: str,
        llm_config: dict[str, Any],
        autoglm_config: dict[str, Any],
    ):
        """Initialize agent executor.

        Args:
            device_serial: Device serial number
            llm_config: LLM provider configuration (for decision making)
            autoglm_config: AutoGLM configuration (for vision analysis)
        """
        self.device_serial = device_serial
        self.step_executor = StepExecutor(device_serial)
        self.adb = ADBConnector()
        self.adb.set_device(device_serial)

        # Initialize AI provider (Qwen with vision for both analysis and decision)
        self.llm = LLMFactory.create("qwen", llm_config)
        # Keep autoglm config for backwards compatibility but don't use it
        self._autoglm_config = autoglm_config

        self.history = ExecutionHistory()
        self.goal: str = ""
        self.task_id: Optional[str] = None

        # Screen resolution for coordinate conversion
        self._screen_width: int = 1080
        self._screen_height: int = 1920

    async def _relative_to_absolute(self, element: list[int]) -> tuple[int, int]:
        """Convert relative coordinates (0-999) to absolute pixels.

        Args:
            element: Relative coordinates [x, y] in 0-999 range

        Returns:
            Tuple of (absolute_x, absolute_y) in pixels
        """
        if not element or len(element) != 2:
            return 0, 0

        x = int(element[0] / 999 * self._screen_width)
        y = int(element[1] / 999 * self._screen_height)
        return x, y

    async def _update_screen_resolution(self):
        """Update screen resolution from device."""
        try:
            self._screen_width, self._screen_height = await self.adb.get_screen_resolution()
            logger.debug(f"Screen resolution: {self._screen_width}x{self._screen_height}")
        except Exception as e:
            logger.warning(f"Could not get screen resolution: {e}")

    async def execute(self, instruction: str, task_id: Optional[str] = None) -> dict[str, Any]:
        """Execute a task using AI-driven probe loop.

        Args:
            instruction: User instruction (e.g., "打开微信")
            task_id: Optional task ID for tracking

        Returns:
            Execution result with generated script
        """
        trace_id = get_trace_id()
        self.task_id = task_id
        self.history = ExecutionHistory()

        logger.info(f"[{trace_id}] Starting agent execution: {instruction}")

        # Parse instruction
        parser = InstructionParser()
        parsed = parser.parse(instruction)
        self.goal = parsed.cleaned

        # If app name detected, prepend to goal
        if parsed.app_name:
            self.goal = f"打开 {parsed.app_name} 并执行: {parsed.cleaned}"

        # Update screen resolution for coordinate conversion
        await self._update_screen_resolution()

        # Initialize Maestro script builder
        script_builder = MaestroScriptBuilder()
        script_builder.set_flow_name(f"Agent: {self.goal[:50]}")

        # Main execution loop
        iteration = 0
        finish_message = None
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.info(f"[{trace_id}] Iteration {iteration}/{self.MAX_ITERATIONS}")

            try:
                # 1. Capture screenshot
                screenshot = await self.step_executor.screenshot()
                if not screenshot:
                    logger.warning(f"[{trace_id}] Failed to capture screenshot")
                    await asyncio.sleep(1)
                    continue

                # 2. Get current app info
                current_app = await self._get_current_app()

                # 3. Vision analysis + AI decision (combined using Qwen with vision)
                decision = await self._vision_analyze(
                    screenshot=screenshot,
                    goal=self.goal,
                    current_app=current_app,
                )

                # Handle finish action
                if decision.action == "finish":
                    logger.info(f"[{trace_id}] AI indicated task completion: {decision.finish_message}")
                    finish_message = decision.finish_message
                    break

                # 5. Execute the decided action (Open-AutoGLM style)
                step = ExecutionStep(
                    action=decision.action,
                    screenshot_before=screenshot,
                )

                result = {"success": False, "error": "Unknown action"}

                # Execute based on action type
                if decision.action == "Tap" and decision.element:
                    # Convert relative coords to absolute
                    abs_x, abs_y = await self._relative_to_absolute(decision.element)
                    step.element = decision.element
                    step.x = abs_x
                    step.y = abs_y
                    result = await self.step_executor.tap_at(abs_x, abs_y)
                    script_builder.add_tap(abs_x, abs_y)

                elif decision.action == "Launch" and decision.app:
                    step.app = decision.app
                    result = await self.step_executor.execute_step({
                        "action": "launchApp",
                        "target": decision.app,
                    })
                    script_builder.add_launch(decision.app)

                elif decision.action in ("Type", "Type_Name") and decision.text:
                    step.text = decision.text
                    result = await self.step_executor.execute_step({
                        "action": "inputText",
                        "value": decision.text,
                    })
                    script_builder.add_input_text(decision.text)

                elif decision.action == "Swipe" and decision.start and decision.end:
                    # Convert relative coords to absolute
                    start_x, start_y = await self._relative_to_absolute(decision.start)
                    end_x, end_y = await self._relative_to_absolute(decision.end)
                    step.start = decision.start
                    step.end = decision.end
                    result = await self.step_executor.execute_step({
                        "action": "swipe",
                        "value": {
                            "startX": start_x / self._screen_width,
                            "startY": start_y / self._screen_height,
                            "endX": end_x / self._screen_width,
                            "endY": end_y / self._screen_height,
                            "duration": 500,
                        },
                    })
                    script_builder.add_swipe(start_x, start_y, end_x, end_y)

                elif decision.action == "Back":
                    result = await self.step_executor.execute_step({
                        "action": "pressKey",
                        "target": "BACK",
                    })
                    script_builder.add_back()

                elif decision.action == "Home":
                    result = await self.step_executor.execute_step({
                        "action": "pressKey",
                        "target": "HOME",
                    })
                    script_builder.add_home()

                elif decision.action == "Wait":
                    duration_str = decision.duration or "2 seconds"
                    duration = int(duration_str.replace("seconds", "").strip())
                    await asyncio.sleep(duration)
                    result = {"success": True, "action": "Wait"}
                    script_builder.add_wait(duration)

                else:
                    # Unknown or unsupported action - wait and continue
                    logger.warning(f"[{trace_id}] Unsupported action: {decision.action}")
                    await asyncio.sleep(1)
                    result = {"success": False, "error": f"Unsupported action: {decision.action}"}

                step.success = result.get("success", False)
                step.error = result.get("error")

                # 6. Wait for UI to settle
                wait_time = self.WAIT_AFTER_TAP if decision.action == "Tap" else self.WAIT_AFTER_ACTION
                await asyncio.sleep(wait_time)

                # 7. Capture after screenshot (for next iteration)
                screenshot_after = await self.step_executor.screenshot()
                step.screenshot_after = screenshot_after

                # 8. Note: Screenshot comparison removed since using Qwen-only approach
                # The AI decision inherently validates the action was appropriate

                self.history.add(step)

                # 9. Check if goal achieved - done via AI decision (finish action)
                # The loop will exit when AI returns finish(message="...")

            except Exception as e:
                logger.error(f"[{trace_id}] Iteration error: {e}")
                self.history.add(ExecutionStep(
                    action="error",
                    success=False,
                    error=str(e),
                ))
                await asyncio.sleep(1)

        # Generate final script from builder (incremental generation during exploration)
        script = script_builder.render(app_id=self._extract_app_id())

        logger.info(f"[{trace_id}] Execution completed after {iteration} iterations")

        return {
            "success": True,
            "task_id": task_id,
            "iterations": iteration,
            "steps": self.history.to_list(),
            "generated_script": script,
            "goal": self.goal,
        }

    async def _vision_analyze(
        self,
        screenshot: bytes,
        goal: str,
        current_app: str,
        page_description: str = "",
    ) -> AgentDecision:
        """Use Qwen with vision to analyze screen and decide next action.

        Args:
            screenshot: Screenshot bytes
            goal: User's goal
            current_app: Current foreground app
            page_description: Optional description of current page

        Returns:
            AgentDecision with action to take
        """
        import base64

        # Build screen info for context
        screen_info = f"""当前 App: {current_app or "unknown"}
用户目标: {goal}
页面描述: {page_description}"""

        # Build messages with screenshot as base64 image
        # Following Open-AutoGLM's MessageBuilder approach
        screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

        system_prompt = AgentPromptTemplate.SYSTEM_PROMPT
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            },
            {
                "type": "text",
                "text": f"**用户目标**：\n{goal}\n\n**当前屏幕信息**：\n{screen_info}\n\n**你的任务**：\n根据屏幕状态和用户目标，决定下一步操作。\n\n**输出格式**：\n在 <answer> 标签中输出操作指令，例如：\n<answer>do(action=\"Tap\", element=[x,y])</answer>\n<answer>finish(message=\"任务完成\")</answer>",
            },
        ]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await self.llm.chat(messages)
            content = response.content.strip()

            logger.debug(f"Vision AI response: {content[:500]}")

            # Parse Open-AutoGLM style <answer> format
            parsed = AgentPromptTemplate.parse_answer(content)

            if parsed.get("_metadata") == "finish":
                return AgentDecision(
                    action="finish",
                    finish_message=parsed.get("message", "任务完成"),
                )

            if parsed.get("_metadata") == "error":
                logger.warning(f"Failed to parse action: {parsed.get('raw', content)[:200]}")
                return AgentDecision(action="Wait", duration="2 seconds")

            # Extract action details based on action type
            action_name = parsed.get("action", "Wait")
            decision = AgentDecision(action=action_name)

            if action_name in ("Tap", "Long Press", "Double Tap"):
                decision.element = parsed.get("element")
            elif action_name == "Launch":
                decision.app = parsed.get("app")
            elif action_name in ("Type", "Type_Name"):
                decision.text = parsed.get("text")
            elif action_name == "Swipe":
                decision.start = parsed.get("start")
                decision.end = parsed.get("end")
            elif action_name == "Wait":
                decision.duration = parsed.get("duration", "2 seconds")

            return decision

        except Exception as e:
            logger.error(f"Vision AI decision error: {e}")
            return AgentDecision(action="Wait", duration="2 seconds")

    async def _ai_decide(
        self,
        goal: str,
        current_app: str,
        vision_result: Any,
    ) -> AgentDecision:
        """Get AI decision for next action.

        Args:
            goal: User's goal
            current_app: Current foreground app
            vision_result: Vision analysis result

        Returns:
            AgentDecision with action to take
        """
        # Extract elements from vision result
        elements = []
        if vision_result and hasattr(vision_result, "elements"):
            for elem in vision_result.elements:
                elements.append({
                    "type": elem.element_type,
                    "text": elem.text,
                    "bounds": elem.bounds,
                    "resource_id": elem.resource_id,
                })

        # Build prompt
        system_prompt, user_prompt = AgentPromptTemplate.build_decision_prompt(
            goal=goal,
            current_app=current_app,
            page_type=vision_result.page_type if vision_result else "unknown",
            page_description=vision_result.overall_description if vision_result else "",
            elements=elements,
            history=self.history.to_list(),
        )

        # Call LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(messages)
            content = response.content.strip()

            logger.debug(f"AI response: {content[:500]}")

            # Parse Open-AutoGLM style <answer> format
            parsed = AgentPromptTemplate.parse_answer(content)

            if parsed.get("_metadata") == "finish":
                return AgentDecision(
                    action="finish",
                    finish_message=parsed.get("message", "任务完成"),
                )

            if parsed.get("_metadata") == "error":
                logger.warning(f"Failed to parse action: {parsed.get('raw', content)[:200]}")
                return AgentDecision(action="Wait", duration="2 seconds")

            # Extract action details based on action type
            action_name = parsed.get("action", "Wait")
            decision = AgentDecision(action=action_name)

            if action_name in ("Tap", "Long Press", "Double Tap"):
                decision.element = parsed.get("element")
            elif action_name == "Launch":
                decision.app = parsed.get("app")
            elif action_name in ("Type", "Type_Name"):
                decision.text = parsed.get("text")
            elif action_name == "Swipe":
                decision.start = parsed.get("start")
                decision.end = parsed.get("end")
            elif action_name == "Wait":
                decision.duration = parsed.get("duration", "2 seconds")

            return decision

        except Exception as e:
            logger.error(f"AI decision error: {e}")
            return AgentDecision(action="Wait", duration="2 seconds")

    async def _get_current_app(self) -> Optional[str]:
        """Get currently visible app package name."""
        try:
            package, _ = await self.adb.get_top_activity()
            return package
        except Exception as e:
            logger.debug(f"Could not get current app: {e}")
            return None

    async def _check_goal_achieved(self, vision_result: Any) -> bool:
        """Check if goal appears to be achieved based on vision analysis.

        This is a simple heuristic check. A more sophisticated approach
        would compare against expected final state.
        """
        if not vision_result:
            return False

        # Check if we're on the expected app
        page_type = getattr(vision_result, "page_type", "")
        description = getattr(vision_result, "overall_description", "")

        # Simple heuristics based on goal keywords
        goal_lower = self.goal.lower()

        if "微信" in goal_lower or "wechat" in goal_lower:
            if "wechat" in page_type.lower() or "weixin" in page_type.lower():
                return True

        if "支付宝" in goal_lower or "alipay" in goal_lower:
            if "alipay" in page_type.lower():
                return True

        # Check for common "success" indicators
        success_keywords = ["success", "完成", "成功", "done", "主页", "home"]
        if any(kw in description.lower() for kw in success_keywords):
            return True

        return False

    def _generate_script(self) -> str:
        """Generate Maestro YAML script from execution history.

        Returns:
            Maestro YAML script as string
        """
        from app.core.script.template import MaestroTemplate

        steps = []
        for step in self.history.steps:
            if step.action == "done" or step.action == "error":
                continue

            step_dict = {
                "action": step.action,
                "target": step.target,
                "value": step.value,
            }
            # Include coordinates if available (for tapOn actions)
            if step.x is not None and step.y is not None:
                step_dict["x"] = step.x
                step_dict["y"] = step.y
            steps.append(step_dict)

        template = MaestroTemplate()
        yaml_content = template.render(
            steps=steps,
            app_id=self._extract_app_id(),
            flow_name=f"Agent: {self.goal[:50]}",
        )

        return yaml_content

    def _extract_app_id(self) -> str:
        """Extract app package ID from execution history.

        Returns:
            App package ID or default
        """
        for step in self.history.steps:
            if step.action == "launchApp" and step.target:
                return step.target

        # Try to infer from goal
        goal_lower = self.goal.lower()
        if "微信" in goal_lower or "wechat" in goal_lower:
            return "com.tencent.mm"
        elif "支付宝" in goal_lower or "alipay" in goal_lower:
            return "com.eg.android.AlipayGphone"
        elif "抖音" in goal_lower or "douyin" in goal_lower:
            return "com.ss.android.ugc.aweme"

        return "com.example.app"

    async def close(self):
        """Cleanup resources."""
        # Qwen client cleanup if needed
        pass