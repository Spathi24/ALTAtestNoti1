"""Telegram account -> existing Worker binding.

Identity is anchored on the stable ``telegram_user_id`` (NEVER the username,
which can change). Onboarding is an invite deep link:
``https://t.me/<bot>?start=<invite_token>`` -> the bot receives ``/start
<token>`` and binds that Telegram user to the Worker the PM invited.

A row with ``invite_token`` set but ``telegram_user_id`` null is a PENDING
invite; once the worker taps the link, the user id / chat id are filled and
``verified`` flips true.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class TelegramIdentity(Base, CanonicalMixin):
    worker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("worker.canonical_id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id = Column(String, nullable=True)  # stable identity anchor; null = pending
    telegram_chat_id = Column(String, nullable=True)  # private chat id for replies
    telegram_username = Column(String, nullable=True)
    telegram_first_name = Column(String, nullable=True)
    telegram_last_name = Column(String, nullable=True)
    telegram_phone = Column(String, nullable=True)

    verified = Column(Boolean, nullable=False, default=False)
    verified_method = Column(String, nullable=True)  # invite_token | contact_phone | manual_admin
    invite_token = Column(String, nullable=True)  # set while a binding is pending

    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
