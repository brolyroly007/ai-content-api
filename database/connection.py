"""SQLite connection manager using aiosqlite."""

from pathlib import Path

import aiosqlite
from loguru import logger

from config import settings

DB_PATH = Path(settings.database_url.replace("sqlite:///", ""))

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    key_prefix TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    rate_limit INTEGER DEFAULT 60,
    daily_limit INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT NOT NULL,
    template_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT NOT NULL,
    template_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_data TEXT NOT NULL,
    output_content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_key ON usage_logs(api_key);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_content_key ON generated_content(api_key);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database schema."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        # Migration: add key_prefix column if missing (existing databases)
        cursor = await db.execute("PRAGMA table_info(api_keys)")
        columns = {row["name"] for row in await cursor.fetchall()}
        if "key_prefix" not in columns:
            await db.execute(
                "ALTER TABLE api_keys ADD COLUMN key_prefix TEXT NOT NULL DEFAULT ''"
            )
        await db.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        await db.close()
