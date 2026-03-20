"""Script validator for pre-execution validation."""
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptValidator:
    """Validates scripts before execution."""

    SUPPORTED_ACTIONS = {
        "launchApp",
        "tapOn",
        "tapOnElement",
        "tapOnText",
        "inputText",
        "swipe",
        "scroll",
        "waitForElement",
        "waitForElementToAppear",
        "assertExists",
        "assertText",
        "screenshot",
        "pressKey",
        "goBack",
        "openLink",
    }

    def validate(self, script: dict) -> tuple[bool, Optional[str]]:
        """Validate script structure.

        Args:
            script: Script dict with steps

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not script:
            return False, "Script is empty"

        # Validate steps exist
        steps = script.get("steps", [])
        if not steps:
            return False, "Script has no steps"

        # Validate each step
        for i, step in enumerate(steps):
            is_valid, error = self._validate_step(step, i)
            if not is_valid:
                return False, error

        # Validate first step is usually launchApp
        first_action = steps[0].get("action", "")
        if first_action != "launchApp":
            logger.warning(f"First action is not launchApp: {first_action}")

        return True, None

    def _validate_step(self, step: dict, index: int) -> tuple[bool, Optional[str]]:
        """Validate a single step.

        Args:
            step: Step dict
            index: Step index

        Returns:
            Tuple of (is_valid, error_message)
        """
        action = step.get("action")
        if not action:
            return False, f"Step {index}: Missing action"

        if action not in self.SUPPORTED_ACTIONS:
            return False, f"Step {index}: Unsupported action '{action}'"

        # Action-specific validation
        if action == "launchApp":
            if not step.get("target"):
                return False, f"Step {index}: launchApp missing target (appId)"

        elif action == "inputText":
            if step.get("value") is None:
                return False, f"Step {index}: inputText missing value"

        elif action == "swipe":
            value = step.get("value", {})
            if not isinstance(value, dict):
                return False, f"Step {index}: swipe value must be an object"

        elif action == "waitForElement":
            if step.get("value") is None:
                return False, f"Step {index}: waitForElement missing timeout value"

        return True, None

    def validate_yaml(self, yaml_content: str) -> tuple[bool, Optional[str]]:
        """Validate Maestro YAML content.

        Args:
            yaml_content: YAML string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not yaml_content or not yaml_content.strip():
            return False, "YAML content is empty"

        # Basic YAML structure check
        lines = yaml_content.split("\n")

        # Check for appId
        has_app_id = any("appId:" in line for line in lines)
        if not has_app_id:
            return False, "Missing appId declaration"

        # Check for flow separator
        has_flow = "---" in yaml_content
        if not has_flow:
            return False, "Missing flow separator '---'"

        return True, None
