import os
import json
import re
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from groq import Groq

from create_embeddings import model as embedding_model
from retrieval import hybrid_retrieve
from tracing import PROMPT_VERSION, create_trace_id, save_trace  # noqa: F401
from revision_guard import enforce_revision_authority


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
REVISION_SOURCE = BASE_DIR / "Agentic Ai" / "handbook_revisions.json"


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


def generate_answer(question, documents, include_usage=False):

    context = "\n\n".join(
        document["text"]
        for document in documents
    )

    revision_question = bool(re.search(r"revision|revised|latest revision|how many times.*handbook", question, re.I))
    authority = ""
    if revision_question and REVISION_SOURCE.exists():
        revision_data = json.loads(REVISION_SOURCE.read_text(encoding="utf-8"))
        authority = (
            "\nAUTHORITATIVE HANDBOOK REVISION REGISTER (use this for revision-count/date questions; "
            "do not infer a total from a partial retrieved excerpt):\n"
            + json.dumps(revision_data, ensure_ascii=False)
            + "\n"
        )

    prompt = f"""
Answer the question using only the provided context.

If the answer is not available in the context,
say that you don't know based on the provided document.

State a policy figure (number of days, amounts, limits) only if it appears in
the context, and apply it only to the employee group the context names.
Never fill a figure in from memory or from another group's rule.

Context:
{context}
{authority}

Question:
{question}

Answer:
"""

    temperature = 0.3

    generation_started = time.perf_counter()
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
    generation_seconds = time.perf_counter() - generation_started

    # A partial retrieved chunk can stop at Revision 8 even though later
    # revisions exist. Fail closed if the model contradicts the authoritative
    # register supplied above.
    if revision_question and authority:
        answer = enforce_revision_authority(question, answer, REVISION_SOURCE)

    if include_usage:
        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "generation_seconds": generation_seconds,
        }
        return answer, prompt, temperature, usage

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
