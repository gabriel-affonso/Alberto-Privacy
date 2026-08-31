from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    gdpr_request_id: Mapped[int] = mapped_column(
        ForeignKey("gdpr_requests.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    gdpr_request = relationship("GdprRequest", back_populates="evidence_items")

