# Integrated eval summary (n=30)

**Pass rate: 25/30 (83%)** (assertions only; judge is advisory)

| Mode | n | passed | pass rate |
|---|---:|---:|---:|
| group_scope | 6 | 5 | 83% |
| group_split_rule | 2 | 2 | 100% |
| group_unresolved | 2 | 2 | 100% |
| lookup | 10 | 7 | 70% |
| multi_step | 2 | 2 | 100% |
| not_covered | 4 | 3 | 75% |
| pii | 1 | 1 | 100% |
| revision_history | 3 | 3 | 100% |

| Metric | Value |
|---|---:|
| Cost per question (mean / total) | $0.000412 / $0.0124 |
| Tokens per question (mean / max) | 4277 / 8782 |
| Latency incl. 429 waits p50 / p95 | 2.8s / 58.2s |
| Model-call time only p50 / p95 | 2.1s / 30.4s |
| Total 429 wait | 446s |
| Answers with ungrounded figures | 3/26 |
| Terminated early (budget) | 2/30 |
| Judge 'supported' | 21/30 |

## Failed cases

| Case | Trace | Failed assertions |
|---|---|---|
| G04-tech-hours | tr_9bd3bc5491b0 | ungrounded:['9.5'] |
| L01-hr-contact | tr_600dcb0bfb00 | terminated:ERROR:APIStatusError; missing:sudhendra |
| L05-dress-code | tr_b603382b8a5a | ungrounded:['17', '19'] |
| L08-pf-timing | tr_4df587dcff84 | ungrounded:['75'] |
| N02-gratuity | tr_9adedf123c0f | terminated:MAX_WALL_CLOCK_EXCEEDED; says_not_covered |
