"""
Фабрика провайдеров — создаёт нужный LLM-провайдер по имени.
"""

from ..config import Config, get_provider_config
from .base import BaseProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider


# Реестр доступных провайдеров
PROVIDERS: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def create_provider(cfg: Config, provider_name: str | None = None) -> BaseProvider:
    """
    Создаёт экземпляр LLM-провайдера по имени.

    Args:
        cfg: Конфигурация приложения.
        provider_name: Имя провайдера (openai, anthropic и т.д.)

    Returns:
        Экземпляр BaseProvider.

    Raises:
        ValueError: Если провайдер не поддерживается или не настроен.
    """
    name = provider_name or cfg.provider
    provider_cfg = get_provider_config(cfg, name)

    # Выбираем класс провайдера
    provider_cls = PROVIDERS.get(name)

    if provider_cls is None:
        # Если нет в реестре — пробуем как OpenAI-совместимый
        if provider_cfg.base_url:
            provider_cls = OpenAIProvider
        else:
            raise ValueError(
                f"Провайдер '{name}' не поддерживается.\n"
                f"Доступные: {', '.join(PROVIDERS.keys())}\n"
                f"Или укажите base_url для OpenAI-совместимого API."
            )

    return provider_cls(
        api_key=provider_cfg.api_key,
        base_url=provider_cfg.base_url,
        model=provider_cfg.default_model,
    )


def get_default_model(cfg: Config, provider_name: str | None = None) -> str:
    """Возвращает модель по умолчанию для провайдера."""
    name = provider_name or cfg.provider
    provider_cfg = get_provider_config(cfg, name)
    if provider_cfg.default_model:
        return provider_cfg.default_model

    # Модели по умолчанию для известных провайдеров
    defaults = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
    }
    return defaults.get(name, "gpt-4o")
