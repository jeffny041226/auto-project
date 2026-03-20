"""Script generator using LLM."""
import json
from typing import Any

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm.factory import LLMFactory
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


class ScriptGenerator:
    """Generates test scripts from structured instructions."""

    def __init__(self, llm_provider: BaseLLMProvider = None):
        """Initialize script generator."""
        if llm_provider:
            self.llm = llm_provider
        else:
            self.llm = LLMFactory.get_default(settings.llm_config)

        self.prompt_template = settings.llm_config.get(
            "script_prompt_template",
            self._default_prompt_template(),
        )

    async def generate(
        self,
        intent: str,
        entities: dict[str, Any],
        instruction: str,
    ) -> dict[str, Any]:
        """Generate pseudo code from intent and entities.

        Args:
            intent: Classified intent name
            entities: Extracted entities
            instruction: Original instruction

        Returns:
            Dict with steps and metadata
        """
        trace_id = get_trace_id()
        logger.info(f"[{trace_id}] Generating script for intent: {intent}")

        # Build prompt
        prompt = self.prompt_template.replace("{{intent}}", intent)
        prompt = prompt.replace("{{entities}}", json.dumps(entities, ensure_ascii=False))
        prompt = prompt.replace("{{instruction}}", instruction)

        messages = [
            {
                "role": "system",
                "content": "You are a mobile app testing script generator. "
                          "Generate step-by-step pseudo code for Maestro framework.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
            result = self._parse_response(response)

            logger.info(f"[{trace_id}] Generated {len(result.get('steps', []))} steps")
            return result

        except Exception as e:
            logger.error(f"[{trace_id}] Script generation error: {e}")
            return {
                "steps": [],
                "error": str(e),
            }

    def _parse_response(self, response: LLMResponse) -> dict[str, Any]:
        """Parse LLM response into script steps."""
        try:
            content = response.content.strip()

            # Extract JSON
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end]
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end]

            content = content.strip()
            result = json.loads(content)

            # Ensure steps exist
            if "steps" not in result:
                result["steps"] = []

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse script response as JSON: {e}")
            logger.debug(f"Raw response: {response.content}")
            return {
                "steps": [],
                "error": f"Parse error: {e}",
            }

    def _default_prompt_template(self) -> str:
        """Get default script generation prompt."""
        return """Generate a test script for mobile app testing.

Intent: {intent}
Entities: {entities}
Instruction: {instruction}

Generate step-by-step pseudo code that includes:
1. Clear action names (launchApp, tap, input, swipe, wait, assert, etc.)
2. Target elements or coordinates
3. Values where needed (text to input, swipe direction, etc.)
4. Wait conditions between actions

Maestro action reference:
- launchApp: Launch an app (appId: "com.tencent.mm")
- tapOnElement: Tap on UI element (selector: "...")
- tapOnText: Tap on text element (text: "Login")
- inputText: Input text (text: "hello")
- swipe: Swipe on screen (startX, startY, endX, endY, duration)
- waitForElement: Wait for element to appear (selector, timeout)
- assertExists: Assert element exists
- assertText: Assert element contains text
- screenshot: Take screenshot

Respond with JSON only:
{{"steps": [
  {{"action": "launchApp", "target": "com.tencent.mm", "value": null}},
  {{"action": "waitForElement", "target": "loginButton", "value": 5000}},
  {{"action": "tapOnElement", "target": "loginButton", "value": null}},
  {{"action": "inputText", "target": "usernameField", "value": "testuser"}}
]}}"""
