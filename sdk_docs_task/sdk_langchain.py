"""
LangChain-based SDK Docs Pipeline
====================================
Drop-in replacement for ingest.py + generate.py using LangChain components:
  - RecursiveCharacterTextSplitter / MarkdownHeaderTextSplitter
  - HuggingFaceEmbeddings
  - Chroma (LangChain wrapper)
  - ChatGroq + prompt templates for generation
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# ---------------------------------------------------------------------------
# LangChain imports
# ---------------------------------------------------------------------------
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

load_dotenv(TASK_DIR.parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
CHROMA_PATH = str(TASK_DIR / "chroma_db")
PAGES_DIR = TASK_DIR / "pages"

COLLECTIONS = {
    "recursive": "sdk_docs_recursive_langchain",
    "structure_aware": "sdk_docs_structure_aware_langchain",
}

TOP_K = 5

# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------

_embeddings = None
_llm = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name=GROQ_MODEL,
            temperature=0,
        )
    return _llm


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

MARKDOWN_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


def _iter_pages():
    """Yield (sdk_version, md_file_path) pairs."""
    for version_dir in sorted(PAGES_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        for md_file in sorted(version_dir.glob("*.md")):
            yield version_dir.name, md_file


def _make_metadata(sdk_version, page_id, source_file, index, method):
    return {
        "sdk_version": sdk_version,
        "page_id": page_id,
        "source_file": source_file,
        "page_type": "reference",
        "chunk_index": index,
        "chunking_method": method,
    }


def ingest(method: str):
    """Ingest SDK docs pages into Chroma using LangChain splitters."""

    # --- Choose splitter ---------------------------------------------------
    if method == "structure_aware":
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=MARKDOWN_HEADERS,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    # --- Build documents ---------------------------------------------------
    all_docs: list[Document] = []

    for sdk_version, md_file in _iter_pages():
        page_id = md_file.stem
        source_file = str(md_file.relative_to(PAGES_DIR)).replace("\\", "/")
        text = md_file.read_text(encoding="utf-8")

        if method == "structure_aware":
            # MarkdownHeaderTextSplitter returns Documents with metadata
            raw_chunks = splitter.split_text(text)
            # Wrap plain strings into Documents with metadata
            docs = [
                Document(
                    page_content=chunk,
                    metadata=_make_metadata(
                        sdk_version, page_id, source_file, idx, method
                    ),
                )
                for idx, chunk in enumerate(raw_chunks)
            ]
        else:
            base_chunks = splitter.split_text(text)
            docs = [
                Document(
                    page_content=chunk,
                    metadata=_make_metadata(
                        sdk_version, page_id, source_file, idx, method
                    ),
                )
                for idx, chunk in enumerate(base_chunks)
            ]

        all_docs.extend(docs)

    if not all_docs:
        raise ValueError("No chunks produced -- check pages directory.")

    # --- Store in Chroma ----------------------------------------------------
    collection_name = COLLECTIONS[method]

    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PATH,
    )

    try:
        vectordb.delete_collection()
    except Exception:
        pass

    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PATH,
    )

    vectordb.add_documents(all_docs)

    result = {
        "collection": collection_name,
        "method": method,
        "chunks": vectordb._collection.count(),
    }
    print(result)
    return result


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

REFUSAL_TEXT = (
    "NOT_IN_CORPUS: This is not documented in the provided SDK reference pages."
)

SYSTEM_PROMPT = f"""You are a documentation assistant for the Nimbus SDK. Answer ONLY using the numbered context chunks provided below. Each chunk is labeled with its chunk_id.

Rules (mandatory -- not suggestions):
1. Every factual claim in your answer must end with a citation in the exact form [chunk_id], where chunk_id is copied verbatim from a context label below (write it exactly as "[chunk_id]", not "[chunk_id=chunk_id]").
2. You may only cite a chunk_id that literally appears in the context below. Never invent a chunk_id.
3. A chunk about a related-but-different subject does NOT support the answer. Only use a chunk if it names the exact subject of the question.
4. If the context does not fully and specifically support an answer to the question, you MUST reply with EXACTLY this text and nothing else:
{REFUSAL_TEXT}
5. Do not use outside knowledge. Do not guess. Do not hedge with "likely" or "typically" -- either cite a chunk_id or refuse with the exact text above."""


def _build_context(docs: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs):
        chunk_id = doc.metadata.get("chunk_id", f"chunk_{i}")
        parts.append(f"[chunk_id={chunk_id}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def retrieve_and_generate(question: str, method: str = "structure_aware", top_k: int = TOP_K):
    """Retrieve relevant chunks and generate an answer using LangChain."""
    collection_name = COLLECTIONS[method]

    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PATH,
    )

    retriever = vectordb.as_retriever(search_kwargs={"k": top_k})
    llm = get_llm()

    docs = retriever.invoke(question)

    # Build context manually so we can track chunk_ids for citation resolution
    context = "\n\n---\n\n".join(
        f"[chunk_id={doc.metadata.get('chunk_id', 'unknown')}]\n{doc.page_content}"
        for doc in docs
    )

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"),
    ])

    chain = rag_prompt | llm
    response = chain.invoke({})

    return response.content.strip(), docs


def resolve_citations(answer_text: str, docs: list[Document]):
    """Extract and validate citations from the generated answer."""
    cited = set(
        re.findall(r"[\[【](?:chunk_id=)?([a-zA-Z0-9_-]+)[\]】]", answer_text)
    )
    resolved = []
    for chunk_id in cited:
        doc = next(
            (d for d in docs if d.metadata.get("chunk_id") == chunk_id), None
        )
        resolved.append({
            "chunk_id": chunk_id,
            "resolves": doc is not None,
            "source_file": doc.metadata.get("source_file") if doc else None,
            "anchor": doc.metadata.get("anchor") if doc else None,
        })
    return resolved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LangChain SDK docs pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ingest", help="Ingest all SDK docs pages")
    ingest_cmd = sub.add_parser("ingest-method", help="Ingest with a specific method")
    ingest_cmd.add_argument("method", choices=list(COLLECTIONS.keys()))

    query_cmd = sub.add_parser("query", help="Query the corpus")
    query_cmd.add_argument("question")
    query_cmd.add_argument("--method", default="structure_aware", choices=list(COLLECTIONS.keys()))

    args = parser.parse_args()

    if args.command == "ingest":
        for m in COLLECTIONS:
            ingest(m)

    elif args.command == "ingest-method":
        ingest(args.method)

    elif args.command == "query":
        answer, docs = retrieve_and_generate(args.question, method=args.method)
        citations = resolve_citations(answer, docs)
        print(f"\n{'=' * 30} ANSWER {'=' * 30}")
        print(answer)
        print(f"\n{'=' * 30} CITATIONS {'=' * 30}")
        for c in citations:
            print(f"  {c['chunk_id']}: resolves={c['resolves']}, source={c.get('source_file')}")

    else:
        parser.print_help()
