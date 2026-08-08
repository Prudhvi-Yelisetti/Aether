"""Text extraction for PDF and DOCX attachments (main.py's ChatRequest.files,
encoding="base64" — see that field's docstring).

Design decision, 2026-08-06: libraries first, vision-model OCR only as a
fallback for genuinely scanned/image-only PDFs — not a dedicated OCR engine
like Tesseract. Two reasons:
1. Most real-world PDFs and DOCX files already have an extractable text
   layer. PyMuPDF/python-docx pull it out instantly and perfectly; running
   OCR on documents that don't need it would be slower and less accurate
   than just reading the text that's already there.
2. Aether ships as a self-contained AppImage (see packaging/appimage/).
   Bundling Tesseract means bundling a system binary and its language
   data — real packaging risk for something most documents don't even
   need. The vision model (routing.py's VISION_MODEL) is already wired
   up, already tested, and needs no new binary dependency — just two
   more pure-Python libraries (pymupdf, python-docx) that install as
   normal wheels.
"""

import base64

import fitz  # PyMuPDF
from docx import Document

from services.logging_config import get_logger
from services.reasoning_service import generate
from services.routing import VISION_MODEL

logger = get_logger(__name__)

# Scanned-PDF OCR fallback is capped at this many pages — each page is a
# real vision-model call (tens of seconds, see STATUS.md's timeout
# investigation for large images), so an uncapped fallback on a 200-page
# scanned book would make one /chat request take proportionally forever.
# A guess at "enough for a real document's first few pages," not measured
# against actual usage yet.
MAX_OCR_PAGES = 5

OCR_PROMPT = (
    "Transcribe all readable text in this image exactly as it appears, "
    "preserving line breaks where they make sense. Return only the "
    "transcribed text, nothing else — no commentary, no description of "
    "the image itself."
)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages_text = [page.get_text() for page in doc]
        combined = "\n\n".join(pages_text).strip()

        if combined:
            return combined

        # No extractable text at all — likely a scanned document. Fall
        # back to the vision model, capped at MAX_OCR_PAGES.
        logger.info("pdf_ocr_fallback", total_pages=doc.page_count, ocr_pages=min(doc.page_count, MAX_OCR_PAGES))
        transcriptions = []
        for i, page in enumerate(doc):
            if i >= MAX_OCR_PAGES:
                transcriptions.append(
                    f"[...{doc.page_count - MAX_OCR_PAGES} more page(s) not transcribed — "
                    f"OCR fallback is capped at {MAX_OCR_PAGES} pages...]"
                )
                break
            pixmap = page.get_pixmap(dpi=150)
            image_b64 = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            page_text = generate(OCR_PROMPT, model=VISION_MODEL, images=[image_b64])
            transcriptions.append(f"--- Page {i + 1} (OCR) ---\n{page_text}")

        return "\n\n".join(transcriptions).strip()
    finally:
        doc.close()


def extract_docx_text(docx_bytes: bytes) -> str:
    import io

    doc = Document(io.BytesIO(docx_bytes))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]

    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                parts.append(row_text)

    return "\n".join(parts).strip()


def extract_document_text(filename: str, raw_bytes: bytes) -> str:
    """Dispatches by extension. Raises ValueError for an unsupported type —
    callers (main.py) turn that into a clear inline note rather than a
    500, same treatment as a genuinely unsupported file the frontend
    already blocks (see ChatWindow.js's addFiles)."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_pdf_text(raw_bytes)
    if lower.endswith(".docx"):
        return extract_docx_text(raw_bytes)
    raise ValueError(f"Unsupported document type: {filename}")
