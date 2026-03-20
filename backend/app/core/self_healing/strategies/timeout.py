"""Timeout fix strategy."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class TimeoutStrategy:
    """Strategy for fixing timeout errors."""

    DEFAULT_TIMEOUT_MS = 5000
    EXTENDED_TIMEOUT_MS = 15000

    async def fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Attempt to fix timeout error.

        Args:
            step: Original step
            error: Error message
            screenshot: Screenshot at failure

        Returns:
            Fixed step with extended timeout or None
        """
        action = step.get("action", "")

        # Only extend timeout for wait/delay actions
        if "wait" in action.lower():
            fixed_step = step.copy()
            fixed_step["value"] = self.EXTENDED_TIMEOUT_MS
            fixed_step["_healed"] = True
            logger.info(f"Extended timeout to {self.EXTENDED_TIMEOUT_MS}ms")
            return fixed_step

        # For other actions, add explicit wait before
        fixed_step = step.copy()
        fixed_step["_pre_action"] = {
            "action": "waitForElementToAppear",
            "target": step.get("target"),
            "value": self.EXTENDED_TIMEOUT_MS,
        }
        fixed_step["_healed"] = True
        logger.info("Added explicit wait before action")
        return fixed_step

    def parse_timeout_from_error(self, error: str) -> Optional[int]:
        """Parse timeout value from error message.

        Args:
            error: Error message

        Returns:
            Timeout in ms or None
        """
        import re

        match = re.search(r"(\d+)\s*(ms|second|sec)", error, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            if unit.startswith("s"):
                value *= 1000
            return value

        return None
