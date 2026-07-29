"""Prepare and chunk official NYSC PDF documents for retrieval."""

from src.pdf_loader import load_all_pdfs
from src.text_chunker import chunk_documents


def prepare_pdf_documents(pdf_records: list[dict]) -> list[dict]:
    """Convert loaded PDF records into the project's document format.

    Args:
        pdf_records: PDF records returned by ``load_all_pdfs``.

    Returns:
        Prepared documents containing text and source metadata.
    """
    prepared_documents = []

    for file_index, record in enumerate(pdf_records, start=1):
        text = str(record.get("text", "")).strip()

        if not text:
            continue

        prepared_documents.append(
            {
                "text": text,
                "metadata": {
                    "id": f"pdf-{file_index}",
                    "category": "Official Document",
                    "question": "",
                    "source_title": str(
                        record.get("source_title", "")
                    ).strip(),
                    "source_url": "",
                    "source_path": str(
                        record.get("source_path", "")
                    ).strip(),
                    "date_verified": "",
                    "document_type": "pdf",
                },
            }
        )

    return prepared_documents


def load_and_chunk_pdf_documents(
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[dict]:
    """Load, prepare, and chunk all PDFs in the configured data directory."""
    pdf_records = load_all_pdfs()
    prepared_documents = prepare_pdf_documents(pdf_records)

    return chunk_documents(
        prepared_documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def main() -> None:
    """Run the PDF preparation pipeline and print a short summary."""
    pdf_records = load_all_pdfs()
    prepared_documents = prepare_pdf_documents(pdf_records)
    pdf_chunks = chunk_documents(prepared_documents)

    print(f"Total PDF documents: {len(prepared_documents)}")
    print(f"Total PDF chunks: {len(pdf_chunks)}")

    if pdf_chunks:
        print(f"First chunk metadata: {pdf_chunks[0]['metadata']}")
    else:
        print("First chunk metadata: None")


if __name__ == "__main__":
    main()
