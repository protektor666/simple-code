"""
Реестр инструментов (tools) — центральный каталог всех доступных инструментов.
Каждый инструмент имеет: имя, описание, JSON-схему параметров, функцию-обработчик.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """Описание одного инструмента."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema параметров
    handler: Callable[..., str]  # Функция, выполняющая инструмент


class ToolRegistry:
    """
    Хранит все зарегистрированные инструменты.
    Предоставляет методы для получения схем и вызова.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Регистрирует инструмент."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Получает инструмент по имени."""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        """Возвращает JSON-схемы всех инструментов для LLM."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return schemas

    def call(self, name: str, arguments: dict) -> str:
        """
        Вызывает инструмент по имени с аргументами.
        Возвращает строковый результат.
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"Ошибка: инструмент '{name}' не найден."
        try:
            result = tool.handler(**arguments)
            return str(result) if result is not None else ""
        except Exception as e:
            return f"Ошибка при выполнении '{name}': {type(e).__name__}: {e}"

    def list_names(self) -> list[str]:
        """Возвращает список имён всех инструментов."""
        return list(self._tools.keys())


def create_default_registry(working_dir: str) -> ToolRegistry:
    """
    Создаёт реестр со всеми встроенными инструментами.
    """
    registry = ToolRegistry()

    from . import file_tools, bash_tools, search_tools

    # Регистрируем все инструменты
    for tool in file_tools.get_tools(working_dir):
        registry.register(tool)
    for tool in bash_tools.get_tools(working_dir):
        registry.register(tool)
    for tool in search_tools.get_tools(working_dir):
        registry.register(tool)

    return registry
