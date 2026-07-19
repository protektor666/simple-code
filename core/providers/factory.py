"""
Фабрика провайдеров — создаёт нужный LLM-провайдер по имени.
"""

import httpx

from ..config import Config, get_provider_config, ProviderConfig
from .base import BaseProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider


# Реестр доступных провайдеров
PROVIDERS: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def _fetch_ollama_models(base_url: str) -> list[str]:
    """Получает список моделей из Ollama /v1/models."""
    try:
        url = f"{base_url.rstrip('/')}/v1/models"
        with httpx.Client(timeout=5.0) as resp:
            r = resp.get(url)
            if r.status_code == 200:
                data = r.json()
                return [m["id"] for m in data.get("data", [])]
    except Exception:
        pass
    return []


def _resolve_model(provider_cfg: ProviderConfig, provider_type: str = "") -> str:
    """
    Определяет модель для провайдера.
    Приоритет:
      1. default_model из конфига
      2. Первая модель с сервера (для Ollama/_lmstudio)
      3. Дефолт для известных типов
    """
    if provider_cfg.default_model:
        return provider_cfg.default_model

    # Пробуем получить модель с сервера
    if provider_cfg.base_url:
        models = _fetch_ollama_models(provider_cfg.base_url)
        if models:
            return models[0]

    # Дефолты по типу провайдера
    defaults = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "ollama": "llama3.2",
        "lmstudio": "",
        "llamacpp": "",
        "vllm": "",
    }
    return defaults.get(provider_type, "gpt-4o")


def create_provider(cfg: Config, provider_name: str | None = None) -> BaseProvider:
    """
    Создаёт экземпляр LLM-провайдера по имени.
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

    # Определяем модель (авто-определение для Ollama и т.д.)
    model = _resolve_model(provider_cfg)

    return provider_cls(
        api_key=provider_cfg.api_key,
        base_url=provider_cfg.base_url,
        model=model,
    )


def get_default_model(cfg: Config, provider_name: str | None = None) -> str:
    """Возвращает модель по умолчанию для провайдера."""
    name = provider_name or cfg.provider
    provider_cfg = get_provider_config(cfg, name)

    # Пытаемся определить тип провайдера из managed list
    provider_type = ""
    try:
        from ..provider_manager import ProviderManager
        mgr = ProviderManager(cfg.working_dir)
        managed = mgr.get_provider(name)
        if managed:
            provider_type = managed.provider_type
    except Exception:
        pass

    return _resolve_model(provider_cfg, provider_type)
