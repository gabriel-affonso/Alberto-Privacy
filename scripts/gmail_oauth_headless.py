#!/usr/bin/env python3
"""Authorize Gmail read-only access from a headless NUC/container.

This helper uses Google's supported loopback redirect for an installed/desktop OAuth
client, but does not require the callback HTTP request to reach the NUC. Open the
printed authorization URL on any browser, complete consent, let the browser fail to
open localhost, then copy the *entire* localhost URL from the address bar back into
this prompt. The authorization code is exchanged by this process and the resulting
refreshable token is stored at GMAIL_OAUTH_TOKEN_FILE.

No email is read or sent by this script.
"""

from __future__ import annotations

import os
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.config import get_settings
from app.gmail_discovery.constants import GMAIL_READONLY_SCOPE


def parse_args():
    parser = ArgumentParser(description="Create a Gmail read-only OAuth token on a headless host.")
    parser.add_argument(
        "--redirect-port",
        type=int,
        default=8765,
        help="Loopback redirect port embedded in the OAuth request (default: 8765).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1024 <= args.redirect_port <= 65535:
        raise SystemExit("--redirect-port must be between 1024 and 65535")

    settings = get_settings()
    client_file = Path(settings.gmail_oauth_client_secrets_file)
    token_file = Path(settings.gmail_oauth_token_file)

    if not client_file.exists():
        raise SystemExit(f"OAuth client JSON not found: {client_file}")

    redirect_uri = f"http://localhost:{args.redirect_port}/"
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file),
        scopes=[GMAIL_READONLY_SCOPE],
        redirect_uri=redirect_uri,
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    print("\nGmail read-only authorization")
    print("================================")
    print("1. Open this URL in your phone/computer browser:\n")
    print(authorization_url)
    print("\n2. Sign in and approve access.")
    print(
        f"3. Google will redirect to {redirect_uri} . On a different device that page "
        "will probably fail to load; that is expected."
    )
    print("4. Copy the ENTIRE URL from the browser address bar, including ?code=... and ?state=... .")
    redirected_url = input("\nPaste the redirected localhost URL here:\n> ").strip()

    if not redirected_url.startswith(redirect_uri):
        raise SystemExit(
            f"Expected a redirected URL beginning with {redirect_uri!r}; got {redirected_url!r}"
        )
    if "code=" not in redirected_url or "state=" not in redirected_url:
        raise SystemExit("The pasted URL does not contain both OAuth code and state parameters")

    # oauthlib rejects plain HTTP by default. Google's installed-app OAuth flow
    # explicitly permits loopback redirects such as http://localhost:<port>/.
    # Enable the exception only for this validated loopback token exchange and
    # restore the process environment immediately afterwards.
    previous_insecure_transport = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    try:
        flow.fetch_token(authorization_response=redirected_url)
    finally:
        if previous_insecure_transport is None:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        else:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = previous_insecure_transport

    credentials = flow.credentials

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    try:
        token_file.chmod(0o600)
    except OSError:
        pass

    print(f"\nSuccess. Gmail read-only token written to: {token_file}")
    print("No Gmail messages were read and no email was sent by this authorization helper.")


if __name__ == "__main__":
    main()
