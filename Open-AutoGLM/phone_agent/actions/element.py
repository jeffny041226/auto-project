"""Element information dataclass for UI element data collection."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ElementInfo:
    """Complete UI element information collected during agent execution.

    This dataclass captures all relevant properties of a UI element
    for accurate Maestro script generation.
    """

    text: Optional[str] = None
    resource_id: Optional[str] = None
    bounds: Optional[list[int]] = None  # [x1, y1, x2, y2]
    center_coords: Optional[list[int]] = None  # [x, y]
    content_desc: Optional[str] = None
    clickable: bool = False
    enabled: bool = True
    # For text input fields
    input_type: Optional[str] = None
    # For list items
    index: Optional[int] = None
    # For image-based matching
    screenshot: Optional[str] = None

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
            "input_type": self.input_type,
            "index": self.index,
            "screenshot": self.screenshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ElementInfo":
        """Create from dictionary."""
        if data is None:
            return cls()
        return cls(
            text=data.get("text"),
            resource_id=data.get("resource_id"),
            bounds=data.get("bounds"),
            center_coords=data.get("center_coords"),
            content_desc=data.get("content_desc"),
            clickable=data.get("clickable", False),
            enabled=data.get("enabled", True),
            input_type=data.get("input_type"),
            index=data.get("index"),
            screenshot=data.get("screenshot"),
        )

    def has_id(self) -> bool:
        """Check if element has a valid resource ID."""
        return bool(self.resource_id and self.resource_id.strip())

    def has_text(self) -> bool:
        """Check if element has text content."""
        return bool(self.text and self.text.strip())

    def has_coordinates(self) -> bool:
        """Check if element has valid center coordinates."""
        return bool(
            self.center_coords
            and len(self.center_coords) == 2
            and all(isinstance(c, (int, float)) for c in self.center_coords)
        )
