# Week 5 — Trace Failure Taxonomy

| Rank | Failure Mode | Count | Frequency | Severity | Example Trace |
|------|--------------|-------|-----------|----------|---------------|
| 1 | Version collision: v3 chunks outrank v2 for v2-specific questions when defaults differ | 3 | 15% | High | search_rec_Q8 |
| 2 | Version collision: v2 chunks outrank v3 for v3-specific questions when defaults differ | 2 | 10% | High | search_sa_Q1 |
| 3 | Version collision: wrong SDK version retrieved but both versions share the same default value | 3 | 15% | Lower | search_rec_Q4 |
| 4 | Wrong page section retrieved (intro/errors instead of parameters) | 2 | 10% | Lower | search_sa_Q7 |

**Summary**: 10 out of 20 traces (50%) exhibit at least one failure mode. The dominant pattern is version collision, where the dense retrieval pipeline cannot distinguish between v2 and v3 documentation for the same API surface. When the two versions have different default values (ranks 1-2), this causes materially incorrect answers. When defaults are the same (rank 3), the failure is benign but indicates the same underlying retrieval weakness. Wrong section retrieval (rank 4) is a secondary issue where the correct page is found but the wrong subsection is ranked highest.
