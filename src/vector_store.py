"""Build and save a FAISS vector store for the NYSC FAQ documents."""

import json
from pathlib import Path

import faiss
import numpy as np

from src.data_loader import load_faq_data
from src.data_preprocessor import prepare_faq_documents
from src.embedding_model import generate_embeddings, load_embedding_model
from src.pdf_preprocessor import load_and_chunk_pdf_documents
from src.text_chunker import chunk_documents


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "nysc_faq.index"
METADATA_PATH = VECTOR_STORE_DIR / "metadata.json"


def create_faiss_index(
    embeddings: np.ndarray,
) -> faiss.IndexFlatIP:
    """Create an inner-product FAISS index from an embedding array.

    Args:
        embeddings: A two-dimensional NumPy array of text embeddings.

    Returns:
        A FAISS index containing the embeddings.

    Raises:
        TypeError: If embeddings is not a NumPy array.
        ValueError: If embeddings is not two-dimensional or is empty.
    """
    if not isinstance(embeddings, np.ndarray):
        raise TypeError("embeddings must be a NumPy array.")

    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a two-dimensional array.")

    if embeddings.size == 0:
        raise ValueError("embeddings cannot be empty.")

    # FAISS expects vectors stored as 32-bit floating-point values.
    float_embeddings = embeddings.astype(np.float32)
    embedding_dimension = float_embeddings.shape[1]

    index = faiss.IndexFlatIP(embedding_dimension)
    index.add(float_embeddings)

    return index


def save_vector_store(
    index: faiss.Index,
    documents: list[dict],
) -> None:
    """Save a FAISS index and its document metadata to disk."""
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(FAISS_INDEX_PATH))

    with METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            documents,
            file,
            indent=2,
            ensure_ascii=False,
        )


def build_vector_store() -> tuple[faiss.IndexFlatIP, list[dict]]:
    """Build, save, and return the combined FAQ and PDF vector store."""
    faq_records = load_faq_data()
    prepared_documents = prepare_faq_documents(faq_records)
    faq_chunks = chunk_documents(prepared_documents)

    if not faq_chunks:
        raise ValueError("No FAQ document chunks are available to index.")

    pdf_chunks = load_and_chunk_pdf_documents()
    all_documents = faq_chunks + pdf_chunks
    chunk_texts = [document["text"] for document in all_documents]

    model = load_embedding_model()
    embeddings = generate_embeddings(chunk_texts, model)

    if embeddings.shape[0] != len(all_documents):
        raise ValueError(
            "The number of embeddings does not match the number of "
            "document chunks."
        )

    index = create_faiss_index(embeddings)
    save_vector_store(index, all_documents)

    return index, all_documents


def main() -> None:
    """Build the vector store and print a short result summary."""
    try:
        index, documents = build_vector_store()
        pdf_chunk_count = sum(
            document.get("metadata", {}).get("document_type") == "pdf"
            for document in documents
        )
        faq_chunk_count = len(documents) - pdf_chunk_count

        print(f"FAQ chunks indexed: {faq_chunk_count}")
        print(f"PDF chunks indexed: {pdf_chunk_count}")
        print(f"Total documents indexed: {len(documents)}")
        print(f"Total vectors in FAISS: {index.ntotal}")
        print(f"Embedding dimension: {index.d}")
        print(f"Index location: {FAISS_INDEX_PATH}")
        print(f"Metadata location: {METADATA_PATH}")
        print("FAISS vector store created successfully.")
    except Exception as error:
        print(f"Could not create the FAISS vector store: {error}")


if __name__ == "__main__":
    main()
