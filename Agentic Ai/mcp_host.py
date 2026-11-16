"""MCP client/host layer for the Week 9 HR handbook practical.

Reads ``mcp_config.json`` (configuration is the only place MCP servers are
declared), spawns each configured server as a subprocess, performs the MCP
``initialize`` handshake, discovers tools through ``tools/list``, and routes
``tools/call`` requests to the server that owns each discovered tool.

Every JSON-RPC message sent or received is appended to
``output/mcp_trace.jsonl`` so discovery and invocation can be evidence-
checked after the fact.

No LLM call happens in this module or inside any MCP server: the model
call lives in the agent/host layer (``agent.py`` / ``llm_client.py``).
"""

import atexit
import contextvars
import json
import os
import queue
import subprocess
import sys
import threading
import time
from itertools import count
from pathlib import Path

AGENTIC_DIR = Path(__file__).resolve().parent
# HR_MCP_CONFIG lets the capstone entry point discover only the handbook server.
DEFAULT_CONFIG_PATH = Path(os.environ.get("HR_MCP_CONFIG") or AGENTIC_DIR / "mcp_config.json")
TRACE_PATH = AGENTIC_DIR / "output" / "mcp_trace.jsonl"

sys.path.insert(0, str(AGENTIC_DIR.parent / "src"))
from redact import redact_obj  # noqa: E402

# Set by the entry point per request; sent to the server as params._meta.trace_id.
TRACE_ID = contextvars.ContextVar("mcp_trace_id", default=None)

PROTOCOL_VERSION = "2025-06-18"
INITIALIZE_TIMEOUT_SECONDS = 120
TOOLS_LIST_TIMEOUT_SECONDS = 120
TOOLS_CALL_TIMEOUT_SECONDS = 120


class MCPDiscoveryError(Exception):
    """A configured MCP server could not be spawned, initialized, or asked
    for its tool list. Callers treat this as 'MCP unavailable'."""


class MCPTransportError(Exception):
    """An already-discovered MCP server failed during tools/call (server
    died, write failed, or a JSON-RPC error response came back). This is
    distinct from a tool-reported failure (an ``isError`` result), so a
    caller can tell 'server problem' from 'tool says not found'."""


def _trace(direction, server_key, payload):
    """Append one sent or received JSON-RPC message to the MCP traffic
    trace file.

    Args:
        direction (str): ``"send"`` or ``"recv"``.
        server_key (str): config key of the server this message belongs to.
        payload (dict): the parsed JSON-RPC message.
    """
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "server": server_key,
        "direction": direction,
        "payload": redact_obj(payload),  # arguments can carry pasted secrets
    }
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        # The trace is evidence, not the tool path: a failed append must
        # not take the agent down, but it must not vanish silently either.
        print(f"[mcp_host] could not write trace to {TRACE_PATH}: {error}", file=sys.stderr)


class MCPServerConnection:
    """One spawned MCP server subprocess connected over stdio using
    newline-delimited JSON-RPC 2.0 (MCP's stdio transport)."""

    def __init__(self, key, config, config_dir):
        """Spawn the server process.

        Args:
            key (str): server key from ``mcpServers`` in the config.
            config (dict): that server's config entry (``command``,
                ``args``, ``cwd``, ``name``).
            config_dir (Path): directory the config file lives in; the
                ``command`` path is resolved relative to it.

        Raises:
            MCPTransportError: the process could not be started.
        """
        self.key = key
        self.label = config.get("name") or key
        self._ids = count(1)
        self._queue = queue.Queue()
        self._closed = False

        command = str((config_dir / config["command"]).resolve())
        cwd = str((config_dir / config.get("cwd", ".")).resolve())
        env = dict(os.environ)
        # Marks this process as an MCP *server*: tools.py skips its MCP
        # client initialization when this is set, so a server subprocess
        # can never spawn itself or its siblings recursively.
        env["HR_MCP_SERVER_ROLE"] = "mcp-server"
        env["PYTHONIOENCODING"] = "utf-8"

        log_path = AGENTIC_DIR / "output" / f"mcp_{key}_stderr.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = open(log_path, "w", encoding="utf-8")

        try:
            self._process = subprocess.Popen(
                [command, *config.get("args", [])],
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._log_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            self._log_handle.close()
            raise MCPTransportError(f"could not start server '{key}': {error}") from error

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        """Push every stdout line from the server onto the response queue;
        a None sentinel marks EOF so a waiting request fails fast instead
        of hanging when the server dies."""
        try:
            for line in self._process.stdout:
                self._queue.put(line)
        finally:
            self._queue.put(None)

    def _send(self, payload):
        """Write one JSON-RPC message to the server's stdin.

        Args:
            payload (dict): the message to send.

        Raises:
            MCPTransportError: stdin is broken or closed (server died).
        """
        _trace("send", self.key, payload)
        try:
            self._process.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
            self._process.stdin.flush()
        except (OSError, ValueError) as error:
            raise MCPTransportError(
                f"server '{self.key}' is not accepting input ({error})"
            ) from error

    def notify(self, method, params=None):
        """Send a JSON-RPC notification (no ``id``, so no response)."""
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def request(self, method, params, timeout):
        """Send a JSON-RPC request and wait for its response.

        Args:
            method (str): e.g. ``initialize``, ``tools/list``, ``tools/call``.
            params (dict | None): request params; ``None`` omits the field.
            timeout (float): seconds to wait before failing.

        Returns:
            dict: the full response message, including an ``error`` entry
            if the server reported a JSON-RPC error (the caller decides
            how to treat it).

        Raises:
            MCPTransportError: timeout, server exit, or invalid JSON on
                the wire (all are transport-level problems, not tool
                results).
        """
        request_id = next(self._ids)
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPTransportError(
                    f"server '{self.key}' did not answer '{method}' within {timeout}s"
                )
            try:
                line = self._queue.get(timeout=remaining)
            except queue.Empty:
                raise MCPTransportError(
                    f"server '{self.key}' did not answer '{method}' within {timeout}s"
                ) from None
            if line is None:
                raise MCPTransportError(
                    f"server '{self.key}' exited while '{method}' was in flight"
                )
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                raise MCPTransportError(
                    f"server '{self.key}' sent invalid JSON ({error}): {line[:200]}"
                ) from error
            _trace("recv", self.key, message)
            if message.get("id") == request_id and ("result" in message or "error" in message):
                return message
            # Anything else (notifications, e.g. logging) is recorded in
            # the trace and skipped here.

    def close(self):
        """Terminate the server process (idempotent)."""
        if self._closed:
            return
        self._closed = True
        try:
            self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        self._log_handle.close()


# Process-wide discovery cache: name -> owning connection, plus the
# per-server tool grouping used for evidence reporting.
_DISCOVERED = False
_OWNERS = {}
_SERVER_TOOLS = {}
_CONNECTIONS = {}


def discover_tools():
    """Spawn every server in ``mcp_config.json``, run the ``initialize``
    handshake, and aggregate everything ``tools/list`` reports.

    Returns:
        list[dict]: MCP tool entries ``{name, description, inputSchema}``
        in config order. This is the source of truth for which tools the
        agent sees.

    Raises:
        MCPDiscoveryError: any configured server fails (no silent
        partial discovery), the config is missing/malformed, or two
        servers claim the same tool name.

    Idempotent: the first successful discovery is cached for the process.
    """
    global _DISCOVERED, _OWNERS, _SERVER_TOOLS, _CONNECTIONS
    if _DISCOVERED:
        return [tool for names in _SERVER_TOOLS.values() for tool in names]

    config, config_dir = _load_config()
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise MCPDiscoveryError(f"{config_dir} contains no mcpServers entries")
    for key, entry in servers.items():
        if not isinstance(entry, dict) or "command" not in entry:
            raise MCPDiscoveryError(f"server '{key}' in {config_dir} has no 'command'")

    tools = []
    owners = {}
    server_tools = {}
    connections = {}
    try:
        for key, entry in servers.items():
            conn = MCPServerConnection(key, entry, config_dir)
            connections[key] = conn
            response = conn.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "hr-agent-host", "version": "1.0"},
                },
                INITIALIZE_TIMEOUT_SECONDS,
            )
            if "error" in response:
                raise MCPDiscoveryError(f"server '{key}' initialize failed: {response['error']}")
            conn.notify("notifications/initialized")

            response = conn.request("tools/list", {}, TOOLS_LIST_TIMEOUT_SECONDS)
            if "error" in response:
                raise MCPDiscoveryError(f"server '{key}' tools/list failed: {response['error']}")

            names = []
            for tool in (response.get("result") or {}).get("tools", []):
                name = tool.get("name")
                if not name:
                    raise MCPDiscoveryError(f"server '{key}' returned a tool with no name")
                if name in owners:
                    raise MCPDiscoveryError(
                        f"tool '{name}' is provided by both '{owners[name].key}' and "
                        f"'{key}'; tool names must be unique across servers"
                    )
                owners[name] = conn
                names.append(tool)
                tools.append(tool)
            server_tools[key] = names
    except (MCPDiscoveryError, MCPTransportError) as error:
        for conn in connections.values():
            conn.close()
        if isinstance(error, MCPDiscoveryError):
            raise
        raise MCPDiscoveryError(str(error)) from error

    _DISCOVERED = True
    _OWNERS = owners
    _SERVER_TOOLS = server_tools
    _CONNECTIONS = connections
    atexit.register(_close_all)
    return tools


def tools_by_server():
    """Return ``{server config key: [MCP tool dicts]}`` from the last
    successful discovery (empty dict before discovery)."""
    return {key: list(names) for key, names in _SERVER_TOOLS.items()}


def known_tools():
    """Return the set of tool names discovered via ``tools/list``."""
    return set(_OWNERS)


def call_tool(name, arguments):
    """Invoke a discovered tool on the server that owns it via
    ``tools/call``.

    Args:
        name (str): tool name as reported by ``tools/list``.
        arguments (dict): JSON object arguments for the tool.

    Returns:
        tuple[str, bool]: the joined ``text`` content and whether the
        server flagged the result ``isError``.

    Raises:
        MCPTransportError: the tool is not owned by any discovered server,
        or the server cannot be reached / answered with a JSON-RPC error.
    """
    conn = _OWNERS.get(name)
    if conn is None:
        raise MCPTransportError(f"no discovered MCP server provides tool '{name}'")
    params = {"name": name, "arguments": arguments}
    if TRACE_ID.get():
        params["_meta"] = {"trace_id": TRACE_ID.get()}
    response = conn.request("tools/call", params, TOOLS_CALL_TIMEOUT_SECONDS)
    if "error" in response:
        error = response.get("error") or {}
        raise MCPTransportError(
            f"server '{conn.key}' returned JSON-RPC error "
            f"{error.get('code')}: {error.get('message')}"
        )
    result = response.get("result") or {}
    parts = [
        part.get("text", "")
        for part in result.get("content", [])
        if part.get("type") == "text"
    ]
    return "\n".join(parts), bool(result.get("isError", False))


def to_openai_schema(tool):
    """Convert one MCP ``tools/list`` entry into the OpenAI/Groq
    chat-completions function-tool shape the existing agent already sends.

    Args:
        tool (dict): MCP tool entry with ``name``, ``description``,
            ``inputSchema``.

    Returns:
        dict: ``{"type": "function", "function": {...}}``.
    """
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get(
                "inputSchema", {"type": "object", "properties": {}}
            ),
        },
    }


def _load_config():
    """Read and minimally validate ``mcp_config.json``.

    Returns:
        tuple[dict, Path]: the parsed config and its directory.

    Raises:
        MCPDiscoveryError: file missing, invalid JSON, or no servers.
    """
    if not DEFAULT_CONFIG_PATH.exists():
        raise MCPDiscoveryError(f"MCP config not found: {DEFAULT_CONFIG_PATH}")
    try:
        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MCPDiscoveryError(f"{DEFAULT_CONFIG_PATH} is not valid JSON: {error}") from error
    if not isinstance(config, dict):
        raise MCPDiscoveryError(f"{DEFAULT_CONFIG_PATH} must contain a JSON object")
    return config, DEFAULT_CONFIG_PATH.parent


def _close_all():
    """Shut down every server process spawned by this host."""
    for conn in list(_CONNECTIONS.values()):
        conn.close()
