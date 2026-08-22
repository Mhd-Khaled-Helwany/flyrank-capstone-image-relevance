# List of evidence for §6 in the capstone pdf

This document is for the capstone reviewers of the internship to make it easier for them to verify my work.

## AI processing

1. Vision model produces structured output validated against a schema; invalid responses are never trusted
Evidence:

**(a) Real vision-model output is structured JSON** — every tagged image has a validated tag file under `data/tags/`, e.g. `data/tags/bamboo.json`:

```json
{
  "subject": "bamboo",
  "category": "plant",
  "attributes": ["green stalks", "segmented stems", "dense grove", "vertical culms", "natural lighting"],
  "caption": "A dense grove of tall green bamboo stalks standing vertically in natural light.",
  "confidence": 1.0
}
```

**(b) The schema is enforced by Pydantic** — `src/vision/schema.py`: `TagSchema` uses closed enums (`Category`, 7 values; `Subject`, 50 values), `confidence: confloat(ge=0.0, le=1.0)` and `"extra": "forbid"`. `validate_tag_payload()` (`src/vision/schema.py:83-88`) returns `(None, errors)` instead of raising, so callers can discard bad payloads.

Valid file validates clean:

```
$ py scripts/validate_sample.py
```

output:
```
{'valid': True, 'tag': {'subject': <Subject.red_fox: 'red fox'>, 'category': <Category.animal: 'animal'>, 'attributes': ['orange fur', 'wild', 'forest'], 'caption': 'A red fox standing in a forest', 'confidence': 0.94}}
```


**(c) Invalid responses are rejected, never trusted** — the schema rejects unknown categories, subjects outside the closed 50-value enum, out-of-range confidence and missing fields:

```
$ py evidence/invalid_tag_rejected.py
```
output:

```
[REJECTED] unknown category: 2 schema error(s)
    - category: Input should be 'animal', 'plant', 'vehicle', 'clothing', 'furniture', 'beverage' or 'electronic device'
    - confidence: Input should be less than or equal to 1
[REJECTED] subject outside closed enum: 1 schema error(s)
    - subject: Input should be 'bamboo', 'bed', ... or 'wolf'
[REJECTED] missing required field: 1 schema error(s)
    - confidence: Field required
```

In the batch job (`scripts/run_batch_tagging.py`, `real_worker`) a payload failing `validate_tag_payload` raises before `persist_tag()` is ever called, so an invalid model response is **never written to disk or DB**; `process_batch` classifies validation failures as non-retryable (`src/vision/processor.py:25-36` markers `validation`/`invalid`/`malformed`) and routes them to the failed list.

Automated coverage: `tests/test_vision_schema.py::test_valid_payload_passes` and `::test_invalid_payload_fails_cleanly` (both green, see Quality section for full-suite output).

2. Low-confidence classifications are flagged instead of accepted
Evidence:

**Flagging mechanism (three places):**
- `TagSchema.needs_review(threshold=0.75)` — `src/vision/schema.py:80-81`
- Stored on ingest: `needs_review = confidence < 0.75` in `image_metadata` (`src/matching/repository.py::upsert_image_metadata`)
- Enforced at matching time: the guard rejects any candidate below threshold with reason `"Tag confidence too low to trust"` (`src/matching/guard.py:71-72`)

```
$ /py evidence/confidence_scan.py
```

output:

```
tag files: 50 | min confidence: 0.3 | max: 1.0 | flagged (<0.75): 1
image_metadata rows with needs_review=1: 1
    - basketball.jpg: confidence=0.3
```

3. Images are processed through a batch background job with retries
Evidence:

**Batch + retry implementation** — `src/vision/processor.py`:
- `process_batch(items, worker, max_retries=3, ...)` (lines 83-171) iterates the manifest, retries only transient failures, and returns `{results, failed, attempts}` per item
- `should_retry_error()` (lines 38-57) retries 429/5xx/timeouts/connection errors; policy/safety refusals and validation errors are **not** retried
- `compute_retry_delay()` (lines 59-81) uses exponential backoff with jitter

Wired into the job: `scripts/run_batch_tagging.py` line 229 — `process_batch(batch, worker, max_retries=2, ...)`.

**(a) Live demo** — a flaky API (two timeouts, then success) is retried until it works; a policy refusal is attempted exactly once and routed to failed:

```
$ py evidence/retry_demo.py
```

output:

```
succeeded: ['tag-ok: img_flaky.jpg']
attempts:  {'img_flaky.jpg': 3, 'img_refused.jpg': 1}
failed:    ['img_refused.jpg']
```

**(b) Automated coverage:**

`test_process_batch_retries_transient_failures_but_not_refusals` proves both directions: a timeouting item is retried (`attempts["bravo"] == 2`) and succeeds, while a policy refusal is given up on immediately (`attempts["charlie"] == 1`).

4. Vision and embedding costs are tracked per call
Evidence:

**Per-call cost computation from the real API response** — `src/vision/gemini_client.py:56-64` reads `usage_metadata` (prompt/completion token counts) from every Gemini response and computes cost with production rates (`$0.000075/1k input`, `$0.0003/1k output`). Embedding calls do the same with their rates (`scripts/seed_embeddings.py`, `EMBEDDING_COST_PER_1K_INPUT`).

**Every call is recorded as one structured record** — `summarize_call_metrics()` (`src/vision/processor.py:173-214`) validates and computes `cost_usd`; `record_call()` (`src/telemetry/call_logger.py:18-25`) stores it and emits one log line per AI call. Real batch runs print exactly this per image/embedding:

```
2026-08-22 14:28:49 INFO AI call: {'call_type': 'vision', 'status': 'success', 'image_id': 1, 'model_name': 'gemini-flash-latest', 'input_tokens': 152, 'output_tokens': 38, 'total_tokens': 190, 'duration_ms': 900, 'retry_count': 0, 'cost_usd': 2.28e-05}
2026-08-22 14:28:49 INFO AI call: {'call_type': 'vision', 'status': 'success', 'image_id': 2, 'model_name': 'gemini-flash-latest', 'input_tokens': 131, 'output_tokens': 25, 'total_tokens': 156, 'duration_ms': 900, 'retry_count': 0, 'cost_usd': 1.7325e-05}
{1: {'cost_usd': 2.28e-05, 'calls': 1, 'total_tokens': 190, 'duration_ms': 900}, 2: {'cost_usd': 1.7325e-05, 'calls': 1, 'total_tokens': 156, 'duration_ms': 900}}
```

Reproduce the recording + aggregation mechanism with:

```
$ py evidence/cost_tracking_demo.py
```

output:
```

--- per-call records ---
image 1: tokens=190 cost=$0.0000228000
image 2: tokens=156 cost=$0.0000173250
--- aggregation ---
{1: {'cost_usd': 2.28e-05, 'calls': 1, 'total_tokens': 190, 'duration_ms': 900}, 2: {'cost_usd': 1.7325e-05, 'calls': 1, 'total_tokens': 156, 'duration_ms': 900}}
```

Automated coverage: `tests/test_batch_processing.py::test_cost_tracking_summarizes_call_metrics_and_cost` asserts the exact cost math `(120 * 0.000075 + 40 * 0.0003) / 1000` and rejects negative token counts.

*Note:* tracking is per-process runtime (log line + in-memory buffer); the `ai_call_log` table exists for durable persistence.

## Matching system

1. Image and post embeddings are stored; posts return ranked image suggestions
Evidence:

2. Semantic matching works for equivalent concepts — "red fox" matches "Vulpes vulpes"
Evidence:

## Safety layer

1. The mismatch guard rejects incorrect recommendations — the wolf-on-a-fox-post scenario provably fails
Evidence:

2. Rejections include a human-readable explanation
Evidence:

3. When no image clears the bar, the system answers "no confident match" with reasons
Evidence:

## Backend 

1. Database models for images, tags, embeddings, posts, suggestions, approvals/rejections — with the required indexes
Evidence:

2. API endpoints validated; the review workflow (approve / reject / inspect why) exists
Evidence:

## Quality and documentation

1. Automated tests cover schema validation, mismatch rejection, and matching accuracy
Evidence:

2. A small labeled evaluation dataset measures top-1 precision — the number is in your README
Evidence:

3. README with architecture explanation and diagram; submission-pack files from § 11 present
Evidence: