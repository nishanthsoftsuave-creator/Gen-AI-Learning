"""Tag every handbook chunk with the employee group it applies to and its start page.

Metadata-only update of the existing Chroma collection: no re-chunking, no re-embedding.
  group: technical | non_technical | both | all   (retrieval keeps caller's group + both + all)
  page:  1-based PDF page where the chunk starts (0 = not found)

Modes:
  naive    group from each chunk's own text only.
  overlap  a chunk that names a group also inherits the group in effect where it overlaps the
           previous chunk: the chunker repeats ~150 chars across a boundary, so a rule can
           start in one chunk and finish in the next (chunk_57 opens with the tail of the
           *technical* outstation rule, then switches to the non-technical section).
"""
import argparse
import re
from pathlib import Path

import chromadb
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent.parent
NON_TECH = re.compile(r"non[\s\-]?technical", re.I)
TECH = re.compile(r"(?<![a-z\-])technical", re.I)
OVERLAP_CHARS = 150  # chunk_document.chunk_text's chunk_overlap


def own_groups(text):
    groups = set()
    if NON_TECH.search(text):
        groups.add("non_technical")
    if TECH.search(NON_TECH.sub("", text)):
        groups.add("technical")
    return groups


ANY_GROUP = re.compile(r"non[\s\-]?technical|(?<![a-z\-])technical", re.I)


def group_in_effect_at_overlap(prev, cur):
    """Group named last in `prev` before the text that `cur` repeats, or None.

    shortcut: exact 40-char match of the boundary text; breaks if the chunker's overlap
    logic changes, upgrade to difflib if the chunker is ever replaced.
    """
    start = prev.find(cur[:40], max(0, len(prev) - (OVERLAP_CHARS + 60)))
    if start < 0:
        return None
    last = None
    for match in ANY_GROUP.finditer(prev[:start]):
        last = "non_technical" if match.group(0).lower().startswith("non") else "technical"
    return last


def group_label(groups):
    return "both" if len(groups) == 2 else next(iter(groups), "all")


def page_of(text, pages):
    for key in (text[:50], text[-50:]):
        key = re.sub(r"\s+", " ", key).strip()
        for number, page in enumerate(pages, 1):
            if key and key in page:
                return number
    return 0


def tag(mode="overlap", pdf=None, chroma_path=None):
    chroma_path = chroma_path or str(BASE / "chroma_db")
    col = chromadb.PersistentClient(path=chroma_path).get_collection("rag_documents")
    data = col.get(include=["documents", "metadatas"])
    order = sorted(range(len(data["ids"])), key=lambda i: int(data["ids"][i].split("_")[1]))
    ids = [data["ids"][i] for i in order]
    docs = [data["documents"][i] for i in order]
    metas = [dict(data["metadatas"][i] or {}) for i in order]
    pdf = pdf or next((BASE / "documents").glob("SS Employee Handbook*.pdf"))
    pages = [re.sub(r"\s+", " ", p.extract_text() or "") for p in PdfReader(pdf).pages]

    groups = [own_groups(d) for d in docs]
    # lead_*: the text before the chunk's first own group marker belongs to `lead_group`; retrieval
    # trims it for the other group (see tools._trim_foreign_lead). Always written so re-tagging resets it.
    lead = [("", 0)] * len(docs)
    if mode == "overlap":
        for i in range(1, len(docs)):
            # Only widen chunks that already name a group; untagged chunks stay "all".
            inherited = group_in_effect_at_overlap(docs[i - 1], docs[i]) if groups[i] else None
            if inherited:
                if inherited not in groups[i]:
                    lead[i] = (inherited, ANY_GROUP.search(docs[i]).start())
                groups[i] = groups[i] | {inherited}
    for meta, g, doc, (lead_group, lead_chars) in zip(metas, groups, docs, lead):
        meta["group"] = group_label(g)
        meta["page"] = page_of(doc, pages)
        meta["lead_group"], meta["lead_chars"] = lead_group, lead_chars
    col.update(ids=ids, metadatas=metas)
    counts = {}
    for m in metas:
        counts[m["group"]] = counts.get(m["group"], 0) + 1
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["naive", "overlap"], default="overlap")
    print(tag(ap.parse_args().mode))
