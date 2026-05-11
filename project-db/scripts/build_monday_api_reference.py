import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

START_URLS = [
    "https://developer.monday.com/api-reference/docs/basics",
    "https://developer.monday.com/api-reference/docs/introduction-to-graphql",
    "https://developer.monday.com/api-reference/reference/about-the-api-reference",
]

ALLOWED_PREFIXES = (
    "https://developer.monday.com/api-reference/docs/",
    "https://developer.monday.com/api-reference/reference/",
)

EXCLUDE_PATTERNS = (
    "/changelog",
    "/login",
    "/community",
    "/apps",
    "/help",
)

OUT = Path("docs/monday-api-reference-all.md")


def clean_url(url: str) -> str:
    url, _frag = urldefrag(url)
    return url.rstrip("/")


def allowed(url: str) -> bool:
    if not url.startswith(ALLOWED_PREFIXES):
        return False
    if any(x in url.lower() for x in EXCLUDE_PATTERNS):
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
        "script, style, nav, footer, header, aside, iframe, noscript, svg, form, button"
    ):
        tag.decompose()


def text_of(el) -> str:
    return re.sub(r"\n{3,}", "\n\n", el.get_text("\n", strip=True)).strip()


def extract_markdown(soup: BeautifulSoup, url: str) -> str:
    remove_junk(soup)

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else url

    # Prefer ReadMe/main content zones, fall back to body.
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.select_one("[class*=content]")
        or soup.body
        or soup
    )

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Source: {url}")
    lines.append("")

    for el in main.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "pre", "code", "table"],
        recursive=True,
    ):
        name = el.name.lower()

        # Avoid duplicating inline code that is inside paragraphs.
        if name == "code" and el.find_parent("pre") is None:
            continue

        if name == "h1":
            continue

        content = text_of(el)
        if not content:
            continue

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
            lines.append("\n```graphql")
            lines.append(code)
            lines.append("```\n")
        elif name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [text_of(c) for c in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines.append("")
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join(["---"] * width) + " |")
                for r in rows[1:]:
                    lines.append("| " + " | ".join(r) + " |")
                lines.append("")
        else:
            lines.append(content)
            lines.append("")

    md = "\n".join(lines)
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    return md.strip() + "\n"


def crawl() -> dict[str, str]:
    seen = set()
    q = deque(clean_url(u) for u in START_URLS)
    pages = {}

    while q:
        url = q.popleft()
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
                q.append(link)

        time.sleep(0.4)

    return pages


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    pages = crawl()

    ordered = sorted(pages.items(), key=lambda kv: kv[0])

    parts = [
        "# monday.com API Reference — Consolidated Local Copy",
        "",
        "Generated from public monday.com developer documentation.",
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