"""Load text from official NYSC PDF documents."""

from pathlib import Path

from pypdf import PdfReader


PDF_DATA_DIR = Path("data/raw")


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
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file was not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must have a .pdf extension.")

    reader = PdfReader(pdf_path)
    page_texts = []

    for page in reader.pages:
        text = page.extract_text()

        if text and text.strip():
            page_texts.append(text.strip())

    extracted_text = "\n".join(page_texts).strip()

    if not extracted_text:
        raise ValueError("No readable text could be extracted from the PDF.")

    return extracted_text


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
            extracted_text = load_pdf_text(pdf_path)
        except Exception as error:
            print(
                f"Warning: Could not load PDF '{pdf_path.name}': "
                f"{type(error).__name__}."
            )
            continue

        documents.append(
            {
                "document_type": "pdf",
                "source_title": pdf_path.stem,
                "source_path": str(pdf_path),
                "text": extracted_text,
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
