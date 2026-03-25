"""Action handling module for Phone Agent."""

from phone_agent.actions.handler import ActionHandler, ActionResult
from phone_agent.actions.handler_multi import (
    MultiStrategyActionHandler,
    ElementLocator,
    parse_action_multi,
)

__all__ = [
    "ActionHandler",
    "ActionResult",
    "MultiStrategyActionHandler",
    "ElementLocator",
    "parse_action_multi",
]
