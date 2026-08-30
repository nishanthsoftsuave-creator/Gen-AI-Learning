# Week 5 — Trace Error Analysis Notes

## 1. Sampling

```text
Sampling method: deterministic random sampling
Seed: 20260830
Population: 46
Sample size: 20
```

Population breakdown:
- generation_dump: 6 traces (3 answerable, 3 refusals)
- search_dump_recursive: 8 traces
- search_dump_structure_aware: 8 traces
- week4_baseline: 12 traces
- week4_after: 12 traces

Selected trace IDs (in deterministic order):

1. gen_Q6
2. gen_Q7
3. gen_R1
4. gen_R2
5. search_rec_Q1
6. search_rec_Q4
7. search_rec_Q6
8. search_rec_Q8
9. search_sa_Q1
10. search_sa_Q4
11. search_sa_Q5
12. search_sa_Q7
13. search_sa_Q8
14. w4b_06
15. w4b_08
16. w4b_10
17. w4a_01
18. w4a_03
19. w4a_04
20. w4a_07

## 2. Open coding

1. gen_Q6 — The generated answer correctly states the default chunk_size_mb is 8 MB, matching the known answer, and the parameters chunk is ranked 1st in retrieved chunks.
2. gen_Q7 — The generated answer correctly states ttl_seconds is 3600 and the exception is TokenExpiredError, with the parameters chunk ranked 4th and the errors chunk ranked 2nd in retrieved chunks.
3. gen_R1 — The system retrieves rate-limiter-configure chunks for a question about an analytics/export endpoint and correctly returns NOT_IN_CORPUS.
4. gen_R2 — The system retrieves client-send chunks for a question about connection pool exhaustion and correctly returns NOT_IN_CORPUS.
5. search_rec_Q1 — The top 2 retrieved chunks are from v2 Client.send() showing retry_backoff_ms default of 100, while the v3 chunks showing default of 250 are ranked 3rd and 4th.
6. search_rec_Q4 — The top 2 retrieved chunks are from v2 RateLimiter.configure() showing window_ms=60000, while the v3 chunk showing the same value is ranked 3rd.
7. search_rec_Q6 — The top 3 retrieved chunks are all from v3 BatchUploader.upload(), with the parameters chunk containing chunk_size_mb=8 ranked 3rd.
8. search_rec_Q8 — The top 2 retrieved chunks are from v3 RateLimiter.configure() which documents a burst parameter, while the v2 chunks which lack burst are ranked 3rd and 4th.
9. search_sa_Q1 — The top retrieved chunk is from v2 Client.send() showing retry_backoff_ms default of 100, while the v3 chunk showing default of 250 is ranked 5th.
10. search_sa_Q4 — The top retrieved chunk is from v2 RateLimiter.configure() showing window_ms=60000, while the v3 chunk showing the same value is ranked 3rd.
11. search_sa_Q5 — The top 4 retrieved chunks are all from v3 Webhooks.subscribe(), with the chunk containing X-Nimbus-Signature ranked 1st.
12. search_sa_Q7 — The top 4 retrieved chunks are all from v3 AuthManager.refresh_token(), with the intro chunk ranked 1st and the parameters chunk containing ttl_seconds=3600 ranked 4th.
13. search_sa_Q8 — The top 3 retrieved chunks are from v3 RateLimiter.configure() which documents a burst parameter, while the v2 chunks which lack burst are ranked 4th and 5th.
14. w4b_06 — The dense-only baseline retrieves the correct v3 BatchUploader.upload() parameters chunk as the top result.
15. w4b_08 — The dense-only baseline retrieves only v3 RateLimiter.configure() chunks for a question about v2, missing the v2 chunk entirely.
16. w4b_10 — The dense-only baseline retrieves v2 RateLimiter.configure() chunks and a v3 errors chunk, but not the v3 parameters chunk containing max_requests=100.
17. w4a_01 — The RRF+fused retrieval correctly retrieves the v3 Client.send() parameters chunk as the top result.
18. w4a_03 — The RRF+fused retrieval retrieves the v3 Client.connect() parameters chunk as the 3rd result out of 3.
19. w4a_04 — The RRF+fused retrieval retrieves v2 RateLimiter.configure() chunks and a v3 intro chunk, but not the v3 parameters chunk containing window_ms=60000.
20. w4a_07 — The RRF+fused retrieval retrieves the v3 AuthManager.refresh_token() parameters chunk as the 3rd result out of 3.

## 3. Code-change guardrail

```text
Code changes during trace analysis: 0
```

## 4. Replay evidence

```text
Replay seed: 20260830
Replay trace_id: gen_Q6
```

The trace gen_Q6 asks: "What is the default `chunk_size_mb` for `BatchUploader.upload()` v3?"

The trace records the following retrieved chunks:
- v3__batch-uploader-upload__structure_aware__1 (parameters section)
- v3__batch-uploader-upload__structure_aware__0 (intro)
- v3__batch-uploader-upload__structure_aware__3 (errors)
- v3__batch-uploader-upload__structure_aware__2 (example)
- v3__rate-limiter-configure__structure_aware__2 (unrelated)

The original answer was:
"The default value for `chunk_size_mb` is **8 MB**. [chunk_id=v3__batch-uploader-upload__structure_aware__1]"

To replay, I would need to:
1. Reconstruct the prompt using the retrieved chunk content and the question
2. Send the same prompt to the same model with the same temperature
3. Compare outputs

```text
Replay limitation:
The trace does not contain the exact prompt template, the model name used at runtime (only GROQ_MODEL env var default "openai/gpt-oss-20b"), or the temperature parameter (hardcoded as 0.3 in rag.py). While the prompt template can be inferred from the source code, the exact model and temperature cannot be confirmed from the trace alone.

Missing field: prompt template (can be inferred from code but not from trace)
Missing field: model name (GROQ_MODEL env var, default "openai/gpt-oss-20b")
Missing field: temperature (hardcoded 0.3 in code)
Impact: Exact generation cannot be reconstructed from trace alone; replay would require running the full pipeline.
```

```text
ORIGINAL OUTPUT
----------------
The default value for `chunk_size_mb` is **8 MB**. [chunk_id=v3__batch-uploader-upload__structure_aware__1]


REPLAYED OUTPUT
---------------
Cannot replay: the trace lacks prompt template, model name, and temperature fields needed to reconstruct the generation. The model (GROQ) is also inherently nondeterministic at temperature=0.3.

Replay result: FAILED

Replay limitation:
The trace does not contain the prompt template, model name, or temperature. While the prompt template can be inferred from src/rag.py and the model defaults to "openai/gpt-oss-20b" with temperature=0.3, the exact prompt construction at runtime cannot be confirmed from the trace alone. Additionally, the Groq API with temperature=0.3 is nondeterministic, so even with identical inputs the output text may differ.
```

## 5. Dated prediction

```text
Date: 2026-08-30

Mode being attacked:
Version collision: dense retrieval returns wrong SDK version when defaults differ

Specific change:
Add SDK version metadata filter to the retrieval query so that only chunks matching the requested version are returned, or add the SDK version explicitly to the user question before embedding.

Current frequency:
25% (5 out of 20 traces)

Prediction:
After the change, this failure mode will decrease from 25% to 5%.
```

## 6. Public benchmark explanation

A public benchmark would not have surfaced the top 3 failure modes because public benchmark questions typically test a single API version in isolation and do not include the same multi-version documentation conflict that exists in this corpus where v2 and v3 pages describe the same API methods with different defaults. Benchmark datasets may also use curated question sets that avoid version-specific phrasing, and their scoring metrics (e.g., exact-match or ROUGE) would judge final-answer correctness without exposing the specific operational failure pattern where the retrieval pipeline returns the wrong version's documentation as the top result.
