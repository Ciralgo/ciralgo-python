# Ciralgo Python SDK

Official Python SDK for the [Ciralgo Platform API](https://www.ciralgo.com).

Version: `1.1.0` (mirrors `openapi.json info.version`).

## Install

```bash
pip install ciralgo
```

Requires Python 3.9+.

## Quickstart

```python
from ciralgo import Client

client = Client(api_key="sk-cg-...")  # or set CIRALGO_API_KEY in your env

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello."}],
)
print(response["choices"][0]["message"]["content"])
```

## Authentication

The SDK reads the API key from (in order):

1. The `api_key=` argument to `Client(...)` or `AsyncClient(...)`.
2. The `CIRALGO_API_KEY` environment variable.

If neither is set, `AuthenticationError` is raised at construction time.

The optional `CIRALGO_BASE_URL` env var overrides the default `https://api.ciralgo.com`. This is useful for staging or for self-hosted Ciralgo deployments.

## Endpoints

The four public proxy operations from the Ciralgo OpenAPI spec (v1.1.0):

### Chat completions

```python
response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-6",
    messages=[
        {"role": "system", "content": "You are a finance compliance assistant."},
        {"role": "user", "content": "Summarise EU AI Act Article 15."},
    ],
    temperature=0.2,
    max_tokens=400,
    tags={"project": "ai-act-summariser", "env": "prod"},
)
```

### Streaming chat completions

```python
for chunk in client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Stream me a haiku."}],
    stream=True,
):
    delta = chunk["choices"][0]["delta"].get("content", "")
    print(delta, end="", flush=True)
```

### Embeddings

```python
embedding = client.embeddings.create(
    model="openai/text-embedding-3-small",
    input="EU AI Act Article 15 covers accuracy, robustness and cybersecurity.",
)
print(len(embedding["data"][0]["embedding"]))  # → vector dimension
```

### Usage

```python
usage = client.usage.get(from_date="2026-06-01", to_date="2026-06-30")
print(usage["total_cost_usd"], usage["calls"])
```

### Anthropic Messages

```python
response = client.anthropic.messages_create(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=400,
    system="You are an EU compliance assistant.",
    messages=[{"role": "user", "content": "What is GDPR Article 32?"}],
)
print(response["content"][0]["text"])
```

## Error handling

The SDK maps HTTP status codes to typed exceptions. Catch the specific class:

```python
from ciralgo import Client
from ciralgo.errors import RateLimitError, UpstreamError, AuthenticationError

try:
    response = client.chat.completions.create(...)
except RateLimitError as e:
    time.sleep(e.retry_after or 5)
    # retry
except UpstreamError as e:
    # upstream LLM provider 5xx, pick a different model
    ...
except AuthenticationError:
    # rotate / re-issue the key
    raise
```

Every exception carries:

- `code`: stable string error code from the API envelope (e.g. `rate_limit_exceeded`)
- `message`: human-readable
- `trace_id`: pass this to Ciralgo support to look up the request server-side
- `status_code`: HTTP status
- `retry_after`: only set on 429

## Async

```python
import asyncio
from ciralgo import AsyncClient

async def main():
    async with AsyncClient() as client:
        # NOTE: async surface in v1.1.0 is the client construction +
        # close lifecycle. Full async parity for chat / embeddings ships
        # in v1.2.0.
        pass

asyncio.run(main())
```

## Migration to a codegen client

The current client is hand-written. A codegen-based replacement is
viable using [openapi-python-client](https://github.com/openapi-generators/openapi-python-client)
against the published Ciralgo OpenAPI spec. The hand-written client
gives us control over:

- Streaming semantics (`stream=True` returning an iterator).
- The `X-Ciralgo-Tags` header marshalling.
- The typed exception hierarchy (codegen produces a single error class).

A future major bump (`v2.0.0`) can switch to codegen if the trade-offs
change.

## Development

From the SDK repo root:

```bash
pip install -e ".[dev]"
pytest
ruff check src
mypy src
```

## Publishing

Publishing to PyPI is handled by a GitHub Actions workflow triggered on
tags of the form `sdk-py-v*`. The workflow uses PyPI Trusted Publishing
(OIDC). No long-lived API token is stored in CI secrets.

The engineer-facing release runbook (version bump, tag push, environment
approval, troubleshooting) is at [docs/publish-runbook.md](docs/publish-runbook.md).

## License

Apache-2.0
