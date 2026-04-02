"""Ollama local LLM provider implementation."""

from collections.abc import AsyncIterator

import httpx
from loguru import logger

from providers.base import BaseProvider, GenerationResult, retry_with_backoff


class OllamaProvider(BaseProvider):
    """Ollama local LLM provider (Llama, Mistral, etc.)."""

    name = "ollama"
    models = ["llama3.2", "llama3.1", "mistral", "codellama", "phi3"]

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate content using Ollama API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        async def _call():
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                tokens_used = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

                return GenerationResult(
                    content=data.get("response", ""),
                    provider=self.name,
                    model=self.model,
                    tokens_used=tokens_used,
                    finish_reason="stop" if data.get("done") else "length",
                )

        try:
            return await retry_with_backoff(_call)
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Stream content using Ollama API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with (
                httpx.AsyncClient(timeout=120.0) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json

                        data = json.loads(line)
                        if data.get("response"):
                            yield data["response"]
                        if data.get("done"):
                            break
        except httpx.HTTPError as e:
            logger.error(f"Ollama streaming error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Ollama is reachable (best-effort sync check)."""
        try:
            import httpx as httpx_sync

            response = httpx_sync.get(f"{self.base_url}/api/tags", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False
