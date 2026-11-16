# Cost per query by stage (leave-policy request, trace `tr_5e0d17a94c3b`)

Model `openai/gpt-oss-20b`, $0.075/M input and $0.30/M output tokens (`cost.py`). Spans are copied from real trace `tr_91795918c2d0`.

| Stage | Cost/query | Latency | Tokens | Evidence |
|---|---:|---:|---:|---|
| Retrieval | $0.00000000 | 0.615 s | 0 | Local hybrid retrieval and reranker; no provider charge |
| Generation | $0.00012015 | 0.758 s | 822 in / 195 out | 822 x $0.075/M + 195 x $0.30/M |
| Tools | $0.00000000 | 0 s | 0 | No tool calls in the normal workflow |
| **Total** | **$0.00012015** | **1.372 s** | **1,017** | Matches `trace.json` |

All of the money is generation; most of the latency is split between retrieval and generation.

Across the 15 live HR queries I ran this session: mean cost $0.000145/query (max $0.000269), mean 1,095 tokens/query (815 in, 281 out), mean latency 2.67 s (retrieval 0.63 s, generation 2.04 s, slowest generation 7.7 s).
