"""Unit tests for the Ciralgo Python SDK.

Uses `respx` to mock the HTTP layer. No live network calls. Tests cover:
  - construction (env var, explicit key, missing key)
  - chat.completions.create (success, error envelope mapping)
  - embeddings.create
  - usage.get
  - anthropic.messages_create
  - streaming chat completion
  - typed error hierarchy
"""

from typing import Iterator

import httpx
import pytest
import respx

from ciralgo import (
    AsyncClient,
    AuthenticationError,
    Client,
    InternalError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    UpstreamError,
    ValidationError,
    __version__,
)


# ── Construction ──────────────────────────────────────────────────────────


class TestConstruction:
    def test_explicit_api_key_wins(self):
        c = Client(api_key="sk-cg-explicit")
        assert c.api_key == "sk-cg-explicit"
        c.close()

    def test_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("CIRALGO_API_KEY", "sk-cg-from-env")
        c = Client()
        assert c.api_key == "sk-cg-from-env"
        c.close()

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("CIRALGO_API_KEY", raising=False)
        with pytest.raises(AuthenticationError) as exc:
            Client()
        assert exc.value.code == "missing_api_key"

    def test_custom_base_url(self):
        c = Client(api_key="sk-cg-test", base_url="https://staging.example/")
        # Trailing slash stripped.
        assert c.base_url == "https://staging.example"
        c.close()

    def test_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("CIRALGO_BASE_URL", "https://from-env.example")
        c = Client(api_key="sk-cg-test")
        assert c.base_url == "https://from-env.example"
        c.close()


# ── Chat completions ──────────────────────────────────────────────────────


class TestChatCompletions:
    @respx.mock
    def test_success(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "model": "openai/gpt-4o-mini",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hi"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                },
            )
        )
        c = Client(api_key="sk-cg-test")
        result = c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result["choices"][0]["message"]["content"] == "Hi"
        c.close()

    @respx.mock
    def test_carries_auth_header(self):
        route = respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": []})
        )
        c = Client(api_key="sk-cg-test")
        c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
        sent = route.calls[0].request
        assert sent.headers["Authorization"] == "Bearer sk-cg-test"
        c.close()

    @respx.mock
    def test_passes_optional_params(self):
        route = respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": []})
        )
        c = Client(api_key="sk-cg-test")
        c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.2,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        body = route.calls[0].request.content.decode()
        assert '"temperature":0.2' in body
        assert '"max_tokens":100' in body
        assert '"response_format":{"type":"json_object"}' in body
        c.close()

    @respx.mock
    def test_carries_idempotency_key(self):
        route = respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": []})
        )
        c = Client(api_key="sk-cg-test")
        c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            idempotency_key="abc-123",
        )
        assert route.calls[0].request.headers["Idempotency-Key"] == "abc-123"
        c.close()

    @respx.mock
    def test_carries_tags_header(self):
        route = respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"choices": []})
        )
        c = Client(api_key="sk-cg-test")
        c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            tags={"project": "test", "env": "ci"},
        )
        tag_header = route.calls[0].request.headers["X-Ciralgo-Tags"]
        assert "project=test" in tag_header
        assert "env=ci" in tag_header
        c.close()


# ── Streaming ─────────────────────────────────────────────────────────────


class TestStreaming:
    @respx.mock
    def test_yields_chunks_and_stops_on_done(self):
        sse_body = (
            'data: {"choices":[{"delta":{"content":"He"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=sse_body, headers={"Content-Type": "text/event-stream"})
        )
        c = Client(api_key="sk-cg-test")
        result = c.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        assert isinstance(result, Iterator)
        chunks = list(result)
        assert len(chunks) == 2
        assert chunks[0]["choices"][0]["delta"]["content"] == "He"
        assert chunks[1]["choices"][0]["delta"]["content"] == "llo"
        c.close()


# ── Embeddings ────────────────────────────────────────────────────────────


class TestEmbeddings:
    @respx.mock
    def test_single_input(self):
        respx.post("https://api.ciralgo.com/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]},
            )
        )
        c = Client(api_key="sk-cg-test")
        r = c.embeddings.create(model="openai/text-embedding-3-small", input="hello")
        assert len(r["data"][0]["embedding"]) == 3
        c.close()

    @respx.mock
    def test_batch_input(self):
        route = respx.post("https://api.ciralgo.com/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        c = Client(api_key="sk-cg-test")
        c.embeddings.create(
            model="openai/text-embedding-3-small",
            input=["one", "two", "three"],
        )
        body = route.calls[0].request.content.decode()
        assert '"input":["one","two","three"]' in body
        c.close()


# ── Usage ─────────────────────────────────────────────────────────────────


class TestUsage:
    @respx.mock
    def test_returns_usage_body(self):
        respx.get("https://api.ciralgo.com/v1/usage").mock(
            return_value=httpx.Response(
                200,
                json={"total_cost_usd": 4.20, "calls": 100, "from": "2026-06-01", "to": "2026-06-30"},
            )
        )
        c = Client(api_key="sk-cg-test")
        r = c.usage.get(from_date="2026-06-01", to_date="2026-06-30")
        assert r["total_cost_usd"] == 4.20
        c.close()


# ── Anthropic Messages ────────────────────────────────────────────────────


class TestAnthropicMessages:
    @respx.mock
    def test_messages_create(self):
        route = respx.post("https://api.ciralgo.com/anthropic/v1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "msg_test",
                    "content": [{"type": "text", "text": "hi"}],
                },
            )
        )
        c = Client(api_key="sk-cg-test")
        r = c.anthropic.messages_create(
            model="anthropic/claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": "hello"}],
        )
        assert r["content"][0]["text"] == "hi"
        body = route.calls[0].request.content.decode()
        assert '"max_tokens":100' in body
        c.close()


# ── Error mapping ─────────────────────────────────────────────────────────


class TestErrorMapping:
    @respx.mock
    def test_400_maps_to_ValidationError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                400,
                json={
                    "ok": False,
                    "error": {"code": "bad_request", "message": "nope", "trace_id": "req_1"},
                },
            )
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(ValidationError) as exc:
            c.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": "hi"}],
            )
        assert exc.value.code == "bad_request"
        assert exc.value.status_code == 400
        assert exc.value.trace_id == "req_1"
        c.close()

    @respx.mock
    def test_401_maps_to_AuthenticationError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"ok": False, "error": {"code": "auth", "message": "no"}})
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(AuthenticationError):
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        c.close()

    @respx.mock
    def test_403_maps_to_PermissionError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(403, json={"ok": False, "error": {"code": "forbidden", "message": "no"}})
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(PermissionError):
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        c.close()

    @respx.mock
    def test_404_maps_to_NotFoundError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(404, json={"ok": False, "error": {"code": "not_found", "message": "no"}})
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(NotFoundError):
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        c.close()

    @respx.mock
    def test_429_maps_to_RateLimitError_with_retry_after(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                429,
                json={
                    "ok": False,
                    "error": {"code": "rate_limit_exceeded", "message": "slow down", "retry_after": 30},
                },
            )
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(RateLimitError) as exc:
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        assert exc.value.retry_after == 30
        c.close()

    @respx.mock
    def test_502_maps_to_UpstreamError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(502, json={"ok": False, "error": {"code": "upstream", "message": "no"}})
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(UpstreamError):
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        c.close()

    @respx.mock
    def test_503_maps_to_InternalError(self):
        respx.post("https://api.ciralgo.com/v1/chat/completions").mock(
            return_value=httpx.Response(503, json={"ok": False, "error": {"code": "internal", "message": "no"}})
        )
        c = Client(api_key="sk-cg-test")
        with pytest.raises(InternalError):
            c.chat.completions.create(model="x", messages=[{"role": "user", "content": "h"}])
        c.close()


# ── Context manager ──────────────────────────────────────────────────────


class TestContextManager:
    def test_with_block_closes_client(self):
        with Client(api_key="sk-cg-test") as c:
            assert c.api_key == "sk-cg-test"
        # No assertion needed (close() must not raise).


# ── AsyncClient (minimal) ────────────────────────────────────────────────


class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_construction(self):
        async with AsyncClient(api_key="sk-cg-test") as c:
            assert c.api_key == "sk-cg-test"


# ── Package metadata ──────────────────────────────────────────────────────


class TestPackageMetadata:
    def test_version_string(self):
        assert __version__ == "1.1.0"
