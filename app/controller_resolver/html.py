from html.parser import HTMLParser
from urllib.parse import urljoin


class PrivacyHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.links: list[str] = []
        self._in_title = False
        self._skip_depth = 0
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if normalized_tag == "title":
            self._in_title = True
            return
        if normalized_tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if normalized_tag == "title":
            self._in_title = False
            return
        if normalized_tag in {"p", "div", "li", "br", "h1", "h2", "h3", "section"}:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title:
            self.title = f"{self.title} {cleaned}".strip()
        if self._skip_depth == 0:
            self._text_parts.append(cleaned)

    @property
    def text(self) -> str:
        return "\n".join(line.strip() for line in " ".join(self._text_parts).splitlines() if line.strip())


def parse_html(base_url: str, html: str) -> tuple[str, str, list[str]]:
    parser = PrivacyHtmlParser(base_url)
    parser.feed(html)
    return parser.title, parser.text, parser.links

