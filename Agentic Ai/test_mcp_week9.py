"""Week 9 regression tests: HR Policy Registry MCP server + dynamic tool
discovery.

Each test pins a writer-side invariant established by this practical:

- mcp_config.json is the only place MCP servers are declared,
- the registry server's recoverable errors are built FROM
  policy_registry.json (never hardcoded, never opaque),
- neither MCP server contains an LLM call,
- the agent module is byte-identical to the pre-server-two baseline,
- the evidence deliverables hold what they claim.

Deliberately offline and fast: the registry server module is stdlib +
JSON only, so tests never import the heavy retrieval stack.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

AGENTIC = Path(__file__).resolve().parent
REPO = AGENTIC.parent
EVID = REPO / "week9-hr-handbook-mcp"

sys.path.insert(0, str(AGENTIC))


def _load_registry_server():
    """Import mcp_policy_registry_server directly (json-only module top,
    no tools.py, no network)."""
    spec = importlib.util.spec_from_file_location(
        "mcp_policy_registry_server", AGENTIC / "mcp_policy_registry_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = _load_registry_server()


# --- configuration is the only server switch -------------------------------

def test_config_declares_exactly_the_two_servers():
    config = json.loads((AGENTIC / "mcp_config.json").read_text(encoding="utf-8"))
    assert set(config["mcpServers"]) == {"hr-handbook", "hr-policy-registry"}
    entry = config["mcpServers"]["hr-policy-registry"]
    assert entry["name"] == "HR Policy Registry MCP server"
    assert entry["args"] == ["mcp_policy_registry_server.py"]


def test_config_carries_no_tool_definitions():
    raw = (AGENTIC / "mcp_config.json").read_text(encoding="utf-8")
    for tool_name in ("get_policy_version", "get_policy_effective_date",
                      "get_policy_deprecation", "get_policy_metadata"):
        assert tool_name not in raw


# --- registry server tool catalog ------------------------------------------

def test_registry_exposes_exactly_four_tools():
    names = [t["name"] for t in registry.TOOL_DEFS]
    assert names == [
        "get_policy_version",
        "get_policy_effective_date",
        "get_policy_deprecation",
        "get_policy_metadata",
    ]
    for tool in registry.TOOL_DEFS:
        assert tool["description"]
        assert tool["inputSchema"]["type"] == "object"
        assert "policy" in tool["inputSchema"]["properties"]
    by_name = {t["name"]: t for t in registry.TOOL_DEFS}
    assert by_name["get_policy_version"]["inputSchema"]["required"] == ["policy", "version"]


# --- recoverable errors are built from the actual registry data ------------

def test_unknown_version_error_is_data_derived_and_recoverable():
    try:
        registry.get_policy_version("remote_work_policy", "v4")
    except registry.PolicyError as exc:
        message = str(exc)
    else:
        raise AssertionError("v4 must not resolve: it was never published")
    assert "Requested remote_work_policy version v4 does not exist." in message
    assert "Latest published version: v3.2." in message
    assert "Status: v4 has not been published." in message
    assert "Effective date: 2026-08-01." not in message  # date belongs to the list form
    assert "- Effective date: 2026-08-01" in message
    assert "Suggested recovery:" in message
    assert "Use v3.2 if the user wants the currently published policy." in message

    # lists must equal what policy_registry.json actually says
    versions = registry.REGISTRY["policies"]["remote_work_policy"]["versions"]
    deprecated = [k for k, v in versions.items() if v["status"] == "deprecated"]
    superseded = [k for k, v in versions.items() if v["status"] == "superseded"]
    assert "- Deprecated versions: " + ", ".join(deprecated) in message
    assert "- Superseded versions: " + ", ".join(superseded) in message
    assert "- Published versions: " + ", ".join(versions) in message


def test_unknown_policy_error_lists_real_policy_ids():
    try:
        registry.get_policy_metadata("vacation_policy")
    except registry.PolicyError as exc:
        message = str(exc)
    else:
        raise AssertionError("vacation_policy must not resolve")
    assert "Policy 'vacation_policy' does not exist" in message
    for policy_id in registry.REGISTRY["policies"]:
        assert policy_id in message


def test_valid_registry_lookups_unchanged():
    assert registry.get_policy_effective_date("remote_work_policy") == {
        "policy": "remote_work_policy",
        "version": "v3.2",
        "effective_date": "2026-08-01",
        "status": "active",
    }
    v1 = registry.get_policy_deprecation("remote_work_policy", "v1")
    assert v1["status"] == "deprecated"
    assert v1["superseded_by"] == "v2"
    metadata = registry.get_policy_metadata("code_of_conduct")
    assert metadata["current_version"] == "v3"
    assert metadata["versions"] == ["v1", "v2", "v3"]


def test_missing_required_argument_is_named():
    # _execute is the MCP dispatch boundary where _require runs (the same
    # entry the server's tools/call handler uses).
    try:
        registry._execute("get_policy_version", {"policy": "remote_work_policy"})
    except registry.PolicyError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing version must be rejected")
    assert "Missing required argument(s): version" in message


# --- no LLM inside any MCP server -------------------------------------------

def test_mcp_servers_contain_no_llm_usage():
    needles = ("Groq(", "chat.completions", "GROQ_API_KEY", "import groq",
               "openai", "llm_client")
    for server_file in ("mcp_handbook_server.py", "mcp_policy_registry_server.py"):
        source = (AGENTIC / server_file).read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in source, f"{server_file} must not use LLM: {needle}"


# --- zero agent-module changes when adding server two ----------------------

def test_agent_module_unchanged_since_before_server_two():
    result = subprocess.run(
        ["git", "diff", "7529bc1", "HEAD", "--",
         "Agentic Ai/agent.py", "Agentic Ai/llm_client.py", "Agentic Ai/budgets.py",
         "Agentic Ai/agent_tracing.py", "Agentic Ai/workflow.py",
         "Agentic Ai/race.py", "Agentic Ai/budget_termination_test.py",
         "Agentic Ai/tools.py"],
        capture_output=True, text=True, cwd=REPO, check=True,
    )
    assert result.stdout == "", f"agent module changed:\n{result.stdout}"


def test_agent_never_names_server_two():
    source = (AGENTIC / "agent.py").read_text(encoding="utf-8")
    for forbidden in ("policy_registry", "get_policy_version",
                      "hr-policy-registry", "mcp_config"):
        assert forbidden not in source


# --- evidence deliverables hold what they claim -----------------------------

def test_evidence_files_exist():
    for name in ("agent_diff.txt", "config_diff.txt", "wire.json",
                 "tool_counts.md", "error_before_after.md", "risk_note.md"):
        assert (EVID / name).is_file(), name


def test_risk_note_is_exactly_five_lines():
    lines = (EVID / "risk_note.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5, f"expected 5 lines, got {len(lines)}"


def test_wire_json_complete_and_annotated():
    wire = json.loads((EVID / "wire.json").read_text(encoding="utf-8"))
    assert wire["initialize"]["request"]["method"] == "initialize"
    assert wire["tools_list"]["request"]["method"] == "tools/list"
    assert wire["tools_call"]["request"]["method"] == "tools/call"
    assert wire["tools_call"]["request"]["params"]["name"] == "get_policy_effective_date"
    for field in ("jsonrpc", "id", "method", "params", "name",
                  "arguments", "result", "error", "tools",
                  "description", "inputSchema"):
        assert field in wire["field_annotations"], field
    missing = [key for key in wire if key not in wire["top_level_field_annotations"]]
    assert missing == [], f"unannotated top-level fields: {missing}"
    assert wire["closing_statement"] == (
        "The LLM call happens in the Host/Agent; the MCP server does not run an LLM."
    )


def test_tool_counts_before_and_after():
    text = (EVID / "tool_counts.md").read_text(encoding="utf-8")
    assert "Before Server 2" in text
    assert "After Server 2" in text
    assert "Number of tools: 3" in text
    assert "Number of tools: 7" in text
    for name in ("get_policy_version", "get_policy_effective_date",
                 "get_policy_deprecation", "get_policy_metadata"):
        assert name in text


def test_error_before_after_same_query_both_states():
    text = (EVID / "error_before_after.md").read_text(encoding="utf-8")
    assert text.count("What is the remote work policy in version v4") >= 2
    assert "ERROR: policy not found" in text          # BEFORE: opaque
    assert "Suggested recovery" in text               # AFTER: recoverable
    assert "MCP server call failed for" in text       # outage stays distinguishable
    assert "Old tool description" in text            # spec section 11 template
    assert "New tool description" in text


def test_config_diff_shows_only_the_server_entry():
    text = (EVID / "config_diff.txt").read_text(encoding="utf-8")
    assert '+      "name": "HR Policy Registry MCP server",' in text
    assert "RESULT: 0 lines changed" not in text  # that claim lives in agent_diff.txt
    assert "0 deletions" in text or "+    \"hr-policy-registry\":" in text


# --- Live MCP behavior (spec section 14, points 1-9) -----------------------
# One real discovery per test session: the fixture imports tools, which
# spawns both configured servers from mcp_config.json and runs
# initialize + tools/list through mcp_host before any assertion runs.

EXPECTED_TOOL_NAMES = [
    "search_handbook", "get_policy_section", "get_handbook_revisions",
    "get_policy_version", "get_policy_effective_date",
    "get_policy_deprecation", "get_policy_metadata",
]


@pytest.fixture(scope="session")
def live_mcp():
    """Run one real MCP discovery for the whole test session.

    Returns:
        tuple: the mcp_host module (holding the live server connections)
        and the tools module whose TOOL_SCHEMAS came from tools/list.
    """
    import mcp_host as host
    import tools as tools_module

    groups = host.tools_by_server()
    assert set(groups) == {"hr-handbook", "hr-policy-registry"}, (
        f"discovery produced unexpected server groups: {list(groups)}"
    )
    return host, tools_module


def test_live_server1_starts(live_mcp):
    """Spec 14.1: the server-1 process spawned from config is running."""
    host, _ = live_mcp
    assert host._CONNECTIONS["hr-handbook"]._process.poll() is None, (
        "hr-handbook server process exited"
    )


def test_live_server2_starts(live_mcp):
    """Spec 14.2: the server-2 process spawned from config is running."""
    host, _ = live_mcp
    assert host._CONNECTIONS["hr-policy-registry"]._process.poll() is None, (
        "hr-policy-registry server process exited"
    )


def test_live_initialize_handshake_and_ping(live_mcp):
    """Spec 14.3: initialize completed for both servers during discovery
    (mcp_host fails loudly otherwise); a fresh ping round-trip proves the
    live JSON-RPC loop still answers."""
    host, _ = live_mcp
    response = host._CONNECTIONS["hr-policy-registry"].request("ping", {}, 10)
    assert response.get("result") == {}


def test_live_tools_list_returns_seven_tools(live_mcp):
    """Spec 14.4: the model-facing list came from tools/list (3 -> 7)."""
    _, tools_module = live_mcp
    names = [t["function"]["name"] for t in tools_module.TOOL_SCHEMAS]
    assert names == EXPECTED_TOOL_NAMES


def test_live_server1_tools_discovered(live_mcp):
    """Spec 14.5: exactly the three handbook tools came from server 1."""
    host, _ = live_mcp
    names = [t["name"] for t in host.tools_by_server()["hr-handbook"]]
    assert names == ["search_handbook", "get_policy_section", "get_handbook_revisions"]


def test_live_server2_tools_discovered(live_mcp):
    """Spec 14.6: exactly the four registry tools came from server 2."""
    host, _ = live_mcp
    names = [t["name"] for t in host.tools_by_server()["hr-policy-registry"]]
    assert names == [
        "get_policy_version", "get_policy_effective_date",
        "get_policy_deprecation", "get_policy_metadata",
    ]


def test_live_server2_tools_call_over_wire(live_mcp):
    """Spec 14.7: a server-2 tools/call round trip, proven by both the
    returned data and a fresh send/recv frame pair in the MCP traffic log."""
    _, tools_module = live_mcp
    trace_path = AGENTIC / "output" / "mcp_trace.jsonl"
    offset = (
        len(trace_path.read_text(encoding="utf-8").splitlines())
        if trace_path.exists() else 0
    )

    result = tools_module.dispatch_tool(
        "get_policy_effective_date", {"policy": "remote_work_policy"}
    )
    assert result["version"] == "v3.2"
    assert result["effective_date"] == "2026-08-01"

    fresh = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()[offset:]
    ]
    sent = next(
        m for m in fresh
        if m["server"] == "hr-policy-registry" and m["direction"] == "send"
        and m["payload"].get("method") == "tools/call"
        and m["payload"]["params"]["name"] == "get_policy_effective_date"
    )
    reply = next(
        m for m in fresh
        if m["server"] == "hr-policy-registry" and m["direction"] == "recv"
        and m["payload"].get("id") == sent["payload"]["id"]
    )
    assert "2026-08-01" in reply["payload"]["result"]["content"][0]["text"]


def test_live_existing_handbook_tool_still_works(live_mcp):
    """Spec 14.8: the pre-existing HR tools still execute (local path)."""
    _, tools_module = live_mcp
    revisions = tools_module.dispatch_tool("get_handbook_revisions", {})
    assert len(revisions["revisions"]) == 11


def test_live_rewritten_description_in_tools_list(live_mcp):
    """Spec 14.9: the ONE rewritten docstring is what tools/list serves."""
    _, tools_module = live_mcp
    description = next(
        t["function"]["description"]
        for t in tools_module.TOOL_SCHEMAS
        if t["function"]["name"] == "get_policy_section"
    )
    assert "USE THIS TOOL WHEN" in description
    assert "INTERPRETING FAILURES" in description


def test_recoverable_error_reaches_the_model():
    """Spec 14.10: the captured after-transcript shows the model received
    the recoverable error and acted on it (v3.2) instead of flailing on
    an opaque failure."""
    text = (EVID / "error_before_after.md").read_text(encoding="utf-8")
    assert "Suggested recovery:" in text           # error text the model got
    assert "has not yet been published" in text    # model's response using it
