"""The three tools available to the agent and the fixed workflow.

Domain: the Soft Suave Employee Handbook (documents/SS Employee Handbook
Updated-2025 (1).pdf), the same PDF already loaded by the main app's
Document Q&A tab (src/app.py, collection "rag_documents" in the project's
root chroma_db/). search_handbook reuses the existing hybrid retrieval
stack; get_policy_section and get_handbook_revisions are anchored to real,
hand-verified text extracted from that same PDF (see README "Third Tool" /
"Existing Architecture" for how each anchor was found and verified).

Note on data quality: this PDF's multi-column layout means the extracted
text is not always in clean reading order -- headings and body text from
adjacent sections sometimes interleave (already documented independently in
sdk_docs_task/../notes.md and taxonomy.md from the Week 5 error analysis of
this same document). get_policy_section surfaces the raw chunk(s) verbatim
rather than a hand-cleaned rewrite, and says so, so nothing here is
invented or silently corrected.
"""

import json
import sys
from pathlib import Path

AGENTIC_DIR = Path(__file__).resolve().parent
BASE_DIR = AGENTIC_DIR.parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import chromadb  # noqa: E402

from create_embeddings import model as embedding_model  # noqa: E402
from retrieval import hybrid_retrieve  # noqa: E402

CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "rag_documents"

REVISIONS_FILE = AGENTIC_DIR / "handbook_revisions.json"

# section key -> a real, verified, unique substring from the extracted PDF
# text that anchors that section. Chosen from body text (not just the
# table-of-contents heading) so the lookup lands on actual content.
POLICY_SECTIONS = {
    "arrear_policy_freshers": {
        "anchor": "ARREAR POLICY: FRESHERS ONLY",
        "summary": "Probation-period performance evaluation policy for new joiners (freshers only).",
    },
    "work_from_home_and_deputation_compensation": {
        "anchor": "eligible to receive monetary compensation of 1000 INR",
        "summary": "Compensation for working non-working days / client deputation, technical vs. non-technical teams.",
    },
    "employee_code_of_conduct": {
        "anchor": "consult a Reporting Senior or HR",
        "summary": "Individual responsibility under the Employee Code of Conduct.",
    },
    "disciplinary_actions": {
        "anchor": "Such disciplinary actions will vary",
        "summary": "Consequences for repeatedly or intentionally failing to follow the Handbook.",
    },
    "conflict_of_interest_and_gifts": {
        "anchor": "We prohibit bribery",
        "summary": "Rules on gifts, benefits, and bribery from clients or other organizations.",
    },
    "employee_grievances": {
        "anchor": "Once the grievance is resolved",
        "summary": "How an employee grievance is raised and resolved.",
    },
    "contact_details": {
        "anchor": "teamhr@softsuave.com",
        "summary": "HR, HRM, and Accounts contact details.",
    },
    "company_leadership": {
        "anchor": "RAMESH VAYAVURU",
        "summary": "Company leadership signatories: Chief Executive Officer and Managing Director.",
    },
}

SUPPORTED_SECTIONS = list(POLICY_SECTIONS.keys())

_collection = None


class ToolError(Exception):
    pass


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection(name=COLLECTION_NAME)
    return _collection


def _validate_section(section):
    if section not in POLICY_SECTIONS:
        raise ToolError(
            f"Unsupported section '{section}'. Supported values: {SUPPORTED_SECTIONS}."
        )


# ---------------------------------------------------------------------------
# Tool 1: search_handbook
# ---------------------------------------------------------------------------

def search_handbook(query, top_k=3):
    """Find relevant passages in the Employee Handbook for a natural-
    language question (narrative policy explanations, procedures)."""

    collection = _get_collection()
    embedding = embedding_model.encode(query).tolist()

    results = hybrid_retrieve(collection, query, embedding, top_k=top_k)

    return {
        "query": query,
        "result_count": len(results),
        "results": [{"chunk_id": r["chunk_id"], "text": r["text"]} for r in results],
    }


# ---------------------------------------------------------------------------
# Tool 2: get_policy_section
# ---------------------------------------------------------------------------

def get_policy_section(section):
    """Retrieve the full, verbatim text of one specific, named Handbook
    section, located by its real anchor phrase rather than by similarity
    search."""

    _validate_section(section)

    anchor = " ".join(POLICY_SECTIONS[section]["anchor"].lower().split())
    collection = _get_collection()
    data = collection.get(include=["documents"])

    matches = []
    seen_prefixes = set()
    for chunk_id, doc in sorted(
        zip(data["ids"], data["documents"]),
        key=lambda pair: int(pair[0].split("_")[1]),
    ):
        normalized_doc = " ".join(doc.lower().split())
        if anchor in normalized_doc:
            prefix = doc[:120]
            if prefix in seen_prefixes:
                continue  # the source chunker overlaps consecutive chunks; skip near-duplicates
            seen_prefixes.add(prefix)
            matches.append({"chunk_id": chunk_id, "text": doc})

    return {
        "section": section,
        "summary": POLICY_SECTIONS[section]["summary"],
        "found": len(matches) > 0,
        "excerpts": matches[:2],
        "note": (
            "Text is extracted verbatim from the source PDF. This document's "
            "multi-column layout means headings and body text from adjacent "
            "sections sometimes interleave in the extracted text -- this is "
            "not corrected here."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 3: get_handbook_revisions
# ---------------------------------------------------------------------------

def get_handbook_revisions():
    """Retrieve the Handbook's own dated revision history and its
    modifications clause -- i.e. how the document itself has changed over
    time, not any HR policy's content."""

    return json.loads(REVISIONS_FILE.read_text(encoding="utf-8"))


TOOL_FUNCTIONS = {
    "search_handbook": search_handbook,
    "get_policy_section": get_policy_section,
    "get_handbook_revisions": get_handbook_revisions,
}


def dispatch_tool(name, arguments):
    if name not in TOOL_FUNCTIONS:
        raise ToolError(f"Unknown tool '{name}'.")

    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except ToolError:
        raise
    except TypeError as error:
        raise ToolError(f"Bad arguments for tool '{name}': {error}") from error


# ---------------------------------------------------------------------------
# Groq tool-calling schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_handbook",
            "description": (
                "Search the Soft Suave Employee Handbook for passages "
                "relevant to a natural-language question: general policy "
                "explanations, procedures, and context that may span more "
                "than one section. Returns ranked text passages. Does NOT "
                "return the full verbatim text of one specific named "
                "section (use get_policy_section for that) and does NOT "
                "return the Handbook's own dated revision history (use "
                "get_handbook_revisions for that)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query, e.g. 'what happens if I raise a grievance'.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of ranked passages to return. Defaults to 3.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_section",
            "description": (
                "Retrieve the full, verbatim text of ONE specific, named "
                "section of the Employee Handbook, located exactly (not by "
                "similarity search). Returns only that section's text -- no "
                "other section, and no revision history. Use "
                "search_handbook instead for a broader natural-language "
                "question, and get_handbook_revisions instead for when/how "
                "the Handbook document itself has been updated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": SUPPORTED_SECTIONS,
                        "description": "Exact section to retrieve.",
                    },
                },
                "required": ["section"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_handbook_revisions",
            "description": (
                "Retrieve the Employee Handbook's own dated revision "
                "history (every revision number and date, from Revision 1 "
                "through the latest) and its modifications clause -- i.e. "
                "how many times and when the Handbook DOCUMENT ITSELF has "
                "been updated. Does NOT return the content of any HR "
                "policy -- use get_policy_section or search_handbook for "
                "that."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
