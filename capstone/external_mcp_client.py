"""A deliberately independent MCP client: raw newline-delimited JSON-RPC over stdio, sharing no code
with mcp_host.py. It stands in for "a client that isn't yours" when no second person is available,
and it is the script a fresh-eyes reviewer can run or read. It does NOT replace the reviewer's own client.

  python capstone/external_mcp_client.py

Checks over the real wire: tools are discoverable, the group filter and the boundary-trim hold for an
outside caller, and the caller's trace id reaches the server's audit log.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "Agentic Ai" / "output" / "mcp_audit.jsonl"
TRACE_ID = f"tr_external_{int(time.time())}"
OUT = HERE / "output" / "external_client_run.json"


def main():
    server = subprocess.Popen([sys.executable, str(HERE / "capstone.py"), "serve-mcp"], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    next_id = iter(range(1, 100))

    def call(method, params=None):
        request = {"jsonrpc": "2.0", "id": next(next_id), "method": method, "params": params or {}}
        server.stdin.write(json.dumps(request) + "\n")
        server.stdin.flush()
        return json.loads(server.stdout.readline())

    def search(query, group):
        reply = call("tools/call", {"name": "search_handbook", "arguments": {"query": query, "top_k": 3, "employee_group": group},
                                    "_meta": {"trace_id": TRACE_ID}})
        return json.loads(reply["result"]["content"][0]["text"])

    started = time.monotonic()
    call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "external-check", "version": "0"}})
    names = [t["name"] for t in call("tools/list")["result"]["tools"]]
    tech = " ".join(c["text"] for c in search("recruitment drive outstation travel compensation per day", "technical")["results"])
    nontech = " ".join(c["text"] for c in search("what compensation do I get for working on a company holiday", "non_technical")["results"])
    bad = call("tools/call", {"name": "get_policy_section", "arguments": {"section": "nope"}})["result"]
    server.stdin.close()
    server.wait(timeout=30)

    audit_lines = [json.loads(line) for line in AUDIT.read_text(encoding="utf-8").splitlines() if TRACE_ID in line]
    checks = {
        "discovers_3_tools": sorted(names) == ["get_handbook_revisions", "get_policy_section", "search_handbook"],
        "technical_caller_gets_outstation_1000": "1000 INR per day" in " ".join(tech.split()),
        "nontechnical_caller_not_given_other_team_figures": not any(f in nontech for f in ("500 INR", "1000 INR", "outstation")),
        "bad_section_is_a_readable_isError_not_a_crash": bad.get("isError") is True and "Unsupported section" in bad["content"][0]["text"],
        "trace_id_reached_server_audit_log": len([a for a in audit_lines if a["trace_id"] == TRACE_ID]) == 2,
        "audit_log_holds_no_query_text": all(set(a) == {"ts", "trace_id", "tool", "employee_group", "latency_ms", "is_error"} for a in audit_lines),
    }
    OUT.write_text(json.dumps({"trace_id": TRACE_ID, "seconds": round(time.monotonic() - started, 1), "tools": names, "checks": checks}, indent=2), encoding="utf-8")
    for name, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + name)
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
