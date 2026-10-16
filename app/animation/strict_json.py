"""Strict bounded import parser for future external animation authoring."""
import json
from typing import Any
from app.animation.service import error

def parse_strict_document(text: str, max_bytes: int = 10_000_000) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        error("VALIDATION_FAILED", "External JSON must be a nonempty object", 422)
    if len(text.encode("utf-8")) > max_bytes:
        error("IMPORT_TOO_LARGE", "External JSON exceeds size limit", 413)
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        d = {}
        for key, value in pairs:
            if key in d:
                error("VALIDATION_FAILED", "Duplicate JSON key", 422, key=key)
            d[key] = value
        return d
    try:
        document = json.loads(text, object_pairs_hook=unique_object,
                              parse_constant=lambda value: error("VALIDATION_FAILED", "Nonfinite JSON number", 422))
    except json.JSONDecodeError:
        error("VALIDATION_FAILED", "Malformed external JSON", 422)
    if not isinstance(document, dict):
        error("VALIDATION_FAILED", "Expected JSON object", 422)
    return document
