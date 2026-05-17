from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MeetingSession:
    user_id: int
    session_id: str
    title: str | None = None
    audio_paths: list[Path] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def part_count(self) -> int:
        return len(self.audio_paths)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, MeetingSession] = {}

    def get(self, user_id: int) -> MeetingSession | None:
        return self._sessions.get(user_id)

    def start(self, user_id: int, title: str | None = None) -> MeetingSession:
        session = MeetingSession(
            user_id=user_id,
            session_id=uuid.uuid4().hex[:12],
            title=title,
        )
        self._sessions[user_id] = session
        return session

    def add_audio(self, user_id: int, path: Path) -> MeetingSession:
        session = self._sessions.get(user_id)
        if session is None:
            session = self.start(user_id)
        session.audio_paths.append(path)
        return session

    def clear(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)
