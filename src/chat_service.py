"""Provide a simple service interface for the NYSC FAQ chatbot."""

import os
import time

from dotenv import load_dotenv

from src.chat_engine import (
    DEFAULT_MODEL_NAME,
    answer_question,
    load_gemini_client,
)
from src.embedding_model import load_embedding_model
from src.retriever import load_vector_store


class NYSCChatService:
    """Load chatbot components once and answer NYSC FAQ questions."""

    def __init__(self) -> None:
        """Load the vector store, embedding model, and Gemini client."""
        load_dotenv()

        self.index, self.documents = load_vector_store()
        self.embedding_model = load_embedding_model()
        self.gemini_client = load_gemini_client()
        self.model_name = os.getenv(
            "GEMINI_MODEL",
            DEFAULT_MODEL_NAME,
        )

    @staticmethod
    def format_sources(sources: list[dict]) -> list[dict]:
        """Remove duplicate source URLs and return consistent source data."""
        formatted_sources = []
        seen_urls = set()

        for source in sources:
            title = source.get("title", "")
            url = source.get("url", "")

            if not title or url in seen_urls:
                continue

            seen_urls.add(url)
            formatted_sources.append(
                {
                    "title": title,
                    "url": url,
                    "category": source.get("category", ""),
                }
            )

        return formatted_sources

    def ask(self, question: str) -> dict:
        """Answer one NYSC question and return a structured result.

        Args:
            question: The user's NYSC-related question.

        Returns:
            A dictionary containing the answer, confidence, sources,
            timing information, and processing status.

        Raises:
            TypeError: If question is not a string.
            ValueError: If question is empty.
        """
        if not isinstance(question, str):
            raise TypeError("question must be a string.")

        cleaned_question = " ".join(question.split())

        if not cleaned_question:
            raise ValueError("question cannot be empty.")

        start_time = time.perf_counter()

        try:
            result = answer_question(
                cleaned_question,
                self.index,
                self.documents,
                self.embedding_model,
                self.gemini_client,
                self.model_name,
            )

            response_time = time.perf_counter() - start_time

            return {
                "question": cleaned_question,
                "answer": result["answer"],
                "confidence": round(
                    float(result.get("confidence", 0.0)),
                    2,
                ),
                "sources": self.format_sources(
                    result.get("sources", [])
                ),
                "response_time": round(response_time, 2),
                "success": True,
                "error": None,
            }
        except Exception as error:
            response_time = time.perf_counter() - start_time

            # Report only the error type so credentials or sensitive
            # request details cannot appear in the returned message.
            safe_error = (
                f"Question processing failed "
                f"({type(error).__name__})."
            )

            return {
                "question": cleaned_question,
                "answer": (
                    "Sorry, I could not process your question at this "
                    "time. Please try again."
                ),
                "confidence": 0.0,
                "sources": [],
                "response_time": round(response_time, 2),
                "success": False,
                "error": safe_error,
            }


def main() -> None:
    """Create the chat service and print one sample response."""
    test_question = "How can I apply for NYSC relocation?"

    try:
        service = NYSCChatService()
        result = service.ask(test_question)

        print(f"Question: {result['question']}")
        print(f"Answer: {result['answer']}")
        print(f"Confidence: {result['confidence']}%")
        print(f"Response time: {result['response_time']} seconds")
        print(f"Success: {result['success']}")
        print("Source titles:")

        for source in result["sources"]:
            print(f"- {source['title']}")
    except Exception:
        # Keep startup errors generic so sensitive information is not shown.
        print("Could not start the NYSC chat service.")


if __name__ == "__main__":
    main()
