"""Maestro Generator - Converts refined steps to Maestro YAML format.

This module transforms refined agent steps into executable Maestro test scripts.
Priority for element selection:
1. id (resource-id) - most stable
2. text - good for buttons with text
3. contentDescription - accessibility labels
4. image - screenshot-based matching (fallback when no other selector available)
5. point coordinates - absolute fallback
"""

from typing import Any, Optional

from app.utils.logger import get_logger, get_trace_id

logger = get_logger(__name__)


class MaestroGenerator:
    """Generates Maestro YAML from refined agent steps.

    Converts step data with element_info into Maestro YAML scripts.
    Element selection priority: id > text > contentDescription > image > point
    """

    def __init__(self):
        """Initialize Maestro generator."""
        pass

    def generate(
        self,
        steps: list[dict[str, Any]],
        app_id: str = "com.example.app",
        flow_name: str = "AI Generated Flow",
    ) -> str:
        """Generate Maestro YAML from refined steps.

        Args:
            steps: List of refined steps with element_info
            app_id: Target app package ID
            flow_name: Name of the flow

        Returns:
            Maestro YAML string
        """
        trace_id = get_trace_id()
        logger.info(f"[{trace_id}] Generating Maestro YAML for {len(steps)} steps")

        if not steps:
            # Return minimal script with just app launch
            return self._render_launch_only(app_id, flow_name)

        yaml_lines = [
            f"appId: {app_id}",
            "---",
            f"# Flow: {flow_name}",
            "",
        ]

        for step in steps:
            yaml_step = self._step_to_yaml(step)
            if yaml_step:
                yaml_lines.append(yaml_step)
                yaml_lines.append("")  # Empty line between steps

        yaml_content = "\n".join(yaml_lines)
        logger.debug(f"[{trace_id}] Generated {len(yaml_content)} chars of YAML")

        return yaml_content

    def _render_launch_only(self, app_id: str, flow_name: str) -> str:
        """Render a minimal script with only app launch.

        Args:
            app_id: App package ID
            flow_name: Flow name

        Returns:
            Minimal Maestro YAML
        """
        return f"""appId: {app_id}
---
# Flow: {flow_name}
- launchApp:
    appId: {app_id}"""

    def _step_to_yaml(self, step: dict[str, Any]) -> Optional[str]:
        """Convert a single step to Maestro YAML.

        Args:
            step: Step dict with action and element_info

        Returns:
            YAML string for the step or None if step is not supported
        """
        action = step.get("action", "")
        element_info = step.get("element_info")

        if not action:
            return None

        action_lower = action.lower()

        # Handle launchApp separately
        if action_lower == "launch":
            return self._render_launch(step)

        # For tap actions, use element_info
        if action_lower in ("tap", "click"):
            return self._render_tap(step, element_info)

        # For input/text actions
        if action_lower in ("type", "input", "inputtext"):
            return self._render_input(step)

        # For swipe actions
        if action_lower == "swipe":
            return self._render_swipe(step)

        # For back action
        if action_lower == "back":
            return "- pressBack"

        # For home action
        if action_lower == "home":
            return "- pressHome"

        # For scroll
        if action_lower == "scroll":
            return "- scroll"

        # For wait
        if action_lower == "wait":
            return "- waitForAnimationToEnd"

        # Log unsupported action
        logger.debug(f"Unsupported action: {action}")
        return None

    def _render_launch(self, step: dict[str, Any]) -> str:
        """Render launchApp step.

        Args:
            step: Step dict

        Returns:
            YAML string
        """
        # Try to get package name from element_info.resource_id (actual package name)
        # or fall back to text (app display name) or action params
        package_name = None

        if "element_info" in step and step["element_info"]:
            # Priority: resource_id (package name) > text (display name)
            package_name = step["element_info"].get("resource_id")
            if not package_name or package_name.startswith("input:"):
                package_name = step["element_info"].get("text")

        if not package_name:
            # Try to get from action params
            action = step.get("action_data", {})
            package_name = action.get("package") or action.get("app")

        if not package_name:
            package_name = "unknown"

        return f"""- launchApp:
    appId: {package_name}"""

    def _render_tap(self, step: dict[str, Any], element_info: Optional[dict]) -> str:
        """Render tapOn step with element selection priority.

        Priority: id > text > contentDescription > image > point

        Args:
            step: Step dict
            element_info: Element information dict

        Returns:
            YAML string
        """
        if not element_info:
            # Fallback to point if no element_info
            return "# Tap (no element info - coordinate tap needed)"

        # Priority 1: resource-id (most stable)
        resource_id = element_info.get("resource_id")
        if resource_id and resource_id.strip() and not resource_id.startswith("input:"):
            return f"""- tapOn:
    id: {resource_id}"""

        # Priority 2: text
        text = element_info.get("text")
        if text and text.strip():
            return f"""- tapOn:
    text: {text}"""

        # Priority 3: content description
        content_desc = element_info.get("content_desc")
        if content_desc and content_desc.strip():
            return f"""- tapOn:
    contentDescription: {content_desc}"""

        # Priority 4: image-based matching (screenshot)
        image_data = element_info.get("image_data") or element_info.get("screenshot")
        if image_data and isinstance(image_data, str) and len(image_data) > 100:
            # Image data is base64 encoded screenshot
            return f"""- tapOn:
    image: {image_data}"""

        # Priority 5: point coordinates
        center_coords = element_info.get("center_coords")
        if center_coords and len(center_coords) == 2:
            x, y = center_coords
            return f"""- tapOn:
    point: {x},{y}"""

        # Fallback
        bounds = element_info.get("bounds")
        if bounds and len(bounds) == 4:
            x1, y1, x2, y2 = bounds
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            return f"""- tapOn:
    point: {center_x},{center_y}"""

        return "# Tap (no valid selector)"

    def _render_input(self, step: dict[str, Any]) -> str:
        """Render inputText step.

        Args:
            step: Step dict

        Returns:
            YAML string
        """
        # Get text from various sources
        text = None
        element_info = step.get("element_info")

        # Try action_data or text field
        action_data = step.get("action_data", {})
        text = action_data.get("text") or step.get("text")

        if not text:
            text = step.get("value", "")

        if not text:
            return "# Input (no text provided)"

        # Escape special characters
        text_escaped = text.replace("\\", "\\\\").replace('"', '\\"')

        # Try to build element selector from element_info
        selector_parts = []
        if element_info:
            # Priority 1: resource-id
            resource_id = element_info.get("resource_id")
            if resource_id and resource_id.strip():
                selector_parts.append(f"id: {resource_id}")

            # Priority 2: text (for input fields, this is usually hint text)
            text_val = element_info.get("text")
            if text_val and text_val.strip() and not text_val.startswith("input:"):
                selector_parts.append(f"text: {text_val}")

            # Priority 3: content-desc
            content_desc = element_info.get("content_desc")
            if content_desc and content_desc.strip():
                selector_parts.append(f"contentDescription: {content_desc}")

        if selector_parts:
            # Maestro supports inputText with element selector
            selector_str = " ".join(selector_parts)
            return f'- inputText:\n    {selector_str}\n    text: "{text_escaped}"'
        else:
            # Fallback: just inputText without selector (types at current cursor)
            return f'- inputText:\n    text: "{text_escaped}"'

    def _render_swipe(self, step: dict[str, Any]) -> str:
        """Render swipe step.

        Args:
            step: Step dict

        Returns:
            YAML string
        """
        action_data = step.get("action_data", {})
        start = action_data.get("start", [0.5, 0.8])
        end = action_data.get("end", [0.5, 0.2])
        duration = action_data.get("duration", 500)

        # Convert relative to absolute if needed (assuming 0-1 range)
        if all(0 <= v <= 1 for v in start + end):
            start_x, start_y = int(start[0] * 1000), int(start[1] * 1000)
            end_x, end_y = int(end[0] * 1000), int(end[1] * 1000)
        else:
            start_x, start_y = start
            end_x, end_y = end

        return f"""- swipe:
    startX: {start_x}
    startY: {start_y}
    endX: {end_x}
    endY: {end_y}
    duration: {duration}"""

    def step_to_maestro_action(self, step: dict[str, Any]) -> str:
        """Convert a single step to Maestro action format.

        Args:
            step: Step dict

        Returns:
            Maestro action string (single line or multi-line YAML)
        """
        yaml = self._step_to_yaml(step)
        return yaml if yaml else ""
