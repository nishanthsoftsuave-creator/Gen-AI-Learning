from sentence_transformers import SentenceTransformer
from chunk_document import chunk_text
from load_pdf import load_pdf


model = SentenceTransformer("all-MiniLM-L6-v2")


def create_embeddings(chunks):
    embeddings = model.encode(chunks)

    return embeddings


if __name__ == "__main__":
    text = load_pdf()

    chunks = chunk_text(text)

    embeddings = create_embeddings(chunks)

    print("\n========== EMBEDDING RESULT ==========")
    print(f"Number of chunks: {len(chunks)}")
    print(f"Number of embeddings: {len(embeddings)}")
    print(f"Embedding dimensions: {len(embeddings[0])}")

    print("\nFirst chunk:")
    print(chunks[0])

    print("\nFirst embedding:")
    print(embeddings[0])