"""Build and save a FAISS vector store for NYSC FAQ and PDF documents."""

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src.data_loader import load_faq_data
from src.data_preprocessor import prepare_faq_documents
from src.embedding_model import generate_embeddings, load_embedding_model
from src.pdf_preprocessor import load_and_chunk_pdf_documents
from src.text_chunker import chunk_documents


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "nysc_faq.index"
METADATA_PATH = VECTOR_STORE_DIR / "metadata.json"

PDF_DIRECTORY = PROJECT_ROOT / "data" / "raw"


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------

def normalize_document(
    document: dict[str, Any],
    default_document_type: str,
) -> dict[str, Any]:
    """Normalize a FAQ or PDF document before storing it.

    This function makes the metadata structure consistent across FAQ and PDF
    documents. It supports both nested metadata and top-level metadata fields.

    Args:
        document: The document chunk to normalize.
        default_document_type: Either ``faq`` or ``pdf``.

    Returns:
        A normalized copy of the document.

    Raises:
        TypeError: If the supplied document is not a dictionary.
        ValueError: If the document does not contain usable text.
    """
    if not isinstance(document, dict):
        raise TypeError("Each document chunk must be a dictionary.")

    normalized_document = dict(document)

    text = str(normalized_document.get("text", "")).strip()

    if not text:
        raise ValueError("A document chunk contains no usable text.")

    normalized_document["text"] = text

    existing_metadata = normalized_document.get("metadata", {})

    if not isinstance(existing_metadata, dict):
        existing_metadata = {}

    metadata = dict(existing_metadata)

    # Check both metadata locations so older records remain compatible.
    document_type = (
        metadata.get("document_type")
        or normalized_document.get("document_type")
        or default_document_type
    )

    document_type = str(document_type).strip().lower()

    if document_type not in {"faq", "pdf"}:
        document_type = default_document_type

    metadata["document_type"] = document_type
    normalized_document["document_type"] = document_type

    # Copy useful top-level values into nested metadata when available.
    metadata_fields = (
        "id",
        "category",
        "question",
        "source_title",
        "source_url",
        "source_path",
        "filename",
        "page_number",
        "date_verified",
    )

    for field in metadata_fields:
        top_level_value = normalized_document.get(field)
        metadata_value = metadata.get(field)

        if metadata_value in (None, "") and top_level_value not in (None, ""):
            metadata[field] = top_level_value

        if top_level_value in (None, "") and metadata.get(field) not in (
            None,
            "",
        ):
            normalized_document[field] = metadata[field]

    # For PDF documents, safely derive the filename when only a source path
    # was provided.
    if document_type == "pdf":
        source_path = metadata.get("source_path")

        if source_path and not metadata.get("filename"):
            metadata["filename"] = Path(str(source_path)).name

        if metadata.get("filename"):
            normalized_document["filename"] = metadata["filename"]

        if not metadata.get("source_title") and metadata.get("filename"):
            source_title = (
                Path(str(metadata["filename"]))
                .stem
                .replace("_", " ")
                .replace("-", " ")
                .title()
            )

            metadata["source_title"] = source_title
            normalized_document["source_title"] = source_title

        if not metadata.get("category"):
            metadata["category"] = "Official NYSC Document"
            normalized_document["category"] = "Official NYSC Document"

    normalized_document["metadata"] = metadata

    return normalized_document


def normalize_documents(
    documents: list[dict[str, Any]],
    default_document_type: str,
) -> list[dict[str, Any]]:
    """Normalize documents and safely remove empty or invalid chunks."""
    normalized_documents: list[dict[str, Any]] = []

    for position, document in enumerate(documents, start=1):
        try:
            normalized_document = normalize_document(
                document=document,
                default_document_type=default_document_type,
            )

            normalized_documents.append(normalized_document)

        except (TypeError, ValueError) as error:
            print(
                f"Skipping invalid {default_document_type.upper()} chunk "
                f"{position}: {error}"
            )

    return normalized_documents


def count_documents_by_type(
    documents: list[dict[str, Any]],
    document_type: str,
) -> int:
    """Count documents using either nested or top-level metadata."""
    expected_type = document_type.strip().lower()

    return sum(
        (
            document.get("metadata", {}).get("document_type")
            or document.get("document_type")
            or "faq"
        )
        == expected_type
        for document in documents
    )


# ---------------------------------------------------------------------------
# FAISS index
# ---------------------------------------------------------------------------

def create_faiss_index(
    embeddings: np.ndarray,
) -> faiss.IndexFlatIP:
    """Create an inner-product FAISS index from an embedding array.

    The vectors are L2-normalized before being added. This allows inner-product
    search to behave like cosine-similarity search.

    Args:
        embeddings: A two-dimensional NumPy array of text embeddings.

    Returns:
        A FAISS index containing the embeddings.

    Raises:
        TypeError: If embeddings is not a NumPy array.
        ValueError: If embeddings is not two-dimensional or is empty.
    """
    if not isinstance(embeddings, np.ndarray):
        raise TypeError("Embeddings must be a NumPy array.")

    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a two-dimensional array.")

    if embeddings.shape[0] == 0:
        raise ValueError("Embeddings cannot be empty.")

    if embeddings.shape[1] == 0:
        raise ValueError("Embedding vectors cannot have zero dimensions.")

    # FAISS expects 32-bit floating-point vectors.
    float_embeddings = np.ascontiguousarray(
        embeddings.astype(np.float32)
    )

    # Normalize vectors so IndexFlatIP performs cosine-similarity search.
    faiss.normalize_L2(float_embeddings)

    embedding_dimension = float_embeddings.shape[1]

    index = faiss.IndexFlatIP(embedding_dimension)
    index.add(float_embeddings)

    return index


# ---------------------------------------------------------------------------
# Save vector store
# ---------------------------------------------------------------------------

def save_vector_store(
    index: faiss.Index,
    documents: list[dict[str, Any]],
) -> None:
    """Save the FAISS index and document metadata to disk."""
    if index.ntotal != len(documents):
        raise ValueError(
            "The FAISS vector count does not match the metadata count."
        )

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(FAISS_INDEX_PATH))

    with METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            documents,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Build vector store
# ---------------------------------------------------------------------------

def build_vector_store() -> tuple[faiss.IndexFlatIP, list[dict[str, Any]]]:
    """Build and save the combined FAQ and PDF vector store."""
    print("=" * 60)
    print("Building the NYSC knowledge-base vector store")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Load and process FAQ documents
    # -----------------------------------------------------------------------

    print("\n1. Loading verified FAQ records...")

    faq_records = load_faq_data()

    print(f"FAQ records loaded: {len(faq_records)}")

    prepared_faq_documents = prepare_faq_documents(faq_records)
    raw_faq_chunks = chunk_documents(prepared_faq_documents)

    faq_chunks = normalize_documents(
        documents=raw_faq_chunks,
        default_document_type="faq",
    )

    if not faq_chunks:
        raise ValueError("No valid FAQ document chunks are available.")

    print(f"Valid FAQ chunks prepared: {len(faq_chunks)}")

    # -----------------------------------------------------------------------
    # Load and process PDF documents
    # -----------------------------------------------------------------------

    print("\n2. Loading official PDF documents...")

    pdf_files = (
        sorted(PDF_DIRECTORY.glob("*.pdf"))
        if PDF_DIRECTORY.exists()
        else []
    )

    print(f"PDF files found in data/raw: {len(pdf_files)}")

    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")

    raw_pdf_chunks = load_and_chunk_pdf_documents()

    if raw_pdf_chunks is None:
        raw_pdf_chunks = []

    if not isinstance(raw_pdf_chunks, list):
        raise TypeError(
            "load_and_chunk_pdf_documents() must return a list."
        )

    pdf_chunks = normalize_documents(
        documents=raw_pdf_chunks,
        default_document_type="pdf",
    )

    print(f"Valid PDF chunks prepared: {len(pdf_chunks)}")

    if pdf_files and not pdf_chunks:
        print(
            "\nWARNING: PDF files were found, but no PDF text chunks were "
            "created."
        )
        print(
            "Check whether the PDFs contain selectable text and whether "
            "src/pdf_preprocessor.py is extracting their contents."
        )

    if not pdf_files:
        print(
            "\nWARNING: No PDF files were found inside data/raw."
        )

    # -----------------------------------------------------------------------
    # Combine documents
    # -----------------------------------------------------------------------

    print("\n3. Combining FAQ and PDF chunks...")

    all_documents = faq_chunks + pdf_chunks

    if not all_documents:
        raise ValueError(
            "No FAQ or PDF document chunks are available to index."
        )

    faq_chunk_count = count_documents_by_type(
        all_documents,
        "faq",
    )

    pdf_chunk_count = count_documents_by_type(
        all_documents,
        "pdf",
    )

    print(f"FAQ chunks to index: {faq_chunk_count}")
    print(f"PDF chunks to index: {pdf_chunk_count}")
    print(f"Total chunks to index: {len(all_documents)}")

    # -----------------------------------------------------------------------
    # Generate embeddings
    # -----------------------------------------------------------------------

    print("\n4. Loading the embedding model...")

    chunk_texts = [
        document["text"]
        for document in all_documents
    ]

    model = load_embedding_model()

    print("Generating embeddings...")

    embeddings = generate_embeddings(
        chunk_texts,
        model,
    )

    if not isinstance(embeddings, np.ndarray):
        embeddings = np.asarray(embeddings)

    if embeddings.shape[0] != len(all_documents):
        raise ValueError(
            "The number of embeddings does not match the number of "
            "document chunks."
        )

    print(f"Embeddings generated: {embeddings.shape[0]}")
    print(f"Embedding dimension: {embeddings.shape[1]}")

    # -----------------------------------------------------------------------
    # Create and save FAISS index
    # -----------------------------------------------------------------------

    print("\n5. Creating the FAISS index...")

    index = create_faiss_index(embeddings)

    print(f"Vectors added to FAISS: {index.ntotal}")

    save_vector_store(
        index=index,
        documents=all_documents,
    )

    print("\n6. Vector store saved successfully.")

    return index, all_documents


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Build the vector store and print a result summary."""
    try:
        index, documents = build_vector_store()

        pdf_chunk_count = count_documents_by_type(
            documents,
            "pdf",
        )

        faq_chunk_count = count_documents_by_type(
            documents,
            "faq",
        )

        print("\n" + "=" * 60)
        print("VECTOR STORE BUILD SUMMARY")
        print("=" * 60)
        print(f"FAQ chunks indexed: {faq_chunk_count}")
        print(f"PDF chunks indexed: {pdf_chunk_count}")
        print(f"Total documents indexed: {len(documents)}")
        print(f"Total vectors in FAISS: {index.ntotal}")
        print(f"Embedding dimension: {index.d}")
        print(f"Index filename: {FAISS_INDEX_PATH.name}")
        print(f"Metadata filename: {METADATA_PATH.name}")
        print("FAISS vector store created successfully.")
        print("=" * 60)

        if pdf_chunk_count == 0:
            print(
                "\nIMPORTANT: No PDF chunks were indexed. "
                "The chatbot cannot retrieve PDF answers until this is fixed."
            )

    except Exception as error:
        print("\n" + "=" * 60)
        print("VECTOR STORE BUILD FAILED")
        print("=" * 60)
        print(f"Reason: {error}")
        print(
            "Check the FAQ loader, PDF preprocessor and embedding model."
        )


if __name__ == "__main__":
    main()
