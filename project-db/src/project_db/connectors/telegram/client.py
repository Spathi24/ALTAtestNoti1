"""Telegram Bot API client (telebot, sync) behind a small interface.

The intake logic works on NORMALISED update dicts so it's transport-agnostic and
testable with ``MockTelegramClient`` (no network). The real client wraps
``telebot.TeleBot`` and converts its Update objects to the same dict shape.

Normalised update::

    {"update_id": int, "message": {message_id, chat_id, from_id, from_username,
     from_first_name, from_last_name, text, date} | None}
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class TelegramClientError(RuntimeError):
    pass


def _normalise_update(u: Any) -> dict[str, Any]:
    """telebot.types.Update -> normalised dict (message-only; other kinds -> None)."""
    msg = getattr(u, "message", None) or getattr(u, "edited_message", None)
    cb = getattr(u, "callback_query", None)
    norm_msg = None
    norm_cb = None
    if msg is not None:
        frm = getattr(msg, "from_user", None)
        norm_msg = {
            "message_id": getattr(msg, "message_id", None),
            "chat_id": getattr(getattr(msg, "chat", None), "id", None),
            "from_id": getattr(frm, "id", None),
            "from_username": getattr(frm, "username", None),
            "from_first_name": getattr(frm, "first_name", None),
            "from_last_name": getattr(frm, "last_name", None),
            "text": getattr(msg, "text", None) or getattr(msg, "caption", None),
            "date": getattr(msg, "date", None),
        }
    if cb is not None:
        frm = getattr(cb, "from_user", None)
        cb_msg = getattr(cb, "message", None)
        norm_cb = {
            "id": getattr(cb, "id", None),
            "data": getattr(cb, "data", None),
            "from": {
                "id": getattr(frm, "id", None),
                "username": getattr(frm, "username", None),
                "first_name": getattr(frm, "first_name", None),
                "last_name": getattr(frm, "last_name", None),
            },
            "message": {
                "message_id": getattr(cb_msg, "message_id", None),
                "chat_id": getattr(getattr(cb_msg, "chat", None), "id", None),
                "date": getattr(cb_msg, "date", None),
            }
            if cb_msg is not None
            else None,
        }
    raw_update = None
    for attr in ("to_dict", "to_json"):
        fn = getattr(u, attr, None)
        if not callable(fn):
            continue
        try:
            raw_update = fn()
            if isinstance(raw_update, str):
                raw_update = json.loads(raw_update)
            break
        except Exception:
            raw_update = None
    return {
        "update_id": getattr(u, "update_id", None),
        "message": norm_msg,
        "callback_query": norm_cb,
        "raw_update": raw_update,
    }


class BaseTelegramClient(ABC):
    @abstractmethod
    def get_me(self) -> dict[str, Any]:
        """Return {id, username, first_name} for the bot (verifies the token)."""

    @abstractmethod
    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        """One-shot poll: normalised updates with update_id >= offset."""

    @abstractmethod
    def send_message(self, chat_id: Any, text: str) -> None:
        """Send a reply to a chat (best-effort)."""


class TelegramClient(BaseTelegramClient):
    """Real client wrapping telebot.TeleBot. Token from TELEGRAM_BOT_TOKEN."""

    def __init__(self, token: str | None = None) -> None:
        tok = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not tok:
            raise TelegramClientError(
                "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather and put the "
                "token in .env."
            )
        try:
            import telebot
        except ImportError as exc:  # pragma: no cover
            raise TelegramClientError(
                'pyTelegramBotAPI not installed. Run: pip install -e ".[telegram]"'
            ) from exc
        # threaded=False: we drive it one-shot from a sync poller, not its own loop.
        self._bot = telebot.TeleBot(tok, threaded=False)

    def get_me(self) -> dict[str, Any]:
        me = self._bot.get_me()
        return {"id": me.id, "username": me.username, "first_name": me.first_name}

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        # timeout=0 -> short poll (return immediately); we control cadence externally.
        updates = self._bot.get_updates(offset=offset, timeout=0, long_polling_timeout=0)
        return [_normalise_update(u) for u in updates]

    def send_message(self, chat_id: Any, text: str) -> None:
        try:
            self._bot.send_message(chat_id, text)
        except Exception:
            # A reply failure must never abort ingestion (the DB write already happened).
            pass


class MockTelegramClient(BaseTelegramClient):
    """In-memory test double. Pre-load ``updates`` (normalised dicts);
    ``sent`` collects (chat_id, text) replies."""

    def __init__(
        self,
        updates: list[dict[str, Any]] | None = None,
        *,
        username: str = "alta_labour_bot",
    ) -> None:
        self._updates = list(updates or [])
        self._username = username
        self.sent: list[tuple[Any, str]] = []

    def get_me(self) -> dict[str, Any]:
        return {"id": 1, "username": self._username, "first_name": "ALTA"}

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        if offset is None:
            return list(self._updates)
        return [u for u in self._updates if (u.get("update_id") or 0) >= offset]

    def send_message(self, chat_id: Any, text: str) -> None:
        self.sent.append((chat_id, text))
