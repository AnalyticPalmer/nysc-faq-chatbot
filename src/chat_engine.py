"""Generate grounded answers from retrieved NYSC FAQ and PDF information."""

import math
import os
import re
from collections import defaultdict

from dotenv import load_dotenv
from google import genai

from src.embedding_model import load_embedding_model
from src.logger import logger
from src.retriever import load_vector_store, search_faq


DEFAULT_MODEL_NAME = "gemini-3.6-flash"
MINIMUM_SIMILARITY = 0.35
RETRIEVAL_TOP_K = 10
MAX_CONTEXT_RESULTS = 8
MAX_CONTEXT_CHARACTERS = 16000

RESPONSE_MODE_AUTO = "auto"
RESPONSE_MODE_AI = "ai"
RESPONSE_MODE_FAQ = "faq"
VALID_RESPONSE_MODES = {
    RESPONSE_MODE_AUTO,
    RESPONSE_MODE_AI,
    RESPONSE_MODE_FAQ,
}

UNAVAILABLE_RESPONSE = (
    "I could not find verified information about this question in the "
    "current NYSC knowledge base."
)
RELATED_BUT_UNCLEAR_RESPONSE = (
    "I found related NYSC documents, but the retrieved sections do not "
    "clearly answer this question."
)

RELEVANCE_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "when",
    "where", "who", "how", "why", "to", "of", "in", "on", "at",
    "for", "from", "with", "and", "or", "this", "that", "according",
    "does", "do", "did", "happens", "happen", "member", "corps",
}
OFFICIAL_DOCUMENT_TERMS = {
    "byelaws", "decree", "policy", "regulation", "rule",
}


def normalize_retrieval_scores(result: dict) -> tuple[float, float] | None:
    """Return compatible decimal similarity and display confidence values."""
    if not isinstance(result, dict):
        return None

    raw_similarity = None

    for field in ("similarity", "score", "similarity_score"):
        value = result.get(field)

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue

        numeric_value = float(value)
        if math.isfinite(numeric_value) and -1.0 <= numeric_value <= 1.0:
            raw_similarity = numeric_value
            break

    confidence_value = result.get("confidence")
    valid_confidence = (
        not isinstance(confidence_value, bool)
        and isinstance(confidence_value, (int, float))
        and math.isfinite(float(confidence_value))
    )

    if raw_similarity is None and valid_confidence:
        numeric_confidence = float(confidence_value)
        raw_similarity = (
            numeric_confidence / 100.0
            if numeric_confidence > 1.0
            else numeric_confidence
        )

    if raw_similarity is None or not -1.0 <= raw_similarity <= 1.0:
        return None

    if valid_confidence and (
        float(confidence_value) > 0.0 or raw_similarity <= 0.0
    ):
        numeric_confidence = float(confidence_value)
        display_confidence = (
            numeric_confidence
            if numeric_confidence > 1.0
            else numeric_confidence * 100.0
        )
    else:
        display_confidence = raw_similarity * 100.0

    display_confidence = max(0.0, min(100.0, display_confidence))
    return raw_similarity, round(display_confidence, 2)


def get_usable_retrieval_results(results: object) -> list[dict]:
    """Keep non-empty FAQ and PDF results with a compatible score."""
    if not isinstance(results, list):
        return []

    usable_results = []

    for result in results:
        if not isinstance(result, dict):
            continue

        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        document_type = str(
            result.get(
                "document_type",
                metadata.get("document_type", "faq"),
            )
        ).strip().lower()

        if document_type not in {"faq", "pdf"}:
            continue

        normalized_scores = normalize_retrieval_scores(result)
        if normalized_scores is None:
            continue

        similarity, confidence = normalized_scores
        compatible_result = result.copy()
        compatible_result["text"] = text.strip()
        compatible_result["metadata"] = metadata
        compatible_result["document_type"] = document_type
        compatible_result["similarity"] = similarity
        compatible_result["confidence"] = confidence
        usable_results.append(compatible_result)

    return usable_results


def _normalize_relevance_text(value: object) -> str:
    """Normalize punctuation and known NYSC document-name variations."""
    normalized = str(value or "").lower()
    normalized = re.sub(
        r"\bbye[\s-]*laws?\b|\bbyelaws?\b",
        " byelaws ",
        normalized,
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _meaningful_terms(value: object) -> set[str]:
    """Extract explainable query terms while retaining important NYSC words."""
    terms = set(_normalize_relevance_text(value).split())
    normalized_terms = set()

    for term in terms - RELEVANCE_STOP_WORDS:
        if term in {"travels", "travelled", "travelling"}:
            term = "travel"
        elif term == "requirements":
            term = "requirement"
        elif term == "permissions":
            term = "permission"

        normalized_terms.add(term)

    return normalized_terms


def _result_search_text(result: dict) -> tuple[str, str]:
    """Return combined candidate text and source-identifying text."""
    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    searchable_fields = (
        result.get("text", ""),
        metadata.get("source_title", ""),
        metadata.get("filename", ""),
        metadata.get("question", ""),
        metadata.get("category", ""),
        metadata.get("section_title", ""),
    )
    source_fields = (
        metadata.get("source_title", ""),
        metadata.get("filename", ""),
        metadata.get("category", ""),
        metadata.get("section_title", ""),
    )

    return (
        _normalize_relevance_text(" ".join(map(str, searchable_fields))),
        _normalize_relevance_text(" ".join(map(str, source_fields))),
    )


def _rerank_retrieval_results(
    question: str,
    results: list[dict],
) -> list[dict]:
    """Rerank evidence using similarity, terms, and source identity."""
    question_terms = _meaningful_terms(question)
    normalized_question = _normalize_relevance_text(question)
    named_document_terms = question_terms & OFFICIAL_DOCUMENT_TERMS
    official_document_requested = bool(
        named_document_terms
        or "according to" in normalized_question
        or "official document" in normalized_question
    )
    reranked_results = []

    for original_position, result in enumerate(results, start=1):
        candidate_text, source_text = _result_search_text(result)
        candidate_terms = _meaningful_terms(candidate_text)
        source_terms = _meaningful_terms(source_text)
        overlap = question_terms & candidate_terms
        vector_similarity = float(result.get("similarity", 0.0))

        keyword_bonus = min(len(overlap) * 0.03, 0.18)
        document_title_match = bool(
            named_document_terms
            and named_document_terms.issubset(source_terms)
        )
        document_title_bonus = 0.25 if document_title_match else 0.0
        source_type_bonus = (
            0.08
            if official_document_requested
            and result.get("document_type") == "pdf"
            else 0.0
        )

        metadata = result.get("metadata", {})
        faq_question_terms = _meaningful_terms(
            metadata.get("question", "")
            if isinstance(metadata, dict)
            else ""
        )
        faq_overlap_ratio = (
            len(question_terms & faq_question_terms) / len(question_terms)
            if question_terms
            else 0.0
        )
        faq_question_bonus = 0.10 if faq_overlap_ratio >= 0.5 else 0.0

        page_bonus = 0.0
        if (
            result.get("document_type") == "pdf"
            and isinstance(metadata, dict)
            and metadata.get("page_number") is not None
        ):
            page_bonus = 0.02

        reranked_result = result.copy()
        reranked_result["rerank_score"] = round(
            vector_similarity
            + keyword_bonus
            + document_title_bonus
            + source_type_bonus
            + faq_question_bonus
            + page_bonus,
            4,
        )
        reranked_result["_matched_terms"] = overlap
        reranked_result["_document_title_match"] = document_title_match
        reranked_results.append(reranked_result)

        source_title = (
            metadata.get("source_title", "")
            if isinstance(metadata, dict)
            else ""
        )
        logger.info(
            "Rerank candidate | original_order=%d | title=%s | type=%s | "
            "similarity=%.4f | rerank_score=%.4f",
            original_position,
            source_title or "Untitled source",
            result.get("document_type", "faq"),
            vector_similarity,
            reranked_result["rerank_score"],
        )

    reranked_results.sort(
        key=lambda result: result["rerank_score"],
        reverse=True,
    )

    for reranked_position, result in enumerate(reranked_results, start=1):
        result["_reranked_position"] = reranked_position

    return reranked_results


def _is_relevant_evidence(question: str, result: dict) -> tuple[bool, str]:
    """Reject candidates that lack meaningful topical overlap."""
    question_terms = _meaningful_terms(question)
    matched_terms = set(result.get("_matched_terms", set()))

    if not matched_terms:
        return False, "no_meaningful_keyword_overlap"

    normalized_question = _normalize_relevance_text(question)

    if "byelaws" in question_terms and not (
        result.get("_document_title_match")
        or "byelaws" in _meaningful_terms(_result_search_text(result)[0])
    ):
        return False, "named_document_not_matched"

    if {"travel", "outside"} & question_terms:
        travel_evidence_terms = {
            "travel", "outside", "permission", "leave", "approval",
            "absent", "absence", "discipline", "disciplinary",
            "penalty", "sanction", "extension", "forfeiture",
        }
        candidate_terms = _meaningful_terms(_result_search_text(result)[0])
        if not candidate_terms & travel_evidence_terms:
            return False, "travel_rule_concept_not_matched"

    required_overlap = 2 if len(question_terms) >= 4 else 1
    if len(matched_terms) < required_overlap:
        return False, "insufficient_keyword_overlap"

    if "official document" in normalized_question and (
        result.get("document_type") != "pdf"
    ):
        return False, "official_document_requested"

    return True, "meaningful_overlap"


def _deduplicate_context_results(results: list[dict]) -> list[dict]:
    """Remove duplicate chunks while preserving strongest evidence."""
    unique_results = []
    seen = set()

    for result in results:
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        normalized_text = _normalize_relevance_text(result.get("text", ""))
        source_identity = (
            metadata.get("source_path")
            or metadata.get("filename")
            or metadata.get("source_title")
            or metadata.get("source_url")
            or "unknown-source"
        )
        page_number = metadata.get("page_number")
        key = (
            str(source_identity).strip().lower(),
            page_number,
            normalized_text[:300],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(result)

    return unique_results


def _select_context_results(
    question: str,
    results: list[dict],
) -> list[dict]:
    """Choose a compact, diverse set of relevant evidence for generation."""
    relevant_results = [
        result
        for result in results
        if _is_relevant_evidence(question, result)[0]
    ]
    relevant_results = _deduplicate_context_results(relevant_results)

    if not relevant_results:
        return []

    selected = []
    per_source_counts: dict[str, int] = defaultdict(int)

    for result in relevant_results:
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        source_identity = str(
            metadata.get("source_path")
            or metadata.get("filename")
            or metadata.get("source_title")
            or metadata.get("source_url")
            or "unknown-source"
        )

        # Allow several chunks from the same official PDF because answers may
        # be distributed across different pages, while avoiding overloading
        # the prompt with repetitive material.
        source_limit = 5 if result.get("document_type") == "pdf" else 2
        if per_source_counts[source_identity] >= source_limit:
            continue

        selected.append(result)
        per_source_counts[source_identity] += 1

        if len(selected) >= MAX_CONTEXT_RESULTS:
            break

    return selected


def load_gemini_client() -> genai.Client:
    """Load environment variables and create a Gemini API client."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to your environment "
            "before starting the chat engine."
        )

    return genai.Client(api_key=api_key)


def _format_page_number(value: object) -> str:
    """Return a safe display value for a PDF page number."""
    if value is None or value == "":
        return "Not provided"

    return str(value)


def build_context(results: list[dict]) -> str:
    """Convert ranked FAQ and PDF results into structured source context."""
    if not results:
        raise ValueError("Cannot build context without retrieval results.")

    context_sections = []
    current_length = 0

    for source_number, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        document_type = result.get("document_type", "faq")
        source_title = (
            metadata.get("source_title")
            or metadata.get("filename")
            or "NYSC source"
        )
        category = metadata.get("category", "")
        text = " ".join(str(result.get("text", "")).split())

        if document_type == "pdf":
            section = (
                f"Source {source_number} — Official NYSC PDF\n"
                f"Document title: {source_title}\n"
                f"Page number: {_format_page_number(metadata.get('page_number'))}\n"
                f"Section title: {metadata.get('section_title', '')}\n"
                f"Category: {category or 'Official Document'}\n"
                f"Document content:\n{text}"
            )
        else:
            section = (
                f"Source {source_number} — Verified NYSC FAQ\n"
                f"FAQ question: {metadata.get('question', '')}\n"
                f"Category: {category}\n"
                f"Source title: {source_title}\n"
                f"Source URL: {metadata.get('source_url', '')}\n"
                f"Verified answer text:\n{text}"
            )

        if current_length + len(section) > MAX_CONTEXT_CHARACTERS:
            logger.info(
                "Context size limit reached | selected_sources=%d | "
                "character_limit=%d",
                len(context_sections),
                MAX_CONTEXT_CHARACTERS,
            )
            break

        context_sections.append(section)
        current_length += len(section)

    if not context_sections:
        raise ValueError("No retrieval result fit within the context limit.")

    return "\n\n---\n\n".join(context_sections)


def build_prompt(question: str, context: str) -> str:
    """Build strict grounding and citation instructions for Gemini."""
    return f"""You are an independent NYSC information assistant.

Use only the supplied verified NYSC context to answer the user's question.

Rules:
1. Do not invent, assume, or add facts that are not supported by the context.
2. Combine relevant facts from multiple supplied sources when they answer different parts of the same question.
3. Prefer official NYSC PDF evidence when the user asks about Bye-Laws, rules, penalties, regulations, or official documents.
4. State the rule first, then explain any penalty or consequence supported by the context.
5. When using PDF evidence, mention the document title and relevant page number or page numbers in a final "Sources" line.
6. When using FAQ evidence, mention the source title in the final "Sources" line.
7. Do not cite a page or source that is not included in the supplied context.
8. Keep the answer simple, direct, and useful.
9. Use numbered steps only when the answer describes a process.
10. Do not claim to represent NYSC.
11. Add this sentence only when the information may change over time:
   "Please confirm time-sensitive information through official NYSC channels."
12. If the supplied context does not clearly answer the question, reply exactly:
"{UNAVAILABLE_RESPONSE}"

Supplied verified context:
{context}

User question:
{question}

Grounded answer:
"""


def extract_answer_from_retrieved_text(text: str) -> str:
    """Extract the answer portion from a prepared FAQ text block."""
    cleaned_text = " ".join(text.split())

    if not cleaned_text:
        raise ValueError("Retrieved FAQ text cannot be empty.")

    if "Answer:" not in cleaned_text:
        return cleaned_text

    answer_text = cleaned_text.split("Answer:", maxsplit=1)[1]

    if "Source:" in answer_text:
        answer_text = answer_text.split("Source:", maxsplit=1)[0]

    return answer_text.strip()


def build_verified_faq_answer(results: list[dict]) -> str:
    """Build an answer directly from the highest-ranked verified FAQ."""
    if not results:
        raise ValueError(
            "A verified FAQ answer requires at least one result."
        )

    highest_ranked_result = min(
        results,
        key=lambda result: result.get("rank", float("inf")),
    )
    answer = extract_answer_from_retrieved_text(
        highest_ranked_result.get("text", "")
    )
    source_note = (
        "Source note: This answer was retrieved directly from the "
        "verified NYSC FAQ knowledge base."
    )

    return f"{answer}\n\n{source_note}"


def _extract_relevant_pdf_sentences(question: str, text: str) -> str:
    """Return up to four PDF sentences that overlap with the question."""
    question_terms = _meaningful_terms(question)
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
        if sentence.strip()
    ]
    ranked_sentences = []

    for position, sentence in enumerate(sentences):
        sentence_terms = _meaningful_terms(sentence)
        overlap = question_terms & sentence_terms
        concept_bonus = len(
            sentence_terms
            & {
                "permission", "penalty", "sanction", "extension",
                "forfeiture", "disciplinary", "approval", "travel",
            }
        )

        if not overlap and not concept_bonus:
            continue

        ranked_sentences.append(
            (len(overlap), concept_bonus, -position, sentence)
        )

    ranked_sentences.sort(reverse=True)
    selected_sentences = [
        sentence for _, _, _, sentence in ranked_sentences[:4]
    ]
    return " ".join(selected_sentences)


def _select_relevant_evidence(
    question: str,
    results: list[dict],
) -> dict | None:
    """Select the strongest result that passes relevance checks."""
    for result in results:
        is_relevant, reason = _is_relevant_evidence(question, result)
        metadata = result.get("metadata", {})
        source_title = (
            metadata.get("source_title", "")
            if isinstance(metadata, dict)
            else ""
        )

        if not is_relevant:
            logger.info(
                "Fallback evidence rejected | title=%s | type=%s | "
                "reason=%s",
                source_title or "Untitled source",
                result.get("document_type", "faq"),
                reason,
            )
            continue

        logger.info(
            "Fallback evidence selected | title=%s | type=%s | reason=%s",
            source_title or "Untitled source",
            result.get("document_type", "faq"),
            reason,
        )
        return result

    return None


def _build_selected_evidence_answer(
    question: str,
    results: list[dict],
) -> str:
    """Build a direct answer from the strongest relevant result."""
    selected_result = _select_relevant_evidence(question, results)
    if selected_result is None:
        return RELATED_BUT_UNCLEAR_RESPONSE

    metadata = selected_result.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    document_type = selected_result.get("document_type", "faq")
    selected_text = selected_result.get("text", "")

    if document_type == "pdf":
        answer = _extract_relevant_pdf_sentences(question, selected_text)
        if not answer:
            return RELATED_BUT_UNCLEAR_RESPONSE

        source_title = (
            metadata.get("source_title")
            or metadata.get("filename")
            or "NYSC document"
        )
        page_number = metadata.get("page_number")
        page_note = (
            f", page {page_number}"
            if page_number not in (None, "")
            else ""
        )
        source_note = (
            "Source note: This answer was retrieved from the official "
            f"NYSC document: {source_title}{page_note}."
        )
    else:
        answer = extract_answer_from_retrieved_text(selected_text)
        source_note = (
            "Source note: This answer was retrieved from the verified "
            "NYSC FAQ knowledge base."
        )

    return f"{answer}\n\n{source_note}"


def build_retrieval_fallback(
    results: list[dict],
    question: str = "",
) -> str:
    """Build a relevance-checked answer when AI generation is unavailable."""
    verified_answer = (
        _build_selected_evidence_answer(question, results)
        if question
        else build_verified_faq_answer(results)
    )

    if verified_answer == RELATED_BUT_UNCLEAR_RESPONSE:
        return verified_answer

    unavailable_note = (
        "The AI-enhanced response service is temporarily unavailable."
    )

    return f"{verified_answer}\n\n{unavailable_note}"


def is_external_generation_error(error: Exception) -> bool:
    """Return whether an exception indicates an external Gemini failure."""
    error_details = f"{type(error).__name__} {error}".lower()
    external_error_indicators = (
        "400", "401", "403", "408", "429", "500", "502", "503", "504",
        "permission_denied", "resource_exhausted", "quota", "rate limit",
        "unavailable", "timeout", "api key", "authentication", "connection",
    )

    return any(
        indicator in error_details
        for indicator in external_error_indicators
    )


def generate_answer(
    question: str,
    client: genai.Client,
    model_name: str,
    context: str,
) -> str:
    """Ask Gemini to answer using only supplied verified context."""
    cleaned_question = " ".join(question.split())
    cleaned_context = context.strip()

    if not cleaned_question:
        raise ValueError("The question cannot be empty.")

    if not cleaned_context:
        raise ValueError("The context cannot be empty.")

    prompt = build_prompt(cleaned_question, cleaned_context)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
    except Exception as error:
        raise RuntimeError(
            f"Gemini could not generate an answer: {error}"
        ) from error

    response_text = getattr(response, "text", None)

    if not response_text or not response_text.strip():
        raise RuntimeError("Gemini returned no text response.")

    return response_text.strip()


def _build_sources(results: list[dict]) -> list[dict]:
    """Build unique source metadata while preserving PDF page citations."""
    sources = []
    seen_sources = set()

    for result in results:
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        source = {
            "title": (
                metadata.get("source_title")
                or metadata.get("filename")
                or ""
            ),
            "url": metadata.get("source_url", ""),
            "category": metadata.get("category", ""),
            "document_type": result.get("document_type", "faq"),
            "source_path": metadata.get("source_path", ""),
            "rank": result.get("rank"),
            "score": result.get("score"),
            "similarity": result.get("similarity"),
            "confidence": result.get("confidence"),
            "page_number": metadata.get("page_number"),
            "section_title": metadata.get("section_title", ""),
        }

        source_key = (
            source["title"],
            source["url"],
            source["source_path"],
            source["page_number"],
            source["section_title"],
        )

        if source_key in seen_sources:
            continue

        seen_sources.add(source_key)
        sources.append(source)

    return sources


def answer_question(
    question: str,
    index: object,
    documents: list[dict],
    embedding_model: object,
    gemini_client: genai.Client | None,
    model_name: str,
    response_mode: str = RESPONSE_MODE_AUTO,
) -> dict:
    """Retrieve relevant evidence and generate a grounded NYSC answer."""
    if response_mode not in VALID_RESPONSE_MODES:
        raise ValueError(
            f"Unsupported response mode: {response_mode}"
        )

    received_results = search_faq(
        question,
        index,
        documents,
        embedding_model,
        top_k=RETRIEVAL_TOP_K,
    )
    results = _rerank_retrieval_results(
        question,
        get_usable_retrieval_results(received_results),
    )

    faq_count = sum(
        result["document_type"] == "faq" for result in results
    )
    pdf_count = sum(
        result["document_type"] == "pdf" for result in results
    )

    if not results:
        logger.info(
            "Retrieval diagnostics | received=%d | usable=0 | "
            "faq=0 | pdf=0 | fallback=true | reason=no_usable_results",
            len(received_results)
            if isinstance(received_results, list)
            else 0,
        )
        return {
            "answer": UNAVAILABLE_RESPONSE,
            "sources": [],
            "confidence": 0.0,
            "generation_mode": "unavailable",
        }

    highest_similarity = max(
        result["similarity"] for result in results
    )
    highest_confidence = max(
        result["confidence"] for result in results
    )

    if highest_similarity < MINIMUM_SIMILARITY:
        logger.info(
            "Retrieval diagnostics | received=%d | usable=%d | "
            "highest_similarity=%.4f | display_confidence=%.2f | "
            "faq=%d | pdf=%d | fallback=true | "
            "reason=below_similarity_threshold",
            len(received_results),
            len(results),
            highest_similarity,
            highest_confidence,
            faq_count,
            pdf_count,
        )
        return {
            "answer": UNAVAILABLE_RESPONSE,
            "sources": [],
            "confidence": 0.0,
            "generation_mode": "unavailable",
        }

    context_results = _select_context_results(question, results)

    logger.info(
        "Retrieval diagnostics | received=%d | usable=%d | "
        "context_selected=%d | highest_similarity=%.4f | "
        "display_confidence=%.2f | faq=%d | pdf=%d",
        len(received_results),
        len(results),
        len(context_results),
        highest_similarity,
        highest_confidence,
        faq_count,
        pdf_count,
    )

    if response_mode == RESPONSE_MODE_FAQ:
        generated_answer = _build_selected_evidence_answer(
            question,
            results,
        )
        generation_mode = "verified_faq"

    elif gemini_client is None:
        generated_answer = build_retrieval_fallback(
            results,
            question,
        )
        generation_mode = "retrieval_fallback"

    elif not context_results:
        generated_answer = RELATED_BUT_UNCLEAR_RESPONSE
        generation_mode = "retrieval_fallback"

    else:
        context = build_context(context_results)

        try:
            generated_answer = generate_answer(
                question,
                gemini_client,
                model_name,
                context,
            )
            generation_mode = "gemini"
        except Exception as error:
            if not is_external_generation_error(error):
                raise

            generated_answer = build_retrieval_fallback(
                results,
                question,
            )
            generation_mode = "retrieval_fallback"

    return {
        "answer": generated_answer,
        "sources": _build_sources(context_results or results),
        "confidence": highest_confidence,
        "generation_mode": generation_mode,
    }


def main() -> None:
    """Load project services and answer a sample NYSC question."""
    test_question = (
        "According to the NYSC Bye-Laws, what happens when a corps "
        "member travels outside the state without permission?"
    )

    try:
        index, documents = load_vector_store()
        embedding_model = load_embedding_model()
        gemini_client = load_gemini_client()
        model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)

        result = answer_question(
            test_question,
            index,
            documents,
            embedding_model,
            gemini_client,
            model_name,
        )

        print(f"Question: {test_question}")
        print(f"Answer: {result['answer']}")
        print(f"Confidence: {result['confidence']}%")
        print("Sources:")

        for source in result["sources"]:
            print(
                f"- {source['title']} | "
                f"page={source.get('page_number')} | "
                f"{source['category']}"
            )
    except Exception as error:
        print(f"Chat engine error: {error}")


if __name__ == "__main__":
    main()