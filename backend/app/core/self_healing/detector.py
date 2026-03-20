"""Self-healing detector for classifying errors."""
from enum import Enum
from typing import Optional, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Known error types for self-healing."""

    ELEMENT_NOT_FOUND = "element_not_found"
    PAGE_JUMP = "page_jump"
    POPUP = "popup"
    TIMEOUT = "timeout"
    INPUT_FAIL = "input_fail"
    UNKNOWN = "unknown"


class SelfHealingDetector:
    """Detects and classifies errors for self-healing."""

    # Error patterns mapped to error types
    ERROR_PATTERNS = {
        ErrorType.ELEMENT_NOT_FOUND: [
            "element.*not.*found",
            "unable.*to.*locate",
            "no.*such.*element",
            "cannot.*find",
            "element.*does.*not.*exist",
            "找不到元素",
            "元素不存在",
        ],
        ErrorType.PAGE_JUMP: [
            "page.*jump",
            "unexpected.*page",
            "navigated.*to",
            "redirected",
            "页面跳转",
        ],
        ErrorType.POPUP: [
            "popup",
            "alert",
            "dialog",
            "overlay",
            "modal",
            "弹窗",
        ],
        ErrorType.TIMEOUT: [
            "timeout",
            "timed.*out",
            "took.*too.*long",
            "wait.*exceeded",
            "超时",
        ],
        ErrorType.INPUT_FAIL: [
            "input.*fail",
            "cannot.*input",
            "unable.*to.*type",
            "输入失败",
        ],
    }

    def __init__(self):
        """Initialize detector."""
        self.strategies = {}

    def register_strategy(self, error_type: ErrorType, strategy) -> None:
        """Register a healing strategy for error type.

        Args:
            error_type: Type of error
            strategy: Strategy instance
        """
        self.strategies[error_type] = strategy
        logger.debug(f"Registered strategy for {error_type.value}")

    def classify_error(self, error_message: str) -> ErrorType:
        """Classify error message to error type.

        Args:
            error_message: Error message string

        Returns:
            Classified ErrorType
        """
        error_lower = error_message.lower()

        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                import re
                if re.search(pattern, error_lower, re.IGNORECASE):
                    logger.debug(f"Classified error as {error_type.value}")
                    return error_type

        logger.debug("Error classified as unknown")
        return ErrorType.UNKNOWN

    async def try_fix(
        self,
        step: dict,
        error: str,
        screenshot: bytes = None,
    ) -> Optional[dict]:
        """Try to fix a failed step.

        Args:
            step: Original step that failed
            error: Error message
            screenshot: Screenshot at time of failure

        Returns:
            Fixed step dict or None
        """
        error_type = self.classify_error(error)
        logger.info(f"Trying to fix {error_type.value} error")

        strategy = self.strategies.get(error_type)
        if not strategy:
            logger.warning(f"No strategy registered for {error_type.value}")
            return None

        try:
            fixed_step = await strategy.fix(step, error, screenshot)
            if fixed_step:
                logger.info(f"Successfully fixed step with {strategy.__class__.__name__}")
                return fixed_step
        except Exception as e:
            logger.error(f"Strategy {strategy.__class__.__name__} failed: {e}")

        return None

    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if error is retryable.

        Args:
            error_type: Type of error

        Returns:
            True if should retry
        """
        # Timeout and popup errors are often transient
        retryable = {ErrorType.TIMEOUT, ErrorType.POPUP, ErrorType.UNKNOWN}
        return error_type in retryable
