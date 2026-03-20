"""Intent classifier using LLM."""
import json
from typing import Any

from app.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm.factory import LLMFactory
from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


class IntentClassifier:
    """LLM-based intent classifier for test instructions."""

    SUPPORTED_INTENTS = [
        "app_open",
        "login",
        "logout",
        "swipe",
        "tap",
        "input",
        "assert",
        "scroll",
        "capture",
        "wait",
        "screenshot",
    ]

    def __init__(self, llm_provider: BaseLLMProvider = None):
        """Initialize classifier with LLM provider."""
        if llm_provider:
            self.llm = llm_provider
        else:
            self.llm = LLMFactory.get_default(settings.llm_config)

        self.prompt_template = settings.llm_config.get(
            "intent_prompt_template",
            self._default_prompt_template(),
        )

    async def classify(self, instruction: str) -> dict[str, Any]:
        """Classify instruction intent using LLM.

        Args:
            instruction: Cleaned user instruction

        Returns:
            Dict with intent, entities, and confidence
        """
        trace_id = get_trace_id()
        logger.info(f"[{trace_id}] Classifying intent for: {instruction[:50]}...")

        # Build prompt
        prompt = self.prompt_template.replace("{{instruction}}", instruction)

        messages = [
            {"role": "system", "content": "You are an intent classifier for mobile app testing."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm.chat(messages)
            result = self._parse_response(response)

            logger.info(
                f"[{trace_id}] Classified intent: {result.get('intent')}, "
                f"confidence: {result.get('confidence', 0):.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"[{trace_id}] Intent classification error: {e}")
            # Return fallback intent
            return {
                "intent": "tap",
                "entities": {},
                "confidence": 0.0,
                "error": str(e),
            }

    def _parse_response(self, response: LLMResponse) -> dict[str, Any]:
        """Parse LLM response into structured intent."""
        try:
            content = response.content.strip()

            # Try to extract JSON from response
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

            # Validate intent
            if result.get("intent") not in self.SUPPORTED_INTENTS:
                logger.warning(f"Unknown intent: {result.get('intent')}, defaulting to tap")
                result["intent"] = "tap"

            # Ensure required fields
            result.setdefault("entities", {})
            result.setdefault("confidence", 0.5)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response.content}")
            return {
                "intent": "tap",
                "entities": {},
                "confidence": 0.0,
                "error": f"Parse error: {e}",
            }

    def _default_prompt_template(self) -> str:
        """Get default prompt template."""
        return """Classify the following user instruction for mobile app testing.

Supported intents:
- app_open: Launch/open an application
- login: Login to an app with credentials
- logout: Logout from an app
- swipe: Swipe on screen (up/down/left/right)
- tap: Tap on element or coordinate
- input: Input text into a field
- assert: Verify element state or text
- scroll: Scroll on screen
- wait: Wait for element or condition
- screenshot: Capture screenshot
- capture: Same as screenshot

Instruction: {instruction}

Respond with JSON only:
{{"intent": "intent_name", "entities": {{"key": "value"}}, "confidence": 0.95}}"""
