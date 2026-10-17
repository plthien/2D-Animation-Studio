"""One authoritative strict JSON parser shared by HTTP C2 and future imports."""
from __future__ import annotations

import json
import math
from typing import Any

from app.animation.service import error


def parse_strict_document(text: str, max_bytes: int = 10_000_000) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        error("VALIDATION_FAILED", "Request validation failed", 422)
    try:
        length = len(text.encode("utf-8", errors="strict"))
    except UnicodeError:
        error("VALIDATION_FAILED", "Request validation failed", 422)
    if length > max_bytes:
        error("IMPORT_TOO_LARGE", "External JSON exceeds size limit", 413)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                error("VALIDATION_FAILED", "Request validation failed", 422,
                      issues=[{"path": key, "message": "Duplicate JSON key"}])
            result[key] = value
        return result

    def checked_float(raw: str) -> float:
        value = float(raw)
        if not math.isfinite(value):
            error("VALIDATION_FAILED", "Request validation failed", 422)
        return value

    def reject_nonfinite(_raw: str) -> None:
        error("VALIDATION_FAILED", "Request validation failed", 422)

    try:
        document = json.loads(
            text, object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite, parse_float=checked_float,
        )
    except (json.JSONDecodeError, ValueError, OverflowError, RecursionError):
        error("VALIDATION_FAILED", "Request validation failed", 422)
    if not isinstance(document, dict):
        error("VALIDATION_FAILED", "Request validation failed", 422)
    return document
