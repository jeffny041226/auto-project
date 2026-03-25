"""Agent decision prompt templates for AI-driven execution loop.

This module provides prompt templates following the Open-AutoGLM format:
- Actions use do(action="...", ...) syntax
- Results are wrapped in <answer>...</answer> tags
- Coordinates use relative 0-999 system
"""
import re
from typing import Any


class AgentPromptTemplate:
    """Prompt templates for the agent decision loop."""

    # System prompt for AI decision maker (Open-AutoGLM format)
    SYSTEM_PROMPT = """你是一个手机自动化助手。你的任务是通过分析当前屏幕状态来决定下一步操作，以完成用户的目标。

操作指令格式：
- do(action="Launch", app="com.tencent.mm")
    启动目标app。此操作完成后，你将自动收到结果状态的截图。
- do(action="Tap", element=[x,y])
    点击操作，点击屏幕上的特定点。坐标系统从左上角 (0,0) 到右下角 (999,999)。
- do(action="Type", text="xxx")
    输入操作，在当前聚焦的输入框中输入文本。
- do(action="Swipe", start=[x1,y1], end=[x2,y2])
    滑动手势，从起始坐标拖动到结束坐标。坐标范围 0-999。
- do(action="Back")
    导航返回到上一个屏幕，相当于按下 Android 返回按钮。
- do(action="Home")
    回到系统桌面，相当于按下 Android 主屏幕按钮。
- do(action="Wait", duration="x seconds")
    等待页面加载。
- finish(message="xxx")
    结束任务，表示准确完整完成任务。

App Name to Package ID Mapping:
- 微信/WeChat: com.tencent.mm
- 支付宝/Alipay: com.eg.android.AlipayGphone
- 淘宝/Taobao: com.taobao.taobao
- 京东/JD: com.jingdong.app.mall
- 抖音/Douyin: com.ss.android.ugc.aweme
- 山海/Shanhai: com.shanhai.app

必须遵循的规则：
1. 在执行任何操作前，先检查当前app是否是目标app，如果不是，先执行 Launch。
2. 如果进入到了无关页面，先执行 Back。如果执行Back后页面没有变化，请点击页面左上角的返回键进行返回，或者右上角的X号关闭。
3. 如果页面未加载出内容，最多连续 Wait 三次，否则执行 Back重新进入。
4. 如果页面显示网络问题，需要重新加载，请点击重新加载。
5. 如果当前页面找不到目标联系人、商品、店铺等信息，可以尝试 Swipe 滑动查找。
6. 在执行下一步操作前请一定要检查上一步的操作是否生效，如果点击没生效，请调整一下点击位置重试。
7. 在结束任务前请一定要仔细检查任务是否完整准确的完成。

输出格式：
在 <answer> 标签中输出操作指令，例如：
<answer>do(action="Tap", element=[500,300])</answer>
或
<answer>finish(message="任务完成")</answer>"""

    # User prompt template for AI decision
    USER_PROMPT_TEMPLATE = """**用户目标**：
{goal}

**当前屏幕信息**：
当前 App: {current_app}
页面类型: {page_type}
页面描述: {page_description}

**检测到的 UI 元素**：
{elements_list}

**最近操作历史**（最近 3 步）：
{history}

**你的任务**：
根据当前屏幕状态和用户目标，决定下一步操作。

坐标系统说明：
- 使用相对坐标，范围 0-999
- 左上角是 (0,0)，右下角是 (999,999)
- 需要将屏幕宽高映射到 0-999 范围

输出格式：
在 <answer> 标签中输出操作指令，例如：
<answer>do(action="Tap", element=[x,y])</answer>
<answer>do(action="Launch", app="com.example.app")</answer>
<answer>do(action="Type", text="要输入的文字")</answer>
<answer>finish(message="任务已完成")</answer>"""""

    @classmethod
    def format_elements(cls, elements: list[dict[str, Any]], screen_width: int = 1080, screen_height: int = 1920) -> str:
        """Format UI elements for prompt with relative coordinates (0-999).

        Args:
            elements: List of UI element dicts
            screen_width: Screen width in pixels (default 1080)
            screen_height: Screen height in pixels (default 1920)
        """
        if not elements:
            return "No UI elements detected on screen."

        lines = []
        for i, elem in enumerate(elements[:15], 1):  # Limit to 15 elements
            elem_type = elem.get("type", "unknown")
            text = elem.get("text", "")
            bounds = elem.get("bounds", {})
            resource_id = elem.get("resource_id", "")

            # Calculate center from bounds and convert to relative 0-999
            rel_x = rel_y = None
            if bounds:
                x = bounds.get("x", 0)
                y = bounds.get("y", 0)
                w = bounds.get("width", 0)
                h = bounds.get("height", 0)
                if w and h:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    # Convert to relative 0-999 coordinates
                    rel_x = int(center_x / screen_width * 999)
                    rel_y = int(center_y / screen_height * 999)

            desc = f"{i}. [{elem_type}]"
            if text:
                desc += f' text="{text}"'
            if resource_id:
                desc += f' id="{resource_id}"'
            if bounds:
                desc += f' bounds={bounds}'
            if rel_x is not None and rel_y is not None:
                desc += f' → element=[{rel_x},{rel_y}]'
            lines.append(desc)

        return "\n".join(lines)

    @classmethod
    def format_history(cls, history: list[dict[str, Any]]) -> str:
        """Format execution history for prompt."""
        if not history:
            return "No previous steps taken."

        recent = history[-3:]  # Last 3 steps
        lines = []
        start_idx = max(0, len(history) - 3)
        for i, step in enumerate(recent, start_idx + 1):
            action = step.get("action", "unknown")
            target = step.get("target", "")
            success = step.get("success", False)
            status = "✓" if success else "✗"
            lines.append(f"{i}. {status} {action}: {target}")

        return "\n".join(lines)

    @classmethod
    def parse_answer(cls, content: str) -> dict[str, Any]:
        """Parse action from <answer> tag in AI response.

        Args:
            content: Raw AI response content

        Returns:
            Parsed action dict with '_metadata' field ('do' or 'finish')
        """
        # Match <answer>...</answer> tags
        match = re.search(r'<answer>(.*?)</answer>', content, re.DOTALL)
        if not match:
            # Try to find do(...) or finish(...) directly
            action_str = content.strip()
        else:
            action_str = match.group(1).strip()

        # Parse the action
        if action_str.startswith("finish"):
            # finish(message="...")
            msg_match = re.search(r'message\s*=\s*["\']([^"\']*)["\']', action_str)
            message = msg_match.group(1) if msg_match else ""
            return {"_metadata": "finish", "message": message}

        elif action_str.startswith("do"):
            # do(action="...", ...)
            # Extract action name
            action_match = re.search(r'action\s*=\s*["\']([^"\']*)["\']', action_str)
            if not action_match:
                return {"_metadata": "error", "raw": action_str}

            action_name = action_match.group(1)
            result = {"_metadata": "do", "action": action_name}

            # Extract various parameters based on action type
            if action_name in ("Tap", "Long Press", "Double Tap"):
                # element=[x,y]
                elem_match = re.search(r'element\s*=\s*\[(\d+)\s*,\s*(\d+)\]', action_str)
                if elem_match:
                    result["element"] = [int(elem_match.group(1)), int(elem_match.group(2))]
            elif action_name == "Type":
                # text="..."
                text_match = re.search(r'text\s*=\s*["\']([^"\']*)["\']', action_str)
                if text_match:
                    result["text"] = text_match.group(1)
            elif action_name == "Type_Name":
                # text="..."
                text_match = re.search(r'text\s*=\s*["\']([^"\']*)["\']', action_str)
                if text_match:
                    result["text"] = text_match.group(1)
            elif action_name == "Launch":
                # app="..."
                app_match = re.search(r'app\s*=\s*["\']([^"\']*)["\']', action_str)
                if app_match:
                    result["app"] = app_match.group(1)
            elif action_name == "Swipe":
                # start=[x,y], end=[x,y]
                start_match = re.search(r'start\s*=\s*\[(\d+)\s*,\s*(\d+)\]', action_str)
                end_match = re.search(r'end\s*=\s*\[(\d+)\s*,\s*(\d+)\]', action_str)
                if start_match:
                    result["start"] = [int(start_match.group(1)), int(start_match.group(2))]
                if end_match:
                    result["end"] = [int(end_match.group(1)), int(end_match.group(2))]
            elif action_name == "Wait":
                # duration="x seconds"
                dur_match = re.search(r'duration\s*=\s*["\'](\d+)\s*seconds?["\']', action_str)
                if dur_match:
                    result["duration"] = f"{dur_match.group(1)} seconds"

            return result

        return {"_metadata": "error", "raw": content}

    @classmethod
    def build_decision_prompt(
        cls,
        goal: str,
        current_app: str,
        page_type: str,
        page_description: str,
        elements: list[dict[str, Any]],
        history: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Build full prompt for AI decision.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.SYSTEM_PROMPT
        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            goal=goal,
            current_app=current_app or "unknown",
            page_type=page_type,
            page_description=page_description,
            elements_list=cls.format_elements(elements),
            history=cls.format_history(history),
        )
        return system_prompt, user_prompt

    # Prompt for generating final Maestro YAML
    SCRIPT_GENERATION_PROMPT = """Based on the following execution history, generate a Maestro YAML script that automates this task.

Goal: {goal}

Execution Steps:
{steps}

Generate a clean Maestro YAML script with:
- Proper appId at the top
- Each step as a proper Maestro command
- No comments or extra fields

Output ONLY the YAML, no explanations."""

    @classmethod
    def build_script_generation_prompt(
        cls,
        goal: str,
        steps: list[dict[str, Any]],
    ) -> str:
        """Build prompt for script generation from history."""
        step_lines = []
        for i, step in enumerate(steps, 1):
            action = step.get("action", "unknown")
            target = step.get("target", "") or ""
            value = step.get("value", "") or ""
            step_lines.append(f"{i}. {action}: target={target}, value={value}")

        return cls.SCRIPT_GENERATION_PROMPT.format(
            goal=goal,
            steps="\n".join(step_lines),
        )