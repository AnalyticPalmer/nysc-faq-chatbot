"""Diagnose text extraction from NYSC Bye-Laws PDF files."""

from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


PROJECT_ROOT = Path(__file__).resolve().parent
OCR_DATA_DIR = PROJECT_ROOT / "data" / "ocr"

MEANINGFUL_TEXT_THRESHOLD = 20
PREVIEW_LENGTH = 300


def is_bye_laws_file(file_path: Path) -> bool:
    """Return True when the filename appears to be a Bye-Laws document."""
    normalized_name = (
        file_path.stem
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )

    return "byelaw" in normalized_name


def clean_preview(text: str) -> str:
    """Prepare extracted text for a readable single-line preview."""
    return " ".join(text.split())[:PREVIEW_LENGTH]


def diagnose_with_pymupdf(file_path: Path) -> dict:
    """Test page-level extraction using PyMuPDF."""
    print("\nPyMuPDF extraction")
    print("-" * 60)

    if fitz is None:
        print("PyMuPDF is not installed.")
        return {
            "total_pages": 0,
            "total_characters": 0,
            "pages_with_text": 0,
            "empty_pages": 0,
        }

    document = fitz.open(file_path)

    total_pages = len(document)
    total_characters = 0
    pages_with_text = 0
    empty_pages = 0

    print(f"Total pages: {total_pages}")

    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            character_count = len(text)

            total_characters += character_count

            if character_count > MEANINGFUL_TEXT_THRESHOLD:
                pages_with_text += 1
            else:
                empty_pages += 1

            print(
                f"Page {page_number}: "
                f"{character_count} extracted characters"
            )

            if text:
                print(f"Preview: {clean_preview(text)}")
            else:
                print("Preview: NO EXTRACTABLE TEXT")

    finally:
        document.close()

    print("\nPyMuPDF summary")
    print(f"Total extracted characters: {total_characters}")
    print(f"Pages with meaningful text: {pages_with_text}")
    print(f"Empty or nearly empty pages: {empty_pages}")

    return {
        "total_pages": total_pages,
        "total_characters": total_characters,
        "pages_with_text": pages_with_text,
        "empty_pages": empty_pages,
    }


def diagnose_with_pypdf(file_path: Path) -> dict:
    """Test page-level extraction using pypdf."""
    print("\npypdf extraction")
    print("-" * 60)

    if PdfReader is None:
        print("pypdf is not installed.")
        return {
            "total_pages": 0,
            "total_characters": 0,
            "pages_with_text": 0,
            "empty_pages": 0,
        }

    reader = PdfReader(str(file_path))

    total_pages = len(reader.pages)
    total_characters = 0
    pages_with_text = 0
    empty_pages = 0

    print(f"Total pages: {total_pages}")

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            print(
                f"Page {page_number}: extraction failed: {error}"
            )
            empty_pages += 1
            continue

        text = text.strip()
        character_count = len(text)

        total_characters += character_count

        if character_count > MEANINGFUL_TEXT_THRESHOLD:
            pages_with_text += 1
        else:
            empty_pages += 1

        print(
            f"Page {page_number}: "
            f"{character_count} extracted characters"
        )

        if text:
            print(f"Preview: {clean_preview(text)}")
        else:
            print("Preview: NO EXTRACTABLE TEXT")

    print("\npypdf summary")
    print(f"Total extracted characters: {total_characters}")
    print(f"Pages with meaningful text: {pages_with_text}")
    print(f"Empty or nearly empty pages: {empty_pages}")

    return {
        "total_pages": total_pages,
        "total_characters": total_characters,
        "pages_with_text": pages_with_text,
        "empty_pages": empty_pages,
    }


def print_final_assessment(
    file_path: Path,
    pymupdf_result: dict,
    pypdf_result: dict,
) -> None:
    """Print a simple conclusion for one OCR PDF."""
    best_character_count = max(
        pymupdf_result["total_characters"],
        pypdf_result["total_characters"],
    )

    best_meaningful_pages = max(
        pymupdf_result["pages_with_text"],
        pypdf_result["pages_with_text"],
    )

    print("\nFinal assessment")
    print("-" * 60)

    if best_character_count >= 1000 and best_meaningful_pages >= 5:
        print(f"SUCCESS: {file_path.name} contains searchable OCR text.")
        print(
            "The document is ready for PDF preprocessing, chunking, "
            "embedding and vector-store indexing."
        )
    elif best_character_count > 0:
        print(
            f"WARNING: {file_path.name} contains some extracted text, "
            "but the OCR quality may still be poor."
        )
    else:
        print(
            f"FAILED: {file_path.name} still contains no extractable text."
        )


def main() -> None:
    """Find and inspect all OCR-generated Bye-Laws PDFs."""
    print("=" * 70)
    print("NYSC BYE-LAWS OCR EXTRACTION DIAGNOSTIC")
    print("=" * 70)
    print(f"OCR directory: {OCR_DATA_DIR}")

    if not OCR_DATA_DIR.exists():
        print("\nERROR: data/ocr directory was not found.")
        print(
            "Run the OCR conversion first so that searchable PDFs "
            "are created inside data/ocr."
        )
        return

    pdf_files = sorted(OCR_DATA_DIR.rglob("*.pdf"))

    bye_laws_files = [
        file_path
        for file_path in pdf_files
        if is_bye_laws_file(file_path)
    ]

    print(f"Total OCR PDF files found: {len(pdf_files)}")
    print(f"Bye-Laws OCR files found: {len(bye_laws_files)}")

    if not bye_laws_files:
        print(
            "\nNo OCR PDF filename containing 'byelaw' was found."
        )

        if pdf_files:
            print("\nAvailable OCR PDF files:")

            for file_path in pdf_files:
                print(f"- {file_path.name}")
        else:
            print("\nThe data/ocr folder is currently empty.")

        return

    for file_number, file_path in enumerate(
        bye_laws_files,
        start=1,
    ):
        print("\n" + "=" * 70)
        print(f"FILE {file_number}: {file_path.name}")
        print("=" * 70)

        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        print(f"File size: {file_size_mb:.2f} MB")
        print(
            f"Relative path: "
            f"{file_path.relative_to(PROJECT_ROOT)}"
        )

        pymupdf_result = diagnose_with_pymupdf(file_path)
        pypdf_result = diagnose_with_pypdf(file_path)

        print_final_assessment(
            file_path=file_path,
            pymupdf_result=pymupdf_result,
            pypdf_result=pypdf_result,
        )

    print("\n" + "=" * 70)
    print("HOW TO INTERPRET THE RESULT")
    print("=" * 70)
    print(
        "1. SUCCESS means the OCR PDF now contains searchable text."
    )
    print(
        "2. WARNING means text exists, but OCR quality may require review."
    )
    print(
        "3. FAILED means the document still requires another OCR attempt."
    )


if __name__ == "__main__":
    main()