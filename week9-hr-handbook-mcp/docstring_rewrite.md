# Task 5 -- one MCP tool docstring rewritten as a tool-use prompt

Tool chosen: **`get_policy_section`** from the existing HR Handbook MCP
server (server one) -- the preferred option named in the practical.

Both texts below were read **directly from captured `tools/list`
responses** (the description as actually served on the MCP wire before
and after the rewrite -- see `tool_counts.md` for those captures), not
retyped from source.

## Original description (the model-facing "docstring")

```text
Retrieve the full, verbatim text of ONE specific, named section of the Employee Handbook, located exactly (not by similarity search). Returns only that section's text -- no other section, and no revision history. Use search_handbook instead for a broader natural-language question, and get_handbook_revisions instead for when/how the Handbook document itself has been updated.
```

376 characters. It states what the tool is but leaves the
operational guidance implicit: no explicit when-to-use cue, no required
argument, no description of the returned fields, no failure
interpretation, no instruction for a missing/nonexistent section.

## Original Python function docstring (unchanged, developer-facing)

```python
def get_policy_section(section):
    """Retrieve the full, verbatim text of one specific, named Handbook
    section, located by its real anchor phrase rather than by similarity
    search."""
```

This one was intentionally left as-is: it documents implementation
behavior for developers and never reaches the model. The model only
ever sees the MCP `tools/list` description above (that is the docstring
that acts as a tool-use prompt).

## Rewritten description (serves as the tool-use prompt)

```text
Retrieve the FULL, VERBATIM text of exactly ONE named section of the Soft Suave Employee Handbook, located by exact section key -- not by similarity search. USE THIS TOOL WHEN the question is about one specific, named policy area (code of conduct, disciplinary actions, employee grievances, conflict of interest and gifts, arrear policy for freshers, work-from-home and deputation compensation, HR contact details, or company leadership) and you need that section's authoritative wording rather than paraphrase. REQUIRED ARGUMENT: `section`, which must be chosen from the schema's enum -- never invent a key. RETURNS: a summary, the verbatim extracted chunk(s) with chunk ids, a `found` flag, and a note that this PDF's multi-column extraction may interleave adjacent-section text; quote it faithfully and do not silently correct or merge it with other sections. INTERPRETING FAILURES: an error means `section` was not one of the supported enum values (the error lists the valid keys) -- correct the argument and call again. If the requested policy or section does not exist under any enum key, DO NOT guess at one: fall back to search_handbook for the closest real content; if that also finds nothing, state plainly that the Handbook contains no such section and name what IS available. Use search_handbook instead for broader natural-language questions, and get_handbook_revisions for when/how the Handbook document itself has been updated.
```

1442 characters, served from commit `7529bc1` onward. No LLM
call was added anywhere -- this is a static description string in
`Agentic Ai/tools.py::TOOL_SCHEMAS`; server one passes it through
verbatim in `tools/list`, and the agent's discovered schema carries it
to the model.

## How the rewrite covers the six required aspects

| Required aspect | Where it now lives in the description |
|---|---|
| What the tool does | "Retrieve the FULL, VERBATIM text of exactly ONE named section ... located by exact section key -- not by similarity search." |
| When the model should use it | "USE THIS TOOL WHEN the question is about one specific, named policy area (code of conduct, disciplinary actions, ...)" |
| What arguments are required | "REQUIRED ARGUMENT: `section`, which must be chosen from the schema's enum -- never invent a key." |
| What information the tool returns | "RETURNS: a summary, the verbatim extracted chunk(s) with chunk ids, a `found` flag, and a note that this PDF's multi-column extraction may interleave adjacent-section text..." |
| How to interpret failures | "INTERPRETING FAILURES: an error means `section` was not one of the supported enum values (the error lists the valid keys) -- correct the argument and call again." |
| What to do when the requested policy/section does not exist | "If the requested policy or section does not exist under any enum key, DO NOT guess at one: fall back to search_handbook for the closest real content; if that also finds nothing, state plainly that the Handbook contains no such section and name what IS available." |

## Where the rewrite takes effect (single source of truth)

`Agentic Ai/tools.py::TOOL_SCHEMAS` (static definition) -> server one's
`tools/list` response -> the agent's discovered `TOOL_SCHEMAS` export.
There is exactly one copy of this text; the MCP layer transports it.

## Live verification after the rewrite

Re-discovery via `tools/list` reported 3 tools and all rewrite markers
present in the served description (`USE THIS TOOL WHEN`,
`REQUIRED ARGUMENT`, `INTERPRETING FAILURES`,
`does not exist under any enum key`, `search_handbook`) -- see the
verification run recorded in this session and commit `7529bc1`.

