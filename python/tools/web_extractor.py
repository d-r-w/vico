from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import List, Sequence
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

DEFAULT_VIEWPORT = {"width": 1280, "height": 1400}
DEFAULT_NAVIGATION_TIMEOUT_MS = 30000
DEFAULT_SETTLE_TIMEOUT_MS = 5000
DEFAULT_SETTLE_DELAY_MS = 1200
DEFAULT_HEADERS_FILE = Path(__file__).resolve().parents[2] / "data" / "web_headers.txt"
DEFAULT_COOKIES_FILE = Path(__file__).resolve().parents[2] / "data" / "web_cookies.txt"


@dataclass(frozen=True)
class PageSegment:
    index: int
    scroll_y: int
    text: str
    media_urls: List[str]


@dataclass(frozen=True)
class WebExtractionResult:
    url: str
    title: str
    segments: List[PageSegment]

    def render_text(self) -> str:
        lines = [
            f"URL: {self.url}",
            f"Title: {self.title or 'Untitled'}",
            "",
        ]

        merged_lines = _unique_lines(segment.text for segment in self.segments)
        merged_media_urls = _unique_items(url for segment in self.segments for url in segment.media_urls)

        for segment in self.segments:
            lines.extend(
                [
                    f"[Segment {segment.index}]",
                    f"Scroll Y: {segment.scroll_y}",
                    "Text:",
                    segment.text or "[No visible text found]",
                    "",
                    "Media URLs:",
                ]
            )

            if segment.media_urls:
                lines.extend(f"- {url}" for url in segment.media_urls)
            else:
                lines.append("[No media URLs found]")

            lines.append("")

        lines.extend(
            [
                "[Merged Content]",
                "\n".join(merged_lines) or "[No visible text found]",
                "",
                "[Merged Media URLs]",
            ]
        )

        if merged_media_urls:
            lines.extend(f"- {url}" for url in merged_media_urls)
        else:
            lines.append("[No media URLs found]")

        return "\n".join(lines).strip()


@dataclass(frozen=True)
class DomainNameValueRule:
    domain: str
    name: str
    value: str
    line_number: int


def extract_webpage_content(
    url: str,
    *,
    max_pages: int = 3,
) -> str:
    if not url:
        raise ValueError("url is required")

    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            extra_http_headers=_resolve_headers_for_url(url),
        )

        cookies = _resolve_cookies_for_url(url)
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_NAVIGATION_TIMEOUT_MS)
            _wait_for_page_settle(page)

            segments: List[PageSegment] = []
            for index in range(1, max_pages + 1):
                segments.append(_extract_segment(page, index))
                if index == max_pages or not _scroll_to_next_viewport(page):
                    break
                _wait_for_page_settle(page)

            result = WebExtractionResult(url=page.url, title=page.title(), segments=segments)
            return result.render_text()
        finally:
            context.close()
            browser.close()


def _resolve_headers_for_url(url: str, file_path: Path = DEFAULT_HEADERS_FILE) -> dict[str, str]:
    headers: dict[str, str] = {}
    for rule in _get_matching_domain_name_value_rules(url, file_path, rule_label="web header"):
        headers[rule.name] = rule.value

    return headers


def _resolve_cookies_for_url(url: str, file_path: Path = DEFAULT_COOKIES_FILE) -> list[dict[str, str]]:
    cookies_by_name: dict[str, dict[str, str]] = {}
    for rule in _get_matching_domain_name_value_rules(url, file_path, rule_label="web cookie"):
        cookies_by_name[rule.name] = {
            "name": rule.name,
            "value": rule.value,
            "domain": rule.domain,
            "path": "/",
        }

    return list(cookies_by_name.values())


def _get_matching_domain_name_value_rules(
    url: str,
    file_path: Path,
    *,
    rule_label: str,
) -> list[DomainNameValueRule]:
    hostname = urlparse(url).hostname
    if not hostname:
        return []

    normalized_host = hostname.strip().lower().rstrip(".")
    matching_rules = [
        rule
        for rule in _load_domain_name_value_rules(file_path, rule_label=rule_label)
        if _host_matches_domain(normalized_host, rule.domain)
    ]

    # Apply broader rules first so more specific domains can override them.
    matching_rules.sort(key=lambda rule: (rule.domain.count("."), len(rule.domain), rule.line_number))
    return matching_rules


def _load_domain_name_value_rules(
    file_path: Path,
    *,
    rule_label: str,
) -> list[DomainNameValueRule]:
    if not file_path.exists():
        return []

    rules: list[DomainNameValueRule] = []
    for line_number, raw_line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in raw_line.split("|", 2)]
        if len(parts) != 3:
            logger.warning(
                "Skipping malformed %s rule on line %s in %s",
                rule_label,
                line_number,
                file_path,
            )
            continue

        domain, name, value = parts
        normalized_domain = domain.lower().rstrip(".")
        if not normalized_domain or not name:
            logger.warning(
                "Skipping incomplete %s rule on line %s in %s",
                rule_label,
                line_number,
                file_path,
            )
            continue

        rules.append(
            DomainNameValueRule(
                domain=normalized_domain,
                name=name,
                value=value,
                line_number=line_number,
            )
        )

    return rules


def _host_matches_domain(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _wait_for_page_settle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=DEFAULT_SETTLE_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(DEFAULT_SETTLE_DELAY_MS)


def _extract_segment(page, index: int) -> PageSegment:
    payload = page.evaluate(
        """
        () => {
          const normalizeText = (value) => value.replace(/\\s+/g, " ").trim();

          const isVisible = (element) => {
            if (!element) {
              return false;
            }

            const style = window.getComputedStyle(element);
            if (
              style.display === "none" ||
              style.visibility === "hidden" ||
              Number.parseFloat(style.opacity || "1") === 0
            ) {
              return false;
            }

            const rect = element.getBoundingClientRect();
            if (rect.width < 1 || rect.height < 1) {
              return false;
            }

            return rect.bottom > 0 && rect.top < window.innerHeight;
          };

          const absoluteUrl = (value) => {
            if (!value) {
              return null;
            }

            try {
              return new URL(value, document.baseURI).href;
            } catch (error) {
              return null;
            }
          };

          const textSnippets = [];
          const seenText = new Set();
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);

          while (walker.nextNode()) {
            const node = walker.currentNode;
            const parent = node.parentElement;
            const text = normalizeText(node.textContent || "");

            if (!text || !parent || !isVisible(parent) || seenText.has(text)) {
              continue;
            }

            seenText.add(text);
            textSnippets.push(text);
          }

          const mediaUrls = [];
          const seenMedia = new Set();
          const mediaSelectors = [
            "img[src]",
            "video[src]",
            "video[poster]",
            "audio[src]",
            "source[src]",
            "a[href]"
          ];

          for (const element of document.querySelectorAll(mediaSelectors.join(","))) {
            const candidate =
              element.currentSrc ||
              element.getAttribute("src") ||
              element.getAttribute("poster") ||
              element.getAttribute("href");

            const url = absoluteUrl(candidate);
            if (!url || seenMedia.has(url)) {
              continue;
            }

            if (element.tagName === "A") {
              const pathname = new URL(url).pathname.toLowerCase();
              const looksLikeFile = /\\.(pdf|png|jpe?g|gif|webp|svg|mp4|webm|mp3|wav|m4a)$/i.test(pathname);
              if (!looksLikeFile) {
                continue;
              }
            } else if (!isVisible(element)) {
              continue;
            }

            seenMedia.add(url);
            mediaUrls.push(url);
          }

          return {
            scrollY: Math.round(window.scrollY),
            text: textSnippets.join("\\n"),
            mediaUrls
          };
        }
        """
    )

    text = str(payload.get("text", "")).strip()
    media_urls = [url for url in payload.get("mediaUrls", []) if isinstance(url, str) and url]

    return PageSegment(
        index=index,
        scroll_y=int(payload.get("scrollY", 0)),
        text=text,
        media_urls=media_urls,
    )


def _scroll_to_next_viewport(page) -> bool:
    payload = page.evaluate(
        """
        () => {
          const before = Math.round(window.scrollY);
          window.scrollBy(0, window.innerHeight);
          const after = Math.round(window.scrollY);
          const maxScroll = Math.max(
            0,
            Math.round(document.documentElement.scrollHeight - window.innerHeight)
          );

          return {
            before,
            after,
            moved: after > before,
            atEnd: after >= maxScroll
          };
        }
        """
    )

    return bool(payload.get("moved")) and not bool(payload.get("atEnd") and payload.get("after") == payload.get("before"))


def _unique_lines(text_blocks: Sequence[str]) -> List[str]:
    lines: List[str] = []
    seen: set[str] = set()

    for block in text_blocks:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            lines.append(line)

    return lines


def _unique_items(items) -> List[str]:
    values: List[str] = []
    seen: set[str] = set()

    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        values.append(item)

    return values
