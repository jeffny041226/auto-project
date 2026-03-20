"""Self-healing strategies package."""
from app.core.self_healing.strategies.element_not_found import ElementNotFoundStrategy
from app.core.self_healing.strategies.page_jump import PageJumpStrategy
from app.core.self_healing.strategies.popup import PopupStrategy
from app.core.self_healing.strategies.timeout import TimeoutStrategy
from app.core.self_healing.strategies.input_fail import InputFailStrategy

__all__ = [
    "ElementNotFoundStrategy",
    "PageJumpStrategy",
    "PopupStrategy",
    "TimeoutStrategy",
    "InputFailStrategy",
]
