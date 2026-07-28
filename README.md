# NYSC FAQ Chatbot

The NYSC FAQ Chatbot is a retrieval-augmented generation (RAG) application
that answers common National Youth Service Corps questions from a curated
knowledge base of official NYSC information. It uses semantic search to find
relevant FAQs and Google Gemini to produce a clear, source-grounded response.

> This is an independent educational project and is not an official NYSC
> platform. Confirm time-sensitive information through official NYSC channels.

## Technology stack

- Python
- Streamlit
- FAISS
- Sentence Transformers (`all-MiniLM-L6-v2`)
- Google Gemini

## Project structure

```text
app/               Streamlit interface
data/faq/          Verified FAQ knowledge base
data/processed/    Retriever evaluation questions
reports/           Evaluation output
src/               Loading, retrieval, generation, and evaluation modules
tests/             Automated tests
vector_store/      Published FAISS index and aligned metadata
```

## Local setup

Use Python 3.10 or newer. Create and activate a virtual environment of your
choice, then install the declared runtime dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your own Gemini API key, or provide the
same variables through your deployment platform:

```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
```

Never commit `.env` or a real API key.

## Run the application

From the repository root:

```bash
streamlit run app/app.py
```

The repository includes the FAISS index and its matching metadata so the
application can start without rebuilding the vector store.

## Validation and evaluation

Validate the FAQ dataset:

```bash
python -m src.validate_faq
```

Evaluate semantic retrieval without calling Gemini:

```bash
python -m src.evaluator
```

Rebuilding the vector store is only necessary after changing the FAQ dataset:

```bash
python -m src.vector_store
```
