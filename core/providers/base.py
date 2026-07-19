"""
Абстрактный базовый класс для LLM-провайдеров.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Вызов инструмента от LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """
    Ответ от LLM.
    Если content непустой — текстовый ответ.
    Если tool_calls непустой — запрос на вызов инструментов.
    """
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""


class BaseProvider(ABC):
    """
    Базовый класс провайдера.
    Каждый провайдер (OpenAI, Anthropic, Custom) реализует этот интерфейс.
    """

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Отправляет сообщение в LLM и возвращает ответ.

        Args:
            messages: История сообщений в формате провайдера.
            tools: Список доступных инструментов (JSON Schema).

        Returns:
            LLMResponse с текстом и/или tool_calls.
        """
        ...

    @abstractmethod
    def format_tools(self, tool_schemas: list[dict]) -> list[dict]:
        """
        Конвертирует универсальные схемы инструментов
        в формат, понятный конкретному провайдеру.
        """
        ...

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """
        Форматирует результат выполнения инструмента
        в сообщение, понятное провайдеру.
        """
        ...

    def get_default_model(self) -> str:
        """Возвращает модель по умолчанию для провайдера."""
        return self.model
