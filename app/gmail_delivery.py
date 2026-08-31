import base64
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Protocol

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import Settings

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailSender(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> dict[str, Any]: ...


class GoogleGmailSender:
    def __init__(self, service: Any, sender_email: str) -> None:
        self.service = service
        self.sender_email = sender_email

    def send(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        message = MIMEText(body, "plain", "utf-8")
        message["To"] = recipient
        message["From"] = self.sender_email
        message["Subject"] = subject
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = self.service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        result["rfc822"] = message.as_bytes()
        return result


def build_google_gmail_sender(settings: Settings) -> GoogleGmailSender:
    secrets = Path(settings.gmail_oauth_client_secrets_file)
    token = Path(settings.gmail_oauth_send_token_file)
    if not secrets.exists():
        raise RuntimeError(f"Gmail OAuth client secrets file not found: {secrets}")
    credentials: Credentials | None = None
    if token.exists():
        credentials = Credentials.from_authorized_user_file(str(token), scopes=[GMAIL_SEND_SCOPE])
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid or GMAIL_SEND_SCOPE not in credentials.scopes:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes=[GMAIL_SEND_SCOPE])
        credentials = flow.run_local_server(port=0)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credentials.to_json(), encoding="utf-8")
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()
    return GoogleGmailSender(service, profile["emailAddress"])
