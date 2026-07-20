"""
Агент — основной цикл рассуждений и вызова инструментов.
Агент получает сообщение пользователя, отправляет LLM,
и если LLM запрашивает инструменты — выполняет их и возвращает результат.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .providers.base import BaseProvider, LLMResponse, ToolCall
from .providers.factory import create_provider, get_default_model
from .providers.tools.registry import ToolRegistry, create_default_registry
from .session import Session, Message


# ---------- Системный промпт ----------

DEFAULT_SYSTEM_PROMPT = """\
Ты — AI-ассистент для работы с кодом. Ты работаешь в терминале.

## Правила

1. Ты можешь читать, создавать и редактировать файлы.
2. Ты можешь выполнять команды в shell.
3. Ты можешь искать файлы и текст в кодовой базе.
4. Будь краток и точен в ответах.
5. Когда редактируешь файл — используй tool edit_file, если нужно заменить конкретную строку.
6. Используй read_file чтобы сначала прочитать файл, прежде чем его редактировать.
7. Для поиска по файлам используй grep_search или glob_search.
8. Всегда объясняй что делаешь перед вызовом инструментов.
"""


def load_system_prompt(cfg: Config) -> str:
    """Загружает системный промпт из файла или использует по умолчанию."""
    if cfg.system_prompt_file:
        path = Path(cfg.system_prompt_file)
        if path.exists():
            return path.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT


# ---------- Callback для логирования ----------

@dataclass
class AgentCallbacks:
    """Обратные вызовы для отображения прогресса."""
    on_thinking: callable = None      # Вызывается перед запросом к LLM
    on_tool_call: callable = None     # Вызывается при вызове инструмента
    on_tool_result: callable = None   # Вызывается при результате инструмента
    on_response: callable = None      # Вызывается при текстовом ответе LLM
    on_error: callable = None         # Вызывается при ошибке


# ---------- Агент ----------

class Agent:
    """
    Основной агент. Управляет циклом:
    1. Получает сообщение пользователя
    2. Отправляет в LLM
    3. Если LLM хочет вызвать инструмент — выполняет его
    4. Отправляет результат обратно в LLM
    5. Повторяет, пока LLM не вернёт текстовый ответ
    """

    def __init__(
        self,
        cfg: Config,
        session: Session,
        callbacks: AgentCallbacks | None = None,
    ):
        self.cfg = cfg
        self.session = session
        self.callbacks = callbacks or AgentCallbacks()

        # Создаём LLM-провайдер
        self.provider: BaseProvider = create_provider(cfg)

        # Создаём реестр инструментов
        self.tools: ToolRegistry = create_default_registry(cfg.working_dir)

        # Системный промпт
        self.system_prompt = load_system_prompt(cfg)

        # Максимальное количество шагов (чтобы избежать бесконечного цикла)
        self.max_steps = cfg.max_agent_steps

    def _notify(self, callback_name: str, *args, **kwargs):
        """Безопасно вызывает callback если он установлен."""
        callback = getattr(self.callbacks, callback_name, None)
        if callback:
            try:
                callback(*args, **kwargs)
            except Exception:
                pass

    def send_message(self, user_message: str) -> str:
        """
        Отправляет сообщение пользователя и запускает агентный цикл.

        Args:
            user_message: Текст сообщения пользователя.

        Returns:
            Финальный текстовый ответ агента.
        """
        # Добавляем сообщение пользователя в сессию
        self.session.add_message(Message(role="user", content=user_message))

        # Формируем список сообщений для LLM
        messages = self._build_messages()

        # Получаем схемы инструментов
        tool_schemas = self.tools.get_schemas()
        formatted_tools = self.provider.format_tools(tool_schemas) if tool_schemas else None

        # Агентный цикл: повторяем пока LLM запрашивает инструменты
        final_response = ""

        for step in range(self.max_steps):
            self._notify("on_thinking", step)

            try:
                response: LLMResponse = self.provider.chat(
                    messages=messages,
                    tools=formatted_tools,
                )
            except Exception as e:
                error_msg = f"Ошибка LLM: {type(e).__name__}: {e}"
                self._notify("on_error", error_msg)
                final_response = error_msg
                break

            # Если LLM вернул текст без вызовов инструментов — готово
            if not response.tool_calls:
                final_response = response.content
                if response.content:
                    self._notify("on_response", response.content)
                break

            # Добавляем ответ LLM (без контента или с контентом) в историю
            assistant_msg = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                # OpenAI формат: добавляем tool_calls в assistant-сообщение
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ]
            messages.append(assistant_msg)

            # Выполняем каждый вызов инструмента
            for tool_call in response.tool_calls:
                self._notify("on_tool_call", tool_call.name, tool_call.arguments)

                result = self.tools.call(tool_call.name, tool_call.arguments)

                self._notify("on_tool_result", tool_call.name, result)

                # Форматируем результат для провайдера
                tool_result_msg = self.provider.format_tool_result(tool_call.id, result)
                messages.append(tool_result_msg)

        # Сохраняем финальный ответ в сессию
        if final_response:
            self.session.add_message(Message(role="assistant", content=final_response))

        return final_response

    def _build_messages(self) -> list[dict]:
        """Собирает все сообщения в формат для LLM."""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Добавляем историю из сессии
        for msg in self.session.messages:
            messages.append({"role": msg.role, "content": msg.content})

        return messages

    def get_available_tools(self) -> list[str]:
        """Возвращает список имён доступных инструментов."""
        return self.tools.list_names()
