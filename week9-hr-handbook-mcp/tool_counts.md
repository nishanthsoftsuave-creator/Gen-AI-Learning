# Tool discovery counts (Task 3)

Every count and name below comes from an **actual `tools/list` response**
captured over the MCP stdio transport in raw JSON-RPC sessions
(`initialize` -> `notifications/initialized` -> `tools/list`) against the
servers declared in `Agentic Ai/mcp_config.json`. The frames were
extracted verbatim from the session's MCP traffic log
(`Agentic Ai/output/mcp_trace.jsonl`) -- the tool list is not maintained
by hand anywhere.

## Before Server 2

MCP configuration at capture time: **server one only** (`hr-handbook`),
i.e. git commits `c6aea49` / `7529bc1` -- before the HR Policy Registry
MCP server was added.

**Number of tools: 3**

Names:

- search_handbook
- get_policy_section
- get_handbook_revisions

### Raw exchange captured for server one

```json
{
  "initialize": {
    "request": {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "initialize",
      "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {
          "name": "hr-agent-host",
          "version": "1.0"
        }
      }
    },
    "response": {
      "jsonrpc": "2.0",
      "id": 1,
      "result": {
        "protocolVersion": "2025-06-18",
        "capabilities": {
          "tools": {
            "listChanged": false
          }
        },
        "serverInfo": {
          "name": "hr-handbook-mcp",
          "version": "1.0.0"
        }
      }
    }
  },
  "tools_list": {
    "request": {
      "jsonrpc": "2.0",
      "id": 2,
      "method": "tools/list",
      "params": {}
    },
    "response": {
      "jsonrpc": "2.0",
      "id": 2,
      "result": {
        "tools": [
          {
            "name": "search_handbook",
            "description": "Search the Soft Suave Employee Handbook for passages relevant to a natural-language question: general policy explanations, procedures, and context that may span more than one section. Returns ranked text passages. Does NOT return the full verbatim text of one specific named section (use get_policy_section for that) and does NOT return the Handbook's own dated revision history (use get_handbook_revisions for that).",
            "inputSchema": {
              "type": "object",
              "properties": {
                "query": {
                  "type": "string",
                  "description": "Natural-language search query, e.g. 'what happens if I raise a grievance'."
                },
                "top_k": {
                  "type": "integer",
                  "description": "Number of ranked passages to return. Defaults to 3."
                }
              },
              "required": [
                "query"
              ]
            }
          },
          {
            "name": "get_policy_section",
            "description": "Retrieve the full, verbatim text of ONE specific, named section of the Employee Handbook, located exactly (not by similarity search). Returns only that section's text -- no other section, and no revision history. Use search_handbook instead for a broader natural-language question, and get_handbook_revisions instead for when/how the Handbook document itself has been updated.",
            "inputSchema": {
              "type": "object",
              "properties": {
                "section": {
                  "type": "string",
                  "enum": [
                    "arrear_policy_freshers",
                    "work_from_home_and_deputation_compensation",
                    "employee_code_of_conduct",
                    "disciplinary_actions",
                    "conflict_of_interest_and_gifts",
                    "employee_grievances",
                    "contact_details",
                    "company_leadership"
                  ],
                  "description": "Exact section to retrieve."
                }
              },
              "required": [
                "section"
              ]
            }
          },
          {
            "name": "get_handbook_revisions",
            "description": "Retrieve the Employee Handbook's own dated revision history (every revision number and date, from Revision 1 through the latest) and its modifications clause -- i.e. how many times and when the Handbook DOCUMENT ITSELF has been updated. Does NOT return the content of any HR policy -- use get_policy_section or search_handbook for that.",
            "inputSchema": {
              "type": "object",
              "properties": {}
            }
          }
        ]
      }
    }
  }
}
```

## After Server 2

MCP configuration at capture time: server one **plus the HR Policy
Registry MCP server added through configuration** (git commit `63a1226`;
see `config_diff.txt`).

**Number of tools: 7**

Names (grouped by the server that returned them in `tools/list`):

Server 1 -- HR Handbook MCP server (`hr-handbook`), 3 tools:

- search_handbook
- get_policy_section
- get_handbook_revisions

Server 2 -- HR Policy Registry MCP server (`hr-policy-registry`), 4 tools:

- get_policy_version
- get_policy_effective_date
- get_policy_deprecation
- get_policy_metadata

### Raw exchange captured for both servers

```json
{
  "hr-handbook": {
    "initialize": {
      "request": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
          "protocolVersion": "2025-06-18",
          "capabilities": {},
          "clientInfo": {
            "name": "hr-agent-host",
            "version": "1.0"
          }
        }
      },
      "response": {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
          "protocolVersion": "2025-06-18",
          "capabilities": {
            "tools": {
              "listChanged": false
            }
          },
          "serverInfo": {
            "name": "hr-handbook-mcp",
            "version": "1.0.0"
          }
        }
      }
    },
    "tools_list": {
      "request": {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
      },
      "response": {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
          "tools": [
            {
              "name": "search_handbook",
              "description": "Search the Soft Suave Employee Handbook for passages relevant to a natural-language question: general policy explanations, procedures, and context that may span more than one section. Returns ranked text passages. Does NOT return the full verbatim text of one specific named section (use get_policy_section for that) and does NOT return the Handbook's own dated revision history (use get_handbook_revisions for that).",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "query": {
                    "type": "string",
                    "description": "Natural-language search query, e.g. 'what happens if I raise a grievance'."
                  },
                  "top_k": {
                    "type": "integer",
                    "description": "Number of ranked passages to return. Defaults to 3."
                  }
                },
                "required": [
                  "query"
                ]
              }
            },
            {
              "name": "get_policy_section",
              "description": "Retrieve the FULL, VERBATIM text of exactly ONE named section of the Soft Suave Employee Handbook, located by exact section key -- not by similarity search. USE THIS TOOL WHEN the question is about one specific, named policy area (code of conduct, disciplinary actions, employee grievances, conflict of interest and gifts, arrear policy for freshers, work-from-home and deputation compensation, HR contact details, or company leadership) and you need that section's authoritative wording rather than paraphrase. REQUIRED ARGUMENT: `section`, which must be chosen from the schema's enum -- never invent a key. RETURNS: a summary, the verbatim extracted chunk(s) with chunk ids, a `found` flag, and a note that this PDF's multi-column extraction may interleave adjacent-section text; quote it faithfully and do not silently correct or merge it with other sections. INTERPRETING FAILURES: an error means `section` was not one of the supported enum values (the error lists the valid keys) -- correct the argument and call again. If the requested policy or section does not exist under any enum key, DO NOT guess at one: fall back to search_handbook for the closest real content; if that also finds nothing, state plainly that the Handbook contains no such section and name what IS available. Use search_handbook instead for broader natural-language questions, and get_handbook_revisions for when/how the Handbook document itself has been updated.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "section": {
                    "type": "string",
                    "enum": [
                      "arrear_policy_freshers",
                      "work_from_home_and_deputation_compensation",
                      "employee_code_of_conduct",
                      "disciplinary_actions",
                      "conflict_of_interest_and_gifts",
                      "employee_grievances",
                      "contact_details",
                      "company_leadership"
                    ],
                    "description": "Exact section to retrieve."
                  }
                },
                "required": [
                  "section"
                ]
              }
            },
            {
              "name": "get_handbook_revisions",
              "description": "Retrieve the Employee Handbook's own dated revision history (every revision number and date, from Revision 1 through the latest) and its modifications clause -- i.e. how many times and when the Handbook DOCUMENT ITSELF has been updated. Does NOT return the content of any HR policy -- use get_policy_section or search_handbook for that.",
              "inputSchema": {
                "type": "object",
                "properties": {}
              }
            }
          ]
        }
      }
    }
  },
  "hr-policy-registry": {
    "initialize": {
      "request": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
          "protocolVersion": "2025-06-18",
          "capabilities": {},
          "clientInfo": {
            "name": "hr-agent-host",
            "version": "1.0"
          }
        }
      },
      "response": {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
          "protocolVersion": "2025-06-18",
          "capabilities": {
            "tools": {
              "listChanged": false
            }
          },
          "serverInfo": {
            "name": "hr-policy-registry-mcp",
            "version": "1.0.0"
          }
        }
      }
    },
    "tools_list": {
      "request": {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
      },
      "response": {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
          "tools": [
            {
              "name": "get_policy_version",
              "description": "Get the full published record of ONE specific version of an HR policy (status, effective date, deprecation info, summary). USE when the user names a policy AND a specific version (e.g. 'remote work policy v4'). REQUIRED: `policy` (registry id) and `version` (exact published key, e.g. v3.2). Returns the version record, or an error if the policy id or version does not exist. For only the current version's metadata use get_policy_metadata; for only a date use get_policy_effective_date.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "policy": {
                    "type": "string",
                    "description": "Policy id: leave_policy, remote_work_policy, attendance_policy, expense_policy, parental_leave_policy, or code_of_conduct."
                  },
                  "version": {
                    "type": "string",
                    "description": "Exact published version key, e.g. v3 or v3.2."
                  }
                },
                "required": [
                  "policy",
                  "version"
                ]
              }
            },
            {
              "name": "get_policy_effective_date",
              "description": "Get the date a policy version took effect. USE when the user asks when a policy started, was effective, or was updated. REQUIRED: `policy`; OPTIONAL: `version` (defaults to the policy's current version). Returns policy id, version, effective date, and status, or an error if the policy id or version does not exist.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "policy": {
                    "type": "string",
                    "description": "Policy id, e.g. remote_work_policy."
                  },
                  "version": {
                    "type": "string",
                    "description": "Optional version key; defaults to the current version."
                  }
                },
                "required": [
                  "policy"
                ]
              }
            },
            {
              "name": "get_policy_deprecation",
              "description": "Check whether a policy version is active, deprecated, or superseded, and which version replaced it. USE when the user asks whether a policy or version is still active, retired, replaced, or superseded. REQUIRED: `policy`; OPTIONAL: `version` (defaults to the current version). Returns status, deprecated_on, and superseded_by, or an error if the policy id or version does not exist.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "policy": {
                    "type": "string",
                    "description": "Policy id, e.g. remote_work_policy."
                  },
                  "version": {
                    "type": "string",
                    "description": "Optional version key; defaults to the current version."
                  }
                },
                "required": [
                  "policy"
                ]
              }
            },
            {
              "name": "get_policy_metadata",
              "description": "Get registry metadata for a policy: title, owner, category, applies_to, current version, full version history, and last reviewed date. USE for questions about policy ownership or administration, or which versions exist. Does NOT return the policy's prose content -- use search_handbook or get_policy_section for Handbook text. REQUIRED: `policy`. Returns metadata, or an error if the policy id does not exist.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "policy": {
                    "type": "string",
                    "description": "Policy id, e.g. code_of_conduct."
                  }
                },
                "required": [
                  "policy"
                ]
              }
            }
          ]
        }
      }
    }
  }
}
```

## Invocation evidence (Task 1)

Query run through the unchanged agent:

    "What is the effective date of the remote work policy?"

The model selected a tool that only server two provides; this is the
actual `tools/call` frame pair from the MCP traffic log (captured at
2026-10-01T12:04:57):

```json
{
  "ts": "2026-10-01T12:04:57",
  "request": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_policy_effective_date",
      "arguments": {
        "policy": "remote_work_policy"
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
          "text": "{\"policy\": \"remote_work_policy\", \"version\": \"v3.2\", \"effective_date\": \"2026-08-01\", \"status\": \"active\"}"
        }
      ]
    }
  }
}
```

Agent-side records for the same runs:

- `Agentic Ai/output/traces/tr_d1ca717aef3a.json` (first run) and
  `tr_f7c3f3e1d42c.json` (clean re-run, process exit 0) -- both show
  `[Tool] get_policy_effective_date({'policy': 'remote_work_policy'}) -> ok`
  and the final answer **August 1, 2026** for policy version v3.2.
