"""Human-in-the-loop browser preparation for privacy portals.

This module deliberately never bypasses authentication, CAPTCHA, MFA, or identity checks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PortalPreview:
    url: str
    captured_at: datetime
    screenshot_path: str | None
    html_excerpt: str
    requires_user_action: bool = False


class BasePrivacyPortal(ABC):
    @abstractmethod
    def detect(self) -> bool: ...

    @abstractmethod
    def open(self) -> None: ...

    def authenticate(self) -> None:
        """Adapters must pause for the user; credentials and MFA are never automated."""
        raise UserActionRequired("Authentication requires user action")

    @abstractmethod
    def navigate_to_request(self) -> None: ...

    @abstractmethod
    def fill_request(self, subject: str, body: str) -> None: ...

    @abstractmethod
    def review(self) -> PortalPreview: ...

    def submit(self, approved: bool) -> PortalPreview:
        if not approved:
            raise PermissionError("Explicit user approval is required before submission")
        return self.capture_confirmation()

    @abstractmethod
    def capture_confirmation(self) -> PortalPreview: ...


class UserActionRequired(RuntimeError):
    pass


class GenericPrivacyPortal(BasePrivacyPortal):
    """Reference adapter for a preselected request URL; it only prepares a preview."""

    def __init__(self, request_url: str, evidence_dir: Path | None = None) -> None:
        self.request_url = request_url
        self.evidence_dir = evidence_dir
        self._opened = False
        self._filled = False

    def detect(self) -> bool:
        return bool(self.request_url.startswith(("https://", "http://")))

    def open(self) -> None:
        if not self.detect():
            raise ValueError("A valid portal URL is required")
        self._opened = True

    def navigate_to_request(self) -> None:
        if not self._opened:
            raise RuntimeError("Portal is not open")

    def fill_request(self, subject: str, body: str) -> None:
        if not self._opened or not subject or not body:
            raise RuntimeError("Portal must be open and request content must be present")
        self._filled = True

    def review(self) -> PortalPreview:
        if not self._filled:
            raise RuntimeError("Request has not been filled")
        return PortalPreview(self.request_url, datetime.now(timezone.utc), None, "Prepared request preview")

    def capture_confirmation(self) -> PortalPreview:
        return PortalPreview(self.request_url, datetime.now(timezone.utc), None, "Submission confirmation not captured")


class PlaywrightPrivacyPortal(GenericPrivacyPortal):
    """Optional browser-backed generic adapter.

    It navigates and captures evidence, but deliberately has no generic submit implementation:
    sites differ too much for a safe blind submission.
    """

    def __init__(self, request_url: str, evidence_dir: Path | None = None) -> None:
        super().__init__(request_url, evidence_dir)
        self._playwright = self._browser = self._page = None

    def open(self) -> None:
        super().open()
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=False)
            self._page = self._browser.new_page()
            self._page.goto(self.request_url, wait_until="domcontentloaded")
        except Exception as exc:
            self.close()
            raise RuntimeError("Browser portal could not be opened; install Playwright browsers and retry") from exc

    def review(self) -> PortalPreview:
        preview = super().review()
        screenshot_path = None
        html = preview.html_excerpt
        if self._page:
            if self.evidence_dir:
                self.evidence_dir.mkdir(parents=True, exist_ok=True)
                screenshot = self.evidence_dir / "portal-preview.png"
                self._page.screenshot(path=str(screenshot), full_page=True)
                screenshot_path = str(screenshot)
            html = self._page.content()[:2000]
        return PortalPreview(preview.url, preview.captured_at, screenshot_path, html)

    def submit(self, approved: bool) -> PortalPreview:
        if not approved:
            raise PermissionError("Explicit user approval is required before submission")
        raise UserActionRequired("A site-specific adapter is required to submit; no generic submit button is clicked")

    def close(self) -> None:
        if self._browser: self._browser.close()
        if self._playwright: self._playwright.stop()
        self._browser = self._playwright = self._page = None
