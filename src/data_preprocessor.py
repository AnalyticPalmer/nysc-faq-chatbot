"""Prepare NYSC FAQ records for later chatbot processing."""

from src.data_loader import load_faq_data


def clean_text(value):
    """Convert a value to clean text with unnecessary spaces removed."""
    if value is None:
        return ""

    return " ".join(str(value).split())


def prepare_faq_documents(records):
    """Convert FAQ records into text documents with useful metadata.

    Records without a question or answer are skipped because they do not
    contain enough information to create a useful FAQ document.
    """
    prepared_documents = []

    for record in records:
        question = clean_text(record.get("question"))
        answer = clean_text(record.get("answer"))

        if not question or not answer:
            continue

        category = clean_text(record.get("category"))
        source_title = clean_text(record.get("source_title"))

        document_text = (
            f"Category: {category}\n"
            f"Question: {question}\n"
            f"Answer: {answer}\n"
            f"Source: {source_title}"
        )

        # Keep the original identifying and source information with the text.
        metadata = {
            "id": clean_text(record.get("id")),
            "category": category,
            "question": question,
            "source_title": source_title,
            "source_url": clean_text(record.get("source_url")),
            "date_verified": clean_text(record.get("date_verified")),
        }

        prepared_documents.append(
            {
                "text": document_text,
                "metadata": metadata,
            }
        )

    return prepared_documents


def main():
    """Load FAQ records, prepare them, and print a short preview."""
    faq_records = load_faq_data()
    prepared_documents = prepare_faq_documents(faq_records)

    print(f"Total prepared documents: {len(prepared_documents)}")

    if prepared_documents:
        print("\nFirst prepared document text:")
        print(prepared_documents[0]["text"])
        print("\nFirst document metadata:")
        print(prepared_documents[0]["metadata"])


if __name__ == "__main__":
    main()
