"""Generate grounded answers from retrieved NYSC FAQ information."""

import os

from dotenv import load_dotenv
from google import genai

from src.embedding_model import load_embedding_model
from src.retriever import load_vector_store, search_faq


DEFAULT_MODEL_NAME = "gemini-3.6-flash"
MINIMUM_CONFIDENCE = 65.0
UNAVAILABLE_RESPONSE = (
    "I could not find verified information about this question in the "
    "current NYSC knowledge base."
)


def load_gemini_client() -> genai.Client:
    """Load environment variables and create a Gemini API client.

    Raises:
        ValueError: If GEMINI_API_KEY is missing from the environment.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to your environment "
            "before starting the chat engine."
        )

    return genai.Client(api_key=api_key)


def build_context(results: list[dict]) -> str:
    """Convert retrieved FAQ results into numbered source context.

    Args:
        results: Ranked FAQ results returned by the retriever.

    Returns:
        A readable context string containing FAQ and source details.

    Raises:
        ValueError: If no retrieval results are provided.
    """
    if not results:
        raise ValueError("Cannot build context without FAQ results.")

    context_sections = []

    for source_number, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        context_sections.append(
            f"Source {source_number}\n"
            f"FAQ question: {metadata.get('question', '')}\n"
            f"Answer text: {result.get('text', '')}\n"
            f"Category: {metadata.get('category', '')}\n"
            f"Source title: {metadata.get('source_title', '')}\n"
            f"Source URL: {metadata.get('source_url', '')}"
        )

    return "\n\n".join(context_sections)


def build_prompt(question: str, context: str) -> str:
    """Build instructions that keep Gemini grounded in FAQ context."""
    return f"""You are an NYSC FAQ assistant.

Answer the user's question only from the supplied context.
Do not invent facts or include information outside the context.
Keep the answer simple and direct.
Use numbered steps when explaining a process.
If the answer is unavailable, reply exactly:
"{UNAVAILABLE_RESPONSE}"
Do not claim to represent NYSC.
Remind the user to confirm time-sensitive information through official NYSC channels.

Supplied context:
{context}

User question:
{question}
"""


def generate_answer(
    question: str,
    client: genai.Client,
    model_name: str,
    context: str,
) -> str:
    """Ask Gemini to answer a question using only supplied FAQ context.

    Raises:
        ValueError: If the question or context is empty.
        RuntimeError: If the API request fails or returns no text.
    """
    cleaned_question = " ".join(question.split())
    cleaned_context = context.strip()

    if not cleaned_question:
        raise ValueError("The question cannot be empty.")

    if not cleaned_context:
        raise ValueError("The FAQ context cannot be empty.")

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


def answer_question(
    question: str,
    index: object,
    documents: list[dict],
    embedding_model: object,
    gemini_client: genai.Client,
    model_name: str,
) -> dict:
    """Retrieve relevant FAQs and generate a grounded Gemini answer."""
    results = search_faq(
        question,
        index,
        documents,
        embedding_model,
        top_k=3,
    )

    if not results:
        return {
            "answer": UNAVAILABLE_RESPONSE,
            "sources": [],
            "confidence": 0.0,
        }

    highest_confidence = max(
        result.get("confidence", 0.0) for result in results
    )

    if highest_confidence < MINIMUM_CONFIDENCE:
        return {
            "answer": UNAVAILABLE_RESPONSE,
            "sources": [],
            "confidence": 0.0,
        }

    context = build_context(results)
    generated_answer = generate_answer(
        question,
        gemini_client,
        model_name,
        context,
    )

    sources = []
    seen_sources = set()

    for result in results:
        metadata = result.get("metadata", {})
        source = {
            "title": metadata.get("source_title", ""),
            "url": metadata.get("source_url", ""),
            "category": metadata.get("category", ""),
        }
        source_key = (
            source["title"],
            source["url"],
            source["category"],
        )

        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append(source)

    return {
        "answer": generated_answer,
        "sources": sources,
        "confidence": highest_confidence,
    }


def main() -> None:
    """Load project services and answer a sample NYSC question."""
    test_question = (
        "What documents should I take to NYSC orientation camp?"
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
                f"{source['category']} | "
                f"{source['url']}"
            )
    except Exception as error:
        print(f"Chat engine error: {error}")


if __name__ == "__main__":
    main()
