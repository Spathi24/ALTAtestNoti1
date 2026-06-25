"""PDF parser: Docling (layout + TableFormer) when available, PyMuPDF fallback.

Docling recovers page layout and TABLE STRUCTURE (TableFormer handles spanning
headers, nested row/column hierarchy and inconsistent indentation -- the
"multiple sums" shape that flat text destroys), and gives every table a page +
bounding box. That is the real upgrade over flat PDF text for the financial
audit, and the citeable anchor later slices need.

Docling is a heavy optional dependency (``pip install -e ".[docling]"``; pulls
torch + onnxruntime + ~500MB HuggingFace models on first run). So it is
lazy-imported: when it is absent or a conversion fails, we fall back to the
existing PyMuPDF text path (``connectors.gdrive.extractors.extract_pdf``) and
emit page-level spans. Either way the parser returns a ParsedDocument; the
service records success/failed. OCR is disabled (these are digital PDFs; it also
avoids a broken rapidocr model and an extra download) -- scanned-PDF OCR is a
future option.
"""

from __future__ import annotations

import io

from project_db.parsing.base import ParsedDocument, ParsedEvidence

_PDF_MIMES = {"application/pdf"}
_MAX_TABLES = 50
_MAX_PAGE_SPANS = 100
_MAX_SAMPLE_ROWS = 25
_MAX_SPAN_CHARS = 8000
_MAX_TOTAL_CHARS = 60_000

_converter = None  # cached Docling DocumentConverter (model load is expensive)
_docling_unavailable = False


def _get_converter():
    """Build (once) a Docling converter with OCR off + table structure on.
    Returns None if Docling can't be imported/initialised (-> PyMuPDF fallback)."""
    global _converter, _docling_unavailable
    if _converter is not None:
        return _converter
    if _docling_unavailable:
        return None
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions()
        opts.do_ocr = False
        opts.do_table_structure = True
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
        return _converter
    except Exception:
        _docling_unavailable = True
        return None


def _bbox_dict(prov) -> dict | None:
    if not prov:
        return None
    b = getattr(prov[0], "bbox", None)
    page = getattr(prov[0], "page_no", None)
    if b is None:
        return {"page": page} if page is not None else None
    return {
        "page": page,
        "l": getattr(b, "l", None),
        "t": getattr(b, "t", None),
        "r": getattr(b, "r", None),
        "b": getattr(b, "b", None),
        "coord_origin": str(getattr(b, "coord_origin", "")),
    }


def _val(x: object):
    if x is None:
        return None
    s = str(x).strip()
    return s if s and s.lower() != "nan" else None


def _parse_with_docling(content: bytes, doc_name: str, converter) -> ParsedDocument:
    from docling_core.types.io import DocumentStream

    res = converter.convert(DocumentStream(name=doc_name or "doc.pdf", stream=io.BytesIO(content)))
    doc = res.document

    spans: list[ParsedEvidence] = []

    # Tables: structured evidence with page + bbox (the Docling win).
    for table in (doc.tables or [])[:_MAX_TABLES]:
        try:
            df = table.export_to_dataframe(doc)
        except Exception:
            df = table.export_to_dataframe()
        headers = [str(c) for c in df.columns]
        rows_sample = []
        for i in range(min(len(df), _MAX_SAMPLE_ROWS)):
            row = df.iloc[i]
            rows_sample.append(
                {headers[j]: v for j, c in enumerate(df.columns) if (v := _val(row[c])) is not None}
            )
        bbox = _bbox_dict(getattr(table, "prov", None))
        try:
            tmd = table.export_to_markdown(doc)
        except Exception:
            tmd = ""
        spans.append(
            ParsedEvidence(
                evidence_type="table_region",
                locator={
                    "page": (bbox or {}).get("page"),
                    "n_rows": int(df.shape[0]),
                    "n_cols": int(df.shape[1]),
                },
                content_text=tmd[:_MAX_SPAN_CHARS],
                content_json={
                    "headers": headers,
                    "n_rows": int(df.shape[0]),
                    "rows_sample": rows_sample,
                },
                bbox=bbox,
                confidence=1.0,
            )
        )

    # Page text: group non-table text items by page.
    by_page: dict = {}
    for tx in doc.texts or []:
        prov = getattr(tx, "prov", None)
        if not prov:
            continue
        by_page.setdefault(prov[0].page_no, []).append(getattr(tx, "text", "") or "")
    for page_no in sorted(p for p in by_page if p is not None)[:_MAX_PAGE_SPANS]:
        text = "\n".join(t for t in by_page[page_no] if t).strip()
        if not text:
            continue
        spans.append(
            ParsedEvidence(
                evidence_type="page",
                locator={"page": page_no},
                content_text=text[:_MAX_SPAN_CHARS],
                confidence=1.0,
            )
        )

    rendered = (doc.export_to_markdown() or "")[:_MAX_TOTAL_CHARS]
    structured = {
        "format": "pdf",
        "backend": "docling",
        "n_pages": len(doc.pages) if getattr(doc, "pages", None) else None,
        "n_tables": len(doc.tables or []),
        "n_texts": len(doc.texts or []),
    }
    return ParsedDocument(rendered_text=rendered, structured=structured, evidence_spans=spans)


def _parse_with_pymupdf(content: bytes) -> ParsedDocument:
    import fitz  # PyMuPDF

    pdf = fitz.open(stream=content, filetype="pdf")
    try:
        spans: list[ParsedEvidence] = []
        parts: list[str] = []
        for i, page in enumerate(pdf, 1):
            text = (page.get_text("text") or "").strip()
            if i <= _MAX_PAGE_SPANS and text:
                spans.append(
                    ParsedEvidence(
                        evidence_type="page",
                        locator={"page": i},
                        content_text=text[:_MAX_SPAN_CHARS],
                        confidence=1.0,
                    )
                )
            if text:
                parts.append(f"## Page {i}\n{text}")
        n_pages = pdf.page_count
    finally:
        pdf.close()
    rendered = "\n\n".join(parts).strip()[:_MAX_TOTAL_CHARS]
    structured = {"format": "pdf", "backend": "pymupdf", "n_pages": n_pages, "n_tables": 0}
    return ParsedDocument(rendered_text=rendered, structured=structured, evidence_spans=spans)


class PdfParser:
    name = "pdf"
    version = "1"

    def can_parse(self, *, mime: str | None, filename: str | None) -> bool:
        if mime and mime.lower().split(";")[0].strip() in _PDF_MIMES:
            return True
        if filename and filename.lower().endswith(".pdf"):
            return True
        return False

    def parse(self, content: bytes, *, doc_name: str, mime: str | None) -> ParsedDocument:
        converter = _get_converter()
        if converter is not None:
            try:
                return _parse_with_docling(content, doc_name, converter)
            except Exception:
                pass  # fall back to PyMuPDF on any Docling failure
        return _parse_with_pymupdf(content)
