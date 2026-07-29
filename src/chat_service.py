"""Provide a simple service interface for the NYSC FAQ chatbot."""

import os
import time

from dotenv import load_dotenv

from src.chat_engine import (
    DEFAULT_MODEL_NAME,
    RESPONSE_MODE_AUTO,
    VALID_RESPONSE_MODES,
    answer_question,
    load_gemini_client,
)
from src.embedding_model import load_embedding_model
from src.logger import logger
from src.retriever import load_vector_store
from src.vector_store import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    build_vector_store,
)


class NYSCChatService:
    """Load chatbot components once and answer NYSC FAQ questions."""

    def __init__(self) -> None:
        """Load the vector store, embedding model, and Gemini client."""
        self.last_topic: str | None = None
        logger.info("Chat service initialization started.")

        try:
            load_dotenv()

            if (
                not FAISS_INDEX_PATH.exists()
                or not METADATA_PATH.exists()
            ):
                logger.info(
                    "Vector store is missing and will be created."
                )

                try:
                    build_vector_store()
                except Exception as error:
                    logger.exception(
                        "Automatic vector store creation failed."
                    )
                    raise RuntimeError(
                        "The vector store could not be initialized."
                    ) from error

                logger.info("Vector store created successfully.")

            self.index, self.documents = load_vector_store()
            self.embedding_model = load_embedding_model()
            self.gemini_client = None

            try:
                self.gemini_client = load_gemini_client()
            except Exception:
                logger.warning(
                    "Gemini client is unavailable. Verified FAQ "
                    "fallback responses will be used."
                )

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

    @staticmethod
    def detect_conversational_intent(question: str) -> str | None:
        """Detect a simple conversational intent from normalized text."""
        normalized_question = "".join(
            character
            for character in question.lower().strip()
            if character.isalnum() or character.isspace()
        )
        normalized_question = " ".join(normalized_question.split())

        intent_phrases = {
            "greeting": {
                "hi",
                "hello",
                "hey",
                "good morning",
                "good afternoon",
                "good evening",
                "how are you",
            },
            "thanks": {
                "thanks",
                "thank you",
                "thank you very much",
                "appreciated",
                "that was helpful",
            },
            "farewell": {
                "bye",
                "goodbye",
                "see you",
                "talk later",
                "have a nice day",
            },
            "help": {
                "help",
                "what can you do",
                "how can you help me",
                "what do you know",
                "what questions can i ask",
            },
            "about": {
                "who are you",
                "what are you",
                "are you an official nysc chatbot",
                "tell me about this chatbot",
            },
        }

        for intent, phrases in intent_phrases.items():
            if normalized_question in phrases:
                return intent

        return None

    @staticmethod
    def build_conversational_response(intent: str) -> dict:
        """Build a structured response for a conversational intent."""
        responses = {
            "greeting": (
                "Hello! Welcome to the NYSC FAQ Assistant. I can help "
                "with registration, mobilization, orientation camp, "
                "relocation, PPA, CDS, monthly clearance, exemption, "
                "passing out, and other common NYSC questions. How can "
                "I help you today?"
            ),
            "thanks": (
                "You are welcome. I am glad I could help. Feel free to "
                "ask another NYSC-related question."
            ),
            "farewell": (
                "Goodbye. I wish you the best with your NYSC journey. "
                "You can return anytime you need more information."
            ),
            "help": (
                "You can ask me about NYSC registration, mobilization, "
                "Senate list, call-up letters, orientation camp, "
                "relocation, PPA, CDS, monthly clearance, exemption, "
                "passing out, foreign-trained graduate requirements, "
                "and portal support."
            ),
            "about": (
                "I am an independent AI-powered NYSC FAQ Assistant built "
                "as an educational AI/ML capstone project. I use a "
                "verified FAQ knowledge base, semantic search, FAISS, "
                "Sentence Transformers, and Google Gemini. I am not an "
                "official NYSC platform."
            ),
        }

        if intent not in responses:
            raise ValueError(
                f"Unsupported conversational intent: {intent}"
            )

        return {
            "question": "",
            "answer": responses[intent],
            "confidence": 100.0,
            "sources": [],
            "response_time": 0.0,
            "success": True,
            "error": None,
            "response_type": "conversational",
            "topic": None,
            "generation_mode": "conversational",
        }

    @staticmethod
    def extract_topic_from_sources(
        sources: list[dict],
    ) -> str | None:
        """Return the first non-empty category found in source metadata."""
        for source in sources:
            category = source.get("category")

            if isinstance(category, str) and category.strip():
                return " ".join(category.split())

        return None

    @staticmethod
    def is_follow_up_question(question: str) -> bool:
        """Return whether a short question may refer to an earlier topic."""
        if NYSCChatService.detect_conversational_intent(question):
            return False

        normalized_question = "".join(
            character
            for character in question.lower().strip()
            if character.isalnum() or character.isspace()
        )
        normalized_question = " ".join(normalized_question.split())

        if not normalized_question:
            return False

        word_references = {
            "it",
            "this",
            "that",
            "them",
            "there",
        }
        phrase_references = {
            "the process",
            "the requirement",
            "the letter",
            "the document",
        }
        words = normalized_question.split()

        if word_references.intersection(words):
            return True

        if any(
            phrase in normalized_question
            for phrase in phrase_references
        ):
            return True

        return len(words) < 10

    def resolve_follow_up_question(self, question: str) -> str:
        """Add the previous topic to a likely follow-up retrieval query."""
        if self.last_topic and self.is_follow_up_question(question):
            return (
                f"{question} The previous NYSC topic was: "
                f"{self.last_topic}."
            )

        return question

    def ask(
        self,
        question: str,
        response_mode: str = RESPONSE_MODE_AUTO,
    ) -> dict:
        """Answer one NYSC question and return a structured result.

        Args:
            question: The user's NYSC-related question.
            response_mode: Requested answer-generation mode.

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

        if response_mode not in VALID_RESPONSE_MODES:
            raise ValueError(
                f"Unsupported response mode: {response_mode}"
            )

        # Record only safe request details, never the question itself.
        logger.info(
            "Valid question received | character_length=%d | model=%s",
            len(cleaned_question),
            self.model_name,
        )

        conversational_intent = self.detect_conversational_intent(
            cleaned_question
        )

        if conversational_intent:
            response = self.build_conversational_response(
                conversational_intent
            )
            response["question"] = cleaned_question
            response["topic"] = self.last_topic
            response["requested_response_mode"] = response_mode
            return response

        # The resolved question is used internally only. The original cleaned
        # question remains in the response shown to the user.
        resolved_question = self.resolve_follow_up_question(
            cleaned_question
        )
        start_time = time.perf_counter()

        try:
            result = answer_question(
                resolved_question,
                self.index,
                self.documents,
                self.embedding_model,
                self.gemini_client,
                self.model_name,
                response_mode=response_mode,
            )

            response_time = time.perf_counter() - start_time
            confidence = round(
                float(result.get("confidence", 0.0)),
                2,
            )
            formatted_sources = self.format_sources(
                result.get("sources", [])
            )
            current_topic = self.extract_topic_from_sources(
                formatted_sources
            )

            if current_topic:
                self.last_topic = current_topic

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
                "response_type": "rag",
                "topic": current_topic,
                "generation_mode": result["generation_mode"],
                "requested_response_mode": response_mode,
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
                "response_type": "error",
                "topic": self.last_topic,
                "generation_mode": "error",
                "requested_response_mode": response_mode,
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
