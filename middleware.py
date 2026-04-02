"""API key authentication and rate limiting."""

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from config import settings
from database.repositories import check_rate_limit, validate_api_key

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str | None = Depends(API_KEY_HEADER)) -> dict:
    """FastAPI dependency that validates the API key from X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Include X-API-Key header.")

    # Allow master key
    if settings.master_api_key and api_key == settings.master_api_key:
        return {
            "key": api_key,
            "name": "master",
            "rate_limit": 9999,
            "daily_limit": 999999,
        }

    key_data = await validate_api_key(api_key)
    if not key_data:
        raise HTTPException(status_code=403, detail="Invalid or deactivated API key.")

    # Use the stored hash (key_data["key"]) for rate limit lookup, since
    # usage_logs now stores the hashed key as the identifier.
    within_limits = await check_rate_limit(
        key_data["key"], key_data["rate_limit"], key_data["daily_limit"]
    )
    if not within_limits:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    return key_data
