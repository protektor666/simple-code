"""
Инструмент для выполнения команд в shell.
"""

import subprocess
import os

from .registry import Tool


def get_tools(working_dir: str) -> list[Tool]:
    """Возвращает список bash-инструментов."""

    def run_command(command: str, timeout: int = 120) -> str:
        """Выполняет команду в shell и возвращает вывод."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env={**os.environ, "TERM": "dumb"},
            )

            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout.rstrip())
            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr.rstrip()}")
            if result.returncode != 0:
                output_parts.append(f"Код возврата: {result.returncode}")

            if not output_parts:
                return "Команда выполнена успешно (без вывода)."

            return "\n".join(output_parts)

        except subprocess.TimeoutExpired:
            return f"Ошибка: команда превышила таймаут ({timeout} сек)."
        except Exception as e:
            return f"Ошибка выполнения команды: {type(e).__name__}: {e}"

    return [
        Tool(
            name="run_command",
            description=(
                "Выполняет команду в shell (bash/cmd). "
                "Возвращает stdout, stderr и код возврата."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Команда для выполнения",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Таймаут в секундах (120 по умолчанию)",
                        "default": 120,
                    },
                },
                "required": ["command"],
            },
            handler=run_command,
        ),
    ]
