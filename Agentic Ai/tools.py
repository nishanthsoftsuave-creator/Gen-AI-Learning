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

import contextvars
import copy
import json
import os
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

# Employee group scoping (capstone). Chunks carry metadata group in
# {technical, non_technical, both, all} (capstone/tag_index.py).
GROUPS = ("technical", "non_technical")
GROUP_SCOPED_TOOLS = {"search_handbook", "get_policy_section"}
_UNSET = object()
# In the agent process the entry point sets this, and dispatch_tool then forces it onto every
# group-scoped call, so the model cannot widen or switch the caller's group. None = unresolved.
CALLER_GROUP = contextvars.ContextVar("caller_group", default=_UNSET)
# When a list is set here, dispatch_tool appends the chunks every tool returned (citations).
EVIDENCE = contextvars.ContextVar("evidence", default=None)


class ToolError(Exception):
    pass


def _check_group(employee_group):
    if employee_group not in (None, *GROUPS):
        raise ToolError(f"Unsupported employee_group '{employee_group}'. Use one of {list(GROUPS)} or omit it.")


def _group_where(employee_group):
    """Chroma filter: the caller's group plus chunks that apply to both groups or to everyone."""
    return {"group": {"$in": [employee_group, "both", "all"]}} if employee_group else None


def _metas(ids):
    if not ids:
        return {}
    data = _get_collection().get(ids=ids, include=["metadatas"])
    return {i: m or {} for i, m in zip(data["ids"], data["metadatas"])}


def _trim_foreign_lead(text, meta, group):
    """Drop the chunk's leading span when it is the tail of the OTHER group's rule.

    The chunker repeats text across a boundary, so a chunk can open with the end of the technical
    rule and then switch to the non-technical section (chunk_57). Tagging such a chunk "both" lets
    the technical caller see the rule, but the non-technical caller must not get that tail.
    """
    lead_group, lead_chars = meta.get("lead_group"), meta.get("lead_chars", 0)
    return text[lead_chars:] if group and lead_chars and lead_group != group else text


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

def search_handbook(query, top_k=3, employee_group=None):
    """Find relevant passages in the Employee Handbook for a natural-
    language question (narrative policy explanations, procedures)."""

    _check_group(employee_group)
    collection = _get_collection()
    embedding = embedding_model.encode(query).tolist()

    results = hybrid_retrieve(
        collection, query, embedding, top_k=top_k, where=_group_where(employee_group)
    )
    metas = _metas([r["chunk_id"] for r in results])

    return {
        "query": query,
        "employee_group": employee_group,
        "result_count": len(results),
        "results": [
            {"chunk_id": r["chunk_id"], "page": metas.get(r["chunk_id"], {}).get("page", 0),
             "text": _trim_foreign_lead(r["text"], metas.get(r["chunk_id"], {}), employee_group)}
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Tool 2: get_policy_section
# ---------------------------------------------------------------------------

def get_policy_section(section, employee_group=None):
    """Retrieve the full, verbatim text of one specific, named Handbook
    section, located by its real anchor phrase rather than by similarity
    search."""

    _validate_section(section)
    _check_group(employee_group)

    anchor = " ".join(POLICY_SECTIONS[section]["anchor"].lower().split())
    collection = _get_collection()
    get_kwargs = {"include": ["documents", "metadatas"]}
    where = _group_where(employee_group)
    if where:
        get_kwargs["where"] = where
    data = collection.get(**get_kwargs)

    matches = []
    seen_prefixes = set()
    for chunk_id, doc, meta in sorted(
        zip(data["ids"], data["documents"], data["metadatas"]),
        key=lambda item: int(item[0].split("_")[1]),
    ):
        normalized_doc = " ".join(doc.lower().split())
        if anchor in normalized_doc:
            prefix = doc[:120]
            if prefix in seen_prefixes:
                continue  # the source chunker overlaps consecutive chunks; skip near-duplicates
            seen_prefixes.add(prefix)
            matches.append({"chunk_id": chunk_id, "page": (meta or {}).get("page", 0),
                            "text": _trim_foreign_lead(doc, meta or {}, employee_group)})

    return {
        "section": section,
        "employee_group": employee_group,
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


# Groq's tool-calling has been observed (Week 8 Step 3 baseline: 14/14
# invalid-argument occurrences, across Q2/Q5/Q8/Q10) to emit one of these
# exact spurious shapes for get_handbook_revisions -- a zero-parameter tool
# -- instead of a clean {}. This is a narrow, exact-match allowlist, not a
# general leniency policy: only these specific shapes are recognized, and
# only for this one tool. Any other argument (e.g. {"foo": "bar"} or
# {"version": "v3"}) is left untouched and still fails exactly as before.
_SPURIOUS_EMPTY_ARGUMENT_FORMS = [
    {},
    {"": ""},
    {"": "{}"},
    {"{}": "{}"},
]


def _normalize_zero_arg_call(name, arguments):
    if name == "get_handbook_revisions" and arguments in _SPURIOUS_EMPTY_ARGUMENT_FORMS:
        return {}
    return arguments


# Set only by the MCP initialization block at the bottom of this module,
# in the agent/host process. It stays None inside an MCP server subprocess
# (HR_MCP_SERVER_ROLE), so a server's dispatch remains purely local.
_mcp_call_tool = None


def _dispatch_mcp_tool(name, arguments):
    """Invoke a tool discovered via MCP ``tools/list`` on the server that
    owns it, through ``tools/call``.

    Args:
        name (str): a tool name from discovery (not in TOOL_FUNCTIONS).
        arguments (dict): JSON-object tool arguments.

    Returns:
        dict: the parsed JSON tool result.

    Raises:
        ToolError: with the server's own message when the server reports
        ``isError`` (e.g. a recoverable "version not found" response), or
        with a message naming the failure when the MCP server itself is
        unreachable -- so the model can tell "unknown policy/version"
        apart from "MCP server failure".
    """
    if not isinstance(arguments, dict):
        raise ToolError(f"Bad arguments for tool '{name}': expected a JSON object.")
    if name not in known_tools():
        raise ToolError(f"Unknown tool '{name}'.")
    try:
        text, is_error = _mcp_call_tool(name, arguments)
    except MCPTransportError as exc:
        raise ToolError(f"MCP server call failed for '{name}': {exc}") from exc
    if is_error:
        raise ToolError(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def model_schemas():
    """Tool schemas shown to the model.

    Once the entry point has set the caller's group, dispatch_tool forces it, so the model must not
    see `employee_group`: a model that fills it with null gets a 400 tool_use_failed from Groq
    (4 of 30 cases in the first integrated run). MCP clients outside the agent still see it.
    """
    if CALLER_GROUP.get() is _UNSET:
        return TOOL_SCHEMAS
    schemas = copy.deepcopy(TOOL_SCHEMAS)
    for schema in schemas:
        schema["function"]["parameters"].get("properties", {}).pop("employee_group", None)
    return schemas


def dispatch_tool(name, arguments):
    arguments = _normalize_zero_arg_call(name, arguments)
    caller_group = CALLER_GROUP.get()
    if caller_group is not _UNSET and name in GROUP_SCOPED_TOOLS and isinstance(arguments, dict):
        arguments = {**arguments, "employee_group": caller_group}

    # HR_VIA_MCP=1 (capstone) sends the handbook tools through the discovered MCP server too,
    # so the group and trace id cross a real hop instead of a local function call.
    over_mcp = name not in TOOL_FUNCTIONS or (
        os.environ.get("HR_VIA_MCP") and _mcp_call_tool and name in known_tools()
    )
    if over_mcp:
        if _mcp_call_tool is None:
            raise ToolError(f"Unknown tool '{name}'.")
        result = _dispatch_mcp_tool(name, arguments)
    else:
        try:
            result = TOOL_FUNCTIONS[name](**arguments)
        except ToolError:
            raise
        except TypeError as error:
            raise ToolError(f"Bad arguments for tool '{name}': {error}") from error

    evidence = EVIDENCE.get()
    if evidence is not None and isinstance(result, dict):
        for chunk in result.get("results", []) + result.get("excerpts", []):
            evidence.append({"tool": name, **chunk})
    return result


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
                    "employee_group": {
                        "type": "string",
                        "enum": list(GROUPS),
                        "description": (
                            "Caller's employee group. Only passages for this group (or for "
                            "everyone) are returned. Omit when the group is unknown."
                        ),
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
                "Retrieve the FULL, VERBATIM text of exactly ONE named "
                "section of the Soft Suave Employee Handbook, located by "
                "exact section key -- not by similarity search. USE THIS "
                "TOOL WHEN the question is about one specific, named "
                "policy area (code of conduct, disciplinary actions, "
                "employee grievances, conflict of interest and gifts, "
                "arrear policy for freshers, work-from-home and "
                "deputation compensation, HR contact details, or company "
                "leadership) and you need that section's authoritative "
                "wording rather than paraphrase. REQUIRED ARGUMENT: "
                "`section`, which must be chosen from the schema's enum -- "
                "never invent a key. RETURNS: a summary, the verbatim "
                "extracted chunk(s) with chunk ids, a `found` flag, and a "
                "note that this PDF's multi-column extraction may "
                "interleave adjacent-section text; quote it faithfully and "
                "do not silently correct or merge it with other sections. "
                "INTERPRETING FAILURES: an error means `section` was not "
                "one of the supported enum values (the error lists the "
                "valid keys) -- correct the argument and call again. If "
                "the requested policy or section does not exist under any "
                "enum key, DO NOT guess at one: fall back to "
                "search_handbook for the closest real content; if that "
                "also finds nothing, state plainly that the Handbook "
                "contains no such section and name what IS available. Use "
                "search_handbook instead for broader natural-language "
                "questions, and get_handbook_revisions for when/how the "
                "Handbook document itself has been updated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": SUPPORTED_SECTIONS,
                        "description": "Exact section to retrieve.",
                    },
                    "employee_group": {
                        "type": "string",
                        "enum": list(GROUPS),
                        "description": "Caller's employee group; omit when unknown.",
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

# ---------------------------------------------------------------------------
# MCP discovery (Week 9): in the agent/host process the exported
# TOOL_SCHEMAS above are replaced by whatever tools/list reports for the
# servers declared in mcp_config.json -- MCP discovery, not this file, is
# the source of truth for which tools the agent sees. Inside an MCP server
# subprocess (HR_MCP_SERVER_ROLE, set by mcp_host.py at spawn and by each
# server script itself at start-up) discovery is skipped entirely, so a
# server never acts as its own client.
# ---------------------------------------------------------------------------

from mcp_host import (  # noqa: E402
    MCPDiscoveryError,
    MCPTransportError,
    call_tool,
    discover_tools,
    known_tools,
    to_openai_schema,
)

if not os.environ.get("HR_MCP_SERVER_ROLE"):
    try:
        TOOL_SCHEMAS = [to_openai_schema(tool) for tool in discover_tools()]
    except MCPDiscoveryError as exc:
        print(
            f"[tools] MCP discovery unavailable ({exc}); "
            "using the built-in handbook tool schemas.",
            file=sys.stderr,
        )
    else:
        _mcp_call_tool = call_tool
