"""
Провайдер для OpenAI API (и совместимых API через base_url).
Работает с OpenAI, Together, Groq, Ollama и любыми OpenAI-совместимыми сервисами.
"""

import json

import httpx

from .base import BaseProvider, LLMResponse, ToolCall


class OpenAIProvider(BaseProvider):
    """
    Провайдер, использующий OpenAI-совместимый API.
    Поддерживает любой сервис с OpenAI-форматом запросов.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Отправляет запрос в OpenAI-совместимый API."""
        # Проверяем ключ только для официальных облачных API
        url = f"{self.base_url or self.DEFAULT_BASE_URL}/chat/completions"
        is_cloud = not self.base_url or "api.openai.com" in self.base_url
        if is_cloud and not self.api_key:
            raise ValueError(
                "API ключ не задан. "
                "Добавьте провайдер заново через /add-provider "
                "или задайте API ключ в simplecode.toml."
            )

        payload: dict = {
            "model": self.model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": 0.7,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Парсим ответ
        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "")

        content = message.get("content") or ""
        tool_calls = []

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                # Парсим аргументы из JSON-строки
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=args,
                ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=finish_reason,
        )

    def format_tools(self, tool_schemas: list[dict]) -> list[dict]:
        """
        Конвертирует универсальные схемы в формат OpenAI.
        Универсальный формат уже совместим с OpenAI, просто оборачиваем.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {}),
                },
            }
            for schema in tool_schemas
        ]

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Форматирует результат инструмента для OpenAI."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def get_default_model(self) -> str:
        return self.model or self.DEFAULT_MODEL
