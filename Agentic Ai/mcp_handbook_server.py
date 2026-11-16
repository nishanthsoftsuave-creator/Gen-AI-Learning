"""HR Handbook MCP server (server 1 of the Week 9 practical).

Exposes the three existing handbook tools -- ``search_handbook``,
``get_policy_section``, ``get_handbook_revisions`` -- as MCP tools over the
stdio transport (newline-delimited JSON-RPC 2.0). The tool list served by
``tools/list`` comes from the existing ``tools.TOOL_SCHEMAS`` definitions,
and ``tools/call`` executes the existing ``tools.dispatch_tool``: this
server adds no tool logic of its own and duplicates none.

No LLM call happens inside this server: results are computed by the
existing Python functions; the model call lives in the agent/host layer.
"""

import json
import os
import sys
import time
from pathlib import Path

AUDIT_PATH = Path(__file__).resolve().parent / "output" / "mcp_audit.jsonl"

# This process is an MCP *server*: it must never act as an MCP client, so
# tools.py skips its MCP-host initialization here (this also makes running
# this script standalone safe -- it cannot recursively spawn servers).
os.environ.setdefault("HR_MCP_SERVER_ROLE", "mcp-server")

SERVER_NAME = "hr-handbook-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

_catalog_cache = None


def _catalog():
    """Return this server's tool list as MCP ``tools/list`` entries.

    Lazy: ``import tools`` pulls in the full retrieval stack (chromadb +
    embedding model, ~25s), so it happens on the first ``tools/list``
    rather than at process start.

    Returns:
        list[dict]: ``{name, description, inputSchema}`` entries built
        from the existing ``tools.TOOL_SCHEMAS`` (static inside a server
        process -- see the MCP block at the bottom of ``tools.py``).
    """
    global _catalog_cache
    if _catalog_cache is None:
        import tools

        _catalog_cache = [
            {
                "name": schema["function"]["name"],
                "description": schema["function"]["description"],
                "inputSchema": schema["function"]["parameters"],
            }
            for schema in tools.TOOL_SCHEMAS
        ]
    return _catalog_cache


def _execute(name, arguments):
    """Run one existing handbook tool through the existing dispatcher.

    Args:
        name (str): tool name, already validated against the catalog.
        arguments (dict): JSON-object arguments from the request.

    Returns:
        tuple[str, bool]: (JSON text of the tool result, False).

    Raises:
        Exception: whatever the underlying tool raises (e.g. ToolError
        for an unsupported section) -- the caller converts failures into
        an MCP ``isError`` result so the model can read the message.
    """
    import tools

    result = tools.dispatch_tool(name, arguments)
    return json.dumps(result, ensure_ascii=False), False


def _audit(trace_id, tool, arguments, started, is_error):
    """One line per tools/call so a request can be followed across the MCP hop.

    Logs the trace id, tool, group and timing only: never the query text, which may hold secrets.
    """
    line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "trace_id": trace_id,
        "tool": tool,
        "employee_group": arguments.get("employee_group"),
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
        "is_error": bool(is_error),
    }
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
    except OSError as error:
        print(f"[mcp-server] audit write failed: {error}", file=sys.stderr)


def _send(message):
    """Write one JSON-RPC message to stdout (the MCP stdio transport)."""
    sys.stdout.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _respond_ok(request_id, result):
    _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _respond_error(request_id, code, message):
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def handle(message):
    """Dispatch one parsed JSON-RPC message and write its response (if the
    message is a request; notifications are never answered)."""
    request_id = message.get("id")
    method = message.get("method")

    if method is None:
        if request_id is not None:
            _respond_error(request_id, -32600, "Invalid Request: missing method")
        return
    if request_id is None:
        # Notification (e.g. notifications/initialized): no response.
        return

    if method == "initialize":
        params = message.get("params") or {}
        client_version = params.get("protocolVersion")
        _respond_ok(request_id, {
            "protocolVersion": (
                client_version if isinstance(client_version, str) else PROTOCOL_VERSION
            ),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    elif method == "ping":
        _respond_ok(request_id, {})
    elif method == "tools/list":
        _respond_ok(request_id, {"tools": _catalog()})
    elif method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in {t["name"] for t in _catalog()}:
            _respond_error(request_id, -32602, f"Unknown tool: {name!r}")
            return
        started = time.monotonic()
        trace_id = (params.get("_meta") or {}).get("trace_id")
        try:
            text, is_error = _execute(name, arguments)
        except Exception as error:
            # Tool-level failures are isError results, not protocol
            # errors: the model must be able to read the message.
            _audit(trace_id, name, arguments, started, True)
            _respond_ok(request_id, {
                "content": [{"type": "text", "text": str(error)}],
                "isError": True,
            })
            return
        _audit(trace_id, name, arguments, started, is_error)
        result = {"content": [{"type": "text", "text": text}]}
        if is_error:
            result["isError"] = True
        _respond_ok(request_id, result)
    else:
        _respond_error(request_id, -32601, f"Method not found: {method}")


def main():
    """Serve newline-delimited JSON-RPC from stdin until EOF."""
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            _send({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {error}"},
            })
            continue
        if not isinstance(message, dict):
            _send({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: not an object"},
            })
            continue
        handle(message)


if __name__ == "__main__":
    main()
