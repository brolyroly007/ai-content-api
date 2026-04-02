"""Content generation endpoint with SSE streaming support."""

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, field_validator

from database.repositories import log_usage, save_generated_content
from export import export_content
from middleware import get_api_key
from providers import get_provider
from config import settings
from templates import get_template

router = APIRouter()


class GenerateRequest(BaseModel):
    """Request body for content generation."""

    template_id: str
    variables: dict[str, str] = {}
    provider: str | None = None
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 2000
    export_format: str = "markdown"

    @field_validator("template_id")
    @classmethod
    def template_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("template_id must not be empty")
        return v.strip()

    @field_validator("variables")
    @classmethod
    def validate_variable_values(cls, v: dict[str, str]) -> dict[str, str]:
        for key, val in v.items():
            if not isinstance(val, str):
                raise ValueError(
                    f"Variable '{key}' must be a string, got {type(val).__name__}"
                )
            if len(val) > 5000:
                raise ValueError(
                    f"Variable '{key}' exceeds max length of 5000 characters "
                    f"({len(val)} chars)"
                )
        return v


@router.post("/generate")
async def generate_content(req: GenerateRequest, api_key: dict = Depends(get_api_key)):
    """Generate content from a template using the specified LLM provider."""
    # Validate template
    try:
        template = get_template(req.template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    # Validate variables against template fields
    valid_field_names = {f.name for f in template.fields}
    unknown_keys = set(req.variables.keys()) - valid_field_names
    if unknown_keys:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown variables for template '{template.id}': {sorted(unknown_keys)}. "
            f"Valid fields: {sorted(valid_field_names)}",
        )

    missing_required = [
        f.name for f in template.fields if f.required and f.name not in req.variables
    ]
    if missing_required:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required fields for template '{template.id}': {sorted(missing_required)}",
        )

    # Build prompt from template
    variables_with_defaults = {}
    for field in template.fields:
        variables_with_defaults[field.name] = req.variables.get(field.name, field.default or "")
    try:
        prompt = template.user_prompt_template.format(**variables_with_defaults)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing template variable: {e}") from None

    # Get provider
    try:
        provider = get_provider(req.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    logger.info(
        f"Generating content: template={req.template_id}, "
        f"provider={provider.name}, stream={req.stream}"
    )

    # Streaming response
    if req.stream:
        return StreamingResponse(
            _stream_generation(provider, prompt, template.system_prompt, api_key, req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Regular response
    try:
        result = await provider.generate(
            prompt,
            system_prompt=template.system_prompt,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}") from e

    # Log usage
    await log_usage(api_key["key"], req.template_id, provider.name, result.tokens_used)
    await save_generated_content(
        api_key["key"],
        req.template_id,
        provider.name,
        req.variables,
        result.content,
        result.tokens_used,
    )

    # Export format
    output = export_content(result.content, req.export_format)

    return {
        "content": output,
        "provider": result.provider,
        "model": result.model,
        "tokens_used": result.tokens_used,
        "template_id": req.template_id,
        "export_format": req.export_format,
    }


async def _stream_generation(provider, prompt, system_prompt, api_key, req):
    """SSE generator for streaming responses."""
    full_content = []
    start = time.monotonic()
    timeout = settings.stream_timeout
    try:
        async for chunk in provider.stream(
            prompt,
            system_prompt=system_prompt,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        ):
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                logger.warning(f"Stream timeout after {elapsed:.1f}s (limit={timeout}s)")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Stream timeout exceeded'})}\n\n"
                return
            full_content.append(chunk)
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        # Log after stream completes
        content = "".join(full_content)
        tokens_estimate = len(content) // 4
        await log_usage(api_key["key"], req.template_id, provider.name, tokens_estimate)
        await save_generated_content(
            api_key["key"],
            req.template_id,
            provider.name,
            req.variables,
            content,
            tokens_estimate,
        )
        yield f"data: {json.dumps({'done': True, 'tokens_used': tokens_estimate})}\n\n"
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
