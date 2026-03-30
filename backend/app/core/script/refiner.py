"""Script Refiner - Uses LLM to refine and filter agent-generated steps.

This module removes unnecessary steps from agent execution traces:
- Back navigation operations that don't contribute to the goal
- Duplicate actions
- Failed action attempts
- Non-contributing scroll/wait operations
"""

import json
from typing import Any

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm.factory import LLMFactory
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


class ScriptRefiner:
    """Refines agent-generated steps using LLM.

    Takes raw steps from agent execution and uses LLM to:
    1. Remove unnecessary back operations
    2. Remove duplicate actions
    3. Remove failed action attempts
    4. Remove non-contributing scroll/wait operations
    5. Keep key navigation steps, input operations, and successful interactions
    """

    DEFAULT_PROMPT = """You are a mobile automation script analyst. Analyze the agent's execution steps and keep only the essential ones for script playback.

## Your Task
Given the list of steps executed by an AI agent on a mobile device, identify and remove:
1. **Back operations** that don't contribute to the goal (e.g., navigating back after completion)
2. **Duplicate actions** - same element tapped multiple times unnecessarily
3. **Failed attempts** - actions that didn't succeed
4. **Non-contributing scroll/wait** - scrolling or waiting that doesn't help achieve the goal

## Keep:
1. **Key navigation steps** - opening apps, navigating to specific screens
2. **Input operations** - typing text, selecting options
3. **Successful interactions** - taps that actually contributed to the goal
4. **App launches** - launchApp commands
5. **Final state actions** - actions that reached the goal

## Input Format
Steps from agent execution:
```json
[
  {
    "action": "Tap",
    "element_info": {
      "text": "微信",
      "resource_id": "com.tencent.mm:id/icon",
      "bounds": [100, 200, 200, 300],
      "center_coords": [150, 250]
    },
    "ai_thought_process": "点击微信图标进入微信",
    "success": true
  },
  ...
]
```

## Output Format
Respond with ONLY a JSON array of refined steps:
```json
[
  {
    "action": "Tap",
    "element_info": {...},
    "reason": "Why this step is essential"
  }
]
```

If no essential steps remain, respond with: []

## Rules
- Preserve the original element_info for each kept step
- Add a "reason" field explaining why the step is essential
- Do NOT invent new steps
- Do NOT modify element_info values
- Keep steps in their original order
"""

    def __init__(self, llm_provider: BaseLLMProvider = None):
        """Initialize script refiner.

        Args:
            llm_provider: Optional LLM provider. Uses default if not provided.
        """
        if llm_provider:
            self.llm = llm_provider
        else:
            self.llm = LLMFactory.get_default(settings.llm_config)

        self.prompt_template = settings.llm_config.get(
            "refine_prompt_template",
            self.DEFAULT_PROMPT,
        )

    async def refine(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Refine agent steps by removing unnecessary ones.

        Args:
            steps: List of step dicts from agent execution

        Returns:
            List of refined/essential steps
        """
        if not steps:
            return []

        trace_id = get_trace_id()
        logger.info(f"[{trace_id}] Refining {len(steps)} steps with LLM")

        # Filter out obvious non-essential steps before sending to LLM
        prefiltered = self._prefilter_steps(steps)
        logger.info(f"[{trace_id}] After prefilter: {len(prefiltered)} steps")

        if not prefiltered:
            return []

        # If very few steps, skip LLM refinement
        if len(prefiltered) <= 2:
            return prefiltered

        # Build prompt with steps
        prompt = self._build_prompt(prefiltered)

        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
            refined = self._parse_response(response)

            logger.info(f"[{trace_id}] Refined to {len(refined)} essential steps")

            # Fallback to prefiltered if refinement returned empty
            if not refined and prefiltered:
                logger.info(f"[{trace_id}] LLM refinement returned empty, using prefiltered {len(prefiltered)} steps")
                return prefiltered

            return refined

        except Exception as e:
            logger.error(f"[{trace_id}] Script refinement error: {e}")
            # Fallback to prefiltered steps on error
            return prefiltered

    def _prefilter_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Pre-filter steps to remove obviously non-essential ones.

        This is a fast pre-filter before sending to LLM.

        Args:
            steps: Original steps

        Returns:
            Steps after pre-filtering
        """
        essential = []

        for step in steps:
            # Skip failed steps
            if not step.get("success", True):
                continue

            action = step.get("action", "")
            action_lower = action.lower() if action else ""

            # Skip back operations (usually not essential for script)
            if action_lower == "back":
                continue

            # Skip home button (unless it's the goal)
            if action_lower == "home":
                continue

            # Skip wait operations (non-contributing)
            if action_lower == "wait":
                continue

            # Skip note/call_api/interact actions
            if action_lower in ("note", "call_api", "interact"):
                continue

            # Skip steps without element_info (except launchApp and Type/Input)
            # Type actions may not have element_info but are essential for input
            if action_lower not in ("launch", "type", "input", "inputtext") and not step.get("element_info"):
                continue

            essential.append(step)

        return essential

    def _build_prompt(self, steps: list[dict[str, Any]]) -> str:
        """Build the refinement prompt with steps.

        Args:
            steps: Filtered steps

        Returns:
            Formatted prompt string
        """
        # Format steps as JSON
        steps_json = json.dumps(steps, ensure_ascii=False, indent=2)

        prompt = f"""Analyze these mobile agent execution steps and keep only essential ones:

{steps_json}

Respond with ONLY a JSON array of essential steps in this format:
```json
[
  {{
    "action": "Tap",
    "element_info": {{...}},
    "reason": "Why this step is essential"
  }}
]
```"""
        return prompt

    def _parse_response(self, response: LLMResponse) -> list[dict[str, Any]]:
        """Parse LLM response to extract refined steps.

        Args:
            response: LLM response

        Returns:
            List of refined steps
        """
        try:
            content = response.content.strip()

            # Extract JSON from response
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end]
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end]

            content = content.strip()

            # Handle empty response
            if not content or content == "[]":
                return []

            result = json.loads(content)

            if not isinstance(result, list):
                logger.warning(f"Expected list, got {type(result)}")
                return []

            # Validate and clean each step
            refined = []
            for step in result:
                if isinstance(step, dict) and "action" in step:
                    # Ensure element_info is preserved if present
                    cleaned = {
                        "action": step.get("action"),
                        "reason": step.get("reason", ""),
                    }
                    if "element_info" in step:
                        cleaned["element_info"] = step["element_info"]
                    refined.append(cleaned)

            return refined

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse refined steps as JSON: {e}")
            logger.debug(f"Raw response: {response.content}")
            return []
