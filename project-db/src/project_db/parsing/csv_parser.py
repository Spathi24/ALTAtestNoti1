"""CSV parser -- the first real parser, proving the evidence spine end to end.

CSV is the lowest-risk tabular format (no merged cells, formulas, or multiple
sheets), so it is the right place to validate `Document -> DocumentParse ->
EvidenceSpan -> DocumentText` before openpyxl (Slice 3) and Docling (Slice 4).

It preserves table structure rather than flattening: the header row is detected,
a Markdown table is rendered for compatibility, and a `table_region`
`EvidenceSpan` carries the headers + a structured row sample so a downstream
extractor can cite *which table* a number came from. Quebec/French CSVs that use
``;`` as the delimiter are handled (comma/semicolon/tab/pipe sniffing).
"""

from __future__ import annotations

import csv
import io

from project_db.parsing.base import ParsedDocument, ParsedEvidence

_CSV_MIMES = {"text/csv", "text/comma-separated-values", "application/csv"}
_MAX_RENDER_ROWS = 1000  # cap the compatibility Markdown; structured sample is separate
_MAX_SAMPLE_ROWS = 25


def _cell(x: object) -> str:
    s = "" if x is None else str(x)
    return s.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    cols = max([len(headers)] + [len(r) for r in rows]) if (headers or rows) else 0
    if cols == 0:
        return ""
    hdr = list(headers) + [""] * (cols - len(headers))
    lines = [
        "| " + " | ".join(_cell(h) for h in hdr) + " |",
        "| " + " | ".join("---" for _ in range(cols)) + " |",
    ]
    for r in rows[:_MAX_RENDER_ROWS]:
        rr = list(r) + [""] * (cols - len(r))
        lines.append("| " + " | ".join(_cell(c) for c in rr) + " |")
    if len(rows) > _MAX_RENDER_ROWS:
        lines.append(f"| ...({len(rows) - _MAX_RENDER_ROWS} more rows) |")
    return "\n".join(lines)


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except Exception:
        # Deterministic fallback: pick the most frequent common delimiter.
        counts = {d: sample.count(d) for d in [",", ";", "\t", "|"]}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


class CsvParser:
    name = "csv"
    version = "1"

    def can_parse(self, *, mime: str | None, filename: str | None) -> bool:
        if mime and mime.lower().split(";")[0].strip() in _CSV_MIMES:
            return True
        if filename and filename.lower().endswith(".csv"):
            return True
        return False

    def parse(self, content: bytes, *, doc_name: str, mime: str | None) -> ParsedDocument:
        text = (
            content.decode("utf-8-sig", errors="replace")
            if isinstance(content, (bytes, bytearray))
            else str(content)
        )
        delimiter = _sniff_delimiter(text[:4096])
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [r for r in reader if any((c or "").strip() for c in r)]

        if not rows:
            return ParsedDocument(
                rendered_text="",
                structured={
                    "format": "csv",
                    "delimiter": delimiter,
                    "n_rows": 0,
                    "n_cols": 0,
                    "headers": [],
                },
                evidence_spans=[],
            )

        headers = [(h or "").strip() for h in rows[0]]
        data_rows = rows[1:]
        n_cols = max(len(r) for r in rows)
        rendered = _to_markdown(headers, data_rows)
        structured = {
            "format": "csv",
            "delimiter": delimiter,
            "n_rows": len(data_rows),
            "n_cols": n_cols,
            "headers": headers,
        }
        sample = [
            {
                headers[i] if i < len(headers) else f"col{i}": (v or "").strip()
                for i, v in enumerate(r)
            }
            for r in data_rows[:_MAX_SAMPLE_ROWS]
        ]
        span = ParsedEvidence(
            evidence_type="table_region",
            locator={
                "format": "csv",
                "delimiter": delimiter,
                "header_row": 1,
                "n_rows": len(data_rows),
                "n_cols": n_cols,
            },
            content_text=rendered[:4000],
            content_json={
                "headers": headers,
                "n_rows": len(data_rows),
                "rows_sample": sample,
            },
            confidence=1.0,
        )
        return ParsedDocument(rendered_text=rendered, structured=structured, evidence_spans=[span])
