"""Neutral provider boundary errors, no legacy web runtime dependency."""
from typing import Any

class ProviderTransportError(Exception):
    def __init__(self, code: str, message: str, status_code: int,
                 *, retryable: bool = False, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
