"""Popup fix strategy."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class PopupStrategy:
    """Strategy for handling popup interference."""

    POPUP_DISMISS_ACTIONS = [
        {"action": "tapOnText", "target": "Close", "value": None},
        {"action": "tapOnText", "target": "Cancel", "value": None},
        {"action": "tapOnText", "target": "OK", "value": None},
        {"action": "tapOnText", "target": "确定", "value": None},
        {"action": "tapOnText", "target": "取消", "value": None},
        {"action": "goBack", "value": None},
    ]

    async def fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Attempt to fix popup interference.

        Args:
            step: Original step
            error: Error message
            screenshot: Screenshot at failure

        Returns:
            Fixed step with popup dismissal or None
        """
        # Return a compound step that dismisses popup first
        fixed_step = step.copy()
        fixed_step["_pre_actions"] = self.POPUP_DISMISS_ACTIONS[:3]
        fixed_step["_healed"] = True

        logger.info("Adding popup dismissal pre-actions")
        return fixed_step

    async def detect_popup(self, screenshot: bytes) -> Optional[dict]:
        """Detect if there's a popup in screenshot.

        Args:
            screenshot: Screenshot bytes

        Returns:
            Popup info dict or None
        """
        # In a real implementation, use vision analysis
        return None
