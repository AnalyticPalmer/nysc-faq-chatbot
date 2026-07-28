"""Validate the structure and content of the NYSC FAQ dataset."""

import json
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "id",
    "category",
    "question",
    "answer",
    "source_title",
    "source_url",
    "date_verified",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAQ_FILE = PROJECT_ROOT / "data" / "faq" / "nysc_faq.json"


def is_empty(value: object) -> bool:
    """Return True when a value is missing useful content."""
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def validate_faq() -> None:
    """Load the FAQ dataset, validate its records, and print a summary."""
    try:
        with FAQ_FILE.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not load the FAQ dataset: {error}")
        return

    if not isinstance(records, list) or not records:
        print("The FAQ dataset must contain a non-empty list.")
        return

    invalid_records = []
    questions = []
    categories = set()

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            invalid_records.append(index)
            continue

        missing_fields = REQUIRED_FIELDS - record.keys()
        empty_fields = [
            field
            for field in REQUIRED_FIELDS
            if field in record and is_empty(record[field])
        ]

        if missing_fields or empty_fields:
            invalid_records.append(index)

        question = record.get("question")
        if isinstance(question, str) and question.strip():
            questions.append(question.strip().casefold())

        category = record.get("category")
        if isinstance(category, str) and category.strip():
            categories.add(category.strip())

    question_counts = Counter(questions)
    duplicate_questions = [
        question
        for question, count in question_counts.items()
        if count > 1
    ]

    print(f"Total FAQ records: {len(records)}")
    print(f"Total categories: {len(categories)}")
    print(f"Category names: {', '.join(sorted(categories))}")
    print(f"Duplicate questions: {len(duplicate_questions)}")
    print(f"Invalid records: {len(invalid_records)}")

    if not duplicate_questions and not invalid_records:
        print("FAQ dataset validation successful.")


if __name__ == "__main__":
    validate_faq()
