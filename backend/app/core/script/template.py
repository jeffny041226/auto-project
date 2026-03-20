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
{% elif step.action == 'tapOnElement' %}
- tapOn:
    {{ step.target }}: {{ step.value or '' }}
{% elif step.action == 'tapOnText' %}
- tapOnText:
    text: {{ step.target }}
{% elif step.action == 'inputText' %}
- inputText:
    {{ step.target }}: {{ step.value }}
{% elif step.action == 'swipe' %}
- swipe:
    startX: {{ step.value.startX | default(0.5) }}
    startY: {{ step.value.startY | default(0.8) }}
    endX: {{ step.value.endX | default(0.5) }}
    endY: {{ step.value.endY | default(0.2) }}
    duration: {{ step.value.duration | default(500) }}
{% elif step.action == 'waitForElement' %}
- waitForElementToAppear:
    {{ step.target }}: {{ step.value }}
    timeout: {{ step.value.timeout | default(5000) }}
{% elif step.action == 'assertExists' %}
- assertExists:
    {{ step.target }}: {{ step.value }}
{% elif step.action == 'assertText' %}
- assertText:
    {{ step.target }}: {{ step.value }}
{% elif step.action == 'screenshot' %}
- screenshot:
    path: {{ step.value | default('screenshots/') }}{{ loop.index }}.png
{% elif step.action == 'scroll' %}
- scroll
{% elif step.action == 'pressKey' %}
- pressKey:
    code: {{ step.value }}
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
            return f"- waitForElementToAppear:\n    timeout: {step.get('value', 5000)}"
        elif action == "assertExists":
            return f"- assertExists"
        elif action == "screenshot":
            return f"- screenshot"
        else:
            return f"# {action}"
