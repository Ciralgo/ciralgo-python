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

from importlib import metadata as _metadata

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

try:
    __version__ = _metadata.version("ciralgo")
except _metadata.PackageNotFoundError:
    # Package is not installed (running from a checkout without pip install -e).
    __version__ = "0.0.0+unknown"

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
