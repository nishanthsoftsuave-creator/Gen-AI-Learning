from pathlib import Path

import chromadb

from chunk_document import chunk_text
from create_embeddings import create_embeddings
from load_pdf import load_pdf


BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "rag_documents"


def store_embeddings(
    pdf_path=None,
    reset=True,
    verbose=True,
):
    # Load PDF text
    text = load_pdf(pdf_path, verbose=verbose)

    # Split text into chunks
    chunks = chunk_text(text)

    if not chunks or not "".join(chunks).strip():
        raise ValueError("No text could be extracted from the PDF.")

    # Create embeddings
    embeddings = create_embeddings(chunks)

    # Create persistent ChromaDB client
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    if reset:
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    # Create or get collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    # Create IDs for each chunk
    ids = [
        f"chunk_{index}"
        for index in range(len(chunks))
    ]

    # Store chunks + embeddings
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist()
    )

    if verbose:
        print("\n========== VECTOR STORE ==========")
        print(f"Total chunks stored: {collection.count()}")
        print(f"Collection: {COLLECTION_NAME}")

    return {
        "chunks": collection.count(),
        "collection": COLLECTION_NAME,
    }


if __name__ == "__main__":
    store_embeddings()
