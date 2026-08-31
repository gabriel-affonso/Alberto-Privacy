from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(primary_key=True)
    gdpr_request_id: Mapped[int] = mapped_column(
        ForeignKey("gdpr_requests.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    rfc822_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    sender: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    gdpr_request = relationship("GdprRequest", back_populates="communications")
