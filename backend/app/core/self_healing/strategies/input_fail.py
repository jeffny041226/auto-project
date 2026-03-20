"""Input failure fix strategy."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class InputFailStrategy:
    """Strategy for fixing input failures."""

    async def fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Attempt to fix input failure.

        Args:
            step: Original step
            error: Error message
            screenshot: Screenshot at failure

        Returns:
            Fixed step or None
        """
        action = step.get("action", "")
        target = step.get("target", "")
        value = step.get("value", "")

        if "input" not in action.lower():
            return None

        fixed_steps = []

        # Step 1: Clear existing text
        clear_step = {
            "action": "tapOnElement",
            "target": target,
            "value": None,
            "_healed": True,
        }
        fixed_steps.append(clear_step)

        # Step 2: Clear field (long press + delete)
        clear_field = {
            "action": "pressKey",
            "target": "CLEAR",
            "value": None,
            "_healed": True,
        }
        fixed_steps.append(clear_field)

        # Step 3: Try input again
        input_step = step.copy()
        input_step["_healed"] = True
        fixed_steps.append(input_step)

        # Return first fixed step (will chain)
        logger.info("Created multi-step fix for input failure")
        return fixed_steps[0]

    def should_clear_first(self, error: str) -> bool:
        """Determine if field should be cleared first.

        Args:
            error: Error message

        Returns:
            True if should clear
        """
        clear_indicators = ["already has", "cannot type", "not empty", "已有内容"]
        return any(ind in error.lower() for ind in clear_indicators)
