"""Client implementation for the Ciralgo Platform API.

This file ships hand-written wrappers over the four public proxy
operations documented in the Ciralgo OpenAPI spec v1.1.0:

    POST  /v1/chat/completions
    POST  /v1/embeddings
    GET   /v1/usage
    POST  /anthropic/v1/messages

A codegen approach using `openapi-python-client` is a viable replacement
that produces fully typed dataclasses from the spec; the README documents
the migration path. The hand-written client gives us full control over
streaming semantics, error mapping, and retries without taking the
codegen toolchain as a hard dependency for every release.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterator, List, Optional, Union

import httpx

from ciralgo.errors import (
    AuthenticationError,
    CiralgoError,
    InternalError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    UpstreamError,
    ValidationError,
)

DEFAULT_BASE_URL = "https://api.ciralgo.com"
DEFAULT_TIMEOUT_SEC = 120
USER_AGENT = "ciralgo-python/1.1.0"


class _ChatCompletions:
    """Sub-resource for /v1/chat/completions.

    Accessed via `client.chat.completions.create(...)`.
    """

    def __init__(self, client: "Client") -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """Create a chat completion.

        Returns the JSON dict when stream=False. When stream=True, returns
        an iterator yielding the SSE chunks as decoded dicts. The final
        `data: [DONE]` sentinel is consumed by the iterator and ends it.
        """
        body: Dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream"] = True
            if stream_options is not None:
                body["stream_options"] = stream_options
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format is not None:
            body["response_format"] = response_format

        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if tags:
            headers["X-Ciralgo-Tags"] = ",".join(f"{k}={v}" for k, v in tags.items())

        if stream:
            return self._client._stream("POST", "/v1/chat/completions", body, headers)
        return self._client._request("POST", "/v1/chat/completions", body, headers)


class _Embeddings:
    """Sub-resource for /v1/embeddings."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        encoding_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model": model, "input": input}
        if encoding_format is not None:
            body["encoding_format"] = encoding_format
        return self._client._request("POST", "/v1/embeddings", body)


class _Usage:
    """Sub-resource for /v1/usage."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def get(
        self,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if group_by:
            params["group_by"] = group_by
        return self._client._request("GET", "/v1/usage", params=params)


class _Anthropic:
    """Sub-resource for /anthropic/v1/messages."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def messages_create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system is not None:
            body["system"] = system
        if tools is not None:
            body["tools"] = tools
        if stream:
            body["stream"] = True
            return self._client._stream("POST", "/anthropic/v1/messages", body)
        return self._client._request("POST", "/anthropic/v1/messages", body)


class _ChatNamespace:
    """`client.chat.completions.create(...)` plumbing."""

    def __init__(self, client: "Client") -> None:
        self.completions = _ChatCompletions(client)


class Client:
    """Synchronous Ciralgo client.

    Usage:

        from ciralgo import Client
        client = Client(api_key="sk-cg-...")
        r = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.api_key = api_key or os.environ.get("CIRALGO_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                code="missing_api_key",
                message=(
                    "No API key found. Pass api_key=... or set CIRALGO_API_KEY in the environment."
                ),
            )
        self.base_url = (base_url or os.environ.get("CIRALGO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._http = httpx.Client(timeout=timeout, headers=self._default_headers())
        self.chat = _ChatNamespace(self)
        self.embeddings = _Embeddings(self)
        self.usage = _Usage(self)
        self.anthropic = _Anthropic(self)

    # Sentinel close method for `with Client(...) as client:` patterns.
    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = self._http.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=extra_headers or None,
            )
        except httpx.TimeoutException as e:
            raise UpstreamError(
                code="upstream_timeout",
                message=f"Request timed out: {e}",
            ) from e
        return self._handle(resp)

    def _stream(
        self,
        method: str,
        path: str,
        json_body: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream SSE chunks from /v1/chat/completions or /anthropic/v1/messages.

        Yields decoded JSON chunks. Consumes and discards the `[DONE]`
        sentinel so the iterator ends naturally.
        """
        import json as _json

        url = f"{self.base_url}{path}"
        headers = dict(self._default_headers())
        headers["Accept"] = "text/event-stream"
        if extra_headers:
            headers.update(extra_headers)

        with self._http.stream(method, url, json=json_body, headers=headers) as resp:
            if resp.status_code >= 400:
                # Read the body, route through _handle for a typed error.
                body = resp.read()
                resp_for_handle = httpx.Response(
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=body,
                )
                self._handle(resp_for_handle)
                return  # _handle always raises

            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    return
                if not payload:
                    continue
                try:
                    yield _json.loads(payload)
                except Exception:
                    # Skip malformed chunks rather than crash the stream.
                    continue

    def _handle(self, resp: httpx.Response) -> Dict[str, Any]:
        """Map a finished httpx.Response to a body dict or a typed exception."""
        if 200 <= resp.status_code < 300:
            if not resp.content:
                return {}
            return resp.json()

        # Error path. Pull what we can from the standard envelope.
        try:
            body = resp.json()
        except Exception:
            body = {}

        err_obj = body.get("error") if isinstance(body, dict) else None
        code = (err_obj or {}).get("code", "unknown_error")
        message = (err_obj or {}).get("message", f"HTTP {resp.status_code}")
        trace_id = (err_obj or {}).get("trace_id") or resp.headers.get("X-Trace-Id")
        retry_after_raw = (err_obj or {}).get("retry_after") or resp.headers.get("Retry-After")
        try:
            retry_after = int(retry_after_raw) if retry_after_raw is not None else None
        except (TypeError, ValueError):
            retry_after = None

        kwargs = dict(code=code, message=message, trace_id=trace_id, status_code=resp.status_code, retry_after=retry_after)
        if resp.status_code == 400:
            raise ValidationError(**kwargs)
        if resp.status_code == 401:
            raise AuthenticationError(**kwargs)
        if resp.status_code == 403:
            raise PermissionError(**kwargs)
        if resp.status_code == 404:
            raise NotFoundError(**kwargs)
        if resp.status_code == 429:
            raise RateLimitError(**kwargs)
        if resp.status_code == 502:
            raise UpstreamError(**kwargs)
        if resp.status_code >= 500:
            raise InternalError(**kwargs)
        raise CiralgoError(**kwargs)


class AsyncClient:
    """Async sibling of Client. Same surface, async methods.

    Intentionally minimal in v1.1.0. Covers the same four operations. A
    follow-up release adds parity for streaming + retries.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        # Reuse the sync client's auth + URL resolution by constructing a
        # bare Client and copying its attributes. Avoids duplicating the
        # config logic until the async surface diverges.
        sync = Client(api_key=api_key, base_url=base_url, timeout=timeout)
        sync.close()
        self.api_key = sync.api_key
        self.base_url = sync.base_url
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers=sync._default_headers(),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
