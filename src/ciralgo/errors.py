"""Typed error hierarchy mirroring the OpenAPI ErrorResponse envelope.

Every API error from Ciralgo carries the shape:

    {
      "ok": false,
      "error": {
        "code": "<stable_code>",
        "message": "<human readable>",
        "trace_id": "<request id>",
        "retry_after": <seconds, only on 429>
      }
    }

The client maps HTTP status codes to one of these exception classes so
customer code can catch the specific class rather than parsing the
envelope by hand:

    try:
        client.chat.completions.create(...)
    except RateLimitError as e:
        time.sleep(e.retry_after or 5)
        # retry
    except UpstreamError as e:
        # upstream LLM provider returned 5xx, try a different model
        ...
"""

from __future__ import annotations

from typing import Optional


class CiralgoError(Exception):
    """Base class for every Ciralgo SDK error.

    Carries the API-level error code, the human message, the trace_id for
    support correlation, and the raw HTTP status code.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        trace_id: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.status_code = status_code
        self.retry_after = retry_after


class ValidationError(CiralgoError):
    """4xx: request shape rejected by the server (400)."""


class AuthenticationError(CiralgoError):
    """401: invalid or missing API key."""


class PermissionError(CiralgoError):
    """403: caller does not have permission (tenant policy, admin MFA, etc.)."""


class NotFoundError(CiralgoError):
    """404: resource does not exist or is not visible to this caller."""


class RateLimitError(CiralgoError):
    """429: per-key / per-org RPM or TPM limit exceeded.

    The `retry_after` attribute is set when the server provided one.
    """


class UpstreamError(CiralgoError):
    """502: upstream LLM provider returned an error or timed out."""


class InternalError(CiralgoError):
    """5xx: unexpected server-side error. Retry with exponential backoff."""
