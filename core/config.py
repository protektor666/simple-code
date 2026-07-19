"""
Модуль конфигурации simple-code.
Загружает настройки из файла simplecode.toml или переменных окружения.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProviderConfig:
    """Настройки одного LLM-провайдера."""
    api_key: str
    base_url: str = ""
    default_model: str = ""

    def __post_init__(self):
        # Подставляем из переменных окружения, если значение пустое
        if not self.api_key:
            self.api_key = ""


@dataclass
class Config:
    """Главный конфигурационный объект."""
    # Текущий провайдер (openai, anthropic, custom)
    provider: str = "openai"
    # Модель по умолчанию
    model: str = ""
    # Максимальное количество шагов агента (tool calls)
    max_agent_steps: int = 30
    # Рабочая директория проекта
    working_dir: str = ""
    # Директория для сессий
    sessions_dir: str = ".simplecode/sessions"
    # Провайдеры
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    # Системный промпт (путь к файлу)
    system_prompt_file: str = ""

    def __post_init__(self):
        if not self.working_dir:
            self.working_dir = os.getcwd()


# ---------- Загрузка конфига ----------

def _find_config_file() -> Path | None:
    """Ищет simplecode.toml в текущей директории и выше."""
    current = Path.cwd()
    for _ in range(10):
        candidate = current / "simplecode.toml"
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def load_config(config_path: str | None = None) -> Config:
    """
    Загружает конфигурацию.
    Приоритет: аргумент config_path > simplecode.toml > значения по умолчанию.
    """
    data = {}
    path = Path(config_path) if config_path else _find_config_file()

    if path and path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)

    # Провайдеры из конфига
    providers = {}
    for name, pdata in data.get("providers", {}).items():
        providers[name] = ProviderConfig(
            api_key=pdata.get("api_key", ""),
            base_url=pdata.get("base_url", ""),
            default_model=pdata.get("default_model", ""),
        )

    cfg = Config(
        provider=data.get("provider", "openai"),
        model=data.get("model", ""),
        max_agent_steps=data.get("max_agent_steps", 30),
        working_dir=data.get("working_dir", ""),
        sessions_dir=data.get("sessions_dir", ".simplecode/sessions"),
        providers=providers,
        system_prompt_file=data.get("system_prompt_file", ""),
    )

    # Попытка загрузить API ключ из переменных окружения
    if cfg.provider not in cfg.providers:
        env_api_key = os.environ.get(f"{cfg.provider.upper()}_API_KEY", "")
        env_base_url = os.environ.get(f"{cfg.provider.upper()}_BASE_URL", "")
        if env_api_key:
            env_model = os.environ.get(f"{cfg.provider.upper()}_MODEL", "")
            providers[cfg.provider] = ProviderConfig(
                api_key=env_api_key,
                base_url=env_base_url,
                default_model=env_model,
            )
            cfg.providers = providers

    return cfg


def get_provider_config(cfg: Config, provider_name: str | None = None) -> ProviderConfig:
    """Возвращает конфиг конкретного провайдера."""
    name = provider_name or cfg.provider
    if name not in cfg.providers:
        raise ValueError(
            f"Провайдер '{name}' не настроен.\n"
            f"Добавьте его в simplecode.toml или задайте {name.upper()}_API_KEY."
        )
    return cfg.providers[name]
