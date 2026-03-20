"""LLM Factory for creating and managing providers."""
from typing import Optional, Any

from app.llm.base import BaseLLMProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.minimax import MiniMaxProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMFactory:
    """Factory for creating LLM providers."""

    _providers: dict[str, type[BaseLLMProvider]] = {
        "mock": MockProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "minimax": MiniMaxProvider,
    }

    _instances: dict[str, BaseLLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[BaseLLMProvider]) -> None:
        """Register a new provider type.

        Args:
            name: Provider name (e.g., 'openai')
            provider_class: Provider class inheriting from BaseLLMProvider
        """
        cls._providers[name] = provider_class
        logger.info(f"Registered LLM provider: {name}")

    @classmethod
    def create(cls, provider_name: str, config: dict[str, Any]) -> BaseLLMProvider:
        """Create an LLM provider instance.

        Args:
            provider_name: Name of the provider to create
            config: Provider configuration dict

        Returns:
            Provider instance

        Raises:
            ValueError: If provider is not registered
        """
        if provider_name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available: {available}"
            )

        # Return cached instance if exists
        if provider_name in cls._instances:
            return cls._instances[provider_name]

        provider_class = cls._providers[provider_name]
        instance = provider_class(config)
        cls._instances[provider_name] = instance
        logger.info(f"Created LLM provider: {provider_name}")
        return instance

    @classmethod
    def get_default(cls, llm_config: dict[str, Any]) -> BaseLLMProvider:
        """Get the default provider from config.

        Args:
            llm_config: Full LLM configuration dict

        Returns:
            Default provider instance
        """
        default_name = llm_config.get("default_provider", "mock")
        providers = llm_config.get("providers", {})
        provider_config = providers.get(default_name, {})

        return cls.create(default_name, provider_config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances."""
        cls._instances.clear()
