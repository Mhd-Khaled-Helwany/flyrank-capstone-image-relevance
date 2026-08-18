from __future__ import annotations

import threading
import logging
from typing import MutableSequence

logger = logging.getLogger("call_logger")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

_lock = threading.Lock()
_calls: MutableSequence[dict] = []

def record_call(call_record: dict) -> None:
    """Store call metadata in-memory and emit a log line.

    This is intentionally lightweight — production should persist to DB.
    """
    with _lock:
        _calls.append(call_record.copy())
    logger.info("AI call: %s", call_record)

def get_calls() -> list[dict]:
    with _lock:
        return [c.copy() for c in _calls]

def clear_calls() -> None:
    with _lock:
        _calls.clear()

def summarize_by_image() -> dict:
    """Return a dict mapping image_id -> aggregated metrics."""
    out: dict = {}
    with _lock:
        for c in _calls:
            img = c.get("image_id") or "_none"
            bucket = out.setdefault(img, {"cost_usd": 0.0, "calls": 0, "total_tokens": 0, "duration_ms": 0})
            bucket["cost_usd"] += float(c.get("cost_usd", 0.0) or 0.0)
            bucket["calls"] += 1
            bucket["total_tokens"] += int(c.get("total_tokens", 0) or 0)
            bucket["duration_ms"] += int(c.get("duration_ms", 0) or 0)
    return out
