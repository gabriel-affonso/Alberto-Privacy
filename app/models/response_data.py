from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResponseFile(Base):
    __tablename__ = "response_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("privacy_cases.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    privacy_case = relationship("PrivacyCase", back_populates="response_files")


class _FindingBase:
    id: Mapped[int] = mapped_column(primary_key=True)
    response_file_id: Mapped[int] = mapped_column(ForeignKey("response_files.id"), index=True)
    value_redacted: Mapped[str | None] = mapped_column(Text)
    value_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    excerpt: Mapped[str | None] = mapped_column(Text)
    position: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    extraction_method: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PersonalDataItem(_FindingBase, Base):
    __tablename__ = "personal_data_items"
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)


class DataSource(_FindingBase, Base):
    __tablename__ = "data_sources"


class DataRecipient(_FindingBase, Base):
    __tablename__ = "data_recipients"


class ProfilingItem(_FindingBase, Base):
    __tablename__ = "profiling_items"


class AdvertisingData(_FindingBase, Base):
    __tablename__ = "advertising_data"


class Device(_FindingBase, Base):
    __tablename__ = "devices"


class Location(_FindingBase, Base):
    __tablename__ = "locations"


class Identifier(_FindingBase, Base):
    __tablename__ = "identifiers"
    identifier_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)


class DataTransfer(_FindingBase, Base):
    __tablename__ = "data_transfers"


class RetentionInformation(_FindingBase, Base):
    __tablename__ = "retention_information"


class AutomatedDecisionInformation(_FindingBase, Base):
    __tablename__ = "automated_decision_information"


class ProvenanceEntity(Base):
    __tablename__ = "provenance_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(500))
    value_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProvenanceRelation(Base):
    __tablename__ = "provenance_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_entity_id: Mapped[int] = mapped_column(ForeignKey("provenance_entities.id"), index=True)
    to_entity_id: Mapped[int] = mapped_column(ForeignKey("provenance_entities.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    response_file_id: Mapped[int] = mapped_column(ForeignKey("response_files.id"), index=True)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
