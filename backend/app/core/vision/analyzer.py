"""Vision analyzer for screenshot analysis."""
from typing import Optional, Any
from dataclasses import dataclass

from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.factory import LLMFactory
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VisionResult:
    """Result of vision analysis."""

    detected_elements: list[dict]
    page_type: Optional[str]
    has_popup: bool
    confidence: float
    raw_response: Any


class VisionAnalyzer:
    """Analyzes screenshots using vision models."""

    def __init__(self, llm_provider: BaseLLMProvider = None):
        """Initialize vision analyzer."""
        if llm_provider:
            self.llm = llm_provider
        else:
            self.llm = LLMFactory.get_default(settings.llm_config)

        self.similarity_threshold = settings.llm_config.get(
            "vision", {}
        ).get("similarity_threshold", 0.85)

    async def analyze_screenshot(
        self,
        screenshot_data: bytes,
        context: str = None,
    ) -> VisionResult:
        """Analyze a screenshot.

        Args:
            screenshot_data: Screenshot image bytes
            context: Optional context about what we're looking for

        Returns:
            VisionResult with detected elements
        """
        logger.debug(f"Analyzing screenshot, size: {len(screenshot_data)} bytes")

        # Build prompt
        prompt = "Analyze this mobile app screenshot. Identify:"
        prompt += "\n1. All visible UI elements (buttons, text fields, etc.)"
        prompt += "\n2. Page type (login, home, settings, etc.)"
        prompt += "\n3. Any popups or overlays"
        prompt += "\n4. Overall layout description"

        if context:
            prompt += f"\n\nLooking for: {context}"

        try:
            # Build message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_data.decode("base64") if isinstance(screenshot_data, bytes) else screenshot_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            response = await self.llm.chat_with_image(messages)

            # Parse response
            result = self._parse_vision_response(response.content)
            logger.debug(f"Vision analysis found {len(result.detected_elements)} elements")
            return result

        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
            return VisionResult(
                detected_elements=[],
                page_type=None,
                has_popup=False,
                confidence=0.0,
                raw_response=str(e),
            )

    async def compare_screenshots(
        self,
        screenshot1: bytes,
        screenshot2: bytes,
    ) -> dict[str, Any]:
        """Compare two screenshots.

        Args:
            screenshot1: Before screenshot
            screenshot2: After screenshot

        Returns:
            Dict with comparison results
        """
        logger.debug("Comparing screenshots")

        prompt = """Compare these two screenshots of a mobile app.
        Identify:
        1. What changed between them
        2. Did the expected action succeed?
        3. Are there any new elements or missing elements?

        Respond in JSON format:
        {
            "changed": true/false,
            "change_description": "...",
            "action_succeeded": true/false,
            "new_elements": ["..."],
            "missing_elements": ["..."]
        }"""

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot1.decode("base64"),
                            },
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot2.decode("base64"),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            response = await self.llm.chat_with_image(messages)

            import json
            result = json.loads(response.content)
            return result

        except Exception as e:
            logger.error(f"Screenshot comparison error: {e}")
            return {
                "changed": False,
                "error": str(e),
            }

    async def find_element(
        self,
        screenshot: bytes,
        element_description: str,
    ) -> Optional[dict]:
        """Find a specific element in screenshot.

        Args:
            screenshot: Screenshot to search
            element_description: Description of element to find

        Returns:
            Element location dict or None
        """
        logger.debug(f"Finding element: {element_description}")

        prompt = f"""Look at this screenshot and find the element described as: {element_description}

        Respond in JSON format:
        {{
            "found": true/false,
            "element": {{
                "type": "button/text_field/etc",
                "text": "the text shown",
                "bounds": {{"x": 100, "y": 200, "width": 50, "height": 30}}
            }},
            "confidence": 0.95
        }}"""

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot.decode("base64") if isinstance(screenshot, bytes) else screenshot,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            response = await self.llm.chat_with_image(messages)

            import json
            result = json.loads(response.content)
            return result

        except Exception as e:
            logger.error(f"Element finding error: {e}")
            return None

    def _parse_vision_response(self, content: str) -> VisionResult:
        """Parse vision model response."""
        import json

        try:
            data = json.loads(content)
            return VisionResult(
                detected_elements=data.get("elements", []),
                page_type=data.get("page_type"),
                has_popup=data.get("has_popup", False),
                confidence=data.get("confidence", 0.8),
                raw_response=data,
            )
        except json.JSONDecodeError:
            # Return basic result if parsing fails
            return VisionResult(
                detected_elements=[],
                page_type=None,
                has_popup=False,
                confidence=0.0,
                raw_response=content,
            )
