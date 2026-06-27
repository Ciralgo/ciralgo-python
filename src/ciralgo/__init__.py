"""Official Python SDK for the Ciralgo Platform API.

Quick start:

    from ciralgo import Client

    client = Client(api_key="sk-cg-...")
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response["choices"][0]["message"]["content"])

The SDK is a thin, typed wrapper over the public proxy surface documented
at https://docs.ciralgo.com. Same authentication, same error envelope.
See the examples/ directory for chat, embeddings, usage, and Anthropic
Messages examples.

The package version mirrors `openapi.json info.version`. Bumping the API
spec triggers a coordinated SDK release.
"""

from ciralgo.client import Client, AsyncClient
from ciralgo.errors import (
    CiralgoError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    UpstreamError,
    InternalError,
)

__version__ = "1.1.0"

__all__ = [
    "Client",
    "AsyncClient",
    "CiralgoError",
    "AuthenticationError",
    "PermissionError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "UpstreamError",
    "InternalError",
    "__version__",
]
