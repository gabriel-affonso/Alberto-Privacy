from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import Settings
from app.gmail_discovery.constants import GMAIL_READONLY_SCOPE
from app.gmail_discovery.parser import extract_header, parse_message_date
from app.gmail_discovery.types import GmailMessageMetadata


class GmailDiscoveryConfigError(RuntimeError):
    pass


class GoogleGmailClient:
    def __init__(self, service: Any) -> None:
        self.service = service

    def search_message_ids(self, query: str, max_results: int) -> list[str]:
        message_ids: list[str] = []
        page_token: str | None = None

        while len(message_ids) < max_results:
            response = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=min(100, max_results - len(message_ids)),
                    pageToken=page_token,
                )
                .execute()
            )
            message_ids.extend(message["id"] for message in response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return message_ids

    def get_message_metadata(self, message_id: str, matched_query: str) -> GmailMessageMetadata:
        response = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = response.get("payload", {}).get("headers", [])
        date = parse_message_date(extract_header(headers, "Date"), response.get("internalDate"))
        return GmailMessageMetadata(
            message_id=message_id,
            sender=extract_header(headers, "From"),
            subject=extract_header(headers, "Subject"),
            date=date,
            matched_query=matched_query,
        )


def build_google_gmail_client(settings: Settings) -> GoogleGmailClient:
    credentials_path = Path(settings.gmail_oauth_client_secrets_file)
    token_path = Path(settings.gmail_oauth_token_file)

    if not credentials_path.exists():
        raise GmailDiscoveryConfigError(
            f"Gmail OAuth client secrets file not found: {credentials_path}"
        )

    credentials: Credentials | None = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_path), scopes=[GMAIL_READONLY_SCOPE]
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), scopes=[GMAIL_READONLY_SCOPE]
        )
        credentials = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")

    from googleapiclient.discovery import build

    return GoogleGmailClient(build("gmail", "v1", credentials=credentials))

