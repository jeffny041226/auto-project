"""AutoGLM Vision Provider - Screenshot analysis and element recognition."""
import os
import json
import base64
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ElementInfo:
    """Detected UI element information."""
    element_type: str
    text: Optional[str]
    bounds: dict[str, int]  # x, y, width, height
    confidence: float
    resource_id: Optional[str] = None


@dataclass
class VisionAnalysisResult:
    """Result of vision analysis."""
    page_type: str
    elements: list[ElementInfo]
    has_popup: bool
    popup_description: Optional[str]
    overall_description: str
    confidence: float


@dataclass
class ElementSearchResult:
    """Result of element search in screenshot."""
    found: bool
    element: Optional[ElementInfo]
    suggestions: list[str]
    confidence: float


@dataclass
class PageChangeResult:
    """Result of page change detection."""
    changed: bool
    change_type: str  # "added", "removed", "modified", "none"
    changed_elements: list[str]
    action_succeeded: bool
    description: str


class AutoGLMProvider(BaseLLMProvider):
    """AutoGLM Vision Provider for screenshot analysis.

    AutoGLM is a vision-based page understanding model used for:
    - Screenshot analysis
    - Element recognition
    - Page state comparison

    This provider integrates with AutoGLM-compatible vision APIs.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize AutoGLM provider.

        Args:
            config: Configuration dict with keys:
                - api_key: AutoGLM API key
                - api_base: Base URL for AutoGLM API
                - model: Vision model name (default: auto-glm-vision)
                - timeout: Request timeout in seconds
        """
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("AUTOGLM_API_KEY")
        self.api_base = config.get(
            "api_base",
            "https://api.minimax.chat/v1"
        ).rstrip("/")
        self.model = config.get("model", "auto-glm-vision")
        self.timeout = config.get("timeout", 30)

        # HTTP client for API calls with redirect handling
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with redirect support."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                follow_redirects=True,  # Handle 308 redirects automatically
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Chat completion (not supported for vision-only provider).

        Raises:
            NotImplementedError: AutoGLM is vision-only
        """
        raise NotImplementedError(
            "AutoGLMProvider is vision-only. Use analyze_screenshot() instead."
        )

    async def embed(self, text: str) -> EmbeddingResponse:
        """Embedding generation (not supported for vision-only provider).

        Raises:
            NotImplementedError: AutoGLM is vision-only
        """
        raise NotImplementedError(
            "AutoGLMProvider does not support embeddings."
        )

    async def health_check(self) -> bool:
        """Check AutoGLM API health."""
        try:
            # Try a simple API call
            response = await self.client.post(
                f"{self.api_base}/health",
                json={"check": True},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"AutoGLM health check failed: {e}")
            return False

    def supports_vision(self) -> bool:
        """AutoGLM is a vision provider."""
        return True

    async def analyze_screenshot(
        self,
        screenshot: bytes,
        context: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """Analyze a screenshot and identify UI elements.

        Args:
            screenshot: Screenshot image bytes (PNG/JPEG)
            context: Optional context about what we're looking for

        Returns:
            VisionAnalysisResult with detected elements
        """
        logger.debug(f"Analyzing screenshot, size: {len(screenshot)} bytes")

        # Encode image to base64
        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        # Build prompt
        prompt = self._build_analysis_prompt(context)

        try:
            response = await self.client.post(
                f"{self.api_base}/vision/analyze",
                json={
                    "model": self.model,
                    "image": image_b64,
                    "prompt": prompt,
                    "return_elements": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_analysis_result(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"AutoGLM API error: {e.response.status_code} - {e.response.text}")
            return VisionAnalysisResult(
                page_type="unknown",
                elements=[],
                has_popup=False,
                popup_description=None,
                overall_description="Analysis failed",
                confidence=0.0,
            )
        except Exception as e:
            logger.error(f"AutoGLM analysis error: {e}")
            return VisionAnalysisResult(
                page_type="unknown",
                elements=[],
                has_popup=False,
                popup_description=None,
                overall_description=f"Error: {str(e)}",
                confidence=0.0,
            )

    async def find_element(
        self,
        screenshot: bytes,
        element_description: str,
    ) -> ElementSearchResult:
        """Find a specific element in a screenshot.

        Args:
            screenshot: Screenshot image bytes
            element_description: Description of element to find

        Returns:
            ElementSearchResult with found element info
        """
        image_b64 = base64.b64encode(screenshot).decode("utf-8")

        prompt = f"""Find the element described as: {element_description}

Return the element's location and properties."""

        try:
            response = await self.client.post(
                f"{self.api_base}/vision/find_element",
                json={
                    "model": self.model,
                    "image": image_b64,
                    "prompt": prompt,
                },
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_element_result(data)

        except Exception as e:
            logger.error(f"AutoGLM find_element error: {e}")
            return ElementSearchResult(
                found=False,
                element=None,
                suggestions=[],
                confidence=0.0,
            )

    async def compare_screenshots(
        self,
        before: bytes,
        after: bytes,
        expected_change: Optional[str] = None,
    ) -> PageChangeResult:
        """Compare two screenshots to detect changes.

        Args:
            before: Screenshot before action
            after: Screenshot after action
            expected_change: Description of expected change

        Returns:
            PageChangeResult with change detection
        """
        before_b64 = base64.b64encode(before).decode("utf-8")
        after_b64 = base64.b64encode(after).decode("utf-8")

        prompt = "Compare these two screenshots."
        if expected_change:
            prompt += f"\n\nExpected change: {expected_change}"

        try:
            response = await self.client.post(
                f"{self.api_base}/vision/compare",
                json={
                    "model": self.model,
                    "image_before": before_b64,
                    "image_after": after_b64,
                    "prompt": prompt,
                },
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_comparison_result(data)

        except Exception as e:
            logger.error(f"AutoGLM compare error: {e}")
            return PageChangeResult(
                changed=False,
                change_type="error",
                changed_elements=[],
                action_succeeded=False,
                description=f"Comparison error: {str(e)}",
            )

    def _build_analysis_prompt(self, context: Optional[str] = None) -> str:
        """Build prompt for screenshot analysis."""
        prompt = """Analyze this mobile app screenshot. Identify:
1. All visible UI elements (buttons, text fields, icons, etc.) with their locations
2. Page type (login, home, settings, list, detail, etc.)
3. Any popups, dialogs, or overlays
4. Overall layout and current state

Provide detailed information about each element found."""
        if context:
            prompt += f"\n\nSpecific context: {context}"
        return prompt

    def _parse_analysis_result(self, data: dict) -> VisionAnalysisResult:
        """Parse API response into VisionAnalysisResult."""
        elements = []
        for elem_data in data.get("elements", []):
            elements.append(ElementInfo(
                element_type=elem_data.get("type", "unknown"),
                text=elem_data.get("text"),
                bounds=elem_data.get("bounds", {}),
                confidence=elem_data.get("confidence", 0.8),
                resource_id=elem_data.get("resource_id"),
            ))

        return VisionAnalysisResult(
            page_type=data.get("page_type", "unknown"),
            elements=elements,
            has_popup=data.get("has_popup", False),
            popup_description=data.get("popup_description"),
            overall_description=data.get("description", ""),
            confidence=data.get("confidence", 0.8),
        )

    def _parse_element_result(self, data: dict) -> ElementSearchResult:
        """Parse API response into ElementSearchResult."""
        element = None
        if data.get("found") and data.get("element"):
            elem_data = data["element"]
            element = ElementInfo(
                element_type=elem_data.get("type", "unknown"),
                text=elem_data.get("text"),
                bounds=elem_data.get("bounds", {}),
                confidence=elem_data.get("confidence", 0.8),
                resource_id=elem_data.get("resource_id"),
            )

        return ElementSearchResult(
            found=data.get("found", False),
            element=element,
            suggestions=data.get("suggestions", []),
            confidence=data.get("confidence", 0.0),
        )

    def _parse_comparison_result(self, data: dict) -> PageChangeResult:
        """Parse API response into PageChangeResult."""
        return PageChangeResult(
            changed=data.get("changed", False),
            change_type=data.get("change_type", "none"),
            changed_elements=data.get("changed_elements", []),
            action_succeeded=data.get("action_succeeded", False),
            description=data.get("description", ""),
        )

    async def chat_with_image(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Vision chat (fallback to analyze_screenshot).

        This is a fallback for code that expects LLM-style interface.
        """
        # Extract image from messages
        image_data = None
        prompt = ""

        for msg in messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if isinstance(item, dict):
                        if item.get("type") == "image" or item.get("source", {}).get("type") == "image":
                            # Handle both direct image and source dict formats
                            if "data" in item:
                                image_data = base64.b64decode(item["data"])
                            elif item.get("source", {}).get("data"):
                                image_data = base64.b64decode(item["source"]["data"])
                        elif item.get("type") == "text":
                            prompt = item.get("text", "")

        if not image_data:
            raise ValueError("No image found in messages")

        result = await self.analyze_screenshot(image_data, prompt)

        # Convert to LLMResponse format
        response_text = json.dumps({
            "page_type": result.page_type,
            "elements": [
                {
                    "type": e.element_type,
                    "text": e.text,
                    "bounds": e.bounds,
                    "confidence": e.confidence,
                }
                for e in result.elements
            ],
            "has_popup": result.has_popup,
            "description": result.overall_description,
            "confidence": result.confidence,
        })

        return LLMResponse(
            content=response_text,
            model=self.model,
            usage={"tokens": 0},
            finish_reason="stop",
            raw_response=result,
        )
