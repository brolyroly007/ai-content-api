"""Google Gemini provider implementation."""

from collections.abc import AsyncIterator

import google.generativeai as genai
from loguru import logger

from providers.base import BaseProvider, GenerationResult, retry_with_backoff


class GeminiProvider(BaseProvider):
    """Google Gemini provider."""

    name = "gemini"
    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
        genai.configure(api_key=api_key)

    def _get_model(self, system_prompt: str = ""):
        """Get a configured Gemini model instance."""
        return genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt if system_prompt else None,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate content using Gemini API."""
        model = self._get_model(system_prompt)

        async def _call():
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            content = response.text or ""
            tokens_used = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                tokens_used = getattr(response.usage_metadata, "total_token_count", 0)

            return GenerationResult(
                content=content,
                provider=self.name,
                model=self.model_name,
                tokens_used=tokens_used,
                finish_reason="stop",
            )

        try:
            return await retry_with_backoff(_call)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Stream content using Gemini API."""
        try:
            model = self._get_model(system_prompt)
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                stream=True,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key)
