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
from src.logger import logger
from src.retriever import load_vector_store


class NYSCChatService:
    """Load chatbot components once and answer NYSC FAQ questions."""

    def __init__(self) -> None:
        """Load the vector store, embedding model, and Gemini client."""
        logger.info("Chat service initialization started.")

        try:
            load_dotenv()

            self.index, self.documents = load_vector_store()
            self.embedding_model = load_embedding_model()
            self.gemini_client = load_gemini_client()
            self.model_name = os.getenv(
                "GEMINI_MODEL",
                DEFAULT_MODEL_NAME,
            )
        except Exception:
            # Do not include environment values or credentials in messages.
            logger.exception("Chat service initialization failed.")
            raise

        logger.info("Chat service initialization completed successfully.")

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

        # Record only safe request details, never the question itself.
        logger.info(
            "Valid question received | character_length=%d | model=%s",
            len(cleaned_question),
            self.model_name,
        )

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
            confidence = round(
                float(result.get("confidence", 0.0)),
                2,
            )
            formatted_sources = self.format_sources(
                result.get("sources", [])
            )

            logger.info(
                "Question processed | success=%s | confidence=%.2f | "
                "response_time=%.2f | source_count=%d",
                True,
                confidence,
                response_time,
                len(formatted_sources),
            )

            return {
                "question": cleaned_question,
                "answer": result["answer"],
                "confidence": confidence,
                "sources": formatted_sources,
                "response_time": round(response_time, 2),
                "success": True,
                "error": None,
            }
        except Exception as error:
            response_time = time.perf_counter() - start_time

            logger.exception(
                "Question processing failed | success=%s | "
                "response_time=%.2f",
                False,
                response_time,
            )

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
