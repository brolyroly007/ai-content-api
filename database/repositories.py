"""CRUD operations for all database tables."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta

from database.connection import get_db


def _hash_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()

# ── API Keys ──────────────────────────────────────────────


async def create_api_key(name: str, rate_limit: int = 60, daily_limit: int = 1000) -> dict:
    """Create a new API key. Returns the plain key (shown only once) but stores only the hash."""
    plain_key = f"ak_{secrets.token_hex(24)}"
    key_hash = _hash_key(plain_key)
    key_prefix = plain_key[:8]
    db = await get_db()
    await db.execute(
        "INSERT INTO api_keys (key, key_prefix, name, rate_limit, daily_limit) "
        "VALUES (?, ?, ?, ?, ?)",
        (key_hash, key_prefix, name, rate_limit, daily_limit),
    )
    await db.commit()
    return {
        "key": plain_key,
        "name": name,
        "rate_limit": rate_limit,
        "daily_limit": daily_limit,
    }


async def validate_api_key(key: str) -> dict | None:
    """Validate an API key and return its data. Hashes the incoming key before lookup."""
    key_hash = _hash_key(key)
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM api_keys WHERE key = ? AND is_active = 1", (key_hash,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_api_keys() -> list[dict]:
    """List all API keys (showing only the prefix for security)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, key_prefix || '...' as key_preview, name, "
        "rate_limit, daily_limit, is_active, created_at FROM api_keys ORDER BY id DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def delete_api_key(key: str) -> bool:
    """Deactivate an API key. Accepts the plain key and hashes before lookup."""
    key_hash = _hash_key(key)
    db = await get_db()
    cursor = await db.execute("UPDATE api_keys SET is_active = 0 WHERE key = ?", (key_hash,))
    await db.commit()
    return cursor.rowcount > 0


# ── Usage Logging ─────────────────────────────────────────


async def log_usage(api_key: str, template_id: str, provider: str, tokens_used: int):
    """Log an API usage event."""
    db = await get_db()
    await db.execute(
        "INSERT INTO usage_logs (api_key, template_id, provider, tokens_used) "
        "VALUES (?, ?, ?, ?)",
        (api_key, template_id, provider, tokens_used),
    )
    await db.commit()


async def get_usage_stats(api_key: str) -> dict:
    """Get usage statistics for an API key."""
    db = await get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Today's request count
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM usage_logs WHERE api_key = ? AND date(created_at) = ?",
        (api_key, today),
    )
    row = await cursor.fetchone()
    today_requests = row["count"] if row else 0

    # Today's tokens
    cursor = await db.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) as total FROM usage_logs "
        "WHERE api_key = ? AND date(created_at) = ?",
        (api_key, today),
    )
    row = await cursor.fetchone()
    today_tokens = row["total"] if row else 0

    # Total requests
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM usage_logs WHERE api_key = ?",
        (api_key,),
    )
    row = await cursor.fetchone()
    total_requests = row["count"] if row else 0

    # Total tokens
    cursor = await db.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) as total FROM usage_logs WHERE api_key = ?",
        (api_key,),
    )
    row = await cursor.fetchone()
    total_tokens = row["total"] if row else 0

    # Provider breakdown
    cursor = await db.execute(
        "SELECT provider, COUNT(*) as count FROM usage_logs "
        "WHERE api_key = ? GROUP BY provider",
        (api_key,),
    )
    rows = await cursor.fetchall()
    by_provider = {row["provider"]: row["count"] for row in rows}

    # Template breakdown
    cursor = await db.execute(
        "SELECT template_id, COUNT(*) as count FROM usage_logs "
        "WHERE api_key = ? GROUP BY template_id ORDER BY count DESC LIMIT 5",
        (api_key,),
    )
    rows = await cursor.fetchall()
    top_templates = {row["template_id"]: row["count"] for row in rows}

    return {
        "today": {"requests": today_requests, "tokens": today_tokens},
        "total": {"requests": total_requests, "tokens": total_tokens},
        "by_provider": by_provider,
        "top_templates": top_templates,
    }


# ── Rate Limiting ─────────────────────────────────────────


async def check_rate_limit(api_key: str, rate_limit: int, daily_limit: int) -> bool:
    """Check if the API key is within rate limits. Returns True if allowed."""
    db = await get_db()
    # Check per-minute rate
    one_minute_ago = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM usage_logs WHERE api_key = ? AND created_at >= ?",
        (api_key, one_minute_ago),
    )
    row = await cursor.fetchone()
    if row and row["count"] >= rate_limit:
        return False

    # Check daily limit
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM usage_logs WHERE api_key = ? AND date(created_at) = ?",
        (api_key, today),
    )
    row = await cursor.fetchone()
    return not (row and row["count"] >= daily_limit)


# ── Generated Content ─────────────────────────────────────


async def save_generated_content(
    api_key: str,
    template_id: str,
    provider: str,
    input_data: dict,
    output_content: str,
    tokens_used: int,
) -> int:
    """Save generated content and return its ID."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO generated_content "
        "(api_key, template_id, provider, input_data, output_content, tokens_used) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (api_key, template_id, provider, json.dumps(input_data), output_content, tokens_used),
    )
    await db.commit()
    return cursor.lastrowid


async def get_recent_content(api_key: str, limit: int = 10) -> list[dict]:
    """Get recent generated content for an API key."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, template_id, provider, tokens_used, created_at "
        "FROM generated_content WHERE api_key = ? ORDER BY id DESC LIMIT ?",
        (api_key, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_content_by_id(content_id: int) -> dict | None:
    """Get a specific generated content by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM generated_content WHERE id = ?", (content_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None
