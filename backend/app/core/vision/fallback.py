"""Accessibility tree fallback for when vision is unavailable."""
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class AccessibilityTreeFallback:
    """Fallback using Android/iOS accessibility tree when vision fails."""

    def __init__(self):
        """Initialize accessibility tree fallback."""
        self.enabled = True

    async def get_accessibility_tree(
        self,
        device_id: str,
    ) -> Optional[dict[str, Any]]:
        """Get accessibility tree from device.

        Args:
            device_id: Device ID

        Returns:
            Accessibility tree dict or None
        """
        logger.debug(f"Getting accessibility tree for device {device_id}")

        # In a real implementation, this would use:
        # - Android: adb shell uiautomator dump
        # - iOS: instruments or accessibility inspector

        # For now, return placeholder
        return {
            "root": {
                "type": "Window",
                "bounds": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                "children": [],
            },
            "xml_dump": "",
        }

    def parse_uiautomator_dump(self, xml_content: str) -> dict[str, Any]:
        """Parse Android uiautomator XML dump.

        Args:
            xml_content: XML content from uiautomator

        Returns:
            Parsed accessibility tree
        """
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_content)

            def parse_element(elem) -> dict:
                attrib = elem.attrib.copy()
                children = [parse_element(child) for child in elem]

                result = {
                    "tag": elem.tag,
                    "attributes": attrib,
                    "bounds": attrib.get("bounds", ""),
                    "text": attrib.get("text", ""),
                    "resource_id": attrib.get("resource-id", ""),
                    "content_desc": attrib.get("content-desc", ""),
                    "class": attrib.get("class", ""),
                    "clickable": attrib.get("clickable", "false") == "true",
                    "children": children,
                }
                return result

            return parse_element(root)

        except Exception as e:
            logger.error(f"XML parsing error: {e}")
            return {}

    def find_element_in_tree(
        self,
        tree: dict,
        selector: dict[str, Any],
    ) -> Optional[dict]:
        """Find element in accessibility tree.

        Args:
            tree: Accessibility tree dict
            selector: Selector criteria

        Returns:
            Found element or None
        """
        # Search by various attributes
        search_by = selector.get("by", "text")
        search_value = selector.get("value", "")

        def search(node: dict) -> Optional[dict]:
            # Check if this node matches
            if search_by == "text":
                if search_value.lower() in node.get("text", "").lower():
                    return node
            elif search_by == "resource_id":
                if search_value in node.get("resource_id", ""):
                    return node
            elif search_by == "content_desc":
                if search_value.lower() in node.get("content_desc", "").lower():
                    return node
            elif search_by == "class":
                if search_value in node.get("class", ""):
                    return node

            # Search children
            for child in node.get("children", []):
                result = search(child)
                if result:
                    return result

            return None

        return search(tree)

    def get_clickable_elements(self, tree: dict) -> list[dict]:
        """Get all clickable elements from tree.

        Args:
            tree: Accessibility tree

        Returns:
            List of clickable elements
        """
        elements = []

        def collect(node: dict):
            if node.get("clickable"):
                elements.append(
                    {
                        "text": node.get("text", ""),
                        "bounds": node.get("bounds", ""),
                        "resource_id": node.get("resource_id", ""),
                    }
                )
            for child in node.get("children", []):
                collect(child)

        collect(tree)
        return elements
