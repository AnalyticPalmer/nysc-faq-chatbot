"""Load text from official NYSC PDF documents."""

from pathlib import Path

from pypdf import PdfReader

from src.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def _has_meaningful_text(text: str) -> bool:
    """Return whether extracted text is substantial enough to index."""
    cleaned = " ".join(text.split())
    letters = sum(character.isalpha() for character in cleaned)
    return letters >= 40 and letters / max(len(cleaned), 1) >= 0.45


def load_pdf_pages(pdf_path: Path) -> list[dict]:
    """Extract readable PDF pages with human-readable page numbers."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file was not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must have a .pdf extension.")

    reader = PdfReader(pdf_path)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if text and _has_meaningful_text(text):
            pages.append(
                {
                    "page_number": page_number,
                    "text": text.strip(),
                }
            )

    if not pages:
        raise ValueError(
            "No readable text layer was found. Run the offline OCR "
            "workflow before indexing this PDF."
        )

    return pages


def load_pdf_text(pdf_path: Path) -> str:
    """Extract and return readable text from a PDF file.

    Args:
        pdf_path: Path to the PDF document.

    Returns:
        Text extracted from all readable pages.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        ValueError: If the path is not a PDF or contains no extractable text.
    """
    pages = load_pdf_pages(pdf_path)
    return "\n".join(page["text"] for page in pages).strip()


def load_all_pdfs(pdf_directory: Path = PDF_DATA_DIR) -> list[dict]:
    """Load all readable PDFs from a directory in filename order.

    A broken or unreadable PDF is skipped so that other documents can still
    be processed.
    """
    if not pdf_directory.exists():
        return []

    pdf_paths = sorted(
        (
            path
            for path in pdf_directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name.lower(),
    )
    documents = []

    for pdf_path in pdf_paths:
        try:
            pages = load_pdf_pages(pdf_path)
        except Exception as error:
            logger.warning(
                "Skipping unreadable PDF | filename=%s | error_type=%s",
                pdf_path.name,
                type(error).__name__,
            )
            continue

        documents.append(
            {
                "document_type": "pdf",
                "source_title": pdf_path.stem,
                "filename": pdf_path.name,
                "source_path": str(pdf_path),
                "pages": pages,
                # Preserve the historical combined-text field for callers
                # that do not yet consume page-aware extraction records.
                "text": "\n".join(page["text"] for page in pages),
            }
        )

    return documents


def main() -> None:
    """Load available PDFs and print a short extraction summary."""
    documents = load_all_pdfs()

    print(f"Number of PDFs found: {len(documents)}")

    for document in documents:
        print(f"File title: {document['source_title']}")
        print(f"Extracted character count: {len(document['text'])}")


if __name__ == "__main__":
    main()
