"""Base LLM provider interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    raw_response: Any
    model: str
    usage: Optional[dict[str, int]] = None
    finish_reason: Optional[str] = None


@dataclass
class EmbeddingResponse:
    """Standardized embedding response."""

    embedding: list[float]
    model: str
    usage: Optional[dict[str, int]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize provider with config."""
        self.config = config
        self.model = config.get("models", {}).get("primary", "unknown")

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional provider-specific arguments

        Returns:
            LLMResponse with content and metadata
        """
        pass

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResponse with vector and metadata
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        pass

    def supports_vision(self) -> bool:
        """Check if provider supports vision/images.

        Returns:
            True if vision is supported
        """
        return False

    async def chat_with_image(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat with image support.

        Default implementation falls back to regular chat.
        Override if provider supports vision.
        """
        return await self.chat(messages, **kwargs)
