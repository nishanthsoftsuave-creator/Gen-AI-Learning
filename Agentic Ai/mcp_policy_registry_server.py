"""HR Policy Registry MCP server (server 2 of the Week 9 practical).

An independently maintained MCP server that exposes STRUCTURED HR policy
metadata (version, effective date, deprecation, registry metadata) from
``policy_registry.json`` -- kept separate from the handbook/document
search server, and reachable by the agent purely through configuration
(``mcp_config.json``) plus MCP discovery (``tools/list``).

No LLM call happens inside this server: every result is computed from the
registry JSON file; the model call lives in the agent/host layer.
"""

import json
import sys
from pathlib import Path

REGISTRY_FILE = Path(__file__).resolve().parent / "policy_registry.json"
REGISTRY = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))

SERVER_NAME = "hr-policy-registry-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

TOOL_DEFS = [
    {
        "name": "get_policy_version",
        "description": (
            "Get the full published record of ONE specific version of an "
            "HR policy (status, effective date, deprecation info, summary). "
            "USE when the user names a policy AND a specific version "
            "(e.g. 'remote work policy v4'). REQUIRED: `policy` (registry "
            "id) and `version` (exact published key, e.g. v3.2). Returns "
            "the version record, or an error if the policy id or version "
            "does not exist. For only the current version's metadata use "
            "get_policy_metadata; for only a date use "
            "get_policy_effective_date."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy": {
                    "type": "string",
                    "description": (
                        "Policy id: leave_policy, remote_work_policy, "
                        "attendance_policy, expense_policy, "
                        "parental_leave_policy, or code_of_conduct."
                    ),
                },
                "version": {
                    "type": "string",
                    "description": "Exact published version key, e.g. v3 or v3.2.",
                },
            },
            "required": ["policy", "version"],
        },
    },
    {
        "name": "get_policy_effective_date",
        "description": (
            "Get the date a policy version took effect. USE when the user "
            "asks when a policy started, was effective, or was updated. "
            "REQUIRED: `policy`; OPTIONAL: `version` (defaults to the "
            "policy's current version). Returns policy id, version, "
            "effective date, and status, or an error if the policy id or "
            "version does not exist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy": {
                    "type": "string",
                    "description": "Policy id, e.g. remote_work_policy.",
                },
                "version": {
                    "type": "string",
                    "description": "Optional version key; defaults to the current version.",
                },
            },
            "required": ["policy"],
        },
    },
    {
        "name": "get_policy_deprecation",
        "description": (
            "Check whether a policy version is active, deprecated, or "
            "superseded, and which version replaced it. USE when the user "
            "asks whether a policy or version is still active, retired, "
            "replaced, or superseded. REQUIRED: `policy`; OPTIONAL: "
            "`version` (defaults to the current version). Returns status, "
            "deprecated_on, and superseded_by, or an error if the policy "
            "id or version does not exist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy": {
                    "type": "string",
                    "description": "Policy id, e.g. remote_work_policy.",
                },
                "version": {
                    "type": "string",
                    "description": "Optional version key; defaults to the current version.",
                },
            },
            "required": ["policy"],
        },
    },
    {
        "name": "get_policy_metadata",
        "description": (
            "Get registry metadata for a policy: title, owner, category, "
            "applies_to, current version, full version history, and last "
            "reviewed date. USE for questions about policy ownership or "
            "administration, or which versions exist. Does NOT return the "
            "policy's prose content -- use search_handbook or "
            "get_policy_section for Handbook text. REQUIRED: `policy`. "
            "Returns metadata, or an error if the policy id does not exist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy": {"type": "string", "description": "Policy id, e.g. code_of_conduct."}
            },
            "required": ["policy"],
        },
    },
]

REQUIRED_ARGS = {
    "get_policy_version": ("policy", "version"),
    "get_policy_effective_date": ("policy",),
    "get_policy_deprecation": ("policy",),
    "get_policy_metadata": ("policy",),
}


class PolicyError(Exception):
    """A tool-level failure whose message is shown to the model as an
    ``isError`` result (not a JSON-RPC protocol error)."""


def _require(arguments, keys):
    """Ensure every required key is present and non-empty.

    Raises:
        PolicyError: naming the missing keys.
    """
    missing = [key for key in keys if not arguments.get(key)]
    if missing:
        raise PolicyError(f"Missing required argument(s): {', '.join(missing)}")


def _get_policy(policy_id):
    """Look up one policy by registry id.

    Raises:
        PolicyError: when the id is not in the registry.
    """
    policy = REGISTRY["policies"].get(policy_id)
    if policy is None:
        raise PolicyError("policy not found")
    return policy


def _resolve(policy_id, version):
    """Resolve (version_key, version_record) for a policy, defaulting to
    the current published version when ``version`` is None.

    Raises:
        PolicyError: when the policy id or the version key is unknown.
    """
    policy = _get_policy(policy_id)
    if version is None:
        version = policy["current_version"]
    record = policy["versions"].get(version)
    if record is None:
        raise PolicyError("policy not found")
    return version, record


def get_policy_version(policy, version):
    """Full record for one exact policy version.

    Args:
        policy (str): registry policy id.
        version (str): exact published version key.

    Returns:
        dict: policy id, version key, status, effective_date,
        deprecated_on, superseded_by, summary.

    Raises:
        PolicyError: unknown policy id or version.
    """
    version_key, record = _resolve(policy, version)
    return {"policy": policy, "version": version_key, **record}


def get_policy_effective_date(policy, version=None):
    """Effective date of a policy version (current version by default).

    Args:
        policy (str): registry policy id.
        version (str | None): optional version key.

    Returns:
        dict: policy id, resolved version, effective_date, status.

    Raises:
        PolicyError: unknown policy id or version.
    """
    version_key, record = _resolve(policy, version)
    return {
        "policy": policy,
        "version": version_key,
        "effective_date": record["effective_date"],
        "status": record["status"],
    }


def get_policy_deprecation(policy, version=None):
    """Deprecation status of a policy version (current version by default).

    Args:
        policy (str): registry policy id.
        version (str | None): optional version key.

    Returns:
        dict: policy id, resolved version, status, deprecated_on,
        superseded_by.

    Raises:
        PolicyError: unknown policy id or version.
    """
    version_key, record = _resolve(policy, version)
    return {
        "policy": policy,
        "version": version_key,
        "status": record["status"],
        "deprecated_on": record["deprecated_on"],
        "superseded_by": record["superseded_by"],
    }


def get_policy_metadata(policy):
    """Registry metadata for one policy.

    Args:
        policy (str): registry policy id.

    Returns:
        dict: title, owner, category, applies_to, current_version,
        last_reviewed, and the ordered version keys.

    Raises:
        PolicyError: unknown policy id.
    """
    record = _get_policy(policy)
    return {
        "policy": policy,
        "title": record["title"],
        "owner": record["owner"],
        "category": record["category"],
        "applies_to": record["applies_to"],
        "current_version": record["current_version"],
        "last_reviewed": record["last_reviewed"],
        "versions": list(record["versions"].keys()),
    }


FUNCS = {
    "get_policy_version": get_policy_version,
    "get_policy_effective_date": get_policy_effective_date,
    "get_policy_deprecation": get_policy_deprecation,
    "get_policy_metadata": get_policy_metadata,
}


def _execute(name, arguments):
    """Run one registry tool.

    Args:
        name (str): tool name, already validated against the catalog.
        arguments (dict): JSON-object arguments from the request.

    Returns:
        tuple[str, bool]: (JSON text of the result, False).

    Raises:
        PolicyError: missing arguments, unknown policy/version.
    """
    func = FUNCS.get(name)
    if func is None:
        raise PolicyError(f"Unknown tool '{name}'.")
    if not isinstance(arguments, dict):
        raise PolicyError("arguments must be a JSON object")
    _require(arguments, REQUIRED_ARGS[name])
    return json.dumps(func(**arguments), ensure_ascii=False), False


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
        _respond_ok(request_id, {"tools": TOOL_DEFS})
    elif method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in FUNCS:
            _respond_error(request_id, -32602, f"Unknown tool: {name!r}")
            return
        try:
            text, is_error = _execute(name, arguments)
        except Exception as error:
            # Tool-level failures are isError results, not protocol
            # errors: the model must be able to read the message.
            _respond_ok(request_id, {
                "content": [{"type": "text", "text": str(error)}],
                "isError": True,
            })
            return
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
