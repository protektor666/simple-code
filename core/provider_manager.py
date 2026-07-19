"""
Модуль управления LLM-провайдерами.
Позволяет добавлять, удалять, просматривать и тестировать провайдеры.
Хранит провайдеры в файле simplecode.providers.json рядом с конфигом.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx

from .config import Config, ProviderConfig


# Типы провайдеров
PROVIDER_TYPES = {
    "openai": "OpenAI (GPT-4o, GPT-4, etc.)",
    "anthropic": "Anthropic (Claude)",
    "ollama": "Ollama (локальный сервер)",
    "lmstudio": "LM Studio (локальный сервер)",
    "llamacpp": "llama.cpp server (локальный сервер)",
    "vllm": "vLLM (локальный сервер)",
    "custom": "Другой OpenAI-совместимый API",
}


@dataclass
class ManagedProvider:
    """Провайдер, управляемый через интерфейс."""
    name: str
    provider_type: str           # openai, anthropic, ollama, lmstudio, custom и т.д.
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    description: str = ""
    is_local: bool = False       # Локально развёрнутый сервер?
    models: list[str] = field(default_factory=list)  # Список доступных моделей

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ManagedProvider":
        return cls(
            name=data.get("name", ""),
            provider_type=data.get("provider_type", "custom"),
            base_url=data.get("base_url", ""),
            api_key=data.get("api_key", ""),
            default_model=data.get("default_model", ""),
            description=data.get("description", ""),
            is_local=data.get("is_local", False),
            models=data.get("models", []),
        )

    def to_provider_config(self) -> ProviderConfig:
        """Конвертирует в ProviderConfig для совместимости с основной системой."""
        return ProviderConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            default_model=self.default_model,
        )


class ProviderManager:
    """
    Управляет списком LLM-провайдеров.
    Сохраняет/загружает из JSON-файла.
    """

    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.providers_file = Path(working_dir) / ".simplecode" / "providers.json"
        self.providers_file.parent.mkdir(parents=True, exist_ok=True)
        self._providers: dict[str, ManagedProvider] = {}
        self._load()

    def _load(self):
        """Загружает провайдеры из файла."""
        if not self.providers_file.exists():
            return
        try:
            with open(self.providers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, pdata in data.items():
                self._providers[name] = ManagedProvider.from_dict(pdata)
        except Exception:
            pass

    def _save(self):
        """Сохраняет провайдеры в файл."""
        data = {name: p.to_dict() for name, p in self._providers.items()}
        with open(self.providers_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_providers(self) -> dict[str, ManagedProvider]:
        """Возвращает все провайдеры."""
        return dict(self._providers)

    def get_provider(self, name: str) -> ManagedProvider | None:
        """Возвращает провайдер по имени."""
        return self._providers.get(name)

    def add_provider(
        self,
        name: str,
        provider_type: str,
        base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        description: str = "",
    ) -> ManagedProvider:
        """
        Добавляет нового провайдера.

        Args:
            name: Уникальное имя провайдера.
            provider_type: Тип (openai, anthropic, ollama, lmstudio, custom и т.д.)
            base_url: URL API (обязательно для не-встроенных провайдеров).
            api_key: API ключ (не нужен для локальных серверов).
            default_model: Модель по умолчанию.
            description: Описание провайдера.

        Returns:
            Созданный ManagedProvider.
        """
        if name in self._providers:
            raise ValueError(f"Провайдер '{name}' уже существует. Используйте update.")

        is_local = provider_type in ("ollama", "lmstudio", "llamacpp", "vllm")

        # Автозаполнение base_url для локальных серверов
        if is_local and not base_url:
            base_url = _default_local_url(provider_type)

        provider = ManagedProvider(
            name=name,
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            description=description or PROVIDER_TYPES.get(provider_type, ""),
            is_local=is_local,
        )

        self._providers[name] = provider
        self._save()
        return provider

    def update_provider(
        self,
        name: str,
        **kwargs,
    ) -> ManagedProvider:
        """Обновляет настройки провайдера."""
        if name not in self._providers:
            raise ValueError(f"Провайдер '{name}' не найден.")

        provider = self._providers[name]
        for key, value in kwargs.items():
            if value is not None and hasattr(provider, key):
                setattr(provider, key, value)

        provider.is_local = provider.provider_type in ("ollama", "lmstudio", "llamacpp", "vllm")
        self._save()
        return provider

    def remove_provider(self, name: str) -> bool:
        """Удаляет провайдер по имени."""
        if name in self._providers:
            del self._providers[name]
            self._save()
            return True
        return False

    def test_connection(self, name: str) -> dict[str, Any]:
        """
        Проверяет соединение с провайдером.
        Возвращает {"ok": bool, "message": str, "models": list[str]}.
        """
        provider = self._providers.get(name)
        if not provider:
            return {"ok": False, "message": f"Провайдер '{name}' не найден.", "models": []}

        # Для локальных серверов пробуем получить список моделей
        if provider.provider_type in ("ollama", "lmstudio", "llamacpp", "vllm", "custom"):
            return self._test_openai_compatible(provider)

        # Для Anthropic проверяем простым запросом
        if provider.provider_type == "anthropic":
            return self._test_anthropic(provider)

        # Для OpenAI проверяем через /models
        if provider.provider_type == "openai":
            return self._test_openai_compatible(provider)

        return {"ok": False, "message": f"Неизвестный тип: {provider.provider_type}", "models": []}

    def _test_openai_compatible(self, provider: ManagedProvider) -> dict[str, Any]:
        """Тестирует OpenAI-совместимый API."""
        base = provider.base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}

        # Пробуем получить список моделей
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{base}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    return {
                        "ok": True,
                        "message": f"Подключено. Доступно моделей: {len(models)}",
                        "models": models,
                    }
                else:
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
                        "models": [],
                    }
        except httpx.ConnectError:
            return {
                "ok": False,
                "message": f"Не удалось подключиться к {base}. Сервер запущен?",
                "models": [],
            }
        except Exception as e:
            return {"ok": False, "message": f"{type(e).__name__}: {e}", "models": []}

    def _test_anthropic(self, provider: ManagedProvider) -> dict[str, Any]:
        """Тестирует Anthropic API."""
        if not provider.api_key:
            return {"ok": False, "message": "API ключ не указан.", "models": []}

        headers = {
            "x-api-key": provider.api_key,
            "anthropic-version": "2023-06-01",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    "https://api.anthropic.com/v1/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    return {
                        "ok": True,
                        "message": f"Подключено. Доступно моделей: {len(models)}",
                        "models": models,
                    }
                else:
                    return {
                        "ok": False,
                        "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
                        "models": [],
                    }
        except Exception as e:
            return {"ok": False, "message": f"{type(e).__name__}: {e}", "models": []}

    def sync_to_config(self, cfg: Config):
        """
        Синхронизирует управляемых провайдеров с основным конфигом.
        Добавляет/обновляет провайдеры в cfg.providers.
        """
        for name, managed in self._providers.items():
            cfg.providers[name] = managed.to_provider_config()


def _default_local_url(provider_type: str) -> str:
    """Возвращает URL по умолчанию для локальных серверов."""
    defaults = {
        "ollama": "http://localhost:11434/v1",
        "lmstudio": "http://localhost:1234/v1",
        "llamacpp": "http://localhost:8080/v1",
        "vllm": "http://localhost:8000/v1",
    }
    return defaults.get(provider_type, "http://localhost:8080/v1")
