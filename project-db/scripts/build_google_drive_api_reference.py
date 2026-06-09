import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urldefrag

import requests
from bs4 import BeautifulSoup

START_URLS = [
    "https://developers.google.com/workspace/drive/api/guides/about-sdk",
    "https://developers.google.com/workspace/drive/api/reference/rest/v3",
]

ALLOWED_PREFIXES = (
    "https://developers.google.com/workspace/drive/api/guides/",
    "https://developers.google.com/workspace/drive/api/reference/rest/v3",
)

EXCLUDE_PATTERNS = (
    "/samples/",
    "/support",
    "/mcp",
    "/terms",
    "/privacy",
    "/feedback",
)

OUT = Path("docs/google-drive-api-reference-all.md")


def clean_url(url: str) -> str:
    url, _frag = urldefrag(url)
    return url.rstrip("/")


def allowed(url: str) -> bool:
    url = clean_url(url)

    if not url.startswith(ALLOWED_PREFIXES):
        return False

    lowered = url.lower()

    if any(pattern in lowered for pattern in EXCLUDE_PATTERNS):
        return False

    return True


def get_soup(url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": "project-db-local-doc-builder/0.1",
        "Accept": "text/html,application/xhtml+xml",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue

        full = clean_url(urljoin(base_url, href))

        if allowed(full):
            links.append(full)

    return sorted(set(links))


def remove_junk(soup: BeautifulSoup) -> None:
    for tag in soup.select(
        "script, style, nav, footer, header, aside, iframe, noscript, svg, form, button, devsite-book-nav, devsite-header"
    ):
        tag.decompose()


def text_of(el) -> str:
    text = el.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def table_to_markdown(table) -> list[str]:
    rows = []

    for tr in table.find_all("tr"):
        cells = [text_of(c) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)

    if not rows:
        return []

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]

    lines = []
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * width) + " |")

    for row in rows[1:]:
        escaped = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")

    return lines


def code_language_for_page(url: str, code_text: str) -> str:
    if "/reference/rest/" in url:
        if code_text.strip().startswith("{") or code_text.strip().startswith("["):
            return "json"
        return "http"

    if "curl" in code_text or "GET " in code_text or "POST " in code_text:
        return "bash"

    return ""


def extract_markdown(soup: BeautifulSoup, url: str) -> str:
    remove_junk(soup)

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else None

    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else url

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.select_one(".devsite-article-body")
        or soup.select_one("[class*=content]")
        or soup.body
        or soup
    )

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Source: {url}")
    lines.append("")

    seen_blocks = set()

    for el in main.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "pre", "table"],
        recursive=True,
    ):
        name = el.name.lower()

        if name == "h1":
            continue

        content = text_of(el)
        if not content:
            continue

        key = (name, content)
        if key in seen_blocks:
            continue
        seen_blocks.add(key)

        if name == "h2":
            lines.append(f"\n## {content}\n")

        elif name == "h3":
            lines.append(f"\n### {content}\n")

        elif name == "h4":
            lines.append(f"\n#### {content}\n")

        elif name == "li":
            lines.append(f"- {content}")

        elif name == "pre":
            code = el.get_text("\n", strip=True)
            lang = code_language_for_page(url, code)
            lines.append("")
            lines.append(f"```{lang}")
            lines.append(code)
            lines.append("```")
            lines.append("")

        elif name == "table":
            table_lines = table_to_markdown(el)
            if table_lines:
                lines.append("")
                lines.extend(table_lines)
                lines.append("")

        else:
            lines.append(content)
            lines.append("")

    md = "\n".join(lines)
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    return md.strip() + "\n"


def crawl() -> dict[str, str]:
    seen = set()
    queue = deque(clean_url(url) for url in START_URLS)
    pages = {}

    while queue:
        url = queue.popleft()

        if url in seen:
            continue

        seen.add(url)

        if not allowed(url):
            continue

        print(f"Fetching {url}")

        try:
            soup = get_soup(url)
        except Exception as e:
            print(f"  failed: {e}")
            continue

        pages[url] = extract_markdown(soup, url)

        for link in extract_links(soup, url):
            if link not in seen:
                queue.append(link)

        time.sleep(0.35)

    return pages


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    pages = crawl()
    ordered = sorted(pages.items(), key=lambda item: item[0])

    parts = [
        "# Google Drive API v3 Reference — Consolidated Local Copy",
        "",
        "Generated from public Google Workspace Drive API documentation.",
        "",
        f"Pages included: {len(ordered)}",
        "",
        "---",
        "",
    ]

    for url, md in ordered:
        parts.append(md)
        parts.append("\n---\n")

    OUT.write_text("\n".join(parts), encoding="utf-8")

    print(f"\nWrote {OUT} with {len(ordered)} pages.")


if __name__ == "__main__":
    main()