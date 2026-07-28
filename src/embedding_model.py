"""Load the embedding model and generate embeddings for FAQ text."""

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_embedding_model() -> SentenceTransformer:
    """Load and return the configured Sentence Transformer model.

    Raises:
        RuntimeError: If the embedding model cannot be loaded.
    """
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as error:
        raise RuntimeError(
            f"Could not load the embedding model '{MODEL_NAME}': {error}"
        ) from error

    return model


def generate_embeddings(
    texts: list[str],
    model: SentenceTransformer,
) -> np.ndarray:
    """Generate normalized NumPy embeddings for non-empty text strings.

    Args:
        texts: A list of text strings to embed.
        model: A loaded Sentence Transformer model.

    Returns:
        A NumPy array containing one embedding for each valid text.

    Raises:
        TypeError: If texts is not a list.
        ValueError: If the list contains no valid text.
    """
    if not isinstance(texts, list):
        raise TypeError("texts must be provided as a list.")

    # Ignore empty strings and remove extra spaces around valid strings.
    valid_texts = [
        text.strip()
        for text in texts
        if isinstance(text, str) and text.strip()
    ]

    if not valid_texts:
        raise ValueError("No valid text was provided for embedding.")

    embeddings = model.encode(
        valid_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return np.asarray(embeddings)


def main() -> None:
    """Load the model, embed sample questions, and print a summary."""
    sample_questions = [
        "How do I register for NYSC?",
        "What documents should I take to camp?",
        "How can I apply for relocation?",
    ]

    model = load_embedding_model()
    embeddings = generate_embeddings(sample_questions, model)

    print(f"Model name: {MODEL_NAME}")
    print(f"Number of texts embedded: {len(sample_questions)}")
    print(f"Embedding array shape: {embeddings.shape}")
    print(f"Embedding dimension: {embeddings.shape[1]}")


if __name__ == "__main__":
    main()
