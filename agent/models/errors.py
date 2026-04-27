class ModelClientError(RuntimeError):
    """Raised when a model provider request fails."""


class ModelRateLimitError(ModelClientError):
    """HTTP 429 — should retry with backoff."""


class ModelServerError(ModelClientError):
    """HTTP 5xx — should retry with backoff."""


class ModelAuthError(ModelClientError):
    """HTTP 401/403 — do not retry."""


class ModelContextWindowError(ModelClientError):
    """Context window or token limit exceeded — trigger truncation."""


class ModelTimeoutError(ModelClientError):
    """Request or connection timed out — should retry."""


class ModelBadRequestError(ModelClientError):
    """HTTP 400 (other) — do not retry."""
