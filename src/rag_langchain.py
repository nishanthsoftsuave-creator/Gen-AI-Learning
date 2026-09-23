"""
LangChain-based RAG Pipeline
==============================
Drop-in replacement for rag.py using LangChain's built-in components:
  - PyPDFLoader          replaces manual pypdf usage
  - RecursiveCharacterTextSplitter replaces hand-written chunking
  - HuggingFaceEmbeddings replaces raw sentence-transformers
  - Chroma               replaces manual chromadb.PersistentClient
  - ChatGroq             replaces raw groq.Groq client
  - RetrievalQA / create_retrieval_chain ties everything together
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# LangChain imports
# ---------------------------------------------------------------------------
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "rag_documents"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# ---------------------------------------------------------------------------
# Shared components (lazily initialised)
# ---------------------------------------------------------------------------
_embeddings = None
_llm = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
        )
    return _embeddings


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name=GROQ_MODEL,
            temperature=0.3,
        )
    return _llm


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def load_and_split_pdf(pdf_path: str, chunk_size: int = 900, chunk_overlap: int = 150):
    """Load a PDF and split it into chunks using LangChain splitters."""
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def ingest_pdf(pdf_path: str, reset: bool = True, verbose: bool = True):
    """Full ingestion pipeline: load → split → embed → store in Chroma."""
    chunks = load_and_split_pdf(pdf_path)

    if not chunks:
        raise ValueError("No text could be extracted from the PDF.")

    vectordb = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PATH,
    )

    if reset:
        try:
            vectordb.delete_collection()
        except Exception:
            pass
        vectordb = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=CHROMA_PATH,
        )

    vectordb.add_documents(chunks)

    if verbose:
        count = vectordb._collection.count()
        print(f"\n{'=' * 40} VECTOR STORE {'=' * 40}")
        print(f"Total chunks stored: {count}")
        print(f"Collection: {COLLECTION_NAME}")

    return {
        "chunks": len(chunks),
        "collection": COLLECTION_NAME,
    }


# ---------------------------------------------------------------------------
# Retrieval + Generation
# ---------------------------------------------------------------------------

def get_retriever(top_k: int = 3):
    """Return a LangChain retriever backed by the Chroma store."""
    vectordb = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PATH,
    )
    return vectordb.as_retriever(search_kwargs={"k": top_k})


RAG_PROMPT = ChatPromptTemplate.from_template(
    """Answer the question using only the provided context.

If the answer is not available in the context,
say that you don't know based on the provided document.

Context:
{context}

Question:
{input}

Answer:"""
)


def build_rag_chain(top_k: int = 3):
    """Build a complete LangChain retrieval chain."""
    retriever = get_retriever(top_k=top_k)
    llm = get_llm()

    document_chain = create_stuff_documents_chain(llm, RAG_PROMPT)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    return retrieval_chain


def ask(question: str, top_k: int = 3) -> str:
    """Ask a question against the ingested documents."""
    chain = build_rag_chain(top_k=top_k)
    result = chain.invoke({"input": question})
    return result["answer"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    while True:
        question = input(
            "\nEnter your question (or type 'exit' to quit): "
        )

        if question.lower() == "exit":
            print("Exiting the program.")
            break

        answer = ask(question)

        print("\n" + "=" * 30 + " ANSWER " + "=" * 30)
        print(answer)
