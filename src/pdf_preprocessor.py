"""Prepare and chunk official NYSC PDF documents for retrieval."""

import re
from pathlib import Path

from src.pdf_loader import load_all_pdfs


HEADING_PREFIXES = (
    "LEAVE", "TRAVEL", "ABSENCE", "DISCIPLINE", "OFFENCES",
    "PENALTIES", "SANCTIONS", "PERMISSION", "DUTIES", "CONDUCT",
    "ORIENTATION", "POSTING", "CDS", "COMMUNITY DEVELOPMENT",
)


def normalize_pdf_title(filename: str) -> str:
    """Return a clean source title while preserving the actual filename."""
    stem = Path(filename).stem
    compact_stem = re.sub(r"[^a-z0-9]", "", stem.lower())

    if "byelaw" in compact_stem or "bylaws" in compact_stem:
        return "NYSC Bye-Laws"

    return " ".join(
        re.sub(r"[_-]+", " ", stem).split()
    )


def _document_label(source_title: str) -> str:
    """Create a stable normalized label included in embedded PDF text."""
    label = re.sub(r"[^a-z0-9]+", "_", source_title.lower()).strip("_")
    return label or "nysc_official_document"


def _is_heading(line: str) -> bool:
    """Detect simple legal-document headings without over-parsing PDFs."""
    cleaned = " ".join(line.split()).strip(" :-")
    if not cleaned or len(cleaned) > 120:
        return False

    upper_text = cleaned.upper()
    letters = [character for character in cleaned if character.isalpha()]
    uppercase_ratio = (
        sum(character.isupper() for character in letters) / len(letters)
        if letters
        else 0.0
    )
    numbered = bool(
        re.match(r"^(?:\d+(?:\.\d+)*|[IVXLCDM]+)[.)\s-]+", upper_text)
    )
    prefixed = upper_text.startswith(HEADING_PREFIXES)
    return prefixed or numbered or (
        len(cleaned.split()) <= 12 and uppercase_ratio >= 0.8
    )


def _is_usable_content(text: str) -> bool:
    """Discard empty, symbol-heavy, and obvious header/footer fragments."""
    cleaned = " ".join(text.split())
    alphanumeric = sum(character.isalnum() for character in cleaned)

    if alphanumeric < 20:
        return False

    if re.fullmatch(r"(?:page\s*)?\d+(?:\s+of\s+\d+)?", cleaned.lower()):
        return False

    if alphanumeric / max(len(cleaned), 1) < 0.45:
        return False

    footer_text = re.sub(r"[^a-z]", "", cleaned.lower())
    if footer_text in {
        "nyscpublicationnotforsaleorreprint",
        "nationalyouthservicecorps",
    }:
        return False

    return True


def _split_content(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split PDF prose near sentence boundaries with a small word overlap."""
    cleaned = " ".join(text.split())
    if not _is_usable_content(cleaned):
        return []

    sentences = re.split(r"(?<=[.!?;:])\s+", cleaned)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if current and len(current) + len(sentence) + 1 > chunk_size:
            if _is_usable_content(current):
                chunks.append(current)

            overlap_words = current.split()
            overlap_text = ""
            while overlap_words and len(overlap_text) < chunk_overlap:
                overlap_text = " ".join(overlap_words[-1:] + overlap_text.split())
                overlap_words.pop()

            current = f"{overlap_text} {sentence}".strip()
        else:
            current = f"{current} {sentence}".strip()

    if _is_usable_content(current):
        chunks.append(current)

    return chunks


def _page_sections(
    page_text: str,
    previous_heading: str,
) -> tuple[list[tuple[str, str]], str]:
    """Group page text under detected headings and carry heading context."""
    sections = []
    current_heading = previous_heading
    content_lines = []

    for raw_line in page_text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue

        if _is_heading(line):
            content = " ".join(content_lines).strip()
            if _is_usable_content(content):
                sections.append((current_heading, content))
            current_heading = line
            content_lines = []
        else:
            content_lines.append(line)

    content = " ".join(content_lines).strip()
    if _is_usable_content(content):
        sections.append((current_heading, content))

    return sections, current_heading


def prepare_pdf_documents(
    pdf_records: list[dict],
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[dict]:
    """Create page-aware, context-rich chunks from loaded PDF records."""
    prepared_chunks = []

    for file_index, record in enumerate(pdf_records, start=1):
        source_path = str(record.get("source_path", "")).strip()
        filename = str(
            record.get("filename") or Path(source_path).name
        ).strip()
        source_title = normalize_pdf_title(
            filename or str(record.get("source_title", ""))
        )
        document_label = _document_label(source_title)
        pages = record.get("pages")

        if not isinstance(pages, list):
            pages = [{"page_number": 1, "text": record.get("text", "")}]

        current_heading = ""
        file_chunk_index = 0

        for page in pages:
            page_number = int(page.get("page_number", 1))
            page_text = str(page.get("text", ""))
            sections, current_heading = _page_sections(
                page_text,
                current_heading,
            )

            for section_title, section_text in sections:
                for content_chunk in _split_content(
                    section_text,
                    chunk_size,
                    chunk_overlap,
                ):
                    embedded_text = (
                        f"Document Title: {source_title}\n"
                        f"Document Label: {document_label}\n"
                        f"Filename: {filename}\n"
                        f"Page: {page_number}\n"
                        f"Section: {section_title or 'General'}\n"
                        f"Content:\n{content_chunk}"
                    )
                    prepared_chunks.append(
                        {
                            "text": embedded_text,
                            "document_type": "pdf",
                            "metadata": {
                                "id": f"pdf-{file_index}-{file_chunk_index}",
                                "category": "Official Document",
                                "question": "",
                                "source_title": source_title,
                                "source_url": "",
                                "source_path": source_path,
                                "filename": filename,
                                "page_number": page_number,
                                "section_title": section_title or "General",
                                "document_label": document_label,
                                "date_verified": "",
                                "document_type": "pdf",
                                "chunk_index": file_chunk_index,
                            },
                        }
                    )
                    file_chunk_index += 1

    return prepared_chunks


def load_and_chunk_pdf_documents(
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[dict]:
    """Load PDFs and create page-aware chunks with embedded source context."""
    return prepare_pdf_documents(
        load_all_pdfs(),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def main() -> None:
    """Run PDF preparation and print a short, safe summary."""
    pdf_chunks = load_and_chunk_pdf_documents()
    print(f"Total PDF chunks: {len(pdf_chunks)}")

    if pdf_chunks:
        print(f"First chunk metadata: {pdf_chunks[0]['metadata']}")
    else:
        print("First chunk metadata: None")


if __name__ == "__main__":
    main()
