At 10x volume the **rate limit** breaks first: 10 queries/min x 1,095 mean tokens = **10,950 tokens/min against the 8,000 TPM account limit** (ceiling about 7.3 queries/min), while cost stays about $2.09/day and mean latency 2.67 s.

Basis: today's volume is not logged, so I assumed a 1 query/min baseline. The limit is real: my 16-question run got a Groq 429 ("Limit 8000, Used 6742, Requested 1412"). Mean tokens/query come from 15 live traces.
