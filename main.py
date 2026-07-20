"""
Simple Code — упрощённый аналог OpenCode.
Точка входа приложения.

Запуск:
    simple-code.exe
    simple-code.exe --provider ollama --model llama3.2
    simple-code.exe --provider ollama --model llama3.2 --ollama-base-url http://localhost:11434
    simple-code.exe --message "напиши hello world на python"

Управление провайдерами:
    simple-code.exe providers
    simple-code.exe add-provider
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config
from core.providers.factory import create_provider, get_default_model
from core.session import Session, SessionManager
from core.agent import Agent, AgentCallbacks
from core.provider_manager import ProviderManager, PROVIDER_TYPES
from core.tui import TUI


# Дефолтные URL для локальных провайдеров
DEFAULT_LOCAL_URLS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
    "llamacpp": "http://localhost:8080",
    "vllm": "http://localhost:8000",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple Code — AI-ассистент для работы с кодом",
    )

    # Основные аргументы (opencode-совместимые)
    parser.add_argument("--provider", default=None, help="LLM-провайдер (ollama, openai, anthropic...)")
    parser.add_argument("--model", default=None, help="Модель LLM")
    parser.add_argument("--ollama-base-url", "--api-base-url", default=None, dest="base_url",
                        help="Base URL для API (например http://localhost:11434)")
    parser.add_argument("-c", "--config", default=None, help="Путь к конфигу")
    parser.add_argument("--dir", default=None, help="Рабочая директория")

    # Прочие опции
    parser.add_argument("--message", default=None, help="Одноразовое сообщение (без TUI)")
    parser.add_argument("-s", "--session", default=None, help="ID сессии для загрузки")

    # Подкоманды
    subparsers = parser.add_subparsers(dest="command", help="Команда")

    providers_parser = subparsers.add_parser("providers", help="Список всех провайдеров")
    providers_parser.add_argument("--dir", default=None)

    add_parser = subparsers.add_parser("add-provider", help="Добавить провайдера")
    add_parser.add_argument("--name", default=None)
    add_parser.add_argument("--type", dest="provider_type", default=None,
                            help=f"Тип: {', '.join(PROVIDER_TYPES.keys())}")
    add_parser.add_argument("--url", default=None)
    add_parser.add_argument("--api-key", default=None)
    add_parser.add_argument("--model", default=None)
    add_parser.add_argument("--dir", default=None)

    remove_parser = subparsers.add_parser("remove-provider", help="Удалить провайдера")
    remove_parser.add_argument("name")
    remove_parser.add_argument("--dir", default=None)

    test_parser = subparsers.add_parser("test-provider", help="Проверить подключение")
    test_parser.add_argument("name")
    test_parser.add_argument("--dir", default=None)

    return parser.parse_args()


def _get_working_dir(args) -> str:
    return args.dir if hasattr(args, "dir") and args.dir else os.getcwd()


def _auto_configure_provider(cfg, provider_manager, args):
    """
    Авто-конфигурация провайдера из аргументов командной строки.
    Создаёт временного провайдера если нужно.
    """
    provider_name = args.provider or cfg.provider
    cfg.provider = provider_name

    # Если уже есть настроенный провайдер с таким именем — используем его
    if provider_name in cfg.providers:
        return

    # Провайдер уже есть в managed list?
    managed = provider_manager.get_provider(provider_name)
    if managed:
        provider_manager.sync_to_config(cfg)
        return

    # Определяем base_url
    base_url = args.base_url or ""
    if not base_url and provider_name in DEFAULT_LOCAL_URLS:
        base_url = DEFAULT_LOCAL_URLS[provider_name]

    # Определяем api_key
    api_key = ""
    if provider_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
    elif provider_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    elif base_url:
        api_key = provider_name

    # Определяем модель
    model = args.model or ""

    # Добавляем провайдера
    try:
        provider_manager.add_provider(
            name=provider_name,
            provider_type=provider_name,
            base_url=base_url,
            api_key=api_key,
            default_model=model,
        )
        provider_manager.sync_to_config(cfg)
    except Exception as e:
        print(f"Предупреждение: {e}", file=sys.stderr)


def cmd_providers(args):
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)
    providers = mgr.list_providers()

    if not providers:
        print("Нет добавленных провайдеров.")
        print("Используйте: simple-code.exe add-provider")
        return

    print(f"\n{'Имя':<20} {'Тип':<12} {'URL':<40} {'Модель':<20}")
    print("-" * 92)
    for name, p in providers.items():
        url = p.base_url or "(по умолчанию)"
        model = p.default_model or "(Авто)"
        print(f"{name:<20} {p.provider_type:<12} {url:<40} {model:<20}")
    print()


def cmd_add_provider(args):
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)

    if args.name and args.provider_type:
        try:
            provider = mgr.add_provider(
                name=args.name,
                provider_type=args.provider_type,
                base_url=args.url or "",
                api_key=args.api_key or "",
                default_model=args.model or "",
            )
            print(f"Провайдер '{provider.name}' добавлен ({provider.provider_type})")
            print(f"  URL: {provider.base_url or '(по умолчанию)'}")
            print(f"  Модель: {provider.default_model or '(Авто)'}")
        except Exception as e:
            print(f"Ошибка: {e}")
        return

    print("\n=== Добавление нового провайдера ===\n")

    name = args.name or input("Имя провайдера (латиница): ").strip().lower().replace(" ", "-")
    if not name:
        print("Имя не может быть пустым.")
        return

    if mgr.get_provider(name):
        print(f"Провайдер '{name}' уже существует.")
        return

    if not args.provider_type:
        print("\nДоступные типы:")
        types = list(PROVIDER_TYPES.items())
        for i, (key, desc) in enumerate(types, 1):
            print(f"  {i}. {key} — {desc}")
        choice = input("\nВыберите тип (номер или имя): ").strip()
        try:
            idx = int(choice) - 1
            provider_type = types[idx][0]
        except (ValueError, IndexError):
            provider_type = choice.lower()
    else:
        provider_type = args.provider_type

    if provider_type not in PROVIDER_TYPES:
        print(f"Неизвестный тип: {provider_type}")
        return

    is_local = provider_type in ("ollama", "lmstudio", "llamacpp", "vllm")

    if not args.url:
        if is_local:
            default_url = DEFAULT_LOCAL_URLS.get(provider_type, "http://localhost:8080")
            base_url = input(f"URL сервера [{default_url}]: ").strip() or default_url
        else:
            base_url = input("Base URL (пусто = официальный API): ").strip()
    else:
        base_url = args.url

    api_key = ""
    if is_local:
        api_key = provider_type
    elif args.api_key:
        api_key = args.api_key
    else:
        api_key = input("API ключ: ").strip()
        if not api_key:
            print("API ключ обязателен.")
            return

    default_model = args.model or input("Модель по умолчанию (пусто = авто): ").strip()

    try:
        provider = mgr.add_provider(
            name=name, provider_type=provider_type,
            base_url=base_url, api_key=api_key,
            default_model=default_model,
        )
        print(f"\nПровайдер '{provider.name}' добавлен ({provider.provider_type})")
    except Exception as e:
        print(f"Ошибка: {e}")


def cmd_remove_provider(args):
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)

    if not mgr.get_provider(args.name):
        print(f"Провайдер '{args.name}' не найден.")
        return

    confirm = input(f"Удалить провайдер '{args.name}'? (y/n): ").strip().lower()
    if confirm in ("y", "yes", "да"):
        mgr.remove_provider(args.name)
        print(f"Провайдер '{args.name}' удалён.")
    else:
        print("Отмена.")


def cmd_test_provider(args):
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)

    print(f"Проверяю подключение к '{args.name}'...")
    result = mgr.test_connection(args.name)

    if result["ok"]:
        print(f"  ✓ {result['message']}")
        if result["models"]:
            print(f"  Доступные модели:")
            for m in result["models"][:15]:
                print(f"    • {m}")
            if len(result["models"]) > 15:
                print(f"    ... и ещё {len(result['models']) - 15}")
    else:
        print(f"  ✗ {result['message']}")


def cmd_chat(args):
    cfg = load_config(args.config)

    if args.dir:
        cfg.working_dir = args.dir

    provider_manager = ProviderManager(cfg.working_dir)

    # Авто-конфигурация провайдера из аргументов
    if args.provider:
        _auto_configure_provider(cfg, provider_manager, args)

    # Если всё ещё нет провайдера — первый запуск, предлагаем
    if cfg.provider not in cfg.providers:
        print("\nНет настроенного провайдера.\n"
              "Запусти с --provider, например:\n"
              "  simple-code.exe --provider ollama\n"
              "  simple-code.exe --provider openai\n")
        sys.exit(0)

    provider_manager.sync_to_config(cfg)

    sessions_dir = os.path.join(cfg.working_dir, cfg.sessions_dir)
    session_manager = SessionManager(sessions_dir)

    if args.session:
        session = session_manager.load_session(args.session)
        if not session:
            print(f"Ошибка: сессия '{args.session}' не найдена.")
            sys.exit(1)
    else:
        existing = session_manager.list_sessions()
        if existing and not args.message:
            last = existing[0]
            print(f"Загружаю последнюю сессию: {last['id']} ({last['title'][:50]})")
            session = session_manager.load_session(last["id"])
        else:
            try:
                model = args.model or get_default_model(cfg)
            except ValueError:
                model = args.model or ""
            session = session_manager.create_session(model=model, provider=cfg.provider)

    agent = Agent(cfg, session)

    if args.message:
        callbacks = AgentCallbacks(
            on_tool_call=lambda name, a: print(f"  ▸ {name}", file=sys.stderr),
            on_tool_result=lambda name, result: None,
            on_error=lambda msg: print(f"  Ошибка: {msg}", file=sys.stderr),
        )
        agent.callbacks = callbacks
        response = agent.send_message(args.message)
        print(response)
        session_manager.save_session(session)
        return

    tui = TUI(agent, session, session_manager, provider_manager)
    tui.run()


def main():
    args = parse_args()

    # Если подкоманда — выполняем её
    if args.command:
        commands = {
            "providers": cmd_providers,
            "add-provider": cmd_add_provider,
            "remove-provider": cmd_remove_provider,
            "test-provider": cmd_test_provider,
        }
        handler = commands.get(args.command)
        if handler:
            handler(args)
        else:
            print(f"Неизвестная команда: {args.command}")
            sys.exit(1)
        return

    # Если нет подкоманды — запускаем чат
    cmd_chat(args)


if __name__ == "__main__":
    main()
