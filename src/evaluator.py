"""Evaluate the semantic retriever without calling the Gemini API."""

import json
import time
from pathlib import Path

from src.embedding_model import load_embedding_model
from src.retriever import load_vector_store, search_faq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DATA_PATH = (
    PROJECT_ROOT / "data" / "processed" / "evaluation_questions.json"
)
EVALUATION_REPORT_PATH = (
    PROJECT_ROOT / "reports" / "evaluation_report.json"
)


def load_evaluation_data() -> list[dict]:
    """Load and validate the retriever evaluation questions.

    Returns:
        A non-empty list of evaluation records.

    Raises:
        FileNotFoundError: If the evaluation data file is missing.
        ValueError: If the loaded data is not a non-empty list.
    """
    if not EVALUATION_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Evaluation data file was not found: "
            f"{EVALUATION_DATA_PATH}"
        )

    with EVALUATION_DATA_PATH.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list) or not records:
        raise ValueError(
            "Evaluation data must be a non-empty list of records."
        )

    return records


def evaluate_retriever() -> dict:
    """Evaluate top-result category accuracy for the semantic retriever."""
    evaluation_records = load_evaluation_data()
    index, documents = load_vector_store()
    embedding_model = load_embedding_model()

    results = []

    for record in evaluation_records:
        start_time = time.perf_counter()

        retrieved_results = search_faq(
            record["question"],
            index,
            documents,
            embedding_model,
            top_k=3,
        )

        response_time = time.perf_counter() - start_time

        if retrieved_results:
            top_result = retrieved_results[0]
            retrieved_category = top_result["metadata"].get(
                "category",
                "",
            )
            confidence = float(top_result.get("confidence", 0.0))
        else:
            retrieved_category = ""
            confidence = 0.0

        expected_category = record["expected_category"]
        correct = retrieved_category == expected_category

        results.append(
            {
                "id": record["id"],
                "question": record["question"],
                "expected_category": expected_category,
                "retrieved_category": retrieved_category,
                "confidence": round(confidence, 2),
                "correct": correct,
                "response_time": round(response_time, 2),
            }
        )

    total_questions = len(results)
    correct_results = sum(
        1 for result in results if result["correct"]
    )
    incorrect_results = total_questions - correct_results
    total_confidence = sum(
        result["confidence"] for result in results
    )
    total_response_time = sum(
        result["response_time"] for result in results
    )

    accuracy = (correct_results / total_questions) * 100
    average_confidence = total_confidence / total_questions
    average_response_time = total_response_time / total_questions

    return {
        "summary": {
            "total_questions": total_questions,
            "correct_results": correct_results,
            "incorrect_results": incorrect_results,
            "accuracy": round(accuracy, 2),
            "average_confidence": round(
                average_confidence,
                2,
            ),
            "average_response_time": round(
                average_response_time,
                2,
            ),
        },
        "results": results,
    }


def save_evaluation_report(report: dict) -> None:
    """Save an evaluation report as readable JSON."""
    EVALUATION_REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with EVALUATION_REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    """Run the retriever evaluation, save it, and print its summary."""
    report = evaluate_retriever()
    save_evaluation_report(report)
    summary = report["summary"]

    print(f"Total questions: {summary['total_questions']}")
    print(f"Correct results: {summary['correct_results']}")
    print(f"Incorrect results: {summary['incorrect_results']}")
    print(f"Accuracy: {summary['accuracy']:.2f}%")
    print(
        f"Average confidence: "
        f"{summary['average_confidence']:.2f}%"
    )
    print(
        f"Average response time: "
        f"{summary['average_response_time']:.2f} seconds"
    )
    print(f"Report location: {EVALUATION_REPORT_PATH}")


if __name__ == "__main__":
    main()
