from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = BASE_DIR / "documents" / "rag_stage1_test_document.pdf"


def load_pdf(pdf_path=None, verbose=True):
    path = Path(pdf_path) if pdf_path else PDF_PATH
    reader = PdfReader(path)

    if verbose:
        print(f"Number of pages: {len(reader.pages)}")

    full_text = ""

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if verbose:
            print(f"\n========== PAGE {page_number} ==========")
            print(text[:500])

        full_text += text + "\n"

    return full_text


if __name__ == "__main__":
    text = load_pdf()

    print("\n========== TOTAL TEXT LENGTH ==========")
    print(len(text))