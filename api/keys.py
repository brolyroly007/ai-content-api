"""API key management endpoints."""

from fastapi import APIRouter, HTTPException, Query

from database.repositories import (
    _hash_key,
    create_api_key,
    delete_api_key,
    get_recent_content,
    get_usage_stats,
    list_api_keys,
    validate_api_key,
)

router = APIRouter()


@router.post("/keys")
async def create_key(
    name: str = Query(..., description="A name to identify this API key"),
    rate_limit: int = Query(60, description="Requests per minute"),
    daily_limit: int = Query(1000, description="Requests per day"),
):
    """Create a new API key. The plain key is shown only once in this response."""
    result = await create_api_key(name, rate_limit, daily_limit)
    result["warning"] = "Store this key securely. It will not be shown again."
    return result


@router.get("/keys")
async def get_keys():
    """List all API keys (masked for security)."""
    keys = await list_api_keys()
    return {"keys": keys}


@router.get("/keys/{key}/usage")
async def get_key_usage(key: str):
    """Get usage statistics for an API key."""
    key_data = await validate_api_key(key)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")
    # Usage logs store the hashed key, so query with the hash
    key_hash = _hash_key(key)
    stats = await get_usage_stats(key_hash)
    stats["key_name"] = key_data["name"]
    stats["rate_limit"] = key_data["rate_limit"]
    stats["daily_limit"] = key_data["daily_limit"]
    return stats


@router.get("/keys/{key}/history")
async def get_key_history(key: str, limit: int = Query(10, ge=1, le=100)):
    """Get recent generated content for an API key."""
    key_data = await validate_api_key(key)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")
    # Content records store the hashed key, so query with the hash
    key_hash = _hash_key(key)
    history = await get_recent_content(key_hash, limit)
    return {"history": history}


@router.delete("/keys/{key}")
async def deactivate_key(key: str):
    """Deactivate an API key."""
    success = await delete_api_key(key)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key deactivated"}
