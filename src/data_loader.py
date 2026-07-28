"""Load the NYSC FAQ dataset from its JSON file."""

import json
from pathlib import Path


# Build the data path from the project root so the loader works from any
# current working directory.
FAQ_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "faq"
    / "nysc_faq.json"
)


def load_faq_data() -> list[dict]:
    """Load and return the FAQ records from the JSON dataset.

    Raises:
        FileNotFoundError: If the FAQ JSON file cannot be found.
        json.JSONDecodeError: If the file does not contain valid JSON.
        ValueError: If the loaded data is not a non-empty list.
    """
    if not FAQ_DATA_PATH.exists():
        raise FileNotFoundError(
            f"FAQ data file was not found: {FAQ_DATA_PATH}"
        )

    with FAQ_DATA_PATH.open("r", encoding="utf-8") as file:
        faq_records = json.load(file)

    if not isinstance(faq_records, list):
        raise ValueError("The FAQ dataset must be a list of records.")

    if not faq_records:
        raise ValueError("The FAQ dataset is empty.")

    return faq_records


def main() -> None:
    """Load the FAQ data and print a short dataset preview."""
    try:
        faq_records = load_faq_data()
        print(f"Total FAQ records: {len(faq_records)}")
        print(f"First FAQ question: {faq_records[0]['question']}")
    except FileNotFoundError as error:
        print(f"File error: {error}")
    except json.JSONDecodeError as error:
        print(f"JSON error: The FAQ data file is not valid JSON. {error}")
    except ValueError as error:
        print(f"Data error: {error}")


if __name__ == "__main__":
    main()
