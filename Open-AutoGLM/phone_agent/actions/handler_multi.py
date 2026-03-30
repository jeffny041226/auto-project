"""Multi-strategy Action Handler - Extended handler with id/text/image/point element support.

This module extends the base ActionHandler to support multiple element location strategies:
- id: Resource ID based (most stable, preferred)
- text: Text matching (good for buttons with text)
- image: Image template matching (good for icons)
- point: Direct coordinates (fallback when other methods fail)

The handler automatically determines the best execution method based on the element format.
"""

import ast
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple

from phone_agent.actions.element import ElementInfo
from phone_agent.config.timing import TIMING_CONFIG
from phone_agent.device_factory import get_device_factory


# Element locator pattern: "id:xxx", "text:xxx", "image:xxx", "point:x,y"
ELEMENT_PATTERN = re.compile(r'^(id|text|image|point):(.+)$')


@dataclass
class ElementLocator:
    """Parsed element locator."""

    strategy: str  # "id", "text", "image", "point"
    value: str     # The actual locator value

    @classmethod
    def parse(cls, element: Any) -> Optional["ElementLocator"]:
        """Parse element string into locator.

        Args:
            element: Element string like "id:xxx", "text:xxx", or a list [x, y]

        Returns:
            ElementLocator or None if parsing fails
        """
        if element is None:
            return None

        if isinstance(element, list) and len(element) == 2:
            # Relative coordinates [x, y] -> point strategy
            return cls(strategy="point", value=f"{element[0]},{element[1]}")

        if isinstance(element, str):
            match = ELEMENT_PATTERN.match(element)
            if match:
                return cls(strategy=match.group(1), value=match.group(2))

        # Try to parse as direct coordinates
        if isinstance(element, str):
            try:
                parts = element.split(",")
                if len(parts) == 2:
                    x, y = int(parts[0]), int(parts[1])
                    return cls(strategy="point", value=f"{x},{y}")
            except ValueError:
                pass

        return None


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False
    # For Maestro script generation
    element_locator: Optional[ElementLocator] = None
    # Complete element information
    element_info: Optional[ElementInfo] = None


class MultiStrategyActionHandler:
    """Extended ActionHandler with multi-strategy element support.

    Supports:
    - id:com.tencent.mm:id/btn -> Use UI automator ID lookup
    - text:登录 -> Use text matching
    - image:base64... -> Use image template matching
    - point:500,500 -> Direct coordinate tap (fallback)
    - [x, y] -> Relative coordinates (0-999) converted to absolute
    """

    def __init__(
        self,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.device_id = device_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover
        # Track last tapped element info for use in subsequent type actions
        self._last_tapped_element_info: Optional[ElementInfo] = None

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int
    ) -> ActionResult:
        """Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.

        Returns:
            ActionResult indicating success and whether to finish.
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(
                success=True, should_finish=True, message=action.get("message")
            )

        if action_type != "do":
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(
                success=False, should_finish=False, message=f"Action failed: {e}"
            )

    def _get_handler(self, action_name: str) -> Callable | None:
        """Get the handler method for an action."""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
        }
        return handlers.get(action_name)

    def _convert_relative_to_absolute(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> Tuple[int, int]:
        """Convert relative coordinates (0-1000) to absolute pixels."""
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _parse_element(self, element: Any) -> Optional[ElementLocator]:
        """Parse element into locator."""
        return ElementLocator.parse(element)

    def _execute_by_locator(
        self,
        locator: ElementLocator,
        screen_width: int,
        screen_height: int,
        require_confirmation: bool = False,
    ) -> ActionResult:
        """Execute tap based on element locator strategy.

        Args:
            locator: Parsed element locator
            screen_width: Screen width
            screen_height: Screen height
            require_confirmation: Whether to require user confirmation

        Returns:
            ActionResult
        """
        result: ActionResult
        if locator.strategy == "id":
            # ID-based tap
            result = self._tap_by_id(locator.value, require_confirmation)
        elif locator.strategy == "text":
            # Text-based tap
            result = self._tap_by_text(locator.value, require_confirmation)
        elif locator.strategy == "image":
            # Image-based tap (would require template matching)
            result = self._tap_by_image_fallback(locator.value, screen_width, screen_height)
        elif locator.strategy == "point":
            # Direct coordinate tap
            result = self._tap_by_point(locator.value, require_confirmation)
        else:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown locator strategy: {locator.strategy}",
            )

        # Track last tapped element for type actions
        if result.success and result.element_info:
            self._last_tapped_element_info = result.element_info

        return result

    def _tap_by_id(self, resource_id: str, require_confirmation: bool = False) -> ActionResult:
        """Tap by resource ID using UI automator.

        Args:
            resource_id: Resource ID like "com.tencent.mm:id/btn"
            require_confirmation: Whether to show confirmation dialog

        Returns:
            ActionResult with element_info
        """
        if require_confirmation and not self.confirmation_callback(f"Tap on {resource_id}"):
            return ActionResult(
                success=False,
                should_finish=True,
                message="User cancelled sensitive operation",
            )

        try:
            device_factory = get_device_factory()
            # Find element with full info
            element_info = self._find_element_info_by_id(resource_id)
            if element_info and element_info.center_coords:
                x, y = element_info.center_coords
                device_factory.tap(x, y, self.device_id)
                return ActionResult(
                    success=True,
                    should_finish=False,
                    element_locator=ElementLocator(strategy="id", value=resource_id),
                    element_info=element_info,
                )
            else:
                return ActionResult(
                    success=False,
                    should_finish=False,
                    message=f"Element not found: {resource_id}",
                )
        except Exception as e:
            return ActionResult(success=False, should_finish=False, message=str(e))

    def _tap_by_text(self, text: str, require_confirmation: bool = False) -> ActionResult:
        """Tap by text using UI automator.

        Args:
            text: Text to match
            require_confirmation: Whether to show confirmation dialog

        Returns:
            ActionResult with element_info
        """
        if require_confirmation and not self.confirmation_callback(f"Tap on text '{text}'"):
            return ActionResult(
                success=False,
                should_finish=True,
                message="User cancelled sensitive operation",
            )

        try:
            device_factory = get_device_factory()
            element_info = self._find_element_info_by_text(text)
            if element_info and element_info.center_coords:
                x, y = element_info.center_coords
                device_factory.tap(x, y, self.device_id)
                return ActionResult(
                    success=True,
                    should_finish=False,
                    element_locator=ElementLocator(strategy="text", value=text),
                    element_info=element_info,
                )
            else:
                return ActionResult(
                    success=False,
                    should_finish=False,
                    message=f"Element not found: {text}",
                )
        except Exception as e:
            return ActionResult(success=False, should_finish=False, message=str(e))

    def _tap_by_image_fallback(
        self, image_data: str, screen_width: int, screen_height: int
    ) -> ActionResult:
        """Fallback tap when image matching is not available.

        For now, we fall back to center of screen as a simple approximation.
        In production, this would use template matching.

        Args:
            image_data: Image data (base64 or file path)
            screen_width: Screen width
            screen_height: Screen height

        Returns:
            ActionResult
        """
        # Fallback: tap center of screen
        center_x = screen_width // 2
        center_y = screen_height // 2
        device_factory = get_device_factory()
        device_factory.tap(center_x, center_y, self.device_id)
        return ActionResult(
            success=True,
            should_finish=False,
            message="Image matching not implemented, tapped center",
        )

    def _tap_by_point(
        self, coords: str, require_confirmation: bool = False
    ) -> ActionResult:
        """Tap by direct coordinates.

        Args:
            coords: Coordinate string "x,y"
            require_confirmation: Whether to show confirmation dialog

        Returns:
            ActionResult with element_info
        """
        try:
            parts = coords.split(",")
            x, y = int(parts[0]), int(parts[1])

            if require_confirmation and not self.confirmation_callback(f"Tap at ({x}, {y})"):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

            device_factory = get_device_factory()
            device_factory.tap(x, y, self.device_id)

            # Find the actual UI element at this point for better element_info
            element_info = self._find_element_at_point(x, y)
            if not element_info:
                element_info = ElementInfo(
                    bounds=[x - 10, y - 10, x + 10, y + 10],  # Approximate bounds
                    center_coords=[x, y],
                )

            return ActionResult(
                success=True,
                should_finish=False,
                element_locator=ElementLocator(strategy="point", value=coords),
                element_info=element_info,
            )
        except Exception as e:
            return ActionResult(success=False, should_finish=False, message=str(e))

    def _find_element_at_point(self, x: int, y: int) -> Optional[ElementInfo]:
        """Find UI element at a specific point coordinate.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            ElementInfo of the element at the point, or None if not found
        """
        try:
            device_factory = get_device_factory()

            output = device_factory._run_command(
                f'uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml',
                self.device_id,
                capture_output=True,
            )

            import re
            # Find all node elements with bounds
            # Pattern: <node ... bounds="[x1,y1][x2,y2]" ... />
            node_pattern = r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>'
            matches = list(re.finditer(node_pattern, output))

            for match in matches:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                # Check if point (x, y) is within bounds
                if x1 <= x <= x2 and y1 <= y <= y2:
                    # Found element at this point - get full node context
                    element_start = match.start()
                    while element_start > 0 and output[element_start] != '<':
                        element_start -= 1
                    element_end = match.end()
                    while element_end < len(output) and output[element_end] != '>':
                        element_end += 1
                    element_end += 1
                    element_context = output[element_start:element_end]

                    # Extract attributes
                    id_match = re.search(r'resource-id="([^"]*)"', element_context)
                    resource_id = id_match.group(1) if id_match else None

                    text_match = re.search(r'text="([^"]*)"', element_context)
                    text = text_match.group(1) if text_match else None

                    desc_match = re.search(r'content-desc="([^"]*)"', element_context)
                    content_desc = desc_match.group(1) if desc_match else None

                    clickable_match = re.search(r'clickable="([^"]*)"', element_context)
                    clickable = clickable_match.group(1).lower() == "true" if clickable_match else False

                    enabled_match = re.search(r'enabled="([^"]*)"', element_context)
                    enabled = enabled_match.group(1).lower() != "false" if enabled_match else True

                    bounds = [x1, y1, x2, y2]
                    center_coords = [(x1 + x2) // 2, (y1 + y2) // 2]

                    return ElementInfo(
                        text=text,
                        resource_id=resource_id,
                        bounds=bounds,
                        center_coords=center_coords,
                        content_desc=content_desc,
                        clickable=clickable,
                        enabled=enabled,
                    )

            return None
        except Exception as e:
            return None

    def _find_element_info_by_id(self, resource_id: str) -> Optional[ElementInfo]:
        """Find element info using UI automator by resource ID.

        Args:
            resource_id: Resource ID

        Returns:
            ElementInfo with full details or None if not found
        """
        try:
            device_factory = get_device_factory()

            output = device_factory._run_command(
                f'uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml',
                self.device_id,
                capture_output=True,
            )

            import re
            # Match element with resource-id
            pattern = rf'resource-id="{re.escape(resource_id)}"'
            match = re.search(pattern, output)
            if not match:
                return None

            # Find the full node element by finding <node before and > after
            # Go back to find '<'
            element_start = match.start()
            while element_start > 0 and output[element_start] != '<':
                element_start -= 1

            # Go forward to find '>' (end of element)
            element_end = match.end()
            while element_end < len(output) and output[element_end] != '>':
                element_end += 1
            element_end += 1  # Include the '>'

            # Get the full element context
            element_context = output[element_start:element_end]

            # Extract bounds
            bounds_pattern = r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            bounds_match = re.search(bounds_pattern, element_context)
            bounds = None
            center_coords = None
            if bounds_match:
                x1, y1, x2, y2 = int(bounds_match.group(1)), int(bounds_match.group(2)), int(bounds_match.group(3)), int(bounds_match.group(4))
                bounds = [x1, y1, x2, y2]
                center_coords = [(x1 + x2) // 2, (y1 + y2) // 2]

            # Extract text
            text_pattern = r'text="([^"]*)"'
            text_match = re.search(text_pattern, element_context)
            text = text_match.group(1) if text_match else None

            # Extract content-desc
            desc_pattern = r'content-desc="([^"]*)"'
            desc_match = re.search(desc_pattern, element_context)
            content_desc = desc_match.group(1) if desc_match else None

            # Extract clickable
            clickable_pattern = r'clickable="([^"]*)"'
            clickable_match = re.search(clickable_pattern, element_context)
            clickable = clickable_match.group(1).lower() == "true" if clickable_match else False

            # Extract enabled
            enabled_pattern = r'enabled="([^"]*)"'
            enabled_match = re.search(enabled_pattern, element_context)
            enabled = enabled_match.group(1).lower() != "false" if enabled_match else True

            return ElementInfo(
                text=text,
                resource_id=resource_id,
                bounds=bounds,
                center_coords=center_coords,
                content_desc=content_desc,
                clickable=clickable,
                enabled=enabled,
            )
        except Exception as e:
            return None

    def _find_element_info_by_text(self, text: str) -> Optional[ElementInfo]:
        """Find element info using UI automator by text.

        Args:
            text: Text to match

        Returns:
            ElementInfo with full details or None if not found
        """
        try:
            device_factory = get_device_factory()

            output = device_factory._run_command(
                f'uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml',
                self.device_id,
                capture_output=True,
            )

            import re
            # Find element containing this text
            # Match text="..." with bounds
            pattern = rf'text="([^"]*{re.escape(text)}[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\)"'
            match = re.search(pattern, output)
            if not match:
                # Try reverse order (bounds before text)
                pattern2 = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="([^"]*{re.escape(text)}[^"]*)"'
                match = re.search(pattern2, output)

            if not match:
                return None

            # Extract groups based on which pattern matched
            if len(match.groups()) == 5:
                matched_text = match.group(1)
                x1, y1, x2, y2 = int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))
            else:
                return None

            bounds = [x1, y1, x2, y2]
            center_coords = [(x1 + x2) // 2, (y1 + y2) // 2]

            # Get more context to extract other attributes
            # Find the full node element by finding < before and > after
            # Go back to find '<'
            element_start = match.start()
            while element_start > 0 and output[element_start] != '<':
                element_start -= 1

            # Go forward to find '>' (end of element)
            element_end = match.end()
            while element_end < len(output) and output[element_end] != '>':
                element_end += 1
            element_end += 1  # Include the '>'

            # Get the full element context
            element_context = output[element_start:element_end]

            # Extract resource-id
            id_pattern = r'resource-id="([^"]*)"'
            id_match = re.search(id_pattern, element_context)
            resource_id = id_match.group(1) if id_match else None

            # Extract content-desc
            desc_pattern = r'content-desc="([^"]*)"'
            desc_match = re.search(desc_pattern, element_context)
            content_desc = desc_match.group(1) if desc_match else None

            # Extract clickable
            clickable_pattern = r'clickable="([^"]*)"'
            clickable_match = re.search(clickable_pattern, element_context)
            clickable = clickable_match.group(1).lower() == "true" if clickable_match else False

            # Extract enabled
            enabled_pattern = r'enabled="([^"]*)"'
            enabled_match = re.search(enabled_pattern, element_context)
            enabled = enabled_match.group(1).lower() != "false" if enabled_match else True

            return ElementInfo(
                text=matched_text,
                resource_id=resource_id,
                bounds=bounds,
                center_coords=center_coords,
                content_desc=content_desc,
                clickable=clickable,
                enabled=enabled,
            )
        except Exception as e:
            return None

    def _find_focused_element_info(self) -> Optional[ElementInfo]:
        """Find the currently focused input element.

        Returns:
            ElementInfo for the focused input field or None if not found
        """
        try:
            device_factory = get_device_factory()

            output = device_factory._run_command(
                f'uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml',
                self.device_id,
                capture_output=True,
            )

            import re

            # Find focused element - typically EditText with focused="true"
            # Pattern: focused="true" ... class="android.widget.EditText" ... bounds="[...]"
            # Or: class="android.widget.EditText" ... focused="true" ... bounds="[...]"
            focused_pattern = r'focused="true"[^>]*class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            match = re.search(focused_pattern, output)

            if not match:
                # Try alternative pattern order
                focused_pattern2 = r'class="android\.widget\.EditText"[^>]*focused="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                match = re.search(focused_pattern2, output)

            if not match:
                # Fallback: find ANY EditText with bounds (even without focused="true")
                # This handles cases where the focus attribute is not set
                edittext_pattern = r'class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                match = re.search(edittext_pattern, output)

            if match:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                bounds = [x1, y1, x2, y2]
                center_coords = [(x1 + x2) // 2, (y1 + y2) // 2]

                # Try to extract resource-id and text from the same element
                # Find the full node element by finding < before and > after
                # Go back to find '<'
                element_start = match.start()
                while element_start > 0 and output[element_start] != '<':
                    element_start -= 1

                # Go forward to find '>' (end of element)
                element_end = match.end()
                while element_end < len(output) and output[element_end] != '>':
                    element_end += 1
                element_end += 1  # Include the '>'

                # Get the full element context
                element_context = output[element_start:element_end]

                # Extract resource-id
                id_pattern = r'resource-id="([^"]*)"'
                id_match = re.search(id_pattern, element_context)
                resource_id = id_match.group(1) if id_match else None

                # Extract text
                text_pattern = r'text="([^"]*)"'
                text_match = re.search(text_pattern, element_context)
                text = text_match.group(1) if text_match else None

                # Extract content-desc
                desc_pattern = r'content-desc="([^"]*)"'
                desc_match = re.search(desc_pattern, element_context)
                content_desc = desc_match.group(1) if desc_match else None

                return ElementInfo(
                    text=text,
                    resource_id=resource_id,
                    bounds=bounds,
                    center_coords=center_coords,
                    content_desc=content_desc,
                    clickable=True,
                    enabled=True,
                )

            return None
        except Exception as e:
            return None

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle app launch action."""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")

        device_factory = get_device_factory()
        package_name = device_factory.launch_app(app_name, self.device_id)
        if package_name:
            # Create element_info for launch action with the actual package name
            element_info = ElementInfo(
                text=app_name,
                resource_id=package_name,  # Store actual package name in resource_id
                bounds=None,
                center_coords=None,
            )
            return ActionResult(True, False, element_info=element_info)
        return ActionResult(False, False, f"App not found: {app_name}")

    def _handle_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle tap action with multi-strategy support."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element specified")

        # Check for sensitive operation
        require_confirmation = "message" in action

        # Try to parse as structured locator first
        locator = self._parse_element(element)

        if locator:
            return self._execute_by_locator(locator, width, height, require_confirmation)

        # Fallback: try as relative coordinates [x, y]
        if isinstance(element, list) and len(element) == 2:
            abs_x, abs_y = self._convert_relative_to_absolute(element, width, height)

            if require_confirmation and not self.confirmation_callback(f"Tap at ({abs_x}, {abs_y})"):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

            device_factory = get_device_factory()
            device_factory.tap(abs_x, abs_y, self.device_id)

            # Create element_info for relative coordinate tap
            element_info = ElementInfo(
                bounds=[abs_x - 10, abs_y - 10, abs_x + 10, abs_y + 10],
                center_coords=[abs_x, abs_y],
            )
            # Track last tapped element for type actions
            self._last_tapped_element_info = element_info

            return ActionResult(
                success=True,
                should_finish=False,
                element_locator=ElementLocator(strategy="point", value=f"{abs_x},{abs_y}"),
                element_info=element_info,
            )

        return ActionResult(False, False, f"Cannot parse element: {element}")

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")

        device_factory = get_device_factory()

        # Find the focused input element before typing
        # First try to find currently focused element
        element_info = self._find_focused_element_info()

        # Fallback to last tapped element if no focused element found
        if not element_info and self._last_tapped_element_info:
            element_info = self._last_tapped_element_info

        # Switch to ADB keyboard
        original_ime = device_factory.detect_and_set_adb_keyboard(self.device_id)
        time.sleep(TIMING_CONFIG.action.keyboard_switch_delay)

        # Clear existing text and type new text
        device_factory.clear_text(self.device_id)
        time.sleep(TIMING_CONFIG.action.text_clear_delay)

        # Handle multiline text by splitting on newlines
        device_factory.type_text(text, self.device_id)
        time.sleep(TIMING_CONFIG.action.text_input_delay)

        # Restore original keyboard
        device_factory.restore_keyboard(original_ime, self.device_id)
        time.sleep(TIMING_CONFIG.action.keyboard_restore_delay)

        # Create element_info with input text info
        if element_info:
            # Enhance with the typed text
            input_element_info = ElementInfo(
                text=element_info.text or text,  # Use input hint text or typed text
                resource_id=element_info.resource_id,
                bounds=element_info.bounds,
                center_coords=element_info.center_coords,
                content_desc=element_info.content_desc,
                clickable=element_info.clickable,
                enabled=element_info.enabled,
            )
        else:
            # Fallback - no focused element found
            input_element_info = ElementInfo(
                text=f"input:{text}",  # Mark as text input
            )

        return ActionResult(True, False, element_info=input_element_info)

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle swipe action."""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_x, start_y = self._convert_relative_to_absolute(start, width, height)
        end_x, end_y = self._convert_relative_to_absolute(end, width, height)

        device_factory = get_device_factory()
        device_factory.swipe(start_x, start_y, end_x, end_y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle back button action."""
        device_factory = get_device_factory()
        device_factory.back(self.device_id)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle home button action."""
        device_factory = get_device_factory()
        device_factory.home(self.device_id)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle double tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        locator = self._parse_element(element)

        if locator and locator.strategy == "point":
            parts = locator.value.split(",")
            x, y = int(parts[0]), int(parts[1])
        elif isinstance(element, list) and len(element) == 2:
            x, y = self._convert_relative_to_absolute(element, width, height)
        else:
            return ActionResult(False, False, "Invalid element for double tap")

        device_factory = get_device_factory()
        device_factory.double_tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        locator = self._parse_element(element)

        if locator and locator.strategy == "point":
            parts = locator.value.split(",")
            x, y = int(parts[0]), int(parts[1])
        elif isinstance(element, list) and len(element) == 2:
            x, y = self._convert_relative_to_absolute(element, width, height)
        else:
            return ActionResult(False, False, "Invalid element for long press")

        device_factory = get_device_factory()
        device_factory.long_press(x, y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle wait action."""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle takeover request (login, captcha, etc.)."""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle note action."""
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action."""
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request."""
        return ActionResult(True, False, message="User interaction required")

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback."""
        input(f"{message}\nPress Enter after completing manual operation...")


def parse_action_multi(response: str) -> dict[str, Any]:
    """Parse action from model response with multi-strategy element support.

    Extended to support:
    - do(action="Tap", element="id:com.tencent.mm:id/btn")
    - do(action="Tap", element="text:登录")
    - do(action="Tap", element="image:...")
    - do(action="Tap", element="point:500,500")
    - do(action="Tap", element=[x,y])  # Relative coordinates (legacy)
    """
    print(f"Parsing action: {response}")
    try:
        response = response.strip()

        # Handle Type action
        if response.startswith('do(action="Type"') or response.startswith(
            'do(action="Type_Name"'
        ):
            text = response.split("text=", 1)[1][1:-2]
            action = {"_metadata": "do", "action": "Type", "text": text}
            return action

        # Handle do() actions
        elif response.startswith("do"):
            try:
                response = response.replace('\n', '\\n')
                response = response.replace('\r', '\\r')
                response = response.replace('\t', '\\t')

                tree = ast.parse(response, mode="eval")
                if not isinstance(tree.body, ast.Call):
                    raise ValueError("Expected a function call")

                call = tree.body
                action = {"_metadata": "do"}
                for keyword in call.keywords:
                    key = keyword.arg
                    value = ast.literal_eval(keyword.value)
                    action[key] = value

                return action
            except (SyntaxError, ValueError) as e:
                raise ValueError(f"Failed to parse do() action: {e}")

        # Handle finish
        elif response.startswith("finish"):
            action = {
                "_metadata": "finish",
                "message": response.replace("finish(message=", "")[1:-2],
            }

        else:
            raise ValueError(f"Failed to parse action: {response}")

        return action
    except Exception as e:
        raise ValueError(f"Failed to parse action: {e}")


def do(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'do' actions."""
    kwargs["_metadata"] = "do"
    return kwargs


def finish(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'finish' actions."""
    kwargs["_metadata"] = "finish"
    return kwargs
