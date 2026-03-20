"""Element not found fix strategy."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ElementNotFoundStrategy:
    """Strategy for fixing element not found errors."""

    async def fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Attempt to fix element not found error.

        Args:
            step: Original step
            error: Error message
            screenshot: Screenshot at failure

        Returns:
            Fixed step or None
        """
        action = step.get("action", "")
        target = step.get("target", "")

        # Try alternative selectors
        alternatives = self._get_alternatives(action, target)

        for alt_target in alternatives:
            if alt_target != target:
                logger.info(f"Trying alternative target: {alt_target}")
                fixed_step = step.copy()
                fixed_step["target"] = alt_target
                fixed_step["_healed"] = True
                fixed_step["_original_target"] = target
                return fixed_step

        # Try tap on text instead of element ID
        if "tapOn" in action and target.startswith("$"):
            fixed_step = step.copy()
            fixed_step["action"] = "tapOnText"
            fixed_step["target"] = target.replace("$", "").replace("id/", "")
            fixed_step["_healed"] = True
            return fixed_step

        # Try using accessibility label
        if "Element" in action:
            fixed_step = step.copy()
            fixed_step["target"] = target.replace("Element", "AccessibilityId")
            fixed_step["_healed"] = True
            return fixed_step

        return None

    def _get_alternatives(self, action: str, target: str) -> list[str]:
        """Get alternative selectors for target.

        Args:
            action: Action type
            target: Original target

        Returns:
            List of alternative targets
        """
        alternatives = []

        # Android resource-id alternatives
        if "resource-id" in target:
            base_id = target.split("/")[-1] if "/" in target else target
            alternatives.extend([
                f"$id/{base_id}",
                f"com.example.app:id/{base_id}",
                f"//*[@resource-id='{base_id}']",
            ])

        # Text-based alternatives
        if "text" in target.lower() or "label" in target.lower():
            # Extract text value
            import re
            match = re.search(r'text="([^"]+)"', target)
            if match:
                alternatives.append(match.group(1))

        # Class-based alternatives
        if "class" in target:
            alternatives.append(target.replace("class/", "description/"))

        return alternatives
