"""Abstract base class for LLM providers."""

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from loguru import logger


@dataclass
class GenerationResult:
    """Result from an LLM generation call."""

    content: str
    provider: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"


async def retry_with_backoff(coro_factory, max_retries=3, base_delay=1.0):
    """Retry an async operation with exponential backoff.

    Args:
        coro_factory: A callable that returns a new coroutine each call.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds (doubled each attempt).

    Returns:
        The result of the coroutine.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc):
                raise
            if attempt == max_retries:
                logger.error(f"All {max_retries} retries exhausted: {exc}")
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1.0)
            logger.warning(
                f"Transient error (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.1f}s: {exc}"
            )
            await asyncio.sleep(delay)
    raise last_exc  # unreachable, but satisfies type checkers


def _is_transient(exc: Exception) -> bool:
    """Return True if the exception looks transient and worth retrying."""
    # OpenAI SDK errors
    try:
        import openai

        if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError,
                            openai.APITimeoutError, openai.InternalServerError)):
            return True
        if isinstance(exc, openai.APIError) and not isinstance(
            exc, (openai.AuthenticationError, openai.BadRequestError,
                  openai.PermissionDeniedError, openai.NotFoundError)
        ):
            return True
    except ImportError:
        pass

    # httpx errors (used by Ollama)
    try:
        import httpx

        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
            return True
    except ImportError:
        pass

    # google.generativeai / google.api_core errors
    try:
        from google.api_core.exceptions import GoogleAPIError, ServiceUnavailable, TooManyRequests

        if isinstance(exc, (ServiceUnavailable, TooManyRequests)):
            return True
        if isinstance(exc, GoogleAPIError) and getattr(exc, "code", 0) >= 500:
            return True
    except ImportError:
        pass

    # Generic network / timeout fallback
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    return False


class BaseProvider(ABC):
    """Abstract interface that all LLM providers implement."""

    name: str = ""
    models: list[str] = []

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate content (non-streaming)."""
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Generate content as a stream of text chunks."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...

    def info(self) -> dict:
        """Return provider metadata."""
        return {
            "name": self.name,
            "models": self.models,
            "available": self.is_available(),
        }
