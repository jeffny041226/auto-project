"""Screenshot redactor for removing sensitive data."""
import re
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import io

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenshotRedactor:
    """Redacts sensitive information from screenshots."""

    PHONE_PATTERN = r"1[3-9]\d{9}"
    EMAIL_PATTERN = r"[\w.-]+@[\w.-]+\.\w+"
    ID_CARD_PATTERN = r"\d{17}[\dXx]"
    BANK_CARD_PATTERN = r"\d{16,19}"
    PASSWORD_PATTERN = r"password[:\s]*\S+"

    def __init__(self):
        """Initialize redactor."""
        pass

    async def redact_screenshot(
        self,
        screenshot_bytes: bytes,
        text_annotations: list[dict],
    ) -> bytes:
        """Redact sensitive data from screenshot.

        Args:
            screenshot_bytes: Original screenshot
            text_annotations: Text regions detected by OCR/vision

        Returns:
            Redacted screenshot bytes
        """
        try:
            img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
            draw = ImageDraw.Draw(img)

            # Default block color (black)
            fill_color = (0, 0, 0)

            # Redact phone numbers
            for ann in text_annotations:
                text = ann.get("text", "")
                bounds = ann.get("bounds", {})

                if self._contains_phone(text):
                    self._draw_rect(draw, bounds, fill_color)

                if self._contains_email(text):
                    self._draw_rect(draw, bounds, fill_color)

            # Redact detected sensitive regions (bounding boxes)
            # This would be enhanced with actual OCR detections

            # Convert back to bytes
            output = io.BytesIO()
            img.save(output, format="PNG")
            return output.getvalue()

        except Exception as e:
            logger.error(f"Screenshot redaction error: {e}")
            return screenshot_bytes

    def _contains_phone(self, text: str) -> bool:
        """Check if text contains phone number."""
        return bool(re.search(self.PHONE_PATTERN, text))

    def _contains_email(self, text: str) -> bool:
        """Check if text contains email."""
        return bool(re.search(self.EMAIL_PATTERN, text))

    def _draw_rect(self, draw: ImageDraw.Draw, bounds: dict, fill: tuple) -> None:
        """Draw filled rectangle.

        Args:
            draw: ImageDraw context
            bounds: Dict with x, y, width, height
            fill: RGB fill color
        """
        x = bounds.get("x", 0)
        y = bounds.get("y", 0)
        width = bounds.get("width", 100)
        height = bounds.get("height", 30)

        draw.rectangle([x, y, x + width, y + height], fill=fill)

    def detect_sensitive_regions(self, screenshot_bytes: bytes) -> list[dict]:
        """Detect regions that may contain sensitive data.

        Args:
            screenshot_bytes: Screenshot to analyze

        Returns:
            List of sensitive region bounds
        """
        # In a real implementation, this would use OCR + pattern matching
        # For now, return empty list
        return []
