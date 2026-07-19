"""
Модуль сессий — сохранение и восстановление истории разговоров.
Сессии хранятся как JSON-файлы в директории .simplecode/sessions/.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class Message:
    """Одно сообщение в чате."""
    role: str            # "user" или "assistant"
    content: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Session:
    """
    Сессия разговора.
    Содержит историю сообщений и метаданные.
    """
    id: str = ""
    title: str = ""
    created_at: str = ""
    updated_at: str = ""
    messages: list[Message] = field(default_factory=list)
    model: str = ""
    provider: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def add_message(self, message: Message):
        """Добавляет сообщение в сессию."""
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

        # Автоматическое название из первого сообщения пользователя
        if not self.title:
            for msg in self.messages:
                if msg.role == "user":
                    self.title = msg.content[:80].replace("\n", " ")
                    break

    def to_dict(self) -> dict:
        """Конвертирует сессию в словарь для JSON."""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "provider": self.provider,
            "messages": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Создаёт сессию из словаря."""
        messages = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=m.get("timestamp", ""),
            )
            for m in data.get("messages", [])
        ]
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            messages=messages,
            model=data.get("model", ""),
            provider=data.get("provider", ""),
        )


class SessionManager:
    """
    Управляет сессиями: создаёт, загружает, сохраняет, список.
    """

    def __init__(self, sessions_dir: str):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Путь к файлу сессии."""
        return self.sessions_dir / f"{session_id}.json"

    def create_session(
        self,
        model: str = "",
        provider: str = "",
    ) -> Session:
        """Создаёт новую сессию."""
        session = Session(model=model, provider=provider)
        self.save_session(session)
        return session

    def save_session(self, session: Session):
        """Сохраняет сессию в JSON-файл."""
        path = self._session_path(session.id)
        data = session.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_session(self, session_id: str) -> Session | None:
        """Загружает сессию по ID."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception:
            return None

    def list_sessions(self) -> list[dict]:
        """Возвращает список всех сессий (метаданные без сообщений)."""
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get("id", ""),
                    "title": data.get("title", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "model": data.get("model", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                continue
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Удаляет сессию."""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
