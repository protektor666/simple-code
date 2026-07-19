"""
Инструменты для поиска файлов и текста в коде.
"""

import os
import re
from pathlib import Path

from .registry import Tool


def get_tools(working_dir: str) -> list[Tool]:
    """Возвращает список инструментов поиска."""

    def glob_search(pattern: str, path: str = ".") -> str:
        """Ищет файлы по glob-паттерну (например **/*.py)."""
        search_root = os.path.join(working_dir, path)
        root = Path(search_root)

        if not root.exists():
            return f"Ошибка: путь '{path}' не найден."

        matches = sorted(root.glob(pattern))

        if not matches:
            return f"Ничего не найдено по паттерну '{pattern}'."

        # Ограничиваем вывод 200 файлами
        results = []
        for match in matches[:200]:
            rel = match.relative_to(working_dir) if match.is_relative_to(working_dir) else match
            if match.is_dir():
                results.append(f"{rel}/")
            else:
                results.append(str(rel))

        header = f"Найдено {len(matches)} совпадений"
        if len(matches) > 200:
            header += f" (показано 200 из {len(matches)})"
        return header + ":\n" + "\n".join(results)

    def grep_search(
        pattern: str,
        path: str = ".",
        include: str = "",
        max_results: int = 100,
    ) -> str:
        """Ищет текст в файлах по регулярному выражению."""
        search_root = os.path.join(working_dir, path)
        root = Path(search_root)

        if not root.exists():
            return f"Ошибка: путь '{path}' не найден."

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Ошибка в регулярном выражении: {e}"

        results = []
        files_searched = 0

        for file_path in root.rglob("*"):
            # Пропускаем директории и скрытые файлы
            if file_path.is_dir():
                continue
            if any(part.startswith(".") for part in file_path.parts):
                continue

            # Фильтр по расширению
            if include and not file_path.match(include):
                continue

            # Пропускаем бинарные файлы (грубо)
            if file_path.stat().st_size > 1_000_000:
                continue

            files_searched += 1

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            rel_path = file_path.relative_to(working_dir)
                            results.append(f"{rel_path}:{line_num}: {line.rstrip()}")

                            if len(results) >= max_results:
                                header = f"Найдено {max_results}+ совпадений (поиск в {files_searched} файлах)"
                                return header + ":\n" + "\n".join(results)
            except Exception:
                continue

        if not results:
            return f"Ничего не найдено по паттерну '{pattern}' в {files_searched} файлах."

        header = f"Найдено {len(results)} совпадений (поиск в {files_searched} файлах)"
        return header + ":\n" + "\n".join(results)

    return [
        Tool(
            name="glob_search",
            description=(
                "Ищет файлы по glob-паттерну. "
                "Примеры: '**/*.py', 'src/**/*.ts', '*.json'"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob-паттерн для поиска файлов",
                    },
                    "path": {
                        "type": "string",
                        "description": "Корневая директория поиска (по умолчанию '.')",
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
            handler=glob_search,
        ),
        Tool(
            name="grep_search",
            description=(
                "Ищет текст в файлах по регулярному выражению. "
                "Возвращает файл, номер строки и совпадение."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Регулярное выражение для поиска",
                    },
                    "path": {
                        "type": "string",
                        "description": "Директория для поиска (по умолчанию '.')",
                        "default": ".",
                    },
                    "include": {
                        "type": "string",
                        "description": "Фильтр по расширению файлов (например '*.py')",
                        "default": "",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (100)",
                        "default": 100,
                    },
                },
                "required": ["pattern"],
            },
            handler=grep_search,
        ),
    ]
