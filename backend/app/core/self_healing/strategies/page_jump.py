"""Page jump fix strategy."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class PageJumpStrategy:
    """Strategy for fixing unexpected page navigation."""

    async def fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Attempt to fix page jump error.

        Args:
            step: Original step
            error: Error message
            screenshot: Screenshot at failure

        Returns:
            Fixed step or None
        """
        # Add navigation back
        fixed_step = step.copy()
        fixed_step["_pre_action"] = "goBack"
        fixed_step["_healed"] = True

        logger.info("Adding goBack pre-action for page jump")
        return fixed_step

    def get_expected_page_actions(self) -> list[str]:
        """Get actions that typically cause page jumps.

        Returns:
            List of problematic actions
        """
        return [
            "tapOnElement",
            "inputText",
            "swipe",
        ]
