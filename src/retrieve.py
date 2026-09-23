import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "rag_documents"

model = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve_documents(question, top_k=3):
    # Connect to existing ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Get our collection
    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    # Convert question into embedding
    question_embedding = model.encode(question).tolist()

    # Search for similar chunks
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k
    )

    return results


if __name__ == "__main__":
    question = input("Enter your question: ")

    results = retrieve_documents(question)

    print("\n========== RETRIEVED CHUNKS ==========")

    for index, document in enumerate(
        results["documents"][0],
        start=1
    ):
        print(f"\n--- Result {index} ---")
        print(document)

    print("\n========== DISTANCES ==========")

    for distance in results["distances"][0]:
        print(distance)