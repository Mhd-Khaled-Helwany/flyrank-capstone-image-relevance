from __future__ import annotations

import os
import time
from typing import Any

def call_gemini_for_tag(prompt: str, model: str = "gemini-flash", timeout: int = 60, *, image_bytes: bytes | None = None) -> dict[str, Any]:
    """Call the Gemini model through the Google GenAI SDK and return metrics."""
    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "google.genai is not installed or not importable. Install it and configure credentials."
        ) from exc

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No Gemini API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment.")

    client = genai.Client(api_key=api_key)
    start = time.time()
    
    # Build content: image (if provided) + text prompt
    if image_bytes:
        import base64
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
                ]
            }
        ]
    else:
        contents = prompt
    
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_schema": None,
        },
    )
    duration_ms = int((time.time() - start) * 1000)

    output_text = getattr(resp, "text", None)
    if output_text is None:
        try:
            output_text = resp.candidates[0].content.parts[0].text
        except Exception:
            output_text = str(resp)

    usage = getattr(resp, "usage_metadata", None)
    input_tokens = 0
    output_tokens = 0
    if usage is not None:
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "completion_token_count", 0) or 0)

    in_cost, out_cost = 0.000075, 0.0003
    cost_usd = (input_tokens * in_cost + output_tokens * out_cost) / 1000.0

    return {
        "value": output_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "model_name": model,
        "model_version": model,
        "cost_usd": cost_usd,
    }
