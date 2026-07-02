from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from litflow.pdf.models import PdfPageText, PdfTextExtraction


def extract_pdf_text(pdf_path: str | None, max_pages: int | None = None) -> PdfTextExtraction:
    if not pdf_path:
        return PdfTextExtraction(warnings=["missing PDF path"])

    path = Path(pdf_path)
    if not path.exists():
        return PdfTextExtraction(warnings=[f"PDF file does not exist: {pdf_path}"])

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                return PdfTextExtraction(errors=[f"PDF is encrypted and could not be decrypted: {exc}"])

        total_pages = len(reader.pages)
        limit = min(total_pages, max_pages) if max_pages else total_pages
        pages: list[PdfPageText] = []
        warnings: list[str] = []
        for index in range(limit):
            try:
                text = reader.pages[index].extract_text() or ""
            except Exception as exc:
                text = ""
                warnings.append(f"page {index + 1}: text extraction failed: {exc}")
            if not text.strip():
                warnings.append(f"page {index + 1}: extracted text is empty")
            pages.append(PdfPageText(page_number=index + 1, text=text, char_count=len(text)))
        if max_pages and total_pages > max_pages:
            warnings.append(f"extraction limited to first {max_pages} pages")
        return PdfTextExtraction(
            page_count=total_pages,
            char_count=sum(page.char_count for page in pages),
            pages=pages,
            warnings=warnings,
        )
    except Exception as exc:
        return PdfTextExtraction(errors=[f"PDF extraction failed: {exc}"])

