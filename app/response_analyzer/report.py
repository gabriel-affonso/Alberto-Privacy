from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.gdpr_request_generator.service import ARTICLE_15_ITEMS
from app.models.response_data import (
    AdvertisingData, AutomatedDecisionInformation, DataRecipient, DataSource, Identifier,
    PersonalDataItem, ResponseFile,
)


def case_report(db: Session, case_id: int) -> dict[str, object]:
    files = list(db.scalars(select(ResponseFile).where(ResponseFile.case_id == case_id)).all())
    categories = list(db.execute(select(PersonalDataItem.category, func.count(PersonalDataItem.id)).join(ResponseFile).where(ResponseFile.case_id == case_id).group_by(PersonalDataItem.category)).all())
    category_names = {name for name, _ in categories}
    requested = {
        "sources": "source" in category_names,
        "recipients": "recipient" in category_names,
        "profiling": "profil" in category_names,
        "advertising": "advertis" in category_names,
        "retention": "retention" in category_names,
        "automated decision-making": "automated decision" in category_names,
    }
    missing = [f"Requested information about {name} was not identified in the supplied response." for name, found in requested.items() if not found]
    return {
        "case_id": case_id,
        "files_received": [{"id": item.id, "name": item.original_name, "sha256": item.sha256, "size_bytes": item.size_bytes} for item in files],
        "categories": [{"name": name, "count": count} for name, count in categories],
        "identifier_count": _count(db, Identifier, files),
        "sources_count": _count(db, DataSource, files),
        "recipients_count": _count(db, DataRecipient, files),
        "advertising_data_count": _count(db, AdvertisingData, files),
        "automated_decision_count": _count(db, AutomatedDecisionInformation, files),
        "requested_items": ARTICLE_15_ITEMS,
        "points_not_identified": missing,
        "confidence": 0.7 if files else 0.0,
    }


def _count(db: Session, model, files: list[ResponseFile]) -> int:
    ids = [item.id for item in files]
    if not ids:
        return 0
    return int(db.scalar(select(func.count(model.id)).where(model.response_file_id.in_(ids))) or 0)
