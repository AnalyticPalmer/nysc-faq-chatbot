from pathlib import Path
from pypdf import PdfReader


pdf_folder = Path("data/raw")
pdf_files = list(pdf_folder.glob("*.pdf"))

print(f"PDF files found: {len(pdf_files)}")

for pdf_path in pdf_files:
    try:
        reader = PdfReader(pdf_path)

        extracted_text = ""

        for page in reader.pages[:3]:
            extracted_text += page.extract_text() or ""

        print("\n" + "=" * 60)
        print(f"File: {pdf_path.name}")
        print(f"Pages: {len(reader.pages)}")
        print(f"Characters extracted: {len(extracted_text)}")
        print(f"Preview: {extracted_text[:300]}")

    except Exception as error:
        print(f"Could not read {pdf_path.name}: {error}")