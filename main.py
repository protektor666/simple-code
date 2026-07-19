"""
Simple Code — упрощённый аналог OpenCode.
Точка входа приложения.

Запуск:
    python main.py
    python main.py --provider anthropic --model claude-sonnet-4-20250514

Управление провайдерами:
    python main.py providers              # Список провайдеров
    python main.py add-provider           # Интерактивное добавление
    python main.py add-provider --name my-ollama --type ollama
    python main.py remove-provider my-ollama
    python main.py test-provider my-ollama
    python main.py use my-ollama
"""

import argparse
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config
from core.providers.factory import create_provider, get_default_model
from core.session import Session, SessionManager
from core.agent import Agent, AgentCallbacks
from core.provider_manager import ProviderManager, PROVIDER_TYPES
from core.tui import TUI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple Code — AI-ассистент для работы с кодом",
    )
    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # --- Чат (по умолчанию) ---
    chat_parser = subparsers.add_parser("chat", help="Запустить интерактивный чат")
    chat_parser.add_argument("-p", "--provider", default=None, help="LLM-провайдер")
    chat_parser.add_argument("-m", "--model", default=None, help="Модель LLM")
    chat_parser.add_argument("-c", "--config", default=None, help="Путь к конфигу")
    chat_parser.add_argument("-s", "--session", default=None, help="ID сессии")
    chat_parser.add_argument("--dir", default=None, help="Рабочая директория")
    chat_parser.add_argument("--message", default=None, help="Одноразовое сообщение")

    # --- Провайдеры ---
    providers_parser = subparsers.add_parser("providers", help="Список всех провайдеров")
    providers_parser.add_argument("--dir", default=None, help="Рабочая директория")

    add_parser = subparsers.add_parser("add-provider", help="Добавить провайдера")
    add_parser.add_argument("--name", default=None, help="Имя провайдера")
    add_parser.add_argument("--type", dest="provider_type", default=None, help=f"Тип: {', '.join(PROVIDER_TYPES.keys())}")
    add_parser.add_argument("--url", default=None, help="Base URL сервера")
    add_parser.add_argument("--api-key", default=None, help="API ключ")
    add_parser.add_argument("--model", default=None, help="Модель по умолчанию")
    add_parser.add_argument("--dir", default=None, help="Рабочая директория")

    remove_parser = subparsers.add_parser("remove-provider", help="Удалить провайдера")
    remove_parser.add_argument("name", help="Имя провайдера")
    remove_parser.add_argument("--dir", default=None, help="Рабочая директория")

    test_parser = subparsers.add_parser("test-provider", help="Проверить подключение")
    test_parser.add_argument("name", help="Имя провайдера")
    test_parser.add_argument("--dir", default=None, help="Рабочая директория")

    use_parser = subparsers.add_parser("use", help="Переключить провайдер")
    use_parser.add_argument("name", help="Имя провайдера")
    use_parser.add_argument("--dir", default=None, help="Рабочая директория")

    return parser.parse_args()


def _get_working_dir(args) -> str:
    return args.dir if hasattr(args, "dir") and args.dir else os.getcwd()


def cmd_providers(args):
    """Показать список всех провайдеров."""
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)
    providers = mgr.list_providers()

    if not providers:
        print("Нет добавленных провайдеров.")
        print("Используйте: python main.py add-provider")
        return

    print(f"\n{'Имя':<20} {'Тип':<12} {'URL':<40} {'Модель':<20}")
    print("-" * 92)
    for name, p in providers.items():
        url = p.base_url or "(по умолчанию)"
        model = p.default_model or "(Авто)"
        print(f"{name:<20} {p.provider_type:<12} {url:<40} {model:<20}")
    print()


def cmd_add_provider(args):
    """Добавить нового провайдера (CLI или интерактивно)."""
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)

    # Если все параметры указаны через CLI — добавляем без интерактива
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

    # Интерактивный режим
    print("\n=== Добавление нового провайдера ===\n")

    if not args.name:
        name = input("Имя провайдера (латиница): ").strip().lower().replace(" ", "-")
    else:
        name = args.name

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
        print(f"Доступные: {', '.join(PROVIDER_TYPES.keys())}")
        return

    is_local = provider_type in ("ollama", "lmstudio", "llamacpp", "vllm")

    if not args.url:
        if is_local:
            from core.provider_manager import _default_local_url
            default_url = _default_local_url(provider_type)
            base_url = input(f"URL сервера [{default_url}]: ").strip() or default_url
        else:
            base_url = input("Base URL (пусто = официальный API): ").strip()
    else:
        base_url = args.url

    if not args.api_key and not is_local:
        api_key = input("API ключ (пусто = без ключа): ").strip()
    else:
        api_key = args.api_key or ""

    if not args.model:
        default_model = input("Модель по умолчанию (пусто = авто): ").strip()
    else:
        default_model = args.model

    try:
        provider = mgr.add_provider(
            name=name,
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
        )
        print(f"\nПровайдер '{provider.name}' добавлен ({provider.provider_type})")
    except Exception as e:
        print(f"Ошибка: {e}")


def cmd_remove_provider(args):
    """Удалить провайдера."""
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
    """Проверить подключение к провайдеру."""
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


def cmd_use(args):
    """Переключить провайдер."""
    wd = _get_working_dir(args)
    mgr = ProviderManager(wd)
    mgr.sync_to_config  # Синхронизируем
    print(f"Активный провайдер: {args.name}")
    print(f"Для полного переключения запустите: python main.py chat --provider {args.name}")


def cmd_chat(args):
    """Запустить интерактивный чат."""
    cfg = load_config(args.config)

    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model
    if args.dir:
        cfg.working_dir = args.dir

    # Синхронизируем управляемых провайдеров
    provider_manager = ProviderManager(cfg.working_dir)
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
            model = args.model or get_default_model(cfg)
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

    # Если нет подкоманды — запускаем чат по умолчанию
    if not args.command:
        # Создаём фиктивный namespace для chat
        args = argparse.Namespace(
            command="chat",
            provider=None, model=None, config=None,
            session=None, dir=None, message=None,
        )
        cmd_chat(args)
        return

    commands = {
        "chat": cmd_chat,
        "providers": cmd_providers,
        "add-provider": cmd_add_provider,
        "remove-provider": cmd_remove_provider,
        "test-provider": cmd_test_provider,
        "use": cmd_use,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Неизвестная команда: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
