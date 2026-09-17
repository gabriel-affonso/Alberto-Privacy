from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramApproval(Base):
    """One-time Telegram confirmation gate for an outbound email request."""

    __tablename__ = "telegram_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    gdpr_request_id: Mapped[int] = mapped_column(ForeignKey("gdpr_requests.id"), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_message_id: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TelegramBotState(Base):
    __tablename__ = "telegram_bot_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    update_offset: Mapped[int] = mapped_column(nullable=False, default=0)
