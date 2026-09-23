import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from groq import Groq

from create_embeddings import model as embedding_model
from retrieval import hybrid_retrieve
from tracing import create_trace_id, save_trace


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "rag_documents"

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)


groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def retrieve_documents(question, top_k=3):
    client = chromadb.PersistentClient(
        path=CHROMA_PATH
    )

    try:
        collection = client.get_collection(
            name=COLLECTION_NAME
        )
    except Exception:
        return []

    if collection.count() == 0:
        return []

    question_embedding = embedding_model.encode(
        question
    ).tolist()

    return hybrid_retrieve(
        collection,
        question,
        question_embedding,
        top_k=top_k
    )


def generate_answer(question, documents):

    context = "\n\n".join(
        document["text"]
        for document in documents
    )

    prompt = f"""
Answer the question using only the provided context.

If the answer is not available in the context,
say that you don't know based on the provided document.

Context:
{context}

Question:
{question}

Answer:
"""

    temperature = 0.3

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=temperature,
    )

    answer = response.choices[0].message.content

    return answer, prompt, temperature


if __name__ == "__main__":

    while True:

        question = input(
            "Enter your question (or type 'exit' to quit): "
        )

        if question.lower() == "exit":
            print("Exiting the program.")
            break

        # ---------------------------------
        # 1. Create trace ID
        # ---------------------------------

        trace_id = create_trace_id()

        # ---------------------------------
        # 2. Retrieve documents
        # ---------------------------------

        documents = retrieve_documents(question)

        # ---------------------------------
        # 3. Generate answer
        # ---------------------------------

        answer, prompt, temperature = generate_answer(
            question,
            documents
        )

        # ---------------------------------
        # 4. Save trace
        # ---------------------------------

        trace_file = save_trace(
            trace_id=trace_id,
            question=question,
            prompt=prompt,
            retrieved_chunks=documents,
            model=GROQ_MODEL,
            temperature=temperature,
            raw_output=answer,
        )

        # ---------------------------------
        # 5. Display answer
        # ---------------------------------

        print("\n========== ANSWER ==========")
        print(answer)

        print(f"\nTrace ID: {trace_id}")
        print(f"Trace saved to: {trace_file}")