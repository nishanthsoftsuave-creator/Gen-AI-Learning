# Error path before and after (Task 7)

The **exact same failing query** was run through the unchanged agent
(`Agentic Ai/agent.py`) twice: once against the HR Policy Registry MCP
server as first written (opaque error), and once after the Task 6 fix
(recoverable error). Both runs were captured live -- console transcripts,
the agent run traces, and the raw JSON-RPC frames in
`Agentic Ai/output/mcp_trace.jsonl`. Nothing below is hand-written
except the commentary.

**Query (identical in both runs):**

    "What is the remote work policy in version v4?"

Ground truth in the registry (`Agentic Ai/policy_registry.json`):
`remote_work_policy` current version is **v3.2** (effective 2026-08-01);
**v4 was never published**.

---

## BEFORE

State: commits `c6aea49` + `ad3f3d2` (both servers configured; the
registry still returned the original opaque error). Captured from run
trace `Agentic Ai/output/traces/tr_920b7b4d510b.json`.

### 1. User query

    What is the remote work policy in version v4?

### 2. Model / tool selection

The model correctly picked the registry tool (despite the agent's
system prompt still describing the original three tools -- the discovered
schema list drives selection):

```
[Tool] get_policy_version({'policy': 'remote_work_policy', 'version': 'v4'}) -> ERROR: policy not found
```

### 3. MCP tool call (raw frame from the wire)

```json
{
  "ts": "2026-10-01T12:16:06",
  "request": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_policy_version",
      "arguments": {
        "policy": "remote_work_policy",
        "version": "v4"
      }
    }
  },
  "response": {
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
      "content": [
        {
          "type": "text",
          "text": "policy not found"
        }
      ],
      "isError": true
    }
  }
}
```

### 4. Original error response

    policy not found

One line. It does not say whether the *policy* is unknown, the
*version* is unknown, the policy is *deprecated*, or the *server* is
broken -- the model cannot tell these apart.

### 5. Model's resulting behavior

Unable to interpret the error, the model guessed: it searched the
handbook twice with progressively broader queries, blew past the
pre-existing 12,000-token budget, and was terminated with **no final
answer at all**:

```text
[Agent] iteration=1 input_tokens=1501 output_tokens=130 cumulative_tokens=1631 cumulative_cost=0.000152
[Tool] get_policy_version({'policy': 'remote_work_policy', 'version': 'v4'}) -> ERROR: policy not found
[Agent] iteration=2 input_tokens=1542 output_tokens=179 cumulative_tokens=3352 cumulative_cost=0.000321
[Tool] search_handbook({'query': 'remote work policy v4', 'top_k': 5}) -> ok
[Agent] iteration=3 input_tokens=2932 output_tokens=304 cumulative_tokens=6588 cumulative_cost=0.000632
[Tool] search_handbook({'query': 'remote work policy', 'top_k': 10}) -> ok
[Agent] iteration=4 input_tokens=5497 output_tokens=311 cumulative_tokens=12396 cumulative_cost=0.001138
[Budget] TRIGGERED after LLM call 4: MAX_TOKENS_EXCEEDED

========== ANSWER ==========
[No final answer -- agent terminated early due to MAX_TOKENS_EXCEEDED]

Termination: MAX_TOKENS_EXCEEDED
Iterations: 4
Total tokens: 12396  Cost: $0.001138
Elapsed: 34.62s
Trace: D:\Nishanth - Learning\Gen AI\rag-python\Agentic Ai\output\traces\tr_920b7b4d510b.json
```

Summary: 4 iterations, 12,396 tokens, termination
`MAX_TOKENS_EXCEEDED`, answer `[No final answer -- agent terminated
early due to MAX_TOKENS_EXCEEDED]`.

---

## AFTER

State: commit `63a1226` (Task 6 fix in
`mcp_policy_registry_server.py` only; agent module untouched -- see
`agent_diff.txt`). Captured from run trace
`Agentic Ai/output/traces/tr_650bbb69db38.json`.

### 1. User query

    What is the remote work policy in version v4?

### 2. Model / tool selection

Same tool, same arguments:

```
[Tool] get_policy_version({'policy': 'remote_work_policy', 'version': 'v4'}) -> ERROR: (recoverable response -- see below)
```

### 3. MCP tool call (raw frame from the wire)

```json
{
  "ts": "2026-10-01T12:35:05",
  "request": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_policy_version",
      "arguments": {
        "policy": "remote_work_policy",
        "version": "v4"
      }
    }
  },
  "response": {
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
      "content": [
        {
          "type": "text",
          "text": "Requested remote_work_policy version v4 does not exist.\n\nLatest published version: v3.2.\nStatus: v4 has not been published.\n\nAvailable information:\n- Current version: v3.2\n- Effective date: 2026-08-01\n- Published versions: v1, v2, v3, v3.2\n- Deprecated versions: v1, v2\n- Superseded versions: v3\n\nSuggested recovery:\nUse v3.2 if the user wants the currently published policy."
        }
      ],
      "isError": true
    }
  }
}
```

### 4. New recoverable error response

    Requested remote_work_policy version v4 does not exist.

Latest published version: v3.2.
Status: v4 has not been published.

Available information:
- Current version: v3.2
- Effective date: 2026-08-01
- Published versions: v1, v2, v3, v3.2
- Deprecated versions: v1, v2
- Superseded versions: v3

Suggested recovery:
Use v3.2 if the user wants the currently published policy.

Every fact in this message is read from `policy_registry.json` by
`_not_found_error()` -- nothing is hardcoded or invented. It tells the
model: what does not exist (v4), what does (v3.2, published versions),
what is deprecated/superseded, and what to do (use v3.2).

### 5. Model's improved response

```text
[Agent] iteration=1 input_tokens=1501 output_tokens=120 cumulative_tokens=1621 cumulative_cost=0.000149
[Tool] get_policy_version({'policy': 'remote_work_policy', 'version': 'v4'}) -> ERROR: Requested remote_work_policy version v4 does not exist.

Latest published version: v3.2.
Status: v4 has not been published.

Available information:
- Current version: v3.2
- Effective date: 2026-08-01
- Published versions: v1, v2, v3, v3.2
- Deprecated versions: v1, v2
- Superseded versions: v3

Suggested recovery:
Use v3.2 if the user wants the currently published policy.
[Agent] iteration=2 input_tokens=1654 output_tokens=188 cumulative_tokens=3463 cumulative_cost=0.000329

========== ANSWER ==========
The requested **remote_work_policy v4** has not yet been published.  
The most recent version available in the handbook is **v3.2**:

- **Effective date:** 2026‑08‑01  
- **Current version:** v3.2  
- **Published versions:** v1, v2, v3, **v3.2**  
- **Deprecated versions:** v1, v2  
- **Superseded versions:** v3  

If you need the full text of the current remote work policy, let me know and I can retrieve the v3.2 section for you.

Termination: COMPLETED
Iterations: 2
Total tokens: 3463  Cost: $0.000329
Elapsed: 1.49s
Trace: D:\Nishanth - Learning\Gen AI\rag-python\Agentic Ai\output\traces\tr_21d3ab286f5c.json
```

Summary: 2 iterations, 3,488 tokens, termination `COMPLETED`, complete
answer: v4 not published; v3.2 current, effective 2026-08-01; version
lists included; offers to fetch the v3.2 section next.

---

## What changed

- **Only** the error construction inside the registry server:
  `_get_policy()` / `_resolve()` in
  `Agentic Ai/mcp_policy_registry_server.py` now raise their message via
  `_not_found_error()`, which builds it from the actual registry data.
  Commit `63a1226` (56 insertions, 4 deletions -- all in that one file).
- The agent, the tools module, the schemas, and the config did not change
  (`agent_diff.txt`, `config_diff.txt`).
- The model-side effect: instead of an uninterpretable failure that
  triggered blind search until the budget died, the model received
  actionable facts and answered in half the iterations for a quarter of
  the tokens.

## Unknown version vs. MCP server failure (live demonstration)

The two failure classes now travel through different paths and arrive
with different, unambiguous messages:

| Failure class | Path | What the model receives |
|---|---|---|
| Unknown policy / version | server executes, returns `isError: true` with the recoverable text above | the data-derived message (names the missing thing + what exists + recovery) |
| MCP server unreachable / died | `tools/call` transport fails; `mcp_host.py` raises `MCPTransportError`; `tools.py::_dispatch_mcp_tool` converts it to `ToolError` | `MCP server call failed for '<tool>': ...` |

The second row was demonstrated live, not asserted: the registry server
process was killed and the same dispatch path was called -- the failure
was raised after 1 ms, result:

```text
MCP server call failed for 'get_policy_effective_date': server 'hr-policy-registry' is not accepting input ([Errno 22] Invalid argument)
```

So a tool-result error is never mistaken for an outage, and an outage is
never mistaken for "policy not found".

