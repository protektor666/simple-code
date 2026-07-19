"""
Инструменты для работы с файлами: чтение, запись, список файлов.
"""

import os
from pathlib import Path

from .registry import Tool


def get_tools(working_dir: str) -> list[Tool]:
    """Возвращает список файловых инструментов."""

    def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Читает содержимое файла."""
        full_path = os.path.join(working_dir, file_path)
        path = Path(full_path)

        if not path.exists():
            return f"Ошибка: файл '{file_path}' не найден."
        if not path.is_file():
            return f"Ошибка: '{file_path}' не является файлом."

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Ошибка чтения файла: {e}"

        total = len(lines)
        # offset — 1-indexed в оригинале, но принимаем 0-indexed
        start = max(0, offset)
        end = min(total, start + limit)
        selected = lines[start:end]

        # Форматируем с номерами строк
        result_lines = []
        for i, line in enumerate(selected, start=start + 1):
            result_lines.append(f"{i}: {line.rstrip()}")

        header = f"Файл: {file_path} (строки {start + 1}-{end} из {total})"
        return header + "\n" + "\n".join(result_lines)

    def write_file(file_path: str, content: str) -> str:
        """Записывает содержимое в файл."""
        full_path = os.path.join(working_dir, file_path)
        path = Path(full_path)

        # Создаём директории если нужно
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Файл '{file_path}' успешно записан ({len(content)} символов)."
        except Exception as e:
            return f"Ошибка записи файла: {e}"

    def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        """Заменяет строку в файле (точное совпадение)."""
        full_path = os.path.join(working_dir, file_path)
        path = Path(full_path)

        if not path.exists():
            return f"Ошибка: файл '{file_path}' не найден."

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Ошибка чтения файла: {e}"

        if old_string not in content:
            return f"Ошибка: строка не найдена в '{file_path}'. Проверьте точность old_string."

        count = content.count(old_string)
        if count > 1:
            return f"Ошибка: строка найдена {count} раз. Укажите больше контекста для уникального поиска."

        new_content = content.replace(old_string, new_string, 1)

        try:
            path.write_text(new_content, encoding="utf-8")
            return f"Файл '{file_path}' успешно обновлён."
        except Exception as e:
            return f"Ошибка записи файла: {e}"

    def list_directory(dir_path: str = ".") -> str:
        """Показывает содержимое директории."""
        full_path = os.path.join(working_dir, dir_path)
        path = Path(full_path)

        if not path.exists():
            return f"Ошибка: директория '{dir_path}' не найдена."
        if not path.is_dir():
            return f"Ошибка: '{dir_path}' не является директорией."

        entries = []
        for entry in sorted(path.iterdir()):
            if entry.name.startswith(".") and entry.name not in (".", ".."):
                prefix = "  "
            else:
                prefix = ""

            if entry.is_dir():
                entries.append(f"  {entry.name}/")
            else:
                size = entry.stat().st_size
                entries.append(f"  {entry.name} ({size} байт)")

        if not entries:
            return f"Директория '{dir_path}' пуста."

        return f"Содержимое '{dir_path}':\n" + "\n".join(entries)

    return [
        Tool(
            name="read_file",
            description=(
                "Читает содержимое файла. "
                "Возвращает содержимое с номерами строк."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу (относительно рабочей директории)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Номер строки начала чтения (0 по умолчанию)",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество строк (2000 по умолчанию)",
                        "default": 2000,
                    },
                },
                "required": ["file_path"],
            },
            handler=read_file,
        ),
        Tool(
            name="write_file",
            description="Записывает содержимое в файл. Создаёт файл если его нет.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу",
                    },
                    "content": {
                        "type": "string",
                        "description": "Содержимое для записи",
                    },
                },
                "required": ["file_path", "content"],
            },
            handler=write_file,
        ),
        Tool(
            name="edit_file",
            description=(
                "Заменяет конкретную строку в файле на новую. "
                "Требует точного совпадения old_string."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Текст для поиска (должен точно совпадать)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Новый текст",
                    },
                },
                "required": ["file_path", "old_string", "new_string"],
            },
            handler=edit_file,
        ),
        Tool(
            name="list_directory",
            description="Показывает содержимое директории (файлы и папки).",
            parameters={
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Путь к директории (по умолчанию '.')",
                        "default": ".",
                    },
                },
            },
            handler=list_directory,
        ),
    ]
