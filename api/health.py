"""Health check endpoint."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger

from database import get_db
from providers import list_providers

router = APIRouter()

VERSION = "1.0.0"


async def _check_database() -> dict:
    """Check database connectivity with a simple query."""
    try:
        db = await get_db()
        try:
            await db.execute("SELECT 1")
            return {"status": "up"}
        finally:
            await db.close()
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return {"status": "down", "error": str(exc)}


def _check_providers() -> dict:
    """Check each configured provider's availability."""
    results = {}
    for info in list_providers():
        name = info["name"]
        results[name] = {
            "status": "up" if info["available"] else "down",
            "models": info["models"],
        }
    return results


@router.get("/health")
async def health_check():
    """System health check with per-component status."""
    db_check = await _check_database()
    provider_checks = _check_providers()

    db_up = db_check["status"] == "up"
    any_provider_down = any(p["status"] == "down" for p in provider_checks.values())

    if not db_up:
        status = "unhealthy"
    elif any_provider_down:
        status = "degraded"
    else:
        status = "healthy"

    body = {
        "status": status,
        "checks": {
            "database": db_check,
            "providers": provider_checks,
        },
        "version": VERSION,
    }

    status_code = 503 if status == "unhealthy" else 200
    return JSONResponse(content=body, status_code=status_code)
