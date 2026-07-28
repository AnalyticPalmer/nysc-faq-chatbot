"""Split prepared NYSC FAQ documents into overlapping text chunks."""

from src.data_loader import load_faq_data
from src.data_preprocessor import prepare_faq_documents


DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 100


def clean_text(text: str) -> str:
    """Remove repeated spaces and unnecessary line breaks from text."""
    return " ".join(text.split())


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into fixed-size chunks with a requested overlap.

    Args:
        text: The text to split.
        chunk_size: The maximum number of characters in each chunk.
        chunk_overlap: The number of characters shared by nearby chunks.

    Returns:
        A list containing the cleaned text chunks.

    Raises:
        ValueError: If the chunk size or overlap settings are invalid.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    cleaned_text = clean_text(text)

    if not cleaned_text:
        return []

    if len(cleaned_text) <= chunk_size:
        return [cleaned_text]

    chunks = []
    step_size = chunk_size - chunk_overlap

    for start in range(0, len(cleaned_text), step_size):
        chunk = cleaned_text[start : start + chunk_size].strip()

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(cleaned_text):
            break

    return chunks


def chunk_documents(
    documents: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Split prepared documents into chunks while preserving metadata."""
    chunked_documents = []

    for document in documents:
        text_chunks = split_text(
            document.get("text", ""),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        total_chunks = len(text_chunks)

        for chunk_index, text_chunk in enumerate(text_chunks):
            # Copy the metadata so the original dictionary is not changed.
            chunk_metadata = dict(document.get("metadata", {}))
            chunk_metadata["chunk_index"] = chunk_index
            chunk_metadata["total_chunks"] = total_chunks

            chunked_documents.append(
                {
                    "text": text_chunk,
                    "metadata": chunk_metadata,
                }
            )

    return chunked_documents


def main() -> None:
    """Load, prepare, and chunk the FAQ data, then print a preview."""
    faq_records = load_faq_data()
    prepared_documents = prepare_faq_documents(faq_records)
    chunks = chunk_documents(prepared_documents)

    print(f"Total original documents: {len(prepared_documents)}")
    print(f"Total chunks created: {len(chunks)}")

    if chunks:
        print("\nFirst chunk text:")
        print(chunks[0]["text"])
        print("\nFirst chunk metadata:")
        print(chunks[0]["metadata"])


if __name__ == "__main__":
    main()
