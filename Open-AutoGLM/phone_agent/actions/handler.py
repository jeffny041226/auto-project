"""Action handler for processing AI model outputs."""

import ast
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from phone_agent.config.timing import TIMING_CONFIG
from phone_agent.device_factory import get_device_factory


@dataclass
class ElementInfo:
    """UI element information for Maestro script generation."""

    text: Optional[str] = None
    resource_id: Optional[str] = None
    bounds: Optional[list[int]] = None
    center_coords: Optional[list[int]] = None
    content_desc: Optional[str] = None
    clickable: bool = False
    enabled: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "resource_id": self.resource_id,
            "bounds": self.bounds,
            "center_coords": self.center_coords,
            "content_desc": self.content_desc,
            "clickable": self.clickable,
            "enabled": self.enabled,
        }


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False
    element_info: Optional[ElementInfo] = None


class ActionHandler:
    """
    Handles execution of actions from AI model output.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        confirmation_callback: Optional callback for sensitive action confirmation.
            Should return True to proceed, False to cancel.
        takeover_callback: Optional callback for takeover requests (login, captcha).
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

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int, thinking: str = ""
    ) -> ActionResult:
        """
        Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.
            thinking: The LLM's thinking process (used for element identification).

        Returns:
            ActionResult indicating success and whether to finish.
        """
        self._thinking = thinking  # Store for use in handlers
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
    ) -> tuple[int, int]:
        """Convert relative coordinates (0-1000) to absolute pixels."""
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _find_element_at_point(self, x: int, y: int) -> Optional[ElementInfo]:
        """Find UI element at a specific point coordinate.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            ElementInfo of the element at the point, or None if not found
        """
        try:
            # Use subprocess directly with adb shell
            serial = self.device_id or ""
            cmd = f"adb {'-s ' + serial if serial else ''} shell uiautomator dump /sdcard/ui.xml && adb {'-s ' + serial if serial else ''} shell cat /sdcard/ui.xml"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
            output = result.stdout if result.returncode == 0 else ""

            import re
            # Find all node elements with bounds
            node_pattern = r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>'
            matches = list(re.finditer(node_pattern, output))

            # Find the MOST SPECIFIC element (smallest bounds) containing the point
            # This avoids returning parent containers that also contain the point
            best_match = None
            best_area = float('inf')

            for match in matches:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                # Check if point (x, y) is within bounds
                if x1 <= x <= x2 and y1 <= y <= y2:
                    # Calculate area (smaller = more specific)
                    area = (x2 - x1) * (y2 - y1)
                    if area < best_area:
                        best_area = area
                        best_match = match

            if best_match:
                match = best_match
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))

                # Use match boundaries directly (regex consumes the full tag)
                element_context = output[match.start():match.end()]

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

                print(f"[DEBUG] _find_element_at_point({x}, {y}): found element: text={repr(text)}, resource_id={repr(resource_id)}, content_desc={repr(content_desc)}, bounds={bounds}")

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

    def _find_element_by_text_or_desc(self) -> Optional[ElementInfo]:
        """Find a clickable element by text or content-desc.

        When coordinates are wrong, we can still find elements by their text/content-desc.

        Returns:
            ElementInfo of a clickable element with text/content-desc, or None
        """
        try:
            serial = self.device_id or ""
            cmd = f"adb {'-s ' + serial if serial else ''} shell uiautomator dump /sdcard/ui.xml && adb {'-s ' + serial if serial else ''} shell cat /sdcard/ui.xml"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
            output = result.stdout if result.returncode == 0 else ""

            import re

            # Find all node elements with bounds
            node_pattern = r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>'
            matches = list(re.finditer(node_pattern, output))

            for match in matches:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))

                # Get the full node context
                element_start = match.start()
                while element_start > 0 and output[element_start] != '<':
                    element_start -= 1
                element_end = match.end()
                while element_end < len(output) and output[element_end] != '>':
                    element_end += 1
                element_end += 1
                element_context = output[element_start:element_end]

                # Extract attributes
                clickable_match = re.search(r'clickable="([^"]*)"', element_context)
                clickable = clickable_match and clickable_match.group(1).lower() == "true"

                # Skip non-clickable elements
                if not clickable:
                    continue

                text_match = re.search(r'text="([^"]*)"', element_context)
                text = text_match.group(1) if text_match else None

                desc_match = re.search(r'content-desc="([^"]*)"', element_context)
                content_desc = desc_match.group(1) if desc_match else None

                # Skip elements with no text and no content_desc
                if not text and not content_desc:
                    continue

                # Skip system elements
                if text and (text.startswith("android:") or text.startswith("input:")):
                    continue

                bounds = [x1, y1, x2, y2]
                center_coords = [(x1 + x2) // 2, (y1 + y2) // 2]

                return ElementInfo(
                    text=text if text else None,
                    resource_id=None,
                    bounds=bounds,
                    center_coords=center_coords,
                    content_desc=content_desc if content_desc else None,
                    clickable=True,
                    enabled=True,
                )

            return None
        except Exception as e:
            print(f"[DEBUG] _find_element_by_text_or_desc failed: {e}")
            return None

    def _find_element_by_thinking(self, fallback_x: int, fallback_y: int) -> Optional[ElementInfo]:
        """Find element based on LLM thinking text.

        When coordinates are wrong, use the thinking text to find the intended element.

        Args:
            fallback_x: Fallback X coordinate if search fails
            fallback_y: Fallback Y coordinate if search fails

        Returns:
            ElementInfo of the intended element, or None
        """
        thinking = getattr(self, '_thinking', '') or ''
        if not thinking:
            return None

        import re
        # Extract potential target text from thinking
        # Looking for patterns like "点击XX" or "tap on XX"
        patterns = [
            r'点击[到]?[的]?(.+?)(?:图标|按钮|区域|元素)',
            r'tap\s+(?:on\s+)?(.+?)(?:icon|button|area|element)',
        ]

        target_text = None
        for pattern in patterns:
            match = re.search(pattern, thinking)
            if match:
                target_text = match.group(1).strip()
                break

        if not target_text:
            return None

        print(f"[DEBUG] _find_element_by_thinking: target_text={repr(target_text)}")

        # Search XML for element with matching text or content_desc
        try:
            serial = self.device_id or ""
            cmd = f"adb {'-s ' + serial if serial else ''} shell uiautomator dump /sdcard/ui.xml && adb {'-s ' + serial if serial else ''} shell cat /sdcard/ui.xml"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
            output = result.stdout if result.returncode == 0 else ""

            # Find elements with matching text
            node_pattern = r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>'
            matches = list(re.finditer(node_pattern, output))

            for match in matches:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))

                # Use match boundaries directly (regex consumes the full tag)
                element_context = output[match.start():match.end()]

                text_match = re.search(r'text="([^"]*)"', element_context)
                text = text_match.group(1) if text_match else None

                desc_match = re.search(r'content-desc="([^"]*)"', element_context)
                content_desc = desc_match.group(1) if desc_match else None

                id_match = re.search(r'resource-id="([^"]*)"', element_context)
                resource_id = id_match.group(1) if id_match else None

                # Check if this element matches our target
                if text and target_text in text:
                    print(f"[DEBUG] Found matching element: text={repr(text)}, resource_id={repr(resource_id)}")
                    return ElementInfo(
                        text=text,
                        resource_id=resource_id,
                        bounds=[x1, y1, x2, y2],
                        center_coords=[(x1+x2)//2, (y1+y2)//2],
                        content_desc=content_desc,
                        clickable=True,
                        enabled=True,
                    )
                if content_desc and target_text in content_desc:
                    print(f"[DEBUG] Found matching element: content_desc={repr(content_desc)}, resource_id={repr(resource_id)}")
                    return ElementInfo(
                        text=text,
                        resource_id=resource_id,
                        bounds=[x1, y1, x2, y2],
                        center_coords=[(x1+x2)//2, (y1+y2)//2],
                        content_desc=content_desc,
                        clickable=True,
                        enabled=True,
                    )

            return None
        except Exception as e:
            print(f"[DEBUG] _find_element_by_thinking failed: {e}")
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
        """Handle tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)

        # Check for sensitive operation
        if "message" in action:
            if not self.confirmation_callback(action["message"]):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

        # BEFORE TAP: Capture element info at target coordinates
        # This is critical because after tap, UI may change
        element_info = self._find_element_at_point(x, y)

        # If found element has no identifying attributes (text/id/desc),
        # try to find the intended element using thinking as hint
        if element_info and not (element_info.text or element_info.resource_id or element_info.content_desc):
            target_element = self._find_element_by_thinking(x, y)
            if target_element:
                element_info = target_element
                # Update coordinates to the correct ones
                x, y = element_info.center_coords

        # If still no useful element, use coordinate-based bounds
        if not element_info or not (element_info.text or element_info.resource_id or element_info.content_desc):
            element_info = ElementInfo(
                bounds=[x - 10, y - 10, x + 10, y + 10],
                center_coords=[x, y],
            )

        # Capture screenshot BEFORE tap for image-based matching
        screenshot_data = self._capture_screenshot_base64()
        if element_info and screenshot_data:
            element_info.screenshot = screenshot_data

        # Execute the tap
        device_factory = get_device_factory()
        device_factory.tap(x, y, self.device_id)

        return ActionResult(True, False, element_info=element_info)

    def _capture_screenshot_base64(self) -> Optional[str]:
        """Capture screenshot and return as base64 encoded string.

        Returns:
            Base64 encoded PNG screenshot, or None if capture fails
        """
        import base64
        try:
            serial = self.device_id or ""
            adb_prefix = f"adb {'-s ' + serial if serial else ''}".split()
            # Capture screenshot to temp file
            temp_path = "/sdcard/temp_screenshot.png"
            subprocess.run([*adb_prefix, "shell", "screencap", "-p", temp_path], capture_output=True)
            # Read and encode
            result = subprocess.run([*adb_prefix, "shell", "cat", temp_path, "|", "base64"], capture_output=True, text=True)
            # Clean up
            subprocess.run([*adb_prefix, "shell", "rm", temp_path], capture_output=True)
            if result.stdout:
                return result.stdout.strip()
            return None
        except Exception as e:
            print(f"[DEBUG] Screenshot capture failed: {e}")
            return None

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")
        print(f"[DEBUG] _handle_type: about to type text={repr(text)}, length={len(text)}")

        device_factory = get_device_factory()

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

        return ActionResult(True, False)

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

        x, y = self._convert_relative_to_absolute(element, width, height)
        device_factory = get_device_factory()
        device_factory.double_tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
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
        """Handle note action (placeholder for content recording)."""
        # This action is typically used for recording page content
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action (placeholder for summarization)."""
        # This action is typically used for content summarization
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request (user choice needed)."""
        # This action signals that user input is needed
        return ActionResult(True, False, message="User interaction required")

    def _send_keyevent(self, keycode: str) -> None:
        """Send a keyevent to the device."""
        from phone_agent.device_factory import DeviceType, get_device_factory
        from phone_agent.hdc.connection import _run_hdc_command

        device_factory = get_device_factory()

        # Handle HDC devices with HarmonyOS-specific keyEvent command
        if device_factory.device_type == DeviceType.HDC:
            hdc_prefix = ["hdc", "-t", self.device_id] if self.device_id else ["hdc"]
            
            # Map common keycodes to HarmonyOS keyEvent codes
            # KEYCODE_ENTER (66) -> 2054 (HarmonyOS Enter key code)
            if keycode == "KEYCODE_ENTER" or keycode == "66":
                _run_hdc_command(
                    hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                    capture_output=True,
                    text=True,
                )
            else:
                # For other keys, try to use the numeric code directly
                # If keycode is a string like "KEYCODE_ENTER", convert it
                try:
                    # Try to extract numeric code from string or use as-is
                    if keycode.startswith("KEYCODE_"):
                        # For now, only handle ENTER, other keys may need mapping
                        if "ENTER" in keycode:
                            _run_hdc_command(
                                hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                                capture_output=True,
                                text=True,
                            )
                        else:
                            # Fallback to ADB-style command for unsupported keys
                            subprocess.run(
                                hdc_prefix + ["shell", "input", "keyevent", keycode],
                                capture_output=True,
                                text=True,
                            )
                    else:
                        # Assume it's a numeric code
                        _run_hdc_command(
                            hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", str(keycode)],
                            capture_output=True,
                            text=True,
                        )
                except Exception:
                    # Fallback to ADB-style command
                    subprocess.run(
                        hdc_prefix + ["shell", "input", "keyevent", keycode],
                        capture_output=True,
                        text=True,
                    )
        else:
            # ADB devices use standard input keyevent command
            cmd_prefix = ["adb", "-s", self.device_id] if self.device_id else ["adb"]
            subprocess.run(
                cmd_prefix + ["shell", "input", "keyevent", keycode],
                capture_output=True,
                text=True,
            )

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")


def parse_action(response: str) -> dict[str, Any]:
    """
    Parse action from model response.

    Args:
        response: Raw response string from the model.

    Returns:
        Parsed action dictionary.

    Raises:
        ValueError: If the response cannot be parsed.
    """
    print(f"Parsing action: {response}")
    try:
        response = response.strip()
        if response.startswith('do(action="Type"') or response.startswith(
            'do(action="Type_Name"'
        ):
            print(f"[DEBUG] parse_action: Type action response={repr(response)}")
            text = response.split("text=", 1)[1][1:-2]
            print(f"[DEBUG] parse_action: extracted text={repr(text)}")
            action = {"_metadata": "do", "action": "Type", "text": text}
            return action
        elif response.startswith("do"):
            # Use AST parsing instead of eval for safety
            try:
                # Handle newlines in the response - replace actual newlines with spaces
                # so the do() call stays on a single line for ast.parse
                response = response.replace('\r\n', ' ').replace('\r', ' ')
                response = response.replace('\n', ' ')

                # Then escape remaining special characters for ast.parse
                response = response.replace('\t', '\\t')

                tree = ast.parse(response, mode="eval")
                if not isinstance(tree.body, ast.Call):
                    raise ValueError("Expected a function call")

                call = tree.body
                # Extract keyword arguments safely
                action = {"_metadata": "do"}
                for keyword in call.keywords:
                    key = keyword.arg
                    value = ast.literal_eval(keyword.value)
                    action[key] = value

                return action
            except (SyntaxError, ValueError) as e:
                raise ValueError(f"Failed to parse do() action: {e}")

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
