"""Template engine for Maestro YAML generation."""
from typing import Any

from jinja2 import Template

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MaestroTemplate:
    """Jinja2 template engine for generating Maestro YAML."""

    BASE_TEMPLATE = """appId: {{ app_id }}
---
# Flow: {{ flow_name }}
{% for step in steps %}
{% if step.action == 'launchApp' %}
- launchApp:
    appId: {{ step.target }}
{% elif step.action == 'tapOn' %}
{% if step.x is defined and step.y is defined %}
- tapOn:
    point: {{ step.x }},{{ step.y }}
{% else %}
- tapOn:
    {{ step.target }}
{% endif %}
{% elif step.action == 'inputText' %}
- inputText:
    text: {{ step.value }}
{% elif step.action == 'swipe' %}
- swipe:
    startX: {{ step.value.startX | default(0.5) }}
    startY: {{ step.value.startY | default(0.5) }}
    endX: {{ step.value.endX | default(0.5) }}
    endY: {{ step.value.endY | default(0.2) }}
    duration: {{ step.value.duration | default(500) }}
{% elif step.action == 'waitForTime' %}
- waitForAnimationToEnd
{% elif step.action == 'waitForAnimationToEnd' %}
- waitForAnimationToEnd
{% elif step.action == 'takeScreenshot' %}
- takeScreenshot
{% elif step.action == 'scroll' %}
- scroll
{% elif step.action == 'pressKey' %}
- pressKey:
    key: {{ step.value }}
{% elif step.action == 'stopApp' %}
- stopApp:
    appId: {{ step.target }}
{% elif step.action == 'eraseText' %}
- eraseText
{% else %}
# Unknown action: {{ step.action }}
{% endif %}
{% endfor %}
"""

    def __init__(self):
        """Initialize template engine."""
        self.template = Template(self.BASE_TEMPLATE)

    def render(
        self,
        steps: list[dict[str, Any]],
        app_id: str = "com.example.app",
        flow_name: str = "Test Flow",
    ) -> str:
        """Render Maestro YAML from steps.

        Args:
            steps: List of step dicts with action, target, value
            app_id: App package ID
            flow_name: Name of the flow

        Returns:
            Rendered Maestro YAML string
        """
        try:
            yaml_content = self.template.render(
                steps=steps,
                app_id=app_id,
                flow_name=flow_name,
            )
            logger.debug(f"Rendered Maestro YAML: {len(yaml_content)} chars")
            return yaml_content
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            raise

    def render_step(self, step: dict[str, Any]) -> str:
        """Render a single step.

        Args:
            step: Step dict

        Returns:
            Rendered YAML for single step
        """
        action = step.get("action", "")

        if action == "launchApp":
            return f"- launchApp:\n    appId: {step.get('target', '')}"
        elif action == "tapOnElement":
            return f"- tapOn:\n    {step.get('target', 'element')}: {step.get('value', '')}"
        elif action == "tapOnText":
            return f"- tapOnText:\n    text: {step.get('target', '')}"
        elif action == "inputText":
            return f"- inputText:\n    text: {step.get('value', '')}"
        elif action == "swipe":
            value = step.get("value", {})
            return (
                f"- swipe:\n"
                f"    startX: {value.get('startX', 0.5)}\n"
                f"    startY: {value.get('startY', 0.8)}\n"
                f"    endX: {value.get('endX', 0.5)}\n"
                f"    endY: {value.get('endY', 0.2)}\n"
                f"    duration: {value.get('duration', 500)}"
            )
        elif action == "waitForElement":
            return f"- waitForAnimationToEnd"
        elif action == "assertExists":
            return f"- assertExists"
        elif action == "screenshot":
            return f"- screenshot"
        else:
            return f"# {action}"
