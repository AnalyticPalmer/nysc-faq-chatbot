"""
Detect scanned PDF documents and convert them into searchable PDFs using OCRmyPDF.

Input folder:
    data/raw

Output folder:
    data/ocr
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import fitz


PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OCR_OUTPUT_DIR = PROJECT_ROOT / "data" / "ocr"

MINIMUM_PAGE_CHARACTERS = 50
MINIMUM_DOCUMENT_CHARACTERS = 500


def extract_pdf_statistics(pdf_path: Path) -> dict:
    """
    Inspect a PDF and return basic text-extraction statistics.

    These statistics help determine whether the document is scanned
    or already contains machine-readable text.
    """
    document = fitz.open(pdf_path)

    total_characters = 0
    meaningful_pages = 0
    empty_pages = 0

    try:
        for page in document:
            text = page.get_text("text").strip()
            character_count = len(text)

            total_characters += character_count

            if character_count >= MINIMUM_PAGE_CHARACTERS:
                meaningful_pages += 1
            else:
                empty_pages += 1

        return {
            "total_pages": len(document),
            "total_characters": total_characters,
            "meaningful_pages": meaningful_pages,
            "empty_pages": empty_pages,
        }

    finally:
        document.close()


def is_scanned_pdf(statistics: dict) -> bool:
    """
    Decide whether a PDF requires OCR.

    A document is treated as scanned when it contains very little
    extractable text or no pages with meaningful text.
    """
    return (
        statistics["total_characters"] < MINIMUM_DOCUMENT_CHARACTERS
        or statistics["meaningful_pages"] == 0
    )


def build_output_path(input_pdf: Path) -> Path:
    """Create the OCR output filename."""
    output_filename = f"{input_pdf.stem}_ocr.pdf"
    return OCR_OUTPUT_DIR / output_filename


def run_ocr(input_pdf: Path, output_pdf: Path) -> bool:
    """
    Run OCRmyPDF on one scanned PDF.

    Returns True when OCR succeeds and the output file is created.
    """
    command = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "--force-ocr",
        "--language",
        "eng",
        "--deskew",
        "--rotate-pages",
        "--optimize",
        "1",
        "--output-type",
        "pdf",
        str(input_pdf),
        str(output_pdf),
    ]

    print("\nRunning OCR...")
    print(f"Input file:  {input_pdf.name}")
    print(f"Output file: {output_pdf.name}")

    try:
        completed_process = subprocess.run(
            command,
            check=False,
        )
    except OSError as error:
        print(f"OCR could not start: {error}")
        return False

    if completed_process.returncode != 0:
        print(
            f"OCR failed for {input_pdf.name}. "
            f"Exit code: {completed_process.returncode}"
        )
        return False

    if not output_pdf.exists():
        print("OCR finished, but the output file was not created.")
        return False

    print("OCR completed successfully.")
    return True


def verify_ocr_output(output_pdf: Path) -> dict:
    """Check whether the OCR output contains extractable text."""
    return extract_pdf_statistics(output_pdf)


def process_pdf(pdf_path: Path) -> str:
    """
    Inspect and process one PDF.

    Possible return values:
        created
        readable
        existing
        failed
    """
    print("\n" + "=" * 70)
    print(f"Checking: {pdf_path.name}")
    print("=" * 70)

    try:
        statistics = extract_pdf_statistics(pdf_path)
    except Exception as error:
        print(f"Could not inspect PDF: {error}")
        return "failed"

    print(f"Total pages: {statistics['total_pages']}")
    print(f"Extracted characters: {statistics['total_characters']}")
    print(f"Meaningful pages: {statistics['meaningful_pages']}")
    print(f"Empty or nearly empty pages: {statistics['empty_pages']}")

    if not is_scanned_pdf(statistics):
        print("Readable text already exists. OCR is not required.")
        return "readable"

    print("Scanned PDF detected.")

    output_pdf = build_output_path(pdf_path)

    if output_pdf.exists():
        print(f"OCR output already exists: {output_pdf.name}")
        return "existing"

    successful = run_ocr(
        input_pdf=pdf_path,
        output_pdf=output_pdf,
    )

    if not successful:
        return "failed"

    try:
        output_statistics = verify_ocr_output(output_pdf)
    except Exception as error:
        print(f"Could not verify OCR output: {error}")
        return "failed"

    print("\nOCR output verification")
    print("-" * 40)
    print(f"Total pages: {output_statistics['total_pages']}")
    print(
        f"Extracted characters: "
        f"{output_statistics['total_characters']}"
    )
    print(
        f"Meaningful pages: "
        f"{output_statistics['meaningful_pages']}"
    )
    print(
        f"Empty or nearly empty pages: "
        f"{output_statistics['empty_pages']}"
    )

    if output_statistics["total_characters"] < MINIMUM_DOCUMENT_CHARACTERS:
        print(
            "Warning: OCR output still contains very little text. "
            "The scan quality may be poor."
        )
    else:
        print("OCR output contains readable text.")

    return "created"


def main() -> None:
    """Process all PDF files inside data/raw."""
    print("=" * 70)
    print("NYSC SCANNED PDF OCR PROCESSOR")
    print("=" * 70)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Input folder: {RAW_DATA_DIR}")
    print(f"Output folder: {OCR_OUTPUT_DIR}")

    if not RAW_DATA_DIR.exists():
        print("\nError: data/raw does not exist.")
        print("Create the folder and place your PDF files inside it.")
        return

    OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(
        file_path
        for file_path in RAW_DATA_DIR.iterdir()
        if file_path.is_file()
        and file_path.suffix.lower() == ".pdf"
    )

    if not pdf_files:
        print("\nNo PDF files were found inside data/raw.")
        return

    print(f"\nPDF files found: {len(pdf_files)}")

    created_count = 0
    readable_count = 0
    existing_count = 0
    failed_count = 0
    scanned_count = 0

    for pdf_path in pdf_files:
        result = process_pdf(pdf_path)

        if result in {"created", "existing", "failed"}:
            try:
                statistics = extract_pdf_statistics(pdf_path)

                if is_scanned_pdf(statistics):
                    scanned_count += 1
            except Exception:
                pass

        if result == "created":
            created_count += 1
        elif result == "readable":
            readable_count += 1
        elif result == "existing":
            existing_count += 1
        else:
            failed_count += 1

    print("\n" + "=" * 70)
    print("OCR SUMMARY")
    print("=" * 70)
    print(f"Total PDFs checked: {len(pdf_files)}")
    print(f"Scanned PDFs detected: {scanned_count}")
    print(f"OCR files created: {created_count}")
    print(f"Readable PDFs skipped: {readable_count}")
    print(f"Existing OCR files skipped: {existing_count}")
    print(f"Failures: {failed_count}")
    print(f"OCR output folder: {OCR_OUTPUT_DIR}")


if __name__ == "__main__":
    main()