# Cost by stage — failed HR handbook query

Based on the captured request: 742 input tokens + 159 output tokens, using the configured GPT-OSS-20B rates ($0.075/M input, $0.30/M output).

| Stage | Cost/query | Evidence |
|---|---:|---|
| Retrieval | $0.00000000 | Local hybrid retrieval; no provider token charge. Retrieval duration was not separately logged. |
| Generation | $0.00010335 | 742 × $0.075/M + 159 × $0.30/M. |
| Tools | $0.00000000 | No tool calls in this normal_workflow request. |
| **Total** | **$0.00010335** | Matches the captured trace. |
