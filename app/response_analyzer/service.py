"""Safe, deterministic first-pass ingestion for supplied DSAR response files."""

import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.response_data import (
    AdvertisingData, AutomatedDecisionInformation, DataRecipient, DataSource, Identifier,
    PersonalDataItem, ProfilingItem, ResponseFile, RetentionInformation,
)

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+?[0-9][0-9 ()-]{6,}[0-9]")
KEYWORD_MODELS = {
    "source": DataSource, "recipient": DataRecipient, "profil": ProfilingItem,
    "advertis": AdvertisingData, "retention": RetentionInformation,
    "automated decision": AutomatedDecisionInformation,
}


def ingest_response(db: Session, case_id: int, filename: str, content: bytes, media_type: str | None, settings: Settings) -> list[ResponseFile]:
    if not content:
        raise ValueError("The uploaded file is empty")
    if len(content) > settings.privacy_max_upload_bytes:
        raise ValueError("The uploaded file exceeds the configured limit")
    stored = [_store_file(db, case_id, filename, content, media_type, settings)]
    if _is_zip(filename, content):
        for member_name, member_content in _safe_zip_members(content, settings):
            stored.append(_store_file(db, case_id, member_name, member_content, None, settings))
    for response_file in stored:
        if response_file.original_name.lower().endswith(".zip"):
            continue
        _extract_findings(db, response_file, _extract_text(response_file.storage_path, response_file.original_name))
    db.commit()
    return stored


def _store_file(db: Session, case_id: int, filename: str, content: bytes, media_type: str | None, settings: Settings) -> ResponseFile:
    safe_name = Path(filename).name or "response.bin"
    root = Path(settings.privacy_data_root).resolve()
    directory = (root / str(case_id) / "incoming").resolve()
    if root not in directory.parents:
        raise ValueError("Invalid response storage path")
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    target = directory / f"{digest[:12]}-{safe_name}"
    target.write_bytes(content)
    response_file = ResponseFile(case_id=case_id, original_name=safe_name, media_type=media_type, storage_path=str(target), sha256=digest, size_bytes=len(content))
    db.add(response_file)
    db.flush()
    return response_file


def _is_zip(filename: str, content: bytes) -> bool:
    return filename.lower().endswith(".zip") or content.startswith(b"PK\x03\x04")


def _safe_zip_members(content: bytes, settings: Settings) -> list[tuple[str, bytes]]:
    result: list[tuple[str, bytes]] = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > settings.privacy_max_zip_members:
            raise ValueError("ZIP contains too many files")
        for info in infos:
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts or info.is_dir():
                raise ValueError("Unsafe ZIP member path")
            if info.filename.lower().endswith((".zip", ".tar", ".gz", ".7z")):
                raise ValueError("Nested archives are not accepted")
            total += info.file_size
            if total > settings.privacy_max_zip_uncompressed_bytes:
                raise ValueError("ZIP expands beyond the configured limit")
            result.append((member.name, archive.read(info)))
    return result


def _extract_text(path: str, filename: str) -> str:
    raw = Path(path).read_bytes()
    lower = filename.lower()
    if lower.endswith(".json"):
        try:
            return json.dumps(json.loads(raw.decode("utf-8")), ensure_ascii=False)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
    if lower.endswith(".csv"):
        return _csv_text(raw)
    if lower.endswith((".txt", ".html", ".htm")):
        return raw.decode("utf-8", errors="replace")
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            return ""
    return ""


def _csv_text(raw: bytes) -> str:
    try:
        rows = csv.reader(io.StringIO(raw.decode("utf-8", errors="replace")))
        return "\n".join(" | ".join(row) for row in rows)
    except csv.Error:
        return ""


def _extract_findings(db: Session, response_file: ResponseFile, text: str) -> None:
    if not text:
        return
    for label, pattern in (("email", EMAIL), ("phone", PHONE)):
        for match in pattern.finditer(text):
            value = match.group(0)
            _add_identifier(db, response_file, label, value, text, match.start())
    for marker, model in KEYWORD_MODELS.items():
        match = re.search(marker, text, flags=re.IGNORECASE)
        if match:
            excerpt = _excerpt(text, match.start())
            db.add(model(response_file_id=response_file.id, value_redacted=_redact(excerpt), value_hash=_hash(excerpt), excerpt=excerpt[:1000], position=str(match.start()), confidence=0.7, extraction_method="keyword"))
            db.add(PersonalDataItem(response_file_id=response_file.id, category=marker, value_redacted=_redact(excerpt), value_hash=_hash(excerpt), excerpt=excerpt[:1000], position=str(match.start()), confidence=0.7, extraction_method="keyword"))


def _add_identifier(db: Session, response_file: ResponseFile, identifier_type: str, value: str, text: str, position: int) -> None:
    excerpt = _excerpt(text, position)
    db.add(Identifier(response_file_id=response_file.id, identifier_type=identifier_type, value_redacted=_redact(value), value_hash=_hash(value), excerpt=excerpt, position=str(position), confidence=0.95, extraction_method="regex"))
    db.add(PersonalDataItem(response_file_id=response_file.id, category=identifier_type, value_redacted=_redact(value), value_hash=_hash(value), excerpt=excerpt, position=str(position), confidence=0.95, extraction_method="regex"))


def _redact(value: str) -> str:
    return value[:2] + "…" + value[-2:] if len(value) > 4 else "…"


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _excerpt(text: str, position: int) -> str:
    return " ".join(text[max(0, position - 120):position + 240].split())[:1000]
