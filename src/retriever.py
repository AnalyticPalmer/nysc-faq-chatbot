"""Retrieve relevant NYSC FAQ documents from the saved FAISS index."""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.embedding_model import generate_embeddings, load_embedding_model


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "nysc_faq.index"
METADATA_PATH = VECTOR_STORE_DIR / "metadata.json"
DEFAULT_TOP_K = 3


def load_vector_store() -> tuple[faiss.Index, list[dict]]:
    """Load the saved FAISS index and its document metadata.

    Returns:
        A tuple containing the FAISS index and metadata documents.

    Raises:
        FileNotFoundError: If the index or metadata file is missing.
        ValueError: If the metadata is invalid or its count does not match
            the number of vectors in the index.
    """
    if not FAISS_INDEX_PATH.exists():
        raise FileNotFoundError(
            f"FAISS index file was not found: {FAISS_INDEX_PATH}"
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file was not found: {METADATA_PATH}"
        )

    index = faiss.read_index(str(FAISS_INDEX_PATH))

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    if not isinstance(documents, list):
        raise ValueError("Vector store metadata must be a list.")

    if len(documents) != index.ntotal:
        raise ValueError(
            "Metadata count does not match the number of vectors in "
            "the FAISS index."
        )

    return index, documents


def convert_score_to_percentage(score: float) -> float:
    """Convert an inner-product similarity score to a percentage."""
    percentage = ((score + 1) / 2) * 100
    limited_percentage = max(0.0, min(100.0, percentage))
    return round(limited_percentage, 2)


def search_faq(
    question: str,
    index: faiss.Index,
    documents: list[dict],
    model: SentenceTransformer,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """Search the saved FAQ vectors for documents relevant to a question.

    Args:
        question: The user's NYSC-related question.
        index: A loaded FAISS index.
        documents: Metadata documents aligned with the indexed vectors.
        model: A loaded Sentence Transformer model.
        top_k: The maximum number of results to return.

    Returns:
        A ranked list of matching FAQ documents.

    Raises:
        TypeError: If question is not a string.
        ValueError: If question is empty, top_k is invalid, or the index
            contains no documents.
    """
    if not isinstance(question, str):
        raise TypeError("question must be a string.")

    cleaned_question = " ".join(question.split())

    if not cleaned_question:
        raise ValueError("question cannot be empty.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    if index.ntotal == 0:
        raise ValueError("The FAISS index contains no documents.")

    search_limit = min(top_k, index.ntotal, len(documents))

    question_embedding = generate_embeddings(
        [cleaned_question],
        model,
    ).astype(np.float32)

    scores, result_indices = index.search(
        question_embedding,
        search_limit,
    )

    results = []

    for score, result_index in zip(scores[0], result_indices[0]):
        # FAISS can return -1 when no valid result is available.
        if result_index < 0 or result_index >= len(documents):
            continue

        document = documents[result_index]
        results.append(
            {
                "rank": len(results) + 1,
                "score": float(score),
                "confidence": convert_score_to_percentage(
                    float(score)
                ),
                "text": document.get("text", ""),
                "metadata": document.get("metadata", {}),
            }
        )

    return results


def main() -> None:
    """Load the vector store and print results for a sample question."""
    test_question = "What documents should I take to NYSC camp?"

    try:
        index, documents = load_vector_store()
        model = load_embedding_model()
        results = search_faq(
            test_question,
            index,
            documents,
            model,
            top_k=DEFAULT_TOP_K,
        )

        print(f"Test question: {test_question}")

        for result in results:
            metadata = result["metadata"]
            print(f"\nRank: {result['rank']}")
            print(f"Confidence: {result['confidence']}%")
            print(f"FAQ question: {metadata.get('question', '')}")
            print(f"Category: {metadata.get('category', '')}")
            print(
                f"Source title: {metadata.get('source_title', '')}"
            )
    except Exception as error:
        print(f"Could not search the FAQ vector store: {error}")


if __name__ == "__main__":
    main()
