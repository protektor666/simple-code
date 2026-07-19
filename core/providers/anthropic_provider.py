"""
Провайдер для Anthropic Claude API.
"""

import json

import httpx

from .base import BaseProvider, LLMResponse, ToolCall


class AnthropicProvider(BaseProvider):
    """Провайдер, использующий Anthropic Messages API."""

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Отправляет запрос в Anthropic API.
        Anthropic использует отдельный system prompt,
        поэтому извлекаем его из первого сообщения.
        """
        url = f"{self.base_url or self.DEFAULT_BASE_URL}/messages"

        # Извлекаем system prompt из первого сообщения
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                chat_messages.append(msg)

        payload: dict = {
            "model": self.model or self.DEFAULT_MODEL,
            "max_tokens": 8192,
            "messages": chat_messages,
        }

        if system_text:
            payload["system"] = system_text

        if tools:
            payload["tools"] = self.format_tools(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Парсим ответ Anthropic
        content = ""
        tool_calls = []
        stop_reason = data.get("stop_reason", "")

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                try:
                    args = json.loads(json.dumps(block["input"]))
                except (TypeError, KeyError):
                    args = {}
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=args,
                ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )

    def format_tools(self, tool_schemas: list[dict]) -> list[dict]:
        """
        Конвертирует универсальные схемы в формат Anthropic.
        Anthropic использует slightly другой формат параметров.
        """
        result = []
        for schema in tool_schemas:
            params = schema.get("parameters", {})
            # Anthropic требует, чтобы параметры были объектом
            # с properties и required на верхнем уровне
            result.append({
                "name": schema["name"],
                "description": schema.get("description", ""),
                "input_schema": params,
            })
        return result

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Форматирует результат инструмента для Anthropic."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "content": result,
        }

    def get_default_model(self) -> str:
        return self.model or self.DEFAULT_MODEL
