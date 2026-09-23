# Week 3 Practical -- Task Set E: results.md

**Domain:** Nimbus SDK developer documentation (synthetic corpus, see "Scope" below)
**App under test:** `rag-python` (existing Week 3 RAG app), extended in place -- `src/chunk_document.py` gained a second chunking method, everything else lives in the new `sdk_docs_task/` folder.

## 0. Scope (read this first)

Per the "time reality" instruction, **only the 6 new v3 reference pages were ingested**, plus 2 v2 pages that already existed on the docs site (`Client.send()` and `RateLimiter.configure()`), added specifically so the metadata-filter bug (Section 4) has a real v2/v3 collision to demonstrate. The whole docs site was **not** re-indexed. Corpus:

| sdk_version | page_id | source_file |
|---|---|---|
| v3 | client-send | v3/client-send.md |
| v3 | client-connect | v3/client-connect.md |
| v3 | webhooks-subscribe | v3/webhooks-subscribe.md |
| v3 | batch-uploader-upload | v3/batch-uploader-upload.md |
| v3 | auth-manager-refresh-token | v3/auth-manager-refresh-token.md |
| v3 | rate-limiter-configure | v3/rate-limiter-configure.md |
| v2 | client-send | v2/client-send.md |
| v2 | rate-limiter-configure | v2/rate-limiter-configure.md |

Every chunk from every page carries `source_file`, `page_id`, `sdk_version`, `page_type` (`reference` for all 8 pages here), plus `anchor` (section slug) and `chunking_method`. Ingestion (`sdk_docs_task/ingest.py`) raises if any chunk would land without a `source_file` -- there were none; see `ingest()`'s `missing_source` check.

The corpus content is synthetic (a fictional "Nimbus SDK") authored for this exercise, not scraped real docs -- this was a deliberate choice so every ground-truth answer is known exactly and independently of retrieval, and so that a genuine `retry_backoff_ms`-style version collision and a genuine cut-fence bug could be engineered deterministically rather than hoped for.

Two Chroma collections hold the same 8 pages: `sdk_docs_recursive` (existing chunker) and `sdk_docs_structure_aware` (new chunker). Same embedding model (`all-MiniLM-L6-v2`, reused from `create_embeddings.py`) for both -- only the chunking changed, per the "don't change two things at once" instruction.

---

## 1. The 8 known-answer questions

Written from the pages **before** any retrieval was run (see `sdk_docs_task/questions.py`, committed before `sdk_docs_task/eval_retrieval.py` was ever executed).

| ID | Question | Correct page / section | Known answer | Depends on |
|---|---|---|---|---|
| Q1 | What is the default value and type of `retry_backoff_ms` on `Client.send()`? | v3/client-send.md -- Parameters | `int`, default `250` (v2 default was `100` -- this is the version-collision question, reused for Section 4) | table row |
| Q2 | In the v3 `Client.send()` code example, what keyword argument is passed alongside `payload` to demonstrate retry configuration? | v3/client-send.md -- Example | `retry_backoff_ms=250` | code fence |
| Q3 | In `Client.connect()` v3, what type is `region` and is it required? | v3/client-connect.md -- Parameters | `str`, Required: Yes | table row |
| Q4 | What is the default `window_ms` in `RateLimiter.configure()` v3? | v3/rate-limiter-configure.md -- Parameters | `60000` | table row |
| Q5 | In the `Webhooks.subscribe()` v3 example, which HTTP header carries the HMAC signature on Nimbus's callback? | v3/webhooks-subscribe.md -- Parameters/Example | `X-Nimbus-Signature` | code fence |
| Q6 | What is the default `chunk_size_mb` for `BatchUploader.upload()` v3? | v3/batch-uploader-upload.md -- Parameters | `8` | table row |
| Q7 | What is the default `ttl_seconds` for `AuthManager.refresh_token()` v3, and what exception is raised on an expired token? | v3/auth-manager-refresh-token.md -- Parameters/Errors | `3600`; `TokenExpiredError` | table row |
| Q8 | Does `RateLimiter.configure()` v2 support a `burst` parameter? | v2/rate-limiter-configure.md -- Parameters | No -- `burst` was added in v3 | table row |

6 of 8 depend on a parameter-table row; 2 depend on a fenced code sample -- above the "at least 3" minimum.

---

## 2. Hit-in-top-5: two numbers, same 8 questions, per-question record

**Metric definition (important):** a "hit" requires the retrieved chunk to be from the correct `page_id` + `sdk_version` **and** to literally contain the fact the question depends on (its `expected_fragment`, e.g. `"| retry_backoff_ms | int | 250 | No |"`), whitespace-normalized. A chunk that merely touches the right page (e.g. the intro paragraph) without containing the actual fact does **not** count as a hit. This is stricter than a page-level match and is what actually answers the assignment's question ("does your chunker keep the value attached to the method").

| Question | recursive | structure_aware |
|---|---|---|
| Q1 | HIT | HIT |
| Q2 | HIT | **MISS** |
| Q3 | HIT | HIT |
| Q4 | HIT | HIT |
| Q5 | HIT | HIT |
| Q6 | HIT | HIT |
| Q7 | HIT | HIT |
| Q8 | HIT | HIT |
| **Score** | **8/8** | **7/8** |

Full search-only dump (all 8 questions x both strategies, top-5 chunk_ids/distances/snippets): [`output/search_dump.md`](output/search_dump.md) (rendered) / [`output/search_dump.json`](output/search_dump.json) (raw, includes full chunk text).

This result is deliberately reported as-is even though it is *not* the flattering direction -- see Section 6 for why the raw score is not the deciding factor.

Q2's structure_aware miss, explained: the atomic "Example" chunk for `v3/client-send.md` (the one containing `retry_backoff_ms=250,`) simply doesn't make the top 5 for that query. Its nearest competitors are the near-identical v2 `Example`/`Errors` chunks and the v3 intro chunk -- because structure-aware chunks are small and single-purpose, this one code example has to win purely on its own semantic weight against several close, related chunks, and it loses narrowly. Recursive's much larger chunks blend multiple sections together, so a query about "the code example" also drags in adjacent table/prose text that happens to score well even when the actual code isn't the best-matching span.

---

## 3. Metadata filter on `sdk_version`: one query, two result lists

**Query:** *"What is the default value and type of retry_backoff_ms on Client.send()?"* (this is Q1, run against the `recursive` collection since that's where the version collision is sharpest).

**Unfiltered top-1 is the stale v2 page** -- exactly the bug the assignment describes.

| Rank | Unfiltered (no filter) | | | Filtered (`where={"sdk_version": "v3"}`) | | |
|---|---|---|---|---|---|---|
| | chunk_id | dist | source | chunk_id | dist | source |
| 1 | `v2__client-send__recursive__0` | 0.8343 | v2/client-send.md | `v3__client-send__recursive__2` | 0.8779 | v3/client-send.md |
| 2 | `v2__client-send__recursive__1` | 0.8408 | v2/client-send.md | `v3__client-send__recursive__1` | 1.0037 | v3/client-send.md |
| 3 | `v3__client-send__recursive__2` | 0.8779 | v3/client-send.md | `v3__auth-manager-refresh-token__recursive__1` | 1.1360 | v3/auth-manager-refresh-token.md |
| 4 | `v3__client-send__recursive__1` | 1.0037 | v3/client-send.md | `v3__client-connect__recursive__0` | 1.1653 | v3/client-connect.md |
| 5 | `v3__auth-manager-refresh-token__recursive__1` | 1.1360 | v3/auth-manager-refresh-token.md | `v3__client-connect__recursive__1` | 1.1881 | v3/client-connect.md |

**Top-1 changes:** `v2__client-send__recursive__0` -> `v3__client-send__recursive__2`. `top1_changed = True`.

Full raw output: [`output/filter_demo.json`](output/filter_demo.json).

Caveat worth being honest about: the filter fixes the *version* bug but does not fix the *chunking* bug -- the corrected top-1 chunk (`v3__client-send__recursive__2`) is itself the corrupted chunk from Section 6 (the one missing its table header). Filtering and chunking are separate failure modes; fixing one doesn't fix the other.

---

## 4. Three cited answers (generation, structure_aware collection, top_k=5)

Grounding prompt (full text in `sdk_docs_task/generate.py`, `SYSTEM_PROMPT`) forces a citation in `[chunk_id]` form per claim and forces an exact refusal string when the context doesn't specifically support the answer -- it does **not** say "use your best judgement" anywhere, per the stated failure mode to avoid.

**Q3** -- *In `Client.connect()` v3, what type is the `region` parameter and is it required?*
> The `region` parameter is a **string** (`str`) and it is **required** when calling `Client.connect()` in v3. [v3__client-connect__structure_aware__1]

Citation resolves: `v3__client-connect__structure_aware__1` -> `v3/client-connect.md`, anchor `parameters`. Chunk content includes `| region | str | n/a | Yes |` -- claim verified against the actual stored chunk.

**Q6** -- *What is the default `chunk_size_mb` for `BatchUploader.upload()` v3?*
> The default value for `chunk_size_mb` is **8 MB**. [chunk_id=v3__batch-uploader-upload__structure_aware__1]

Citation resolves: `v3__batch-uploader-upload__structure_aware__1` -> `v3/batch-uploader-upload.md`, anchor `parameters`. Chunk contains `| chunk_size_mb | int | 8 | No |`.

**Q7** -- *What is the default `ttl_seconds` for `AuthManager.refresh_token()` v3, and what exception is raised when the refresh token has expired?*
> The default `ttl_seconds` is **3600** [v3__auth-manager-refresh-token__structure_aware__1].
> When the refresh token has expired, `TokenExpiredError` is raised [v3__auth-manager-refresh-token__structure_aware__3].

Two citations, two different chunks, both resolve: `...__1` -> `parameters` anchor (`| ttl_seconds | int | 3600 | No |`), `...__3` -> `errors` anchor (`raises TokenExpiredError`). This is the multi-claim/multi-citation case working correctly -- each claim points at the specific chunk that actually backs it, not one blanket citation for the whole answer.

Full raw output incl. retrieved chunk_ids per question: [`output/generation_dump.json`](output/generation_dump.json).

---

## 5. Three refusal transcripts (out-of-corpus, forced, verbatim)

**R1** -- *What is the rate limit (requests per minute) for the /v3/analytics/export endpoint?*
> NOT_IN_CORPUS: This is not documented in the provided SDK reference pages.

(First attempt at this prompt version actually failed here -- see Section 6, second embarrassment, for the honest diagnosis and fix.)

**R2** -- *What error code does Client.send() return when the connection pool is exhausted?*
> NOT_IN_CORPUS: This is not documented in the provided SDK reference pages.

**R3** -- *Does Nimbus SDK v3 support WebSocket streaming for real-time message delivery?*
> NOT_IN_CORPUS: This is not documented in the provided SDK reference pages.

All 3 use the exact same literal refusal string (`REFUSAL_TEXT` in `generate.py`), byte-for-byte, not a paraphrase -- checked programmatically (`correctly_refused` field in the dump), not eyeballed.

---

## 6. Two things that embarrassed us

**#1 -- recursive chunker splits a table row in half, and ranks the wrong SDK version first.** For the flagship `retry_backoff_ms` question against the `recursive` collection: unfiltered top-1 is the **v2** page (Section 3), and the v3 chunk that eventually surfaces (`v3__client-send__recursive__2`) starts mid-row:

```
/a | Yes | | retry_backoff_ms | int | 250 | No | | timeout_ms | int | 5000 | No | ...
```

That `/a | Yes |` fragment is the tail end of the `payload` row (`| payload | dict | n/a | Yes |`) -- the recursive chunker's 900-character greedy accumulation cut *inside a table cell*, between chunks `v3__client-send__recursive__1` and `...__2`. A chunk that starts with an orphaned table-row fragment and no header row anywhere in it is a real, reproducible instance of exactly the bug the assignment named up front. Diagnosed by actually running `recursive_chunk_text` against the drafted pages and inspecting chunk boundaries (`sdk_docs_task/diagnose_chunks.py`) -- not eyeballed after the fact. The same script also caught a fenced code block split mid-block in `v2/client-send.md` and `v3/batch-uploader-upload.md` (odd `` ``` `` count per chunk).

**#2 -- the first refusal prompt did not force refusal; it suggested it, and R1 slipped through.** The first version of `SYSTEM_PROMPT` said only "if the context does not fully support an answer... refuse." Under that prompt, R1 ("rate limit for the /v3/analytics/export endpoint") did **not** refuse -- it answered:

> 100 requests per minute [v3__rate-limiter-configure__structure_aware__1]

That's the SDK's general client-side `RateLimiter.configure()` default, not the (nonexistent) rate limit for a specific HTTP endpoint. The model treated "this chunk mentions rate limits" as license to answer a differently-scoped question -- a topically-adjacent chunk was accepted as support for a claim it doesn't actually make. This is the exact failure mode the assignment warns about ("a plausible, non-existent parameter ends up in someone's production code"), just one level removed (a plausible-but-wrong number instead of a fabricated parameter name). Fix: rule 3 was added to the prompt, explicit about this exact confusion ("a general client-side setting is NOT evidence for a question about a specific, different thing... even if both involve the same keyword"). Re-run: R1 refuses correctly (Section 5). This is reported as a before/after, not smoothed over, because it's the actual finding -- the first prompt "suggested" refusal and failed on the first real test of it.

---

## 7. Which chunker ships, and why

**Structure-aware ships**, despite scoring **7/8 vs recursive's 8/8** on raw hit-in-top-5 (Section 2). The raw number favors recursive, and reporting it any other way would be dishonest -- but hit-in-top-5 only measures whether *a* correct chunk is retrievable, not whether the chunk you get back is trustworthy. Recursive's failures in this corpus are **content-corruption failures**: a table row torn across a chunk boundary mid-cell, a code fence split so its closing backticks land in a different chunk than its opening line (Section 6, #1). Those chunks are wrong in a way that survives no matter how retrieval or reranking improves later -- the source text stored in the vector DB is itself malformed. Structure-aware's failure mode (Q2's Example chunk narrowly missing top-5, Section 2) is a *ranking* problem: the chunk is intact and correct, it's just occasionally outranked by close semantic neighbors. Ranking problems are fixable downstream (widen `k`, add a reranker, tune the query); corrupted-chunk problems are not fixable without re-chunking. Given this is explicitly framed as ingesting more pages over time (a "v3 release just landed," more will follow), a chunker that never corrupts a table row or a code fence is the safer property to hold going into a full re-index, even at a one-point cost on this small 8-page/8-question sample. The bonus section below documents the real cost of that choice too -- structure-aware isn't free.

---

## 8. Bonus: precision-wins, completeness-loses

**Question:** *"What is the default chunk_size_mb for BatchUploader.upload(), and how is it passed in the example code?"* -- run at `top_k=3` against both collections.

Retrieval precision favors structure_aware: its top-1 chunk (`v3__batch-uploader-upload__structure_aware__1`, distance 0.912) is a tighter semantic match than recursive's best (`v3__batch-uploader-upload__recursive__0`, distance 0.973) -- confirmed in `sdk_docs_task/generate.py::run_bonus`. But none of structure_aware's top-3 chunks contain a code fence at all (Parameters, intro, Errors -- all prose/table, no `` ``` ``); recursive's top-3 includes two chunks that do contain the fenced example, because its loose section-blending happened to carry the code sample along with the table.

**recursive's answer:**
> The default value for `chunk_size_mb` is **8 MB** [chunk_id=v3__batch-uploader-upload__recursive__1]. In the example code it is passed explicitly as `chunk_size_mb=8` [chunk_id=v3__batch-uploader-upload__recursive__1].

**structure_aware's answer:**
> NOT_IN_CORPUS: This is not documented in the provided SDK reference pages.

Structure-aware's forced-refusal prompt (Section 4/5) treats "no code sample in context" as "the question isn't fully supported" and correctly refuses rather than inventing a code line -- which is the right call given the grounding rule, but it means the user gets nothing instead of a partial answer. Two sentences on the tension: a chunker precise enough to isolate exactly one fact per chunk also isolates that fact away from the other facts (like "how do I actually call this") a real question usually wants together, so a strict per-claim grounding policy converts that precision into an outright refusal instead of a partial answer. The fix isn't to loosen the chunker back into recursive's blending -- it's to retrieve more broadly (higher `k`, or explicitly also fetch the sibling `Example` chunk for whatever page's `Parameters` chunk wins) while keeping the chunks themselves clean.

---

## 9. Code diff

`src/chunk_document.py` gained `structure_aware_chunk_markdown()` (plus its `_split_into_sections` / `_blocks_from_lines` / `_pack_blocks` helpers) and a `"structure_aware"` entry in `CHUNKING_METHODS` / `chunk_text()`. Nothing existing was changed or removed -- the original `recursive`/`fixed_character` paths are untouched. Full unified diff: [`output/chunk_document.diff`](output/chunk_document.diff).

New metadata fields (`source_file`, `page_id`, `sdk_version`, `page_type`, plus `anchor`/`chunking_method`) are attached in `sdk_docs_task/ingest.py` (new file -- the existing `src/vector_store.py` used by the PDF-upload app was left alone since it serves a different, single-PDF flow; this task's ingestion is page-based, not PDF-based).

---

## 10. Submission checklist

- [x] `results.md` with all 8 questions and known-correct page + section (Section 1)
- [x] Two hit-in-top-5 numbers in one table -- recursive 8/8, structure_aware 7/8 (Section 2)
- [x] Unfiltered vs filtered result lists for one sdk_version query, with scores (Section 3)
- [x] 3 cited answers + 3 refusal transcripts pasted verbatim (Sections 4, 5)
- [x] Code diff showing the second chunker and the metadata fields (Section 9)
- [x] One paragraph: which chunker ships, and why (Section 7)
- [x] Bonus: precision-vs-completeness side-by-side (Section 8)
