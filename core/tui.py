"""
Терминальный интерфейс (TUI) с использованием rich.
Отображает чат, статус агента, и управление провайдерами.
"""

import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .agent import Agent, AgentCallbacks
from .session import Session, SessionManager
from .provider_manager import ProviderManager, PROVIDER_TYPES


# Цвета
USER_COLOR = "cyan"
ASSISTANT_COLOR = "green"
TOOL_COLOR = "yellow"
ERROR_COLOR = "red"
SUCCESS_COLOR = "green"
DIM_COLOR = "dim"


class TUI:
    """
    Терминальный интерфейс simple-code.
    Обрабатывает ввод пользователя и отображение ответов.
    """

    def __init__(
        self,
        agent: Agent,
        session: Session,
        session_manager: SessionManager,
        provider_manager: ProviderManager,
    ):
        self.agent = agent
        self.session = session
        self.session_manager = session_manager
        self.provider_manager = provider_manager
        self.console = Console()

        # Устанавливаем callbacks для отображения прогресса
        self.agent.callbacks = AgentCallbacks(
            on_thinking=self._on_thinking,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
            on_response=self._on_response,
            on_error=self._on_error,
        )

    # ---------- Callbacks ----------

    def _on_thinking(self, step: int):
        if step == 0:
            self.console.print()
        self.console.print(f"[{DIM_COLOR}]Думаю... (шаг {step + 1})[/{DIM_COLOR}]")

    def _on_tool_call(self, tool_name: str, arguments: dict):
        args_str = ", ".join(f"{k}={repr(v)[:60]}" for k, v in arguments.items())
        self.console.print(f"  [{TOOL_COLOR}]▸ {tool_name}[/{TOOL_COLOR}]({args_str})")

    def _on_tool_result(self, tool_name: str, result: str):
        lines = result.split("\n")
        if len(lines) > 5:
            preview = "\n".join(lines[:5]) + f"\n  ... ({len(lines)} строк всего)"
        else:
            preview = result
        self.console.print(
            Panel(preview, title=f"[{TOOL_COLOR}]{tool_name}[/{TOOL_COLOR}]", border_style=DIM_COLOR, padding=(0, 1))
        )

    def _on_response(self, content: str):
        pass

    def _on_error(self, error_msg: str):
        self.console.print(f"[{ERROR_COLOR}]✗ {error_msg}[/{ERROR_COLOR}]")

    # ---------- Отображение ----------

    def print_welcome(self):
        welcome = Panel(
            "[bold]Simple Code[/bold] — AI-ассистент для работы с кодом\n\n"
            f"Модель: [{ASSISTANT_COLOR}]{self.agent.provider.get_default_model()}[/{ASSISTANT_COLOR}]\n"
            f"Провайдер: [{ASSISTANT_COLOR}]{self.agent.cfg.provider}[/{ASSISTANT_COLOR}]\n"
            f"Сессия: [{DIM_COLOR}]{self.session.id}[/{DIM_COLOR}]\n\n"
            f"[{DIM_COLOR}]/help — справка | /providers — управление провайдерами[/{DIM_COLOR}]",
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(welcome)

    def print_help(self):
        help_text = Table(show_header=False, padding=(0, 2))
        help_text.add_column(style="bold cyan")
        help_text.add_column()
        help_text.add_row("/help", "Показать эту справку")
        help_text.add_row("/session", "Показать текущую сессию")
        help_text.add_row("/sessions", "Список всех сессий")
        help_text.add_row("/load <id>", "Загрузить сессию по ID")
        help_text.add_row("/new", "Начать новую сессию")
        help_text.add_row("/tools", "Показать доступные инструменты")
        help_text.add_row("/providers", "Список всех провайдеров")
        help_text.add_row("/add-provider", "Добавить нового провайдера (интерактивно)")
        help_text.add_row("/remove-provider <имя>", "Удалить провайдер")
        help_text.add_row("/test-provider <имя>", "Проверить подключение к провайдеру")
        help_text.add_row("/use <имя>", "Переключиться на провайдер")
        help_text.add_row("/quit", "Выйти")
        self.console.print(Panel(help_text, title="Команды", border_style="blue"))

    def print_tools(self):
        tools = self.agent.tools.get_schemas()
        table = Table(title="Доступные инструменты", border_style="blue")
        table.add_column("Имя", style="bold cyan")
        table.add_column("Описание")
        for tool in tools:
            table.add_row(tool["name"], tool["description"][:80])
        self.console.print(table)

    def print_session_info(self):
        self.console.print(Panel(
            f"ID: {self.session.id}\n"
            f"Название: {self.session.title or '(нет)'}\n"
            f"Создана: {self.session.created_at}\n"
            f"Сообщений: {len(self.session.messages)}\n"
            f"Модель: {self.session.model}",
            title="Текущая сессия", border_style="blue",
        ))

    def print_sessions_list(self):
        sessions = self.session_manager.list_sessions()
        if not sessions:
            self.console.print(f"[{DIM_COLOR}]Нет сохранённых сессий[/{DIM_COLOR}]")
            return
        table = Table(title="Сессии", border_style="blue")
        table.add_column("ID", style="bold cyan")
        table.add_column("Название")
        table.add_column("Сообщений", justify="right")
        table.add_column("Обновлена")
        for s in sessions:
            title = s["title"][:50] if s["title"] else "(без названия)"
            table.add_row(s["id"], title, str(s["message_count"]), s["updated_at"][:19])
        self.console.print(table)

    def print_message(self, role: str, content: str):
        if role == "user":
            self.console.print()
            self.console.print(f"[bold {USER_COLOR}]Вы:[/bold {USER_COLOR}]")
            self.console.print(content)
        elif role == "assistant":
            self.console.print()
            self.console.print(f"[bold {ASSISTANT_COLOR}]Ассистент:[/bold {ASSISTANT_COLOR}]")
            try:
                self.console.print(Markdown(content))
            except Exception:
                self.console.print(content)

    # ---------- Управление провайдерами ----------

    def print_providers(self):
        """Отображает таблицу всех провайдеров."""
        providers = self.provider_manager.list_providers()

        if not providers:
            self.console.print(f"[{DIM_COLOR}]Нет добавленных провайдеров. Используйте /add-provider[/{DIM_COLOR}]")
            return

        current = self.agent.cfg.provider
        table = Table(title="Провайдеры", border_style="blue")
        table.add_column("Имя", style="bold cyan")
        table.add_column("Тип")
        table.add_column("URL")
        table.add_column("Модель")
        table.add_column("Статус")

        for name, p in providers.items():
            marker = f" [{SUCCESS_COLOR}]*[/{SUCCESS_COLOR}]" if name == current else ""
            status = "локальный" if p.is_local else "облачный"
            table.add_row(
                f"{name}{marker}",
                p.provider_type,
                p.base_url or "(по умолчанию)",
                p.default_model or "(Авто)",
                status,
            )

        self.console.print(table)
        self.console.print(f"[{DIM_COLOR}]* — текущий активный провайдер[/{DIM_COLOR}]")

    def interactive_add_provider(self):
        """Интерактивный мастер добавления провайдера."""
        self.console.print(Panel("[bold]Добавление нового провайдера[/bold]", border_style="blue"))

        # Шаг 1: Имя
        name = Prompt.ask("[bold cyan]Имя провайдера (латиница, например: my-ollama)[/bold cyan]")
        if not name.strip():
            self.console.print(f"[{ERROR_COLOR}]Имя не может быть пустым.[/{ERROR_COLOR}]")
            return
        name = name.strip().lower().replace(" ", "-")

        if self.provider_manager.get_provider(name):
            self.console.print(f"[{ERROR_COLOR}]Провайдер '{name}' уже существует.[/{ERROR_COLOR}]")
            return

        # Шаг 2: Тип провайдера
        self.console.print("\n[bold]Доступные типы провайдеров:[/bold]")
        types = list(PROVIDER_TYPES.items())
        for i, (key, desc) in enumerate(types, 1):
            self.console.print(f"  [{TOOL_COLOR}]{i}[/{TOOL_COLOR}]. {key} — {desc}")

        type_choice = Prompt.ask(
            "[bold cyan]Выберите тип (номер или имя)[/bold cyan]",
            default="1",
        )

        # Парсим выбор
        try:
            idx = int(type_choice) - 1
            provider_type = types[idx][0]
        except (ValueError, IndexError):
            provider_type = type_choice.strip().lower()
            if provider_type not in PROVIDER_TYPES:
                self.console.print(f"[{ERROR_COLOR}]Неизвестный тип: {provider_type}[/{ERROR_COLOR}]")
                return

        is_local = provider_type in ("ollama", "lmstudio", "llamacpp", "vllm")

        # Шаг 3: URL
        if is_local:
            from .provider_manager import _default_local_url
            default_url = _default_local_url(provider_type)
            base_url = Prompt.ask(
                f"[bold cyan]URL сервера[/bold cyan]",
                default=default_url,
            )
        else:
            base_url = Prompt.ask(
                "[bold cyan]Base URL (оставьте пустым для официального API)[/bold cyan]",
                default="",
            )

        # Шаг 4: API ключ
        if is_local:
            api_key = provider_type  # "ollama", "lmstudio" и т.д.
        elif provider_type in ("openai", "anthropic", "custom") and base_url != "":
            api_key = Prompt.ask("[bold cyan]API ключ (или оставьте пустым)[/bold cyan]", default="")
        elif provider_type in ("openai", "anthropic"):
            api_key = Prompt.ask("[bold cyan]API ключ[/bold cyan]", default="")
            if not api_key:
                self.console.print(f"[{ERROR_COLOR}]API ключ обязателен для облачных провайдеров.[/{ERROR_COLOR}]")
                return
        else:
            api_key = Prompt.ask("[bold cyan]API ключ[/bold cyan]", default="")
            if not api_key:
                self.console.print(f"[{ERROR_COLOR}]API ключ обязателен.[/{ERROR_COLOR}]")
                return

        # Шаг 5: Модель по умолчанию
        default_model = Prompt.ask(
            "[bold cyan]Модель по умолчанию (оставьте пустым для авто)[/bold cyan]",
            default="",
        )

        # Шаг 6: Описание
        desc = Prompt.ask(
            "[bold cyan]Описание (необязательно)[/bold cyan]",
            default="",
        )

        # Создаём провайдер
        try:
            provider = self.provider_manager.add_provider(
                name=name,
                provider_type=provider_type,
                base_url=base_url,
                api_key=api_key,
                default_model=default_model,
                description=desc,
            )
            self.console.print(f"\n[{SUCCESS_COLOR}]✓ Провайдер '{name}' успешно добавлен![/{SUCCESS_COLOR}]")
            self.console.print(f"  Тип: {provider.provider_type}")
            self.console.print(f"  URL: {provider.base_url or '(по умолчанию)'}")
            self.console.print(f"  Модель: {provider.default_model or '(Авто)'}")

            # Предлагаем проверить соединение
            if Confirm.ask("\n[bold cyan]Проверить подключение?[/bold cyan]", default=True):
                self._test_provider(name)

        except Exception as e:
            self.console.print(f"[{ERROR_COLOR}]Ошибка: {e}[/{ERROR_COLOR}]")

    def _test_provider(self, name: str):
        """Проверяет подключение к провайдеру."""
        self.console.print(f"[{DIM_COLOR}]Проверяю подключение к '{name}'...[/{DIM_COLOR}]")
        result = self.provider_manager.test_connection(name)

        if result["ok"]:
            self.console.print(f"[{SUCCESS_COLOR}]✓ {result['message']}[/{SUCCESS_COLOR}]")
            if result["models"]:
                # Сохраняем список моделей
                self.provider_manager.update_provider(name, models=result["models"])
                # Показываем первые 10 моделей
                shown = result["models"][:10]
                for m in shown:
                    self.console.print(f"  • {m}")
                if len(result["models"]) > 10:
                    self.console.print(f"  ... и ещё {len(result['models']) - 10}")
        else:
            self.console.print(f"[{ERROR_COLOR}]✗ {result['message']}[/{ERROR_COLOR}]")

    def handle_use_provider(self, name: str):
        """Переключает активный провайдер."""
        if not name:
            self.console.print(f"[{ERROR_COLOR}]Укажите имя: /use <имя>[/{ERROR_COLOR}]")
            return

        # Проверяем в управляемых провайдерах
        managed = self.provider_manager.get_provider(name)
        if managed:
            # Синхронизируем с основным конфигом
            self.provider_manager.sync_to_config(self.agent.cfg)
            self.agent.cfg.provider = name
            # Пересоздаём провайдер в агенте
            from .providers.factory import create_provider
            self.agent.provider = create_provider(self.agent.cfg)
            self.console.print(f"[{SUCCESS_COLOR}]Переключено на '{name}' ({managed.provider_type})[/{SUCCESS_COLOR}]")
            return

        # Проверяем в статических провайдерах
        from .providers.factory import PROVIDERS
        if name in PROVIDERS or name in self.agent.cfg.providers:
            self.agent.cfg.provider = name
            from .providers.factory import create_provider
            self.agent.provider = create_provider(self.agent.cfg)
            self.console.print(f"[{SUCCESS_COLOR}]Переключено на '{name}'[/{SUCCESS_COLOR}]")
            return

        self.console.print(f"[{ERROR_COLOR}]Провайдер '{name}' не найден.[/{ERROR_COLOR}]")

    # ---------- Основной цикл ----------

    def run(self):
        self.print_welcome()

        if self.session.messages:
            self.console.print(f"\n[{DIM_COLOR}]--- История сессии ---[/{DIM_COLOR}]")
            for msg in self.session.messages:
                self.print_message(msg.role, msg.content)
            self.console.print(f"[{DIM_COLOR}]--- Конец истории ---[/{DIM_COLOR}]\n")

        while True:
            try:
                self.console.print()
                user_input = self.console.input(f"[bold {USER_COLOR}]>>> [/bold {USER_COLOR}]")

                if user_input.startswith("/"):
                    if self._handle_command(user_input):
                        break
                    continue

                if not user_input.strip():
                    continue

                self.console.print()
                response = self.agent.send_message(user_input)
                self.print_message("assistant", response)
                self.session_manager.save_session(self.session)

            except KeyboardInterrupt:
                self.console.print(f"\n[{DIM_COLOR}]Нажмите /quit для выхода[/{DIM_COLOR}]")
                continue
            except EOFError:
                break

        self.console.print(f"[{DIM_COLOR}]До свидания![/{DIM_COLOR}]")

    def _handle_command(self, command: str) -> bool:
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/help":
            self.print_help()

        elif cmd == "/session":
            self.print_session_info()

        elif cmd == "/sessions":
            self.print_sessions_list()

        elif cmd == "/load":
            if not arg:
                self.console.print(f"[{ERROR_COLOR}]Укажите ID сессии: /load <id>[/{ERROR_COLOR}]")
            else:
                new_session = self.session_manager.load_session(arg)
                if new_session:
                    self.session = new_session
                    self.agent.session = new_session
                    self.console.print(f"[{SUCCESS_COLOR}]Сессия {arg} загружена[/{SUCCESS_COLOR}]")
                else:
                    self.console.print(f"[{ERROR_COLOR}]Сессия {arg} не найдена[/{ERROR_COLOR}]")

        elif cmd == "/new":
            new_session = self.session_manager.create_session(
                model=self.agent.provider.get_default_model(),
                provider=self.agent.cfg.provider,
            )
            self.session = new_session
            self.agent.session = new_session
            self.console.print(f"[{SUCCESS_COLOR}]Новая сессия: {new_session.id}[/{SUCCESS_COLOR}]")

        elif cmd == "/tools":
            self.print_tools()

        elif cmd == "/providers":
            self.print_providers()

        elif cmd == "/add-provider":
            self.interactive_add_provider()

        elif cmd == "/remove-provider":
            if not arg:
                self.console.print(f"[{ERROR_COLOR}]Укажите имя: /remove-provider <имя>[/{ERROR_COLOR}]")
            else:
                managed = self.provider_manager.get_provider(arg)
                if managed:
                    if Confirm.ask(f"Удалить провайдер '{arg}'?", default=False):
                        self.provider_manager.remove_provider(arg)
                        self.console.print(f"[{SUCCESS_COLOR}]Провайдер '{arg}' удалён.[/{SUCCESS_COLOR}]")
                else:
                    self.console.print(f"[{ERROR_COLOR}]Провайдер '{arg}' не найден.[/{ERROR_COLOR}]")

        elif cmd == "/test-provider":
            if not arg:
                self.console.print(f"[{ERROR_COLOR}]Укажите имя: /test-provider <имя>[/{ERROR_COLOR}]")
            else:
                self._test_provider(arg)

        elif cmd == "/use":
            self.handle_use_provider(arg)

        elif cmd == "/quit":
            self.session_manager.save_session(self.session)
            return True

        else:
            self.console.print(f"[{ERROR_COLOR}]Неизвестная команда: {cmd}. /help — справка[/{ERROR_COLOR}]")

        return False
