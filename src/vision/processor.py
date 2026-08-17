from __future__ import annotations
import json
import random
import time
from typing import Any, Callable, Iterable
from .schema import TagSchema, validate_tag_payload

_RETRYABLE_ERROR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "connection",
    "connect",
    "timeout",
    "temporar",
    "rate limit",
    "too many requests",
    "unavailable",
    "reset by peer",
    "service unavailable",
)

_NON_RETRYABLE_ERROR_MARKERS = (
    "refused",
    "policy",
    "safety",
    "denied",
    "forbidden",
    "not allowed",
    "validation",
    "invalid",
    "malformed",
    "reject",
)

def should_retry_error(error: BaseException | Exception) -> bool:
    """Return whether the error is transient enough for a retry."""
    if error is None:
        return False

    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return True

    message = str(error).lower()
    if any(marker in message for marker in _NON_RETRYABLE_ERROR_MARKERS):
        return False

    if any(marker in message for marker in _RETRYABLE_ERROR_MARKERS):
        return True

    return False

def compute_retry_delay(
    attempt: int,
    *,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: float = 0.75,
    rng: random.Random | None = None,
) -> float:
    """Use exponential backoff with jitter to avoid retry storms."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")

    if base_delay < 0:
        raise ValueError("base_delay must be >= 0")

    if max_delay < 0:
        raise ValueError("max_delay must be >= 0")

    random_source = rng or random.Random()
    exponential_wait = base_delay * (2**attempt)
    jitter_multiplier = 1.0 + random_source.uniform(0.0, jitter)
    backoff = min(max_delay, exponential_wait * jitter_multiplier)
    return max(0.0, backoff)

def process_batch(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: float = 0.75,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Process a batch of items while retrying only transient failures."""
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    results: list[Any] = []
    failed: list[tuple[Any, Exception]] = []
    attempts: dict[Any, int] = {}
    random_source = rng or random.Random()

    for item in items:
        try_count = 0
        while True:
            try:
                result = worker(item)
                attempts[item] = try_count + 1
                results.append(result)
                break
            except Exception as exc:  # pragma: no cover - exercised via tests
                if not should_retry_error(exc) or try_count >= max_retries:
                    failed.append((item, exc))
                    attempts[item] = try_count + 1
                    break

                retry_delay = compute_retry_delay(
                    try_count,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    jitter=jitter,
                    rng=random_source,
                )
                time.sleep(retry_delay)
                try_count += 1

    return {"results": results, "failed": failed, "attempts": attempts}

def summarize_call_metrics(
    *,
    call_type: str,
    status: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_ms: int = 0,
    image_id: int | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    base_cost_per_1k_input: float = 0.0,
    base_cost_per_1k_output: float = 0.0,
    retry_count: int = 0,
) -> dict[str, Any]:
    """Summarize metadata for one AI call, including prompt/completion tokens and cost."""
    if call_type not in {"vision", "embedding"}:
        raise ValueError("call_type must be 'vision' or 'embedding'")
    if status not in {"success", "retry", "failed"}:
        raise ValueError("status must be 'success', 'retry', or 'failed'")
    if input_tokens < 0 or output_tokens < 0 or duration_ms < 0:
        raise ValueError("tokens and duration_ms must be non-negative")
    if retry_count < 0:
        raise ValueError("retry_count must be non-negative")

    total_tokens = int(input_tokens) + int(output_tokens)
    input_cost = (float(input_tokens) * float(base_cost_per_1k_input)) / 1000.0
    output_cost = (float(output_tokens) * float(base_cost_per_1k_output)) / 1000.0
    total_cost = round(input_cost + output_cost, 12)

    return {
        "call_type": call_type,
        "status": status,
        "image_id": image_id,
        "model_name": model_name,
        "model_version": model_version,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": total_tokens,
        "duration_ms": int(duration_ms),
        "retry_count": int(retry_count),
        "cost_usd": total_cost,
    }

def validate_raw_response(raw: dict) -> dict:
    tag, errors = validate_tag_payload(raw)
    if tag is not None:
        return {"valid": True, "tag": tag.model_dump()}
    return {"valid": False, "errors": errors, "raw_response": raw}

def validate_from_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return validate_raw_response(raw)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a sample vision model JSON")
    parser.add_argument("json_file", help="Path to JSON file to validate")
    args = parser.parse_args()
    result = validate_from_json_file(args.json_file)
    print(json.dumps(result, indent=2))

__all__ = [
    "compute_retry_delay",
    "process_batch",
    "should_retry_error",
    "summarize_call_metrics",
    "validate_from_json_file",
    "validate_raw_response",
]
