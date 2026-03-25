"""Maestro Script Generator - Generates Maestro YAML scripts with multiple element location strategies.

This module provides Maestro script generation with support for:
- id: Resource ID based element location
- text: Text matching based element location
- image: Image template matching based element location
- point: Direct coordinate based location (fallback)

The AI chooses the most appropriate strategy based on screen analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class ElementStrategy(Enum):
    """Element location strategy."""

    ID = "id"           # Resource ID (most stable)
    TEXT = "text"       # Text matching
    IMAGE = "image"     # Image template matching
    POINT = "point"     # Direct coordinates (fallback)


@dataclass
class ScriptStep:
    """A single step in the generated script."""

    action: str
    # Element location strategy
    strategy: Optional[ElementStrategy] = None
    # Element identifier based on strategy
    element_id: Optional[str] = None      # For ID strategy: "com.tencent.mm:id/btn"
    element_text: Optional[str] = None    # For TEXT strategy: "登录"
    element_image: Optional[str] = None   # For IMAGE strategy: base64 or file path
    # Coordinates for POINT strategy or fallback
    x: Optional[int] = None
    y: Optional[int] = None
    # Additional parameters
    text: Optional[str] = None            # For inputText action
    start_x: Optional[int] = None
    start_y: Optional[int] = None
    end_x: Optional[int] = None
    end_y: Optional[int] = None
    duration: Optional[int] = None        # For swipe duration
    app_id: Optional[str] = None         # For launchApp action
    key: Optional[str] = None             # For pressKey action
    message: Optional[str] = None         # For notes


class MaestroScriptBuilder:
    """Builds Maestro YAML scripts with multi-strategy element support.

    This class accumulates actions during exploration and generates
    Maestro YAML with optimal element location strategies.
    """

    def __init__(self, app_id: str = "com.example.app"):
        """Initialize script builder.

        Args:
            app_id: App package ID for the Maestro script
        """
        self.app_id = app_id
        self.flow_name = ""
        self.steps: list[ScriptStep] = []

    def set_flow_name(self, name: str):
        """Set the flow name."""
        self.flow_name = name

    def set_app_id(self, app_id: str):
        """Set the app package ID."""
        self.app_id = app_id

    def add_launch(self, app_id: str):
        """Add a launchApp step."""
        step = ScriptStep(action="launchApp", app_id=app_id)
        self.steps.append(step)

    def add_tap_by_id(self, resource_id: str):
        """Add a tapOn step by resource ID (most stable)."""
        step = ScriptStep(action="tapOn", strategy=ElementStrategy.ID, element_id=resource_id)
        self.steps.append(step)

    def add_tap_by_text(self, text: str):
        """Add a tapOn step by text matching."""
        step = ScriptStep(action="tapOn", strategy=ElementStrategy.TEXT, element_text=text)
        self.steps.append(step)

    def add_tap_by_image(self, image_data: str):
        """Add a tapOn step by image template matching."""
        step = ScriptStep(action="tapOn", strategy=ElementStrategy.IMAGE, element_image=image_data)
        self.steps.append(step)

    def add_tap_by_point(self, x: int, y: int):
        """Add a tapOn step by direct coordinates (fallback)."""
        step = ScriptStep(action="tapOn", strategy=ElementStrategy.POINT, x=x, y=y)
        self.steps.append(step)

    def add_tap(self, x: int, y: int, strategy: ElementStrategy = ElementStrategy.POINT,
                element_id: Optional[str] = None, element_text: Optional[str] = None,
                element_image: Optional[str] = None):
        """Add a tapOn step with explicit strategy.

        Args:
            x: X coordinate (for POINT strategy or fallback)
            y: Y coordinate (for POINT strategy or fallback)
            strategy: Element location strategy
            element_id: Resource ID (for ID strategy)
            element_text: Text to match (for TEXT strategy)
            element_image: Image data (for IMAGE strategy)
        """
        step = ScriptStep(
            action="tapOn",
            strategy=strategy,
            x=x,
            y=y,
            element_id=element_id,
            element_text=element_text,
            element_image=element_image,
        )
        self.steps.append(step)

    def add_input_text(self, text: str):
        """Add an inputText step."""
        step = ScriptStep(action="inputText", text=text)
        self.steps.append(step)

    def add_swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 500):
        """Add a swipe step with coordinates."""
        step = ScriptStep(
            action="swipe",
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            duration=duration,
        )
        self.steps.append(step)

    def add_back(self):
        """Add a pressKey BACK step."""
        step = ScriptStep(action="pressKey", key="BACK")
        self.steps.append(step)

    def add_home(self):
        """Add a pressKey HOME step."""
        step = ScriptStep(action="pressKey", key="HOME")
        self.steps.append(step)

    def add_wait(self, seconds: int = 1):
        """Add a waitForAnimationToEnd step."""
        step = ScriptStep(action="waitForAnimationToEnd")
        self.steps.append(step)

    def add_stop_app(self, app_id: Optional[str] = None):
        """Add a stopApp step."""
        step = ScriptStep(action="stopApp", app_id=app_id or self.app_id)
        self.steps.append(step)

    def add_screenshot(self):
        """Add a takeScreenshot step."""
        step = ScriptStep(action="takeScreenshot")
        self.steps.append(step)

    def add_note(self, message: str):
        """Add an extendedWaitFor element to wait for specific content."""
        step = ScriptStep(action="extendedWaitFor", message=message)
        self.steps.append(step)

    def _format_element_locator(self, step: ScriptStep) -> str:
        """Format element locator based on strategy.

        Args:
            step: ScriptStep with element information

        Returns:
            Formatted locator string for Maestro YAML
        """
        if step.strategy == ElementStrategy.ID and step.element_id:
            return f"id:{step.element_id}"
        elif step.strategy == ElementStrategy.TEXT and step.element_text:
            return f"text:{step.element_text}"
        elif step.strategy == ElementStrategy.IMAGE and step.element_image:
            return f"image:{step.element_image}"
        elif step.strategy == ElementStrategy.POINT and step.x is not None and step.y is not None:
            return f"point:{step.x},{step.y}"
        elif step.x is not None and step.y is not None:
            # Fallback to point
            return f"point:{step.x},{step.y}"
        else:
            return "unknown"

    def render(self, app_id: Optional[str] = None) -> str:
        """Render the accumulated steps as Maestro YAML.

        Args:
            app_id: Optional app ID override

        Returns:
            Maestro YAML script string
        """
        target_app = app_id or self.app_id
        if not target_app:
            target_app = "com.example.app"

        lines = [
            f"appId: {target_app}",
            "---",
        ]

        if self.flow_name:
            lines.append(f"# Flow: {self.flow_name}")
            lines.append(f"# Generated by Open-AutoGLM Agent")
            lines.append("")

        for i, step in enumerate(self.steps, 1):
            action = step.action

            if action == "launchApp":
                lines.append(f"- launchApp:")
                lines.append(f"    appId: {step.app_id or target_app}")

            elif action == "tapOn":
                lines.append(f"- tapOn:")
                locator = self._format_element_locator(step)
                if step.strategy == ElementStrategy.ID:
                    lines.append(f"    id: {step.element_id}")
                elif step.strategy == ElementStrategy.TEXT:
                    lines.append(f"    text: {step.element_text}")
                elif step.strategy == ElementStrategy.IMAGE:
                    lines.append(f"    image: {step.element_image}")
                elif step.strategy == ElementStrategy.POINT:
                    lines.append(f"    point: {step.x},{step.y}")
                else:
                    lines.append(f"    point: {step.x},{step.y}")

            elif action == "inputText":
                lines.append(f"- inputText:")
                lines.append(f"    text: {step.text or ''}")

            elif action == "swipe":
                lines.append(f"- swipe:")
                lines.append(f"    startX: {step.start_x or 0}")
                lines.append(f"    startY: {step.start_y or 0}")
                lines.append(f"    endX: {step.end_x or 0}")
                lines.append(f"    endY: {step.end_y or 0}")
                lines.append(f"    duration: {step.duration or 500}")

            elif action == "pressKey":
                lines.append(f"- pressKey:")
                lines.append(f"    key: {step.key or 'BACK'}")

            elif action == "waitForAnimationToEnd":
                lines.append("- waitForAnimationToEnd")

            elif action == "stopApp":
                lines.append(f"- stopApp:")
                lines.append(f"    appId: {step.app_id or target_app}")

            elif action == "takeScreenshot":
                lines.append("- takeScreenshot")

            elif action == "extendedWaitFor":
                # Wait for specific content/element
                lines.append("- extendedWaitFor:")
                lines.append(f"    visibility: {step.message or 'true'}")

            else:
                lines.append(f"# Step {i}: Unknown action {action}")

        return "\n".join(lines)

    def render_compact(self, app_id: Optional[str] = None) -> str:
        """Render in compact format with single-line actions where possible.

        Args:
            app_id: Optional app ID override

        Returns:
            Compact Maestro YAML string
        """
        target_app = app_id or self.app_id
        if not target_app:
            target_app = "com.example.app"

        lines = [f"appId: {target_app}", "---"]

        if self.flow_name:
            lines.append(f"# {self.flow_name}")

        for step in self.steps:
            action = step.action

            if action == "launchApp":
                lines.append(f'- launchApp: {{appId: {step.app_id or target_app}}}')
            elif action == "tapOn":
                locator = self._format_element_locator(step)
                if step.strategy == ElementStrategy.ID:
                    lines.append(f'- tapOn: {{id: {step.element_id}}}')
                elif step.strategy == ElementStrategy.TEXT:
                    lines.append(f'- tapOn: {{text: "{step.element_text}"}}')
                elif step.strategy == ElementStrategy.POINT:
                    lines.append(f'- tapOn: {{point: {step.x},{step.y}}}')
                else:
                    lines.append(f'- tapOn: {{point: {step.x or 0},{step.y or 0}}}')
            elif action == "inputText":
                lines.append(f'- inputText: {{text: "{step.text or ""}"}}')
            elif action == "swipe":
                lines.append(f'- swipe: {{startX: {step.start_x}, startY: {step.start_y}, endX: {step.end_x}, endY: {step.end_y}, duration: {step.duration or 500}}}')
            elif action == "pressKey":
                lines.append(f'- pressKey: {{key: {step.key or "BACK"}}}')
            elif action == "waitForAnimationToEnd":
                lines.append("- waitForAnimationToEnd")
            elif action == "stopApp":
                lines.append(f'- stopApp: {{appId: {step.app_id or target_app}}}')
            elif action == "takeScreenshot":
                lines.append("- takeScreenshot")

        return "\n".join(lines)

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the generated script.

        Returns:
            Dictionary with script statistics
        """
        stats = {
            "total_steps": len(self.steps),
            "by_action": {},
            "by_strategy": {},
        }

        for step in self.steps:
            # Count by action
            action = step.action
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

            # Count by strategy
            if step.strategy:
                strategy_name = step.strategy.value
                stats["by_strategy"][strategy_name] = stats["by_strategy"].get(strategy_name, 0) + 1

        return stats
