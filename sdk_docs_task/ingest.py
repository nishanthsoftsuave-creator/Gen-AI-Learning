import re
import sys
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import chromadb

from chunk_document import chunk_text
from create_embeddings import model as embedding_model

PAGES_DIR = TASK_DIR / "pages"
CHROMA_PATH = str(TASK_DIR / "chroma_db")

COLLECTIONS = {
    "recursive": "sdk_docs_recursive",
    "structure_aware": "sdk_docs_structure_aware",
}


def _anchor_for_chunk(chunk_value):
    for line in chunk_value.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            heading = heading.replace("(cont.)", "").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            return slug or "top"
    return "top"


def iter_pages():
    for version_dir in sorted(PAGES_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        sdk_version = version_dir.name
        for md_file in sorted(version_dir.glob("*.md")):
            yield sdk_version, md_file


def ingest(method):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection_name = COLLECTIONS[method]

    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=collection_name)

    all_ids = []
    all_docs = []
    all_metas = []

    for sdk_version, md_file in iter_pages():
        page_id = md_file.stem
        source_file = str(md_file.relative_to(PAGES_DIR)).replace("\\", "/")
        text = md_file.read_text(encoding="utf-8")

        chunks = chunk_text(text, method=method)

        for index, chunk in enumerate(chunks):
            chunk_id = f"{sdk_version}__{page_id}__{method}__{index}"
            anchor = _anchor_for_chunk(chunk)

            all_ids.append(chunk_id)
            all_docs.append(chunk)
            all_metas.append({
                "source_file": source_file,
                "page_id": page_id,
                "sdk_version": sdk_version,
                "page_type": "reference",
                "anchor": anchor,
                "chunk_index": index,
                "chunking_method": method,
            })

    if not all_docs:
        raise ValueError("No chunks produced -- check pages directory.")

    missing_source = [m for m in all_metas if not m.get("source_file")]
    if missing_source:
        raise ValueError(f"{len(missing_source)} chunk(s) have no source_file -- failed ingest.")

    embeddings = embedding_model.encode(all_docs)

    collection.add(
        ids=all_ids,
        documents=all_docs,
        embeddings=embeddings.tolist(),
        metadatas=all_metas,
    )

    return {
        "collection": collection_name,
        "method": method,
        "chunks": collection.count(),
        "pages_indexed": len(set((m["sdk_version"], m["page_id"]) for m in all_metas)),
    }


if __name__ == "__main__":
    for chunking_method in COLLECTIONS:
        result = ingest(chunking_method)
        print(result)
