"""Retrieve relevant NYSC FAQ and PDF documents from the FAISS index."""

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.embedding_model import generate_embeddings, load_embedding_model


# ---------------------------------------------------------------------------
# Project paths and retrieval settings
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"

FAISS_INDEX_PATH = VECTOR_STORE_DIR / "nysc_faq.index"
METADATA_PATH = VECTOR_STORE_DIR / "metadata.json"

# Return a broad result set so downstream reranking can compare source types.
DEFAULT_TOP_K = 20


# ---------------------------------------------------------------------------
# Vector-store loading
# ---------------------------------------------------------------------------

def load_vector_store() -> tuple[faiss.Index, list[dict[str, Any]]]:
    """Load the FAISS index and its aligned document metadata.

    Returns:
        A tuple containing the FAISS index and metadata documents.

    Raises:
        FileNotFoundError: If the index or metadata file is missing.
        ValueError: If the metadata is invalid or does not match the index.
    """
    if not FAISS_INDEX_PATH.exists():
        raise FileNotFoundError(
            f"FAISS index file was not found: {FAISS_INDEX_PATH.name}"
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file was not found: {METADATA_PATH.name}"
        )

    index = faiss.read_index(str(FAISS_INDEX_PATH))

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    if not isinstance(documents, list):
        raise ValueError("Vector-store metadata must be a list.")

    if index.ntotal == 0:
        raise ValueError("The FAISS index contains no vectors.")

    if len(documents) != index.ntotal:
        raise ValueError(
            "Metadata count does not match the number of vectors "
            "stored in the FAISS index."
        )

    return index, documents


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def get_document_metadata(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Return consistent metadata from a stored FAQ or PDF document."""
    nested_metadata = document.get("metadata", {})

    if not isinstance(nested_metadata, dict):
        nested_metadata = {}

    metadata = dict(nested_metadata)

    supported_fields = (
        "id",
        "document_type",
        "category",
        "question",
        "source_title",
        "source_url",
        "source_path",
        "filename",
        "page_number",
        "section_title",
        "date_verified",
    )

    for field in supported_fields:
        if metadata.get(field) in (None, ""):
            value = document.get(field)

            if value not in (None, ""):
                metadata[field] = value

    document_type = str(
        metadata.get("document_type", "faq")
    ).strip().lower()

    if document_type not in {"faq", "pdf"}:
        document_type = "faq"

    metadata["document_type"] = document_type

    if document_type == "pdf":
        source_path = metadata.get("source_path")

        if source_path and not metadata.get("filename"):
            metadata["filename"] = Path(str(source_path)).name

        if not metadata.get("source_title") and metadata.get("filename"):
            metadata["source_title"] = (
                Path(str(metadata["filename"]))
                .stem
                .replace("_", " ")
                .replace("-", " ")
                .title()
            )

        if not metadata.get("category"):
            metadata["category"] = "Official NYSC Document"

    return metadata


def get_document_type(document: dict[str, Any]) -> str:
    """Return either faq or pdf for a stored document."""
    return get_document_metadata(document).get(
        "document_type",
        "faq",
    )


def is_bye_law_document(metadata: dict[str, Any]) -> bool:
    """Check whether metadata belongs to an NYSC Bye-Laws document."""
    source_title = str(
        metadata.get("source_title", "")
    ).lower()

    filename = str(
        metadata.get("filename", "")
    ).lower()

    combined_name = f"{source_title} {filename}"

    bye_law_terms = (
        "byelaw",
        "bye-law",
        "bye law",
        "bye_law",
    )

    return any(
        term in combined_name
        for term in bye_law_terms
    )


# ---------------------------------------------------------------------------
# Similarity-score helpers
# ---------------------------------------------------------------------------

def convert_score_to_percentage(score: float) -> float:
    """Convert a cosine-similarity score into a display percentage."""
    percentage = score * 100
    limited_percentage = max(0.0, min(100.0, percentage))

    return round(limited_percentage, 2)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search_faq(
    question: str,
    index: faiss.Index,
    documents: list[dict[str, Any]],
    model: SentenceTransformer,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Search all indexed NYSC FAQ and PDF documents."""
    if not isinstance(question, str):
        raise TypeError("Question must be a string.")

    cleaned_question = " ".join(question.split())

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    if not isinstance(top_k, int):
        raise TypeError("top_k must be an integer.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    if index.ntotal == 0:
        raise ValueError("The FAISS index contains no documents.")

    if not documents:
        raise ValueError("No vector-store metadata documents are available.")

    if len(documents) != index.ntotal:
        raise ValueError(
            "The document count does not match the FAISS vector count."
        )

    # Search a wider internal pool so relevant PDF chunks can be inspected.
    candidate_limit = min(
        max(top_k * 10, 200),
        index.ntotal,
        len(documents),
    )

    question_embedding = generate_embeddings(
        [cleaned_question],
        model,
    )

    if not isinstance(question_embedding, np.ndarray):
        question_embedding = np.asarray(question_embedding)

    if question_embedding.ndim != 2:
        raise ValueError(
            "The generated question embedding must be two-dimensional."
        )

    if question_embedding.shape[0] != 1:
        raise ValueError(
            "Exactly one question embedding should be generated."
        )

    question_embedding = np.ascontiguousarray(
        question_embedding.astype(np.float32)
    )

    faiss.normalize_L2(question_embedding)

    scores, result_indices = index.search(
        question_embedding,
        candidate_limit,
    )

    candidate_results: list[dict[str, Any]] = []

    for score, result_index in zip(
        scores[0],
        result_indices[0],
    ):
        if result_index < 0:
            continue

        if result_index >= len(documents):
            continue

        document = documents[int(result_index)]

        if not isinstance(document, dict):
            continue

        text = str(document.get("text", "")).strip()

        if not text:
            continue

        metadata = get_document_metadata(document)
        document_type = metadata.get("document_type", "faq")

        candidate_results.append(
            {
                "rank": len(candidate_results) + 1,
                "score": float(score),
                "similarity": float(score),
                "confidence": convert_score_to_percentage(
                    float(score)
                ),
                "text": text,
                "document_type": document_type,
                "metadata": metadata,
            }
        )

    if not candidate_results:
        return []

    balanced_results: list[dict[str, Any]] = [
        candidate_results[0]
    ]

    pdf_candidates = [
        result
        for result in candidate_results
        if result.get("document_type") == "pdf"
    ]

    # Include up to ten PDF candidates during diagnosis.
    for pdf_result in pdf_candidates[:10]:
        if pdf_result not in balanced_results:
            balanced_results.append(pdf_result)

    for result in candidate_results:
        if result not in balanced_results:
            balanced_results.append(result)

        if len(balanced_results) >= top_k:
            break

    balanced_results = balanced_results[:top_k]

    for rank, result in enumerate(balanced_results, start=1):
        result["rank"] = rank

    return balanced_results


# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------

def print_result(result: dict[str, Any]) -> None:
    """Print one retrieval result in a readable diagnostic format."""
    metadata = result.get("metadata", {})

    document_type = metadata.get(
        "document_type",
        result.get("document_type", "faq"),
    )

    readable_type = (
        "Official PDF Document"
        if document_type == "pdf"
        else "Verified FAQ"
    )

    print("\n" + "-" * 60)
    print(f"Rank: {result.get('rank')}")
    print(f"Source type: {readable_type}")
    print(f"Similarity score: {result.get('score', 0):.4f}")
    print(f"Similarity percentage: {result.get('confidence', 0)}%")
    print(f"Title: {metadata.get('source_title', 'Not available')}")
    print(f"Category: {metadata.get('category', 'Not available')}")

    if document_type == "faq":
        print(
            f"FAQ question: "
            f"{metadata.get('question', 'Not available')}"
        )

    if document_type == "pdf":
        print(
            f"PDF filename: "
            f"{metadata.get('filename', 'Not available')}"
        )
        print(
            f"Page number: "
            f"{metadata.get('page_number', 'Not available')}"
        )
        print(
            f"Section title: "
            f"{metadata.get('section_title', 'Not available')}"
        )

    preview = (
        result.get("text", "")[:1000]
        .replace("\n", " ")
        .strip()
    )

    print(f"Text preview: {preview}...")


def find_bye_law_keyword_matches(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find Bye-Laws chunks containing travel or permission-related terms."""
    search_terms = (
        "travel",
        "travelling",
        "traveling",
        "outside the state",
        "leave the state",
        "permission",
        "approval",
        "leave station",
        "leaving the station",
        "absence",
        "absent",
        "without permission",
        "without approval",
    )

    matches: list[dict[str, Any]] = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        metadata = get_document_metadata(document)

        if metadata.get("document_type") != "pdf":
            continue

        if not is_bye_law_document(metadata):
            continue

        text = str(document.get("text", "")).strip()
        lowered_text = text.lower()

        matched_terms = [
            term
            for term in search_terms
            if term in lowered_text
        ]

        if not matched_terms:
            continue

        matches.append(
            {
                "text": text,
                "metadata": metadata,
                "matched_terms": matched_terms,
            }
        )

    return matches


def print_bye_law_matches(
    matches: list[dict[str, Any]],
) -> None:
    """Print direct keyword matches from indexed Bye-Laws chunks."""
    print("\n" + "=" * 60)
    print("DIRECT BYE-LAWS KEYWORD SEARCH")
    print("=" * 60)
    print(f"Bye-Laws keyword matches found: {len(matches)}")

    if not matches:
        print(
            "\nNo Bye-Laws chunks contained the expected travel, "
            "permission, approval, leave or absence terms."
        )
        return

    for match_number, match in enumerate(
        matches[:20],
        start=1,
    ):
        metadata = match.get("metadata", {})

        print("\n" + "-" * 60)
        print(f"Match: {match_number}")
        print(
            f"Title: "
            f"{metadata.get('source_title', 'Not available')}"
        )
        print(
            f"Filename: "
            f"{metadata.get('filename', 'Not available')}"
        )
        print(
            f"Page number: "
            f"{metadata.get('page_number', 'Not available')}"
        )
        print(
            f"Section title: "
            f"{metadata.get('section_title', 'Not available')}"
        )
        print(
            "Matched terms: "
            + ", ".join(match.get("matched_terms", []))
        )

        preview = (
            match.get("text", "")[:1500]
            .replace("\n", " ")
            .strip()
        )

        print(f"Text preview: {preview}...")


# ---------------------------------------------------------------------------
# Diagnostic test
# ---------------------------------------------------------------------------

def main() -> None:
    """Test retrieval and directly inspect indexed Bye-Laws chunks."""
    test_question = (
        "According to the NYSC Bye-Laws, what happens when a corps "
        "member travels outside the state without permission?"
    )

    try:
        print("=" * 60)
        print("NYSC HYBRID RETRIEVER DIAGNOSTIC TEST")
        print("=" * 60)
        print(f"Test question: {test_question}")

        index, documents = load_vector_store()

        faq_count = sum(
            get_document_type(document) == "faq"
            for document in documents
        )

        pdf_count = sum(
            get_document_type(document) == "pdf"
            for document in documents
        )

        bye_law_chunk_count = sum(
            get_document_type(document) == "pdf"
            and is_bye_law_document(
                get_document_metadata(document)
            )
            for document in documents
        )

        print(f"Total indexed documents: {len(documents)}")
        print(f"FAQ chunks available: {faq_count}")
        print(f"PDF chunks available: {pdf_count}")
        print(f"Bye-Laws PDF chunks available: {bye_law_chunk_count}")

        model = load_embedding_model()

        results = search_faq(
            question=test_question,
            index=index,
            documents=documents,
            model=model,
            top_k=DEFAULT_TOP_K,
        )

        print(f"Results returned: {len(results)}")

        pdf_results = sum(
            result.get("document_type") == "pdf"
            for result in results
        )

        faq_results = len(results) - pdf_results

        bye_law_results = sum(
            result.get("document_type") == "pdf"
            and is_bye_law_document(
                result.get("metadata", {})
            )
            for result in results
        )

        print(f"FAQ results returned: {faq_results}")
        print(f"PDF results returned: {pdf_results}")
        print(f"Bye-Laws PDF results returned: {bye_law_results}")

        print("\n" + "=" * 60)
        print("TOP 20 RETRIEVAL RESULTS")
        print("=" * 60)

        for result in results:
            print_result(result)

        direct_matches = find_bye_law_keyword_matches(
            documents
        )

        print_bye_law_matches(direct_matches)

        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 60)

        if bye_law_chunk_count == 0:
            print(
                "Problem: No Bye-Laws chunks were identified in "
                "the vector-store metadata."
            )
        elif not direct_matches:
            print(
                "Problem: Bye-Laws chunks exist, but none contains "
                "the expected travel or permission wording."
            )
        elif bye_law_results == 0:
            print(
                "Problem: Relevant wording exists in the Bye-Laws "
                "chunks, but none appeared in the top retrieval results."
            )
        else:
            print(
                "Success: Bye-Laws chunks exist and at least one "
                "appeared in the retrieval results."
            )

    except Exception as error:
        print("\n" + "=" * 60)
        print("RETRIEVER DIAGNOSTIC TEST FAILED")
        print("=" * 60)
        print(f"Reason: {error}")


if __name__ == "__main__":
    main()
