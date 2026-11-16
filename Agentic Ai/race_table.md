# Week 10 HR Handbook Race

The exact existing `race_questions.json` file was used unchanged. It is the
repo's Week 7 HR set; no separate Week 6 HR evaluation file exists here.
Cases: Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10. SHA-256 of source set: `f8318c3f20221dbedb118b5c3a0eaeac00210af0ed28e99fe36477a47e551d50`.

Latency percentiles use nearest rank (for 10 cases, p99 is the maximum).

| Metric | Single agent | HR specialist orchestrator |
|---|---:|---:|
| Pass rate | 9/10 (90%) | 9/10 (90%) |
| Latency p50 / p99 | 34586.9 / 89586.0 ms | 41699.2 / 139488.5 ms |
| Total tokens | 58,729 | 71,533 |
| Cost per question | $0.000557 | $0.000825 |

Totals: single-agent $0.005573; orchestrator $0.008249.
